"""Spec B validation (§7).

Two tests, both point in time:

1. Screen test — rank every name with enough history on the composite score
   (ignoring the other hard filters), split into quintiles within each region,
   and track equal-weighted returns to the next rebalance. Q1 – Q5 shows
   whether the score itself separates winners from losers. A second split
   compares names that pass all hard filters with those that fail.
2. Portfolio test — run the full process each quarter (filters, scores,
   construction limits, sell rule), let weights drift monthly, charge costs on
   turnover, and compare with the cap-weighted benchmark.

Delisted companies keep their final return (bankruptcy or takeover); after
delisting, the position is cash until the next rebalance. The research-note
overlay (conviction, governance) is NOT used here: the backtest tests the
screen, not the judgement, as the spec requires.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .config import BacktestParams, PortfolioParams, ScreenParams
from .engine import Engine
from .portfolio import build
from .screen import run, score_all


def rebalance_dates(eng: Engine, bp: BacktestParams) -> list[pd.Timestamp]:
    start = eng.month_end(bp.start)
    end = eng.month_end(bp.end) if bp.end else eng.months[-1]
    months = eng.months[(eng.months >= start) & (eng.months <= end)]
    return list(months[::bp.rebalance_months])


def run_backtest(eng: Engine, sp: ScreenParams | None = None, pp: PortfolioParams | None = None,
                 bp: BacktestParams | None = None) -> dict:
    sp, pp, bp = sp or ScreenParams(), pp or PortfolioParams(), bp or BacktestParams()
    dates = rebalance_dates(eng, bp)
    end = eng.month_end(bp.end) if bp.end else eng.months[-1]
    rets = eng.returns
    bench_r = eng.benchmark_returns()

    port_monthly, quint_rows, rebal_log, holdings_log = [], [], [], []
    w_prev = pd.Series(dtype=float)  # drifted weights just before rebalance
    for k, d in enumerate(dates):
        nxt = dates[k + 1] if k + 1 < len(dates) else end
        period = rets.index[(rets.index > d) & (rets.index <= nxt)]
        if len(period) == 0:
            break

        res = run(eng.snapshot(d), sp)
        pf = build(res, pp, prev=w_prev if len(w_prev) else None, notes={})
        w = pf.weights
        trades = w.subtract(w_prev, fill_value=0).abs()
        turnover = trades.sum() / 2
        cost = trades.sum() * bp.cost_bps / 1e4

        # ---- monthly drift with delistings -> cash
        cur = w.copy()
        cash = 1 - cur.sum()
        for i, m in enumerate(period):
            r = rets.loc[m, cur.index]
            gone = r.isna() & (cur > 0)
            cash += cur[gone].sum()
            cur[gone] = 0
            port_r = float((cur * r.fillna(0)).sum())
            if i == 0:
                port_r -= cost
            total = cur.sum() + cash
            cur = cur * (1 + r.fillna(0))
            denom = cur.sum() + cash
            port_monthly.append({"date": m, "portfolio": port_r / max(total, 1e-12)})
            cur, cash = cur / denom, cash / denom
        w_prev = cur[cur > 0]

        # ---- screen quintiles
        scored = score_all(eng.snapshot(d), sp)
        fwd = _forward_returns(rets, period)
        if len(scored):
            scored = scored.assign(fwd=scored["company_id"].map(fwd))
            for region, g in scored.groupby("region"):
                if len(g) < bp.quintile_min_names:
                    continue
                q = pd.qcut(g["composite"].rank(method="first"), 5, labels=[5, 4, 3, 2, 1]).astype(int)
                for qi, gg in g.groupby(q):
                    quint_rows.append({"date": d, "region": region, "quintile": qi,
                                       "ret": gg["fwd"].mean(), "n": len(gg)})
        allf = res.frame.assign(fwd=res.frame["company_id"].map(fwd))
        universe = allf[allf["f_universe"] & allf["f_liquidity"] & ~allf["is_financial"]]
        rebal_log.append({
            "date": d.date().isoformat(), "holdings": len(w), "turnover": turnover, "cost": cost,
            "passed": int(res.passed.shape[0]), "universe": int(universe.shape[0]),
            "pass_ret": float(universe.loc[universe["passed"], "fwd"].mean()),
            "fail_ret": float(universe.loc[~universe["passed"], "fwd"].mean()),
        })
        holdings_log.append({"date": d.date().isoformat(),
                             "weights": {c: round(float(x), 5) for c, x in w.items()}})

    pm = pd.DataFrame(port_monthly).set_index("date")["portfolio"]
    bm = bench_r.reindex(pm.index).fillna(0)
    return _summarise(pm, bm, pd.DataFrame(quint_rows), rebal_log, holdings_log, bp)


def _forward_returns(rets: pd.DataFrame, period: pd.DatetimeIndex) -> pd.Series:
    """Compounded return over the period; a delisted name earns its final return then cash."""
    block = rets.loc[period]
    return (1 + block.fillna(0)).prod() - 1


def _stats(pm: pd.Series, bm: pd.Series) -> dict:
    years = len(pm) / 12
    ex = pm - bm
    cum_p, cum_b = (1 + pm).cumprod(), (1 + bm).cumprod()
    rel = cum_p / cum_b
    te = ex.std(ddof=1) * np.sqrt(12)
    cagr_p = cum_p.iloc[-1] ** (1 / years) - 1
    cagr_b = cum_b.iloc[-1] ** (1 / years) - 1
    return {
        "months": int(len(pm)),
        "cagr": cagr_p, "bench_cagr": cagr_b, "excess": cagr_p - cagr_b,
        "vol": pm.std(ddof=1) * np.sqrt(12), "bench_vol": bm.std(ddof=1) * np.sqrt(12),
        "tracking_error": te, "information_ratio": (ex.mean() * 12 / te) if te > 0 else None,
        "hit_rate": float((ex > 0).mean()),
        "max_drawdown": float((cum_p / cum_p.cummax() - 1).min()),
        "max_relative_drawdown": float((rel / rel.cummax() - 1).min()),
        "beta": float(np.cov(pm, bm)[0, 1] / np.var(bm, ddof=1)),
    }


def _summarise(pm, bm, quint, rebal_log, holdings_log, bp) -> dict:
    stats = _stats(pm, bm)
    rl = pd.DataFrame(rebal_log)
    years = len(pm) / 12
    stats["turnover_annual"] = float(rl["turnover"].sum() / years) if len(rl) else 0.0
    stats["avg_holdings"] = float(rl["holdings"].mean()) if len(rl) else 0.0
    stats["cost_drag_annual"] = float(rl["cost"].sum() / years) if len(rl) else 0.0

    cum = pd.DataFrame({"portfolio": (1 + pm).cumprod(), "benchmark": (1 + bm).cumprod()})
    cum["relative"] = cum["portfolio"] / cum["benchmark"]
    excess = pm - bm
    calendar = pd.DataFrame({"portfolio": (1 + pm).groupby(pm.index.year).prod() - 1,
                             "benchmark": (1 + bm).groupby(bm.index.year).prod() - 1})
    calendar["excess"] = calendar["portfolio"] - calendar["benchmark"]

    periods_per_year = 12 / bp.rebalance_months
    quintiles, spread = [], []
    if len(quint):
        q = quint.groupby(["region", "quintile"]).agg(ret=("ret", "mean"), n=("n", "mean")).reset_index()
        q["annualised"] = (1 + q["ret"]) ** periods_per_year - 1
        allq = quint.groupby("quintile").agg(ret=("ret", "mean"), n=("n", "sum")).reset_index()
        allq["region"] = "All"
        allq["annualised"] = (1 + allq["ret"]) ** periods_per_year - 1
        quintiles = pd.concat([allq, q])[["region", "quintile", "annualised", "n"]].to_dict("records")
        piv = quint.pivot_table(index=["date", "region"], columns="quintile", values="ret").reset_index()
        piv["spread"] = piv[1] - piv[5]
        sp = piv.groupby("region")["spread"].agg(["mean", "count", lambda s: (s > 0).mean()]).reset_index()
        sp.columns = ["region", "mean", "periods", "hit_rate"]
        sp["annualised"] = (1 + sp["mean"]) ** periods_per_year - 1
        spread = sp.to_dict("records")

    return _clean({
        "stats": stats,
        "series": [{"date": d.date().isoformat(), **{k: float(v) for k, v in r.items()}, "excess": float(excess.loc[d])}
                   for d, r in cum.iterrows()],
        "calendar": [{"year": int(y), **{k: float(v) for k, v in r.items()}} for y, r in calendar.iterrows()],
        "quintiles": quintiles,
        "quintile_spread": spread,
        "rebalances": rebal_log,
        "holdings": holdings_log,
    })


def _clean(o):
    if isinstance(o, dict):
        return {k: _clean(v) for k, v in o.items()}
    if isinstance(o, list):
        return [_clean(v) for v in o]
    if isinstance(o, (np.floating, float)):
        return None if not np.isfinite(o) else float(o)
    if isinstance(o, np.integer):
        return int(o)
    return o
