"""Independent read-only acceptance of the five v2.3 follow-up fixes."""
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
from audit_artifacts.gemini_review_20260923.v2_3_remediation import (
    run_factorial_experiment_v2_3 as exp,
    test_experiment_engine_v2_3 as tests,
    verify_claims_v2_3 as verifier,
)
from audit_artifacts.gemini_review_20260923.review_v2_2_claims import json_safe

HOME = Path(__file__).resolve().parent
OUT = HOME / 'v2_3_followup_review_20260924'
SUB = Path(exp.__file__).parent
FROZEN = HOME / 'v2_3_independent_review' / 'frozen_inputs'


def snapshot():
    files = [p for directory in [SUB, HOME / 'v2_1_remediation', HOME / 'v2_2_remediation',
                                HOME / 'v2_2_independent_review', HOME / 'v2_3_independent_review']
             for p in directory.rglob('*') if p.is_file() and '__pycache__' not in p.parts]
    files += [ROOT / n for n in ['reflexivity_engine.py', 'now_reflexivity_radar.py',
                                 'shared_executor.py', 'true_accounting.py']]
    return {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}


def main():
    OUT.mkdir(exist_ok=True)
    rerun = OUT / 'rerun'
    rerun.mkdir(exist_ok=True)
    before = snapshot()
    evidence = {}
    manifest = json.loads((SUB / 'manifest_v2_3.json').read_text())
    frozen_bytes = {}
    for name in ['now_ohlcv_local.csv', 'market_data_local.csv']:
        data = (FROZEN / name).read_bytes()
        assert hashlib.sha256(data).hexdigest() == manifest[name]['sha256']
        frozen_bytes[name] = data
    evidence['frozen_input_hashes_match_manifest'] = True
    real_read = pd.read_csv

    def read_frozen(path, *args, **kwargs):
        if isinstance(path, (str, Path)):
            resolved = Path(path).resolve()
            if resolved in [ROOT / n for n in frozen_bytes] or resolved in [FROZEN / n for n in frozen_bytes]:
                path = io.BytesIO(frozen_bytes[resolved.name])
        return real_read(path, *args, **kwargs)

    runs = {}
    real_sim = exp.run_execution_simulation

    def capture(df, *args, **kwargs):
        result = real_sim(df, *args, **kwargs)
        if df.date.iloc[0] == pd.Timestamp('2014-04-16') and df.date.iloc[-1] >= pd.Timestamp('2026-09-14'):
            runs[(kwargs['asset'], kwargs['config'])] = result
        return result

    log = io.StringIO()
    with patch.object(pd, 'read_csv', read_frozen):
        with contextlib.redirect_stdout(log), patch.object(exp, 'OUT_DIR', rerun), patch.object(exp, 'run_execution_simulation', capture):
            exp.main()
        with contextlib.redirect_stdout(log), patch.object(verifier, 'OUT_DIR', rerun):
            verifier.main()
    (OUT / 'submitted_run.log').write_text(log.getvalue(), encoding='utf-8')
    comparisons = {}
    for p in SUB.glob('*.csv'):
        comparisons[p.name] = (p.read_bytes() == (rerun / p.name).read_bytes()
                              if p.stat().st_size <= 3 else
                              real_read(p).equals(real_read(rerun / p.name)))
    evidence['all_csv_reproduction'] = comparisons
    assert all(comparisons.values()), comparisons
    print('ALL_FOLLOWUP_CSVS_REPRODUCED', flush=True)

    # Symmetric cutoff probes, for both peak and trough metrics.
    boundaries = []
    for is_top in [True, False]:
        for extreme, signal in [(102, 99), (99, 102), (20, 18)]:
            p = 200 - np.abs(np.arange(160) - extreme) if is_top else 100 + np.abs(np.arange(160) - extreme)
            df = pd.DataFrame({'date': pd.bdate_range('2020-01-01', periods=160),
                               'close': p, 'Trigger_Panic': False, 'raw_sell': False})
            df.loc[signal, 'raw_sell' if is_top else 'Trigger_Panic'] = True
            boundaries.append({'type': 'peak' if is_top else 'trough',
                               'E': extreme, 'S': signal, 'result': exp.evaluate_signals(df)})
    evidence['symmetric_boundary_probes'] = boundaries
    assert boundaries[0]['result']['sell_fdr'] == 0
    assert boundaries[1]['result']['top_miss_rate'] == 100
    assert boundaries[4]['result']['bottom_miss_rate'] == 100

    # Check the newly disclosed timestamps against actual fills and cash flows.
    sub = real_read(rerun / 'subperiod_evaluation_v2_3.csv')
    timestamp_checks = []
    for row in sub[sub.Mode == 'Mode_A_Continuous_Inherited'].to_dict('records'):
        ex = runs[(row['Asset'], row['Config'])]['executor_instance']
        fills = [f for f in ex.fills if row['Start_Dt'] <= f['dt'] <= row['End_Dt']]
        actual_first = fills[0]['dt'] if fills else 'NONE'
        declared_deposit = row['Actual_Deposit_Dt']
        cash_on_declared_date = sum(amount for dt, amount in ex.acc.cash_flows
                                   if dt.strftime('%Y-%m-%d') == declared_deposit)
        timestamp_checks.append({'Asset': row['Asset'], 'Config': row['Config'],
                                 'Segment': row['Segment'],
                                 'reported_first_fill': row['First_Fill_Dt'],
                                 'actual_first_fill_in_segment': actual_first,
                                 'reported_actual_deposit_dt': declared_deposit,
                                 'cashflow_on_reported_deposit_date': cash_on_declared_date})
    evidence['mode_a_timestamp_checks'] = timestamp_checks
    evidence['incorrect_mode_a_first_fill_rows'] = sum(r['reported_first_fill'] != r['actual_first_fill_in_segment'] for r in timestamp_checks)
    evidence['no_cashflow_on_declared_deposit_date_rows'] = sum(r['cashflow_on_reported_deposit_date'] == 0 for r in timestamp_checks)

    # Explicit re-run of repaired regression scenarios and mutation assertions.
    case = tests.TestFactorialExperimentEngineV23()
    case.setUp()
    case.test_05_wave_cost_accounting_and_stop_isolation()
    case.test_07_holding_dca_catch_up_and_pending_sell_protection()
    case.test_10_mutation_catch()
    case.test_11_mode_a_flat_no_fee_zero_economic_return()
    evidence['cost_guard_mutations_flat_scenario_pass'] = True

    # Submitted full-period metrics and trade ledgers should not change in this statistics-only revision.
    prior = HOME / 'v2_3_independent_review' / 'rerun'
    unchanged = {}
    metric_cols = ['Config', 'Strat_Final', 'Bench_Final', 'Strat_XIRR%', 'Bench_XIRR%',
                   'Alpha_XIRR%', 'Strat_MDD%', 'Bench_MDD%', 'Stop_Loss_Orders']
    for asset in ['now', 'qqq', 'spy']:
        name = f'factorial_ablation_results_v2_3_{asset}.csv'
        unchanged[asset] = real_read(rerun / name)[metric_cols].equals(real_read(prior / name)[metric_cols])
    evidence['full_period_financial_metrics_unchanged'] = unchanged
    evidence['mode_b_dca_totals'] = sorted(sub[sub.Mode == 'Mode_B_Fresh_Reset'].Strat_Total_DCA.unique().tolist())
    evidence['now_c7_mode_a_historical'] = sub[(sub.Asset == 'NOW') & (sub.Config == 'C7_Full_Candidate')
        & (sub.Mode == 'Mode_A_Continuous_Inherited') & sub.Segment.str.startswith('Historical')].iloc[0].to_dict()
    evidence['files_unchanged_by_review'] = snapshot() == before
    assert evidence['files_unchanged_by_review']
    (OUT / 'findings.json').write_text(json.dumps(json_safe(evidence), ensure_ascii=False,
                                                indent=2, allow_nan=False, default=str), encoding='utf-8')
    (OUT / 'protected_file_hashes.json').write_text(json.dumps(before, indent=2), encoding='utf-8')
    print('V2_3_FOLLOWUP_REVIEW_COMPLETED')


if __name__ == '__main__':
    main()
