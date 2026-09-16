"""Ad-hoc OOS-extension check (not part of the paper pipeline).
Re-runs the two validated strategy templates through the existing
StrategyRunner with the SAME start date as make_paper_figures.py but an
extended end date, to see if results hold on the extra ~1.5-2 years of data.
"""
from __future__ import annotations
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from strategy_engine import STRATEGY_TEMPLATES, StrategyDefinition, StrategyConfig, StrategyRunner

START = "2019-01-01"
END = "2026-08-22"

for template_id in ["garch_volmanaged", "vix_vrp"]:
    tmpl = STRATEGY_TEMPLATES[template_id]
    defn = StrategyDefinition(
        name=tmpl["name"],
        tickers=tmpl["default_tickers"],
        benchmark="SPY",
        config=StrategyConfig(**tmpl["default_config"]),
        regime_code=tmpl["code"],
    )
    runner = StrategyRunner(defn)
    result = runner.run(start_date=START, end_date=END)
    m = result["metrics"]
    log = result["daily_log"]
    last_date = log[-1]["date"] if log else None
    print(f"=== {template_id} ===")
    print(f"  requested end={END}  actual last data date={last_date}  n_days={len(log)}")
    for k in ("total_return", "annual_return", "annual_vol", "sharpe", "max_drawdown"):
        print(f"  {k}: {m.get(k)}")
    print()
