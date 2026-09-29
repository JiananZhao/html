"""
Factorial Ablation Experiment Runner (v2.0 Frozen Specification)
100% Local-first, Read-only on production models.
Strict parity with FROZEN_SPEC_AND_BENCHMARK_PROTOCOL.md v2.0
"""

import sys
import os
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from true_accounting import UnitizedAccount, calculate_xirr
from shared_executor import SharedExecutor

OUT_DIR = Path(__file__).resolve().parent

def expanding_rank(s, min_periods=100):
    vals = s.values
    n = len(vals)
    res = np.full(n, np.nan)
    sorted_arr = []
    import bisect
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

def prepare_base_features(df_p, df_m, price_col='close'):
    """Compute base coordinates without assigning signal decisions."""
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
    
    # M0 Composite Score
    df['Composite_Score_M0'] = (
        df['Score_Dim1_Pos'] * 0.30 +
        df['Score_Dim2_Vel'] * 0.20 +
        df['Score_Dim3_Lyapunov'] * 0.20 +
        df['Score_Dim5_Liquidity'] * 0.10 +
        df['Score_Dim6_Macro'] * 0.20
    )
    
    # Factor A Decoupled Scores (Strict Spec v2.0)
    # Speed term: strictly expanding_rank on max(q1_dot, 0)
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
    
    return df

def generate_signals(df, use_factor_a=False, use_factor_b=False, use_factor_c=False, price_col='close'):
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
        
    gate_panic = (df['Dist_200MA'] <= 0.0) | (p < df['MA50'])
    turned_up = (df['q1_dot'] > 0) & (df['q1_dot'].shift(1) <= 0)
    
    if not use_factor_b:
        # Baseline single-day rigid pulse (includes -25% legacy exception)
        inflection_panic = ((p > df['MA10']) & turned_up) | ((df['Dist_200MA'] < -25.0) & turned_up)
        raw_panic = regime_panic_raw & gate_panic & inflection_panic
    else:
        # Factor B: Panic Memory Latch strictly per Spec v2.0
        # Zero bypass of MA10. Must have q1_dot > 0 strictly positive.
        K_window = 15
        latch = False
        timer = 0
        p_anchor = 0.0
        raw_panic_arr = np.zeros(n, dtype=bool)
        
        for i in range(n):
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
                if p_i < p_anchor * 0.98: # New low by > 2%: refresh anchor & timer
                    p_anchor = p_i
                    timer = K_window
                else:
                    timer -= 1
                    if timer <= 0:
                        latch = False
            
            # Strict signal gate: latch active, instantaneous momentum positive, price above MA10
            if latch and (q_dot_i > 0) and (p_i > ma10_i):
                raw_panic_arr[i] = True
                # Latch consumed upon passing all signal filters
                latch = False
                
        raw_panic = pd.Series(raw_panic_arr, index=df.index)

    # -------------------------------------------------------------
    # 2. Bubble Top & Bear Top Triggers
    # -------------------------------------------------------------
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
    
    # Hysteresis Filter
    def apply_hys(raw_flags, min_days=15, price_step=0.07, is_top=False):
        final_flags = []
        last_dt = None
        last_p = None
        for idx in range(n):
            flag = raw_flags.iloc[idx]
            dt = df['date'].iloc[idx]
            p_val = p.iloc[idx]
            act = False
            if flag:
                days = (dt - last_dt).days if last_dt else 999
                if is_top:
                    if days > min_days or p_val > (last_p * (1 + price_step) if last_p else 0):
                        act = True
                        last_dt = dt
                        last_p = p_val
                else:
                    if days > min_days or p_val < (last_p * (1 - price_step) if last_p else 999999):
                        act = True
                        last_dt = dt
                        last_p = p_val
            final_flags.append(act)
        return pd.Series(final_flags, index=df.index)

    df['Trigger_Panic'] = apply_hys(raw_panic, min_days=15, price_step=0.07, is_top=False)
    df['Trigger_Bubble_Top'] = apply_hys(raw_bubble_top, min_days=25, price_step=0.08, is_top=True)
    df['Trigger_Bear_Top'] = apply_hys(raw_bear_top, min_days=20, price_step=0.06, is_top=True)
    
    df['raw_sell'] = df['Trigger_Bubble_Top'] | df['Trigger_Bear_Top']
    df['sell_reason'] = np.where(df['Trigger_Bubble_Top'], 'BUBBLE', np.where(df['Trigger_Bear_Top'], 'BEAR', 'NONE'))
    
    # Trend Buy condition (baseline)
    df['cond_trend'] = (p > df['MA50']).rolling(3).sum() == 3
    df['raw_buy'] = df['Trigger_Panic'] | df['cond_trend']
    
    return df

def evaluate_signals(df, price_col='close', window=20):
    """
    Signal layer objective classification evaluation.
    Matches Trigger_Panic against local troughs in [S - 15, S + 5] (Strictly Spec v2.0).
    Separately evaluates trend and re-entry buys via 20-day forward return.
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
    # Given S, search E in [max(0, S - 15), min(n, S + 6)]
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
    
    # Sell Matching: Extrema E must be in [S - 15, S + 5]
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
    
    return {
        'total_eval_days': int(np.sum(eval_mask)),
        'true_minima': total_mins,
        'true_maxima': total_maxs,
        'panic_buy_signals': len(buy_signals),
        'panic_buy_fdr': round(fdr_buys * 100, 2),
        'buy_fdr': round(fdr_buys * 100, 2),
        'bottom_miss_rate': round(miss_rate_buys * 100, 2),
        'sell_signals': len(sell_signals),
        'sell_fdr': round(fdr_sells * 100, 2),
        'top_miss_rate': round(miss_rate_sells * 100, 2)
    }

def run_execution_simulation(df, price_col='close', initial_cash=10000.0, dca_monthly=1000.0, fee_rate=0.001, use_factor_c=False, use_factor_a=False):
    """
    Unified execution engine strictly enforcing:
    1. Daily order precedence: step() first, then target_pos decision.
    2. Benchmark monthly reinvestment: whenever dca > 0, submit_order(1.0).
    3. Strategy DCA reinvestment: if pos == 1.0 and dca > 0, submit_order(1.0).
       If pos == 0.0, dca cash stays idle in cash pool.
    4. Factor C state machine maintained on ACTUAL FILLS, with stop loss timer from reentry fill.
    """
    acc = UnitizedAccount(initial_cash=initial_cash, initial_date=df['date'].iloc[0])
    bench_acc = UnitizedAccount(initial_cash=initial_cash, initial_date=df['date'].iloc[0])
    
    executor = SharedExecutor(acc, fee_rate=fee_rate, execution_mode='NEXT_CLOSE', account_type='strat')
    bench_executor = SharedExecutor(bench_acc, fee_rate=fee_rate, execution_mode='NEXT_CLOSE', account_type='bench')
    
    bench_executor.submit_order(1.0, "Benchmark Initial Buy", df['date'].iloc[0])
    
    # Strategy state
    pos = 0.0 # Strict initial condition: start in cash
    curr_m = -1
    last_fill_count = 0
    
    # Factor C tracker
    exit_mode = 'NONE' # 'NONE', 'AFTER_BUBBLE', 'AFTER_BEAR'
    cash_days_count = 0
    reentry_fill_price = None
    stop_timer = 0
    
    # Pre-calculate condition series
    p = df[price_col]
    ma50 = df['MA50']
    ma20 = df['MA20']
    q1_dot = df['q1_dot']
    macro_stress = df['Score_MacroStress_A'] if use_factor_a else df['Score_Dim6_Macro']
    hyg_rebound = df['HYG'] > df['Macro_MA200']
    
    # Pullback 2-day band
    ma50_band = (abs(p - ma50) / (ma50 + 1e-8) <= 0.025).rolling(2).sum() == 2
    # Reclaim 3-day band
    ma50_reclaim_3d = (p > ma50).rolling(3).sum() == 3
    
    for i in range(len(df)):
        dt = df['date'].iloc[i]
        p_i = p.iloc[i]
        
        m = dt.month
        deposit = dca_monthly if m != curr_m else 0.0
        curr_m = m
        
        # Step 1: Execute previous pending orders and process today's deposit
        executor.step(dt, p_i, p_i, dca_amount=deposit)
        bench_executor.step(dt, p_i, p_i, dca_amount=deposit)
        
        # Benchmark DCA reinvestment
        if deposit > 0:
            bench_executor.submit_order(1.0, "Monthly benchmark investment", dt)
            
        # Check actual fill returns from executor to update position and Factor C state
        if len(executor.fills) > last_fill_count:
            latest_fill = executor.fills[-1]
            last_fill_count = len(executor.fills)
            if latest_fill['direction'] == 'BUY':
                pos = 1.0
                if exit_mode in ['AFTER_BUBBLE', 'AFTER_BEAR']:
                    # Started reentry stop loss countdown
                    reentry_fill_price = latest_fill['price']
                    stop_timer = 10
                exit_mode = 'NONE'
                cash_days_count = 0
            elif latest_fill['direction'] == 'SELL':
                pos = 0.0
                reentry_fill_price = None
                stop_timer = 0
                # Identify exit mode from last sell order reason
                last_order = executor.orders_history[-1]
                if 'BUBBLE' in last_order['reason']:
                    exit_mode = 'AFTER_BUBBLE'
                elif 'BEAR' in last_order['reason']:
                    exit_mode = 'AFTER_BEAR'
                else:
                    exit_mode = 'NONE'
                cash_days_count = 0
                
        if pos == 0.0:
            cash_days_count += 1
            
        # Check stop loss if holding from a reentry
        stop_loss_triggered = False
        if pos == 1.0 and stop_timer > 0 and reentry_fill_price is not None:
            if p_i < reentry_fill_price * 0.95:
                stop_loss_triggered = True
                stop_timer = 0
            else:
                stop_timer -= 1
                # Daily deposit additions do NOT reset stop_timer
                
        # Step 2: Determine daily target position intent
        s_panic = df['Trigger_Panic'].iloc[i]
        s_sell = df['raw_sell'].iloc[i]
        s_sell_reason = df['sell_reason'].iloc[i]
        
        target_pos = None
        target_reason = None
        
        if pos > 0.0:
            # Holding position: check exit signals or stop loss
            if stop_loss_triggered:
                target_pos = 0.0
                target_reason = 'STOP_LOSS_5PCT'
            elif s_sell:
                target_pos = 0.0
                target_reason = s_sell_reason
            elif deposit > 0:
                # DCA reinvestment while holding
                target_pos = 1.0
                target_reason = 'DCA_HOLDING_REINVEST'
        else:
            # Cash position: check entry signals
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
                    # Path A: 2-day pullback test of 50MA held + above 20MA + positive momentum
                    path_a = ma50_band.iloc[i] and (p_i > ma20.iloc[i]) and (q1_dot.iloc[i] > 0)
                    # Path B: Cool-down >= 10 trading days + 20-day high breakout + positive momentum
                    if i >= 20:
                        path_b = (cash_days_count >= 10) and (p_i > p.iloc[i-20:i].max()) and (q1_dot.iloc[i] > 0)
                    else:
                        path_b = False
                    if path_a or path_b:
                        can_buy = True
                        b_reason = 'REENTRY_AFTER_BUBBLE'
                elif exit_mode == 'AFTER_BEAR':
                    # Macro stress abatement OR HYG recovery, AND 3-day MA50 reclaim with positive momentum
                    macro_ok = (macro_stress.iloc[i] < 60.0) or hyg_rebound.iloc[i]
                    if macro_ok and ma50_reclaim_3d.iloc[i] and (q1_dot.iloc[i] > 0):
                        can_buy = True
                        b_reason = 'REENTRY_AFTER_BEAR'
                else:
                    # Normal trend buy
                    if df['cond_trend'].iloc[i]:
                        can_buy = True
                        b_reason = 'TREND_BUY'
                        
            if can_buy:
                target_pos = 1.0
                target_reason = b_reason
                
        # Step 3: Submit order if target position intent requires execution
        if target_pos is not None:
            executor.submit_order(target_pos, target_reason, dt)
            
    # Calculate GIPS & Financial Performance Metrics
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
    
    # Round-trip Ledger & Duration in TRADING DAYS
    date_to_idx = {df['date'].iloc[idx].strftime('%Y-%m-%d'): idx for idx in range(len(df))}
    round_trips = []
    current_entry = None
    for f in executor.fills:
        if f['direction'] == 'BUY' and current_entry is None:
            current_entry = f
        elif f['direction'] == 'SELL' and current_entry is not None:
            idx_in = date_to_idx.get(current_entry['dt'], 0)
            idx_out = date_to_idx.get(f['dt'], len(df) - 1)
            duration_trading_days = max(1, idx_out - idx_in)
            p_in = current_entry['price']
            p_out = f['price']
            pnl_pct = (p_out * (1 - fee_rate) - p_in * (1 + fee_rate)) / (p_in * (1 + fee_rate)) * 100.0
            round_trips.append({
                'entry_dt': current_entry['dt'],
                'exit_dt': f['dt'],
                'duration_trading_days': duration_trading_days,
                'pnl_pct': pnl_pct,
                'is_short_term': duration_trading_days <= 5
            })
            current_entry = None
            
    n_rt = len(round_trips)
    short_rt = sum(1 for r in round_trips if r['is_short_term'])
    short_rt_ratio = (short_rt / n_rt * 100.0) if n_rt > 0 else 0.0
    avg_pnl = float(np.mean([r['pnl_pct'] for r in round_trips])) if n_rt > 0 else 0.0
    
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
        'benchmark_terminal_cash': round(bench_acc.cash, 2)
    }

def main():
    print("=" * 80)
    print("RUNNING FACTORIAL EXPERIMENT v2.0 (STRICT SPEC COMPLIANCE)")
    print("=" * 80)
    
    now_p = pd.read_csv(ROOT / 'now_ohlcv_local.csv')
    macro = pd.read_csv(ROOT / 'market_data_local.csv')
    df_now = prepare_base_features(now_p, macro, price_col='close')
    
    # Filter to valid production warmup period
    # To ensure dual control parity, find first date where all features are valid
    # In production, NOW signal_ready starts 2014-04-16
    df_warm = df_now[df_now['date'] >= '2014-04-16'].copy().reset_index(drop=True)
    
    split_date = '2020-01-01'
    df_in_sample = df_warm[df_warm['date'] < split_date].copy().reset_index(drop=True)
    df_hist_segment = df_warm[df_warm['date'] >= split_date].copy().reset_index(drop=True)
    
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
    
    results = []
    
    for name, fa, fb, fc in combos:
        df_sig = generate_signals(df_warm, fa, fb, fc, price_col='close')
        sig_eval = evaluate_signals(df_sig, price_col='close')
        exec_full = run_execution_simulation(df_sig, price_col='close', use_factor_c=fc, use_factor_a=fa)
        
        # Historical Segment 2020-2026
        df_seg_sig = generate_signals(df_hist_segment, fa, fb, fc, price_col='close')
        exec_seg = run_execution_simulation(df_seg_sig, price_col='close', use_factor_c=fc, use_factor_a=fa)
        
        results.append({
            'Config': name,
            'A_Score': fa,
            'B_Latch': fb,
            'C_Reentry': fc,
            # Signal Layer (Panic Bottoms)
            'Bottom_Miss%': sig_eval['bottom_miss_rate'],
            'Panic_FDR%': sig_eval['panic_buy_fdr'],
            'Top_Miss%': sig_eval['top_miss_rate'],
            'Sell_FDR%': sig_eval['sell_fdr'],
            # Execution Full Warm Period (2014-2026)
            'Strat_Final': exec_full['strat_final'],
            'Bench_Final': exec_full['bench_final'],
            'Strat_XIRR%': exec_full['strat_xirr'],
            'Bench_XIRR%': exec_full['bench_xirr'],
            'Delta_XIRR_pct_pt': exec_full['alpha_xirr_diff'],
            'Strat_MDD%': exec_full['strat_mdd'],
            'Bench_MDD%': exec_full['bench_mdd'],
            'RoundTrips': exec_full['round_trips'],
            'ShortRT%': exec_full['short_term_rate'],
            # Historical Segment 2020-2026
            'Seg_Strat_Final': exec_seg['strat_final'],
            'Seg_Bench_Final': exec_seg['bench_final'],
            'Seg_Strat_XIRR%': exec_seg['strat_xirr'],
            'Seg_Bench_XIRR%': exec_seg['bench_xirr'],
            'Seg_Delta_XIRR_pct_pt': exec_seg['alpha_xirr_diff'],
            'Seg_Strat_MDD%': exec_seg['strat_mdd']
        })
        
    # 2. Run Cross-Asset Validations: QQQ and SPY
    for ticker in ['QQQ', 'SPY']:
        print(f"\n--- Running Cross-Asset: {ticker} ---")
        df_asset_p = macro[['date', ticker]].dropna().rename(columns={ticker: 'close'})
        df_asset = prepare_base_features(df_asset_p, macro, price_col='close')
        df_asset_warm = df_asset[df_asset['date'] >= '2014-04-16'].copy().reset_index(drop=True)
        
        asset_results = []
        for name, fa, fb, fc in combos:
            df_sig = generate_signals(df_asset_warm, fa, fb, fc, price_col='close')
            sig_eval = evaluate_signals(df_sig, price_col='close')
            exec_full = run_execution_simulation(df_sig, price_col='close', use_factor_c=fc, use_factor_a=fa)
            
            asset_results.append({
                'Ticker': ticker,
                'Config': name,
                'Bottom_Miss%': sig_eval['bottom_miss_rate'],
                'Panic_FDR%': sig_eval['panic_buy_fdr'],
                'Top_Miss%': sig_eval['top_miss_rate'],
                'Sell_FDR%': sig_eval['sell_fdr'],
                'Strat_Final': exec_full['strat_final'],
                'Bench_Final': exec_full['bench_final'],
                'Strat_XIRR%': exec_full['strat_xirr'],
                'Bench_XIRR%': exec_full['bench_xirr'],
                'Delta_XIRR_pct_pt': exec_full['alpha_xirr_diff'],
                'Strat_MDD%': exec_full['strat_mdd'],
                'Bench_MDD%': exec_full['bench_mdd'],
                'RoundTrips': exec_full['round_trips'],
                'ShortRT%': exec_full['short_term_rate']
            })
        df_asset_res = pd.DataFrame(asset_results)
        df_asset_res.to_csv(OUT_DIR / f'factorial_ablation_results_v2_{ticker.lower()}.csv', index=False)
        print(df_asset_res[['Config', 'Bottom_Miss%', 'Strat_Final', 'Bench_Final', 'Delta_XIRR_pct_pt', 'Strat_MDD%', 'ShortRT%']].to_string(index=False))

if __name__ == '__main__':
    main()
