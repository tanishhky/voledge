# VolEdge — 90-Second Demo Script

For the screen-recorded walkthrough (owed to Alex Shirokov; reusable for any
recruiter link). Goal: prove the thesis end-to-end in 90 seconds. Record at
1080p, dark theme, no audio cuts.

## Setup before recording
- Backend + frontend running (`backend: uvicorn main:app`; `frontend: npm run dev`).
- A ticker pre-loaded if you have a Polygon options key (e.g. SPY); otherwise run
  the **backtest-only** variant below (no key needed).
- Tabs to use, in order: **PRICE → REVERSION → SURFACE/PREMIUM → STRATEGY → RESULTS**.

## The 90 seconds (with key — full thesis)

| Time | On screen | Say (one line) |
|---|---|---|
| 0:00–0:10 | EQUITY ▸ PRICE tab, candles + GMM distribution | "VolEdge models the *underlying's* realized distribution…" |
| 0:10–0:20 | EQUITY ▸ REVERSION, half-life + Hurst | "…with mean-reversion diagnostics — OU half-life, Hurst, Dickey-Fuller." |
| 0:20–0:35 | OPTIONS ▸ SURFACE then BKM | "…then the *option-implied* distribution: model-free BKM risk-neutral moments, validated against Black-Scholes." |
| 0:35–0:55 | OPTIONS ▸ **PREMIUM** (the headline) | "The gap between them — risk-neutral minus realized — *is* the risk premium. Orange is what options price, cyan is what realizes; the spread is the read." |
| 0:55–1:15 | BACKTEST ▸ STRATEGY → run `garch_volmanaged` | "And I trade it: GARCH vol-targeting, walk-forward, zero look-ahead." |
| 1:15–1:30 | BACKTEST ▸ RESULTS tearsheet | "Sharpe 0.85 vs SPY's 0.68 at 41% lower drawdown. The premium is real — and I show harvesting it naively *loses money*, which is why it exists." |

## Backtest-only variant (NO API key)
If you don't have a Polygon options key, skip SURFACE/BKM/PREMIUM live and lead
with the engineering + results:
1. STRATEGY → run `garch_volmanaged` (SPY/BIL) → RESULTS tearsheet (Sharpe 0.85).
2. STRATEGY → run `vix_vrp` → RESULTS (the −15% "premium is crash-comp" finding).
3. Cut to a still of the PREMIUM tab populated from a saved cache to show the
   measurement layer.

## The one-paragraph caption (for the link)
> VolEdge measures the variance/skew **risk premium** — model-free option-implied
> (BKM) moments vs horizon-matched realized moments — and backtests strategies
> that trade it through a no-look-ahead walk-forward engine. A GARCH vol-targeted
> strategy beat SPY risk-adjusted (Sharpe 0.85 vs 0.68) at 41% lower drawdown;
> a naive variance-premium harvest lost money, empirically confirming the premium
> as crash-risk compensation. FastAPI/React, ~6k LOC, all analytics computed
> locally.

## Hard rules
- Never claim a number that isn't in `README.md`'s Results table.
- If BKM looks off on a real chain, it's strike coverage — say so, don't spin it.
- Lead with GARCH (the win); frame VRP as the *finding*, not a failure.
