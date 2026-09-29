"""Independent diagnostic review; does not alter submitted models or reports."""
import hashlib
import json
from pathlib import Path
import sys
import warnings

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
HOME = Path(__file__).resolve().parent
SUB = HOME / 'v3_0_model_validity'
OUT = HOME / 'v3_0_m2_independent_review_20260924'
FROZEN = HOME / 'v2_3_independent_review' / 'frozen_inputs'
sys.path.insert(0, str(SUB))
from predictive_evaluator import (evaluate_signals_m1, generate_baseline_signals,
                                  generate_dynamical_candidates)


def compact(rows):
    n = len(rows)
    counts = {key: sum(r['class'] == key for r in rows) for key in ['TP', 'FP', 'Null']}
    values = [r['fwd_60'] for r in rows if pd.notna(r['fwd_60'])]
    return {'n': n, **counts, 'precision_pct': round(100 * counts['TP'] / n, 2) if n else None,
            'fwd60_median_pct': round(100 * float(np.median(values)), 2) if values else None}


def main():
    OUT.mkdir(exist_ok=True)
    before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in SUB.iterdir() if p.is_file()}
    macro = pd.read_csv(FROZEN / 'market_data_local.csv')
    prices = {'NOW': pd.read_csv(FROZEN / 'now_ohlcv_local.csv')}
    prices.update({a: macro[['date', a]].rename(columns={a: 'close'}) for a in ['QQQ', 'SPY']})
    evidence = {'scope': 'descriptive probes; no tuning and no candidate acceptance', 'assets': {}}
    reported = pd.read_csv(SUB / 'baseline_report_m2.csv')
    for asset, price in prices.items():
        df = generate_dynamical_candidates(generate_baseline_signals(price), macro_df=macro)
        dates = pd.to_datetime(df.date)
        common = df.V_Threshold.notna() & df.MA200.notna() & df.MA20.notna()
        eligible = (dates >= '2014-01-01') & (dates.shift(-60) <= '2019-12-31') & common
        out = {'input_start': str(dates.min().date()), 'common_ready_start': str(dates[common].min().date())}
        for model, col in [('Baseline', 'Baseline_Signal'), ('Dynamical_M2_Candidate', 'Dynamical_Signal')]:
            result = evaluate_signals_m1(df, col)
            original = [r for r in result['signal_results'] if str(r['signal_date']) <= '2019-12-31']
            early = [r for r in original if str(r['signal_date']) < '2014-01-01']
            crossing = [r for r in original if r['signal_idx'] + 60 < len(df)
                        and dates.iloc[r['signal_idx'] + 60] > pd.Timestamp('2019-12-31')]
            corrected = [r for r in original if eligible.iloc[r['signal_idx']]]
            expected = reported[(reported.Model == model) & (reported.Asset == asset)].iloc[0]
            assert compact(original)['n'] == expected.Total_Alerts
            assert compact(original)['TP'] == expected.TP_Hits
            assert compact(original)['FP'] == expected.FP_Misses
            assert compact(original)['precision_pct'] == expected['Absolute_Precision%']
            assert compact(original)['fwd60_median_pct'] == expected['Fwd_60_Med%']
            indices = [r['signal_idx'] for r in original]
            out[model] = {'submitted_reproduced': compact(original), 'pre2014': compact(early),
                          'labels_cross_2020': compact(crossing), 'same_period_common_ready_purged': compact(corrected),
                          'first_signal': str(original[0]['signal_date']) if original else None,
                          'adjacent_alert_gaps_le15_rows': int((np.diff(indices) <= 15).sum()),
                          'negative_x_signals': int(sum(df.x.iloc[i] < 0 for i in indices)),
                          'positive_v_signals': int(sum(df.v.iloc[i] > 0 for i in indices))}
        # Is dV dominated by the normalized-position term or by v^2?
        positive = df.loc[eligible & (df.x > 0)]
        potential = 0.5 * positive.k * positive.x_pos ** 2
        kinetic = 0.5 * positive.v ** 2
        out['median_potential_to_kinetic_ratio_positive_x'] = float((potential / kinetic.replace(0, np.nan)).median())
        evidence['assets'][asset] = out
        print(asset, json.dumps(out, ensure_ascii=False), flush=True)

    def probe(path, at):
        df = pd.DataFrame({'date': pd.bdate_range('2018-01-01', periods=len(path)),
                           'close': path, 'alert': False})
        df.loc[at, 'alert'] = True
        return compact(evaluate_signals_m1(df, 'alert')['signal_results'])

    evidence['right_censor_probe'] = probe([100.0] * 10, 9)
    evidence['missing_path_probe'] = probe([100.0] + [np.nan] * 30 + [89.0] * 30, 0)
    assert evidence['right_censor_probe']['Null'] == 1
    assert evidence['missing_path_probe']['TP'] == 1
    evidence['submitted_files_unchanged'] = before == {
        p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in SUB.iterdir() if p.is_file()}
    assert evidence['submitted_files_unchanged']
    (OUT / 'findings.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2), encoding='utf-8')
    print('M2_REVIEW_COMPLETED: submitted numbers reproduced; period and evaluator counterexamples confirmed')


if __name__ == '__main__':
    with warnings.catch_warnings():
        warnings.simplefilter('ignore', (FutureWarning, RuntimeWarning))
        main()
