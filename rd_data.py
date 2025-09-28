# rd_data.py

import streamlit as st
import pandas as pd
from data_processing import load_and_transform_data # Import data processing function
from visualization import create_yield_curve_chart # Import visualization function

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
st.markdown(f"**Most recent date:** `{default_frame}`")

# Optional: Add data info to the sidebar (using data from df_long)
st.sidebar.header("Data Info")
st.sidebar.markdown(f"Total data points:**{len(df_long.index)}**")
st.sidebar.markdown(f"Initial date:**{df_long['Date'].min().date()}**")

# Generate the plot using the function from visualization.py
fig = create_yield_curve_chart(df_long, most_recent_date)
    
# Display the figure
st.plotly_chart(fig, use_container_width=True)




