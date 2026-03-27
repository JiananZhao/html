# rd_data.py

import os
import streamlit as st
import pandas as pd

from data_processing import load_and_transform_data
from visualization import (
    create_yield_curve_chart,
    create_breadth_bar_chart,
    create_breadth_timeseries_chart,
    create_unemployment_chart,
    create_credit_spread_chart,
    create_fed_balance_sheet_chart,
    create_gold_oil_ratio_chart
)
from market_analysis import (
    get_sp500_stock_data,
    calculate_market_breadth_history,
    get_latest_breadth_snapshot,
    get_sp500_symbols,
    get_unemployment_data,
    get_highyield_data,
    get_fed_balance_sheet_data,
    get_gold_oil_ratio_data
)

# ------------------------------------------------------------------
# 0. PAGE CONFIG
# ------------------------------------------------------------------
st.set_page_config(layout="wide", page_title="Yield Curve and Market Breadth")


def get_local_fred_api_key():
    try:
        return st.secrets["FRED_API_KEY"]
    except Exception:
        return os.getenv("FRED_API_KEY", "")


FRED_API_KEY = get_local_fred_api_key()

# ------------------------------------------------------------------
# 1. INITIALIZATION and DATA ACQUISITION
# ------------------------------------------------------------------

current_sp500_symbols = get_sp500_symbols()
stock_data = None
breadth_history = pd.DataFrame()

fig_timeseries = None
fig_bar = None

df_unrate = pd.DataFrame()
df_fed_bs = pd.DataFrame()
df_gold_oil = pd.DataFrame()

breadth_data = {
    "eligible_total": "N/A",
    "20DMA_count": "N/A",
    "20DMA_percentage": 0,
    "60DMA_count": "N/A",
    "60DMA_percentage": 0,
}

# 1A. Fetch stock data
if current_sp500_symbols:
    stock_data = get_sp500_stock_data()

# 1B. Calculate market breadth
if stock_data is not None and not stock_data.empty:
    breadth_history = calculate_market_breadth_history(stock_data)

    if not breadth_history.empty:
        breadth_data = get_latest_breadth_snapshot(breadth_history)
        fig_timeseries = create_breadth_timeseries_chart(breadth_history)
        fig_bar = create_breadth_bar_chart(breadth_data)

# 1C. Get unemployment data
with st.spinner("正在获取 FRED 失业率数据..."):
    df_unrate = get_unemployment_data()

# 1D. Get Fed balance sheet data
with st.spinner("正在获取 FRED 美联储资产负债表数据..."):
    df_fed_bs = get_fed_balance_sheet_data()

# 1E. Get Gold / Oil Ratio data
with st.spinner("正在获取 Gold / Oil Ratio 数据..."):
    df_gold_oil = get_gold_oil_ratio_data()

# ------------------------------------------------------------------
# 2. LAYOUT
# ------------------------------------------------------------------
col_treasury, col_market = st.columns([2, 3])

# ------------------------------------------------------------------
# 2A. LEFT COLUMN: Treasury / Macro
# ------------------------------------------------------------------
with col_treasury:
    st.subheader("U.S. Treasury Yield Curve")

    df_long = load_and_transform_data()
    if df_long is None or df_long.empty:
        st.stop()

    most_recent_date = df_long["Date"].max()
    default_frame = str(most_recent_date.date())

    st.markdown(f"**Date:** `{default_frame}`")

    fig_treasury = create_yield_curve_chart(df_long, most_recent_date)
    st.plotly_chart(fig_treasury, use_container_width=True)

    # --- Unemployment chart ---
    if not df_unrate.empty:
        st.subheader("UNRATE")

        y_min_unrate = float(df_unrate["Unemployment_Rate"].min())
        y_max_unrate = float(df_unrate["Unemployment_Rate"].max())

        manual_unrate_y = st.checkbox("手动设置失业率 Y 轴范围", key="unrate_manual_y")

        unrate_y_range = None
        if manual_unrate_y and y_min_unrate < y_max_unrate:
            unrate_y_range = st.slider(
                "失业率 Y 轴范围 (%)",
                min_value=round(y_min_unrate, 2),
                max_value=round(y_max_unrate, 2),
                value=(round(y_min_unrate, 2), round(y_max_unrate, 2)),
                step=0.1,
                key="unrate_y_range",
            )

        fig_unrate = create_unemployment_chart(df_unrate, y_range=unrate_y_range)
        st.plotly_chart(
            fig_unrate,
            use_container_width=True,
            config={"scrollZoom": True}
        )

    elif not FRED_API_KEY:
        st.warning("请设置 FRED_API_KEY 以显示失业率数据。")
    else:
        st.info("失业率数据加载中或加载失败。")

    # --- Fed Balance Sheet chart ---
    if not df_fed_bs.empty:
        st.subheader("Fed Balance Sheet")

        y_min_data = float(df_fed_bs["balance_sheet_tn"].min())
        y_max_data = float(df_fed_bs["balance_sheet_tn"].max())

        manual_y = st.checkbox("手动设置 Fed Balance Sheet Y 轴范围", key="fed_manual_y")

        fed_y_range = None
        if manual_y and y_min_data < y_max_data:
            fed_y_range = st.slider(
                "Fed Balance Sheet Y 轴范围 (USD Trillions)",
                min_value=round(y_min_data, 2),
                max_value=round(y_max_data, 2),
                value=(round(y_min_data, 2), round(y_max_data, 2)),
                step=0.05,
                key="fed_y_range",
            )

        fig_fed_bs = create_fed_balance_sheet_chart(df_fed_bs, y_range=fed_y_range)
        st.plotly_chart(
            fig_fed_bs,
            use_container_width=True,
            config={"scrollZoom": True}
        )

    elif not FRED_API_KEY:
        st.warning("请设置 FRED_API_KEY 以显示 Fed Balance Sheet 数据。")
    else:
        st.info("Fed Balance Sheet 数据加载中或加载失败。")

    # --- Gold / Oil Ratio chart ---
    if not df_gold_oil.empty:
        st.subheader("Gold / Oil Ratio")

        ratio_min = float(df_gold_oil["gold_oil_ratio"].min())
        ratio_max = float(df_gold_oil["gold_oil_ratio"].max())

        manual_ratio_y = st.checkbox("手动设置金油比 Y 轴范围", key="gold_oil_manual_y")

        ratio_y_range = None
        if manual_ratio_y and ratio_min < ratio_max:
            ratio_y_range = st.slider(
                "Gold / Oil Ratio Y 轴范围",
                min_value=round(ratio_min, 2),
                max_value=round(ratio_max, 2),
                value=(round(ratio_min, 2), round(ratio_max, 2)),
                step=0.1,
                key="gold_oil_y_range",
            )

        fig_gold_oil = create_gold_oil_ratio_chart(df_gold_oil, y_range=ratio_y_range)
        st.plotly_chart(
            fig_gold_oil,
            use_container_width=True,
            config={"scrollZoom": True}
        )

    elif not FRED_API_KEY:
        st.warning("请设置 FRED_API_KEY 以显示 Gold / Oil Ratio 数据。")
    else:
        st.info("Gold / Oil Ratio 数据加载中或加载失败。")

# ------------------------------------------------------------------
# 2B. RIGHT COLUMN: Market Breadth + Credit Spread
# ------------------------------------------------------------------
with col_market:
    if fig_timeseries is not None:
        st.subheader("20D & 60D MA")
        st.plotly_chart(fig_timeseries, use_container_width=True)

        if fig_bar is not None:
            st.plotly_chart(fig_bar, use_container_width=True)

    elif stock_data is None:
        st.error("未能获取股票数据，无法计算市场宽度历史。")
    else:
        st.warning("股票数据获取成功，但历史计算失败或数据不足（需要至少60天数据）。")

    # --- Credit Spread ---
    df_spread = get_highyield_data()

    if df_spread is not None and not df_spread.empty:
        fig_spread = create_credit_spread_chart(df_spread)
        if fig_spread is not None:
            st.subheader("High Yield (Option-Adjusted Spread)")
            st.plotly_chart(fig_spread, use_container_width=True)

    elif not FRED_API_KEY:
        st.warning("请设置 FRED_API_KEY 以显示信用利差数据。")
    else:
        st.info("信用利差数据加载中或加载失败。")

# ------------------------------------------------------------------
# 3. SIDEBAR
# ------------------------------------------------------------------
st.sidebar.header("Treasury Yield")
st.sidebar.markdown(f"总数据点: **{len(df_long) // 12}**")
st.sidebar.markdown(f"Current date: **{df_long['Date'].max().date()}**")

latest_breadth_date = "N/A"
if not breadth_history.empty:
    latest_breadth_date = breadth_history.index[-1].strftime("%Y-%m-%d")

st.sidebar.header("S&P 500 宽度信息")
st.sidebar.markdown(f"数据统计日期: **{latest_breadth_date}**")
st.sidebar.markdown(
    f"成分股总数: **{len(current_sp500_symbols) if current_sp500_symbols else 'N/A'}**"
)
st.sidebar.markdown(f"参与计算股票数: **{breadth_data.get('eligible_total', 'N/A')}**")
st.sidebar.markdown(f"**高于 20日 MA 数量:** **{breadth_data.get('20DMA_count', 'N/A')}**")
st.sidebar.markdown(f"**高于 60日 MA 数量:** **{breadth_data.get('60DMA_count', 'N/A')}**")

if not df_fed_bs.empty:
    latest_fed_date = df_fed_bs.iloc[-1]["date"].date()
    latest_fed_assets = df_fed_bs.iloc[-1]["balance_sheet_tn"]

    st.sidebar.header("Fed Balance Sheet")
    st.sidebar.markdown(f"最新日期: **{latest_fed_date}**")
    st.sidebar.markdown(f"总资产: **{latest_fed_assets:.2f}T USD**")

if not df_gold_oil.empty:
    latest_ratio_row = df_gold_oil.iloc[-1]

    st.sidebar.header("Gold / Oil Ratio")
    st.sidebar.markdown(f"最新日期: **{latest_ratio_row['date'].date()}**")
    st.sidebar.markdown(f"金油比: **{latest_ratio_row['gold_oil_ratio']:.2f}**")
    st.sidebar.markdown(f"Gold: **{latest_ratio_row['gold_usd_per_oz']:.2f} USD/oz**")
    st.sidebar.markdown(f"WTI: **{latest_ratio_row['oil_usd_per_bbl']:.2f} USD/bbl**")
