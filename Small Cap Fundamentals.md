# Small Cap Fundamentals – What Drives Share Prices

Oct 16, 2026 · Summary of the five CFA Level II (2026) equity valuation readings: *Equity Valuation: Applications and Processes*, *Discounted Dividend Valuation*, *Free Cash Flow Valuation*, *Market-Based Valuation: Price and Enterprise Value Multiples*, *Residual Income Valuation*.

The readings are about valuation in general, not about small caps. Points marked **(small cap)** are either where the readings mention smaller or neglected companies directly, or where I have applied their logic to small caps.

## 1. How share prices increase

A share is worth the present value of the cash it will produce for its owners:

```
Value = Σ  CF_t / (1 + r)^t        CF = dividends, FCFE, or (book value + residual income)
```

Because every model starts from this formula, a share price can rise for only four reasons.

| Driver | What happens | Where the readings show it |
| --- | --- | --- |
| **1. The fundamentals grow** | Earnings, free cash flow and book value compound. If the valuation multiple stays the same, price grows at the same rate *g* as the fundamentals. | Gordon model: value and dividends both grow at *g*, so the expected return is dividend yield + *g* |
| **2. Expectations rise** | The price already reflects what the market expects. It moves when news changes that expected growth or profitability. | Intel fell 30% on a 2–4 point revenue miss; you can work backwards from a price to the growth it implies |
| **3. The required return falls** | Lower risk, lower interest rates or better liquidity reduce *r*, and the multiple rises. | Justified P/E = (1 − b)/(r − g), so the multiple moves inversely to *r* |
| **4. A mispricing closes** | Estimated value minus price = (true value − price) + (your estimation error). You only earn the first part, and often only when a **catalyst** forces the market to look again. | Grossman–Stiglitz; Cornell's Intel study |

**The key point: growth by itself does not create value.** Reinvested profit adds value only when the return on that reinvestment beats the cost of equity:

```
Sustainable growth    g   = retention ratio × ROE
Value                 V   = E1/r  (no-growth value)  +  PVGO  (value of future growth)
Residual income       V   = Book value + PV of Σ (ROE − r) × Book value
Justified P/B         P/B = (ROE − g) / (r − g)      → above 1 only if ROE > r
```

A company that reinvests at less than *r* still grows its EPS, but it destroys value. A company with **ROE above *r*** that can **reinvest at that rate for a long time** compounds book value, residual income and price together. This is the main thing to look for in a small cap.

## 2. Fundamentals to look for in a small cap

### a. Returns on capital above the cost of equity, and lasting
- ROE or ROIC that sits clearly above *r* (residual income is positive). Use ROIC when debt levels differ between companies.
- **Split ROE with DuPont** (margin × asset turnover × leverage). IBM's 52% ROE came from 7× leverage; its margins and turnover were ordinary for its industry. ROE driven by margins and turnover is the kind to own.
- **How long it lasts.** High returns attract competitors and tend to fall back over time. Dechow et al. found residual income decays by about 38% a year on average.
  - Signs that high returns will last: a low payout ratio, and an industry where high returns have historically persisted.
  - Signs that they will fade: an extreme ROE, large one-off items, and high accruals.

### b. A long runway to reinvest
- A low payout or no dividend is fine as long as the retained profit earns more than *r*. **(Small cap)** Smaller and younger companies pay dividends less often, so value them with FCF or residual income models rather than a dividend model.
- A competitive edge that can be defended: Porter's five forces, market share trends, and a cost-leadership or differentiation strategy.
- Be realistic about how long fast growth lasts. A patent or first-mover lead is temporary, and growth eventually settles near nominal GDP.

### c. Profit that turns into cash
- `FCFE = Net income + non-cash charges − capex − working-capital investment + net borrowing`. Check that FCF follows earnings over several years.
- **Accruals.** The cash part of earnings is more persistent than the accrual part (Sloan 1996). Companies with high accruals have lower future ROA.
- **Working-capital releases cannot repeat.** Cutting inventory or stretching payables flatters FCF once, and a growing company will need more working capital, not less.
- A company that is profitable but has negative FCF because it is investing heavily (a retailer opening stores, for example) is not automatically bad. Value it with residual income, which recognises value earlier.

### d. Earnings quality (red flags)
- Receivables growing faster than sales. At Tangoe, receivables rose 32% against 12% sales growth before it was charged with fraud.
- Costs capitalised instead of expensed. Livent's reported debt/EBITDA was 1.7×, but 5.5× once those costs were treated as expenses.
- Revenue booked early or counted gross. Diebold used bill-and-hold sales; Groupon counted the full voucher price as revenue.
- Gains that will not recur counted as operating income, and "core" or "adjusted" earnings that the company defines itself. Rebuild underlying EPS yourself.
- Optimistic estimates: long asset lives, low reserves, and "cookie-jar" provisions released later.
- **EBITDA is not cash flow.** It ignores taxes, capex and working capital. Never discount EBITDA or divide it by a bond yield.

### e. Balance sheet strength
- Leverage raises both ROE and risk. Check net debt/EBITDA, interest cover and off-balance-sheet obligations.
- When comparing companies with different debt levels, use EV multiples (EV/EBITDA, EV/Sales) rather than P/E or P/S. Use an FCFF model when leverage is changing.
- Book value: remove goodwill, think about internally built intangibles that are missing from it, and watch whether buybacks are distorting P/B.

### f. Governance and dilution
- Fraud-risk indicators from the readings: related-party transactions, complex ownership, high turnover among managers or auditors, management promising aggressive targets, and pay heavily tied to the share price.
- Use **diluted** EPS and the fully diluted share count, because options and convertibles transfer value away from existing shareholders.
- **(Small cap)** Look at management ownership and how they have allocated capital in the past (the readings mention ownership structure as a qualitative factor).

### g. A sensible price
- **"A good company is not necessarily a good investment."** Returns depend on the price you pay.
- Compare multiples only alongside the fundamentals behind them:
  - P/E rises with growth and falls with risk.
  - P/B rises with ROE.
  - P/S rises with profit margin.
  - EV/EBITDA rises with ROIC and FCFF growth.
- Practical adjustments:
  - For cyclical companies, use **normalised EPS**: average ROE × current book value.
  - When earnings are negative, rank on **earnings yield (E/P)** instead of P/E.
  - For peer averages, use the median or harmonic mean so outliers don't dominate.
  - Treat PEG with care: it assumes growth and P/E are linearly related and ignores risk and how long growth lasts.
- **Terminal value usually makes up most of a DCF value**: 88–94% in the readings' examples. Run sensitivity checks on *g* and *r*. Residual income models depend less on terminal value.

## 3. Points specific to small caps

| Issue | What the readings say | What it means for us |
| --- | --- | --- |
| Neglect | Markets are less efficient for stocks that few analysts cover (Grossman–Stiglitz) | There is more room for price and value to differ, so research effort pays off more |
| Liquidity | Thinly traded shares carry an **illiquidity discount**, and selling a large block gets a lower price | Size positions by average daily volume, and expect a higher required return |
| Required return | Build-up approach: country return ± adjustments for **size**, industry and leverage | Use a higher *r*, which lowers justified multiples |
| Choosing a model | Use FCF or residual income models when there are no dividends, when FCF is negative near term, or when terminal value is very uncertain | Residual income or FCFE usually fit better than a dividend model |
| Catalysts | Price may take a long time to converge on value without a catalyst | Look for events such as an earnings inflection, a spin-off, a refinancing or a takeover |
| Takeover value | A **control perspective** (FCF) applies when a company could be acquired | A small cap with high ROIC and low debt can attract bidders, which can put a floor under the price |

## 4. One-page checklist

1. Is ROE or ROIC above the cost of equity, and is it driven by margins and turnover rather than leverage?
2. Can the company reinvest at that return for 5–10 years or more? What protects it from competitors?
3. Does profit turn into cash: steady FCF, low accruals, receivables not growing faster than sales?
4. Is the balance sheet safe, with moderate net debt/EBITDA and no hidden liabilities?
5. Are the earnings clean: no recurring "one-offs", no aggressive capitalisation or revenue recognition?
6. Are governance and dilution acceptable: insider ownership, a stable auditor, a controlled share count?
7. Is the price sensible: what growth does today's price imply, and is that plausible?
8. Is there a catalyst, and is the stock liquid enough for the position size?

## 5. How this maps to our specs

- **Spec B** pillars match sections 2a–2e: the earnings, cash and returns pillars plus the ROIC check and the leverage filter. Items to consider adding: receivables growth vs sales growth, share-count dilution, and the governance red flags in 2f. ROE should be tested **against the cost of equity**, not only ranked against peers.
- **Spec A** factors map onto the same theory:
  - Quality corresponds to ROE > r.
  - Value corresponds to justified multiples.
  - Low investment matches the warning that growth only adds value when ROE > r.
  - Momentum matches the readings' relative-strength and earnings-surprise indicators.
