"""
load_warehouse.py
=================
Loads the raw extracts (staging) and the star schema into a local SQLite
warehouse, then executes the SQL scripts in /sql and saves every named query
result to data/sql_output/<name>.csv.

SQLite is used so the project runs anywhere with zero setup. The SQL is kept
close to ANSI; where SQL Server / PostgreSQL syntax differs it is noted in a
comment in the .sql file.

Named queries in the .sql files start with a comment line:
    -- @name: query_name

Run:  python src/load_warehouse.py
"""
from __future__ import annotations

import re
import sqlite3

import pandas as pd

import config as C

OUT_DIR = C.ROOT / "data" / "sql_output"
MODEL_DIR = C.ROOT / "data" / "model"

STAGING = {
    "stg_crm_customers": "crm_customers.csv",
    "stg_hr_technicians": "hr_technicians.csv",
    "stg_fsm_service_requests": "fsm_service_requests.csv",
    "stg_billing_invoices": "billing_invoices.csv",
    "stg_csat_survey_responses": "csat_survey_responses.csv",
    "stg_sla_policy": "sla_policy.csv",
    "stg_regional_targets": "regional_targets.csv",
}
MODEL_TABLES = ["DimDate", "DimRegion", "DimCustomer", "DimTechnician", "DimServiceType", "DimPriority",
                "FactServiceRequests", "FactTargets", "FactBacklogSnapshot", "SecurityUserRegion"]


def split_statements(sql: str):
    """Split a script on ';' at end of line, keeping the '-- @name:' tag of each statement."""
    for chunk in re.split(r";\s*\n", sql):
        if not re.sub(r"--.*", "", chunk).strip():
            continue
        m = re.search(r"--\s*@name:\s*(\w+)", chunk)
        yield (m.group(1) if m else None), chunk.strip()


def run_script(con: sqlite3.Connection, path):
    print(f"\n-- {path.name}")
    for name, stmt in split_statements(path.read_text(encoding="utf-8")):
        if name:
            df = pd.read_sql_query(stmt, con)
            df.to_csv(OUT_DIR / f"{name}.csv", index=False)
            print(f"   {name:45s} {len(df):>6,} rows")
        else:
            con.executescript(stmt + ";")


def main():
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for old in OUT_DIR.glob("*.csv"):
        old.unlink()
    if C.WAREHOUSE_DB.exists():
        C.WAREHOUSE_DB.unlink()
    con = sqlite3.connect(C.WAREHOUSE_DB)
    con.execute("PRAGMA foreign_keys = ON")

    run_script(con, C.SQL_DIR / "create_tables.sql")

    for table, file in STAGING.items():
        df = pd.read_csv(C.RAW_DIR / file, dtype=str, keep_default_na=False)
        df.to_sql(table, con, if_exists="append", index=False)
    for table in MODEL_TABLES:
        df = pd.read_csv(MODEL_DIR / f"{table}.csv")
        df.to_sql(table, con, if_exists="append", index=False)
    con.commit()
    print("   staging + model tables loaded")

    for script in ["validation_queries.sql", "transformations.sql", "kpi_queries.sql"]:
        run_script(con, C.SQL_DIR / script)
    con.close()
    print(f"\nWarehouse: {C.WAREHOUSE_DB}\nQuery outputs: {OUT_DIR}")


if __name__ == "__main__":
    main()
