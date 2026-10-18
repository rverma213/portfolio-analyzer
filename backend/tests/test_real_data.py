"""Offline tests for the real-data adapters (no network)."""
from __future__ import annotations

import pandas as pd
import pytest

from smallcap.data import ishares
from smallcap.data.real import sec
from smallcap.data.real.symbols import candidates

HOLDINGS = '''iShares MSCI World Small Cap UCITS ETF
Fund Holdings as of,"Oct 15, 2026"

Ticker,Name,Sector,Asset Class,Market Value,Weight (%),Notional Value,Shares,Price,Location,Exchange,Currency,FX Rate,Market Currency
CROX,CROCS INC,Consumer Discretionary,Equity,"1,000,000",0.20,"1,000,000","10,000",100.00,United States,NASDAQ,USD,1.00,USD
BEZ,BEAZLEY PLC,Financials,Equity,"700,000",0.14,"700,000","10,000",8.00,United Kingdom,London Stock Exchange,GBP,1.30,GBP
XYZ,SOME TELCO,Communication,Equity,"100,000",0.02,"100,000","1,000",1.00,Japan,Tokyo Stock Exchange,JPY,0.0067,JPY
USD,USD CASH,Cash and/or Derivatives,Cash,"100,000",0.02,"100,000","100,000",1.00,United States,-,USD,1.00,USD
'''


@pytest.mark.parametrize("ticker,exchange,country,first", [
    ("CROX", "NASDAQ", "United States", "CROX"),
    ("MOGA", "New York Stock Exchange Inc.", "United States", "MOGA"),
    ("6481", "Tokyo Stock Exchange", "Japan", "6481.T"),
    ("1882", "Hong Kong Exchanges And Clearing Ltd", "Hong Kong", "1882.HK"),
    ("HUSQ B", "Nasdaq Omx Nordic", "Sweden", "HUSQ-B.ST"),
    ("NOKIA", "Nasdaq Omx Helsinki Ltd.", "Finland", "NOKIA.HE"),
    ("BEZ", "London Stock Exchange", "United Kingdom", "BEZ.L"),
    ("TFII", "Toronto Stock Exchange", "Canada", "TFII.TO"),
])
def test_symbol_candidates(ticker, exchange, country, first):
    c = candidates(ticker, exchange, country)
    assert c[0] == first


def test_share_class_candidate():
    assert "MOG-A" in candidates("MOGA", "New York Stock Exchange Inc.", "United States")


def test_holdings_parse(tmp_path):
    p = tmp_path / "h.csv"
    p.write_text(HOLDINGS, encoding="utf-8")
    assert str(ishares.holdings_date(p)) == "2026-10-15"
    h = ishares.parse(p)
    assert list(h["ticker"]) == ["CROX", "BEZ", "XYZ"]  # cash line dropped
    assert h["weight"].sum() == pytest.approx(1.0)
    assert h.set_index("ticker").loc["XYZ", "sector"] == "Communication Services"
    assert h.set_index("ticker").loc["BEZ", "region"] == "Europe"


def _fact(start, end, val, filed, form="10-K"):
    d = {"end": end, "val": val, "filed": filed, "form": form}
    if start:
        d["start"] = start
    return d


def test_sec_uses_first_filing_and_annual_periods():
    facts = {"facts": {"us-gaap": {
        "Revenues": {"units": {"USD": [
            _fact("2023-01-01", "2023-12-31", 100, "2024-02-20"),
            _fact("2023-01-01", "2023-12-31", 105, "2025-02-20"),   # restated next year: ignored
            _fact("2023-10-01", "2023-12-31", 30, "2024-02-20"),    # quarter inside a 10-K: ignored
            _fact("2024-01-01", "2024-12-31", 120, "2025-02-20"),
            _fact("2024-01-01", "2024-06-30", 55, "2024-08-01", "10-Q"),
        ]}},
        "NetIncomeLoss": {"units": {"USD": [
            _fact("2023-01-01", "2023-12-31", 10, "2024-02-20"),
            _fact("2024-01-01", "2024-12-31", 12, "2025-02-20"),
        ]}},
        "OperatingIncomeLoss": {"units": {"USD": [_fact("2024-01-01", "2024-12-31", 15, "2025-02-20")]}},
        "DepreciationDepletionAndAmortization": {"units": {"USD": [_fact("2024-01-01", "2024-12-31", 5, "2025-02-20")]}},
        "StockholdersEquity": {"units": {"USD": [_fact(None, "2023-12-31", 50, "2024-02-20"),
                                                 _fact(None, "2024-12-31", 60, "2025-02-20")]}},
        "LongTermDebtNoncurrent": {"units": {"USD": [_fact(None, "2024-12-31", 20, "2025-02-20")]}},
        "LongTermDebtCurrent": {"units": {"USD": [_fact(None, "2024-12-31", 5, "2025-02-20")]}},
    }}}
    df = sec.to_schema(sec.annual_statements(facts)).set_index("period_end")
    assert df.loc["2023-12-31", "revenue"] == 100            # original, not the restatement
    assert str(df.loc["2023-12-31", "filing_date"].date()) == "2024-02-20"
    assert df.loc["2024-12-31", "revenue"] == 120
    assert df.loc["2024-12-31", "ebitda"] == 20                # EBIT + D&A
    assert df.loc["2024-12-31", "debt"] == 25                  # non-current + current
    assert len(df) == 2


def test_usd_needs_no_fx_rows():
    from smallcap.data.real.yahoo import to_usd
    empty = pd.DataFrame({"USD": []}, index=pd.DatetimeIndex([]))
    dates = pd.Series(pd.to_datetime(["2020-01-31", "2020-02-29"]))
    assert list(to_usd("USD", empty, dates)) == [1.0, 1.0]


def test_pence_detected_from_ishares_usd_price():
    from smallcap.data.real.build import fix_price_units
    d = pd.Timestamp("2026-09-30")
    fx = pd.DataFrame({"GBP": [1.3], "USD": [1.0]}, index=pd.DatetimeIndex([d]))
    px = pd.DataFrame({"symbol": ["IMI.L", "XYZ.L"], "date": [d, d], "close": [3040.0, 30.4]})
    h = pd.DataFrame({"symbol": ["IMI.L", "XYZ.L"], "quote_currency": ["GBP", "GBP"], "price": [39.53, 39.53]})
    out = fix_price_units(h, px, fx)
    assert list(out["quote_currency"]) == ["GBp", "GBP"]   # 3040p, but 30.40 is already pounds
    assert out["price_check"].between(0.9, 1.1).all()


def test_real_holdings_layout(tmp_path):
    """Layout of the actual iShares download: day/month/year date, only 'Market Currency'."""
    p = tmp_path / "h.csv"
    p.write_text('Fund Holdings as of,"14/Oct/2026"\n\n'
                 'Ticker,Name,Sector,Asset Class,Market Value,Weight (%),Notional Value,Shares,Price,Location,'
                 'Exchange,Market Currency\n'
                 '"MRNA","MODERNA","Health Care","Equity","65,187,299.10","0.74","65,187,299.10","288,057.00",'
                 '"226.30","United States","NASDAQ","USD"\n', encoding="utf-8")
    assert str(ishares.holdings_date(p)) == "2026-10-14"
    assert ishares.parse(p).loc[0, "currency"] == "USD"


def test_sec_no_us_gaap_returns_empty():
    assert sec.annual_statements({"facts": {"ifrs-full": {}}}).empty


def test_yahoo_sourced_names_need_fewer_years():
    from smallcap.config import ScreenParams
    from smallcap.screen import apply_filters
    snap = pd.DataFrame({
        "company_id": ["US1", "JP1"], "sector": "Industrials", "region": ["North America", "Japan"],
        "in_benchmark": True, "mcap_usd": 2e9, "adv_usd": 5e6, "n_years": [4, 4],
        "filing_estimated": [False, True], "positive_fcf_years": 4, "equity": 1e9, "roe": 0.15,
        "roe_median": 0.15, "leverage": 1.0, "dilution": 0.0, "receivables_gap": 0.0,
    })
    f = apply_filters(snap, ScreenParams()).set_index("company_id")
    assert not f.loc["US1", "f_history"]      # SEC data: 5 years required
    assert f.loc["JP1", "f_history"]          # Yahoo data: 4 years is enough
