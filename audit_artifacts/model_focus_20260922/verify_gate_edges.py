"""Offline checks of remaining execution and raw-feature gate edge cases."""
import ast
import json
from pathlib import Path
import socket
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def deny_network(*args, **kwargs):
    raise RuntimeError("Offline audit")


socket.socket.connect = deny_network
from reflexivity_interactive_chart import run_reflexivity_simulation

obs = {}
n = 700
df = pd.DataFrame({"date": pd.bdate_range("2018-01-01", periods=n),
                   "QQQ": 100 + np.arange(n) * .1, "HYG": 80.,
                   "NFCI": -1., "BAA10Y": 1., "Real_Yield": 1.})
result = run_reflexivity_simulation(df)
f = result.features
ready_dates = set(f.loc[f.signal_ready, "date"].dt.strftime("%Y-%m-%d"))
ready_orders = [o for o in result.orders if str(o["submit_dt"])[:10] in ready_dates]
accounts = result.daily_accounts.query("type == 'strat'")
obs["macro_normal_holding_dca"] = {
    "rows": len(f), "ready_days": int(f.signal_ready.sum()),
    "first_ready_date": str(f.loc[f.signal_ready, "date"].iloc[0]),
    "target_position_values": result.signals.Position.unique().tolist(),
    "orders_submitted_on_ready_days": len(ready_orders),
    "ending_cash": float(accounts.cash.iloc[-1]),
    "ending_shares": float(accounts.shares.iloc[-1]),
    "ready_period_dca_events": [c for c in result.cashflows if str(c.get("actual_dt"))[:10] in ready_dates],
}

for filename in ["now_reflexivity_radar.py", "single_stock_reflexivity_radar.py"]:
    tree = ast.parse((ROOT / filename).read_text(encoding="utf-8-sig"))
    function = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "run_backtest")
    gate_nodes = [node for node in function.body if isinstance(node, ast.Assign) and ast.unparse(node.targets[0]) in ["core_cols", "df_bt['signal_ready']"]]
    env = {"pd": pd, "np": np}
    exec(compile(ast.Module(body=[gate_nodes[0]], type_ignores=[]), filename, "exec"), env)
    data = {c: [1.] for c in env["core_cols"]}
    data.update({"Real_Yield": [np.nan], "RY_Surge": [False], "NOW": [101.], "MA50": [100.]})
    env["df_bt"] = pd.DataFrame(data)
    exec(compile(ast.Module(body=gate_nodes[1:], type_ignores=[]), filename, "exec"), env)
    obs[filename] = {"real_yield_is_missing": True, "derived_ry_surge": False,
                     "signal_ready": bool(env["df_bt"].signal_ready.iloc[0]),
                     "gate_includes_real_yield": "Real_Yield" in env["core_cols"]}

path = Path(__file__).with_name("gate_edge_verification.json")
path.write_text(json.dumps(obs, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
print(json.dumps(obs, ensure_ascii=True, indent=2, default=str))
