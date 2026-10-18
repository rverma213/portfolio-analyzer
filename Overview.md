# Global Smaller Companies – Strategy Specifications

Oct 16, 2026 · @Ravi

## Purpose and scope

Two long-only strategies aim to beat the MSCI World Small Cap Index after costs, using public or low-cost data only. They share a benchmark and universe but differ in how decisions are made.

- **Spec A – Quantitative (top-down):** start from a risk budget and a target information ratio, then let a factor model and optimizer choose weights across the whole universe.
- **Spec B – Fundamental (bottom-up):** start from individual companies, screen on earnings, free cash flow and ROE, then build a concentrated portfolio by conviction with simple risk limits.

Both methods are kept deliberately simple so every holding can be explained in one sentence. This is a design specification, not investment advice.

## Side-by-side comparison

| Dimension | A – Quantitative (top-down) | B – Fundamental (bottom-up) |
| --- | --- | --- |
| Objective | Excess return of 2.0% p.a. at 4% tracking error (IR 0.5), rolling 3 years | Excess return of 3.0% p.a. over a full cycle (5 years); TE allowed 5–8% |
| Starting point | Risk budget and target IR | Individual company quality and valuation |
| Decision driver | Composite factor score fed to an optimizer | Screen rank plus analyst review of each name |
| Holdings | 200–400 stocks | 40–80 stocks |
| Typical active weight | 0.2–1.0% per stock | 1.0–3.0% per stock |
| Signals | Value, quality, momentum, low investment (4 factors, equal weight) | Earnings, free cash flow, ROE, balance sheet (4 pillars) |
| Risk control | Factor risk model; TE target enforced by optimizer | Simple limits: stock, sector, country, liquidity; TE monitored, not targeted |
| Rebalance | Monthly | Quarterly review; trade on thesis change |
| Turnover (one-way) | 60–100% p.a. | 25–40% p.a. |
| Main data need | Prices and fundamentals for whole universe (\~4,000 stocks) | Deep fundamentals for screened names (\~500 short-list) |
| Infrastructure | Python pipeline, database, risk model, optimizer (cvxpy) | Python pipeline, database, FastAPI + React app, research notes |
| Explaining a holding | "Ranks in top decile on the composite score within its sector" | "Converts 95% of earnings to cash, ROE 18% for five years, FCF yield 7%" |
| Key risk | Factor crowding; model risk in data-poor markets | Concentration; style drift into quality/low-beta |

The two can run together: Spec B's screen score can become one signal in Spec A, and Spec A's risk model can monitor Spec B's unintended bets.

## Common elements

| Item | Specification |
| --- | --- |
| Benchmark | MSCI World Small Cap Index (net total return), about 4,000 stocks in 23 developed markets |
| Base currency | GBP for reporting; currency exposure unhedged, as in the benchmark |
| Universe | Benchmark constituents, reconstructed from the iShares MSCI World Small Cap UCITS ETF daily holdings file |
| Off-benchmark names | Up to 10% of the portfolio in developed-market small caps outside the index (e.g., recent IPOs, migrants) |
| Vehicle | Long-only, fully invested (cash ≤ 3%), no derivatives or leverage |
| Liquidity floor | 20-day average daily value traded ≥ $1m; position ≤ 10% of ADV to trade in one day |
| Performance measures | Excess return, tracking error, information ratio, hit rate, drawdown vs benchmark |
| Attribution | Monthly: country, sector, style factor, currency and stock-specific contributions |
| Governance | Written rules for every step; changes logged with date and reason; quarterly review against these specs |

## The two specifications

Each tab follows the same order: objective, methodology, portfolio rules, data sources, infrastructure, validation and open questions.

- Spec A – Quantitative: target IR, factor signals, risk model, optimizer constraints.
- Spec B – Fundamental: screening filters, earnings/FCF/ROE pillars, research checklist, conviction sizing.
