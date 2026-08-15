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
        line_color="rgba(22, 163, 74, 0.8)",
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
# 14. 个股量化与交互式 K 线 / 均线走势图
# ------------------------------------------------------------------
def create_stock_price_chart(df_stock: pd.DataFrame, symbol: str, chart_type: str = "Candlestick", timeframe: str = "1Y"):
    """
    绘制个股交互式价格走势图，支持 Candlestick / Line 切换，叠加 20MA, 50MA, 200MA 与成交量副图
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
    
    col_map = {c: c.capitalize() for c in df.columns if c.lower() in ['open', 'high', 'low', 'close', 'volume']}
    df.rename(columns=col_map, inplace=True)

    if 'Close' in df.columns:
        df['MA20'] = df['Close'].rolling(window=20).mean()
        df['MA50'] = df['Close'].rolling(window=50).mean()
        df['MA200'] = df['Close'].rolling(window=200).mean()

    df = filter_by_timeframe(df, 'Date', timeframe)
    if df.empty:
        return None

    from plotly.subplots import make_subplots
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
            go.Scatter(
                x=df['Date'],
                y=df['Close'],
                mode='lines',
                name=f"{symbol} 收盘价",
                line=dict(color='#2563eb', width=2),
                showlegend=True
            ),
            row=1, col=1
        )

    if 'MA20' in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df['Date'], y=df['MA20'],
                mode='lines', name='20 MA (月线)',
                line=dict(color='#f59e0b', width=1.5),
                showlegend=True
            ),
            row=1, col=1
        )
    if 'MA50' in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df['Date'], y=df['MA50'],
                mode='lines', name='50 MA (季线)',
                line=dict(color='#06b6d4', width=1.5),
                showlegend=True
            ),
            row=1, col=1
        )
    if 'MA200' in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df['Date'], y=df['MA200'],
                mode='lines', name='200 MA (年线/牛熊分界)',
                line=dict(color='#8b5cf6', width=2),
                showlegend=True
            ),
            row=1, col=1
        )

    if has_volume:
        vol_colors = []
        if has_ohlc:
            for _, row in df.iterrows():
                if row['Close'] >= row['Open']:
                    vol_colors.append('rgba(34, 197, 94, 0.6)')
                else:
                    vol_colors.append('rgba(239, 68, 68, 0.6)')
        else:
            vol_colors = 'rgba(100, 116, 139, 0.6)'

        fig.add_trace(
            go.Bar(
                x=df['Date'],
                y=df['Volume'],
                name="成交量",
                marker_color=vol_colors,
                showlegend=False
            ),
            row=2, col=1
        )
        fig.update_yaxes(title_text="Volume", row=2, col=1)

    fig.update_layout(
        template="plotly_white",
        hovermode="x unified",
        xaxis_rangeslider_visible=False,
        height=580,
        margin=dict(l=40, r=40, t=50, b=40),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        uirevision=f"stock_chart_{symbol}_{timeframe}_{chart_type}"
    )
    fig.update_yaxes(title_text="股价 (USD)", row=1, col=1)

    return fig


# ------------------------------------------------------------------
# 15. 半导体产业链多股归一化相对收益对比图
# ------------------------------------------------------------------
def create_relative_performance_chart(df_prices: pd.DataFrame, tickers: list, timeframe: str = "YTD"):
    """
    计算多股相对于区间基准日的百分比累计收益率 ((P_t / P_0 - 1) * 100) 并绘制对比图
    """
    if df_prices is None or df_prices.empty:
        return None

    df = df_prices.copy()
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
    if df.empty or len(df) < 2:
        return None

    valid_tickers = [t for t in tickers if t in df.columns and df[t].dropna().count() > 1]
    if not valid_tickers:
        return None

    fig = go.Figure()

    palette = [
        '#2563eb', '#16a34a', '#dc2626', '#d97706', '#9333ea',
        '#0891b2', '#e11d48', '#4f46e5', '#059669', '#ca8a04',
        '#7c3aed', '#0284c7', '#be123c', '#475569'
    ]

    for i, ticker in enumerate(valid_tickers):
        s = df[ticker].dropna()
        if s.empty:
            continue
        base_val = s.iloc[0]
        if base_val == 0 or pd.isna(base_val):
            continue
        norm_series = (df[ticker] / base_val - 1.0) * 100.0
        color = palette[i % len(palette)]
        width = 2.5 if ticker in ['NVDA', 'SOXX', 'SMH'] else 1.8
        
        fig.add_trace(
            go.Scatter(
                x=df['Date'],
                y=norm_series,
                mode='lines',
                name=ticker,
                line=dict(color=color, width=width),
                hovertemplate=f"<b>{ticker}</b>: %{{y:+.2f}}%<extra></extra>"
            )
        )

    fig.add_hline(
        y=0,
        line_dash="dash",
        line_color="gray",
        annotation_text="0% 基准线",
        annotation_position="bottom left"
    )

    fig.update_layout(
        title=f"半导体核心标的累计收益率对比 (Relative Performance) - [{timeframe}]",
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
        uirevision=f"semi_rel_perf_{timeframe}"
    )

    return fig


# ------------------------------------------------------------------
# 16. 个股季度/年度核心财务规模与利润率走势双轴图
# ------------------------------------------------------------------
def create_financial_trends_chart(df_trends: pd.DataFrame, period_type: str = "季度"):
    """
    绘制个股营收、净利润、自由现金流规模 (柱状图) 与毛利率、净利率 (双轴折线图)
    """
    if df_trends is None or df_trends.empty:
        return None

    from plotly.subplots import make_subplots
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    if 'Revenue_Bn' in df_trends.columns:
        fig.add_trace(
            go.Bar(
                x=df_trends['Period'],
                y=df_trends['Revenue_Bn'],
                name="总营收 ($B)",
                marker_color='#3b82f6',
                hovertemplate="%{x} 营收: $%{y:.2f} B<extra></extra>"
            ),
            secondary_y=False
        )

    if 'NetIncome_Bn' in df_trends.columns:
        fig.add_trace(
            go.Bar(
                x=df_trends['Period'],
                y=df_trends['NetIncome_Bn'],
                name="净利润 ($B)",
                marker_color='#10b981',
                hovertemplate="%{x} 净利润: $%{y:.2f} B<extra></extra>"
            ),
            secondary_y=False
        )

    if 'FCF_Bn' in df_trends.columns and (df_trends['FCF_Bn'] != 0).any():
        fig.add_trace(
            go.Bar(
                x=df_trends['Period'],
                y=df_trends['FCF_Bn'],
                name="自由现金流 FCF ($B)",
                marker_color='#f59e0b',
                hovertemplate="%{x} FCF: $%{y:.2f} B<extra></extra>"
            ),
            secondary_y=False
        )

    if 'GrossMargin_Pct' in df_trends.columns:
        fig.add_trace(
            go.Scatter(
                x=df_trends['Period'],
                y=df_trends['GrossMargin_Pct'],
                name="毛利率 (%)",
                mode="lines+markers",
                line=dict(color='#8b5cf6', width=2.5),
                marker=dict(size=6),
                hovertemplate="%{x} 毛利率: %{y:.1f}%<extra></extra>"
            ),
            secondary_y=True
        )

    if 'NetMargin_Pct' in df_trends.columns:
        fig.add_trace(
            go.Scatter(
                x=df_trends['Period'],
                y=df_trends['NetMargin_Pct'],
                name="净利润率 (%)",
                mode="lines+markers",
                line=dict(color='#ec4899', width=2.5, dash="dot"),
                marker=dict(size=6),
                hovertemplate="%{x} 净利率: %{y:.1f}%<extra></extra>"
            ),
            secondary_y=True
        )

    fig.update_layout(
        title=f"个股历年{period_type}核心财务规模 ($B) 与盈利质量趋势 (%)",
        template="plotly_white",
        barmode='group',
        hovermode="x unified",
        height=480,
        margin=dict(l=40, r=40, t=50, b=40),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        uirevision=f"fin_trends_{period_type}"
    )

    fig.update_yaxes(title_text="金额 (十亿美元, $B)", secondary_y=False)
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
    
    if current_eps and current_eps > 0:
        base_metric = current_eps
    elif current_pe and current_pe > 0:
        base_metric = df[close_col].iloc[-1] / current_pe
    else:
        base_metric = df[close_col].mean() / 25.0

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
    col_map = {c: c.capitalize() for c in df.columns if c.lower() in ['open', 'high', 'low', 'close', 'volume']}
    df.rename(columns=col_map, inplace=True)

    if 'Close' not in df.columns:
        return None

    df['MA20'] = df['Close'].rolling(window=20).mean()
    df['MA50'] = df['Close'].rolling(window=50).mean()
    df['MA200'] = df['Close'].rolling(window=200).mean()

    ema12 = df['Close'].ewm(span=12, adjust=False).mean()
    ema26 = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = ema12 - ema26
    df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['MACD_Hist'] = df['MACD'] - df['MACD_Signal']

    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0.0)).fillna(0.0)
    loss = (-delta.where(delta < 0, 0.0)).fillna(0.0)
    avg_gain = gain.ewm(alpha=1.0/14.0, min_periods=14, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1.0/14.0, min_periods=14, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    df['RSI'] = (100.0 - (100.0 / (1.0 + rs))).fillna(50.0)

    df = filter_by_timeframe(df, 'Date', timeframe)
    if df.empty or len(df) < 5:
        return None

    from plotly.subplots import make_subplots
    fig = make_subplots(
        rows=3, cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.55, 0.25, 0.20],
        subplot_titles=(
            f"{symbol} 价格走势与均线系统 (MA20 / MA50 / MA200)",
            "MACD (12, 26, 9) 动量指标",
            "RSI (14) 强弱动量 (30 超卖 / 70 超买)"
        )
    )

    has_ohlc = all(c in df.columns for c in ['Open', 'High', 'Low', 'Close'])
    if has_ohlc:
        fig.add_trace(
            go.Candlestick(
                x=df['Date'], open=df['Open'], high=df['High'], low=df['Low'], close=df['Close'],
                name="K线", increasing_line_color='#22c55e', decreasing_line_color='#ef4444', showlegend=False
            ),
            row=1, col=1
        )
    else:
        fig.add_trace(
            go.Scatter(x=df['Date'], y=df['Close'], mode='lines', name="收盘价", line=dict(color='#2563eb', width=2)),
            row=1, col=1
        )

    fig.add_trace(go.Scatter(x=df['Date'], y=df['MA20'], mode='lines', name="20 MA", line=dict(color='#f59e0b', width=1.2)), row=1, col=1)
    fig.add_trace(go.Scatter(x=df['Date'], y=df['MA50'], mode='lines', name="50 MA", line=dict(color='#06b6d4', width=1.2)), row=1, col=1)
    fig.add_trace(go.Scatter(x=df['Date'], y=df['MA200'], mode='lines', name="200 MA (年线)", line=dict(color='#8b5cf6', width=2)), row=1, col=1)

    hist_colors = ['rgba(34, 197, 94, 0.7)' if h >= 0 else 'rgba(239, 68, 68, 0.7)' for h in df['MACD_Hist']]
    fig.add_trace(go.Bar(x=df['Date'], y=df['MACD_Hist'], name="MACD 柱 (Hist)", marker_color=hist_colors, showlegend=False), row=2, col=1)
    fig.add_trace(go.Scatter(x=df['Date'], y=df['MACD'], mode='lines', name="DIF (快线)", line=dict(color='#2563eb', width=1.5)), row=2, col=1)
    fig.add_trace(go.Scatter(x=df['Date'], y=df['MACD_Signal'], mode='lines', name="DEA (慢线)", line=dict(color='#f97316', width=1.5)), row=2, col=1)

    fig.add_trace(go.Scatter(x=df['Date'], y=df['RSI'], mode='lines', name="RSI(14)", line=dict(color='#7c3aed', width=2)), row=3, col=1)
    fig.add_hline(y=70, line_dash="dash", line_color="rgba(239, 68, 68, 0.8)", row=3, col=1)
    fig.add_hline(y=30, line_dash="dash", line_color="rgba(34, 197, 94, 0.8)", row=3, col=1)

    fig.update_layout(
        template="plotly_white",
        hovermode="x unified",
        xaxis_rangeslider_visible=False,
        height=680,
        margin=dict(l=40, r=40, t=50, b=40),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        uirevision=f"tech_chart_{symbol}_{timeframe}"
    )

    fig.update_yaxes(title_text="股价", row=1, col=1)
    fig.update_yaxes(title_text="MACD", row=2, col=1)
    fig.update_yaxes(title_text="RSI", range=[0, 100], row=3, col=1)

    return fig
