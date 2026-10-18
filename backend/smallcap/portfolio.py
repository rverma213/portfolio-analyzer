"""Spec B portfolio construction (§4).

Order of operations:
1. Candidates = names that passed every hard filter, by composite rank.
2. Remove names blocked by governance flags (two or more, or one unjustified).
3. Keep existing holdings still in the top 40% (sell rule); then add new names
   by rank until the target number of holdings is reached.
4. Size by conviction (note if written, else by rank tercile), then cap by
   max position, liquidity (5 days of ADV at 25% participation for the AUM),
   sector and country bands vs benchmark, and the off-benchmark limit.
5. Scale to be fully invested (cash ≤ 3%) without breaching any cap.

Benchmark floors (benchmark weight − band) cannot always be met by a
concentrated long-only book, so they are reported, not forced.
"""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from .config import PortfolioParams
from .notes import Note
from .screen import ScreenResult

MIN_WEIGHT = 0.005  # below this a position is not worth holding


@dataclass
class Portfolio:
    as_of: pd.Timestamp
    holdings: pd.DataFrame
    checks: list[dict]
    exposures: dict[str, list[dict]]
    characteristics: list[dict]
    skipped: list[dict] = field(default_factory=list)

    @property
    def weights(self) -> pd.Series:
        return self.holdings.set_index("company_id")["weight"]


def benchmark(frame: pd.DataFrame) -> pd.DataFrame:
    b = frame[frame["in_benchmark"]].copy()
    b["bench_weight"] = b["mcap_usd"] / b["mcap_usd"].sum()
    return b


def _country_cap(country: str, bench_w: float, p: PortfolioParams) -> float:
    band = p.country_band_large if country in p.large_countries else p.country_band
    return bench_w + band


def build(screen: ScreenResult, p: PortfolioParams,
          prev: pd.Series | None = None, notes: dict[str, Note] | None = None) -> Portfolio:
    notes = notes or {}
    f = screen.frame
    bench = benchmark(f)
    sector_bw = bench.groupby("sector")["bench_weight"].sum()
    country_bw = bench.groupby("country")["bench_weight"].sum()

    cands = screen.passed.copy()
    if p.include_financials:
        fin = screen.financials.copy()
        fin["composite"] = fin["fin_composite"]
        cands = pd.concat([cands, fin]).sort_values("composite", ascending=False)
        cands["rank"] = np.arange(1, len(cands) + 1)
        cands["rank_pct"] = cands["rank"] / len(cands)

    skipped: list[dict] = []
    blocked = cands["company_id"].map(lambda c: c in notes and notes[c].governance_blocked)
    for cid in cands.loc[blocked, "company_id"]:
        skipped.append({"company_id": cid, "reason": "governance flags"})
    cands = cands[~blocked]
    rejected = cands["company_id"].map(lambda c: c in notes and notes[c].status in ("rejected", "sold"))
    for cid in cands.loc[rejected, "company_id"]:
        skipped.append({"company_id": cid, "reason": f"research status: {notes[cid].status}"})
    cands = cands[~rejected]

    # Existing holdings first if they still meet the sell rule.
    if prev is not None and len(prev):
        keep = cands["company_id"].isin(prev.index) & (cands["rank_pct"] <= p.sell_rank_pct)
        order = pd.concat([cands[keep], cands[~keep & ~cands["company_id"].isin(prev.index)]])
    else:
        order = cands

    third = max(p.target_holdings // 3, 1)
    liq_cap = order["adv_usd"] * p.adv_days * p.adv_participation / p.aum_usd

    rows, sec_w, cty_w, off_w = [], {}, {}, 0.0
    for pos, (_, r) in enumerate(order.iterrows()):
        if len(rows) >= p.target_holdings:
            break
        cid = r["company_id"]
        note = notes.get(cid)
        conviction = (note.conviction if note and note.conviction
                      else "high" if pos < third else "medium" if pos < 2 * third else "low")
        cap = min(p.max_position, liq_cap.loc[r.name])
        w = min(p.conviction_weights[conviction], cap)
        room_s = sector_bw.get(r["sector"], 0) + p.sector_band - sec_w.get(r["sector"], 0)
        room_c = _country_cap(r["country"], country_bw.get(r["country"], 0), p) - cty_w.get(r["country"], 0)
        room_o = p.off_benchmark_max - off_w if not r["in_benchmark"] else 1.0
        w = min(w, room_s, room_c, room_o)
        if w < MIN_WEIGHT:
            why = ("liquidity" if cap < MIN_WEIGHT else "sector band" if room_s < MIN_WEIGHT
                   else "country band" if room_c < MIN_WEIGHT else "off-benchmark limit")
            skipped.append({"company_id": cid, "reason": why})
            continue
        rows.append({"company_id": cid, "conviction": conviction, "weight": w, "cap": cap,
                     "conviction_source": "note" if note and note.conviction else "rank"})
        sec_w[r["sector"]] = sec_w.get(r["sector"], 0) + w
        cty_w[r["country"]] = cty_w.get(r["country"], 0) + w
        if not r["in_benchmark"]:
            off_w += w

    h = pd.DataFrame(rows, columns=["company_id", "conviction", "weight", "cap", "conviction_source"])
    if h.empty:
        return Portfolio(screen.as_of, h, [], {"sector": [], "country": []}, [], skipped)
    h = h.merge(f, on="company_id", how="left")
    h["target_weight"] = _scale(h, sector_bw, country_bw, p)
    h["weight"] = h["target_weight"]
    if prev is not None and len(prev):
        # Trade on thesis change, not on drift: a retained name within the band keeps its weight.
        held = h["company_id"].map(prev).fillna(0.0)
        hold = (held > 0) & ((h["target_weight"] - held).abs() < p.trade_band) & (held <= h["cap"])
        h.loc[hold, "weight"] = held[hold]
        if h["weight"].sum() > 1:
            h["weight"] *= 1 / h["weight"].sum()
    h["new"] = ~h["company_id"].isin(prev.index) if prev is not None else True
    h["days_to_trade"] = h["weight"] * p.aum_usd / (h["adv_usd"] * p.adv_participation)
    h = h.sort_values("weight", ascending=False).reset_index(drop=True)

    exposures = {
        "sector": _exposure(h, bench, "sector", sector_bw, lambda k, bw: (bw - p.sector_band, bw + p.sector_band)),
        "country": _exposure(h, bench, "country", country_bw,
                             lambda k, bw: (bw - (p.country_band_large if k in p.large_countries else p.country_band),
                                            _country_cap(k, bw, p))),
    }
    return Portfolio(screen.as_of, h, _checks(h, exposures, p), exposures,
                     _characteristics(h, bench), skipped)


def _scale(h: pd.DataFrame, sector_bw, country_bw, p: PortfolioParams) -> pd.Series:
    """Scale weights toward 1 - (small cash buffer) while respecting every cap."""
    target = 1.0 - min(0.01, p.max_cash)
    w = h["weight"].to_numpy(dtype=float).copy()
    cap = h["cap"].to_numpy(dtype=float).copy()
    sec, cty = h["sector"].to_numpy(), h["country"].to_numpy()
    off = ~h["in_benchmark"].to_numpy(dtype=bool)
    for _ in range(50):
        free = w < cap - 1e-9
        gap = target - w.sum()
        if abs(gap) < 1e-6 or (gap > 0 and not free.any()):
            break
        base = w[free].sum() if gap > 0 else w.sum()
        if base <= 0:
            break
        if gap > 0:
            w[free] *= 1 + gap / base
        else:
            w *= target / w.sum()
        w = np.minimum(w, cap)
        for keys, bw_map, cap_fn in ((sec, sector_bw, lambda k: sector_bw.get(k, 0) + p.sector_band),
                                     (cty, country_bw, lambda k: _country_cap(k, country_bw.get(k, 0), p))):
            for k in np.unique(keys):
                m = keys == k
                limit = cap_fn(k)
                if w[m].sum() > limit:
                    w[m] *= limit / w[m].sum()
                    cap[m] = np.minimum(cap[m], w[m])  # freeze this group
        if w[off].sum() > p.off_benchmark_max:
            w[off] *= p.off_benchmark_max / w[off].sum()
            cap[off] = np.minimum(cap[off], w[off])
    return pd.Series(w, index=h.index)


def _exposure(h, bench, col, bw_map, band_fn) -> list[dict]:
    pw = h.groupby(col)["weight"].sum()
    keys = sorted(set(pw.index) | set(bw_map.index), key=lambda k: -max(pw.get(k, 0), bw_map.get(k, 0)))
    out = []
    for k in keys:
        bw, w = float(bw_map.get(k, 0)), float(pw.get(k, 0))
        lo, hi = band_fn(k, bw)
        out.append({"name": k, "portfolio": w, "benchmark": bw, "active": w - bw,
                    "min": max(lo, 0.0), "max": hi, "within": (w <= hi + 1e-9), "below_floor": w < lo - 1e-9})
    return out


def _checks(h: pd.DataFrame, exposures, p: PortfolioParams) -> list[dict]:
    n, cash = len(h), 1 - h["weight"].sum()
    off = h.loc[~h["in_benchmark"].astype(bool), "weight"].sum()
    sec_ok = all(e["within"] for e in exposures["sector"])
    cty_ok = all(e["within"] for e in exposures["country"])
    floors = [e["name"] for e in exposures["sector"] + exposures["country"] if e["below_floor"]]
    return [
        {"rule": "Holdings", "limit": f"{p.min_holdings}–{p.max_holdings}", "actual": n,
         "pass": p.min_holdings <= n <= p.max_holdings},
        {"rule": "Max position", "limit": f"{p.max_position:.1%}", "actual": f"{h['weight'].max():.2%}",
         "pass": h["weight"].max() <= p.max_position + 1e-9},
        {"rule": "Cash", "limit": f"≤ {p.max_cash:.0%}", "actual": f"{cash:.2%}", "pass": cash <= p.max_cash + 1e-9},
        {"rule": "Sector weight", "limit": f"≤ benchmark + {p.sector_band:.0%}", "actual": "within" if sec_ok else "breach",
         "pass": sec_ok},
        {"rule": "Country weight", "limit": f"≤ benchmark + {p.country_band:.0%} (US/Japan {p.country_band_large:.0%})",
         "actual": "within" if cty_ok else "breach", "pass": cty_ok},
        {"rule": "Benchmark floors", "limit": "≥ benchmark − band (reported)",
         "actual": ", ".join(floors) if floors else "all met", "pass": not floors, "advisory": True},
        {"rule": "Liquidity", "limit": f"≤ {p.adv_days:g} days at {p.adv_participation:.0%} of ADV",
         "actual": f"max {h['days_to_trade'].max():.1f} days", "pass": h["days_to_trade"].max() <= p.adv_days + 1e-6},
        {"rule": "Off-benchmark", "limit": f"≤ {p.off_benchmark_max:.0%}", "actual": f"{off:.2%}",
         "pass": off <= p.off_benchmark_max + 1e-9},
    ]


CHAR_METRICS = [
    ("roe_median", "ROE (5y median)", "higher"),
    ("fcf_conversion", "FCF conversion", "higher"),
    ("leverage", "Net debt / EBITDA", "lower"),
    ("earnings_yield", "Earnings yield", "higher"),
    ("fcf_yield", "FCF yield", "higher"),
    ("dilution", "Dilution (3y CAGR)", "lower"),
    ("accruals", "Accruals", "lower"),
]


def _wmedian(x: pd.Series, w: pd.Series) -> float:
    m = x.notna() & np.isfinite(x)
    x, w = x[m].to_numpy(), w[m].to_numpy()
    if len(x) == 0:
        return float("nan")
    o = np.argsort(x)
    cw = np.cumsum(w[o]) / w.sum()
    return float(x[o][np.searchsorted(cw, 0.5)])


def _characteristics(h: pd.DataFrame, bench: pd.DataFrame) -> list[dict]:
    """Weighted medians: the spec's 'higher ROE, higher FCF conversion, lower leverage' check."""
    out = []
    for col, label, better in CHAR_METRICS:
        pv, bv = _wmedian(h[col], h["weight"]), _wmedian(bench[col], bench["bench_weight"])
        ok = (pv > bv) if better == "higher" else (pv < bv)
        out.append({"metric": col, "label": label, "portfolio": pv, "benchmark": bv,
                    "better": better, "pass": bool(ok)})
    return out
