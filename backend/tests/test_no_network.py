"""The public app serves prebuilt data only: no endpoint may open a network connection."""
from __future__ import annotations

import ast
import socket
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from smallcap import api
from smallcap.data import demo
from smallcap.data.store import Dataset
from smallcap.engine import Engine


FETCHERS = ("requests", "yfinance", "urllib", "httpx", "smallcap.data.real", "smallcap.data.ishares", ".data.real",
            ".data.ishares")
SERVED = ["api.py", "engine.py", "screen.py", "metrics.py", "portfolio.py", "backtest.py", "stock.py", "notes.py", "config.py",
          "data/store.py"]


def test_served_modules_do_not_import_data_fetchers():
    """Only the CLI builders download data; nothing the API loads may import them."""
    root = Path(api.__file__).parent
    for name in SERVED:
        tree = ast.parse((root / name).read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                mods = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom):
                mods = ["." * node.level + (node.module or "")]
                mods += [mods[0].rstrip(".") + "." + a.name for a in node.names]
            else:
                continue
            for m in mods:
                assert not m.startswith(FETCHERS) and not any(f in m for f in (".real", ".ishares")), f"{name}: {m}"


@pytest.fixture()
def offline_client(tmp_path, monkeypatch):
    # The event loop talks to itself over loopback (a socketpair on Windows); anything else is a fetch.
    real_connect = socket.socket.connect

    def guarded(self, address, *args):
        if isinstance(address, tuple) and address[0] not in ("127.0.0.1", "::1", "localhost"):
            raise AssertionError(f"network access attempted: {address}")
        return real_connect(self, address, *args)
    monkeypatch.setattr(socket.socket, "connect", guarded)
    t = demo.generate(n_companies=300, seed=11)
    monkeypatch.setattr(api, "_engine", Engine(Dataset(**t, source="demo", built="test")))
    monkeypatch.setattr(api, "BACKTEST_CACHE", tmp_path)
    return TestClient(api.app)


def test_every_endpoint_works_offline(offline_client):
    c = offline_client
    meta = c.get("/api/meta").json()
    as_of = meta["latest"]
    assert c.get("/api/pipeline").status_code == 200
    assert c.get("/api/universe", params={"as_of": as_of}).status_code == 200
    s = c.post("/api/screen", json={"as_of": as_of}).json()
    cid = (s["passed"] or s["excluded"])[0]["company_id"]
    assert c.get(f"/api/company/{cid}").status_code == 200
    assert c.get("/api/stocks").status_code == 200
    assert c.get(f"/api/stock/{cid}").status_code == 200
    assert c.post("/api/portfolio", json={"as_of": as_of}).status_code == 200
    body = {"backtest": {"start": "2018-03-31", "end": "2019-12-31"}}
    assert c.post("/api/backtest", json=body).status_code == 200
