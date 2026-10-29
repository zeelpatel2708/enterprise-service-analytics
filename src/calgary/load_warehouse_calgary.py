"""
load_warehouse_calgary.py
=========================
Loads the Calgary star schema into SQLite and runs sql/calgary/*.sql, saving
each named query to data/calgary/sql_output/<name>.csv.

Run:  python src/calgary/load_warehouse_calgary.py
"""
import sqlite3
import sys
from pathlib import Path

import pandas as pd

import config_calgary as CC

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from load_warehouse import split_statements  # noqa: E402  (shared helper from Edition A)

TABLES = ["DimDate", "DimServiceType", "DimCommunity", "DimChannel", "FactServiceRequests", "FactBacklogSnapshot"]
INDEXES = [
    "CREATE INDEX ix_f_req ON FactServiceRequests (RequestedDateKey)",
    "CREATE INDEX ix_f_closed ON FactServiceRequests (ClosedDateKey)",
    "CREATE INDEX ix_f_svc ON FactServiceRequests (ServiceTypeKey)",
    "CREATE INDEX ix_f_comm ON FactServiceRequests (CommunityKey)",
    "CREATE UNIQUE INDEX ix_d_date ON DimDate (DateKey)",
]


def main():
    CC.SQL_OUT_DIR.mkdir(parents=True, exist_ok=True)
    for old in CC.SQL_OUT_DIR.glob("*.csv"):
        old.unlink()
    if CC.WAREHOUSE_DB.exists():
        CC.WAREHOUSE_DB.unlink()
    con = sqlite3.connect(CC.WAREHOUSE_DB)
    for t in TABLES:
        df = pd.read_csv(CC.MODEL_DIR / f"{t}.csv", keep_default_na=False, na_values=[""])
        # integer columns with blanks are read as float; store them as integers so
        # integer arithmetic like ClosedDateKey / 100 behaves in SQL
        for c in df.select_dtypes("float").columns:
            if (df[c].dropna() % 1 == 0).all():
                df[c] = df[c].astype("Int64")
        df.to_sql(t, con, index=False, chunksize=100_000)
    for ix in INDEXES:
        con.execute(ix)
    con.commit()
    print("   model tables loaded")
    for script in sorted(CC.SQL_DIR.glob("*.sql")):
        print(f"-- {script.name}")
        for name, stmt in split_statements(script.read_text(encoding="utf-8")):
            if name:
                df = pd.read_sql_query(stmt, con)
                df.to_csv(CC.SQL_OUT_DIR / f"{name}.csv", index=False)
                print(f"   {name:40s} {len(df):>6,} rows")
            else:
                con.executescript(stmt + ";")
    con.close()


if __name__ == "__main__":
    main()
