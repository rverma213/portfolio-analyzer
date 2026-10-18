"""Yahoo Finance via yfinance: monthly prices, FX, share counts, non-US statements.

Everything fetched is cached under data/raw/yahoo/ so a rebuild only downloads
what is missing or stale. Prices are split-adjusted closes plus dividend-
adjusted closes (for total return) and volume, in the listing currency.
"""
from __future__ import annotations

import json
import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

from ...config import RAW_DIR

log = logging.getLogger(__name__)
CACHE = RAW_DIR / "yahoo"
PRICE_START = "2008-01-01"
# Minor currency units Yahoo uses for some listings.
MINOR_UNITS = {"GBp": ("GBP", 0.01), "GBX": ("GBP", 0.01), "ILA": ("ILS", 0.01), "ZAc": ("ZAR", 0.01)}

logging.getLogger("yfinance").setLevel(logging.CRITICAL)


# ------------------------------------------------------------------ prices
def download_monthly(symbols: list[str], batch: int = 150) -> pd.DataFrame:
    """Long frame: symbol, date (month end), close, adj_close, volume. Cached per symbol."""
    pdir = CACHE / "prices"
    pdir.mkdir(parents=True, exist_ok=True)
    today = date.today().isoformat()
    need = [s for s in symbols if not _fresh(pdir / f"{_safe(s)}.parquet", days=7)]
    for i in range(0, len(need), batch):
        chunk = need[i:i + batch]
        log.info("prices %d-%d of %d", i + 1, i + len(chunk), len(need))
        raw = _retry(lambda: yf.download(chunk, start=PRICE_START, interval="1mo", auto_adjust=False,
                                         group_by="ticker", threads=True, progress=False))
        for s in chunk:
            try:
                df = raw[s] if isinstance(raw.columns, pd.MultiIndex) else raw
            except KeyError:
                df = pd.DataFrame()
            df = df.dropna(how="all")
            out = pd.DataFrame({
                "close": df.get("Close"), "adj_close": df.get("Adj Close"), "volume": df.get("Volume"),
            }).dropna(subset=["close"]) if len(df) else pd.DataFrame(columns=["close", "adj_close", "volume"])
            out.index.name = "date"
            out = out.reset_index()
            out["fetched"] = today
            out.to_parquet(pdir / f"{_safe(s)}.parquet", index=False)
    frames = []
    for s in symbols:
        p = pdir / f"{_safe(s)}.parquet"
        if p.exists():
            df = pd.read_parquet(p)
            if len(df):
                frames.append(df.assign(symbol=s))
    if not frames:
        return pd.DataFrame(columns=["symbol", "date", "close", "adj_close", "volume"])
    px = pd.concat(frames, ignore_index=True)
    px["date"] = pd.to_datetime(px["date"]).dt.tz_localize(None) + pd.offsets.MonthEnd(0)
    # Keep complete months only (drop the month in progress).
    px = px[px["date"] <= pd.Timestamp(date.today()) - pd.offsets.MonthEnd(1)]
    return px.drop(columns="fetched", errors="ignore")


def has_prices(symbols: list[str]) -> dict[str, bool]:
    px = download_monthly(symbols)
    counts = px.groupby("symbol").size()
    return {s: bool(counts.get(s, 0) >= 3) for s in symbols}


def fx_monthly(currencies: set[str]) -> pd.DataFrame:
    """Month-end USD per unit of each currency (minor units handled by `to_usd`)."""
    majors = sorted({MINOR_UNITS.get(c, (c, 1))[0] for c in currencies if c} - {"USD"})
    syms = {c: f"{c}USD=X" for c in majors}
    px = download_monthly(list(syms.values()))
    out = px.pivot(index="date", columns="symbol", values="close").rename(columns={v: k for k, v in syms.items()})
    out["USD"] = 1.0
    return out.sort_index().ffill()


def to_usd(currency: str, fx: pd.DataFrame, dates: pd.Series) -> np.ndarray:
    major, scale = MINOR_UNITS.get(currency, (currency, 1.0))
    if major == "USD":  # no FX lookup: fx may have no dates when every name is USD
        return np.full(len(dates), scale)
    if major not in fx.columns:
        return np.full(len(dates), np.nan)
    rate = fx[major].reindex(pd.DatetimeIndex(dates), method="ffill").to_numpy()
    return rate * scale


# --------------------------------------------------------------- quote info
def quote_info(symbols: list[str], workers: int = 2, attempts: int = 4) -> pd.DataFrame:
    """Currency, current shares outstanding and market cap (fast_info), cached a week."""
    qdir = CACHE / "info"
    qdir.mkdir(parents=True, exist_ok=True)

    def one(s):
        p = qdir / f"{_safe(s)}.json"
        if _fresh(p, days=7):
            cached = json.loads(p.read_text())
            if (cached.get("shares") and not cached.get("error")) or _fresh(p, hours=1):
                return cached
        rec = {"symbol": s}
        for attempt in range(attempts):
            rec = {"symbol": s}
            try:
                fi = yf.Ticker(s).fast_info
                rec.update(currency=fi.get("currency"), shares=fi.get("shares"),
                           market_cap=fi.get("marketCap"), last_price=fi.get("lastPrice"))
                break
            except Exception as e:  # noqa: BLE001 - recorded, not fatal
                rec["error"] = str(e)[:200]
                if "rate" not in rec["error"].lower():
                    break
                time.sleep(10 * (attempt + 1))  # throttled: back off and retry
        p.write_text(json.dumps(rec, default=float))
        return rec

    return pd.DataFrame(_pool(one, symbols, workers, "quote info"))


# ------------------------------------------------------------ fundamentals
# yfinance row names -> our columns (first match wins).
ROWS = {
    "revenue": ["Total Revenue", "Operating Revenue"],
    "net_income": ["Net Income Common Stockholders", "Net Income",
                   "Net Income From Continuing Operation Net Minority Interest"],
    "ebit": ["EBIT", "Operating Income"],
    "ebitda": ["EBITDA", "Normalized EBITDA"],
    "pretax": ["Pretax Income"],
    "tax": ["Tax Provision"],
    "cfo": ["Operating Cash Flow", "Cash Flow From Continuing Operating Activities"],
    "capex": ["Capital Expenditure", "Purchase Of PPE"],
    "total_assets": ["Total Assets"],
    "equity": ["Stockholders Equity", "Common Stock Equity"],
    "debt": ["Total Debt"],
    "cash": ["Cash And Cash Equivalents", "Cash Cash Equivalents And Short Term Investments"],
    "receivables": ["Accounts Receivable", "Receivables"],
    "shares_diluted": ["Diluted Average Shares", "Ordinary Shares Number", "Share Issued"],
    "dividends": ["Cash Dividends Paid", "Common Stock Dividend Paid"],
}


def statements(symbols: list[str], workers: int = 2, attempts: int = 3) -> pd.DataFrame:
    """Annual statements (up to ~4 years on Yahoo), cached for 30 days, reporting currency."""
    fdir = CACHE / "fundamentals"
    fdir.mkdir(parents=True, exist_ok=True)

    def one(s):
        p = fdir / f"{_safe(s)}.json"
        if _fresh(p, days=30):
            cached = json.loads(p.read_text())
            # Failed or empty fetches are retried after a few hours, not trusted for a month.
            if (cached.get("rows") and not cached.get("error")) or _fresh(p, hours=6):
                return cached
        rec = {"symbol": s, "rows": [], "currency": None}
        try:
            # When Yahoo throttles, it returns empty tables without an error: back off and retry.
            for attempt in range(attempts):
                tk = yf.Ticker(s)
                frames = [f for f in (tk.income_stmt, tk.balance_sheet, tk.cashflow)
                          if f is not None and not f.empty]
                if frames:
                    break
                time.sleep(5 * (attempt + 1))
            try:
                rec["currency"] = tk.info.get("financialCurrency")
            except Exception:  # noqa: BLE001
                pass
            if frames:
                merged = pd.concat(frames)
                merged = merged[~merged.index.duplicated(keep="first")]
                for col in merged.columns:
                    row = {"period_end": pd.Timestamp(col).date().isoformat()}
                    for key, names in ROWS.items():
                        val = None
                        for n in names:
                            if n in merged.index and pd.notna(merged.at[n, col]):
                                val = float(merged.at[n, col])
                                break
                        row[key] = val
                    rec["rows"].append(row)
        except Exception as e:  # noqa: BLE001
            rec["error"] = str(e)[:200]
        p.write_text(json.dumps(rec))
        return rec

    out = []
    for rec in _pool(one, symbols, workers, "statements"):
        for r in rec.get("rows", []):
            out.append({"symbol": rec["symbol"], "currency": rec.get("currency"), **r})
    return pd.DataFrame(out)


# ------------------------------------------------------------------ helpers
def _safe(s: str) -> str:
    return s.replace("/", "_").replace("^", "_").replace("=", "_")


def _fresh(p: Path, days: float = 0, hours: float = 0) -> bool:
    age = timedelta(days=days, hours=hours)
    return p.exists() and datetime.fromtimestamp(p.stat().st_mtime) > datetime.now() - age


def _retry(fn, tries: int = 3):
    for i in range(tries):
        try:
            return fn()
        except Exception:  # noqa: BLE001
            if i == tries - 1:
                raise
            time.sleep(5 * (i + 1))


def _pool(fn, items, workers, label):
    out, done = [], 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(fn, s) for s in items]
        for f in as_completed(futs):
            out.append(f.result())
            done += 1
            if done % 200 == 0:
                log.info("%s %d/%d", label, done, len(items))
    return out
