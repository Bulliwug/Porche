"""
Piano B: esegue l'estrazione dal PC locale e scrive nelle tabelle Snowflake.

Usa lo STESSO codice Python della stored procedure (04_procedure.sql, tra i $$):
la pagina del configuratore viene scaricata dal PC, le INSERT vanno su Snowflake.
Non serve l'External Access Integration (passo 02) né la procedura (passo 04):
bastano le tabelle create con 01_setup.sql e 03_tables.sql.

Uso:
  # 1) prova senza Snowflake: verifica solo che il configuratore risponda dal PC
  python snowflake/load_from_local.py --dry-run

  # 2) caricamento vero (login aziendale SSO nel browser)
  python snowflake/load_from_local.py --account <account> --user <nome.cognome@maserati.com>

  # login con password invece che SSO: impostare la variabile SNOWFLAKE_PASSWORD
  python snowflake/load_from_local.py --account <account> --user <utente> --authenticator snowflake
"""
import argparse
import json
import os
import re
from pathlib import Path

PROC_FILE = Path(__file__).with_name("04_procedure.sql")


def load_procedure_code():
    """Carica il codice Python della procedura (la parte tra i due $$)."""
    code = PROC_FILE.read_text(encoding="utf-8").split("$$")[1]
    namespace = {}
    exec(compile(code, str(PROC_FILE), "exec"), namespace)
    return namespace["run"]


class SnowflakeSession:
    """Adattatore minimo: espone session.sql(query, params).collect() come Snowpark."""

    def __init__(self, conn):
        self.cur = conn.cursor()

    def sql(self, query, params=None):
        self._pending = (query, params)
        return self

    def collect(self):
        query, params = self._pending
        self.cur.execute(query, params)
        return []


class DryRunSession:
    """Non scrive nulla: conta le righe che verrebbero inserite."""

    def sql(self, query, params=None):
        table = re.search(r"INSERT INTO (\w+)", query).group(1)
        rows = len(json.loads(params[-1])) if table == "PORSCHE_OPTIONS" else 1
        print(f"  [prova] {table}: {rows} righe")
        return self

    def collect(self):
        return []


def main():
    ap = argparse.ArgumentParser(description="Estrazione Porsche dal PC locale verso Snowflake")
    ap.add_argument("--locale", default="en-US")
    ap.add_argument("--model", default="95BBW1", help="codice modello (95BBW1 = Macan GTS USA)")
    ap.add_argument("--dry-run", action="store_true", help="non si collega a Snowflake")
    ap.add_argument("--account", help="identificativo account Snowflake, es. abc12345.west-europe.azure")
    ap.add_argument("--user")
    ap.add_argument("--authenticator", default="externalbrowser",
                    help="externalbrowser (SSO, default) oppure snowflake (password in SNOWFLAKE_PASSWORD)")
    ap.add_argument("--role", default="SYSADMIN")
    ap.add_argument("--warehouse", default="CAR_PRICING_WH")
    ap.add_argument("--database", default="CAR_PRICING")
    ap.add_argument("--schema", default="PORSCHE")
    args = ap.parse_args()

    run = load_procedure_code()

    if args.dry_run:
        print(run(DryRunSession(), args.locale, args.model))
        return

    if not (args.account and args.user):
        ap.error("servono --account e --user (oppure usa --dry-run)")

    import snowflake.connector
    snowflake.connector.paramstyle = "qmark"  # la procedura usa i segnaposto "?"
    params = dict(account=args.account, user=args.user, authenticator=args.authenticator,
                  role=args.role, warehouse=args.warehouse, database=args.database, schema=args.schema)
    if args.authenticator == "snowflake":
        if not os.environ.get("SNOWFLAKE_PASSWORD"):
            ap.error("con --authenticator snowflake imposta prima la variabile SNOWFLAKE_PASSWORD")
        params["password"] = os.environ["SNOWFLAKE_PASSWORD"]
    conn = snowflake.connector.connect(**params)
    try:
        print(run(SnowflakeSession(conn), args.locale, args.model))
    finally:
        conn.close()


if __name__ == "__main__":
    main()
