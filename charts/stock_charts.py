from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

from charts.theme import filter_by_timeframe, apply_chart_theme

# ------------------------------------------------------------------
# 1. ???????????????????????? K ??? / ???????????????
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
            subplot_titles=(f"{symbol} ????????????????????? (MA20 / MA50 / MA200)", "????????? (Volume)")
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
                name=f"{symbol} K???",
                increasing_line_color='#22c55e',
                decreasing_line_color='#ef4444',
                showlegend=True
            ),
            row=1, col=1
        )
    elif 'Close' in df.columns:
        fig.add_trace(
            go.Scatter(x=df['Date'], y=df['Close'], mode='lines', name=f"{symbol} ?????????", line=dict(color='#2563eb', width=2)),
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
            go.Bar(x=df['Date'], y=df['Volume'], name="?????????", marker_color=colors, showlegend=False),
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
# 2. ????????????????????????????????????????????? (Normalized Performance)
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
        title=f"?????????????????????????????????????????? (?????? = 100) - [{timeframe}]",
        labels={"value": "???????????? (??????????????????100)", "Date": "??????", "variable": "????????????"},
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
# 3. ??????????????????????????????????????? (Revenue, Margin, FCF)
# ------------------------------------------------------------------
def create_financial_trends_chart(df_stmt: pd.DataFrame, symbol: str = "", period_type: str = "??????"):
    if df_stmt is None or df_stmt.empty:
        return None
    df = df_stmt.copy()

    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=(
            f"??????????????????????????? ($M)",
            f"??????????????????????????? (%)",
            f"?????????????????????????????? ($M)",
            f"????????????????????? ($M / %)"
        )
    )

    if 'Revenue ($M)' in df.columns:
        fig.add_trace(go.Bar(x=df['Period'], y=df['Revenue ($M)'], name="????????? ($M)", marker_color='#3b82f6'), row=1, col=1)
    if 'Net Income ($M)' in df.columns:
        fig.add_trace(go.Scatter(x=df['Period'], y=df['Net Income ($M)'], name="????????? ($M)", line=dict(color='#22c55e', width=2.5)), row=1, col=1)

    if 'Gross Margin (%)' in df.columns:
        fig.add_trace(go.Scatter(x=df['Period'], y=df['Gross Margin (%)'], name="????????? (%)", line=dict(color='#8b5cf6', width=2)), row=1, col=2)
    if 'Operating Margin (%)' in df.columns:
        fig.add_trace(go.Scatter(x=df['Period'], y=df['Operating Margin (%)'], name="??????????????? (%)", line=dict(color='#f59e0b', width=2)), row=1, col=2)
    if 'Net Margin (%)' in df.columns:
        fig.add_trace(go.Scatter(x=df['Period'], y=df['Net Margin (%)'], name="????????? (%)", line=dict(color='#10b981', width=2)), row=1, col=2)

    if 'Operating Cash Flow ($M)' in df.columns:
        fig.add_trace(go.Bar(x=df['Period'], y=df['Operating Cash Flow ($M)'], name="?????????????????? ($M)", marker_color='#60a5fa'), row=2, col=1)
    if 'Free Cash Flow ($M)' in df.columns:
        fig.add_trace(go.Scatter(x=df['Period'], y=df['Free Cash Flow ($M)'], name="??????????????? ($M)", line=dict(color='#059669', width=2.5)), row=2, col=1)
    if 'CapEx ($M)' in df.columns:
        fig.add_trace(go.Bar(x=df['Period'], y=df['CapEx ($M)'], name="???????????? ($M)", marker_color='#f87171'), row=2, col=1)

    if 'R&D Expenses ($M)' in df.columns:
        fig.add_trace(go.Bar(x=df['Period'], y=df['R&D Expenses ($M)'], name="???????????? ($M)", marker_color='#a78bfa'), row=2, col=2)
    if 'R&D / Rev (%)' in df.columns:
        fig.add_trace(go.Scatter(x=df['Period'], y=df['R&D / Rev (%)'], name="??????????????? (%)", line=dict(color='#ec4899', width=2)), row=2, col=2)

    title_text = f"{symbol} ??????????????????????????? ({period_type})" if symbol else f"??????????????????????????? ({period_type})"
    fig.update_layout(
        template="plotly_white",
        height=650,
        title_text=title_text,
        hovermode="x unified",
        showlegend=True
    )
    return fig


# ------------------------------------------------------------------
# 4. PE / PS Band ????????????????????????
# ------------------------------------------------------------------
def create_pe_ps_band_chart(
    df_stock: pd.DataFrame, 
    symbol: str, 
    current_eps: float = None, 
    current_rev_per_share: float = None, 
    timeframe: str = "3Y"
):
    """
    ????????????????????????????????? PE / PS ????????????????????????
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
            name=f"{symbol} ????????????",
            line=dict(color='#1e293b', width=2.5),
            hovertemplate=f"<b>{symbol} ??????</b>: $%{{y:.2f}}<extra></extra>"
        )
    )

    fig.update_layout(
        title=f"{symbol} {val_type} ?????????????????? ({val_type} Band) - [{timeframe}]",
        template="plotly_white",
        height=500,
        hovermode="x unified",
        yaxis_title="?????? ($ USD)",
        uirevision=f"{val_type.lower()}_band_{symbol}_{timeframe}"
    )
    return fig


# ------------------------------------------------------------------
# 5. ??????????????????????????????????????? (RSI, MACD, Bollinger Bands)
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
        subplot_titles=(f"{symbol} ?????????????????? (Bollinger Bands)", "MACD (12, 26, 9)", "RSI (14) ????????????")
    )

    fig.add_trace(go.Scatter(x=df['Date'], y=df['BB_Upper'], name="????????????", line=dict(color='rgba(148, 163, 184, 0.5)', dash='dot')), row=1, col=1)
    fig.add_trace(go.Scatter(x=df['Date'], y=df['BB_Lower'], name="????????????", fill='tonexty', fillcolor='rgba(241, 245, 249, 0.4)', line=dict(color='rgba(148, 163, 184, 0.5)', dash='dot')), row=1, col=1)
    fig.add_trace(go.Scatter(x=df['Date'], y=df['BB_Mid'], name="???????????? (20MA)", line=dict(color='#64748b', width=1.2)), row=1, col=1)
    fig.add_trace(go.Scatter(x=df['Date'], y=df['Close'], name=f"{symbol} ??????", line=dict(color='#2563eb', width=2)), row=1, col=1)

    fig.add_trace(go.Scatter(x=df['Date'], y=df['MACD'], name="MACD", line=dict(color='#3b82f6', width=1.5)), row=2, col=1)
    fig.add_trace(go.Scatter(x=df['Date'], y=df['Signal'], name="Signal (?????????)", line=dict(color='#f97316', width=1.5)), row=2, col=1)
    hist_colors = ['#22c55e' if h >= 0 else '#ef4444' for h in df['Hist']]
    fig.add_trace(go.Bar(x=df['Date'], y=df['Hist'], name="MACD ?????????", marker_color=hist_colors), row=2, col=1)

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
    fig.update_yaxes(title_text="??????", row=1, col=1)
    fig.update_yaxes(title_text="MACD", row=2, col=1)
    fig.update_yaxes(title_text="RSI", range=[0, 100], row=3, col=1)

    return fig


# ------------------------------------------------------------------
# 6. ????????????????????? Max Pain ??????????????????
# ------------------------------------------------------------------
def create_max_pain_chart(options_data: dict, current_price: float = None):
    """
    ???????????????????????????????????? Call / Put ???????????? (OI) ?????????????????? Max Pain ??????????????????
    """
    if not options_data or "df_strikes" not in options_data:
        return None
    df = options_data["df_strikes"].copy()
    if df.empty or 'strike' not in df.columns:
        return None

    symbol = options_data.get("symbol", "")
    exp_date = options_data.get("expiration", "")
    max_pain = options_data.get("max_pain_price", None)

    # ???????????????????????? 35% ???????????????????????????????????????????????????????????????????????????
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
            name="Call ??????????????? (OI)",
            marker_color='#16a34a',
            opacity=0.85
        )
    )

    fig.add_trace(
        go.Bar(
            x=df_plot['strike'],
            y=df_plot['put_oi'],
            name="Put ??????????????? (OI)",
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
            annotation_text=f"??????: ${current_price:.2f}",
            annotation_position="top right"
        )

    fig.update_layout(
        title=f"<b>{symbol} ?????????????????? (OI) ?????????????????????????????? (Max Pain) ??? ?????????: [{exp_date}]</b>",
        template="plotly_white",
        height=480,
        barmode="group",
        hovermode="x unified",
        xaxis_title="????????? (Strike Price $)",
        yaxis_title="????????????????????? (Contracts)",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    return fig


# ------------------------------------------------------------------
# 7. ??????????????????????????????????????????????????????????????????
# ------------------------------------------------------------------
def create_volatility_momentum_chart(df_metrics: pd.DataFrame, symbol: str, timeframe: str = "1Y"):
    """
    ????????????????????? Chandelier ??????????????????????????????20D ??????????????? (Bias %) ?????????????????? (BandWidth %)
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
            f"{symbol} ?????????20MA ??? Chandelier ?????????????????????????????????",
            f"20D ??????????????? (Bias %) ??? ????????????????????? (BandWidth %)"
        )
    )

    fig.add_trace(go.Scatter(x=df[date_col], y=df['Close'], name="?????????", line=dict(color='#2563eb', width=2)), row=1, col=1)

    ma20 = df['Close'].rolling(20).mean()
    fig.add_trace(go.Scatter(x=df[date_col], y=ma20, name="20MA", line=dict(color='#f59e0b', width=1.5, dash='dash')), row=1, col=1)

    if 'Chandelier_Exit' in df.columns:
        fig.add_trace(go.Scatter(x=df[date_col], y=df['Chandelier_Exit'], name="Chandelier ???????????????", line=dict(color='#dc2626', width=1.8, dash='dot')), row=1, col=1)

    if 'Bias20' in df.columns:
        bias_colors = ['#16a34a' if b >= 0 else '#ef4444' for b in df['Bias20']]
        fig.add_trace(go.Bar(x=df[date_col], y=df['Bias20'], name="20D ????????? (%)", marker_color=bias_colors, opacity=0.7), row=2, col=1)
        fig.add_hline(y=8.0, line_dash="dash", line_color="#dc2626", annotation_text="+8% ????????????", row=2, col=1)
        fig.add_hline(y=-8.0, line_dash="dash", line_color="#16a34a", annotation_text="-8% ????????????", row=2, col=1)

    if 'BandWidth' in df.columns:
        fig.add_trace(go.Scatter(x=df[date_col], y=df['BandWidth'], name="??????????????? (BandWidth %)", line=dict(color='#8b5cf6', width=1.8)), row=2, col=1)

    fig.update_layout(
        template="plotly_white",
        height=620,
        hovermode="x unified",
        uirevision=f"vol_mom_{symbol}_{timeframe}",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    fig.update_yaxes(title_text="?????? ($)", row=1, col=1)
    fig.update_yaxes(title_text="????????? / ?????? (%)", row=2, col=1)
    return fig


def create_interactive_reflexivity_radar(df, symbol: str):
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots
    import pandas as pd
    
    if df is None or df.empty or 'q1' not in df.columns:
        return None
        
    date_col = 'date' if 'date' in df.columns else df.index

    # Create subplots: 4 rows
    # Row 1: Price + 4-Quadrant Signals (40% height)
    # Row 2: ??????????????? (q1 & q1_dot) (20%)
    # Row 3: ???????????????????????????????????? (Gap & V_dot) (20%)
    # Row 4: ?????????????????? (BAA10Y & NFCI) (20%)
    fig = make_subplots(
        rows=4, cols=1, 
        shared_xaxes=True, 
        vertical_spacing=0.03,
        row_heights=[0.4, 0.2, 0.2, 0.2],
        subplot_titles=(
            f"[{symbol}] ????????????????????????????????? (4-Quadrant Signals)", 
            "Layer 2: ???????????? q1 (??????????????? %) ??? ???????????? q1_dot", 
            "Layer 3: ???????????? (Reflexive Gap) ??? ??????????????????????????? (v_dot)",
            "Layer 4: ?????????????????? (BAA10Y ?????? & NFCI ????????????)"
        ),
        specs=[[{"secondary_y": False}], [{"secondary_y": True}], [{"secondary_y": True}], [{"secondary_y": True}]]
    )
    
    # --- Row 1: Price and Signals ---
    fig.add_trace(go.Scatter(x=df[date_col], y=df['close'], mode='lines', name='Close Price', line=dict(color='black', width=1.5)), row=1, col=1)
    if 'MA50' in df.columns:
        fig.add_trace(go.Scatter(x=df[date_col], y=df['MA50'], mode='lines', name='50 MA', line=dict(color='blue', width=1, dash='dot')), row=1, col=1)
    if 'MA200' in df.columns:
        fig.add_trace(go.Scatter(x=df[date_col], y=df['MA200'], mode='lines', name='200 MA', line=dict(color='red', width=1.5)), row=1, col=1)

    if 'Trigger_Panic' in df.columns:
        df_panic = df[df['Trigger_Panic'] == True]
        fig.add_trace(go.Scatter(x=df_panic[date_col], y=df_panic['close'], mode='markers', name='I: ????????? (Panic)', marker=dict(color='fuchsia', size=12, symbol='triangle-up', line=dict(color='white', width=1))), row=1, col=1)
    if 'Trigger_Stage' in df.columns:
        df_stage = df[df['Trigger_Stage'] == True]
        fig.add_trace(go.Scatter(x=df_stage[date_col], y=df_stage['close'], mode='markers', name='II: ????????? (Stage)', marker=dict(color='blue', size=10, symbol='triangle-up', line=dict(color='white', width=1))), row=1, col=1)
    if 'Trigger_Bubble_Top' in df.columns:
        df_bubble = df[df['Trigger_Bubble_Top'] == True]
        fig.add_trace(go.Scatter(x=df_bubble[date_col], y=df_bubble['close'], mode='markers', name='III: ????????? (Bubble)', marker=dict(color='red', size=12, symbol='triangle-down', line=dict(color='white', width=1))), row=1, col=1)
    if 'Trigger_Bear_Top' in df.columns:
        df_bear = df[df['Trigger_Bear_Top'] == True]
        fig.add_trace(go.Scatter(x=df_bear[date_col], y=df_bear['close'], mode='markers', name='IV: ?????? (Bear Top)', marker=dict(color='orange', size=10, symbol='triangle-down', line=dict(color='white', width=1))), row=1, col=1)

    # --- Row 2: ??????????????? (q1 on primary y, q1_dot on secondary y) ---
    fig.add_trace(go.Scatter(x=df[date_col], y=df['q1'], mode='lines', name='q1 (?????????%)', line=dict(color='#8b5cf6', width=1.5)), row=2, col=1, secondary_y=False)
    fig.add_trace(go.Scatter(x=df[date_col], y=df['q1_dot'], mode='lines', name='q1_dot (??????)', line=dict(color='#10b981', width=1.5)), row=2, col=1, secondary_y=True)
    fig.add_hline(y=0, line_dash="dash", line_color="gray", row=2, col=1)

    # --- Row 3: ??????????????????????????? (Gap on primary, v_dot on secondary) ---
    if 'Gap' in df.columns:
        fig.add_trace(go.Scatter(x=df[date_col], y=df['Gap'], mode='lines', fill='tozeroy', name='Reflexive Gap', line=dict(color='rgba(255,165,0,0.7)', width=1)), row=3, col=1, secondary_y=False)
    if 'v_dot' in df.columns:
        fig.add_trace(go.Scatter(x=df[date_col], y=df['v_dot'], mode='lines', name='V_dot (????????????)', line=dict(color='#ef4444', width=1.5)), row=3, col=1, secondary_y=True)
    fig.add_hline(y=0, line_dash="dash", line_color="gray", row=3, col=1)

    # --- Row 4: ???????????? (BAA10Y on primary, NFCI on secondary) ---
    if 'BAA10Y' in df.columns:
        fig.add_trace(go.Scatter(x=df[date_col], y=df['BAA10Y'], mode='lines', name='BAA10Y ????????????', line=dict(color='#3b82f6', width=1.5)), row=4, col=1, secondary_y=False)
    if 'NFCI' in df.columns:
        fig.add_trace(go.Scatter(x=df[date_col], y=df['NFCI'], mode='lines', name='NFCI ????????????', line=dict(color='#f59e0b', width=1.5)), row=4, col=1, secondary_y=True)

    # Add range slider to x-axis
    fig.update_layout(
        height=1000,
        hovermode="x unified",
        template="plotly_white",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        xaxis4=dict(
            rangeslider=dict(visible=True, thickness=0.05),
            type="date"
        )
    )
    
    # Improve y-axis formatting
    fig.update_yaxes(title_text="q1 (%)", row=2, col=1, secondary_y=False)
    fig.update_yaxes(title_text="q1_dot", row=2, col=1, secondary_y=True)
    fig.update_yaxes(title_text="Gap Z-Score", row=3, col=1, secondary_y=False)
    fig.update_yaxes(title_text="V_dot", row=3, col=1, secondary_y=True)
    fig.update_yaxes(title_text="BAA10Y (%)", row=4, col=1, secondary_y=False)
    fig.update_yaxes(title_text="NFCI", row=4, col=1, secondary_y=True)

    return fig
