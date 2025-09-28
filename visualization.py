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


def create_breadth_bar_chart(breadth_data: dict):
    """
    Generates a horizontal bar chart displaying 20 DMA and 60 DMA breadth percentages.
    """
    # Extract data with safe defaults
    pct_20ma = breadth_data.get("20DMA_percentage", 0)
    pct_60ma = breadth_data.get("60DMA_percentage", 0)
    total = breadth_data.get("eligible_total", 0)
    
    if total == 0:
        return None

    # Prepare data for plotting
    df_bar = pd.DataFrame({
        'Metric': ['20日均线上方', '60日均线上方'],
        'Percentage': [pct_20ma, pct_60ma],
        'Remaining': [100 - pct_20ma, 100 - pct_60ma],
        'Text': [
            f"{pct_20ma:.1f}% ({breadth_data.get('20DMA_count')}/{total})",
            f"{pct_60ma:.1f}% ({breadth_data.get('60DMA_count')}/{total})"
        ]
    })

    # Create stacked bar chart using go.Bar
    fig = go.Figure(data=[
        # Bar 1: The percentage ABOVE the MA (Green)
        go.Bar(
            y=df_bar['Metric'],
            x=df_bar['Percentage'],
            name='Above MA',
            orientation='h',
            marker=dict(color='lightgreen', line=dict(color='darkgreen', width=1)),
            text=df_bar['Text'],
            textposition='inside',
            insidetextanchor='middle',
            hoverinfo='none' # Hide hover info for the segment itself
        ),
        # Bar 2: The percentage BELOW the MA (Gray/Red for context)
        go.Bar(
            y=df_bar['Metric'],
            x=df_bar['Remaining'],
            name='Below MA',
            orientation='h',
            marker=dict(color='lightcoral', line=dict(color='darkred', width=1)),
            hoverinfo='none'
        )
    ])

    fig.update_layout(
        barmode='stack',
        xaxis=dict(range=[0, 100], showgrid=False, zeroline=False, title='股票百分比 (%)'),
        yaxis=dict(autorange="reversed"), # 20 DMA at top, 60 DMA at bottom
        title={
            'text': f"S&P 500 市场宽度 (总股票数: {total})",
            'y':0.95,
            'x':0.5,
            'xanchor': 'center',
            'yanchor': 'top'
        },
        showlegend=False,
        height=600,
        margin=dict(l=20, r=20, t=50, b=20),
        plot_bgcolor='white'
    )
    
    # Remove borders and padding for a cleaner look
    fig.update_traces(marker_line_width=0, opacity=1.0) 
    
    return fig

def create_breadth_timeseries_chart(df_breadth: pd.DataFrame):
    """
    生成显示 20 DMA 和 60 DMA 市场宽度历史的线图。
    """
    
    # 熔化数据以方便 Plotly Express 绘图（将 20DMA 和 60DMA 变成一列）
    df_long = df_breadth[['20DMA_Breadth', '60DMA_Breadth']].reset_index().rename(columns={'index': 'Date'})
    df_long = df_long.melt(
        id_vars=['Date'],
        value_vars=['20DMA_Breadth', '60DMA_Breadth'],
        var_name='Moving_Average',
        value_name='Breadth_Percentage'
    )
    
    # 映射标签
    label_map = {
        '20DMA_Breadth': '高于 20 日均线 (%)',
        '60DMA_Breadth': '高于 60 日均线 (%)'
    }
    df_long['Label'] = df_long['Moving_Average'].map(label_map)

    fig = px.line(
        df_long,
        x='Date',
        y='Breadth_Percentage',
        color='Label',
        title="S&P 500 市场宽度历史趋势",
        labels={'Breadth_Percentage': '股票百分比 (%)', 'Date': '日期', 'Label': '指标'},
        color_discrete_map={
            '高于 20 日均线 (%)': 'darkgreen',
            '高于 60 日均线 (%)': 'orange'
        }
    )

    # 添加 50% 基线（牛市/熊市分界线）
    fig.add_hline(y=50, line_dash="dash", line_color="red", 
                  annotation_text="50% 基线", 
                  annotation_position="bottom right")

    fig.update_layout(
        template="plotly_white",
        yaxis_range=[0, 100],
        hovermode="x unified",
        legend_title_text=''
    )
    
    return fig
