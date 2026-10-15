"""
Fase 1 – scarica i dati grezzi Porsche (solo HTTP, nessun browser necessario).

Per ogni modello salva in <out>/raw/<codice>/:
  configurator.json    – dati del configuratore (optional, prezzi, categorie), decodificati dal turbo-stream
  technical_data.json  – scheda tecnica completa (API porsche.com)
  standard_equipment.json – equipaggiamento di serie (API porsche.com)
e in <out>/models_overview.json l'elenco modelli con prezzo base, carrozzeria, trazione, ecc.

Uso:
  python scrape.py --locale it-IT --market italy --out data
  python scrape.py --models 992142,982850
"""
import argparse
import json
import re
import time
from pathlib import Path

import requests

from astroprops import islands
from turbostream import decode, stream_from_html

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36")
CONFIGURATOR = "https://configurator.porsche.com/{locale}/mode/model/{code}"
MODELS_PAGE = "https://www.porsche.com/{market}/models/"
API = "https://www.porsche.com/pcom-model-pages-isr/api/{locale}/{kind}/{code}/"


def get(session, url, retries=3):
    for attempt in range(retries):
        try:
            r = session.get(url, timeout=60)
            if r.status_code == 404:
                return None
            r.raise_for_status()
            r.encoding = "utf-8"
            return r
        except requests.RequestException as e:
            if attempt == retries - 1:
                print(f"    ! {url}: {e}")
                return None
            time.sleep(2 ** (attempt + 1))


def models_overview(session, market):
    """Modelli dalla pagina /models/: dict codice -> record (prezzo, carrozzeria, potenza, ...)."""
    r = get(session, MODELS_PAGE.format(market=market))
    found = {}

    def walk(o):
        if isinstance(o, dict):
            m = o.get("model")
            if isinstance(m, dict) and "modelType" in m:
                found.setdefault(m["modelType"], o)
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    for props in islands(r.text):
        walk(props)
    codes = set(re.findall(r"configurator\.porsche\.com/[a-zA-Z-]+/mode/model/([A-Za-z0-9]+)", r.text))
    return found, sorted(codes | set(found))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--locale", default="it-IT")
    ap.add_argument("--market", default="italy", help="segmento URL di porsche.com (italy, germany, ...)")
    ap.add_argument("--out", default="data")
    ap.add_argument("--models", help="codici modello separati da virgola (default: tutti)")
    ap.add_argument("--delay", type=float, default=1.5, help="pausa tra richieste (s)")
    args = ap.parse_args()

    out = Path(args.out)
    (out / "raw").mkdir(parents=True, exist_ok=True)
    s = requests.Session()
    s.headers.update({"User-Agent": UA, "Accept-Language": args.locale})

    overview, codes = models_overview(s, args.market)
    (out / "models_overview.json").write_text(json.dumps(overview, ensure_ascii=False, indent=1))
    if args.models:
        codes = args.models.split(",")
    print(f"Modelli da scaricare: {len(codes)}")

    for i, code in enumerate(codes, 1):
        dest = out / "raw" / code
        dest.mkdir(exist_ok=True)
        print(f"[{i}/{len(codes)}] {code}")
        r = get(s, CONFIGURATOR.format(locale=args.locale, code=code))
        if r is not None:
            try:
                data = decode(stream_from_html(r.text))["loaderData"]
                (dest / "configurator.json").write_text(json.dumps(data, ensure_ascii=False, default=str))
            except Exception as e:
                print(f"    ! configuratore non decodificabile: {e}")
        time.sleep(args.delay)
        for kind, fname in (("technical-data", "technical_data.json"),
                            ("standard-equipment", "standard_equipment.json")):
            r = get(s, API.format(locale=args.locale, kind=kind, code=code))
            if r is not None:
                (dest / fname).write_text(r.text)
            time.sleep(args.delay)


if __name__ == "__main__":
    main()
