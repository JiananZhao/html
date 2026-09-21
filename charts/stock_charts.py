from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

from charts.theme import filter_by_timeframe, apply_chart_theme

# ------------------------------------------------------------------
# 1. 个股量化与交互式 K 线 / 均线走势图
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
    col_map = {c: c.capitalize() for c in df.columns if c.lower() in ['open', 'high', 'low', 'close', 'volume']}
    df.rename(columns=col_map, inplace=True)

    if 'Close' in df.columns:
        df['MA20'] = df['Close'].rolling(window=20).mean()
        df['MA50'] = df['Close'].rolling(window=50).mean()
        df['MA200'] = df['Close'].rolling(window=200).mean()

    df = filter_by_timeframe(df, 'Date', timeframe)
    if df.empty:
        return None

    has_volume = 'Volume' in df.columns and (df['Volume'] > 0).any()

    if has_volume:
        fig = make_subplots(
            rows=2, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.03,
            row_heights=[0.75, 0.25],
            subplot_titles=(f"{symbol} 价格与均线系统 (MA20 / MA50 / MA200)", "成交量 (Volume)")
        )
    else:
        fig = make_subplots(rows=1, cols=1)

    has_ohlc = all(col in df.columns for col in ['Open', 'High', 'Low', 'Close'])
    if chart_type == "Candlestick" and has_ohlc:
        fig.add_trace(
            go.Candlestick(
                x=df['Date'],
                open=df['Open'],
                high=df['High'],
                low=df['Low'],
                close=df['Close'],
                name=f"{symbol} K线",
                increasing_line_color='#22c55e',
                decreasing_line_color='#ef4444',
                showlegend=True
            ),
            row=1, col=1
        )
    elif 'Close' in df.columns:
        fig.add_trace(
            go.Scatter(x=df['Date'], y=df['Close'], mode='lines', name=f"{symbol} 收盘价", line=dict(color='#2563eb', width=2)),
            row=1, col=1
        )

    if 'MA20' in df.columns:
        fig.add_trace(go.Scatter(x=df['Date'], y=df['MA20'], mode='lines', name="MA20", line=dict(color='#f59e0b', width=1.5)), row=1, col=1)
    if 'MA50' in df.columns:
        fig.add_trace(go.Scatter(x=df['Date'], y=df['MA50'], mode='lines', name="MA50", line=dict(color='#8b5cf6', width=1.5)), row=1, col=1)
    if 'MA200' in df.columns:
        fig.add_trace(go.Scatter(x=df['Date'], y=df['MA200'], mode='lines', name="MA200", line=dict(color='#ef4444', width=2)), row=1, col=1)

    if has_volume:
        colors = ['#22c55e' if c >= o else '#ef4444' for c, o in zip(df['Close'], df['Open'])] if has_ohlc else '#64748b'
        fig.add_trace(
            go.Bar(x=df['Date'], y=df['Volume'], name="成交量", marker_color=colors, showlegend=False),
            row=2, col=1
        )

    fig.update_layout(
        template="plotly_white",
        height=600,
        hovermode="x unified",
        xaxis_rangeslider_visible=False,
        uirevision=f"stock_price_{symbol}_{timeframe}",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    return fig


# ------------------------------------------------------------------
# 2. 半导体产业链标的相对表现走势图 (Normalized Performance)
# ------------------------------------------------------------------
def create_relative_performance_chart(df_norm: pd.DataFrame, symbols: list, timeframe: str = "1Y"):
    if df_norm is None or df_norm.empty or 'Date' not in df_norm.columns:
        return None
    df = df_norm.copy()
    df['Date'] = pd.to_datetime(df['Date'])
    df = filter_by_timeframe(df, 'Date', timeframe)
    if df.empty:
        return None

    val_cols = [c for c in symbols if c in df.columns]
    if not val_cols:
        return None
    
    first_row = df[val_cols].iloc[0]
    for col in val_cols:
        if first_row[col] > 0:
            df[col] = (df[col] / first_row[col]) * 100.0

    fig = px.line(
        df,
        x='Date',
        y=val_cols,
        title=f"半导体产业链龙头相对表现走势 (基准 = 100) - [{timeframe}]",
        labels={"value": "相对表现 (以区间起点为100)", "Date": "日期", "variable": "标的代码"},
        template="plotly_white"
    )
    fig.add_hline(y=100, line_dash="dash", line_color="gray")
    fig.update_layout(
        height=550,
        hovermode="x unified",
        uirevision=f"semi_rel_{timeframe}",
        legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5)
    )
    return fig


# ------------------------------------------------------------------
# 3. 多期核心财务指标趋势走势图 (Revenue, Margin, FCF)
# ------------------------------------------------------------------
def create_financial_trends_chart(df_stmt: pd.DataFrame, symbol: str = "", period_type: str = "季度"):
    if df_stmt is None or df_stmt.empty:
        return None
    df = df_stmt.copy()

    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=(
            f"营收与利润规模趋势 ($M)",
            f"盈利能力利润率趋势 (%)",
            f"自由现金流与资本开支 ($M)",
            f"研发支出及占比 ($M / %)"
        )
    )

    if 'Revenue ($M)' in df.columns:
        fig.add_trace(go.Bar(x=df['Period'], y=df['Revenue ($M)'], name="总营收 ($M)", marker_color='#3b82f6'), row=1, col=1)
    if 'Net Income ($M)' in df.columns:
        fig.add_trace(go.Scatter(x=df['Period'], y=df['Net Income ($M)'], name="净利润 ($M)", line=dict(color='#22c55e', width=2.5)), row=1, col=1)

    if 'Gross Margin (%)' in df.columns:
        fig.add_trace(go.Scatter(x=df['Period'], y=df['Gross Margin (%)'], name="毛利率 (%)", line=dict(color='#8b5cf6', width=2)), row=1, col=2)
    if 'Operating Margin (%)' in df.columns:
        fig.add_trace(go.Scatter(x=df['Period'], y=df['Operating Margin (%)'], name="营业利润率 (%)", line=dict(color='#f59e0b', width=2)), row=1, col=2)
    if 'Net Margin (%)' in df.columns:
        fig.add_trace(go.Scatter(x=df['Period'], y=df['Net Margin (%)'], name="净利率 (%)", line=dict(color='#10b981', width=2)), row=1, col=2)

    if 'Operating Cash Flow ($M)' in df.columns:
        fig.add_trace(go.Bar(x=df['Period'], y=df['Operating Cash Flow ($M)'], name="经营性现金流 ($M)", marker_color='#60a5fa'), row=2, col=1)
    if 'Free Cash Flow ($M)' in df.columns:
        fig.add_trace(go.Scatter(x=df['Period'], y=df['Free Cash Flow ($M)'], name="自由现金流 ($M)", line=dict(color='#059669', width=2.5)), row=2, col=1)
    if 'CapEx ($M)' in df.columns:
        fig.add_trace(go.Bar(x=df['Period'], y=df['CapEx ($M)'], name="资本开支 ($M)", marker_color='#f87171'), row=2, col=1)

    if 'R&D Expenses ($M)' in df.columns:
        fig.add_trace(go.Bar(x=df['Period'], y=df['R&D Expenses ($M)'], name="研发支出 ($M)", marker_color='#a78bfa'), row=2, col=2)
    if 'R&D / Rev (%)' in df.columns:
        fig.add_trace(go.Scatter(x=df['Period'], y=df['R&D / Rev (%)'], name="研发费用率 (%)", line=dict(color='#ec4899', width=2)), row=2, col=2)

    title_text = f"{symbol} 核心财务趋势走势图 ({period_type})" if symbol else f"核心财务趋势走势图 ({period_type})"
    fig.update_layout(
        template="plotly_white",
        height=650,
        title_text=title_text,
        hovermode="x unified",
        showlegend=True
    )
    return fig


# ------------------------------------------------------------------
# 4. PE / PS Band 动态估值通道图表
# ------------------------------------------------------------------
def create_pe_ps_band_chart(
    df_stock: pd.DataFrame, 
    symbol: str, 
    current_eps: float = None, 
    current_rev_per_share: float = None, 
    timeframe: str = "3Y"
):
    """
    绘制个股历史股价与动态 PE / PS 估值带叠加走势图
    """
    if df_stock is None or df_stock.empty or 'Close' not in df_stock.columns:
        return None

    df = df_stock.copy()
    if 'Date' not in df.columns:
        if isinstance(df.index, pd.DatetimeIndex):
            df = df.reset_index()
            df.rename(columns={'index': 'Date'}, inplace=True)
        elif 'date' in df.columns:
            df.rename(columns={'date': 'Date'}, inplace=True)

    df['Date'] = pd.to_datetime(df['Date'])
    df = filter_by_timeframe(df, 'Date', timeframe)
    if df.empty:
        return None

    is_ps_mode = (current_rev_per_share is not None and current_rev_per_share > 0)
    is_pe_mode = (current_eps is not None and current_eps > 0)

    if not is_pe_mode and not is_ps_mode:
        return None

    val_type = "PS" if is_ps_mode else "PE"
    base_metric = current_rev_per_share if is_ps_mode else current_eps
    
    multiples = [1, 2, 4, 8, 16, 24, 32] if is_ps_mode else [5, 10, 20, 30, 45, 60, 80]
    colors = ['#c300ff', '#0011ff', '#00fff2', '#00ff08', '#fbff00', '#ffb300', '#ff0000']

    fig = go.Figure()

    for mult, color in zip(multiples, colors):
        band_price = base_metric * mult
        fig.add_trace(
            go.Scatter(
                x=df['Date'],
                y=[band_price] * len(df),
                mode='lines',
                name=f"{val_type} {mult}x (${band_price:.1f})",
                line=dict(color=color, dash='dash', width=1.2),
                hoverinfo='skip'
            )
        )

    fig.add_trace(
        go.Scatter(
            x=df['Date'],
            y=df['Close'],
            mode='lines',
            name=f"{symbol} 真实股价",
            line=dict(color='#1e293b', width=2.5),
            hovertemplate=f"<b>{symbol} 股价</b>: $%{{y:.2f}}<extra></extra>"
        )
    )

    fig.update_layout(
        title=f"{symbol} {val_type} 动态估值通道 ({val_type} Band) - [{timeframe}]",
        template="plotly_white",
        height=500,
        hovermode="x unified",
        yaxis_title="价格 ($ USD)",
        uirevision=f"{val_type.lower()}_band_{symbol}_{timeframe}"
    )
    return fig


# ------------------------------------------------------------------
# 5. 技术动量与超买超卖信号图表 (RSI, MACD, Bollinger Bands)
# ------------------------------------------------------------------
def create_technical_momentum_chart(df_stock: pd.DataFrame, symbol: str, timeframe: str = "1Y"):
    if df_stock is None or df_stock.empty or 'Close' not in df_stock.columns:
        return None
    df = df_stock.copy()
    if 'Date' not in df.columns:
        if isinstance(df.index, pd.DatetimeIndex):
            df = df.reset_index()
            df.rename(columns={'index': 'Date'}, inplace=True)
        elif 'date' in df.columns:
            df.rename(columns={'date': 'Date'}, inplace=True)
    df['Date'] = pd.to_datetime(df['Date'])

    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / (loss + 1e-9)
    df['RSI'] = 100 - (100 / (1 + rs))

    exp12 = df['Close'].ewm(span=12, adjust=False).mean()
    exp26 = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = exp12 - exp26
    df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['Hist'] = df['MACD'] - df['Signal']

    df['BB_Mid'] = df['Close'].rolling(window=20).mean()
    df['BB_Std'] = df['Close'].rolling(window=20).std()
    df['BB_Upper'] = df['BB_Mid'] + 2 * df['BB_Std']
    df['BB_Lower'] = df['BB_Mid'] - 2 * df['BB_Std']

    df = filter_by_timeframe(df, 'Date', timeframe)
    if df.empty:
        return None

    fig = make_subplots(
        rows=3, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.04,
        row_heights=[0.55, 0.25, 0.20],
        subplot_titles=(f"{symbol} 股价与布林带 (Bollinger Bands)", "MACD (12, 26, 9)", "RSI (14) 超买超卖")
    )

    fig.add_trace(go.Scatter(x=df['Date'], y=df['BB_Upper'], name="布林上轨", line=dict(color='rgba(148, 163, 184, 0.5)', dash='dot')), row=1, col=1)
    fig.add_trace(go.Scatter(x=df['Date'], y=df['BB_Lower'], name="布林下轨", fill='tonexty', fillcolor='rgba(241, 245, 249, 0.4)', line=dict(color='rgba(148, 163, 184, 0.5)', dash='dot')), row=1, col=1)
    fig.add_trace(go.Scatter(x=df['Date'], y=df['BB_Mid'], name="布林中轨 (20MA)", line=dict(color='#64748b', width=1.2)), row=1, col=1)
    fig.add_trace(go.Scatter(x=df['Date'], y=df['Close'], name=f"{symbol} 股价", line=dict(color='#2563eb', width=2)), row=1, col=1)

    fig.add_trace(go.Scatter(x=df['Date'], y=df['MACD'], name="MACD", line=dict(color='#3b82f6', width=1.5)), row=2, col=1)
    fig.add_trace(go.Scatter(x=df['Date'], y=df['Signal'], name="Signal (信号线)", line=dict(color='#f97316', width=1.5)), row=2, col=1)
    hist_colors = ['#22c55e' if h >= 0 else '#ef4444' for h in df['Hist']]
    fig.add_trace(go.Bar(x=df['Date'], y=df['Hist'], name="MACD 柱状图", marker_color=hist_colors), row=2, col=1)

    fig.add_trace(go.Scatter(x=df['Date'], y=df['RSI'], name="RSI (14)", line=dict(color='#8b5cf6', width=2)), row=3, col=1)
    fig.add_hline(y=70, line_dash="dash", line_color="red", row=3, col=1)
    fig.add_hline(y=30, line_dash="dash", line_color="green", row=3, col=1)

    fig.update_layout(
        template="plotly_white",
        height=700,
        hovermode="x unified",
        xaxis_rangeslider_visible=False,
        uirevision=f"tech_mom_{symbol}_{timeframe}"
    )
    fig.update_yaxes(title_text="股价", row=1, col=1)
    fig.update_yaxes(title_text="MACD", row=2, col=1)
    fig.update_yaxes(title_text="RSI", range=[0, 100], row=3, col=1)

    return fig


# ------------------------------------------------------------------
# 6. 期权持仓分布与 Max Pain 最大痛点图表
# ------------------------------------------------------------------
def create_max_pain_chart(options_data: dict, current_price: float = None):
    """
    绘制期权到期日各行权价的 Call / Put 未平仓量 (OI) 分布，并标注 Max Pain 最大痛点价位
    """
    if not options_data or "df_strikes" not in options_data:
        return None
    df = options_data["df_strikes"].copy()
    if df.empty or 'strike' not in df.columns:
        return None

    symbol = options_data.get("symbol", "")
    exp_date = options_data.get("expiration", "")
    max_pain = options_data.get("max_pain_price", None)

    # 聚焦当前价格上下 35% 范围内的核心行权价区间，避免被边缘深度虚值期权稀释
    if current_price is not None and current_price > 0:
        low_strike = current_price * 0.65
        high_strike = current_price * 1.35
        df_plot = df[(df['strike'] >= low_strike) & (df['strike'] <= high_strike)].copy()
        if len(df_plot) < 5:
            df_plot = df.copy()
    else:
        df_plot = df.copy()

    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            x=df_plot['strike'],
            y=df_plot['call_oi'],
            name="Call 看涨未平仓 (OI)",
            marker_color='#16a34a',
            opacity=0.85
        )
    )

    fig.add_trace(
        go.Bar(
            x=df_plot['strike'],
            y=df_plot['put_oi'],
            name="Put 看跌未平仓 (OI)",
            marker_color='#dc2626',
            opacity=0.85
        )
    )

    if max_pain is not None and pd.notna(max_pain):
        fig.add_vline(
            x=max_pain,
            line_width=2.5,
            line_dash="dash",
            line_color="#9333ea",
            annotation_text=f"Max Pain: ${max_pain:.1f}",
            annotation_position="top left"
        )

    if current_price is not None and pd.notna(current_price):
        fig.add_vline(
            x=current_price,
            line_width=2,
            line_dash="dot",
            line_color="#2563eb",
            annotation_text=f"现价: ${current_price:.2f}",
            annotation_position="top right"
        )

    fig.update_layout(
        title=f"<b>{symbol} 期权未平仓量 (OI) 分布与做市商最大痛点 (Max Pain) — 到期日: [{exp_date}]</b>",
        template="plotly_white",
        height=480,
        barmode="group",
        hovermode="x unified",
        xaxis_title="行权价 (Strike Price $)",
        yaxis_title="未平仓合约张数 (Contracts)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    return fig


# ------------------------------------------------------------------
# 7. 微观量价动量、动态吊灯止损与波动率挤压走势图
# ------------------------------------------------------------------
def create_volatility_momentum_chart(df_metrics: pd.DataFrame, symbol: str, timeframe: str = "1Y"):
    """
    绘制股价与动态 Chandelier 吊灯多头追踪止损线、20D 均线偏离度 (Bias %) 及布林带带宽 (BandWidth %)
    """
    if df_metrics is None or df_metrics.empty:
        return None
    df = df_metrics.copy()
    if 'Date' in df.columns:
        date_col = 'Date'
        df[date_col] = pd.to_datetime(df[date_col])
    else:
        df = df.reset_index()
        date_col = df.columns[0]
        df[date_col] = pd.to_datetime(df[date_col])

    df = filter_by_timeframe(df, date_col, timeframe)
    if df.empty:
        return None

    fig = make_subplots(
        rows=2, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.06,
        row_heights=[0.65, 0.35],
        subplot_titles=(
            f"{symbol} 股价、20MA 与 Chandelier 动态吊灯多头追踪止损位",
            f"20D 均线偏离度 (Bias %) 与 布林带带宽挤压 (BandWidth %)"
        )
    )

    fig.add_trace(go.Scatter(x=df[date_col], y=df['Close'], name="收盘价", line=dict(color='#2563eb', width=2)), row=1, col=1)

    ma20 = df['Close'].rolling(20).mean()
    fig.add_trace(go.Scatter(x=df[date_col], y=ma20, name="20MA", line=dict(color='#f59e0b', width=1.5, dash='dash')), row=1, col=1)

    if 'Chandelier_Exit' in df.columns:
        fig.add_trace(go.Scatter(x=df[date_col], y=df['Chandelier_Exit'], name="Chandelier 动态止损线", line=dict(color='#dc2626', width=1.8, dash='dot')), row=1, col=1)

    if 'Bias20' in df.columns:
        bias_colors = ['#16a34a' if b >= 0 else '#ef4444' for b in df['Bias20']]
        fig.add_trace(go.Bar(x=df[date_col], y=df['Bias20'], name="20D 偏离度 (%)", marker_color=bias_colors, opacity=0.7), row=2, col=1)
        fig.add_hline(y=8.0, line_dash="dash", line_color="#dc2626", annotation_text="+8% 冲高过热", row=2, col=1)
        fig.add_hline(y=-8.0, line_dash="dash", line_color="#16a34a", annotation_text="-8% 超跌反弹", row=2, col=1)

    if 'BandWidth' in df.columns:
        fig.add_trace(go.Scatter(x=df[date_col], y=df['BandWidth'], name="布林带带宽 (BandWidth %)", line=dict(color='#8b5cf6', width=1.8)), row=2, col=1)

    fig.update_layout(
        template="plotly_white",
        height=620,
        hovermode="x unified",
        uirevision=f"vol_mom_{symbol}_{timeframe}",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    fig.update_yaxes(title_text="价格 ($)", row=1, col=1)
    fig.update_yaxes(title_text="偏离度 / 带宽 (%)", row=2, col=1)
    return fig


def create_interactive_reflexivity_radar(df, symbol: str, default_range: str = '1Y'):
    """
    构建 4 层反身性相空间动力学雷达图，内置可选期限按钮与 Y 轴自适应。
    default_range: '1M', '3M', '6M', '1Y', '3Y', '5Y', 'ALL'
    """
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    import pandas as pd
    
    if df is None or df.empty or 'Composite_Score' not in df.columns:
        return None
        
    date_col = 'date' if 'date' in df.columns else df.index

    # 确保 date 列为 datetime 类型
    if isinstance(date_col, str):
        df = df.copy()
        df[date_col] = pd.to_datetime(df[date_col])

    # Create subplots: 4 rows
    fig = make_subplots(
        rows=4, cols=1, 
        shared_xaxes=True, 
        vertical_spacing=0.03,
        row_heights=[0.4, 0.2, 0.2, 0.2],
        subplot_titles=(
            f"[{symbol}] 反身性相空间动力学 4-Quadrant Radar", 
            "Layer 2: 状态位置 q1 (偏离度 %) 与 状态速度 q1_dot", 
            "Layer 3: 反身性偏离度 (Reflexive Gap) 与 稳定性导数 (V_dot)",
            "Layer 4: 宏观信用环境 (BAA10Y 信用利差 & NFCI 芝加哥金融条件)"
        ),
        specs=[[{"secondary_y": False}], [{"secondary_y": True}], [{"secondary_y": True}], [{"secondary_y": True}]]
    )
    
    # --- Layer 1: Price and Signals ---
    fig.add_trace(go.Scatter(x=df[date_col], y=df['close'], mode='lines', name='Close Price', line=dict(color='black', width=1.5)), row=1, col=1)
    if 'MA50' in df.columns:
        fig.add_trace(go.Scatter(x=df[date_col], y=df['MA50'], mode='lines', name='50 MA', line=dict(color='blue', width=1, dash='dot')), row=1, col=1)
    if 'MA200' in df.columns:
        fig.add_trace(go.Scatter(x=df[date_col], y=df['MA200'], mode='lines', name='200 MA', line=dict(color='red', width=1.2)), row=1, col=1)

    # Signal points
    if 'Trigger_Panic' in df.columns:
        df_panic = df[df['Trigger_Panic'] == True]
        fig.add_trace(go.Scatter(x=df_panic[date_col], y=df_panic['close'], mode='markers', name='I: 恐慌极值底 (Panic)', marker=dict(color='fuchsia', size=12, symbol='triangle-up', line=dict(color='white', width=1))), row=1, col=1)
    
    if 'Trigger_Stage' in df.columns:
        df_stage = df[df['Trigger_Stage'] == True]
        fig.add_trace(go.Scatter(x=df_stage[date_col], y=df_stage['close'], mode='markers', name='II: 蓄势确认底 (Stage)', marker=dict(color='blue', size=10, symbol='triangle-up', line=dict(color='white', width=1))), row=1, col=1)

    if 'Trigger_Bubble_Top' in df.columns:
        df_bubble = df[df['Trigger_Bubble_Top'] == True]
        fig.add_trace(go.Scatter(x=df_bubble[date_col], y=df_bubble['close'], mode='markers', name='III: 极度泡沫顶 (Bubble)', marker=dict(color='red', size=12, symbol='triangle-down', line=dict(color='white', width=1))), row=1, col=1)

    if 'Trigger_Bear_Top' in df.columns:
        df_bear = df[df['Trigger_Bear_Top'] == True]
        fig.add_trace(go.Scatter(x=df_bear[date_col], y=df_bear['close'], mode='markers', name='IV: 熊市逃顶 (Bear Top)', marker=dict(color='orange', size=10, symbol='triangle-down', line=dict(color='white', width=1))), row=1, col=1)

    # --- Layer 2: Composite Score & q1_dot ---
    if 'Composite_Score' in df.columns:
        fig.add_trace(go.Scatter(x=df[date_col], y=df['Composite_Score'], mode='lines', name='Composite Score (综合得分)', line=dict(color='purple', width=1.5)), row=2, col=1, secondary_y=False)
    if 'q1_dot' in df.columns:
        fig.add_trace(go.Scatter(x=df[date_col], y=df['q1_dot'], mode='lines', name='q1_dot (状态速度)', line=dict(color='#0ea5e9', width=1.2)), row=2, col=1, secondary_y=True)
    # Thresholds
    fig.add_hline(y=70, line_dash="dash", line_color="red", row=2, col=1, annotation_text="Overbought 70")
    fig.add_hline(y=35, line_dash="dash", line_color="green", row=2, col=1, annotation_text="Oversold 35")
    
    # --- Layer 3: Gap & V_dot ---
    if 'Gap' in df.columns:
        fig.add_trace(go.Scatter(x=df[date_col], y=df['Gap'], mode='lines', fill='tozeroy', name='Reflexive Gap (反身性偏差)', line=dict(color='rgba(255,165,0,0.7)', width=1)), row=3, col=1, secondary_y=False)
    if 'v_dot' in df.columns:
        fig.add_trace(go.Scatter(x=df[date_col], y=df['v_dot'], mode='lines', name='V_dot (李雅普诺夫导数)', line=dict(color='#ef4444', width=1.5)), row=3, col=1, secondary_y=True)
    fig.add_hline(y=0, line_dash="dash", line_color="gray", row=3, col=1)

    # --- Layer 4: Macro Tension (BAA10Y on primary, NFCI on secondary) ---
    if 'BAA10Y' in df.columns:
        fig.add_trace(go.Scatter(x=df[date_col], y=df['BAA10Y'], mode='lines', name='BAA10Y 信用利差', line=dict(color='#3b82f6', width=1.5)), row=4, col=1, secondary_y=False)
    if 'NFCI' in df.columns:
        fig.add_trace(go.Scatter(x=df[date_col], y=df['NFCI'], mode='lines', name='NFCI 金融条件', line=dict(color='#f59e0b', width=1.5)), row=4, col=1, secondary_y=True)

    # =========================================================================
    # 动态自适应 Y 轴与双轴联动按钮 (各预设期限切片的精准极值计算)
    # =========================================================================
    last_dt = df[date_col].iloc[-1]
    total_days = (last_dt - df[date_col].iloc[0]).days
    total_years = total_days / 365.25
    end_str = (last_dt + pd.DateOffset(days=5)).strftime('%Y-%m-%d')

    time_windows = [
        ("近1月", 1),
        ("近3月", 3),
        ("近6月", 6),
        ("近1年", 12),
        ("近3年", 36),
        ("近5年", 60),
        (f"全部 ({total_years:.1f}年)", None)
    ]

    updatemenu_buttons = []

    # 初始默认边界 (防护性初始化为全量)
    initial_x_start = df[date_col].iloc[0]
    initial_y_price_range = [df['close'].min() * 0.94, df['close'].max() * 1.06]

    # 用于 Layer 1 价格 Y 轴计算的列
    price_cols = ['close']
    if 'MA50' in df.columns:
        price_cols.append('MA50')
    if 'MA200' in df.columns:
        price_cols.append('MA200')

    for label, months in time_windows:
        if months is not None:
            s_dt = last_dt - pd.DateOffset(months=months)
            s_slice = df[df[date_col] >= s_dt]
        else:
            s_dt = df[date_col].iloc[0]
            s_slice = df

        if s_slice.empty:
            continue

        s_str = s_dt.strftime('%Y-%m-%d')

        # --- Layer 1: 价格切片极值 (带 6% 呼吸边距) ---
        p_min = s_slice[price_cols].min().min()
        p_max = s_slice[price_cols].max().max()
        p_pad = (p_max - p_min) * 0.06 if p_max > p_min else p_max * 0.06
        y_p_min = max(0, p_min - p_pad)
        y_p_max = p_max + p_pad

        # --- Layer 2: Composite Score (0-100 固定量纲, q1_dot 自适应) ---
        y_score_min = 0
        y_score_max = 105
        if 'q1_dot' in s_slice.columns:
            qd_min = s_slice['q1_dot'].min()
            qd_max = s_slice['q1_dot'].max()
            qd_pad = (qd_max - qd_min) * 0.08 if qd_max > qd_min else 1.0
            y_qd_range = [qd_min - qd_pad, qd_max + qd_pad]
        else:
            y_qd_range = [-5, 5]

        # --- Layer 3: Gap & V_dot 自适应 ---
        if 'Gap' in s_slice.columns:
            g_min = s_slice['Gap'].min()
            g_max = s_slice['Gap'].max()
            g_pad = (g_max - g_min) * 0.08 if g_max > g_min else 1.0
            y_gap_range = [g_min - g_pad, g_max + g_pad]
        else:
            y_gap_range = [-20, 20]
        if 'v_dot' in s_slice.columns:
            vd_min = s_slice['v_dot'].min()
            vd_max = s_slice['v_dot'].max()
            vd_pad = (vd_max - vd_min) * 0.08 if vd_max > vd_min else 1.0
            y_vd_range = [vd_min - vd_pad, vd_max + vd_pad]
        else:
            y_vd_range = [-5, 5]

        # --- Layer 4: BAA10Y & NFCI 自适应 ---
        if 'BAA10Y' in s_slice.columns:
            b_min = s_slice['BAA10Y'].min()
            b_max = s_slice['BAA10Y'].max()
            b_pad = (b_max - b_min) * 0.08 if b_max > b_min else 0.1
            y_baa_range = [b_min - b_pad, b_max + b_pad]
        else:
            y_baa_range = [0, 5]
        if 'NFCI' in s_slice.columns:
            n_min = s_slice['NFCI'].min()
            n_max = s_slice['NFCI'].max()
            n_pad = (n_max - n_min) * 0.08 if n_max > n_min else 0.1
            y_nfci_range = [n_min - n_pad, n_max + n_pad]
        else:
            y_nfci_range = [-1, 1]

        # 匹配初始视野
        key_tag = f"{months}M" if months and months < 12 else (f"{months // 12}Y" if months else "ALL")
        if default_range == key_tag or (default_range == '1Y' and months == 12):
            initial_x_start = s_dt
            initial_y_price_range = [y_p_min, y_p_max]

        # 构造 Plotly Relayout 联动按钮：点击同时精准更新全部 4 层 X 轴与 Y 轴范围
        # Plotly subplots axis naming: row1=yaxis, row2=yaxis2 (primary) + yaxis5 (secondary),
        # row3=yaxis3 (primary) + yaxis6 (secondary), row4=yaxis4 (primary) + yaxis7 (secondary)
        updatemenu_buttons.append(dict(
            label=label,
            method='relayout',
            args=[{
                'xaxis4.range': [s_str, end_str],
                'yaxis.range': [y_p_min, y_p_max],
                'yaxis2.range': [y_score_min, y_score_max],
                'yaxis5.range': y_qd_range,
                'yaxis3.range': y_gap_range,
                'yaxis6.range': y_vd_range,
                'yaxis4.range': y_baa_range,
                'yaxis7.range': y_nfci_range,
            }]
        ))

    fig.update_layout(
        height=1000,
        hovermode="x unified",
        template="plotly_white",
        font=dict(size=14, family="sans-serif"),
        legend=dict(
            orientation="h", 
            yanchor="bottom", 
            y=1.06, 
            xanchor="center", 
            x=0.5,
            bgcolor="#ffffff",
            bordercolor="#b2bec3",
            borderwidth=1.5,
            font=dict(color="#111111", size=15, family="sans-serif")
        ),
        margin=dict(l=65, r=45, t=220, b=45),
        # 内置期限切换按钮组 (点击同时自适应调整全部 Y 轴与 X 轴)
        updatemenus=[
            dict(
                type="buttons",
                direction="right",
                x=0.0,
                y=1.16,
                xanchor="left",
                yanchor="bottom",
                bgcolor="#f5f6fa",
                bordercolor="#dcdde1",
                borderwidth=1,
                font=dict(color="#2f3542", size=14, family="sans-serif"),
                buttons=updatemenu_buttons
            )
        ]
    )

    # 底部滑块 (rangeslider)
    fig.update_xaxes(
        rangeslider=dict(visible=True, thickness=0.03, bgcolor="#f1f2f6"),
        range=[initial_x_start.strftime('%Y-%m-%d'), end_str],
        row=4, col=1
    )

    # 初始 Y 轴设置为默认期限切片的精准极值区间
    fig.update_yaxes(
        range=initial_y_price_range,
        title_text="价格 (USD)", tickprefix="$",
        gridcolor="#f1f2f6", zerolinecolor="#dcdde1",
        row=1, col=1
    )
    fig.update_yaxes(title_text="综合得分", range=[0, 105], gridcolor="#f1f2f6", zerolinecolor="#dcdde1", row=2, col=1)
    fig.update_yaxes(title_text="反身性 Gap", gridcolor="#f1f2f6", zerolinecolor="#dcdde1", row=3, col=1)
    fig.update_yaxes(title_text="信用利差", gridcolor="#f1f2f6", zerolinecolor="#dcdde1", row=4, col=1)
    
    return fig
