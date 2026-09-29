"""Read-only model audit using local data; write evidence only beside this file."""

import contextlib
import io
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from now_reflexivity_radar import NOWReflexivityRadar
from reflexivity_engine import run_universal_reflexivity_radar
from shared_executor import SharedExecutor


OUT = Path(__file__).resolve().parent


def inspect_frame(label, frame, price_col):
    """Expose all panic gates and a clearly defined pulse-mismatch count."""
    df = frame.copy()
    turned = (df.q1_dot > 0) & (df.q1_dot.shift(1) <= 0)
    df['regime_panic'] = (
        (df.Dist_200MA.rolling(20).min() < -15)
        | (df.Dist_200MA < -10) | (df.Composite_Score < 32)
    )
    df['gate_panic'] = (df.Dist_200MA <= 0) | (df[price_col] < df.MA50)
    df['turned_up'] = turned
    df['above_MA10'] = df[price_col] > df.MA10
    df['trend_buy'] = (df[price_col] > df.MA50).rolling(3).sum() == 3
    cols = [
        'date', price_col, 'q1', 'q1_dot', 'q1_ddot', 'v_dot',
        'Score_Dim3_Lyapunov', 'Score_Dim6_Macro', 'Composite_Score',
        'regime_panic', 'gate_panic', 'turned_up', 'above_MA10',
        'Trigger_Panic', 'Trigger_Bear_Top', 'trend_buy', 'action',
    ]
    selected = df.loc[df.date.between('2020-03-16', '2020-04-20'), cols]
    selected.to_csv(OUT / f'{label}_pandemic.csv', index=False)
    print('\nMODEL', label)
    print(selected.to_string(index=False, float_format=lambda x: f'{x:.4f}'))
    eligible = turned & df.regime_panic & df.gate_panic
    missed = eligible & ~df.above_MA10 & ~(df.Dist_200MA < -25)
    print('eligible_panic_turns=', int(eligible.sum()),
          'same_day_MA10_rejections=', int(missed.sum()))
    print('rejected_dates=', df.loc[missed, 'date'].dt.strftime('%Y-%m-%d').tolist())
    proposed = df.above_MA10 & (turned.rolling(5).max() > 0)
    stale = proposed & (df.q1_dot <= 0)
    print('proposed_window_with_nonpositive_momentum=', int(stale.sum()))


def main():
    radar = NOWReflexivityRadar()
    with contextlib.redirect_stdout(io.StringIO()):
        radar.load_and_preprocess()
        radar.compute_all_dimensions()
        radar.run_backtest()
    inspect_frame('NOW_dedicated', radar.df_bt, 'NOW')
    fills = pd.DataFrame(radar.result.fills)
    orders = pd.DataFrame(radar.result.orders)
    trades = fills.merge(orders[['order_id', 'submit_dt', 'reason']], on='order_id')
    trades = trades[~trades.reason.str.contains('Standing Order')]
    trades.to_csv(OUT / 'NOW_discretionary_fills.csv', index=False)
    print('\nNOW_DEDICATED_2020_FILLS')
    print(trades.loc[trades.dt.between('2020-03-01', '2020-12-31'),
                     ['submit_dt', 'dt', 'direction', 'price', 'reason']].to_string(index=False))
    print('NOW_DEDICATED_METRICS', radar.perf_metrics)

    captured = []

    class CapturedExecutor(SharedExecutor):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            captured.append(self)

    with patch('shared_executor.SharedExecutor', CapturedExecutor):
        generic = run_universal_reflexivity_radar(
            'NOW', pd.read_csv('now_ohlcv_local.csv'),
            pd.read_csv('market_data_local.csv'),
        )
    inspect_frame('NOW_universal', generic, 'close')
    gf = pd.DataFrame(captured[0].fills)
    gf.to_csv(OUT / 'NOW_universal_fills.csv', index=False)
    print('\nNOW_UNIVERSAL_2020_FILLS')
    print(gf.loc[gf.dt.between('2020-03-01', '2020-12-31'),
                 ['dt', 'direction', 'price']].to_string(index=False))
    print('READ_ONLY_AUDIT_OK')


if __name__ == '__main__':
    main()
