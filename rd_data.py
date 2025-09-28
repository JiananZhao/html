# rd_data.py

import streamlit as st
import pandas as pd
import requests # <-- 新增：间接依赖于 market_analysis.py 中的 requests
from data_processing import load_and_transform_data 
from visualization import create_yield_curve_chart, create_breadth_gauge_chart
from market_analysis import get_sp500_stock_data, calculate_market_breadth, get_sp500_symbols # <-- 导入 get_sp500_symbols

# Set page configuration
st.set_page_config(layout="wide", page_title="Yield Curve and Market Breadth")

# ------------------------------------
# 1. 数据加载和处理
# ------------------------------------
col_treasury, col_market = st.columns([2, 1])

with col_treasury:
    st.header("Daily U.S. Treasury Yield Curve Animation")
    df_long = load_and_transform_data()

    if df_long is None:
        st.stop()

    most_recent_date = df_long['Date'].max()
    default_frame = str(most_recent_date.date())

    st.markdown(f"**最新国债数据日期:** `{default_frame}`")
    
    # 生成并显示国债图表
    fig_treasury = create_yield_curve_chart(df_long, most_recent_date)
    st.plotly_chart(fig_treasury, use_container_width=True)

    # 侧边栏信息 (保持不变)
    st.sidebar.header("国债数据信息")
    st.sidebar.markdown(f"总数据点: **{len(df_long)}**")
    st.sidebar.markdown(f"起始日期: **{df_long['Date'].min().date()}**")


with col_market:
    st.header("S&P 500 市场宽度 (20 DMA)")
    
    # 获取最新的成分股列表以显示总数
    current_sp500_symbols = get_sp500_symbols()
    
    # 1. 获取 S&P 500 数据
    stock_data = get_sp500_stock_data()
    
    if stock_data is not None:
        # 2. 计算宽度指标
        breadth_data = calculate_market_breadth(stock_data)
        
        # 3. 生成并显示仪表盘
        fig_gauge = create_breadth_gauge_chart(breadth_data)
        if fig_gauge:
            st.plotly_chart(fig_gauge, use_container_width=True)
        else:
            st.warning("无法计算宽度指标，可能是数据不足或图表生成失败。")

    else:
        st.error("未能获取股票数据，无法计算市场宽度。")

    st.sidebar.header("S&P 500 宽度信息")
    st.sidebar.markdown(f"成分股总数: **{len(current_sp500_symbols) if current_sp500_symbols else 'N/A'}**")
    st.sidebar.markdown(f"参与计算股票数: **{breadth_data.get('total', 'N/A')}**")
    st.sidebar.markdown(f"高于20日MA数量: **{breadth_data.get('count', 'N/A')}**")
