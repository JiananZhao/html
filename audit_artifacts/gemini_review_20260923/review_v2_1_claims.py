"""Independent v2.1 audit: replay selected paths and test semantic counterexamples.

All changes are confined to new evidence files and temporary in-memory probes.
"""

import hashlib
import io
import json
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

from audit_artifacts.gemini_review_20260923 import run_factorial_experiment as old
from audit_artifacts.gemini_review_20260923.v2_1_remediation import (
    run_factorial_experiment_v2_1 as exp,
    test_experiment_engine_v2_1 as tests,
)
from reflexivity_engine import run_universal_reflexivity_radar
from shared_executor import SharedExecutor


BASE = Path(__file__).resolve().parent
OUT = BASE / 'v2_1_independent_review'
ROOT = BASE.parent.parent


def fixture(count):
    case = tests.TestFactorialExperimentEngineV21()
    case.setUp()
    return case.df_base.iloc[:count].copy()


def main():
    OUT.mkdir(exist_ok=True)
    originals = [p for p in exp.OUT_DIR.iterdir() if p.is_file()]
    hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in originals}
    evidence = {}
    prices = pd.read_csv(ROOT / 'now_ohlcv_local.csv')
    macro = pd.read_csv(ROOT / 'market_data_local.csv')
    new_features = exp.prepare_base_features(prices, macro)
    old_features = old.prepare_base_features(prices, macro)
    columns = ['q1', 'q1_dot', 'q1_ddot', 'v_dot', 'Composite_Score_M0',
               'Score_Overheat_A', 'Score_PanicDepth_A']
    evidence['2020_03_20_model_drift'] = {}
    for name, df in [('frozen_v2', old_features), ('submitted_v2_1', new_features)]:
        row = df.loc[df.date.eq(pd.Timestamp('2020-03-20')), columns].iloc[0]
        evidence['2020_03_20_model_drift'][name] = row.round(6).to_dict()

    captures = []

    class Capture(SharedExecutor):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            captures.append(self)

    with patch('shared_executor.SharedExecutor', Capture):
        production = run_universal_reflexivity_radar('NOW', prices, macro)
    account = captures[0]
    evidence['production_actual_reproduction'] = {
        'first_ready': str(production.loc[production.signal_ready, 'date'].iloc[0].date()),
        'fills': len(account.fills),
        'final_equity': round(account.daily_states[-1]['equity'], 2),
        'final_unit_nav': round(account.daily_states[-1]['unit_nav'], 4),
    }
    evidence['new_signal_ready_first_date'] = str(
        new_features.loc[new_features.signal_ready, 'date'].iloc[0].date()
    )

    evidence['selected_reproductions'] = {}
    for asset in ['NOW', 'QQQ', 'SPY']:
        raw = prices if asset == 'NOW' else macro[['date', asset]].dropna().rename(columns={asset: 'close'})
        features = exp.prepare_base_features(raw, macro)
        warm = features[features.date >= '2014-04-16'].reset_index(drop=True)
        saved = pd.read_csv(exp.OUT_DIR / f'factorial_ablation_results_v2_1_{asset.lower()}.csv')
        asset_result = {}
        for label, a, b, c in [('C0_Baseline', False, False, False),
                               ('C2_Panic_Latch', False, True, False),
                               ('C7_Full_Candidate', True, True, True)]:
            sig = exp.generate_signals(warm, a, b, c)
            result = exp.run_execution_simulation(sig, use_factor_a=a, use_factor_c=c)
            row = saved[saved.Config.eq(label)].iloc[0]
            assert result['strat_final'] == row.Strat_Final
            assert result['stop_loss_order_count'] == row.StopOrders
            fills = result['executor_instance'].fills
            asset_result[label] = {
                key: result[key] for key in ['strat_final', 'strat_xirr', 'strat_mdd',
                                             'stop_loss_order_count', 'benchmark_first_fill_dt']
            }
            asset_result[label]['strategy_first_fill'] = fills[0]['dt']
        evidence['selected_reproductions'][asset] = asset_result

    # Missing raw close must not become an executable quote through preparation.
    dates = pd.bdate_range('2020-01-01', periods=220)
    raw = pd.DataFrame({'date': dates, 'close': 100.0})
    raw.loc[210, 'close'] = np.nan
    raw_macro = pd.DataFrame({'date': dates, 'HYG': 80.0, 'BAA10Y': 1.5,
                              'NFCI': -0.5, 'Real_Yield': 1.0})
    prepared = exp.prepare_base_features(raw, raw_macro).iloc[209:216].reset_index(drop=True)
    prepared['Trigger_Panic'] = False
    prepared.loc[0, 'Trigger_Panic'] = True
    prepared['raw_sell'] = False
    prepared['sell_reason'] = 'NONE'
    prepared['cond_trend'] = False
    result = exp.run_execution_simulation(prepared, dca_monthly=0)
    executor = result['executor_instance']
    evidence['missing_quote_full_pipeline'] = {
        'raw_missing_date': str(dates[210].date()),
        'prepared_price': float(prepared.close.iloc[1]),
        'first_fill': executor.fills[0]['dt'],
        'valuation_quality': executor.daily_states[1]['valuation_quality'],
    }
    assert executor.fills[0]['dt'] == str(dates[210].date())

    # A DCA addition must not replace the original entry of an open position.
    df = fixture(30)
    df.loc[0, 'Trigger_Panic'] = True
    df.loc[24, ['raw_sell', 'sell_reason']] = [True, 'BUBBLE']
    result = exp.run_execution_simulation(df)
    fills = result['executor_instance'].fills
    buys = [f for f in fills if f['direction'] == 'BUY']
    trade = result['round_trips_ledger'][0]
    expected_duration = 25 - 1
    evidence['dca_overwrites_round_trip_entry'] = {
        'actual_initial_entry': buys[0]['dt'],
        'dca_addition': buys[-1]['dt'],
        'reported_entry': trade['entry_dt'],
        'reported_duration': int(trade['duration_trading_days']),
        'expected_holding_duration': expected_duration,
        'reported_short_term': bool(trade['is_short_term']),
    }
    assert trade['entry_dt'] != buys[0]['dt']

    # Reintroduce the actual premature-consumption bug, not a forged output.
    source = Path(exp.__file__).read_text(encoding='utf-8')
    marker = '# If suppressed by hysteresis, latch is NOT consumed and continues countdown.'
    assert source.count(marker) == 1
    mutant = source.replace(marker, 'latch = False  # actual premature-consumption mutation')
    namespace = dict(exp.__dict__)
    exec(compile(mutant, exp.__file__, 'exec'), namespace)
    log = io.StringIO()
    with patch.object(exp, 'generate_signals', namespace['generate_signals']):
        suite = unittest.defaultTestLoader.loadTestsFromModule(tests)
        result = unittest.TextTestRunner(stream=log).run(suite)
    evidence['actual_premature_consumption_mutation'] = {
        'tests_run': result.testsRun, 'all_tests_passed': result.wasSuccessful(),
        'test_output': log.getvalue(),
    }
    assert result.wasSuccessful()

    # Isolate the claimed causal role of the 5% stop within the submitted model.
    # This is a counterfactual probe, not a proposed strategy or a new candidate.
    stop_condition = 'if pd.notna(p_i) and p_i < reentry_fill_price * 0.95:'
    assert source.count(stop_condition) == 1
    no_stop_namespace = dict(exp.__dict__)
    exec(compile(source.replace(stop_condition, 'if False:'), exp.__file__, 'exec'),
         no_stop_namespace)
    warm_now = new_features[new_features.date >= '2014-04-16'].reset_index(drop=True)
    c3_signals = exp.generate_signals(warm_now, False, False, True)
    c3 = exp.run_execution_simulation(c3_signals, use_factor_c=True)
    c3_without_stop = no_stop_namespace['run_execution_simulation'](
        c3_signals, use_factor_c=True
    )
    evidence['now_c3_stop_only_counterfactual'] = {
        'submitted_c3_final': c3['strat_final'],
        'same_c3_without_stop_final': c3_without_stop['strat_final'],
        'submitted_c0_final': evidence['selected_reproductions']['NOW']['C0_Baseline']['strat_final'],
        'scope': 'Same submitted v2.1 rules and data; only stop trigger disabled in memory.',
    }

    # Test fixtures claim DCA on Jan 6/Jan 9; the actual schedule is monthly.
    df = fixture(10)
    df.loc[1, 'Trigger_Panic'] = True
    df.loc[4, ['raw_sell', 'sell_reason']] = [True, 'BEAR']
    df.loc[5, 'close'] = np.nan
    result = exp.run_execution_simulation(df)
    evidence['claimed_dca_conflict_fixture'] = {
        'sell_signal_date': str(df.date.iloc[4].date()),
        'missing_date': str(df.date.iloc[5].date()),
        'scheduled_deposit_dates': [cf['planned_dt'] for cf in result['executor_instance'].cashflows],
    }

    ledgers = pd.read_csv(exp.OUT_DIR / 'round_trip_ledgers_v2_1.csv')
    cash = pd.read_csv(exp.OUT_DIR / 'cash_intervals_v2_1.csv')
    evidence['ledger_coverage'] = {
        'round_trip_rows': len(ledgers), 'round_trip_assets': sorted(ledgers.Asset.unique().tolist()),
        'cash_rows': len(cash), 'cash_assets': sorted(cash.Asset.unique().tolist()),
    }
    manifest = json.loads((BASE / 'v2_independent_review/v2_frozen_manifest.json').read_text(encoding='utf-8'))
    evidence['v2_manifest_mismatches'] = [
        name for name, item in manifest.items()
        if hashlib.sha256((BASE / name).read_bytes()).hexdigest() != item['sha256']
    ]
    assert not evidence['v2_manifest_mismatches']
    assert hashes == {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in originals}
    evidence['original_v2_1_files_unchanged'] = True
    (OUT / 'findings.json').write_text(json.dumps(evidence, indent=2, ensure_ascii=False), encoding='utf-8')
    print(json.dumps(evidence, indent=2, ensure_ascii=False))
    print('V2_1_INDEPENDENT_AUDIT_COMPLETED')


if __name__ == '__main__':
    main()
