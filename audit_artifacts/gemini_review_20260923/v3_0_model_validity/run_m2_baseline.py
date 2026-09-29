import os
import sys
from pathlib import Path
import pandas as pd
import numpy as np
import json

sys.path.append(str(Path(__file__).parent))
from predictive_evaluator import evaluate_signals_m1, generate_baseline_signals, generate_dynamical_candidates, identify_drawdown_events, evaluate_recall

def run_baseline_evaluation():
    ROOT = Path("E:/AI/Github_AIProject/html")
    FROZEN_DIR = ROOT / 'audit_artifacts' / 'gemini_review_20260923' / 'v2_3_independent_review' / 'frozen_inputs'
    
    macro_path = FROZEN_DIR / 'market_data_local.csv'
    now_path = FROZEN_DIR / 'now_ohlcv_local.csv'
    
    if not macro_path.exists() or not now_path.exists():
        print(f"Error: Frozen data not found in {FROZEN_DIR}")
        return
        
    macro = pd.read_csv(macro_path)
    now_prices = pd.read_csv(now_path)
    
    qqq_prices = macro[['date', 'QQQ']].rename(columns={'QQQ': 'close'})
    spy_prices = macro[['date', 'SPY']].rename(columns={'SPY': 'close'})
    
    assets = {
        'NOW': now_prices,
        'QQQ': qqq_prices,
        'SPY': spy_prices
    }
    
    report = []
    
    for name, df in assets.items():
        print(f"\nProcessing {name}...")
        
        # Identify Events on FULL data first, then filter later
        events_all = identify_drawdown_events(df, price_col='close', drop_threshold=0.10, recovery_threshold=0.10)
        
        # Filter events whose peak is in 2014-2019
        events_insample = [e for e in events_all if '2014-01-01' <= e['peak_date'] <= '2019-12-31']
        
        # 1. Generate Dynamical Variables (This computes x, v, k, V, dV, MA20, MA200)
        df_sig = generate_dynamical_candidates(df, macro_df=macro, price_col='close', k_window=252)
        df_sig['MA20'] = df_sig['close'].rolling(20).mean()
        
        # State A (Overheat): Fixed to Dynamical Overheat (V > 95th percentile)
        df_sig['Overheat_A'] = df_sig['Dynamical_Overheat']
        df_sig['Active_A_15d'] = df_sig['Overheat_A'].rolling(15).max().fillna(0).astype(bool)
        
        # Weakness B Conditions (States)
        df_sig['Weakness_B1_dV'] = df_sig['dV'] <= 0
        df_sig['Weakness_B2_v'] = df_sig['v'] < 0
        df_sig['Weakness_B3_MA20'] = df_sig['close'] < df_sig['MA20']
        
        # Combine and apply uniform edge detection (first day of intersection)
        for b_name, b_col in [('B1_dV', 'Weakness_B1_dV'), ('B2_v', 'Weakness_B2_v'), ('B3_MA20', 'Weakness_B3_MA20')]:
            raw_col = f'Raw_{b_name}'
            df_sig[raw_col] = df_sig['Active_A_15d'] & df_sig[b_col]
            df_sig[f'Signal_{b_name}'] = df_sig[raw_col] & (~df_sig[raw_col].shift(1).fillna(False))
        
        models = [
            ('Signal_B1_dV', 'Dyn_A + dV<=0'),
            ('Signal_B2_v', 'Dyn_A + v<0'),
            ('Signal_B3_MA20', 'Dyn_A + P<MA20')
        ]
        
        # Warmup and Boundaries
        # Max lookback is 252 (for k_window). So we ignore any signals before idx 252.
        idx_2019_end = df_sig[df_sig['date'] <= '2019-12-31'].index[-1]
        
        for sig_col, prefix in models:
            eval_res = evaluate_signals_m1(df_sig, sig_col, price_col='close', window=60, threshold=0.10)
            recall_res = evaluate_recall(events_insample, df_sig, sig_col, lead_window=60)
            
            in_sample = []
            for r in eval_res['signal_results']:
                # Common warmup (>= 252), and inside In-Sample period
                if r['signal_idx'] >= 252 and '2014-01-01' <= r['signal_date'] and r['signal_idx'] + 60 <= idx_2019_end:
                    in_sample.append(r)
            
            tp = sum(1 for r in in_sample if r['class'] == 'TP')
            fp = sum(1 for r in in_sample if r['class'] == 'FP')
            null_c = sum(1 for r in in_sample if r['class'] == 'Null')
            cens_c = sum(1 for r in in_sample if r['class'] == 'Censored')
            tot = tp + fp + null_c  
            
            abs_win = (tp / tot * 100) if tot > 0 else 0.0
            
            fwd_60 = [r['fwd_60'] for r in in_sample if r['class'] != 'Censored' and pd.notna(r['fwd_60'])]
            
            report.append({
                'Model': prefix,
                'Asset': name,
                'Alerts': tot,
                'TP': tp,
                'FP': fp,
                'Null': null_c,
                'Censored': cens_c,
                'Abs_Prec%': round(abs_win, 2),
                'Recall%': recall_res['recall_pct'],
                'Caught_Ev': recall_res['caught_events'],
                'Fwd_60_Med%': round(np.median(fwd_60) * 100, 2) if fwd_60 else None
            })
            
    df_report = pd.DataFrame(report)
    print("\n--- M2 WEAKNESS ABLATION STUDY (2014-2019 FULLY IN-SAMPLE, WARMUP=252) ---")
    print(df_report.to_string(index=False))
    
    out_path = Path(__file__).parent / 'ablation_report_m2.csv'
    df_report.to_csv(out_path, index=False)
    print(f"\nReport saved to {out_path}")

if __name__ == "__main__":
    run_baseline_evaluation()
