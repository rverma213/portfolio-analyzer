"""FastAPI service: one endpoint per stage of the portfolio process.

    GET  /api/meta                 dataset info, defaults, labels
    GET  /api/pipeline             counts at every stage for the overview
    GET  /api/universe             constituents and country/sector mix
    POST /api/screen               hard-filter funnel, ranked list, exclusions
    GET  /api/company/{id}         5-year history, scores, prices
    POST /api/portfolio            holdings, limit checks, exposures
    POST /api/backtest             screen quintiles and portfolio backtest

Research notes are not served: the public app is read-only apart from the backtest
cache, and portfolios are built from the rules alone.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

import numpy as np
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .backtest import run_backtest
from .config import (DATA_DIR, METRIC_LABELS, METRICS, PILLARS, ROOT, BacktestParams,
                     PortfolioParams, ScreenParams)
from .data.store import describe
from .engine import Engine
from .portfolio import benchmark
from .screen import FILTERS

app = FastAPI(title="Portfolio Analyzer – Global Smaller Companies")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                   allow_methods=["*"], allow_headers=["*"])

_engine: Engine | None = None
BACKTEST_CACHE = DATA_DIR / "cache" / "backtests"


def engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = Engine()
    return _engine


# ------------------------------------------------------------------ helpers
def records(df: pd.DataFrame, cols: list[str] | None = None) -> list[dict]:
    if cols is not None:
        df = df[list(dict.fromkeys(c for c in cols if c in df.columns))]
    return [{k: clean(v) for k, v in row.items()} for row in df.to_dict("records")]


def clean(v):
    if isinstance(v, (pd.Timestamp,)):
        return None if pd.isna(v) else v.date().isoformat()
    if isinstance(v, (np.bool_, bool)):
        return bool(v)
    if isinstance(v, (np.integer,)):
        return int(v)
    if isinstance(v, (np.floating, float)):
        return None if not math.isfinite(v) else float(v)
    if isinstance(v, (list, tuple, np.ndarray)):
        return [clean(x) for x in v]
    if v is pd.NaT or (not isinstance(v, (str, dict)) and pd.isna(v)):
        return None
    return v


BASE_COLS = ["company_id", "ticker", "name", "country", "region", "sector", "mcap_usd", "adv_usd",
             "in_benchmark"]
METRIC_COLS = list(METRICS) + ["roe_median", "roe", "book_to_price", "sales_growth", "positive_fcf_years",
                               "n_years", "filing_estimated", "cost_of_equity"]
SCORE_COLS = [f"s_{m}" for m in METRICS] + [f"p_{p}" for p in PILLARS] + ["composite", "rank", "rank_pct"]


class ScreenRequest(BaseModel):
    as_of: str | None = None
    screen: ScreenParams = ScreenParams()


class PortfolioRequest(ScreenRequest):
    portfolio: PortfolioParams = PortfolioParams()


class BacktestRequest(BaseModel):
    screen: ScreenParams = ScreenParams()
    portfolio: PortfolioParams = PortfolioParams()
    backtest: BacktestParams = BacktestParams()
    refresh: bool = False


# ------------------------------------------------------------------ endpoints
@app.get("/api/meta")
def meta():
    e = engine()
    quarter_ends = [d.date().isoformat() for d in e.months if d.month in (3, 6, 9, 12)]
    return {
        "dataset": describe(e.ds),
        "demo": e.ds.source == "demo",
        "data_report": _data_report(e.ds.source),
        "as_of_dates": quarter_ends + ([e.months[-1].date().isoformat()]
                                       if e.months[-1].month not in (3, 6, 9, 12) else []),
        "latest": e.months[-1].date().isoformat(),
        "defaults": {"screen": ScreenParams().model_dump(), "portfolio": PortfolioParams().model_dump(),
                     "backtest": BacktestParams().model_dump()},
        "metrics": [{"key": k, "label": METRIC_LABELS[k], "pillar": p, "higher_is_better": h}
                    for k, (p, h) in METRICS.items()],
        "pillars": PILLARS,
        "filters": [{"key": k, "label": lbl, "applies_to_financials": fin} for k, lbl, fin in FILTERS],
    }


@app.get("/api/pipeline")
def pipeline(as_of: str | None = None):
    e = engine()
    res = e.screen(as_of)
    pf = e.portfolio(as_of, use_notes=False)
    cached = _latest_cached_backtest()
    return {
        "as_of": res.as_of.date().isoformat(),
        "stages": [
            {"key": "universe", "label": "Universe", "count": int(res.frame["f_universe"].sum()),
             "detail": f"{int(res.frame['in_benchmark'].sum())} benchmark members"},
            {"key": "screener", "label": "Hard filters", "count": int(res.passed.shape[0]),
             "detail": f"{int(res.financials.shape[0])} financials on a separate list"},
            {"key": "portfolio", "label": "Portfolio", "count": int(len(pf.holdings)),
             "detail": f"{sum(c['pass'] for c in pf.checks if not c.get('advisory'))}/"
                       f"{sum(1 for c in pf.checks if not c.get('advisory'))} limits met"},
            {"key": "backtest", "label": "Backtest",
             "count": None if cached is None else cached["stats"].get("information_ratio"),
             "detail": "not run yet" if cached is None else
             f"{cached['stats']['excess']:+.1%} a year vs benchmark"},
        ],
        "funnel": res.funnel,
    }


@app.get("/api/universe")
def universe(as_of: str | None = None):
    e = engine()
    snap = e.snapshot(as_of)
    b = benchmark(snap)
    snap = snap.merge(b[["company_id", "bench_weight"]], on="company_id", how="left")
    snap["bench_weight"] = snap["bench_weight"].fillna(0)

    def mix(col):
        g = snap.groupby(col).agg(count=("company_id", "size"), bench_count=("in_benchmark", "sum"),
                                  bench_weight=("bench_weight", "sum"), mcap=("mcap_usd", "sum"))
        return records(g.sort_values("bench_weight", ascending=False).reset_index())

    return {
        "as_of": snap["as_of"].iloc[0].date().isoformat(),
        "summary": {
            "companies": int(len(snap)), "benchmark": int(snap["in_benchmark"].sum()),
            "median_mcap": float(snap["mcap_usd"].median()), "total_mcap": float(snap["mcap_usd"].sum()),
        },
        "by_country": mix("country"), "by_sector": mix("sector"), "by_region": mix("region"),
        "rows": records(snap.sort_values("mcap_usd", ascending=False),
                        BASE_COLS + ["bench_weight", "n_years"]),
    }


@app.post("/api/screen")
def screen(req: ScreenRequest):
    e = engine()
    res = e.screen(req.as_of, req.screen)
    f = res.frame
    passed = res.passed
    excluded = f[~f["passed"]]
    fin = res.financials
    return {
        "as_of": res.as_of.date().isoformat(),
        "funnel": res.funnel,
        "passed": records(passed, BASE_COLS + METRIC_COLS + SCORE_COLS + ["research_list",
                                                                          "missing_metrics", "score_group"]),
        "excluded": records(excluded, BASE_COLS + METRIC_COLS + ["failed", "first_failed"]),
        "financials": records(fin, BASE_COLS + ["roe_median", "roe_spread", "roe_stability", "earnings_yield",
                                                "book_to_price", "fin_composite", "fin_rank"]),
    }


@app.get("/api/company/{company_id}")
def company(company_id: str, as_of: str | None = None):
    e = engine()
    comp = e.ds.companies[e.ds.companies["company_id"] == company_id]
    if comp.empty:
        raise HTTPException(404, f"unknown company {company_id}")
    res = e.screen(as_of)
    row = res.frame[res.frame["company_id"] == company_id]
    hist = e.stmt[e.stmt["company_id"] == company_id].sort_values("fiscal_year")
    stm = e.ds.statements[e.ds.statements["company_id"] == company_id].sort_values("fiscal_year")
    hist = hist.merge(stm[["fiscal_year", "ebit", "cfo", "capex", "total_assets", "receivables",
                           "shares_diluted", "dividends"]], on="fiscal_year", how="left")
    hist = hist[hist["filing_date"] <= res.as_of]
    px = e.ds.monthly[(e.ds.monthly["company_id"] == company_id) & (e.ds.monthly["date"] <= res.as_of)]
    bench = e.benchmark_returns()
    px = px.assign(index=(1 + px["total_return"].fillna(0)).cumprod())
    bidx = (1 + bench.reindex(px["date"]).fillna(0)).cumprod()
    px["bench_index"] = bidx.to_numpy()
    return {
        "as_of": res.as_of.date().isoformat(),
        "company": records(comp)[0],
        "screen": records(row, BASE_COLS + METRIC_COLS + SCORE_COLS + ["passed", "failed", "research_list",
                                                                       "earnings_yield", "fcf_yield"])[0]
        if len(row) else None,
        "history": records(hist),
        "prices": records(px, ["date", "price", "mcap_usd", "index", "bench_index", "in_benchmark"]),
    }


@app.post("/api/portfolio")
def portfolio(req: PortfolioRequest):
    e = engine()
    pf = e.portfolio(req.as_of, req.screen, req.portfolio, use_notes=False)
    names = e.ds.companies.set_index("company_id")[["ticker", "name"]]
    skipped = [{**s, **names.loc[s["company_id"]].to_dict()} for s in pf.skipped]
    return {
        "as_of": pf.as_of.date().isoformat(),
        "holdings": records(pf.holdings, BASE_COLS + ["weight", "target_weight", "conviction",
                                                      "conviction_source", "rank", "composite",
                                                      "days_to_trade", "roe_median", "fcf_conversion",
                                                      "leverage", "earnings_yield", "fcf_yield"]
                            + [f"p_{p}" for p in PILLARS]),
        "checks": [{k: clean(v) for k, v in c.items()} for c in pf.checks],
        "exposures": {k: [{kk: clean(vv) for kk, vv in r.items()} for r in v] for k, v in pf.exposures.items()},
        "characteristics": [{k: clean(v) for k, v in c.items()} for c in pf.characteristics],
        "skipped": skipped,
        "cash": clean(1 - pf.holdings["weight"].sum()) if len(pf.holdings) else 1.0,
    }


@app.post("/api/backtest")
def backtest(req: BacktestRequest):
    key = hashlib.sha1(json.dumps(
        {"s": req.screen.model_dump(), "p": req.portfolio.model_dump(), "b": req.backtest.model_dump(),
         "data": describe(engine().ds)}, sort_keys=True).encode()).hexdigest()[:16]
    path = BACKTEST_CACHE / f"{key}.json"
    if path.exists() and not req.refresh:
        return json.loads(path.read_text())
    out = run_backtest(engine(), req.screen, req.portfolio, req.backtest)
    out["key"] = key
    out["params"] = {"screen": req.screen.model_dump(), "portfolio": req.portfolio.model_dump(),
                     "backtest": req.backtest.model_dump()}
    BACKTEST_CACHE.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out))
    return out


def _data_report(source: str) -> dict | None:
    """Coverage and limitations written by build-real (data/real_report.json)."""
    p = DATA_DIR / "real_report.json"
    if source != "real" or not p.exists():
        return None
    return json.loads(p.read_text())


def _latest_cached_backtest() -> dict | None:
    if not BACKTEST_CACHE.exists():
        return None
    files = sorted(BACKTEST_CACHE.glob("*.json"), key=lambda p: p.stat().st_mtime)
    return json.loads(files[-1].read_text()) if files else None


# Serve the built front end (npm run build) from the same origin, with a
# fallback to index.html so client-side routes survive a page refresh.
_dist = ROOT / "frontend" / "dist"
if _dist.exists():
    from fastapi.responses import FileResponse

    app.mount("/assets", StaticFiles(directory=Path(_dist / "assets")), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path.startswith("api/"):
            raise HTTPException(404)
        f = _dist / path
        return FileResponse(f if path and f.is_file() else _dist / "index.html")
