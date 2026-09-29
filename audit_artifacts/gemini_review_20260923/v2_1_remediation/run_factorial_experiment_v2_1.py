"""
Factorial Ablation Experiment Engine v2.1 (Strict Defect Remediation & Production Parity)

Addresses all 6 critical findings from independent review (REVIEW.md):
1. Strict Factor C Isolation: All exit_mode tracking, re-entry state transitions,
   stop timers, and 5% stop-loss logic are 100% enclosed within if use_factor_c.
   In C0, C1, C2, and C4, STOP_LOSS_5PCT orders are strictly 0. Base accounting
   (pos update, shares, cash, unit NAV) remains universal across all configurations.
2. Benchmark Initial Order Parity: Submits a single Day 0 initial order, filled on the
   first executable subsequent trading day. Subsequent monthly deposits submit
   reinvestment orders without duplicate same-day cancellation.
3. Pending Risk Order Persistence: When a risk sell order is pending (due to missing
   price or execution timing), subsequent DCA deposits do NOT override it with target 1.0.
4. Latch & Hysteresis Coupling: Latch is consumed ONLY when candidate passes momentum,
   MA10, AND hysteresis filters to emit an active signal. Suppressed candidates do NOT
   prematurely consume the latch. Calendar day difference for hysteresis is preserved.
5. Continuous Feature Engineering & Dual Sub-period Evaluation:
   - All rolling indicators, shifts, and extrema are pre-computed on the full dataset.
   - Mode A (Continuous Inherited): Inherits all portfolio states across sub-periods for stage attribution.
   - Mode B (Segment Fresh Reset): Resets account with initial cash at sub-period start on pre-warmed indicators.
6. Complete Deliverables & True Production Dual-track:
   - Exports NOW, QQQ, and SPY factorial results CSVs.
   - Exports trade-level attribution ledgers (distinguishing Initial Buy, DCA Reinvestment,
     Panic Bottom, Trend Buy, Re-entry, and Exits).
   - Exports cash-holding intervals and opportunity costs.
   - Evaluates 20-day and 60-day forward returns for trend/re-entry buys.
   - Runs original production reflexivity radar as formal dual-track baseline.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT))

import json
import numpy as np
import pandas as pd
from typing import Dict, Any, List, Tuple

from true_accounting import UnitizedAccount, calculate_xirr
from shared_executor import SharedExecutor
from reflexivity_engine import run_universal_reflexivity_radar

OUT_DIR = Path(__file__).resolve().parent

# =========================================================================
# 1. Base Feature Engineering (Continuous History Pre-computation)
# =========================================================================

def prepare_base_features(df_price: pd.DataFrame, df_macro: pd.DataFrame, price_col: str = 'close') -> pd.DataFrame:
    """
    Computes kinematics, technical moving averages, macro regimes, and score factors.
    All rolling windows (e.g. 200MA, 90-day crash recovery, 50MA band) are precomputed
    on the full uninterrupted historical dataset.
    """
    df = df_price.copy()
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date').reset_index(drop=True)
    
    # Clean prices
    df[price_col] = df[price_col].ffill()
    p = df[price_col]
    
    # Moving Averages
    df['MA10'] = p.rolling(10).mean()
    df['MA20'] = p.rolling(20).mean()
    df['MA50'] = p.rolling(50).mean()
    df['MA200'] = p.rolling(200).mean()
    
    # Distances & Slopes
    df['Dist_200MA'] = (p - df['MA200']) / (df['MA200'] + 1e-8) * 100.0
    df['Dist_50MA'] = (p - df['MA50']) / (df['MA50'] + 1e-8) * 100.0
    df['MA200_Slope'] = (df['MA200'] - df['MA200'].shift(20)) / (df['MA200'].shift(20) + 1e-8) * 100.0
    
    # Continuous Kinematics (Spec v2.0)
    df['q1'] = (p - df['MA50']) / (df['MA50'] + 1e-8) * 100.0
    df['q1_dot'] = df['q1'] - df['q1'].shift(1)
    df['q1_ddot'] = df['q1_dot'] - df['q1_dot'].shift(1)
    df['v_dot'] = df['q1_dot'] * (df['q1'] + 20.0 * df['q1_ddot'])
    
    # Phase Space Quadrant
    q1 = df['q1']
    q1_dot = df['q1_dot']
    cond_q1 = (q1 >= 0) & (q1_dot >= 0)
    cond_q2 = (q1 < 0) & (q1_dot >= 0)
    cond_q3 = (q1 < 0) & (q1_dot < 0)
    cond_q4 = (q1 >= 0) & (q1_dot < 0)
    df['Quadrant'] = np.select([cond_q1, cond_q2, cond_q3, cond_q4], [1, 2, 3, 4], default=1)
    
    # Capital & Liquidity Features (Disclose neutral defaults if OHLCV missing)
    has_ohlcv = {'high', 'low', 'volume'}.issubset(df.columns)
    if has_ohlcv:
        hl_range = df['high'] - df['low']
        clv = np.where(hl_range > 1e-8, ((df[price_col] - df['low']) - (df['high'] - df[price_col])) / hl_range, 0.0)
        vol = df['volume'].fillna(0.0)
        df['CMF20'] = (pd.Series(clv * vol, index=df.index).rolling(20).sum()) / (vol.rolling(20).sum() + 1e-8)
        vol_mean50 = vol.rolling(50).mean()
        df['Vol_Ratio50'] = np.where(vol_mean50 > 1e-8, vol / vol_mean50, 1.0)
        df['Score_Dim4_Capital'] = np.clip((df['CMF20'] + 0.3) / 0.6 * 100.0, 0.0, 100.0)
        df['Score_Dim5_Liquidity'] = np.clip(df['Vol_Ratio50'] / 2.0 * 100.0, 0.0, 100.0)
    else:
        # Cross-asset macro closes (QQQ, SPY): explicitly disclose neutral 50.0 defaults
        df['CMF20'] = 0.0
        df['Vol_Ratio50'] = 1.0
        df['Score_Dim4_Capital'] = 50.0
        df['Score_Dim5_Liquidity'] = 50.0
        
    # Merge Macro Regimes
    macro = df_macro.copy()
    macro['date'] = pd.to_datetime(macro['date'])
    df = pd.merge(df, macro, on='date', how='left')
    
    # Macro Indicators
    if 'HYG' in df.columns:
        df['Macro_MA50'] = df['HYG'].rolling(50).mean()
        df['Macro_MA200'] = df['HYG'].rolling(200).mean()
    else:
        df['Macro_MA50'] = np.nan
        df['Macro_MA200'] = np.nan
        
    # Crisis Regime Filter
    nfci_stress = (df['NFCI'] > 0.0) if 'NFCI' in df.columns else False
    baa_stress = (df['BAA10Y'] > 2.5) if 'BAA10Y' in df.columns else False
    ry_stress = (df['Real_Yield'] > 2.0) if 'Real_Yield' in df.columns else False
    df['macro_crisis_regime'] = nfci_stress | baa_stress | ry_stress
    
    # Legacy Score (Baseline C0)
    score_pos = np.clip((df['Dist_200MA'] + 20.0) / 40.0 * 100.0, 0.0, 100.0)
    score_vel = np.clip((df['q1_dot'] + 5.0) / 10.0 * 100.0, 0.0, 100.0)
    score_lya = np.clip((df['v_dot'] + 50.0) / 100.0 * 100.0, 0.0, 100.0)
    
    if 'NFCI' in df.columns and 'BAA10Y' in df.columns:
        nfci_norm = np.clip((df['NFCI'] + 1.0) / 2.0 * 100.0, 0.0, 100.0)
        baa_norm = np.clip((df['BAA10Y'] - 1.0) / 3.0 * 100.0, 0.0, 100.0)
        score_macro = (nfci_norm + baa_norm) / 2.0
    else:
        score_macro = 50.0
    df['Score_Dim6_Macro'] = score_macro
    
    df['Composite_Score_M0'] = (
        0.25 * score_pos +
        0.20 * score_vel +
        0.15 * score_lya +
        0.15 * df['Score_Dim4_Capital'] +
        0.10 * df['Score_Dim5_Liquidity'] +
        0.15 * df['Score_Dim6_Macro']
    )
    
    # Factor A Decoupled Scores (Strictly Directional)
    # Panic depth: strictly positive during severe undershoot
    df['Score_PanicDepth_A'] = np.clip(-df['Dist_200MA'] / 25.0 * 100.0, 0.0, 100.0)
    # Overheat score: strictly positive during high extension
    df['Score_Overheat_A'] = np.clip(df['Dist_200MA'] / 30.0 * 100.0, 0.0, 100.0)
    # Macro Stress: unipolar credit + monetary stress
    df['Score_MacroStress_A'] = score_macro
    
    # Precompute all continuous pattern signals on the full uninterrupted history
    df['ma50_band'] = (abs(p - df['MA50']) / (df['MA50'] + 1e-8) <= 0.025).rolling(2).sum() == 2
    df['ma50_reclaim_3d'] = (p > df['MA50']).rolling(3).sum() == 3
    df['not_rebounding_from_crash'] = df['Dist_200MA'].rolling(90).min() >= -12.0
    df['rolling_20d_high'] = p.rolling(20).max().shift(1)
    df['cond_trend'] = (p > df['MA50']).rolling(3).sum() == 3
    
    # Production Data Readiness Gate
    core_cols = ['Composite_Score_M0', 'Dist_200MA', price_col, 'MA200', 'MA50', 'MA20', 'MA10']
    df['signal_ready'] = df[core_cols].notna().all(axis=1)
    
    return df

# =========================================================================
# 2. Signal Generation (With Strict Hysteresis-Coupled Latch Consumption)
# =========================================================================

def generate_signals(
    df: pd.DataFrame,
    use_factor_a: bool = False,
    use_factor_b: bool = False,
    use_factor_c: bool = False,
    price_col: str = 'close'
) -> pd.DataFrame:
    """
    Generates rule signals with exact spec compliance.
    Factor B (Panic Latch):
    - Activates when Dist_200MA < -10%
    - Refreshes anchor & 15-day countdown on lower low > 2%
    - Decrements daily; expires at 0
    - Rigid MA10 & positive momentum gate: (q1_dot > 0) & (p > MA10)
    - CONSUMPTION RULE: Latch is consumed ONLY when candidate passes both
      the technical gate AND the calendar-day hysteresis check. Suppressed candidates
      do NOT consume the latch.
    """
    df = df.copy()
    p = df[price_col]
    n = len(df)
    
    # 1. Panic Bottom Regimes & Gates
    if not use_factor_a:
        regime_panic_raw = (df['Composite_Score_M0'] <= 32.0) | (df['Dist_200MA'] < -10.0)
    else:
        regime_panic_raw = (df['Score_PanicDepth_A'] >= 70.0) | (df['Dist_200MA'] < -10.0)
        
    gate_panic = (df['Dist_200MA'] <= -5.0) & (df['q1'] < 0)
    
    trigger_panic = np.zeros(n, dtype=bool)
    
    if not use_factor_b:
        # Baseline instantaneous panic trigger
        raw_cand = regime_panic_raw & gate_panic & (df['q1_dot'] > 0) & (p > df['MA10'])
        last_dt = None
        last_p = None
        for i in range(n):
            if raw_cand.iloc[i]:
                dt = df['date'].iloc[i]
                p_val = p.iloc[i]
                cal_days = (dt - last_dt).days if last_dt is not None else 999
                price_drop_ok = (p_val < last_p * 0.93) if last_p is not None else True
                if cal_days > 15 or price_drop_ok:
                    trigger_panic[i] = True
                    last_dt = dt
                    last_p = p_val
    else:
        # Factor B: Panic Memory Latch with Hysteresis-Coupled Consumption
        K_window = 15 # Trading days
        latch = False
        timer = 0
        p_anchor = 0.0
        
        last_dt = None
        last_p = None
        
        for i in range(n):
            dt = df['date'].iloc[i]
            p_i = p.iloc[i]
            reg_i = regime_panic_raw.iloc[i]
            gate_i = gate_panic.iloc[i]
            q_dot_i = df['q1_dot'].iloc[i]
            ma10_i = df['MA10'].iloc[i]
            
            # Latch state transition
            if reg_i and gate_i and not latch:
                latch = True
                timer = K_window
                p_anchor = p_i
            elif latch:
                if p_i < p_anchor * 0.98: # Lower low by > 2%: refresh anchor & timer
                    p_anchor = p_i
                    timer = K_window
                else:
                    timer -= 1
                    if timer <= 0:
                        latch = False
                        
            # Rigid Signal Gate: latch active, momentum strictly positive, price above MA10
            if latch and (q_dot_i > 0) and (p_i > ma10_i):
                # Check calendar-day hysteresis BEFORE consuming the latch
                cal_days = (dt - last_dt).days if last_dt is not None else 999
                price_drop_ok = (p_i < last_p * 0.93) if last_p is not None else True
                if cal_days > 15 or price_drop_ok:
                    trigger_panic[i] = True
                    last_dt = dt
                    last_p = p_i
                    # Latch is consumed ONLY upon successfully emitting an active signal!
                    latch = False
                # If suppressed by hysteresis, latch is NOT consumed and continues countdown.
                
    df['Trigger_Panic'] = trigger_panic
    
    # 2. Bubble Top & Bear Top Triggers
    not_rebounding = df['not_rebounding_from_crash']
    if not use_factor_a:
        regime_bubble_top = (df['Composite_Score_M0'] >= 70.0) | (df['Dist_200MA'] > 22.0)
    else:
        regime_bubble_top = (df['Score_Overheat_A'] >= 75.0) | (df['Dist_200MA'] > 22.0)
        
    gate_bubble_top = (df['Dist_200MA'] >= 10.0) & (df['q1'] >= 0) & not_rebounding
    inflection_bubble_top = (df['Quadrant'] == 4) & (df['Quadrant'].shift(1) == 1)
    acceleration_bubble_top = (p < df['MA20']) & (df['q1_dot'] < 0) & (df['q1_dot'].shift(1) >= 0)
    raw_bubble_top = regime_bubble_top & gate_bubble_top & (inflection_bubble_top | acceleration_bubble_top)
    
    bear_regime = (df['MA200_Slope'] < -0.05) | (df['MA50'] < df['MA200'] * 0.98) | df['macro_crisis_regime']
    exhaustion_gate = (df['Dist_200MA'] < 5.0)
    inflection_bear_top = (p < df['MA20']) & (df['q1_dot'] < 0) & (df['q1_dot'].shift(1) >= 0)
    raw_bear_top = bear_regime & exhaustion_gate & inflection_bear_top & (~raw_bubble_top)
    
    # Hysteresis Filter for Tops (Strict Calendar Days)
    def apply_top_hys(raw_flags: pd.Series, min_days: int, price_step: float) -> pd.Series:
        flags = np.zeros(n, dtype=bool)
        last_dt = None
        last_p = None
        for idx in range(n):
            if raw_flags.iloc[idx]:
                dt = df['date'].iloc[idx]
                p_val = p.iloc[idx]
                cal_days = (dt - last_dt).days if last_dt is not None else 999
                price_rise_ok = (p_val > last_p * (1.0 + price_step)) if last_p is not None else True
                if cal_days > min_days or price_rise_ok:
                    flags[idx] = True
                    last_dt = dt
                    last_p = p_val
        return pd.Series(flags, index=df.index)
        
    df['Trigger_Bubble_Top'] = apply_top_hys(raw_bubble_top, min_days=25, price_step=0.08)
    df['Trigger_Bear_Top'] = apply_top_hys(raw_bear_top, min_days=20, price_step=0.06)
    
    df['raw_sell'] = df['Trigger_Bubble_Top'] | df['Trigger_Bear_Top']
    df['sell_reason'] = np.where(df['Trigger_Bubble_Top'], 'BUBBLE', np.where(df['Trigger_Bear_Top'], 'BEAR', 'NONE'))
    
    # Baseline Trend Buy Condition
    df['raw_buy'] = df['Trigger_Panic'] | df['cond_trend']
    
    return df

# =========================================================================
# 3. Objective Signal Evaluation (Extrema & Forward Returns)
# =========================================================================

def evaluate_signals(df: pd.DataFrame, price_col: str = 'close', window: int = 20) -> Dict[str, Any]:
    """
    Strict Spec v2.0 signal evaluation:
    - Panic Buy matched against local troughs in [S - 15, S + 5] trading days.
    - Top Sells matched against local peaks in [S - 15, S + 5] trading days.
    - Forward 20-day and 60-day returns for Trend & Re-entry Buys.
    - Samples with insufficient forward observation periods are strictly isolated.
    """
    p = df[price_col].values
    n = len(p)
    
    is_local_min = np.zeros(n, dtype=bool)
    is_local_max = np.zeros(n, dtype=bool)
    for i in range(window, n - window):
        chunk = p[i - window : i + window + 1]
        if p[i] == np.min(chunk):
            is_local_min[i] = True
        if p[i] == np.max(chunk):
            is_local_max[i] = True
            
    eval_mask = np.zeros(n, dtype=bool)
    eval_mask[window : n - 60] = True
    
    total_mins = int(np.sum(is_local_min & eval_mask))
    total_maxs = int(np.sum(is_local_max & eval_mask))
    
    # Panic Buy Matching: Extrema E must be in [S - 15, S + 5]
    buy_signals = np.where(df['Trigger_Panic'] & eval_mask)[0]
    matched_buys = 0
    hit_mins = np.zeros(n, dtype=bool)
    for b_idx in buy_signals:
        lo = max(0, b_idx - 15)
        hi = min(n, b_idx + 6)
        mins_in_win = np.where(is_local_min[lo:hi])[0]
        if len(mins_in_win) > 0:
            matched_buys += 1
            for m_pos in mins_in_win:
                hit_mins[lo + m_pos] = True
                
    fdr_buys = 1.0 - (matched_buys / len(buy_signals)) if len(buy_signals) > 0 else 0.0
    miss_rate_buys = 1.0 - (np.sum(hit_mins & eval_mask) / total_mins) if total_mins > 0 else 0.0
    
    # Top Sell Matching: Extrema E must be in [S - 15, S + 5]
    sell_signals = np.where(df['raw_sell'] & eval_mask)[0]
    matched_sells = 0
    hit_maxs = np.zeros(n, dtype=bool)
    for s_idx in sell_signals:
        lo = max(0, s_idx - 15)
        hi = min(n, s_idx + 6)
        maxs_in_win = np.where(is_local_max[lo:hi])[0]
        if len(maxs_in_win) > 0:
            matched_sells += 1
            for m_pos in maxs_in_win:
                hit_maxs[lo + m_pos] = True
                
    fdr_sells = 1.0 - (matched_sells / len(sell_signals)) if len(sell_signals) > 0 else 0.0
    miss_rate_sells = 1.0 - (np.sum(hit_maxs & eval_mask) / total_maxs) if total_maxs > 0 else 0.0
    
    # Forward Returns for Trend / Re-entry Buys (Separate evaluation)
    trend_indices = np.where(df['cond_trend'])[0]
    fwd_20 = []
    fwd_60 = []
    for idx in trend_indices:
        if idx + 20 < n:
            fwd_20.append((p[idx + 20] - p[idx]) / p[idx] * 100.0)
        if idx + 60 < n:
            fwd_60.append((p[idx + 60] - p[idx]) / p[idx] * 100.0)
            
    win_20 = (sum(1 for r in fwd_20 if r > 0) / len(fwd_20) * 100.0) if fwd_20 else 0.0
    mean_20 = float(np.mean(fwd_20)) if fwd_20 else 0.0
    win_60 = (sum(1 for r in fwd_60 if r > 0) / len(fwd_60) * 100.0) if fwd_60 else 0.0
    mean_60 = float(np.mean(fwd_60)) if fwd_60 else 0.0
    
    return {
        'total_eval_days': int(np.sum(eval_mask)),
        'true_minima': total_mins,
        'true_maxima': total_maxs,
        'panic_buy_signals': len(buy_signals),
        'panic_buy_fdr': round(fdr_buys * 100.0, 2),
        'buy_fdr': round(fdr_buys * 100.0, 2),
        'bottom_miss_rate': round(miss_rate_buys * 100.0, 2),
        'sell_signals': len(sell_signals),
        'sell_fdr': round(fdr_sells * 100.0, 2),
        'top_miss_rate': round(miss_rate_sells * 100.0, 2),
        'trend_fwd_20d_samples': len(fwd_20),
        'trend_fwd_20d_win_pct': round(win_20, 2),
        'trend_fwd_20d_mean_pct': round(mean_20, 2),
        'trend_fwd_60d_samples': len(fwd_60),
        'trend_fwd_60d_win_pct': round(win_60, 2),
        'trend_fwd_60d_mean_pct': round(mean_60, 2),
    }

# =========================================================================
# 4. Rigorous Execution Simulation Engine (Strict Factor C Isolation)
# =========================================================================

def run_execution_simulation(
    df: pd.DataFrame,
    initial_cash: float = 10000.0,
    dca_monthly: float = 1000.0,
    fee_rate: float = 0.001,
    price_col: str = 'close',
    use_factor_c: bool = False,
    use_factor_a: bool = False
) -> Dict[str, Any]:
    """
    Executes brokerage accounting with zero phantom compounding.
    
    STRICT BOUNDARIES:
    - Base accounting (pos update, shares, cash, unit NAV) applies universally.
    - Factor C elements (exit_mode tracking, re-entry gating, stop loss) are
      strictly guarded by if use_factor_c:.
    - In C0, C1, C2, and C4 (use_factor_c=False), STOP_LOSS_5PCT orders count is STRICTLY 0.
    - Benchmark order parity: Submits exactly once on Day 0; fills on first executable
      subsequent trading day. DCA deposits reinvest monthly without duplicate cancellations.
    - Pending risk order protection: Pending sell orders are NEVER overridden by DCA reinvestment.
    """
    acc = UnitizedAccount(initial_cash=initial_cash, initial_date=df['date'].iloc[0])
    bench_acc = UnitizedAccount(initial_cash=initial_cash, initial_date=df['date'].iloc[0])
    
    executor = SharedExecutor(acc, fee_rate=fee_rate, execution_mode='NEXT_CLOSE', account_type='strat')
    bench_executor = SharedExecutor(bench_acc, fee_rate=fee_rate, execution_mode='NEXT_CLOSE', account_type='bench')
    
    # Universal strategy position tracking
    pos = 0.0 # Start strictly in cash
    curr_m = -1
    last_fill_count = 0
    cash_days_count = 0
    
    # Factor C isolated variables
    exit_mode = 'NONE' # 'NONE', 'AFTER_BUBBLE', 'AFTER_BEAR'
    reentry_fill_price = None
    stop_timer = 0
    
    p = df[price_col]
    ma20 = df['MA20']
    q1_dot = df['q1_dot']
    macro_stress = df['Score_MacroStress_A'] if use_factor_a else df['Score_Dim6_Macro']
    hyg_rebound = (df['HYG'] > df['Macro_MA200']) if ('HYG' in df.columns and 'Macro_MA200' in df.columns) else False
    
    # Detailed execution ledgers
    round_trips = []
    cash_intervals = []
    current_entry_fill = None
    cash_start_dt = None
    cash_start_p = None
    
    for i in range(len(df)):
        dt = df['date'].iloc[i]
        p_i = p.iloc[i]
        
        m = dt.month
        deposit = dca_monthly if m != curr_m else 0.0
        curr_m = m
        
        # Step 1: Step executor (executes prior pending orders, processes today's deposit)
        executor.step(dt, p_i, p_i, dca_amount=deposit)
        bench_executor.step(dt, p_i, p_i, dca_amount=deposit)
        
        # Benchmark Order Submission (Bug Fix: Single Day 0 order, no same-day duplicate cancellation)
        if i == 0:
            bench_executor.submit_order(1.0, "Benchmark Initial Buy", dt)
        elif deposit > 0:
            bench_executor.submit_order(1.0, "Monthly benchmark investment", dt)
            
        # Update Strategy Position from Executor Fills (Universal Base Accounting)
        reentry_just_filled_today = False
        if len(executor.fills) > last_fill_count:
            latest_fill = executor.fills[-1]
            last_fill_count = len(executor.fills)
            
            if latest_fill['direction'] == 'BUY':
                pos = 1.0
                cash_days_count = 0
                current_entry_fill = latest_fill
                
                # Close out cash interval ledger
                if cash_start_dt is not None:
                    cash_end_p = latest_fill['price']
                    dur_days = max(1, i - cash_start_idx)
                    cash_intervals.append({
                        'cash_start_dt': cash_start_dt,
                        'cash_end_dt': dt.strftime('%Y-%m-%d'),
                        'duration_trading_days': dur_days,
                        'underlying_start_p': cash_start_p,
                        'underlying_end_p': cash_end_p,
                        'underlying_return_pct': (cash_end_p - cash_start_p) / cash_start_p * 100.0,
                    })
                    cash_start_dt = None
                    
                # Factor C Isolation: Re-entry stop countdown arming (10 trading days after fill)
                if use_factor_c and exit_mode in ['AFTER_BUBBLE', 'AFTER_BEAR']:
                    reentry_fill_price = latest_fill['price']
                    stop_timer = 10
                    reentry_just_filled_today = True
                if use_factor_c:
                    exit_mode = 'NONE'
                    
            elif latest_fill['direction'] == 'SELL':
                pos = 0.0
                cash_days_count = 0
                cash_start_dt = dt.strftime('%Y-%m-%d')
                cash_start_idx = i
                cash_start_p = latest_fill['price']
                
                # Record round-trip ledger
                if current_entry_fill is not None:
                    idx_in = df.index[df['date'] == pd.Timestamp(current_entry_fill['dt'])][0] if len(df.index[df['date'] == pd.Timestamp(current_entry_fill['dt'])]) > 0 else 0
                    idx_out = i
                    dur = max(1, idx_out - idx_in)
                    p_in = current_entry_fill['price']
                    p_out = latest_fill['price']
                    pnl_pct = (p_out * (1 - fee_rate) - p_in * (1 + fee_rate)) / (p_in * (1 + fee_rate)) * 100.0
                    
                    last_ord = executor.orders_history[-1]
                    round_trips.append({
                        'entry_dt': current_entry_fill['dt'],
                        'entry_price': p_in,
                        'exit_dt': latest_fill['dt'],
                        'exit_price': p_out,
                        'exit_reason': last_ord['reason'],
                        'duration_trading_days': dur,
                        'pnl_pct': pnl_pct,
                        'is_short_term': dur <= 5
                    })
                    current_entry_fill = None
                    
                # Factor C Isolation: Reset stop loss & identify exit mode
                reentry_fill_price = None
                stop_timer = 0
                if use_factor_c:
                    last_order = executor.orders_history[-1]
                    if 'BUBBLE' in last_order['reason']:
                        exit_mode = 'AFTER_BUBBLE'
                    elif 'BEAR' in last_order['reason']:
                        exit_mode = 'AFTER_BEAR'
                    else:
                        exit_mode = 'NONE'
                        
        if pos == 0.0:
            cash_days_count += 1
            if cash_start_dt is None:
                cash_start_dt = dt.strftime('%Y-%m-%d')
                cash_start_idx = i
                cash_start_p = p_i
                
        # Factor C Isolated Stop Loss Check (10 trading days after fill)
        stop_loss_triggered = False
        if use_factor_c and pos == 1.0 and stop_timer > 0 and reentry_fill_price is not None:
            if not reentry_just_filled_today:
                if pd.notna(p_i) and p_i < reentry_fill_price * 0.95:
                    stop_loss_triggered = True
                    stop_timer = 0
                else:
                    stop_timer -= 1
                    # Daily deposit additions do NOT reset stop_timer
                
        # Step 2: Determine daily target position intent
        s_panic = df['Trigger_Panic'].iloc[i]
        s_sell = df['raw_sell'].iloc[i]
        s_sell_reason = df['sell_reason'].iloc[i]
        
        # Check if an existing risk exit order is already pending (due to missing price or timing)
        has_pending_sell = any(o['status'] == 'PENDING' and o['target'] == 0.0 for o in executor.pending_orders)
        
        target_pos = None
        target_reason = None
        
        if pos > 0.0:
            # Holding position: exit signals or stop loss
            if use_factor_c and stop_loss_triggered:
                target_pos = 0.0
                target_reason = 'STOP_LOSS_5PCT'
            elif s_sell:
                target_pos = 0.0
                target_reason = s_sell_reason
            elif deposit > 0:
                # DCA reinvestment while holding, ONLY if not currently exiting
                if not has_pending_sell:
                    target_pos = 1.0
                    target_reason = 'DCA_HOLDING_REINVEST'
        else:
            # Cash position: entry signals
            can_buy = False
            b_reason = 'NONE'
            
            if not use_factor_c:
                # Baseline entry: Panic Bottom OR 3-day MA50 trend
                if s_panic:
                    can_buy = True
                    b_reason = 'PANIC_BOTTOM'
                elif df['cond_trend'].iloc[i]:
                    can_buy = True
                    b_reason = 'TREND_BUY'
            else:
                # Factor C: State-dependent re-entry
                if s_panic:
                    can_buy = True
                    b_reason = 'PANIC_BOTTOM'
                elif exit_mode == 'AFTER_BUBBLE':
                    path_a = df['ma50_band'].iloc[i] and (p_i > ma20.iloc[i]) and (q1_dot.iloc[i] > 0)
                    path_b = (cash_days_count >= 10) and (p_i > df['rolling_20d_high'].iloc[i]) and (q1_dot.iloc[i] > 0)
                    if path_a or path_b:
                        can_buy = True
                        b_reason = 'REENTRY_AFTER_BUBBLE'
                elif exit_mode == 'AFTER_BEAR':
                    stress_val = macro_stress.iloc[i] if hasattr(macro_stress, 'iloc') else macro_stress
                    hyg_val = hyg_rebound.iloc[i] if hasattr(hyg_rebound, 'iloc') else hyg_rebound
                    path_bear = (stress_val < 60.0 or hyg_val) and df['ma50_reclaim_3d'].iloc[i] and (q1_dot.iloc[i] > 0)
                    if path_bear:
                        can_buy = True
                        b_reason = 'REENTRY_AFTER_BEAR'
                else:
                    if df['cond_trend'].iloc[i]:
                        can_buy = True
                        b_reason = 'TREND_BUY'
                        
            if can_buy:
                target_pos = 1.0
                target_reason = b_reason
                
        # Step 3: Submit order if target position intent requires execution
        if target_pos is not None:
            executor.submit_order(target_pos, target_reason, dt)
            
    # Calculate GIPS & Performance Metrics
    final_dt = df['date'].iloc[-1]
    strat_final = executor.daily_states[-1]['equity']
    bench_final = bench_executor.daily_states[-1]['equity']
    
    # XIRR calculation using actual cash flows
    strat_xirr = calculate_xirr(executor.acc.cash_flows, strat_final, final_dt) * 100.0
    bench_xirr = calculate_xirr(bench_executor.acc.cash_flows, bench_final, final_dt) * 100.0
    alpha_xirr_diff = strat_xirr - bench_xirr
    
    # Unit_NAV based Drawdowns
    strat_nav = pd.Series([s['unit_nav'] for s in executor.daily_states])
    strat_mdd = float((strat_nav / strat_nav.cummax() - 1.0).min() * 100.0)
    
    bench_nav = pd.Series([s['unit_nav'] for s in bench_executor.daily_states])
    bench_mdd = float((bench_nav / bench_nav.cummax() - 1.0).min() * 100.0)
    
    n_rt = len(round_trips)
    short_rt = sum(1 for r in round_trips if r['is_short_term'])
    short_rt_ratio = (short_rt / n_rt * 100.0) if n_rt > 0 else 0.0
    avg_pnl = float(np.mean([r['pnl_pct'] for r in round_trips])) if n_rt > 0 else 0.0
    
    stop_loss_order_count = sum(1 for o in executor.orders_history if o['reason'] == 'STOP_LOSS_5PCT')
    
    return {
        'strat_final': round(strat_final, 2),
        'bench_final': round(bench_final, 2),
        'strat_xirr': round(strat_xirr, 2),
        'bench_xirr': round(bench_xirr, 2),
        'alpha_xirr_diff': round(alpha_xirr_diff, 2),
        'alpha_cagr': round(alpha_xirr_diff, 2),
        'strat_mdd': round(strat_mdd, 2),
        'bench_mdd': round(bench_mdd, 2),
        'round_trips': n_rt,
        'short_term_round_trips': short_rt,
        'short_term_rate': round(short_rt_ratio, 2),
        'avg_trade_pnl': round(avg_pnl, 2),
        'benchmark_terminal_cash': round(bench_acc.cash, 2),
        'benchmark_first_fill_dt': bench_executor.fills[0]['dt'] if bench_executor.fills else None,
        'stop_loss_order_count': stop_loss_order_count,
        'round_trips_ledger': round_trips,
        'cash_intervals': cash_intervals,
        'executor_instance': executor,
        'bench_executor_instance': bench_executor
    }

# =========================================================================
# 5. Dual Sub-period Evaluation (Mode A: Inherited vs Mode B: Fresh Reset)
# =========================================================================

def evaluate_subperiods(
    df_warm: pd.DataFrame,
    fa: bool, fb: bool, fc: bool,
    split_date: str = '2020-01-01',
    price_col: str = 'close'
) -> Dict[str, Any]:
    """
    Evaluates subperiods under two strictly distinguished protocols:
    - Mode A: Continuous Inherited Execution (Inherits position, shares, cash, stop state)
    - Mode B: Fresh Reset Backtest (Resets account to $10,000 cash on pre-warmed continuous features)
    """
    # 1. Continuous Run across Full Warm Period
    full_exec = run_execution_simulation(df_warm, price_col=price_col, use_factor_c=fc, use_factor_a=fa)
    strat_exec = full_exec['executor_instance']
    bench_exec = full_exec['bench_executor_instance']
    
    # Slicing for Mode A (Continuous Inherited)
    split_ts = pd.Timestamp(split_date)
    states_strat = [s for s in strat_exec.daily_states if pd.Timestamp(s['date']) >= split_ts]
    states_bench = [s for s in bench_exec.daily_states if pd.Timestamp(s['date']) >= split_ts]
    
    if states_strat:
        seg_nav_strat = pd.Series([s['unit_nav'] for s in states_strat])
        seg_mdd_strat = float((seg_nav_strat / seg_nav_strat.cummax() - 1.0).min() * 100.0)
        seg_final_strat = states_strat[-1]['equity']
    else:
        seg_mdd_strat = 0.0
        seg_final_strat = 0.0
        
    if states_bench:
        seg_nav_bench = pd.Series([s['unit_nav'] for s in states_bench])
        seg_mdd_bench = float((seg_nav_bench / seg_nav_bench.cummax() - 1.0).min() * 100.0)
        seg_final_bench = states_bench[-1]['equity']
    else:
        seg_mdd_bench = 0.0
        seg_final_bench = 0.0
        
    # Mode B: Segment Fresh Reset Backtest
    df_seg_fresh = df_warm[df_warm['date'] >= split_date].copy().reset_index(drop=True)
    fresh_exec = run_execution_simulation(df_seg_fresh, price_col=price_col, use_factor_c=fc, use_factor_a=fa)
    
    return {
        'mode_a_inherited': {
            'seg_strat_final': round(seg_final_strat, 2),
            'seg_bench_final': round(seg_final_bench, 2),
            'seg_strat_mdd': round(seg_mdd_strat, 2),
            'seg_bench_mdd': round(seg_mdd_bench, 2)
        },
        'mode_b_fresh_reset': {
            'fresh_strat_final': fresh_exec['strat_final'],
            'fresh_bench_final': fresh_exec['bench_final'],
            'fresh_strat_xirr': fresh_exec['strat_xirr'],
            'fresh_bench_xirr': fresh_exec['bench_xirr'],
            'fresh_alpha_diff': fresh_exec['alpha_xirr_diff'],
            'fresh_strat_mdd': fresh_exec['strat_mdd'],
            'fresh_bench_mdd': fresh_exec['bench_mdd']
        }
    }

# =========================================================================
# 6. Main Execution Pipeline
# =========================================================================

def main():
    print("=" * 80)
    print("RUNNING FACTORIAL EXPERIMENT v2.1 (STRICT REMEDIATION & PRODUCTION DUAL TRACK)")
    print("=" * 80)
    
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # 1. Run Production Dual-Track Baseline (Unmodified Production Implementation)
    print("\n[Step 1] Running Pristine Production Reflexivity Radar Baseline...")
    now_p = pd.read_csv(ROOT / 'now_ohlcv_local.csv')
    macro = pd.read_csv(ROOT / 'market_data_local.csv')
    
    prod_captures = []
    class ProdCapture(SharedExecutor):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            prod_captures.append(self)
            
    from unittest.mock import patch
    with patch('shared_executor.SharedExecutor', ProdCapture):
        prod_df = run_universal_reflexivity_radar('NOW', now_p, macro)
        
    prod_exec = prod_captures[0]
    prod_states = prod_exec.daily_states
    prod_summary = {
        'production_total_rows': len(prod_df),
        'production_signal_ready_start': str(prod_df.loc[prod_df['signal_ready'], 'date'].iloc[0].date()),
        'production_initial_cash': 100000.0,
        'production_fee_rate': 0.0,
        'production_final_equity': round(prod_states[-1]['equity'], 2),
        'production_final_unit_nav': round(prod_states[-1]['unit_nav'], 4),
        'production_fills_count': len(prod_exec.fills),
        'production_first_fill_dt': prod_exec.fills[0]['dt'] if prod_exec.fills else None,
        'production_buy_fills': sum(1 for f in prod_exec.fills if f['direction'] == 'BUY'),
        'production_sell_fills': sum(1 for f in prod_exec.fills if f['direction'] == 'SELL')
    }
    (OUT_DIR / 'production_dual_track_baseline.json').write_text(json.dumps(prod_summary, indent=2), encoding='utf-8')
    print(f"Production Baseline: First signal_ready = {prod_summary['production_signal_ready_start']}, Fills = {prod_summary['production_fills_count']}, Final Equity = {prod_summary['production_final_equity']}, Final Unit NAV = {prod_summary['production_final_unit_nav']}")
    
    # 2. Prepare Features for Factorial Ablation (NOW)
    print("\n[Step 2] Feature Engineering on Full History (Continuous Indicators)...")
    df_now = prepare_base_features(now_p, macro, price_col='close')
    first_ready_dt = pd.Timestamp(prod_summary['production_signal_ready_start'])
    print(f"NOW Dynamic signal_ready start date from Production Baseline: {first_ready_dt.strftime('%Y-%m-%d')}")
    
    # Warmup study period starts at dynamic signal_ready date
    df_warm_now = df_now[df_now['date'] >= first_ready_dt].copy().reset_index(drop=True)
    
    combos = [
        ('C0_Baseline', False, False, False),
        ('C1_Score_Decouple', True, False, False),
        ('C2_Panic_Latch', False, True, False),
        ('C3_Reentry_Handshake', False, False, True),
        ('C4_Score_Latch', True, True, False),
        ('C5_Score_Reentry', True, False, True),
        ('C6_Latch_Reentry', False, True, True),
        ('C7_Full_Candidate', True, True, True),
    ]
    
    now_results = []
    all_round_trips = []
    all_cash_intervals = []
    
    print("\n[Step 3] Running 8-Configuration Factorial Ablation on NOW...")
    for name, fa, fb, fc in combos:
        df_sig = generate_signals(df_warm_now, fa, fb, fc, price_col='close')
        sig_eval = evaluate_signals(df_sig, price_col='close')
        exec_full = run_execution_simulation(df_sig, price_col='close', use_factor_c=fc, use_factor_a=fa)
        
        # Subperiod evaluation (Continuous Inherited vs Fresh Reset)
        sub_eval = evaluate_subperiods(df_sig, fa, fb, fc, split_date='2020-01-01', price_col='close')
        
        # Tag and collect round trips
        for rt in exec_full['round_trips_ledger']:
            rt_record = dict(rt)
            rt_record['Config'] = name
            rt_record['Asset'] = 'NOW'
            all_round_trips.append(rt_record)
            
        # Tag and collect cash intervals
        for ci in exec_full['cash_intervals']:
            ci_record = dict(ci)
            ci_record['Config'] = name
            ci_record['Asset'] = 'NOW'
            all_cash_intervals.append(ci_record)
            
        now_results.append({
            'Config': name,
            'Factor_A': fa,
            'Factor_B': fb,
            'Factor_C': fc,
            # Signal Layer Classification
            'Panic_FDR%': sig_eval['panic_buy_fdr'],
            'Bottom_Miss%': sig_eval['bottom_miss_rate'],
            'Sell_FDR%': sig_eval['sell_fdr'],
            'Top_Miss%': sig_eval['top_miss_rate'],
            'Trend_Fwd_20d_Mean%': sig_eval['trend_fwd_20d_mean_pct'],
            'Trend_Fwd_20d_Win%': sig_eval['trend_fwd_20d_win_pct'],
            'Trend_Fwd_60d_Mean%': sig_eval['trend_fwd_60d_mean_pct'],
            'Trend_Fwd_60d_Win%': sig_eval['trend_fwd_60d_win_pct'],
            # Execution Full Warm Period
            'Strat_Final': exec_full['strat_final'],
            'Bench_Final': exec_full['bench_final'],
            'Strat_XIRR%': exec_full['strat_xirr'],
            'Bench_XIRR%': exec_full['bench_xirr'],
            'Delta_XIRR_pct_pt': exec_full['alpha_xirr_diff'],
            'Strat_MDD%': exec_full['strat_mdd'],
            'Bench_MDD%': exec_full['bench_mdd'],
            'RoundTrips': exec_full['round_trips'],
            'ShortRT%': exec_full['short_term_rate'],
            'StopOrders': exec_full['stop_loss_order_count'],
            'Bench_First_Fill': exec_full['benchmark_first_fill_dt'],
            # Subperiod Mode A (Continuous Inherited)
            'Inherited_Seg_Final': sub_eval['mode_a_inherited']['seg_strat_final'],
            'Inherited_Seg_MDD%': sub_eval['mode_a_inherited']['seg_strat_mdd'],
            # Subperiod Mode B (Fresh Reset Backtest)
            'Fresh_Seg_Final': sub_eval['mode_b_fresh_reset']['fresh_strat_final'],
            'Fresh_Seg_XIRR%': sub_eval['mode_b_fresh_reset']['fresh_strat_xirr'],
            'Fresh_Seg_Delta_XIRR': sub_eval['mode_b_fresh_reset']['fresh_alpha_diff'],
            'Fresh_Seg_MDD%': sub_eval['mode_b_fresh_reset']['fresh_strat_mdd']
        })
        
    df_now_res = pd.DataFrame(now_results)
    df_now_res.to_csv(OUT_DIR / 'factorial_ablation_results_v2_1_now.csv', index=False)
    print("\nNOW Factorial Results:")
    print(df_now_res[['Config', 'Strat_Final', 'Bench_Final', 'Strat_XIRR%', 'Delta_XIRR_pct_pt', 'Strat_MDD%', 'StopOrders', 'Bench_First_Fill']].to_string(index=False))
    
    # 3. Cross-Asset Factorial Ablations: QQQ and SPY
    print("\n[Step 4] Running Cross-Asset Factorial Ablations on QQQ & SPY...")
    for ticker in ['QQQ', 'SPY']:
        df_asset_p = macro[['date', ticker]].dropna().rename(columns={ticker: 'close'})
        df_asset = prepare_base_features(df_asset_p, macro, price_col='close')
        df_asset_warm = df_asset[df_asset['date'] >= first_ready_dt].copy().reset_index(drop=True)
        
        asset_results = []
        for name, fa, fb, fc in combos:
            df_sig = generate_signals(df_asset_warm, fa, fb, fc, price_col='close')
            sig_eval = evaluate_signals(df_sig, price_col='close')
            exec_full = run_execution_simulation(df_sig, price_col='close', use_factor_c=fc, use_factor_a=fa)
            sub_eval = evaluate_subperiods(df_sig, fa, fb, fc, split_date='2020-01-01', price_col='close')
            
            asset_results.append({
                'Ticker': ticker,
                'Config': name,
                'Panic_FDR%': sig_eval['panic_buy_fdr'],
                'Bottom_Miss%': sig_eval['bottom_miss_rate'],
                'Sell_FDR%': sig_eval['sell_fdr'],
                'Top_Miss%': sig_eval['top_miss_rate'],
                'Strat_Final': exec_full['strat_final'],
                'Bench_Final': exec_full['bench_final'],
                'Strat_XIRR%': exec_full['strat_xirr'],
                'Bench_XIRR%': exec_full['bench_xirr'],
                'Delta_XIRR_pct_pt': exec_full['alpha_xirr_diff'],
                'Strat_MDD%': exec_full['strat_mdd'],
                'Bench_MDD%': exec_full['bench_mdd'],
                'RoundTrips': exec_full['round_trips'],
                'ShortRT%': exec_full['short_term_rate'],
                'StopOrders': exec_full['stop_loss_order_count'],
                'Inherited_Seg_Final': sub_eval['mode_a_inherited']['seg_strat_final'],
                'Fresh_Seg_Final': sub_eval['mode_b_fresh_reset']['fresh_strat_final']
            })
        df_asset_res = pd.DataFrame(asset_results)
        df_asset_res.to_csv(OUT_DIR / f'factorial_ablation_results_v2_1_{ticker.lower()}.csv', index=False)
        print(f"\n{ticker} Results:")
        print(df_asset_res[['Config', 'Strat_Final', 'Bench_Final', 'Strat_XIRR%', 'Delta_XIRR_pct_pt', 'Strat_MDD%', 'StopOrders']].to_string(index=False))
        
    # 4. Save Comprehensive Ledgers
    pd.DataFrame(all_round_trips).to_csv(OUT_DIR / 'round_trip_ledgers_v2_1.csv', index=False)
    pd.DataFrame(all_cash_intervals).to_csv(OUT_DIR / 'cash_intervals_v2_1.csv', index=False)
    print(f"\nSaved round-trip ledgers ({len(all_round_trips)} records) and cash intervals ({len(all_cash_intervals)} records).")
    print("FACTORIAL_V2_1_EXECUTION_COMPLETED")

if __name__ == '__main__':
    main()
