# rd_data.py

import streamlit as st
import pandas as pd
import requests # Used indirectly by market_analysis
from data_processing import load_and_transform_data 
from visualization import create_yield_curve_chart, create_breadth_gauge_chart
from market_analysis import get_sp500_stock_data, calculate_market_breadth, get_sp500_symbols 

# Set page configuration
st.set_page_config(layout="wide", page_title="Yield Curve and Market Breadth")

# ------------------------------------------------------------------
# 1. INITIALIZATION and DATA ACQUISITION (CRITICAL: Runs BEFORE layout)
#    This ensures all variables needed by st.sidebar exist.
# ------------------------------------------------------------------

# Initialize variables to ensure they exist globally, even if data acquisition fails
current_sp500_symbols = get_sp500_symbols()

breadth_data = {
    "count": "N/A", 
    "total": "N/A", 
    "percentage": 0
}
stock_data = None
fig_gauge = None

# 1A. Try fetching stock data only if we have the symbols
if current_sp500_symbols:
    stock_data = get_sp500_stock_data()

# 1B. Try calculating breadth and creating the gauge chart
if stock_data is not None and not stock_data.empty:
    breadth_data = calculate_market_breadth(stock_data)
    fig_gauge = create_breadth_gauge_chart(breadth_data)

# ------------------------------------------------------------------
# 2. LAYOUT: Treasury Data (Left Column)
# ------------------------------------------------------------------

col_treasury, col_market = st.columns([2, 1])

with col_treasury:
    st.header("Daily U.S. Treasury Yield Curve Animation")
    df_long = load_and_transform_data()

    if df_long is None:
        st.stop()

    most_recent_date = df_long['Date'].max()
    default_frame = str(most_recent_date.date())

    st.markdown(f"**最新国债数据日期:** `{default_frame}`")
    
    # Generate and display the treasury chart
    fig_treasury = create_yield_curve_chart(df_long, most_recent_date)
    st.plotly_chart(fig_treasury, use_container_width=True)

# ------------------------------------------------------------------
# 3. LAYOUT: Market Breadth (Right Column)
# ------------------------------------------------------------------
with col_market:
    st.header("S&P 500 市场宽度 (20 DMA)")
    
    if not current_sp500_symbols:
        st.warning("未能获取 S&P 500 成分股列表。")
    
    if fig_gauge:
        st.plotly_chart(fig_gauge, use_container_width=True)
    elif stock_data is None:
        st.error("未能获取股票数据，无法计算市场宽度。")
    else:
        # Show status if data was pulled but calculation or chart failed
        st.warning(f"获取 {breadth_data.get('total', 0)} 支股票数据，但图表创建失败或计算结果无效。")

# ------------------------------------------------------------------
# 4. SIDEBAR (Safe to access all initialized variables)
# ------------------------------------------------------------------
st.sidebar.header("国债数据信息")
st.sidebar.markdown(f"总数据点: **{len(df_long)}**")
st.sidebar.markdown(f"起始日期: **{df_long['Date'].min().date()}**")

st.sidebar.header("S&P 500 宽度信息")
st.sidebar.markdown(f"成分股总数: **{len(current_sp500_symbols) if current_sp500_symbols else 'N/A'}**")
st.sidebar.markdown(f"参与计算股票数: **{breadth_data.get('total', 'N/A')}**")
st.sidebar.markdown(f"高于20日MA数量: **{breadth_data.get('count', 'N/A')}**")
