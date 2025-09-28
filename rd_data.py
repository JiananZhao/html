# rd_data.py

import streamlit as st
import pandas as pd
import requests 
from data_processing import load_and_transform_data 
from visualization import create_yield_curve_chart, create_breadth_gauge_chart
from market_analysis import get_sp500_stock_data, calculate_market_breadth, get_sp500_symbols 

# Set page configuration
st.set_page_config(layout="wide", page_title="Yield Curve and Market Breadth")

# ------------------------------------------------------------------
# 1. 初始化变量和获取市场数据 (在任何 with 块外部运行)
# ------------------------------------------------------------------

# 确保侧边栏信息在任何情况下都能被访问
current_sp500_symbols = get_sp500_symbols()

# 默认初始化 breadth_data
breadth_data = {
    "count": "N/A", 
    "total": "N/A", 
    "percentage": 0
}
stock_data = None
fig_gauge = None

# 尝试获取股票数据
if current_sp500_symbols:
    stock_data = get_sp500_stock_data()

# 尝试计算市场宽度
if stock_data is not None and not stock_data.empty:
    breadth_data = calculate_market_breadth(stock_data)
    # 仅在数据成功计算后才创建图表
    fig_gauge = create_breadth_gauge_chart(breadth_data)

# ------------------------------------------------------------------
# 2. 布局和渲染
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
    
    # 生成并显示国债图表
    fig_treasury = create_yield_curve_chart(df_long, most_recent_date)
    st.plotly_chart(fig_treasury, use_container_width=True)


with col_market:
    st.header("S&P 500 市场宽度 (20 DMA)")
    
    # 显示成分股获取状态
    if not current_sp500_symbols:
        st.warning("未能获取 S&P 500 成分股列表。")
    
    # 显示市场宽度图表或错误信息
    if fig_gauge:
        st.plotly_chart(fig_gauge, use_container_width=True)
    elif stock_data is None:
        st.error("未能获取股票数据，无法计算市场宽度。")
    else:
        st.warning(f"成功获取 {breadth_data.get('total', 0)} 支股票数据，但图表创建失败或计算结果无效。")


# ------------------------------------------------------------------
# 3. 侧边栏代码 (现在安全访问所有变量)
# ------------------------------------------------------------------
st.sidebar.header("国债数据信息")
st.sidebar.markdown(f"总数据点: **{len(df_long)}**")
st.sidebar.markdown(f"起始日期: **{df_long['Date'].min().date()}**")

st.sidebar.header("S&P 500 宽度信息")
# 这里的 current_sp500_symbols 和 breadth_data 现在保证在全局作用域中被定义
st.sidebar.markdown(f"成分股总数: **{len(current_sp500_symbols) if current_sp500_symbols else 'N/A'}**")
st.sidebar.markdown(f"参与计算股票数: **{breadth_data.get('total', 'N/A')}**")
st.sidebar.markdown(f"高于20日MA数量: **{breadth_data.get('count', 'N/A')}**")
