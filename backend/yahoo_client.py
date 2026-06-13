"""Yahoo Finance adapter (via yfinance) — key-free data source.

Ported from the PinSight reference implementation (`pinsight/data/yahoo.py`).
Free, no API key, but scrappy: quotes are ~15-min delayed, intraday history is
range-limited, and the library breaks when Yahoo changes its JSON. Used as
VolEdge's default when no Polygon key is supplied.

Both functions return data in the SAME shapes the Polygon path produces, so the
rest of the `/volatility` pipeline (enrich → IV/greeks → BKM → premium) and the
cache/reprocess flow are reused unchanged:
  - candles  -> List[Candle]
  - chain    -> (List[OptionContract], {contract_ticker: {"close", "volume"}})
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import List, Tuple, Dict, Optional

import pandas as pd
import yfinance as yf

from models import Candle, OptionContract


# VolEdge timeframe -> yfinance interval. 4hour has no native yfinance interval;
# fall back to hourly. Note yfinance caps intraday history (e.g. 1m ~ last 7d).
_YF_INTERVAL = {
    "1min": "1m", "5min": "5m", "15min": "15m", "30min": "30m",
    "1hour": "60m", "4hour": "1h", "1day": "1d", "1week": "1wk",
}


def _yahoo_symbol(ticker: str, asset_class: str) -> str:
    """Map a VolEdge/Polygon-style ticker to a Yahoo symbol."""
    t = ticker.upper().strip()
    if asset_class == "crypto":
        t = t[2:] if t.startswith("X:") else t
        if "-" not in t and t.endswith("USD"):
            t = t[:-3] + "-USD"
        return t
    if asset_class == "forex":
        t = t[2:] if t.startswith("C:") else t
        return t if t.endswith("=X") else f"{t}=X"
    return t  # stocks/ETFs


def _f(v) -> Optional[float]:
    if v is None or pd.isna(v):
        return None
    f = float(v)
    return f if f != 0 else None


def fetch_candles_yahoo(
    ticker: str, asset_class: str, timeframe: str,
    start_date: str, end_date: str,
) -> List[Candle]:
    """OHLCV candles via yfinance, normalized to VolEdge's Candle schema."""
    interval = _YF_INTERVAL.get(timeframe, "1d")
    sym = _yahoo_symbol(ticker, asset_class)

    # yfinance's `end` is exclusive — nudge it forward a day so the last bar is included.
    try:
        end_inc = (date.fromisoformat(end_date) + timedelta(days=1)).isoformat()
    except Exception:
        end_inc = end_date

    df = yf.download(sym, start=start_date, end=end_inc, interval=interval,
                     progress=False, auto_adjust=False)
    if df is None or df.empty:
        return []

    # Single-ticker download can come back with a MultiIndex column header.
    if isinstance(df.columns, pd.MultiIndex):
        lvl1 = df.columns.get_level_values(-1)
        if sym in set(lvl1):
            df = df.xs(sym, axis=1, level=-1)
        else:
            df = df.droplevel(-1, axis=1)
    df = df.dropna(subset=["Open", "High", "Low", "Close"])

    candles: List[Candle] = []
    for ts, r in df.iterrows():
        try:
            t_ms = int(pd.Timestamp(ts).timestamp() * 1000)
        except Exception:
            continue
        try:
            candles.append(Candle(
                timestamp=t_ms,
                open=float(r["Open"]), high=float(r["High"]),
                low=float(r["Low"]), close=float(r["Close"]),
                volume=float(r["Volume"]) if pd.notna(r.get("Volume")) else 0.0,
                vwap=None,
            ))
        except Exception:
            continue
    return candles


def fetch_option_chain_yahoo(
    underlying: str,
    strike_lo: float,
    strike_hi: float,
    today: date,
    target_dtes: Tuple[int, ...] = (30, 60),
    include_nearest: bool = True,
    max_dte: int = 80,
) -> Tuple[List[OptionContract], Dict[str, dict]]:
    """Pull OTM+ITM option contracts for the expiries closest to each target DTE.

    Crucial detail: liquid underlyings (e.g. SPY) have many near-term (daily /
    weekly) expiries, so naively taking the first N expiries yields only 0–20 DTE
    and BKM never sees the 30d / 60d tenors. Instead we pick the single expiry
    nearest each `target_dte` (plus the nearest expiry overall for the near-term
    surface), which lands within a few days of the targets thanks to weekly
    expiries — well inside BKM's DTE tolerance.

    Returns (contracts, bars) where `bars[contract_ticker] = {"close": mid,
    "volume": v}` — mirroring the Polygon `cached_bars` shape so `enrich_contract`
    and the reprocess path are reused verbatim. `close` is the mid (from bid/ask)
    or last price when a two-sided quote is missing.
    """
    tk = yf.Ticker(underlying.upper())
    try:
        expiries = list(tk.options)
    except Exception:
        expiries = []

    # Map each available expiry to its DTE; keep only future ones within range.
    dated = []
    for e in expiries:
        try:
            d = (date.fromisoformat(e) - today).days
        except Exception:
            continue
        if 0 <= d <= max_dte:
            dated.append((e, d))

    chosen: set = set()
    if dated:
        if include_nearest:
            chosen.add(min(dated, key=lambda x: x[1])[0])
        for tgt in target_dtes:
            chosen.add(min(dated, key=lambda x: abs(x[1] - tgt))[0])
    chosen = sorted(chosen)

    contracts: List[OptionContract] = []
    bars: Dict[str, dict] = {}

    for exp in chosen:
        try:
            ch = tk.option_chain(exp)
        except Exception:
            continue
        for df, ctype in [(ch.calls, "call"), (ch.puts, "put")]:
            if df is None or df.empty:
                continue
            for _, r in df.iterrows():
                strike = _f(r.get("strike"))
                if not strike or strike < strike_lo or strike > strike_hi:
                    continue
                bid, ask, last = _f(r.get("bid")), _f(r.get("ask")), _f(r.get("lastPrice"))
                vol = _f(r.get("volume")) or 0.0
                # Liquidity guard: prefer a live two-sided quote; fall back to the
                # last trade only if it actually traded. Drops stale deep-OTM
                # strikes whose phantom prices wreck the BKM wing integrals.
                if bid and ask:
                    mid = (bid + ask) / 2.0
                elif last and vol > 0:
                    mid = last
                else:
                    continue
                if mid <= 0:
                    continue
                sym = r.get("contractSymbol") or f"O:{underlying.upper()}{exp}{ctype[0].upper()}{int(strike*1000):08d}"
                contracts.append(OptionContract(
                    ticker=sym,
                    underlying_ticker=underlying.upper(),
                    contract_type=ctype,
                    strike_price=float(strike),
                    expiration_date=exp,
                    shares_per_contract=100,
                ))
                bars[sym] = {"close": float(mid), "volume": float(vol)}

    return contracts, bars
