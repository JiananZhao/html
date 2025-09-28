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
        height=200,
        margin=dict(l=20, r=20, t=50, b=20),
        plot_bgcolor='white'
    )
    
    # Remove borders and padding for a cleaner look
    fig.update_traces(marker_line_width=0, opacity=1.0) 
    
    return fig

def create_breadth_timeseries_chart(df_breadth: pd.DataFrame, df_spy: pd.DataFrame = None): # <-- NEW: Add df_spy parameter
    """
    生成显示 20 DMA 和 60 DMA 市场宽度历史的线图，并可选地叠加 SPY 指数价格。
    """
    
    # 熔化数据以方便 Plotly Express 绘图
    df_long = df_breadth[['20DMA_Breadth', '60DMA_Breadth']].reset_index().rename(columns={'index': 'Date'})
    df_long = df_long.melt(
        id_vars=['Date'],
        value_vars=['20DMA_Breadth', '60DMA_Breadth'],
        var_name='Moving_Average',
        value_name='Breadth_Percentage'
    )
    
    label_map = {
        '20DMA_Breadth': '高于 20 日均线 (%)',
        '60DMA_Breadth': '高于 60 日均线 (%)'
    }
    df_long['Label'] = df_long['Moving_Average'].map(label_map)

    # --- 开始创建图表 (使用 go.Figure 而不是 px.line 以便双 Y 轴) ---
    fig = go.Figure()

    # 添加市场宽度数据 (主 Y 轴)
    for label in df_long['Label'].unique():
        df_subset = df_long[df_long['Label'] == label]
        fig.add_trace(
            go.Scatter(
                x=df_subset['Date'],
                y=df_subset['Breadth_Percentage'],
                mode='lines',
                name=label,
                line=dict(
                    color='darkgreen' if '20' in label else 'orange',
                    width=2
                ),
                yaxis='y1' # <-- 指定使用第一个Y轴
            )
        )

    # 添加 50% 基线
    fig.add_hline(y=50, line_dash="dash", line_color="red", 
                  annotation_text="50% 基线", 
                  annotation_position="bottom right",
                  layer="below", # 确保基线在折线下方
                  row="all", col="all", # 适用于所有子图，但这里只有一个主图
                  yaxis="y1" # 适用于第一个Y轴
    )

    # --- NEW: 如果提供了 SPY 数据，则添加 SPY 价格到副 Y 轴 ---
    if df_spy is not None and not df_spy.empty:
        # 将 SPY 数据与市场宽度数据按日期对齐
        # 确保 df_spy 的索引是日期，并且与 df_breadth 的日期范围一致
        df_spy_aligned = df_spy.reindex(df_breadth.index).dropna() # 使用 reindex 来对齐日期

        if not df_spy_aligned.empty:
            fig.add_trace(
                go.Scatter(
                    x=df_spy_aligned.index,
                    y=df_spy_aligned['SPY_Close'],
                    mode='lines',
                    name='SPY 收盘价',
                    line=dict(color='blue', width=1.5, dash='dot'), # 使用虚线或不同样式
                    yaxis='y2' # <-- 指定使用第二个Y轴
                )
            )
        else:
            st.warning("SPY 数据与市场宽度数据日期无法对齐或为空。")

    # --- 更新布局以支持双 Y 轴 ---
    fig.update_layout(
        template="plotly_white",
        title_text="S&P 500 市场宽度历史趋势与 SPY 指数", # 更新图表标题
        xaxis_title="日期",
        yaxis_title="股票百分比 (%)", # 主 Y 轴标题
        hovermode="x unified",
        legend_title_text='',
        height=500,
        
        # 定义主 Y 轴 (y1)
        yaxis=dict(
            range=[0, 100],
            title="股票百分比 (%)",
            showgrid=True,
            zeroline=False,
            side='left'
        ),
        # 定义副 Y 轴 (y2)
        yaxis2=dict(
            title="SPY 收盘价",
            overlaying='y', # 叠加在 'y' (即 y1) 之上
            side='right', # 放在右侧
            showgrid=False, # 不显示网格线以保持清晰
            zeroline=False
        ),
        
        # 范围选择器和滑动条
        xaxis=dict(
            rangeselector=dict(
                buttons=list([
                    dict(count=6, label="6m", step="month", stepmode="backward"),
                    dict(count=1, label="1y", step="year", stepmode="backward"),
                    dict(count=5, label="5y", step="year", stepmode="backward"),
                    dict(step="all")
                ])
            ),
            rangeslider=dict(visible=True, thickness=0.07),
            # 确保默认范围是过去 5 年，且数据足够长
            range=[df_breadth.index[-1] - pd.DateOffset(years=5), df_breadth.index[-1]] if not df_breadth.empty else None
        )
    )
    
    return fig
