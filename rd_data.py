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
# ------------------------------------------------------------------

current_sp500_symbols = get_sp500_symbols()

# Default initialization now includes both 20DMA and 60DMA keys
breadth_data = {
    "eligible_total": "N/A",
    "20DMA_count": "N/A", "20DMA_percentage": 0,
    "60DMA_count": "N/A", "60DMA_percentage": 0,
}
stock_data = None
fig_gauge = None # <-- Now unused, but initialize for safety

# Try fetching stock data only if we have the symbols
if current_sp500_symbols:
    stock_data = get_sp500_stock_data()

# Try calculating breadth and creating the bar chart
if stock_data is not None and not stock_data.empty:
    breadth_data = calculate_market_breadth(stock_data)
    # --- CRITICAL: Call the NEW bar chart function ---
    fig_breadth = create_breadth_bar_chart(breadth_data) 
else:
    fig_breadth = None # Ensure fig_breadth is defined even on failure

# ------------------------------------------------------------------
# 2. LAYOUT: Treasury Data (Left Column)
# ------------------------------------------------------------------

col_treasury, col_market = st.columns([3, 2])

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
    st.header("S&P 500 市场宽度") # Removed the specific (20 DMA) label
    
    if not current_sp500_symbols:
        st.warning("未能获取 S&P 500 成分股列表。")
    
    if fig_breadth: # Check the new fig_breadth variable
        st.plotly_chart(fig_breadth, use_container_width=True)
    elif stock_data is None:
        st.error("未能获取股票数据，无法计算市场宽度。")
    else:
        # Show status if data was pulled but calculation or chart failed
        st.warning("股票数据获取成功，但计算或图表创建失败。")

# ------------------------------------------------------------------
# 4. SIDEBAR (Update to display both 20DMA and 60DMA)
# ------------------------------------------------------------------
st.sidebar.header("国债数据信息")
st.sidebar.markdown(f"总数据点: **{len(df_long)}**")
st.sidebar.markdown(f"起始日期: **{df_long['Date'].min().date()}**")

st.sidebar.header("S&P 500 宽度信息")
st.sidebar.markdown(f"成分股总数: **{len(current_sp500_symbols) if current_sp500_symbols else 'N/A'}**")
st.sidebar.markdown(f"参与计算股票数: **{breadth_data.get('eligible_total', 'N/A')}**")
st.sidebar.markdown(f"**高于 20日 MA 数量:** **{breadth_data.get('20DMA_count', 'N/A')}**")
st.sidebar.markdown(f"**高于 60日 MA 数量:** **{breadth_data.get('60DMA_count', 'N/A')}**")


