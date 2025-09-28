# visualization.py

import plotly.express as px
import streamlit as st
import pandas as pd
from datetime import datetime # <--- 关键修改：导入 datetime 类
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
    
    # ... (其余的代码逻辑保持不变)
    default_frame = str(most_recent_date.date())

    # Create the interactive animated plot
    fig = px.line(
        # ...
    )

    # Customize the layout
    fig.update_layout(
        # ...
    )

    # visualization.py
    # ... (设置滑块的代码)
    date_list = sorted(df_long['Date'].unique())
    most_recent_dt = pd.to_datetime(most_recent_date) 
    
    # 修正：移除 .tolist()，因为 date_list 已经是 Python 列表了
    if most_recent_dt in date_list:
        default_index = date_list.index(most_recent_dt) # <--- 关键修改
    else:
        # Fallback to the last item if exact match isn't found
        default_index = len(date_list) - 1

    if fig.layout.sliders:
        fig.layout.sliders[0].active = default_index

    return fig
