-- =====================================================================
-- 04 – Stored procedure: scarica UN modello dal configuratore Porsche
--      e scrive PORSCHE_RAW, PORSCHE_MODELS, PORSCHE_OPTIONS.
--
-- Uso:  CALL SCRAPE_PORSCHE_MODEL('en-US', '95BBW1');   -- Macan GTS, USA
--       CALL SCRAPE_PORSCHE_MODEL('it-IT', 'XABDE1');   -- Macan GTS Electric, Italia
-- =====================================================================
USE ROLE SYSADMIN;
USE SCHEMA CAR_PRICING.PORSCHE;

CREATE OR REPLACE PROCEDURE SCRAPE_PORSCHE_MODEL(LOCALE STRING, MODEL_CODE STRING)
  RETURNS STRING
  LANGUAGE PYTHON
  RUNTIME_VERSION = '3.11'
  PACKAGES = ('snowflake-snowpark-python', 'requests')
  EXTERNAL_ACCESS_INTEGRATIONS = (PORSCHE_CONFIGURATOR_EAI)
  HANDLER = 'run'
  COMMENT = 'Scarica optional e prezzi di un modello dal configuratore Porsche'
AS
$$
import datetime
import html
import json
import re

import requests

URL = "https://configurator.porsche.com/{locale}/mode/model/{code}"
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36")

# ---------- decoder turbo-stream (dati incorporati nella pagina) ----------
SPECIAL = {-1: None, -2: None, -3: None, -4: 0.0, -5: None, -6: None, -7: None}
ENQUEUE_RE = re.compile(r'streamController\.enqueue\((".*?")\);?\s*</script>', re.S)


def decode_page(page_html):
    stream = "".join(json.loads(m.group(1)) for m in ENQUEUE_RE.finditer(page_html))
    values = json.loads(stream.split("\n")[0])
    cache = {}

    def hyd(i):
        if isinstance(i, int) and i < 0:
            return SPECIAL.get(i)
        if i in cache:
            return cache[i]
        v = values[i]
        if isinstance(v, list):
            if v and isinstance(v[0], str) and len(v[0]) == 1 and len(v) <= 3:
                out = v[1] if v[0] == "D" and len(v) > 1 else None   # date / promise / tipi speciali
                cache[i] = out
                return out
            out = []
            cache[i] = out
            out.extend(hyd(x) for x in v)
            return out
        if isinstance(v, dict):
            out = {}
            cache[i] = out
            for k, vi in v.items():
                out[values[int(k[1:])] if k.startswith("_") else k] = hyd(vi)
            return out
        cache[i] = v
        return v

    return hyd(0)["loaderData"]


# ---------- pulizia testi ----------
def clean(s):
    if s is None:
        return None
    s = re.sub(r"<br\s*/?>|</p>\s*<p>", "\n", str(s))
    s = html.unescape(re.sub(r"<[^>]+>", "", s))
    return re.sub(r"[ \t]+", " ", s).strip() or None


# ---------- classificazione COMPASS (stesse regole di poc_compass/porsche_us.py) ----------
AREA = {
    "Esterno": ["Wheels", "Tires", "Wheel Accessories", "Exterior", "Roof and Transport Systems",
                "Exterior Decals and Logos", "Lights and Vision", "Exterior Colors", "Exterior Packages"],
    "Interno": ["Seats", "Interior Packages and Trim", "Seat Belts and Seat Design",
                "Steering Wheel and Gearshift Lever/Selector", "Interior",
                "Keys, Floor Mats & Owner's Manual Wallets", "Interior Colors & Material"],
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


def classify(item, category, section_id):
    title = item.get("title") or ""
    if item.get("isStandardEquipment"):
        return "Dotazione di serie", "Sì", "inclusa nel prezzo base"
    if section_id == "section-vehicle-accessories":
        return "Accessorio concessionario", "No", "accessorio venduto dal concessionario"
    if section_id == "section-individualization-delivery":
        return "Servizio", "No", "servizio di consegna"
    if item.get("packageContents"):
        return "Pacchetto", "No", "pacchetto aggregato: fuori perimetro POC"
    if "Package" in (category or "") and re.search(r"\bPackage\b", title):
        return "Pacchetto", "No", "pacchetto per nome e categoria: fuori perimetro POC"
    if section_id in ("section-exterior-color", "section-interior-color"):
        return "Colore / materiale", "Da validare", "scelta estetica: da decidere per l'Equipment Adjusted"
    if re.search(r"\bPackage\b", title):
        return "Componente singolo", "Sì", "codice unico ma il nome contiene 'Package': da confermare"
    return "Componente singolo", "Sì", "componente singolo"


# ---------- estrazione optional ----------
def option_rows(cc, translations):
    cfg = cc.get("configuration") or {}
    views = cc.get("views") or {}
    prices = (cfg.get("prices") or {}).get("options") or {}
    selected = set(cfg.get("options") or [])
    currency = (cc.get("market") or {}).get("currency")
    sections = views.get("optionsList") or []
    cat_section = {c.get("id"): s.get("id") for s in sections for c in s.get("categories") or []}
    rows, seen = [], set()

    def row(item, section_id, cat_title, group_title):
        oid = item.get("id")
        price = item.get("priceNumeric")
        if price is None and oid in prices:
            price = prices[oid].get("gross")
        if price is None and item.get("isStandardEquipment"):
            price = 0
        section_id = section_id or cat_section.get(item.get("categoryId"))
        color = item.get("color")
        cat_title = cat_title or item.get("categoryTitle")
        item_type, in_scope, reason = classify(item, cat_title, section_id)
        return {
            "section": translations.get(section_id, section_id) or "Standard equipment",
            "category": cat_title or item.get("categoryTitle"),
            "option_group": group_title or item.get("groupTitle"),
            "option_code": oid,
            "option_name": clean(item.get("title")),
            "price": price,
            "currency": currency,
            "price_text": clean(item.get("price")) or ("Standard" if item.get("isStandardEquipment") else None),
            "is_standard": bool(item.get("isStandardEquipment")),
            "is_default": oid in selected or bool(item.get("isSelected")),
            "option_type": item.get("optionType"),
            "color_hex": ", ".join(color) if isinstance(color, list) else color,
            "exclusive_manufaktur": bool(item.get("exclusive")),
            "description": clean(item.get("description")),
            "package_contents": json.dumps(item["packageContents"], ensure_ascii=False)
                                if item.get("packageContents") else None,
            "item_type": item_type,
            "in_scope": in_scope,
            "scope_reason": reason,
            "vehicle_area": AREA_BY_CAT.get(cat_title) or SECTION_AREA.get(section_id) or "Altro",
        }

    for sec in sections:
        for cat in sec.get("categories") or []:
            for grp in cat.get("groups") or []:
                for item in grp.get("items") or []:
                    if item.get("id") not in seen:
                        seen.add(item.get("id"))
                        rows.append(row(item, sec.get("id"), cat.get("title"), grp.get("title")))
    # equipaggiamenti presenti solo nell'indice di ricerca (in genere di serie)
    for oid, item in ((views.get("search") or {}).get("options") or {}).items():
        if oid not in seen:
            seen.add(oid)
            rows.append(row(item, item.get("sectionId"), item.get("categoryTitle"), item.get("groupTitle")))
    return rows


# ---------- handler ----------
def run(session, locale, model_code):
    url = URL.format(locale=locale, code=model_code)
    resp = requests.get(url, headers={"User-Agent": UA, "Accept-Language": locale}, timeout=60)
    if resp.status_code != 200:
        return f"ERRORE: HTTP {resp.status_code} da {url}"
    resp.encoding = "utf-8"
    data = decode_page(resp.text)
    cc = data["customer-configurator"]
    translations = (data.get("customer-locale") or {}).get("translations") or {}
    cat = cc.get("catalog") or {}
    cfg = cc.get("configuration") or {}
    base = ((cfg.get("prices") or {}).get("main") or {}).get("base") or {}
    currency = (cc.get("market") or {}).get("currency")
    options = option_rows(cc, translations)
    snapshot = datetime.datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    name = cat.get("modelName") or model_code

    # 1) dati grezzi (solo le parti utili, per tenere il JSON compatto)
    raw = {"catalog": cat, "configuration": cfg, "market": cc.get("market"),
           "views": {"optionsList": (cc.get("views") or {}).get("optionsList"),
                     "search_options": ((cc.get("views") or {}).get("search") or {}).get("options")},
           "section_titles": {k: v for k, v in translations.items() if k.startswith("section-")}}
    session.sql(
        "INSERT INTO PORSCHE_RAW (SNAPSHOT_TS, LOCALE, MODEL_CODE, URL, PAYLOAD) "
        "SELECT TO_TIMESTAMP_NTZ(?), ?, ?, ?, PARSE_JSON(?)",
        params=[snapshot, locale, model_code, url, json.dumps(raw, ensure_ascii=False, default=str)],
    ).collect()

    # 2) modello
    model = {"model_name": name, "model_year": cat.get("modelYear"), "model_family": cat.get("modelFamily"),
             "engine_type": cat.get("engineType"), "base_price": base.get("raw"), "currency": currency,
             "base_price_text": clean(base.get("gross")),
             "destination_charge": (((cfg.get("prices") or {}).get("main") or {}).get("destinationCharge") or {}).get("raw"),
             "standard_wheels": (cfg.get("wheelOption") or {}).get("title"),
             "standard_transmission": (cfg.get("transmissionOption") or {}).get("title"),
             "price_list_date": cfg.get("checkDate"), "n_options": len(options), "url": url}
    session.sql(
        "INSERT INTO PORSCHE_MODELS SELECT TO_TIMESTAMP_NTZ(?), ?, ?, "
        "m:model_name::STRING, m:model_year::NUMBER, m:model_family::STRING, m:engine_type::STRING, "
        "m:base_price::NUMBER(14,2), m:currency::STRING, m:base_price_text::STRING, "
        "m:destination_charge::NUMBER(14,2), "
        "m:standard_wheels::STRING, m:standard_transmission::STRING, m:price_list_date::STRING, "
        "m:n_options::NUMBER, m:url::STRING "
        "FROM (SELECT PARSE_JSON(?) AS m)",
        params=[snapshot, locale, model_code, json.dumps(model, ensure_ascii=False)],
    ).collect()

    # 3) optional (una sola INSERT con FLATTEN sull'array JSON)
    session.sql(
        "INSERT INTO PORSCHE_OPTIONS SELECT TO_TIMESTAMP_NTZ(?), ?, ?, ?, "
        "f.value:section::STRING, f.value:category::STRING, f.value:option_group::STRING, "
        "f.value:option_code::STRING, f.value:option_name::STRING, f.value:price::NUMBER(14,2), "
        "f.value:currency::STRING, f.value:price_text::STRING, f.value:is_standard::BOOLEAN, "
        "f.value:is_default::BOOLEAN, f.value:option_type::STRING, f.value:color_hex::STRING, "
        "f.value:exclusive_manufaktur::BOOLEAN, f.value:description::STRING, "
        "f.value:package_contents::STRING, f.value:item_type::STRING, f.value:in_scope::STRING, "
        "f.value:scope_reason::STRING, f.value:vehicle_area::STRING "
        "FROM TABLE(FLATTEN(INPUT => PARSE_JSON(?))) f",
        params=[snapshot, locale, model_code, name, json.dumps(options, ensure_ascii=False)],
    ).collect()

    n_std = sum(1 for o in options if o["item_type"] == "Dotazione di serie")
    n_single = sum(1 for o in options if o["item_type"] == "Componente singolo")
    n_pack = sum(1 for o in options if o["item_type"] == "Pacchetto")
    return (f"OK {name} ({model_code}, {locale}): prezzo base {base.get('raw')} {currency} "
            f"(+{model['destination_charge']} destination), {n_std} dotazioni di serie, "
            f"{n_single} optional singoli, {n_pack} pacchetti, snapshot {snapshot} UTC")
$$;
