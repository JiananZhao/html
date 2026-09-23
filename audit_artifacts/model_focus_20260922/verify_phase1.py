"""Offline verification of the changed scoring expressions, not a portfolio backtest."""
import ast
import bisect
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
results = {}


def tree(filename):
    return ast.parse((ROOT / filename).read_text(encoding="utf-8-sig"))


def execute(nodes, env):
    exec(compile(ast.Module(body=nodes, type_ignores=[]), "production_ast", "exec"), env)


for filename in ["now_reflexivity_radar.py", "single_stock_reflexivity_radar.py", "reflexivity_engine.py"]:
    node = next(n for n in ast.walk(tree(filename)) if isinstance(n, ast.FunctionDef) and n.name == "expanding_rank")
    env = {"np": np, "pd": pd, "bisect": bisect}
    execute([node], env)
    rank = env["expanding_rank"]
    constant = rank(pd.Series(np.zeros(200)))
    assert constant.iloc[-1] == 50.0
    assert constant.iloc[:99].isna().all()
    sample = pd.Series([0., 1., 1., np.nan, -1., 0.] * 40)
    full = rank(sample)
    pd.testing.assert_series_equal(full.iloc[:160], rank(sample.iloc[:160]))
    changed = sample.copy()
    changed.iloc[160:] = 10000
    pd.testing.assert_series_equal(full.iloc[:160], rank(changed).iloc[:160])
    results[filename] = {"constant_200": float(constant.iloc[-1]), "warmup_prefix_future_tests": "PASS"}

gap_files = ["reflexivity_interactive_chart.py", "export_multi_asset_deliverables.py", "daily_market_monitor.py", "宏观反身性阿尔法模型_模型A_Plus.py"]
for filename in gap_files:
    node = next(n for n in ast.walk(tree(filename)) if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "gap_score" for t in n.targets))

    def gap_score(s):
        env = {"pd": pd, "np": np, "sub": pd.DataFrame({"Gap": s})}
        execute([node], env)
        return env["gap_score"]

    constant = gap_score(pd.Series([-100.] * 200))
    increasing = gap_score(pd.Series(np.linspace(-200, -100, 200)))
    falling = gap_score(pd.Series(np.linspace(-100, -200, 200)))
    pd.testing.assert_series_equal(increasing.iloc[:160], gap_score(pd.Series(np.linspace(-200, -100, 200)[:160])))
    assert increasing.between(0, 30).all()
    results[filename] = {"constant_negative_score": float(constant.iloc[-1]),
                         "negative_highest_score": float(increasing.iloc[-1]),
                         "negative_lowest_score": float(falling.iloc[-1]),
                         "warmup_value": float(constant.iloc[0]),
                         "prefix_and_range_tests": "PASS"}

for filename in ["micro_bubble_radar.py", "smh_bubble_radar.py"]:
    method = next(n for n in ast.walk(tree(filename)) if isinstance(n, ast.FunctionDef) and n.name == "compute_all_dimensions")
    wanted = {"is_valid", "above", "df['Breadth_Valid_Count']", "df['Breadth_Coverage']", "df['Breadth_50']"}
    nodes = [n for n in method.body if isinstance(n, ast.Assign) and ast.unparse(n.targets[0]) in wanted]
    assert len(nodes) == 5

    def breadth(df):
        env = {"df": df.copy(), "np": np, "pd": pd, "self": SimpleNamespace(const_cols=["A", "B"])}
        execute(nodes, env)
        return env["df"]

    df = pd.DataFrame({"A": np.arange(1., 61.), "B": [np.nan] * 60})
    output = breadth(df)
    assert output["Breadth_50"].iloc[-1] == 1
    assert output["Breadth_Valid_Count"].iloc[-1] == 1
    assert output["Breadth_Coverage"].iloc[-1] == .5
    assert output["Breadth_50"].iloc[:19].isna().all()
    pd.testing.assert_frame_equal(output.iloc[:40], breadth(df.iloc[:40]))
    missing = pd.DataFrame({"A": np.arange(1., 61.), "B": np.arange(1., 61.)})
    missing.loc[59, "B"] = np.nan
    raw_count = int(breadth(missing)["Breadth_Valid_Count"].iloc[-1])
    filled_count = int(breadth(missing.ffill())["Breadth_Valid_Count"].iloc[-1])
    results[filename] = {"valid_only_breadth": 1., "coverage": .5,
                         "raw_missing_valid_count": raw_count, "ffilled_missing_valid_count": filled_count,
                         "denominator_warmup_prefix_tests": "PASS"}

(OUT / "phase1_verification.json").write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(results, ensure_ascii=True, indent=2))
