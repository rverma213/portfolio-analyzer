"""API smoke tests: every endpoint answers and returns the shapes the front end expects."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from smallcap import api, notes as notes_mod
from smallcap.data import demo
from smallcap.data.store import Dataset
from smallcap.engine import Engine


@pytest.fixture(scope="module")
def client(tmp_path_factory):
    t = demo.generate(n_companies=500, seed=5)
    api._engine = Engine(Dataset(**t, source="demo", built="test"))
    api.BACKTEST_CACHE = tmp_path_factory.mktemp("cache")
    notes_mod.NOTES_DIR = tmp_path_factory.mktemp("notes")
    return TestClient(api.app)


def test_meta(client):
    m = client.get("/api/meta").json()
    assert m["demo"] and len(m["filters"]) == 9 and m["defaults"]["screen"]["max_dilution"] == 0.05


def test_screen_and_company(client):
    s = client.post("/api/screen", json={"as_of": "2020-06-30"}).json()
    assert s["funnel"][-1]["remaining"] == len(s["passed"])
    assert all(r["failed"] for r in s["excluded"])
    cid = s["passed"][0]["company_id"]
    c = client.get(f"/api/company/{cid}", params={"as_of": "2020-06-30"}).json()
    assert c["screen"]["passed"] and c["history"] and c["prices"]
    assert all(h["filing_date"] <= "2020-06-30" for h in c["history"])


def test_notes_are_not_served_or_used(client):
    s = client.post("/api/screen", json={}).json()
    cid = s["passed"][0]["company_id"]
    assert client.get(f"/api/notes/{cid}").status_code in (404, 405)
    assert client.put(f"/api/notes/{cid}", json={"company_id": cid}).status_code in (404, 405)
    assert client.get("/api/research").status_code in (404, 405)
    assert "note" not in client.get(f"/api/company/{cid}").json()
    # A note on disk that would exclude the name must not change the API's portfolio.
    before = client.post("/api/portfolio", json={}).json()["holdings"]
    notes_mod.write(notes_mod.Note(company_id=cid, governance_flags=["turnover", "related_party"]))
    after = client.post("/api/portfolio", json={"use_notes": True}).json()["holdings"]
    assert after == before


def test_portfolio(client):
    pf = client.post("/api/portfolio", json={"as_of": "2019-12-31"}).json()
    n = len(pf["holdings"])
    holdings_check = next(c for c in pf["checks"] if c["rule"] == "Holdings")
    # A small test universe may not yield 40 names; the check must report that honestly.
    assert n > 0 and holdings_check["actual"] == n and holdings_check["pass"] == (40 <= n <= 80)


def test_backtest_is_cached(client):
    body = {"backtest": {"start": "2016-03-31", "end": "2018-12-31"}}
    a = client.post("/api/backtest", json=body).json()
    b = client.post("/api/backtest", json=body).json()
    assert a["key"] == b["key"] and a["stats"] == b["stats"]
    assert client.get("/api/pipeline").json()["stages"][-1]["count"] is not None


def test_engine_loads_once_under_concurrent_requests(monkeypatch):
    """Simultaneous first requests must share one dataset load (512 MB instances)."""
    import threading
    import time
    built = []

    class Slow:
        def __init__(self):
            time.sleep(0.2)
            built.append(self)

    saved = api._engine
    monkeypatch.setattr(api, "Engine", Slow)
    api._engine = None
    try:
        ts = [threading.Thread(target=api.engine) for _ in range(8)]
        [t.start() for t in ts]
        [t.join() for t in ts]
        assert len(built) == 1
    finally:
        api._engine = saved


def test_head_request_on_site_root(client):
    if not (api.ROOT / "frontend" / "dist").exists():
        return  # the site route exists only once the front end is built
    assert client.head("/").status_code == 200


def test_stock_list_and_profile(client):
    opts = client.get("/api/stocks").json()
    assert len(opts) == len(api.engine().ds.companies)
    mo = api.engine().ds.monthly
    cid = mo[mo["date"] <= "2020-06-30"]["company_id"].value_counts().index[0]  # longest history
    p = client.get(f"/api/stock/{cid}", params={"as_of": "2020-06-30"}).json()
    assert p["as_of"] == "2020-06-30" and p["company"]["company_id"] == cid
    assert p["series"][-1]["date"] == "2020-06-30" and p["series"][0]["index"] == 100
    assert all(f["filing_date"] <= "2020-06-30" for f in p["fundamentals"])
    assert {r["key"] for r in p["returns"]} >= {"1m", "ytd", "1y", "3y", "since"}
    assert any(r["corr_36"] is not None for r in p["series"]) and any(r["vol_12"] is not None for r in p["series"])
    assert client.get("/api/stock/NOT-A-COMPANY").status_code == 404


def test_stock_statistics_match_definitions():
    import numpy as np
    import pandas as pd
    from smallcap import stock as st
    dates = pd.date_range("2015-01-31", periods=61, freq="ME")
    rng = np.random.default_rng(1)
    b = pd.Series(rng.normal(0.01, 0.04, 61), index=dates)
    r = 1.5 * b + rng.normal(0, 0.02, 61)
    px = pd.DataFrame({"company_id": "X", "date": dates, "total_return": r.to_numpy(), "price": 1.0,
                       "mcap_usd": 1.0, "adv_usd": 1.0, "in_benchmark": True})
    m = st.monthly_series(px, b)
    rr, bb = r.iloc[1:], b.iloc[1:]
    assert m["index"].iloc[-1] == pytest.approx(100 * (1 + rr).prod())
    assert m["vol_36"].iloc[-1] == pytest.approx(rr.iloc[-36:].std() * np.sqrt(12))
    assert m["corr_12"].iloc[-1] == pytest.approx(rr.iloc[-12:].corr(bb.iloc[-12:]))
    assert m["corr_36"].iloc[:36].isna().all()  # a full window is needed
    one_y = next(x for x in st.horizon_returns(m) if x["key"] == "1y")
    assert one_y["stock"] == pytest.approx((1 + rr.iloc[-12:]).prod() - 1)
    risk = {x["key"]: x for x in st.risk_stats(m)}
    assert risk["5y"]["beta"] == pytest.approx(rr.cov(bb) / bb.var())
