# visualization.py

import plotly.express as px
import streamlit as st
import pandas as pd
from data_processing import CUSTOM_X_AXIS_TICKS_LABELS

def create_yield_curve_chart(df_long: pd.DataFrame, most_recent_date: datetime):
    """
    Generates the interactive Plotly yield curve chart.
    
    Args:
        df_long: The long-format DataFrame.
        most_recent_date: The latest date in the dataset.
        
    Returns:
        A Plotly Figure object.
    """
    
    default_frame = str(most_recent_date.date())

    # Create the interactive animated plot
    fig = px.line(
        df_long,
        x='Maturity_Years',
        y='Yield',
        animation_frame=df_long['Date'].astype(str),
        animation_group='Date',
        hover_data={'Maturity_Label': True, 'Yield': ':.2f'},
        markers=True,
        labels={
            "Maturity_Years": "Time to Maturity (Years)",
            "Yield": "Yield (%)",
            "animation_frame": "Date"
        },
        title="U.S. Treasury Yield Curve Animation"
    )

    # Calculate Y-axis range dynamically
    min_yield = df_long['Yield'].min()
    max_yield = df_long['Yield'].max()
    y_range = [min_yield * 0.8, max_yield * 1.05]
    
    # Customize the layout
    fig.update_layout(
        xaxis_title="Time to Maturity (Years)",
        yaxis_title="Yield (%)",
        template="plotly_white",
        yaxis_range=y_range,
        height=600,
        width=600,
        hovermode="x unified",
        
        # --- 自定义 X 轴刻度 ---
        xaxis=dict(
            tickmode='array',
            tickvals=list(CUSTOM_X_AXIS_TICKS_LABELS.values()),
            ticktext=list(CUSTOM_X_AXIS_TICKS_LABELS.keys()),
            range=[-0.1, 31],
        )
    )

    # --- 设置默认显示最新日期曲线 ---
    date_list = sorted(df_long['Date'].unique())
    
    # 找到最新日期在排序列表中的索引
    # 确保 most_recent_date 是 datetime.datetime 或 np.datetime64 类型，与 date_list 元素匹配
    most_recent_dt = pd.to_datetime(most_recent_date) 
    
    # 转换为字符串以便与 date_list 中的 numpy.datetime64 元素进行比较（更安全）
    if most_recent_dt in date_list:
        default_index = date_list.tolist().index(most_recent_dt)
    else:
        # Fallback to the last item if exact match isn't found (shouldn't happen)
        default_index = len(date_list) - 1

    if fig.layout.sliders:
        fig.layout.sliders[0].active = default_index

    return fig
