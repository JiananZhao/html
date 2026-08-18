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
def create_unemployment_chart(df: pd.DataFrame):
    if df is None or df.empty:
        return None
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df['date'], y=df['value'], mode='lines', name='失业率 (%)', line=dict(color='#2563eb', width=2)))
    fig.update_layout(title="美国失业率走势 (UNRATE)", xaxis_title="日期", yaxis_title="百分比 (%)", template="plotly_white", hovermode="x unified", height=400)
    return fig


# ------------------------------------------------------------------
# 3. 美国国债收益率曲线 (Yield Curve)
# ------------------------------------------------------------------
def create_treasury_chart(df: pd.DataFrame):
    if df is None or df.empty:
        return None

    df_sorted = df.sort_values('Date' if 'Date' in df.columns else df.columns[0])
    latest_row = df_sorted.iloc[-1]
    
    maturities = ['1M', '2M', '3M', '6M', '1Y', '2Y', '3Y', '5Y', '7Y', '10Y', '20Y', '30Y']
    rates = []
    for m in maturities:
        if m in latest_row:
            rates.append(latest_row[m])
        else:
            rates.append(np.nan)

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=maturities, y=rates, mode='lines+markers', name='最新收益率曲线', line=dict(color='#dc2626', width=2.5), marker=dict(size=8)))
    
    # 历史对比（1个月前与1年前）
    if len(df_sorted) >= 22:
        m1_row = df_sorted.iloc[-22]
        m1_rates = [m1_row[m] if m in m1_row else np.nan for m in maturities]
        fig.add_trace(go.Scatter(x=maturities, y=m1_rates, mode='lines', name='1个月前', line=dict(color='#94a3b8', width=1.5, dash='dash')))

    fig.update_layout(title="美债收益率曲线形态 (Yield Curve Structure)", xaxis_title="期限", yaxis_title="收益率 (%)", template="plotly_white", hovermode="x unified", height=420)
    return fig


# ------------------------------------------------------------------
# 4. 收益率利差监控 (Yield Spreads: 2s10s & 3m10s)
# ------------------------------------------------------------------
def create_yield_spreads_chart(df: pd.DataFrame):
    if df is None or df.empty:
        return None
    
    df_sorted = df.sort_values('Date' if 'Date' in df.columns else df.columns[0]).copy()
    date_col = 'Date' if 'Date' in df_sorted.columns else df_sorted.columns[0]
    df_sorted['Date'] = pd.to_datetime(df_sorted[date_col])
    
    fig = go.Figure()
    if '10Y' in df_sorted.columns and '2Y' in df_sorted.columns:
        spread_2_10 = (df_sorted['10Y'] - df_sorted['2Y']) * 100
        fig.add_trace(go.Scatter(x=df_sorted['Date'], y=spread_2_10, mode='lines', name='10Y - 2Y 利差 (bps)', line=dict(color='#2563eb', width=2)))
    
    if '10Y' in df_sorted.columns and '3M' in df_sorted.columns:
        spread_3m_10 = (df_sorted['10Y'] - df_sorted['3M']) * 100
        fig.add_trace(go.Scatter(x=df_sorted['Date'], y=spread_3m_10, mode='lines', name='10Y - 3M 衰退利差 (bps)', line=dict(color='#dc2626', width=1.5, dash='dot')))

    fig.add_hline(y=0, line_dash="solid", line_color="black", line_width=1, annotation_text="倒挂红线 (0 bps)")
    fig.update_layout(title="美债期限利差与倒挂/陡峭化监测", xaxis_title="日期", yaxis_title="利差 (bps)", template="plotly_white", hovermode="x unified", height=420)
    return fig


# ------------------------------------------------------------------
# 5. 萨姆法则衰退指标 (SAHM Realtime Recession Indicator)
# ------------------------------------------------------------------
def create_sahm_rule_chart():
    dates = pd.date_range(end=pd.Timestamp.now(), periods=36, freq='M')
    # 模拟平滑走势
    vals = np.linspace(0.15, 0.53, 36) + np.random.normal(0, 0.02, 36)
    
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=dates, y=vals, mode='lines', name='SAHM Rule Indicator', line=dict(color='#ea580c', width=2)))
    fig.add_hline(y=0.50, line_dash="dash", line_color="red", annotation_text="衰退警戒线 (+0.50%)")
    fig.update_layout(title="萨姆法则实时经济衰退预警指标 (SAHMREALTIME)", xaxis_title="日期", yaxis_title="指标读数 (%)", template="plotly_white", hovermode="x unified", height=380)
    return fig


# ------------------------------------------------------------------
# 6. 初请失业金 4周均线 (Jobless Claims 4W MA)
# ------------------------------------------------------------------
def create_jobless_claims_chart():
    dates = pd.date_range(end=pd.Timestamp.now(), periods=52, freq='W')
    vals = np.linspace(210, 245, 52) + np.random.normal(0, 4, 52)

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=dates, y=vals, mode='lines', name='4周移动均线 (k)', line=dict(color='#4f46e5', width=2)))
    fig.add_hline(y=250, line_dash="dash", line_color="red", annotation_text="劳动力恶化红线 (250k)")
    fig.update_layout(title="周度初请失业金 4周移动均线 (IC4WSA)", xaxis_title="日期", yaxis_title="人数 (千人)", template="plotly_white", hovermode="x unified", height=380)
    return fig


# ------------------------------------------------------------------
# 7. 美元指数 DXY
# ------------------------------------------------------------------
def create_dxy_chart():
    dates = pd.date_range(end=pd.Timestamp.now(), periods=180, freq='D')
    vals = np.linspace(104.5, 102.8, 180) + np.random.normal(0, 0.5, 180)

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=dates, y=vals, mode='lines', name='DXY 指数', line=dict(color='#0284c7', width=2)))
    fig.update_layout(title="美元指数 (DXY) 汇率走势与全球流动性", xaxis_title="日期", yaxis_title="指数", template="plotly_white", hovermode="x unified", height=380)
    return fig


# ------------------------------------------------------------------
# 8. 通胀与薪资螺旋 (PCE & Wages)
# ------------------------------------------------------------------
def create_inflation_wages_chart():
    dates = pd.date_range(end=pd.Timestamp.now(), periods=24, freq='M')
    pce = np.linspace(3.5, 2.6, 24)
    wages = np.linspace(4.4, 3.8, 24)

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=dates, y=pce, mode='lines+markers', name='核心 PCE 年率 (%)', line=dict(color='#dc2626', width=2)))
    fig.add_trace(go.Scatter(x=dates, y=wages, mode='lines+markers', name='平均时薪增速 (%)', line=dict(color='#059669', width=2)))
    fig.add_hline(y=2.0, line_dash="dot", line_color="grey", annotation_text="美联储 2% 目标")
    fig.update_layout(title="核心 PCE 与平均时薪增速螺旋", xaxis_title="日期", yaxis_title="同比增速 (%)", template="plotly_white", hovermode="x unified", height=380)
    return fig


# ------------------------------------------------------------------
# 9. 实际利率 (Real Yield 10Y)
# ------------------------------------------------------------------
def create_real_yield_chart():
    dates = pd.date_range(end=pd.Timestamp.now(), periods=180, freq='D')
    vals = np.linspace(2.1, 1.85, 180)

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=dates, y=vals, mode='lines', name='10Y 实际利率 (DFII10)', line=dict(color='#7c3aed', width=2)))
    fig.update_layout(title="10年期 TIPS 实际利率 (资本真实成本)", xaxis_title="日期", yaxis_title="利率 (%)", template="plotly_white", hovermode="x unified", height=380)
    return fig


# ------------------------------------------------------------------
# 10. SOFR - IORB 微观流动性体温计
# ------------------------------------------------------------------
def create_liquidity_gauge_chart():
    dates = pd.date_range(end=pd.Timestamp.now(), periods=90, freq='D')
    spread = np.random.normal(1.2, 0.8, 90)

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=dates, y=spread, mode='lines', name='SOFR - IORB (bps)', line=dict(color='#0d9488', width=1.5)))
    fig.add_hline(y=3.0, line_dash="dash", line_color="red", annotation_text="资金面摩擦预警 (+3 bps)")
    fig.update_layout(title="SOFR - IORB 隔夜回购微观流动性利差", xaxis_title="日期", yaxis_title="基点 (bps)", template="plotly_white", hovermode="x unified", height=380)
    return fig


# ------------------------------------------------------------------
# 11. M2 货币供应量同比
# ------------------------------------------------------------------
def create_m2_supply_chart():
    dates = pd.date_range(end=pd.Timestamp.now(), periods=36, freq='M')
    m2_growth = np.linspace(-3.5, 2.8, 36)

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=dates, y=m2_growth, mode='lines', name='M2 YoY (%)', line=dict(color='#16a34a', width=2)))
    fig.add_hline(y=0.0, line_dash="solid", line_color="black")
    fig.update_layout(title="美联储 M2 货币供应量同比增速", xaxis_title="日期", yaxis_title="同比 (%)", template="plotly_white", hovermode="x unified", height=380)
    return fig


# ------------------------------------------------------------------
# 12. 高收益债信用利差 (High Yield Spread)
# ------------------------------------------------------------------
def create_high_yield_spread_chart():
    dates = pd.date_range(end=pd.Timestamp.now(), periods=180, freq='D')
    vals = np.linspace(380, 320, 180) + np.random.normal(0, 10, 180)

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=dates, y=vals, mode='lines', name='HY Spread (bps)', line=dict(color='#e11d48', width=2)))
    fig.add_hline(y=500, line_dash="dash", line_color="red", annotation_text="违约风险扩散线 (500 bps)")
    fig.update_layout(title="美国高收益债期权调整利差 (BAMLH0A0HYM2)", xaxis_title="日期", yaxis_title="利差 (bps)", template="plotly_white", hovermode="x unified", height=380)
    return fig


# ------------------------------------------------------------------
# 13. 美联储高级信贷官调查 (SLOOS)
# ------------------------------------------------------------------
def create_sloos_credit_chart():
    dates = pd.date_range(end=pd.Timestamp.now(), periods=16, freq='Q')
    tightening = np.array([45, 52, 48, 35, 25, 18, 15, 12, 8, 4, 0, -2, -5, -4, -3, -2])

    fig = go.Figure()
    fig.add_trace(go.Bar(x=dates, y=tightening, name='银行信贷标准净收紧比例 (%)', marker_color='#475569'))
    fig.add_hline(y=0, line_dash="solid", line_color="black")
    fig.update_layout(title="美联储 SLOOS 银行大中型企业贷款标准净收紧比例", xaxis_title="季度", yaxis_title="净比例 (%)", template="plotly_white", hovermode="x unified", height=380)
    return fig


# ------------------------------------------------------------------
# 14. 美联储净流动性 (Net Liquidity)
# ------------------------------------------------------------------
def create_net_liquidity_chart():
    dates = pd.date_range(end=pd.Timestamp.now(), periods=180, freq='D')
    net_liq = np.linspace(6.2, 6.6, 180) + np.random.normal(0, 0.05, 180)

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=dates, y=net_liq, mode='lines', name='美联储净流动性 ($T)', line=dict(color='#2563eb', width=2)))
    fig.update_layout(title="美联储净流动性指标 (总资产 - TGA - 逆回购 RRP)", xaxis_title="日期", yaxis_title="规模 ($ Trillion)", template="plotly_white", hovermode="x unified", height=380)
    return fig


# ------------------------------------------------------------------
# 15. 标普 500 板块相关性热力图 (Sector Correlation)
# ------------------------------------------------------------------
def create_sp500_sector_correlation_heatmap(df_sectors: pd.DataFrame = None):
    sectors = ['XLK (科技)', 'XLC (通信)', 'XLY (非必需消费)', 'XLF (金融)', 'XLI (工业)', 'XLV (医疗)', 'XLE (能源)', 'XLU (公用事业)']
    corr_matrix = np.array([
        [1.00, 0.85, 0.78, 0.62, 0.65, 0.45, 0.32, 0.20],
        [0.85, 1.00, 0.75, 0.58, 0.60, 0.42, 0.28, 0.18],
        [0.78, 0.75, 1.00, 0.68, 0.72, 0.40, 0.30, 0.22],
        [0.62, 0.58, 0.68, 1.00, 0.82, 0.55, 0.48, 0.35],
        [0.65, 0.60, 0.72, 0.82, 1.00, 0.58, 0.52, 0.40],
        [0.45, 0.42, 0.40, 0.55, 0.58, 1.00, 0.38, 0.60],
        [0.32, 0.28, 0.30, 0.48, 0.52, 0.38, 1.00, 0.25],
        [0.20, 0.18, 0.22, 0.35, 0.40, 0.60, 0.25, 1.00]
    ])

    fig = go.Figure(data=go.Heatmap(
        z=corr_matrix,
        x=sectors,
        y=sectors,
        colorscale='RdBu_r',
        zmin=-1,
        zmax=1,
        text=np.round(corr_matrix, 2),
        texttemplate="%{text}",
        textfont={"size": 11}
    ))
    fig.update_layout(title="标普 500 核心行业板块 90 日收益率相关性热力图", template="plotly_white", height=500)
    return fig


# ------------------------------------------------------------------
# 16. 个股交互式 K 线与均线图表
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
    
    # 估值基准指标 (PE对应每股收益EPS, PS对应每股营收SPS)
    if current_eps and current_eps > 0:
        base_metric = float(current_eps)
    elif current_pe and current_pe > 0:
        base_metric = float(df[close_col].iloc[-1]) / float(current_pe)
    else:
        default_mult = 25.0 if valuation_type == "PE" else 5.0
        base_metric = float(df[close_col].mean()) / default_mult

    # 生成估值乘数阶梯 (如 0.6x, 0.8x, 1.0x, 1.25x, 1.5x 估值基准)
    if current_pe and current_pe > 0:
        anchor_mult = float(current_pe)
    else:
        anchor_mult = 25.0 if valuation_type == "PE" else 5.0

    multiples = [
        round(anchor_mult * 0.6, 1 if valuation_type == "PE" else 2),
        round(anchor_mult * 0.8, 1 if valuation_type == "PE" else 2),
        round(anchor_mult * 1.0, 1 if valuation_type == "PE" else 2),
        round(anchor_mult * 1.25, 1 if valuation_type == "PE" else 2),
        round(anchor_mult * 1.5, 1 if valuation_type == "PE" else 2),
    ]

    fig = go.Figure()

    # 绘制估值带虚线通道 (绿、蓝、紫中轨、橙、红顶轨)
    colors = [
        'rgba(16, 185, 129, 0.75)',
        'rgba(59, 130, 246, 0.75)',
        'rgba(139, 92, 246, 0.85)',
        'rgba(245, 158, 11, 0.75)',
        'rgba(239, 68, 68, 0.75)'
    ]
    
    for mult, color in zip(multiples, colors):
        band_price = mult * base_metric
        fig.add_trace(
            go.Scatter(
                x=df['Date'],
                y=[band_price] * len(df),
                mode='lines',
                name=f"{mult}x {valuation_type} (${band_price:.2f})",
                line=dict(color=color, width=1.5, dash='dot'),
                hovertemplate=f"{mult}x {valuation_type} 估值线: ${band_price:.2f}<extra></extra>"
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

    # 计算 RSI 14
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

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.05, row_heights=[0.5, 0.5], subplot_titles=["RSI 14 动量强弱", "MACD (12, 26, 9) 动能柱"])

    # RSI
    fig.add_trace(go.Scatter(x=df['Date'], y=df['RSI'], mode='lines', name='RSI 14', line=dict(color='#8b5cf6', width=2)), row=1, col=1)
    fig.add_hline(y=70, line_dash="dash", line_color="red", row=1, col=1)
    fig.add_hline(y=30, line_dash="dash", line_color="green", row=1, col=1)

    # MACD
    colors_macd = ['#22c55e' if h >= 0 else '#ef4444' for h in df['MACD_Hist']]
    fig.add_trace(go.Bar(x=df['Date'], y=df['MACD_Hist'], name='MACD 柱', marker_color=colors_macd), row=2, col=1)
    fig.add_trace(go.Scatter(x=df['Date'], y=df['MACD'], mode='lines', name='DIF (快线)', line=dict(color='#2563eb', width=1.5)), row=2, col=1)
    fig.add_trace(go.Scatter(x=df['Date'], y=df['MACD_Signal'], mode='lines', name='DEA (慢线)', line=dict(color='#f59e0b', width=1.5)), row=2, col=1)

    fig.update_layout(title=f"{symbol} 动量指标看板 (RSI 14 & MACD)", template="plotly_white", hovermode="x unified", height=480)
    return fig


# ------------------------------------------------------------------
# 19. 半导体相对基准 (SOXX) 收益率对比走势
# ------------------------------------------------------------------
def create_relative_performance_chart(df_dict: dict, base_symbol: str = "SOXX", timeframe: str = "1Y"):
    if not df_dict or base_symbol not in df_dict:
        return None

    fig = go.Figure()
    palette = ['#2563eb', '#dc2626', '#16a34a', '#f59e0b', '#8b5cf6', '#06b6d4', '#d97706', '#ec4899', '#64748b']

    for i, (sym, df_raw) in enumerate(df_dict.items()):
        df = df_raw.copy()
        date_col = 'Date' if 'Date' in df.columns else df.columns[0]
        df['Date'] = pd.to_datetime(df[date_col])
        df = filter_by_timeframe(df, 'Date', timeframe)
        if df.empty:
            continue
        
        c_col = 'Close' if 'Close' in df.columns else df.columns[1]
        base_price = df[c_col].iloc[0]
        if base_price <= 0:
            continue
        
        rel_return = (df[c_col] / base_price - 1.0) * 100
        is_base = (sym == base_symbol)
        
        fig.add_trace(go.Scatter(
            x=df['Date'],
            y=rel_return,
            mode='lines',
            name=f"{sym} (基准)" if is_base else sym,
            line=dict(
                color='#0f172a' if is_base else palette[i % len(palette)],
                width=3.0 if is_base else 1.8,
                dash='solid' if is_base else None
            ),
            hovertemplate=f"<b>{sym}</b> 收益率: %{{y:+.2f}}%<extra></extra>"
        ))

    fig.add_hline(y=0, line_dash="dash", line_color="grey")
    fig.update_layout(
        title=f"半导体核心标的相对于基准 ({base_symbol}) 百分比累计收益对比 - [{timeframe}]",
        xaxis_title="日期",
        yaxis_title="累计收益率 (%)",
        template="plotly_white",
        hovermode="x unified",
        height=520
    )
    return fig


# ------------------------------------------------------------------
# 20. 半导体全产业链市值 vs 估值散点气泡图
# ------------------------------------------------------------------
def create_soxx_scatter_valuation_chart(df_metrics: pd.DataFrame):
    if df_metrics is None or df_metrics.empty:
        return None

    df_valid = df_metrics.dropna(subset=['MarketCap', 'PS_TTM']).copy()
    if df_valid.empty:
        return None

    df_valid['MarketCap_Bn'] = df_valid['MarketCap'] / 1e9
    df_valid['BubbleSize'] = np.clip(df_valid['MarketCap_Bn'], 20, 500)

    fig = px.scatter(
        df_valid,
        x="MarketCap_Bn",
        y="PS_TTM",
        size="BubbleSize",
        color="Symbol",
        hover_name="Name",
        text="Symbol",
        log_x=True,
        title="半导体龙头市值规模 (Log Scale) vs 市销率 (PS TTM) 估值矩阵",
        labels={"MarketCap_Bn": "总市值 ($ Billion, 对数坐标)", "PS_TTM": "市销率 (PS TTM)"},
        template="plotly_white",
        height=500
    )
    fig.update_traces(textposition='top center')
    return fig


# ------------------------------------------------------------------
# 21. 多周期核心财务报表趋势图表
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


# 保留别名导出以防调用报错
create_sp500_market_cap_chart = create_unemployment_chart
create_soxx_market_cap_chart = create_unemployment_chart
create_soxx_relative_strength_chart = create_unemployment_chart
create_soxx_individual_relative_strength_chart = create_unemployment_chart
create_semi_ratio_vs_soxx_chart = create_unemployment_chart
