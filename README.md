# Global Smaller Companies – Spec B implementation

Spec B (fundamental, bottom-up) from `Spec B – Fundamental.md`, built as a Python engine with a FastAPI service and a
React front end. The app shows every stage of the process:

| Page | What it shows |
| --- | --- |
| Overview | The pipeline with live counts at each stage, and the hard-filter funnel |
| 1 Universe | Benchmark and off-benchmark names; country, sector and region mix |
| 2 Screener | Adjustable hard filters, cost of equity and pillar weights; a clickable funnel showing who each filter removed; ranked, excluded and financials lists |
| 3 Research | The top-150 research list and a note editor: checklist, governance red flags, conviction, thesis, sell trigger |
| 4 Portfolio | Holdings, all limit checks, quality vs benchmark, active sector and country exposure, names skipped by limits |
| 5 Backtest | Point-in-time screen quintiles by region, portfolio vs benchmark, calendar years, turnover, rebalance log |

Click any company to open a drawer with its filter results, pillar and metric scores, 5-year charts and research note
(deep link: `#company=TICKER`).

## Quick start

```bash
# backend (Python 3.10+)
cd backend
pip install -e ".[dev]"
python -m smallcap.cli build-demo     # synthetic dataset -> data/smallcap.duckdb
python -m smallcap.cli serve          # API on http://127.0.0.1:8000

# front end, in a second terminal
cd frontend
npm install
npm run dev                           # http://localhost:5173 (proxies /api to :8000)
```

Or run `npm run build` once; `serve` then also serves the built app at http://127.0.0.1:8000.

Tests: `cd backend && python -m pytest` (32 tests: filters, point-in-time correctness, scoring, portfolio limits,
governance rules, notes, backtest, API).

## Layout

```
backend/smallcap/
  config.py      every Spec B parameter (filters, cost of equity, sizing, limits) in one place
  data/demo.py   deterministic synthetic universe (see "Data" below)
  data/ishares.py iShares WSML holdings: download, archive, parse
  data/store.py  DuckDB tables + dated Parquet snapshots under data/raw/
  metrics.py     the 11 pillar metrics, computed point in time
  screen.py      hard filters -> funnel -> sector/region percentile scores -> composite -> research list
  portfolio.py   conviction sizing, liquidity/sector/country/off-benchmark caps, sell rule, limit checks
  backtest.py    quarterly point-in-time backtest + screen quintiles by region
  notes.py       research notes: research/notes/<ticker>.md (JSON front matter + Markdown)
  api.py         FastAPI endpoints, one per stage
frontend/src/
  pages/         Overview, Universe, Screener, Research, Portfolio, Backtest
  components/    table, funnel, company drawer, controls
```

## Data

**The default dataset is synthetic.** `build-demo` generates 2,400 companies in 23 developed markets, 2008–2026. It has
annual statements with filing dates, listings, delistings (bankruptcy at −90%, takeovers at +30%), benchmark bands, and
a minority of serial share issuers and aggressive accounters, so that every screen has something to catch.
Returns contain a deliberately small link to fundamentals. **Backtest results on demo data show how the machinery works,
not whether the strategy works.**

### Real data

```bash
set SEC_USER_AGENT=Your Name your@email        # SEC requires contact details (PowerShell: $env:SEC_USER_AGENT="...")
python -m smallcap.cli import-holdings WSML_holdings.csv   # file downloaded from the iShares fund page
python -m smallcap.cli build-real               # add --limit 50 for a quick trial run
python -m smallcap.cli serve
```

| Data | Source | Notes |
| --- | --- | --- |
| Universe and weights | iShares WSML holdings CSV (you download it; the site blocks scripts) | Archived under `data/raw/ishares/<date>/`; archive one regularly to build membership history |
| Symbols | iShares ticker + exchange → Yahoo symbol | Unmapped names go to `data/unresolved_symbols.csv`; fix them in `data/symbol_overrides.csv` (`ticker,exchange,yahoo`) |
| Prices, volume, FX | Yahoo Finance (monthly, 2008→) | Total return from dividend-adjusted closes; market cap and ADV converted to USD |
| US fundamentals | SEC EDGAR company facts | Full history, **real filing dates**, first-reported values (point in time) |
| Non-US fundamentals | Yahoo Finance | About 4 annual periods; filing date estimated as period end + 90 days |

Everything is cached under `data/raw/`, so reruns are incremental. Coverage and limitations go to
`data/real_report.json` and are shown in the app's banner.

## Known limitations

Real data:

- Only today's constituents are known, so backtests have survivorship bias until holdings files are archived over time.
- Historical market caps assume today's share count.
- Non-US fundamentals (Yahoo) cover about 4 years, so those companies need 4 years of statements instead of 5
  (`min_years_estimated`, adjustable in the Screener). Today's screen is global, but in the backtest non-US
  names only qualify once 4 years have been filed (2026), so historical results are effectively US-only.
  A paid source (EODHD or FMP) would fix this.

Demo data:

- Annual statements stand in for TTM figures; quarterly data would make the yields more current.
- Turnover in the demo backtest (~65–70% a year) is above the spec's 25–40%. Most of it is genuine rank churn.
  A 0.5pp no-trade band for retained holdings is in place; real fundamentals are usually more persistent than the
  demo's.
- Benchmark floors (benchmark weight − band) are reported, not enforced. With financials excluded by default (an open
  question in the spec), the Financials floor is always flagged.
- The backtest does not use research notes, by design: it tests the screen, not the judgement.

## Deploying (Render)

The repo includes a `Dockerfile` that builds the front end and serves it with the API from one container.
The app reads only the committed `data/smallcap.duckdb` (plus `data/real_report.json` and saved backtests):
no data is downloaded while it runs, and the data builders' dependencies (yfinance) are not installed.
`tests/test_no_network.py` checks this.

1. On https://dashboard.render.com choose **New → Web Service**, connect this repository, language **Docker**.
2. Health check path: `/api/meta`. No environment variables are needed.
3. To refresh the data, run `build-real` locally, commit the new `data/smallcap.duckdb`, and push.

