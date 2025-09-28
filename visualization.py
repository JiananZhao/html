# visualization.py

import plotly.express as px
import plotly.graph_objects as go # Required for the Gauge chart
import streamlit as st
import pandas as pd
from datetime import datetime 
from data_processing import CUSTOM_X_AXIS_TICKS_LABELS

def create_yield_curve_chart(df_long: pd.DataFrame, most_recent_date: datetime):
    """
    Generates the interactive Plotly yield curve chart, defaulting to the latest date.
    """
    
    # Prepare data for Plotly animation
    df_long['Date_str'] = df_long['Date'].astype(str) 

    # Create the interactive animated plot
    fig = px.line(
        df_long,
        x='Maturity_Years',
        y='Yield',
        animation_frame='Date_str',
        animation_group='Date_str', 
        hover_data={'Maturity_Label': True, 'Yield': ':.2f'},
        markers=True,
        labels={
            "Maturity_Years": "Time to Maturity (Years)",
            "Yield": "Yield (%)",
            "animation_frame": "Date"
        },
        title="U.S. Treasury Yield Curve Animation"
    )

    # Calculate Y-axis range safely and dynamically
    min_yield = df_long['Yield'].min()
    max_yield = df_long['Yield'].max()
    
    y_floor = max(-0.5, min_yield - 0.5) 
    y_ceiling = max_yield * 1.05
    y_range = [y_floor, y_ceiling] 

    # Customize the layout
    fig.update_layout(
        xaxis_title="Time to Maturity (Years)",
        yaxis_title="Yield (%)",
        template="plotly_white",
        yaxis_range=y_range, 
        height=600,
        width=600,
        hovermode="x unified",
        
        # Custom X-axis ticks
        xaxis=dict(
            tickmode='array',
            tickvals=list(CUSTOM_X_AXIS_TICKS_LABELS.values()),
            ticktext=list(CUSTOM_X_AXIS_TICKS_LABELS.keys()),
            range=[-1, 31],
            type='linear' 
        )
    )

    # Set default frame to the most recent date
    date_list = sorted(df_long['Date'].unique())
    most_recent_dt = pd.to_datetime(most_recent_date) 
    
    if most_recent_dt in date_list:
        default_index = date_list.index(most_recent_dt) 
    else:
        default_index = len(date_list) - 1

    if fig.layout.sliders:
        fig.layout.sliders[0].active = default_index

    return fig


def create_breadth_gauge_chart(breadth_data: dict):
    """
    Generates a gauge chart showing the percentage of stocks above the 20 DMA.
    """
    percentage = breadth_data.get("percentage", 0)
    count = breadth_data.get("count", 0)
    total = breadth_data.get("total", 0)
    
    if total == 0:
        return None

    fig = go.Figure(go.Indicator(
        mode = "gauge+number",
        value = percentage,
        domain = {'x': [0, 1], 'y': [0, 1]},
        title = {'text': "20日均线上方的股票百分比"},
        gauge = {
            'axis': {'range': [None, 100], 'tickwidth': 1, 'tickcolor': "darkblue"},
            'bar': {'color': "green"},
            'bgcolor': "white",
            'borderwidth': 2,
            'bordercolor': "gray",
            'steps': [
                {'range': [0, 25], 'color': 'red'},
                {'range': [25, 50], 'color': 'lightcoral'},
                {'range': [50, 75], 'color': 'lightgreen'},
                {'range': [75, 100], 'color': 'green'}],
            'threshold': {
                'line': {'color': "red", 'width': 4},
                'thickness': 0.75,
                'value': 50}
        }
    ))

    fig.update_layout(
        margin=dict(l=20, r=20, t=50, b=20),
        height=500,
        title_text=f"当前宽度：{count}/{total} (股票数)"
    )
    
    return fig
