# Spec B – Fundamental, bottom-up

Spec B targets 3.0% a year above MSCI World Small Cap over a five-year cycle by owning 40–80 companies that turn earnings into cash, earn a high and stable ROE, and trade at a reasonable free cash flow yield.

## 1. Objective

| Item | Target |
| --- | --- |
| Excess return | +3.0% p.a. net of costs over rolling 5 years |
| Tracking error | Monitored, expected 5–8%; reviewed if above 9% |
| Holdings | 40–80 companies |
| Turnover (one-way) | 25–40% p.a. (average holding period 3+ years) |
| Quality of portfolio vs benchmark | Higher ROE, higher FCF conversion, lower leverage — checked each quarter |
| Explainability | Every holding has a one-page thesis and a written sell trigger |

## 2. Investment philosophy

Small companies that convert profits into cash and reinvest at high returns compound value, and the market under-prices that persistence because coverage is thin. Earnings can be managed; cash flow and returns on capital are harder to fake, so the process anchors on them.

## 3. Screening methodology

**Step 1 – Hard filters** remove companies the process cannot judge or trade:

1. Benchmark constituent (plus up to 10% off-benchmark developed small caps).
2. 20-day average daily value traded ≥ $1m.
3. At least 5 years of annual statements. Interim rule while non-US data comes from the free Yahoo source
   (about 4 years, estimated filing dates): 4 years for those companies.
4. Positive free cash flow in at least 3 of the last 5 years.
5. Positive book equity and ROE > 0.
6. Net debt ÷ EBITDA < 3x.
7. Financials (banks, insurers) scored on a separate ROE and book-value list, not on FCF.
8. **ROE beats the cost of equity:** 5-year median ROE ≥ the regional cost of equity (see table below). Growth only creates value when reinvested profit earns more than its cost, so ranking ROE against peers is not enough.
9. **Limited dilution:** diluted share count grows ≤ 5% a year over 3 years.
10. **Receivables in line with sales:** 3-year receivables growth exceeds 3-year sales growth by no more than 15 percentage points a year. Receivables outrunning sales is a classic sign of early or doubtful revenue.

| Region | Cost of equity (small cap) |
| --- | --- |
| North America | 9.0% |
| Europe (incl. UK, Israel) | 9.0% |
| Japan | 7.0% |
| Pacific ex Japan | 9.0% |

Cost of equity = local long-term risk-free rate + a small-cap equity risk premium; reviewed once a year and logged.

**Step 2 – Score four pillars.** Each metric is winsorised at the 1st and 99th percentiles and ranked 0–100 within its sector and region (falling back to region alone when a sector–region group has fewer than 10 names).

| Pillar | Metric | Definition |
| --- | --- | --- |
| Earnings | Earnings yield | TTM net income ÷ market cap |
| Earnings | Earnings stability | Number of loss years in last 5 (fewer is better) |
| Earnings | Accruals | (Net income – operating cash flow) ÷ average assets (lower is better) |
| Earnings | Receivables gap | 3-year receivables growth – 3-year sales growth, % a year (lower is better) |
| Cash | FCF yield | (Operating cash flow – capex) ÷ enterprise value |
| Cash | FCF conversion | 5-year sum of FCF ÷ 5-year sum of net income |
| Returns | ROE spread | 5-year median ROE – regional cost of equity |
| Returns | ROE stability | 5-year standard deviation of ROE (lower is better) |
| Returns | ROIC cross-check | NOPAT ÷ (debt + equity – cash), to catch leverage-driven ROE |
| Balance sheet | Leverage | Net debt ÷ EBITDA (lower is better) |
| Balance sheet | Dilution | 3-year growth in diluted share count, % a year (lower is better) |

**Step 3 – Rank.** Composite = equal-weighted average of the four pillar scores. The top 150 names form the research list. Each pillar score is shown, so a rank is always explained.

**Step 4 – Research review.** For each name on the list, a short check before buying:

- [ ] Read the last annual report: what drives revenue, who are the customers?
- [ ] Confirm FCF is not flattered by one-offs (working capital release, asset sales, capitalised costs)
- [ ] Check ROE against ROIC: is it driven by margins or by leverage and buybacks?
- [ ] Note management ownership and capital allocation record
- [ ] Check the governance red flags below
- [ ] Write the thesis in three sentences and the sell trigger in one

**Governance red flags** (recorded in the research note for each name):

1. Material related-party transactions
2. Complex group or ownership structure that obscures control
3. High turnover of CEO, CFO, directors or auditor in the last 3 years
4. Auditor disputes, qualified opinions, restatements or persistent late filings
5. Management committing to aggressive targets, with pay tied mainly to short-term earnings or the share price
6. History of securities-law or reporting violations

One flag requires a written justification in the note before buying; two or more flags exclude the name.

## 4. Portfolio construction

| Rule | Specification |
| --- | --- |
| Position sizing | Three conviction levels: 1.0%, 1.75%, 2.5% |
| Maximum position | 4.0% (after market moves) |
| Sector weight | Benchmark ±10% |
| Country weight | Benchmark ±10% (US and Japan ±15%) |
| Liquidity | Position ≤ 5 days of 20-day ADV at 25% participation |
| Cash | ≤ 3% |
| Sell triggers | Thesis broken; composite falls out of top 40%; valuation target reached; better idea needs the capital; a hard filter is failed; governance flags reach two |

## 5. Data sources

| Data | Source | Coverage | Cost | Notes |
| --- | --- | --- | --- | --- |
| Universe and sectors | [iShares MSCI World Small Cap UCITS ETF holdings](https://www.ishares.com) | Global | Free | Constituents, weights, GICS sector |
| US statements | [SEC EDGAR XBRL API](https://www.sec.gov/edgar/sec-api-documentation) | US | Free | Net income, cash flow, capex, equity, debt tags |
| UK statements | [Companies House API](https://developer.company-information.service.gov.uk) | UK | Free | Filed accounts; annual reports for review |
| EU statements | [filings.xbrl.org](https://filings.xbrl.org) | EU (ESEF) | Free | Structured annual reports since 2021 |
| Japan statements | [EDINET](https://disclosure2.edinet-fsa.go.jp) | Japan | Free | Large benchmark weight; Japanese-language tags |
| Canada statements | [SEDAR+](https://www.sedarplus.ca) | Canada | Free | Filings as documents, less structured |
| Global normalised fundamentals | Financial Modeling Prep or EODHD | Global | Low monthly fee | Fastest way to cover all 23 countries |
| Prices and market cap | yfinance (prototype), EODHD/FMP (production) | Global | Free / low fee | For FCF yield, EV, liquidity |
| Identifier mapping | [OpenFIGI API](https://www.openfigi.com/api) | Global | Free | Ticker to FIGI |
| Company documents | Company investor-relations websites | Global | Free | Annual reports, presentations, transcripts |

## 6. Infrastructure

1. **Ingest** (weekly): holdings, prices; quarterly: statements for the universe.
2. **Store**: DuckDB tables for statements (company, period end, filing date), prices and scores.
3. **Screen** (monthly): apply filters, compute pillars and composite, save a dated snapshot.
4. **Review**: React web app that shows every stage of the process — universe, hard-filter funnel, screener (sliders for filters and pillar weights, sortable table, 5-year charts per company), research list, portfolio and backtest.
5. **Research notes**: one Markdown file per holding (thesis, trigger, conviction, checklist, governance flags, review dates) kept in git.
6. **Monitor** (quarterly): portfolio vs benchmark on ROE, FCF conversion, leverage; TE and attribution.

| Layer | Tool |
| --- | --- |
| Language | Python 3.10+ |
| Data handling | pandas |
| Storage | DuckDB + Parquet |
| API | FastAPI |
| Front end | React + TypeScript (Vite), Recharts for charts |
| Research notes | Markdown with a JSON front matter block, in a git repository |
| Scheduling | cron or GitHub Actions |
| Risk monitoring | Spec A's risk model if built; otherwise realised TE from 3 years of weekly returns |

## 7. Validation and monitoring

- Backtest the screen (not the judgement) over 10+ years: return of top vs bottom quintile by region.
- Use statements only from the filing date; include delisted companies.
- Quarterly: style exposures (quality, low beta, size, value) so tilts are known, not discovered.
- Annual: review each sell decision against what happened next.

## 8. Open questions

- Parse EDINET and ESEF directly, or pay a vendor for normalised global statements?
- Should financials be included at all, or held only via a separate small sleeve?
