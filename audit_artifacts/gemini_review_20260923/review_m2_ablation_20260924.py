"""Independent reproduction and boundary audit of the three B conditions."""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import sys
from unittest.mock import patch
import warnings

import numpy as np
import pandas as pd

HOME = Path(__file__).resolve().parent
SUB = HOME / 'v3_0_model_validity'
OUT = HOME / 'v3_0_m2_ablation_review_20260924'
sys.path.insert(0, str(SUB))
import predictive_evaluator as ev
import run_m2_baseline as runner


def main():
    OUT.mkdir(exist_ok=True)
    before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in SUB.iterdir() if p.is_file()}
    real_recall, real_csv = ev.evaluate_recall, pd.DataFrame.to_csv
    checks = []

    def check_recall(events, df, signal_col, lead_window):
        result = real_recall(events, df, signal_col, lead_window)
        ready = df[['V_Threshold', 'V', 'v', 'dV', 'MA20']].notna().all(axis=1)
        first_ready = int(np.flatnonzero(ready)[0])
        end = df.index[df.date <= '2019-12-31'][-1]
        full_sig = np.flatnonzero(df[signal_col])
        allowed = ready & (df.date >= '2014-01-01') & (np.arange(len(df)) + 60 <= end)
        eval_sig = np.flatnonzero(df[signal_col] & allowed)
        event_rows = []
        for e in events:
            hits = [int(s) for s in full_sig if e['peak_idx'] - lead_window <= s <= e['break_idx']]
            strict = [int(s) for s in full_sig if e['peak_idx'] - lead_window <= s < e['break_idx']]
            restricted = [int(s) for s in eval_sig if e['peak_idx'] - lead_window <= s < e['break_idx']]
            event_rows.append({'peak_date': str(e['peak_date']), 'break_date': str(df.date.iloc[e['break_idx']]),
                               'hits': [str(df.date.iloc[s]) for s in hits],
                               'strictly_before_break': bool(strict), 'common_scope_strict': bool(restricted),
                               'peak_before_feature_ready': e['peak_idx'] < first_ready})
        checks.append({'asset': ['NOW', 'QQQ', 'SPY'][len(checks) // 3], 'signal': signal_col,
                       'first_ready_idx': first_ready, 'first_ready_date': str(df.date.iloc[first_ready]),
                       'reported_recall': result, 'strict_caught': sum(e['strictly_before_break'] for e in event_rows),
                       'common_scope_strict_caught': sum(e['common_scope_strict'] for e in event_rows),
                       'events': event_rows})
        return result

    def redirect(frame, path, *args, **kwargs):
        return real_csv(frame, OUT / Path(path).name, *args, **kwargs)

    log = io.StringIO()
    with contextlib.redirect_stdout(log), patch.object(runner, 'evaluate_recall', check_recall), patch.object(pd.DataFrame, 'to_csv', redirect):
        runner.run_baseline_evaluation()
    (OUT / 'run.log').write_text(log.getvalue(), encoding='utf-8')
    a = pd.read_csv(OUT / 'ablation_report_m2.csv')
    assert a.equals(pd.read_csv(SUB / 'ablation_report_m2.csv'))
    toy = pd.DataFrame({'close': [100., 95., 89., 80., 75., 83.],
                         'alert': [False, False, True, False, False, False]})
    boundary = ev.evaluate_recall(ev.identify_drawdown_events(toy), toy, 'alert')
    assert boundary['recall_pct'] == 100.0
    sets = {}
    for asset in ['NOW', 'QQQ', 'SPY']:
        group = [c for c in checks if c['asset'] == asset]
        sets[asset] = {c['signal']: [e['peak_date'] for e in c['events'] if e['hits']] for c in group}
    unchanged = before == {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in SUB.iterdir() if p.is_file()}
    assert unchanged
    evidence = {'reproduced': True, 'checks': checks, 'caught_event_sets': sets,
                'same_close_break_counterexample': boundary, 'submitted_files_unchanged': unchanged}
    (OUT / 'findings.json').write_text(json.dumps(evidence, indent=2, default=str), encoding='utf-8')
    print(a.to_string(index=False))
    for c in checks:
        print(c['asset'], c['signal'], 'ready=', c['first_ready_idx'], c['first_ready_date'],
              'caught=', c['reported_recall']['caught_events'], 'strict=', c['strict_caught'],
              'scope_strict=', c['common_scope_strict_caught'],
              'pre_ready_events=', sum(e['peak_before_feature_ready'] for e in c['events']))
    print('M2_ABLATION_REVIEW_COMPLETED')


if __name__ == '__main__':
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', (FutureWarning, RuntimeWarning))
        main()
