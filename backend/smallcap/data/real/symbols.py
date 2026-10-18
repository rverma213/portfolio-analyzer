"""Map iShares holdings (local ticker + exchange + location) to Yahoo Finance symbols.

Each holding gets an ordered list of candidate symbols; the first one Yahoo has
prices for wins (see yahoo.resolve). Anything that still fails can be fixed by
hand in data/symbol_overrides.csv (columns: ticker, exchange, yahoo).
"""
from __future__ import annotations

import re

import pandas as pd

from ...config import DATA_DIR

OVERRIDES = DATA_DIR / "symbol_overrides.csv"

# Exchange-name keywords (lower case) -> Yahoo suffix. Checked in order.
EXCHANGE_SUFFIX = [
    ("tokyo", ".T"), ("nagoya", ".N"), ("london", ".L"), ("xetra", ".DE"), ("deutsche", ".DE"),
    ("frankfurt", ".F"), ("toronto", ".TO"), ("tsx venture", ".V"), ("venture", ".V"), ("asx", ".AX"),
    ("australian", ".AX"), ("six swiss", ".SW"), ("swiss", ".SW"), ("stockholm", ".ST"),
    ("copenhagen", ".CO"), ("helsinki", ".HE"), ("oslo", ".OL"), ("amsterdam", ".AS"),
    ("paris", ".PA"), ("brussels", ".BR"), ("lisbon", ".LS"), ("dublin", ".IR"), ("irish", ".IR"),
    ("borsa italiana", ".MI"), ("milan", ".MI"), ("madrid", ".MC"), ("bolsa", ".MC"),
    ("wiener", ".VI"), ("vienna", ".VI"), ("tel aviv", ".TA"), ("hong kong", ".HK"),
    ("singapore", ".SI"), ("new zealand", ".NZ"),
]
US_EXCHANGE_WORDS = ("new york", "nyse", "nasdaq", "cboe", "bats", "american", "arca", "nyse mkt")

# Fallback by country of listing when the exchange name is not recognised.
COUNTRY_SUFFIX = {
    "United States": "", "Canada": ".TO", "United Kingdom": ".L", "Japan": ".T", "Australia": ".AX",
    "Germany": ".DE", "France": ".PA", "Netherlands": ".AS", "Belgium": ".BR", "Italy": ".MI",
    "Spain": ".MC", "Portugal": ".LS", "Ireland": ".IR", "Switzerland": ".SW", "Sweden": ".ST",
    "Denmark": ".CO", "Finland": ".HE", "Norway": ".OL", "Austria": ".VI", "Israel": ".TA",
    "Hong Kong": ".HK", "Singapore": ".SI", "New Zealand": ".NZ",
}
# Nordic exchanges are often reported as "Nasdaq Omx Nordic": use the country.
NORDIC = {"Sweden": ".ST", "Denmark": ".CO", "Finland": ".HE"}


def suffix_for(exchange: str, country: str) -> str | None:
    ex = (exchange or "").lower()
    if "nordic" in ex or "omx" in ex:
        return NORDIC.get(country, COUNTRY_SUFFIX.get(country))
    for word, sfx in EXCHANGE_SUFFIX:
        if word in ex:
            return sfx
    if any(w in ex for w in US_EXCHANGE_WORDS):
        return ""
    return COUNTRY_SUFFIX.get(country)


def candidates(ticker: str, exchange: str, country: str) -> list[str]:
    """Ordered guesses for the Yahoo symbol of one holding."""
    t = (ticker or "").strip().upper().rstrip(".")
    if not t:
        return []
    sfx = suffix_for(exchange, country)
    if sfx is None:
        return []
    out: list[str] = []

    def add(base: str, s: str = sfx):
        sym = f"{base}{s}"
        if base and sym not in out:
            out.append(sym)

    if sfx == ".HK" and t.isdigit():
        add(t.zfill(4))
    elif sfx == ".T" and t.isdigit():
        add(t)
    else:
        dashed = re.sub(r"[ ./]+", "-", t)
        add(dashed)
        add(t.replace(" ", "").replace(".", ""))
        # Share classes written without a separator, e.g. MOGA -> MOG-A (US) or HUSQB -> HUSQ-B.
        if re.fullmatch(r"[A-Z]{2,6}[AB]", t):
            add(f"{t[:-1]}-{t[-1]}")
        if sfx == ".L":
            add(dashed.rstrip("-"))
        if sfx == ".TO":
            add(dashed, ".V")  # TSX Venture names sometimes appear under the TSX
    return out


def load_overrides() -> dict[tuple[str, str], str]:
    if not OVERRIDES.exists():
        return {}
    df = pd.read_csv(OVERRIDES, dtype=str).fillna("")
    return {(r.ticker.strip().upper(), r.exchange.strip()): r.yahoo.strip() for r in df.itertuples()}
