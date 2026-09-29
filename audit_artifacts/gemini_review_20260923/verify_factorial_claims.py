"""Audit the submitted experiment without changing it or its existing outputs."""

import importlib.util
import json
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

from reflexivity_engine import run_universal_reflexivity_radar
from shared_executor import SharedExecutor
from true_accounting import UnitizedAccount, calculate_xirr


OUT = Path(__file__).resolve().parent
ROOT = OUT.parent.parent
spec = importlib.util.spec_from_file_location(
    'factorial_subject', OUT / 'run_factorial_experiment.py'
)
subject = importlib.util.module_from_spec(spec)
spec.loader.exec_module(subject)


def main():
    price = pd.read_csv(ROOT / 'now_ohlcv_local.csv')
    macro = pd.read_csv(ROOT / 'market_data_local.csv')
    base = subject.prepare_base_features(price, macro)
    evidence = {'actual_full_start': str(base.date.iloc[0].date())}
    for name, enabled in [('C0', False), ('C7', True)]:
        captures = []

        class CaptureExecutor(SharedExecutor):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                captures.append(self)

        signals = subject.generate_signals(base, enabled, enabled, enabled)
        with patch.object(subject, 'SharedExecutor', CaptureExecutor):
            reported = subject.run_execution_simulation(signals)
        strategy, benchmark = captures
        nav = pd.Series([s['unit_nav'] for s in strategy.daily_states])
        evidence[name] = {
            'reported_final': reported['strat_final'],
            'reported_alpha_pct': reported['alpha_cagr'],
            'reported_equity_mdd_pct': reported['strat_mdd'],
            'unit_nav_mdd_pct': round(float((nav / nav.cummax() - 1).min() * 100), 4),
            'strategy_xirr_pct': round(calculate_xirr(
                strategy.acc.cash_flows, reported['strat_final'], base.date.iloc[-1]
            ) * 100, 4),
            'benchmark_fills': len(benchmark.fills),
            'benchmark_cashflows': len(benchmark.cashflows),
            'benchmark_terminal_cash': round(benchmark.acc.cash, 2),
            'benchmark_final': reported['bench_final'],
            'first_strategy_fill': strategy.fills[0]['dt'],
        }
        if name == 'C0':
            original = run_universal_reflexivity_radar('NOW', price, macro)
            first_ready = original.loc[original.signal_ready, 'date'].iloc[0]
            evidence['production_first_ready'] = str(first_ready.date())
            evidence['C0_buys_before_production_ready'] = int(
                (signals.raw_buy & (signals.date < first_ready)).sum()
            )

    # This countercheck invests each monthly contribution at the next close.
    # It changes no candidate strategy and is not a corrected experiment report.
    account = UnitizedAccount(initial_cash=10000, initial_date=base.date.iloc[0])
    executor = SharedExecutor(account, fee_rate=0.001,
                              execution_mode='NEXT_CLOSE', account_type='bench')
    last_month = None
    for row in base.itertuples():
        month = (row.date.year, row.date.month)
        deposit = 1000 if month != last_month else 0
        executor.step(row.date, row.close, row.close, dca_amount=deposit)
        if deposit:
            executor.submit_order(1.0, 'Monthly benchmark investment', row.date)
        last_month = month
    evidence['monthly_invested_benchmark_countercheck'] = {
        'terminal_equity': round(executor.daily_states[-1]['equity'], 2),
        'terminal_cash': round(account.cash, 2),
        'fills': len(executor.fills),
    }

    # A single trough at row 50; +10 days is valid in the frozen specification.
    synthetic = pd.DataFrame({'close': np.abs(np.arange(160) - 50) + 100.0,
                              'Trigger_Panic': False, 'raw_sell': False})
    for day in [40, 60]:
        sample = synthetic.copy()
        sample.loc[day, 'Trigger_Panic'] = True
        result = subject.evaluate_signals(sample)
        evidence[f'signal_offset_{day - 50}_days'] = {
            'buy_fdr_pct': result['buy_fdr'],
            'bottom_miss_pct': result['bottom_miss_rate'],
        }
    text = json.dumps(evidence, indent=2, ensure_ascii=False)
    (OUT / 'factorial_claims_verification.json').write_text(text, encoding='utf-8')
    print(text)
    print('AUDIT_REPRODUCTION_COMPLETED')


if __name__ == '__main__':
    main()
