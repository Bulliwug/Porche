"""
COMPASS POC – estrazione Porsche Macan GTS, mercato USA.

Fonte primaria: configurator.porsche.com (dati incorporati nella pagina del modello).
Fonte integrativa: copia locale dell'API "standard-equipment" di porsche.com (descrizioni
delle dotazioni di serie), se presente. www.porsche.com risponde 403 a questo ambiente dal 27/10.

Output: Excel con Riepilogo, Dotazioni di serie, Optional (classificati), Optional singoli
(perimetro POC), Pacchetti (fuori perimetro), Template Maserati, Log aree di verifica.
Salva anche i dati grezzi decodificati per l'audit trail.

Uso:
  python poc_compass/porsche_us.py --model 95BBW1 \
      --std-eq-cache poc_us/raw/95BBW1/standard_equipment.json --out poc_compass/output
"""
import argparse
import datetime as dt
import html
import json
import re
import sys
from pathlib import Path

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from turbostream import decode, stream_from_html  # noqa: E402

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36")
URL = "https://configurator.porsche.com/{locale}/mode/model/{code}"

# area del veicolo ("posizione") a partire dalla categoria Porsche
AREA = {
    "Esterno": ["Wheels", "Tires", "Wheel Accessories", "Exterior", "Roof and Transport Systems",
                "Exterior Decals and Logos", "Lights and Vision", "Exterior Colors", "Exterior Packages"],
    "Interno": ["Seats", "Interior Packages and Trim", "Seat Belts and Seat Design",
                "Steering Wheel and Gearshift Lever/Selector", "Interior",
                "Keys, Floor Mats & Owner's Manual Wallets", "Interior Colors & Material",
                "Interior Colors and Materials"],
    "Meccanica e prestazioni": ["Performance", "Steering Codes"],
    "Comfort e tecnologia": ["Interior Comfort", "Assistance Systems", "Audio and Communication"],
}
AREA_BY_CAT = {c: a for a, cats in AREA.items() for c in cats}
SECTION_AREA = {"section-exterior-color": "Esterno", "section-wheels": "Esterno",
                "section-interior-color": "Interno", "section-interior-seats": "Interno",
                "section-individualization-exterior": "Esterno",
                "section-individualization-interior": "Interno",
                "section-individualization-technology": "Comfort e tecnologia",
                "section-individualization-packages": "Pacchetti",
                "section-vehicle-accessories": "Accessori concessionario",
                "section-individualization-delivery": "Servizi di consegna"}


def clean(s):
    if s is None:
        return None
    s = re.sub(r"<br\s*/?>|</p>\s*<p>|</li>\s*<li>", "\n", str(s))
    s = html.unescape(re.sub(r"<[^>]+>", " ", s))
    return re.sub(r"[ \t]+", " ", re.sub(r" *\n *", "\n", s)).strip() or None


def norm(s):
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def area_for(category, section_id):
    return AREA_BY_CAT.get(category) or SECTION_AREA.get(section_id) or "Altro"


def classify(item, category, section_id):
    """Tipo di voce + perimetro POC, con il motivo (regola esplicita, verificabile)."""
    title = item.get("title") or ""
    if section_id == "section-vehicle-accessories":
        return "Accessorio concessionario", "No", "accessorio venduto dal concessionario, non dotazione del veicolo"
    if section_id == "section-individualization-delivery":
        return "Servizio", "No", "servizio di consegna, non dotazione del veicolo"
    if item.get("packageContents"):
        return "Pacchetto", "No", "pacchetto aggregato (ha un elenco di contenuti): fuori perimetro POC"
    if "Package" in (category or "") and re.search(r"\bPackage\b", title):
        return "Pacchetto", "No", "pacchetto per nome e categoria: fuori perimetro POC"
    if section_id in ("section-exterior-color", "section-interior-color"):
        return "Colore / materiale", "Da validare", "scelta estetica: da decidere se rientra nell'Equipment Adjusted"
    if re.search(r"\bPackage\b", title):
        return "Componente singolo", "Sì", "codice optional unico ma il nome contiene 'Package': da confermare"
    return "Componente singolo", "Sì", "componente singolo"


def fetch(locale, code):
    url = URL.format(locale=locale, code=code)
    r = requests.get(url, headers={"User-Agent": UA, "Accept-Language": locale}, timeout=60)
    r.raise_for_status()
    r.encoding = "utf-8"
    return url, r.text


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="95BBW1")
    ap.add_argument("--locale", default="en-US")
    ap.add_argument("--std-eq-cache", help="JSON standard-equipment salvato in precedenza (opzionale)")
    ap.add_argument("--out", default="poc_compass/output")
    args = ap.parse_args()

    out = Path(args.out)
    (out / "raw").mkdir(parents=True, exist_ok=True)
    ts = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    stamp = ts[:10]

    url, page = fetch(args.locale, args.model)
    data = decode(stream_from_html(page))["loaderData"]
    (out / "raw" / f"{args.model}_{args.locale}_{stamp}.json").write_text(
        json.dumps(data, ensure_ascii=False, default=str))
    cc = data["customer-configurator"]
    tr = (data.get("customer-locale") or {}).get("translations") or {}
    cat, cfg = cc["catalog"], cc["configuration"]
    main_p = cfg["prices"]["main"]
    currency = cc["market"]["currency"]
    selected = set(cfg.get("options") or [])

    # ---- tutte le voci del configuratore
    items, seen = [], set()
    for sec in cc["views"]["optionsList"]:
        for c in sec["categories"]:
            for g in c["groups"]:
                for it in g["items"]:
                    if it["id"] not in seen:
                        seen.add(it["id"])
                        items.append((sec["id"], c.get("title"), g.get("title"), it))
    for oid, it in cc["views"]["search"]["options"].items():
        if oid not in seen:
            seen.add(oid)
            items.append((it.get("sectionId"), it.get("categoryTitle"), it.get("groupTitle"), it))

    # ---- dotazioni di serie: configuratore + descrizioni dalla cache API
    api_desc, api_rows = {}, []
    if args.std_eq_cache and Path(args.std_eq_cache).exists():
        se = json.loads(Path(args.std_eq_cache).read_text())
        for c in se.get("categories", []):
            for e in c.get("equipment", []):
                # alcuni nomi includono note legali dopo il primo a capo: vanno nella descrizione
                name, _, note = (e.get("name") or "").partition("\n")
                name = name.strip()
                if name.startswith("*") and api_rows:  # nota a piè di pagina della voce precedente
                    prev_cat, prev_name, prev_desc = api_rows[-1]
                    api_rows[-1] = (prev_cat, prev_name, "\n".join(x for x in (prev_desc, name) if x))
                    api_desc[norm(prev_name)] = api_rows[-1][2]
                    continue
                desc = "\n".join(x for x in (clean(e.get("description")), clean(note)) if x) or None
                api_desc[norm(name)] = desc
                api_rows.append((c["name"], name, desc))
    std, std_names = [], set()
    for sec_id, cat_t, grp_t, it in items:
        if it.get("isStandardEquipment"):
            std_names.add(norm(it["title"]))
            desc = clean(it.get("description")) or api_desc.get(norm(it["title"]))
            std.append({"codice": it["id"], "dotazione (terminologia Porsche)": clean(it["title"]),
                        "descrizione": desc, "categoria Porsche": cat_t,
                        "area veicolo": area_for(cat_t, sec_id),
                        "fonte": f"configuratore {stamp}" + (" + descrizione API 15/10" if not clean(it.get("description")) and desc else "")})
    for cat_t, name, desc in api_rows:  # voci presenti solo nell'API
        if norm(name) not in std_names:
            std.append({"codice": None, "dotazione (terminologia Porsche)": name, "descrizione": desc,
                        "categoria Porsche": cat_t, "area veicolo": area_for(cat_t, None),
                        "fonte": "solo API dotazione di serie 15/10"})

    # ---- optional classificati
    opts, packs = [], []
    for sec_id, cat_t, grp_t, it in items:
        if it.get("isStandardEquipment"):
            continue
        tipo, perimetro, motivo = classify(it, cat_t, sec_id)
        price = it.get("priceNumeric")
        if price is None:
            price = (cfg["prices"]["options"].get(it["id"]) or {}).get("gross")
        row = {"codice": it["id"], "optional (terminologia Porsche)": clean(it.get("title")),
               f"prezzo {currency}": price, "prezzo testo": clean(it.get("price")),
               "tipo voce": tipo, "in perimetro POC": perimetro, "motivo": motivo,
               "categoria Porsche": cat_t, "gruppo": grp_t,
               "sezione configuratore": tr.get(sec_id, sec_id), "area veicolo": area_for(cat_t, sec_id),
               "selezionato di default": it["id"] in selected,
               "descrizione": clean(it.get("description"))}
        opts.append(row)
        if tipo == "Pacchetto":
            packs.append({"codice": it["id"], "pacchetto": clean(it.get("title")), f"prezzo {currency}": price,
                          "contenuto": clean(json.dumps(it.get("packageContents"), ensure_ascii=False))
                          if it.get("packageContents") else None,
                          "descrizione": clean(it.get("description"))})
    df_opt = pd.DataFrame(opts).sort_values(["in perimetro POC", "area veicolo", f"prezzo {currency}"],
                                            ascending=[False, True, False])
    df_single = df_opt[df_opt["in perimetro POC"] == "Sì"].drop(columns=["in perimetro POC", "motivo"])

    base, dest = main_p["base"]["raw"], (main_p.get("destinationCharge") or {}).get("raw")
    summary = [
        ("Brand", "Porsche"), ("Modello", cat.get("modelName")), ("Codice modello", args.model),
        ("Anno modello", cat.get("modelYear")), ("Motorizzazione", cat.get("engineType")),
        ("Mercato", "USA" if args.locale == "en-US" else args.locale), ("Valuta", currency),
        ("Prezzo Visual (MSRP base)", base),
        ("Destination charge", dest),
        ("MSRP + destination", base + (dest or 0)),
        ("Data listino (configuratore)", cfg.get("checkDate")),
        ("Cerchi di serie", (cfg.get("wheelOption") or {}).get("title")),
        ("Trasmissione di serie", (cfg.get("transmissionOption") or {}).get("title")),
        ("N. dotazioni di serie", len(std)),
        ("N. optional singoli (perimetro)", len(df_single)),
        ("N. pacchetti (fuori perimetro)", len(packs)),
        ("Estrazione", ts), ("Fonte", url),
    ]

    template_cols = ["brand", "modello", "mercato", "codice", "voce (terminologia Maserati)", "tipo",
                     "di serie (S/N)", "prezzo USD", "categoria", "area veicolo", "descrizione"]
    template = pd.DataFrame([["Maserati", "Grecale V6 Trofeo", "USA", "<codice>", "ESEMPIO – da sostituire",
                              "Componente singolo", "N", 0, "<categoria>", "Interno", "<descrizione>"]],
                            columns=template_cols)

    log = pd.DataFrame([
        ("01", "Navigabilità dei configuratori", "Risolto",
         "Nessuna navigazione necessaria: la pagina del modello contiene già tutti i dati in forma strutturata (React Router turbo-stream). Accesso diretto al codice modello 95BBW1."),
        ("02", "Estrazione del prezzo base", "Risolto",
         f"Prezzo base {base} {currency} letto come numero dal campo prices.main.base; destination charge {dest} separata."),
        ("03", "Dotazioni di serie", "Risolto / mitigato",
         f"{sum(1 for s in std if s['codice'])} voci dal configuratore (con codice); descrizioni integrate dall'API standard-equipment (copia del 15/10). Dal 27/10 www.porsche.com risponde 403 a questo ambiente: descrizioni non aggiornabili da qui."),
        ("04", "Opzioni a pagamento", "Risolto",
         f"{len(df_single)} componenti singoli in perimetro; pacchetti ({len(packs)}), accessori concessionario e servizi esclusi con regola esplicita (colonna 'motivo')."),
        ("05", "Normalizzazione cross-brand", "Aperto", "Da fare quando saranno disponibili i dati Maserati Grecale (template incluso)."),
        ("06", "Documentazione dei fallimenti", "In corso",
         "Rischi: blocco anti-bot di www.porsche.com (attivo da 27/10), dipendenza dal formato turbo-stream della pagina, cambio codici modello al model year. Configuratore conforme al robots.txt (pagine /mode/model/<codice> consentite)."),
    ], columns=["area", "verifica", "stato", "evidenza"])

    xlsx = out / f"COMPASS_POC_Porsche_{cat.get('modelName','').replace(' ', '')}_{args.model}_USA_{stamp}.xlsx"
    with pd.ExcelWriter(xlsx, engine="openpyxl") as xw:
        pd.DataFrame(summary, columns=["campo", "valore"]).to_excel(xw, sheet_name="Riepilogo", index=False)
        pd.DataFrame(std).to_excel(xw, sheet_name="Dotazioni di serie", index=False)
        df_single.to_excel(xw, sheet_name="Optional singoli", index=False)
        df_opt.to_excel(xw, sheet_name="Optional (tutti)", index=False)
        pd.DataFrame(packs).to_excel(xw, sheet_name="Pacchetti (fuori perim.)", index=False)
        pd.DataFrame([["Compilare una riga per ogni dotazione di serie (di serie = S) e per ogni optional singolo "
                       "(di serie = N, con prezzo USD). La riga 3 è solo un esempio di formato: sostituirla."]]
                     ).to_excel(xw, sheet_name="Template Maserati", index=False, header=False)
        template.to_excel(xw, sheet_name="Template Maserati", index=False, startrow=1)
        log.to_excel(xw, sheet_name="Log aree di verifica", index=False)
        for ws in xw.sheets.values():
            ws.freeze_panes = "A2" if ws.title != "Template Maserati" else "A3"
            for col in ws.columns:
                w = max(len(str(c.value or "")) for c in list(col)[:300])
                ws.column_dimensions[col[0].column_letter].width = min(max(10, w + 2), 70)
    print(f"{cat.get('modelName')} {args.model}: base {base} {currency} (+{dest} destination), "
          f"{len(std)} dotazioni di serie, {len(df_single)} optional singoli, {len(packs)} pacchetti -> {xlsx}")


if __name__ == "__main__":
    main()
