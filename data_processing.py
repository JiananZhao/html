# data_processing.py

import pandas as pd
import streamlit as st
from datetime import datetime

# Define constants (Maturity Maps) here
MATURITY_MAP = {
    '1 Mo': 1/12, '2 Mo': 2/12, '3 Mo': 3/12, '6 Mo': 6/12,
    '1 Yr': 1, '2 Yr': 2, '3 Yr': 3, '5 Yr': 5, '7 Yr': 7,
    '10 Yr': 10, '20 Yr': 20, '30 Yr': 30
}

CUSTOM_X_AXIS_TICKS_LABELS = {
    '1 Yr': 1, '5 Yr': 5, '10 Yr': 10, '15 Yr': 15, '20 Yr': 20, '30 Yr': 30
}


@st.cache_data
def load_and_transform_data():
    """Loads, cleans, filters, and transforms the yield curve data."""
    
    try:
        # Load the data file
        df = pd.read_csv('daily-treasury-rates.csv')
    except FileNotFoundError:
        st.error("Error: 'daily-treasury-rates.csv' not found. Please ensure the data file is correctly placed.")
        return None # Return None on error

    # 1. Clean the 'Date' column and filter for data since 2000
    df['Date'] = pd.to_datetime(df['Date'])
    df = df[df['Date'].dt.year >= 2000].copy()

    # Identify the yield columns and rename them
    yield_cols = [col for col in df.columns if col.strip() in MATURITY_MAP]
    df.columns = [col.strip() if col.strip() in MATURITY_MAP else col for col in df.columns]

    # 2. Data Transformation (Melting)
    df_long = df.melt(
        id_vars=['Date'],
        value_vars=yield_cols,
        var_name='Maturity_Label',
        value_name='Yield'
    ).dropna(subset=['Yield'])

    # Convert Maturity_Label to a numerical X-axis value (in years)
    df_long['Maturity_Years'] = df_long['Maturity_Label'].map(MATURITY_MAP)

    # Sort data for correct line drawing
    df_long = df_long.sort_values(by=['Date', 'Maturity_Years'])

    # Ensure Yield is numeric
    df_long['Yield'] = pd.to_numeric(df_long['Yield'], errors='coerce')
    
    return df_long
