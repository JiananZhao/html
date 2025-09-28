import pandas as pd
import plotly.express as px
import plotly.io as pio # <-- Import plotly.io for file writing
import os # <-- Import os for path manipulation

# -----------------
# 1. Data Setup (Assuming 'yield-curve-rates.csv' is in the working directory)
# -----------------
try:
    df = pd.read_csv('daily-treasury-rates.csv')
except FileNotFoundError:
    print("Error: 'daily-treasury-rates.csv' not found. Please download the historical data.")
    # Exit the script gracefully if data isn't found
    exit()

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
).dropna()

# Convert Maturity_Label to a numerical X-axis value (in years)
df_long['Maturity_Years'] = df_long['Maturity_Label'].map(maturity_map)

# Sort the data frame by Date and then by Maturity (for correct line drawing)
df_long = df_long.sort_values(by=['Date', 'Maturity_Years'])

# Ensure Yield is numeric
df_long['Yield'] = pd.to_numeric(df_long['Yield'], errors='coerce')

# Rerun this entire section of your Spyder script after the data preprocessing steps

# -----------------
# 3. Visualization and Display (REVISED)
# -----------------
# Create the interactive animated plot
fig = px.line(
    df_long,
    x='Maturity_Years',
    y='Yield',
    # --- CRITICAL CHANGE: Removed the incorrect 'color' argument ---
    # The animation_frame groups the line implicitly by date.
    animation_frame=df_long['Date'].astype(str),
    
    # Use 'Maturity_Label' for hover text and explicitly show markers
    hover_data={'Maturity_Years': False, 'Maturity_Label': True},
    markers=True, # <-- Explicitly show the data points
    
    labels={
        "Maturity_Years": "Time to Maturity (Years)",
        "Yield": "Yield (%)",
        "animation_frame": "Date"
    },
    title="Daily U.S. Treasury Yield Curve Animation (2025)"
)

# Customize the layout
fig.update_layout(
    xaxis_tickvals=list(maturity_map.values()),
    xaxis_ticktext=list(maturity_map.keys()),
    xaxis_range=[-0.1, 31],
    yaxis_range=[2, 6],
    yaxis_title="Yield (%)",
    template="plotly_white"
)

# Display the figure using the robust method:
output_file = 'yield_curve_animation.html'
# You will need 'import plotly.io as pio' at the top of your script
pio.write_html(fig, file=output_file, auto_open=True)
