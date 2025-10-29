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
    
    # 1. Prepare data for Plotly animation
    # Convert Date column to string (e.g., '2025-09-26') for animation frame titles
    df_long['Date_str'] = df_long['Date'].astype(str).str[:10] # Ensure only date part is used

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

    # 2. Calculate Y-axis range safely and dynamically
    min_yield = df_long['Yield'].min()
    max_yield = df_long['Yield'].max()
    
    y_floor = max(-0.5, min_yield - 0.5) 
    y_ceiling = max_yield * 1.05
    y_range = [y_floor, y_ceiling] 

    # 3. Customize the layout
    fig.update_layout(
        xaxis_title="Time to Maturity (Years)",
        yaxis_title="Yield (%)",
        template="plotly_white",
        yaxis_range=y_range, 
        height=400,
        width=600,
        hovermode="x unified",
        
        # Custom X-axis ticks
        xaxis=dict(
            tickmode='array',
            # Assuming CUSTOM_X_AXIS_TICKS_LABELS is correctly imported/defined
            tickvals=list(CUSTOM_X_AXIS_TICKS_LABELS.values()), 
            ticktext=list(CUSTOM_X_AXIS_TICKS_LABELS.keys()),
            range=[-1, 31],
            type='linear' 
        )
    )

    # 4. CRITICAL FIX: Set default frame to the most recent date

    # Target date string in the format matching the animation frame titles
    latest_date_str = pd.to_datetime(most_recent_date).strftime('%Y-%m-%d')
    
    # Check if the figure has frames (i.e., if animation was successfully created)
    if fig.frames and fig.layout.sliders:
        
        # Find the index of the frame that matches the latest date string
        frame_titles = [f.name for f in fig.frames]
        
        try:
            default_index = frame_titles.index(latest_date_str)
        except ValueError:
            # Fallback: if the exact date string isn't found, use the last frame
            default_index = len(fig.frames) - 1
        
        # A. Update the slider's active position (sets the animation state)
        fig.layout.sliders[0].active = default_index
        
        # B. Update the initial data trace (sets the static plot view)
        # Without this, the plot displays the first row of df_long.
        # We replace the initial data with the data from the default frame.
        if fig.frames[default_index].data:
            fig.data[0].y = fig.frames[default_index].data[0].y
            fig.data[0].x = fig.frames[default_index].data[0].x
        
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
        height=200,
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

    # 添加 20% 基线
    fig.add_hline(y=20, line_dash="dash", line_color="red", 
                  annotation_text="20% 基线", 
                  annotation_position="bottom right")
                  
    # --- 关键修改 1: 增加 Range Slider 和 Selector ---
    fig.update_xaxes(
        # 激活范围选择器 (Range Selector) 按钮
        rangeselector=dict(
            buttons=list([
                dict(count=1, label="1m", step="month", stepmode="backward"),
                dict(count=6, label="6m", step="month", stepmode="backward"),
                dict(count=1, label="1y", step="year", stepmode="backward"),
                dict(count=5, label="5y", step="year", stepmode="backward"),
                dict(step="all")
            ])
        ),
        # 激活范围滑动条 (Range Slider)
        rangeslider=dict(visible=True, thickness=0.07), # thickness 增加滑动条的可见性
        # 设置默认视图范围为过去 5 年 (确保数据够长)
        range=[df_breadth.index[-1] - pd.DateOffset(years=5), df_breadth.index[-1]]
    )

    # --- 关键修改 2: 调整布局高度/宽度，适应更长的X轴 ---
    fig.update_layout(
        template="plotly_white",
        yaxis_range=[0, 100],
        hovermode="x unified",
        legend_title_text='',
        height=500,  # 适当增加高度
    )
    
    return fig

def create_unemployment_chart(df_unrate: pd.DataFrame):
    """
    生成美国失业率历史趋势图表。
    """
    if df_unrate is None or df_unrate.empty:
        return None

    # 创建线图
    fig = px.line(
        df_unrate,
        x=df_unrate.index,
        y='Unemployment_Rate',
        title='UNRATE',
        labels={'Unemployment_Rate': '失业率 (%)'},
        template="plotly_white",
        line_shape='spline' # 平滑曲线
    )

    # 添加历史平均值 (可选)
    avg_rate = df_unrate['Unemployment_Rate'].mean()
    fig.add_hline(
        y=avg_rate, 
        line_dash="dot", 
        line_color="gray", 
        annotation_text=f"历史平均值 ({avg_rate:.1f}%)", 
        annotation_position="bottom left",
    )

    # 范围选择器和滑动条
    fig.update_layout(
        xaxis=dict(
            rangeselector=dict(
                buttons=list([
                    dict(count=1, label="1y", step="year", stepmode="backward"),
                    dict(count=5, label="5y", step="year", stepmode="backward"),
                    dict(step="all")
                ])
            ),
            rangeslider=dict(visible=True, thickness=0.07)
        ),
        hovermode="x unified",
        height=550, 
        yaxis_title="失业率 (%)",
        yaxis_range=[3.0, df_unrate['Unemployment_Rate'].max() * 0.6] # 动态Y轴范围 yaxis_range=[df_unrate['Unemployment_Rate'].min() * 0.8, df_unrate['Unemployment_Rate'].max() * 0.4]
    )
    
    return fig

def create_credit_spread_chart(df_data):
    """创建信用利差的 Plotly 交互式线图"""
    if df_data.empty:
        return None

    # 列名必须与 load_fred_data 返回的 DataFrame 匹配
    df_data.columns = ['Option-Adjusted Spread (%)']
    
    fig = px.line(
        df_data,
        x=df_data.index,
        y='Option-Adjusted Spread (%)',
        title='美高收益债信用利差 (High Yield Spread)',
        labels={'x': '日期', 'Option-Adjusted Spread (%)': '利差 (%)'},
    )
    # 范围选择器和滑动条
    fig.update_layout(
        xaxis=dict(
            rangeselector=dict(
                buttons=list([
                    dict(count=3, label="3m", step="month", stepmode="backward"),
                    dict(count=1, label="1y", step="year", stepmode="backward"),
                    dict(count=5, label="5y", step="year", stepmode="backward"),
                    dict(step="all")
                ])
            ),
            rangeslider=dict(visible=True, thickness=0.07)
        ),
        yaxis=dict(
            title="期权调整利差 (%)",
            autorange=True,  # 确保 Y 轴在 X 轴范围改变时自动重新计算并缩放
            fixedrange=False, # 确保 Y 轴可以缩放（默认为 False，但明确写出更保险）
            rangeslider=dict(visible=True, thickness=0.07)
        ),
        hovermode="x unified",
        height=550,
        template="plotly_white"
    )
    fig.update_yaxes(autorange=True)
    
    return fig
