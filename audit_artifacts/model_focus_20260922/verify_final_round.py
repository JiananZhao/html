"""Audit refined Phase 1 using production AST and offline macro simulation."""
import ast
import bisect
import json
from pathlib import Path
import socket
import sys
from types import SimpleNamespace

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
OUT = Path(__file__).resolve().parent


def no_network(*args, **kwargs):
    raise RuntimeError("Network disabled during audit")


socket.socket.connect = no_network


def read_tree(filename):
    return ast.parse((ROOT / filename).read_text(encoding="utf-8-sig"))


def execute(nodes, env):
    exec(compile(ast.Module(body=nodes, type_ignores=[]), "source_ast", "exec"), env)


obs = {}
for filename in ["now_reflexivity_radar.py", "single_stock_reflexivity_radar.py", "reflexivity_engine.py"]:
    node = next(n for n in ast.walk(read_tree(filename)) if isinstance(n, ast.FunctionDef) and n.name == "expanding_rank")
    env = {"pd": pd, "np": np, "bisect": bisect}
    execute([node], env)
    result = env["expanding_rank"](pd.Series([0.] * 200))
    assert result.iloc[-1] == 50
    assert result.iloc[:99].isna().all()
    obs[filename] = {"constant_rank": float(result.iloc[-1]), "warmup_nan": True}

for filename in ["reflexivity_interactive_chart.py", "daily_market_monitor.py", "export_multi_asset_deliverables.py", "宏观反身性阿尔法模型_模型A_Plus.py"]:
    nodes = list(ast.walk(read_tree(filename)))
    rank = next(n for n in nodes if isinstance(n, ast.FunctionDef) and n.name == "mid_rank_pct")
    assignment = next(n for n in nodes if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "gap_score" for t in n.targets))
    env = {"pd": pd, "np": np, "sub": pd.DataFrame({"Gap": [-100.] * 200 + [np.nan]})}
    execute([rank, assignment], env)
    s = env["gap_score"]
    assert s.iloc[199] == 15
    assert s.iloc[:59].isna().all()
    assert pd.isna(s.iloc[-1])
    obs[filename] = {"constant_gap_component": float(s.iloc[199]), "warmup_and_current_missing_nan": True}

smh_tree = read_tree("smh_bubble_radar.py")
method = next(n for n in ast.walk(smh_tree) if isinstance(n, ast.FunctionDef) and n.name == "compute_all_dimensions")
wanted = {"is_valid", "above", "df['Breadth_Valid_Count']", "df['Breadth_Coverage']", "df['Breadth_50']"}
nodes = [n for n in method.body if isinstance(n, ast.Assign) and ast.unparse(n.targets[0]) in wanted]
raw = pd.DataFrame({"A": np.arange(1., 61.), "B": np.arange(1., 61.)})
raw.loc[59, "B"] = np.nan
env = {"pd": pd, "np": np, "df": raw.ffill(), "self": SimpleNamespace(const_cols=["A", "B"], fresh_mask=raw.notna())}
execute(nodes, env)
assert env["df"]["Breadth_Valid_Count"].iloc[-1] == 1
obs["smh_current_missing_excluded"] = True

from reflexivity_interactive_chart import run_reflexivity_simulation
market = pd.read_csv(ROOT / "market_data_local.csv")
obs["full_macro_calls"] = {}
for ticker in ["QQQ", "SPY"]:
    try:
        result = run_reflexivity_simulation(market, ticker=ticker)
        obs["full_macro_calls"][ticker] = {"status": "PASS", "rows": len(result.features)}
    except Exception as exc:
        info = {"error_type": type(exc).__name__, "error": str(exc)}
        tb = exc.__traceback__
        while tb:
            if tb.tb_frame.f_code.co_name == "run_reflexivity_simulation":
                local = tb.tb_frame.f_locals
                info.update({"line": tb.tb_lineno, "date": str(local.get("dt")), "pos": local.get("pos"), "signal_ready": bool(local.get("signal_ready"))})
            tb = tb.tb_next
        obs["full_macro_calls"][ticker] = info

# Run only the unchanged feature-building section, ending before accounts exist.
function = next(n for n in read_tree("reflexivity_interactive_chart.py").body if isinstance(n, ast.FunctionDef) and n.name == "run_reflexivity_simulation")
feature_nodes = [n for n in function.body if n.lineno <= 102]


def features(data):
    env = {"pd": pd, "np": np, "df_raw": data, "ticker": "QQQ"}
    execute(feature_nodes, env)
    return env["sub"]

base = features(market)
target = base.loc[base["signal_ready"] & (base["date"] >= "2020-01-01"), "date"].iloc[0]
damaged = market.copy()
damaged.loc[pd.to_datetime(damaged["date"]) == target, "NFCI"] = np.nan
changed = features(damaged)
row = changed.loc[changed["date"] == target].iloc[0]
obs["missing_nfci_gate"] = {"date": str(target), "nfci_is_nan": bool(pd.isna(row["NFCI"])), "signal_ready": bool(row["signal_ready"])}

short = market.iloc[:100].copy()
short["date"] = pd.bdate_range("2020-01-01", periods=len(short))
result = run_reflexivity_simulation(short)
obs["warmup_trading"] = {"ready_days": int(result.features["signal_ready"].sum()), "orders": len(result.orders), "fills": len(result.fills), "first_fill": result.fills[0] if result.fills else None}

# Execute actual decision block with controlled states, without an account or price download.
outer_loop = next(n for n in function.body if isinstance(n, ast.For))
decision = next(n for n in outer_loop.body if isinstance(n, ast.If) and isinstance(n.test, ast.Name) and n.test.id == "signal_ready")


class Recorder:
    last_sell_p = 100.

    def __init__(self):
        self.orders = []

    def submit_order(self, *args):
        self.orders.append(args)


def decision_case(regime, **extra):
    ex = Recorder()
    sub = pd.DataFrame({"Sell_Signal": [False], "Cond_Panic": [False], "Above_MA20_Conf": [True], "Above_MA50_Conf": [True], "HYG": [110.], "HYG_MA200": [100.]})
    env = {"signal_ready": True, "pos": 0., "exit_regime": regime, "sub": sub, "i": 0, "gap": 2., "gap_med": 1., "p_val": 103., "allow_breakout": False, "executor": ex, "dt": pd.Timestamp("2020-01-02")}
    env.update(extra)
    execute([decision], env)
    return {"orders": [(float(o[0]), o[1], str(o[2])) for o in ex.orders], "pos": env["pos"]}

obs["bear_healed_decision"] = decision_case("BEAR")
obs["breakout_disabled_decision"] = decision_case("BUBBLE")
obs["cache_inventory"] = {"engine_state_exists": (ROOT / "engine_state").exists(), "states_exists": (ROOT / ".states").exists(), "states_files": [str(p.relative_to(ROOT)) for p in (ROOT / ".states").rglob("*") if p.is_file()]}
(OUT / "final_round_verification.json").write_text(json.dumps(obs, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
print(json.dumps(obs, ensure_ascii=True, indent=2, default=str))
