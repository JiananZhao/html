# visualization.py

import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# ------------------------------------------------------------------
# 1. 美债收益率曲线图表 (Yield Curve)
# ------------------------------------------------------------------
def create_treasury_chart(df_long: pd.DataFrame):
    """
    生成原版国债收益率曲线图表
    对比最新、1个月前及1年前的收益率形态演变（X轴为期限，Y轴为收益率%）
    """
    if df_long is None or df_long.empty:
        return None

    df = df_long.sort_values(by=['Date', 'Maturity_Years']).copy()
    df['Date_Str'] = df['Date'].dt.strftime('%Y-%m-%d')

    latest_date = df['Date'].max()
    date_1m_ago = df[df['Date'] <= latest_date - pd.DateOffset(months=1)]['Date'].max()
    date_1y_ago = df[df['Date'] <= latest_date - pd.DateOffset(years=1)]['Date'].max()

    ref_dates = [d for d in [latest_date, date_1m_ago, date_1y_ago] if pd.notna(d)]
    df_filtered = df[df['Date'].isin(ref_dates)].copy()

    fig = px.line(
        df_filtered,
        x='Maturity_Label',
        y='Yield',
        color='Date_Str',
        markers=True,
        title=f"US Treasury Yield Curve ({latest_date.strftime('%Y-%m-%d')})",
        labels={'Maturity_Label': '期限 (Maturity)', 'Yield': '收益率 (%)', 'Date_Str': '日期'},
        template='plotly_white'
    )

    fig.update_layout(
        hovermode='x unified',
        height=500,
        yaxis_title='收益率 (%)',
        xaxis_title='期限 (Maturity)',
        uirevision='treasury_yield_curve'
    )
    return fig

# ------------------------------------------------------------------
# 2. 失业率趋势图表 (UNRATE)
# ------------------------------------------------------------------
def create_unemployment_chart(df_unrate: pd.DataFrame, y_range=None):
    if df_unrate is None or df_unrate.empty:
        return None

    fig = px.line(
        df_unrate,
        x=df_unrate.index,
        y='Unemployment_Rate',
        title='UNRATE (美国失业率)',
        labels={'Unemployment_Rate': '失业率 (%)'},
        template="plotly_white",
        line_shape='spline'
    )

    avg_rate = df_unrate['Unemployment_Rate'].mean()
    fig.add_hline(
        y=avg_rate,
        line_dash="dot",
        line_color="gray",
        annotation_text=f"历史平均值 ({avg_rate:.1f}%)",
        annotation_position="bottom left",
    )

    fig.update_layout(
        xaxis=dict(
            rangeselector=dict(
                buttons=list([
                    dict(count=1, label="1y", step="year", stepmode="backward"),
                    dict(count=5, label="5y", step="year", stepmode="backward"),
                    dict(count=10, label="10y", step="year", stepmode="backward"),
                    dict(step="all")
                ])
            ),
            rangeslider=dict(visible=True, thickness=0.07),
            range=[df_unrate.index[-1] - pd.DateOffset(years=10), df_unrate.index[-1]]
        ),
        hovermode="x unified",
        height=550,
        yaxis_title="失业率 (%)",
        uirevision="unemployment_chart"
    )

    fig.update_yaxes(fixedrange=False)
    if y_range is not None:
        fig.update_yaxes(range=list(y_range), autorange=False)
    else:
        fig.update_yaxes(autorange=True)

    return fig

# ------------------------------------------------------------------
# 3. 信用利差图表 (Credit Spread)
# ------------------------------------------------------------------
def create_credit_spread_chart(df_data: pd.DataFrame):
    if df_data is None or df_data.empty:
        return None

    fig = px.line(
        df_data,
        x=df_data.index,
        y='Value',
        title='US High Yield Option-Adjusted Spread (高收益债信用利差)',
        labels={'Value': '利差 (%)'},
        template="plotly_white"
    )

    fig.update_layout(
        xaxis=dict(
            rangeselector=dict(
                buttons=list([
                    dict(count=1, label="1y", step="year", stepmode="backward"),
                    dict(count=5, label="5y", step="year", stepmode="backward"),
                    dict(step="all")
                ])
            ),
            rangeslider=dict(visible=True, thickness=0.07),
            range=[df_data.index[-1] - pd.DateOffset(years=1), df_data.index[-1]]
        ),
        hovermode="x unified",
        height=550,
        yaxis_range=[1.0, 5.0],
        template="plotly_white"
    )
    return fig

# ------------------------------------------------------------------
# 4. 美联储资产负债表图表 (Fed Balance Sheet)
# ------------------------------------------------------------------
def create_fed_balance_sheet_chart(df_fed: pd.DataFrame, y_range=None):
    if df_fed is None or df_fed.empty:
        return None

    df_fed = df_fed.copy()
    df_fed["date"] = pd.to_datetime(df_fed["date"])

    fig = px.line(
        df_fed,
        x="date",
        y="balance_sheet_tn",
        title="Fed Balance Sheet (美联储总资产, 万亿美元)",
        labels={"date": "Date", "balance_sheet_tn": "Total Assets (Trillion USD)"},
        template="plotly_white"
    )

    fig.update_layout(
        hovermode="x unified",
        height=500,
        yaxis_title="Total Assets (Trillion USD)",
        uirevision="fed_balance_sheet_chart"
    )

    fig.update_yaxes(fixedrange=False)
    if y_range is not None:
        fig.update_yaxes(range=list(y_range), autorange=False)
    else:
        fig.update_yaxes(autorange=True)

    return fig

# ------------------------------------------------------------------
# 5. 金油比图表 (Gold / Oil Ratio)
# ------------------------------------------------------------------
def create_gold_oil_ratio_chart(df_ratio: pd.DataFrame, y_range=None):
    if df_ratio is None or df_ratio.empty:
        return None

    df_ratio = df_ratio.copy()
    df_ratio["date"] = pd.to_datetime(df_ratio["date"])
    df_ratio = df_ratio.sort_values("date")

    fig = px.line(
        df_ratio,
        x="date",
        y="gold_oil_ratio",
        title="Gold / Oil Ratio (金油比)",
        labels={"date": "Date", "gold_oil_ratio": "Gold / Oil Ratio"},
        template="plotly_white"
    )

    if "gold_usd_per_oz" in df_ratio.columns and "oil_usd_per_bbl" in df_ratio.columns:
        fig.update_traces(
            customdata=df_ratio[["gold_usd_per_oz", "oil_usd_per_bbl"]].to_numpy(),
            hovertemplate=(
                "Date=%{x|%Y-%m-%d}"
                "<br>Gold/Oil Ratio=%{y:.2f}"
                "<br>Gold=%{customdata[0]:.2f} USD/oz"
                "<br>WTI=%{customdata[1]:.2f} USD/bbl"
                "<extra></extra>"
            )
        )

    median_ratio = float(df_ratio["gold_oil_ratio"].median())
    fig.add_hline(
        y=median_ratio,
        line_dash="dot",
        line_color="gray",
        annotation_text=f"Median ({median_ratio:.2f})",
        annotation_position="bottom left",
    )

    last_date = df_ratio["date"].max()
    first_date = df_ratio["date"].min()
    default_start = max(first_date, last_date - pd.DateOffset(years=5))

    fig.update_layout(
        hovermode="x unified",
        height=420,
        yaxis_title="Gold / Oil Ratio",
        uirevision="gold_oil_ratio_chart",
        xaxis=dict(
            rangeselector=dict(
                buttons=list([
                    dict(count=3, label="3m", step="month", stepmode="backward"),
                    dict(count=1, label="1y", step="year", stepmode="backward"),
                    dict(count=5, label="5y", step="year", stepmode="backward"),
                    dict(count=10, label="10y", step="year", stepmode="backward"),
                    dict(step="all", label="all"),
                ])
            ),
            rangeslider=dict(visible=True, thickness=0.07),
            range=[default_start, last_date],
        ),
    )

    fig.update_yaxes(fixedrange=False)
    if y_range is not None:
        fig.update_yaxes(range=list(y_range), autorange=False)
    else:
        fig.update_yaxes(autorange=True)

    return fig
