import numpy as np
import pandas as pd
from typing import Dict, Any, List

def identify_drawdown_events(df: pd.DataFrame, price_col: str = 'close', drop_threshold: float = 0.10, recovery_threshold: float = 0.10) -> List[Dict[str, Any]]:
    # ... (same as before, keeping this unchanged) ...
    p = df[price_col].values
    n = len(p)
    events = []
    
    in_drawdown = False
    peak_idx = 0
    peak_price = p[0]
    trough_idx = 0
    trough_price = p[0]
    
    for i in range(1, n):
        if not in_drawdown:
            if pd.notna(p[i]) and p[i] > peak_price:
                peak_price = p[i]
                peak_idx = i
            elif pd.notna(p[i]) and (peak_price - p[i]) / peak_price >= drop_threshold:
                in_drawdown = True
                break_idx = i
                trough_price = p[i]
                trough_idx = i
        else:
            if pd.notna(p[i]) and p[i] < trough_price:
                trough_price = p[i]
                trough_idx = i
            elif pd.notna(p[i]) and (p[i] - trough_price) / trough_price >= recovery_threshold:
                events.append({
                    'peak_idx': int(peak_idx),
                    'peak_date': df['date'].iloc[peak_idx] if 'date' in df.columns else None,
                    'peak_price': peak_price,
                    'break_idx': int(break_idx),
                    'trough_idx': int(trough_idx),
                    'trough_date': df['date'].iloc[trough_idx] if 'date' in df.columns else None,
                    'trough_price': trough_price,
                    'drawdown_pct': (peak_price - trough_price) / peak_price
                })
                in_drawdown = False
                peak_price = p[i]
                peak_idx = i
                
    if in_drawdown:
        events.append({
            'peak_idx': int(peak_idx),
            'peak_date': df['date'].iloc[peak_idx] if 'date' in df.columns else None,
            'peak_price': peak_price,
            'break_idx': int(break_idx),
            'trough_idx': int(trough_idx),
            'trough_date': df['date'].iloc[trough_idx] if 'date' in df.columns else None,
            'trough_price': trough_price,
            'drawdown_pct': (peak_price - trough_price) / peak_price
        })
        
    return events


def evaluate_signals_m1(df: pd.DataFrame, signal_col: str, price_col: str = 'close', window: int = 60, threshold: float = 0.10) -> Dict[str, Any]:
    # ... (same as before, keeping this unchanged) ...
    p = df[price_col].values
    n = len(p)
    signals = np.where(df[signal_col])[0]
    
    tp_count = 0
    fp_count = 0
    null_count = 0
    
    signal_results = []
    
    for s in signals:
        anchor_p = p[s]
        hit_tp = False
        hit_fp = False
        res_class = 'Null'
        has_nan = False
        end_idx = min(s + 1 + window, n)
        
        if pd.isna(anchor_p) or anchor_p == 0:
            continue
            
        for i in range(s + 1, end_idx):
            if pd.isna(p[i]):
                has_nan = True
                continue
            ret = (p[i] - anchor_p) / anchor_p
            if ret <= -threshold:
                hit_tp = True
                res_class = 'Censored' if has_nan else 'TP'
                break
            elif ret >= threshold:
                hit_fp = True
                res_class = 'Censored' if has_nan else 'FP'
                break
                
        if not hit_tp and not hit_fp:
            if end_idx < s + 1 + window:
                res_class = 'Censored'
            elif has_nan:
                res_class = 'Censored'
            else:
                res_class = 'Null'
                
        if res_class == 'TP':
            tp_count += 1
        elif res_class == 'FP':
            fp_count += 1
        elif res_class == 'Null':
            null_count += 1
            
        fwd_20 = (p[s+20] - anchor_p) / anchor_p if s+20 < n and pd.notna(p[s+20]) else np.nan
        fwd_40 = (p[s+40] - anchor_p) / anchor_p if s+40 < n and pd.notna(p[s+40]) else np.nan
        fwd_60 = (p[s+60] - anchor_p) / anchor_p if s+60 < n and pd.notna(p[s+60]) else np.nan
        
        signal_results.append({
            'signal_idx': int(s),
            'signal_date': df['date'].iloc[s] if 'date' in df.columns else None,
            'anchor_price': anchor_p,
            'class': res_class,
            'fwd_20': fwd_20,
            'fwd_40': fwd_40,
            'fwd_60': fwd_60
        })
        
    total = tp_count + fp_count + null_count
    abs_win_rate = tp_count / total if total > 0 else 0.0
    cond_win_rate = tp_count / (tp_count + fp_count) if (tp_count + fp_count) > 0 else 0.0
    
    # Exclude censored from medians or include? Usually exclude.
    valid_res = [r for r in signal_results if r['class'] != 'Censored']
    fwd_20_med = np.nanmedian([r['fwd_20'] for r in valid_res if pd.notna(r['fwd_20'])]) if valid_res else np.nan
    fwd_40_med = np.nanmedian([r['fwd_40'] for r in valid_res if pd.notna(r['fwd_40'])]) if valid_res else np.nan
    fwd_60_med = np.nanmedian([r['fwd_60'] for r in valid_res if pd.notna(r['fwd_60'])]) if valid_res else np.nan
    
    return {
        'total_signals': total,
        'TP': tp_count,
        'FP': fp_count,
        'Null': null_count,
        'Censored': len(signal_results) - total,
        'abs_win_rate_pct': round(abs_win_rate * 100, 2),
        'cond_win_rate_pct': round(cond_win_rate * 100, 2),
        'fwd_20_median_pct': round(fwd_20_med * 100, 2) if not np.isnan(fwd_20_med) else None,
        'fwd_40_median_pct': round(fwd_40_med * 100, 2) if not np.isnan(fwd_40_med) else None,
        'fwd_60_median_pct': round(fwd_60_med * 100, 2) if not np.isnan(fwd_60_med) else None,
        'signal_results': signal_results
    }

def evaluate_recall(events: List[Dict[str, Any]], signals_df: pd.DataFrame, signal_col: str, lead_window: int = 60, min_idx: int = 0) -> Dict[str, Any]:
    """
    Evaluate Recall and Lead Time.
    - An event is an 'advance_warning' if signal arrives < break_idx.
    - An event is 'sameday_confirmation' if signal arrives == break_idx.
    - Both must be >= peak_idx - lead_window.
    """
    signals = np.where(signals_df[signal_col])[0]
    caught_advance = 0
    caught_sameday = 0
    
    # Only consider events whose peak is after min_idx
    valid_events = [ev for ev in events if ev['peak_idx'] >= min_idx]
    total_events = len(valid_events)
    lead_times = []
    
    for ev in valid_events:
        peak_idx = ev['peak_idx']
        break_idx = ev['break_idx']
        
        valid_signals = [s for s in signals if peak_idx - lead_window <= s <= break_idx]
        
        if len(valid_signals) > 0:
            first_sig = valid_signals[0]
            
            if first_sig < break_idx:
                caught_advance += 1
                cat = 'advance_warning'
            else:
                caught_sameday += 1
                cat = 'sameday_confirmation'
                
            lead_times.append({
                'event_peak_date': ev['peak_date'],
                'first_signal_idx': first_sig,
                'first_signal_date': signals_df['date'].iloc[first_sig] if 'date' in signals_df.columns else None,
                'type': cat,
                'days_to_break': break_idx - first_sig
            })
                
    recall_advance = caught_advance / total_events if total_events > 0 else 0.0
    return {
        'total_events': total_events,
        'caught_advance': caught_advance,
        'caught_sameday': caught_sameday,
        'recall_advance_pct': round(recall_advance * 100, 2),
        'lead_times': lead_times
    }



def generate_baseline_signals(df: pd.DataFrame, price_col: str = 'close', overheat_threshold: float = 1.20) -> pd.DataFrame:
    """
    Generate M2 Simple Baselines.
    Baseline 1 (Overheat): Close > MA200 by threshold (e.g., +20%).
    Baseline 2 (Weakness): Close < MA20.
    """
    df = df.copy()
    df['MA200'] = df[price_col].rolling(200).mean()
    df['MA20'] = df[price_col].rolling(20).mean()
    
    # State 1: Overheat (Trend Deviation)
    df['Baseline_Overheat'] = df[price_col] > df['MA200'] * overheat_threshold
    
    # State 2: Weakness (Momentum Reversal)
    df['Baseline_Weakness'] = df[price_col] < df['MA20']
    
    # TTL Logic: Overheat active if happened in last 15 days
    df['Overheat_Active_15d'] = df['Baseline_Overheat'].rolling(15).max() > 0
    
    # Baseline Final Signal
    # Active overheat + current weakness. 
    # Edge detection: trigger only on the FIRST day weakness is confirmed.
    df['Combined_Raw'] = df['Overheat_Active_15d'] & df['Baseline_Weakness']
    df['Baseline_Signal'] = df['Combined_Raw'] & (~df['Combined_Raw'].shift(1).fillna(False))
    
    return df


def generate_dynamical_candidates(df: pd.DataFrame, macro_df: pd.DataFrame = None, price_col: str = 'close', k_window: int = 252) -> pd.DataFrame:
    """
    Generate M2 Optional Dynamical Candidates.
    Hypothesis: 
    - The market behaves statistically like a damped harmonic oscillator subject to macro-driven restoring forces.
    - V = 0.5 * k * x^2 + 0.5 * v^2
    - x(t): Log price deviation from MA200
    - v(t): Velocity (e.g. 5-day diff of x)
    - k(t): Restoring force parameter, driven by localized variance and Macro Stress (e.g. NFCI).
    - Signal Hypothesis: Active when V > V_threshold (high potential energy / bubble) AND dV/dt <= 0 (energy dissipation / momentum breaking).
    """
    df = df.copy()
    
    if macro_df is not None and 'NFCI' in macro_df.columns:
        # Merge NFCI into df on 'date'
        df = pd.merge(df, macro_df[['date', 'NFCI']], on='date', how='left')
        df['NFCI'] = df['NFCI'].ffill().fillna(0)
    else:
        df['NFCI'] = 0.0
        
    df['MA200'] = df[price_col].rolling(200).mean()
    
    # 1. State Variables
    # x(t): Deviation from trend
    df['x'] = np.log(df[price_col]) - np.log(df['MA200'])
    # Only care about positive bubbles for overheat
    df['x_pos'] = df['x'].clip(lower=0)
    
    # v(t): Velocity (rate of change of deviation)
    df['v'] = df['x'].diff(5) / 5.0
    
    # 2. Parameter Identification: Restoring Force k(t)
    # Base k0: Inverse of rolling 252-day variance of x
    df['x_var'] = df['x'].rolling(k_window).var()
    df['k0'] = 1.0 / df['x_var'].replace(0, np.nan)
    
    # Macro Multiplier: Tight liquidity (NFCI > 0) increases the restoring force exponentially
    # Loose liquidity (NFCI < 0) decreases the restoring force
    alpha = 1.0  # Macro sensitivity coefficient
    df['macro_multiplier'] = np.exp(alpha * df['NFCI'])
    df['k'] = df['k0'] * df['macro_multiplier']
    
    # 3. Energy Function V(x, v)
    # We use x_pos here because we are looking for over-valuation (bubble) risks, not undervalued crashes.
    df['V'] = 0.5 * df['k'] * (df['x_pos'] ** 2) + 0.5 * (df['v'] ** 2)
    
    # 4. Discrete Derivative of V (dV/dt)
    # Note: Because k is time-varying, dV includes the 0.5 * dk * x^2 term automatically in discrete diff.
    df['dV'] = df['V'].diff(1)
    
    # 5. Signal Conditions (Hypothesis)
    # Condition 1: High Energy State (V is in the top 5% of its rolling 2-year history)
    df['V_Threshold'] = df['V'].rolling(k_window).quantile(0.95)
    df['Dynamical_Overheat'] = df['V'] > df['V_Threshold']
    
    # Condition 2: Energy Dissipation (dV <= 0)
    # The system is losing energy (momentum is failing against the restoring force)
    df['Dynamical_Weakness'] = df['dV'] <= 0
    
    # TTL Logic: Overheat state can be preserved for 15 days
    df['Dyn_Overheat_Active_15d'] = df['Dynamical_Overheat'].rolling(15).max() > 0
    
    # Final Signal: Overheat is/was active, and weakness is confirmed today.
    # Edge detection: trigger on the first day of weakness.
    df['Dyn_Combined_Raw'] = df['Dyn_Overheat_Active_15d'] & df['Dynamical_Weakness']
    df['Dynamical_Signal'] = df['Dyn_Combined_Raw'] & (~df['Dyn_Combined_Raw'].shift(1).fillna(False))
    
    return df
