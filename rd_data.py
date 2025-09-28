# rd_data.py

import streamlit as st
import pandas as pd
import requests 
from data_processing import load_and_transform_data 
from visualization import create_yield_curve_chart, create_breadth_bar_chart, create_breadth_timeseries_chart 
from market_analysis import get_sp500_stock_data, calculate_market_breadth_history, get_latest_breadth_snapshot, get_sp500_symbols, get_spy_data 
from datetime import date, timedelta # <-- Make sure timedelta is imported here

# Set page configuration
st.set_page_config(layout="wide", page_title="Yield Curve and Market Breadth")

# ------------------------------------------------------------------
# 1. INITIALIZATION and DATA ACQUISITION 
#    CRITICAL: Runs BEFORE layout to ensure all sidebar variables exist and
#              data for plots is ready.
# ------------------------------------------------------------------

# Initialize variables with safe defaults
current_sp500_symbols = get_sp500_symbols()
stock_data = None
breadth_history = pd.DataFrame()
spy_data = pd.DataFrame() 
fig_timeseries = None
fig_bar = None

# Default initialization for sidebar (safe for global access)
breadth_data = {
    "eligible_total": "N/A",
    "20DMA_count": "N/A", "20DMA_percentage": 0,
    "60DMA_count": "N/A", "60DMA_percentage": 0,
}

# Define the start and end dates for data download (matching the 5-year window + buffer)
end_date_for_download = date.today()
start_date_for_download = end_date_for_download - timedelta(days=2008) # Roughly 5.5 years for buffer

# 1A. Try fetching S&P 500 component stock data
if current_sp500_symbols:
    stock_data = get_sp500_stock_data()
    
    # 1B. Get SPY data using the same date range
    spy_data = get_spy_data(start_date_for_download, end_date_for_download)


# 1C. Try calculating breadth history and latest snapshot, then create charts
if stock_data is not None and not stock_data.empty:
    breadth_history = calculate_market_breadth_history(stock_data)
    
    if not breadth_history.empty:
        # Get latest data for the bar chart and sidebar
        breadth_data = get_latest_breadth_snapshot(breadth_history) 
        
        # Create both charts, passing SPY data to the time series chart
        fig_timeseries = create_breadth_timeseries_chart(breadth_history, spy_data) 
        fig_bar = create_breadth_bar_chart(breadth_data)

# ------------------------------------------------------------------
# 2. LAYOUT: Treasury Data (Left Column)
# ------------------------------------------------------------------

# Adjust column width for a wider right plot (e.g., [3, 2] for 60/40 split)
col_treasury, col_market = st.columns([3, 2]) 

with col_treasury:
    st.header("Daily U.S. Treasury Yield Curve Animation")
    df_long = load_and_transform_data()

    if df_long is None:
        st.stop() # Stop if treasury data cannot be loaded

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
    st.header("S&P 500 市场宽度分析") 
    
    if fig_timeseries: # Check if historical data and chart were successfully created
        st.subheader("历史趋势 (20日 & 60日 MA) 与 SPY") 
        st.plotly_chart(fig_timeseries, use_container_width=True)
        
        # Display the latest snapshot bar chart below the time series
        if fig_bar: # Ensure bar chart was also created
            st.subheader("最新快照")
            st.plotly_chart(fig_bar, use_container_width=True)
        else:
            st.warning("最新市场宽度快照图表创建失败。")

    elif stock_data is None: # If no stock data was fetched at all
        st.error("未能获取股票数据，无法计算市场宽度历史。")
    else: # If stock data was fetched but breadth history calculation failed or was empty
        st.warning("股票数据获取成功，但历史宽度计算失败或数据不足（需要至少60天数据）。")


# ------------------------------------------------------------------
# 4. SIDEBAR 
# ------------------------------------------------------------------
st.sidebar.header("国债数据信息")
# df_long is guaranteed to be loaded if the app reaches here (due to st.stop() above)
st.sidebar.markdown(f"总数据点: **{len(df_long)}**") 
st.sidebar.markdown(f"起始日期: **{df_long['Date'].min().date()}**")

st.sidebar.header("S&P 500 宽度信息")
# Variables are guaranteed to exist due to initialization at the top
st.sidebar.markdown(f"成分股总数: **{len(current_sp500_symbols) if current_sp500_symbols else 'N/A'}**")
st.sidebar.markdown(f"参与计算股票数: **{breadth_data.get('eligible_total', 'N/A')}**")
st.sidebar.markdown(f"**高于 20日 MA 数量:** **{breadth_data.get('20DMA_count', 'N/A')}**")
st.sidebar.markdown(f"**高于 60日 MA 数量:** **{breadth_data.get('60DMA_count', 'N/A')}**")
