"""Read-only audit of v2.3; all regenerated artifacts go to a new directory."""
from pathlib import Path
import contextlib
import hashlib
import io
import json
import sys
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from audit_artifacts.gemini_review_20260923.v2_3_remediation import (
    run_factorial_experiment_v2_3 as exp,
    test_experiment_engine_v2_3 as tests,
    verify_claims_v2_3 as verifier,
)
from audit_artifacts.gemini_review_20260923.review_v2_2_claims import json_safe
from true_accounting import calculate_xirr

OUT = Path(__file__).parent / 'v2_3_independent_review'
SUB = Path(exp.__file__).parent


def snapshot():
    files = [p for folder in [SUB, SUB.parent / 'v2_2_remediation',
                             SUB.parent / 'v2_1_remediation']
             for p in folder.rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    files += [ROOT / n for n in ['reflexivity_engine.py', 'now_reflexivity_radar.py',
                                 'true_accounting.py', 'shared_executor.py']]
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}


def base(n=35):
    case = tests.TestFactorialExperimentEngineV23()
    case.setUp()
    return case.df_base.iloc[:n].copy()


def main():
    OUT.mkdir(exist_ok=True)
    rerun = OUT / 'rerun'
    rerun.mkdir(exist_ok=True)
    before = snapshot()
    evidence = {}
    # A local scheduled update appended a row during review. Recover only an
    # exact SHA-256-matching historical prefix, without altering live data.
    manifest = json.loads((SUB / 'manifest_v2_3.json').read_text())
    frozen_dir = OUT / 'frozen_inputs'
    frozen_dir.mkdir(exist_ok=True)
    substitutions = {}
    provenance = {}
    for name in ['now_ohlcv_local.csv', 'market_data_local.csv']:
        live = (ROOT / name).read_bytes()
        expected = manifest[name]['sha256']
        candidate = live
        removed = 0
        while hashlib.sha256(candidate).hexdigest() != expected and removed < 10:
            candidate = b''.join(candidate.splitlines(keepends=True)[:-1])
            removed += 1
        assert hashlib.sha256(candidate).hexdigest() == expected, name
        frozen = frozen_dir / name
        frozen.write_bytes(candidate)
        substitutions[str((ROOT / name).resolve())] = frozen
        provenance[name] = {'live_sha256': hashlib.sha256(live).hexdigest(),
                            'frozen_sha256': expected, 'trailing_lines_removed': removed}
    evidence['frozen_input_provenance'] = provenance
    original_read_csv = pd.read_csv

    def frozen_read_csv(path, *args, **kwargs):
        if isinstance(path, (str, Path)):
            path = substitutions.get(str(Path(path).resolve()), path)
        return original_read_csv(path, *args, **kwargs)

    reader_patch = patch.object(pd, 'read_csv', frozen_read_csv)
    reader_patch.start()
    full_runs = {}
    original_sim = exp.run_execution_simulation

    def capture(df, *args, **kwargs):
        result = original_sim(df, *args, **kwargs)
        if df.date.iloc[0] == pd.Timestamp('2014-04-16') and df.date.iloc[-1] >= pd.Timestamp('2026-09-14'):
            full_runs[(kwargs.get('asset', 'NOW'), kwargs.get('config', 'C0'))] = result
        return result

    log = io.StringIO()
    with contextlib.redirect_stdout(log), patch.object(exp, 'OUT_DIR', rerun), patch.object(exp, 'run_execution_simulation', capture):
        exp.main()
    with contextlib.redirect_stdout(log), patch.object(verifier, 'OUT_DIR', rerun):
        verifier.main()
    (OUT / 'submitted_run.log').write_text(log.getvalue(), encoding='utf-8')
    comparisons = {}
    for p in SUB.glob('*.csv'):
        comparisons[p.name] = ((rerun / p.name).read_bytes() == p.read_bytes()
                              if p.stat().st_size <= 3
                              else pd.read_csv(p).equals(pd.read_csv(rerun / p.name)))
    assert all(comparisons.values()), comparisons
    evidence['csv_reproduction'] = comparisons
    print('ALL_V2_3_CSVS_REPRODUCED', flush=True)

    # Independent reconciliation of inherited segment opening balances/cash flows.
    sub_csv = pd.read_csv(SUB / 'subperiod_evaluation_v2_3.csv')
    corrections = []
    for (asset, config), result in full_runs.items():
        row = sub_csv[(sub_csv.Asset == asset) & (sub_csv.Config == config)
                      & (sub_csv.Mode == 'Mode_A_Continuous_Inherited')
                      & (sub_csv.Segment == 'Historical_Verification_2020_2026')].iloc[0]
        rec = {'Asset': asset, 'Config': config}
        for prefix, key in [('Strat', 'executor_instance'), ('Bench', 'bench_executor_instance')]:
            ex = result[key]
            opening = [s for s in ex.daily_states if s['date'] < '2020-01-01'][-1]
            states = [s for s in ex.daily_states if '2020-01-01' <= s['date'] <= '2026-09-14']
            flows = [(dt, amount) for dt, amount in ex.acc.cash_flows
                     if pd.Timestamp('2020-01-01') <= dt <= pd.Timestamp('2026-09-14')]
            corrected = calculate_xirr([(pd.Timestamp('2020-01-01'), opening['equity'])] + flows,
                                       states[-1]['equity'], pd.Timestamp(states[-1]['date'])) * 100
            nav = pd.Series([opening['unit_nav']] + [s['unit_nav'] for s in states])
            mdd = (nav / nav.cummax() - 1).min() * 100
            first_dt = pd.Timestamp(states[0]['date'])
            first_deposit = sum(amount for dt, amount in flows if dt == first_dt)
            rec[prefix] = {
                'reported_opening': float(row[f'{prefix}_Start_Equity']),
                'previous_close_opening': opening['equity'],
                'actual_first_snapshot_date': states[0]['date'],
                'double_included_first_day_deposit': first_deposit,
                'reported_xirr': float(row[f'{prefix}_XIRR%']),
                'corrected_xirr_pre_first_session': round(corrected, 6),
                'reported_mdd': float(row[f'{prefix}_MDD%']),
                'corrected_mdd_with_opening_anchor': round(mdd, 6),
            }
        corrections.append(rec)
    evidence['mode_a_opening_cashflow_audit'] = corrections

    # Flat prices, no fees: any non-zero segment XIRR must arise from accounting.
    flat = base(100)
    calendar = pd.bdate_range('2019-12-27', periods=len(flat) + 1)
    flat['date'] = calendar[calendar != pd.Timestamp('2020-01-01')][:len(flat)]
    flat.loc[0, 'Trigger_Panic'] = True
    flat_result = original_sim(flat, initial_cash=100000, dca_monthly=1000, fee_rate=0)
    segments = exp.run_subperiod_evaluations('FLAT', 'C0', flat, '2019-12-27', False, False, flat_result)
    flat_a = next(r for r in segments if r['Mode'] == 'Mode_A_Continuous_Inherited'
                  and r['Segment'] == 'Historical_Verification_2020_2026')
    evidence['flat_no_fee_mode_a_counterexample'] = flat_a
    assert flat_a['Strat_XIRR%'] < 0

    # Mode B excludes the initial day's monthly contribution from disclosure.
    evidence['mode_b_first_day_deposit_omission'] = {
        'reported_initial': 100000,
        'actual_initial_cashflow_plus_first_dca': 101000,
        'omitted_first_day_dca': 1000,
        'affected_mode_b_rows': int((sub_csv.Mode == 'Mode_B_Fresh_Reset').sum()),
    }

    # Real pending sell + missing quote + scheduled contribution: exercise the loop.
    guard = base(8)
    guard['date'] = pd.to_datetime(['2023-01-27', '2023-01-30', '2023-01-31',
                                  '2023-02-01', '2023-02-02', '2023-02-03',
                                  '2023-02-06', '2023-02-07'])
    guard.loc[0, 'Trigger_Panic'] = True
    guard.loc[2, ['raw_sell', 'sell_reason']] = [True, 'BEAR']
    guard.loc[3, 'close'] = np.nan
    protected = original_sim(guard)
    ex = protected['executor_instance']
    risk = [o for o in ex.orders_history if o['reason'] == 'BEAR'][0]
    assert risk['status'] == 'FILLED' and risk['actual_dt'] == '2023-02-02'
    evidence['pending_sell_actual_loop_pass'] = risk

    # Their suite still passes with the actual DCA guard removed.
    source = Path(exp.__file__).read_text(encoding='utf-8')
    marker = 'if pos == 1.0 and not submitted_sell_today and not has_pending_sell:'
    assert source.count(marker) == 1
    ns = dict(exp.__dict__)
    exec(compile(source.replace(marker, 'if pos == 1.0 and not submitted_sell_today:'), exp.__file__, 'exec'), ns)
    suite_log = io.StringIO()
    with patch.object(exp, 'run_execution_simulation', ns['run_execution_simulation']):
        result = unittest.TextTestRunner(stream=suite_log).run(unittest.defaultTestLoader.loadTestsFromModule(tests))
    evidence['removed_pending_sell_guard_mutation'] = {
        'all_tests_still_pass': result.wasSuccessful(), 'tests': result.testsRun,
        'output': suite_log.getvalue(),
    }
    bad = ns['run_execution_simulation'](guard)
    bad_risk = [o for o in bad['executor_instance'].orders_history if o['reason'] == 'BEAR'][0]
    evidence['removed_guard_actual_consequence'] = bad_risk
    assert bad_risk['status'] == 'CANCELLED'

    # Equal masks still create false errors when matching windows cross the cutoff.
    peak = pd.DataFrame({'date': pd.bdate_range('2020-01-01', periods=160),
                         'close': 200 - np.abs(np.arange(160) - 102),
                         'Trigger_Panic': False, 'raw_sell': False})
    peak.loc[99, 'raw_sell'] = True  # E=102 is within [84,104], but masked away.
    evidence['cross_cutoff_matching_counterexample'] = exp.evaluate_signals(peak)

    # Risk clock: true NaN days plus DCA fill, boundary days 10 and 11.
    stop = base(40)
    stop.loc[1, 'Trigger_Panic'] = True
    stop.loc[4, ['raw_sell', 'sell_reason']] = [True, 'BUBBLE']
    stop['ma50_band'] = False
    stop.loc[12, 'ma50_band'] = True
    stop.loc[12, 'q1_dot'] = .2
    stop.loc[14:17, 'close'] = np.nan
    stop.loc[14:24, 'signal_ready'] = False
    stop_cases = {}
    for day in [23, 24, 25]:
        probe = stop.copy()
        probe.loc[day, 'close'] = 94
        res = original_sim(probe, use_factor_c=True)
        stop_cases[str(day - 13)] = res['stop_loss_order_count']
    evidence['actual_nan_dca_stop_clock'] = stop_cases
    assert stop_cases == {'10': 1, '11': 0, '12': 0}

    # Run all four forward horizon paths with actual missing endpoint quotes.
    forward = base(75)
    forward.loc[0, 'Trigger_Panic'] = True
    paths = {}
    for day, flag in [(20, 'valid_sig_20'), (21, 'valid_fill_20'),
                      (60, 'valid_sig_60'), (61, 'valid_fill_60')]:
        probe = forward.copy()
        probe.loc[day, 'close'] = np.nan
        res = original_sim(probe, dca_monthly=0)
        paths[flag] = res['event_forward_evaluations'][0][flag]
    assert not any(paths.values())
    evidence['all_four_missing_horizon_paths'] = paths
    evidence['files_unchanged'] = snapshot() == before
    assert evidence['files_unchanged']
    (OUT / 'findings.json').write_text(json.dumps(json_safe(evidence), ensure_ascii=False,
                                                indent=2, allow_nan=False, default=str), encoding='utf-8')
    (OUT / 'protected_file_hashes.json').write_text(json.dumps(before, indent=2), encoding='utf-8')
    reader_patch.stop()
    print('V2_3_INDEPENDENT_AUDIT_COMPLETED')


if __name__ == '__main__':
    main()
