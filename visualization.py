import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go

# ------------------------------------------------------------------
# 1. 国债收益率形态演变图表
# ------------------------------------------------------------------
def create_treasury_chart(df_long: pd.DataFrame):
    """
    绘制原版国债收益率曲线图表
    对比最新、1个月前及1年前的收益率形态演变（X轴为期限，Y轴为收益率%）
    """
    if df_long is None or df_long.empty:
        return None

    df = df_long.copy()
    if 'Date' in df.columns:
        df['Date'] = pd.to_datetime(df['Date'])
        latest_date = df['Date'].max()
    else:
        return None

    # Determine maturity column name from data_processing load_and_transform_data
    mat_col = 'Maturity_Years' if 'Maturity_Years' in df.columns else ('Maturity_Label' if 'Maturity_Label' in df.columns else 'Maturity')

    # 计算 1个月前 与 1年前 的目标日期
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
# 2. 失业率趋势图表 (UNRATE - 动态 Y 轴)
# ------------------------------------------------------------------
def create_unemployment_chart(df_unrate: pd.DataFrame, y_range=None):
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

    df = df.sort_values(date_col)
    last_date = df[date_col].max()
    first_date = df[date_col].min()

    fig = px.line(
        df,
        x=date_col,
        y=val_col,
        title='UNRATE (美国失业率)',
        labels={val_col: '失业率 (%)', date_col: '日期'},
        template="plotly_white",
        line_shape='spline'
    )

    avg_rate = df[val_col].mean()
    fig.add_hline(
        y=avg_rate,
        line_dash="dot",
        line_color="gray",
        annotation_text=f"历史平均值 ({avg_rate:.1f}%)",
        annotation_position="bottom left",
    )

    default_start = max(first_date, last_date - pd.DateOffset(years=10))

    fig.update_layout(
        xaxis=dict(
            rangeselector=dict(
                buttons=list([
                    dict(count=1, label="1y", step="year", stepmode="backward"),
                    dict(count=5, label="5y", step="year", stepmode="backward"),
                    dict(count=10, label="10y", step="year", stepmode="backward"),
                    dict(step="all", label="all")
                ])
            ),
            rangeslider=dict(visible=False),
            range=[default_start, last_date]
        ),
        hovermode="x unified",
        height=500,
        yaxis_title="失业率 (%)",
        uirevision="unemployment_chart"
    )

    if y_range is not None:
        fig.update_yaxes(range=list(y_range), autorange=False)
    else:
        fig.update_yaxes(autorange=True, fixedrange=False)

    return fig

# ------------------------------------------------------------------
# 3. 信用利差图表 (Credit Spread - 动态 Y 轴)
# ------------------------------------------------------------------
def create_credit_spread_chart(df_data: pd.DataFrame, y_range=None):
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

    df = df.sort_values(date_col)
    last_date = df[date_col].max()
    first_date = df[date_col].min()

    fig = px.line(
        df,
        x=date_col,
        y=val_col,
        title='US High Yield Option-Adjusted Spread (高收益债信用利差)',
        labels={val_col: '利差 (%)', date_col: '日期'},
        template="plotly_white"
    )

    default_start = max(first_date, last_date - pd.DateOffset(years=5))

    fig.update_layout(
        xaxis=dict(
            rangeselector=dict(
                buttons=list([
                    dict(count=1, label="1y", step="year", stepmode="backward"),
                    dict(count=3, label="3y", step="year", stepmode="backward"),
                    dict(count=5, label="5y", step="year", stepmode="backward"),
                    dict(step="all", label="all")
                ])
            ),
            rangeslider=dict(visible=False),
            range=[default_start, last_date]
        ),
        hovermode="x unified",
        height=500,
        yaxis_title="利差 (%)",
        uirevision="credit_spread_chart",
        template="plotly_white"
    )

    if y_range is not None:
        fig.update_yaxes(range=list(y_range), autorange=False)
    else:
        fig.update_yaxes(autorange=True, fixedrange=False)

    return fig

# ------------------------------------------------------------------
# 4. 美联储资产负债表图表 (Fed Balance Sheet - 动态 Y 轴)
# ------------------------------------------------------------------
def create_fed_balance_sheet_chart(df_fed: pd.DataFrame, y_range=None):
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

    df_fed = df_fed.sort_values(date_col)
    last_date = df_fed[date_col].max()
    first_date = df_fed[date_col].min()

    fig = px.line(
        df_fed,
        x=date_col,
        y=val_col,
        title="Fed Balance Sheet (美联储总资产, 万亿美元)",
        labels={date_col: "Date", val_col: "Total Assets (Trillion USD)"},
        template="plotly_white"
    )

    default_start = max(first_date, last_date - pd.DateOffset(years=10))

    fig.update_layout(
        hovermode="x unified",
        height=500,
        yaxis_title="Total Assets (Trillion USD)",
        uirevision="fed_balance_sheet_chart",
        xaxis=dict(
            rangeselector=dict(
                buttons=list([
                    dict(count=1, label="1y", step="year", stepmode="backward"),
                    dict(count=5, label="5y", step="year", stepmode="backward"),
                    dict(count=10, label="10y", step="year", stepmode="backward"),
                    dict(step="all", label="all")
                ])
            ),
            rangeslider=dict(visible=False),
            range=[default_start, last_date]
        )
    )

    if y_range is not None:
        fig.update_yaxes(range=list(y_range), autorange=False)
    else:
        fig.update_yaxes(autorange=True, fixedrange=False)

    return fig

# ------------------------------------------------------------------
# 5. 金油比图表 (Gold / Oil Ratio - 动态 Y 轴)
# ------------------------------------------------------------------
def create_gold_oil_ratio_chart(df_ratio: pd.DataFrame, y_range=None):
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

    df_ratio = df_ratio.sort_values(date_col)

    fig = px.line(
        df_ratio,
        x=date_col,
        y="gold_oil_ratio",
        title="Gold / Oil Ratio (金油比)",
        labels={date_col: "Date", "gold_oil_ratio": "Gold / Oil Ratio"},
        template="plotly_white"
    )

    avg_ratio = df_ratio["gold_oil_ratio"].mean()
    fig.add_hline(
        y=avg_ratio,
        line_dash="dot",
        line_color="gray",
        annotation_text=f"历史平均值 ({avg_ratio:.1f})",
        annotation_position="bottom left",
    )

    last_date = df_ratio[date_col].max()
    first_date = df_ratio[date_col].min()
    default_start = max(first_date, last_date - pd.DateOffset(years=5))

    fig.update_layout(
        hovermode="x unified",
        height=500,
        yaxis_title="Gold / Oil Ratio",
        uirevision="gold_oil_ratio_chart",
        xaxis=dict(
            rangeselector=dict(
                buttons=list([
                    dict(count=1, label="1y", step="year", stepmode="backward"),
                    dict(count=3, label="3y", step="year", stepmode="backward"),
                    dict(count=5, label="5y", step="year", stepmode="backward"),
                    dict(step="all", label="all")
                ])
            ),
            rangeslider=dict(visible=False),
            range=[default_start, last_date]
        ),
    )

    if y_range is not None:
        fig.update_yaxes(range=list(y_range), autorange=False)
    else:
        fig.update_yaxes(autorange=True, fixedrange=False)

    return fig

# ------------------------------------------------------------------
# 6. 10Y TIPS 实际利率与 10Y 盈亏平衡通胀率图表
# ------------------------------------------------------------------
def create_real_yield_breakeven_chart(df_data: pd.DataFrame, y_range=None):
    if df_data is None or df_data.empty:
        return None

    df = df_data.copy()
    date_col = 'date' if 'date' in df.columns else df.columns[0]
    df[date_col] = pd.to_datetime(df[date_col])
    df = df.sort_values(date_col)

    cols = [c for c in ['10Y_Real_Yield', '10Y_Breakeven_Inflation'] if c in df.columns]
    if not cols:
        return None

    fig = px.line(
        df,
        x=date_col,
        y=cols,
        title="10Y TIPS 实际利率 & 10Y 盈亏平衡通胀率 (%)",
        labels={"value": "利率/通胀率 (%)", date_col: "Date", "variable": "指标"},
        template="plotly_white"
    )

    last_date = df[date_col].max()
    first_date = df[date_col].min()
    default_start = max(first_date, last_date - pd.DateOffset(years=5))

    fig.update_layout(
        hovermode="x unified",
        height=450,
        yaxis_title="率 (%)",
        uirevision="real_yield_breakeven_chart",
        xaxis=dict(
            rangeselector=dict(
                buttons=list([
                    dict(count=1, label="1y", step="year", stepmode="backward"),
                    dict(count=5, label="5y", step="year", stepmode="backward"),
                    dict(step="all", label="all"),
                ])
            ),
            rangeslider=dict(visible=False),
            range=[default_start, last_date],
        ),
    )

    if y_range is not None:
        fig.update_yaxes(range=list(y_range), autorange=False)
    else:
        fig.update_yaxes(autorange=True, fixedrange=False)

    return fig

# ------------------------------------------------------------------
# 7. 芝加哥联储金融条件指数图表 (NFCI)
# ------------------------------------------------------------------
def create_nfci_chart(df_nfci: pd.DataFrame, y_range=None):
    if df_nfci is None or df_nfci.empty:
        return None

    df = df_nfci.copy()
    date_col = 'date' if 'date' in df.columns else df.columns[0]
    df[date_col] = pd.to_datetime(df[date_col])
    df = df.sort_values(date_col)

    val_col = 'NFCI' if 'NFCI' in df.columns else df.columns[1]

    fig = px.line(
        df,
        x=date_col,
        y=val_col,
        title="芝加哥联储全国金融条件指数 (NFCI)",
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

    last_date = df[date_col].max()
    first_date = df[date_col].min()
    default_start = max(first_date, last_date - pd.DateOffset(years=5))

    fig.update_layout(
        hovermode="x unified",
        height=450,
        yaxis_title="NFCI 指数",
        uirevision="nfci_chart",
        xaxis=dict(
            rangeselector=dict(
                buttons=list([
                    dict(count=1, label="1y", step="year", stepmode="backward"),
                    dict(count=5, label="5y", step="year", stepmode="backward"),
                    dict(step="all", label="all"),
                ])
            ),
            rangeslider=dict(visible=False),
            range=[default_start, last_date],
        ),
    )

    if y_range is not None:
        fig.update_yaxes(range=list(y_range), autorange=False)
    else:
        fig.update_yaxes(autorange=True, fixedrange=False)

    return fig

# ------------------------------------------------------------------
# 8. 美联储净流动性与银行准备金余额图表
# ------------------------------------------------------------------
def create_net_liquidity_chart(df_liq: pd.DataFrame, y_range=None):
    if df_liq is None or df_liq.empty:
        return None

    df = df_liq.copy()
    date_col = 'date' if 'date' in df.columns else df.columns[0]
    df[date_col] = pd.to_datetime(df[date_col])
    df = df.sort_values(date_col)

    cols = [c for c in ['Fed_Net_Liquidity_Tn', 'Bank_Reserves_Tn'] if c in df.columns]
    if not cols:
        return None

    fig = px.line(
        df,
        x=date_col,
        y=cols,
        title="美联储净流动性 & 银行准备金余额 (万亿美元)",
        labels={"value": "万亿美元 (Trillion USD)", date_col: "Date", "variable": "指标"},
        template="plotly_white"
    )

    last_date = df[date_col].max()
    first_date = df[date_col].min()
    default_start = max(first_date, last_date - pd.DateOffset(years=5))

    fig.update_layout(
        hovermode="x unified",
        height=450,
        yaxis_title="万亿美元 (Trillion USD)",
        uirevision="net_liquidity_chart",
        xaxis=dict(
            rangeselector=dict(
                buttons=list([
                    dict(count=1, label="1y", step="year", stepmode="backward"),
                    dict(count=5, label="5y", step="year", stepmode="backward"),
                    dict(step="all", label="all"),
                ])
            ),
            rangeslider=dict(visible=False),
            range=[default_start, last_date],
        ),
    )

    if y_range is not None:
        fig.update_yaxes(range=list(y_range), autorange=False)
    else:
        fig.update_yaxes(autorange=True, fixedrange=False)

    return fig

# ------------------------------------------------------------------
# 9. SOFR - IORB 利率与利差双轴图表
# ------------------------------------------------------------------
def create_sofr_iorb_chart(df_sofr: pd.DataFrame, y_range=None):
    if df_sofr is None or df_sofr.empty:
        return None

    df = df_sofr.copy()
    date_col = 'date' if 'date' in df.columns else df.columns[0]
    df[date_col] = pd.to_datetime(df[date_col])
    df = df.sort_values(date_col)

    fig = go.Figure()

    if 'SOFR' in df.columns:
        fig.add_trace(go.Scatter(x=df[date_col], y=df['SOFR'], name="SOFR (%)", line=dict(color="#2563eb", width=2)))
    if 'IORB' in df.columns:
        fig.add_trace(go.Scatter(x=df[date_col], y=df['IORB'], name="IORB (%)", line=dict(color="#16a34a", width=2)))
    if 'Spread_bps' in df.columns:
        fig.add_trace(go.Scatter(x=df[date_col], y=df['Spread_bps'], name="SOFR - IORB 利差 (bps)", yaxis="y2", line=dict(color="#dc2626", width=1.5, dash="dot")))

    last_date = df[date_col].max()
    first_date = df[date_col].min()
    default_start = max(first_date, last_date - pd.DateOffset(years=3))

    fig.update_layout(
        title="SOFR 隔夜融资利率 vs IORB 准备金利率 & 利差 (bps)",
        template="plotly_white",
        height=450,
        hovermode="x unified",
        uirevision="sofr_iorb_chart",
        yaxis=dict(title="利率 (%)"),
        yaxis2=dict(title="利差 (bps)", overlaying="y", side="right"),
        xaxis=dict(
            rangeselector=dict(
                buttons=list([
                    dict(count=6, label="6m", step="month", stepmode="backward"),
                    dict(count=1, label="1y", step="year", stepmode="backward"),
                    dict(count=3, label="3y", step="year", stepmode="backward"),
                    dict(step="all", label="all"),
                ])
            ),
            rangeslider=dict(visible=False),
            range=[default_start, last_date],
        ),
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
EOF
