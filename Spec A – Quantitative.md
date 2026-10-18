# Spec A – Quantitative, top-down

Spec A targets 2.0% a year above MSCI World Small Cap at 4% tracking error, an information ratio of 0.5, by tilting a broad portfolio toward four rewarded factors under a factor risk model.

## 1. Objective

| Item | Target |
| --- | --- |
| Excess return | +2.0% p.a. net of costs vs benchmark (net TR, GBP) |
| Tracking error (ex-ante) | 4.0%, allowed range 3.0–5.0% |
| Information ratio | 0.5 over rolling 3 years |
| Holdings | 200–400 stocks |
| Turnover (one-way) | ≤ 100% p.a. |
| Unintended risk | ≥ 60% of active risk from the intended factors and stock selection, ≤ 40% from country, sector and currency |

The targets follow the fundamental law of active management:

```latex
IR \approx IC \times \sqrt{Breadth} \times TC
```

IC is the correlation of the signal with next-month returns, Breadth is the number of independent bets per year and TC is how much of the signal survives the constraints. An IR of 0.5 needs only a modest IC (about 0.02–0.03) because breadth is large, but a long-only small-cap portfolio typically keeps a TC of only 0.3–0.5.

## 2. Methodology

1. **Universe.** Take benchmark constituents each month. Drop stocks below the liquidity floor or with under 24 months of price history.
2. **Signals.** Four factors, each the average of 2–3 simple measures:
   - Value: earnings yield (E/P), book-to-price, FCF yield (FCF ÷ EV)
   - Quality: ROE, gross profit ÷ assets, low accruals
   - Momentum: 12-month return excluding the last month
   - Investment: minus total asset growth over 1 year
3. **Standardise.** Winsorise each measure at ±3 standard deviations, then z-score within sector and region so every stock competes with its peers.
4. **Combine.** Composite score = equal-weighted average of the four factor z-scores. No weight fitting on past returns.
5. **Expected return (alpha).** Alpha = IC × residual volatility × composite score, with IC fixed at 0.03. This keeps alpha in the same units as risk.
6. **Risk model.** See section 3.
7. **Optimise.** Maximise alpha minus a risk penalty minus trading costs, subject to the constraints in section 4. Increase or decrease the risk penalty until ex-ante TE is 4%.
8. **Trade.** Rebalance monthly. Skip trades under 0.05% of the portfolio.

## 3. Risk model (simple fundamental factor model)

Each stock's return is explained by its exposures to common factors plus a stock-specific part. Active risk is then:

```latex
TE^2 = h_a^\top (X F X^\top + \Delta) h_a
```

h\_a is the active weight vector, X the exposures, F the factor covariance and Δ the specific variances.

| Component | Specification |
| --- | --- |
| Country factors | 23, one per benchmark country |
| Sector factors | 11 GICS sectors |
| Currency | One per currency vs GBP, from FX returns |
| Style factors | 6: size, beta, momentum, value, quality, liquidity |
| Exposures | Style = z-scores, cap-weighted mean 0, std 1; country/sector = 0 or 1 |
| Estimation | Weekly cross-sectional regression, weighted by √market cap |
| Factor covariance | Exponentially weighted: half-life 52 weeks for volatility, 104 weeks for correlation |
| Specific risk | Exponentially weighted residual variance (half-life 52 weeks), shrunk 50% toward its size-decile average |
| Why weekly | Reduces the time-zone and stale-price problems of daily data for Japan, Australia and illiquid names |

The model is checked monthly with a bias statistic: realised ÷ forecast volatility for test portfolios should sit between 0.8 and 1.2.

## 4. Portfolio constraints

| Constraint | Limit |
| --- | --- |
| Stock active weight | –benchmark weight to +1.0% |
| Stock absolute weight | ≤ 1.5% |
| Sector active weight | ±3% |
| Country active weight | ±3% (±5% for US and Japan) |
| Style active exposure | Size, beta, liquidity within ±0.25 standard deviations |
| Liquidity | Position ≤ 3 days of 20-day ADV at 25% participation |
| Monthly turnover | ≤ 10% one-way |
| Transaction costs | Commission 5 bp + spread + impact (impact ∝ √(trade ÷ ADV)) |

## 5. Data sources

| Data | Source | Coverage | Cost | Notes |
| --- | --- | --- | --- | --- |
| Benchmark constituents and weights | [iShares MSCI World Small Cap UCITS ETF holdings](https://www.ishares.com) | Global, daily | Free | Proxy for index; archive the file daily to build history |
| Second constituent check | [SPDR MSCI World Small Cap UCITS ETF holdings](https://www.ssga.com) | Global | Free | Cross-check weights and sectors |
| Index rules | [MSCI index methodology](https://www.msci.com/index-methodology) | Rules only | Free | Rebalance dates, size bands |
| Prices, volumes | Yahoo Finance via yfinance; Stooq | Global | Free | Prototype only: gaps, no delisted stocks |
| Prices, volumes, delisted | EODHD or Financial Modeling Prep | Global | Low monthly fee | Production choice; includes delisted tickers |
| US fundamentals | [SEC EDGAR XBRL API](https://www.sec.gov/edgar/sec-api-documentation) | US, from 2009 | Free | Point-in-time via filing dates |
| Non-US fundamentals | FMP or EODHD fundamentals | Global | Low monthly fee | Check for point-in-time history |
| Identifier mapping | [OpenFIGI API](https://www.openfigi.com/api) | Global | Free | Map ETF tickers to exchange tickers |
| Factor research | [Ken French Data Library](https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html), [AQR Data Sets](https://www.aqr.com/Insights/Datasets), [JKP Global Factors](https://jkpfactors.com) | Global | Free | Sanity-check factor returns; not for live signals |
| FX and rates | [Bank of England database](https://www.bankofengland.co.uk/boeapps/database/), [ECB](https://data.ecb.europa.eu), [FRED](https://fred.stlouisfed.org) | Global | Free | FX for currency factors; GBP risk-free rate |
| Upgrade path | WRDS (Compustat Global, CRSP) | Global | Institutional | If university access is available |

## 6. Infrastructure

1. **Ingest** (daily): download ETF holdings, prices, FX; weekly: fundamentals.
2. **Store**: raw files kept unchanged as Parquet; cleaned tables in DuckDB keyed on (FIGI, date, filing date).
3. **Compute** (monthly): signals → composite → alpha; weekly: risk-model update.
4. **Optimise** (monthly): cvxpy problem → target weights → trade list.
5. **Report**: holdings, ex-ante TE and risk decomposition, attribution, model checks.

| Layer | Tool |
| --- | --- |
| Language | Python 3.12 |
| Data handling | pandas or polars |
| Storage | DuckDB + Parquet files |
| Statistics | statsmodels, numpy |
| Optimiser | cvxpy (OSQP or Clarabel solver) |
| Scheduling | cron on a small cloud VM, or GitHub Actions |
| Version control | git; data snapshots dated, never overwritten |
| Reporting | Streamlit dashboard plus a monthly PDF |
| Compute | A laptop is enough: \~4,000 stocks × weekly data fits in memory |

## 7. Validation and monitoring

- Backtest at least 10 years, using only data available on each date (filing date + 1 day).
- Include delisted stocks and their final returns.
- Report IC per signal by region; drop a signal only if its IC is negative over 5+ years.
- Monthly: ex-ante vs realised TE, bias statistic, TC, turnover, cost vs estimate.
- Breach rule: if ex-ante TE leaves 3–5%, rebalance back within 5 trading days.

## 8. Open questions

- Can delisted-stock history be bought for non-US markets at an acceptable cost?
- Should currency be hedged, or left as an active bet within the 4% budget?
