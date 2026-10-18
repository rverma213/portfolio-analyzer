"""Spec B metrics, computed point in time.

Statement metrics are computed once per (company, fiscal year) over the
5-year window ending in that year. A snapshot at any as-of date then takes, for
each company, the latest statement whose *filing date* is on or before that
date (filing date + 0 days; the month-end snapshot is already after the filing)
and joins the market data for that month. Nothing published after the as-of
date can leak in.

Annual statements stand in for TTM figures: "TTM net income" in the spec is the
last reported fiscal year here. Quarterly data would tighten this.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

WINDOW = 5
GROWTH_YEARS = 3
STALE_MONTHS = 18  # a statement older than this is treated as missing


def statement_metrics(statements: pd.DataFrame) -> pd.DataFrame:
    s = statements.sort_values(["company_id", "fiscal_year"]).copy()
    g = s.groupby("company_id", sort=False)

    s["filing_estimated"] = (s["filing_estimated"].fillna(False).astype(bool)
                             if "filing_estimated" in s else False)
    s["fcf"] = s["cfo"] - s["capex"]
    s["avg_equity"] = (s["equity"] + g["equity"].shift(1).fillna(s["equity"])) / 2
    s["avg_assets"] = (s["total_assets"] + g["total_assets"].shift(1).fillna(s["total_assets"])) / 2
    s["roe"] = np.where(s["avg_equity"] > 0, s["net_income"] / s["avg_equity"], np.nan)
    s["is_loss"] = (s["net_income"] < 0).astype(float)
    s["pos_fcf"] = (s["fcf"] > 0).astype(float)

    def roll(col, fn, window=WINDOW):
        return g[col].transform(lambda x: getattr(x.rolling(window, min_periods=1), fn)())

    s["n_years"] = g["fiscal_year"].transform(lambda x: x.rolling(WINDOW, min_periods=1).count())
    s["loss_years"] = roll("is_loss", "sum")
    s["positive_fcf_years"] = roll("pos_fcf", "sum")
    s["roe_median"] = roll("roe", "median")
    s["roe_stability"] = g["roe"].transform(lambda x: x.rolling(WINDOW, min_periods=3).std(ddof=0))
    fcf_sum = roll("fcf", "sum")
    ni_sum = roll("net_income", "sum")
    s["fcf_conversion"] = np.where(ni_sum > 0, fcf_sum / ni_sum, np.nan)
    s["accruals"] = (s["net_income"] - s["cfo"]) / s["avg_assets"]

    invested = s["debt"] + s["equity"] - s["cash"]
    s["roic"] = np.where(invested > 0, s["ebit"] * (1 - s["tax_rate"]) / invested, np.nan)

    s["net_debt"] = s["debt"] - s["cash"]
    s["leverage"] = np.where(
        s["ebitda"] > 0, s["net_debt"] / s["ebitda"],
        np.where(s["net_debt"] > 0, 99.0, 0.0))  # net debt on negative EBITDA fails

    def cagr(col):
        prev = g[col].shift(GROWTH_YEARS)
        ratio = s[col] / prev
        return np.where((prev > 0) & (s[col] > 0), ratio ** (1 / GROWTH_YEARS) - 1, np.nan)

    s["sales_growth"] = cagr("revenue")
    s["receivables_growth"] = cagr("receivables")
    s["receivables_gap"] = s["receivables_growth"] - s["sales_growth"]
    s["dilution"] = cagr("shares_diluted")

    keep = ["company_id", "fiscal_year", "period_end", "filing_date", "filing_estimated", "n_years", "revenue",
            "net_income", "fcf", "equity", "debt", "cash", "ebitda", "roe", "loss_years",
            "positive_fcf_years", "roe_median", "roe_stability", "fcf_conversion", "accruals",
            "roic", "net_debt", "leverage", "sales_growth", "receivables_growth",
            "receivables_gap", "dilution"]
    return s[keep].reset_index(drop=True)


def snapshot(as_of: pd.Timestamp, stmt_metrics: pd.DataFrame, monthly: pd.DataFrame,
             companies: pd.DataFrame) -> pd.DataFrame:
    """One row per company alive at `as_of`: market data + latest filed statement metrics."""
    month = monthly.loc[monthly["date"] <= as_of, "date"].max()
    mkt = monthly.loc[monthly["date"] == month,
                      ["company_id", "mcap_usd", "adv_usd", "in_benchmark", "price"]]
    filed = stmt_metrics[stmt_metrics["filing_date"] <= month]
    latest = filed.sort_values("filing_date").groupby("company_id").tail(1)
    latest = latest[latest["period_end"] >= month - pd.DateOffset(months=STALE_MONTHS)]

    snap = mkt.merge(companies[["company_id", "ticker", "name", "country", "region", "sector"]],
                     on="company_id", how="left")
    snap = snap.merge(latest, on="company_id", how="left")
    snap["n_years"] = snap["n_years"].fillna(0)
    snap["filing_estimated"] = snap["filing_estimated"].astype("boolean").fillna(False).astype(bool)

    ev = snap["mcap_usd"] + snap["debt"] - snap["cash"]
    snap["earnings_yield"] = snap["net_income"] / snap["mcap_usd"]
    snap["fcf_yield"] = np.where(ev > 0, snap["fcf"] / ev, np.nan)
    snap["book_to_price"] = snap["equity"] / snap["mcap_usd"]
    snap["ev_usd"] = ev
    snap["as_of"] = month
    return snap.reset_index(drop=True)


def history(company_id: str, stmt_metrics: pd.DataFrame) -> pd.DataFrame:
    return stmt_metrics[stmt_metrics["company_id"] == company_id].sort_values("fiscal_year")
