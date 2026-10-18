"""DuckDB + Parquet storage.

Raw source files are written once under data/raw/<source>/<date>/ and never
overwritten; the cleaned tables live in DuckDB. Three tables make up the model:

companies   one row per company: id, name, country, region, sector, listing dates
statements  one row per company and fiscal year, with the filing date that makes
            it usable (point in time)
monthly     one row per company and month end: total return, price, market cap,
            20-day ADV in USD, benchmark membership
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date

import duckdb
import pandas as pd

from ..config import DB_PATH, RAW_DIR

TABLES = ("companies", "statements", "monthly")


@dataclass
class Dataset:
    companies: pd.DataFrame
    statements: pd.DataFrame
    monthly: pd.DataFrame
    source: str
    built: str

    @property
    def months(self) -> pd.DatetimeIndex:
        return pd.DatetimeIndex(sorted(self.monthly["date"].unique()))


def save(tables: dict[str, pd.DataFrame], source: str) -> None:
    stamp = date.today().isoformat()
    raw = RAW_DIR / source / stamp
    raw.mkdir(parents=True, exist_ok=True)
    for name in TABLES:
        path = raw / f"{name}.parquet"
        if not path.exists():  # dated snapshots are never overwritten
            tables[name].to_parquet(path, index=False)
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(str(DB_PATH)) as con:
        for name in TABLES:
            df = tables[name]  # noqa: F841 - referenced by DuckDB below
            con.execute(f"CREATE OR REPLACE TABLE {name} AS SELECT * FROM df")
        con.execute("CREATE OR REPLACE TABLE meta (key VARCHAR, value VARCHAR)")
        con.execute("INSERT INTO meta VALUES ('source', ?), ('built', ?)", [source, stamp])


def load() -> Dataset:
    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"No database at {DB_PATH}. Build one with: python -m smallcap.cli build-demo")
    with duckdb.connect(str(DB_PATH), read_only=True) as con:
        frames = {name: con.execute(f"SELECT * FROM {name}").df() for name in TABLES}
        meta = dict(con.execute("SELECT key, value FROM meta").fetchall())
    for col in ("period_end", "filing_date"):
        frames["statements"][col] = pd.to_datetime(frames["statements"][col])
    frames["monthly"]["date"] = pd.to_datetime(frames["monthly"]["date"])
    for col in ("listed_date", "delisted_date"):
        frames["companies"][col] = pd.to_datetime(frames["companies"][col])
    return Dataset(**frames, source=meta.get("source", "unknown"), built=meta.get("built", ""))


def describe(ds: Dataset) -> dict:
    return json.loads(json.dumps({
        "source": ds.source,
        "built": ds.built,
        "companies": int(len(ds.companies)),
        "statements": int(len(ds.statements)),
        "first_month": ds.months[0].date().isoformat(),
        "last_month": ds.months[-1].date().isoformat(),
    }))
