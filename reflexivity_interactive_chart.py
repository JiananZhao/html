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


def run_reflexivity_simulation(df_raw, ticker='QQQ', dca_monthly=1000.0, allow_breakout=True):
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
    gap_score = np.clip((sub['Gap'] / sub['Gap_Upper']) * 15.0, 0.0, 30.0)
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

    sub = sub.dropna().reset_index(drop=True)
    sub = sub[sub['date'] >= '2009-01-01'].reset_index(drop=True)

    # 7. 真实券商两状态流水记账 (True Brokerage Ledger)
    total_invested = 0.0
    bench_shares = 0.0
    strat_shares = 0.0
    strat_cash = 0.0
    pos = 1.0
    curr_m = -1
    exit_regime = None
    trades = []
    
    bench_vals = []
    strat_vals = []
    positions = []

    for i in range(len(sub)):
        p = sub[ticker].iloc[i]
        d_str = sub['date'].iloc[i].strftime('%Y-%m-%d')
        m = sub['date'].iloc[i].month

        # 月度定投现金注入
        if m != curr_m:
            total_invested += dca_monthly
            bench_shares += dca_monthly / p
            if pos > 0:
                strat_shares += dca_monthly / p
            else:
                strat_cash += dca_monthly
            curr_m = m

        p_val = sub[ticker].iloc[i]
        gap = sub['Gap'].iloc[i]
        gap_med = sub['Gap_Median'].iloc[i]

        # 卖出
        if pos > 0 and sub['Sell_Signal'].iloc[i]:
            strat_cash += strat_shares * p
            is_bub = sub['Cond_Bubble'].iloc[i]
            exit_regime = 'BUBBLE' if is_bub else 'BEAR'
            r_reason = '宏观黄昏期泡沫止盈' if is_bub else '系统宏观紧缩熊市避险'
            trades.append({
                'action': 'SELL',
                'date': d_str,
                'price': p,
                'reason': r_reason
            })
            strat_shares = 0.0
            pos = 0.0

        # 买入
        elif pos == 0.0:
            can_buy = False
            b_reason = ""

            if exit_regime == 'BUBBLE':
                is_panic = sub['Cond_Panic'].iloc[i]
                gap_cooled = (gap < gap_med)
                trend_conf = sub['Above_MA20_Conf'].iloc[i] and sub['Above_MA50_Conf'].iloc[i]
                last_sell_p = trades[-1]['price']
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
                strat_shares += strat_cash / p
                strat_cash = 0.0
                pos = 1.0
                exit_regime = None
                trades.append({
                    'action': 'BUY',
                    'date': d_str,
                    'price': p,
                    'reason': b_reason
                })

        bench_vals.append(bench_shares * p)
        strat_vals.append(strat_shares * p + strat_cash)
        positions.append(pos)

    sub['Bench_Equity'] = bench_vals
    sub['Strat_Equity'] = strat_vals
    sub['Position'] = positions

    return {'df': sub, 'trades': trades, 'total_invested': total_invested}


def build_interactive_4layer_chart(sub, trades, ticker='QQQ', default_range='6M'):
    """
    构建 4 层上下严格对齐、时间轴联动缩放、Y 轴自适应价格极值的 Plotly 交互图表
    default_range: '1M', '3M', '6M', '1Y', '3Y', '5Y', 'ALL'
    """
    color_accent = '#0984e3' if ticker == 'QQQ' else '#00b894'
    
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
            x=sub['date'], y=sub[ticker],
            mode='lines', name=f'{ticker} 收盘价',
            line=dict(color=color_accent, width=2.0),
            hovertemplate=f"<b>{ticker}</b>: $%{{y:.2f}}<extra></extra>"
        ), row=1, col=1
    )

    # 关键均线
    fig.add_trace(
        go.Scatter(
            x=sub['date'], y=sub['MA20'],
            mode='lines', name='MA20 短线',
            line=dict(color='#e67e22', width=1.3, dash='dash'),
            hovertemplate="MA20: $%{y:.2f}<extra></extra>"
        ), row=1, col=1
    )
    fig.add_trace(
        go.Scatter(
            x=sub['date'], y=sub['MA50'],
            mode='lines', name='MA50 生命线',
            line=dict(color='#e74c3c', width=1.4),
            hovertemplate="MA50: $%{y:.2f}<extra></extra>"
        ), row=1, col=1
    )
    fig.add_trace(
        go.Scatter(
            x=sub['date'], y=sub['MA200'],
            mode='lines', name='MA200 牛熊分界',
            line=dict(color='#8e44ad', width=1.8),
            hovertemplate="MA200: $%{y:.2f}<extra></extra>"
        ), row=1, col=1
    )

    # 🟡 宏观过热预警散点 (Score >= 70, 带深色轮廓更醒目)
    alerts = sub[sub['Overheat_Alert']]
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

    # 逐笔交易标记 (买点 🟢 / 卖点 🔴)
    buy_trades = [t for t in trades if t['action'] == 'BUY']
    sell_trades = [t for t in trades if t['action'] == 'SELL']

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
    fig.add_trace(
        go.Scatter(
            x=sub['date'], y=sub['Gap'],
            mode='lines', name='反身性 Gap',
            line=dict(color='#e84393', width=1.6),
            hovertemplate="反身性偏离 Gap: %{y:.2f}<extra></extra>"
        ), row=2, col=1
    )
    fig.add_trace(
        go.Scatter(
            x=sub['date'], y=sub['Gap_Upper'],
            mode='lines', name='自适应 85% 阈值',
            line=dict(color='#d35400', width=1.4, dash='dot'),
            hovertemplate="自适应 85% 阈值: %{y:.2f}<extra></extra>"
        ), row=2, col=1
    )
    fig.add_hline(y=0.0, line_dash="solid", line_color="#b2bec3", line_width=0.8, row=2, col=1)

    # =========================================================================
    # ROW 3: 0~100 宏观过热雷达能量带
    # =========================================================================
    fig.add_trace(
        go.Scatter(
            x=sub['date'], y=sub['Overheat_Score'],
            mode='lines', name='过热雷达分',
            line=dict(color='#6c5ce7', width=1.7),
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
    fig.add_trace(
        go.Scatter(
            x=sub['date'], y=sub['Strat_Equity'],
            mode='lines', name='策略真实净值',
            line=dict(color='#00b894', width=2.4),
            hovertemplate="策略净值: $%{y:,.0f}<extra></extra>"
        ), row=4, col=1
    )
    fig.add_trace(
        go.Scatter(
            x=sub['date'], y=sub['Bench_Equity'],
            mode='lines', name='Buy & Hold 基准',
            line=dict(color='#7f8c8d', width=1.3, dash='dash'),
            hovertemplate="基准净值: $%{y:,.0f}<extra></extra>"
        ), row=4, col=1
    )

    # =========================================================================
    # 动态自适应 Y 轴与双轴联动按钮计算 (解决 Y 轴空白过大问题)
    # =========================================================================
    last_dt = sub['date'].iloc[-1]
    end_str = (last_dt + pd.DateOffset(days=5)).strftime('%Y-%m-%d')
    
    # 预先计算各预设周期的 X 轴范围与对应可见切片的 Y 轴极值 (带 6% 视觉呼吸边距)
    time_windows = [
        ("近1月", 1),
        ("近3月", 3),
        ("近6月", 6),
        ("近1年", 12),
        ("近3年", 36),
        ("近5年", 60),
        ("全部 (17.6年)", None)
    ]
    
    updatemenu_buttons = []
    
    # 记录当前 default_range 的初始边界
    initial_x_start = sub['date'].iloc[0]
    initial_y_p_min = sub[ticker].min()
    initial_y_p_max = sub[ticker].max()
    initial_y_eq_min = sub['Bench_Equity'].min()
    initial_y_eq_max = sub['Strat_Equity'].max()

    for label, months in time_windows:
        if months is not None:
            s_dt = last_dt - pd.DateOffset(months=months)
            s_slice = sub[sub['date'] >= s_dt]
        else:
            s_dt = sub['date'].iloc[0]
            s_slice = sub

        s_str = s_dt.strftime('%Y-%m-%d')
        
        # 价格切片极值
        p_min = s_slice[[ticker, 'MA20', 'MA50', 'MA200']].min().min()
        p_max = s_slice[[ticker, 'MA20', 'MA50', 'MA200']].max().max()
        p_pad = (p_max - p_min) * 0.06
        y_p_min = max(0, p_min - p_pad)
        y_p_max = p_max + p_pad
        
        # 净值切片极值
        eq_min = s_slice['Bench_Equity'].min()
        eq_max = s_slice['Strat_Equity'].max()
        eq_pad = (eq_max - eq_min) * 0.06
        y_eq_min = max(0, eq_min - eq_pad)
        y_eq_max = eq_max + eq_pad
        
        # 匹配初始视野
        key_tag = f"{months}M" if months in [1, 3, 6] else (f"{months//12}Y" if months else "ALL")
        if default_range == key_tag or (default_range == '6M' and months == 6):
            initial_x_start = s_dt
            initial_y_p_min = y_p_min
            initial_y_p_max = y_p_max
            initial_y_eq_min = y_eq_min
            initial_y_eq_max = y_eq_max

        # 构造 Plotly Relayout 联动按钮：点击同时精准更新 X 轴与 Y 轴范围！
        updatemenu_buttons.append(dict(
            label=label,
            method='relayout',
            args=[{
                'xaxis4.range': [s_str, end_str],
                'yaxis.range': [y_p_min, y_p_max],
                'yaxis4.range': [y_eq_min, y_eq_max]
            }]
        ))

    # =========================================================================
    # 图例配置 (白底黑字清晰可辨) 与布局排版
    # =========================================================================
    fig.update_layout(
        template='plotly_white',
        height=1060,
        hovermode='x unified',
        margin=dict(l=65, r=35, t=140, b=40),
        
        # 🌟 优化项 1: 白底黑字、浅灰外边框的高清晰图例
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.04,
            xanchor="center",
            x=0.5,
            bgcolor="#ffffff",                      # 纯白底色
            bordercolor="#b2bec3",                  # 浅灰精致边框
            borderwidth=1.5,
            font=dict(color="#111111", size=11, family="sans-serif") # 纯黑高清晰文字！
        ),

        # 🌟 优化项 2: 内置双轴联动切换按钮组 (点击同时自适应调整 Y 轴与 X 轴)
        updatemenus=[
            dict(
                type="buttons",
                direction="right",
                x=0.0,
                y=1.17,
                xanchor="left",
                yanchor="bottom",
                bgcolor="#f5f6fa",
                bordercolor="#dcdde1",
                borderwidth=1,
                font=dict(color="#2f3542", size=11, family="sans-serif"),
                buttons=updatemenu_buttons
            )
        ]
    )

    # 关联底部滑块
    fig.update_xaxes(
        rangeslider=dict(visible=True, thickness=0.035, bgcolor="#f1f2f6"),
        range=[initial_x_start.strftime('%Y-%m-%d'), end_str],
        row=4, col=1
    )

    # 🌟 优化项 2 (初始加载自适应): 将 Y 轴初始化为该时间窗口切片的精准极值区间 (拒绝留白)
    fig.update_yaxes(
        range=[initial_y_p_min, initial_y_p_max],
        title_text="价格 (USD)", tickprefix="$",
        gridcolor="#f1f2f6", zerolinecolor="#dcdde1",
        row=1, col=1
    )
    fig.update_yaxes(title_text="Gap 偏离度", gridcolor="#f1f2f6", zerolinecolor="#dcdde1", row=2, col=1)
    fig.update_yaxes(title_text="雷达评分", range=[0, 105], gridcolor="#f1f2f6", zerolinecolor="#dcdde1", row=3, col=1)
    fig.update_yaxes(
        range=[initial_y_eq_min, initial_y_eq_max],
        title_text="账户净值", tickprefix="$",
        gridcolor="#f1f2f6", zerolinecolor="#dcdde1",
        row=4, col=1
    )

    return fig
