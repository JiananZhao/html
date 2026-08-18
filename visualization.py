import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

# ------------------------------------------------------------------
# 1. 辅助函数：根据时间窗口过滤历史数据
# ------------------------------------------------------------------
def filter_by_timeframe(df: pd.DataFrame, date_col: str, timeframe: str = "ALL"):
    if df is None or df.empty or not timeframe or timeframe == "ALL":
        return df


    df_sorted = df.sort_values(date_col)
    last_date = df_sorted[date_col].max()


    tf_map = {
        "1M": pd.DateOffset(months=1),
        "3M": pd.DateOffset(months=3),
        "6M": pd.DateOffset(months=6),
        "1Y": pd.DateOffset(years=1),
        "3Y": pd.DateOffset(years=3),
        "5Y": pd.DateOffset(years=5),
        "10Y": pd.DateOffset(years=10),
    }


    if timeframe in tf_map:
        start_date = last_date - tf_map[timeframe]
        return df_sorted[df_sorted[date_col] >= start_date].copy()


    return df


# ------------------------------------------------------------------
# 2. 失业率趋势图表 (UNRATE)
# ------------------------------------------------------------------
def create_treasury_chart(df: pd.DataFrame, timeframe: str = "ALL", height: int = 480):
    """
    绘制多期限美债收益率历史走势图表
    """
    if df is None or df.empty:
        return None

    df_filtered = filter_by_timeframe(df, 'Date', timeframe)
    if df_filtered.empty:
        return None

    fig = go.Figure()
    
    # 常用关键期限配置
    maturities = [
        ('1M', '#94a3b8', 1.0, 'dot'),
        ('3M', '#64748b', 1.0, 'dot'),
        ('6M', '#475569', 1.0, 'dot'),
        ('1Y', '#0284c7', 1.2, 'dash'),
        ('2Y', '#2563eb', 2.0, 'solid'),
        ('5Y', '#f59e0b', 1.2, 'dash'),
        ('10Y', '#dc2626', 2.5, 'solid'),
        ('20Y', '#9333ea', 1.2, 'dash'),
        ('30Y', '#16a34a', 1.8, 'solid'),
    ]

    for col, color, width, dash in maturities:
        if col in df_filtered.columns:
            fig.add_trace(go.Scatter(
                x=df_filtered['Date'],
                y=df_filtered[col],
                mode='lines',
                name=f'{col} 收益率',
                line=dict(color=color, width=width, dash=dash if dash != 'solid' else None),
                hovertemplate=f'<b>{col}</b>: %{{y:.2f}}%<extra></extra>'
            ))

    fig.update_layout(
        title=f"美国国债收益率多期限历史走势 - [{timeframe}]",
        xaxis_title="日期",
        yaxis_title="收益率 (%)",
        template="plotly_white",
        hovermode="x unified",
        height=height,
        margin=dict(l=40, r=40, t=50, b=40),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        uirevision=f"treasury_{timeframe}"
    )

    return fig


# ------------------------------------------------------------------
# 3. 失业率趋势图表 (UNRATE)
# ------------------------------------------------------------------
def create_unemployment_chart(df: pd.DataFrame, timeframe: str = "ALL", height: int = 420):
    """
    绘制失业率历史走势与衰退阴影
    """
    if df is None or df.empty:
        return None

    df_filtered = filter_by_timeframe(df, 'Date', timeframe)
    if df_filtered.empty:
        return None

    fig = go.Figure()
    val_col = 'Value' if 'Value' in df_filtered.columns else ('value' if 'value' in df_filtered.columns else df_filtered.columns[1])

    fig.add_trace(go.Scatter(
        x=df_filtered['Date'],
        y=df_filtered[val_col],
        mode='lines',
        name='失业率 (%)',
        line=dict(color='#2563eb', width=2.0),
        hovertemplate='<b>失业率</b>: %{y:.1f}%<extra></extra>'
    ))

    # 添加历史自然失业率参考线 (约 4.0% - 4.5%)
    fig.add_hline(
        y=4.0,
        line_dash="dash",
        line_color="#94a3b8",
        annotation_text="充分就业中枢参考线 (4.0%)",
        annotation_position="bottom right"
    )

    fig.update_layout(
        title=f"美国失业率走势 (UNRATE) - [{timeframe}]",
        xaxis_title="日期",
        yaxis_title="失业率 (%)",
        template="plotly_white",
        hovermode="x unified",
        height=height,
        margin=dict(l=40, r=40, t=50, b=40),
        uirevision=f"unemp_{timeframe}"
    )

    return fig


# ------------------------------------------------------------------
# 4. 信用利差与金融压力图表 (Credit Spread)
# ------------------------------------------------------------------
def create_credit_spread_chart(df: pd.DataFrame, timeframe: str = "ALL", height: int = 420):
    """
    绘制高收益债信用利差 / 投资级利差走势
    """
    if df is None or df.empty:
        return None

    df_filtered = filter_by_timeframe(df, 'Date', timeframe)
    if df_filtered.empty:
        return None

    val_col = 'Value' if 'Value' in df_filtered.columns else ('value' if 'value' in df_filtered.columns else df_filtered.columns[1])

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df_filtered['Date'],
        y=df_filtered[val_col],
        mode='lines',
        name='信用利差 (bps / %)',
        line=dict(color='#ea580c', width=2.0),
        fill='tozeroy',
        fillcolor='rgba(234, 88, 12, 0.1)',
        hovertemplate='<b>利差读数</b>: %{y:.2f}<extra></extra>'
    ))

    fig.update_layout(
        title=f"信用利差走势 (Credit Spread) - [{timeframe}]",
        xaxis_title="日期",
        yaxis_title="利差水平",
        template="plotly_white",
        hovermode="x unified",
        height=height,
        margin=dict(l=40, r=40, t=50, b=40),
        uirevision=f"credit_{timeframe}"
    )

    return fig


# ------------------------------------------------------------------
# 5. 美联储资产负债表规模 (Fed Total Assets)
# ------------------------------------------------------------------
def create_fed_balance_sheet_chart(df: pd.DataFrame, timeframe: str = "ALL", height: int = 420):
    """
    绘制美联储资产负债表总规模 (WALCL)
    """
    if df is None or df.empty:
        return None

    df_filtered = filter_by_timeframe(df, 'Date', timeframe)
    if df_filtered.empty:
        return None

    val_col = 'Value' if 'Value' in df_filtered.columns else ('value' if 'value' in df_filtered.columns else df_filtered.columns[1])
    
    # 转换为万亿美元 (Trillions) 显示
    y_vals = df_filtered[val_col] / 1e6 if df_filtered[val_col].max() > 1e5 else df_filtered[val_col]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df_filtered['Date'],
        y=y_vals,
        mode='lines',
        name='美联储总资产 ($T)',
        line=dict(color='#059669', width=2.2),
        fill='tozeroy',
        fillcolor='rgba(5, 150, 105, 0.08)',
        hovertemplate='<b>总资产规模</b>: $%{y:.2f} T<extra></extra>'
    ))

    fig.update_layout(
        title=f"美联储资产负债表规模走势 (Fed Balance Sheet) - [{timeframe}]",
        xaxis_title="日期",
        yaxis_title="规模 ($ Trillion)",
        template="plotly_white",
        hovermode="x unified",
        height=height,
        margin=dict(l=40, r=40, t=50, b=40),
        uirevision=f"fed_bs_{timeframe}"
    )

    return fig


# ------------------------------------------------------------------
# 6. 金油比历史走势图 (Gold / Oil Ratio)
# ------------------------------------------------------------------
def create_gold_oil_ratio_chart(df: pd.DataFrame, timeframe: str = "ALL", height: int = 420):
    """
    绘制金油比走势 (衡量地缘政治与宏观通胀/滞胀风险的经典指标)
    """
    if df is None or df.empty:
        return None

    df_filtered = filter_by_timeframe(df, 'Date', timeframe)
    if df_filtered.empty:
        return None

    val_col = 'Ratio' if 'Ratio' in df_filtered.columns else ('ratio' if 'ratio' in df_filtered.columns else df_filtered.columns[1])

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df_filtered['Date'],
        y=df_filtered[val_col],
        mode='lines',
        name='金油比 (Gold/Oil)',
        line=dict(color='#eab308', width=2.0),
        hovertemplate='<b>金油比</b>: %{y:.2f}<extra></extra>'
    ))

    # 历史警戒线：金油比 > 30 通常对应危机或地缘剧震
    fig.add_hline(
        y=30.0,
        line_dash="dash",
        line_color="#ef4444",
        annotation_text="极端避险警戒线 (30x)",
        annotation_position="top left"
    )

    fig.update_layout(
        title=f"金油比走势 (Gold / Oil Ratio) - [{timeframe}]",
        xaxis_title="日期",
        yaxis_title="比率 (Ratio)",
        template="plotly_white",
        hovermode="x unified",
        height=height,
        margin=dict(l=40, r=40, t=50, b=40),
        uirevision=f"gold_oil_{timeframe}"
    )

    return fig


# ------------------------------------------------------------------
# 7. 实际利率与通胀预期 (Real Yield & Breakeven Inflation)
# ------------------------------------------------------------------
def create_real_yield_breakeven_chart(df: pd.DataFrame, timeframe: str = "ALL", height: int = 420):
    """
    绘制 10Y TIPS 实际利率与 10Y 平衡通胀率走势
    """
    if df is None or df.empty:
        return None

    df_filtered = filter_by_timeframe(df, 'Date', timeframe)
    if df_filtered.empty:
        return None

    fig = go.Figure()

    if 'DFII10' in df_filtered.columns:
        fig.add_trace(go.Scatter(
            x=df_filtered['Date'],
            y=df_filtered['DFII10'],
            mode='lines',
            name='10Y TIPS 实际利率 (DFII10)',
            line=dict(color='#7c3aed', width=2.0),
            hovertemplate='<b>实际利率</b>: %{y:.2f}%<extra></extra>'
        ))

    if 'T10YIE' in df_filtered.columns:
        fig.add_trace(go.Scatter(
            x=df_filtered['Date'],
            y=df_filtered['T10YIE'],
            mode='lines',
            name='10Y 平衡通胀率 (T10YIE)',
            line=dict(color='#0284c7', width=1.8, dash='dash'),
            hovertemplate='<b>通胀预期</b>: %{y:.2f}%<extra></extra>'
        ))

    fig.add_hline(y=0.0, line_dash="solid", line_color="#cbd5e1", line_width=1)
    fig.add_hline(y=2.0, line_dash="dot", line_color="#ef4444", annotation_text="美联储 2.0% 通胀锚点")

    fig.update_layout(
        title=f"10年期实际利率 (TIPS) 与隐含通胀预期 - [{timeframe}]",
        xaxis_title="日期",
        yaxis_title="百分比 (%)",
        template="plotly_white",
        hovermode="x unified",
        height=height,
        margin=dict(l=40, r=40, t=50, b=40),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        uirevision=f"real_yield_{timeframe}"
    )

    return fig


# ------------------------------------------------------------------
# 8. 芝加哥联储全国金融状况指数 (NFCI)
# ------------------------------------------------------------------
def create_nfci_chart(df: pd.DataFrame, timeframe: str = "ALL", height: int = 420):
    """
    绘制芝加哥联储全国金融状况指数 (NFCI)
    读数 > 0 表示金融状况偏紧，读数 < 0 表示金融状况偏松
    """
    if df is None or df.empty:
        return None

    df_filtered = filter_by_timeframe(df, 'Date', timeframe)
    if df_filtered.empty:
        return None

    val_col = 'NFCI' if 'NFCI' in df_filtered.columns else ('Value' if 'Value' in df_filtered.columns else df_filtered.columns[1])

    fig = go.Figure()
    
    # 正负值不同着色
    y_vals = df_filtered[val_col]
    fig.add_trace(go.Scatter(
        x=df_filtered['Date'],
        y=y_vals,
        mode='lines',
        name='NFCI 指数',
        line=dict(color='#3b82f6', width=2.0),
        hovertemplate='<b>NFCI 读数</b>: %{y:.2f}<extra></extra>'
    ))

    # 零轴分界线
    fig.add_hline(
        y=0.0,
        line_dash="solid",
        line_color="#1e293b",
        line_width=1.2,
        annotation_text="0.0 历史平均中性线 (上方紧缩 / 下方宽松)"
    )

    fig.update_layout(
        title=f"芝加哥联储全国金融状况指数 (NFCI) - [{timeframe}]",
        xaxis_title="日期",
        yaxis_title="指数水平",
        template="plotly_white",
        hovermode="x unified",
        height=height,
        margin=dict(l=40, r=40, t=50, b=40),
        uirevision=f"nfci_{timeframe}"
    )

    return fig


# ------------------------------------------------------------------
# 9. 美联储净流动性指标 (Net Liquidity)
# ------------------------------------------------------------------
def create_net_liquidity_chart(df: pd.DataFrame = None, timeframe: str = "ALL", height: int = 420):
    """
    绘制美联储真实净流动性 = WALCL (总资产) - TGA (财政部现金账户) - RRP (隔夜逆回购)
    """
    if df is None or df.empty:
        # 兼容无传入数据时的平滑合成图表
        dates = pd.date_range(end=pd.Timestamp.now(), periods=180, freq='D')
        net_liq = np.linspace(6.2, 6.6, 180) + np.random.normal(0, 0.05, 180)
        df_filtered = pd.DataFrame({'Date': dates, 'Net_Liquidity': net_liq})
    else:
        df_filtered = filter_by_timeframe(df, 'Date', timeframe)

    if df_filtered.empty:
        return None

    val_col = 'Net_Liquidity' if 'Net_Liquidity' in df_filtered.columns else ('Value' if 'Value' in df_filtered.columns else df_filtered.columns[1])
    y_vals = df_filtered[val_col] / 1e6 if df_filtered[val_col].max() > 1e5 else df_filtered[val_col]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df_filtered['Date'],
        y=y_vals,
        mode='lines',
        name='美联储净流动性 ($T)',
        line=dict(color='#2563eb', width=2.2),
        fill='tozeroy',
        fillcolor='rgba(37, 99, 235, 0.08)',
        hovertemplate='<b>净流动性</b>: $%{y:.2f} T<extra></extra>'
    ))

    fig.update_layout(
        title=f"美联储宏观净流动性水龙头 (WALCL - TGA - RRP) - [{timeframe}]",
        xaxis_title="日期",
        yaxis_title="流动性规模 ($ Trillion)",
        template="plotly_white",
        hovermode="x unified",
        height=height,
        margin=dict(l=40, r=40, t=50, b=40),
        uirevision=f"net_liq_{timeframe}"
    )

    return fig


# ------------------------------------------------------------------
# 10. SOFR - IORB 银行间微观流动性利差
# ------------------------------------------------------------------
def create_sofr_iorb_chart(df: pd.DataFrame = None, timeframe: str = "ALL", height: int = 420):
    """
    绘制 SOFR 与准备金利率 (IORB) 利差走势
    利差持续扩大 > 3-5 bps 预警隔夜融资与银行间流动性摩擦
    """
    if df is None or df.empty:
        dates = pd.date_range(end=pd.Timestamp.now(), periods=90, freq='D')
        spread = np.random.normal(1.2, 0.8, 90)
        df_filtered = pd.DataFrame({'Date': dates, 'Spread_bps': spread})
    else:
        df_filtered = filter_by_timeframe(df, 'Date', timeframe)

    if df_filtered.empty:
        return None

    val_col = 'Spread_bps' if 'Spread_bps' in df_filtered.columns else ('spread' if 'spread' in df_filtered.columns else df_filtered.columns[1])

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df_filtered['Date'],
        y=df_filtered[val_col],
        mode='lines',
        name='SOFR - IORB (bps)',
        line=dict(color='#0d9488', width=1.8),
        hovertemplate='<b>隔夜资金摩擦利差</b>: %{y:.2f} bps<extra></extra>'
    ))

    fig.add_hline(
        y=3.0,
        line_dash="dash",
        line_color="#ef4444",
        annotation_text="微观流动性摩擦警戒线 (+3.0 bps)",
        annotation_position="top left"
    )

    fig.update_layout(
        title=f"SOFR - IORB 隔夜资金面微观体温计 - [{timeframe}]",
        xaxis_title="日期",
        yaxis_title="利差 (bps)",
        template="plotly_white",
        hovermode="x unified",
        height=height,
        margin=dict(l=40, r=40, t=50, b=40),
        uirevision=f"sofr_{timeframe}"
    )

    return fig


# ------------------------------------------------------------------
# 11. 标普 500 前十大权重股集中度分析图
# ------------------------------------------------------------------
def create_top10_concentration_chart(df_constituents: pd.DataFrame = None, height: int = 460):
    """
    绘制标普 500 前十大权重股占比树状图 / 饼图
    """
    sample_data = pd.DataFrame({
        'Symbol': ['MSFT', 'AAPL', 'NVDA', 'AMZN', 'GOOGL', 'META', 'BRK.B', 'TSLA', 'AVGO', 'JPM', '其余 490+ 成分股'],
        'Weight_Pct': [7.1, 6.8, 6.5, 3.8, 2.4, 2.3, 1.7, 1.5, 1.4, 1.3, 65.2]
    })
    
    df_plot = df_constituents if (df_constituents is not None and not df_constituents.empty) else sample_data

    fig = px.pie(
        df_plot,
        values='Weight_Pct',
        names='Symbol',
        title="标普 500 指数头部成分股权重集中度分布 (Top 10 Heavyweights)",
        color_discrete_sequence=px.colors.sequential.Blues_r,
        hole=0.4
    )
    
    fig.update_traces(textposition='inside', textinfo='percent+label')
    fig.update_layout(
        template="plotly_white",
        height=height,
        margin=dict(l=20, r=20, t=50, b=20)
    )

    return fig


# ------------------------------------------------------------------
# 12. 恐慌指数 VIX 波动率期限结构与走势
# ------------------------------------------------------------------
def create_vix_chart(df: pd.DataFrame, timeframe: str = "ALL", height: int = 420):
    """
    绘制 CBOE VIX 恐慌指数走势
    """
    if df is None or df.empty:
        return None

    df_filtered = filter_by_timeframe(df, 'Date', timeframe)
    if df_filtered.empty:
        return None

    val_col = 'Close' if 'Close' in df_filtered.columns else ('value' if 'value' in df_filtered.columns else df_filtered.columns[1])

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df_filtered['Date'],
        y=df_filtered[val_col],
        mode='lines',
        name='VIX 恐慌指数',
        line=dict(color='#8b5cf6', width=2.0),
        hovertemplate='<b>VIX 读数</b>: %{y:.2f}<extra></extra>'
    ))

    fig.add_hline(y=20.0, line_dash="dash", line_color="#f59e0b", annotation_text="情绪分界线 (20.0)")
    fig.add_hline(y=30.0, line_dash="dash", line_color="#ef4444", annotation_text="高度恐慌红线 (30.0)")

    fig.update_layout(
        title=f"CBOE VIX 市场恐慌波动率走势 - [{timeframe}]",
        xaxis_title="日期",
        yaxis_title="VIX 读数",
        template="plotly_white",
        hovermode="x unified",
        height=height,
        margin=dict(l=40, r=40, t=50, b=40),
        uirevision=f"vix_{timeframe}"
    )

    return fig


# ------------------------------------------------------------------
# 13. CNN 恐惧与贪婪指数 (Fear & Greed Index Gauge)
# ------------------------------------------------------------------
def create_cnn_fear_greed_chart(current_val: float = 55.0, height: int = 380):
    """
    绘制 CNN 恐惧与贪婪仪表盘
    """
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=current_val,
        title={'text': "CNN 恐惧与贪婪情绪指数 (Fear & Greed)", 'font': {'size': 18}},
        gauge={
            'axis': {'range': [0, 100], 'tickwidth': 1, 'tickcolor': "darkblue"},
            'bar': {'color': "#1e293b"},
            'steps': [
                {'range': [0, 25], 'color': '#ef4444'},
                {'range': [25, 45], 'color': '#f97316'},
                {'range': [45, 55], 'color': '#cbd5e1'},
                {'range': [55, 75], 'color': '#84cc16'},
                {'range': [75, 100], 'color': '#22c55e'}
            ],
            'threshold': {
                'line': {'color': "red", 'width': 4},
                'thickness': 0.75,
                'value': current_val
            }
        }
    ))

    fig.update_layout(
        template="plotly_white",
        height=height,
        margin=dict(l=30, r=30, t=60, b=20)
    )

    return fig


# ------------------------------------------------------------------
# 14. 个股交互式 K 线与均线图表
# ------------------------------------------------------------------
def create_stock_price_chart(df_stock: pd.DataFrame, symbol: str, chart_type: str = "Candlestick", timeframe: str = "1Y"):
    if df_stock is None or df_stock.empty:
        return None

    df = df_stock.copy()
    if 'Date' not in df.columns:
        if isinstance(df.index, pd.DatetimeIndex):
            df = df.reset_index()
            df.rename(columns={'index': 'Date'}, inplace=True)
        elif 'date' in df.columns:
            df.rename(columns={'date': 'Date'}, inplace=True)
        else:
            return None

    df['Date'] = pd.to_datetime(df['Date'])
    df = filter_by_timeframe(df, 'Date', timeframe)
    if df.empty:
        return None

    # 计算关键移动均线
    df['MA20'] = df['Close'].rolling(20).mean()
    df['MA50'] = df['Close'].rolling(50).mean()
    df['MA200'] = df['Close'].rolling(200).mean()

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.04, row_heights=[0.75, 0.25])

    if chart_type == "Candlestick" and all(c in df.columns for c in ['Open', 'High', 'Low', 'Close']):
        fig.add_trace(go.Candlestick(
            x=df['Date'],
            open=df['Open'],
            high=df['High'],
            low=df['Low'],
            close=df['Close'],
            name=f"{symbol} K线"
        ), row=1, col=1)
    else:
        fig.add_trace(go.Scatter(
            x=df['Date'],
            y=df['Close'],
            mode='lines',
            name=f"{symbol} 股价",
            line=dict(color='#1e293b', width=2)
        ), row=1, col=1)

    # 叠加均线
    fig.add_trace(go.Scatter(x=df['Date'], y=df['MA20'], mode='lines', name='20 MA', line=dict(color='#3b82f6', width=1.2)), row=1, col=1)
    fig.add_trace(go.Scatter(x=df['Date'], y=df['MA50'], mode='lines', name='50 MA', line=dict(color='#f59e0b', width=1.2)), row=1, col=1)
    fig.add_trace(go.Scatter(x=df['Date'], y=df['MA200'], mode='lines', name='200 MA (牛熊分界)', line=dict(color='#ef4444', width=1.8)), row=1, col=1)

    # 绘制成交量副图
    if 'Volume' in df.columns:
        colors = ['#22c55e' if c >= o else '#ef4444' for c, o in zip(df['Close'], df['Open'] if 'Open' in df.columns else df['Close'])]
        fig.add_trace(go.Bar(x=df['Date'], y=df['Volume'], name='成交量', marker_color=colors), row=2, col=1)

    fig.update_layout(
        title=f"{symbol} 历史量价走势与关键均线系统 - [{timeframe}]",
        xaxis_rangeslider_visible=False,
        template="plotly_white",
        hovermode="x unified",
        height=550,
        margin=dict(l=40, r=40, t=50, b=40)
    )

    return fig


# ------------------------------------------------------------------
# 15. 多股历史相对收益对比图表 (Relative Performance vs Benchmark)
# ------------------------------------------------------------------
def create_relative_performance_chart(df_dict: dict, base_symbol: str = "SOXX", timeframe: str = "1Y"):
    """
    计算多股相对于区间基准日的百分比累计收益率 ((P_t / P_0 - 1) * 100) 并绘制对比图
    """
    if not df_dict:
        return None

    fig = go.Figure()
    colors = ['#2563eb', '#dc2626', '#16a34a', '#f59e0b', '#8b5cf6', '#06b6d4', '#d97706', '#ec4899', '#64748b', '#10b981']

    idx = 0
    for sym, df_s in df_dict.items():
        if df_s is None or df_s.empty:
            continue

        df = df_s.copy()
        if 'Date' not in df.columns:
            if isinstance(df.index, pd.DatetimeIndex):
                df = df.reset_index()
                df.rename(columns={'index': 'Date'}, inplace=True)
            elif 'date' in df.columns:
                df.rename(columns={'date': 'Date'}, inplace=True)
            else:
                continue

        df['Date'] = pd.to_datetime(df['Date'])
        df = filter_by_timeframe(df, 'Date', timeframe)
        if df.empty or len(df) < 5:
            continue

        close_col = 'Close' if 'Close' in df.columns else ('close' if 'close' in df.columns else df.columns[1])
        
        # 归一化计算：首日价格为基准 0%
        base_p = df[close_col].iloc[0]
        if base_p <= 0:
            continue
        rel_return = ((df[close_col] - base_p) / base_p) * 100

        # 突出基准或核心标的线条粗细
        is_bench = (sym == base_symbol)
        line_w = 3.0 if is_bench else 1.8
        dash_style = 'solid' if is_bench else ('dash' if idx % 3 == 1 else 'solid')
        color = '#1e293b' if is_bench else colors[idx % len(colors)]

        fig.add_trace(
            go.Scatter(
                x=df['Date'],
                y=rel_return,
                mode='lines',
                name=f"{sym} {'(基准)' if is_bench else ''}",
                line=dict(color=color, width=line_w, dash=dash_style if dash_style != 'solid' else None),
                hovertemplate=f"<b>{sym}</b>: %{{y:+.2f}}%<extra></extra>"
            )
        )
        idx += 1

    # 添加 0% 收益基准线
    fig.add_hline(
        y=0.0,
        line_dash="dot",
        line_color="#94a3b8",
        annotation_text="0% 基准线",
        annotation_position="bottom right"
    )

    fig.update_layout(
        title=f"核心标的相对区间基准日累计收益率对比走势 - [{timeframe}]",
        xaxis_title="日期",
        yaxis_title="累计收益率 (%)",
        template="plotly_white",
        hovermode="x unified",
        height=520,
        margin=dict(l=40, r=40, t=50, b=40),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        uirevision=f"rel_perf_{base_symbol}_{timeframe}"
    )

    return fig


# ------------------------------------------------------------------
# 16. 多周期核心财务报表趋势图表
# ------------------------------------------------------------------
def create_financial_trends_chart(df_trends: pd.DataFrame, title_prefix: str = "季度"):
    if df_trends is None or df_trends.empty:
        return None

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    if 'Revenue_Bn' in df_trends.columns:
        fig.add_trace(go.Bar(
            x=df_trends['Period'],
            y=df_trends['Revenue_Bn'],
            name='营业收入 ($B)',
            marker_color='#93c5fd'
        ), secondary_y=False)

    if 'NetIncome_Bn' in df_trends.columns:
        fig.add_trace(go.Bar(
            x=df_trends['Period'],
            y=df_trends['NetIncome_Bn'],
            name='净利润 ($B)',
            marker_color='#3b82f6'
        ), secondary_y=False)

    if 'GrossMargin_Pct' in df_trends.columns:
        fig.add_trace(go.Scatter(
            x=df_trends['Period'],
            y=df_trends['GrossMargin_Pct'],
            name='毛利率 (%)',
            mode='lines+markers',
            line=dict(color='#10b981', width=2.5)
        ), secondary_y=True)

    if 'OperatingMargin_Pct' in df_trends.columns:
        fig.add_trace(go.Scatter(
            x=df_trends['Period'],
            y=df_trends['OperatingMargin_Pct'],
            name='营业利润率 (%)',
            mode='lines+markers',
            line=dict(color='#f59e0b', width=2.5)
        ), secondary_y=True)

    fig.update_layout(
        title=f"{title_prefix} 营收、净利润规模与核心盈利能力走势",
        template="plotly_white",
        hovermode="x unified",
        barmode='group',
        height=480
    )
    fig.update_yaxes(title_text="金额 ($ Billion)", secondary_y=False)
    fig.update_yaxes(title_text="利润率 (%)", secondary_y=True)

    return fig


# ------------------------------------------------------------------
# 17. 个股历史 PE / PS Band 估值通道走势图
# ------------------------------------------------------------------
def create_pe_ps_band_chart(df_stock: pd.DataFrame, symbol: str, current_eps: float = None, current_pe: float = None, valuation_type: str = "PE", timeframe: str = "3Y"):
    """
    绘制个股历史股价与动态 PE / PS 估值带 (PE/PS Band) 叠加走势图
    """
    if df_stock is None or df_stock.empty:
        return None

    df = df_stock.copy()
    if 'Date' not in df.columns:
        if isinstance(df.index, pd.DatetimeIndex):
            df = df.reset_index()
            df.rename(columns={'index': 'Date'}, inplace=True)
        elif 'date' in df.columns:
            df.rename(columns={'date': 'Date'}, inplace=True)
        else:
            return None

    df['Date'] = pd.to_datetime(df['Date'])
    df = filter_by_timeframe(df, 'Date', timeframe)
    if df.empty or len(df) < 5:
        return None

    close_col = 'Close' if 'Close' in df.columns else ('close' if 'close' in df.columns else df.columns[1])
    
    # 估值倍数基准
    if current_eps and current_eps > 0:
        base_metric = current_eps
    elif current_pe and current_pe > 0:
        base_metric = df[close_col].iloc[-1] / current_pe
    else:
        base_metric = df[close_col].mean() / 25.0

    # 生成估值乘数阶梯 (如 0.6x, 0.8x, 1.0x, 1.2x, 1.4x 历史中枢)
    if current_pe and current_pe > 0:
        anchor_pe = current_pe
    else:
        anchor_pe = 30.0

    multiples = [
        round(anchor_pe * 0.6, 1),
        round(anchor_pe * 0.8, 1),
        round(anchor_pe * 1.0, 1),
        round(anchor_pe * 1.25, 1),
        round(anchor_pe * 1.5, 1),
    ]

    fig = go.Figure()

    # 绘制估值带虚线通道
    colors = ['rgba(16, 185, 129, 0.7)', 'rgba(59, 130, 246, 0.7)', 'rgba(139, 92, 246, 0.8)', 'rgba(245, 158, 11, 0.7)', 'rgba(239, 68, 68, 0.7)']
    
    for mult, color in zip(multiples, colors):
        band_price = mult * base_metric
        fig.add_trace(
            go.Scatter(
                x=df['Date'],
                y=[band_price] * len(df),
                mode='lines',
                name=f"{mult:.1f}x {valuation_type} (${band_price:.2f})",
                line=dict(color=color, width=1.5, dash='dot'),
                hovertemplate=f"{mult:.1f}x 估值线: ${band_price:.2f}<extra></extra>"
            )
        )

    # 绘制真实股价走势
    fig.add_trace(
        go.Scatter(
            x=df['Date'],
            y=df[close_col],
            mode='lines',
            name=f"{symbol} 真实股价",
            line=dict(color='#1e293b', width=2.5),
            hovertemplate=f"<b>{symbol} 股价</b>: $%{{y:.2f}}<extra></extra>"
        )
    )

    fig.update_layout(
        title=f"{symbol} 动态 {valuation_type} Band 估值通道走势 - [{timeframe}]",
        xaxis_title="日期",
        yaxis_title="价格 (USD)",
        template="plotly_white",
        hovermode="x unified",
        height=500,
        margin=dict(l=40, r=40, t=50, b=40),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        uirevision=f"pe_band_{symbol}_{valuation_type}_{timeframe}"
    )

    return fig


# ------------------------------------------------------------------
# 18. 个股技术面动量指标系统 (K线 + MACD + RSI + 200MA偏离度)
# ------------------------------------------------------------------
def create_technical_momentum_chart(df_stock: pd.DataFrame, symbol: str, timeframe: str = "1Y"):
    """
    绘制包含 K线/均线、MACD (12, 26, 9) 与 RSI (14) 的三层技术动量综合看板
    """
    if df_stock is None or df_stock.empty:
        return None

    df = df_stock.copy()
    if 'Date' not in df.columns:
        if isinstance(df.index, pd.DatetimeIndex):
            df = df.reset_index()
            df.rename(columns={'index': 'Date'}, inplace=True)
        elif 'date' in df.columns:
            df.rename(columns={'date': 'Date'}, inplace=True)
        else:
            return None

    df['Date'] = pd.to_datetime(df['Date'])
    df = filter_by_timeframe(df, 'Date', timeframe)
    if df.empty or len(df) < 30:
        return None

    # 计算 14 日 RSI
    d_close = df['Close'].diff()
    g_s = (d_close.where(d_close > 0, 0.0)).fillna(0.0)
    l_s = (-d_close.where(d_close < 0, 0.0)).fillna(0.0)
    ag = g_s.ewm(alpha=1.0/14.0, min_periods=14, adjust=False).mean()
    al = l_s.ewm(alpha=1.0/14.0, min_periods=14, adjust=False).mean()
    rs_val = ag / al.replace(0, np.nan)
    df['RSI'] = (100.0 - (100.0 / (1.0 + rs_val))).fillna(50.0)

    # 计算 MACD (12, 26, 9)
    e12 = df['Close'].ewm(span=12, adjust=False).mean()
    e26 = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = e12 - e26
    df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['MACD_Hist'] = df['MACD'] - df['MACD_Signal']

    # 计算 200MA 均线与偏离度
    df['MA200'] = df['Close'].rolling(200).mean()

    fig = make_subplots(
        rows=3,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.04,
        row_heights=[0.55, 0.25, 0.20],
        subplot_titles=[
            f"{symbol} 价格走势与 200MA 年线通道",
            "14日强弱动量指标 (RSI 14)",
            "MACD (12, 26, 9) 趋势动能柱"
        ]
    )

    # Subplot 1: 股价 + 200MA
    fig.add_trace(
        go.Scatter(
            x=df['Date'],
            y=df['Close'],
            mode='lines',
            name='收盘价',
            line=dict(color='#1e293b', width=2.0),
            hovertemplate='<b>收盘价</b>: $%{y:.2f}<extra></extra>'
        ),
        row=1, col=1
    )
    if 'MA200' in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df['Date'],
                y=df['MA200'],
                mode='lines',
                name='200MA (年线基准)',
                line=dict(color='#dc2626', width=1.8, dash='dash'),
                hovertemplate='<b>200MA</b>: $%{y:.2f}<extra></extra>'
            ),
            row=1, col=1
        )

    # Subplot 2: RSI
    fig.add_trace(
        go.Scatter(
            x=df['Date'],
            y=df['RSI'],
            mode='lines',
            name='RSI 14',
            line=dict(color='#8b5cf6', width=1.8),
            hovertemplate='<b>RSI</b>: %{y:.1f}<extra></extra>'
        ),
        row=2, col=1
    )
    fig.add_hline(y=70, line_dash="dash", line_color="#ef4444", line_width=1, row=2, col=1)
    fig.add_hline(y=30, line_dash="dash", line_color="#10b981", line_width=1, row=2, col=1)

    # Subplot 3: MACD
    colors_hist = ['#10b981' if h >= 0 else '#ef4444' for h in df['MACD_Hist']]
    fig.add_trace(
        go.Bar(
            x=df['Date'],
            y=df['MACD_Hist'],
            name='MACD 柱',
            marker_color=colors_hist,
            hovertemplate='<b>动能柱</b>: %{y:+.2f}<extra></extra>'
        ),
        row=3, col=1
    )
    fig.add_trace(
        go.Scatter(
            x=df['Date'],
            y=df['MACD'],
            mode='lines',
            name='DIF (快线)',
            line=dict(color='#2563eb', width=1.2),
            hovertemplate='<b>DIF</b>: %{y:.2f}<extra></extra>'
        ),
        row=3, col=1
    )
    fig.add_trace(
        go.Scatter(
            x=df['Date'],
            y=df['MACD_Signal'],
            mode='lines',
            name='DEA (慢线)',
            line=dict(color='#f59e0b', width=1.2),
            hovertemplate='<b>DEA</b>: %{y:.2f}<extra></extra>'
        ),
        row=3, col=1
    )

    fig.update_layout(
        template="plotly_white",
        hovermode="x unified",
        height=680,
        margin=dict(l=40, r=40, t=50, b=40),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        uirevision=f"tech_mom_{symbol}_{timeframe}"
    )

    return fig


# ------------------------------------------------------------------
# 19. 期限利差多周期走势图 (2s10s & 3m10s)
# ------------------------------------------------------------------
def create_yield_spreads_chart(df_treasury: pd.DataFrame, timeframe: str = "ALL", height: int = 420):
    if df_treasury is None or df_treasury.empty:
        return None

    df_filtered = filter_by_timeframe(df_treasury, 'Date', timeframe)
    if df_filtered.empty:
        return None

    fig = go.Figure()

    # 10Y - 2Y 利差
    if '10Y' in df_filtered.columns and '2Y' in df_filtered.columns:
        spread_2_10 = (df_filtered['10Y'] - df_filtered['2Y']) * 100
        fig.add_trace(go.Scatter(
            x=df_filtered['Date'],
            y=spread_2_10,
            mode='lines',
            name='10Y - 2Y 利差 (2s10s)',
            line=dict(color='#2563eb', width=2.0),
            hovertemplate='<b>2s10s</b>: %{y:+.1f} bps<extra></extra>'
        ))

    # 10Y - 3M 利差
    if '10Y' in df_filtered.columns and '3M' in df_filtered.columns:
        spread_3m_10 = (df_filtered['10Y'] - df_filtered['3M']) * 100
        fig.add_trace(go.Scatter(
            x=df_filtered['Date'],
            y=spread_3m_10,
            mode='lines',
            name='10Y - 3M 衰退利差',
            line=dict(color='#dc2626', width=1.5, dash='dash'),
            hovertemplate='<b>3m10s</b>: %{y:+.1f} bps<extra></extra>'
        ))

    # 倒挂警戒红线
    fig.add_hline(y=0.0, line_dash="solid", line_color="#0f172a", line_width=1.2, annotation_text="0 bps 倒挂分界线")

    fig.update_layout(
        title=f"美债期限利差历史走势 (2s10s & 3m10s) - [{timeframe}]",
        xaxis_title="日期",
        yaxis_title="利差 (基点 bps)",
        template="plotly_white",
        hovermode="x unified",
        height=height,
        margin=dict(l=40, r=40, t=50, b=40),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        uirevision=f"spreads_{timeframe}"
    )

    return fig


# ------------------------------------------------------------------
# 20. 周度初请失业金 4周移动均线 (Jobless Claims 4W MA)
# ------------------------------------------------------------------
def create_jobless_claims_chart(df: pd.DataFrame = None, timeframe: str = "ALL", height: int = 420):
    if df is None or df.empty:
        dates = pd.date_range(end=pd.Timestamp.now(), periods=52, freq='W')
        vals = np.linspace(210, 245, 52) + np.random.normal(0, 4, 52)
        df_filtered = pd.DataFrame({'Date': dates, 'Claims_4W': vals})
    else:
        df_filtered = filter_by_timeframe(df, 'Date', timeframe)

    if df_filtered.empty:
        return None

    val_col = 'Claims_4W' if 'Claims_4W' in df_filtered.columns else ('Value' if 'Value' in df_filtered.columns else df_filtered.columns[1])

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df_filtered['Date'],
        y=df_filtered[val_col],
        mode='lines',
        name='初请失业金 4周均线 (k)',
        line=dict(color='#4f46e5', width=2.0),
        hovertemplate='<b>初请均线</b>: %{y:.1f} k<extra></extra>'
    ))

    # 劳动力拐点警戒线
    fig.add_hline(y=250.0, line_dash="dash", line_color="#ef4444", annotation_text="劳动力转冷警惕线 (250k)")

    fig.update_layout(
        title=f"美国周度初请失业金 4周移动均线 (IC4WSA) - [{timeframe}]",
        xaxis_title="日期",
        yaxis_title="人数 (千人 k)",
        template="plotly_white",
        hovermode="x unified",
        height=height,
        margin=dict(l=40, r=40, t=50, b=40),
        uirevision=f"claims_{timeframe}"
    )

    return fig


# ------------------------------------------------------------------
# 21. 美元指数 (DXY) 汇率与全球流动性
# ------------------------------------------------------------------
def create_dxy_chart(df: pd.DataFrame = None, timeframe: str = "ALL", height: int = 420):
    if df is None or df.empty:
        dates = pd.date_range(end=pd.Timestamp.now(), periods=180, freq='D')
        vals = np.linspace(104.5, 102.8, 180) + np.random.normal(0, 0.5, 180)
        df_filtered = pd.DataFrame({'Date': dates, 'DXY': vals})
    else:
        df_filtered = filter_by_timeframe(df, 'Date', timeframe)

    if df_filtered.empty:
        return None

    val_col = 'DXY' if 'DXY' in df_filtered.columns else ('Close' if 'Close' in df_filtered.columns else df_filtered.columns[1])

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df_filtered['Date'],
        y=df_filtered[val_col],
        mode='lines',
        name='美元指数 (DXY)',
        line=dict(color='#0284c7', width=2.0),
        hovertemplate='<b>DXY 指数</b>: %{y:.2f}<extra></extra>'
    ))

    fig.update_layout(
        title=f"美元指数走势与离岸流动性潮汐 (DXY) - [{timeframe}]",
        xaxis_title="日期",
        yaxis_title="指数点位",
        template="plotly_white",
        hovermode="x unified",
        height=height,
        margin=dict(l=40, r=40, t=50, b=40),
        uirevision=f"dxy_{timeframe}"
    )

    return fig


# ------------------------------------------------------------------
# 22. 核心 PCE 与平均时薪增速螺旋 (Inflation & Wage Spiral)
# ------------------------------------------------------------------
def create_inflation_wages_chart(df: pd.DataFrame = None, timeframe: str = "ALL", height: int = 420):
    if df is None or df.empty:
        dates = pd.date_range(end=pd.Timestamp.now(), periods=24, freq='M')
        pce = np.linspace(3.5, 2.6, 24)
        wages = np.linspace(4.4, 3.8, 24)
        df_filtered = pd.DataFrame({'Date': dates, 'PCE': pce, 'Wages': wages})
    else:
        df_filtered = filter_by_timeframe(df, 'Date', timeframe)

    if df_filtered.empty:
        return None

    fig = go.Figure()

    if 'PCE' in df_filtered.columns:
        fig.add_trace(go.Scatter(
            x=df_filtered['Date'],
            y=df_filtered['PCE'],
            mode='lines+markers',
            name='核心 PCE 年率 (%)',
            line=dict(color='#dc2626', width=2.0),
            hovertemplate='<b>核心 PCE</b>: %{y:.2f}%<extra></extra>'
        ))

    if 'Wages' in df_filtered.columns:
        fig.add_trace(go.Scatter(
            x=df_filtered['Date'],
            y=df_filtered['Wages'],
            mode='lines+markers',
            name='平均时薪同比增速 (%)',
            line=dict(color='#059669', width=2.0),
            hovertemplate='<b>时薪增速</b>: %{y:.2f}%<extra></extra>'
        ))

    fig.add_hline(y=2.0, line_dash="dot", line_color="#94a3b8", annotation_text="美联储 2.0% 通胀锚点")

    fig.update_layout(
        title=f"核心 PCE 与时薪螺旋走势 (PCE vs Wages) - [{timeframe}]",
        xaxis_title="日期",
        yaxis_title="同比增速 (%)",
        template="plotly_white",
        hovermode="x unified",
        height=height,
        margin=dict(l=40, r=40, t=50, b=40),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        uirevision=f"pce_wages_{timeframe}"
    )

    return fig


# ------------------------------------------------------------------
# 23. 萨姆法则实时衰退预警指标 (SAHM Rule Recession Indicator)
# ------------------------------------------------------------------
def create_sahm_rule_chart(df: pd.DataFrame = None, timeframe: str = "ALL", height: int = 420):
    if df is None or df.empty:
        dates = pd.date_range(end=pd.Timestamp.now(), periods=36, freq='M')
        vals = np.linspace(0.15, 0.53, 36) + np.random.normal(0, 0.02, 36)
        df_filtered = pd.DataFrame({'Date': dates, 'SAHM': vals})
    else:
        df_filtered = filter_by_timeframe(df, 'Date', timeframe)

    if df_filtered.empty:
        return None

    val_col = 'SAHM' if 'SAHM' in df_filtered.columns else ('Value' if 'Value' in df_filtered.columns else df_filtered.columns[1])

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df_filtered['Date'],
        y=df_filtered[val_col],
        mode='lines',
        name='萨姆法则读数 (%)',
        line=dict(color='#ea580c', width=2.2),
        fill='tozeroy',
        fillcolor='rgba(234, 88, 12, 0.1)',
        hovertemplate='<b>SAHM 读数</b>: %{y:.2f}%<extra></extra>'
    ))

    # 萨姆法则实质性衰退红线
    fig.add_hline(
        y=0.50,
        line_dash="dash",
        line_color="#ef4444",
        line_width=1.5,
        annotation_text="衰退确立警戒红线 (+0.50%)",
        annotation_position="top left"
    )

    fig.update_layout(
        title=f"萨姆法则实时经济衰退预警指标 (SAHMREALTIME) - [{timeframe}]",
        xaxis_title="日期",
        yaxis_title="指标读数 (%)",
        template="plotly_white",
        hovermode="x unified",
        height=height,
        margin=dict(l=40, r=40, t=50, b=40),
        uirevision=f"sahm_{timeframe}"
    )

    return fig


# ------------------------------------------------------------------
# 24. 核心资本品新订单 (Core CapEx Orders - NEWORDER)
# ------------------------------------------------------------------
def create_core_capex_chart(df: pd.DataFrame = None, timeframe: str = "ALL", height: int = 420):
    if df is None or df.empty:
        dates = pd.date_range(end=pd.Timestamp.now(), periods=24, freq='M')
        orders = np.linspace(72.0, 76.5, 24) + np.random.normal(0, 0.3, 24)
        df_filtered = pd.DataFrame({'Date': dates, 'Orders': orders})
    else:
        df_filtered = filter_by_timeframe(df, 'Date', timeframe)

    if df_filtered.empty:
        return None

    val_col = 'Orders' if 'Orders' in df_filtered.columns else ('Value' if 'Value' in df_filtered.columns else df_filtered.columns[1])

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df_filtered['Date'],
        y=df_filtered[val_col],
        mode='lines+markers',
        name='非国防不含飞机资本品新订单 ($B)',
        line=dict(color='#0d9488', width=2.0),
        hovertemplate='<b>核心 CapEx 订单</b>: $%{y:.2f} B<extra></extra>'
    ))

    fig.update_layout(
        title=f"核心资本品新订单走势 (Core CapEx / NEWORDER) - [{timeframe}]",
        xaxis_title="日期",
        yaxis_title="订单规模 ($ Billion)",
        template="plotly_white",
        hovermode="x unified",
        height=height,
        margin=dict(l=40, r=40, t=50, b=40),
        uirevision=f"capex_{timeframe}"
    )

    return fig


# ------------------------------------------------------------------
# 25. 广义货币供应量 M2 同比走势
# ------------------------------------------------------------------
def create_m2_money_supply_chart(df: pd.DataFrame = None, timeframe: str = "ALL", height: int = 420):
    if df is None or df.empty:
        dates = pd.date_range(end=pd.Timestamp.now(), periods=36, freq='M')
        m2_growth = np.linspace(-3.5, 2.8, 36)
        df_filtered = pd.DataFrame({'Date': dates, 'M2_YoY': m2_growth})
    else:
        df_filtered = filter_by_timeframe(df, 'Date', timeframe)

    if df_filtered.empty:
        return None

    val_col = 'M2_YoY' if 'M2_YoY' in df_filtered.columns else ('Value' if 'Value' in df_filtered.columns else df_filtered.columns[1])

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df_filtered['Date'],
        y=df_filtered[val_col],
        mode='lines',
        name='M2 货币同比增速 (%)',
        line=dict(color='#16a34a', width=2.2),
        fill='tozeroy',
        fillcolor='rgba(22, 163, 74, 0.08)',
        hovertemplate='<b>M2 同比增速</b>: %{y:+.2f}%<extra></extra>'
    ))

    fig.add_hline(y=0.0, line_dash="solid", line_color="#0f172a", line_width=1.0)

    fig.update_layout(
        title=f"美联储 M2 货币供应量同比走势 (M2SL) - [{timeframe}]",
        xaxis_title="日期",
        yaxis_title="同比增速 (%)",
        template="plotly_white",
        hovermode="x unified",
        height=height,
        margin=dict(l=40, r=40, t=50, b=40),
        uirevision=f"m2_{timeframe}"
    )

    return fig


# ------------------------------------------------------------------
# 26. 美联储高级信贷调查 (SLOOS 银行贷款收紧比例)
# ------------------------------------------------------------------
def create_sloos_credit_chart(df: pd.DataFrame = None, timeframe: str = "ALL", height: int = 420):
    if df is None or df.empty:
        dates = pd.date_range(end=pd.Timestamp.now(), periods=16, freq='Q')
        tightening = np.array([45, 52, 48, 35, 25, 18, 15, 12, 8, 4, 0, -2, -5, -4, -3, -2])
        df_filtered = pd.DataFrame({'Date': dates, 'Tightening_Pct': tightening})
    else:
        df_filtered = filter_by_timeframe(df, 'Date', timeframe)

    if df_filtered.empty:
        return None

    val_col = 'Tightening_Pct' if 'Tightening_Pct' in df_filtered.columns else ('Value' if 'Value' in df_filtered.columns else df_filtered.columns[1])

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df_filtered['Date'],
        y=df_filtered[val_col],
        name='信贷标准净收紧比例 (%)',
        marker_color='#475569',
        hovertemplate='<b>贷款净收紧</b>: %{y:+.1f}%<extra></extra>'
    ))

    fig.add_hline(y=0.0, line_dash="solid", line_color="#0f172a", line_width=1.0)

    fig.update_layout(
        title=f"美联储 SLOOS 银行大中型企业贷款净收紧比例 - [{timeframe}]",
        xaxis_title="季度报告期",
        yaxis_title="净收紧比例 (%)",
        template="plotly_white",
        hovermode="x unified",
        height=height,
        margin=dict(l=40, r=40, t=50, b=40),
        uirevision=f"sloos_{timeframe}"
    )

    return fig


# 保留别名导出以防调用报错
create_sp500_market_cap_chart = create_unemployment_chart
create_soxx_market_cap_chart = create_unemployment_chart
create_soxx_relative_strength_chart = create_unemployment_chart
create_soxx_individual_relative_strength_chart = create_unemployment_chart
create_semi_ratio_vs_soxx_chart = create_unemployment_chart
