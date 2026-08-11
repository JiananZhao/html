import os
import datetime
import requests
import pandas as pd
import numpy as np
import streamlit as st
from zoneinfo import ZoneInfo

# ------------------------------------------------------------------
# 1. 国债收益率数据转换与原版收益率曲线图表渲染
# ------------------------------------------------------------------
from data_processing import load_and_transform_data

from visualization import (
    create_treasury_chart,
    create_unemployment_chart,
    create_credit_spread_chart,
    create_fed_balance_sheet_chart,
    create_gold_oil_ratio_chart,
)

# ------------------------------------------------------------------
# 2. 市场分析与新版市场宽度 UI 组件
# ------------------------------------------------------------------
from market_analysis import (
    get_sp500_symbols,
    get_sp500_stock_data,
)

from market_breadth_viz import (
    render_market_breadth_ui,
    create_market_breadth_chart,
    load_market_breadth_data,
)

# ------------------------------------------------------------------
# 3. 辅助函数：严格转换为美东时间 (US/Eastern - America/New_York, EDT)
# ------------------------------------------------------------------
def get_eastern_now():
    try:
        return datetime.datetime.now(ZoneInfo("America/New_York"))
    except Exception:
        tz_offset = datetime.timezone(datetime.timedelta(hours=-4))
        return datetime.datetime.now(tz_offset)

def get_file_updated_time_eastern(file_path):
    if os.path.exists(file_path):
        mtime = os.path.getmtime(file_path)
        try:
            dt = datetime.datetime.fromtimestamp(mtime, tz=datetime.timezone.utc).astimezone(ZoneInfo("America/New_York"))
            return dt.strftime("%Y-%m-%d %H:%M EDT")
        except Exception:
            pass
    return get_eastern_now().strftime("%Y-%m-%d %H:%M EDT")

def get_current_time_str_eastern():
    return get_eastern_now().strftime("%Y-%m-%d %H:%M EDT")

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

@st.cache_data(ttl=60 * 60 * 6)
def get_gold_oil_ratio_data():
    df_oil = _fetch_fred_series_observations("DCOILWTICO", "oil_usd_per_bbl", "1990-01-01")
    if df_oil.empty:
        return pd.DataFrame()
    
    try:
        import yfinance as yf
        gold_df = yf.download("GC=F", start="1990-01-01", progress=False)["Close"]
        if not gold_df.empty:
            gold_df = gold_df.reset_index()
            gold_df.columns = ["date", "gold_usd_per_oz"]
            gold_df["date"] = pd.to_datetime(gold_df["date"])
            df_merged = pd.merge(gold_df, df_oil, on="date", how="inner").sort_values("date")
            df_merged["gold_oil_ratio"] = df_merged["gold_usd_per_oz"] / df_merged["oil_usd_per_bbl"]
            return df_merged.dropna().reset_index(drop=True)
    except Exception:
        pass
    return pd.DataFrame()

# ------------------------------------------------------------------
# 4. Streamlit 主页面应用渲染
# ------------------------------------------------------------------
st.set_page_config(page_title="Financial Data Dashboard", layout="wide")

st.title("📈 宏观经济与市场宽度量化看板")

# 侧边栏
FRED_API_KEY = _get_fred_api_key()
if not FRED_API_KEY:
    st.sidebar.warning("⚠️ 未检测到 FRED_API_KEY，部分宏观功能受限。")

# --- 1. 原版国债收益率曲线图表 ---
st.markdown("---")
st.header("📊 美债收益率曲线 (Yield Curve)")

treasury_csv = "daily-treasury-rates.csv"
treasury_updated = get_file_updated_time_eastern(treasury_csv)

with st.spinner("正在获取并转换国债收益率数据..."):
    df_long = load_and_transform_data()

if df_long is not None and not df_long.empty:
    latest_date = df_long['Date'].max().strftime('%Y-%m-%d')
    st.caption(f"🕒 数据刷新时间 (美东时间): **{treasury_updated}** | 最新数据交易日: **{latest_date}**")

    fig_treasury = create_treasury_chart(df_long)
    if fig_treasury:
        st.plotly_chart(fig_treasury, use_container_width=True)
    
    st.sidebar.header("国债数据信息")
    st.sidebar.markdown(f"刷新时间 (美东): **{treasury_updated}**")
    st.sidebar.markdown(f"最新日期: **{latest_date}**")
    st.sidebar.markdown(f"总数据点: **{len(df_long)//12}**")
else:
    st.error("未能加载国债收益率数据，请检查 daily-treasury-rates.csv 文件。")

# --- 2. S&P 500 市场宽度分析模块 ---
st.markdown("---")
render_market_breadth_ui()

# --- 3. FRED 宏观经济指标与流动性追踪 (含可调节 Y 轴范围控制) ---
st.markdown("---")
st.header("📊 宏观指标与流动性追踪")

current_et_str = get_current_time_str_eastern()

col1, col2 = st.columns(2)

with col1:
    df_unrate = get_unemployment_data()
    if not df_unrate.empty:
        latest_unrate_date = pd.to_datetime(df_unrate['date'].iloc[-1]).strftime('%Y-%m-%d') if 'date' in df_unrate.columns else "最新"
        st.subheader("美国失业率 (UNRATE)")
        st.caption(f"🕒 数据刷新时间 (美东时间): **{current_et_str}** | 最新公布日期: **{latest_unrate_date}**")
        
        # 可调节 Y 轴 UI 控制
        val_unrate = df_unrate['Unemployment_Rate'] if 'Unemployment_Rate' in df_unrate.columns else df_unrate.iloc[:, 1]
        u_min = float(val_unrate.dropna().min())
        u_max = float(val_unrate.dropna().max())
        
        unrate_y_range = None
        if st.checkbox("手动设置失业率 Y 轴范围", key="unrate_manual_y"):
            unrate_y_range = st.slider(
                "失业率 Y 轴范围 (%)",
                min_value=round(max(0.0, u_min - 2.0), 1),
                max_value=round(u_max + 3.0, 1),
                value=(round(u_min, 1), round(u_max, 1)),
                step=0.1,
                key="unrate_y_slider"
            )

        fig_unrate = create_unemployment_chart(df_unrate, y_range=unrate_y_range)
        if fig_unrate:
            st.plotly_chart(fig_unrate, use_container_width=True)
    else:
        st.info("失业率数据加载中或不可用。")

with col2:
    df_fed_bs = get_fed_balance_sheet_data()
    if not df_fed_bs.empty:
        latest_fed_date = pd.to_datetime(df_fed_bs['date'].iloc[-1]).strftime('%Y-%m-%d') if 'date' in df_fed_bs.columns else "最新"
        st.subheader("美联储资产负债表 (WALCL)")
        st.caption(f"🕒 数据刷新时间 (美东时间): **{current_et_str}** | 最新公布日期: **{latest_fed_date}**")
        
        # 可调节 Y 轴 UI 控制
        val_fed = df_fed_bs['balance_sheet_tn'] if 'balance_sheet_tn' in df_fed_bs.columns else df_fed_bs.iloc[:, 1]
        f_min = float(val_fed.dropna().min())
        f_max = float(val_fed.dropna().max())
        
        fed_y_range = None
        if st.checkbox("手动设置资产负债表 Y 轴范围", key="fed_manual_y"):
            fed_y_range = st.slider(
                "资产负债表 Y 轴范围 (万亿美元)",
                min_value=round(max(0.0, f_min - 1.0), 2),
                max_value=round(f_max + 1.0, 2),
                value=(round(f_min, 2), round(f_max, 2)),
                step=0.05,
                key="fed_y_slider"
            )

        fig_fed_bs = create_fed_balance_sheet_chart(df_fed_bs, y_range=fed_y_range)
        if fig_fed_bs:
            st.plotly_chart(fig_fed_bs, use_container_width=True)
    else:
        st.info("美联储资产负债表数据加载中或不可用。")

col3, col4 = st.columns(2)

with col3:
    df_highyield = get_highyield_data()
    if not df_highyield.empty:
        latest_hy_date = pd.to_datetime(df_highyield['date'].iloc[-1]).strftime('%Y-%m-%d') if 'date' in df_highyield.columns else "最新"
        st.subheader("高收益债信用利差 (US High Yield Credit Spread)")
        st.caption(f"🕒 数据刷新时间 (美东时间): **{current_et_str}** | 最新公布日期: **{latest_hy_date}**")
        
        # 可调节 Y 轴 UI 控制
        val_hy = df_highyield['Value'] if 'Value' in df_highyield.columns else df_highyield.iloc[:, 1]
        hy_min = float(val_hy.dropna().min())
        hy_max = float(val_hy.dropna().max())
        
        credit_y_range = None
        if st.checkbox("手动设置信用利差 Y 轴范围", key="credit_manual_y"):
            credit_y_range = st.slider(
                "信用利差 Y 轴范围 (%)",
                min_value=round(max(0.0, hy_min - 1.0), 1),
                max_value=round(hy_max + 2.0, 1),
                value=(round(hy_min, 1), round(hy_max, 1)),
                step=0.1,
                key="credit_y_slider"
            )

        fig_credit = create_credit_spread_chart(df_highyield, y_range=credit_y_range)
        if fig_credit:
            st.plotly_chart(fig_credit, use_container_width=True)
    else:
        st.info("高收益债信用利差数据加载中或不可用。")

with col4:
    df_gold_oil = get_gold_oil_ratio_data()
    if not df_gold_oil.empty:
        latest_go_date = pd.to_datetime(df_gold_oil['date'].iloc[-1]).strftime('%Y-%m-%d') if 'date' in df_gold_oil.columns else "最新"
        st.subheader("Gold / Oil Ratio (金油比)")
        st.caption(f"🕒 数据刷新时间 (美东时间): **{current_et_str}** | 最新公布日期: **{latest_go_date}**")
        
        # 可调节 Y 轴 UI 控制
        val_go = df_gold_oil['gold_oil_ratio'] if 'gold_oil_ratio' in df_gold_oil.columns else df_gold_oil.iloc[:, -1]
        go_min = float(val_go.dropna().min())
        go_max = float(val_go.dropna().max())
        
        go_y_range = None
        if st.checkbox("手动设置金油比 Y 轴范围", key="go_manual_y"):
            go_y_range = st.slider(
                "金油比 Y 轴范围",
                min_value=round(max(0.0, go_min - 5.0), 1),
                max_value=round(go_max + 10.0, 1),
                value=(round(go_min, 1), round(go_max, 1)),
                step=0.5,
                key="go_y_slider"
            )

        fig_gold_oil = create_gold_oil_ratio_chart(df_gold_oil, y_range=go_y_range)
        if fig_gold_oil:
            st.plotly_chart(fig_gold_oil, use_container_width=True)
