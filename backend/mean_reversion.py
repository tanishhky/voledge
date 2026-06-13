"""
Mean-reversion diagnostics.

Visual, descriptive diagnostics that answer one question for any metric:
"Is this series mean-reverting, and how fast?" Three standard, independent
estimators are reported so they corroborate (or contradict) each other:

  * OU half-life  — from the AR(1) speed of reversion. Discrete OU:
        y_t = c + phi * y_{t-1} + e,   phi = exp(-theta * dt)
    Half-life = ln(2) / theta = -ln(2) / ln(phi).  Small half-life => fast
    reversion; if phi >= 1 the series is not reverting (random walk / trending).

  * ADF-style t-stat — t-statistic on the lagged-level coefficient of the
    delta regression (Dickey-Fuller without augmentation). More negative =
    stronger statistical evidence against a unit root (i.e. mean-reverting).

  * Hurst exponent — H < 0.5 mean-reverting, ~0.5 random walk, > 0.5 trending.
    Estimated from the scaling of the std of lagged differences.

A *rolling* half-life series is also produced so the "is the rate of reversion
converging?" question is answerable by eye.

These are deliberately model-light and meant for visualization, not for
generating trade signals on their own.
"""
from __future__ import annotations

import numpy as np
from typing import List, Optional, Dict, Any

from models import Candle
from volatility_engine import _periods_per_year


def _ols_with_tstat(x: np.ndarray, y: np.ndarray) -> Optional[Dict[str, float]]:
    """Simple OLS y = a + b*x. Returns slope b, intercept a, and t-stat of b."""
    n = len(x)
    if n < 5:
        return None
    X = np.column_stack([np.ones(n), x])
    try:
        beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    except np.linalg.LinAlgError:
        return None
    resid = y - X @ beta
    dof = n - 2
    if dof <= 0:
        return None
    sigma2 = float(resid @ resid) / dof
    xtx_inv = np.linalg.pinv(X.T @ X)
    se_b = float(np.sqrt(max(sigma2 * xtx_inv[1, 1], 1e-30)))
    t_stat = float(beta[1] / se_b) if se_b > 0 else 0.0
    return {"intercept": float(beta[0]), "slope": float(beta[1]), "t_stat": t_stat}


def ou_half_life(series: np.ndarray) -> Optional[float]:
    """Half-life of mean reversion from the AR(1) delta regression."""
    series = np.asarray(series, dtype=float)
    if len(series) < 10:
        return None
    y_lag = series[:-1]
    dy = np.diff(series)
    fit = _ols_with_tstat(y_lag, dy)
    if not fit:
        return None
    b = fit["slope"]
    phi = 1.0 + b
    if phi <= 0 or phi >= 1:
        # Not reverting (or degenerate): no finite, meaningful half-life.
        return None
    hl = -np.log(2.0) / np.log(phi)
    if hl <= 0 or not np.isfinite(hl):
        return None
    return float(hl)


def adf_tstat(series: np.ndarray) -> Optional[float]:
    """Dickey-Fuller-style t-statistic on the lagged level (no augmentation)."""
    series = np.asarray(series, dtype=float)
    if len(series) < 10:
        return None
    fit = _ols_with_tstat(series[:-1], np.diff(series))
    return fit["t_stat"] if fit else None


def hurst_exponent(series: np.ndarray, max_lag: int = 40) -> Optional[float]:
    """Hurst exponent via the scaling of the std of lagged differences."""
    series = np.asarray(series, dtype=float)
    n = len(series)
    if n < 30:
        return None
    max_lag = min(max_lag, n // 2)
    lags = range(2, max_lag)
    tau = []
    valid_lags = []
    for lag in lags:
        diff = series[lag:] - series[:-lag]
        sd = np.std(diff)
        if sd > 0:
            tau.append(sd)
            valid_lags.append(lag)
    if len(valid_lags) < 4:
        return None
    poly = np.polyfit(np.log(valid_lags), np.log(tau), 1)
    return float(poly[0])


def _rolling_half_life(series: np.ndarray, window: int, step: int) -> Dict[str, List]:
    """Compute half-life on a sliding window — the 'is reversion converging?' view."""
    idxs: List[int] = []
    hls: List[Optional[float]] = []
    n = len(series)
    if n < window:
        return {"index": [], "half_life": []}
    for start in range(0, n - window + 1, step):
        win = series[start:start + window]
        hl = ou_half_life(win)
        idxs.append(start + window - 1)  # right edge of the window
        hls.append(round(hl, 3) if hl is not None else None)
    return {"index": idxs, "half_life": hls}


def _downsample(values: np.ndarray, max_points: int = 600) -> np.ndarray:
    """Uniformly downsample for plotting without distorting shape."""
    n = len(values)
    if n <= max_points:
        return values
    idx = np.linspace(0, n - 1, max_points).astype(int)
    return values[idx]


def analyze_series(
    values: np.ndarray,
    timestamps: List[int],
    label: str,
    rolling_window: int,
    rolling_step: int,
) -> Dict[str, Any]:
    """Full diagnostic bundle for one metric, ready for the frontend."""
    values = np.asarray(values, dtype=float)
    mask = np.isfinite(values)
    values = values[mask]
    ts = list(np.asarray(timestamps)[mask]) if len(timestamps) == len(mask) else list(range(len(values)))

    n = len(values)
    out: Dict[str, Any] = {"label": label, "n": int(n)}
    if n < 30:
        out["error"] = "insufficient data"
        return out

    mean = float(np.mean(values))
    std = float(np.std(values, ddof=1))
    last = float(values[-1])

    hl = ou_half_life(values)
    t_stat = adf_tstat(values)
    hurst = hurst_exponent(values)

    # Verdict corroborates Hurst with the OU half-life: don't call something
    # mean-reverting if there is no finite, in-sample half-life (e.g. a trending
    # price can score a borderline Hurst < 0.5 yet have no real reversion).
    if hurst is None:
        verdict = "unknown"
    elif hurst < 0.45 and hl is not None and hl < n:
        verdict = "mean-reverting"
    elif hurst > 0.55:
        verdict = "trending"
    else:
        verdict = "random walk"

    rolling = _rolling_half_life(values, rolling_window, rolling_step)
    roll_ts = [ts[i] for i in rolling["index"]] if ts else rolling["index"]

    plot_vals = _downsample(values)
    plot_ts = _downsample(np.asarray(ts)) if ts else list(range(len(plot_vals)))

    return {
        "label": label,
        "n": int(n),
        "mean": round(mean, 6),
        "std": round(std, 6),
        "last": round(last, 6),
        "z_score": round((last - mean) / std, 4) if std > 0 else None,
        "half_life": round(hl, 3) if hl is not None else None,
        "adf_tstat": round(t_stat, 4) if t_stat is not None else None,
        "hurst": round(hurst, 4) if hurst is not None else None,
        "verdict": verdict,
        "series": {
            "timestamps": [int(t) for t in plot_ts],
            "values": [round(float(v), 6) for v in plot_vals],
        },
        "rolling_half_life": {
            "timestamps": [int(t) for t in roll_ts],
            "values": rolling["half_life"],
        },
    }


def _realized_vol_series(
    candles: List[Candle], window: int, timeframe: str, asset_class: str
) -> tuple[np.ndarray, List[int]]:
    """Trailing annualized realized-vol series aligned to candle timestamps."""
    closes = np.array([c.close for c in candles], dtype=float)
    ts = [c.timestamp for c in candles]
    log_ret = np.diff(np.log(closes))
    ann = np.sqrt(_periods_per_year(timeframe, asset_class))
    vols: List[float] = []
    vol_ts: List[int] = []
    for i in range(window, len(log_ret) + 1):
        w = log_ret[i - window:i]
        vols.append(float(np.std(w, ddof=1) * ann))
        vol_ts.append(ts[i])  # +1 offset from diff, aligns to candle close
    return np.array(vols), vol_ts


def mean_reversion_analysis(
    candles: List[Candle],
    timeframe: str = "1day",
    asset_class: str = "stocks",
    vol_window: int = 20,
    rolling_window: int = 90,
    rolling_step: int = 5,
) -> Dict[str, Any]:
    """
    Run mean-reversion diagnostics on price, log-price, and realized volatility.

    Returns { metrics: { price: {...}, log_price: {...}, realized_vol: {...} },
              meta: {...} }.
    """
    if len(candles) < 30:
        return {"error": "Need at least 30 candles for mean-reversion analysis.", "metrics": {}}

    closes = np.array([c.close for c in candles], dtype=float)
    ts = [c.timestamp for c in candles]

    rolling_window = min(rolling_window, max(30, len(closes) // 2))

    metrics: Dict[str, Any] = {}
    metrics["price"] = analyze_series(closes, ts, "Price", rolling_window, rolling_step)
    metrics["log_price"] = analyze_series(
        np.log(closes), ts, "Log Price", rolling_window, rolling_step
    )

    if len(closes) > vol_window + 30:
        vol_series, vol_ts = _realized_vol_series(candles, vol_window, timeframe, asset_class)
        rw_vol = min(rolling_window, max(30, len(vol_series) // 2))
        metrics["realized_vol"] = analyze_series(
            vol_series, vol_ts, f"Realized Vol ({vol_window}p, annualized)", rw_vol, rolling_step
        )
    else:
        metrics["realized_vol"] = {"label": "Realized Vol", "error": "insufficient data", "n": 0}

    return {
        "metrics": metrics,
        "meta": {
            "n_candles": len(candles),
            "timeframe": timeframe,
            "asset_class": asset_class,
            "vol_window": vol_window,
            "rolling_window": rolling_window,
        },
    }
