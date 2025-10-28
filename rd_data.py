# rd_data.py

import streamlit as st
import pandas as pd
import requests 
import datetime
import plotly.express as px
from data_processing import load_and_transform_data 
from visualization import create_yield_curve_chart, create_breadth_bar_chart, create_breadth_timeseries_chart, create_unemployment_chart, create_credit_spread_chart
from market_analysis import get_sp500_stock_data, calculate_market_breadth_history, get_latest_breadth_snapshot, get_sp500_symbols, get_unemployment_data, get_highyield_data

# Set page configuration
st.set_page_config(layout="wide", page_title="Yield Curve and Market Breadth")

# ------------------------------------------------------------------
# 1. INITIALIZATION and DATA ACQUISITION 
#    CRITICAL: Runs BEFORE layout to ensure all sidebar variables exist.
# ------------------------------------------------------------------

current_sp500_symbols = get_sp500_symbols()
stock_data = None
breadth_history = pd.DataFrame()
fig_timeseries = None
fig_bar = None
df_unrate = pd.DataFrame() # <-- 新增
fig_unrate = None        # <-- 新增

# Default initialization for sidebar (safe for global access)
breadth_data = {
    "eligible_total": "N/A",
    "20DMA_count": "N/A", "20DMA_percentage": 0,
    "60DMA_count": "N/A", "60DMA_percentage": 0,
}

# 1A. Try fetching stock data
# if current_sp500_symbols:
#    stock_data = get_sp500_stock_data()

# 1B. Try calculating breadth history and latest snapshot
if stock_data is not None and not stock_data.empty:
    # Calculate the breadth for all historical dates
    breadth_history = calculate_market_breadth_history(stock_data)
    
    if not breadth_history.empty:
        # Get latest data for the bar chart and sidebar
        breadth_data = get_latest_breadth_snapshot(breadth_history) 
        
        # Create both charts
        fig_timeseries = create_breadth_timeseries_chart(breadth_history)
        fig_bar = create_breadth_bar_chart(breadth_data)
# 1D. Get Unemployment Data
with st.spinner('正在获取 FRED 失业率数据...'):
    df_unrate = get_unemployment_data()
    if not df_unrate.empty:
        fig_unrate = create_unemployment_chart(df_unrate) # <-- 创建图表
        
# ------------------------------------------------------------------
# 2. LAYOUT: Treasury Data (Left Column)
# ------------------------------------------------------------------

# Adjust column width for a wider right plot
col_treasury, col_market = st.columns([2, 3]) 

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

    # --- 失业率图表 ---
    if fig_unrate:
        st.subheader("宏观经济指标")
        st.plotly_chart(fig_unrate, use_container_width=True)
    elif not FRED_API_KEY:
         st.warning("请设置 FRED_API_KEY 以显示宏观经济指标。")


# ------------------------------------------------------------------
# 3. LAYOUT: Market Breadth (Right Column)
# ------------------------------------------------------------------
with col_market:
    st.header("S&P 500 市场宽度分析") 
    
    if fig_timeseries:
        st.subheader("历史趋势 (20日 & 60日 MA)")
        st.plotly_chart(fig_timeseries, use_container_width=True)
        
        # Place the bar chart below the time series chart
        st.subheader("Market Breadth Today")
        st.plotly_chart(fig_bar, use_container_width=True)

    elif stock_data is None:
        st.error("未能获取股票数据，无法计算市场宽度历史。")
    else:
        st.warning("股票数据获取成功，但历史计算失败或数据不足（需要至少60天数据）。")


# ------------------------------------------------------------------
# 4. SIDEBAR 
# ------------------------------------------------------------------
st.sidebar.header("国债数据信息")
# df_long is guaranteed to be loaded if the app reaches here
st.sidebar.markdown(f"总数据点: **{len(df_long)//12}**") 
st.sidebar.markdown(f"Current date: **{df_long['Date'].max().date()}**")
# 确保在侧边栏使用数据之前，它们已经被成功计算和加载
latest_breadth_date = "N/A"
if not breadth_history.empty:
    # 提取 breadth_history DataFrame 的最后一个索引（即最新日期）
    latest_breadth_date = breadth_history.index[-1].strftime('%Y-%m-%d')
st.sidebar.header("S&P 500 宽度信息")
st.sidebar.markdown(f"数据统计日期: **{latest_breadth_date}**") 
# Variables are guaranteed to exist due to initialization
st.sidebar.markdown(f"成分股总数: **{len(current_sp500_symbols) if current_sp500_symbols else 'N/A'}**")
st.sidebar.markdown(f"参与计算股票数: **{breadth_data.get('eligible_total', 'N/A')}**")
st.sidebar.markdown(f"**高于 20日 MA 数量:** **{breadth_data.get('20DMA_count', 'N/A')}**")
st.sidebar.markdown(f"**高于 60日 MA 数量:** **{breadth_data.get('60DMA_count', 'N/A')}**")

# --- 右侧：信用利差 ---
with col_market:
    st.header("Credit Spread")
    
    # 1. 加载信用利差数据
    # 假设 FRED_SERIES_ID_SPREAD 和 START_DATE_SPREAD 已经定义
    df_spread = get_highyield_data()
    
    # 2. 检查数据并生成图表
    if not df_spread.empty:
        fig_spread = create_credit_spread_chart(df_spread)

        st.subheader("美国高收益债信用利差 (Option-Adjusted Spread)")
        
        # 3. 显示图表
        st.plotly_chart(fig_spread, use_container_width=True)


    elif not FRED_API_KEY:
        st.warning("请设置 FRED_API_KEY 以显示信用利差数据。")
    else:
        st.info("信用利差数据加载中或加载失败。")







