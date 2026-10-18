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
