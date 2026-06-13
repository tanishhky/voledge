# VolEdge — Roadmap & Decision Memo (2026-06-13)

This file exists so the next session can pick up the VolEdge direction
discussion without re-litigating it. It is a planning artefact, not a
spec; it should be edited freely as the direction firms up.

## Why this file exists

On 2026-06-13 the question came up: as part of the resume revamp for
FTE 2027 applications (first wave early July), should VolEdge be
refined further before it gets a recruiter-grade README and demo? The
user's self-assessment was that VolEdge is "a half-baked research thing
where only the comparative B&H visualisation is complete." The
evaluation below pushes back on that read.

## Honest evaluation of the codebase

VolEdge is **not** half-baked. The engineering substance is real:

- **6,064 lines** of Python backend + a React frontend with 18+
  specialised panels.
- **`bkm_engine.py`** — Bakshi-Kapadia-Madan (2003) model-free
  risk-neutral moment extraction from option chains. This is the kind
  of analytics buy-side desks pay Bloomberg for; implementing it
  locally is research-level work.
- **`volatility_engine.py`** (~886 lines) — Black-Scholes, Brent-root
  IV inversion, tenor-matched variance-risk-premium, signal
  generation with transaction costs.
- **`strategy_engine.py`** (~1,117 lines) — a DSL for user-written
  strategy code with AST validation and sandboxed execution. That
  combination (DSL + AST validation + sandbox) is real engineering,
  not student-grade.
- **`wfo_engine.py`** — walk-forward optimisation with proper
  in-sample / out-of-sample separation.
- **`tearsheet_engine.py`** (~724 lines) — Monte Carlo, equity,
  drawdown, heatmap, VaR, PDF report generation.
- **`analysis.py`** — GMM physical distribution + Mahalanobis
  label-stable moment evolution.
- 18+ React panels including IV surface, BKM, sensitivity 3D surface,
  multi-strategy compare, animated P&L replay, WFO panel, library
  panel.
- SQLite persistence, Docker compose, `paper/paper_voledge.tex`
  drafted.

## Why it *feels* half-baked

The surface area is huge; the thesis is thin. A recruiter or Alex
Shirokov does not read 18 panels. They want one sentence: *"I built X,
I ran experiment Y, I found Z."* VolEdge has X (the platform) and Y
(the engine), but Z (a sharp finding) is buried or absent. That is
what produces the half-baked feeling — not the engineering, but the
narrative.

## Three roadmap options

### Roadmap A — Reframe as a software platform, not a research project
**Effort:** 3 days. **Recommended given the July application
timeline.**

- Rewrite the README from "feature list" to research-thesis-driven
  narrative: *"Buy-side-grade local options analytics stack: BKM
  model-free risk-neutral moments without paid APIs, walk-forward
  backtest engine with AST-sandboxed strategy code, full tearsheet
  reporting."* That sentence is true today.
- Record the polished 90-second demo for Alex (overdue since
  2026-05-31): BKM panel + one strategy backtest tearsheet vs SPY
  buy-and-hold.
- Turn `paper/paper_voledge.tex` into a 4-page technical note
  describing the implementation: BKM derivation, walk-forward
  architecture, AST validation. Do **not** claim a research finding;
  claim engineering credibility.
- Resume bullet writes itself.

### Roadmap B — Make one sharp research claim
**Effort:** 2-3 weeks.

- Pick a single thesis. Example: *"BKM-derived skew + VRP signals
  outperform delta-1 trend on US equities, 2018-2024, after
  transaction costs."*
- Run that one backtest cleanly, with no-lookahead discipline (the
  PinSight architecture is the gold standard to copy).
- Headline number becomes the paper's central result.
- This converts VolEdge into an actual research artefact, but the
  effort puts it outside the early-July application window.

### Roadmap C — Park it
**Effort:** 2 days.

- Polish README minimally, send Alex the basic demo to discharge the
  obligation.
- Move firepower to PinSight + DriftEdge, where the no-lookahead
  architectural enforcement and live paper trading (DriftEdge Kuber
  agent with RSA-signed Kalshi POSTs) are genuinely uncommon for
  student work.
- Treat VolEdge as a Tier 2 project on the resume.

## Recommendation as of 2026-06-13

**Roadmap A.** Reasoning:

1. The July application window is tight (3-4 weeks). Roadmap B is
   high-value but risks missing the window.
2. The BKM implementation is real and defensible standalone. "I built
   buy-side analytics infrastructure" is a strong pitch on its own.
3. Roadmap A discharges the overdue Alex Shirokov deliverable, which
   was the blocker preventing the resume from claiming VolEdge anyway.
4. The infrastructure built under Roadmap A is exactly what Roadmap B
   would need later. Post-application escalation to B is cheap.

## Decision taken (2026-06-13)

**Committed to the hybrid A→B path.** The user rejected stopping at A
("why stop at mediocrity… make the absolute best") and committed to
building the sharp research finding directly into the platform rather
than after the application window. The agreed framing splits VolEdge
into two resume bullets that connect into one story:

1. **Research bullet (landing/analysis page):** the risk premium `Q − P`.
   The old GMM-on-time-at-price "HVN/LVN" framing (volume-profile
   folklore, not quant-respected) is retired as the headline; the GMM
   machinery is repurposed toward the physical distribution. The
   thesis the platform now states: risk-neutral moments (BKM) vs
   horizon-matched realized moments → the variance / skew / kurtosis
   risk premium as a forward-looking signal.
2. **Engineering bullet:** the universe + AST-sandboxed strategy DSL +
   walk-forward + tearsheet backtest engine.

### Shipped this session (2026-06-13)
- `backend/physical_moments.py` — horizon-matched physical return
  moments + `compute_risk_premium` (Q − P spread + plain-English read).
  Fixes the apples-to-oranges comparison in the old BKM panel (which
  compared price-space GMM moments to annualized return RN moments).
- `backend/mean_reversion.py` + `POST /mean-reversion` — OU half-life,
  Hurst, Dickey-Fuller t-stat, rolling half-life on price/log-price/
  realized-vol. Cosmetic/diagnostic, explicitly not a signal generator.
- Premium folded into `/volatility` + `/volatility/reprocess`
  (`phys_30d/60d`, `premium_30d/60d` on `VolatilityAnalysis`).
- Frontend: `PremiumPanel.jsx` (PREMIUM tab), `MeanReversionPanel.jsx`
  (REVERSION tab), wired into `App.jsx` + `api.js`.
- README reframed to lead with the thesis; PREMIUM + REVERSION documented.

### Still open (next sessions)
- **Roadmap B proper:** run ONE clean backtest of a premium-driven
  strategy (e.g. sell variance when the 30d variance premium is rich)
  under no-lookahead discipline → headline number for the paper/resume.
- Polished 90-sec demo for Alex Shirokov (PREMIUM tab + one backtest
  tearsheet vs SPY). Still overdue.
- Turn `paper/paper_voledge.tex` into the technical note (now with a
  real finding, not just engineering).

## Related context

- Demo + paper to Alex Shirokov has been owed since end of May 2026.
  Two-message plan (demo first, paper a few days later) is in
  `Vault/Career/Meetings-Log.md`.
- PinSight + DriftEdge READMEs are the parallel work; they share the
  no-lookahead-discipline angle.
- Three project-paper errors to fix before any resume PDF goes out:
  Regime-Aware alpha-claim caveat (8.37% first-half-only), beta 0.85
  not 0.77, SP500 sector analysis "published / ORCID" claim is wrong.
- Master resume revamp is in flight; target completion 2-3 weeks from
  2026-06-13. First applications go out early July (Citadel, Jane
  Street, JPMC QR are typically July-open, closed by mid-October).
