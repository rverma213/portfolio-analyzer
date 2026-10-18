"""Build the real-data DuckDB from an iShares holdings file + Yahoo + SEC EDGAR.

    python -m smallcap.cli build-real [--holdings FILE] [--limit N]

Steps (each cached, so reruns are incremental):
1. Parse the latest archived iShares WSML holdings file (the universe).
2. Resolve each holding to a Yahoo symbol; unresolved names are written to
   data/unresolved_symbols.csv for manual mapping in data/symbol_overrides.csv.
3. Monthly prices, volume and FX from Yahoo -> total return, USD price,
   market cap and ADV in USD.
4. Annual statements: SEC EDGAR for US listings (full history, real filing
   dates); Yahoo for everything else (about 4 years, filing date estimated as
   period end + 90 days and flagged).
5. Save companies / statements / monthly to DuckDB and write
   data/real_report.json describing coverage and known limitations.

Known limitations, also shown in the app:
* Membership: only today's constituents are known, so every name is treated as
  a benchmark member throughout history (survivorship bias in backtests until a
  history of holdings files has been archived).
* Historical market caps assume today's share count (split-safe; ignores
  issuance and buybacks between then and now).
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

import numpy as np
import pandas as pd

from ...config import DATA_DIR
from .. import ishares, store
from . import sec, yahoo
from .symbols import candidates, load_overrides

log = logging.getLogger(__name__)
FILING_LAG_ESTIMATE = pd.Timedelta(days=90)
REPORT = DATA_DIR / "real_report.json"


def build(holdings_path: str | Path | None = None, limit: int | None = None, use_sec: bool = True) -> dict:
    path = Path(holdings_path) if holdings_path else ishares.latest_archived()
    if path is None:
        raise FileNotFoundError("No holdings file. Download WSML holdings from iShares and run: "
                                "python -m smallcap.cli import-holdings <file>")
    as_of = ishares.holdings_date(path)
    h = ishares.parse(path)
    if limit:
        h = h.sort_values("weight", ascending=False).head(limit).reset_index(drop=True)
    log.info("holdings: %d equities from %s (as of %s)", len(h), path.name, as_of)

    # ---- 1. symbols
    h, unresolved = resolve_symbols(h)
    unresolved.to_csv(DATA_DIR / "unresolved_symbols.csv", index=False)
    log.info("symbols: %d resolved, %d unresolved", len(h), len(unresolved))

    # ---- 2. prices, FX, quote info
    px = yahoo.download_monthly(h["symbol"].tolist())
    info = yahoo.quote_info(h["symbol"].tolist()).set_index("symbol")
    h["quote_currency"] = h["symbol"].map(info["currency"]).fillna(h["currency"])
    h["shares_now"] = h["symbol"].map(info["shares"])
    fx = yahoo.fx_monthly(set(h["quote_currency"].dropna()) | set(h["currency"].dropna()))
    h = fix_price_units(h, px, fx)

    # ---- 3. statements (before monthly: they back up missing share counts)
    stmts = build_statements(h, fx, use_sec=use_sec)
    latest_shares = stmts.sort_values("period_end").groupby("company_id")["shares_diluted"].last()
    h["shares_source"] = np.where(h["shares_now"].notna(), "quote", None)
    fallback = h["shares_now"].isna() & h["symbol"].map(latest_shares).notna()
    h.loc[fallback, "shares_now"] = h.loc[fallback, "symbol"].map(latest_shares)
    h.loc[fallback, "shares_source"] = "statements"
    log.info("share counts: %d from quotes, %d from statements, %d missing",
             (h["shares_source"] == "quote").sum(), fallback.sum(), h["shares_now"].isna().sum())
    monthly = build_monthly(h, px, fx)

    companies = build_companies(h, monthly)
    keep = set(companies["company_id"])
    monthly = monthly[monthly["company_id"].isin(keep)]
    stmts = stmts[stmts["company_id"].isin(keep)]

    store.save({"companies": companies, "statements": stmts, "monthly": monthly}, source="real")
    report = coverage_report(h, unresolved, companies, stmts, monthly, as_of, path)
    REPORT.write_text(json.dumps(report, indent=2, default=str))
    return report


# --------------------------------------------------------------------------- symbols
def resolve_symbols(h: pd.DataFrame, max_tries: int = 4) -> tuple[pd.DataFrame, pd.DataFrame]:
    overrides = load_overrides()
    h = h.copy()
    h["cands"] = [
        [overrides[(t.upper(), e)]] if (t.upper(), e) in overrides else candidates(t, e, c)
        for t, e, c in zip(h["ticker"], h["exchange"], h["country"])
    ]
    h["symbol"] = None
    for i in range(max_tries):
        todo = h["symbol"].isna() & h["cands"].map(lambda c: len(c) > i)
        if not todo.any():
            break
        trial = h.loc[todo, "cands"].map(lambda c: c[i])
        ok = yahoo.has_prices(sorted(set(trial)))
        h.loc[todo, "symbol"] = trial.where(trial.map(ok), None)
    unresolved = h[h["symbol"].isna()][["ticker", "name", "exchange", "country", "weight", "cands"]]
    resolved = h[h["symbol"].notna()].drop(columns="cands")
    # Two holdings resolving to one symbol (share classes): keep the larger weight.
    resolved = resolved.sort_values("weight", ascending=False).drop_duplicates("symbol")
    return resolved.reset_index(drop=True), unresolved.reset_index(drop=True)


# ------------------------------------------------------------------------ price units
MINOR_CODE = {"GBP": "GBp", "ILS": "ILA", "ZAR": "ZAc"}


def fix_price_units(h: pd.DataFrame, px: pd.DataFrame, fx: pd.DataFrame) -> pd.DataFrame:
    """Detect listings quoted in pence/agorot/cents by comparing with the iShares USD price.

    Yahoo's quote currency (which says GBp vs GBP) is not always available, e.g. when
    throttled. The holdings file's price is in USD, so a Yahoo close that converts to
    ~100x the iShares price means the listing is quoted in minor units.
    """
    h = h.copy()
    last = px.sort_values("date").groupby("symbol").tail(1).set_index("symbol")
    usd = pd.Series(np.nan, index=h.index)
    for c in h["quote_currency"].dropna().unique():
        m = h["quote_currency"] == c
        syms = h.loc[m, "symbol"]
        rate = yahoo.to_usd(c, fx, last["date"].reindex(syms).fillna(fx.index.max()))
        usd[m] = last["close"].reindex(syms).to_numpy() * rate
    ratio = usd / h["price"]
    minor = h["quote_currency"].isin(MINOR_CODE) & ratio.between(30, 300)
    h.loc[minor, "quote_currency"] = h.loc[minor, "quote_currency"].map(MINOR_CODE)
    h["price_check"] = ratio.where(~minor, ratio / 100)
    log.info("price units: %d listings switched to minor currency units", minor.sum())
    return h


# --------------------------------------------------------------------------- monthly
def build_monthly(h: pd.DataFrame, px: pd.DataFrame, fx: pd.DataFrame) -> pd.DataFrame:
    meta = h.set_index("symbol")
    px = px[px["symbol"].isin(meta.index)].sort_values(["symbol", "date"]).copy()
    cur = px["symbol"].map(meta["quote_currency"])
    rate = np.full(len(px), np.nan)
    for c in cur.dropna().unique():
        m = (cur == c).to_numpy()
        rate[m] = yahoo.to_usd(c, fx, px.loc[m, "date"])
    px["fx"] = rate
    px["price_usd"] = px["close"] * px["fx"]
    px["total_return"] = px.groupby("symbol")["adj_close"].pct_change()
    # Guard against bad prints: monthly moves beyond -95%/+500% are treated as missing.
    px.loc[(px["total_return"] < -0.95) | (px["total_return"] > 5), "total_return"] = np.nan

    # Market cap: today's shares x price (split-adjusted close), so history is split-safe.
    last = px.groupby("symbol").tail(1).set_index("symbol")
    shares = meta["shares_now"].reindex(last.index)
    mcap_now = shares * last["price_usd"]
    px["mcap_usd"] = px["symbol"].map(mcap_now) * px["close"] / px["symbol"].map(last["close"])
    days = px["date"].dt.days_in_month * 21 / 30.4
    px["adv_usd"] = px["volume"] * px["price_usd"] / days
    px["in_benchmark"] = True  # see module docstring: membership history not yet known
    out = px.rename(columns={"symbol": "company_id", "price_usd": "price"})
    return out[["company_id", "date", "total_return", "price", "mcap_usd", "adv_usd", "in_benchmark"]] \
        .dropna(subset=["price"]).reset_index(drop=True)


# ------------------------------------------------------------------------ statements
COLUMNS = ["company_id", "fiscal_year", "period_end", "filing_date", "revenue", "ebitda", "ebit", "net_income",
           "cfo", "capex", "total_assets", "equity", "debt", "cash", "receivables", "shares_diluted",
           "tax_rate", "dividends", "filing_estimated", "source"]


def build_statements(h: pd.DataFrame, fx: pd.DataFrame, use_sec: bool = True) -> pd.DataFrame:
    frames = []
    us = h[h["symbol"].map(lambda s: "." not in s) & (h["country"] == "United States")]
    done: set[str] = set()
    if use_sec and len(us):
        cik = sec.ticker_map()
        for i, s in enumerate(us["symbol"]):
            if i and i % 200 == 0:
                log.info("SEC %d/%d", i, len(us))
            c = cik.get(s.upper())
            if not c:
                continue
            try:
                facts = sec.company_facts(c)
            except Exception as e:  # noqa: BLE001
                log.warning("SEC %s: %s", s, e)
                continue
            df = sec.to_schema(sec.annual_statements(facts)) if facts else pd.DataFrame()
            if len(df) >= 2:
                frames.append(df.assign(company_id=s))
                done.add(s)
    rest = [s for s in h["symbol"] if s not in done]
    log.info("statements: %d from SEC, %d from Yahoo", len(done), len(rest))
    yf_rows = yahoo.statements(rest)
    if len(yf_rows):
        # Reporting currency can differ from the listing currency (e.g. CNY for a HK listing).
        needed = {yahoo.MINOR_UNITS.get(c, (c, 1))[0] for c in yf_rows["currency"].dropna().unique()}
        missing = needed - set(fx.columns)
        if missing:
            fx = fx.join(yahoo.fx_monthly(missing).drop(columns="USD"), how="outer").sort_index().ffill()
        frames.append(_yahoo_to_schema(yf_rows, h, fx))
    if not frames:
        return pd.DataFrame(columns=COLUMNS)
    st = pd.concat(frames, ignore_index=True)
    st["period_end"] = pd.to_datetime(st["period_end"])
    st["filing_date"] = pd.to_datetime(st["filing_date"])
    st["fiscal_year"] = st["period_end"].dt.year
    st = st.dropna(subset=["revenue", "net_income"], how="all")
    st = st.sort_values("period_end").drop_duplicates(["company_id", "fiscal_year"], keep="last")
    return st[COLUMNS].reset_index(drop=True)


def _yahoo_to_schema(rows: pd.DataFrame, h: pd.DataFrame, fx: pd.DataFrame) -> pd.DataFrame:
    meta = h.set_index("symbol")
    d = rows.copy()
    d["period_end"] = pd.to_datetime(d["period_end"])
    ccy = d["currency"].fillna(d["symbol"].map(meta["quote_currency"]))
    ccy = ccy.map(lambda c: yahoo.MINOR_UNITS.get(c, (c, 1))[0] if isinstance(c, str) else c)
    rate = np.full(len(d), np.nan)
    for c in ccy.dropna().unique():
        m = (ccy == c).to_numpy()
        rate[m] = yahoo.to_usd(c, fx, d.loc[m, "period_end"])
    money = ["revenue", "net_income", "ebit", "ebitda", "cfo", "capex", "total_assets", "equity", "debt",
             "cash", "receivables", "dividends", "pretax", "tax"]
    for col in money:
        d[col] = pd.to_numeric(d[col], errors="coerce") * rate
    tax_rate = (d["tax"] / d["pretax"]).where(d["pretax"] > 0).clip(0, 0.4).fillna(0.25)
    return pd.DataFrame({
        "company_id": d["symbol"], "period_end": d["period_end"],
        "filing_date": d["period_end"] + FILING_LAG_ESTIMATE,
        "revenue": d["revenue"], "ebit": d["ebit"], "ebitda": d["ebitda"].fillna(d["ebit"]),
        "net_income": d["net_income"], "cfo": d["cfo"], "capex": d["capex"].abs(),
        "total_assets": d["total_assets"], "equity": d["equity"], "debt": d["debt"].fillna(0.0),
        "cash": d["cash"], "receivables": d["receivables"], "shares_diluted": d["shares_diluted"],
        "tax_rate": tax_rate, "dividends": d["dividends"].abs(),
        "filing_estimated": True, "source": "yahoo",
    })


# ------------------------------------------------------------------------- companies
def build_companies(h: pd.DataFrame, monthly: pd.DataFrame) -> pd.DataFrame:
    first = monthly.groupby("company_id")["date"].min()
    c = h[h["symbol"].isin(first.index)]
    return pd.DataFrame({
        "company_id": c["symbol"], "ticker": c["symbol"], "name": c["name"], "country": c["country"],
        "region": c["region"], "sector": c["sector"], "listed_date": c["symbol"].map(first),
        "delisted_date": pd.NaT, "delist_reason": None, "delist_return": np.nan,
        "bench_weight_file": c["weight"], "local_ticker": c["ticker"], "exchange": c["exchange"],
    }).reset_index(drop=True)


def coverage_report(h, unresolved, companies, stmts, monthly, as_of, path) -> dict:
    yrs = stmts.groupby("company_id").size()
    src = stmts.groupby("company_id")["source"].first()
    w = h.set_index("symbol")["weight"]
    return {
        "holdings_file": str(path), "holdings_as_of": as_of,
        "holdings": int(len(h) + len(unresolved)),
        "resolved": int(len(h)), "unresolved": int(len(unresolved)),
        "unresolved_weight": float(unresolved["weight"].sum()),
        "with_prices": int(len(companies)),
        "with_statements": int(yrs.size),
        "statements_from_sec": int((src == "sec").sum()),
        "statements_from_yahoo": int((src == "yahoo").sum()),
        "with_5y_history": int((yrs >= 5).sum()),
        "weight_with_5y_history": float(w.reindex(yrs[yrs >= 5].index).sum()),
        "short_price_history": sorted(monthly.groupby("company_id").size().loc[lambda x: x < 24].index),
        "no_statements": sorted(set(companies["company_id"]) - set(yrs.index)),
        "missing_market_cap": sorted(set(companies["company_id"])
                                     - set(monthly.dropna(subset=["mcap_usd"])["company_id"])),
        "shares_from_statements": sorted(h.loc[h["shares_source"] == "statements", "symbol"]),
        # Yahoo close in USD vs iShares USD price: far from 1 means a units or symbol problem.
        "price_mismatch": sorted(h.loc[h["price_check"].notna() & ~h["price_check"].between(0.5, 2), "symbol"]),
        "first_month": str(monthly["date"].min().date()) if len(monthly) else None,
        "last_month": str(monthly["date"].max().date()) if len(monthly) else None,
        "limitations": [
            "Benchmark membership history is not known yet: every current constituent is treated as a member "
            "throughout, so backtests have survivorship bias until daily holdings files are archived.",
            "Historical market caps assume today's share count (split-safe, ignores later issuance/buybacks).",
            "Non-US statements come from Yahoo: about 4 annual periods, filing dates estimated as period end "
            "+ 90 days. With the 5-year history filter most non-US names cannot pass.",
        ],
    }
