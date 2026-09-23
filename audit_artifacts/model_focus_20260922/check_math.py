"""Read-only model diagnostics; execute selected source AST without entry points."""
import ast
import contextlib
import io
import json
import os
from pathlib import Path
import socket
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))


def deny_network(*args, **kwargs):
    raise RuntimeError("Offline audit: network disabled")


socket.socket.connect = deny_network


def source_class(path):
    tree = ast.parse((ROOT / path).read_text(encoding="utf-8-sig"))
    return next(node for node in tree.body if isinstance(node, ast.ClassDef))


def execute(nodes, env):
    exec(compile(ast.Module(body=nodes, type_ignores=[]), "source_extract", "exec"), env)


observations = {}
micro = source_class("micro_bubble_radar.py")
compute = next(node for node in micro.body if getattr(node, "name", "") == "compute_all_dimensions")
lppls_nodes = [node for node in compute.body if 77 <= node.lineno <= 113]
env = {"np": np, "pd": pd, "ticker": "IGV",
       "df": pd.DataFrame({"IGV": 100 * np.exp(0.001 * np.arange(131))})}
execute(lppls_nodes, env)
observations["constant_exponential_growth"] = {
    "daily_log_return": 0.001,
    "lppls_r2": float(env["df"]["LPPLS_R2"].iloc[-1]),
    "log_linear_baseline_r2": 1.0,
}

market = pd.read_csv(ROOT / "market_data_local.csv")
observations["breadth"] = {}
for symbol, filename, how in [("IGV", "igv_constituents_local.csv", "inner"),
                              ("SMH", "smh_constituents_local.csv", "left")]:
    constituents = pd.read_csv(ROOT / filename)
    cols = [c for c in constituents if c != "date"]
    df = market.merge(constituents, on="date", how=how).sort_values("date")
    prices = df[cols].ffill() if symbol == "SMH" else df[cols]
    ma = prices.rolling(50, min_periods=20).mean()
    above = prices > ma
    valid = prices.notna() & ma.notna()
    old = above.sum(axis=1) / above.notna().sum(axis=1)
    corrected = (above & valid).sum(axis=1) / valid.sum(axis=1).replace(0, np.nan)
    delta = corrected - old
    comparable = corrected.notna()
    affected = comparable & (delta.abs() > 1e-10)
    idx = delta.idxmax()
    observations["breadth"][symbol] = {
        "comparable_dates": int(comparable.sum()), "changed_dates": int(affected.sum()),
        "max_difference_percentage_points": float(delta.max() * 100),
        "example": {"date": df.loc[idx, "date"], "old": float(old.loc[idx]),
                    "valid_only": float(corrected.loc[idx]), "valid_count": int(valid.loc[idx].sum()),
                    "total_count": len(cols)},
    }
    live_window = df["date"] >= ("2012-01-01" if symbol == "IGV" else "2009-01-01")
    observations["breadth"][symbol]["changed_dates_in_backtest_window"] = int((affected & live_window).sum())
    observations["breadth"][symbol]["max_difference_pp_in_backtest_window"] = float(delta[live_window].max() * 100)

observations["macro_gap"] = {}
for ticker in ["QQQ", "SPY"]:
    price, credit = market[ticker], market["HYG"]
    y = (price - price.rolling(200).mean()) / (price.rolling(200).std() + 1e-8)
    x = (credit - credit.rolling(200).mean()) / (credit.rolling(200).std() + 1e-8)
    beta = (y.rolling(252).cov(x) / (x.rolling(252).var() + 1e-8)).clip(-2, 2)
    alpha = y.rolling(252).mean() - beta * x.rolling(252).mean()
    gap = y - beta * x
    upper = gap.expanding(min_periods=20).quantile(.85)
    observations["macro_gap"][ticker] = {
        "nonpositive_upper_dates": int((upper <= 0).sum()),
        "minimum_upper": float(upper.min()),
        "omitted_intercept_median_abs": float(alpha.abs().median()),
        "omitted_intercept_max_abs": float(alpha.abs().max()),
        "nonpositive_upper_dates_since_2009": int(((upper <= 0) & (market["date"] >= "2009-01-01")).sum()),
        "nonpositive_upper_first_date": market.loc[upper <= 0, "date"].iloc[0] if (upper <= 0).any() else None,
        "nonpositive_upper_last_date": market.loc[upper <= 0, "date"].iloc[-1] if (upper <= 0).any() else None,
    }
observations["signed_threshold_counterexample"] = {
    "gap": -2, "gap_upper": -1, "score": float(np.clip(-2 / -1 * 15, 0, 30))}

now = source_class("now_reflexivity_radar.py")
methods = [node for node in now.body if getattr(node, "name", "") in
           ["__init__", "load_and_preprocess", "compute_all_dimensions"]]
now.body = methods
env = {"pd": pd, "np": np, "os": os, "BASE_DIR": str(ROOT)}
execute([now], env)
with contextlib.redirect_stdout(io.StringIO()):
    model = env["NOWReflexivityRadar"]()
    model.load_and_preprocess()
    df = model.compute_all_dimensions()
df_bt = df[df["date"] >= "2013-06-01"].copy().reset_index(drop=True)
original = source_class("now_reflexivity_radar.py")
backtest = next(node for node in original.body if getattr(node, "name", "") == "run_backtest")
conditions = [node for node in backtest.body if 255 <= node.lineno <= 277]
env = {"df_bt": df_bt}
execute(conditions, env)
suppressed = env["cond_bear"] & env["recently_crashed"]
observations["now_crisis_suppression"] = {
    "bear_condition_dates": int(env["cond_bear"].sum()),
    "suppressed_signal_dates": int(suppressed.sum()),
    "examples": df_bt.loc[suppressed, "date"].dt.strftime("%Y-%m-%d").head(8).tolist(),
    "note": "Condition dates, not unique trades or confirmed held-position exits.",
}
observations["now_price_factor_spearman"] = df[["Score_Dim1_Pos", "Score_Dim2_Vel", "Score_Dim3_Lyapunov"]].corr(method="spearman").to_dict()
observations["now_capital_score"] = {
    "min": float(df["Score_Dim4_Capital"].min()),
    "max": float(df["Score_Dim4_Capital"].max()),
}
rank_node = next(node for node in methods[-1].body if getattr(node, "name", "") == "expanding_rank")
import bisect
env = {"np": np, "pd": pd, "bisect": bisect}
execute([rank_node], env)
observations["constant_series_rank"] = float(env["expanding_rank"](pd.Series(np.zeros(200))).iloc[-1])
out = Path(__file__).with_name("math_observations.json")
out.write_text(json.dumps(observations, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(observations, ensure_ascii=False, indent=2))
