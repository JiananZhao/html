import os
import sys
from pathlib import Path
import pandas as pd
import numpy as np
import json

sys.path.append(str(Path(__file__).parent))
from predictive_evaluator import evaluate_signals_m1, generate_baseline_signals, generate_dynamical_candidates, identify_drawdown_events, evaluate_recall

def block_bootstrap_median(returns: list, block_size: int = 60, num_bootstraps: int = 1000) -> tuple:
    """
    Compute 95% Confidence Interval for the median of forward returns using Block Bootstrapping.
    Handles overlapping 60-day windows by resampling blocks instead of individual observations.
    """
    if not returns or len(returns) < 5:
        return np.nan, np.nan, np.nan
        
    arr = np.array(returns)
    n = len(arr)
    
    # Simple stationary block bootstrap: sample blocks of length `block_size` with replacement
    boot_medians = []
    for _ in range(num_bootstraps):
        boot_sample = []
        while len(boot_sample) < n:
            start_idx = np.random.randint(0, max(1, n - block_size + 1))
            end_idx = min(start_idx + block_size, n)
            boot_sample.extend(arr[start_idx:end_idx])
            
        boot_sample = boot_sample[:n]  # truncate to exact size
        boot_medians.append(np.median(boot_sample))
        
    med = np.median(arr)
    ci_lower = np.percentile(boot_medians, 2.5)
    ci_upper = np.percentile(boot_medians, 97.5)
    return med, ci_lower, ci_upper

def run_m3_evaluation():
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
    signals_log = []
    events_log = []
    
    for name, df in assets.items():
        print(f"\nProcessing {name}...")
        
        # 1. Identify Events
        events_all = identify_drawdown_events(df, price_col='close', drop_threshold=0.10, recovery_threshold=0.10)
        
        # 2. Generate Features
        df_sig = generate_dynamical_candidates(df, macro_df=macro, price_col='close', k_window=252)
        df_sig['MA20'] = df_sig['close'].rolling(20).mean()
        
        # Determine first_valid_idx (Common Warm-up)
        # V_Threshold requires MA200 + 252_var + 252_quantile = approx 702
        first_valid_idx = df_sig['V_Threshold'].first_valid_index()
        if first_valid_idx is None:
            first_valid_idx = 702
            
        print(f"[{name}] Common Warm-up concludes at index: {first_valid_idx} (Date: {df_sig['date'].iloc[first_valid_idx]})")
        
        # Filter events for 2014-2019 AND peak >= first_valid_idx
        events_insample = [e for e in events_all if e['peak_idx'] >= first_valid_idx and e['peak_date'] <= '2019-12-31']
        for ev in events_insample:
            events_log.append({
                'Asset': name,
                'Peak_Date': ev['peak_date'],
                'Peak_Price': ev['peak_price'],
                'Break_Date': df_sig['date'].iloc[ev['break_idx']],
                'Trough_Date': ev['trough_date'],
                'Drawdown_Pct': round(ev['drawdown_pct'] * 100, 2)
            })
        
        # State A (Overheat): Fixed to Dynamical Overheat
        df_sig['Overheat_A'] = df_sig['Dynamical_Overheat']
        df_sig['Active_A_15d'] = df_sig['Overheat_A'].rolling(15).max().fillna(0).astype(bool)
        
        # Weakness B Conditions
        df_sig['Weakness_B1_dV'] = df_sig['dV'] <= 0
        df_sig['Weakness_B2_v'] = df_sig['v'] < 0
        df_sig['Weakness_B3_MA20'] = df_sig['close'] < df_sig['MA20']
        
        for b_name, b_col in [('B1_dV', 'Weakness_B1_dV'), ('B2_v', 'Weakness_B2_v'), ('B3_MA20', 'Weakness_B3_MA20')]:
            raw_col = f'Raw_{b_name}'
            df_sig[raw_col] = df_sig['Active_A_15d'] & df_sig[b_col]
            df_sig[f'Signal_{b_name}'] = df_sig[raw_col] & (~df_sig[raw_col].shift(1).fillna(False))
        
        models = [
            ('Signal_B3_MA20', 'B3: P<MA20 (Baseline)'),
            ('Signal_B1_dV', 'B1: dV<=0 (Energy)'),
            ('Signal_B2_v', 'B2: v<0 (Velocity)')
        ]
        
        idx_2019_end = df_sig[df_sig['date'] <= '2019-12-31'].index[-1]
        
        for sig_col, prefix in models:
            eval_res = evaluate_signals_m1(df_sig, sig_col, price_col='close', window=60, threshold=0.10)
            recall_res = evaluate_recall(events_insample, df_sig, sig_col, lead_window=60, min_idx=first_valid_idx)
            
            in_sample = []
            for r in eval_res['signal_results']:
                # Apply Common Warmup & Time Boundary
                if r['signal_idx'] >= first_valid_idx and r['signal_date'] <= '2019-12-31' and r['signal_idx'] + 60 <= idx_2019_end:
                    in_sample.append(r)
                    r['Asset'] = name
                    r['Model'] = prefix
                    signals_log.append(r)
            
            tp = sum(1 for r in in_sample if r['class'] == 'TP')
            fp = sum(1 for r in in_sample if r['class'] == 'FP')
            null_c = sum(1 for r in in_sample if r['class'] == 'Null')
            cens_c = sum(1 for r in in_sample if r['class'] == 'Censored')
            tot = tp + fp + null_c  
            
            abs_win = (tp / tot * 100) if tot > 0 else np.nan
            
            fwd_60 = [r['fwd_60'] for r in in_sample if r['class'] != 'Censored' and pd.notna(r['fwd_60'])]
            med, ci_lower, ci_upper = block_bootstrap_median(fwd_60, block_size=60)
            
            report.append({
                'Model': prefix,
                'Asset': name,
                'Alerts': tot,
                'TP': tp,
                'FP': fp,
                'Null': null_c,
                'Abs_Prec%': f"{abs_win:.2f}" if not np.isnan(abs_win) else "N/A",
                'Recall_Adv%': recall_res['recall_advance_pct'],
                'Caught_Adv': recall_res['caught_advance'],
                'Caught_Same': recall_res['caught_sameday'],
                'Fwd_60_Med%': f"{med*100:.2f}" if not np.isnan(med) else "N/A",
                'Fwd_60_CI95': f"[{ci_lower*100:.2f}, {ci_upper*100:.2f}]" if not np.isnan(ci_lower) else "N/A"
            })
            
    df_report = pd.DataFrame(report)
    print("\n--- M3 CONTROLLED PREDICTIVE VALIDITY EVALUATION ---")
    print(df_report.to_string(index=False))
    
    out_dir = Path(__file__).parent
    df_report.to_csv(out_dir / 'm3_summary_report.csv', index=False)
    pd.DataFrame(signals_log).to_csv(out_dir / 'm3_signals_log.csv', index=False)
    pd.DataFrame(events_log).to_csv(out_dir / 'm3_events_log.csv', index=False)
    print(f"\nArtifacts saved to {out_dir}")

if __name__ == "__main__":
    run_m3_evaluation()
