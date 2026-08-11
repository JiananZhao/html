"""
Market Breadth Visualization Component for Streamlit
Reads pre-calculated daily market breadth from market_breadth.csv
"""
import os
import datetime
import pandas as pd
import plotly.express as px
import streamlit as st

BREADTH_CSV = "market_breadth.csv"

def get_file_updated_time(file_path=BREADTH_CSV):
    if os.path.exists(file_path):
        mtime = os.path.getmtime(file_path)
        return datetime.datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M")
    return datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

@st.cache_data(ttl=3600)
def load_market_breadth_data(file_path=BREADTH_CSV):
    """
    读取并缓存 GitHub Actions 每日预计算的 market_breadth.csv 数据
    """
    if not os.path.exists(file_path) or os.path.getsize(file_path) == 0:
        return None
    try:
        df = pd.read_csv(file_path)
        if df.empty or "date" not in df.columns:
            return None
        df["date"] = pd.to_datetime(df["date"])
        df = df.sort_values("date")
        return df
    except Exception as e:
        print(f"Error loading market breadth CSV: {e}")
        return None

def create_market_breadth_chart(df_breadth: pd.DataFrame = None, y_range=None):
    """
    创建 S&P 500 市场宽度 (% 高于 20MA / 50MA / 200MA) 的 Plotly 折线图
    """
    if df_breadth is None or df_breadth.empty:
        df_breadth = load_market_breadth_data()

    if df_breadth is None or df_breadth.empty:
        return None

    df = df_breadth.copy()
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date")

    cols_to_plot = [c for c in ["pct_above_20ma", "pct_above_50ma", "pct_above_200ma"] if c in df.columns]
    if not cols_to_plot:
        return None

    labels_map = {
        "pct_above_20ma": "% > 20MA",
        "pct_above_50ma": "% > 50MA",
        "pct_above_200ma": "% > 200MA",
        "date": "Date",
        "value": "Percentage (%)",
        "variable": "MA Period"
    }

    fig = px.line(
        df,
        x="date",
        y=cols_to_plot,
        title="S&P 500 Market Breadth (% of Stocks Above Moving Averages)",
        labels=labels_map,
        template="plotly_white"
    )

    last_date = df["date"].max()
    first_date = df["date"].min()
    default_start = max(first_date, last_date - pd.DateOffset(years=3))

    fig.update_layout(
        hovermode="x unified",
        height=450,
        yaxis_title="Percentage (%)",
        uirevision="market_breadth_chart",
        xaxis=dict(
            rangeselector=dict(
                buttons=list([
                    dict(count=1, label="1m", step="month", stepmode="backward"),
                    dict(count=6, label="6m", step="month", stepmode="backward"),
                    dict(count=1, label="1y", step="year", stepmode="backward"),
                    dict(count=3, label="3y", step="year", stepmode="backward"),
                    dict(step="all", label="all"),
                ])
            ),
            rangeslider=dict(visible=True, thickness=0.07),
            range=[default_start, last_date],
        ),
    )

    # 标示超买 (70%) 与超卖 (30%) 区域界限
    fig.add_hline(
        y=70,
        line_dash="dash",
        line_color="rgba(239, 68, 68, 0.6)",
        annotation_text="Overbought (70%)",
        annotation_position="top left"
    )
    fig.add_hline(
        y=30,
        line_dash="dash",
        line_color="rgba(34, 197, 94, 0.6)",
        annotation_text="Oversold (30%)",
        annotation_position="bottom left"
    )

    fig.update_yaxes(fixedrange=False)

    if y_range is not None:
        fig.update_yaxes(range=list(y_range), autorange=False)
    else:
        fig.update_yaxes(autorange=True)

    return fig

def render_market_breadth_ui():
    """
    在 Streamlit 中直接渲染市场宽度模块的 UI 组件（含具体到分钟的数据更新时间）
    """
    st.subheader("📊 S&P 500 市场宽度分析 (Market Breadth)")
    df = load_market_breadth_data()
    
    if df is None or df.empty:
        st.info("尚无市场宽度数据，GitHub Actions 会在美股收盘后自动生成并更新 market_breadth.csv。")
        return

    latest_row = df.iloc[-1]
    latest_date = pd.to_datetime(latest_row['date']).strftime('%Y-%m-%d')
    file_mtime = get_file_updated_time(BREADTH_CSV)
    
    st.caption(f"🕒 数据刷新时间: **{file_mtime}** | 最新交易日: **{latest_date}**")

    # 顶部指标卡片
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("最新交易日", latest_date)
    with col2:
        val20 = latest_row.get('pct_above_20ma', 0)
        st.metric("% > 20MA", f"{val20:.1f}%")
    with col3:
        val50 = latest_row.get('pct_above_50ma', 0)
        st.metric("% > 50MA", f"{val50:.1f}%")
    with col4:
        val200 = latest_row.get('pct_above_200ma', 0)
        st.metric("% > 200MA", f"{val200:.1f}%")

    # 折线图渲染
    fig = create_market_breadth_chart(df)
    if fig:
        st.plotly_chart(fig, use_container_width=True)
