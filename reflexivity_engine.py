import numpy as np
import pandas as pd
import bisect
import warnings

warnings.filterwarnings('ignore')

def run_universal_reflexivity_radar(ticker: str, df_price: pd.DataFrame, df_macro: pd.DataFrame) -> pd.DataFrame:
    """
    通用反身性相空间动力学数学引擎 (Universal Reflexivity Dynamics Engine)
    
    参数:
    - ticker: 标的代码 (如 'NVDA')
    - df_price: 包含 date, open, high, low, close, volume 的日线数据
    - df_macro: 包含 date, SPY, HYG, BAA10Y, NFCI, Real_Yield 的宏观数据
    
    返回:
    - 带有所有技术指标、相空间导数、4象限信号、综合得分及回测对账数据的 DataFrame
    """
    
    # 1. 数据对齐与预处理
    df_price = df_price.copy()
    df_macro = df_macro.copy()
    
    # 确保日期格式一致且无时区
    df_price['date'] = pd.to_datetime(df_price['date']).dt.tz_localize(None)
    df_macro['date'] = pd.to_datetime(df_macro['date']).dt.tz_localize(None)
    
    # 使用 left merge 保留所有交易日，并前向填充宏观数据（最多5天），解决个股数据被陈旧宏观数据截断的问题
    df = pd.merge(df_price, df_macro[['date', 'HYG', 'BAA10Y', 'NFCI', 'Real_Yield']], on='date', how='left')
    df = df.sort_values('date').reset_index(drop=True)
    
    # 前向填充最新几天的缺失宏观数据
    macro_cols = ['HYG', 'BAA10Y', 'NFCI', 'Real_Yield']
    df[macro_cols] = df[macro_cols].ffill(limit=5)
    
    # 剔除完全没有宏观数据的早期历史
    df = df.dropna(subset=macro_cols).reset_index(drop=True)
    
    if len(df) < 252:
        # 数据过少，直接返回原数据
        return df

    # =========================================================================
    # 第一步：基础技术指标与均线网络
    # =========================================================================
    df['MA10'] = df['close'].rolling(10).mean()
    df['MA20'] = df['close'].rolling(20).mean()
    df['MA50'] = df['close'].rolling(50).mean()
    df['MA200'] = df['close'].rolling(200).mean()
    df['Dist_50MA'] = (df['close'] - df['MA50']) / (df['MA50'] + 1e-8) * 100.0
    df['Dist_200MA'] = (df['close'] - df['MA200']) / (df['MA200'] + 1e-8) * 100.0
    df['MA200_Slope'] = (df['MA200'] - df['MA200'].shift(10)) / (df['MA200'].shift(10) + 1e-8) * 100.0

    # =========================================================================
    # 第二步：宏观信用环境与流动性状态
    # =========================================================================
    df['Macro_MA50'] = df['HYG'].rolling(50).mean()
    df['Macro_MA200'] = df['HYG'].rolling(200).mean()
    df['BAA_MA60'] = df['BAA10Y'].rolling(60).mean()
    df['BAA_Stress'] = df['BAA10Y'] > df['BAA_MA60']
    df['RY_Surge'] = (df['Real_Yield'] - df['Real_Yield'].rolling(60).min()) > 0.35

    # =========================================================================
    # 第三步：反身性认知偏差（Reflexive Gap）
    # =========================================================================
    df['Price_Z'] = (df['close'] - df['MA200']) / (df['close'].rolling(200).std() + 1e-8)
    df['Macro_Z'] = (df['HYG'] - df['Macro_MA200']) / (df['HYG'].rolling(200).std() + 1e-8)
    roll_cov = df['Price_Z'].rolling(252).cov(df['Macro_Z'])
    roll_var = df['Macro_Z'].rolling(252).var()
    df['Dynamic_Beta'] = (roll_cov / (roll_var + 1e-8)).clip(lower=-2.0, upper=2.0)
    df['Expected_Price_Z'] = df['Macro_Z'] * df['Dynamic_Beta']
    df['Gap'] = df['Price_Z'] - df['Expected_Price_Z']
    df['Gap_Max_45'] = df['Gap'].rolling(45, min_periods=1).max()
    df['Gap_Upper'] = df['Gap'].expanding(min_periods=50).quantile(0.85)

    # =========================================================================
    # 第四步：拉格朗日相空间动力学 (q, q_dot, q_ddot, V_dot)
    # =========================================================================
    # 状态位置 q1: 年线相对偏离度 (%)
    df['q1'] = df['Dist_200MA']
    # 广义速度 q1_dot: 10 天低通后向有限差分 (%/day)
    df['q1_dot'] = (df['q1'] - df['q1'].shift(10)) / 10.0
    # 广义加速度 q1_ddot: 5 天二阶有限差分 (%/day^2)
    df['q1_ddot'] = (df['q1_dot'] - df['q1_dot'].shift(5)) / 5.0
    # 相空间能量变化率代理指标: V_dot = q1_dot * (q1 + tau * q1_ddot)
    tau = 100.0
    df['v_dot'] = df['q1_dot'] * (df['q1'] + tau * df['q1_ddot'])

    # 相平面四象限动力学粗扫
    df['Quadrant'] = 0
    df.loc[(df['q1'] >= 0) & (df['q1_dot'] >= 0), 'Quadrant'] = 1
    df.loc[(df['q1'] < 0) & (df['q1_dot'] >= 0), 'Quadrant'] = 2
    df.loc[(df['q1'] < 0) & (df['q1_dot'] < 0), 'Quadrant'] = 3
    df.loc[(df['q1'] >= 0) & (df['q1_dot'] < 0), 'Quadrant'] = 4

    # =========================================================================
    # 第五步：微观资金流向 (CMF) 与换手率异常
    # =========================================================================
    high_low_range = df['high'] - df['low']
    high_low_range = high_low_range.replace(0, np.nan)
    clv = (2 * df['close'] - (df['high'] + df['low'])) / high_low_range
    clv = clv.fillna(0.0)
    vol_clv = clv * df['volume']
    df['CMF20'] = vol_clv.rolling(20).sum() / (df['volume'].rolling(20).sum() + 1e-8)
    df['Vol_Ratio50'] = df['volume'] / (df['volume'].rolling(50).mean() + 1e-8)

    # =========================================================================
    # 第六步：无量纲分位数标定 (Expanding Percentile 0~100)
    # =========================================================================
    def expanding_rank(s, min_periods=100):
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

    df['Score_Dim1_Pos'] = expanding_rank(df['q1'])
    df['Score_Dim2_Vel'] = expanding_rank(df['q1_dot'])
    df['Score_Dim3_Lyapunov'] = expanding_rank(df['v_dot'])
    # 剥离专用内部人交易 (Score_Dim4_Capital 权重置0)，此处全设为 50中性
    df['Score_Dim4_Capital'] = 50.0 
    df['Score_Dim5_Liquidity'] = (expanding_rank(df['CMF20']) * 0.6 + expanding_rank(df['Vol_Ratio50']) * 0.4)
    df['Score_Dim6_Macro'] = (expanding_rank(df['BAA10Y']) * 0.5 + expanding_rank(df['NFCI']) * 0.5)

    # 重新分配权重 (总和=1.0)
    # Pos: 0.30, Vel: 0.20, Lyapunov: 0.20, Liquidity: 0.10, Macro: 0.20
    df['Composite_Score'] = (
        df['Score_Dim1_Pos'] * 0.30 +
        df['Score_Dim2_Vel'] * 0.20 +
        df['Score_Dim3_Lyapunov'] * 0.20 +
        df['Score_Dim5_Liquidity'] * 0.10 +
        df['Score_Dim6_Macro'] * 0.20
    )

    # =========================================================================
    # 第七步：四象限高信噪比观测信号 (Strict Regime Gating)
    # =========================================================================
    
    # 象限 I: 极度恐慌底 (Panic Crash Bottom)
    regime_panic = (df['Dist_200MA'].rolling(20).min() < -15.0) | (df['Dist_200MA'] < -10.0) | (df['Composite_Score'] < 32.0)
    gate_panic = (df['Dist_200MA'] <= 0.0) | (df['close'] < df['MA50'])
    inflection_panic = ((df['close'] > df['MA10']) & (df['q1_dot'] > 0) & (df['q1_dot'].shift(1) <= 0)) | ((df['Dist_200MA'] < -25.0) & (df['q1_dot'] > 0) & (df['q1_dot'].shift(1) <= 0))
    raw_panic = regime_panic & gate_panic & inflection_panic

    # 宏观危机过滤
    macro_crisis_regime = (df['HYG'] < df['Macro_MA200']) & ((df['NFCI'] > -0.40) | df['RY_Surge'])

    # 象限 II: 阶段蓄势底 (Stage Consolidation Bottom)
    not_rebounding_from_crash = df['Dist_200MA'].rolling(90).min() >= -12.0
    bull_structure = (df['MA200_Slope'] >= -0.05) & (df['MA50'] >= df['MA200'] * 0.96) & (~macro_crisis_regime) & not_rebounding_from_crash
    equilibrium_test = ((df['Dist_200MA'] >= -12.0) & (df['Dist_200MA'] <= 8.0)) | ((df['Dist_50MA'].abs() <= 3.5) & (df['Dist_200MA'] <= 10.0))
    cool_score = (df['Composite_Score'].rolling(10).min() <= 50.0) | (df['Composite_Score'] <= 60.0)
    inflection_stage = (df['close'] > df['MA10']) & (df['q1_dot'] > 0) & (df['q1_dot'].shift(1) <= 0)
    raw_stage = bull_structure & equilibrium_test & cool_score & inflection_stage & (~raw_panic)

    # 象限 III: 极度泡沫顶 (Bull Bubble Climax Top)
    regime_bubble_top = (df['Composite_Score'] >= 70.0) | (df['Dist_200MA'] > 22.0)
    gate_bubble_top = (df['Dist_200MA'] >= 10.0) & (df['q1'] >= 0) & not_rebounding_from_crash
    inflection_bubble_top = (df['Quadrant'] == 4) & (df['Quadrant'].shift(1) == 1)
    acceleration_bubble_top = (df['close'] < df['MA20']) & (df['q1_dot'] < 0) & (df['q1_dot'].shift(1) >= 0)
    raw_bubble_top = regime_bubble_top & gate_bubble_top & (inflection_bubble_top | acceleration_bubble_top)

    # 象限 IV: 熊市反弹衰竭顶 (Bear Rebound Exhaustion Top)
    bear_regime = (df['MA200_Slope'] < -0.05) | (df['MA50'] < df['MA200'] * 0.98) | macro_crisis_regime
    exhaustion_gate = (df['Dist_200MA'] < 5.0)
    inflection_bear_top = (df['close'] < df['MA20']) & (df['q1_dot'] < 0) & (df['q1_dot'].shift(1) >= 0)
    raw_bear_top = bear_regime & exhaustion_gate & inflection_bear_top & (~raw_bubble_top)

    # =========================================================================
    # 第八步：状态迟滞抗震荡滤波 (Hysteresis & Cooldown)
    # =========================================================================
    def apply_hys(df_sub, raw_flags, min_days, price_step, is_top=False):
        final_flags = []
        last_dt = None
        last_p = None
        for idx in range(len(df_sub)):
            flag = raw_flags.iloc[idx]
            dt = df_sub['date'].iloc[idx]
            p = df_sub['close'].iloc[idx]
            act = False
            if flag:
                days = (dt - last_dt).days if last_dt else 999
                if is_top:
                    if days > min_days or p > (last_p * (1 + price_step) if last_p else 0):
                        act = True
                        last_dt = dt
                        last_p = p
                else:
                    if days > min_days or p < (last_p * (1 - price_step) if last_p else 999999):
                        act = True
                        last_dt = dt
                        last_p = p
            final_flags.append(act)
        return pd.Series(final_flags, index=df_sub.index)

    df['Trigger_Panic'] = apply_hys(df, raw_panic, min_days=15, price_step=0.07, is_top=False)
    df['Trigger_Stage'] = apply_hys(df, raw_stage, min_days=20, price_step=0.06, is_top=False)
    df['Trigger_Bubble_Top'] = apply_hys(df, raw_bubble_top, min_days=25, price_step=0.08, is_top=True)
    df['Trigger_Bear_Top'] = apply_hys(df, raw_bear_top, min_days=20, price_step=0.06, is_top=True)
    
    # =========================================================================
    # 第九步：集成真实券商账本系统 (SharedExecutor Single Source of Truth)
    # =========================================================================
    core_cols = ['Composite_Score', 'Gap_Max_45', 'Dist_200MA', 'NFCI', 'BAA10Y', 'HYG', 'Real_Yield', 'close', 'MA200', 'MA50', 'MA10']
    df['signal_ready'] = df[core_cols].notna().all(axis=1)

    cond_trend = (df['close'] > df['MA50']).rolling(3).sum() == 3
    
    # 统一使用带有迟滞抗震荡机制的 Trigger 信号作为买卖输入
    raw_sell = (df['Trigger_Bubble_Top'] | df['Trigger_Bear_Top']) & df['signal_ready']
    raw_buy = (df['Trigger_Panic'] | cond_trend) & df['signal_ready']

    from shared_executor import SharedExecutor
    from true_accounting import UnitizedAccount
    
    strat_acc = UnitizedAccount(initial_cash=100000.0, initial_date=df['date'].iloc[0])
    executor = SharedExecutor(strat_acc, fee_rate=0.0, execution_mode='NEXT_CLOSE', account_type='strat')
    
    actions = []
    pos = 1.0  # 初始默认满仓
    curr_m = -1

    for i in range(len(df)):
        dt = df['date'].iloc[i]
        p_close = df['close'].iloc[i]
        is_valid = not np.isnan(p_close)
        
        # 记录本月初定投 (模拟每月1号定投1000)
        m = dt.month
        if m != curr_m and df['signal_ready'].iloc[i]:
            executor.schedule_cashflow(dt, 1000.0)
            curr_m = m

        executor.step(dt, p_open=p_close, p_close=p_close, is_p_open_valid=is_valid, is_p_close_valid=is_valid)

        if df['signal_ready'].iloc[i] and is_valid:
            s = raw_sell.iloc[i]
            b = raw_buy.iloc[i]

            if pos > 0 and s:
                pos = 0.0
                executor.place_order(dt, order_type='SELL', target_weight=0.0, reason='Macro Reflexivity Risk / Bear Exhaustion')
            elif pos == 0.0 and b:
                pos = 1.0
                executor.place_order(dt, order_type='BUY', target_weight=1.0, reason='Panic Bottom / Trend Breakout Re-entry')
                
        executor.mark_to_market(dt, p_close)
        
        # 回溯当天的买卖动作供 UI 画图使用
        today_action = 'HOLD'
        # 查找当天是否成交
        for tr in executor.trades:
            if tr['date'].strftime('%Y-%m-%d') == dt.strftime('%Y-%m-%d'):
                today_action = tr['type']
                break
                
        if not df['signal_ready'].iloc[i]:
            today_action = 'WAITING'
            
        actions.append(today_action)
        
    df['action'] = actions

    return df
