"""Single-stock profile: everything stored for one company, with return and risk
statistics against the cap-weighted benchmark, all as of a month end.

Monthly total returns drive every statistic. Annualised volatility is the standard
deviation of monthly returns x sqrt(12); rolling windows need a full window of
months before they report a value.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

ROLLING = (12, 36)
# key, months, annualised
HORIZONS = [("1m", 1, False), ("3m", 3, False), ("6m", 6, False), ("1y", 12, False),
            ("3y", 36, True), ("5y", 60, True), ("10y", 120, True)]
RISK_WINDOWS = [("3y", 36), ("5y", 60), ("all", None)]
COMPUTED = ["fcf", "net_debt", "roe", "roe_median", "roic", "leverage", "fcf_conversion", "accruals",
            "sales_growth", "dilution", "n_years"]


def _growth(r: pd.Series, annualise: bool) -> float | None:
    if r.empty:
        return None
    total = float((1 + r.fillna(0)).prod() - 1)
    if not annualise:
        return total
    return (1 + total) ** (12 / len(r)) - 1 if total > -1 else -1.0


def _drawdown(index: pd.Series) -> pd.Series:
    return index / index.cummax() - 1


def monthly_series(px: pd.DataFrame, bench: pd.Series) -> pd.DataFrame:
    """Per month: price data, both return indices (100 at the first month) and rolling risk."""
    d = px.sort_values("date").set_index("date").copy()
    r = d["total_return"].copy()
    b = bench.reindex(d.index).copy()
    r.iloc[0] = np.nan  # the index starts here, so the first month carries no return
    b.iloc[0] = np.nan
    d["bench_return"] = b
    d["index"] = 100 * (1 + r.fillna(0)).cumprod()
    d["bench_index"] = 100 * (1 + b.fillna(0)).cumprod()
    d["relative"] = 100 * d["index"] / d["bench_index"]
    d["drawdown"] = _drawdown(d["index"])
    d["bench_drawdown"] = _drawdown(d["bench_index"])
    for n in ROLLING:
        d[f"corr_{n}"] = r.rolling(n, min_periods=n).corr(b)
        d[f"vol_{n}"] = r.rolling(n, min_periods=n).std() * np.sqrt(12)
        d[f"bench_vol_{n}"] = b.rolling(n, min_periods=n).std() * np.sqrt(12)
    return d.reset_index()


def horizon_returns(m: pd.DataFrame) -> list[dict]:
    rets = m.iloc[1:]
    end = m["date"].iloc[-1]
    out = []
    for key, n, ann in HORIZONS:
        w = rets.iloc[-n:] if len(rets) >= n else None
        out.append({"key": key, "label": key.upper() if key.endswith("y") else key, "annualised": ann,
                    "stock": None if w is None else _growth(w["total_return"], ann),
                    "benchmark": None if w is None else _growth(w["bench_return"], ann)})
    ytd = rets[rets["date"].dt.year == end.year]
    out.insert(3, {"key": "ytd", "label": "YTD", "annualised": False,
                   "stock": _growth(ytd["total_return"], False), "benchmark": _growth(ytd["bench_return"], False)})
    ann = len(rets) >= 12
    out.append({"key": "since", "label": f"Since {m['date'].iloc[0]:%b %Y}", "annualised": ann,
                "stock": _growth(rets["total_return"], ann), "benchmark": _growth(rets["bench_return"], ann)})
    for o in out:
        o["excess"] = None if o["stock"] is None or o["benchmark"] is None else o["stock"] - o["benchmark"]
    return out


def risk_stats(m: pd.DataFrame) -> list[dict]:
    rets = m.iloc[1:]
    out = []
    for key, n in RISK_WINDOWS:
        w = rets if n is None else rets.iloc[-n:]
        if n is not None and len(rets) < n:
            out.append({"key": key, "months": n, "available": False})
            continue
        both = w[["total_return", "bench_return"]].dropna()
        r, b = both["total_return"], both["bench_return"]
        idx = (1 + w["total_return"].fillna(0)).cumprod()
        bidx = (1 + w["bench_return"].fillna(0)).cumprod()
        var_b = b.var()
        out.append({
            "key": key, "months": int(len(w)), "available": True,
            "start": w["date"].iloc[0], "end": w["date"].iloc[-1],
            "vol": r.std() * np.sqrt(12), "bench_vol": b.std() * np.sqrt(12),
            "correlation": r.corr(b), "beta": r.cov(b) / var_b if var_b > 0 else None,
            "tracking_error": (r - b).std() * np.sqrt(12),
            "max_drawdown": float(_drawdown(pd.concat([pd.Series([1.0]), idx])).min()),
            "bench_max_drawdown": float(_drawdown(pd.concat([pd.Series([1.0]), bidx])).min()),
            "best_month": r.max(), "worst_month": r.min(),
            "positive_months": float((r > 0).mean()) if len(r) else None,
            "beat_months": float((r > b).mean()) if len(r) else None,
        })
    return out


def calendar_years(m: pd.DataFrame) -> list[dict]:
    rets = m.iloc[1:]
    out = []
    for year, g in rets.groupby(rets["date"].dt.year):
        s, b = _growth(g["total_return"], False), _growth(g["bench_return"], False)
        out.append({"year": int(year), "months": int(len(g)), "partial": len(g) < 12,
                    "stock": s, "benchmark": b, "excess": s - b})
    return out


def fundamentals(statements: pd.DataFrame, stmt_metrics: pd.DataFrame, company_id: str,
                 as_of: pd.Timestamp) -> pd.DataFrame:
    """Every stored statement column plus the derived ratios, for years filed by `as_of`."""
    raw = statements[statements["company_id"] == company_id]
    calc = stmt_metrics.loc[stmt_metrics["company_id"] == company_id, ["fiscal_year"] + COMPUTED]
    f = raw.merge(calc, on="fiscal_year", how="left").sort_values("fiscal_year")
    return f[f["filing_date"] <= as_of]
