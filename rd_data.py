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
        return pd.read_csv('daily-treasury-rates.csv')
    df = load_data()
    
except FileNotFoundError:
    st.error("Error: 'daily-treasury-rates.csv' not found. Please ensure the data file is correctly placed.")
    st.stop()

# 1. Clean the 'Date' column and filter for data since 2000
df['Date'] = pd.to_datetime(df['Date'])
df = df[df['Date'].dt.year >= 2000].copy()

# 2. Define Maturity Labels and their corresponding numerical values (in years)
# ⚠️ 这里重新定义了 maturity_map，因为我们需要 Maturity_Years 作为 X 轴的数值
maturity_map = {
    '1 Mo': 1/12, '2 Mo': 2/12, '3 Mo': 3/12, '6 Mo': 6/12,
    '1 Yr': 1, '2 Yr': 2, '3 Yr': 3, '5 Yr': 5, '7 Yr': 7,
    '10 Yr': 10, '20 Yr': 20, '30 Yr': 30
}
# 用于自定义 X 轴刻度显示的标签
custom_x_axis_ticks_labels = {
    '1 Yr': 1, '5 Yr': 5, '10 Yr': 10, '15 Yr': 15, '20 Yr': 20, '30 Yr': 30
}


# Identify the yield columns and rename columns
yield_cols = [col for col in df.columns if col.strip() in maturity_map]
df.columns = [col.strip() if col.strip() in maturity_map else col for col in df.columns]

# -----------------
# 2. Data Transformation (Melting)
# -----------------
df_long = df.melt(
    id_vars=['Date'],
    value_vars=yield_cols,
    var_name='Maturity_Label',
    value_name='Yield'
).dropna(subset=['Yield'])

# Convert Maturity_Label to a numerical X-axis value (in years)
# ⚠️ 重新启用 Maturity_Years 作为 X 轴的数值
df_long['Maturity_Years'] = df_long['Maturity_Label'].map(maturity_map)

# Sort by Date and then by Maturity_Years (for correct line drawing)
df_long = df_long.sort_values(by=['Date', 'Maturity_Years'])

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
    x='Maturity_Years', # <-- X-axis switched back to numerical Maturity_Years
    y='Yield',
    animation_frame=df_long['Date'].astype(str),
    animation_group='Date',
    hover_data={'Maturity_Label': True, 'Yield': ':.2f'}, # 悬停时仍显示 Maturity_Label
    markers=True,category_orders=(),
    labels={
        "Maturity_Years": "Time to Maturity (Years)", # X轴标签
        "Yield": "Yield (%)",
        "animation_frame": "Date"
        },
    title="U.S. Treasury Yield Curve Animation"
)

# Customize the layout
fig.update_layout(
    xaxis_title="Time to Maturity (Years)", # X轴标题
    yaxis_title="Yield (%)",
    template="plotly_white",
    yaxis_range=[df_long['Yield'].min() * 0.8, df_long['Yield'].max() * 1.05],
    # yaxis_range=[0, 8],
    height=600, # 保持高度不变
    width=600,
    hovermode="x unified",

    # --- 自定义 X 轴刻度 ---
    xaxis=dict(
        tickmode='array', # 使用数组模式设置刻度
        tickvals=list(custom_x_axis_ticks_labels.values()), # 实际的数值位置
        ticktext=list(custom_x_axis_ticks_labels.keys()),
        range=[-0.1, 31],)
)

# --- 确保设置滑块索引的逻辑正确 ---
date_list = sorted(df_long['Date'].unique())
default_index = date_list.index(most_recent_date)

if fig.layout.sliders:
    fig.layout.sliders[0].active = default_index
else:
    st.warning("Plotly figure did not create a slider for animation_frame.")
st.plotly_chart(fig, use_container_width=True)





