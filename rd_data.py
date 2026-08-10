import os
import datetime
import requests
import pandas as pd
import numpy as np
import streamlit as st

# ------------------------------------------------------------------
# 1. 图表渲染组件导入
# ------------------------------------------------------------------
from visualization import (
    create_treasury_chart,
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
# 3. FRED 宏观经济数据获取辅助函数
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
# 4. Streamlit 主页面应用渲染
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
