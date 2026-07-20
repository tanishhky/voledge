# ◈ VolEdge — Volatility Trading & Strategy Platform

![tests](https://github.com/tanishhky/voledge/actions/workflows/tests.yml/badge.svg)

**The thesis in one line:** the gap between what options *price* (the risk-neutral
distribution, extracted model-free via BKM) and what the underlying *realizes*
(the physical distribution, horizon-matched) **is the risk premium** — and that
spread, `Q − P`, is a forward-looking signal you can size and trade.

VolEdge is a full-stack platform built around that idea. It pairs:

1. **The research engine** — model-free risk-neutral moments (BKM 2003) measured
   against statistically-correct, horizon-matched realized moments, surfaced as
   the variance / skew / kurtosis risk premium on the **PREMIUM** tab. Plus
   mean-reversion diagnostics (OU half-life, Hurst, Dickey-Fuller, rolling
   half-life) on the **REVERSION** tab.
2. **The execution engine** — define a trading universe, write strategy code in a
   sandboxed (AST-validated) DSL, and backtest it with walk-forward optimization,
   Monte-Carlo tearsheets, and PDF reporting.

**Runs with zero API keys.** Data comes from **Yahoo Finance by default** (free,
~15-min delayed — candles *and* live option chains), with **Polygon.io** as an
optional drop-in for higher rate limits (leave the key blank to use Yahoo). All
greeks, IV, risk-neutral moments, and realized moments are computed locally — no
paid analytics API required. The Yahoo options adapter is ported from the PinSight
reference implementation.

## Architecture

```
price-distribution-tool/
├── backend/
│   ├── main.py                 # FastAPI — all endpoints
│   ├── polygon_client.py       # Polygon.io stock/crypto/forex OHLCV + parallel fetch
│   ├── options_client.py       # Polygon.io options contracts + bars
│   ├── analysis.py             # D1, D2 distributions + GMM + Mahalanobis label-stable moment evolution
│   ├── volatility_engine.py    # Black-Scholes, IV, tenor-matched VRP, signal generation w/ txn costs
│   ├── bkm_engine.py           # Bakshi-Kapadia-Madan (2003) model-free risk-neutral moments
│   ├── models.py               # Pydantic data models
│   ├── strategy_engine.py      # Walk-forward engine, AST validator, sandboxing
│   ├── strategy_routes.py      # API route definitions for strategy execution
│   ├── tearsheet_engine.py     # Quantitative tearsheet, Monte Carlo, PDF report generation
│   ├── wfo_engine.py           # Walk-forward optimization (out-of-sample testing)
│   ├── database.py             # SQLite persistence for strategies & run history
│   ├── data_fetcher.py         # Multi-source data abstraction (yfinance, Alpha Vantage, Tiingo)
│   ├── data_quality.py         # Pre-execution data quality checks
│   ├── config.py               # Environment-based settings (pydantic)
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── main.jsx
│   │   ├── App.jsx               # Main layout, state, tab routing
│   │   ├── api.js                # API client with validation error unwrapping
│   │   └── components/
│   │       ├── Controls.jsx          # Collapsible sidebar: multi-key input, core params
│   │       ├── SettingsModal.jsx     # Header dropdown: batch sizes, expiry ranges, moment rules
│   │       ├── CandlestickChart.jsx  # Plotly OHLCV + volume
│   │       ├── DistributionChart.jsx # D1/D2 histogram + KDE
│   │       ├── GMMChart.jsx          # GMM decomposition breakdown
│   │       ├── ComparisonChart.jsx   # D1 vs D2 overlay
│   │       ├── VolatilityPanel.jsx   # IV surface, term structure, skew, chain table
│   │       ├── BKMPanel.jsx          # BKM risk-neutral vs GMM physical moment comparison
│   │       ├── SignalsPanel.jsx      # Trade signals with legs, greeks, PnL, execution costs
│   │       ├── ResultsPanel.jsx      # Textual narrative output + tables
│   │       ├── MomentsChart.jsx      # 2×2 moment evolution charts (Mean, σ, Weight, Kurtosis)
│   │       ├── MergePanel.jsx        # Cache file merger with dedup statistics
│   │       ├── StrategyPanel.jsx     # Strategy config, code editor, walk-forward execution
│   │       ├── TearsheetPanel.jsx    # Full quantitative tearsheet (equity, drawdown, heatmap, VaR)
│   │       ├── ComparePanel.jsx      # Multi-strategy side-by-side comparison
│   │       ├── SensitivityPanel.jsx  # Parameter sensitivity sweep (3D surface & heatmap)
│   │       ├── WfoPanel.jsx          # Walk-forward optimization (in-sample vs OOS)
│   │       ├── LibraryPanel.jsx      # Saved strategy library (SQLite-backed)
│   │       └── EquityAnimator.jsx    # Animated P&L replay with interactive scrubbing
│   ├── index.html
│   ├── package.json
│   └── vite.config.js
├── docker-compose.yml
├── STRATEGY_INTEGRATION_GUIDE.md
└── README.md
```

## Core Workflows & Features

### Demonstrations

- **Full Walkthrough (live data):** Price + GMM fit → IV surface → BKM risk-neutral vs physical moments → generated trade signals → the Strategy Lab, run end to end on a live SPY chain.
![VolEdge Full Walkthrough](assets/voledge-demo-walkthrough.gif)

Check out the interactive backtesting and analysis features:

- **BKM Moments & Volatility Analysis:** Fetch options chains, compute risk-neutral moments via BKM, and generate trading signals.
![Volatility & BKM Panel Demo](assets/demos/bkm_vol_demo.webp)

- **API Mode Walk-Forward Execution:** Execute complex multi-regime strategies with zero look-ahead bias right out of the box.
![Strategy API Execution Demo](assets/demos/strategy_demo.webp)

- **Parameter Sensitivity Sweep:** Instantly visualize how tiny configuration changes impact your CAGR and Sharpe using 3D surface plots.
![Sensitivity Panel Demo](assets/demos/sensitivity_demo.webp)

- **Walk-Forward Optimization (WFO):** Dynamically optimize and map metrics over moving training windows.
![WFO Panel & Tearsheet Demo](assets/demos/tearsheet_wfo_demo.webp)

### 1. Data Fetching & Parallel Processing
- **Key-free by default (Yahoo Finance)** — Leave the API-key box blank and both candles and full option chains are pulled from Yahoo (`backend/yahoo_client.py`), no signup required. BKM/premium run on a real chain out of the box.
- **Multi-API Key Support (Polygon, optional)** — Paste one or more Polygon keys to switch to Polygon and bypass its free-tier rate limits.
- **Parallel Chunking** — The backend automatically splits historical date ranges across all available keys for concurrent fetching.
- **Batched Option Lookups** — Options bars are fetched via round-robin key assignment. Rate limits are exactly managed (batch sizes and delays are configurable in settings).
- **Multi-Source Abstraction** — `DataFetcher` supports yfinance (default), Alpha Vantage, and Tiingo for strategy backtesting.
- **Data Quality Checks** — Automated pre-execution validation detects missing dates, stale prices, extreme returns, survivorship bias, duplicate timestamps, and weekend data.

### 2. Gaussian Mixture Model (GMM) Analysis
- **Independent or Synced Fitting** — Fit N components independently to Time-at-Price (D1) and Volume-Weighted (D2) distributions, or use "Sync D1/D2" to find the universally best shared N minimizing combined BIC.
- **Label-Stable Moment Evolution** — Track how each Gaussian component's Mean, Volatility (σ), and Probability Weight drift over time via a sliding window. Uses **Mahalanobis-distance matching** between windows to prevent discontinuous jumps when component ordering shifts in sklearn's GMM optimizer.
- **Re-Analyze** — Change bins or the maximum/desired components via the themed sliders and instantly re-run the math without re-fetching underlying candles.

### 3. Volatility Engine (Locally Computed)
- **Black-Scholes Pricing** — Full implementation with continuous dividends handling call/put greeks analytically.
- **Implied Volatility Tracking** — Brent root-finding for IV calculation mapped to a 3D Volatility Surface.
- **Tenor-Matched VRP** — Volatility Risk Premium computed at specific tenors (10d, 20d, 30d) using inverse-distance-weighted ATM IV. Each VRP directly compares IV at that tenor vs the corresponding realized vol.
- **Metrics Dashboard** — 25Δ Put-Call Skew (fear premium), VRP, Term Structure, and Parkinson high-low volatility estimators.

### 4. BKM Model-Free Risk-Neutral Moments
- **Bakshi-Kapadia-Madan (2003) Engine** — Extracts variance, skewness, and kurtosis directly from OTM option prices via Simpson's-rule integration. No distributional assumption required.
- **Dual Tenor Extraction** — Computes moments at both 30-day and 60-day horizons.
- **RN vs Physical Comparison** — The BKM Panel shows side-by-side risk-neutral (BKM from options) vs physical (GMM price-space) moments with color-coded mispricing alerts. For the *statistically correct, horizon-matched* comparison, see the **PREMIUM** tab below.
- **Actionable Insights** — Flags when the market is pricing more downside than the physical distribution suggests (expensive puts), or when tail options are overpriced/underpriced.

### ⭐ The Risk Premium (Q − P) — Headline
The **PREMIUM** tab is the platform's central claim. It pairs the BKM
risk-neutral moments with **horizon-matched physical return moments** (computed
on overlapping `target_dte`-day log returns, so both distributions describe the
*same* forecast horizon — unlike the BKM panel's price-space comparison) and
reports the spread for each moment:

- **Variance risk premium** = RN variance − realized variance. Persistently
  positive ⇒ options price more variance than realizes (the short-vol carry).
- **Skew risk premium** = RN skew − physical skew. More-negative RN skew ⇒ the
  market is paying up for crash protection beyond what has historically realized.
- **Kurtosis risk premium** = RN kurtosis − physical kurtosis (tail pricing).

Each tenor (30d / 60d) ships with a plain-English **read** generated from the
spreads (e.g. *"Options price 9.1 vol-pts more variance than realized — variance
risk premium is rich; carry favors selling premium"*). Backend:
`physical_moments.py` (`compute_physical_moments`, `compute_risk_premium`).

### ↻ Mean-Reversion Diagnostics
The **REVERSION** tab is a descriptive lens (not a signal generator) answering
"does this metric mean-revert, and how fast?" for price, log-price, and a
trailing realized-vol series. Three independent estimators corroborate each other:

- **OU half-life** — from the AR(1) speed of reversion (`-ln 2 / ln φ`).
- **Hurst exponent** — H < 0.5 mean-reverting, ≈ 0.5 random walk, > 0.5 trending.
- **Dickey-Fuller t-stat** — evidence against a unit root.

Plus a **rolling half-life** series so you can see by eye whether the speed of
reversion is itself converging, a long-run mean band (±1σ, ±2σ), and a current
z-score. Backend: `mean_reversion.py` (`mean_reversion_analysis`).

### ⚙ Premium-Driven Backtests — Results

The platform thesis is closed end-to-end: the **PREMIUM** tab *measures* the
risk premium, and two built-in strategies *trade* it through the walk-forward
engine (zero look-ahead). Numbers below are real, out-of-sample, on free
Yahoo Finance data, **2019-01 → 2024-12**, net of modeled transaction costs.

| Strategy | Return | Ann. | Vol | Sharpe | Max DD |
|---|---|---|---|---|---|
| **GARCH vol-managed SPY** (2020–24) | +75.1% | 11.9% | **13.9%** | **0.85** | **−19.7%** |
| SPY buy-and-hold (same) | +94.6% | 14.3% | 21.0% | 0.68 | −33.7% |
| **VIX variance-premium harvest** (2019–24) | −15.4% | −2.9% | 17.8% | −0.16 | −44.0% |
| SPY (2019–24) | +123.9% | 15.1% | 20.1% | 0.75 | −33.7% |

- **GARCH vol-managed** (`garch_volmanaged`) — the clean positive result. A
  GARCH(1,1) conditional-variance forecast scales SPY exposure to a 15% vol
  target (Moreira–Muir style), the rest in T-bills. Apples-to-apples vs SPY
  buy-and-hold it delivered a **higher Sharpe (0.85 vs 0.68, +25%)** at **41%
  lower max drawdown (−19.7% vs −33.7%)** and a realized 13.9% vol. Disciplined
  volatility-timing works.
- **VIX variance-premium harvest** (`vix_vrp`) — the honest reality check. Holds
  short-vol (SVXY) when `VIX² − realized` is positive, scaling exposure down as
  VIX rises and stepping out in stress (VIX > 30). Net of realistic transaction
  costs over 2019–24 it **lost money (−15.4%, Sharpe −0.16, −44% max drawdown)**.
  This is the intended finding, not a failure to hide: across two major vol
  spikes (COVID-2020, 2022) the variance premium behaves as *compensation for
  crash risk*, not harvestable alpha with simple long-only instruments — exactly
  why the premium exists. The platform *measures* the premium (PREMIUM tab) and
  then *shows it is dangerous to harvest naively*.

**Engine validation.**
- *Walk-forward accounting* — a 100%-SPY strategy reproduces SPY buy-and-hold to
  ±0.000pp at every rebalance frequency (daily → quarterly), confirming the
  mark-to-market is correct and frequency-independent.
- *BKM extractor* — unit-tested against a Black-Scholes chain of known
  volatility: recovers the true 20% vol and ~0 skew/kurtosis and converges toward
  truth as strike coverage widens (residual error is strike truncation — the same
  limitation BKM has on any real, finite option chain). A put-skew chain
  correctly yields negative risk-neutral skew.

### 5. Trade Signal Generation
Evaluates real-time math thresholds against the enriched options chain to output actionable strategies. All signals include **transaction cost adjustments** using bid-ask spreads (or a 3% mid-price haircut as fallback):

1. **Vol Crush** — When VRP > 5%, sell short strangles to capture premium.
2. **Skew Trade** — When 25Δ Put Skew exceeds GMM tail risk, sell put credit spreads.
3. **Calendar Spread** — When term structure inverts (backwardation), sell near / buy far.
4. **Mean Reversion** — When price displaces from primary High Volume Nodes, buy directional options.
5. **Gamma Scalp** — When GMM distribution is distinctly multi-modal, buy straddle + delta-hedge.

Each signal reports `estimated_execution_cost` for full transparency on spread drag.

### 6. Caching & Merging System
- **Raw-Only Cache** — Session data (candles, option contracts, closed bars) saves locally as `.json`. No computed data is exported, ensuring purity.
- **Instant Restore** — Uploading a cache file skips all API hits and immediately recomputes GMM and options greeks.
- **Merge Tool** — Dedicated MERGE tab lets you drag-and-drop multiple cache files. It intelligently dedupes overlapping candles (by timestamp) and contracts (by ID) to synthesize larger continuous datasets.

### 7. Strategy Lab & Walk-Forward Engine
- **Zero Look-Ahead Bias** — Upload custom Python code for regime detection and allocation. The engine executes day-by-day, ensuring logic strictly receives `t-1` historical data.
- **Built-in Templates** — Fast-start strategies: **VIX Variance-Premium Harvest** and **GARCH Vol-Managed** (the premium-driven pair, see Results above), plus Gaussian HMM Regime Switching, Dual MA Momentum, and simple Volatility thresholding.
- **Interactive Animator** — Animate walk-forward P&L alongside an overlaid historical price chart, dynamically shaded by active regimes with scrubbing and speed controls.
- **Strict Sandboxing** — The Python code evaluator strips dangerous built-ins and uses AST parsing to rigidly lock down imports to secure numerical libraries (numpy, pandas, scipy, sklearn, hmmlearn).

### 8. Quantitative Tearsheet & Reports
- **Full Tearsheet** — Post-backtest analytics comparable to pyfolio/quantstats: CAGR, Sharpe, Sortino, Calmar, Omega, Tail Ratio, VaR (historical, parametric, Cornish-Fisher), CVaR, Ulcer Index, drawdown table, monthly return heatmap, rolling metrics, and benchmark comparison (alpha, beta, info ratio, up/down capture).
- **Monte Carlo Simulation** — Block bootstrap (21-day blocks to preserve autocorrelation) with 10,000 paths. Reports confidence intervals for terminal wealth, max drawdown, and probability of loss. Fan chart visualization.
- **PDF Report Export** — One-click professional PDF generation with equity curve chart, key metrics table, and drawdown analysis via ReportLab + matplotlib.

### 9. Parameter Sensitivity & Walk-Forward Optimization
- **Grid Sweep** — Sweep over any parameter range (e.g., `rebalance_days`, `transaction_cost`) and visualize how strategy performance varies via 3D surface plots and heatmaps.
- **Walk-Forward Optimization** — Splits data into N folds of rolling train/test windows. For each fold: optimizes parameters in-sample, evaluates out-of-sample. Stitches OOS equity curves for unbiased composite performance.
- **Multi-Strategy Comparison** — Run multiple strategies or configs, compare side-by-side with overlaid equity curves and pairwise return correlations.

### 10. Strategy Library & Persistence
- **SQLite Database** — Strategies, run history, and sessions are persisted in a local SQLite database (`voledge.db`).
- **Strategy CRUD** — Save, load, update, fork, and delete strategies. Tag and search your library.
- **Run History** — All backtest executions are logged with configs, metrics, and duration for auditability.

### 11. Dynamic UI/UX
- **Function-Grouped Navigation** — tabs grouped by purpose with in-panel sub-toggles: **EQUITY** (Price [Charts/Profile/Stats], Moments, Reversion — the underlying), **OPTIONS** (Surface, BKM, Premium, Signals — the derivatives), **BACKTEST** (Strategy, Results [Tearsheet/Animate/Compare], Optimize [Sensitivity/Walk-Forward], Library), **TOOLS** (Merge). The EQUITY/OPTIONS split makes explicit which views analyze the underlying vs the option chain.
- **Collapsible Sidebar** — The Controls sidebar is draggable/resizable (200px–450px) and collapses into a micro-icon strip to maximize chart space.
- **Configuration Hub** — A header gear icon ⚙ opens Settings for tweaking batch variables (requests vs delay), option expirations (near/far boundaries), and sliding window ratios.
- **Theming** — Fully unified dark-mode styling with natively customized WebKit range sliders (`#3b82f6` accents). Font stack: JetBrains Mono for data, DM Sans for UI.

## Setup & Run

### Option A: Docker Compose (Recommended)

```bash
docker-compose up --build
```
- Frontend: http://localhost:80
- Backend API: http://localhost:8000/docs

### Option B: Local Development

#### 1. Backend
```bash
cd backend
pip3 install -r requirements.txt
python3 -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

#### 2. Frontend
```bash
cd frontend
npm install
npm run dev
```
- Frontend: http://localhost:5173
- Backend API: http://localhost:8000/docs

### 3. Usage Guide

1. **Setup**: Leave the CONNECTION key box blank to use free Yahoo Finance data (candles + option chains), or paste Polygon.io key(s) for higher rate limits.
2. **Fetch**: Enter a ticker (e.g. SPY, BTCUSD), select a timeframe, and click **▶ Fetch & Analyze**.
3. **Tweak Analysis**: Slide the Bin/N sliders. Click **⟳ Re-Analyze (GMM)** to instantly update the charts in the CHARTS and MOMENTS tabs.
4. **Vol Scan**: Click **◈ Run Vol Analysis** to pull the options chain and compute the Volatility Surface, BKM Moments, and Signals.
5. **BKM Moments**: Navigate to the **BKM** tab to compare risk-neutral (from options) vs physical (from GMM) moments and see mispricing alerts.
6. **Simulate**: Click the ⚙ icon top right to adjust near/far expiration constraints or edit Dividend/Risk-Free rates in the sidebar, then hit **⟳ Reprocess (cached)**.
7. **Data Portability**: Click **↓ Save** at the bottom of the sidebar to dump raw data. Use the **MERGE** tab to combine it with older saves.
8. **Strategy Lab**: Switch to the **STRATEGY** tab to code, validate, and execute zero look-ahead bias backtests using your own active regime detection.
9. **Tearsheet**: After a strategy executes, navigate to the **TEARSHEET** tab for full quantitative analytics. Download a PDF report with the button.
10. **Sensitivity / WFO**: Use the **SENSITIVITY** tab for parameter sweeps and **WFO** for out-of-sample walk-forward optimization.
11. **Animator**: Navigate to the **ANIMATE** tab to replay the P&L timeline alongside historical price data.

## API Endpoints

```text
GET   /health                          → Health check
GET   /supported-intervals             → Valid timeframes

POST  /fetch                           → Fetch OHLCV + auto-detects asset class
POST  /analyze                         → GMM distribution + sliding moment evolution
POST  /mean-reversion                  → OU half-life, Hurst, DF t-stat, rolling half-life
POST  /volatility                      → Vol surface + BKM moments + physical moments + Q−P premium + signals
POST  /volatility/reprocess            → Recalculates greeks + BKM + premium + signals (no API hit)

POST  /strategy/validate               → Validates user-uploaded Python strategy code
POST  /strategy/run                    → Executes a walk-forward strategy backtest
POST  /strategy/run-template           → Runs a built-in strategy template
GET   /strategy/templates              → List available strategy templates
GET   /strategy/docs                   → Core API specifications for strategy logic

POST  /strategy/manual/upload-data     → Upload CSV/Excel data for manual mode
POST  /strategy/manual/validate        → Validate manual strategy code
POST  /strategy/manual/run             → Execute manual mode backtest

POST  /strategy/tearsheet              → Compute full quantitative tearsheet
POST  /strategy/monte-carlo            → Block-bootstrap Monte Carlo simulation
POST  /strategy/report                 → Generate downloadable PDF report
POST  /strategy/data-quality           → Run data quality checks on uploaded data

GET   /strategy/library                → List saved strategies
POST  /strategy/library/save           → Save a strategy to the library
GET   /strategy/library/{id}           → Load a saved strategy
PUT   /strategy/library/{id}           → Update a saved strategy
DELETE /strategy/library/{id}          → Delete a saved strategy

GET   /strategy/runs                   → List recent backtest runs
GET   /strategy/runs/{id}              → Get full details of a run

POST  /strategy/compare                → Run multiple strategies for side-by-side comparison
POST  /strategy/sensitivity            → Parameter sensitivity grid sweep
POST  /strategy/wfo                    → Walk-forward optimization
```

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `sqlite:///voledge.db` | SQLite (or PostgreSQL) connection string |
| `CORS_ORIGINS` | `http://localhost:5173,...` | Comma-separated allowed origins |
| `MAX_UPLOAD_SIZE_MB` | `100` | Maximum file upload size |
| `SANDBOX_TIMEOUT_SECONDS` | `300` | Strategy execution timeout |
| `POLYGON_API_KEY` | — | Default Polygon key (optional, can paste in UI) |
| `ALPHA_VANTAGE_API_KEY` | — | Alpha Vantage key (for strategy data fetching) |
| `TIINGO_API_KEY` | — | Tiingo key (for strategy data fetching) |
| `LOG_LEVEL` | `INFO` | Logging verbosity |

## Limitations & Notes

- **Data sources**: Yahoo Finance (default, no key) returns candles and full option chains, ~15-min delayed, with no SLA — the library can break when Yahoo changes its schema. Polygon.io (optional, paste a key) allows 5 calls/min per free-tier key; the settings defaults (`Batch Size`=5, `Delay`=61s) stay within that, and multiple keys scale throughput linearly.
- **BKM on real chains**: validated on live Yahoo SPY chains — recovers a sensible skew/kurtosis term structure (e.g. 30d skew ≈ −2.2 / kurt ≈ 9, 60d ≈ −1.6 / 3.4). The Yahoo adapter selects the expiries nearest the 30d/60d tenors and a ±20% strike window; wider windows inflate skew/kurtosis from deep-OTM quote noise. Kurtosis remains the least reliable moment on free data.
- **Options Data Limitations**: Yahoo quotes are delayed snapshots; deep-OTM strikes can be stale (a liquidity filter drops quotes without a two-sided market or recent volume). Transaction-cost estimates use a 3% mid-price haircut when bid/ask is unavailable.
- **BKM Requirements**: Model-free risk-neutral moments require ≥3 OTM calls and ≥3 OTM puts within the target DTE bucket. Broader strike ranges or deeper chains improve accuracy.
- **IV Accuracy**: Black-Scholes inherently prices European options. For American equity options, there is a minor early-exercise discrepancy, but BS serves as the standard approximation.
- **Signal Disclaimer**: Generated signals are mathematical indicators derived purely from statistical anomalies (VRP, Skew, KDE multimodality). They are **not** investment advice.

## Working Paper

A short technical write-up of the Q-P thesis and validated results (`paper/paper_voledge.pdf`) is
submitted to SSRN, currently under editorial review:
[Abstract ID 7113098](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=7113098).
