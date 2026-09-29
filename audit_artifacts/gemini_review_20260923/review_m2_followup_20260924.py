"""Read-only follow-up probes for M2 recall and common eligibility."""
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
OUT = HOME / 'v3_0_m2_followup_review_20260924'
sys.path.insert(0, str(SUB))
import predictive_evaluator as ev
import run_m2_baseline as runner


def main():
    OUT.mkdir(exist_ok=True)
    before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in SUB.iterdir() if p.is_file()}
    captured = []
    actual_recall = ev.evaluate_recall
    actual_csv = pd.DataFrame.to_csv

    def inspect_recall(events, frame, signal_col, lead_window):
        result = actual_recall(events, frame, signal_col, lead_window)
        prices = frame.close.to_numpy()
        all_signals = np.flatnonzero(frame[signal_col])
        records = []
        for event in events:
            peak, trough = event['peak_idx'], event['trough_idx']
            crossing = next(i for i in range(peak, trough + 1)
                            if prices[i] <= event['peak_price'] * 0.9)
            matches = [int(s) for s in all_signals if peak - lead_window <= s <= trough]
            records.append({'peak': str(event['peak_date']), 'trough': str(event['trough_date']),
                            'first_10pct_date': str(frame.date.iloc[crossing]),
                            'matches': [str(frame.date.iloc[s]) for s in matches],
                            'caught_only_after_10pct': bool(matches) and min(matches) >= crossing})
        end = frame.index[frame.date <= '2019-12-31'][-1]
        original_mask = (frame.date >= '2014-01-01') & (np.arange(len(frame)) + 60 <= end)
        common = frame.V_Threshold.notna()
        captured.append({'signal': signal_col, 'result': result, 'events': records,
                         'alerts_before_common_ready': int((original_mask & frame[signal_col] & ~common).sum())})
        return result

    def redirect_csv(frame, path, *args, **kwargs):
        return actual_csv(frame, OUT / Path(path).name, *args, **kwargs)

    log = io.StringIO()
    with patch.object(runner, 'evaluate_recall', inspect_recall), patch.object(pd.DataFrame, 'to_csv', redirect_csv), contextlib.redirect_stdout(log):
        runner.run_baseline_evaluation()
    (OUT / 'run.log').write_text(log.getvalue(), encoding='utf-8')
    reproduced = pd.read_csv(OUT / 'incremental_report_m2.csv')
    submitted = pd.read_csv(SUB / 'incremental_report_m2.csv')
    assert reproduced.equals(submitted)

    synthetic = pd.DataFrame({'date': pd.bdate_range('2019-01-01', periods=6),
                              'close': [100.0, 95.0, 89.0, 80.0, 75.0, 83.0],
                              'alert': [False, False, False, False, True, False]})
    events = ev.identify_drawdown_events(synthetic)
    late = ev.evaluate_recall(events, synthetic, 'alert')
    assert late['recall_pct'] == 100.0
    tail = synthetic.assign(alert=[False, False, False, False, False, True])
    assert ev.evaluate_signals_m1(tail, 'alert')['Censored'] == 1
    missing = pd.DataFrame({'close': [100.0] + [np.nan] * 30 + [89.0] * 30,
                            'alert': [True] + [False] * 60})
    assert ev.evaluate_signals_m1(missing, 'alert')['Censored'] == 1
    unchanged = before == {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in SUB.iterdir() if p.is_file()}
    assert unchanged
    evidence = {'report_reproduced': True, 'censor_probes_fixed': True,
                'late_recall_counterexample': late, 'real_recall_details': captured,
                'submitted_files_unchanged': unchanged}
    (OUT / 'findings.json').write_text(json.dumps(evidence, indent=2, default=str), encoding='utf-8')
    print(reproduced.to_string(index=False))
    for index, r in enumerate(captured):
        bad = [e for e in r['events'] if e['caught_only_after_10pct']]
        outside = [e for e in r['events'] if e['trough'] > '2019-12-31']
        print(['NOW', 'QQQ', 'SPY'][index // 3], r['signal'],
              'pre_common_ready=', r['alerts_before_common_ready'],
              'caught_only_after_10pct=', len(bad), 'trough_after2019=', len(outside))
    print('M2_FOLLOWUP_REVIEW_COMPLETED: censor repairs pass; late recall counterexample remains')


if __name__ == '__main__':
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', (FutureWarning, RuntimeWarning))
        main()
