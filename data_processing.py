# data_processing.py

import pandas as pd
import streamlit as st

# Define constants (Maturity Maps)
MATURITY_MAP = {
    '1 Mo': 1/12, '2 Mo': 2/12, '3 Mo': 3/12, '6 Mo': 6/12,
    '1 Yr': 1, '2 Yr': 2, '3 Yr': 3, '5 Yr': 5, '7 Yr': 7,
    '10 Yr': 10, '20 Yr': 20, '30 Yr': 30
}

# Define custom ticks for the X-axis
CUSTOM_X_AXIS_TICKS_LABELS = {
    '0 Yr': 0, 
    '1 Yr': 1, '5 Yr': 5, '10 Yr': 10, '15 Yr': 15, '20 Yr': 20, '30 Yr': 30
}


@st.cache_data(ttl=timedelta(hours=1))
def load_and_transform_data():
    """Loads, cleans, filters, and transforms the yield curve data."""
    
    try:
        # Load the data file
        df = pd.read_csv('daily-treasury-rates.csv')
    except FileNotFoundError:
        # st.error is now handled in the main app, but we return None
        return None 

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
    ).dropna(subset=['Yield']) # Drop NaNs introduced during melt

    # Convert Maturity_Label to a numerical X-axis value (in years)
    df_long['Maturity_Years'] = df_long['Maturity_Label'].map(MATURITY_MAP)

    # Ensure Yield is numeric and handle potential issues
    df_long['Yield'] = pd.to_numeric(df_long['Yield'], errors='coerce') 
    
    # CRITICAL: Drop any rows where Yield became NaN after coercion
    df_long = df_long.dropna(subset=['Yield'])

    # Sort data for correct line drawing
    df_long = df_long.sort_values(by=['Date', 'Maturity_Years'])
    
    return df_long
