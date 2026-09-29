"""
Universal Reflexivity Radar Factorial Ablation Experiment Framework v2.2
=========================================================================
Strict Remediation & Frozen Model Restoration:
1. 100% restore frozen mathematical model from original baseline (run_factorial_experiment.py):
   - q1 = Dist_200MA (relative to MA200, NOT MA50)
   - q1_dot = 10-day difference / 10
   - q1_ddot = 5-day difference / 5
   - tau = 100.0, v_dot = q1_dot * (q1 + tau * q1_ddot)
   - MA200_Slope = 10-day slope
   - Expanding percentile ranks for all M0 scores and Factor A scores
   - Discrete event forward returns (20d, 60d) for actual discrete entry/reentry events
2. Strict preservation of frozen missing price propagation rules (no ffill on close quotes)
3. Production signal_ready gating dependency (Gap_Max_45, core_cols)
4. Position-wave cost accounting (initial_entry_fill preserved across DCA, correct PnL)
5. Comprehensive ledgers for all 3 assets (NOW, QQQ, SPY) + open positions & open cash intervals
"""

import sys
from pathlib import Path
import bisect
import numpy as np
import pandas as pd
from typing import Dict, List, Any, Tuple

# Workspace paths
ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT))

from true_accounting import UnitizedAccount, calculate_xirr
from shared_executor import SharedExecutor
from reflexivity_engine import run_universal_reflexivity_radar

OUT_DIR = Path(__file__).resolve().parent


def expanding_rank(s: pd.Series, min_periods: int = 100) -> pd.Series:
    """Strict bisect-based expanding percentile rank [0, 100]."""
    vals = s.values
    n = len(vals)
    res = np.full(n, np.nan)
    sorted_arr = []
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
    Compute base coordinates and macro regimes strictly per frozen model v2.0.
    DO NOT ffill() close price series. Raw NaNs are preserved for execution delay.
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
    
    # Lagrange phase space kinematics (Frozen Model v2.0)
    df['q1'] = df['Dist_200MA']
    df['q1_dot'] = (df['q1'] - df['q1'].shift(10)) / 10.0
    df['q1_ddot'] = (df['q1_dot'] - df['q1_dot'].shift(5)) / 5.0
    tau = 100.0
    df['v_dot'] = df['q1_dot'] * (df['q1'] + tau * df['q1_ddot'])
    
    # Phase Space Quadrant
    df['Quadrant'] = 0
    df.loc[(df['q1'] >= 0) & (df['q1_dot'] >= 0), 'Quadrant'] = 1
    df.loc[(df['q1'] < 0) & (df['q1_dot'] >= 0), 'Quadrant'] = 2
    df.loc[(df['q1'] < 0) & (df['q1_dot'] < 0), 'Quadrant'] = 3
    df.loc[(df['q1'] >= 0) & (df['q1_dot'] < 0), 'Quadrant'] = 4
    
    # Micro liquidity
    if 'high' in df.columns and 'low' in df.columns and 'volume' in df.columns:
        hr = (df['high'] - df['low']).replace(0, np.nan)
        clv = ((2 * p - (df['high'] + df['low'])) / hr).fillna(0.0)
        df['CMF20'] = (clv * df['volume']).rolling(20).sum() / (df['volume'].rolling(20).sum() + 1e-8)
        df['Vol_Ratio50'] = df['volume'] / (df['volume'].rolling(50).mean() + 1e-8)
        score_dim5 = (expanding_rank(df['CMF20']) * 0.6 + expanding_rank(df['Vol_Ratio50']) * 0.4)
    else:
        df['CMF20'] = 0.0
        df['Vol_Ratio50'] = 1.0
        score_dim5 = pd.Series(50.0, index=df.index)
        
    df['Score_Dim1_Pos'] = expanding_rank(df['q1'])
    df['Score_Dim2_Vel'] = expanding_rank(df['q1_dot'])
    df['Score_Dim3_Lyapunov'] = expanding_rank(df['v_dot'])
    df['Score_Dim5_Liquidity'] = score_dim5
    df['Score_Dim6_Macro'] = (expanding_rank(df['BAA10Y']) * 0.5 + expanding_rank(df['NFCI']) * 0.5)
    
    # M0 Composite Score (Weights: 0.30, 0.20, 0.20, 0.10, 0.20)
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
    
    # Macro crisis regime
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
    
    # 1. Panic Bottom Regimes & Gates
    if not use_factor_a:
        regime_panic_raw = (df['Dist_200MA'].rolling(20).min() < -15.0) | (df['Dist_200MA'] < -10.0) | (df['Composite_Score_M0'] < 32.0)
    else:
        regime_panic_raw = (df['Dist_200MA'].rolling(20).min() < -15.0) | (df['Dist_200MA'] < -10.0) | (df['Score_PanicDepth_A'] >= 80.0)
        
    gate_panic = (df['Dist_200MA'] <= 0.0) | (p < df['MA50'])
    turned_up = (df['q1_dot'] > 0) & (df['q1_dot'].shift(1) <= 0)
    
    if not use_factor_b:
        inflection_panic = ((p > df['MA10']) & turned_up) | ((df['Dist_200MA'] < -25.0) & turned_up)
        raw_panic = regime_panic_raw & gate_panic & inflection_panic
        
        # Calendar-day Hysteresis
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
            ma10_i = df['MA10'].iloc[i]
            
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

    # 2. Bubble Top & Bear Top Triggers
    not_rebounding_from_crash = df['Dist_200MA'].rolling(90).min() >= -12.0
    
    if not use_factor_a:
        regime_bubble_top = (df['Composite_Score_M0'] >= 70.0) | (df['Dist_200MA'] > 22.0)
    else:
        regime_bubble_top = (df['Score_Overheat_A'] >= 75.0) | (df['Dist_200MA'] > 22.0)
        
    gate_bubble_top = (df['Dist_200MA'] >= 10.0) & (df['q1'] >= 0) & not_rebounding_from_crash
    inflection_bubble_top = (df['Quadrant'] == 4) & (df['Quadrant'].shift(1) == 1)
    acceleration_bubble_top = (p < df['MA20']) & (df['q1_dot'] < 0) & (df['q1_dot'].shift(1) >= 0)
    raw_bubble_top = regime_bubble_top & gate_bubble_top & (inflection_bubble_top | acceleration_bubble_top)
    
    bear_regime = (df['MA200_Slope'] < -0.05) | (df['MA50'] < df['MA200'] * 0.98) | df['macro_crisis_regime']
    exhaustion_gate = (df['Dist_200MA'] < 5.0)
    inflection_bear_top = (p < df['MA20']) & (df['q1_dot'] < 0) & (df['q1_dot'].shift(1) >= 0)
    raw_bear_top = bear_regime & exhaustion_gate & inflection_bear_top & (~raw_bubble_top)
    
    def apply_top_hys(raw_flags: pd.Series, min_days: int, price_step: float) -> pd.Series:
        flags = np.zeros(n, dtype=bool)
        last_dt = None
        last_p = None
        for idx in range(n):
            if raw_flags.iloc[idx]:
                dt = df['date'].iloc[idx]
                p_val = p.iloc[idx]
                cal_days = (dt - last_dt).days if last_dt is not None else 999
                price_rise_ok = (p_val > last_p * (1.0 + price_step)) if (last_p is not None and pd.notna(p_val)) else True
                if cal_days > min_days or price_rise_ok:
                    flags[idx] = True
                    last_dt = dt
                    last_p = p_val
        return pd.Series(flags, index=df.index)

    df['Trigger_Bubble_Top'] = apply_top_hys(raw_bubble_top, min_days=25, price_step=0.08)
    df['Trigger_Bear_Top'] = apply_top_hys(raw_bear_top, min_days=20, price_step=0.06)
    
    df['raw_sell'] = df['Trigger_Bubble_Top'] | df['Trigger_Bear_Top']
    df['sell_reason'] = np.where(df['Trigger_Bubble_Top'], 'BUBBLE', np.where(df['Trigger_Bear_Top'], 'BEAR', 'NONE'))
    
    df['cond_trend'] = (p > df['MA50']).rolling(3).sum() == 3
    
    # Production Readiness Gating: signals only active when signal_ready is True
    ready = df['signal_ready'] if 'signal_ready' in df.columns else pd.Series(True, index=df.index)
    df['strat_buy_signal'] = (df['Trigger_Panic'] | df['cond_trend']) & ready
    df['strat_sell_signal'] = df['raw_sell'] & ready
    
    return df


def evaluate_signals(df: pd.DataFrame, price_col: str = 'close', window: int = 20) -> Dict[str, Any]:
    """Objective classification evaluation against local extrema in [S - 15, S + 5]."""
    p = df[price_col]
    n = len(df)
    
    # Identify local extrema
    is_trough = pd.Series(False, index=df.index)
    is_peak = pd.Series(False, index=df.index)
    for i in range(window, n - window):
        sub = p.iloc[i - window : i + window + 1]
        if pd.notna(p.iloc[i]):
            if p.iloc[i] == sub.min():
                is_trough.iloc[i] = True
            if p.iloc[i] == sub.max():
                is_peak.iloc[i] = True
                
    trough_indices = set(np.where(is_trough)[0])
    peak_indices = set(np.where(is_peak)[0])
    
    # 1. Panic Bottom Signal Evaluation (Window [S - 15, S + 5])
    panic_signals = np.where(df['Trigger_Panic'])[0]
    matched_panics = 0
    covered_troughs = set()
    for s in panic_signals:
        matched = False
        for t in trough_indices:
            if s - 15 <= t <= s + 5:
                matched = True
                covered_troughs.add(t)
        if matched:
            matched_panics += 1
            
    panic_buy_fdr = ((len(panic_signals) - matched_panics) / len(panic_signals) * 100.0) if len(panic_signals) > 0 else 0.0
    bottom_miss_rate = ((len(trough_indices) - len(covered_troughs)) / len(trough_indices) * 100.0) if len(trough_indices) > 0 else 0.0
    
    # 2. Sell Signals Evaluation (Window [S - 5, S + 20])
    sell_signals = np.where(df['raw_sell'])[0]
    matched_sells = 0
    covered_peaks = set()
    for s in sell_signals:
        matched = False
        for pk in peak_indices:
            if s - 5 <= pk <= s + 20:
                matched = True
                covered_peaks.add(pk)
        if matched:
            matched_sells += 1
            
    sell_fdr = ((len(sell_signals) - matched_sells) / len(sell_signals) * 100.0) if len(sell_signals) > 0 else 0.0
    top_miss_rate = ((len(peak_indices) - len(covered_peaks)) / len(peak_indices) * 100.0) if len(peak_indices) > 0 else 0.0
    
    return {
        'panic_signals_count': int(len(panic_signals)),
        'panic_buy_fdr': round(panic_buy_fdr, 2),
        'bottom_miss_rate': round(bottom_miss_rate, 2),
        'sell_signals_count': int(len(sell_signals)),
        'sell_fdr': round(sell_fdr, 2),
        'top_miss_rate': round(top_miss_rate, 2),
    }


def evaluate_event_forward_returns(
    df: pd.DataFrame,
    executor: SharedExecutor,
    price_col: str = 'close',
    asset: str = 'NOW',
    config: str = 'C0'
) -> List[Dict[str, Any]]:
    """
    Evaluates forward 20d and 60d returns specifically for actual discrete trade events:
    - Distinguishes Signal Date (order submit_dt) vs Execution Date (fill dt);
    - Separates DCA Additions from initial Trend Entry and Reentry;
    - Truncated samples (<20d or <60d to end) are marked non-evaluable and effective count disclosed.
    """
    n = len(df)
    date_to_idx = {df['date'].iloc[i].strftime('%Y-%m-%d'): i for i in range(n)}
    
    order_map = {o['order_id']: o for o in executor.orders_history}
    event_records = []
    
    for fill in executor.fills:
        order = order_map.get(fill['order_id'], {})
        reason = order.get('reason', 'UNKNOWN')
        direction = fill['direction']
        
        # Categorize discrete trade event
        if direction == 'BUY':
            if 'DCA' in reason:
                cat = 'DCA_ADDITION'
            elif 'REENTRY' in reason:
                cat = 'REENTRY_BUY'
            elif 'PANIC' in reason or 'Trigger_Panic' in reason:
                cat = 'PANIC_BUY'
            else:
                cat = 'TREND_BUY'
        else:
            cat = 'EXIT_SELL'
            
        dt_fill = fill['dt']
        dt_sig = order.get('submit_dt', dt_fill)
        idx_fill = date_to_idx.get(dt_fill, -1)
        idx_sig = date_to_idx.get(dt_sig, -1)
        
        p_fill = fill['price']
        p_sig = df[price_col].iloc[idx_sig] if (0 <= idx_sig < n) else p_fill
        
        # From Fill Date
        valid_fill_20 = (0 <= idx_fill and idx_fill + 20 < n)
        valid_fill_60 = (0 <= idx_fill and idx_fill + 60 < n)
        ret_fill_20 = round(((df[price_col].iloc[idx_fill + 20] - p_fill) / p_fill * 100.0), 4) if valid_fill_20 else np.nan
        ret_fill_60 = round(((df[price_col].iloc[idx_fill + 60] - p_fill) / p_fill * 100.0), 4) if valid_fill_60 else np.nan
        
        # From Signal Date
        valid_sig_20 = (0 <= idx_sig and idx_sig + 20 < n and pd.notna(p_sig))
        valid_sig_60 = (0 <= idx_sig and idx_sig + 60 < n and pd.notna(p_sig))
        ret_sig_20 = round(((df[price_col].iloc[idx_sig + 20] - p_sig) / p_sig * 100.0), 4) if valid_sig_20 else np.nan
        ret_sig_60 = round(((df[price_col].iloc[idx_sig + 60] - p_sig) / p_sig * 100.0), 4) if valid_sig_60 else np.nan
        
        event_records.append({
            'Asset': asset,
            'Config': config,
            'event_type': cat,
            'signal_dt': dt_sig,
            'fill_dt': dt_fill,
            'signal_price': round(p_sig, 4) if pd.notna(p_sig) else np.nan,
            'fill_price': round(p_fill, 4) if pd.notna(p_fill) else np.nan,
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
    Unified Execution Engine strictly implementing:
    - Universal base accounting with signed_shares conversion;
    - Position-wave tracking preserving initial_entry_fill across DCA additions;
    - Correct wave PnL based on total invested capital and fees;
    - Factor C isolation (0 stops when use_factor_c=False, exact 10-day stop timer when True);
    - Full end-to-end missing price delay and stale valuation support.
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
    exit_mode = 'NONE'
    cooldown_timer = 0
    stop_timer = 0
    reentry_fill_price = None
    
    # Pre-calculate condition series for Factor C re-entry
    ma50 = df['MA50'] if 'MA50' in df.columns else p.rolling(50).mean()
    ma20 = df['MA20'] if 'MA20' in df.columns else p.rolling(20).mean()
    q1_dot = df['q1_dot'] if 'q1_dot' in df.columns else pd.Series(0.0, index=df.index)
    macro_stress = df['Score_MacroStress_A'] if (use_factor_a and 'Score_MacroStress_A' in df.columns) else (df['Score_Dim6_Macro'] if 'Score_Dim6_Macro' in df.columns else pd.Series(50.0, index=df.index))
    hyg_rebound = (df['HYG'] > df['Macro_MA200']) if ('HYG' in df.columns and 'Macro_MA200' in df.columns) else pd.Series(False, index=df.index)
    ma50_band = df['ma50_band'] if 'ma50_band' in df.columns else ((abs(p - ma50) / (ma50 + 1e-8) <= 0.025).rolling(2).sum() == 2)
    ma50_reclaim_3d = df['ma50_reclaim_3d'] if 'ma50_reclaim_3d' in df.columns else ((p > ma50).rolling(3).sum() == 3)
    
    for i in range(n):
        dt = df['date'].iloc[i]
        p_i = p.iloc[i]
        m = dt.month
        
        deposit = dca_monthly if m != curr_m else 0.0
        curr_m = m
        
        # Step 1: Step executors (executes prior pending orders, processes deposit)
        executor.step(dt, p_i, p_i, dca_amount=deposit)
        bench_executor.step(dt, p_i, p_i, dca_amount=deposit)
        
        # Benchmark Order Submission: single order Day 0, then monthly on deposit
        if i == 0:
            bench_executor.submit_order(1.0, "Benchmark Initial Buy", dt)
        elif deposit > 0:
            bench_executor.submit_order(1.0, "Monthly benchmark investment", dt)
            
        # Process Fills & Wave Accounting
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
                
                if direction == 'BUY':
                    shares = signed_s
                    cost = shares * p_fill + fee
                    pos = 1.0
                    cash_days_count = 0
                    
                    if current_entry_fill is None:
                        # Initial entry of a new wave
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
                        
                    # Factor C Isolation: arm stop countdown on reentry fill
                    if use_factor_c and exit_mode in ['AFTER_BUBBLE', 'AFTER_BEAR']:
                        reentry_fill_price = p_fill
                        stop_timer = 10
                        reentry_just_filled_today = True
                    if use_factor_c:
                        exit_mode = 'NONE'
                        
                elif direction == 'SELL':
                    shares = abs(signed_s)
                    net_proceeds = shares * p_fill - fee
                    pos = 0.0
                    cash_days_count = 0
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
                        
                        last_ord = executor.orders_history[-1] if len(executor.orders_history) > 0 else {'reason': 'UNKNOWN'}
                        round_trips.append({
                            'Asset': asset,
                            'Config': config,
                            'entry_dt': current_entry_fill['dt'],
                            'entry_price': current_entry_fill['price'],
                            'entry_vwap': round(vwap, 4),
                            'exit_dt': dt_fill,
                            'exit_price': p_fill,
                            'exit_reason': last_ord.get('reason', 'UNKNOWN'),
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
                        
                    # Factor C Isolation: exit mode classification
                    reentry_fill_price = None
                    stop_timer = 0
                    if use_factor_c:
                        last_order = executor.orders_history[-1] if len(executor.orders_history) > 0 else {'reason': 'UNKNOWN'}
                        reason_str = last_order.get('reason', '')
                        if 'BUBBLE' in reason_str:
                            exit_mode = 'AFTER_BUBBLE'
                            cooldown_timer = 20
                        elif 'BEAR' in reason_str:
                            exit_mode = 'AFTER_BEAR'
                            cooldown_timer = 20
                        elif 'STOP_LOSS' in reason_str:
                            exit_mode = 'AFTER_STOP'
                            cooldown_timer = 15
                        else:
                            exit_mode = 'NONE'

        if pos == 0.0:
            cash_days_count += 1
            
        # Timers decrement
        if use_factor_c and not reentry_just_filled_today:
            if cooldown_timer > 0:
                cooldown_timer -= 1
                
        # Production signal_ready gating
        is_ready = df['signal_ready'].iloc[i] if 'signal_ready' in df.columns else True
        if not is_ready:
            continue
            
        # Strategy Decision Logic
        submitted_sell_today = False
        
        # Priority 1: Risk Sell Orders
        # 1.1 Factor C Re-entry Stop Loss
        if use_factor_c and pos == 1.0 and stop_timer > 0 and reentry_fill_price is not None:
            if pd.notna(p_i) and p_i < reentry_fill_price * 0.95:
                executor.submit_order(0.0, "STOP_LOSS_5PCT", dt)
                stop_loss_order_count += 1
                submitted_sell_today = True
                stop_timer = 0
                reentry_fill_price = None
            elif not reentry_just_filled_today:
                stop_timer -= 1
                if stop_timer <= 0:
                    reentry_fill_price = None
                
        # 1.2 Bubble / Bear Top Sell
        if not submitted_sell_today and pos == 1.0 and df['raw_sell'].iloc[i]:
            executor.submit_order(0.0, df['sell_reason'].iloc[i], dt)
            submitted_sell_today = True
            
        # Priority 2: Strategy Buy Orders
        if not submitted_sell_today and pos == 0.0:
            if not use_factor_c:
                # Baseline C0 entry: Panic Buy OR Trend Buy
                can_buy = df['Trigger_Panic'].iloc[i] or df['cond_trend'].iloc[i]
                if can_buy:
                    reason = "PANIC_BUY" if df['Trigger_Panic'].iloc[i] else "TREND_BUY"
                    executor.submit_order(1.0, reason, dt)
            else:
                can_buy = False
                buy_reason = 'NONE'
                # Factor C: State-dependent re-entry strictly per frozen v2.0
                if df['Trigger_Panic'].iloc[i]:
                    can_buy = True
                    buy_reason = 'PANIC_BUY'
                elif exit_mode == 'AFTER_BUBBLE':
                    # Path A: 2-day pullback test of 50MA held + above 20MA + positive momentum
                    path_a = bool(ma50_band.iloc[i]) and (p_i > ma20.iloc[i]) and (q1_dot.iloc[i] > 0)
                    # Path B: Cool-down >= 10 trading days + 20-day high breakout + positive momentum
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
                elif exit_mode == 'AFTER_STOP':
                    if cooldown_timer <= 0:
                        can_buy = df['Trigger_Panic'].iloc[i] or df['cond_trend'].iloc[i]
                        buy_reason = 'REENTRY_AFTER_STOP'
                else:
                    if df['cond_trend'].iloc[i]:
                        can_buy = True
                        buy_reason = 'TREND_BUY'
                    
                if can_buy:
                    executor.submit_order(1.0, buy_reason, dt)
                    
        # Priority 3: DCA Follow-up
        if deposit > 0 and pos == 1.0 and not submitted_sell_today:
            executor.submit_order(1.0, "DCA_HOLDING_REINVEST", dt)
            
    # Record Open Position at end of simulation if any
    if current_entry_fill is not None and len(wave_buys) > 0:
        idx_in_matches = df.index[df['date'] == pd.Timestamp(current_entry_fill['dt'])]
        idx_in = idx_in_matches[0] if len(idx_in_matches) > 0 else 0
        dur = max(1, n - 1 - idx_in)
        total_buy_cost = sum(b['cost'] for b in wave_buys)
        total_buy_shares = sum(b['shares'] for b in wave_buys)
        latest_price = p.iloc[-1]
        latest_val = total_buy_shares * latest_price if pd.notna(latest_price) else total_buy_cost
        unrealized_pnl = latest_val - total_buy_cost
        vwap = sum(b['shares'] * b['price'] for b in wave_buys) / total_buy_shares if total_buy_shares > 0 else current_entry_fill['price']
        open_positions.append({
            'Asset': asset,
            'Config': config,
            'entry_dt': current_entry_fill['dt'],
            'entry_vwap': round(vwap, 4),
            'holding_trading_days_to_end': dur,
            'total_buy_shares': round(total_buy_shares, 4),
            'total_buy_cost': round(total_buy_cost, 2),
            'latest_market_val': round(latest_val, 2),
            'unrealized_pnl': round(unrealized_pnl, 2),
            'unrealized_pnl_pct': round(unrealized_pnl / total_buy_cost * 100.0, 4) if total_buy_cost > 0 else 0.0,
            'num_dca_additions': len(wave_buys) - 1
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
            'underlying_return_pct': round((latest_price - cash_start_p) / cash_start_p * 100.0, 4) if cash_start_p else 0.0
        })

    # Summary Statistics
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


def main():
    print("=" * 80)
    print("Universal Reflexivity Radar Factorial Ablation Experiment v2.2")
    print("=" * 80)
    
    prices = pd.read_csv(ROOT / 'now_ohlcv_local.csv')
    macro = pd.read_csv(ROOT / 'market_data_local.csv')
    
    # 1. Production Dual-Track Baseline Verification
    print("\n[Step 1] Running Production Dual-Track Baseline...")
    prod_df = run_universal_reflexivity_radar('NOW', prices, macro)
    first_ready_dt = prod_df.loc[prod_df['signal_ready'], 'date'].iloc[0]
    print(f"Production first signal_ready date: {first_ready_dt.strftime('%Y-%m-%d')}")
    
    # 2. Continuous Full-History Technical Features Preparation
    print("\n[Step 2] Computing Full-History Features (Zero Model Drift)...")
    df_now_features = prepare_base_features(prices, macro, price_col='close')
    first_ready_v22 = df_now_features.loc[df_now_features['signal_ready'], 'date'].iloc[0]
    print(f"v2.2 first signal_ready date: {first_ready_v22.strftime('%Y-%m-%d')}")
    assert first_ready_v22 == first_ready_dt, "signal_ready start date mismatch!"
    
    # Slice research period from dynamic signal_ready date
    df_now_warm = df_now_features[df_now_features['date'] >= first_ready_dt].copy().reset_index(drop=True)
    
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
    
    # 3. Factorial Ablation: NOW
    print("\n[Step 3] Running Factorial Ablation: NOW...")
    now_results = []
    for name, fa, fb, fc in combos:
        df_sig = generate_signals(df_now_warm, fa, fb, fc, price_col='close')
        sig_eval = evaluate_signals(df_sig, price_col='close')
        exec_res = run_execution_simulation(
            df_sig, price_col='close', use_factor_c=fc, use_factor_a=fa, asset='NOW', config=name
        )
        
        all_round_trips.extend(exec_res['round_trips_ledger'])
        all_cash_intervals.extend(exec_res['cash_intervals'])
        all_open_positions.extend(exec_res['open_positions'])
        all_open_cash_intervals.extend(exec_res['open_cash_intervals'])
        all_event_evals.extend(exec_res['event_forward_evaluations'])
        
        now_results.append({
            'Ticker': 'NOW',
            'Config': name,
            'A_Score': fa,
            'B_Latch': fb,
            'C_Reentry': fc,
            'Panic_FDR%': sig_eval['panic_buy_fdr'],
            'Bottom_Miss%': sig_eval['bottom_miss_rate'],
            'Sell_FDR%': sig_eval['sell_fdr'],
            'Top_Miss%': sig_eval['top_miss_rate'],
            'Strat_Final': exec_res['strat_final'],
            'Bench_Final': exec_res['bench_final'],
            'Strat_XIRR%': exec_res['strat_xirr'],
            'Bench_XIRR%': exec_res['bench_xirr'],
            'Delta_XIRR_pct_pt': exec_res['alpha_xirr_diff'],
            'Strat_MDD%': exec_res['strat_mdd'],
            'Bench_MDD%': exec_res['bench_mdd'],
            'RoundTrips': exec_res['round_trips'],
            'ShortRT%': exec_res['short_term_rate'],
            'StopOrders': exec_res['stop_loss_order_count'],
            'Strat_First_Fill': exec_res['strategy_first_fill_dt'],
            'Bench_First_Fill': exec_res['benchmark_first_fill_dt']
        })
    df_now_res = pd.DataFrame(now_results)
    df_now_res.to_csv(OUT_DIR / 'factorial_ablation_results_v2_2_now.csv', index=False)
    print("\nNOW Factorial Results:")
    print(df_now_res[['Config', 'Strat_Final', 'Bench_Final', 'Strat_XIRR%', 'Delta_XIRR_pct_pt', 'Strat_MDD%', 'StopOrders', 'Strat_First_Fill', 'Bench_First_Fill']].to_string(index=False))
    
    # 4. Cross-Asset Factorial Ablations: QQQ and SPY
    print("\n[Step 4] Running Cross-Asset Factorial Ablations on QQQ & SPY...")
    for ticker in ['QQQ', 'SPY']:
        df_asset_p = macro[['date', ticker]].dropna().rename(columns={ticker: 'close'})
        df_asset = prepare_base_features(df_asset_p, macro, price_col='close')
        df_asset_warm = df_asset[df_asset['date'] >= first_ready_dt].copy().reset_index(drop=True)
        
        asset_results = []
        for name, fa, fb, fc in combos:
            df_sig = generate_signals(df_asset_warm, fa, fb, fc, price_col='close')
            sig_eval = evaluate_signals(df_sig, price_col='close')
            exec_res = run_execution_simulation(
                df_sig, price_col='close', use_factor_c=fc, use_factor_a=fa, asset=ticker, config=name
            )
            
            all_round_trips.extend(exec_res['round_trips_ledger'])
            all_cash_intervals.extend(exec_res['cash_intervals'])
            all_open_positions.extend(exec_res['open_positions'])
            all_open_cash_intervals.extend(exec_res['open_cash_intervals'])
            all_event_evals.extend(exec_res['event_forward_evaluations'])
            
            asset_results.append({
                'Ticker': ticker,
                'Config': name,
                'A_Score': fa,
                'B_Latch': fb,
                'C_Reentry': fc,
                'Panic_FDR%': sig_eval['panic_buy_fdr'],
                'Bottom_Miss%': sig_eval['bottom_miss_rate'],
                'Sell_FDR%': sig_eval['sell_fdr'],
                'Top_Miss%': sig_eval['top_miss_rate'],
                'Strat_Final': exec_res['strat_final'],
                'Bench_Final': exec_res['bench_final'],
                'Strat_XIRR%': exec_res['strat_xirr'],
                'Bench_XIRR%': exec_res['bench_xirr'],
                'Delta_XIRR_pct_pt': exec_res['alpha_xirr_diff'],
                'Strat_MDD%': exec_res['strat_mdd'],
                'Bench_MDD%': exec_res['bench_mdd'],
                'RoundTrips': exec_res['round_trips'],
                'ShortRT%': exec_res['short_term_rate'],
                'StopOrders': exec_res['stop_loss_order_count'],
                'Strat_First_Fill': exec_res['strategy_first_fill_dt'],
                'Bench_First_Fill': exec_res['benchmark_first_fill_dt']
            })
        df_asset_res = pd.DataFrame(asset_results)
        df_asset_res.to_csv(OUT_DIR / f'factorial_ablation_results_v2_2_{ticker.lower()}.csv', index=False)
        print(f"\n{ticker} Results:")
        print(df_asset_res[['Config', 'Strat_Final', 'Bench_Final', 'Strat_XIRR%', 'Delta_XIRR_pct_pt', 'Strat_MDD%', 'StopOrders', 'Strat_First_Fill']].to_string(index=False))
        
    # 5. Save Comprehensive Cross-Asset Ledgers
    pd.DataFrame(all_round_trips).to_csv(OUT_DIR / 'round_trip_ledgers_v2_2.csv', index=False)
    pd.DataFrame(all_cash_intervals).to_csv(OUT_DIR / 'cash_intervals_v2_2.csv', index=False)
    pd.DataFrame(all_open_positions).to_csv(OUT_DIR / 'open_positions_v2_2.csv', index=False)
    pd.DataFrame(all_open_cash_intervals).to_csv(OUT_DIR / 'open_cash_intervals_v2_2.csv', index=False)
    pd.DataFrame(all_event_evals).to_csv(OUT_DIR / 'forward_return_evaluations_v2_2.csv', index=False)
    
    print(f"\nSaved Comprehensive Ledgers:")
    print(f"- Round trips: {len(all_round_trips)} records across assets: {pd.DataFrame(all_round_trips)['Asset'].unique().tolist()}")
    print(f"- Cash intervals: {len(all_cash_intervals)} records across assets: {pd.DataFrame(all_cash_intervals)['Asset'].unique().tolist()}")
    print(f"- Open positions: {len(all_open_positions)} records")
    print(f"- Open cash intervals: {len(all_open_cash_intervals)} records")
    print(f"- Event evaluations: {len(all_event_evals)} discrete trade event records")
    print("\nV2_2_EXECUTION_COMPLETED_SUCCESSFULLY")


if __name__ == '__main__':
    main()
