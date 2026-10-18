"""Tests for the Spec B pipeline on a small in-memory demo dataset."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from smallcap import notes as notes_mod
from smallcap.backtest import run_backtest
from smallcap.config import BacktestParams, PortfolioParams, ScreenParams
from smallcap.data import demo
from smallcap.data.store import Dataset
from smallcap.engine import Engine
from smallcap.portfolio import build
from smallcap.screen import apply_filters, percentile_scores


@pytest.fixture(scope="session")
def eng() -> Engine:
    t = demo.generate(n_companies=700, seed=11)
    return Engine(Dataset(**t, source="demo", built="test"))


@pytest.fixture
def tmp_notes(tmp_path, monkeypatch):
    monkeypatch.setattr(notes_mod, "NOTES_DIR", tmp_path / "notes")
    return tmp_path / "notes"


# ----------------------------------------------------------------- data
def test_demo_is_deterministic():
    a = demo.generate(n_companies=50, seed=3)
    b = demo.generate(n_companies=50, seed=3)
    pd.testing.assert_frame_equal(a["statements"], b["statements"])
    pd.testing.assert_frame_equal(a["monthly"], b["monthly"])


def test_delisted_companies_keep_final_return(eng):
    gone = eng.ds.companies.dropna(subset=["delisted_date"])
    assert len(gone) > 0
    last = eng.ds.monthly.sort_values("date").groupby("company_id").tail(1).set_index("company_id")
    for cid, row in gone.set_index("company_id").head(20).iterrows():
        assert last.loc[cid, "date"] == row["delisted_date"]
        assert last.loc[cid, "total_return"] == pytest.approx(row["delist_return"])


# ----------------------------------------------------------- point in time
@pytest.mark.parametrize("as_of", ["2013-03-31", "2017-06-30", "2021-09-30"])
def test_snapshot_uses_only_filed_statements(eng, as_of):
    snap = eng.snapshot(as_of)
    month = snap["as_of"].iloc[0]
    assert (snap["filing_date"].dropna() <= month).all()
    # and it is the latest filed one
    filed = eng.stmt[eng.stmt["filing_date"] <= month].groupby("company_id")["filing_date"].max()
    s = snap.dropna(subset=["filing_date"]).set_index("company_id")["filing_date"]
    assert (s == filed.reindex(s.index)).all()


def test_snapshot_only_contains_listed_companies(eng):
    snap = eng.snapshot("2016-12-31")
    month = snap["as_of"].iloc[0]
    comp = eng.ds.companies.set_index("company_id").loc[snap["company_id"]]
    assert (comp["listed_date"] <= month).all()
    assert ((comp["delisted_date"].isna()) | (comp["delisted_date"] >= month)).all()


# ------------------------------------------------------------------ filters
def _frame(**overrides):
    base = dict(company_id="X", sector="Industrials", region="Europe", country="Germany", in_benchmark=True,
                mcap_usd=1e9, adv_usd=5e6, n_years=5, positive_fcf_years=5, equity=1e8, roe=0.15,
                leverage=1.0, roe_median=0.15, dilution=0.01, receivables_gap=0.0)
    base.update(overrides)
    return pd.DataFrame([base])


@pytest.mark.parametrize("override,failed", [
    ({"roe_median": 0.08}, "roe_vs_coe"),           # below 9% European cost of equity
    ({"dilution": 0.08}, "dilution"),               # issuing 8% a year
    ({"receivables_gap": 0.20}, "receivables"),     # receivables outrunning sales by 20pp
    ({"leverage": 3.5}, "leverage"),
    ({"positive_fcf_years": 2}, "fcf_record"),
    ({"adv_usd": 5e5}, "liquidity"),
    ({"n_years": 4}, "history"),
])
def test_each_hard_filter(override, failed):
    f = apply_filters(_frame(**override), ScreenParams())
    assert not f["passed"].iloc[0]
    assert failed in f["failed"].iloc[0]


def test_clean_company_passes():
    assert apply_filters(_frame(), ScreenParams())["passed"].iloc[0]


def test_japan_uses_lower_cost_of_equity():
    f = apply_filters(_frame(region="Japan", country="Japan", roe_median=0.08), ScreenParams())
    assert f["passed"].iloc[0]


def test_roe_filter_can_be_switched_off():
    p = ScreenParams(require_roe_above_coe=False)
    assert apply_filters(_frame(roe_median=0.02), p)["passed"].iloc[0]


def test_financials_exempt_from_fcf_and_leverage():
    f = apply_filters(_frame(sector="Financials", positive_fcf_years=0, leverage=12, receivables_gap=0.5),
                      ScreenParams())
    assert f["passed"].iloc[0]


def test_funnel_is_monotonic_and_reconciles(eng):
    res = eng.screen("2019-12-31")
    rem = [s["remaining"] for s in res.funnel]
    assert all(a >= b for a, b in zip(rem, rem[1:]))
    for a, b in zip(res.funnel, res.funnel[1:]):
        assert a["remaining"] - b["removed"] == b["remaining"]
    assert rem[-1] == len(res.passed)


# ------------------------------------------------------------------ scores
def test_scores_bounded_and_directional():
    n = 40
    f = pd.DataFrame({"company_id": range(n), "sector": "Industrials", "region": "Europe",
                      "earnings_yield": np.linspace(0.01, 0.2, n), "leverage": np.linspace(0, 2.5, n)})
    metrics = {"earnings_yield": ("Earnings", True), "leverage": ("Balance sheet", False)}
    s = percentile_scores(f, metrics, min_group=10)
    assert s.filter(like="s_").min().min() >= 0 and s.filter(like="s_").max().max() <= 100
    assert s["s_earnings_yield"].iloc[-1] == 100 and s["s_earnings_yield"].iloc[0] == 0
    assert s["s_leverage"].iloc[0] == 100 and s["s_leverage"].iloc[-1] == 0


def test_small_groups_fall_back_to_region():
    f = pd.DataFrame({"company_id": range(12), "region": "Japan",
                      "sector": ["Energy"] * 2 + ["Industrials"] * 10, "earnings_yield": np.arange(12.0)})
    s = percentile_scores(f, {"earnings_yield": ("Earnings", True)}, min_group=10)
    assert set(s.loc[:1, "score_group"]) == {"region"}
    assert set(s.loc[2:, "score_group"]) == {"sector_region"}


def test_research_list_is_top_ranked(eng):
    res = eng.screen("2020-06-30", ScreenParams(research_list_size=50))
    rl = res.research_list
    assert len(rl) == min(50, len(res.passed))
    assert rl["composite"].min() >= res.passed["composite"].iloc[len(rl):].max()


# ---------------------------------------------------------------- portfolio
def test_portfolio_respects_hard_limits(eng):
    p = PortfolioParams()
    res = eng.screen("2020-06-30")
    pf = build(res, p)
    h = pf.holdings
    assert h["weight"].max() <= p.max_position + 1e-9
    assert 1 - h["weight"].sum() <= p.max_cash + 1e-9
    assert (h["days_to_trade"] <= p.adv_days + 1e-6).all()
    assert h["company_id"].isin(res.passed["company_id"]).all()
    off = h.loc[~h["in_benchmark"].astype(bool), "weight"].sum()
    assert off <= p.off_benchmark_max + 1e-9
    for e in pf.exposures["sector"] + pf.exposures["country"]:
        assert e["portfolio"] <= e["max"] + 1e-9


def test_governance_flags_block_and_conviction_from_note(eng, tmp_notes):
    res = eng.screen("2020-06-30")
    top = res.passed["company_id"].tolist()
    notes = {
        top[0]: notes_mod.Note(company_id=top[0], governance_flags=["related_party", "turnover"]),
        top[1]: notes_mod.Note(company_id=top[1], governance_flags=["related_party"]),  # unjustified
        top[2]: notes_mod.Note(company_id=top[2], governance_flags=["related_party"],
                               governance_justification="Founder leases HQ at audited market rent."),
        top[3]: notes_mod.Note(company_id=top[3], conviction="low"),
    }
    pf = build(res, PortfolioParams(), notes=notes)
    held = set(pf.holdings["company_id"])
    assert top[0] not in held and top[1] not in held
    assert top[2] in held
    row = pf.holdings.set_index("company_id").loc[top[3]]
    assert row["conviction"] == "low" and row["conviction_source"] == "note"


def test_sell_rule_keeps_holdings_in_top_40pct(eng):
    p = PortfolioParams()
    res = eng.screen("2020-06-30")
    prev = res.passed.set_index("company_id")["rank_pct"]
    prev = prev[(prev > 0.2) & (prev <= 0.4)].head(5)
    prev[:] = 0.02
    pf = build(res, p, prev=prev)
    assert set(prev.index) <= set(pf.holdings["company_id"])


# -------------------------------------------------------------------- notes
def test_note_round_trip(tmp_notes):
    n = notes_mod.Note(company_id="ABC US", conviction="high", thesis="Compounds at 20% ROE.",
                       governance_flags=["turnover"], governance_justification="CFO retired.",
                       body="## Notes\nGood business.")
    notes_mod.write(n)
    back = notes_mod.read("ABC US")
    assert back.conviction == "high" and back.thesis == n.thesis and back.body == n.body
    assert not back.governance_blocked
    assert "ABC US" in notes_mod.read_all()


# ----------------------------------------------------------------- backtest
def test_backtest_runs_and_reconciles(eng):
    bp = BacktestParams(start="2016-03-31", end="2019-12-31", cost_bps=0)
    out = run_backtest(eng, bp=bp)
    s = out["stats"]
    assert s["months"] == len(out["series"]) > 30
    last = out["series"][-1]
    assert last["relative"] == pytest.approx(last["portfolio"] / last["benchmark"])
    assert {q["quintile"] for q in out["quintiles"]} == {1, 2, 3, 4, 5}
    assert 0 <= s["hit_rate"] <= 1


def test_costs_reduce_returns(eng):
    a = run_backtest(eng, bp=BacktestParams(start="2016-03-31", end="2018-12-31", cost_bps=0))
    b = run_backtest(eng, bp=BacktestParams(start="2016-03-31", end="2018-12-31", cost_bps=100))
    assert b["stats"]["cagr"] < a["stats"]["cagr"]
