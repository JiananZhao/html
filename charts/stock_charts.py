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
            go.Scatter(x=df['Date'], y=df['Close'], mode='lines', name=f"{symbol} 收盘价", line=dict(color='#38bdf8', width=2.2)),
            row=1, col=1
        )

    if 'MA20' in df.columns:
        fig.add_trace(go.Scatter(x=df['Date'], y=df['MA20'], mode='lines', name="MA20", line=dict(color='#f59e0b', width=1.5)), row=1, col=1)
    if 'MA50' in df.columns:
        fig.add_trace(go.Scatter(x=df['Date'], y=df['MA50'], mode='lines', name="MA50", line=dict(color='#a78bfa', width=1.5)), row=1, col=1)
    if 'MA200' in df.columns:
        fig.add_trace(go.Scatter(x=df['Date'], y=df['MA200'], mode='lines', name="MA200", line=dict(color='#ef4444', width=2)), row=1, col=1)

    if has_volume:
        colors = ['#22c55e' if c >= o else '#ef4444' for c, o in zip(df['Close'], df['Open'])] if has_ohlc else '#64748b'
        fig.add_trace(
            go.Bar(x=df['Date'], y=df['Volume'], name="成交量", marker_color=colors, showlegend=False),
            row=2, col=1
        )

    fig = apply_chart_theme(
        fig,
        height=600,
        hovermode="x unified",
        uirevision=f"stock_price_{symbol}_{timeframe}",
        showlegend=True
    )
    fig.update_layout(
        xaxis_rangeslider_visible=False,
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
        color_discrete_sequence=['#38bdf8', '#10b981', '#f59e0b', '#ec4899', '#a855f7', '#06b6d4', '#f97316', '#84cc16']
    )
    fig.add_hline(y=100, line_dash="dash", line_color="#94a3b8")
    fig = apply_chart_theme(
        fig,
        title=f"半导体产业链龙头相对表现走势 (基准 = 100) - [{timeframe}]",
        height=550,
        hovermode="x unified",
        uirevision=f"semi_rel_{timeframe}",
        showlegend=True
    )
    fig.update_layout(
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
    fig = apply_chart_theme(
        fig,
        title=title_text,
        height=650,
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

    import streamlit as st
    curr_theme = st.session_state.get("theme_mode", "dark")
    stock_line_color = '#ffffff' if curr_theme == "dark" else '#0f172a'

    fig.add_trace(
        go.Scatter(
            x=df['Date'],
            y=df['Close'],
            mode='lines',
            name=f"{symbol} 真实股价",
            line=dict(color=stock_line_color, width=2.8),
            hovertemplate=f"<b>{symbol} 股价</b>: $%{{y:.2f}}<extra></extra>"
        )
    )

    fig = apply_chart_theme(
        fig,
        title=f"{symbol} {val_type} 动态估值通道 ({val_type} Band) - [{timeframe}]",
        height=500,
        hovermode="x unified",
        yaxis_title="价格 ($ USD)",
        uirevision=f"{val_type.lower()}_band_{symbol}_{timeframe}",
        showlegend=True
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

    import streamlit as st
    curr_theme = st.session_state.get("theme_mode", "dark")
    bb_fill = 'rgba(56, 189, 248, 0.08)' if curr_theme == "dark" else 'rgba(241, 245, 249, 0.4)'
    stock_color = '#38bdf8' if curr_theme == "dark" else '#2563eb'

    fig.add_trace(go.Scatter(x=df['Date'], y=df['BB_Upper'], name="布林上轨", line=dict(color='rgba(148, 163, 184, 0.6)', dash='dot')), row=1, col=1)
    fig.add_trace(go.Scatter(x=df['Date'], y=df['BB_Lower'], name="布林下轨", fill='tonexty', fillcolor=bb_fill, line=dict(color='rgba(148, 163, 184, 0.6)', dash='dot')), row=1, col=1)
    fig.add_trace(go.Scatter(x=df['Date'], y=df['BB_Mid'], name="布林中轨 (20MA)", line=dict(color='#94a3b8', width=1.2)), row=1, col=1)
    fig.add_trace(go.Scatter(x=df['Date'], y=df['Close'], name=f"{symbol} 股价", line=dict(color=stock_color, width=2.2)), row=1, col=1)

    fig.add_trace(go.Scatter(x=df['Date'], y=df['MACD'], name="MACD", line=dict(color='#38bdf8', width=1.6)), row=2, col=1)
    fig.add_trace(go.Scatter(x=df['Date'], y=df['Signal'], name="Signal (信号线)", line=dict(color='#f97316', width=1.5)), row=2, col=1)
    hist_colors = ['#22c55e' if h >= 0 else '#ef4444' for h in df['Hist']]
    fig.add_trace(go.Bar(x=df['Date'], y=df['Hist'], name="MACD 柱状图", marker_color=hist_colors), row=2, col=1)

    fig.add_trace(go.Scatter(x=df['Date'], y=df['RSI'], name="RSI (14)", line=dict(color='#a855f7', width=2)), row=3, col=1)
    fig.add_hline(y=70, line_dash="dash", line_color="#ef4444", row=3, col=1)
    fig.add_hline(y=30, line_dash="dash", line_color="#10b981", row=3, col=1)

    fig = apply_chart_theme(
        fig,
        height=700,
        hovermode="x unified",
        uirevision=f"tech_mom_{symbol}_{timeframe}",
        showlegend=True
    )
    fig.update_layout(xaxis_rangeslider_visible=False)
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
            line_color="#c084fc",
            annotation_text=f"Max Pain: ${max_pain:.1f}",
            annotation_position="top left"
        )

    if current_price is not None and pd.notna(current_price):
        fig.add_vline(
            x=current_price,
            line_width=2,
            line_dash="dot",
            line_color="#38bdf8",
            annotation_text=f"现价: ${current_price:.2f}",
            annotation_position="top right"
        )

    title_str = f"<b>{symbol} 期权未平仓量 (OI) 分布与做市商最大痛点 (Max Pain) — 到期日: [{exp_date}]</b>"
    fig = apply_chart_theme(
        fig,
        title=title_str,
        height=480,
        hovermode="x unified",
        showlegend=True
    )
    fig.update_layout(
        barmode="group",
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

    fig.add_trace(go.Scatter(x=df[date_col], y=df['Close'], name="收盘价", line=dict(color='#38bdf8', width=2)), row=1, col=1)

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
        fig.add_trace(go.Scatter(x=df[date_col], y=df['BandWidth'], name="布林带带宽 (BandWidth %)", line=dict(color='#a855f7', width=1.8)), row=2, col=1)

    fig = apply_chart_theme(
        fig,
        height=620,
        hovermode="x unified",
        uirevision=f"vol_mom_{symbol}_{timeframe}",
        showlegend=True
    )
    fig.update_layout(
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    fig.update_yaxes(title_text="价格 ($)", row=1, col=1)
    fig.update_yaxes(title_text="偏离度 / 带宽 (%)", row=2, col=1)
    return fig


def create_interactive_reflexivity_radar(
    df, 
    symbol: str, 
    default_range: str = '6M',
    start_date: str = None,
    end_date: str = None
):
    """
    构建 4 层微观反身性动能雷达图，具备全周期 Y 轴自适应、警戒线与高可读性排版。
    """
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    import pandas as pd
    import numpy as np

    if df is None or df.empty or 'Composite_Score' not in df.columns:
        return None

    date_col = 'date' if 'date' in df.columns else df.index

    # 确保 date 列为 datetime 类型
    if isinstance(date_col, str):
        df = df.copy()
        df[date_col] = pd.to_datetime(df[date_col]).dt.tz_localize(None)

    last_dt = df[date_col].iloc[-1]
    first_dt = df[date_col].iloc[0]

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

    # 提取当前视野切片，计算精确极值
    s_slice = df[(df[date_col] >= s_dt) & (df[date_col] <= e_dt)]
    if s_slice.empty:
        s_slice = df
        s_dt = first_dt
        e_dt = last_dt

    # Subplot titles
    fig = make_subplots(
        rows=4, cols=1, 
        shared_xaxes=True, 
        vertical_spacing=0.05,
        row_heights=[0.42, 0.20, 0.20, 0.18],
        subplot_titles=(
            f"<b>[{symbol}] 股价走势与关键买卖决策点</b>", 
            "<b>Layer 2: 动能综合得分 (Composite Score, 0~100) 与 状态速度 (q1_dot)</b>", 
            "<b>Layer 3: 情绪偏离度 (Reflexive Gap) 与 能量变化率 (V_dot)</b>",
            "<b>Layer 4: 宏观信用流动性底色 (BAA10Y 信用利差 & NFCI 金融条件)</b>"
        ),
        specs=[[{"secondary_y": False}], [{"secondary_y": True}], [{"secondary_y": True}], [{"secondary_y": True}]]
    )

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
        close_c = "#38bdf8"
    else:
        paper_bg = "#ffffff"
        plot_bg = "#ffffff"
        font_c = "#0f172a"
        tpl = "plotly_white"
        grid_c = "#f1f5f9"
        zero_c = "#e2e8f0"
        legend_bg = "rgba(255, 255, 255, 0.95)"
        legend_border = "#cbd5e1"
        close_c = "#0f172a"

    # --- Layer 1: Price and Signals ---
    fig.add_trace(go.Scatter(
        x=s_slice[date_col], y=s_slice['close'], mode='lines', 
        name='收盘价', line=dict(color=close_c, width=2.2),
        hovertemplate='%{x}<br>收盘价: $%{y:.2f}<extra></extra>'
    ), row=1, col=1)

    if 'MA50' in s_slice.columns:
        fig.add_trace(go.Scatter(
            x=s_slice[date_col], y=s_slice['MA50'], mode='lines', 
            name='50日均线', line=dict(color='#2563eb', width=1.2, dash='dot'),
            hovertemplate='%{x}<br>50MA: $%{y:.2f}<extra></extra>'
        ), row=1, col=1)
    if 'MA200' in s_slice.columns:
        fig.add_trace(go.Scatter(
            x=s_slice[date_col], y=s_slice['MA200'], mode='lines', 
            name='200日均线', line=dict(color='#dc2626', width=1.5),
            hovertemplate='%{x}<br>200MA: $%{y:.2f}<extra></extra>'
        ), row=1, col=1)

    # Signal points
    if 'Trigger_Panic' in s_slice.columns:
        df_panic = s_slice[s_slice['Trigger_Panic'] == True]
        if not df_panic.empty:
            fig.add_trace(go.Scatter(
                x=df_panic[date_col], y=df_panic['close'], mode='markers', 
                name='I: 恐慌极值底 (Panic)', 
                marker=dict(color='#d946ef', size=12, symbol='triangle-up', line=dict(color='white', width=1)),
                hovertemplate='%{x}<br>恐慌极值底: $%{y:.2f}<extra></extra>'
            ), row=1, col=1)
    
    if 'Trigger_Stage' in s_slice.columns:
        df_stage = s_slice[s_slice['Trigger_Stage'] == True]
        if not df_stage.empty:
            fig.add_trace(go.Scatter(
                x=df_stage[date_col], y=df_stage['close'], mode='markers', 
                name='II: 蓄势确认底 (Stage)', 
                marker=dict(color='#3b82f6', size=10, symbol='triangle-up', line=dict(color='white', width=1)),
                hovertemplate='%{x}<br>蓄势确认底: $%{y:.2f}<extra></extra>'
            ), row=1, col=1)

    if 'Trigger_Bubble_Top' in s_slice.columns:
        df_bubble = s_slice[s_slice['Trigger_Bubble_Top'] == True]
        if not df_bubble.empty:
            fig.add_trace(go.Scatter(
                x=df_bubble[date_col], y=df_bubble['close'], mode='markers', 
                name='III: 极度泡沫顶 (Bubble)', 
                marker=dict(color='#ef4444', size=12, symbol='triangle-down', line=dict(color='white', width=1)),
                hovertemplate='%{x}<br>极度泡沫顶: $%{y:.2f}<extra></extra>'
            ), row=1, col=1)

    if 'Trigger_Bear_Top' in s_slice.columns:
        df_bear = s_slice[s_slice['Trigger_Bear_Top'] == True]
        if not df_bear.empty:
            fig.add_trace(go.Scatter(
                x=df_bear[date_col], y=df_bear['close'], mode='markers', 
                name='IV: 熊市逃顶 (Bear Top)', 
                marker=dict(color='#f97316', size=10, symbol='triangle-down', line=dict(color='white', width=1)),
                hovertemplate='%{x}<br>熊市逃顶: $%{y:.2f}<extra></extra>'
            ), row=1, col=1)

    # Execution markers
    if 'action' in s_slice.columns:
        df_buy = s_slice[s_slice['action'] == 'BUY']
        if not df_buy.empty:
            fig.add_trace(go.Scatter(
                x=df_buy[date_col], y=df_buy['close'], mode='markers', 
                name='【B】实盘买入', 
                marker=dict(color='#16a34a', size=15, symbol='arrow-up', line=dict(color='black', width=1)),
                hovertemplate='%{x}<br>实盘买入: $%{y:.2f}<extra></extra>'
            ), row=1, col=1)
        
        df_sell = s_slice[s_slice['action'] == 'SELL']
        if not df_sell.empty:
            fig.add_trace(go.Scatter(
                x=df_sell[date_col], y=df_sell['close'], mode='markers', 
                name='【S】实盘卖出', 
                marker=dict(color='#dc2626', size=15, symbol='arrow-down', line=dict(color='black', width=1)),
                hovertemplate='%{x}<br>实盘卖出: $%{y:.2f}<extra></extra>'
            ), row=1, col=1)

    # --- Layer 2: Composite Score & q1_dot ---
    if 'Composite_Score' in s_slice.columns:
        fig.add_trace(go.Scatter(
            x=s_slice[date_col], y=s_slice['Composite_Score'], mode='lines', 
            name='综合得分', line=dict(color='#8b5cf6', width=1.6),
            showlegend=False,
            hovertemplate='%{x}<br>综合得分: %{y:.1f}<extra></extra>'
        ), row=2, col=1, secondary_y=False)
    if 'q1_dot' in s_slice.columns:
        fig.add_trace(go.Scatter(
            x=s_slice[date_col], y=s_slice['q1_dot'], mode='lines', 
            name='状态速度 (q1_dot)', line=dict(color='#0ea5e9', width=1.2, dash='dash'),
            showlegend=False,
            hovertemplate='%{x}<br>状态速度 q1_dot: %{y:.2f}<extra></extra>'
        ), row=2, col=1, secondary_y=True)

    fig.add_hline(y=70, line_dash="dash", line_color="#ef4444", line_width=1, row=2, col=1, annotation_text="泡沫警戒 70", annotation_position="top left")
    fig.add_hline(y=35, line_dash="dash", line_color="#10b981", line_width=1, row=2, col=1, annotation_text="恐慌低吸 35", annotation_position="bottom left")

    # --- Layer 3: Gap & V_dot ---
    if 'Gap' in s_slice.columns:
        fig.add_trace(go.Scatter(
            x=s_slice[date_col], y=s_slice['Gap'], mode='lines', 
            fill='tozeroy', fillcolor='rgba(245, 158, 11, 0.15)',
            name='情绪偏离度 (Gap)', line=dict(color='#f59e0b', width=1.5),
            showlegend=False,
            hovertemplate='%{x}<br>情绪偏离度 Gap: %{y:.2f} σ<extra></extra>'
        ), row=3, col=1, secondary_y=False)
    if 'v_dot' in s_slice.columns:
        fig.add_trace(go.Scatter(
            x=s_slice[date_col], y=s_slice['v_dot'], mode='lines', 
            name='V_dot (李雅普诺夫能量变化率)', line=dict(color='#ef4444', width=1.2),
            showlegend=False,
            hovertemplate='%{x}<br>V_dot: %{y:.2f}<extra></extra>'
        ), row=3, col=1, secondary_y=True)

    # Layer 3 警戒线与阴影带
    fig.add_hline(y=0, line_dash="solid", line_color="#94a3b8", line_width=1, row=3, col=1)
    fig.add_hline(y=2.0, line_dash="dot", line_color="#ef4444", line_width=1.2, row=3, col=1, annotation_text="+2.0 情绪过热警戒线", annotation_position="top left")
    fig.add_hline(y=-2.0, line_dash="dot", line_color="#10b981", line_width=1.2, row=3, col=1, annotation_text="-2.0 情绪冰点超跌线", annotation_position="bottom left")
    fig.add_hrect(y0=2.0, y1=20.0, fillcolor="rgba(239, 68, 68, 0.05)", line_width=0, row=3, col=1)
    fig.add_hrect(y0=-20.0, y1=-2.0, fillcolor="rgba(16, 185, 129, 0.05)", line_width=0, row=3, col=1)

    # --- Layer 4: Macro Tension (BAA10Y on primary, NFCI on secondary) ---
    if 'BAA10Y' in s_slice.columns:
        fig.add_trace(go.Scatter(
            x=s_slice[date_col], y=s_slice['BAA10Y'], mode='lines', 
            name='BAA10Y 信用利差', line=dict(color='#3b82f6', width=1.5),
            showlegend=False,
            hovertemplate='%{x}<br>BAA10Y 信用利差: %{y:.2f}%<extra></extra>'
        ), row=4, col=1, secondary_y=False)
    if 'NFCI' in s_slice.columns:
        fig.add_trace(go.Scatter(
            x=s_slice[date_col], y=s_slice['NFCI'], mode='lines', 
            name='NFCI 金融条件', line=dict(color='#f59e0b', width=1.3, dash='dot'),
            showlegend=False,
            hovertemplate='%{x}<br>NFCI 金融条件: %{y:.2f}<extra></extra>'
        ), row=4, col=1, secondary_y=True)
    fig.add_hline(y=0, line_dash="dash", line_color="#94a3b8", line_width=1, row=4, col=1)

    # =========================================================================
    # 动态极值计算：严格根据 s_slice 切片自适应所有 4 层 Y 轴
    # =========================================================================
    # Layer 1 价格自适应
    price_cols = ['close']
    if 'MA50' in df.columns:
        price_cols.append('MA50')
    if 'MA200' in df.columns:
        price_cols.append('MA200')
    p_min = s_slice[price_cols].min().min()
    p_max = s_slice[price_cols].max().max()
    p_pad = max((p_max - p_min) * 0.06, p_max * 0.03)
    y_p_range = [max(0, p_min - p_pad), p_max + p_pad]

    # Layer 2 速度自适应
    if 'q1_dot' in s_slice.columns:
        qd_min = s_slice['q1_dot'].min()
        qd_max = s_slice['q1_dot'].max()
        qd_pad = max((qd_max - qd_min) * 0.08, 0.5)
        y_qd_range = [qd_min - qd_pad, qd_max + qd_pad]
    else:
        y_qd_range = [-5, 5]

    # Layer 3 Gap & V_dot 自适应
    if 'Gap' in s_slice.columns:
        g_min = s_slice['Gap'].min()
        g_max = s_slice['Gap'].max()
        y_gap_range = [min(g_min - 0.4, -2.5), max(g_max + 0.4, 2.5)]
    else:
        y_gap_range = [-2.5, 2.5]
    if 'v_dot' in s_slice.columns:
        vd_min = s_slice['v_dot'].min()
        vd_max = s_slice['v_dot'].max()
        vd_pad = max((vd_max - vd_min) * 0.08, 0.5)
        y_vd_range = [vd_min - vd_pad, vd_max + vd_pad]
    else:
        y_vd_range = [-5, 5]

    # Layer 4 利差与 NFCI 自适应 (避免过窄放大微小锯齿)
    if 'BAA10Y' in s_slice.columns:
        b_min = s_slice['BAA10Y'].min()
        b_max = s_slice['BAA10Y'].max()
        b_span = b_max - b_min
        if b_span < 0.4:
            b_mid = (b_max + b_min) / 2.0
            y_baa_range = [max(0, b_mid - 0.25), b_mid + 0.25]
        else:
            y_baa_range = [max(0, b_min - b_span * 0.08), b_max + b_span * 0.08]
    else:
        y_baa_range = [1.0, 4.0]
    if 'NFCI' in s_slice.columns:
        n_min = s_slice['NFCI'].min()
        n_max = s_slice['NFCI'].max()
        n_span = n_max - n_min
        y_nfci_range = [n_min - max(0.1, n_span * 0.08), n_max + max(0.1, n_span * 0.08)]
    else:
        y_nfci_range = [-1, 1]

    # =========================================================================
    # 统一 Layout 与无重叠 Legend 排版
    # =========================================================================
    fig.update_layout(
        height=980,
        hovermode="x unified",
        template=tpl,
        paper_bgcolor=paper_bg,
        plot_bgcolor=plot_bg,
        font=dict(size=14, family="sans-serif", color=font_c),
        legend=dict(
            orientation="h", 
            yanchor="bottom", 
            y=1.02, 
            xanchor="center", 
            x=0.5,
            bgcolor=legend_bg,
            bordercolor=legend_border,
            borderwidth=1,
            font=dict(color=font_c, size=14, family="sans-serif")
        ),
        margin=dict(l=65, r=65, t=70, b=40)
    )

    # 4 层 X 轴范围与刻度同步
    start_str = s_dt.strftime('%Y-%m-%d')
    end_str = (e_dt + pd.DateOffset(days=3)).strftime('%Y-%m-%d')
    fig.update_xaxes(
        range=[start_str, end_str],
        gridcolor=grid_c, zerolinecolor=zero_c,
        tickfont=dict(color=font_c, size=14)
    )

    # 4 层 Y 轴应用自适应区间
    fig.update_yaxes(
        range=y_p_range,
        title_text="价格 (USD)", tickprefix="$",
        gridcolor=grid_c, zerolinecolor=zero_c,
        tickfont=dict(color=font_c, size=14),
        row=1, col=1
    )
    fig.update_yaxes(
        range=[0, 105],
        title_text="综合得分",
        gridcolor=grid_c, zerolinecolor=zero_c,
        tickfont=dict(color=font_c, size=14),
        row=2, col=1, secondary_y=False
    )
    fig.update_yaxes(
        range=y_qd_range,
        title_text="速度 q1_dot",
        showgrid=False,
        tickfont=dict(color=font_c, size=14),
        row=2, col=1, secondary_y=True
    )
    fig.update_yaxes(
        range=y_gap_range,
        title_text="情绪偏离度 (Z-Score)",
        gridcolor=grid_c, zerolinecolor=zero_c,
        tickfont=dict(color=font_c, size=14),
        row=3, col=1, secondary_y=False
    )
    fig.update_yaxes(
        range=y_vd_range,
        title_text="能量 V_dot",
        showgrid=False,
        tickfont=dict(color=font_c, size=14),
        row=3, col=1, secondary_y=True
    )
    fig.update_yaxes(
        range=y_baa_range,
        title_text="信用利差 (%)", ticksuffix="%",
        gridcolor=grid_c, zerolinecolor=zero_c,
        tickfont=dict(color=font_c, size=14),
        row=4, col=1, secondary_y=False
    )
    fig.update_yaxes(
        range=y_nfci_range,
        title_text="NFCI 金融条件",
        showgrid=False,
        tickfont=dict(color=font_c, size=14),
        row=4, col=1, secondary_y=True
    )

    return fig

