import pandas as pd
import streamlit as st
from datetime import date, timedelta

MATURITY_MAP = {
    "1 Mo": 1/12, "2 Mo": 2/12, "3 Mo": 3/12, "4 Mo": 4/12, "6 Mo": 6/12,
    "1 Yr": 1, "2 Yr": 2, "3 Yr": 3, "5 Yr": 5, "7 Yr": 7,
    "10 Yr": 10, "20 Yr": 20, "30 Yr": 30
}

@st.cache_data(ttl=3600)
def load_and_transform_data(csv_file="daily-treasury-rates.csv"):
    try:
        df = pd.read_csv(csv_file)
        if 'Date' in df.columns:
            df['Date'] = pd.to_datetime(df['Date'])
            all_cols = df.columns.tolist()
            yield_cols = [col for col in MATURITY_MAP.keys() if col in all_cols]
            
            df_long = pd.melt(
                df,
                id_vars=['Date'],
                value_vars=yield_cols,
                var_name='Maturity_Label',
                value_name='Yield'
            ).dropna(subset=['Yield'])
            
            df_long['Maturity_Years'] = df_long['Maturity_Label'].map(MATURITY_MAP)
            df_long['Yield'] = pd.to_numeric(df_long['Yield'], errors='coerce')
            df_long = df_long.dropna(subset=['Yield'])
            df_long = df_long.sort_values(by=['Date', 'Maturity_Years'])
            return df_long
    except Exception as e:
        print(f"Error in load_and_transform_data: {e}")
    return pd.DataFrame()
