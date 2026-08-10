import os
import datetime
import requests
import pandas as pd
import numpy as np
import plotly.express as px
import streamlit as st

# ------------------------------------------------------------------
# 1. 图表渲染组件导入 (仅导入 visualization.py 中实际存在的函数)
# ------------------------------------------------------------------
from visualization import (
    create_unemployment_chart,
    create_credit_spread_chart,
    create_fed_balance_sheet_chart,
    create_gold_oil_ratio_chart,
)

# ------------------------------------------------------------------
# 2. 市场数据与市场宽度组件导入
# ------------------------------------------------------------------
from market_analysis import (
    get_sp500_stock_data,
)

from market_breadth_viz import (
    render_market_breadth_ui,
    create_market_breadth_chart,
    load_market_breadth_data,
)

# ------------------------------------------------------------------
# 3. 本地定义的国债收益率图表生成函数 (解决 create_treasury_chart ImportError)
# ------------------------------------------------------------------
def create_treasury_chart(df_treasury: pd.DataFrame):
    if df_treasury is None or df_treasury.empty:
        return None
    df = df_treasury.copy()
    df["Date"] = pd.to_datetime(df["Date"])
    rate_cols = [
        c for c in ["1 Mo", "3 Mo", "6 Mo", "1 Yr", "2 Yr", "3 Yr", "5 Yr", "7 Yr", "10 Yr", "20 Yr", "30 Yr"]
        if c in df.columns
    ]
    if not rate_cols:
        return None

    fig = px.line(
        df,
        x="Date",
        y=rate_cols,
        title="US Treasury Yield Curve (国债收益率曲线)",
        labels={"value": "Yield (%)", "variable": "Maturity", "Date": "Date"},
        template="plotly_white",
    )
    
    last_date = df["Date"].max()
    default_start = max(df["Date"].min(), last_date - pd.DateOffset(years=3))

    fig.update_layout(
        hovermode="x unified",
        height=450,
        yaxis_title="Yield (%)",
        uirevision="treasury_chart",
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
    return fig

# ------------------------------------------------------------------
# 4. FRED 宏观经济数据获取辅助函数
# ------------------------------------------------------------------
def _get_fred_api_key():
    try:
        return st.secrets["FRED_API_KEY"]
    except Exception:
        return os.getenv("FRED_API_KEY", "")

@st.cache_data(ttl=60 * 60 * 6)
def _fetch_fred_series_observations(series_id, value_col, observation_start="2000-01-01"):
    fred_api_key = _get_fred_api_key()
    if not fred_api_key:
        return pd.DataFrame()

    url = "https://api.stlouisfed.org/fred/series/observations"
    params = {
        "series_id": series_id,
        "api_key": fred_api_key,
        "file_type": "json",
        "observation_start": observation_start,
        "sort_order": "asc",
    }

    try:
        response = requests.get(url, params=params, timeout=15)
        response.raise_for_status()
        data = response.json().get("observations", [])

        if not data:
            return pd.DataFrame()

        df = pd.DataFrame(data)
        df = df[df["value"] != "."].copy()

        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        df[value_col] = pd.to_numeric(df["value"], errors="coerce")
        df = df.dropna(subset=["date", value_col])

        return df[["date", value_col]].reset_index(drop=True)

    except Exception as e:
        print(f"Error fetching FRED series {series_id}: {e}")
        return pd.DataFrame()

@st.cache_data(ttl=60 * 60 * 6)
def get_unemployment_data():
    return _fetch_fred_series_observations("UNRATE", "Unemployment_Rate", "2000-01-01")

@st.cache_data(ttl=60 * 60 * 6)
def get_highyield_data():
    return _fetch_fred_series_observations("BAMLH0A0HYM2", "Value", "2000-01-01")

@st.cache_data(ttl=60 * 60 * 6)
def get_fed_balance_sheet_data():
    df = _fetch_fred_series_observations("WALCL", "value", "2008-01-01")
    if not df.empty:
        df["balance_sheet_tn"] = df["value"] / 1_000_000
        return df[["date", "balance_sheet_tn"]].reset_index(drop=True)
    return pd.DataFrame()

# ------------------------------------------------------------------
# 5. Streamlit 主页面应用渲染
# ------------------------------------------------------------------
st.set_page_config(page_title="Financial Data Dashboard", layout="wide")

st.title("📈 宏观经济与市场宽度量化看板")

# 侧边栏及提示
FRED_API_KEY = _get_fred_api_key()
if not FRED_API_KEY:
    st.sidebar.warning("⚠️ 未检测到 FRED_API_KEY，宏观数据功能受限。")

# --- 1. S&P 500 市场宽度渲染 ---
st.markdown("---")
render_market_breadth_ui()

# --- 2. 宏观数据渲染 (国债收益率/失业率/美联储资产负债表) ---
st.markdown("---")
st.header("📊 宏观经济与美债收益率追踪")

# 尝试获取美债数据
treasury_csv = "daily-treasury-rates.csv"
if os.path.exists(treasury_csv) and os.path.getsize(treasury_csv) > 10:
    try:
        df_treasury = pd.read_csv(treasury_csv)
        if "Date" in df_treasury.columns:
            df_treasury["Date"] = pd.to_datetime(df_treasury["Date"])
            df_treasury = df_treasury.sort_values("Date")
            fig_treasury = create_treasury_chart(df_treasury)
            if fig_treasury:
                st.plotly_chart(fig_treasury, use_container_width=True)
    except Exception as e:
        st.warning(f"读取国债收益率文件异常: {e}")

# FRED 宏观图表（失业率与资产负债表）
col1, col2 = st.columns(2)

with col1:
    df_unrate = get_unemployment_data()
    if not df_unrate.empty:
        st.subheader("美国失业率 (UNRATE)")
        fig_unrate = create_unemployment_chart(df_unrate)
        if fig_unrate:
            st.plotly_chart(fig_unrate, use_container_width=True)
    else:
        st.info("失业率数据无可用缓存或加载中。")

with col2:
    df_fed_bs = get_fed_balance_sheet_data()
    if not df_fed_bs.empty:
        st.subheader("美联储资产负债表 (WALCL)")
        fig_fed_bs = create_fed_balance_sheet_chart(df_fed_bs)
        if fig_fed_bs:
            st.plotly_chart(fig_fed_bs, use_container_width=True)
    else:
        st.info("美联储资产负债表数据无可用缓存或加载中。")
