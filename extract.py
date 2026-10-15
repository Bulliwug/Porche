"""
Fase 2 – dai dati grezzi a Excel/CSV.

Fogli prodotti:
  Modelli          – un record per modello: prezzo base, carrozzeria, trazione, cambio, dati tecnici chiave
  Optional         – tutti gli optional del configuratore con sezione/categoria/gruppo, prezzo, di serie sì/no
  DatiTecnici      – scheda tecnica completa (formato lungo: modello, categoria, voce, valore)
  DotazioneSerie   – equipaggiamento di serie per modello

Uso:
  python extract.py --data data --xlsx porsche_configuratore.xlsx
"""
import argparse
import html
import json
import re
from pathlib import Path

import pandas as pd

# voci della scheda tecnica riportate anche come colonne nel foglio Modelli
KEY_SPECS = {  # per ogni colonna: pattern in ordine di priorità
    # etichette italiane e inglesi (mercato USA)
    "potenza_kW": [r"^Potenza combinata \(kW\)", r"^Potenza fino a \(kW\)", r"^Potenza \(kW\)$",
                   r"^Power up to \(kW\)"],
    "potenza_CV": [r"^Potenza combinata \(CV\)", r"^Potenza fino a \(CV\)", r"^Potenza \(CV\)$"],
    "potenza_hp": [r"^Power up to \(HP\)", r"^Max\. engine power$"],
    "potenza_overboost_kW": [r"^Potenza di overboost .*\(kW\)", r"^Overboost Power .*\(kW\)"],
    "coppia_max": [r"^Coppia combinata", r"^Coppia massima$", r"^Coppia massima",
                   r"^Max\. engine torque$", r"^Max\. torque"],
    "cilindrata": [r"^Cilindrata$", r"^Displacement$"],
    "0_100_kmh": [r"^Accelerazione 0 - 100 km/h"],
    "0_60_mph": [r"^0 - 60 mph with (Sport Chrono|Launch Control)", r"^0 - 60 mph$"],
    "velocita_max": [r"^Velocità massima$", r"^Top track speed"],
    "consumo_mpg_combinato": [r"^Combined$"],
    "consumo_carburante_misto": [r"^Consumo carburante ponderato misto", r"^Consumo carburante ciclo misto"],
    "consumo_elettrico_misto": [r"^Consumo (di )?energia elettrica ponderato misto",
                                r"^Consumo (di )?energia elettrica ciclo misto"],
    "co2_misto": [r"^Emissioni CO.? ponderat", r"^Emissioni CO.? ciclo misto"],
    "autonomia_elettrica": [r"^Autonomia elettrica (combinata|ciclo misto)", r"^Autonomia elettrica"],
    "batteria": [r"^Capacità (complessiva|lorda|netta) della batteria", r"^Gross battery capacity"],
    "ricarica_DC_10_80": [r"^Tempo di ricarica in corrente continua",
                          r"^Charging time for direct current \(DC\) with maximum"],
    "lunghezza": [r"^Lunghezza$", r"^Length$"],
    "larghezza": [r"^Larghezza$", r"^Larghezza", r"^Width \(without mirrors\)"],
    "altezza": [r"^Altezza$", r"^Altezza \(", r"^Height$", r"^Height \(air suspension\) \(standard"],
    "passo": [r"^Passo$", r"^Wheelbase$"],
    "peso_DIN": [r"^Peso a vuoto \(DIN\)"],
    "peso_curb": [r"^Curb weight$"],
}


def clean(s):
    if s is None:
        return None
    s = re.sub(r"<br\s*/?>|</p>\s*<p>", "\n", str(s))
    s = html.unescape(re.sub(r"<[^>]+>", "", s))
    return re.sub(r"[ \t]+", " ", s).strip() or None


def load(path):
    return json.loads(path.read_text()) if path.exists() else None


def tech_rows(code, name, td):
    rows = []
    for cat in (td or {}).get("categories", []):
        for a in cat.get("attributes", []):
            rows.append({"codice_modello": code, "modello": name, "categoria": cat.get("label"),
                         "voce": clean(a.get("label")), "valore": clean(a.get("value")),
                         "id_voce": a.get("id")})
    return rows


def equipment_rows(code, name, se):
    rows = []
    for cat in (se or {}).get("categories", []):
        for e in cat.get("equipment", []):
            rows.append({"codice_modello": code, "modello": name, "categoria": cat.get("name"),
                         "equipaggiamento": clean(e.get("name")),
                         "descrizione": clean(e.get("description"))})
    return rows


def option_rows(code, name, conf):
    cc = conf["customer-configurator"]
    tr = conf.get("customer-locale", {}).get("translations", {})
    prices = (cc.get("configuration") or {}).get("prices", {}).get("options", {})
    selected = set((cc.get("configuration") or {}).get("options") or [])
    currency = (cc.get("market") or {}).get("currency")
    rows, seen = [], set()
    cat_section = {cat.get("id"): sec.get("id")
                   for sec in (cc.get("views") or {}).get("optionsList") or []
                   for cat in sec.get("categories") or []}

    def row(item, section_id, cat_title, group_title):
        oid = item.get("id")
        price = item.get("priceNumeric")
        if price is None and oid in prices:
            price = prices[oid].get("gross")
        if price is None and item.get("isStandardEquipment"):
            price = 0
        section_id = section_id or cat_section.get(item.get("categoryId"))
        color = item.get("color")
        return {
            "codice_modello": code, "modello": name,
            "sezione": tr.get(section_id, section_id) or "Equipaggiamento di serie",
            "categoria": cat_title or item.get("categoryTitle"),
            "gruppo": group_title or item.get("groupTitle"),
            "codice_optional": oid,
            "nome": clean(item.get("title")),
            "prezzo": price,
            "valuta": currency,
            "prezzo_testo": clean(item.get("price")) or ("Di serie" if item.get("isStandardEquipment") else None),
            "di_serie": bool(item.get("isStandardEquipment")),
            "selezionato_default": oid in selected or bool(item.get("isSelected")),
            "tipo": item.get("optionType"),
            "colore_hex": ", ".join(color) if isinstance(color, list) else color,
            "exclusive_manufaktur": bool(item.get("exclusive")),
            "descrizione": clean(item.get("description")),
            "contenuto_pacchetto": clean(json.dumps(item["packageContents"], ensure_ascii=False))
                                   if item.get("packageContents") else None,
        }

    for sec in (cc.get("views") or {}).get("optionsList") or []:
        for cat in sec.get("categories") or []:
            for grp in cat.get("groups") or []:
                for item in grp.get("items") or []:
                    if item.get("id") in seen:
                        continue
                    seen.add(item.get("id"))
                    rows.append(row(item, sec.get("id"), cat.get("title"), grp.get("title")))
    # optional presenti solo nell'indice di ricerca (non mostrati nell'elenco principale)
    for oid, item in ((cc.get("views") or {}).get("search") or {}).get("options", {}).items():
        if oid not in seen:
            seen.add(oid)
            rows.append(row(item, item.get("sectionId"), item.get("categoryTitle"), item.get("groupTitle")))
    return rows


def model_row(code, ov, conf, td, n_opt):
    cc = (conf or {}).get("customer-configurator", {})
    cat = cc.get("catalog") or {}
    cfg = cc.get("configuration") or {}
    m = (ov or {}).get("model", {})
    base = ((cfg.get("prices") or {}).get("main") or {}).get("base") or {}
    row = {
        "codice_modello": code,
        "modello": cat.get("modelName") or m.get("modelName") or (td or {}).get("name"),
        "anno_modello": cat.get("modelYear") or m.get("modelYear"),
        "gamma": cat.get("modelFamily") or m.get("modelRange"),
        "serie": m.get("modelSeries"),
        "carrozzeria": m.get("bodyType"),
        "trazione": m.get("wheelDrive"),
        "posti": m.get("seats"),
        "alimentazione": m.get("fuelTypeText") or cat.get("engineType"),
        "cambio": m.get("gearTypeText"),
        "prezzo_base": base.get("raw") or (m.get("price") or {}).get("value"),
        "valuta": (cc.get("market") or {}).get("currency") or (m.get("price") or {}).get("currencyCode"),
        "prezzo_base_testo": clean(base.get("gross")) or (m.get("price") or {}).get("formattedValue"),
        "cerchi_di_serie": (cfg.get("wheelOption") or {}).get("title"),
        "trasmissione_di_serie": (cfg.get("transmissionOption") or {}).get("title"),
        "n_optional": n_opt,
        "data_listino": cfg.get("checkDate"),
        "url_configuratore": f"https://configurator.porsche.com/{(cc.get('market') or {}).get('locale', 'it-IT')}/mode/model/{code}",
    }
    specs = tech_rows(code, None, td)
    for col, pats in KEY_SPECS.items():
        row[col] = next((r["valore"] for pat in pats for r in specs
                         if r["voce"] and re.search(pat, r["voce"])), None)
    return row


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data")
    ap.add_argument("--xlsx", default="porsche_configuratore.xlsx")
    args = ap.parse_args()

    data = Path(args.data)
    overview = load(data / "models_overview.json") or {}
    models, options, specs, equip = [], [], [], []
    for d in sorted(p for p in (data / "raw").iterdir() if p.is_dir()):
        code = d.name
        conf, td, se = load(d / "configurator.json"), load(d / "technical_data.json"), load(d / "standard_equipment.json")
        name = ((conf or {}).get("customer-configurator", {}).get("catalog") or {}).get("modelName") \
            or (td or {}).get("name") or code
        opts = option_rows(code, name, conf) if conf else []
        models.append(model_row(code, overview.get(code), conf, td, len(opts)))
        options += opts
        specs += tech_rows(code, name, td)
        equip += equipment_rows(code, name, se)
        print(f"{code} {name}: {len(opts)} optional, {len(tech_rows(code, name, td))} dati tecnici")

    dfs = {"Modelli": pd.DataFrame(models), "Optional": pd.DataFrame(options),
           "DatiTecnici": pd.DataFrame(specs), "DotazioneSerie": pd.DataFrame(equip)}
    with pd.ExcelWriter(args.xlsx, engine="openpyxl") as xw:
        for sheet, df in dfs.items():
            df.to_excel(xw, sheet_name=sheet, index=False)
            ws = xw.sheets[sheet]
            ws.freeze_panes = "A2"
            ws.auto_filter.ref = ws.dimensions
            for col in ws.columns:
                width = max(len(str(c.value or "")) for c in list(col)[:200])
                ws.column_dimensions[col[0].column_letter].width = min(max(10, width + 2), 60)
    stem = Path(args.xlsx).with_suffix("")
    for sheet, df in dfs.items():
        df.to_csv(f"{stem}_{sheet}.csv", index=False, encoding="utf-8-sig")
    print(f"Scritto {args.xlsx} (+ CSV) – {len(models)} modelli, {len(options)} optional")


if __name__ == "__main__":
    main()
