"""Independent reproduction and counterexamples for the v2 delivery claims.

Original experiment, tests, and results remain unchanged. Mutations below are
in-memory probes of test sensitivity, never changes to the submitted files.
"""

import contextlib
import hashlib
import io
import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from audit_artifacts.gemini_review_20260923 import run_factorial_experiment as exp
from audit_artifacts.gemini_review_20260923 import test_experiment_engine as tests
from shared_executor import SharedExecutor


OUT = Path(__file__).resolve().parent / 'v2_independent_review'
ROOT = OUT.parent.parent.parent


def capture_run(frame, **kwargs):
    """Observe actual orders and fills without changing execution behavior."""
    captured = []

    class Capture(SharedExecutor):
        def __init__(self, *args, **inner_kwargs):
            super().__init__(*args, **inner_kwargs)
            captured.append(self)

    with patch.object(exp, 'SharedExecutor', Capture):
        metrics = exp.run_execution_simulation(frame, **kwargs)
    return metrics, captured


def fixture(count=35):
    case = tests.TestFactorialExperimentEngine()
    case.setUp()
    frame = case.df_base.iloc[:count].copy()
    frame['close'] = 100.0
    frame['MA10'] = 90.0
    frame['MA20'] = 90.0
    return frame


def main():
    OUT.mkdir(exist_ok=True)
    report = {}
    paths = list(exp.OUT_DIR.glob('*.py')) + list(exp.OUT_DIR.glob('*.csv'))
    before = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}

    # Initial benchmark order is submitted twice on the same date.
    _, captured = capture_run(fixture(8))
    bench = captured[1]
    report['benchmark_first_month_counterexample'] = {
        'fills': len(bench.fills), 'cash': bench.acc.cash,
        'orders': bench.orders_history, 'pending': bench.pending_orders,
    }
    assert len(bench.fills) == 0

    # Factor C is disabled, yet its reentry stop loss still executes.
    frame = fixture(12)
    frame.loc[[0, 5], 'Trigger_Panic'] = True
    frame.loc[3, ['raw_sell', 'sell_reason']] = [True, 'BUBBLE']
    frame.loc[7:, 'close'] = 94.0
    _, captured = capture_run(frame, use_factor_c=False)
    stops = [o for o in captured[0].orders_history
             if o['reason'] == 'STOP_LOSS_5PCT']
    report['factor_c_disabled_stop_orders'] = stops
    assert len(stops) == 1

    # Probe whether the submitted tests detect disabled reentry and stop logic.
    source = Path(exp.__file__).read_text(encoding='utf-8')
    mutated = source.replace('stop_loss_triggered = True',
                             'stop_loss_triggered = False')
    mutated = mutated.replace('if path_a or path_b:', 'if False:')
    namespace = dict(exp.__dict__)
    exec(compile(mutated, exp.__file__, 'exec'), namespace)
    stream = io.StringIO()
    with patch.object(exp, 'run_execution_simulation',
                      namespace['run_execution_simulation']):
        suite = unittest.defaultTestLoader.loadTestsFromModule(tests)
        result = unittest.TextTestRunner(stream=stream).run(suite)
    report['disabled_stop_and_bubble_reentry_test_suite'] = {
        'tests_run': result.testsRun, 'passed': result.wasSuccessful(),
        'log': stream.getvalue(),
    }
    assert result.wasSuccessful()

    # A lock is consumed on a raw candidate suppressed by later hysteresis.
    frame = fixture(30)
    frame.loc[[0, 4], 'Dist_200MA'] = -12.0
    frame.loc[1, 'q1_dot'] = 0.2
    frame.loc[5:, 'q1_dot'] = 0.2
    trace_result = {}

    def trace(frame_obj, event, arg):
        if (event == 'return'
                and frame_obj.f_code is exp.generate_signals.__code__):
            flags = frame_obj.f_locals['raw_panic_arr']
            trace_result['raw_candidate_indices'] = [
                int(i) for i, flag in enumerate(flags) if flag
            ]
        return trace

    sys.settrace(trace)
    try:
        sig = exp.generate_signals(frame, use_factor_b=True)
    finally:
        sys.settrace(None)
    trace_result['final_signal_indices'] = sig.index[sig.Trigger_Panic].tolist()
    report['latch_consumed_before_hysteresis'] = trace_result
    assert trace_result['raw_candidate_indices'] == [1, 5]
    assert trace_result['final_signal_indices'] == [1]

    # Reproduce the real entry point in a separate output directory.
    original_output = exp.OUT_DIR
    with patch.object(exp, 'OUT_DIR', OUT), contextlib.redirect_stdout(io.StringIO()):
        exp.main()
    report['main_generated_csvs'] = sorted(p.name for p in OUT.glob('*.csv'))
    report['cross_asset_csv_exact_matches'] = {}
    for ticker in ['qqq', 'spy']:
        name = f'factorial_ablation_results_v2_{ticker}.csv'
        left = pd.read_csv(OUT / name)
        right = pd.read_csv(original_output / name)
        pd.testing.assert_frame_equal(left, right)
        report['cross_asset_csv_exact_matches'][ticker] = True
    report['main_exports_now_csv'] = (OUT / 'factorial_ablation_results_v2.csv').exists()
    assert not report['main_exports_now_csv']

    macro = pd.read_csv(ROOT / 'market_data_local.csv')
    prices = pd.read_csv(ROOT / 'now_ohlcv_local.csv')
    full = exp.prepare_base_features(prices, macro)
    warm = full[full.date >= '2014-04-16'].reset_index(drop=True)
    report['now_selected_reproduction'] = {}
    for label, flag in [('C0', False), ('C7', True)]:
        sig = exp.generate_signals(warm, flag, flag, flag)
        metrics, captured = capture_run(sig, use_factor_c=flag, use_factor_a=flag)
        report['now_selected_reproduction'][label] = metrics
        report['now_selected_reproduction'][label]['stop_orders'] = sum(
            o['reason'] == 'STOP_LOSS_5PCT' for o in captured[0].orders_history
        )
        report['now_selected_reproduction'][label]['benchmark_first_fill'] = (
            captured[1].fills[0]['dt']
        )
    # Old verification harness omits new execution flags: its 'C7' is not C7.
    full_sig = exp.generate_signals(full, True, True, True)
    report['old_verifier_c7_missing_flags'] = exp.run_execution_simulation(full_sig)['strat_final']
    report['c7_with_execution_flags'] = exp.run_execution_simulation(
        full_sig, use_factor_c=True, use_factor_a=True
    )['strat_final']

    after = {str(p): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    assert before == after
    report['original_files_unchanged'] = True
    (OUT / 'findings.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8'
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print('INDEPENDENT_V2_REVIEW_COMPLETED')


if __name__ == '__main__':
    main()
