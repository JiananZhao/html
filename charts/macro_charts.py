from plotly.subplots import make_subplots
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

from charts.theme import filter_by_timeframe, apply_chart_theme

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
# 10. S&P 500 前十大权重股集中度饼图
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
# 14. 初请与续请失业金图表 (Jobless Claims)
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
# 15. 美元指数图表 (DXY)
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
# 16. 核心 CPI 与薪资增速图表
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
# 17. 萨姆规则衰退指标图表 (Sahm Rule)
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
# 18. 核心资本品新订单图表 (Core CapEx Orders)
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
# 19. 广义货币供应量 M2 图表
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
# 20. 银行贷款标准 SLOOS 图表
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


# ------------------------------------------------------------------
# 21. 股权风险溢价 (ERP) 综合图表
# ------------------------------------------------------------------
def create_erp_chart(erp_dict: dict, timeframe: str = "3Y"):
    if not erp_dict or "df_history" not in erp_dict:
        return None
    df = filter_by_timeframe(erp_dict["df_history"].copy(), 'date', timeframe)
    if df.empty:
        return None

    current_ey = erp_dict.get("current_ey", 4.65)
    df['Earnings_Yield'] = current_ey
    df['ERP'] = df['Earnings_Yield'] - df['10Y_Yield']

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    
    # 标普 500 盈利收益率 vs 10Y 美债利率
    fig.add_trace(go.Scatter(x=df['date'], y=df['10Y_Yield'], name="10Y 美债收益率 (%)", line=dict(color='#ef4444', width=2)), secondary_y=False)
    fig.add_trace(go.Scatter(x=df['date'], y=df['Earnings_Yield'], name="标普 500 盈利收益率 (%)", line=dict(color='#22c55e', width=2, dash='dot')), secondary_y=False)
    
    # ERP 溢价利差柱状填充
    colors = ['#3b82f6' if val >= 0 else '#f97316' for val in df['ERP']]
    fig.add_trace(go.Bar(x=df['date'], y=df['ERP'], name="ERP 风险溢价差 (EY - 10Y)", marker_color=colors, opacity=0.35), secondary_y=True)

    fig.add_hline(y=0, line_dash="dash", line_color="gray", secondary_y=True)
    fig.update_layout(
        title="<b>S&P 500 股权风险溢价 (Equity Risk Premium, ERP)</b>",
        hovermode="x unified",
        template="plotly_dark",
        height=450,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    fig.update_yaxes(title_text="收益率 (%)", secondary_y=False)
    fig.update_yaxes(title_text="ERP 风险溢价 (%)", secondary_y=True)
    return fig


# ------------------------------------------------------------------
# 22. CBOE SKEW 与暗池 DIX 双子图
# ------------------------------------------------------------------
def create_skew_dix_chart(skew_dix_dict: dict, timeframe: str = "1Y"):
    df_skew = skew_dix_dict.get("df_skew", pd.DataFrame())
    df_dix = skew_dix_dict.get("df_dix", pd.DataFrame())
    
    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08,
                        subplot_titles=("<b>CBOE SKEW 黑天鹅偏度指数 (左尾极端尾部防守)</b>",
                                        "<b>SqueezeMetrics DIX 暗池机构买入比例 (%)</b>"))
    
    # 1. SKEW
    if not df_skew.empty:
        df_s = filter_by_timeframe(df_skew.copy(), 'date', timeframe)
        if not df_s.empty:
            fig.add_trace(go.Scatter(x=df_s['date'], y=df_s['SKEW'], name="SKEW 指数", line=dict(color='#a855f7', width=2)), row=1, col=1)
            fig.add_hline(y=140, line_dash="dash", line_color="#ef4444", annotation_text="高防守警戒线 (140)", row=1, col=1)
            fig.add_hline(y=120, line_dash="dot", line_color="#94a3b8", row=1, col=1)

    # 2. DIX
    if not df_dix.empty:
        df_d = filter_by_timeframe(df_dix.copy(), 'date', timeframe)
        if not df_d.empty:
            fig.add_trace(go.Scatter(x=df_d['date'], y=df_d['DIX_pct'], name="DIX 暗池买入比 (%)", line=dict(color='#38bdf8', width=2)), row=2, col=1)
            fig.add_hline(y=45.0, line_dash="dash", line_color="#22c55e", annotation_text="机构多头强吸筹线 (45%)", row=2, col=1)
            fig.add_hline(y=40.0, line_dash="dot", line_color="#94a3b8", row=2, col=1)

    fig.update_layout(template="plotly_dark", height=550, hovermode="x unified", showlegend=False)
    return fig


# ------------------------------------------------------------------
# 23. 跨资产避险/风险偏好比率 (铜金比 & HYG/TLT)
# ------------------------------------------------------------------
def create_cross_asset_ratios_chart(df_ratios: pd.DataFrame, timeframe: str = "2Y"):
    if df_ratios is None or df_ratios.empty:
        return None
    df = filter_by_timeframe(df_ratios.copy(), 'date', timeframe)
    if df.empty:
        return None

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.08,
                        subplot_titles=("<b>铜金比 (Copper / Gold Ratio × 1000) — 工业复苏 vs 避险</b>",
                                        "<b>信用利差风险比率 (HYG / TLT) — 风险偏好 Risk-On 体温计</b>"))
    
    # 铜金比
    if 'Copper_Gold_Ratio' in df.columns:
        fig.add_trace(go.Scatter(x=df['date'], y=df['Copper_Gold_Ratio'], name="铜金比", line=dict(color='#f59e0b', width=2)), row=1, col=1)
        if 'CG_MA50' in df.columns:
            fig.add_trace(go.Scatter(x=df['date'], y=df['CG_MA50'], name="50日均线", line=dict(color='#cbd5e1', width=1, dash='dot')), row=1, col=1)

    # HYG / TLT
    if 'HYG_TLT_Ratio' in df.columns:
        fig.add_trace(go.Scatter(x=df['date'], y=df['HYG_TLT_Ratio'], name="HYG/TLT", line=dict(color='#10b981', width=2)), row=2, col=1)
        if 'HT_MA50' in df.columns:
            fig.add_trace(go.Scatter(x=df['date'], y=df['HT_MA50'], name="50日均线", line=dict(color='#cbd5e1', width=1, dash='dot')), row=2, col=1)

    fig.update_layout(template="plotly_dark", height=550, hovermode="x unified", showlegend=True)
    return fig
