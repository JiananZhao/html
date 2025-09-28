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
end_date_for
