# VolEdge — Interview Question Bank

Anticipated questions for quant-research / quant-dev interviews, with answers
grounded in what the code actually does. Honest about limitations — interviewers
reward candidates who know the holes in their own work.

---

## 1. The thesis

**Q: One sentence — what is VolEdge?**
A platform that measures the gap between what options *price* (the risk-neutral
distribution, via model-free BKM moments) and what the underlying *realizes* (the
physical distribution, horizon-matched), surfaces that gap as the variance/skew
risk premium, and backtests strategies that try to trade it.

**Q: Why is "price ≠ probability" central here?**
The option-implied (risk-neutral, Q) distribution embeds a risk premium, so it is
*not* the real-world (physical, P) probability. The whole platform is built around
keeping Q and P as distinct measured objects and studying `Q − P`. The premium is
precisely the wedge between them.

---

## 2. BKM / risk-neutral moments

**Q: How do you get risk-neutral moments without assuming a model?**
Bakshi-Kapadia-Madan (2003). Any twice-differentiable payoff can be spanned by a
continuum of OTM options (Carr-Madan). The variance/cubic/quartic contracts have
known weights `w(K)`, so their prices are `∫ w(K)·O(K) dK` over OTM calls and
puts. From those three contract prices (V, W, X) you get risk-neutral variance,
skew, and kurtosis in closed form. No distributional assumption — only that you
can integrate across strikes.

**Q: Implementation details?**
OTM calls for `K>S`, OTM puts for `K≤S`; using `ln(K/S)` the call/put integrands
unify. Simpson's rule over the (irregular) strike grid, trapezoidal fallback for
degenerate segments. `e^{rT}` appears once in the moment formulas, not in the
integrands.

**Q: How do you know it's right?**
Unit test against a Black-Scholes chain of known vol: it recovers ~20% vol, ~0
skew, ~0 excess kurtosis, and converges to truth as strike coverage widens. A
synthetic put-skew chain yields negative RN skew. *(I actually found and fixed a
bug here — see Q on bugs.)*

**Q: Biggest weakness of the BKM number?**
Strike truncation and discretization. Real chains are finite and sparse, so the
wings (which dominate the quartic/kurtosis integral) are under-sampled → variance
slightly understated, kurtosis the least reliable moment. This is inherent to BKM
on real data, not specific to my implementation.

---

## 3. The premium (`Q − P`)

**Q: How is the physical side computed so it's comparable to BKM?**
Horizon-matched. BKM gives moments of the `T`-day return distribution, so I
compute physical moments on *overlapping `T`-day log returns* (not 1-day returns —
skew/kurtosis are horizon-dependent). Variance premium = RN var − realized var,
etc.

**Q: A subtlety in that comparison?**
Annualization basis: realized vol uses 252 trading days; BKM `T = dte/365`
(calendar). There's a small (~1.5%) basis mismatch, standard in VRP work. Skew and
kurtosis are dimensionless at the horizon, so they compare directly.

**Q: The honest seam in the project?**
The *live* PREMIUM tab runs BKM on a single current chain (a snapshot) for any
ticker. The *backtest* needs a premium time series, which free data can't give
per-name, so the backtest uses an index VIX proxy. Two different measurements of
the same idea — I'm explicit about it. The backtest's job is to show the premium
the live tool surfaces is economically real (and risky), not to reproduce BKM
historically.

---

## 4. Strategy results (be ready to defend every number)

**Q: What did you actually find?**
Two results, on real Yahoo data, net of modeled costs, walk-forward:
- **GARCH(1,1) vol-managed SPY (2020–24):** scale exposure to a 15% vol target.
  Sharpe **0.85 vs SPY 0.68**, max DD **−19.7% vs −33.7%**, realized vol 13.9%.
  Vol-timing beat buy-and-hold risk-adjusted with far lower drawdown.
- **VIX variance-premium harvest (2019–24):** short-vol (SVXY) when `VIX² −
  realized > 0`, de-risking as VIX rises, out in stress. It **lost money**
  (−15.4%, Sharpe −0.16, −44% DD). That's the point: the premium is compensation
  for crash risk, not free alpha for a naive long-only harvester.

**Q: Why does vol-managed work (Moreira–Muir intuition)?**
Volatility is forecastable (persistent/clustered) but expected returns are not, so
scaling down in high-forecast-vol states improves the realized return/risk
trade-off — and because the variance premium makes high-vol states expensive to be
long, you're paid to step aside.

**Q: Is the GARCH result just leverage timing / data mining?**
Single a-priori parameter (15% target), one underlying (SPY), one expanding-window
GARCH(1,1) refit per rebalance, compared apples-to-apples to SPY buy-and-hold. No
parameter sweep behind the headline. I'd next stress it with walk-forward
parameter selection (the OPTIMIZE tab) and multiple underlyings.

**Q: Why is the VRP strategy in the repo if it loses?**
Because hiding it would be the dishonest move. A losing naive-short-vol backtest
that I can *explain* (crash-risk compensation) demonstrates I understand risk
premia as compensation, not anomalies. The contrast with the working vol-managed
strategy is the actual insight.

---

## 5. No look-ahead / engine

**Q: How do you guarantee no look-ahead?**
The walk-forward engine slices `data[:i]` at each decision point `i`; the strategy
`detect_regime`/`get_allocations` only ever see history up to yesterday. Strategy
code is AST-validated and sandboxed (no I/O, no network, whitelisted imports).

**Q: You mentioned a bug you found in your own engine — what was it?**
The mark-to-market ran *after* rebalancing: positions were reset to target at
today's price and then valued at that same price, so one period of P&L was dropped
at every rebalance. With daily rebalancing that meant *no* return accrued (≈0% vol,
pure cost bleed). Fix: mark holdings to today's price *first*, then rebalance;
cost turnover from the actual drifted weights. Validation: a 100%-SPY strategy now
reproduces SPY buy-and-hold to ±0.000pp at any rebalance frequency. The earlier
"good" VRP number was partly an artifact of this bug — fixing it made the result
honestly worse, which I kept.

**Q: How is transaction cost modeled?**
Per-leg: bid/ask (spread bps), market impact bps, slippage %, per-share commission
with a minimum, optional flat fee; or a simple cost-per-turnover fallback. Charged
on the actual drift-to-target turnover each rebalance.

---

## 6. GMM / mean-reversion (the descriptive layer)

**Q: What does the GMM on price actually estimate?**
A mixture fit (BIC-selected components, Mahalanobis-matched across a sliding window
for label stability) to the time-at-price / volume-weighted distributions — a
physical-distribution estimate. I deliberately retired the old "high/low volume
node" framing because node-as-support is retail folklore, not a quant edge.

**Q: Mean-reversion diagnostics — what and why three?**
OU half-life (AR(1) speed, `−ln2/lnφ`), Hurst exponent, and a Dickey-Fuller
t-stat, plus a rolling half-life. Three independent estimators so they corroborate
or contradict. The verdict requires a *finite in-sample half-life* before calling
something mean-reverting — a trending price can score a borderline Hurst < 0.5 yet
have no real reversion. It's a descriptive lens, explicitly not a signal
generator.

---

## 7. System design

**Q: Stack and why?**
FastAPI backend (typed Pydantic models, async option-chain fetching with
rate-limit batching across keys), React + Plotly frontend, SQLite for
strategy/run persistence, Docker compose. The compute (BS greeks, IV inversion via
Brent, BKM, GMM, GARCH) is all local — no paid analytics API.

**Q: Where would this break at scale / what would you do next?**
(1) Real intraday option data (free tier is daily bars) to validate BKM on live
chains. (2) Replace overlapping-return moment estimates with a cleaner term
structure. (3) Walk-forward parameter selection on the vol-managed strategy across
many underlyings. (4) A proper event/position ledger instead of the simplified
weight-based accounting.

---

## 8. Curveballs

**Q: If I gave you a Bloomberg terminal tomorrow, what's the first thing you'd
re-check?** BKM on a real, liquid chain (SPX) vs the VIX — they should roughly
agree; any large gap is a data/strike-coverage problem, not a model win.

**Q: What part are you least confident about?** The kurtosis premium — both legs
(BKM quartic integral and overlapping-return sample kurtosis) are the noisiest
estimates in the system. I'd lean on variance and skew premia for any real
decision.

**Q: What did building this teach you that a course didn't?** That the variance
risk premium is easy to *measure* and hard to *keep* — the gap between a clean
backtest and a survivable strategy is transaction costs, gap risk, and the
discipline to not data-mine the drawdown away.
