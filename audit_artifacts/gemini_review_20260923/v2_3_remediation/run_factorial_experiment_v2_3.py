"""
Universal Reflexivity Radar Factorial Ablation Experiment Engine v2.3
=====================================================================
Remediation Release v2.3 strictly adhering to:
1. Strict Frozen Specification:
   - Zero model drift: exact 2020-03-20 values and full history features.
   - Complete removal of unapproved stop cooldown state and timer.
   - Factor C exit mode returns directly to 'NONE' upon stop loss fill.
2. Trade & Risk Clock Decoupling:
   - Stop loss timer decrements on every holding day (pos == 1.0, not re-entry fill day).
   - Missing price days and unready days advance the trading calendar clock.
   - Stop loss price check runs whenever price is valid, independently of macro signal_ready.
3. Protected DCA Follow-up & NEXT_CLOSE Timing:
   - DCA orders protect pending risk sell orders (never cancels them).
   - DCA catch-up invests delayed cash as soon as price quote is valid.
4. Valuation Integrity (Zero Cost Fallback):
   - Open position stale valuation strictly matches executor's last_valid_price.
   - Forward return evaluation requires both start quote and horizon quote to be valid.
5. Signal Extrema Evaluation Window & End Truncation:
   - Both buy and sell extrema matching use [S - 15, S + 5].
   - Truncation mask [window : n - 60] applies to both signals and extrema in denominators.
6. Continuous Full-History Signal Generation Before Slicing:
   - Signals generated on continuous full history before slicing to research period.
   - Dedicated sub-period evaluation (Mode A Inherited Attribution vs Mode B Fresh Reset).
"""

import sys
import os
import bisect
from pathlib import Path
from typing import Dict, Any, List, Tuple
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT))

from shared_executor import SharedExecutor
from true_accounting import UnitizedAccount, calculate_xirr
from reflexivity_engine import run_universal_reflexivity_radar

OUT_DIR = Path(__file__).resolve().parent


def expanding_rank(s: pd.Series, min_periods: int = 100) -> pd.Series:
    """Historical expanding percentile ranking [0, 100] strictly per frozen Spec v2.0."""
    vals = s.values
    n = len(vals)
    res = np.full(n, np.nan)
    sorted_arr: List[float] = []
    for i in range(n):
        v = vals[i]
        if np.isnan(v):
            continue
        pos_left = bisect.bisect_left(sorted_arr, v)
        pos_right = bisect.bisect_right(sorted_arr, v)
        sorted_arr.insert(pos_right, v)
        N_t = len(sorted_arr)
        if N_t >= min_periods:
            E_t = pos_right - pos_left + 1
            res[i] = 100.0 * (pos_left + 0.5 * E_t) / N_t
    return pd.Series(res, index=s.index)


def prepare_base_features(df_p: pd.DataFrame, df_m: pd.DataFrame, price_col: str = 'close') -> pd.DataFrame:
    """
    Compute base features without making signal decisions.
    Strictly equivalent to frozen Spec v2.0 with production signal_ready dependency.
    """
    df = df_p.copy()
    df['date'] = pd.to_datetime(df['date']).dt.tz_localize(None)
    df_m = df_m.copy()
    df_m['date'] = pd.to_datetime(df_m['date']).dt.tz_localize(None)
    
    macro_cols = ['HYG', 'BAA10Y', 'NFCI', 'Real_Yield']
    df = pd.merge(df, df_m[['date'] + macro_cols], on='date', how='left')
    df = df.sort_values('date').reset_index(drop=True)
    df[macro_cols] = df[macro_cols].ffill(limit=5)
    df = df.dropna(subset=macro_cols).reset_index(drop=True)
    
    p = df[price_col]
    df['MA10'] = p.rolling(10).mean()
    df['MA20'] = p.rolling(20).mean()
    df['MA50'] = p.rolling(50).mean()
    df['MA200'] = p.rolling(200).mean()
    df['Dist_200MA'] = (p - df['MA200']) / (df['MA200'] + 1e-8) * 100.0
    df['Dist_50MA'] = (p - df['MA50']) / (df['MA50'] + 1e-8) * 100.0
    df['MA200_Slope'] = (df['MA200'] - df['MA200'].shift(10)) / (df['MA200'].shift(10) + 1e-8) * 100.0
    
    df['q1'] = df['Dist_200MA']
    df['q1_dot'] = (df['q1'] - df['q1'].shift(10)) / 10.0
    df['q1_ddot'] = (df['q1_dot'] - df['q1_dot'].shift(5)) / 5.0
    tau = 100.0
    df['v_dot'] = df['q1_dot'] * (df['q1'] + tau * df['q1_ddot'])
    
    df['Quadrant'] = 0
    df.loc[(df['q1'] >= 0) & (df['q1_dot'] >= 0), 'Quadrant'] = 1
    df.loc[(df['q1'] < 0) & (df['q1_dot'] >= 0), 'Quadrant'] = 2
    df.loc[(df['q1'] < 0) & (df['q1_dot'] < 0), 'Quadrant'] = 3
    df.loc[(df['q1'] >= 0) & (df['q1_dot'] < 0), 'Quadrant'] = 4
    
    if 'high' in df.columns and 'low' in df.columns and 'volume' in df.columns:
        hr = (df['high'] - df['low']).replace(0, np.nan)
        clv = ((2 * p - (df['high'] + df['low'])) / hr).fillna(0.0)
        df['CMF20'] = (clv * df['volume']).rolling(20).sum() / (df['volume'].rolling(20).sum() + 1e-8)
        df['Vol_Ratio50'] = df['volume'] / (df['volume'].rolling(50).mean() + 1e-8)
        score_dim5 = (expanding_rank(df['CMF20']) * 0.6 + expanding_rank(df['Vol_Ratio50']) * 0.4)
    else:
        score_dim5 = pd.Series(50.0, index=df.index)
        
    df['Score_Dim1_Pos'] = expanding_rank(df['q1'])
    df['Score_Dim2_Vel'] = expanding_rank(df['q1_dot'])
    df['Score_Dim3_Lyapunov'] = expanding_rank(df['v_dot'])
    df['Score_Dim5_Liquidity'] = score_dim5
    df['Score_Dim6_Macro'] = (expanding_rank(df['BAA10Y']) * 0.5 + expanding_rank(df['NFCI']) * 0.5)
    
    # Composite Score M0
    df['Composite_Score_M0'] = (
        df['Score_Dim1_Pos'] * 0.30 +
        df['Score_Dim2_Vel'] * 0.20 +
        df['Score_Dim3_Lyapunov'] * 0.20 +
        df['Score_Dim5_Liquidity'] * 0.10 +
        df['Score_Dim6_Macro'] * 0.20
    )
    
    # Factor A Decoupled Scores (Strict Spec v2.0)
    q1_dot_pos = np.maximum(df['q1_dot'], 0.0)
    v_dot_pos = np.maximum(df['q1'], 0.0) * np.maximum(df['q1_dot'], 0.0)
    df['Score_Overheat_A'] = (
        df['Score_Dim1_Pos'] * 0.50 +
        expanding_rank(q1_dot_pos) * 0.30 +
        expanding_rank(v_dot_pos) * 0.20
    )
    df['Score_MacroStress_A'] = df['Score_Dim6_Macro']
    df['Score_PanicDepth_A'] = (
        expanding_rank(-df['q1']) * 0.60 +
        expanding_rank(np.maximum(-df['q1_dot'], 0.0)) * 0.40
    )
    
    df['Macro_MA200'] = df['HYG'].rolling(200).mean()
    df['RY_Surge'] = (df['Real_Yield'] - df['Real_Yield'].rolling(60).min()) > 0.35
    df['macro_crisis_regime'] = (df['HYG'] < df['Macro_MA200']) & ((df['NFCI'] > -0.40) | df['RY_Surge'])
    
    # Reflexive Gap & Production Readiness Dependency
    df['Price_Z'] = (p - df['MA200']) / (p.rolling(200).std() + 1e-8)
    df['Macro_Z'] = (df['HYG'] - df['Macro_MA200']) / (df['HYG'].rolling(200).std() + 1e-8)
    roll_cov = df['Price_Z'].rolling(252).cov(df['Macro_Z'])
    roll_var = df['Macro_Z'].rolling(252).var()
    df['Dynamic_Beta'] = (roll_cov / (roll_var + 1e-8)).clip(lower=-2.0, upper=2.0)
    df['Expected_Price_Z'] = df['Macro_Z'] * df['Dynamic_Beta']
    df['Gap'] = df['Price_Z'] - df['Expected_Price_Z']
    df['Gap_Max_45'] = df['Gap'].rolling(45, min_periods=1).max()
    
    core_cols = ['Composite_Score_M0', 'Gap_Max_45', 'Dist_200MA', 'NFCI', 'BAA10Y', 'HYG', 'Real_Yield', price_col, 'MA200', 'MA50', 'MA10']
    df['signal_ready'] = df[core_cols].notna().all(axis=1)
    
    return df


def generate_signals(
    df: pd.DataFrame,
    use_factor_a: bool = False,
    use_factor_b: bool = False,
    use_factor_c: bool = False,
    price_col: str = 'close'
) -> pd.DataFrame:
    """Generate signal masks and indicators strictly following v2.0 frozen specifications."""
    df = df.copy()
    p = df[price_col]
    n = len(df)
    
    # -------------------------------------------------------------
    # 1. Panic Bottom Regime & Trigger
    # -------------------------------------------------------------
    if not use_factor_a:
        regime_panic_raw = (df['Dist_200MA'].rolling(20).min() < -15.0) | (df['Dist_200MA'] < -10.0) | (df['Composite_Score_M0'] < 32.0)
    else:
        regime_panic_raw = (df['Dist_200MA'].rolling(20).min() < -15.0) | (df['Dist_200MA'] < -10.0) | (df['Score_PanicDepth_A'] >= 80.0)
        
    ma50 = df['MA50'] if 'MA50' in df.columns else p.rolling(50).mean()
    ma10 = df['MA10'] if 'MA10' in df.columns else p.rolling(10).mean()
    gate_panic = (df['Dist_200MA'] <= 0.0) | (p < ma50)
    turned_up = (df['q1_dot'] > 0) & (df['q1_dot'].shift(1) <= 0)
    
    if not use_factor_b:
        inflection_panic = ((p > ma10) & turned_up) | ((df['Dist_200MA'] < -25.0) & turned_up)
        raw_panic = regime_panic_raw & gate_panic & inflection_panic
        
        flags = np.zeros(n, dtype=bool)
        last_dt = None
        last_p = None
        for i in range(n):
            if raw_panic.iloc[i]:
                dt = df['date'].iloc[i]
                p_val = p.iloc[i]
                cal_days = (dt - last_dt).days if last_dt is not None else 999
                price_drop_ok = (p_val < last_p * 0.93) if (last_p is not None and pd.notna(p_val)) else True
                if cal_days > 15 or price_drop_ok:
                    flags[i] = True
                    last_dt = dt
                    last_p = p_val
        df['Trigger_Panic'] = pd.Series(flags, index=df.index)
    else:
        # Factor B: Panic Memory Latch with calendar-day hysteresis non-consumption
        K_window = 15
        latch = False
        timer = 0
        p_anchor = 0.0
        raw_panic_arr = np.zeros(n, dtype=bool)
        last_dt = None
        last_p = None
        
        for i in range(n):
            dt = df['date'].iloc[i]
            p_i = p.iloc[i]
            reg_i = regime_panic_raw.iloc[i]
            gate_i = gate_panic.iloc[i]
            q_dot_i = df['q1_dot'].iloc[i]
            ma10_i = ma10.iloc[i]
            
            if reg_i and gate_i and not latch:
                latch = True
                timer = K_window
                p_anchor = p_i
            elif latch:
                if pd.notna(p_i) and pd.notna(p_anchor) and p_i < p_anchor * 0.98:
                    p_anchor = p_i
                    timer = K_window
                else:
                    timer -= 1
                    if timer <= 0:
                        latch = False
                        
            # Rigid Signal Gate: latch active, momentum strictly positive, price above MA10
            if latch and (q_dot_i > 0) and (p_i > ma10_i):
                cal_days = (dt - last_dt).days if last_dt is not None else 999
                price_drop_ok = (p_i < last_p * 0.93) if (last_p is not None and pd.notna(p_i)) else True
                if cal_days > 15 or price_drop_ok:
                    raw_panic_arr[i] = True
                    last_dt = dt
                    last_p = p_i
                    # Latch is consumed ONLY upon successfully emitting an active signal!
                    latch = False
                # If suppressed by hysteresis, latch is NOT consumed and continues countdown.
                
        df['Trigger_Panic'] = pd.Series(raw_panic_arr, index=df.index)

    # -------------------------------------------------------------
    # 2. Bubble Top & Bear Top Triggers
    # -------------------------------------------------------------
    not_rebounding_from_crash = df['Dist_200MA'].rolling(90).min() >= -12.0
    
    if not use_factor_a:
        regime_bubble_top = (df['Composite_Score_M0'] >= 70.0) | (df['Dist_200MA'] > 22.0)
    else:
        regime_bubble_top = (df['Score_Overheat_A'] >= 75.0) | (df['Dist_200MA'] > 22.0)
        
    q1_series = df['q1'] if 'q1' in df.columns else df['Dist_200MA']
    gate_bubble_top = (df['Dist_200MA'] >= 10.0) & (q1_series >= 0) & not_rebounding_from_crash
    inflection_bubble_top = (df['Quadrant'] == 4) & (df['Quadrant'].shift(1) == 1)
    acceleration_bubble_top = (p < df['MA20']) & (df['q1_dot'] < 0) & (df['q1_dot'].shift(1) >= 0)
    raw_bubble_top = regime_bubble_top & gate_bubble_top & (inflection_bubble_top | acceleration_bubble_top)
    
    bear_regime = (df['MA200_Slope'] < -0.05) | (df['MA50'] < df['MA200'] * 0.98) | df['macro_crisis_regime']
    exhaustion_gate = (df['Dist_200MA'] < 5.0)
    inflection_bear_top = (p < df['MA20']) & (df['q1_dot'] < 0) & (df['q1_dot'].shift(1) >= 0)
    raw_bear_top = bear_regime & exhaustion_gate & inflection_bear_top & (~raw_bubble_top)
    
    def apply_hys_top(raw_flags: pd.Series, min_days: int = 15, price_step: float = 0.07) -> pd.Series:
        flags = np.zeros(n, dtype=bool)
        last_dt = None
        last_p = None
        for idx in range(n):
            if raw_flags.iloc[idx]:
                dt = df['date'].iloc[idx]
                p_val = p.iloc[idx]
                cal_days = (dt - last_dt).days if last_dt is not None else 999
                price_up_ok = (p_val > last_p * (1.0 + price_step)) if (last_p is not None and pd.notna(p_val)) else True
                if cal_days > min_days or price_up_ok:
                    flags[idx] = True
                    last_dt = dt
                    last_p = p_val
        return pd.Series(flags, index=df.index)

    df['Trigger_Bubble_Top'] = apply_hys_top(raw_bubble_top, min_days=25, price_step=0.08)
    df['Trigger_Bear_Top'] = apply_hys_top(raw_bear_top, min_days=20, price_step=0.06)
    
    df['raw_sell'] = df['Trigger_Bubble_Top'] | df['Trigger_Bear_Top']
    df['sell_reason'] = np.where(df['Trigger_Bubble_Top'], 'BUBBLE', np.where(df['Trigger_Bear_Top'], 'BEAR', 'NONE'))
    
    # Baseline Trend Buy Condition
    df['cond_trend'] = (p > df['MA50']).rolling(3).sum() == 3
    df['raw_buy'] = df['Trigger_Panic'] | df['cond_trend']
    
    return df


def evaluate_signals(df: pd.DataFrame, price_col: str = 'close', window: int = 20) -> Dict[str, Any]:
    """
    Signal layer objective classification evaluation strictly per Spec v2.0:
    - Search window for BOTH buy and sell extrema is [S - 15, S + 5];
    - Truncation mask [window : n - 60] applies to both extrema and signals.
      Signals or extrema outside this evaluation window are excluded from denominators.
    """
    p = df[price_col].values
    n = len(p)
    
    is_local_min = np.zeros(n, dtype=bool)
    is_local_max = np.zeros(n, dtype=bool)
    for i in range(window, n - window):
        chunk = p[i - window : i + window + 1]
        if pd.notna(p[i]) and np.all(pd.notna(chunk)):
            if p[i] == np.min(chunk):
                is_local_min[i] = True
            if p[i] == np.max(chunk):
                is_local_max[i] = True
                
    eval_mask = np.zeros(n, dtype=bool)
    if n > window + 60:
        eval_mask[window : n - 60] = True
    else:
        eval_mask[:] = False
        
    # Context extrema for matching signals across evaluation boundaries
    context_mins = np.where(is_local_min)[0]
    context_maxs = np.where(is_local_max)[0]
    
    # Evaluated extrema for miss rate calculations within evaluation window
    eval_mins = np.where(is_local_min & eval_mask)[0]
    eval_maxs = np.where(is_local_max & eval_mask)[0]
    total_mins = len(eval_mins)
    total_maxs = len(eval_maxs)
    
    # 1. Panic Bottom Signal Evaluation (Window [S - 15, S + 5])
    panic_signals = np.where(df['Trigger_Panic'] & eval_mask)[0]
    context_panics = np.where(df['Trigger_Panic'])[0]
    matched_panics = 0
    for s in panic_signals:
        if any(s - 15 <= t <= s + 5 for t in context_mins):
            matched_panics += 1
            
    covered_troughs = 0
    for t in eval_mins:
        if any(s - 15 <= t <= s + 5 for s in context_panics):
            covered_troughs += 1
            
    panic_buy_fdr = ((len(panic_signals) - matched_panics) / len(panic_signals) * 100.0) if len(panic_signals) > 0 else 0.0
    bottom_miss_rate = ((total_mins - covered_troughs) / total_mins * 100.0) if total_mins > 0 else 0.0
    
    # 2. Sell Signals Evaluation (Window [S - 15, S + 5])
    sell_signals = np.where(df['raw_sell'] & eval_mask)[0]
    context_sells = np.where(df['raw_sell'])[0]
    matched_sells = 0
    for s in sell_signals:
        if any(s - 15 <= pk <= s + 5 for pk in context_maxs):
            matched_sells += 1
            
    covered_peaks = 0
    for pk in eval_maxs:
        if any(s - 15 <= pk <= s + 5 for s in context_sells):
            covered_peaks += 1
            
    sell_fdr = ((len(sell_signals) - matched_sells) / len(sell_signals) * 100.0) if len(sell_signals) > 0 else 0.0
    top_miss_rate = ((total_maxs - covered_peaks) / total_maxs * 100.0) if total_maxs > 0 else 0.0
    
    return {
        'panic_signals_count': int(len(panic_signals)),
        'panic_buy_fdr': round(panic_buy_fdr, 2),
        'bottom_miss_rate': round(bottom_miss_rate, 2),
        'sell_signals_count': int(len(sell_signals)),
        'sell_fdr': round(sell_fdr, 2),
        'top_miss_rate': round(top_miss_rate, 2),
        'total_eval_days': int(np.sum(eval_mask)),
        'true_minima': total_mins,
        'true_maxima': total_maxs
    }


def evaluate_event_forward_returns(
    df: pd.DataFrame,
    executor: SharedExecutor,
    price_col: str = 'close',
    asset: str = 'NOW',
    config: str = 'C0'
) -> List[Dict[str, Any]]:
    """
    Evaluate discrete forward returns across 4 distinct paths:
    (signal vs fill) x (20d vs 60d).
    Strict requirement: start quote AND target quote must both be valid (pd.notna).
    """
    event_records = []
    n = len(df)
    date_to_idx = {df['date'].iloc[i].strftime('%Y-%m-%d'): i for i in range(n)}
    
    order_map = {o['order_id']: o for o in executor.orders_history}
    
    for fill in executor.fills:
        order = order_map.get(fill['order_id'], {})
        reason = str(order.get('reason', 'UNKNOWN') or '')
        
        if 'PANIC' in reason:
            cat = 'PANIC_BUY'
        elif 'REENTRY' in reason:
            cat = 'REENTRY_BUY'
        elif 'DCA' in reason:
            cat = 'DCA_ADDITION'
        elif 'TREND' in reason:
            cat = 'TREND_BUY'
        elif fill['direction'] == 'SELL':
            cat = 'EXIT_SELL'
        else:
            cat = 'OTHER'
            
        dt_fill = fill['dt']
        dt_sig = order.get('submit_dt', dt_fill)
        idx_fill = date_to_idx.get(dt_fill, -1)
        idx_sig = date_to_idx.get(dt_sig, -1)
        
        p_fill = fill['price']
        p_sig = df[price_col].iloc[idx_sig] if (0 <= idx_sig < n) else p_fill
        
        # 1. Fill Date Forward Returns (20d & 60d)
        p_target_fill_20 = df[price_col].iloc[idx_fill + 20] if (0 <= idx_fill and idx_fill + 20 < n) else np.nan
        p_target_fill_60 = df[price_col].iloc[idx_fill + 60] if (0 <= idx_fill and idx_fill + 60 < n) else np.nan
        
        valid_fill_20 = bool(0 <= idx_fill and idx_fill + 20 < n and pd.notna(p_fill) and pd.notna(p_target_fill_20))
        valid_fill_60 = bool(0 <= idx_fill and idx_fill + 60 < n and pd.notna(p_fill) and pd.notna(p_target_fill_60))
        ret_fill_20 = round(float((p_target_fill_20 - p_fill) / p_fill * 100.0), 4) if valid_fill_20 else np.nan
        ret_fill_60 = round(float((p_target_fill_60 - p_fill) / p_fill * 100.0), 4) if valid_fill_60 else np.nan
        
        # 2. Signal Date Forward Returns (20d & 60d)
        p_target_sig_20 = df[price_col].iloc[idx_sig + 20] if (0 <= idx_sig and idx_sig + 20 < n) else np.nan
        p_target_sig_60 = df[price_col].iloc[idx_sig + 60] if (0 <= idx_sig and idx_sig + 60 < n) else np.nan
        
        valid_sig_20 = bool(0 <= idx_sig and idx_sig + 20 < n and pd.notna(p_sig) and pd.notna(p_target_sig_20))
        valid_sig_60 = bool(0 <= idx_sig and idx_sig + 60 < n and pd.notna(p_sig) and pd.notna(p_target_sig_60))
        ret_sig_20 = round(float((p_target_sig_20 - p_sig) / p_sig * 100.0), 4) if valid_sig_20 else np.nan
        ret_sig_60 = round(float((p_target_sig_60 - p_sig) / p_sig * 100.0), 4) if valid_sig_60 else np.nan
        
        event_records.append({
            'Asset': asset,
            'Config': config,
            'event_type': cat,
            'signal_dt': dt_sig,
            'fill_dt': dt_fill,
            'signal_price': round(float(p_sig), 4) if pd.notna(p_sig) else np.nan,
            'fill_price': round(float(p_fill), 4) if pd.notna(p_fill) else np.nan,
            'valid_fill_20': valid_fill_20,
            'fwd_ret_fill_20d': ret_fill_20,
            'valid_fill_60': valid_fill_60,
            'fwd_ret_fill_60d': ret_fill_60,
            'valid_sig_20': valid_sig_20,
            'fwd_ret_sig_20d': ret_sig_20,
            'valid_sig_60': valid_sig_60,
            'fwd_ret_sig_60d': ret_sig_60,
        })
    return event_records


def run_execution_simulation(
    df: pd.DataFrame,
    initial_cash: float = 100000.0,
    dca_monthly: float = 1000.0,
    fee_rate: float = 0.0005,
    price_col: str = 'close',
    use_factor_c: bool = False,
    use_factor_a: bool = False,
    asset: str = 'NOW',
    config: str = 'C0'
) -> Dict[str, Any]:
    """
    Unified Execution Engine v2.3 strictly implementing:
    - Universal base accounting with signed_shares conversion;
    - Wave tracking preserving initial_entry_fill across DCA additions;
    - Complete removal of post-stop cooldown state (Factor C resets directly to NONE);
    - Trade clock progression for stop loss independently of signal_ready;
    - Stop loss countdown only exempts re-entry fill day; subsequent days check stop loss then decrement;
    - Protected DCA follow-up (never cancels pending risk sell orders);
    - Zero cost fallback in open positions valuation: itemized reconciliation with executor state.
    """
    df = df.copy()
    p = df[price_col]
    n = len(df)
    
    strat_acc = UnitizedAccount(initial_cash=initial_cash, initial_date=df['date'].iloc[0])
    bench_acc = UnitizedAccount(initial_cash=initial_cash, initial_date=df['date'].iloc[0])
    
    executor = SharedExecutor(strat_acc, fee_rate=fee_rate, execution_mode='NEXT_CLOSE', account_type='strat')
    bench_executor = SharedExecutor(bench_acc, fee_rate=fee_rate, execution_mode='NEXT_CLOSE', account_type='bench')
    
    pos = 0.0
    curr_m = -1
    last_fill_count = 0
    stop_loss_order_count = 0
    
    # Wave position tracking
    initial_entry_fill = None
    current_entry_fill = None
    wave_buys: List[Dict[str, Any]] = []
    round_trips: List[Dict[str, Any]] = []
    open_positions: List[Dict[str, Any]] = []
    
    # Cash interval tracking
    cash_intervals: List[Dict[str, Any]] = []
    open_cash_intervals: List[Dict[str, Any]] = []
    cash_start_dt = df['date'].iloc[0].strftime('%Y-%m-%d')
    cash_start_idx = 0
    cash_start_p = p.iloc[0]
    cash_days_count = 0
    
    # Factor C variables
    exit_mode = 'NONE'  # Allowed states: 'NONE', 'AFTER_BUBBLE', 'AFTER_BEAR'
    reentry_fill_price = None
    stop_timer = 0
    
    # Factor C indicators
    ma20 = df['MA20'] if 'MA20' in df.columns else p.rolling(20).mean()
    ma50 = df['MA50'] if 'MA50' in df.columns else p.rolling(50).mean()
    ma50_band = df['ma50_band'] if 'ma50_band' in df.columns else ((abs(p - ma50) / (ma50 + 1e-8) <= 0.025).rolling(2).sum() == 2)
    q1_dot = df['q1_dot'] if 'q1_dot' in df.columns else pd.Series(0.0, index=df.index)
    macro_stress = df['Score_MacroStress_A'] if (use_factor_a and 'Score_MacroStress_A' in df.columns) else (df['Score_Dim6_Macro'] if 'Score_Dim6_Macro' in df.columns else pd.Series(50.0, index=df.index))
    hyg_rebound = (df['HYG'] > df['Macro_MA200']) if ('HYG' in df.columns and 'Macro_MA200' in df.columns) else pd.Series(False, index=df.index)
    ma50_reclaim_3d = df['ma50_reclaim_3d'] if 'ma50_reclaim_3d' in df.columns else ((p > ma50).rolling(3).sum() == 3)
    
    for i in range(n):
        dt = df['date'].iloc[i]
        p_i = p.iloc[i]
        p_open_val = df['open'].iloc[i] if ('open' in df.columns and pd.notna(df['open'].iloc[i])) else p_i
        
        m = dt.month
        deposit = dca_monthly if m != curr_m else 0.0
        curr_m = m
        
        # Step 1: Step executors (executes prior pending orders, processes deposit, updates close valuation)
        executor.step(dt, p_open_val, p_i, dca_amount=deposit)
        bench_executor.step(dt, p_open_val, p_i, dca_amount=deposit)
        
        # Benchmark Order Submission: Day 0 initial buy, subsequent monthly DCA buys
        if i == 0:
            bench_executor.submit_order(1.0, "Benchmark Initial Buy", dt)
        elif deposit > 0 or bench_executor.acc.cash > 1e-4:
            has_pending_bench_buy = any(o['target'] == 1.0 for o in bench_executor.pending_orders)
            if not has_pending_bench_buy:
                bench_executor.submit_order(1.0, "Monthly benchmark investment", dt)
                
        # Step 2: Process Fills & Position Wave Accounting
        reentry_just_filled_today = False
        if len(executor.fills) > last_fill_count:
            new_fills = executor.fills[last_fill_count:]
            last_fill_count = len(executor.fills)
            for latest_fill in new_fills:
                dt_fill = latest_fill['dt']
                p_fill = latest_fill['price']
                signed_s = latest_fill['signed_shares']
                fee = latest_fill['fee']
                direction = latest_fill['direction']
                
                # Fetch order reason for this fill
                order_id = latest_fill['order_id']
                last_order = next((o for o in executor.orders_history if o['order_id'] == order_id), {})
                reason_str = str(last_order.get('reason', '') or '')
                
                if direction == 'BUY':
                    shares = abs(signed_s)
                    cost = shares * p_fill + fee
                    pos = 1.0
                    cash_days_count = 0
                    
                    if current_entry_fill is None:
                        # Initial entry of a new holding wave
                        initial_entry_fill = latest_fill
                        current_entry_fill = latest_fill
                        wave_buys = [{
                            'dt': dt_fill,
                            'shares': shares,
                            'price': p_fill,
                            'cost': cost,
                            'fee': fee
                        }]
                        # Close out cash interval ledger
                        if cash_start_dt is not None:
                            cash_end_p = p_fill
                            dur_days = max(1, i - cash_start_idx)
                            cash_intervals.append({
                                'Asset': asset,
                                'Config': config,
                                'cash_start_dt': cash_start_dt,
                                'cash_end_dt': dt_fill,
                                'duration_trading_days': dur_days,
                                'underlying_start_p': cash_start_p,
                                'underlying_end_p': cash_end_p,
                                'underlying_return_pct': (cash_end_p - cash_start_p) / cash_start_p * 100.0,
                            })
                            cash_start_dt = None
                    else:
                        # DCA addition while holding: append to wave, DO NOT overwrite initial_entry_fill!
                        wave_buys.append({
                            'dt': dt_fill,
                            'shares': shares,
                            'price': p_fill,
                            'cost': cost,
                            'fee': fee
                        })
                        
                    # Re-entry fill detection: ONLY when fill was a re-entry order
                    if 'REENTRY' in reason_str or (use_factor_c and exit_mode in ['AFTER_BUBBLE', 'AFTER_BEAR']):
                        reentry_just_filled_today = True
                        reentry_fill_price = p_fill
                        stop_timer = 10
                    exit_mode = 'NONE'
                    
                elif direction == 'SELL':
                    shares = abs(signed_s)
                    net_proceeds = shares * p_fill - fee
                    pos = 0.0
                    cash_start_dt = dt_fill
                    cash_start_idx = i
                    cash_start_p = p_fill
                    
                    if current_entry_fill is not None:
                        # True wave duration from initial entry date to exit date
                        idx_in_matches = df.index[df['date'] == pd.Timestamp(current_entry_fill['dt'])]
                        idx_in = idx_in_matches[0] if len(idx_in_matches) > 0 else 0
                        dur = max(1, i - idx_in)
                        
                        total_buy_cost = sum(b['cost'] for b in wave_buys)
                        total_buy_shares = sum(b['shares'] for b in wave_buys)
                        realized_pnl = net_proceeds - total_buy_cost
                        wave_return_pct = (realized_pnl / total_buy_cost * 100.0) if total_buy_cost > 0 else 0.0
                        vwap = (sum(b['shares'] * b['price'] for b in wave_buys) / total_buy_shares) if total_buy_shares > 0 else current_entry_fill['price']
                        
                        round_trips.append({
                            'Asset': asset,
                            'Config': config,
                            'entry_dt': current_entry_fill['dt'],
                            'entry_price': current_entry_fill['price'],
                            'entry_vwap': round(vwap, 4),
                            'exit_dt': dt_fill,
                            'exit_price': p_fill,
                            'exit_reason': reason_str,
                            'duration_trading_days': dur,
                            'total_buy_cost': round(total_buy_cost, 2),
                            'net_sell_proceeds': round(net_proceeds, 2),
                            'realized_pnl': round(realized_pnl, 2),
                            'wave_return_pct': round(wave_return_pct, 4),
                            'is_short_term': dur <= 5,
                            'num_dca_additions': len(wave_buys) - 1
                        })
                        current_entry_fill = None
                        initial_entry_fill = None
                        wave_buys = []
                        
                    reentry_fill_price = None
                    stop_timer = 0
                    # Factor C exit mode classification: strictly 'AFTER_BUBBLE', 'AFTER_BEAR', or 'NONE'
                    if use_factor_c:
                        if 'BUBBLE' in reason_str:
                            exit_mode = 'AFTER_BUBBLE'
                        elif 'BEAR' in reason_str:
                            exit_mode = 'AFTER_BEAR'
                        else:
                            exit_mode = 'NONE'
                    cash_days_count = 0

        if pos == 0.0:
            cash_days_count += 1
            
        submitted_sell_today = False
        
        # -------------------------------------------------------------
        # Step 3: Trade Clock & Re-entry Stop Loss Countdown (Requirement 3)
        # -------------------------------------------------------------
        # "止损时钟只豁免首次再入场成交日。not filled today 应明确为
        # '不是再入场首次成交当天'，不能因为当天发生定投加仓就暂停倒计时。
        # 后续每天先检查仍有效的止损，再递减，确保第十日有效、第十一日失效；
        # 缺价日也推进时钟。"
        if use_factor_c and pos == 1.0 and stop_timer > 0 and reentry_fill_price is not None and not reentry_just_filled_today:
            # 1. First check if stop loss condition is triggered on valid price quote
            if pd.notna(p_i) and p_i < reentry_fill_price * 0.95:
                executor.submit_order(0.0, "STOP_LOSS_5PCT", dt)
                stop_loss_order_count += 1
                submitted_sell_today = True
                stop_timer = 0
                reentry_fill_price = None
            else:
                # 2. Then decrement timer by 1 trading day (advances even on missing price days)
                stop_timer -= 1
                if stop_timer <= 0:
                    reentry_fill_price = None

        # -------------------------------------------------------------
        # Step 4: Macro Strategy Exit Orders (Bubble / Bear Top)
        # -------------------------------------------------------------
        is_ready = df['signal_ready'].iloc[i] if 'signal_ready' in df.columns else True
        has_raw_sell = df['raw_sell'].iloc[i] if 'raw_sell' in df.columns else False
        sell_reason_str = str(df['sell_reason'].iloc[i]) if 'sell_reason' in df.columns else 'NONE'
        if not submitted_sell_today and pos == 1.0 and is_ready and has_raw_sell:
            executor.submit_order(0.0, sell_reason_str, dt)
            submitted_sell_today = True
            
        # -------------------------------------------------------------
        # Step 5: Strategy New Entry Orders (Requires is_ready == True and pos == 0.0)
        # -------------------------------------------------------------
        if not submitted_sell_today and pos == 0.0 and is_ready:
            if not use_factor_c:
                can_buy = df['Trigger_Panic'].iloc[i] or df['cond_trend'].iloc[i]
                if can_buy:
                    reason = "PANIC_BUY" if df['Trigger_Panic'].iloc[i] else "TREND_BUY"
                    executor.submit_order(1.0, reason, dt)
            else:
                can_buy = False
                buy_reason = 'NONE'
                if df['Trigger_Panic'].iloc[i]:
                    can_buy = True
                    buy_reason = 'PANIC_BUY'
                elif exit_mode == 'AFTER_BUBBLE':
                    path_a = bool(ma50_band.iloc[i]) and (p_i > ma20.iloc[i]) and (q1_dot.iloc[i] > 0)
                    if i >= 20:
                        path_b = (cash_days_count >= 10) and (p_i > p.iloc[i-20:i].max()) and (q1_dot.iloc[i] > 0)
                    else:
                        path_b = False
                    if path_a or path_b:
                        can_buy = True
                        buy_reason = 'REENTRY_AFTER_BUBBLE'
                elif exit_mode == 'AFTER_BEAR':
                    macro_ok = (macro_stress.iloc[i] < 60.0) or hyg_rebound.iloc[i]
                    if macro_ok and ma50_reclaim_3d.iloc[i] and (q1_dot.iloc[i] > 0):
                        can_buy = True
                        buy_reason = 'REENTRY_AFTER_BEAR'
                else:  # exit_mode == 'NONE'
                    if df['cond_trend'].iloc[i]:
                        can_buy = True
                        buy_reason = 'TREND_BUY'
                if can_buy:
                    executor.submit_order(1.0, buy_reason, dt)
                    
        # -------------------------------------------------------------
        # Step 6: Protected Holding DCA Cash Follow-up (Requirement 2)
        # -------------------------------------------------------------
        # "定投追投必须保护已有待成交卖单。若存在前日挂起的风险卖单，禁止提交定投买单将其取消。"
        has_pending_sell = any(o['target'] == 0.0 for o in executor.pending_orders)
        has_pending_buy = any(o['target'] == 1.0 for o in executor.pending_orders)
        
        if pos == 1.0 and not submitted_sell_today and not has_pending_sell:
            has_idle_cash = (deposit > 0) or (executor.acc.cash > 1e-4) or (executor.pending_cash > 0)
            if has_idle_cash and not has_pending_buy:
                executor.submit_order(1.0, "DCA_HOLDING_REINVEST", dt)
                
    # -------------------------------------------------------------
    # Step 7: Record Open Position at End of Simulation (Requirement 4)
    # -------------------------------------------------------------
    if current_entry_fill is not None and len(wave_buys) > 0:
        idx_in_matches = df.index[df['date'] == pd.Timestamp(current_entry_fill['dt'])]
        idx_in = idx_in_matches[0] if len(idx_in_matches) > 0 else 0
        dur = max(1, n - 1 - idx_in)
        total_buy_cost = sum(b['cost'] for b in wave_buys)
        total_buy_shares = sum(b['shares'] for b in wave_buys)
        
        latest_price = p.iloc[-1]
        eval_price = latest_price if pd.notna(latest_price) else executor.last_valid_price
        
        # Requirement 4: "彻底删除成本估值兜底。无可用估值价格时，应标记无法估值并暴露异常，不能把成本当市值。
        # 正常陈旧估值应与执行器的持仓市值、现金及估值质量逐项对账。"
        if eval_price is None or pd.isna(eval_price):
            raise ValueError(f"Unable to value open position for {asset} {config}: no valid price available in history!")
            
        latest_market_val = total_buy_shares * eval_price
        unrealized_pnl = latest_market_val - total_buy_cost
        unrealized_pnl_pct = (unrealized_pnl / total_buy_cost * 100.0) if total_buy_cost > 0 else 0.0
        vwap = (sum(b['shares'] * b['price'] for b in wave_buys) / total_buy_shares) if total_buy_shares > 0 else current_entry_fill['price']
        
        # Itemized reconciliation with executor account state
        last_state = executor.daily_states[-1]
        val_quality = last_state['valuation_quality']
        acc_equity = last_state['equity']
        acc_cash = last_state['cash']
        assert abs((latest_market_val + acc_cash) - acc_equity) < 1e-2, (
            f"Open position market value {latest_market_val} + cash {acc_cash} does not reconcile with executor equity {acc_equity}!"
        )
        
        open_positions.append({
            'Asset': asset,
            'Config': config,
            'entry_dt': current_entry_fill['dt'],
            'entry_vwap': round(vwap, 4),
            'holding_trading_days_to_end': dur,
            'total_buy_shares': round(total_buy_shares, 4),
            'total_buy_cost': round(total_buy_cost, 2),
            'latest_market_val': round(latest_market_val, 2),
            'unrealized_pnl': round(unrealized_pnl, 2),
            'unrealized_pnl_pct': round(unrealized_pnl_pct, 4),
            'num_dca_additions': len(wave_buys) - 1,
            'eval_price': round(eval_price, 4),
            'valuation_quality': val_quality,
            'executor_cash': round(acc_cash, 2),
            'executor_equity': round(acc_equity, 2)
        })
        
    if cash_start_dt is not None:
        dur_days = max(1, n - 1 - cash_start_idx)
        latest_price = p.iloc[-1]
        open_cash_intervals.append({
            'Asset': asset,
            'Config': config,
            'cash_start_dt': cash_start_dt,
            'duration_trading_days_to_end': dur_days,
            'underlying_start_p': cash_start_p,
            'underlying_end_p': latest_price,
            'underlying_return_pct': round((latest_price - cash_start_p) / cash_start_p * 100.0, 4) if (cash_start_p and pd.notna(latest_price)) else 0.0
        })

    # -------------------------------------------------------------
    # Step 8: Summary Metrics Computation
    # -------------------------------------------------------------
    strat_final = executor.daily_states[-1]['equity'] if executor.daily_states else initial_cash
    bench_final = bench_executor.daily_states[-1]['equity'] if bench_executor.daily_states else initial_cash
    s_xirr = calculate_xirr(executor.acc.cash_flows, strat_final, df['date'].iloc[-1])
    strat_xirr = (s_xirr * 100.0) if pd.notna(s_xirr) else 0.0
    b_xirr = calculate_xirr(bench_executor.acc.cash_flows, bench_final, df['date'].iloc[-1])
    bench_xirr = (b_xirr * 100.0) if pd.notna(b_xirr) else 0.0
    
    strat_navs = [s['unit_nav'] for s in executor.daily_states]
    bench_navs = [s['unit_nav'] for s in bench_executor.daily_states]
    strat_mdd = ((pd.Series(strat_navs) - pd.Series(strat_navs).cummax()) / pd.Series(strat_navs).cummax()).min() * 100.0
    bench_mdd = ((pd.Series(bench_navs) - pd.Series(bench_navs).cummax()) / pd.Series(bench_navs).cummax()).min() * 100.0
    
    num_rt = len(round_trips)
    short_rt = sum(1 for r in round_trips if r['is_short_term'])
    short_rate = (short_rt / num_rt * 100.0) if num_rt > 0 else 0.0
    
    bench_first_fill = bench_executor.fills[0]['dt'] if bench_executor.fills else 'NONE'
    strat_first_fill = executor.fills[0]['dt'] if executor.fills else 'NONE'
    
    event_evals = evaluate_event_forward_returns(df, executor, price_col=price_col, asset=asset, config=config)
    
    return {
        'strat_final': round(strat_final, 2),
        'bench_final': round(bench_final, 2),
        'strat_xirr': round(strat_xirr, 2),
        'bench_xirr': round(bench_xirr, 2),
        'alpha_xirr_diff': round(strat_xirr - bench_xirr, 2),
        'strat_mdd': round(strat_mdd, 2),
        'bench_mdd': round(bench_mdd, 2),
        'round_trips': num_rt,
        'short_term_rate': round(short_rate, 2),
        'stop_loss_order_count': stop_loss_order_count,
        'benchmark_first_fill_dt': bench_first_fill,
        'strategy_first_fill_dt': strat_first_fill,
        'round_trips_ledger': round_trips,
        'cash_intervals': cash_intervals,
        'open_positions': open_positions,
        'open_cash_intervals': open_cash_intervals,
        'event_forward_evaluations': event_evals,
        'executor_instance': executor,
        'bench_executor_instance': bench_executor
    }


def run_subperiod_evaluations(
    asset: str,
    config: str,
    df_sig_full: pd.DataFrame,
    start_dt_str: str,
    use_factor_a: bool,
    use_factor_c: bool,
    full_exec_res: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Evaluate sub-periods under both Mode A and Mode B (Requirement 5):
    - Sub-period 1: Early Dev / Calibration Segment (start_dt to 2019-12-31)
    - Sub-period 2: Historical Sub-period Verification Segment (2020-01-01 to 2026-09-14)
    - Mode A: Continuous Inherited Attribution (starting equity, cash flows, terminal equity, XIRR, anchored MDD)
    - Mode B: Fresh Reset Backtest ($100k reset, independent account & orders, continuous technical history)
    """
    sub_records = []
    segments = [
        ('Calibration_Segment_2014_2019', start_dt_str, '2019-12-31'),
        ('Historical_Verification_2020_2026', '2020-01-01', '2026-09-14')
    ]
    
    strat_ex = full_exec_res['executor_instance']
    bench_ex = full_exec_res['bench_executor_instance']
    
    for seg_name, t0_str, t1_str in segments:
        t0 = pd.Timestamp(t0_str)
        t1 = pd.Timestamp(t1_str)
        
        # -------------------------------------------------------------
        # Mode A: Continuous Inherited Attribution
        # -------------------------------------------------------------
        opening_strat = [s for s in strat_ex.daily_states if s['date'] < t0_str]
        opening_bench = [s for s in bench_ex.daily_states if s['date'] < t0_str]
        
        strat_states = [s for s in strat_ex.daily_states if t0 <= pd.Timestamp(s['date']) <= t1]
        bench_states = [s for s in bench_ex.daily_states if t0 <= pd.Timestamp(s['date']) <= t1]
        
        if strat_states and bench_states:
            if opening_strat and opening_bench:
                # Inherited segment: anchored at prior period closing state
                s_start_eq = opening_strat[-1]['equity']
                b_start_eq = opening_bench[-1]['equity']
                s_nav_anchor = opening_strat[-1]['unit_nav']
                b_nav_anchor = opening_bench[-1]['unit_nav']
                
                # Cash flows strictly within the segment [t0, t1]
                s_cf_during = [cf for cf in strat_ex.acc.cash_flows if t0 <= cf[0] <= t1]
                b_cf_during = [cf for cf in bench_ex.acc.cash_flows if t0 <= cf[0] <= t1]
                
                s_sub_cf = [(t0, s_start_eq)] + s_cf_during
                b_sub_cf = [(t0, b_start_eq)] + b_cf_during
                
                s_navs = pd.Series([s_nav_anchor] + [s['unit_nav'] for s in strat_states])
                b_navs = pd.Series([b_nav_anchor] + [s['unit_nav'] for s in bench_states])
            else:
                # Inception segment: starting from initial cash injection at start
                s_start_eq = 100000.0
                b_start_eq = 100000.0
                first_dt = pd.Timestamp(strat_states[0]['date'])
                
                # All DCA cash flows in this segment (excluding initial 100k capital)
                s_cf_during = [cf for cf in strat_ex.acc.cash_flows[1:] if cf[0] <= t1]
                b_cf_during = [cf for cf in bench_ex.acc.cash_flows[1:] if cf[0] <= t1]
                
                s_sub_cf = [(first_dt, s_start_eq)] + s_cf_during
                b_sub_cf = [(first_dt, b_start_eq)] + b_cf_during
                
                s_navs = pd.Series([s['unit_nav'] for s in strat_states])
                b_navs = pd.Series([s['unit_nav'] for s in bench_states])
                
            s_end_eq = strat_states[-1]['equity']
            b_end_eq = bench_states[-1]['equity']
            s_total_dca = sum(cf[1] for cf in s_cf_during)
            b_total_dca = sum(cf[1] for cf in b_cf_during)
            
            s_xirr_val = calculate_xirr(s_sub_cf, s_end_eq, pd.Timestamp(strat_states[-1]['date']))
            b_xirr_val = calculate_xirr(b_sub_cf, b_end_eq, pd.Timestamp(bench_states[-1]['date']))
            s_xirr = (s_xirr_val * 100.0) if pd.notna(s_xirr_val) else 0.0
            b_xirr = (b_xirr_val * 100.0) if pd.notna(b_xirr_val) else 0.0
            
            s_mdd = ((s_navs - s_navs.cummax()) / s_navs.cummax()).min() * 100.0
            b_mdd = ((b_navs - b_navs.cummax()) / b_navs.cummax()).min() * 100.0
            
            sub_records.append({
                'Asset': asset,
                'Config': config,
                'Segment': seg_name,
                'Mode': 'Mode_A_Continuous_Inherited',
                'Start_Dt': t0_str,
                'End_Dt': t1_str,
                'Strat_Start_Equity': round(s_start_eq, 2),
                'Strat_Total_DCA': round(s_total_dca, 2),
                'Strat_End_Equity': round(s_end_eq, 2),
                'Strat_XIRR%': round(s_xirr, 2),
                'Strat_MDD%': round(s_mdd, 2),
                'Bench_Start_Equity': round(b_start_eq, 2),
                'Bench_Total_DCA': round(b_total_dca, 2),
                'Bench_End_Equity': round(b_end_eq, 2),
                'Bench_XIRR%': round(b_xirr, 2),
                'Bench_MDD%': round(b_mdd, 2),
                'Alpha_XIRR%': round(s_xirr - b_xirr, 2),
                'Actual_Deposit_Dt': "INHERITED" if opening_strat else strat_ex.acc.cash_flows[0][0].strftime('%Y-%m-%d'),
                'First_DCA_Dt': s_cf_during[0][0].strftime('%Y-%m-%d') if s_cf_during else 'NONE',
                'First_Fill_Dt': next((o['dt'] for o in strat_ex.fills if t0 <= pd.Timestamp(o['dt']) <= t1), 'NONE')
            })
            
        # -------------------------------------------------------------
        # Mode B: Fresh Reset Backtest ($100k reset, continuous technical indicators)
        # -------------------------------------------------------------
        df_sub = df_sig_full[(df_sig_full['date'] >= t0) & (df_sig_full['date'] <= t1)].copy().reset_index(drop=True)
        if len(df_sub) > 5:
            res_b = run_execution_simulation(
                df_sub, initial_cash=100000.0, dca_monthly=1000.0, fee_rate=0.0005,
                use_factor_c=use_factor_c, use_factor_a=use_factor_a, asset=asset, config=config
            )
            # Total DCA includes all monthly contributions (cash_flows[0] is initial 100k capital, cash_flows[1:] are DCAs)
            s_dca_b = sum(cf[1] for cf in res_b['executor_instance'].acc.cash_flows[1:])
            b_dca_b = sum(cf[1] for cf in res_b['bench_executor_instance'].acc.cash_flows[1:])
            
            sub_records.append({
                'Asset': asset,
                'Config': config,
                'Segment': seg_name,
                'Mode': 'Mode_B_Fresh_Reset',
                'Start_Dt': df_sub['date'].iloc[0].strftime('%Y-%m-%d'),
                'End_Dt': df_sub['date'].iloc[-1].strftime('%Y-%m-%d'),
                'Strat_Start_Equity': 100000.0,
                'Strat_Total_DCA': round(s_dca_b, 2),
                'Strat_End_Equity': res_b['strat_final'],
                'Strat_XIRR%': res_b['strat_xirr'],
                'Strat_MDD%': res_b['strat_mdd'],
                'Bench_Start_Equity': 100000.0,
                'Bench_Total_DCA': round(b_dca_b, 2),
                'Bench_End_Equity': res_b['bench_final'],
                'Bench_XIRR%': res_b['bench_xirr'],
                'Bench_MDD%': res_b['bench_mdd'],
                'Alpha_XIRR%': res_b['alpha_xirr_diff'],
                'Actual_Deposit_Dt': df_sub['date'].iloc[0].strftime('%Y-%m-%d'),
                'First_DCA_Dt': df_sub['date'].iloc[0].strftime('%Y-%m-%d'),
                'First_Fill_Dt': res_b['strategy_first_fill_dt']
            })
            
    return sub_records


def main():
    print("=" * 80)
    print("UNIVERSAL REFLEXIVITY RADAR FACTORIAL ABLATION EXPERIMENT ENGINE v2.3")
    print("=" * 80)
    
    # 1. Load Local Data (Frozen Input Provenance Support)
    frozen_macro = OUT_DIR.parent / 'v2_3_independent_review' / 'frozen_inputs' / 'market_data_local.csv'
    frozen_prices = OUT_DIR.parent / 'v2_3_independent_review' / 'frozen_inputs' / 'now_ohlcv_local.csv'
    
    prices_path = frozen_prices if frozen_prices.exists() else (ROOT / 'now_ohlcv_local.csv')
    macro_path = frozen_macro if frozen_macro.exists() else (ROOT / 'market_data_local.csv')
    
    print("\n[Step 1] Loading local market data...")
    prices = pd.read_csv(prices_path)
    macro = pd.read_csv(macro_path)
    
    # 2. Production Baseline Reference
    print("\n[Step 2] Establishing Production Baseline...")
    prod_df = run_universal_reflexivity_radar('NOW', prices, macro)
    first_ready_dt = prod_df.loc[prod_df['signal_ready'], 'date'].iloc[0]
    print(f"Production first signal_ready date: {first_ready_dt.strftime('%Y-%m-%d')}")
    
    combos = [
        ("C0_Baseline", False, False, False),
        ("C1_Decoupled_Scores", True, False, False),
        ("C2_Panic_Latch", False, True, False),
        ("C3_Reentry_Stop", False, False, True),
        ("C4_A_plus_B", True, True, False),
        ("C5_A_plus_C", True, False, True),
        ("C6_B_plus_C", False, True, True),
        ("C7_Full_Candidate", True, True, True)
    ]
    
    all_round_trips = []
    all_cash_intervals = []
    all_open_positions = []
    all_open_cash_intervals = []
    all_event_evals = []
    all_subperiod_evals = []
    
    assets_data = {
        'NOW': prices,
        'QQQ': macro[['date', 'QQQ']].dropna().rename(columns={'QQQ': 'close'}),
        'SPY': macro[['date', 'SPY']].dropna().rename(columns={'SPY': 'close'})
    }
    
    results_by_asset = {}
    
    for asset_name, asset_df in assets_data.items():
        print(f"\n[Step 3] Processing Full-History Continuous Signals & Factorial Ablation: {asset_name}...")
        
        # Prepare full-history base features
        df_features = prepare_base_features(asset_df, macro, price_col='close')
        start_date_str = first_ready_dt.strftime('%Y-%m-%d')
        print(f"  -> {asset_name} research period start: {start_date_str}")
        
        asset_summary = []
        
        for name, fa, fb, fc in combos:
            # Requirement 4: Generate signals on FULL continuous history FIRST, then slice
            df_sig_full = generate_signals(df_features, fa, fb, fc, price_col='close')
            
            # Slice to uniform research period from production signal_ready date
            df_sig = df_sig_full[df_sig_full['date'] >= first_ready_dt].copy().reset_index(drop=True)
            
            # Evaluate signals layer
            sig_eval = evaluate_signals(df_sig, price_col='close')
            
            # Run execution simulation
            exec_res = run_execution_simulation(
                df_sig, price_col='close', use_factor_c=fc, use_factor_a=fa, asset=asset_name, config=name
            )
            
            all_round_trips.extend(exec_res['round_trips_ledger'])
            all_cash_intervals.extend(exec_res['cash_intervals'])
            all_open_positions.extend(exec_res['open_positions'])
            all_open_cash_intervals.extend(exec_res['open_cash_intervals'])
            all_event_evals.extend(exec_res['event_forward_evaluations'])
            
            # Sub-period Evaluation (Mode A & Mode B)
            sub_evals = run_subperiod_evaluations(
                asset=asset_name, config=name, df_sig_full=df_sig_full,
                start_dt_str=start_date_str, use_factor_a=fa, use_factor_c=fc,
                full_exec_res=exec_res
            )
            all_subperiod_evals.extend(sub_evals)
            
            asset_summary.append({
                'Ticker': asset_name,
                'Config': name,
                'Factor_A': fa,
                'Factor_B': fb,
                'Factor_C': fc,
                'Strat_Final': exec_res['strat_final'],
                'Bench_Final': exec_res['bench_final'],
                'Strat_XIRR%': exec_res['strat_xirr'],
                'Bench_XIRR%': exec_res['bench_xirr'],
                'Alpha_XIRR%': exec_res['alpha_xirr_diff'],
                'Strat_MDD%': exec_res['strat_mdd'],
                'Bench_MDD%': exec_res['bench_mdd'],
                'Round_Trips': exec_res['round_trips'],
                'Short_Term_Rate%': exec_res['short_term_rate'],
                'Stop_Loss_Orders': exec_res['stop_loss_order_count'],
                'Panic_Signals': sig_eval['panic_signals_count'],
                'Panic_FDR%': sig_eval['panic_buy_fdr'],
                'Bottom_Miss_Rate%': sig_eval['bottom_miss_rate'],
                'Sell_Signals': sig_eval['sell_signals_count'],
                'Sell_FDR%': sig_eval['sell_fdr'],
                'Top_Miss_Rate%': sig_eval['top_miss_rate'],
                'Bench_First_Fill': exec_res['benchmark_first_fill_dt'],
                'Strat_First_Fill': exec_res['strategy_first_fill_dt']
            })
            
        df_summary = pd.DataFrame(asset_summary)
        results_by_asset[asset_name] = df_summary
        csv_path = OUT_DIR / f'factorial_ablation_results_v2_3_{asset_name.lower()}.csv'
        df_summary.to_csv(csv_path, index=False)
        print(f"  -> Exported {csv_path.name}")

    # 4. Export Global Ledgers
    print("\n[Step 4] Exporting Comprehensive Ledgers and Sub-period Reports...")
    pd.DataFrame(all_round_trips).to_csv(OUT_DIR / 'round_trip_ledgers_v2_3.csv', index=False)
    pd.DataFrame(all_cash_intervals).to_csv(OUT_DIR / 'cash_intervals_v2_3.csv', index=False)
    pd.DataFrame(all_open_positions).to_csv(OUT_DIR / 'open_positions_v2_3.csv', index=False)
    pd.DataFrame(all_open_cash_intervals).to_csv(OUT_DIR / 'open_cash_intervals_v2_3.csv', index=False)
    pd.DataFrame(all_event_evals).to_csv(OUT_DIR / 'forward_return_evaluations_v2_3.csv', index=False)
    pd.DataFrame(all_subperiod_evals).to_csv(OUT_DIR / 'subperiod_evaluation_v2_3.csv', index=False)
    
    print("\n[Step 5] Printing Summary Tables across NOW, QQQ, SPY:")
    for asset_name, df_res in results_by_asset.items():
        print(f"\n--- {asset_name} Factorial Ablation Results ---")
        cols_print = ['Config', 'Strat_Final', 'Bench_Final', 'Strat_XIRR%', 'Bench_XIRR%', 'Alpha_XIRR%', 'Strat_MDD%', 'Bench_MDD%', 'Stop_Loss_Orders']
        print(df_res[cols_print].to_string(index=False))
        
    print("\nExecution simulation complete. All files written to v2_3_remediation.")


if __name__ == '__main__':
    main()
