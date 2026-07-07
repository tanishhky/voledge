"""Generate the figures for paper/paper_voledge.tex (paper/fig/*.png).

Re-runs the two validated built-in strategies through the SAME walk-forward
engine the app uses (StrategyRunner, zero look-ahead, net of modeled costs)
on live Yahoo data, and renders the BKM closed-form convergence study.

Run from the repo root:  backend/venv/bin/python scripts/make_paper_figures.py

Figures:
  fig/garch_volmanaged.png   equity curve vs SPY buy-and-hold (2020-2024)
  fig/vix_vrp.png            naive VRP harvest vs SPY (2019-2024)
  fig/bkm_validation.png     BKM recovers BS sigma as wings/grid widen
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
OUT = ROOT / "paper" / "fig"
OUT.mkdir(parents=True, exist_ok=True)

plt.rcParams.update({"figure.dpi": 150, "font.size": 9,
                     "axes.grid": True, "grid.alpha": 0.3})

from strategy_engine import (STRATEGY_TEMPLATES, StrategyDefinition,
                             StrategyConfig, StrategyRunner)


def _run_template(template_id: str, start: str, end: str) -> dict:
    tmpl = STRATEGY_TEMPLATES[template_id]
    defn = StrategyDefinition(
        name=tmpl["name"],
        tickers=tmpl["default_tickers"],
        benchmark="SPY",
        config=StrategyConfig(**tmpl["default_config"]),
        regime_code=tmpl["code"],
    )
    runner = StrategyRunner(defn)
    result = runner.run(start_date=start, end_date=end)
    m = result["metrics"]
    print(f"{template_id}: sharpe={m.get('sharpe')} "
          f"maxdd={m.get('max_drawdown')} ret={m.get('total_return')}")
    return result


def _equity_fig(result: dict, title: str, fname: str,
                strat_label: str) -> None:
    log = pd.DataFrame(result["daily_log"])
    log["date"] = pd.to_datetime(log["date"])
    log = log.dropna(subset=["benchmark_value"])
    strat = log["portfolio_value"] / log["portfolio_value"].iloc[0]
    bench = log["benchmark_value"] / log["benchmark_value"].iloc[0]
    fig, ax = plt.subplots(figsize=(6.8, 3.2))
    ax.plot(log["date"], strat, lw=1.5, color="#1f4e8c", label=strat_label)
    ax.plot(log["date"], bench, lw=1.2, color="#888888", ls="--",
            label="SPY buy-and-hold")
    ax.set_ylabel("growth of $1")
    ax.set_title(title)
    ax.legend(frameon=False, loc="upper left")
    fig.tight_layout()
    fig.savefig(OUT / fname)
    plt.close(fig)


# ── BKM closed-form convergence ──────────────────────────────────────────

def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _bs_price(kind: str, S: float, K: float, r: float, sigma: float,
              T: float) -> float:
    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    if kind == "call":
        return S * _norm_cdf(d1) - K * math.exp(-r * T) * _norm_cdf(d2)
    return K * math.exp(-r * T) * _norm_cdf(-d2) - S * _norm_cdf(-d1)


def _bkm_fig() -> None:
    from bkm_engine import compute_bkm_moments
    from models import OptionContract, OptionContractWithGreeks

    S, r, sigma, dte = 100.0, 0.04, 0.20, 30
    T = dte / 365.0

    def chain(width: float, step: float) -> list:
        out = []
        k = max(S - width, 1.0)   # strikes must stay positive
        while k <= S + width + 1e-9:
            for kind in ("call", "put"):
                out.append(OptionContractWithGreeks(
                    contract=OptionContract(
                        ticker=f"S{kind[0]}{k:.1f}", underlying_ticker="SYN",
                        contract_type=kind, strike_price=round(k, 4),
                        expiration_date="2099-01-01"),
                    mid_price=_bs_price(kind, S, k, r, sigma, T),
                    implied_volatility=sigma, days_to_expiry=dte))
            k += step
        return out

    widths = [10, 20, 30, 50, 80, 120]
    vols = []
    for w in widths:
        m = compute_bkm_moments(chain(w, 0.25), spot=S, r=r, target_dte=dte)
        vols.append(m["rn_volatility"] if m else float("nan"))

    fig, ax = plt.subplots(figsize=(5.2, 3.2))
    ax.plot(widths, vols, "o-", color="#1f4e8c", lw=1.4,
            label="BKM recovered volatility")
    ax.axhline(sigma, color="#b22222", ls="--", lw=1.0,
               label="Black-Scholes truth (20%)")
    ax.set_xlabel("strike coverage: spot $\\pm$ width ($)")
    ax.set_ylabel("annualized volatility")
    ax.set_title("BKM extractor converges to closed-form truth as wings widen")
    ax.legend(frameon=False)
    fig.tight_layout()
    fig.savefig(OUT / "bkm_validation.png")
    plt.close(fig)
    print("bkm_validation:", [round(v, 4) for v in vols])


def main() -> None:
    _bkm_fig()
    # Fetch from 2019 so the 252-day training burn-in ends BEFORE Feb 2020:
    # the paper's evaluation window is 2020-2024 INCLUDING the COVID crash.
    # Starting the fetch at 2020-01-01 silently burns all of 2020 as
    # training and reports a crash-free window (Sharpe 0.93 on 2021-2024),
    # which is not the table's claim.
    g = _run_template("garch_volmanaged", "2019-01-01", "2024-12-31")
    _equity_fig(g, "GARCH vol-managed SPY vs buy-and-hold (walk-forward, net of costs)",
                "garch_volmanaged.png", "GARCH vol-target 15% (SPY/BIL)")
    v = _run_template("vix_vrp", "2019-01-01", "2024-12-31")
    _equity_fig(v, "Naive variance-premium harvest vs SPY (walk-forward, net of costs)",
                "vix_vrp.png", "VRP harvest (SVXY/TLT)")
    print(f"figures written to {OUT}")


if __name__ == "__main__":
    main()
