"""Command line: build data, run a backtest, start the API.

    python -m smallcap.cli build-demo [--companies 2000] [--seed 7]
    python -m smallcap.cli import-holdings FILE   # archive a downloaded iShares WSML holdings CSV
    python -m smallcap.cli build-real [--limit N] [--no-sec]
    python -m smallcap.cli ishares            # try to download the holdings file directly
    python -m smallcap.cli backtest
    python -m smallcap.cli serve [--port 8000]
"""
from __future__ import annotations

import argparse
import json
import time


def main() -> None:
    ap = argparse.ArgumentParser(prog="smallcap")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build-demo", help="generate the synthetic demo dataset")
    b.add_argument("--companies", type=int, default=2400)
    b.add_argument("--seed", type=int, default=7)
    sub.add_parser("ishares", help="try to download and archive the iShares WSML holdings file")
    ih = sub.add_parser("import-holdings", help="archive a downloaded iShares WSML holdings CSV")
    ih.add_argument("file")
    br = sub.add_parser("build-real", help="build the database from holdings + Yahoo + SEC EDGAR")
    br.add_argument("--holdings", help="holdings CSV (default: latest archived)")
    br.add_argument("--limit", type=int, help="only the N largest holdings (for a quick test)")
    br.add_argument("--no-sec", action="store_true", help="skip SEC EDGAR (Yahoo fundamentals only)")
    sub.add_parser("backtest", help="run the default backtest and print the summary")
    s = sub.add_parser("serve", help="start the API")
    s.add_argument("--port", type=int, default=8000)
    a = ap.parse_args()

    if a.cmd == "build-demo":
        from .data import demo, store
        t = time.time()
        tables = demo.generate(a.companies, a.seed)
        store.save(tables, source="demo")
        print(f"demo dataset: {len(tables['companies'])} companies, "
              f"{len(tables['statements'])} statements, {len(tables['monthly'])} monthly rows "
              f"in {time.time() - t:.1f}s")
    elif a.cmd == "ishares":
        from .data import ishares
        path = ishares.archive()
        print(f"saved {path}")
    elif a.cmd == "import-holdings":
        from .data import ishares
        path = ishares.import_file(a.file)
        h = ishares.parse(path)
        print(f"archived {path}: {len(h)} equities, holdings date {ishares.holdings_date(path)}")
        print(h.groupby("country").size().sort_values(ascending=False).head(10).to_string())
    elif a.cmd == "build-real":
        import logging
        from .data.real.build import build
        logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
        t = time.time()
        report = build(a.holdings, limit=a.limit, use_sec=not a.no_sec)
        print(json.dumps(report, indent=2, default=str))
        print(f"{time.time() - t:.0f}s")
    elif a.cmd == "backtest":
        from .backtest import run_backtest
        from .engine import Engine
        t = time.time()
        out = run_backtest(Engine())
        print(json.dumps(out["stats"], indent=2))
        print(json.dumps(out["quintile_spread"], indent=2))
        print(f"{time.time() - t:.1f}s")
    elif a.cmd == "serve":
        import uvicorn
        uvicorn.run("smallcap.api:app", host="127.0.0.1", port=a.port)


if __name__ == "__main__":
    main()
