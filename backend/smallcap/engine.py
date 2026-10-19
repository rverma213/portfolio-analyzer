"""Holds the dataset and precomputed tables; every stage runs through here."""
from __future__ import annotations

from functools import lru_cache

import pandas as pd

from . import metrics, notes, portfolio, screen
from .config import PortfolioParams, ScreenParams
from .data.store import Dataset, load


class Engine:
    def __init__(self, ds: Dataset | None = None):
        self.ds = ds or load()
        self.stmt = metrics.statement_metrics(self.ds.statements)
        self.months = self.ds.months
        self.returns = self.ds.monthly.pivot(index="date", columns="company_id", values="total_return")
        self.mcap = self.ds.monthly.pivot(index="date", columns="company_id", values="mcap_usd")
        self.bench = self.ds.monthly.pivot(index="date", columns="company_id", values="in_benchmark")
        self._snap = lru_cache(maxsize=256)(self._snapshot)
        self._bench_returns: pd.Series | None = None

    # -------------------------------------------------------------- dates
    def month_end(self, as_of: str | pd.Timestamp | None) -> pd.Timestamp:
        if as_of is None:
            return self.months[-1]
        ts = pd.Timestamp(as_of)
        eligible = self.months[self.months <= ts]
        return eligible[-1] if len(eligible) else self.months[0]

    # -------------------------------------------------------------- stages
    def _snapshot(self, month: pd.Timestamp) -> pd.DataFrame:
        return metrics.snapshot(month, self.stmt, self.ds.monthly, self.ds.companies)

    def snapshot(self, as_of=None) -> pd.DataFrame:
        return self._snap(self.month_end(as_of))

    def screen(self, as_of=None, params: ScreenParams | None = None) -> screen.ScreenResult:
        return screen.run(self.snapshot(as_of), params or ScreenParams())

    def portfolio(self, as_of=None, sp: ScreenParams | None = None, pp: PortfolioParams | None = None,
                  prev: pd.Series | None = None, use_notes: bool = True) -> portfolio.Portfolio:
        res = self.screen(as_of, sp)
        return portfolio.build(res, pp or PortfolioParams(), prev, notes.read_all() if use_notes else {})

    def benchmark_returns(self) -> pd.Series:
        """Cap-weighted monthly return of benchmark members as of the prior month end."""
        if self._bench_returns is None:
            self._bench_returns = self._benchmark_returns()
        return self._bench_returns

    def _benchmark_returns(self) -> pd.Series:
        w = (self.mcap.where(self.bench.astype("boolean").fillna(False).astype(bool))).shift(1)
        r = self.returns.reindex_like(w)
        num = (w * r.fillna(0)).sum(axis=1)
        den = w.where(r.notna()).sum(axis=1)
        return (num / den).iloc[1:]
