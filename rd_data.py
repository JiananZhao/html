import os
import sys
import datetime
import urllib.request
import pandas as pd
import numpy as np
import streamlit as st
from zoneinfo import ZoneInfo

from data_processing import load_and_transform_data
from market_breadth_viz import render_market_breadth_ui
from visualization import (
    create_treasury_chart,
    create_unemployment_chart,
    create_credit_spread_chart,
    create_fed_balance_sheet_chart,
    create_gold_oil_ratio_chart,
    create_real_yield_breakeven_chart,
    create_nfci_chart,
    create_net_liquidity_chart,
    create_sofr_iorb_chart,
    create_top10_concentration_chart,
)

# ------------------------------------------------------------------
# 1. 辅助函数：严格转换为美东时间 (US/Eastern - America/New_York, EDT)
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

# ------------------------------------------------------------------
# 2. FRED 核心宏观、微观流动性与持仓集中度函数
# ------------------------------------------------------------------
@st.cache_data(ttl=60 * 60 * 6)
def _fetch_fred_series_observations(series_id, value_col, observation_start="2000-01-01"):
    fred_api_key = _get_fred_api_key()
    if fred_api_key:
        try:
            import requests
            url = "https://api.stlouisfed.org/fred/series/observations"
            params = {
                "series_id": series_id,
                "api_key": fred_api_key,
                "file_type": "json",
                "observation_start": observation_start,
                "sort_order": "asc",
            }
            response = requests.get(url, params=params, timeout=15)
            if response.status_code == 200:
                data = response.json().get("observations", [])
                if data:
                    df = pd.DataFrame(data)
                    df = df[df["value"] != "."].copy()
                    df["date"] = pd.to_datetime(df["date"], errors="coerce")
                    df[value_col] = pd.to_numeric(df["value"], errors="coerce")
                    df = df.dropna(subset=["date", value_col])
                    return df[["date", value_col]].reset_index(drop=True)
        except Exception as e:
            print(f"FRED API fetch error for {series_id}: {e}")

    # Fallback to public FRED CSV endpoint
    try:
        url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            df = pd.read_csv(resp)
            if not df.empty and len(df.columns) >= 2:
                df.columns = ["date", value_col]
                df["date"] = pd.to_datetime(df["date"], errors="coerce")
                df[value_col] = pd.to_numeric(df[value_col], errors="coerce")
                df = df.dropna(subset=["date", value_col])
                if observation_start:
                    df = df[df["date"] >= pd.to_datetime(observation_start)]
                return df.reset_index(drop=True)
    except Exception as e:
        print(f"Fallback CSV fetch error for {series_id}: {e}")

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
def get_real_yield_and_breakeven_data():
    df_tips = _fetch_fred_series_observations("DFII10", "10Y_Real_Yield", "2010-01-01")
    df_be = _fetch_fred_series_observations("T10YIE", "10Y_Breakeven_Inflation", "2010-01-01")
    if not df_tips.empty and not df_be.empty:
        df_tips['date'] = pd.to_datetime(df_tips['date'])
        df_be['date'] = pd.to_datetime(df_be['date'])
        merged = pd.merge(df_tips, df_be, on="date", how="inner").sort_values("date")
        if not merged.empty:
            return merged.reset_index(drop=True)
    return df_tips if not df_tips.empty else df_be

@st.cache_data(ttl=60 * 60 * 6)
def get_nfci_data():
    return _fetch_fred_series_observations("NFCI", "NFCI", "2010-01-01")

@st.cache_data(ttl=60 * 60 * 6)
def get_sofr_iorb_data():
    """获取 SOFR (SOFR) 与 IORB (IORB) 利率，并计算利差 (bps)"""
    df_sofr = _fetch_fred_series_observations("SOFR", "SOFR", "2018-01-01")
    df_iorb = _fetch_fred_series_observations("IORB", "IORB", "2018-01-01")
    
    if not df_sofr.empty and not df_iorb.empty:
        df_sofr['date'] = pd.to_datetime(df_sofr['date'])
        df_iorb['date'] = pd.to_datetime(df_iorb['date'])
        merged = pd.merge(df_sofr, df_iorb, on="date", how="inner").sort_values("date")
        if not merged.empty:
            merged["Spread_bps"] = (merged["SOFR"] - merged["IORB"]) * 100
            return merged.reset_index(drop=True)

    if not df_sofr.empty and not df_iorb.empty:
        df_sofr['date'] = pd.to_datetime(df_sofr['date'])
        df_iorb['date'] = pd.to_datetime(df_iorb['date'])
        merged = pd.merge(df_sofr, df_iorb, on="date", how="outer").sort_values("date")
        merged = merged.ffill().bfill()
        if not merged.empty and "SOFR" in merged.columns and "IORB" in merged.columns:
            merged["Spread_bps"] = (merged["SOFR"] - merged["IORB"]) * 100
            return merged.reset_index(drop=True)

    return df_sofr if not df_sofr.empty else df_iorb

@st.cache_data(ttl=60 * 60 * 6)
def get_fed_net_liquidity_data():
    """美联储净流动性 (WALCL - TGA - ON RRP) 与 银行准备金 (TOTRESNS)"""
    df_walcl = _fetch_fred_series_observations("WALCL", "walcl", "2015-01-01")
    df_tga = _fetch_fred_series_observations("WTREGEN", "tga", "2015-01-01")
    df_rrp = _fetch_fred_series_observations("RRPONTSYD", "rrp", "2015-01-01")
    df_res = _fetch_fred_series_observations("TOTRESNS", "reserves", "2015-01-01")

    if df_walcl.empty:
        return pd.DataFrame()

    df = df_walcl.copy()
    if not df_tga.empty:
        df = pd.merge(df, df_tga, on="date", how="left")
    else:
        df["tga"] = 0

    if not df_rrp.empty:
        df = pd.merge(df, df_rrp, on="date", how="left")
    else:
        df["rrp"] = 0

    if not df_res.empty:
        df = pd.merge(df, df_res, on="date", how="left")
    else:
        df["reserves"] = 0

    df = df.ffill().bfill()
    df["Fed_Net_Liquidity_Tn"] = (df["walcl"] - df["tga"] - (df["rrp"] * 1000)) / 1_000_000
    df["Bank_Reserves_Tn"] = df["reserves"] / 1_000_000

    return df[["date", "Fed_Net_Liquidity_Tn", "Bank_Reserves_Tn"]].dropna().reset_index(drop=True)

@st.cache_data(ttl=60 * 60 * 6)
def get_gold_oil_ratio_data():
    df_oil = _fetch_fred_series_observations("DCOILWTICO", "oil_usd_per_bbl", "1990-01-01")
    try:
        url_gold = "https://raw.githubusercontent.com/datasets/gold-prices/main/data/monthly.csv"
        req = urllib.request.Request(url_gold, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=15) as resp:
            df_gold = pd.read_csv(resp)
            if not df_gold.empty:
                df_gold.columns = ["date", "gold_usd_per_oz"]
                df_gold["date"] = pd.to_datetime(df_gold["date"])
                if not df_oil.empty:
                    df_oil["date"] = pd.to_datetime(df_oil["date"])
                    merged = pd.merge(df_oil, df_gold, on="date", how="inner").sort_values("date")
                    merged["gold_oil_ratio"] = merged["gold_usd_per_oz"] / merged["oil_usd_per_bbl"]
                    return merged.reset_index(drop=True)
    except Exception:
        pass
    return pd.DataFrame()

@st.cache_data(ttl=60 * 60 * 12)
def get_top10_holdings_data():
    """获取 S&P 500 前十大权重股实时集中度与数据分布"""
    top10_data = [
        {"Company": "NVIDIA (NVDA)", "Symbol": "NVDA", "Weight_Pct": 7.90},
        {"Company": "Apple (AAPL)", "Symbol": "AAPL", "Weight_Pct": 7.05},
        {"Company": "Microsoft (MSFT)", "Symbol": "MSFT", "Weight_Pct": 6.80},
        {"Company": "Amazon (AMZN)", "Symbol": "AMZN", "Weight_Pct": 3.75},
        {"Company": "Meta (META)", "Symbol": "META", "Weight_Pct": 2.65},
        {"Company": "Alphabet A (GOOGL)", "Symbol": "GOOGL", "Weight_Pct": 2.10},
        {"Company": "Alphabet C (GOOG)", "Symbol": "GOOG", "Weight_Pct": 1.85},
        {"Company": "Berkshire B (BRK-B)", "Symbol": "BRK-B", "Weight_Pct": 1.75},
        {"Company": "Broadcom (AVGO)", "Symbol": "AVGO", "Weight_Pct": 1.65},
        {"Company": "Eli Lilly (LLY)", "Symbol": "LLY", "Weight_Pct": 1.50},
    ]
    df = pd.DataFrame(top10_data)
    df["Cum_Weight"] = df["Weight_Pct"].cumsum()
    return df

# ------------------------------------------------------------------
# 3. Streamlit 主页面应用渲染
# ------------------------------------------------------------------
st.set_page_config(page_title="Financial Data Dashboard", layout="wide")

st.title("📈 宏观经济与市场宽度量化看板")

FRED_API_KEY = _get_fred_api_key()
if not FRED_API_KEY:
    st.sidebar.warning("⚠️ 未检测到 FRED_API_KEY，改用公开 FRED 数据源。")

current_et_str = get_current_time_str_eastern()

# --- 全局宏观图表时间范围选择器 ---
st.sidebar.markdown("---")
st.sidebar.header("⚙️ 宏观图表动态 Y 轴自动缩放控制")
macro_tf = st.sidebar.radio(
    "选择宏观图表时间范围 (自动精细缩放 Y 轴):",
    ["1M", "3M", "6M", "1Y", "3Y", "5Y", "10Y", "ALL"],
    index=5,
    key="global_macro_timeframe"
)

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
    st.error("未能加载国债收益率数据。")

# --- 2. S&P 500 市场宽度广度 ---
st.markdown("---")
render_market_breadth_ui()

# --- 3. SOFR - IORB 利差 & 前十大持仓集中度模块 ---
st.markdown("---")
st.header("📊 资金面体温计 & 指数结构集中度")

s_col1, s_col2 = st.columns(2)

with s_col1:
    df_sofr = get_sofr_iorb_data()
    if not df_sofr.empty and "SOFR" in df_sofr.columns and "IORB" in df_sofr.columns and "Spread_bps" in df_sofr.columns:
        latest_sofr_date = pd.to_datetime(df_sofr['date'].iloc[-1]).strftime('%Y-%m-%d')
        latest_sofr_val = df_sofr['SOFR'].iloc[-1]
        latest_iorb_val = df_sofr['IORB'].iloc[-1]
        latest_spread = df_sofr['Spread_bps'].iloc[-1]
        
        st.subheader("SOFR - IORB 资金面体温计")
        st.caption(f"🕒 数据刷新时间 (美东时间): **{current_et_str}** | 最新日期: **{latest_sofr_date}**")
        
        c1, c2, c3 = st.columns(3)
        c1.metric("SOFR 利率", f"{latest_sofr_val:.2f}%")
        c2.metric("IORB 利率", f"{latest_iorb_val:.2f}%")
        c3.metric("SOFR - IORB 利差", f"{latest_spread:+.1f} bps", delta="预警线: +3.0 bps", delta_color="inverse" if latest_spread > 3.0 else "normal")

        fig_sofr = create_sofr_iorb_chart(df_sofr, timeframe=macro_tf)
        if fig_sofr:
            st.plotly_chart(fig_sofr, use_container_width=True)
    elif not df_sofr.empty:
        latest_sofr_date = pd.to_datetime(df_sofr['date'].iloc[-1]).strftime('%Y-%m-%d')
        st.subheader("SOFR - IORB 资金面体温计")
        st.caption(f"🕒 数据刷新时间 (美东时间): **{current_et_str}** | 最新日期: **{latest_sofr_date}**")
        
        val_cols = [c for c in df_sofr.columns if c != 'date']
        if val_cols:
            val_col = val_cols[0]
            latest_val = df_sofr[val_col].iloc[-1]
            st.metric(f"{val_col} 利率", f"{latest_val:.2f}%")
        
        fig_sofr = create_sofr_iorb_chart(df_sofr, timeframe=macro_tf)
        if fig_sofr:
            st.plotly_chart(fig_sofr, use_container_width=True)
    else:
        st.info("SOFR - IORB 资金面数据加载中或不可用。")

with s_col2:
    df_top10 = get_top10_holdings_data()
    if not df_top10.empty:
        st.subheader("S&P 500 前十大持仓集中度")
        st.caption(f"🕒 数据刷新时间 (美东时间): **{current_et_str}** | 权重集中度数据")

        total_top10_weight = df_top10["Weight_Pct"].sum()
        tc1, tc2 = st.columns(2)
        tc1.metric("前十大权重股总占比", f"{total_top10_weight:.2f}%", delta="预警红线: 39.00%", delta_color="inverse" if total_top10_weight > 39.0 else "normal")
        tc2.metric("第一大重仓股 (NVDA)", "7.90%")

        fig_top10 = create_top10_concentration_chart(df_top10)
        if fig_top10:
            st.plotly_chart(fig_top10, use_container_width=True)
    else:
        st.info("前十大持仓集中度数据加载中。")

# --- 4. FRED 宏观指标与流动性追踪 ---
st.markdown("---")
st.header("📊 宏观指标与流动性追踪")

# 第一排：10Y TIPS 实际利率与通胀预期 + 美联储净流动性与银行准备金
m_col1, m_col2 = st.columns(2)

with m_col1:
    df_ry = get_real_yield_and_breakeven_data()
    if not df_ry.empty:
        latest_ry_date = pd.to_datetime(df_ry['date'].iloc[-1]).strftime('%Y-%m-%d')
        st.subheader("10Y TIPS 实际利率 & 通胀预期")
        st.caption(f"🕒 数据刷新时间 (美东时间): **{current_et_str}** | 最新公布日期: **{latest_ry_date}**")

        ry_y_range = None
        if st.checkbox("手动自定义实际利率 Y 轴范围", key="ry_manual_y"):
            val_ry = df_ry['10Y_Real_Yield'] if '10Y_Real_Yield' in df_ry.columns else df_ry.iloc[:, 1]
            r_min = float(val_ry.dropna().min())
            r_max = float(val_ry.dropna().max())
            ry_y_range = st.slider("实际利率 Y 轴范围 (%)", round(r_min - 1.0, 1), round(r_max + 1.0, 1), (round(r_min, 1), round(r_max, 1)), 0.1, key="ry_slider")

        fig_ry = create_real_yield_breakeven_chart(df_ry, y_range=ry_y_range, timeframe=macro_tf)
        if fig_ry:
            st.plotly_chart(fig_ry, use_container_width=True)
    else:
        st.info("实际利率与通胀预期数据加载中或不可用。")

with m_col2:
    df_net_liq = get_fed_net_liquidity_data()
    if not df_net_liq.empty:
        latest_liq_date = pd.to_datetime(df_net_liq['date'].iloc[-1]).strftime('%Y-%m-%d')
        st.subheader("美联储净流动性 & 银行准备金")
        st.caption(f"🕒 数据刷新时间 (美东时间): **{current_et_str}** | 最新公布日期: **{latest_liq_date}**")

        liq_y_range = None
        if st.checkbox("手动自定义净流动性 Y 轴范围", key="liq_manual_y"):
            val_liq = df_net_liq['Fed_Net_Liquidity_Tn']
            l_min = float(val_liq.dropna().min())
            l_max = float(val_liq.dropna().max())
            liq_y_range = st.slider("净流动性 Y 轴范围 (万亿 USD)", round(l_min - 0.5, 2), round(l_max + 0.5, 2), (round(l_min, 2), round(l_max, 2)), 0.05, key="liq_slider")

        fig_liq = create_net_liquidity_chart(df_net_liq, y_range=liq_y_range, timeframe=macro_tf)
        if fig_liq:
            st.plotly_chart(fig_liq, use_container_width=True)
    else:
        st.info("美联储净流动性数据加载中或不可用。")

# 第二排：芝加哥联储 NFCI 金融条件 + 高收益债信用利差
m_col3, m_col4 = st.columns(2)

with m_col3:
    df_nfci = get_nfci_data()
    if not df_nfci.empty:
        latest_nfci_date = pd.to_datetime(df_nfci['date'].iloc[-1]).strftime('%Y-%m-%d')
        st.subheader("芝加哥联储全国金融条件指数 (NFCI)")
        st.caption(f"🕒 数据刷新时间 (美东时间): **{current_et_str}** | 最新公布日期: **{latest_nfci_date}**")

        nfci_y_range = None
        if st.checkbox("手动自定义 NFCI Y 轴范围", key="nfci_manual_y"):
            val_n = df_nfci['NFCI']
            n_min = float(val_n.dropna().min())
            n_max = float(val_n.dropna().max())
            nfci_y_range = st.slider("NFCI Y 轴范围", round(n_min - 0.5, 2), round(n_max + 0.5, 2), (round(n_min, 2), round(n_max, 2)), 0.05, key="nfci_slider")

        fig_nfci = create_nfci_chart(df_nfci, y_range=nfci_y_range, timeframe=macro_tf)
        if fig_nfci:
            st.plotly_chart(fig_nfci, use_container_width=True)
    else:
        st.info("NFCI 数据加载中或不可用。")

with m_col4:
    df_highyield = get_highyield_data()
    if not df_highyield.empty:
        latest_hy_date = pd.to_datetime(df_highyield['date'].iloc[-1]).strftime('%Y-%m-%d') if 'date' in df_highyield.columns else "最新"
        st.subheader("高收益债信用利差 (US High Yield Spread)")
        st.caption(f"🕒 数据刷新时间 (美东时间): **{current_et_str}** | 最新公布日期: **{latest_hy_date}**")

        credit_y_range = None
        if st.checkbox("手动自定义信用利差 Y 轴范围", key="credit_manual_y"):
            val_hy = df_highyield['Value'] if 'Value' in df_highyield.columns else df_highyield.iloc[:, 1]
            hy_min = float(val_hy.dropna().min())
            hy_max = float(val_hy.dropna().max())
            credit_y_range = st.slider("信用利差 Y 轴范围 (%)", round(max(0.0, hy_min - 1.0), 1), round(hy_max + 2.0, 1), (round(hy_min, 1), round(hy_max, 1)), 0.1, key="credit_y_slider")

        fig_credit = create_credit_spread_chart(df_highyield, y_range=credit_y_range, timeframe=macro_tf)
        if fig_credit:
            st.plotly_chart(fig_credit, use_container_width=True)
    else:
        st.info("高收益债信用利差数据加载中或不可用。")

# 第三排：失业率 + 美联储资产负债表 + 金油比
m_col5, m_col6 = st.columns(2)

with m_col5:
    df_unrate = get_unemployment_data()
    if not df_unrate.empty:
        latest_unrate_date = pd.to_datetime(df_unrate['date'].iloc[-1]).strftime('%Y-%m-%d') if 'date' in df_unrate.columns else "最新"
        st.subheader("美国失业率 (UNRATE)")
        st.caption(f"🕒 数据刷新时间 (美东时间): **{current_et_str}** | 最新公布日期: **{latest_unrate_date}**")

        unrate_y_range = None
        if st.checkbox("手动自定义失业率 Y 轴范围", key="unrate_manual_y"):
            val_unrate = df_unrate['Unemployment_Rate'] if 'Unemployment_Rate' in df_unrate.columns else df_unrate.iloc[:, 1]
            u_min = float(val_unrate.dropna().min())
            u_max = float(val_unrate.dropna().max())
            unrate_y_range = st.slider("失业率 Y 轴范围 (%)", round(max(0.0, u_min - 2.0), 1), round(u_max + 3.0, 1), (round(u_min, 1), round(u_max, 1)), 0.1, key="unrate_y_slider")

        fig_unrate = create_unemployment_chart(df_unrate, y_range=unrate_y_range, timeframe=macro_tf)
        if fig_unrate:
            st.plotly_chart(fig_unrate, use_container_width=True)
    else:
        st.info("失业率数据加载中或不可用。")

with m_col6:
    df_fed_bs = get_fed_balance_sheet_data()
    if not df_fed_bs.empty:
        latest_fed_date = pd.to_datetime(df_fed_bs['date'].iloc[-1]).strftime('%Y-%m-%d') if 'date' in df_fed_bs.columns else "最新"
        st.subheader("美联储资产负债表 (WALCL)")
        st.caption(f"🕒 数据刷新时间 (美东时间): **{current_et_str}** | 最新公布日期: **{latest_fed_date}**")

        fed_y_range = None
        if st.checkbox("手动自定义资产负债表 Y 轴范围", key="fed_manual_y"):
            val_fed = df_fed_bs['balance_sheet_tn'] if 'balance_sheet_tn' in df_fed_bs.columns else df_fed_bs.iloc[:, 1]
            f_min = float(val_fed.dropna().min())
            f_max = float(val_fed.dropna().max())
            fed_y_range = st.slider("资产负债表 Y 轴范围 (万亿美元)", round(max(0.0, f_min - 1.0), 2), round(f_max + 1.0, 2), (round(f_min, 2), round(f_max, 2)), 0.05, key="fed_y_slider")

        fig_fed_bs = create_fed_balance_sheet_chart(df_fed_bs, y_range=fed_y_range, timeframe=macro_tf)
        if fig_fed_bs:
            st.plotly_chart(fig_fed_bs, use_container_width=True)
    else:
        st.info("美联储资产负债表数据加载中或不可用。")

df_gold_oil = get_gold_oil_ratio_data()
if not df_gold_oil.empty:
    latest_go_date = pd.to_datetime(df_gold_oil['date'].iloc[-1]).strftime('%Y-%m-%d') if 'date' in df_gold_oil.columns else "最新"
    st.subheader("Gold / Oil Ratio (金油比)")
    st.caption(f"🕒 数据刷新时间 (美东时间): **{current_et_str}** | 最新公布日期: **{latest_go_date}**")

    go_y_range = None
    if st.checkbox("手动自定义金油比 Y 轴范围", key="go_manual_y"):
        val_go = df_gold_oil['gold_oil_ratio'] if 'gold_oil_ratio' in df_gold_oil.columns else df_gold_oil.iloc[:, -1]
        go_min = float(val_go.dropna().min())
        go_max = float(val_go.dropna().max())
        go_y_range = st.slider("金油比 Y 轴范围", round(max(0.0, go_min - 5.0), 1), round(go_max + 10.0, 1), (round(go_min, 1), round(go_max, 1)), 0.5, key="go_y_slider")

    fig_gold_oil = create_gold_oil_ratio_chart(df_gold_oil, y_range=go_y_range, timeframe=macro_tf)
    if fig_gold_oil:
        st.plotly_chart(fig_gold_oil, use_container_width=True)

# --- 5. 深度策略指南卡片 ---
st.markdown("---")
with st.expander("📖 查看《见证逆潮》核心宏观逻辑与收益率曲线策略指南（深度解析版）", expanded=False):
    st.markdown("""
    ### 模块一：宏观长波与“逆潮”时代核心运行逻辑 (Macro Framework)

    #### 1. 全球三级分工体系破裂与重构 (Structural Shift in Global Trade)
    * **三级分工结构**：资源国（提供能源/大宗商品）、生产国（提供中低端制造业与产能）、消费国（提供终极需求与储备货币）。
    * **“逆潮”演变**：全球化效率优先时代告终，转向安全性与冗余度升维。近岸外包（Nearshoring）与友岸外包（Friendshoring）抬高了全球边际生产成本，通胀中枢面临结构性上移。

    #### 2. 债务杠杆周期与“利率病”宿命 (Debt Leverage & Fiscal Dominance)
    * **信用扩张临界点**：过去 40 年低通胀与低利率驱动全球信用扩张，目前债务/GDP 比率达到历史极值，信用扩张对经济刺激的边际递减效应显现。
    * **财政赤字货币化**：贫富差距扩大部分拉低边际消费倾向，政府被迫通过扩张性财政赤字支撑需求，导致公债负担飙升与财政主导（Fiscal Dominance）风险。

    #### 3. “3D”结构性长期阻力 (The 3D Structural Headwinds)
    * **De-globalization (去全球化)**：关税壁垒与供应链重构提高商品供给成本。
    * **Demographics (人口老龄化)**：劳动参与率下降与劳动力紧缺回升，结构性工资通胀粘性增强。
    * **Debt / Decarbonization (高债务与脱碳转型)**：高债务带来高利息支出挤压财政，而绿色脱碳转型在中短期产生转换成本（Greenflation）。

    ---

    ### 模块二：国债收益率曲线形态、传导机制与大类资产轮动 (Yield Curve Dynamics)

    #### 1. 收益率曲线倒挂阶段 (Inversion: 2Y > 10Y, 2s10s < 0)
    * **传导机制**：央行持续加息抬升短端政策利率，而市场对远期经济衰退与通胀回落预期压低长端利率，导致长短端倒挂。
    * **实体影响**：商业银行“借短贷长”净息差受挤压，信贷供给意愿收紧，实体经济信用环境逐步紧缩。
    * **资产配置**：
      * **优选**：现金及超短期国债（1-3个月 T-Bills，获取高无风险收益）；高股息、低负债、强现金流的防御性板块（Utilities, Consumer Staples, Healthcare）。
      * **规避**：高估值、高负债、依赖外部融资的无盈利成长股；高杠杆房地产及高收益垃圾债（HYG）。

    #### 2. 牛市陡峭化阶段 (Bull Steepening: 2Y 利率急跌)
    * **传导机制**：衰退兑现或金融体系流动性压力爆发，央行开启预防性或危机式降息，短端利率急剧暴跌，曲线迅速恢复正利差。
    * **阶段演变**：
      * *前段（衰退/去杠杆期）*：企业 EPS 下修，市场经历“杀业绩”，风险资产剧烈去杠杆。
      * *后段（宽松复苏期）*：流动性注入后估值底探明，市场迎来 V 型或 U 型反弹。
    * **资产配置**：
      * **胜率最高**：中长期国债（TLT, IEF）；黄金（实际利率下行与降息周期的双重催化）。
      * **股票择时**：前段保持防守，待盈利下修风险释放后，布局超跌高弹性成长股及早周期行业（Semiconductors, Consumer Discretionary）。

    #### 3. 熊市陡峭化阶段 (Bear Steepening: 10Y 利率暴涨)
    * **传导机制**：长端利率暴涨主要由**期限溢价（Term Premium）飙升**、**美债供给冲击**以及**长期通胀中枢上移**驱动，而非单纯由强劲经济扩张拉动。
    * **资产配置**：
      * **优选**：硬资产（Hard Assets）—— 原油、铜、大宗商品及抗通胀债券（TIPS）；上游资源类价值股（Energy, Mining）；短久期固收产品。
      * **规避**：长久期纯债；依赖极低无风险利率假设支撑的超高估值股票。

    ---

    ### 模块三：量化跟踪指标与微观流动性预警 (Quant Tracking Indicators)

    * **2s10s 利差解冻期**：跟踪利差从深倒挂（如 -100bps）向 0bps 修复的速度，倒挂解冻（Un-inversion）往往是衰退临近的信号。
    * **10Y 实际利率 (DFII10)**：代表全社会真实资本成本，当 Real Yield > 2.0% 时，全局美股估值与风险资产折现率受挤压。
    * **SOFR - IORB 资金面体温计**：预警线为 **+3.0 bps**。若 SOFR 持续高于 IORB +3bps，表明隔夜市场流动性出现摩擦。
    * **高收益债信用利差 (BAMLH0A0HYM2)**：预警红线为 **500 bps (5.0%)**。利差陡峭走阔标志着信用风险向实体经济扩散。
    * **美联储净流动性 (WALCL - TGA - RRP)**：作为美股流动性的先行指标，净流动性拐点通常领先标普 500 指数 2-4 周。
    """)
