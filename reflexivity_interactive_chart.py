# -*- coding: utf-8 -*-
"""
========================================================================================
项目名称：宏观反身性阿尔法模型 —— 动态可交互 4 层全景图谱引擎
文件名称：reflexivity_interactive_chart.py
技术选型：Plotly 动态微件 (毫秒级响应、局部滚轮放大、时间滑块、一键聚焦近期)
========================================================================================
"""

import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots


def run_reflexivity_simulation(df_raw, ticker='QQQ', dca_monthly=1000.0, allow_breakout=True, cost_config=0.0):
    """
    轻量化、脱机闭环的纯现货双轨制反身性模型仿真
    返回 sub (包含所有技术与宏观指标、雷达分、净值曲线) 与 trades (逐笔买卖交易记录)
    """
    sub = df_raw[['date', ticker, 'HYG', 'NFCI', 'BAA10Y', 'Real_Yield']].copy()
    sub['date'] = pd.to_datetime(sub['date']).dt.tz_localize(None)
    sub = sub.sort_values('date').reset_index(drop=True)
    
    # 1. 均线体系
    sub['MA10'] = sub[ticker].rolling(10).mean()
    sub['MA20'] = sub[ticker].rolling(20).mean()
    sub['MA50'] = sub[ticker].rolling(50).mean()
    sub['MA200'] = sub[ticker].rolling(200).mean()
    sub['Dist_200MA'] = (sub[ticker] - sub['MA200']) / sub['MA200'] * 100.0

    # 2. 宏观信用大趋势与实际利率
    sub['HYG_MA200'] = sub['HYG'].rolling(200).mean()
    sub['BAA_MA60'] = sub['BAA10Y'].rolling(60).mean()
    sub['BAA_Stress'] = sub['BAA10Y'] > sub['BAA_MA60']
    sub['RY_Surge'] = (sub['Real_Yield'] - sub['Real_Yield'].rolling(60).min()) > 0.40

    # 3. NFCI 滚动 252 天 Z-Score
    sub['NFCI_Roll_Mean'] = sub['NFCI'].rolling(252).mean()
    sub['NFCI_Roll_Std'] = sub['NFCI'].rolling(252).std()
    sub['NFCI_Z'] = (sub['NFCI'] - sub['NFCI_Roll_Mean']) / (sub['NFCI_Roll_Std'] + 1e-8)

    # 4. 反身性偏离度 Gap (动态 Beta 定价)
    sub['Price_Z'] = (sub[ticker] - sub[ticker].rolling(200).mean()) / (sub[ticker].rolling(200).std() + 1e-8)
    sub['Macro_Z'] = (sub['HYG'] - sub['HYG'].rolling(200).mean()) / (sub['HYG'].rolling(200).std() + 1e-8)
    roll_cov = sub['Price_Z'].rolling(252).cov(sub['Macro_Z'])
    roll_var = sub['Macro_Z'].rolling(252).var()
    sub['Dynamic_Beta'] = (roll_cov / (roll_var + 1e-8)).clip(lower=-2.0, upper=2.0)
    sub['Expected_Price_Z'] = sub['Macro_Z'] * sub['Dynamic_Beta']
    sub['Gap'] = sub['Price_Z'] - sub['Expected_Price_Z']

    # 45 天记忆窗口与自适应 85% 分位数阈值
    sub['Gap_Max_45'] = sub['Gap'].rolling(45, min_periods=1).max()
    sub['PriceZ_Max_45'] = sub['Price_Z'].rolling(45, min_periods=1).max()
    sub['Gap_Median'] = sub['Gap'].rolling(252, min_periods=20).median()
    sub['Gap_Upper'] = sub['Gap'].expanding(min_periods=20).quantile(0.85)

    # 5. 双轨制宏观过热雷达分 (0 - 100)
    z_score = np.clip((sub['Price_Z'] - 0.5) / 1.5 * 40.0, 0.0, 40.0)
    dist_score = np.clip((sub['Dist_200MA'] - 5.0) / 15.0 * 30.0, 0.0, 30.0)
    def mid_rank_pct(s):
        s_valid = s.dropna()
        if len(s_valid) < 60:
            return np.nan
        val = s.iloc[-1]
        if np.isnan(val):
            return np.nan
        L_t = (s_valid < val).sum()
        E_t = (s_valid == val).sum()
        N_t = len(s_valid)
        return (L_t + 0.5 * E_t) / N_t * 30.0
        
    gap_score = sub['Gap'].rolling(252, min_periods=60).apply(mid_rank_pct, raw=False)
    sub['Overheat_Score'] = z_score + dist_score + gap_score
    sub['Overheat_Alert'] = sub['Overheat_Score'] >= 70.0

    # 6. 右侧破位判定与确认
    sub['Cond_Bubble'] = (
        (sub['Gap_Max_45'] > sub['Gap_Upper']) & 
        (sub['PriceZ_Max_45'] > 1.5) & 
        (sub['Dist_200MA'] > 5.0) & 
        (sub['NFCI'] > -0.50) & 
        sub['BAA_Stress'] & 
        (sub[ticker] < sub['MA20'])
    )

    sub['Macro_Crisis'] = (
        (sub['HYG'] < sub['HYG_MA200']) & 
        sub['RY_Surge'] & 
        (sub['NFCI_Z'] > 1.2) & 
        (sub['NFCI'] > -0.50)
    )
    sub['Cond_Bear'] = sub['Macro_Crisis'] & (sub[ticker] < sub['MA50']) & (sub[ticker] < sub['MA200'])
    sub['Sell_Signal'] = sub['Cond_Bubble'] | sub['Cond_Bear']

    sub['Above_MA50_Conf'] = (sub[ticker] > sub['MA50']).rolling(3, min_periods=1).sum() == 3
    sub['Above_MA20_Conf'] = (sub[ticker] > sub['MA20']).rolling(3, min_periods=1).sum() == 3
    sub['Cond_Panic'] = (sub['Dist_200MA'].rolling(10, min_periods=1).min() < -10.0) & (sub[ticker] > sub['MA10'])

    core_cols = ['Overheat_Score', 'Gap', 'Dist_200MA', 'NFCI', 'BAA10Y', 'HYG', 'Real_Yield', ticker, 'MA200']
    sub['signal_ready'] = sub[core_cols].notna().all(axis=1)
    # No dropna() here to preserve the timeline
    sub = sub[sub['date'] >= '2009-01-01'].reset_index(drop=True)

    # 7. 接入共享执行器与单位化核算 (T+1 延迟执行, 新版账户)
    from true_accounting import UnitizedAccount
    from shared_executor import SharedExecutor
    
    acc = UnitizedAccount(initial_cash=0.0, initial_date=sub['date'].iloc[0])
    bench_acc = UnitizedAccount(initial_cash=0.0, initial_date=sub['date'].iloc[0])
    
    executor = SharedExecutor(acc, fee_rate=cost_config, account_type='strat')
    bench_executor = SharedExecutor(bench_acc, fee_rate=0.0, account_type='bench')
    
    curr_m = -1
    exit_regime = None
    pos = 1.0 # 初始目标满仓
    
    bench_eqs = []
    strat_eqs = []
    bench_navs = []
    strat_navs = []
    positions = []
    total_invested = 0.0

    for i in range(len(sub)):
        p = sub[ticker].iloc[i]
        dt = sub['date'].iloc[i]
        m = dt.month

        # 月度定投
        dca_amount = 0.0
        if m != curr_m:
            dca_amount = dca_monthly
            total_invested += dca_monthly
            curr_m = m

        # 1. 每日执行引擎推进 (当期估值 -> 资金流入 -> NEXT_CLOSE旧订单执行 -> 扣费估值)
        executor.step(dt, p, p, dca_amount)
        bench_executor.step(dt, p, p, dca_amount)

        # 2. 依据当日信息与【已成交记录】产生新订单 (Target Position)
        gap = sub['Gap'].iloc[i]
        gap_med = sub['Gap_Median'].iloc[i]
        p_val = p

        signal_ready = sub.get('signal_ready', pd.Series([True]*len(sub))).iloc[i]

        action_taken = False
        if signal_ready:
            # 卖出逻辑
            if pos > 0 and sub['Sell_Signal'].iloc[i]:
                is_bub = sub['Cond_Bubble'].iloc[i]
                exit_regime = 'BUBBLE' if is_bub else 'BEAR'
                r_reason = '宏观黄昏期泡沫止盈' if is_bub else '系统宏观紧缩熊市避险'
                executor.submit_order(0.0, r_reason, dt)
                pos = 0.0
                action_taken = True
            
            # 买入逻辑
            elif pos == 0.0:
                can_buy = False
                b_reason = ""
                is_panic = False
                gap_cooled = False
                trend_conf = False
                breakout_higher = False

                if exit_regime == 'BUBBLE':
                    is_panic = sub['Cond_Panic'].iloc[i]
                    gap_cooled = (gap < gap_med)
                    trend_conf = sub['Above_MA20_Conf'].iloc[i] and sub['Above_MA50_Conf'].iloc[i]
                    
                    # 必须使用已实际成交的 last_sell_p
                    last_sell_p = executor.last_sell_p
                    if last_sell_p is not None:
                        breakout_higher = (p_val > last_sell_p * 1.02) and trend_conf

                    if is_panic:
                        can_buy = True
                        b_reason = '泡沫急跌杀出极值黄金坑'
                    elif gap_cooled and trend_conf:
                        can_buy = True
                        b_reason = '估值出清且右侧重构主升'
                    elif allow_breakout and breakout_higher:
                        can_buy = True
                        b_reason = '突破卖出价右侧防踏空接回'

                elif exit_regime == 'BEAR':
                    hyg_healed = (sub['HYG'].iloc[i] > sub['HYG_MA200'].iloc[i])
                    price_healed = sub['Above_MA50_Conf'].iloc[i]
                    if hyg_healed and price_healed:
                        can_buy = True
                        b_reason = '信用债先导修复且趋势重构'

                if can_buy:
                    executor.submit_order(1.0, b_reason, dt)
                    pos = 1.0
                    exit_regime = None
                    action_taken = True

        if not action_taken and dca_amount > 0:
            # 仅在定投日发送维持仓位订单，避免产生几百个冗余订单
            executor.submit_order(pos, "Standing Order / DCA", dt)

        # 基准始终满仓，仅在首日或定投日发送订单
        if i == 0 or dca_amount > 0:
            bench_executor.submit_order(1.0, "Bench Standing Order / DCA", dt)

        # 记录日终资产与净值状态
        bench_eqs.append(bench_executor.acc.shares * p + bench_executor.acc.cash)
        strat_eqs.append(executor.acc.shares * p + executor.acc.cash)
        bench_navs.append(bench_executor.acc.unit_nav)
        strat_navs.append(executor.acc.unit_nav)
        positions.append(pos)

    # 将账户每日状态汇总
    all_states = executor.daily_states + bench_executor.daily_states
    daily_accounts = pd.DataFrame(all_states)
    
    sub['Strat_Equity'] = strat_eqs
    sub['Bench_Equity'] = bench_eqs
    sub['Strat_NAV'] = strat_navs
    sub['Bench_NAV'] = bench_navs

    from core_engine.simulation_result import SimulationResult

    result = SimulationResult(
        features=sub,
        signals=pd.DataFrame({'date': sub['date'], 'Position': positions}),
        orders=executor.orders_history + executor.pending_orders,
        fills=executor.fills,
        cashflows=executor.cashflows,
        daily_accounts=daily_accounts,
        metrics={'total_invested': total_invested},
        metadata={'ticker': ticker, 'start_date': sub['date'].iloc[0], 'end_date': sub['date'].iloc[-1]}
    )
    # result.validate() # 暂时先不校验或者在外部校验，以防有兼容性问题

    return result


def build_interactive_4layer_chart(
    sim_result, 
    ticker='QQQ', 
    default_range='6M',
    start_date=None,
    end_date=None
):
    """
    构建 4 层上下严格对齐、时间轴联动缩放、Y 轴自适应价格极值的 Plotly 交互图表
    """
    sub = sim_result.features
    fills_df = pd.DataFrame(sim_result.fills) if sim_result.fills else pd.DataFrame()
    orders_df = pd.DataFrame(sim_result.orders) if sim_result.orders else pd.DataFrame()
    
    trades = []
    if not fills_df.empty and not orders_df.empty:
        merged = pd.merge(fills_df, orders_df, on='order_id', how='left')
        for _, row in merged.iterrows():
            trades.append({
                'action': row['direction'],
                'date': row['dt'],
                'price': row['price'],
                'reason': row['reason'] if pd.notna(row['reason']) else 'System Executed'
            })
            
    import streamlit as st
    curr_theme = st.session_state.get("theme_mode", "dark")
    if curr_theme == "dark":
        paper_bg = "#0b0f19"
        plot_bg = "#0e131f"
        font_c = "#f8fafc"
        tpl = "plotly_dark"
        grid_c = "rgba(255, 255, 255, 0.08)"
        zero_c = "#334155"
        legend_bg = "rgba(19, 27, 42, 0.95)"
        legend_border = "#334155"
        color_accent = '#38bdf8' if ticker == 'QQQ' else '#2dd4bf'
        ma200_c = '#c084fc'  # bright lilac
        overheat_c = '#818cf8'  # bright indigo
        bench_c = '#94a3b8'  # bright slate
    else:
        paper_bg = "#ffffff"
        plot_bg = "#ffffff"
        font_c = "#0f172a"
        tpl = "plotly_white"
        grid_c = "#f1f5f9"
        zero_c = "#e2e8f0"
        legend_bg = "rgba(255, 255, 255, 0.95)"
        legend_border = "#cbd5e1"
        color_accent = '#0984e3' if ticker == 'QQQ' else '#00b894'
        ma200_c = '#8e44ad'
        overheat_c = '#6c5ce7'
        bench_c = '#7f8c8d'
    
    last_dt = sub['date'].iloc[-1]
    first_dt = sub['date'].iloc[0]

    # 解析目标时间切片窗口
    if start_date is not None and end_date is not None:
        s_dt = pd.to_datetime(start_date)
        e_dt = pd.to_datetime(end_date)
    else:
        e_dt = last_dt
        if default_range == '1M':
            s_dt = last_dt - pd.DateOffset(months=1)
        elif default_range == '3M':
            s_dt = last_dt - pd.DateOffset(months=3)
        elif default_range == '6M':
            s_dt = last_dt - pd.DateOffset(months=6)
        elif default_range == '1Y':
            s_dt = last_dt - pd.DateOffset(years=1)
        elif default_range == '3Y':
            s_dt = last_dt - pd.DateOffset(years=3)
        elif default_range == '5Y':
            s_dt = last_dt - pd.DateOffset(years=5)
        else:
            s_dt = first_dt

    if s_dt < first_dt:
        s_dt = first_dt
    if e_dt > last_dt:
        e_dt = last_dt
    if s_dt >= e_dt:
        s_dt = e_dt - pd.DateOffset(days=30)

    s_slice = sub[(sub['date'] >= s_dt) & (sub['date'] <= e_dt)]
    if s_slice.empty:
        s_slice = sub
        s_dt = first_dt
        e_dt = last_dt

    fig = make_subplots(
        rows=4, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.038,
        row_heights=[0.44, 0.18, 0.18, 0.20],
        subplot_titles=[
            f"<b>① {ticker} 价格走势、关键均线体系与双轨决策信号 (买点 🟢 / 卖点 🔴 / 过热预警 🟡)</b>",
            "<b>② 宏观反身性偏离度 Gap vs 自适应 85% 泡沫阈值 (量化估值透支程度)</b>",
            "<b>③ 0~100 宏观过热雷达评分能量带 (Overheating Radar Score, 70分高危警报)</b>",
            "<b>④ 真实券商定投净值对账曲线 (策略 1.0x 账户 vs Buy & Hold 基准)</b>"
        ]
    )

    # =========================================================================
    # ROW 1: 价格走势 + 均线体系 + 买卖点 + 过热散点 (高对比度精美配色)
    # =========================================================================
    # 标的收盘价
    fig.add_trace(
        go.Scatter(
            x=s_slice['date'], y=s_slice[ticker],
            mode='lines', name=f'{ticker} 收盘价',
            line=dict(color=color_accent, width=2.0),
            hovertemplate=f"<b>{ticker}</b>: $%{{y:.2f}}<extra></extra>"
        ), row=1, col=1
    )

    # 关键均线
    if 'MA20' in s_slice.columns:
        fig.add_trace(
            go.Scatter(
                x=s_slice['date'], y=s_slice['MA20'],
                mode='lines', name='MA20 短线',
                line=dict(color='#e67e22', width=1.3, dash='dash'),
                hovertemplate="MA20: $%{y:.2f}<extra></extra>"
            ), row=1, col=1
        )
    if 'MA50' in s_slice.columns:
        fig.add_trace(
            go.Scatter(
                x=s_slice['date'], y=s_slice['MA50'],
                mode='lines', name='MA50 生命线',
                line=dict(color='#e74c3c', width=1.4),
                hovertemplate="MA50: $%{y:.2f}<extra></extra>"
            ), row=1, col=1
        )
    if 'MA200' in s_slice.columns:
        fig.add_trace(
            go.Scatter(
                x=s_slice['date'], y=s_slice['MA200'],
                mode='lines', name='MA200 牛熊分界',
                line=dict(color=ma200_c, width=1.8),
                hovertemplate="MA200: $%{y:.2f}<extra></extra>"
            ), row=1, col=1
        )

    # 🟡 宏观过热预警散点 (Score >= 70, 带深色轮廓更醒目)
    if 'Overheat_Alert' in s_slice.columns:
        alerts = s_slice[s_slice['Overheat_Alert']]
        if not alerts.empty:
            fig.add_trace(
                go.Scatter(
                    x=alerts['date'], y=alerts[ticker],
                    mode='markers', name='🟡 过热黄色预警',
                    marker=dict(symbol='circle', size=6.5, color='#f1c40f', line=dict(width=1, color='#2c3e50'), opacity=0.9),
                    customdata=alerts[['Overheat_Score', 'Gap', 'Dist_200MA']],
                    hovertemplate="<b>[🟡 过热预警]</b><br>价格: $%{y:.2f}<br>雷达分: %{customdata[0]:.1f}<br>Gap: %{customdata[1]:.2f}<br>乖离率: %{customdata[2]:+.1f}%<extra></extra>"
                ), row=1, col=1
            )

    # 逐笔交易标记 (买点 🟢 / 卖点 🔴) 过滤掉常规的每月定投订单
    buy_trades = [t for t in trades if t['action'] == 'BUY' and 'Standing Order / DCA' not in t['reason'] and pd.to_datetime(t['date']) >= s_dt and pd.to_datetime(t['date']) <= e_dt]
    sell_trades = [t for t in trades if t['action'] == 'SELL' and 'Standing Order / DCA' not in t['reason'] and pd.to_datetime(t['date']) >= s_dt and pd.to_datetime(t['date']) <= e_dt]

    if buy_trades:
        b_df = pd.DataFrame(buy_trades)
        b_df['date'] = pd.to_datetime(b_df['date'])
        fig.add_trace(
            go.Scatter(
                x=b_df['date'], y=b_df['price'],
                mode='markers+text', name='🟢 买入/增殖接回',
                text=[f"买入 ${p:.1f}" for p in b_df['price']],
                textposition="bottom center",
                textfont=dict(color="#00b894", size=10, family="Arial Black"),
                marker=dict(symbol='triangle-up', size=13, color='#00b894', line=dict(width=1.5, color='#ffffff')),
                customdata=b_df['reason'],
                hovertemplate="<b>🟢 [系统买入]</b><br>成交价: $%{y:.2f}<br>归因: %{customdata}<extra></extra>"
            ), row=1, col=1
        )

    if sell_trades:
        s_df = pd.DataFrame(sell_trades)
        s_df['date'] = pd.to_datetime(s_df['date'])
        fig.add_trace(
            go.Scatter(
                x=s_df['date'], y=s_df['price'],
                mode='markers+text', name='🔴 避险清仓卖出',
                text=[f"卖出 ${p:.1f}" for p in s_df['price']],
                textposition="top center",
                textfont=dict(color="#d63031", size=10, family="Arial Black"),
                marker=dict(symbol='triangle-down', size=13, color='#d63031', line=dict(width=1.5, color='#ffffff')),
                customdata=s_df['reason'],
                hovertemplate="<b>🔴 [避险卖出]</b><br>成交价: $%{y:.2f}<br>归因: %{customdata}<extra></extra>"
            ), row=1, col=1
        )

    # =========================================================================
    # ROW 2: 宏观反身性偏离度 Gap vs 自适应 85% 阈值
    # =========================================================================
    if 'Gap' in s_slice.columns:
        fig.add_trace(
            go.Scatter(
                x=s_slice['date'], y=s_slice['Gap'],
                mode='lines', name='反身性 Gap',
                line=dict(color='#e84393', width=1.6),
                hovertemplate="反身性偏离 Gap: %{y:.2f}<extra></extra>"
            ), row=2, col=1
        )
    if 'Gap_Upper' in s_slice.columns:
        fig.add_trace(
            go.Scatter(
                x=s_slice['date'], y=s_slice['Gap_Upper'],
                mode='lines', name='自适应 85% 阈值',
                line=dict(color='#d35400', width=1.4, dash='dot'),
                hovertemplate="自适应 85% 阈值: %{y:.2f}<extra></extra>"
            ), row=2, col=1
        )
    fig.add_hline(y=0.0, line_dash="solid", line_color="#b2bec3", line_width=1.0, row=2, col=1)
    fig.add_hline(y=2.0, line_dash="dot", line_color="#ef4444", line_width=1.2, row=2, col=1, annotation_text="+2.0 情绪过热警戒", annotation_position="top left")
    fig.add_hline(y=-2.0, line_dash="dot", line_color="#10b981", line_width=1.2, row=2, col=1, annotation_text="-2.0 情绪冰点超跌", annotation_position="bottom left")
    fig.add_hrect(y0=2.0, y1=15.0, fillcolor="rgba(239, 68, 68, 0.05)", line_width=0, row=2, col=1)
    fig.add_hrect(y0=-15.0, y1=-2.0, fillcolor="rgba(16, 185, 129, 0.05)", line_width=0, row=2, col=1)

    # =========================================================================
    # ROW 3: 0~100 宏观过热雷达能量带
    # =========================================================================
    if 'Overheat_Score' in s_slice.columns:
        fig.add_trace(
            go.Scatter(
                x=s_slice['date'], y=s_slice['Overheat_Score'],
                mode='lines', name='过热雷达分',
                line=dict(color=overheat_c, width=1.7),
                hovertemplate="过热雷达评分: %{y:.1f} / 100<extra></extra>"
            ), row=3, col=1
        )
    fig.add_hline(
        y=70.0, line_dash="dash", line_color="#d63031", line_width=1.3,
        annotation_text="70分 高危过热警戒红线", annotation_position="top left",
        annotation_font=dict(color="#d63031", size=10),
        row=3, col=1
    )
    fig.add_hrect(
        y0=70.0, y1=100.0, fillcolor="#d63031", opacity=0.10, line_width=0,
        row=3, col=1
    )

    # =========================================================================
    # ROW 4: 真实券商定投净值对账曲线
    # =========================================================================
    if 'Strat_Equity' in s_slice.columns:
        fig.add_trace(
            go.Scatter(
                x=s_slice['date'], y=s_slice['Strat_Equity'],
                mode='lines', name='策略真实净值',
                line=dict(color='#00b894', width=2.4),
                hovertemplate="策略净值: $%{y:,.0f}<extra></extra>"
            ), row=4, col=1
        )
    if 'Bench_Equity' in s_slice.columns:
        fig.add_trace(
            go.Scatter(
                x=s_slice['date'], y=s_slice['Bench_Equity'],
                mode='lines', name='Buy & Hold 基准',
                line=dict(color=bench_c, width=1.3, dash='dash'),
                hovertemplate="基准净值: $%{y:,.0f}<extra></extra>"
            ), row=4, col=1
        )

    # =========================================================================
    # =========================================================================
    # 动态极值计算：严格根据可见切片自适应全部 4 层 Y 轴
    # =========================================================================
    last_dt = sub['date'].iloc[-1]
    first_dt = sub['date'].iloc[0]

    # 解析目标时间切片窗口
    if start_date is not None and end_date is not None:
        s_dt = pd.to_datetime(start_date)
        e_dt = pd.to_datetime(end_date)
    else:
        e_dt = last_dt
        if default_range == '1M':
            s_dt = last_dt - pd.DateOffset(months=1)
        elif default_range == '3M':
            s_dt = last_dt - pd.DateOffset(months=3)
        elif default_range == '6M':
            s_dt = last_dt - pd.DateOffset(months=6)
        elif default_range == '1Y':
            s_dt = last_dt - pd.DateOffset(years=1)
        elif default_range == '3Y':
            s_dt = last_dt - pd.DateOffset(years=3)
        elif default_range == '5Y':
            s_dt = last_dt - pd.DateOffset(years=5)
        else:
            s_dt = first_dt

    if s_dt < first_dt:
        s_dt = first_dt
    if e_dt > last_dt:
        e_dt = last_dt
    if s_dt >= e_dt:
        s_dt = e_dt - pd.DateOffset(days=30)

    s_slice = sub[(sub['date'] >= s_dt) & (sub['date'] <= e_dt)]
    if s_slice.empty:
        s_slice = sub
        s_dt = first_dt
        e_dt = last_dt

    # 1. 价格切片极值 (带 6% 呼吸边距)
    p_cols = [ticker]
    for c in ['MA20', 'MA50', 'MA200']:
        if c in s_slice.columns:
            p_cols.append(c)
    p_min = s_slice[p_cols].min().min()
    p_max = s_slice[p_cols].max().max()
    p_pad = max((p_max - p_min) * 0.06, p_max * 0.03)
    y_p_range = [max(0, p_min - p_pad), p_max + p_pad]

    # 2. Gap 极值 (保证 0 轴与 +-2.0 警戒线可见)
    g_cols = ['Gap']
    if 'Gap_Upper' in s_slice.columns:
        g_cols.append('Gap_Upper')
    g_min = s_slice[g_cols].min().min()
    g_max = s_slice[g_cols].max().max()
    y_gap_range = [min(g_min - 0.4, -2.5), max(g_max + 0.4, 2.5)]

    # 3. 净值切片极值 (带 6% 呼吸边距)
    eq_cols = []
    if 'Bench_Equity' in s_slice.columns:
        eq_cols.append('Bench_Equity')
    if 'Strat_Equity' in s_slice.columns:
        eq_cols.append('Strat_Equity')
    if eq_cols:
        eq_min = s_slice[eq_cols].min().min()
        eq_max = s_slice[eq_cols].max().max()
        eq_pad = max((eq_max - eq_min) * 0.06, eq_max * 0.03)
        y_eq_range = [max(0, eq_min - eq_pad), eq_max + eq_pad]
    else:
        y_eq_range = [0, 1000000]

    # =========================================================================
    # 图例配置与排版布局 (杜绝重叠碰撞)
    # =========================================================================
    fig.update_layout(
        template=tpl,
        paper_bgcolor=paper_bg,
        plot_bgcolor=plot_bg,
        height=1000,
        hovermode='x unified',
        font=dict(size=14, family="sans-serif", color=font_c),
        margin=dict(l=65, r=45, t=70, b=40),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="center",
            x=0.5,
            bgcolor=legend_bg,
            bordercolor=legend_border,
            borderwidth=1,
            font=dict(color=font_c, size=13, family="sans-serif")
        )
    )

    # 4 层 X 轴范围与刻度同步
    start_str = s_dt.strftime('%Y-%m-%d')
    end_str = (e_dt + pd.DateOffset(days=3)).strftime('%Y-%m-%d')
    fig.update_xaxes(
        range=[start_str, end_str],
        gridcolor=grid_c, zerolinecolor=zero_c,
        tickfont=dict(color=font_c, size=14)
    )

    # 4 层 Y 轴应用精准自适应极值
    fig.update_yaxes(
        range=y_p_range,
        title_text="价格 (USD)", tickprefix="$",
        gridcolor=grid_c, zerolinecolor=zero_c,
        tickfont=dict(color=font_c, size=14),
        row=1, col=1
    )
    fig.update_yaxes(
        range=y_gap_range,
        title_text="反身性 Gap",
        gridcolor=grid_c, zerolinecolor=zero_c,
        tickfont=dict(color=font_c, size=14),
        row=2, col=1
    )
    fig.update_yaxes(
        range=[0, 105],
        title_text="雷达评分",
        gridcolor=grid_c, zerolinecolor=zero_c,
        tickfont=dict(color=font_c, size=14),
        row=3, col=1
    )
    fig.update_yaxes(
        range=y_eq_range,
        title_text="账户净值", tickprefix="$",
        gridcolor=grid_c, zerolinecolor=zero_c,
        tickfont=dict(color=font_c, size=14),
        row=4, col=1
    )

    return fig
