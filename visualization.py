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
        template="plotly_white",
        line_shape='spline'
    )
    fig.add_hline(
        y=4.0,
        line_dash="dot",
        line_color="red",
        annotation_text="4.0% 压力警戒线",
        annotation_position="top left"
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
# 4. 美联储总资产规模图表 (WALCL)
# ------------------------------------------------------------------
def create_fed_balance_sheet_chart(df_data: pd.DataFrame, y_range=None, timeframe="ALL"):
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

    val_col = 'Fed_Assets_Trillions' if 'Fed_Assets_Trillions' in df.columns else df.columns[1]
    df = filter_by_timeframe(df, date_col, timeframe)
    if df.empty:
        return None

    fig = px.line(
        df,
        x=date_col,
        y=val_col,
        title=f'Federal Reserve Total Assets (美联储总资产规模) - [{timeframe}]',
        labels={val_col: '总资产 (万亿美元)', date_col: '日期'},
        template="plotly_white"
    )
    fig.update_layout(
        hovermode="x unified",
        height=450,
        yaxis_title="总资产 (万亿美元)",
        uirevision=f"fed_bs_chart_{timeframe}"
    )
    if y_range is not None:
        fig.update_yaxes(range=list(y_range), autorange=False)
    else:
        fig.update_yaxes(autorange=True, fixedrange=False)
    return fig

# ------------------------------------------------------------------
# 5. 金油比图表 (Gold / Oil Ratio)
# ------------------------------------------------------------------
def create_gold_oil_ratio_chart(df_data: pd.DataFrame, y_range=None, timeframe="ALL"):
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

    val_col = 'Gold_Oil_Ratio' if 'Gold_Oil_Ratio' in df.columns else df.columns[1]
    df = filter_by_timeframe(df, date_col, timeframe)
    if df.empty:
        return None

    fig = px.line(
        df,
        x=date_col,
        y=val_col,
        title=f'Gold / Oil Ratio (金油比) - [{timeframe}]',
        labels={val_col: '比值', date_col: '日期'},
        template="plotly_white"
    )
    fig.add_hline(
        y=25.0,
        line_dash="dot",
        line_color="orange",
        annotation_text="25 宏观风险分界线",
        annotation_position="bottom left"
    )
    fig.update_layout(
        hovermode="x unified",
        height=450,
        yaxis_title="金油比",
        uirevision=f"gold_oil_chart_{timeframe}"
    )
    if y_range is not None:
        fig.update_yaxes(range=list(y_range), autorange=False)
    else:
        fig.update_yaxes(autorange=True, fixedrange=False)
    return fig

# ------------------------------------------------------------------
# 6. 实际利率与通胀预期图表 (Real Yield & Breakeven)
# ------------------------------------------------------------------
def create_real_yield_breakeven_chart(df_data: pd.DataFrame, timeframe="ALL"):
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
    if 'Real_Yield_10Y' in df.columns:
        fig.add_trace(go.Scatter(x=df[date_col], y=df['Real_Yield_10Y'], mode='lines', name='10Y 实际利率 (TIPS)'))
    if 'Breakeven_10Y' in df.columns:
        fig.add_trace(go.Scatter(x=df[date_col], y=df['Breakeven_10Y'], mode='lines', name='10Y 平衡通胀率 (Breakeven)'))

    fig.update_layout(
        title=f'10Y TIPS 实际利率 vs 平衡通胀预期 - [{timeframe}]',
        xaxis_title='日期',
        yaxis_title='收益率 / 通胀率 (%)',
        hovermode='x unified',
        template='plotly_white',
        height=450,
        uirevision=f"real_yield_chart_{timeframe}"
    )
    fig.update_yaxes(autorange=True, fixedrange=False)
    return fig

# ------------------------------------------------------------------
# 7. 芝加哥联储全国金融状况指数图表 (NFCI)
# ------------------------------------------------------------------
def create_nfci_chart(df_data: pd.DataFrame, timeframe="ALL"):
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

    val_col = 'NFCI' if 'NFCI' in df.columns else df.columns[1]
    df = filter_by_timeframe(df, date_col, timeframe)
    if df.empty:
        return None

    fig = px.line(
        df,
        x=date_col,
        y=val_col,
        title=f'Chicago Fed National Financial Conditions Index (NFCI) - [{timeframe}]',
        labels={val_col: 'NFCI 指数', date_col: '日期'},
        template="plotly_white"
    )
    fig.add_hline(
        y=0.0,
        line_dash="solid",
        line_color="black",
        annotation_text="0 (历史平均水平，正值收紧/负值宽松)",
        annotation_position="top left"
    )
    fig.update_layout(
        hovermode="x unified",
        height=450,
        yaxis_title="NFCI 指数",
        uirevision=f"nfci_chart_{timeframe}"
    )
    fig.update_yaxes(autorange=True, fixedrange=False)
    return fig

# ------------------------------------------------------------------
# 8. 美联储净流动性图表 (Net Liquidity)
# ------------------------------------------------------------------
def create_net_liquidity_chart(df_data: pd.DataFrame, timeframe="ALL"):
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

    val_col = 'Net_Liquidity_Billions' if 'Net_Liquidity_Billions' in df.columns else df.columns[1]
    df = filter_by_timeframe(df, date_col, timeframe)
    if df.empty:
        return None

    fig = px.line(
        df,
        x=date_col,
        y=val_col,
        title=f'Fed Net Liquidity (美联储净流动性 = Assets - TGA - RRP) - [{timeframe}]',
        labels={val_col: '净流动性 (十亿美元)', date_col: '日期'},
        template="plotly_white"
    )
    fig.update_layout(
        hovermode="x unified",
        height=450,
        yaxis_title="净流动性 (十亿美元)",
        uirevision=f"net_liq_chart_{timeframe}"
    )
    fig.update_yaxes(autorange=True, fixedrange=False)
    return fig

# ------------------------------------------------------------------
# 9. SOFR - IORB 利差图表
# ------------------------------------------------------------------
def create_sofr_iorb_chart(df_data: pd.DataFrame, timeframe="ALL"):
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

    val_col = 'SOFR_IORB_Spread_Bps' if 'SOFR_IORB_Spread_Bps' in df.columns else df.columns[1]
    df = filter_by_timeframe(df, date_col, timeframe)
    if df.empty:
        return None

    fig = px.line(
        df,
        x=date_col,
        y=val_col,
        title=f'SOFR - IORB Spread (基点 Bps) - [{timeframe}]',
        labels={val_col: '利差 (Bps)', date_col: '日期'},
        template="plotly_white"
    )
    fig.add_hline(y=0.0, line_dash="solid", line_color="gray")
    fig.update_layout(
        hovermode="x unified",
        height=450,
        yaxis_title="利差 (Bps)",
        uirevision=f"sofr_iorb_chart_{timeframe}"
    )
    fig.update_yaxes(autorange=True, fixedrange=False)
    return fig

# ------------------------------------------------------------------
# 10. 标普500前十大集中度图表
# ------------------------------------------------------------------
def create_top10_concentration_chart(df_data: pd.DataFrame, timeframe="ALL"):
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

    val_col = 'Top10_Weight' if 'Top10_Weight' in df.columns else df.columns[1]
    df = filter_by_timeframe(df, date_col, timeframe)
    if df.empty:
        return None

    fig = px.line(
        df,
        x=date_col,
        y=val_col,
        title=f'S&P 500 Top 10 Weight Concentration (前十大权重集中度) - [{timeframe}]',
        labels={val_col: '权重占比 (%)', date_col: '日期'},
        template="plotly_white"
    )
    fig.update_layout(
        hovermode="x unified",
        height=450,
        yaxis_title="前十大权重占比 (%)",
        uirevision=f"top10_chart_{timeframe}"
    )
    fig.update_yaxes(autorange=True, fixedrange=False)
    return fig

# ------------------------------------------------------------------
# 11. VIX 恐慌指数图表
# ------------------------------------------------------------------
def create_vix_chart(df_data: pd.DataFrame, timeframe="ALL"):
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

    val_col = 'VIX' if 'VIX' in df.columns else df.columns[1]
    df = filter_by_timeframe(df, date_col, timeframe)
    if df.empty:
        return None

    fig = px.line(
        df,
        x=date_col,
        y=val_col,
        title=f'CBOE Volatility Index (VIX) - [{timeframe}]',
        labels={val_col: 'VIX 点位', date_col: '日期'},
        template="plotly_white"
    )
    fig.add_hline(y=20.0, line_dash="dash", line_color="orange", annotation_text="20 风险关注线")
    fig.add_hline(y=30.0, line_dash="dot", line_color="red", annotation_text="30 恐慌警戒线")
    fig.update_layout(
        hovermode="x unified",
        height=450,
        yaxis_title="VIX 点位",
        uirevision=f"vix_chart_{timeframe}"
    )
    fig.update_yaxes(autorange=True, fixedrange=False)
    return fig

# ------------------------------------------------------------------
# 12. CNN 恐慌与贪婪图表
# ------------------------------------------------------------------
def create_cnn_fear_greed_chart(df_data: pd.DataFrame, timeframe="ALL"):
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

    val_col = 'Fear_Greed_Index' if 'Fear_Greed_Index' in df.columns else df.columns[1]
    df = filter_by_timeframe(df, date_col, timeframe)
    if df.empty:
        return None

    fig = px.line(
        df,
        x=date_col,
        y=val_col,
        title=f'CNN Fear & Greed Historical Index - [{timeframe}]',
        labels={val_col: '得分 (0-100)', date_col: '日期'},
        template="plotly_white"
    )
    fig.add_hline(y=25.0, line_dash="dot", line_color="red", annotation_text="极度恐慌 (25)")
    fig.add_hline(y=75.0, line_dash="dot", line_color="green", annotation_text="极度贪婪 (75)")
    fig.update_layout(
        hovermode="x unified",
        height=450,
        yaxis_title="指数得分",
        uirevision=f"cnn_fg_chart_{timeframe}"
    )
    fig.update_yaxes(range=[0, 100], fixedrange=False)
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
        fig.add_trace(go.Scatter(x=df[date_col], y=df['Spread_10Y2Y'], mode='lines', name='10Y - 2Y 利差 (%)'))
    if 'Spread_10Y3M' in df.columns:
        fig.add_trace(go.Scatter(x=df[date_col], y=df['Spread_10Y3M'], mode='lines', name='10Y - 3M 利差 (%)'))

    fig.add_hline(y=0.0, line_dash="solid", line_color="black", annotation_text="0 (倒挂分界线)")
    fig.update_layout(
        title=f'U.S. Treasury Yield Curve Spreads (10Y-2Y & 10Y-3M) - [{timeframe}]',
        xaxis_title='日期',
        yaxis_title='利差 (%)',
        hovermode='x unified',
        template='plotly_white',
        height=450,
        uirevision=f"yield_spreads_chart_{timeframe}"
    )
    fig.update_yaxes(autorange=True, fixedrange=False)
    return fig

# ------------------------------------------------------------------
# 14. 初请/续请失业金图表
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
        fig.add_trace(go.Scatter(x=df[date_col], y=df['Initial_Claims'], mode='lines', name='初请失业金 (ICSA)'))
    if 'Continued_Claims' in df.columns:
        fig.add_trace(go.Scatter(x=df[date_col], y=df['Continued_Claims'], mode='lines', name='续请失业金 (CCSA)', yaxis="y2"))

    fig.update_layout(
        title=f'Initial & Continued Jobless Claims - [{timeframe}]',
        xaxis_title='日期',
        yaxis=dict(title='初请人数 (人)'),
        yaxis2=dict(title='续请人数 (人)', overlaying='y', side='right'),
        hovermode='x unified',
        template='plotly_white',
        height=450,
        uirevision=f"jobless_claims_chart_{timeframe}"
    )
    return fig

# ------------------------------------------------------------------
# 15. 美元指数图表
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

    val_col = 'DXY_Index' if 'DXY_Index' in df.columns else df.columns[1]
    df = filter_by_timeframe(df, date_col, timeframe)
    if df.empty:
        return None

    fig = px.line(
        df,
        x=date_col,
        y=val_col,
        title=f'U.S. Dollar Index (美元指数) - [{timeframe}]',
        labels={val_col: '指数点位', date_col: '日期'},
        template="plotly_white"
    )
    fig.update_layout(
        hovermode="x unified",
        height=450,
        yaxis_title="指数点位",
        uirevision=f"dxy_chart_{timeframe}"
    )
    fig.update_yaxes(autorange=True, fixedrange=False)
    return fig

# ------------------------------------------------------------------
# 16. 通胀与薪资螺旋图表
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
        fig.add_trace(go.Scatter(x=df[date_col], y=df['Core_CPI_YoY'], mode='lines', name='核心 CPI 同比 (%)'))
    if 'Hourly_Earnings_YoY' in df.columns:
        fig.add_trace(go.Scatter(x=df[date_col], y=df['Hourly_Earnings_YoY'], mode='lines', name='时薪同比增速 (%)'))

    fig.add_hline(y=2.0, line_dash="dot", line_color="green", annotation_text="联储 2% 目标通胀")
    fig.update_layout(
        title=f'Core CPI vs Hourly Earnings Growth (YoY %) - [{timeframe}]',
        xaxis_title='日期',
        yaxis_title='同比增速 (%)',
        hovermode='x unified',
        template='plotly_white',
        height=450,
        uirevision=f"inf_wage_chart_{timeframe}"
    )
    fig.update_yaxes(autorange=True, fixedrange=False)
    return fig

# ------------------------------------------------------------------
# 17. 萨姆法则衰退指标图表
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

    val_col = 'Sahm_Value' if 'Sahm_Value' in df.columns else df.columns[1]
    df = filter_by_timeframe(df, date_col, timeframe)
    if df.empty:
        return None

    fig = px.line(
        df,
        x=date_col,
        y=val_col,
        title=f'Sahm Rule Recession Indicator (萨姆衰退指标) - [{timeframe}]',
        labels={val_col: '数值 (ppts)', date_col: '日期'},
        template="plotly_white"
    )
    fig.add_hline(y=0.5, line_dash="dash", line_color="red", annotation_text="0.5 衰退触发阈值")
    fig.update_layout(
        hovermode="x unified",
        height=450,
        yaxis_title="萨姆指标 (ppts)",
        uirevision=f"sahm_chart_{timeframe}"
    )
    fig.update_yaxes(autorange=True, fixedrange=False)
    return fig

# ------------------------------------------------------------------
# 18. 核心资本品新订单图表
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

    val_col = 'Core_Capex_Orders' if 'Core_Capex_Orders' in df.columns else df.columns[1]
    df = filter_by_timeframe(df, date_col, timeframe)
    if df.empty:
        return None

    fig = px.line(
        df,
        x=date_col,
        y=val_col,
        title=f'Core Capital Goods Orders (核心资本品新订单) - [{timeframe}]',
        labels={val_col: '金额 (百万美元)', date_col: '日期'},
        template="plotly_white"
    )
    fig.update_layout(
        hovermode="x unified",
        height=450,
        yaxis_title="金额 (百万美元)",
        uirevision=f"capex_chart_{timeframe}"
    )
    fig.update_yaxes(autorange=True, fixedrange=False)
    return fig

# ------------------------------------------------------------------
# 19. M2 货币供应量图表
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
    if 'M2_Amount' in df.columns:
        fig.add_trace(go.Scatter(x=df[date_col], y=df['M2_Amount'], mode='lines', name='M2 绝对总量 (十亿美元)'))
    if 'M2_YoY' in df.columns:
        fig.add_trace(go.Scatter(x=df[date_col], y=df['M2_YoY'], mode='lines', name='M2 同比增速 (YoY %)', yaxis="y2"))

    fig.update_layout(
        title=f'M2 Money Supply & YoY Growth - [{timeframe}]',
        xaxis_title='日期',
        yaxis=dict(title='M2 总量 (十亿美元)'),
        yaxis2=dict(title='YoY 增速 (%)', overlaying='y', side='right'),
        hovermode='x unified',
        template='plotly_white',
        height=450,
        uirevision=f"m2_chart_{timeframe}"
    )
    return fig

# ------------------------------------------------------------------
# 20. SLOOS 信贷收紧比例图表
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

    val_col = 'Tightening_Percentage' if 'Tightening_Percentage' in df.columns else df.columns[1]
    df = filter_by_timeframe(df, date_col, timeframe)
    if df.empty:
        return None

    fig = px.bar(
        df,
        x=date_col,
        y=val_col,
        title=f'Senior Loan Officer Survey - C&I Loan Tightening % - [{timeframe}]',
        labels={val_col: '净收紧比例 (%)', date_col: '日期'},
        template="plotly_white"
    )
    fig.add_hline(y=0.0, line_dash="solid", line_color="black")
    fig.update_layout(
        hovermode="x unified",
        height=450,
        yaxis_title="净收紧比例 (%)",
        uirevision=f"sloos_chart_{timeframe}"
    )
    fig.update_yaxes(autorange=True, fixedrange=False)
    return fig

# ------------------------------------------------------------------
# 21. 个股历史股价走势与均线图表
# ------------------------------------------------------------------
def create_stock_price_chart(df_data: pd.DataFrame, ticker: str, timeframe="ALL"):
    if df_data is None or df_data.empty:
        return None
    df = df_data.copy()
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

    df['MA50'] = df['Close'].rolling(window=50).mean()
    df['MA200'] = df['Close'].rolling(window=200).mean()

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df[date_col], y=df['Close'], mode='lines', name=f'{ticker} 收盘价'))
    fig.add_trace(go.Scatter(x=df[date_col], y=df['MA50'], mode='lines', name='50日均线 (MA50)', line=dict(dash='dot')))
    fig.add_trace(go.Scatter(x=df[date_col], y=df['MA200'], mode='lines', name='200日均线 (MA200)', line=dict(dash='dash')))

    fig.update_layout(
        title=f'{ticker} Stock Price & Moving Averages - [{timeframe}]',
        xaxis_title='日期',
        yaxis_title='价格 (USD)',
        hovermode='x unified',
        template='plotly_white',
        height=450,
        uirevision=f"stock_price_{ticker}_{timeframe}"
    )
    fig.update_yaxes(autorange=True, fixedrange=False)
    return fig

# ------------------------------------------------------------------
# 22. 个股 vs 标普500 相对收益图表
# ------------------------------------------------------------------
def create_relative_performance_chart(df_stock: pd.DataFrame, df_sp500: pd.DataFrame, ticker: str, timeframe="ALL"):
    if df_stock is None or df_stock.empty or df_sp500 is None or df_sp500.empty:
        return None
    df_s = df_stock.copy()
    df_sp = df_sp500.copy()
    df_s['Date'] = pd.to_datetime(df_s['Date'])
    df_sp['Date'] = pd.to_datetime(df_sp['Date'])

    df = pd.merge(df_s[['Date', 'Close']], df_sp[['Date', 'Close']], on='Date', suffixes=(f'_{ticker}', '_SP500')).dropna()
    df = filter_by_timeframe(df, 'Date', timeframe)
    if df.empty:
        return None

    first_s = df[f'Close_{ticker}'].iloc[0]
    first_sp = df['Close_SP500'].iloc[0]

    df['Return_Stock'] = (df[f'Close_{ticker}'] / first_s - 1) * 100
    df['Return_SP500'] = (df['Close_SP500'] / first_sp - 1) * 100

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df['Date'], y=df['Return_Stock'], mode='lines', name=f'{ticker} 累计收益 (%)'))
    fig.add_trace(go.Scatter(x=df['Date'], y=df['Return_SP500'], mode='lines', name='S&P 500 累计收益 (%)', line=dict(dash='dash')))

    fig.update_layout(
        title=f'{ticker} vs S&P 500 Relative Performance - [{timeframe}]',
        xaxis_title='日期',
        yaxis_title='累计收益率 (%)',
        hovermode='x unified',
        template='plotly_white',
        height=450,
        uirevision=f"rel_perf_{ticker}_{timeframe}"
    )
    fig.update_yaxes(autorange=True, fixedrange=False)
    return fig

# ------------------------------------------------------------------
# 23. 核心财务指标趋势图表 (Revenue, Net Income, FCF)
# ------------------------------------------------------------------
def create_financial_trends_chart(df_data: pd.DataFrame, ticker: str):
    if df_data is None or df_data.empty:
        return None
    df = df_data.copy()

    fig = go.Figure()
    if 'Revenue' in df.columns:
        fig.add_trace(go.Bar(x=df['Year'], y=df['Revenue'], name='总营收 (十亿美元)'))
    if 'Net_Income' in df.columns:
        fig.add_trace(go.Bar(x=df['Year'], y=df['Net_Income'], name='净利润 (十亿美元)'))
    if 'Free_Cash_Flow' in df.columns:
        fig.add_trace(go.Bar(x=df['Year'], y=df['Free_Cash_Flow'], name='自由现金流 (十亿美元)'))

    fig.update_layout(
        barmode='group',
        title=f'{ticker} Annual Financials & Cash Flow Trends',
        xaxis_title='财年',
        yaxis_title='金额 (十亿美元)',
        hovermode='x unified',
        template='plotly_white',
        height=450,
        uirevision=f"fin_trends_{ticker}"
    )
    return fig

# ------------------------------------------------------------------
# 24. PE / PS 估值通道 Band 图表
# ------------------------------------------------------------------
def create_pe_ps_band_chart(df_data: pd.DataFrame, ticker: str, timeframe="ALL"):
    if df_data is None or df_data.empty:
        return None
    df = df_data.copy()
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

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df[date_col], y=df['Close'], mode='lines', name=f'{ticker} 收盘价', line=dict(color='black', width=2)))

    if 'PE_15x' in df.columns:
        fig.add_trace(go.Scatter(x=df[date_col], y=df['PE_15x'], mode='lines', name='PE 15x', line=dict(dash='dot')))
    if 'PE_25x' in df.columns:
        fig.add_trace(go.Scatter(x=df[date_col], y=df['PE_25x'], mode='lines', name='PE 25x', line=dict(dash='dot')))
    if 'PE_35x' in df.columns:
        fig.add_trace(go.Scatter(x=df[date_col], y=df['PE_35x'], mode='lines', name='PE 35x', line=dict(dash='dot')))
    if 'PE_45x' in df.columns:
        fig.add_trace(go.Scatter(x=df[date_col], y=df['PE_45x'], mode='lines', name='PE 45x', line=dict(dash='dot')))

    fig.update_layout(
        title=f'{ticker} Historical P/E Valuation Bands - [{timeframe}]',
        xaxis_title='日期',
        yaxis_title='股价 (USD)',
        hovermode='x unified',
        template='plotly_white',
        height=450,
        uirevision=f"pe_band_{ticker}_{timeframe}"
    )
    fig.update_yaxes(autorange=True, fixedrange=False)
    return fig

# ------------------------------------------------------------------
# 25. 技术动能图表 (RSI / MACD / Bollinger)
# ------------------------------------------------------------------
def create_technical_momentum_chart(df_data: pd.DataFrame, ticker: str, timeframe="ALL"):
    if df_data is None or df_data.empty:
        return None
    df = df_data.copy()
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

    # 计算简易 RSI(14)
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / (loss + 1e-9)
    df['RSI'] = 100 - (100 / (1 + rs))

    fig = px.line(
        df,
        x=date_col,
        y='RSI',
        title=f'{ticker} 14-Day RSI Momentum Indicator - [{timeframe}]',
        labels={'RSI': 'RSI', date_col: '日期'},
        template="plotly_white"
    )
    fig.add_hline(y=70, line_dash="dot", line_color="red", annotation_text="超买区 (70)")
    fig.add_hline(y=30, line_dash="dot", line_color="green", annotation_text="超卖区 (30)")
    fig.update_layout(
        hovermode="x unified",
        height=400,
        yaxis_title="RSI",
        uirevision=f"tech_rsi_{ticker}_{timeframe}"
    )
    fig.update_yaxes(range=[0, 100], fixedrange=False)
    return fig
