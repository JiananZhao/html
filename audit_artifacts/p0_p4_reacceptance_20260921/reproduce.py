"""Offline acceptance probes; production data and state are never modified."""
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
    raise RuntimeError("Acceptance audit: network disabled")


socket.socket.connect = deny_network
import numpy as np
import pandas as pd
from true_accounting import UnitizedAccount
from shared_executor import SharedExecutor
from core_engine.export_utils import generate_trade_pairs
from core_engine.state_manager import StateManager

# Retain stdout wrappers: radar modules replace sys.stdout at import time.
stdout_refs = [sys.stdout]
import energy_bubble_radar as energy
stdout_refs.append(sys.stdout)
from now_reflexivity_radar import NOWReflexivityRadar
stdout_refs.append(sys.stdout)

observations = {}


def energy_frame():
    return pd.DataFrame({
        "date": ["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"],
        "XLE": [100.0, 100.0, 110.0, 80.0], "OIL": [80.0] * 4,
        "Composite_Radar_Score": [80.0] * 4,
        "Cond_Bubble": [False, True, False, False],
        "Cond_Bear": [False] * 4, "Cond_Panic": [False] * 4,
        "Above_MA20_Conf": [False] * 4,
        "Above_MA50_Conf": [False] * 4,
        "Sell_Signal": [False, True, False, False],
    })


def run_energy(frame, directory, **kwargs):
    directory.mkdir(exist_ok=True)
    previous = Path.cwd()
    try:
        os.chdir(directory)
        with contextlib.redirect_stdout(io.StringIO()):
            return energy.run_brokerage_backtest(frame, **kwargs)
    finally:
        os.chdir(previous)


with tempfile.TemporaryDirectory(prefix="quant_acceptance_") as tmp:
    temp = Path(tmp)
    frame = energy_frame()
    full, _ = run_energy(frame, temp / "full")
    run_energy(frame.iloc[:2].copy(), temp / "split")
    resumed, _ = run_energy(frame, temp / "split")
    observations["split_vs_full"] = {
        "full_equity": float(full.metrics["strat_final"]),
        "resumed_equity": float(resumed.metrics["strat_final"]),
        "full_fills": len(full.fills), "resumed_fills": len(resumed.fills),
        "resumed_duplicate_order_ids": int(pd.DataFrame(resumed.orders).order_id.duplicated().sum()),
        "resumed_cashflow_rows": len(resumed.cashflows),
        "full_cashflow_rows": len(full.cashflows),
    }
    before_count = len(resumed.orders)
    noop, changed = run_energy(frame, temp / "split")
    observations["noop_idempotence"] = {
        "is_updated": changed, "orders_before": before_count,
        "orders_after": len(noop.orders),
    }
    revised = frame.copy()
    revised.loc[3, "XLE"] = 40.0
    cached_revision, changed = run_energy(revised, temp / "split", dca_monthly=2000)
    fresh_revision, _ = run_energy(revised, temp / "fresh_revision", dca_monthly=2000)
    observations["history_and_config_change"] = {
        "accepted_as_unchanged": not changed,
        "cached_total_invested": float(cached_revision.metrics["total_invested"]),
        "fresh_total_invested": float(fresh_revision.metrics["total_invested"]),
        "cached_equity": float(cached_revision.metrics["strat_final"]),
        "fresh_equity": float(fresh_revision.metrics["strat_final"]),
    }
    revised_only = frame.copy()
    revised_only.loc[2, "XLE"] = 200.0
    cached_only, revision_changed = run_energy(revised_only, temp / "full")
    fresh_only, _ = run_energy(revised_only, temp / "history_only_fresh")
    observations["history_only_revision"] = {
        "accepted_as_unchanged": not revision_changed,
        "revised_execution_day_price": float(cached_only.features.XLE.iloc[2]),
        "cached_strat_equity": float(cached_only.metrics["strat_final"]),
        "fresh_strat_equity": float(fresh_only.metrics["strat_final"]),
    }
    cached_config, config_changed = run_energy(frame, temp / "full", dca_monthly=2000)
    fresh_config, _ = run_energy(frame, temp / "config_only_fresh", dca_monthly=2000)
    observations["config_only_change"] = {
        "accepted_as_unchanged": not config_changed,
        "cached_invested": float(cached_config.metrics["total_invested"]),
        "fresh_invested": float(fresh_config.metrics["total_invested"]),
        "cached_equity": float(cached_config.metrics["strat_final"]),
        "fresh_equity": float(fresh_config.metrics["strat_final"]),
    }
    run_energy(frame.iloc[:2].copy(), temp / "interrupted")
    original_save = StateManager.save_checkpoint
    def fail_save(*args, **kwargs):
        raise RuntimeError("simulated crash after CSV writes, before checkpoint")
    StateManager.save_checkpoint = fail_save
    try:
        run_energy(frame, temp / "interrupted")
    except RuntimeError:
        pass
    finally:
        StateManager.save_checkpoint = original_save
    retry, _ = run_energy(frame, temp / "interrupted")
    observations["interrupted_publication"] = {
        "daily_rows": len(retry.daily_accounts),
        "expected_daily_rows": len(frame) * 2,
        "duplicate_date_type_rows": int(retry.daily_accounts.duplicated(["date", "type"]).sum()),
    }

    neutral = energy_frame()
    neutral["Cond_Bubble"] = False
    neutral["Sell_Signal"] = False
    neutral1, _ = run_energy(neutral, temp / "neutral_noop")
    neutral2, updated = run_energy(neutral, temp / "neutral_noop")
    observations["neutral_noop"] = {
        "is_updated": updated, "orders_before": len(neutral1.orders),
        "orders_after": len(neutral2.orders),
    }

    # Run existing tests. State-manager test directories are isolated under temp.
    suite_log = io.StringIO()
    totals = {"run": 0, "failures": 0, "errors": 0}
    previous = Path.cwd()
    for path in sorted((ROOT / "tests").glob("test_*.py")):
        spec = importlib.util.spec_from_file_location(path.stem, path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        os.chdir(ROOT if "baseline" in path.stem else temp)
        with contextlib.redirect_stdout(suite_log):
            result = unittest.TextTestRunner(stream=suite_log, verbosity=2).run(
                unittest.defaultTestLoader.loadTestsFromModule(module)
            )
        totals["run"] += result.testsRun
        totals["failures"] += len(result.failures)
        totals["errors"] += len(result.errors)
    os.chdir(previous)
    observations["existing_tests"] = totals
    (OUT / "existing_tests.txt").write_text(suite_log.getvalue(), encoding="utf-8")

    # Execute the newly advertised smoke test in a disposable directory.
    spec = importlib.util.spec_from_file_location("new_smoke", ROOT / "test_incremental_engine.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    smoke_log = io.StringIO()
    os.chdir(temp)
    with contextlib.redirect_stdout(smoke_log):
        module.test_missing_price_and_incremental()
    os.chdir(previous)
    (OUT / "advertised_smoke_test.txt").write_text(smoke_log.getvalue(), encoding="utf-8")

dates = pd.to_datetime(["2024-01-02", "2024-01-03", "2024-01-04"])
acc = UnitizedAccount(1000, dates[0])
ex = SharedExecutor(acc)
ex.submit_order(1.0, "close signal", dates[0])
ex.step(dates[0], 100.0, 100.0)
observations["same_day_guard"] = {
    "fill_count": len(ex.fills), "pending_count": len(ex.pending_orders), "shares": acc.shares,
}
acc = UnitizedAccount()
ex = SharedExecutor(acc)
ex.step(dates[0], 100.0, 100.0, 1000)
ex.step(dates[0], 100.0, 100.0, 1000)
observations["repeat_day_dca"] = {"cash": acc.cash, "flow_count": len(ex.cashflows)}

acc = UnitizedAccount(1000, dates[0])
ex = SharedExecutor(acc, execution_mode="NEXT_OPEN")
ex.step(dates[0], 100.0, 100.0)
ex.submit_order(1.0, "buy", dates[0])
ex.step(dates[1], 100.0, 110.0, 1000)
observations["next_open_dca_order"] = {
    "shares": acc.shares, "cash": acc.cash,
    "units": acc.units, "equity": ex.daily_states[-1]["equity"],
    "expected_under_announced_open_deposit_policy": {"shares": 20.0, "cash": 0.0, "units": 2000.0, "equity": 2200.0},
}

acc = UnitizedAccount(1000, dates[0])
ex = SharedExecutor(acc)
ex.step(dates[0], 100.0, 100.0)
ex.step(dates[1], np.nan, np.nan, 500)
state = json.loads(json.dumps(ex.get_state()))
restored = SharedExecutor(UnitizedAccount())
restored.restore_state(state)
restored.step(dates[2], 105.0, 105.0)
observations["pending_cash_resume"] = {
    "cash_after_resume": restored.acc.cash,
    "pending_cash": restored.pending_cash,
    "executor_cashflow_rows": len(restored.cashflows),
    "account_cashflow_rows": len(restored.acc.cash_flows),
}

orders = [
    {"order_id": "s", "status": "CANCELLED", "target": 0.0,
     "submit_dt": "2024-01-02", "actual_dt": None, "reason": "sell"},
    {"order_id": "b", "status": "CANCELLED", "target": 1.0,
     "submit_dt": "2024-01-03", "actual_dt": None, "reason": "buy"},
]
pairs = generate_trade_pairs(orders, [], pd.DataFrame({
    "date": ["2024-01-02", "2024-01-03"], "XLE": [100.0, 80.0],
}), "XLE")
observations["cancelled_orders_pairing"] = {"fills": 0, "reported_pairs": len(pairs)}

# Exercise actual public feature methods on local, model-aligned data.
import micro_bubble_radar as micro
stdout_refs.append(sys.stdout)
import smh_bubble_radar as smh
stdout_refs.append(sys.stdout)
market = pd.read_csv(ROOT / "market_data_local.csv")
trend_results = {}
for symbol, cls in [("IGV", micro.MicroBubbleRadar), ("SMH", smh.SMHBubbleRadar)]:
    loader = cls()
    loader.market_data_path = str(ROOT / "market_data_local.csv")
    loader.constituents_path = str(ROOT / (symbol.lower() + "_constituents_local.csv"))
    loader.load_and_preprocess()
    aligned = loader.df.iloc[:700].copy()
    cut = 500
    computed = []
    for variant in ["full", "prefix", "future_mutated"]:
        radar = cls()
        radar.const_cols = loader.const_cols
        radar.df = aligned.iloc[:cut].copy() if variant == "prefix" else aligned.copy()
        if variant == "future_mutated":
            radar.df.loc[radar.df.index[cut:], symbol] *= 2
        radar.compute_all_dimensions()
        computed.append(radar.df)
    full_df, prefix, mutated = computed
    pd.testing.assert_frame_equal(full_df.iloc[:cut], prefix, check_exact=False, atol=1e-10, rtol=1e-10)
    pd.testing.assert_frame_equal(full_df.iloc[:cut], mutated.iloc[:cut], check_exact=False, atol=1e-10, rtol=1e-10)
    trend_results[symbol] = {
        "public_feature_prefix_and_future_perturbation": "PASS",
        "full_rows": len(full_df), "prefix_rows": len(prefix),
        "first_valid_trend_index": int(full_df.Log_Trend.first_valid_index()),
        "last_prefix_residual": float(prefix.Valuation_Residual.iloc[-1]),
    }
observations["active_trend_prefix_tests"] = trend_results

previous = Path.cwd()
os.chdir(ROOT)
with contextlib.redirect_stdout(io.StringIO()):
    radar = NOWReflexivityRadar()
    radar.load_and_preprocess()
    radar.compute_all_dimensions()
    now_result = radar.run_backtest()
os.chdir(previous)
correct_dd = {}
for kind, group in now_result.daily_accounts.groupby("type"):
    nav = group.unit_nav
    correct_dd[kind] = float((nav / nav.cummax() - 1).min() * 100)
observations["now_performance"] = {
    "reported_metrics": now_result.metrics,
    "unit_nav_drawdowns_pct": correct_dd,
    "capital_from_account_equivalent": 10000 + now_result.metrics["total_injected"],
}
from core_engine.export_utils import export_deliverables
with tempfile.TemporaryDirectory(prefix="quant_export_acceptance_") as tmp:
    os.chdir(tmp)
    with contextlib.redirect_stdout(io.StringIO()):
        export_deliverables(now_result, "ServiceNow (NOW)")
    overview = pd.read_excel(next(Path(tmp).glob("*.xlsx")), sheet_name=0)
    manifest = json.loads((Path(tmp) / "now_manifest.json").read_text(encoding="utf-8"))
    observations["now_export"] = {
        "overview": overview.to_dict("records"),
        "manifest_keys": sorted(manifest),
    }
    os.chdir(previous)

from reflexivity_interactive_chart import run_reflexivity_simulation
macro_results = {}
for ticker in ["QQQ", "SPY"]:
    macro = run_reflexivity_simulation(market, ticker=ticker)
    try:
        macro.validate()
        validation = "PASS"
    except ValueError as exc:
        validation = str(exc)
    macro_results[ticker] = {
        "contract_validation": validation,
        "account_types": macro.daily_accounts.type.unique().tolist(),
        "metrics_keys": sorted(macro.metrics),
        "fills": len(macro.fills),
    }
observations["macro_contracts"] = macro_results
acc = UnitizedAccount(1000, dates[0])
ex = SharedExecutor(acc, execution_mode="NEXT_OPEN")
ex.submit_order(1.0, "first session open buy", dates[0])
ex.step(dates[1], 100.0, np.nan)
observations["first_open_close_missing"] = {
    "shares": acc.shares, "cash": acc.cash,
    "reported_equity": ex.daily_states[-1]["equity"],
    "known_open_value": acc.shares * 100.0 + acc.cash,
}

(OUT / "observations.json").write_text(json.dumps(observations, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(observations, ensure_ascii=False, indent=2))
