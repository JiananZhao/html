from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

# ------------------------------------------------------------------
# 1. 国债收益率形态演变图表
# ------------------------------------------------------------------
def create_treasury_chart(df_long: pd.DataFrame):
    if df_long is None or df_long.empty:
        return None
    df = df_long.copy()
    if 'Date' in df.columns:
        df['Date'] = pd.to_datetime(df['Date'])
        latest_date = df['Date'].max()
    else:
        return None

    mat_col = 'Maturity_Years' if 'Maturity_Years' in df.columns else ('Maturity_Label' if 'Maturity_Label' in df.columns else 'Maturity')
    date_1m = latest_date - pd.DateOffset(months=1)
    date_1y = latest_date - pd.DateOffset(years=1)

    available_dates = df['Date'].unique()
    
    def _find_nearest_date(target):
        past_dates = [d for d in available_dates if d <= target]
        return max(past_dates) if past_dates else min(available_dates)

    target_dates = [
        latest_date,
        _find_nearest_date(date_1m),
        _find_nearest_date(date_1y)
    ]

    df_filtered = df[df['Date'].isin(target_dates)].copy()
    df_filtered['Date_Str'] = df_filtered['Date'].dt.strftime('%Y-%m-%d')

    fig = px.line(
        df_filtered,
        x=mat_col,
        y='Yield',
        color='Date_Str',
        title='U.S. Treasury Yield Curve Comparison',
        labels={mat_col: '期限 (Maturity Years)', 'Yield': '收益率 (%)', 'Date_Str': '日期'},
        template='plotly_white'
    )
    fig.update_traces(mode='lines+markers', marker=dict(size=6))
    fig.update_layout(
        height=500,
        hovermode='x unified',
        uirevision='treasury_yield_chart',
        yaxis_title='收益率 (%)'
    )
    fig.update_yaxes(autorange=True, fixedrange=False)
    return fig

# ------------------------------------------------------------------
# 辅助函数：根据选定时间范围切片 DataFrame
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
def create_unemployment_chart(df_unrate: pd.DataFrame, y_range=None, timeframe="ALL"):
    if df_unrate is None or df_unrate.empty:
        return None
    df = df_unrate.copy()
    if 'date' in df.columns:
        date_col = 'date'
        df[date_col] = pd.to_datetime(df[date_col])
    elif 'Date' in df.columns:
        date_col = 'Date'
        df[date_col] = pd.to_datetime(df[date_col])
    else:
        df = df.reset_index()
        date_col = df.columns[0]
        df[date_col] = pd.to_datetime(df[date_col])

    val_col = 'Unemployment_Rate' if 'Unemployment_Rate' in df.columns else df.columns[1]
    df = filter_by_timeframe(df, date_col, timeframe)
    if df.empty:
        return None

    fig = px.line(
        df,
        x=date_col,
        y=val_col,
        title=f'UNRATE (美国失业率) - [{timeframe}]',
        labels={val_col: '失业率 (%)', date_col: '日期'},
        template="plotly_white",
        line_shape='spline'
    )
    avg_rate = df[val_col].mean()
    fig.add_hline(
        y=avg_rate,
        line_dash="dot",
        line_color="gray",
        annotation_text=f"阶段平均值 ({avg_rate:.1f}%)",
        annotation_position="bottom left",
    )
    fig.update_layout(
        hovermode="x unified",
        height=450,
        yaxis_title="失业率 (%)",
        uirevision=f"unemployment_chart_{timeframe}"
    )
    if y_range is not None:
        fig.update_yaxes(range=list(y_range), autorange=False)
    else:
        fig.update_yaxes(autorange=True, fixedrange=False)
    return fig

# ------------------------------------------------------------------
# 3. 信用利差图表 (Credit Spread)
# ------------------------------------------------------------------
def create_credit_spread_chart(df_data: pd.DataFrame, y_range=None, timeframe="ALL"):
    if df_data is None or df_data.empty:
        return None
    df = df_data.copy()
    if 'date' in df.columns:
        date_col = 'date'
        df[date_col] = pd.to_datetime(df[date_col])
    elif 'Date' in df.columns:
        date_col = 'Date'
        df[date_col] = pd.to_datetime(df[date_col])
    else:
        df = df.reset_index()
        date_col = df.columns[0]
        df[date_col] = pd.to_datetime(df[date_col])

    val_col = 'Value' if 'Value' in df.columns else df.columns[1]
    df = filter_by_timeframe(df, date_col, timeframe)
    if df.empty:
        return None

    fig = px.line(
        df,
        x=date_col,
        y=val_col,
        title=f'US High Yield Option-Adjusted Spread (高收益债信用利差) - [{timeframe}]',
        labels={val_col: '利差 (%)', date_col: '日期'},
        template="plotly_white"
    )
    fig.update_layout(
        hovermode="x unified",
        height=450,
        yaxis_title="利差 (%)",
        uirevision=f"credit_spread_chart_{timeframe}"
    )
    if y_range is not None:
        fig.update_yaxes(range=list(y_range), autorange=False)
    else:
        fig.update_yaxes(autorange=True, fixedrange=False)
    return fig

# ------------------------------------------------------------------
# 4. 美联储资产负债表图表 (Fed Balance Sheet)
# ------------------------------------------------------------------
def create_fed_balance_sheet_chart(df_fed: pd.DataFrame, y_range=None, timeframe="ALL"):
    if df_fed is None or df_fed.empty:
        return None
    df_fed = df_fed.copy()
    if 'date' in df_fed.columns:
        date_col = 'date'
        df_fed[date_col] = pd.to_datetime(df_fed[date_col])
    elif 'Date' in df_fed.columns:
        date_col = 'Date'
        df_fed[date_col] = pd.to_datetime(df_fed[date_col])
    else:
        df_fed = df_fed.reset_index()
        date_col = df_fed.columns[0]
        df_fed[date_col] = pd.to_datetime(df_fed[date_col])

    val_col = 'balance_sheet_tn' if 'balance_sheet_tn' in df_fed.columns else df_fed.columns[1]
    df_fed = filter_by_timeframe(df_fed, date_col, timeframe)
    if df_fed.empty:
        return None

    fig = px.line(
        df_fed,
        x=date_col,
        y=val_col,
        title=f"Fed Balance Sheet (美联储总资产, 万亿美元) - [{timeframe}]",
        labels={date_col: "Date", val_col: "Total Assets (Trillion USD)"},
        template="plotly_white"
    )
    fig.update_layout(
        hovermode="x unified",
        height=450,
        yaxis_title="Total Assets (Trillion USD)",
        uirevision=f"fed_balance_sheet_chart_{timeframe}"
    )
    if y_range is not None:
        fig.update_yaxes(range=list(y_range), autorange=False)
    else:
        fig.update_yaxes(autorange=True, fixedrange=False)
    return fig

# ------------------------------------------------------------------
# 5. 金油比图表 (Gold / Oil Ratio)
# ------------------------------------------------------------------
def create_gold_oil_ratio_chart(df_ratio: pd.DataFrame, y_range=None, timeframe="ALL"):
    if df_ratio is None or df_ratio.empty:
        return None
    df_ratio = df_ratio.copy()
    if 'date' in df_ratio.columns:
        date_col = 'date'
        df_ratio[date_col] = pd.to_datetime(df_ratio[date_col])
    elif 'Date' in df_ratio.columns:
        date_col = 'Date'
        df_ratio[date_col] = pd.to_datetime(df_ratio[date_col])
    else:
        df_ratio = df_ratio.reset_index()
        date_col = df_ratio.columns[0]
        df_ratio[date_col] = pd.to_datetime(df_ratio[date_col])

    df_ratio = filter_by_timeframe(df_ratio, date_col, timeframe)
    if df_ratio.empty:
        return None

    fig = px.line(
        df_ratio,
        x=date_col,
        y="gold_oil_ratio",
        title=f"Gold / Oil Ratio (金油比) - [{timeframe}]",
        labels={date_col: "Date", "gold_oil_ratio": "Gold / Oil Ratio"},
        template="plotly_white"
    )
    avg_ratio = df_ratio["gold_oil_ratio"].mean()
    fig.add_hline(
        y=avg_ratio,
        line_dash="dot",
        line_color="gray",
        annotation_text=f"阶段平均值 ({avg_ratio:.1f})",
        annotation_position="bottom left",
    )
    fig.update_layout(
        hovermode="x unified",
        height=450,
        yaxis_title="Gold / Oil Ratio",
        uirevision=f"gold_oil_ratio_chart_{timeframe}"
    )
    if y_range is not None:
        fig.update_yaxes(range=list(y_range), autorange=False)
    else:
        fig.update_yaxes(autorange=True, fixedrange=False)
    return fig

# ------------------------------------------------------------------
# 6. 10Y TIPS 实际利率与 10Y 盈亏平衡通胀率图表
# ------------------------------------------------------------------
def create_real_yield_breakeven_chart(df_data: pd.DataFrame, y_range=None, timeframe="ALL"):
    if df_data is None or df_data.empty:
        return None
    df = df_data.copy()
    date_col = 'date' if 'date' in df.columns else df.columns[0]
    df[date_col] = pd.to_datetime(df[date_col])

    cols = [c for c in ['10Y_Real_Yield', '10Y_Breakeven_Inflation'] if c in df.columns]
    if not cols:
        return None

    df = filter_by_timeframe(df, date_col, timeframe)
    if df.empty:
        return None

    fig = px.line(
        df,
        x=date_col,
        y=cols,
        title=f"10Y TIPS 实际利率 & 10Y 盈亏平衡通胀率 (%) - [{timeframe}]",
        labels={"value": "利率/通胀率 (%)", date_col: "Date", "variable": "指标"},
        template="plotly_white"
    )
    fig.update_layout(
        hovermode="x unified",
        height=450,
        yaxis_title="率 (%)",
        uirevision=f"real_yield_breakeven_chart_{timeframe}"
    )
    if y_range is not None:
        fig.update_yaxes(range=list(y_range), autorange=False)
    else:
        fig.update_yaxes(autorange=True, fixedrange=False)
    return fig

# ------------------------------------------------------------------
# 7. 芝加哥联储金融条件指数图表 (NFCI)
# ------------------------------------------------------------------
def create_nfci_chart(df_nfci: pd.DataFrame, y_range=None, timeframe="ALL"):
    if df_nfci is None or df_nfci.empty:
        return None
    df = df_nfci.copy()
    date_col = 'date' if 'date' in df.columns else df.columns[0]
    df[date_col] = pd.to_datetime(df[date_col])

    val_col = 'NFCI' if 'NFCI' in df.columns else df.columns[1]
    df = filter_by_timeframe(df, date_col, timeframe)
    if df.empty:
        return None

    fig = px.line(
        df,
        x=date_col,
        y=val_col,
        title=f"芝加哥联储全国金融条件指数 (NFCI) - [{timeframe}]",
        labels={val_col: "NFCI 指数", date_col: "Date"},
        template="plotly_white"
    )
    fig.add_hline(
        y=0,
        line_dash="dash",
        line_color="rgba(239, 68, 68, 0.7)",
        annotation_text="零轴分界 (<0宽松, >0紧缩)",
        annotation_position="top left"
    )
    fig.update_layout(
        hovermode="x unified",
        height=450,
        yaxis_title="NFCI 指数",
        uirevision=f"nfci_chart_{timeframe}"
    )
    if y_range is not None:
        fig.update_yaxes(range=list(y_range), autorange=False)
    else:
        fig.update_yaxes(autorange=True, fixedrange=False)
    return fig

# ------------------------------------------------------------------
# 8. 美联储净流动性与银行准备金余额图表
# ------------------------------------------------------------------
def create_net_liquidity_chart(df_liq: pd.DataFrame, y_range=None, timeframe="ALL"):
    if df_liq is None or df_liq.empty:
        return None
    df = df_liq.copy()
    date_col = 'date' if 'date' in df.columns else df.columns[0]
    df[date_col] = pd.to_datetime(df[date_col])

    cols = [c for c in ['Fed_Net_Liquidity_Tn', 'Bank_Reserves_Tn'] if c in df.columns]
    if not cols:
        return None

    df = filter_by_timeframe(df, date_col, timeframe)
    if df.empty:
        return None

    fig = px.line(
        df,
        x=date_col,
        y=cols,
        title=f"美联储净流动性 & 银行准备金余额 (万亿美元) - [{timeframe}]",
        labels={"value": "万亿美元 (Trillion USD)", date_col: "Date", "variable": "指标"},
        template="plotly_white"
    )
    fig.update_layout(
        hovermode="x unified",
        height=450,
        yaxis_title="万亿美元 (Trillion USD)",
        uirevision=f"net_liquidity_chart_{timeframe}"
    )
    if y_range is not None:
        fig.update_yaxes(range=list(y_range), autorange=False)
    else:
        fig.update_yaxes(autorange=True, fixedrange=False)
    return fig

# ------------------------------------------------------------------
# 9. SOFR - IORB 利率与利差双轴图表
# ------------------------------------------------------------------
def create_sofr_iorb_chart(df_sofr: pd.DataFrame, y_range=None, timeframe="ALL"):
    if df_sofr is None or df_sofr.empty:
        return None
    df = df_sofr.copy()
    date_col = 'date' if 'date' in df.columns else df.columns[0]
    df[date_col] = pd.to_datetime(df[date_col])

    df = filter_by_timeframe(df, date_col, timeframe)
    if df.empty:
        return None

    fig = go.Figure()

    if 'SOFR' in df.columns:
        fig.add_trace(go.Scatter(x=df[date_col], y=df['SOFR'], name="SOFR (%)", line=dict(color="#2563eb", width=2)))
    if 'IORB' in df.columns:
        fig.add_trace(go.Scatter(x=df[date_col], y=df['IORB'], name="IORB (%)", line=dict(color="#16a34a", width=2)))
    if 'Spread_bps' in df.columns:
        fig.add_trace(go.Scatter(x=df[date_col], y=df['Spread_bps'], name="SOFR - IORB 利差 (bps)", yaxis="y2", line=dict(color="#dc2626", width=1.5, dash="dot")))

    fig.update_layout(
        title=f"SOFR 隔夜融资利率 vs IORB 准备金利率 & 利差 (bps) - [{timeframe}]",
        template="plotly_white",
        height=450,
        hovermode="x unified",
        uirevision=f"sofr_iorb_chart_{timeframe}",
        yaxis=dict(title="利率 (%)"),
        yaxis2=dict(title="利差 (bps)", overlaying="y", side="right")
    )
    if y_range is not None:
        fig.update_yaxes(range=list(y_range), autorange=False)
    else:
        fig.update_yaxes(autorange=True, fixedrange=False)
    return fig

# ------------------------------------------------------------------
# 10. S&P 500 前十大权重股集中度饼图/柱状图
# ------------------------------------------------------------------
def create_top10_concentration_chart(df_top10: pd.DataFrame):
    if df_top10 is None or df_top10.empty:
        return None
    df = df_top10.copy()
    fig = px.pie(
        df,
        names="Company",
        values="Weight_Pct",
        title="S&P 500 前十大持仓权重占比 (总占比 39.30%)",
        color_discrete_sequence=px.colors.qualitative.Prism,
        template="plotly_white"
    )
    fig.update_traces(textposition='inside', textinfo='percent+label')
    fig.update_layout(
        height=450,
        uirevision="top10_pie_chart",
        legend=dict(orientation="h", yanchor="bottom", y=-0.2, xanchor="center", x=0.5)
    )
    return fig

# ------------------------------------------------------------------
# 11. CBOE VIX 恐慌指数图表
# ------------------------------------------------------------------
def create_vix_chart(df_vix: pd.DataFrame, y_range=None, timeframe="ALL"):
    if df_vix is None or df_vix.empty:
        return None
    df = df_vix.copy()
    if 'date' in df.columns:
        date_col = 'date'
        df[date_col] = pd.to_datetime(df[date_col])
    elif 'Date' in df.columns:
        date_col = 'Date'
        df[date_col] = pd.to_datetime(df[date_col])
    else:
        df = df.reset_index()
        date_col = df.columns[0]
        df[date_col] = pd.to_datetime(df[date_col])

    val_col = 'VIX' if 'VIX' in df.columns else df.columns[1]
    df = filter_by_timeframe(df, date_col, timeframe)
    if df.empty:
        return None

    fig = px.line(
        df,
        x=date_col,
        y=val_col,
        title=f'CBOE Volatility Index (VIX 恐慌指数) - [{timeframe}]',
        labels={val_col: 'VIX 指数', date_col: '日期'},
        template="plotly_white"
    )
    fig.add_hline(
        y=20,
        line_dash="dash",
        line_color="rgba(234, 179, 8, 0.8)",
        annotation_text="20 (情绪分界)",
        annotation_position="top left"
    )
    fig.add_hline(
        y=30,
        line_dash="dash",
        line_color="rgba(239, 68, 68, 0.8)",
        annotation_text="30 (高恐慌预警)",
        annotation_position="top left"
    )
    fig.update_layout(
        hovermode="x unified",
        height=450,
        yaxis_title="VIX 指数",
        uirevision=f"vix_chart_{timeframe}"
    )
    if y_range is not None:
        fig.update_yaxes(range=list(y_range), autorange=False)
    else:
        fig.update_yaxes(autorange=True, fixedrange=False)
    return fig

# ------------------------------------------------------------------
# 12. CNN 恐慌与贪婪指数图表 (Fear & Greed Index)
# ------------------------------------------------------------------
def create_cnn_fear_greed_chart(df_fgi: pd.DataFrame, y_range=None, timeframe="ALL"):
    if df_fgi is None or df_fgi.empty:
        return None
    df = df_fgi.copy()
    if 'date' in df.columns:
        date_col = 'date'
        df[date_col] = pd.to_datetime(df[date_col])
    elif 'Date' in df.columns:
        date_col = 'Date'
        df[date_col] = pd.to_datetime(df[date_col])
    else:
        df = df.reset_index()
        date_col = df.columns[0]
        df[date_col] = pd.to_datetime(df[date_col])

    val_col = 'Score' if 'Score' in df.columns else df.columns[1]
    df = filter_by_timeframe(df, date_col, timeframe)
    if df.empty:
        return None

    fig = px.line(
        df,
        x=date_col,
        y=val_col,
        title=f'CNN Fear & Greed Index (恐慌与贪婪指数) - [{timeframe}]',
        labels={val_col: '指数 Score (0-100)', date_col: '日期'},
        template="plotly_white"
    )
    fig.add_hline(
        y=25,
        line_dash="dash",
        line_color="rgba(220, 38, 38, 0.8)",
        annotation_text="25 (极度恐慌)",
        annotation_position="bottom left"
    )
    fig.add_hline(
        y=50,
        line_dash="dot",
        line_color="gray",
        annotation_text="50 (中性)",
        annotation_position="bottom left"
    )
    fig.add_hline(
        y=75,
        line_dash="dash",
        line_color="rgba(220, 38, 38, 0.8)",
        annotation_text="75 (极度贪婪)",
        annotation_position="top left"
    )
    fig.update_layout(
        hovermode="x unified",
        height=450,
        yaxis_title="指数分值 (0-100)",
        uirevision=f"cnn_fgi_chart_{timeframe}"
    )
    if y_range is not None:
        fig.update_yaxes(range=list(y_range), autorange=False)
    else:
        fig.update_yaxes(range=[0, 100], autorange=False)
    return fig

# ------------------------------------------------------------------
# 13. 国债收益率利差 (10Y-2Y & 10Y-3M)
# ------------------------------------------------------------------
def create_yield_spreads_chart(df_data: pd.DataFrame, timeframe="ALL"):
    if df_data is None or df_data.empty:
        return None
    df = df_data.copy()
    if 'date' in df.columns:
        date_col = 'date'
        df[date_col] = pd.to_datetime(df[date_col])
    else:
        df = df.reset_index()
        date_col = df.columns[0]
        df[date_col] = pd.to_datetime(df[date_col])

    df = filter_by_timeframe(df, date_col, timeframe)
    if df.empty:
        return None

    fig = go.Figure()
    if 'Spread_10Y2Y' in df.columns:
        fig.add_trace(go.Scatter(x=df[date_col], y=df['Spread_10Y2Y'], mode='lines', name='10Y-2Y 期限利差 (%)', line=dict(color='#2563eb', width=2)))
    if 'Spread_10Y3M' in df.columns:
        fig.add_trace(go.Scatter(x=df[date_col], y=df['Spread_10Y3M'], mode='lines', name='10Y-3M 期限利差 (%)', line=dict(color='#dc2626', width=1.5, dash='dot')))

    fig.add_hline(y=0.0, line_dash="solid", line_color="black", annotation_text="0 轴倒挂分界线")
    fig.update_layout(
        title=f"10Y-2Y & 10Y-3M 美债期限利差对比 - [{timeframe}]",
        template="plotly_white",
        height=450,
        hovermode="x unified",
        yaxis_title="利差 (%)",
        uirevision=f"yield_spreads_{timeframe}"
    )
    return fig

# ------------------------------------------------------------------
# 14. 个股量化与交互式 K 线 / 均线走势图
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
# 15. 半导体产业链标的相对表现走势图 (Normalized Performance)
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
# 16. 多期核心财务指标趋势走势图 (Revenue, Margin, FCF)
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
# 17. PE / PS Band 动态估值通道图表
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

    # 判断当前是 PS 模式还是 PE 模式
    is_ps_mode = (current_rev_per_share is not None and current_rev_per_share > 0)
    is_pe_mode = (current_eps is not None and current_eps > 0)

    if not is_pe_mode and not is_ps_mode:
        return None

    val_type = "PS" if is_ps_mode else "PE"
    base_metric = current_rev_per_share if is_ps_mode else current_eps
    
    # 估值通道倍数梯队：PS 模式使用 (4x, 8x, 12x, 16x, 22x)，PE 模式使用 (20x, 30x, 45x, 60x, 80x)
    multiples = [4, 8, 12, 16, 22] if is_ps_mode else [20, 30, 45, 60, 80]
    colors = ['#94a3b8', '#60a5fa', '#3b82f6', '#f59e0b', '#ef4444']

    fig = go.Figure()

    # 1. 绘制 5 条动态估值通道虚线
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

    # 2. 绘制真实股价
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

    # 3. 动态更新图表标题与布局
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
# 18. 技术动量与超买超卖信号图表 (RSI, MACD, Bollinger Bands)
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
# 19. 初请与续请失业金图表 (Jobless Claims)
# ------------------------------------------------------------------
def create_jobless_claims_chart(df_data: pd.DataFrame, timeframe="ALL"):
    if df_data is None or df_data.empty:
        return None
    df = df_data.copy()
    if 'date' in df.columns:
        date_col = 'date'
        df[date_col] = pd.to_datetime(df[date_col])
    else:
        df = df.reset_index()
        date_col = df.columns[0]
        df[date_col] = pd.to_datetime(df[date_col])

    df = filter_by_timeframe(df, date_col, timeframe)
    if df.empty:
        return None

    fig = go.Figure()
    if 'Initial_Claims' in df.columns:
        fig.add_trace(go.Scatter(x=df[date_col], y=df['Initial_Claims'], mode='lines', name='初请失业金 (周度)', line=dict(color='#2563eb', width=2)))
    if 'Continued_Claims' in df.columns:
        fig.add_trace(go.Scatter(x=df[date_col], y=df['Continued_Claims'], mode='lines', name='续请失业金', yaxis='y2', line=dict(color='#f97316', width=1.5, dash='dot')))

    fig.update_layout(
        title=f"美国初请与续请失业金人数高频追踪 - [{timeframe}]",
        template="plotly_white",
        height=450,
        hovermode="x unified",
        yaxis=dict(title="初请失业金 (人数)"),
        yaxis2=dict(title="续请失业金 (人数)", overlaying="y", side="right"),
        uirevision=f"jobless_claims_{timeframe}"
    )
    return fig

# ------------------------------------------------------------------
# 20. 美元指数图表 (DXY)
# ------------------------------------------------------------------
def create_dxy_chart(df_data: pd.DataFrame, timeframe="ALL"):
    if df_data is None or df_data.empty:
        return None
    df = df_data.copy()
    if 'date' in df.columns:
        date_col = 'date'
        df[date_col] = pd.to_datetime(df[date_col])
    else:
        df = df.reset_index()
        date_col = df.columns[0]
        df[date_col] = pd.to_datetime(df[date_col])

    val_col = 'DXY' if 'DXY' in df.columns else df.columns[1]
    df = filter_by_timeframe(df, date_col, timeframe)
    if df.empty:
        return None

    fig = px.line(
        df,
        x=date_col,
        y=val_col,
        title=f"Nominal Broad U.S. Dollar Index (美元指数) - [{timeframe}]",
        labels={val_col: '美元指数', date_col: '日期'},
        template="plotly_white"
    )
    fig.update_layout(
        hovermode="x unified",
        height=450,
        yaxis_title="美元指数点位",
        uirevision=f"dxy_chart_{timeframe}"
    )
    return fig

# ------------------------------------------------------------------
# 21. 核心 CPI 与薪资增速图表
# ------------------------------------------------------------------
def create_inflation_wages_chart(df_data: pd.DataFrame, timeframe="ALL"):
    if df_data is None or df_data.empty:
        return None
    df = df_data.copy()
    if 'date' in df.columns:
        date_col = 'date'
        df[date_col] = pd.to_datetime(df[date_col])
    else:
        df = df.reset_index()
        date_col = df.columns[0]
        df[date_col] = pd.to_datetime(df[date_col])

    df = filter_by_timeframe(df, date_col, timeframe)
    if df.empty:
        return None

    fig = go.Figure()
    if 'Core_CPI_YoY' in df.columns:
        fig.add_trace(go.Scatter(x=df[date_col], y=df['Core_CPI_YoY'], mode='lines', name='核心 CPI 同比 (%)', line=dict(color='#dc2626', width=2)))
    if 'Wages_YoY' in df.columns:
        fig.add_trace(go.Scatter(x=df[date_col], y=df['Wages_YoY'], mode='lines', name='平均时薪同比 (%)', line=dict(color='#16a34a', width=2)))

    fig.add_hline(y=2.0, line_dash="dash", line_color="gray", annotation_text="2% 通胀目标")
    fig.update_layout(
        title=f"核心 CPI 通胀 vs. 平均时薪增速同比 - [{timeframe}]",
        template="plotly_white",
        height=450,
        hovermode="x unified",
        yaxis_title="同比增速 (%)",
        uirevision=f"inf_wages_{timeframe}"
    )
    return fig

# ------------------------------------------------------------------
# 22. 萨姆规则衰退指标图表 (Sahm Rule)
# ------------------------------------------------------------------
def create_sahm_rule_chart(df_data: pd.DataFrame, timeframe="ALL"):
    if df_data is None or df_data.empty:
        return None
    df = df_data.copy()
    if 'date' in df.columns:
        date_col = 'date'
        df[date_col] = pd.to_datetime(df[date_col])
    else:
        df = df.reset_index()
        date_col = df.columns[0]
        df[date_col] = pd.to_datetime(df[date_col])

    val_col = 'Sahm_Rule' if 'Sahm_Rule' in df.columns else df.columns[1]
    df = filter_by_timeframe(df, date_col, timeframe)
    if df.empty:
        return None

    fig = px.line(
        df,
        x=date_col,
        y=val_col,
        title=f"Sahm Rule Recession Indicator (萨姆规则衰退指标) - [{timeframe}]",
        labels={val_col: '萨姆指标值', date_col: '日期'},
        template="plotly_white"
    )
    fig.add_hline(y=0.50, line_dash="dash", line_color="red", annotation_text="0.50 衰退触发警戒线", annotation_position="top left")
    fig.update_layout(
        hovermode="x unified",
        height=450,
        yaxis_title="指标点位",
        uirevision=f"sahm_chart_{timeframe}"
    )
    return fig

# ------------------------------------------------------------------
# 23. 核心资本品新订单图表 (Core CapEx Orders)
# ------------------------------------------------------------------
def create_core_capex_chart(df_data: pd.DataFrame, timeframe="ALL"):
    if df_data is None or df_data.empty:
        return None
    df = df_data.copy()
    if 'date' in df.columns:
        date_col = 'date'
        df[date_col] = pd.to_datetime(df[date_col])
    else:
        df = df.reset_index()
        date_col = df.columns[0]
        df[date_col] = pd.to_datetime(df[date_col])

    df = filter_by_timeframe(df, date_col, timeframe)
    if df.empty:
        return None

    fig = go.Figure()
    if 'Core_CapEx' in df.columns:
        fig.add_trace(go.Scatter(x=df[date_col], y=df['Core_CapEx'], mode='lines', name='核心资本品订单规模 ($M)', line=dict(color='#2563eb', width=2)))
    if 'Core_CapEx_YoY' in df.columns:
        fig.add_trace(go.Bar(x=df[date_col], y=df['Core_CapEx_YoY'], name='订单同比增速 (%)', yaxis='y2', marker_color='#93c5fd', opacity=0.6))

    fig.update_layout(
        title=f"核心资本品订单规模与同比增速 (前瞻资本开支) - [{timeframe}]",
        template="plotly_white",
        height=450,
        hovermode="x unified",
        yaxis=dict(title="规模 ($M)"),
        yaxis2=dict(title="同比增速 (%)", overlaying="y", side="right"),
        uirevision=f"core_capex_{timeframe}"
    )
    return fig

# ------------------------------------------------------------------
# 24. 广义货币供应量 M2 图表
# ------------------------------------------------------------------
def create_m2_money_supply_chart(df_data: pd.DataFrame, timeframe="ALL"):
    if df_data is None or df_data.empty:
        return None
    df = df_data.copy()
    if 'date' in df.columns:
        date_col = 'date'
        df[date_col] = pd.to_datetime(df[date_col])
    else:
        df = df.reset_index()
        date_col = df.columns[0]
        df[date_col] = pd.to_datetime(df[date_col])

    df = filter_by_timeframe(df, date_col, timeframe)
    if df.empty:
        return None

    fig = go.Figure()
    if 'M2' in df.columns:
        fig.add_trace(go.Scatter(x=df[date_col], y=df['M2'], mode='lines', name='M2 货币供应总量 ($B)', line=dict(color='#059669', width=2)))
    if 'M2_YoY' in df.columns:
        fig.add_trace(go.Scatter(x=df[date_col], y=df['M2_YoY'], mode='lines', name='M2 同比增速 (%)', yaxis='y2', line=dict(color='#f59e0b', width=1.5, dash='dot')))

    fig.add_hline(y=0.0, line_dash="solid", line_color="black", yref="y2")
    fig.update_layout(
        title=f"M2 广义货币供应量总量与同比增速 - [{timeframe}]",
        template="plotly_white",
        height=450,
        hovermode="x unified",
        yaxis=dict(title="总量 ($B)"),
        yaxis2=dict(title="同比增速 (%)", overlaying="y", side="right"),
        uirevision=f"m2_chart_{timeframe}"
    )
    return fig

# ------------------------------------------------------------------
# 25. 银行贷款标准 SLOOS 图表
# ------------------------------------------------------------------
def create_sloos_credit_chart(df_data: pd.DataFrame, timeframe="ALL"):
    if df_data is None or df_data.empty:
        return None
    df = df_data.copy()
    if 'date' in df.columns:
        date_col = 'date'
        df[date_col] = pd.to_datetime(df[date_col])
    else:
        df = df.reset_index()
        date_col = df.columns[0]
        df[date_col] = pd.to_datetime(df[date_col])

    val_col = 'Tightening_Net_Pct' if 'Tightening_Net_Pct' in df.columns else df.columns[1]
    df = filter_by_timeframe(df, date_col, timeframe)
    if df.empty:
        return None

    fig = px.line(
        df,
        x=date_col,
        y=val_col,
        title=f"美联储高级贷款官意见调查 (SLOOS 银行信贷净收紧比例) - [{timeframe}]",
        labels={val_col: '净收紧比例 (%)', date_col: '日期'},
        template="plotly_white"
    )
    fig.add_hline(y=0.0, line_dash="solid", line_color="black", annotation_text="0% (正值收紧 / 负值放宽)")
    fig.update_layout(
        hovermode="x unified",
        height=450,
        yaxis_title="净收紧银行占比 (%)",
        uirevision=f"sloos_chart_{timeframe}"
    )
    return fig
