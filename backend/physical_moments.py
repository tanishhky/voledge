"""
Physical (P-measure) return moments and the risk-premium spread.

This is the *other half* of the BKM engine. `bkm_engine.py` extracts the
risk-neutral (Q-measure) distribution implied by option prices; this module
estimates the physical (P-measure) distribution that actually realized in the
underlying. The gap between them — Q minus P — is the risk premium:

    variance risk premium = RN variance  - realized variance
    skew     risk premium = RN skewness  - realized skewness
    kurtosis risk premium = RN kurtosis  - realized kurtosis

A persistently positive variance premium means options are pricing more
variance than tends to realize (the classic short-vol carry). A more negative
RN skew than physical skew means the market is paying up for crash protection
beyond what the underlying has historically delivered.

Horizons are matched to the BKM target DTE so the two distributions describe
the same forecast horizon: skew/kurtosis are computed on overlapping
`horizon`-day log returns, not on 1-day returns (those moments are
horizon-dependent and would not be comparable to the option-implied tenor).
"""
from __future__ import annotations

import numpy as np
from scipy import stats
from typing import List, Optional, Dict, Any

from models import Candle
from volatility_engine import _periods_per_year, _candles_per_day


# Calendar -> trading-day conversion. BKM target_dte is in calendar days;
# realized returns live on the trading-day grid.
_TRADING_DAYS_PER_CALENDAR_DAY = 252.0 / 365.0


def compute_physical_moments(
    candles: List[Candle],
    target_dte: int,
    timeframe: str = "1day",
    asset_class: str = "stocks",
    lookback_days: int = 252,
) -> Optional[Dict[str, Any]]:
    """
    Estimate the physical return distribution over a `target_dte`-calendar-day
    horizon, matched to a BKM risk-neutral tenor.

    Returns a dict with:
      phys_volatility  — annualized realized vol (close-to-close, lookback window)
      phys_variance    — annualized realized variance (phys_volatility ** 2)
      phys_skewness    — skewness of overlapping horizon log returns
      phys_kurtosis    — excess kurtosis of overlapping horizon log returns
      horizon_candles  — return horizon in candles
      n_returns        — number of overlapping horizon returns used
      lookback_candles — daily-return sample used for the vol estimate
    Returns None if there is not enough data.
    """
    if target_dte <= 0 or len(candles) < 5:
        return None

    closes = np.array([c.close for c in candles], dtype=float)
    if np.any(closes <= 0):
        return None

    ann = _periods_per_year(timeframe, asset_class)
    cpd = _candles_per_day(timeframe, asset_class)

    # ── Annualized realized volatility from daily-grid log returns ──
    log_returns = np.diff(np.log(closes))
    lookback_candles = max(20, int(round(lookback_days * cpd)))
    rv_sample = log_returns[-lookback_candles:] if len(log_returns) > lookback_candles else log_returns
    if len(rv_sample) < 5:
        return None
    phys_vol = float(np.std(rv_sample, ddof=1) * np.sqrt(ann))

    # ── Horizon-matched overlapping log returns for skew / kurtosis ──
    horizon = max(1, int(round(target_dte * _TRADING_DAYS_PER_CALENDAR_DAY * cpd)))
    if len(closes) <= horizon + 5:
        # Not enough history for the requested horizon; skew/kurt unavailable.
        return {
            "phys_volatility": round(phys_vol, 6),
            "phys_variance": round(phys_vol ** 2, 8),
            "phys_skewness": None,
            "phys_kurtosis": None,
            "horizon_candles": horizon,
            "n_returns": 0,
            "lookback_candles": int(len(rv_sample)),
            "target_dte": target_dte,
        }

    horizon_returns = np.log(closes[horizon:] / closes[:-horizon])
    # Keep the horizon-return sample on the same lookback window.
    horizon_returns = horizon_returns[-lookback_candles:] if len(horizon_returns) > lookback_candles else horizon_returns

    phys_skew = float(stats.skew(horizon_returns, bias=False))
    phys_kurt = float(stats.kurtosis(horizon_returns, fisher=True, bias=False))  # excess

    return {
        "phys_volatility": round(phys_vol, 6),
        "phys_variance": round(phys_vol ** 2, 8),
        "phys_skewness": round(phys_skew, 6),
        "phys_kurtosis": round(phys_kurt, 6),
        "horizon_candles": horizon,
        "n_returns": int(len(horizon_returns)),
        "lookback_candles": int(len(rv_sample)),
        "target_dte": target_dte,
    }


def compute_risk_premium(
    rn_bkm: Optional[Dict[str, Any]],
    phys: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    """
    The headline of the platform: Q minus P.

    Pairs a BKM risk-neutral moment dict (from `compute_bkm_moments`) with a
    physical moment dict (from `compute_physical_moments`) at the same tenor and
    returns the spread for each moment, plus a plain-English read of the
    variance and skew premia.
    """
    if not rn_bkm or not phys:
        return None

    rn_vol = rn_bkm.get("rn_volatility")
    rn_skew = rn_bkm.get("rn_skewness")
    rn_kurt = rn_bkm.get("rn_kurtosis")
    p_vol = phys.get("phys_volatility")
    p_skew = phys.get("phys_skewness")
    p_kurt = phys.get("phys_kurtosis")

    def _spread(a, b):
        return round(float(a - b), 6) if (a is not None and b is not None) else None

    variance_premium = (
        round(float(rn_vol ** 2 - p_vol ** 2), 8)
        if (rn_vol is not None and p_vol is not None) else None
    )
    vol_premium = _spread(rn_vol, p_vol)
    skew_premium = _spread(rn_skew, p_skew)
    kurt_premium = _spread(rn_kurt, p_kurt)

    # ── Plain-English interpretation (the "so what") ──
    reads: List[str] = []
    if vol_premium is not None:
        if vol_premium > 0.01:
            reads.append(
                f"Options price {vol_premium * 100:.1f} vol-pts more variance than "
                "realized — variance risk premium is rich; carry favors selling premium."
            )
        elif vol_premium < -0.01:
            reads.append(
                f"Options price {abs(vol_premium) * 100:.1f} vol-pts less variance than "
                "realized — IV is cheap vs realized; carry favors owning premium."
            )
        else:
            reads.append("IV and realized variance are roughly in line — no clear variance carry.")
    if skew_premium is not None:
        if skew_premium < -0.1:
            reads.append(
                "Risk-neutral skew is more negative than physical — the market is paying "
                "up for downside protection beyond what has realized (rich put skew)."
            )
        elif skew_premium > 0.1:
            reads.append(
                "Risk-neutral skew sits above physical — downside is comparatively "
                "underpriced relative to history."
            )

    return {
        "variance_premium": variance_premium,
        "vol_premium": vol_premium,
        "skew_premium": skew_premium,
        "kurt_premium": kurt_premium,
        "rn_volatility": rn_vol,
        "rn_skewness": rn_skew,
        "rn_kurtosis": rn_kurt,
        "phys_volatility": p_vol,
        "phys_skewness": p_skew,
        "phys_kurtosis": p_kurt,
        "target_dte": rn_bkm.get("target_dte") or phys.get("target_dte"),
        "interpretation": " ".join(reads) if reads else None,
    }
