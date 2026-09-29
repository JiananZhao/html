"""Independent reproduction of M3 and diagnostic bootstrap counterexamples."""
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
OUT = HOME / 'v3_0_m3_independent_review_20260924'
sys.path.insert(0, str(SUB))
import run_m3_evaluation as m3


def main():
    OUT.mkdir(exist_ok=True)
    before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in SUB.iterdir() if p.is_file()}
    real_csv = pd.DataFrame.to_csv

    def redirect(frame, path, *args, **kwargs):
        return real_csv(frame, OUT / Path(path).name, *args, **kwargs)

    np.random.seed(20260924)
    log = io.StringIO()
    with contextlib.redirect_stdout(log), patch.object(pd.DataFrame, 'to_csv', redirect):
        m3.run_m3_evaluation()
    (OUT / 'run.log').write_text(log.getvalue(), encoding='utf-8')
    summary = pd.read_csv(OUT / 'm3_summary_report.csv')
    submitted = pd.read_csv(SUB / 'm3_summary_report.csv')
    assert summary.drop(columns='Fwd_60_CI95').equals(submitted.drop(columns='Fwd_60_CI95'))
    for name in ['m3_signals_log.csv', 'm3_events_log.csv']:
        assert pd.read_csv(OUT / name).equals(pd.read_csv(SUB / name))
    signals = pd.read_csv(OUT / 'm3_signals_log.csv')
    events = pd.read_csv(OUT / 'm3_events_log.csv')
    early = signals[signals.signal_date < '2014-01-01']
    early_counts = early.groupby(['Asset', 'Model']).agg(
        alerts=('class', 'size'), tp=('class', lambda x: int((x == 'TP').sum()))).reset_index()
    event_counts = events[events.Peak_Date < '2014-01-01'].groupby('Asset').size().to_dict()
    probes = {}
    for n in [17, 25, 44, 60]:
        values = np.linspace(-0.3, 0.3, n).tolist()
        med, lo, hi = m3.block_bootstrap_median(values, block_size=60, num_bootstraps=100)
        assert med == lo == hi
        probes[str(n)] = {'distinct_returns': n, 'median': med, 'lower': lo, 'upper': hi}
    unchanged = before == {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in SUB.iterdir() if p.is_file()}
    assert unchanged
    evidence = {'all_non_ci_summary_values_reproduced': True, 'both_ledgers_reproduced': True,
                'pre2014_alerts': early_counts.to_dict('records'), 'pre2014_events': event_counts,
                'bootstrap_degenerate_probes': probes,
                'audit_seed': 20260924, 'submitted_files_unchanged': unchanged}
    (OUT / 'findings.json').write_text(json.dumps(evidence, indent=2), encoding='utf-8')
    print(early_counts.to_string(index=False))
    print('PRE2014_EVENTS', event_counts)
    print('BOOTSTRAP_DEGENERATE_AT_N', list(probes))
    print('M3_REVIEW_COMPLETED: period regression and degenerate intervals confirmed')


if __name__ == '__main__':
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', (FutureWarning, RuntimeWarning))
        main()
