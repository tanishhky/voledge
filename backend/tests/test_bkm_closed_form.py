"""BKM engine must recover Black-Scholes closed-form truth.

Under Black-Scholes the log return ln(S_T/S) is normal, so the model-free
risk-neutral moments extracted from a dense BS-priced option chain have
known values:

    annualized volatility  -> sigma (the pricing vol)
    skewness               -> 0
    excess kurtosis        -> 0

This is the regression guard for the 2026-06-13 fix: the engine previously
carried a spurious 1/T and a doubled e^{rT}, inflating moments ~2.7x. Any
reintroduction of that class of bug fails these assertions immediately.
"""

from __future__ import annotations

import math

import pytest

from bkm_engine import compute_bkm_moments
from models import OptionContract, OptionContractWithGreeks


def _norm_cdf(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


def _bs_price(kind: str, S: float, K: float, r: float, sigma: float,
              T: float) -> float:
    d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    if kind == "call":
        return S * _norm_cdf(d1) - K * math.exp(-r * T) * _norm_cdf(d2)
    return K * math.exp(-r * T) * _norm_cdf(-d2) - S * _norm_cdf(-d1)


def _bs_chain(S: float, r: float, sigma: float, dte: int,
              k_lo: float, k_hi: float, step: float) -> list:
    """Dense synthetic chain priced exactly by Black-Scholes."""
    T = dte / 365.0
    chain = []
    k = k_lo
    while k <= k_hi + 1e-9:
        for kind in ("call", "put"):
            px = _bs_price(kind, S, k, r, sigma, T)
            chain.append(OptionContractWithGreeks(
                contract=OptionContract(
                    ticker=f"SYN{kind[0].upper()}{k:.1f}",
                    underlying_ticker="SYN",
                    contract_type=kind,
                    strike_price=round(k, 4),
                    expiration_date="2099-01-01",
                ),
                mid_price=px,
                implied_volatility=sigma,
                days_to_expiry=dte,
            ))
        k += step
    return chain


@pytest.mark.parametrize("sigma", [0.15, 0.25, 0.40])
def test_bkm_recovers_bs_volatility(sigma):
    S, r, dte = 100.0, 0.04, 30
    # Wide wings + fine grid so truncation/discretization error is small.
    # The estimator converges to sigma as the grid refines (integrand kink
    # at K=S dominates the error): step 0.5 -> -4.9%, 0.25 -> -2.5%,
    # 0.10 -> -1.0%, 0.05 -> -0.5% at sigma=0.15. Grid 0.10 keeps every
    # case inside the 2% assertion with real headroom.
    chain = _bs_chain(S, r, sigma, dte, k_lo=30.0, k_hi=250.0, step=0.10)
    m = compute_bkm_moments(chain, spot=S, r=r, target_dte=dte)
    assert m is not None
    assert m["rn_volatility"] == pytest.approx(sigma, rel=0.02), (
        f"BKM vol {m['rn_volatility']} vs BS sigma {sigma}")


def test_bkm_recovers_zero_skew_and_kurtosis():
    S, r, sigma, dte = 100.0, 0.04, 0.25, 30
    chain = _bs_chain(S, r, sigma, dte, k_lo=30.0, k_hi=250.0, step=0.25)
    m = compute_bkm_moments(chain, spot=S, r=r, target_dte=dte)
    assert m is not None
    # Log-returns are normal under BS: both higher moments are zero.
    assert abs(m["rn_skewness"]) < 0.15, m["rn_skewness"]
    assert abs(m["rn_kurtosis"]) < 0.30, m["rn_kurtosis"]


def test_bkm_magnitude_guard_against_scaling_bugs():
    """The pre-fix engine inflated variance ~2.7x. Assert the recovered
    vol is within a tight band, so ANY stray 1/T or e^{rT} factor (the
    smallest such error is e^{rT} ~ 1.003, but 1/T here is 12.2x) trips."""
    S, r, sigma, dte = 100.0, 0.04, 0.20, 30
    chain = _bs_chain(S, r, sigma, dte, k_lo=30.0, k_hi=250.0, step=0.25)
    m = compute_bkm_moments(chain, spot=S, r=r, target_dte=dte)
    assert m is not None
    assert 0.19 < m["rn_volatility"] < 0.21


def test_bkm_refuses_sparse_chain():
    """Fewer than 3 OTM strikes per side -> None, not garbage."""
    S, r, sigma, dte = 100.0, 0.04, 0.25, 30
    chain = _bs_chain(S, r, sigma, dte, k_lo=95.0, k_hi=105.0, step=5.0)
    assert compute_bkm_moments(chain, spot=S, r=r, target_dte=dte) is None
