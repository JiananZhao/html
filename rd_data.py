import pandas as pd
import plotly.express as px
import streamlit as st # <-- NEW: Import Streamlit

# Remove 'import plotly.io as pio' and 'import os' as they are not needed here

st.set_page_config(layout="wide", page_title="Yield Curve Visualization") # <-- Optional, but recommended

# -----------------
# 1. Data Setup (The Streamlit-friendly way)
# -----------------
# In a full Streamlit app, you should use st.file_uploader or st.cache_data
# For this example, we assume the file 'daily-treasury-rates.csv' is present.

try:
    # Use st.cache_data to load the data only once for efficiency
    @st.cache_data
    def load_data():
        return pd.read_csv('daily-treasury-rates.csv')
    
    df = load_data()
    
except FileNotFoundError:
    st.error("Error: 'daily-treasury-rates.csv' not found. Please ensure the file is in the same directory as the app.")
    st.stop() # <-- Use st.stop() instead of exit() to halt the Streamlit script gracefully

# 1. Clean the 'Date' column and filter for data since 2000
df['Date'] = pd.to_datetime(df['Date'])
df = df[df['Date'].dt.year >= 2000].copy()

# 2. Define Maturity Labels and their corresponding numerical values (in years)
maturity_map = {
    '1 Mo': 1/12, '2 Mo': 2/12, '3 Mo': 3/12, '6 Mo': 6/12,
    '1 Yr': 1, '2 Yr': 2, '3 Yr': 3, '5 Yr': 5, '7 Yr': 7,
    '10 Yr': 10, '20 Yr': 20, '30 Yr': 30
}

# Identify the yield columns
yield_cols = [col for col in df.columns if col.strip() in maturity_map]

# 3. Rename columns to match dictionary keys for easy melting
df.columns = [col.strip() if col.strip() in maturity_map else col for col in df.columns]

# -----------------
# 2. Data Transformation (Melting)
# -----------------
# Convert from wide to long format
df_long = df.melt(
    id_vars=['Date'],
    value_vars=yield_cols,
    var_name='Maturity_Label',
    value_name='Yield'
).dropna(subset=['Yield']) # Only drop rows where 'Yield' is NaN

# Convert Maturity_Label to a numerical X-axis value (in years)
df_long['Maturity_Years'] = df_long['Maturity_Label'].map(maturity_map)

# Sort the data frame by Date and then by Maturity (for correct line drawing)
df_long = df_long.sort_values(by=['Date', 'Maturity_Years'])

# Ensure Yield is numeric (already done, but good practice)
df_long['Yield'] = pd.to_numeric(df_long['Yield'], errors='coerce')


# -----------------
# 3. Visualization and Display (STREAMLIT INTEGRATION)
# -----------------
st.title("Daily U.S. Treasury Yield Curve Animation")

# Create the interactive animated plot
fig = px.line(
    df_long,
    x='Maturity_Years',
    y='Yield',
    animation_frame=df_long['Date'].astype(str),
    hover_data={'Maturity_Years': False, 'Maturity_Label': True},
    markers=True,
    labels={
        "Maturity_Years": "Time to Maturity (Years)",
        "Yield": "Yield (%)",
        "animation_frame": "Date"
    },
    title="Daily U.S. Treasury Yield Curve Animation (Post-2000)"
)

# Customize the layout
fig.update_layout(
    xaxis_tickvals=list(maturity_map.values()),
    xaxis_ticktext=list(maturity_map.keys()),
    xaxis_range=[-0.1, 31],
    # It's better to dynamically set yaxis_range based on data:
    yaxis_range=[df_long['Yield'].min() * 0.95, df_long['Yield'].max() * 1.05],
    yaxis_title="Yield (%)",
    template="plotly_white",
    width=1200,
    height=600 # Set a fixed height for better mobile display
)

# CRITICAL CHANGE: Use st.plotly_chart() to display the figure
st.plotly_chart(fig, use_container_width=True)

