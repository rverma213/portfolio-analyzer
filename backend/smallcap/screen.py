"""Spec B screen: hard filters -> pillar scores -> composite -> research list.

Every company keeps the full list of filters it failed, so the front end can
explain an exclusion as well as a rank.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .config import FINANCIAL_METRICS, FINANCIAL_SECTORS, METRICS, PILLARS, ScreenParams

# (key, label, applies to financials?)
FILTERS = [
    ("universe", "Benchmark or eligible off-benchmark", True),
    ("liquidity", "ADV ≥ $1m", True),
    ("history", "≥ 5 years of statements (4 if from Yahoo)", True),
    ("fcf_record", "Positive FCF in ≥ 3 of 5 years", False),
    ("profitable", "Positive equity and ROE", True),
    ("leverage", "Net debt / EBITDA < 3x", False),
    ("roe_vs_coe", "5y median ROE ≥ cost of equity", True),
    ("dilution", "Share count growth ≤ 5% a year", True),
    ("receivables", "Receivables growth ≤ sales growth + 15pp", False),
]


@dataclass
class ScreenResult:
    as_of: pd.Timestamp
    frame: pd.DataFrame        # every company alive at as_of, with filter flags and scores
    funnel: list[dict]
    params: ScreenParams

    @property
    def passed(self) -> pd.DataFrame:
        f = self.frame
        return f[f["passed"] & ~f["is_financial"]].sort_values("rank")

    @property
    def financials(self) -> pd.DataFrame:
        f = self.frame
        return f[f["passed"] & f["is_financial"]].sort_values("fin_rank")

    @property
    def research_list(self) -> pd.DataFrame:
        return self.passed.head(self.params.research_list_size)


def apply_filters(snap: pd.DataFrame, p: ScreenParams) -> pd.DataFrame:
    f = snap.copy()
    f["is_financial"] = f["sector"].isin(FINANCIAL_SECTORS)
    f["cost_of_equity"] = f["region"].map(p.cost_of_equity)
    f["roe_spread"] = f["roe_median"] - f["cost_of_equity"]

    estimated = (f["filing_estimated"].fillna(False).astype(bool) if "filing_estimated" in f
                 else pd.Series(False, index=f.index))
    bench_max = f.loc[f["in_benchmark"], "mcap_usd"].max()
    off_bench_ok = (~f["in_benchmark"]) & (f["mcap_usd"] <= bench_max) & (f["mcap_usd"] >= 1e8)
    checks = {
        "universe": f["in_benchmark"] | (p.allow_off_benchmark & off_bench_ok),
        "liquidity": f["adv_usd"] >= p.min_adv_usd,
        "history": f["n_years"] >= np.where(estimated, p.min_years_estimated, p.min_years),
        "fcf_record": f["positive_fcf_years"] >= p.min_positive_fcf_years,
        "profitable": (f["equity"] > 0) & (f["roe"] > 0),
        "leverage": f["leverage"] < p.max_net_debt_ebitda,
        "roe_vs_coe": (f["roe_spread"] >= 0) if p.require_roe_above_coe else pd.Series(True, f.index),
        "dilution": f["dilution"].fillna(0) <= p.max_dilution,
        "receivables": f["receivables_gap"].fillna(0) <= p.max_receivables_gap,
    }
    failed = pd.Series([[] for _ in range(len(f))], index=f.index)
    for key, _, applies_fin in FILTERS:
        ok = checks[key].fillna(False).astype(bool)
        if not applies_fin:
            ok = ok | f["is_financial"]
        f[f"f_{key}"] = ok
        failed = failed.combine(ok, lambda lst, good, k=key: lst if good else lst + [k])
    f["failed"] = failed
    f["first_failed"] = failed.map(lambda x: x[0] if x else None)
    f["passed"] = failed.map(len) == 0
    return f


def funnel(f: pd.DataFrame) -> list[dict]:
    steps, remaining = [], len(f)
    steps.append({"key": "alive", "label": "Listed companies", "remaining": remaining, "removed": 0})
    alive = pd.Series(True, index=f.index)
    for key, label, _ in FILTERS:
        alive_next = alive & f[f"f_{key}"]
        removed = int(alive.sum() - alive_next.sum())
        alive = alive_next
        steps.append({"key": key, "label": label, "remaining": int(alive.sum()), "removed": removed})
    n_fin = int((alive & f["is_financial"]).sum())
    steps.append({"key": "financials", "label": "Financials → separate list",
                  "remaining": int(alive.sum()) - n_fin, "removed": n_fin})
    return steps


def percentile_scores(f: pd.DataFrame, metrics: dict[str, tuple[str, bool]],
                      min_group: int, by_sector: bool = True) -> pd.DataFrame:
    """Winsorise at 1st/99th percentile, then rank 0-100 within sector x region.

    Groups smaller than `min_group` fall back to region, then to the whole set.
    Missing values score a neutral 50 and are counted in `missing_metrics`.
    """
    out = pd.DataFrame(index=f.index)
    sizes_sr = (f.groupby(["sector", "region"])["company_id"].transform("count") if by_sector
                else pd.Series(0, index=f.index))
    sizes_r = f.groupby("region")["company_id"].transform("count")
    level = np.where(sizes_sr >= min_group, "sector_region",
                     np.where(sizes_r >= min_group, "region", "all"))
    keys = {
        "sector_region": f["sector"] + "|" + f["region"],
        "region": f["region"],
        "all": pd.Series("all", index=f.index),
    }
    group_key = pd.Series(np.select([level == k for k in keys], [keys[k] for k in keys]), index=f.index)

    for metric, (_, higher) in metrics.items():
        x = f[metric].astype(float).replace([np.inf, -np.inf], np.nan)
        lo, hi = x.quantile(0.01), x.quantile(0.99)
        x = x.clip(lo, hi)
        r = x.groupby(group_key).rank(ascending=higher, method="average")
        n = x.groupby(group_key).transform("count")
        score = np.where(n > 1, (r - 1) / (n - 1) * 100, 50.0)
        out[f"s_{metric}"] = pd.Series(score, index=f.index).where(x.notna(), 50.0)
    out["missing_metrics"] = f[list(metrics)].isna().sum(axis=1)
    out["score_group"] = level
    return out


def composite(scores: pd.DataFrame, metrics: dict[str, tuple[str, bool]],
              weights: dict[str, float]) -> pd.DataFrame:
    out = pd.DataFrame(index=scores.index)
    pillars = sorted({p for p, _ in metrics.values()}, key=lambda x: (PILLARS + ["Value"]).index(x))
    for pillar in pillars:
        cols = [f"s_{m}" for m, (pp, _) in metrics.items() if pp == pillar]
        out[f"p_{pillar}"] = scores[cols].mean(axis=1)
    w = np.array([weights.get(p, 1.0) for p in pillars], dtype=float)
    w = w / w.sum() if w.sum() > 0 else np.full(len(pillars), 1 / len(pillars))
    out["composite"] = out[[f"p_{p}" for p in pillars]].to_numpy() @ w
    return out


def run(snap: pd.DataFrame, p: ScreenParams) -> ScreenResult:
    f = apply_filters(snap, p)
    steps = funnel(f)

    main = f["passed"] & ~f["is_financial"]
    f["composite"] = np.nan
    f["rank"] = np.nan
    f["rank_pct"] = np.nan
    if main.any():
        sc = percentile_scores(f[main], METRICS, p.min_group_size)
        comp = composite(sc, METRICS, p.pillar_weights)
        for c in list(sc.columns) + list(comp.columns):
            f[c] = pd.concat([sc, comp], axis=1)[c]
        f.loc[main, "rank"] = f.loc[main, "composite"].rank(ascending=False, method="first")
        f.loc[main, "rank_pct"] = f.loc[main, "rank"] / main.sum()

    fin = f["passed"] & f["is_financial"]
    f["fin_rank"] = np.nan
    if fin.any():
        sc = percentile_scores(f[fin], FINANCIAL_METRICS, p.min_group_size, by_sector=False)
        comp = composite(sc, FINANCIAL_METRICS, {"Returns": 1, "Earnings": 1, "Value": 1})
        both = pd.concat([sc, comp], axis=1)
        for c in both.columns:
            f[f"fin_{c}"] = both[c]
        f.loc[fin, "fin_rank"] = f.loc[fin, "fin_composite"].rank(ascending=False, method="first")

    f["research_list"] = main & (f["rank"] <= p.research_list_size)
    return ScreenResult(as_of=f["as_of"].iloc[0], frame=f, funnel=steps, params=p)


def score_all(snap: pd.DataFrame, p: ScreenParams) -> pd.DataFrame:
    """Composite for every non-financial with enough history, ignoring other hard filters.

    Used by the backtest to test the *score* across its whole range (quintiles),
    separately from the filters.
    """
    f = apply_filters(snap, p)
    ok = f["f_universe"] & f["f_liquidity"] & f["f_history"] & ~f["is_financial"]
    g = f[ok].copy()
    if g.empty:
        return g
    sc = percentile_scores(g, METRICS, p.min_group_size)
    comp = composite(sc, METRICS, p.pillar_weights)
    return pd.concat([g, sc, comp], axis=1)
