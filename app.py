# rd_data.py

import streamlit as st
import pandas as pd
from data_processing import load_and_transform_data # 从模块导入数据处理函数
from visualization import create_yield_curve_chart # 从模块导入图表生成函数

# Set page configuration
st.set_page_config(layout="wide", page_title="Yield Curve Visualization")

# -----------------
# 1. Load Data
# -----------------
df_long = load_and_transform_data()

# Check if data loading failed
if df_long is None:
    st.stop()

# Get the most recent date for display and default plot setting
most_recent_date = df_long['Date'].max()
default_frame = str(most_recent_date.date())

# -----------------
# 2. Visualization and Display (UI Control)
# -----------------
st.title("Daily U.S. Treasury Yield Curve Animation")
st.markdown(f"**最新数据日期:** `{default_frame}`")

# Generate the plot using the function from visualization.py
fig = create_yield_curve_chart(df_long, most_recent_date)
    
# Display the figure
st.plotly_chart(fig, use_container_width=True)

# 可选：在侧边栏添加其他交互或信息
st.sidebar.header("数据信息")
st.sidebar.markdown(f"总数据点: **{len(df_long)}**")
st.sidebar.markdown(f"起始日期: **{df_long['Date'].min().date()}**")
