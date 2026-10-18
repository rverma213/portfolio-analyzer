"""SEC EDGAR XBRL company facts -> annual statements with real filing dates (US).

For every fiscal year, each value is taken from the FIRST annual report that
contained it (minimum `filed` date). Later restatements are ignored, so the
data is point in time: a backtest only sees what was published then.

Set SEC_USER_AGENT to identify yourself to the SEC, e.g.
    set SEC_USER_AGENT=YourName research your@email
SEC asks for contact details in the User-Agent; the default omits them.
"""
from __future__ import annotations

import gzip
import json
import logging
import os
import threading
import time
from datetime import datetime, timedelta

import pandas as pd
import requests

from ...config import RAW_DIR

log = logging.getLogger(__name__)
CACHE = RAW_DIR / "sec"
UA = os.environ.get("SEC_USER_AGENT", "small-cap-portfolio/0.1 research tool")
ANNUAL_FORMS = {"10-K", "10-K/A", "10-KT", "20-F", "20-F/A", "40-F"}

_lock = threading.Lock()
_last = [0.0]


def _get(url: str) -> requests.Response:
    """GET with SEC's rate limit (≤ 10 requests a second) respected across threads."""
    with _lock:
        wait = 0.12 - (time.time() - _last[0])
        if wait > 0:
            time.sleep(wait)
        _last[0] = time.time()
    r = requests.get(url, headers={"User-Agent": UA, "Accept-Encoding": "gzip, deflate"}, timeout=60)
    return r


def ticker_map() -> dict[str, int]:
    """Exchange ticker (Yahoo style, e.g. BRK-B) -> CIK. Cached for a week."""
    p = CACHE / "company_tickers.json"
    if not (p.exists() and datetime.fromtimestamp(p.stat().st_mtime) > datetime.now() - timedelta(days=7)):
        p.parent.mkdir(parents=True, exist_ok=True)
        r = _get("https://www.sec.gov/files/company_tickers.json")
        if r.status_code == 403:
            raise RuntimeError(
                "SEC refused the request (403). www.sec.gov requires contact details in the User-Agent. "
                "Set the environment variable SEC_USER_AGENT, e.g. 'Jane Smith jane@example.com', and rerun.")
        r.raise_for_status()
        p.write_bytes(r.content)
    data = json.loads(p.read_text())
    return {v["ticker"].upper().replace(".", "-"): int(v["cik_str"]) for v in data.values()}


def company_facts(cik: int, max_age_days: int = 30) -> dict | None:
    p = CACHE / "companyfacts" / f"CIK{cik:010d}.json.gz"
    if p.exists() and datetime.fromtimestamp(p.stat().st_mtime) > datetime.now() - timedelta(days=max_age_days):
        return json.loads(gzip.decompress(p.read_bytes()))
    r = _get(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json")
    if r.status_code == 404:
        return None
    r.raise_for_status()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(gzip.compress(r.content))  # raw file kept unchanged (compressed)
    return r.json()


# Concept priority lists. Duration (flow) items need a ~1-year period; instants are point in time.
FLOWS = {
    "revenue": ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax",
                "RevenueFromContractWithCustomerIncludingAssessedTax", "SalesRevenueNet", "SalesRevenueGoodsNet"],
    "net_income": ["NetIncomeLoss", "NetIncomeLossAvailableToCommonStockholdersBasic", "ProfitLoss"],
    "ebit": ["OperatingIncomeLoss"],
    "dna": ["DepreciationDepletionAndAmortization", "DepreciationAndAmortization",
            "DepreciationAmortizationAndAccretionNet", "Depreciation"],
    "pretax": ["IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest",
               "IncomeLossFromContinuingOperationsBeforeIncomeTaxesMinorityInterestAndIncomeLossFromEquityMethodInvestments"],
    "tax": ["IncomeTaxExpenseBenefit"],
    "cfo": ["NetCashProvidedByUsedInOperatingActivities",
            "NetCashProvidedByUsedInOperatingActivitiesContinuingOperations"],
    "capex": ["PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets"],
    "dividends": ["PaymentsOfDividends", "PaymentsOfDividendsCommonStock"],
    "shares_diluted": ["WeightedAverageNumberOfDilutedSharesOutstanding"],
}
INSTANTS = {
    "total_assets": ["Assets"],
    "equity": ["StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"],
    "cash": ["CashAndCashEquivalentsAtCarryingValue",
             "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents", "Cash"],
    "receivables": ["AccountsReceivableNetCurrent", "ReceivablesNetCurrent"],
    "debt_noncurrent": ["LongTermDebtNoncurrent", "LongTermDebtAndCapitalLeaseObligations", "LongTermNotesPayable"],
    "debt_current": ["LongTermDebtCurrent", "DebtCurrent", "LongTermDebtAndCapitalLeaseObligationsCurrent"],
    "debt_short": ["ShortTermBorrowings"],
    "debt_total": ["LongTermDebt", "LongTermDebtAndCapitalLeaseObligationsIncludingCurrentMaturities",
                   "DebtAndCapitalLeaseObligations"],
}


def _facts(gaap: dict, concept: str, unit: str, annual_duration: bool) -> pd.DataFrame:
    units = gaap.get(concept, {}).get("units", {})
    rows = units.get(unit) or (units.get("shares") if unit == "shares" else None) or []
    df = pd.DataFrame(rows)
    if df.empty or "form" not in df:
        return pd.DataFrame()
    df = df[df["form"].isin(ANNUAL_FORMS)].copy()
    df["end"] = pd.to_datetime(df["end"])
    df["filed"] = pd.to_datetime(df["filed"])
    if annual_duration:
        if "start" not in df:
            return pd.DataFrame()
        days = (df["end"] - pd.to_datetime(df["start"])).dt.days
        df = df[(days >= 330) & (days <= 400)]
    elif "start" in df:
        df = df[df["start"].isna()]
    # First publication of each period's value = point-in-time original.
    return df.sort_values("filed").drop_duplicates("end")[["end", "val", "filed"]]


def _pick(gaap: dict, concepts: list[str], unit: str, annual: bool) -> pd.DataFrame:
    """Combine concepts in priority order: for each period end, first concept with a value wins."""
    out = pd.DataFrame()
    for c in concepts:
        f = _facts(gaap, c, unit, annual)
        if f.empty:
            continue
        f = f[~f["end"].isin(out["end"])] if len(out) else f
        out = pd.concat([out, f])
    return out


def annual_statements(facts: dict) -> pd.DataFrame:
    gaap = facts.get("facts", {}).get("us-gaap")
    if not gaap:
        return pd.DataFrame()
    flows = {k: _pick(gaap, v, "shares" if k == "shares_diluted" else "USD", True) for k, v in FLOWS.items()}
    anchor = pd.concat([flows["revenue"], flows["net_income"]])
    if anchor.empty:
        return pd.DataFrame()
    # Fiscal year ends = period ends of annual revenue / net income; filing date = first annual filing.
    periods = anchor.groupby("end")["filed"].min().reset_index().rename(columns={"end": "period_end",
                                                                                  "filed": "filing_date"})
    out = periods.copy()
    for k, f in flows.items():
        out[k] = out["period_end"].map(f.set_index("end")["val"]) if len(f) else None
    for k, concepts in INSTANTS.items():
        f = _pick(gaap, concepts, "USD", False)
        out[k] = out["period_end"].map(f.set_index("end")["val"]) if len(f) else None
    return out


def to_schema(df: pd.DataFrame) -> pd.DataFrame:
    """Map raw SEC fields to the statements table columns."""
    if df.empty:
        return df
    d = df.copy()
    num = lambda c: pd.to_numeric(d.get(c), errors="coerce")  # noqa: E731
    parts = pd.concat([num("debt_noncurrent"), num("debt_current"), num("debt_short")], axis=1)
    debt = parts.sum(axis=1, min_count=1)
    debt = debt.fillna(num("debt_total").add(num("debt_short").fillna(0), fill_value=0)).fillna(0.0)
    tax_rate = (num("tax") / num("pretax")).where(num("pretax") > 0).clip(0, 0.4).fillna(0.25)
    ebit = num("ebit")
    return pd.DataFrame({
        "period_end": d["period_end"], "filing_date": d["filing_date"],
        "revenue": num("revenue"), "ebit": ebit, "ebitda": ebit + num("dna").fillna(0),
        "net_income": num("net_income"), "cfo": num("cfo"), "capex": num("capex").abs(),
        "total_assets": num("total_assets"), "equity": num("equity"), "debt": debt, "cash": num("cash"),
        "receivables": num("receivables"), "shares_diluted": num("shares_diluted"),
        "tax_rate": tax_rate, "dividends": num("dividends").abs(),
        "filing_estimated": False, "source": "sec",
    })
