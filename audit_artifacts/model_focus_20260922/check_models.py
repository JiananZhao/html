"""Offline model-focused audit. No production state or data are written."""
import ast
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import socket
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))


def deny_network(*args, **kwargs):
    raise RuntimeError("Audit network disabled")


socket.socket.connect = deny_network
import numpy as np
import pandas as pd
from shared_executor import SharedExecutor
from true_accounting import UnitizedAccount
from reflexivity_interactive_chart import run_reflexivity_simulation

stdout_refs = [sys.stdout]
import energy_bubble_radar as energy
stdout_refs.append(sys.stdout)
import now_reflexivity_radar as now
stdout_refs.append(sys.stdout)
import micro_bubble_radar as micro
stdout_refs.append(sys.stdout)
import smh_bubble_radar as smh
stdout_refs.append(sys.stdout)

obs = {}


def energy_run(df, folder):
    folder.mkdir(exist_ok=True)
    previous = Path.cwd()
    try:
        os.chdir(folder)
        with contextlib.redirect_stdout(io.StringIO()):
            return energy.run_brokerage_backtest(df)
    finally:
        os.chdir(previous)


with tempfile.TemporaryDirectory(prefix="model_focus_") as tmp:
    temp = Path(tmp)
    cached = pd.read_csv(ROOT / "energy_radar_local.csv")
    try:
        energy_run(cached, temp / "actual_energy")
        obs["actual_energy_entry"] = "PASS"
    except Exception as exc:
        obs["actual_energy_entry"] = f"{type(exc).__name__}: {exc}"
    frame = pd.DataFrame({
        "date": ["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"],
        "XLE": [100.0, 100.0, 110.0, 80.0], "OIL": [80.0] * 4,
        "Composite_Radar_Score": [80.0] * 4,
        "Cond_Bubble": [False, True, False, False],
        "Cond_Bear": False, "Cond_Panic": False,
        "Above_MA20_Conf": False, "Above_MA50_Conf": False,
        "Sell_Signal": [False, True, False, False],
    })
    # Explicit diagnostic-only alias to reach bugs hidden behind missing 'close'.
    frame["close"] = frame.XLE
    full, _ = energy_run(frame, temp / "alias_full")
    try:
        energy_run(frame, temp / "alias_full")
        obs["alias_noop"] = "PASS"
    except Exception as exc:
        obs["alias_noop"] = f"{type(exc).__name__}: {exc}"
    energy_run(frame.iloc[:2].copy(), temp / "changed_signal")
    revised = frame.copy()
    revised["Cond_Bubble"] = False
    revised["Sell_Signal"] = False
    continued, _ = energy_run(revised, temp / "changed_signal")
    fresh, _ = energy_run(revised, temp / "changed_signal_fresh")
    obs["signal_revision_not_hashed"] = {
        "resumed_directions": [f["direction"] for f in continued.fills],
        "fresh_directions": [f["direction"] for f in fresh.fills],
        "resumed_equity": float(continued.metrics["strat_final"]),
        "fresh_equity": float(fresh.metrics["strat_final"]),
    }
    energy_run(frame.iloc[:2].copy(), temp / "price_revision")
    changed_price = frame.copy()
    changed_price.loc[0, ["XLE", "close"]] = 90.0
    try:
        energy_run(changed_price, temp / "price_revision")
        obs["invalid_hash_replay"] = "PASS"
    except Exception as exc:
        obs["invalid_hash_replay"] = f"{type(exc).__name__}: {exc}"

    log = io.StringIO()
    totals = {"run": 0, "failures": 0, "errors": 0}
    for path in sorted((ROOT / "tests").glob("test_*.py")):
        spec = importlib.util.spec_from_file_location(path.stem, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        os.chdir(ROOT if "baseline" in path.stem else temp)
        with contextlib.redirect_stdout(log):
            result = unittest.TextTestRunner(stream=log, verbosity=2).run(
                unittest.defaultTestLoader.loadTestsFromModule(module))
        totals["run"] += result.testsRun
        totals["failures"] += len(result.failures)
        totals["errors"] += len(result.errors)
    os.chdir(ROOT)
    obs["tests"] = totals
    (OUT / "tests.txt").write_text(log.getvalue(), encoding="utf-8")

dt = pd.Timestamp("2024-01-02")
ex = SharedExecutor(UnitizedAccount(1000, dt))
ex.submit_order(1.0, "buy", dt)
ex.submit_order(1.0, "buy", dt)
ex.step(pd.Timestamp("2024-01-03"), 100.0, 100.0)
obs["repeat_signal_cancels_order"] = {
    "pending": len(ex.pending_orders), "fills": len(ex.fills),
    "order_statuses": [o["status"] for o in ex.orders_history],
    "shares": ex.acc.shares,
}

market = pd.read_csv(ROOT / "market_data_local.csv")
macro = run_reflexivity_simulation(market, ticker="QQQ")
date = "2020-12-01"
missing = market.copy()
missing.loc[missing.date == date, "HYG"] = np.nan
macro_missing = run_reflexivity_simulation(missing, ticker="QQQ")
base_dates = set(pd.to_datetime(macro.daily_accounts.date))
bad_dates = set(pd.to_datetime(macro_missing.daily_accounts.date))
obs["macro_missing_factor"] = {
    "missing_factor_date": date,
    "session_existed_before": pd.Timestamp(date) in base_dates,
    "session_exists_after": pd.Timestamp(date) in bad_dates,
    "removed_account_sessions": len(base_dates - bad_dates),
}

for symbol, cls in [("IGV", micro.MicroBubbleRadar), ("SMH", smh.SMHBubbleRadar)]:
    loader = cls()
    loader.market_data_path = str(ROOT / "market_data_local.csv")
    loader.constituents_path = str(ROOT / (symbol.lower() + "_constituents_local.csv"))
    loader.load_and_preprocess()
    source = loader.df.iloc[:700].copy()
    results = []
    for kind in ["full", "prefix", "future_mutation"]:
        radar = cls()
        radar.const_cols = loader.const_cols
        radar.df = source.iloc[:500].copy() if kind == "prefix" else source.copy()
        if kind == "future_mutation":
            radar.df.loc[radar.df.index[500:], symbol] *= 2
        radar.compute_all_dimensions()
        results.append(radar.df)
    pd.testing.assert_frame_equal(results[0].iloc[:500], results[1], atol=1e-10, rtol=1e-10)
    pd.testing.assert_frame_equal(results[0].iloc[:500], results[2].iloc[:500], atol=1e-10, rtol=1e-10)
    obs[symbol + "_causality"] = {"result": "PASS", "first_trend_index": int(results[0].Log_Trend.first_valid_index())}

sec = pd.read_csv(ROOT / "now_sec_fundamentals_local.csv")
tree = ast.parse((ROOT / "scripts/fetch_now_fundamentals_free.py").read_text(encoding="utf-8-sig"))
quarters_node = next(n for n in ast.walk(tree) if isinstance(n, ast.Assign)
                     and isinstance(n.targets[0], ast.Name) and n.targets[0].id == "quarters")
quarters = ast.literal_eval(quarters_node.value)
columns = ["date", "diluted_shares_m", "sbc_pct_rev", "insider_net_flow_m"]
def generated_fundamentals(nodes):
    q = pd.DataFrame(nodes, columns=columns)
    q.date = pd.to_datetime(q.date)
    daily = pd.DataFrame({"date": pd.date_range("2010-01-01", "2026-09-18")}).merge(q, on="date", how="left")
    daily[columns[1:]] = daily[columns[1:]].interpolate().bfill().ffill()
    daily.date = daily.date.dt.strftime("%Y-%m-%d")
    return daily
generated = generated_fundamentals(quarters)
joined = sec.merge(generated, on="date", suffixes=("_actual", "_generated"))
obs["fundamentals_source_match"] = {
    "matched_rows": len(joined),
    "max_abs_differences": {c: float((joined[c+"_actual"]-joined[c+"_generated"]).abs().max()) for c in columns[1:]},
}
modified = [tuple([r[0], r[1], r[2], 0.0]) if r[0] == "2020-12-31" else r for r in quarters]
future_changed = generated_fundamentals(modified)
probe_date = "2020-09-30"
obs["fundamentals_future_node_change"] = {
    "future_node": "2020-12-31", "historical_date": probe_date,
    "original_insider_value": float(generated.loc[generated.date == probe_date, "insider_net_flow_m"].iloc[0]),
    "after_future_node_change": float(future_changed.loc[future_changed.date == probe_date, "insider_net_flow_m"].iloc[0]),
}
(OUT / "observations.json").write_text(json.dumps(obs, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(obs, ensure_ascii=False, indent=2))
