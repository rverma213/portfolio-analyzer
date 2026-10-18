"""Deterministic synthetic universe for building and testing the pipeline offline.

This is NOT market data. It reproduces the *shape* of the real problem so that
every stage of Spec B can be exercised end to end:

* ~23 developed markets with approximate MSCI World Small Cap country weights
* annual statements with point-in-time filing dates (Japan files on a March year)
* listings, delistings (bankruptcy with a -90% final return, takeovers at +30%)
* benchmark membership driven by market-cap bands that drift with the market
* a minority of companies with aggressive accounting (receivables outrun sales,
  high accruals) and a minority of serial share issuers

Returns contain a deliberately small link to fundamentals (quality, cheapness,
accounting aggressiveness) so the backtest has something to find. Any result on
demo data illustrates mechanics only and is not evidence the strategy works.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ..config import REGIONS, SECTORS

COUNTRY_WEIGHTS = {
    "United States": 0.585, "Japan": 0.115, "United Kingdom": 0.055, "Canada": 0.035,
    "Australia": 0.030, "Sweden": 0.020, "Switzerland": 0.016, "Germany": 0.015,
    "France": 0.012, "Italy": 0.010, "Israel": 0.010, "Spain": 0.006, "Netherlands": 0.006,
    "Denmark": 0.006, "Norway": 0.006, "Hong Kong": 0.006, "Singapore": 0.005,
    "Belgium": 0.005, "Finland": 0.004, "Austria": 0.004, "New Zealand": 0.003,
    "Ireland": 0.002, "Portugal": 0.002,
}
SECTOR_WEIGHTS = {
    "Industrials": 0.19, "Financials": 0.12, "Consumer Discretionary": 0.13,
    "Information Technology": 0.11, "Health Care": 0.10, "Real Estate": 0.08,
    "Materials": 0.08, "Consumer Staples": 0.05, "Energy": 0.05,
    "Communication Services": 0.04, "Utilities": 0.03,
}
# Sector base EBITDA margin and asset turnover.
SECTOR_PROFILE = {
    "Communication Services": (0.22, 0.6), "Consumer Discretionary": (0.12, 1.3),
    "Consumer Staples": (0.11, 1.4), "Energy": (0.20, 0.6), "Financials": (0.18, 0.15),
    "Health Care": (0.16, 0.8), "Industrials": (0.13, 1.0), "Information Technology": (0.17, 0.9),
    "Materials": (0.15, 0.8), "Real Estate": (0.45, 0.15), "Utilities": (0.30, 0.35),
}
COUNTRY_CODES = {
    "United States": "US", "Japan": "JP", "United Kingdom": "LN", "Canada": "CN",
    "Australia": "AU", "Sweden": "SS", "Switzerland": "SW", "Germany": "GR", "France": "FP",
    "Italy": "IM", "Israel": "IT", "Spain": "SM", "Netherlands": "NA", "Denmark": "DC",
    "Norway": "NO", "Hong Kong": "HK", "Singapore": "SP", "Belgium": "BB", "Finland": "FH",
    "Austria": "AV", "New Zealand": "NZ", "Ireland": "ID", "Portugal": "PL",
}
_NAME_A = ["North", "Silver", "Harbor", "Summit", "Atlas", "Crown", "Pioneer", "Vantage",
           "Granite", "Beacon", "Meridian", "Evergreen", "Falcon", "Keystone", "Orion",
           "Sterling", "Cobalt", "Highland", "Redwood", "Lakeside", "Trident", "Aurora",
           "Westbrook", "Ironwood", "Bluewater", "Crescent", "Ember", "Juniper", "Nova", "Polar"]
_NAME_B = ["Industries", "Holdings", "Systems", "Group", "Technologies", "Brands", "Logistics",
           "Materials", "Health", "Energy", "Capital", "Networks", "Foods", "Engineering",
           "Labs", "Properties", "Instruments", "Retail", "Services", "Components"]

FIRST_FY = 2008
LAST_FY = 2025
PRICE_START = "2009-01-31"
PRICE_END = "2026-09-30"


def generate(n_companies: int = 2400, seed: int = 7) -> dict[str, pd.DataFrame]:
    rng = np.random.default_rng(seed)
    months = pd.date_range(PRICE_START, PRICE_END, freq="ME")
    n_m = len(months)
    years = np.arange(FIRST_FY, LAST_FY + 1)
    n_y = len(years)

    # ---------------------------------------------------------------- companies
    countries = rng.choice(list(COUNTRY_WEIGHTS), n_companies,
                           p=_norm(list(COUNTRY_WEIGHTS.values())))
    sectors = rng.choice(list(SECTOR_WEIGHTS), n_companies,
                         p=_norm(list(SECTOR_WEIGHTS.values())))
    # ~62% exist from the start; the rest list (IPO) between 2010 and 2024.
    ipo_month = np.where(rng.random(n_companies) < 0.62, 0,
                         rng.integers(12, n_m - 30, n_companies))
    names, tickers = _names(rng, n_companies, countries)

    quality0 = rng.normal(0, 1, n_companies)
    aggressive = rng.random(n_companies) < 0.10
    serial_issuer = rng.random(n_companies) < 0.12
    turnover_daily = np.exp(rng.normal(np.log(0.003), 0.6, n_companies))
    beta = np.clip(rng.normal(1.0, 0.25, n_companies), 0.4, 1.8)
    idio_vol = np.clip(rng.normal(0.075, 0.02, n_companies), 0.035, 0.15)

    # ------------------------------------------------------- annual statements
    quality = np.zeros((n_companies, n_y))
    quality[:, 0] = quality0
    for t in range(1, n_y):
        quality[:, t] = 0.9 * quality[:, t - 1] + np.sqrt(1 - 0.81) * rng.normal(0, 1, n_companies)

    margin_base = np.array([SECTOR_PROFILE[s][0] for s in sectors])
    asset_turn = np.array([SECTOR_PROFILE[s][1] for s in sectors]) * np.exp(rng.normal(0, 0.2, n_companies))
    revenue = np.zeros((n_companies, n_y))
    revenue[:, 0] = np.exp(rng.normal(np.log(600e6), 0.9, n_companies))
    # Common annual demand shock so loss years cluster in downturns (2009, 2020).
    macro = rng.normal(0, 0.03, n_y)
    macro[years == 2009] = -0.10
    macro[years == 2020] = -0.07

    is_fin = sectors == "Financials"
    dep_rate = np.where(is_fin, 0.005, np.where(sectors == "Real Estate", 0.015, 0.045))
    # Banks and insurers fund themselves mostly with deposits / policy liabilities.
    other_ratio = np.where(is_fin, 0.80, 0.20)
    rows = []
    equity_prev = revenue[:, 0] / asset_turn * np.where(is_fin, 0.12, 0.45)
    shares_prev = np.exp(rng.normal(np.log(60e6), 0.7, n_companies))
    dso = np.clip(rng.normal(55, 15, n_companies), 15, 120)
    dso_norm = dso.copy()
    # Some aggressive accounters have not been caught yet by the end of the data.
    writedown_year = np.where(aggressive, rng.integers(6, n_y + 6, n_companies), -1)
    tax_rate = np.where(countries == "United States", 0.24, 0.25)

    for t, fy in enumerate(years):
        q = quality[:, t]
        # Serial issuers raise equity every year and use it to buy growth
        # (acquisitions), so their ROE holds up: only the dilution screen catches them.
        dil = np.where(serial_issuer, rng.uniform(0.06, 0.15, n_companies),
                       np.clip(rng.normal(0.006, 0.01, n_companies), -0.03, 0.04))
        if t > 0:
            g = (0.045 + 0.035 * q + macro[t] + rng.normal(0, 0.09, n_companies)
                 + np.where(serial_issuer, dil, 0))
            revenue[:, t] = revenue[:, t - 1] * np.exp(np.clip(g, -0.5, 0.6))
        rev = revenue[:, t]
        assets = rev / asset_turn
        margin = np.clip(margin_base + 0.05 * q + macro[t] + rng.normal(0, 0.035, n_companies), -0.25, 0.7)
        ebitda = rev * margin
        dep = dep_rate * assets
        ebit = ebitda - dep
        other_liab = other_ratio * assets
        debt_prev = np.maximum(assets - equity_prev - other_liab, 0)
        interest = 0.05 * debt_prev
        pretax = ebit - interest
        net_income = np.where(pretax > 0, pretax * (1 - tax_rate), pretax)

        # Aggressive accounting: revenue booked early -> receivables outrun sales,
        # cash lags earnings, then a write-down year reverses it.
        wd = writedown_year == t
        # Revenue is pulled forward only in the ~5 years before the write-down.
        building = aggressive & (t < writedown_year) & (t >= writedown_year - 5)
        net_income = np.where(wd, net_income - 0.12 * assets, net_income)
        dso = np.where(building, dso * rng.uniform(1.15, 1.32, n_companies), dso)
        dso = np.where(wd, dso * 0.6, dso)
        # Ordinary year-to-year noise in collection days, pulled back to the company's norm.
        pull = np.where(building, 1.0, (dso_norm / dso) ** 0.3)
        dso = np.clip(dso * np.exp(rng.normal(0, 0.06, n_companies)) * pull, 10, 400)
        receivables = rev * dso / 365

        wc_drag = 0.03 * rev * np.clip(g if t > 0 else 0.05, 0, None)
        cfo = net_income + dep - wc_drag + rng.normal(0, 0.015, n_companies) * rev
        cfo = np.where(building, cfo - 0.025 * rev, cfo)
        cfo = np.where(wd, cfo + 0.10 * assets, cfo)  # write-down is non-cash
        capex = dep * np.clip(1.15 + 0.6 * q * 0.2 + rng.normal(0, 0.2, n_companies), 0.6, 2.2)

        shares = shares_prev * (1 + dil)
        new_equity = np.maximum(dil, 0) * np.maximum(equity_prev, 0) * 1.5
        dividends = np.maximum(net_income, 0) * 0.30
        equity = equity_prev + net_income - dividends + new_equity
        # Cash beyond 10% of assets is mostly returned (special dividends / buybacks).
        excess = np.maximum(equity + other_liab - assets - 0.10 * assets, 0)
        dividends = dividends + 0.7 * excess
        equity = equity - 0.7 * excess
        debt = np.maximum(assets - equity - other_liab, 0)
        cash = np.maximum(equity + other_liab - assets, 0) + 0.06 * assets

        period_end = np.where(countries == "Japan", f"{fy + 1}-03-31", f"{fy}-12-31")
        lag = rng.integers(55, 115, n_companies)
        filing = pd.to_datetime(period_end) + pd.to_timedelta(lag, unit="D")
        for i in range(n_companies):
            rows.append((i, fy, period_end[i], filing[i], rev[i], ebitda[i], ebit[i], net_income[i],
                         cfo[i], capex[i], assets[i], equity[i], debt[i], cash[i], receivables[i],
                         shares[i], tax_rate[i], dividends[i]))
        equity_prev, shares_prev = equity, shares

    statements = pd.DataFrame(rows, columns=[
        "idx", "fiscal_year", "period_end", "filing_date", "revenue", "ebitda", "ebit",
        "net_income", "cfo", "capex", "total_assets", "equity", "debt", "cash",
        "receivables", "shares_diluted", "tax_rate", "dividends"])
    statements["period_end"] = pd.to_datetime(statements["period_end"])

    # ------------------------------------------------------------ monthly prices
    regions = np.array([REGIONS[c] for c in countries])
    region_names = sorted(set(REGIONS.values()))
    glob = rng.normal(0.0075, 0.042, n_m)
    glob[(months >= "2020-02-29") & (months <= "2020-03-31")] = [-0.09, -0.22]
    reg_ret = {r: glob + rng.normal(0, 0.018, n_m) for r in region_names}
    sec_ret = {s: rng.normal(0, 0.02, n_m) for s in SECTORS}

    # Latest filed annual statement per company per month (point in time).
    ni_by_year = statements.pivot(index="idx", columns="fiscal_year", values="net_income").to_numpy()
    filing_by_year = statements.pivot(index="idx", columns="fiscal_year", values="filing_date").to_numpy()
    q_month = np.zeros((n_companies, n_m))
    ni_month = np.full((n_companies, n_m), np.nan)
    eq_by_year_all = statements.pivot(index="idx", columns="fiscal_year", values="equity").to_numpy()
    eq_month = np.full((n_companies, n_m), np.nan)
    for m, d in enumerate(months):
        filed = filing_by_year <= np.datetime64(d)
        last = np.where(filed.any(axis=1), filed.shape[1] - 1 - np.argmax(filed[:, ::-1], axis=1), -1)
        ok = last >= 0
        ni_month[ok, m] = ni_by_year[ok, last[ok]]
        eq_month[ok, m] = eq_by_year_all[ok, last[ok]]
        q_month[:, m] = np.where(ok, quality[np.arange(n_companies), np.maximum(last, 0)], quality0)

    mcap = np.full((n_companies, n_m), np.nan)
    ret = np.full((n_companies, n_m), np.nan)
    alive = np.zeros((n_companies, n_m), dtype=bool)
    # Market value starts from book value x a P/B linked to quality, so
    # valuations are anchored to fundamentals rather than random.
    pb = np.exp(rng.normal(np.log(1.7), 0.45, n_companies) + 0.25 * quality0)
    eq_by_year = statements.pivot(index="idx", columns="fiscal_year", values="equity").to_numpy()
    list_year = np.clip(months[ipo_month].year - FIRST_FY - 1, 0, n_y - 1)
    mcap0 = np.maximum(eq_by_year[np.arange(n_companies), list_year], 5e7) * pb
    price0 = rng.uniform(5, 80, n_companies)
    delisted_month = np.full(n_companies, -1)
    delist_return = np.full(n_companies, np.nan)
    delist_reason = np.array([""] * n_companies, dtype=object)
    current = np.where(ipo_month == 0, mcap0, np.nan)

    for m in range(n_m):
        listing = ipo_month == m
        current = np.where(listing & (m > 0), mcap0 * np.exp(rng.normal(0, 0.2, n_companies)), current)
        live = ~np.isnan(current) & (delisted_month < 0) & (ipo_month <= m)
        trading = live & ~listing  # a new listing starts trading the month after it lists
        if m > 0:
            # Prices are anchored to fundamental value (latest filed book x P/B):
            # a slow pull toward it, plus small quality and accounting effects.
            fair = np.maximum(eq_month[:, m - 1], 1e6) * pb
            gap = np.where(trading & np.isfinite(fair), np.log(fair / current), 0.0)
            alpha = (0.012 * q_month[:, m] - 0.025 * aggressive) / 12 + 0.005 * np.clip(gap, -2, 2)
            r = (beta * np.array([reg_ret[x][m] for x in regions])
                 + np.array([sec_ret[s][m] for s in sectors])
                 + rng.normal(0, 1, n_companies) * idio_vol + alpha)
            r = np.clip(r, -0.6, 1.5)
            wd_month = (writedown_year >= 0) & (months[m].year == FIRST_FY + writedown_year + 1) & (months[m].month == 4)
            r = np.where(aggressive & wd_month, r - 0.35, r)
            # Delisting hazards: bankruptcy rises as quality falls; takeovers are random.
            p_bk = 0.0007 * np.exp(-1.3 * q_month[:, m])
            p_ta = 0.0018
            u = rng.random(n_companies)
            bk = trading & (u < p_bk) & (m < n_m - 1)
            ta = trading & ~bk & (u > 1 - p_ta) & (m < n_m - 1)
            r = np.where(bk, -0.90, np.where(ta, 0.30 + r, r))
            ret[trading, m] = r[trading]
            current = np.where(trading, current * (1 + r), current)
            delisted_month = np.where(bk | ta, m, delisted_month)
            delist_return = np.where(bk | ta, r, delist_return)
            delist_reason = np.where(bk, "bankruptcy", np.where(ta, "takeover", delist_reason))
        mcap[live, m] = current[live]
        alive[live, m] = True

    # Benchmark bands drift with the market so membership stays ~stable in count.
    mkt_index = np.cumprod(1 + glob)
    lower = 150e6 * mkt_index / mkt_index[0]
    upper = 10e9 * mkt_index / mkt_index[0]
    # Companies present at the start are seasoned listings, not new issues.
    months_listed = np.where(ipo_month[:, None] == 0, 999, np.arange(n_m)[None, :] - ipo_month[:, None])
    in_bench = alive & (mcap >= lower) & (mcap <= upper) & (months_listed >= 12)

    adv = mcap * turnover_daily[:, None] * np.exp(rng.normal(0, 0.25, (n_companies, n_m)))
    price = price0[:, None] * np.ones((1, n_m))
    growth = np.nan_to_num(np.log1p(np.where(alive, ret, 0.0)))
    price = price * np.exp(np.cumsum(growth, axis=1))

    ci, mi = np.nonzero(alive)
    monthly = pd.DataFrame({
        "idx": ci, "date": months[mi], "total_return": ret[ci, mi], "price": price[ci, mi],
        "mcap_usd": mcap[ci, mi], "adv_usd": adv[ci, mi], "in_benchmark": in_bench[ci, mi],
    })
    # First listed month has no return.
    monthly.loc[monthly["date"] == months[ipo_month[monthly["idx"]]], "total_return"] = np.nan

    companies = pd.DataFrame({
        "idx": np.arange(n_companies), "ticker": tickers, "name": names, "country": countries,
        "region": regions, "sector": sectors,
        "listed_date": months[ipo_month],
        "delisted_date": [months[x] if x >= 0 else pd.NaT for x in delisted_month],
        "delist_reason": [r or None for r in delist_reason],
        "delist_return": delist_return,
    })
    companies["company_id"] = companies["ticker"]
    id_map = companies.set_index("idx")["company_id"]
    statements["company_id"] = statements["idx"].map(id_map)
    monthly["company_id"] = monthly["idx"].map(id_map)
    # Companies that listed after a fiscal year should not have filed it yet;
    # keep only statements whose filing date is after listing minus 3 years
    # (IPO prospectuses include ~3 years of history).
    listed = statements["company_id"].map(companies.set_index("company_id")["listed_date"])
    statements = statements[statements["period_end"] >= listed - pd.DateOffset(years=3)]
    delisted = statements["company_id"].map(companies.set_index("company_id")["delisted_date"])
    statements = statements[delisted.isna() | (statements["filing_date"] <= delisted)]

    return {
        "companies": companies.drop(columns="idx"),
        "statements": statements.drop(columns="idx").reset_index(drop=True),
        "monthly": monthly.drop(columns="idx").reset_index(drop=True),
    }


def _norm(w):
    w = np.asarray(w, dtype=float)
    return w / w.sum()


def _names(rng, n, countries):
    names, tickers, seen = [], [], set()
    letters = np.array(list("ABCDEFGHIJKLMNOPQRSTUVWXYZ"))
    for i in range(n):
        names.append(f"{rng.choice(_NAME_A)} {rng.choice(_NAME_B)}")
        while True:
            t = "".join(rng.choice(letters, rng.integers(3, 5))) + " " + COUNTRY_CODES[countries[i]]
            if t not in seen:
                seen.add(t)
                tickers.append(t)
                break
    # Disambiguate duplicate names with the ticker root.
    s = pd.Series(names)
    dup = s.duplicated(keep=False)
    s[dup] = s[dup] + " (" + pd.Series(tickers)[dup].str.split().str[0] + ")"
    return s.tolist(), tickers
