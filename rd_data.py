import pandas as pd
import plotly.express as px
import streamlit as st
from datetime import datetime

# Set page configuration
st.set_page_config(layout="wide", page_title="Yield Curve Visualization")

# -----------------
# 1. Data Setup (Streamlit-friendly way)
# -----------------

try:
    @st.cache_data
    def load_data():
        # Load data from the file updated by GitHub Actions
        return pd.read_csv('daily-treasury-rates.csv')
    
    df = load_data()
    
except FileNotFoundError:
    st.error("Error: 'daily-treasury-rates.csv' not found. Please ensure the data file is correctly placed.")
    st.stop()

# 1. Clean the 'Date' column and filter for data since 2000
df['Date'] = pd.to_datetime(df['Date'])
df = df[df['Date'].dt.year >= 2000].copy()

# 2. Define Maturity Labels and their intended display order (for X-axis)
maturity_labels = [
    '1 Mo', '2 Mo', '3 Mo', '6 Mo',
    '1 Yr', '2 Yr', '3 Yr', '5 Yr', '7 Yr',
    '10 Yr', '20 Yr', '30 Yr'
]

# Identify the yield columns and rename columns
yield_cols = [col for col in df.columns if col.strip() in maturity_labels]
df.columns = [col.strip() if col.strip() in maturity_labels else col for col in df.columns]

# -----------------
# 2. Data Transformation (Melting)
# -----------------
df_long = df.melt(
    id_vars=['Date'],
    value_vars=yield_cols,
    var_name='Maturity_Label',
    value_name='Yield'
).dropna(subset=['Yield'])

# Set correct categorical order for X-axis (even distribution)
df_long['Maturity_Label'] = pd.Categorical(
    df_long['Maturity_Label'],
    categories=maturity_labels,
    ordered=True
)

# Sort by Date and the new Categorical Maturity
df_long = df_long.sort_values(by=['Date', 'Maturity_Label'])

# Ensure Yield is numeric
df_long['Yield'] = pd.to_numeric(df_long['Yield'], errors='coerce')


# -----------------
# 3. Visualization and Display (STREAMLIT INTEGRATION)
# -----------------

# --- 关键：找到最新日期并设置默认值 ---
most_recent_date = df_long['Date'].max()
default_frame = str(most_recent_date.date())

st.title("Daily U.S. Treasury Yield Curve Animation")
st.markdown(f"**最新数据日期:** `{default_frame}`")

# Create the interactive animated plot
fig = px.line(
    df_long,
    x='Maturity_Label', 
    y='Yield',
    # 动画框架使用日期的字符串形式
    animation_frame=df_long['Date'].astype(str),
    animation_group='Date', 
    hover_data={'Maturity_Label': True, 'Yield': ':.2f'},
    markers=True,
    labels={
        "Maturity_Label": "Time to Maturity",
        "Yield": "Yield (%)",
        "animation_frame": "Date"
    },
    title="U.S. Treasury Yield Curve Animation"
)

# Customize the layout
fig.update_layout(
    xaxis_title="Time to Maturity (Evenly Distributed)",
    yaxis_title="Yield (%)",
    template="plotly_white",
    height=600, 
    width=400, 
    yaxis_range=[df_long['Yield'].min() * 0.95, df_long['Yield'].max() * 1.05],
    hovermode="x unified",
)

# --- 确保设置滑块索引的逻辑正确 ---
# 1. 提取所有唯一的日期并排序
date_list = sorted(df_long['Date'].unique())
# 2. 找到最新日期在排序列表中的索引
default_index = date_list.index(most_recent_date)

# 3. 设置 Plotly 动画滑块的激活索引
# 确保 sliders[0] 存在，因为 px.line with animation_frame 会自动创建它
if fig.layout.sliders:
    fig.layout.sliders[0].active = default_index
else:
    st.warning("Plotly figure did not create a slider for animation_frame.")
    
# CRITICAL CHANGE: Use st.plotly_chart() to display the figure
st.plotly_chart(fig, use_container_width=True)


