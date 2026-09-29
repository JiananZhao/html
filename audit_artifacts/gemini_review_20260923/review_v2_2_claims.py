"""Independent, offline v2.2 audit. Submitted source/data are never rewritten."""
from pathlib import Path
import contextlib
import hashlib
import io
import json
import sys
from unittest.mock import patch

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from audit_artifacts.gemini_review_20260923.v2_2_remediation import (
    run_factorial_experiment_v2_2 as exp,
    test_experiment_engine_v2_2 as tests,
    verify_claims_v2_2 as verifier,
)
from audit_artifacts.gemini_review_20260923 import run_factorial_experiment as old
from reflexivity_engine import run_universal_reflexivity_radar

OUT = Path(__file__).resolve().parent / 'v2_2_independent_review'
SUBMITTED = Path(exp.__file__).parent
COMBOS = [(False, False, False), (True, False, False),
          (False, True, False), (False, False, True),
          (True, True, False), (True, False, True),
          (False, True, True), (True, True, True)]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def json_safe(value):
    """Normalize NumPy scalars and missing metrics to strict JSON values."""
    if isinstance(value, dict):
        return {k: json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    if isinstance(value, np.generic):
        return json_safe(value.item())
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def snapshot():
    roots = [SUBMITTED, SUBMITTED.parent / 'v2_1_remediation']
    files = [p for folder in roots for p in folder.rglob('*')
             if p.is_file() and '__pycache__' not in p.parts]
    files += [ROOT / p for p in ['reflexivity_engine.py',
                                'now_reflexivity_radar.py',
                                'shared_executor.py', 'true_accounting.py']]
    return {str(p.relative_to(ROOT)): digest(p) for p in files}


def base(n=35):
    case = tests.TestFactorialExperimentEngineV22()
    case.setUp()
    return case.df_base.iloc[:n].copy()


def main():
    OUT.mkdir(exist_ok=True)
    rerun = OUT / 'rerun'
    rerun.mkdir(exist_ok=True)
    before = snapshot()
    evidence = {}
    manifest = json.loads((SUBMITTED / 'manifest_v2_2.json').read_text())
    evidence['input_manifest_matches'] = {
        p: digest(ROOT / p) == record['sha256'] for p, record in manifest.items()
    }

    # Run the submitted program and verifier, redirecting all their outputs.
    log = io.StringIO()
    with contextlib.redirect_stdout(log), patch.object(exp, 'OUT_DIR', rerun):
        exp.main()
    with contextlib.redirect_stdout(log), patch.object(verifier, 'OUT_DIR', rerun):
        verifier.main()
    (OUT / 'submitted_run.log').write_text(log.getvalue(), encoding='utf-8')
    matches = {}
    for p in SUBMITTED.glob('*.csv'):
        if p.stat().st_size <= 3:
            matches[p.name] = (rerun / p.name).read_bytes() == p.read_bytes()
        else:
            matches[p.name] = pd.read_csv(p).equals(pd.read_csv(rerun / p.name))
    evidence['all_submitted_csvs_reproduced'] = matches
    assert all(matches.values())
    print('SUBMITTED_MAIN_AND_VERIFIER_REPRODUCED', flush=True)

    prices = pd.read_csv(ROOT / 'now_ohlcv_local.csv')
    macro = pd.read_csv(ROOT / 'market_data_local.csv')
    features = exp.prepare_base_features(prices, macro)
    frozen = old.prepare_base_features(prices, macro)
    common = [c for c in frozen.columns if c in features and c != 'date']
    comparison = {}
    for c in common:
        if pd.api.types.is_numeric_dtype(features[c]):
            comparison[c] = {
                'missing_mask_equal': bool(features[c].isna().equals(frozen[c].isna())),
                'max_abs_diff': float((features[c] - frozen[c]).abs().max())
                if features[c].dtype != bool else float((features[c] != frozen[c]).sum()),
            }
    evidence['all_common_numeric_features'] = comparison
    prod = run_universal_reflexivity_radar('NOW', prices, macro)
    evidence['full_history_ready_parity'] = bool(features.signal_ready.equals(prod.signal_ready))
    start = features.loc[features.signal_ready, 'date'].iloc[0]

    # Compare actual main's slice-before-signals path against promised continuity.
    continuity = []
    stop_counterfactual = []
    source = Path(exp.__file__).read_text(encoding='utf-8')
    marker = "exit_mode = 'AFTER_STOP'"
    assert source.count(marker) == 1
    no_cooldown_ns = dict(exp.__dict__)
    exec(compile(source.replace(marker, "exit_mode = 'NONE'"), exp.__file__, 'exec'), no_cooldown_ns)
    for asset in ['NOW', 'QQQ', 'SPY']:
        raw = prices if asset == 'NOW' else macro[['date', asset]].dropna().rename(columns={asset: 'close'})
        full = exp.prepare_base_features(raw, macro)
        warm = full[full.date >= start].copy().reset_index(drop=True)
        csv = pd.read_csv(SUBMITTED / f'factorial_ablation_results_v2_2_{asset.lower()}.csv')
        for idx, (fa, fb, fc) in enumerate(COMBOS):
            cut_sig = exp.generate_signals(warm, fa, fb, fc)
            all_sig = exp.generate_signals(full, fa, fb, fc)
            kept = all_sig[all_sig.date >= start].copy().reset_index(drop=True)
            differences = {
                c: kept.loc[kept[c] != cut_sig[c], 'date'].dt.strftime('%Y-%m-%d').tolist()
                for c in ['Trigger_Panic', 'Trigger_Bubble_Top', 'Trigger_Bear_Top', 'cond_trend']
            }
            fixed = exp.run_execution_simulation(kept, use_factor_a=fa, use_factor_c=fc)
            continuity.append({
                'asset': asset, 'config': f'C{idx}', 'signal_differences': differences,
                'submitted_final': float(csv.iloc[idx]['Strat_Final']),
                'continuous_signals_final': fixed['strat_final'],
                'continuous_first_fill': fixed['strategy_first_fill_dt'],
            })
            if fc:
                cf = no_cooldown_ns['run_execution_simulation'](
                    cut_sig, use_factor_a=fa, use_factor_c=True)
                stop_counterfactual.append({
                    'asset': asset, 'config': f'C{idx}',
                    'submitted_final': float(csv.iloc[idx]['Strat_Final']),
                    'only_remove_added_after_stop_mode_final': cf['strat_final'],
                    'counterfactual_stop_orders': cf['stop_loss_order_count'],
                })
        print('CONTINUITY_AND_STOP_STATE_PROBED', asset, flush=True)
    evidence['signal_continuity'] = continuity
    evidence['unapproved_after_stop_cooldown_counterfactual'] = stop_counterfactual

    # Genuine missing quote with generated readiness, and monthly contribution.
    raw = prices.copy()
    raw.loc[raw.date.eq('2018-02-01'), 'close'] = np.nan
    prepared = exp.prepare_base_features(raw, macro)
    sub = exp.generate_signals(prepared)
    sub = sub[sub.date.between('2018-01-29', '2018-02-07')].copy().reset_index(drop=True)
    # Controlled entry isolates execution; retain real generated readiness.
    sub['Trigger_Panic'] = False
    sub.loc[0, 'Trigger_Panic'] = True
    sub['cond_trend'] = False
    sub['raw_sell'] = False
    sub['sell_reason'] = 'NONE'
    res = exp.run_execution_simulation(sub, initial_cash=10000, dca_monthly=1000)
    ex = res['executor_instance']
    evidence['missing_monthly_dca'] = {
        'dates': sub.date.dt.strftime('%Y-%m-%d').tolist(),
        'readiness': sub.signal_ready.tolist(),
        'fills': ex.fills, 'cashflows': ex.cashflows,
        'final_cash': ex.daily_states[-1]['cash'],
        'orders': ex.orders_history,
    }

    # A stop timer must count trading sessions, including temporarily unready ones.
    stop = base()
    stop['signal_ready'] = True
    stop.loc[1, 'Trigger_Panic'] = True
    stop.loc[4, ['raw_sell', 'sell_reason']] = [True, 'BUBBLE']
    stop['ma50_band'] = False
    stop.loc[12, 'ma50_band'] = True
    stop.loc[12, 'q1_dot'] = .2  # Reentry fills day 13.
    stop.loc[14:24, 'signal_ready'] = False
    stop.loc[25, 'close'] = 94.0  # Day 12 after reentry: expired in trading time.
    late = exp.run_execution_simulation(stop, use_factor_c=True, dca_monthly=0)
    evidence['stop_timer_freezes_on_unready_days'] = {
        'reentry_fill': str(stop.date.iloc[13].date()),
        'late_stop_signal': str(stop.date.iloc[25].date()),
        'elapsed_trading_rows': 12,
        'stop_orders': late['stop_loss_order_count'],
        'orders': late['executor_instance'].orders_history,
    }
    assert late['stop_loss_order_count'] == 1

    # Final missing quote must value open wave at executor's last valid quote.
    terminal = base(4)
    terminal.loc[0, 'Trigger_Panic'] = True
    terminal.loc[2, 'close'] = 120.0
    terminal.loc[3, 'close'] = np.nan
    end = exp.run_execution_simulation(terminal, initial_cash=10000, dca_monthly=0, fee_rate=0)
    evidence['open_wave_missing_terminal_quote'] = {
        'ledger': end['open_positions'][0],
        'account_state': end['executor_instance'].daily_states[-1],
    }
    assert end['open_positions'][0]['latest_market_val'] == 10000
    assert end['executor_instance'].daily_states[-1]['equity'] == 12000

    # Sell matching must follow the same frozen E in [S-15,S+5] convention.
    peak = pd.DataFrame({'date': pd.bdate_range('2020-01-01', periods=160),
                         'close': 200 - np.abs(np.arange(160) - 50),
                         'Trigger_Panic': False, 'raw_sell': False})
    sell_probes = {}
    for day in [40, 60]:
        df = peak.copy()
        df.loc[day, 'raw_sell'] = True
        sell_probes[str(day)] = exp.evaluate_signals(df)
    evidence['sell_extrema_window_reversed'] = sell_probes

    # NaN erasure in an A score bypasses their full-history equivalence assertion.
    marker_return = '    return df\n\n\ndef generate_signals'
    assert marker_return in source
    mutant = source.replace(marker_return,
        "    df.loc[df['date'].eq(pd.Timestamp('2019-01-02')), 'Score_Overheat_A'] = np.nan\n"
        + marker_return, 1)
    ns = dict(exp.__dict__)
    exec(compile(mutant, exp.__file__, 'exec'), ns)
    case = tests.TestFactorialExperimentEngineV22()
    case.setUp()
    with patch.object(exp, 'prepare_base_features', ns['prepare_base_features']):
        case.test_08_full_history_model_equivalence()
    evidence['nan_mask_mutation_survives_test08'] = True

    # Forward return availability must include availability of horizon quote.
    fwd = base(30)
    fwd.loc[0, 'Trigger_Panic'] = True
    fwd.loc[21, 'close'] = np.nan
    fwd_res = exp.run_execution_simulation(fwd, dca_monthly=0)
    event = fwd_res['event_forward_evaluations'][0]
    evidence['forward_valid_flag_with_missing_horizon_quote'] = event
    assert event['valid_fill_20'] and np.isnan(event['fwd_ret_fill_20d'])

    # Publish the independently reproduced baseline numbers and event counts.
    evidence['actual_benchmark_metrics'] = {}
    for asset in ['NOW', 'QQQ', 'SPY']:
        df = pd.read_csv(rerun / f'factorial_ablation_results_v2_2_{asset.lower()}.csv')
        evidence['actual_benchmark_metrics'][asset] = df.iloc[0][
            ['Bench_Final', 'Bench_XIRR%', 'Bench_MDD%']].to_dict()
    events = pd.read_csv(rerun / 'forward_return_evaluations_v2_2.csv')
    evidence['event_counts'] = events.event_type.value_counts().to_dict()
    evidence['total_events'] = len(events)
    evidence['unique_entry_asset_date_type'] = int(events[events.event_type.isin(
        ['TREND_BUY', 'REENTRY_BUY', 'PANIC_BUY'])].drop_duplicates(
        ['Asset', 'fill_dt', 'event_type']).shape[0])
    evidence['files_unchanged'] = snapshot() == before
    assert evidence['files_unchanged']
    (OUT / 'findings.json').write_text(json.dumps(json_safe(evidence), indent=2,
                                                ensure_ascii=False, allow_nan=False,
                                                default=str), encoding='utf-8')
    (OUT / 'protected_file_hashes.json').write_text(json.dumps(before, indent=2), encoding='utf-8')
    print('V2_2_INDEPENDENT_AUDIT_COMPLETED')


if __name__ == '__main__':
    main()
