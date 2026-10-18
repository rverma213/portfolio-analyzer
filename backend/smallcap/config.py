"""Spec B parameters in one place.

Every number here traces to a line in `Spec B – Fundamental.md`. The API exposes
these as defaults; the front end can override them per request (sliders), but a
change to a default belongs in the spec first.
"""
from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
DB_PATH = DATA_DIR / "smallcap.duckdb"
NOTES_DIR = ROOT / "research" / "notes"

# MSCI World's 23 developed markets mapped to the four regions used for ranking.
REGIONS: dict[str, str] = {
    "United States": "North America",
    "Canada": "North America",
    "United Kingdom": "Europe",
    "France": "Europe",
    "Germany": "Europe",
    "Switzerland": "Europe",
    "Netherlands": "Europe",
    "Sweden": "Europe",
    "Denmark": "Europe",
    "Norway": "Europe",
    "Finland": "Europe",
    "Belgium": "Europe",
    "Austria": "Europe",
    "Ireland": "Europe",
    "Italy": "Europe",
    "Spain": "Europe",
    "Portugal": "Europe",
    "Israel": "Europe",
    "Japan": "Japan",
    "Australia": "Pacific ex Japan",
    "Hong Kong": "Pacific ex Japan",
    "Singapore": "Pacific ex Japan",
    "New Zealand": "Pacific ex Japan",
}

SECTORS = [
    "Communication Services",
    "Consumer Discretionary",
    "Consumer Staples",
    "Energy",
    "Financials",
    "Health Care",
    "Industrials",
    "Information Technology",
    "Materials",
    "Real Estate",
    "Utilities",
]

# Sectors scored on the separate ROE / book-value list (Spec B, hard filter 7).
FINANCIAL_SECTORS = {"Financials"}

# Metric -> (pillar, higher_is_better). Order defines display order.
METRICS: dict[str, tuple[str, bool]] = {
    "earnings_yield": ("Earnings", True),
    "loss_years": ("Earnings", False),
    "accruals": ("Earnings", False),
    "receivables_gap": ("Earnings", False),
    "fcf_yield": ("Cash", True),
    "fcf_conversion": ("Cash", True),
    "roe_spread": ("Returns", True),
    "roe_stability": ("Returns", False),
    "roic": ("Returns", True),
    "leverage": ("Balance sheet", False),
    "dilution": ("Balance sheet", False),
}
PILLARS = ["Earnings", "Cash", "Returns", "Balance sheet"]

# Financials list: ROE and book value instead of FCF (Spec B, hard filter 7).
FINANCIAL_METRICS: dict[str, tuple[str, bool]] = {
    "roe_spread": ("Returns", True),
    "roe_stability": ("Returns", False),
    "earnings_yield": ("Earnings", True),
    "book_to_price": ("Value", True),
}

METRIC_LABELS = {
    "earnings_yield": "Earnings yield",
    "loss_years": "Loss years (5y)",
    "accruals": "Accruals",
    "receivables_gap": "Receivables gap",
    "fcf_yield": "FCF yield",
    "fcf_conversion": "FCF conversion",
    "roe_spread": "ROE spread",
    "roe_stability": "ROE volatility",
    "roic": "ROIC",
    "leverage": "Net debt / EBITDA",
    "dilution": "Dilution",
    "book_to_price": "Book to price",
}


class ScreenParams(BaseModel):
    """Hard filters and scoring choices (Spec B §3)."""

    min_adv_usd: float = Field(1_000_000, description="20-day average daily value traded")
    min_years: int = Field(5, ge=1, le=10, description="Years of annual statements")
    # Free non-US statements (Yahoo) only go back about 4 years, so they get a lower bar.
    min_years_estimated: int = Field(4, ge=1, le=10,
                                     description="Years required when statements come from Yahoo")
    min_positive_fcf_years: int = Field(3, ge=0, le=5)
    max_net_debt_ebitda: float = 3.0
    require_roe_above_coe: bool = True
    max_dilution: float = Field(0.05, description="Diluted share CAGR, 3 years")
    max_receivables_gap: float = Field(0.15, description="Receivables minus sales CAGR, 3 years")
    allow_off_benchmark: bool = True
    cost_of_equity: dict[str, float] = {
        "North America": 0.09,
        "Europe": 0.09,
        "Japan": 0.07,
        "Pacific ex Japan": 0.09,
    }
    pillar_weights: dict[str, float] = {p: 1.0 for p in PILLARS}
    research_list_size: int = 150
    min_group_size: int = 10


class PortfolioParams(BaseModel):
    """Portfolio construction rules (Spec B §4)."""

    aum_usd: float = 100_000_000
    target_holdings: int = 60
    min_holdings: int = 40
    max_holdings: int = 80
    conviction_weights: dict[str, float] = {"high": 0.025, "medium": 0.0175, "low": 0.010}
    max_position: float = 0.04
    sector_band: float = 0.10
    country_band: float = 0.10
    country_band_large: float = 0.15  # US and Japan
    large_countries: list[str] = ["United States", "Japan"]
    adv_days: float = 5.0
    adv_participation: float = 0.25
    max_cash: float = 0.03
    off_benchmark_max: float = 0.10
    sell_rank_pct: float = 0.40  # sell when composite falls out of the top 40%
    trade_band: float = 0.005  # leave a retained holding alone if within 0.5pp of target
    max_governance_flags: int = 1  # two or more flags exclude
    include_financials: bool = False


class BacktestParams(BaseModel):
    start: str = "2015-03-31"
    end: str | None = None
    rebalance_months: int = 3
    cost_bps: float = 40.0  # one-way, commission + spread + impact for small caps
    quintile_min_names: int = 25
