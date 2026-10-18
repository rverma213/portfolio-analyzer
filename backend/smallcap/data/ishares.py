"""iShares MSCI World Small Cap UCITS ETF (WSML) holdings: download, archive, parse.

The holdings file is the free proxy for benchmark constituents and weights
(Spec B §5). Archive it every day: the history of these files *is* the
point-in-time benchmark membership.

The iShares site refuses scripted requests (HTTP 500 even with browser
headers), so in practice: download the CSV from the fund page ("Holdings" tab →
"Download") and run `python -m smallcap.cli import-holdings <file>`, which
archives it under data/raw/ishares/<holdings date>/.
"""
from __future__ import annotations

import csv
import io
import re
import shutil
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import requests

from ..config import RAW_DIR, REGIONS

URL = ("https://www.ishares.com/uk/individual/en/products/251776/"
       "ishares-msci-world-small-cap-ucits-etf/1506575576011.ajax"
       "?fileType=csv&fileName=WSML_holdings&dataType=fund")
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "text/csv,application/octet-stream,*/*",
    "Referer": "https://www.ishares.com/uk/individual/en/products/251776/",
}
# iShares names that differ from ours.
SECTOR_MAP = {"Communication": "Communication Services", "Information Technology": "Information Technology"}
LOCATION_MAP = {"Korea (South)": "South Korea"}


def archive(url: str = URL) -> Path:
    resp = requests.get(url, headers=HEADERS, timeout=60)
    resp.raise_for_status()
    tmp = RAW_DIR / "ishares" / "download.csv"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_bytes(resp.content)
    return import_file(tmp)


def import_file(path: str | Path) -> Path:
    """Copy a downloaded holdings file into the dated archive (never overwriting)."""
    path = Path(path)
    as_of = holdings_date(path) or date.today()
    out = RAW_DIR / "ishares" / as_of.isoformat() / "WSML_holdings.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    if not out.exists():
        shutil.copyfile(path, out)
    return out


def latest_archived() -> Path | None:
    files = sorted((RAW_DIR / "ishares").glob("*/WSML_holdings.csv"))
    return files[-1] if files else None


def holdings_date(path: str | Path) -> date | None:
    """Read 'Fund Holdings as of' from the file header."""
    text = Path(path).read_text(encoding="utf-8-sig", errors="replace")
    for line in text.splitlines()[:12]:
        if "as of" in line.lower():
            m = re.search(r'"?([A-Za-z]{3,9}\.? \d{1,2}, \d{4}|\d{1,2}[/ -][A-Za-z]{3}[/ -]\d{4}|\d{2}/\d{2}/\d{4})"?', line)
            if m:
                raw = m.group(1).replace(".", "")
                for fmt in ("%b %d, %Y", "%B %d, %Y", "%d/%b/%Y", "%d-%b-%Y", "%d %b %Y", "%d/%m/%Y"):
                    try:
                        return datetime.strptime(raw, fmt).date()
                    except ValueError:
                        pass
    return None


def parse(path: str | Path) -> pd.DataFrame:
    """Equity holdings: ticker, name, sector, country, region, exchange, currency, weight."""
    text = Path(path).read_text(encoding="utf-8-sig", errors="replace")
    lines = text.splitlines()
    start = next(i for i, ln in enumerate(lines) if re.match(r'^"?Ticker"?,', ln))
    rows = list(csv.reader(io.StringIO("\n".join(lines[start:]))))
    header = [h.strip() for h in rows[0]]
    body = [r for r in rows[1:] if len(r) == len(header)]
    df = pd.DataFrame(body, columns=header)
    df = df[df["Asset Class"].str.strip().str.lower() == "equity"].copy()

    def col(*names):
        for n in names:
            if n in df.columns:
                return df[n].astype(str).str.strip()
        return pd.Series("", index=df.index)

    def num(s):
        return pd.to_numeric(s.str.replace(",", "", regex=False), errors="coerce")

    out = pd.DataFrame({
        "ticker": col("Ticker"),
        "name": col("Name").str.title(),
        "sector": col("Sector").map(lambda s: SECTOR_MAP.get(s, s)),
        "country": col("Location").map(lambda s: LOCATION_MAP.get(s, s)),
        "exchange": col("Exchange"),
        "currency": col("Market Currency", "Currency"),
        "isin": col("ISIN"),
        "weight": num(col("Weight (%)")) / 100,
        "market_value": num(col("Market Value")),
        "price": num(col("Price")),
    })
    out = out[out["country"].isin(REGIONS) & (out["ticker"] != "") & (out["ticker"] != "-")]
    out["region"] = out["country"].map(REGIONS)
    out["weight"] = out["weight"] / out["weight"].sum()
    out = out.drop_duplicates(subset=["ticker", "exchange"])
    return out.reset_index(drop=True)
