"""Descriptive warning diagnostics; no fitting or production changes.

Forward lows are measured from the signal close, not a future peak. Horizons
are input rows; QQQ/SPY's supplied calendar is not certified exchange sessions.
Overlapping outcomes are descriptive and are not independent significance tests.
"""
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from audit_artifacts.gemini_review_20260923.v2_3_remediation import run_factorial_experiment_v2_3 as exp

HOME = Path(__file__).resolve().parent
OUT = HOME / 'v2_3_final_review_20260924'
FROZEN = HOME / 'v2_3_independent_review' / 'frozen_inputs'


def main():
    OUT.mkdir(exist_ok=True)
    macro = pd.read_csv(FROZEN / 'market_data_local.csv')
    assets = {'NOW': pd.read_csv(FROZEN / 'now_ohlcv_local.csv')}
    for asset in ['QQQ', 'SPY']:
        assets[asset] = macro[['date', asset]].dropna().rename(columns={asset: 'close'})
    summary, details, cases = [], [], []
    for asset, price in assets.items():
        df = exp.generate_signals(exp.prepare_base_features(price, macro))
        df = df[df.date >= '2014-04-16'].reset_index(drop=True)
        ready = df.signal_ready & df.close.notna()
        # Existing production C0 bubble-regime thresholds; no changed rules.
        elevated = (df.Composite_Score_M0 >= 70) | (df.Dist_200MA > 22)
        warm = elevated & (df.Dist_200MA >= 10)
        score_hot = df.Composite_Score_M0 >= 70
        groups = {
            'all_ready_days': ready,
            'simple_dist_ge10_days': ready & (df.Dist_200MA >= 10),
            'dashboard_score_ge70_days': ready & score_hot,
            'dashboard_score_ge70_onsets': ready & score_hot & ~score_hot.shift(1, fill_value=False),
            'overheat_state_days': ready & warm,
            'overheat_state_onsets': ready & warm & ~warm.shift(1, fill_value=False),
            'bubble_top_trigger': ready & df.Trigger_Bubble_Top,
            'bear_top_trigger': ready & df.Trigger_Bear_Top,
        }
        p = df.close.to_numpy()
        for horizon in [20, 60]:
            for group, mask in groups.items():
                events = []
                for i in np.flatnonzero(mask):
                    future = p[i + 1:i + horizon + 1]
                    if len(future) != horizon or not np.isfinite(future).all() or not p[i] > 0:
                        continue
                    event = {'asset': asset, 'group': group, 'horizon_rows': horizon,
                             'date': str(df.date.iloc[i].date()),
                             'future_low_vs_signal_pct': float((future.min() / p[i] - 1) * 100),
                             'endpoint_return_pct': float((future[-1] / p[i] - 1) * 100)}
                    events.append(event)
                details.extend(events)
                if events:
                    low = np.array([e['future_low_vs_signal_pct'] for e in events])
                    ret = np.array([e['endpoint_return_pct'] for e in events])
                    summary.append({'asset': asset, 'group': group, 'horizon_rows': horizon,
                                    'n': len(events), 'drop_5_pct_rate': float((low <= -5).mean() * 100),
                                    'drop_10_pct_rate': float((low <= -10).mean() * 100),
                                    'drop_20_pct_rate': float((low <= -20).mean() * 100),
                                    'median_endpoint_return_pct': float(np.median(ret))})
        if asset == 'NOW':
            cols = ['date', 'q1', 'q1_dot', 'q1_ddot', 'v_dot', 'Score_Dim3_Lyapunov',
                    'Score_Dim6_Macro', 'Composite_Score_M0', 'Score_Overheat_A']
            row = df.loc[df.date == '2020-03-20', cols].iloc[0].to_dict()
            row['date'] = str(row['date'].date())
            cases.append(row)
    pd.DataFrame(summary).to_csv(OUT / 'warning_diagnostics.csv', index=False)
    pd.DataFrame(details).to_csv(OUT / 'warning_event_details.csv', index=False)
    (OUT / 'model_cases.json').write_text(json.dumps(cases, indent=2), encoding='utf-8')
    table = pd.DataFrame(summary)
    print(table[(table.horizon_rows == 60) & table.group.isin(
        ['all_ready_days', 'simple_dist_ge10_days', 'dashboard_score_ge70_onsets',
         'overheat_state_onsets', 'bubble_top_trigger'])].round(2).to_string(index=False))
    print('MODEL_WARNING_DIAGNOSTICS_COMPLETED')


if __name__ == '__main__':
    main()
