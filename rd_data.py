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
    create_real_yield_breakeven_chart,
    create_nfci_chart,
    create_net_liquidity_chart,
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

# ------------------------------------------------------------------
# FRED 核心宏观与流动性指标获取函数
# ------------------------------------------------------------------
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
    """获取 10Y TIPS 实际利率 (DFII10) 与 10Y 盈亏平衡通胀率 (T10YIE)"""
    df_tips = _fetch_fred_series_observations("DFII10", "10Y_Real_Yield", "2010-01-01")
    df_be = _fetch_fred_series_observations("T10YIE", "10Y_Breakeven_Inflation", "2010-01-01")
    if not df_tips.empty and not df_be.empty:
        merged = pd.merge(df_tips, df_be, on="date", how="inner").sort_values("date")
        return merged.reset_index(drop=True)
    return df_tips if not df_tips.empty else df_be

@st.cache_data(ttl=60 * 60 * 6)
def get_nfci_data():
    """获取芝加哥联储全国金融条件指数 (NFCI)"""
    return _fetch_fred_series_observations("NFCI", "NFCI", "2010-01-01")

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
    # WALCL: Millions USD, TGA: Millions USD, RRP: Billions USD -> Trillion USD
    df["Fed_Net_Liquidity_Tn"] = (df["walcl"] - df["tga"] - (df["rrp"] * 1000)) / 1_000_000
    df["Bank_Reserves_Tn"] = df["reserves"] / 1_000_000

    return df[["date", "Fed_Net_Liquidity_Tn", "Bank_Reserves_Tn"]].dropna().reset_index(drop=True)

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

current_et_str = get_current_time_str_eastern()

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

# --- 3. 宏观流动性与真实资本成本多维指标 ---
st.markdown("---")
st.header("📊 宏观流动性与多维指标追踪")

# 第一排：10Y TIPS 实际利率与通胀预期 + 美联储净流动性与银行准备金
m_col1, m_col2 = st.columns(2)

with m_col1:
    df_ry = get_real_yield_and_breakeven_data()
    if not df_ry.empty:
        latest_ry_date = pd.to_datetime(df_ry['date'].iloc[-1]).strftime('%Y-%m-%d')
        st.subheader("10Y TIPS 实际利率 & 通胀预期")
        st.caption(f"🕒 数据刷新时间 (美东时间): **{current_et_str}** | 最新公布日期: **{latest_ry_date}**")

        ry_y_range = None
        if st.checkbox("手动设置实际利率 Y 轴范围", key="ry_manual_y"):
            val_ry = df_ry['10Y_Real_Yield'] if '10Y_Real_Yield' in df_ry.columns else df_ry.iloc[:, 1]
            r_min = float(val_ry.dropna().min())
            r_max = float(val_ry.dropna().max())
            ry_y_range = st.slider("实际利率 Y 轴范围 (%)", round(r_min - 1.0, 1), round(r_max + 1.0, 1), (round(r_min, 1), round(r_max, 1)), 0.1, key="ry_slider")

        fig_ry = create_real_yield_breakeven_chart(df_ry, y_range=ry_y_range)
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
        if st.checkbox("手动设置净流动性 Y 轴范围", key="liq_manual_y"):
            val_liq = df_net_liq['Fed_Net_Liquidity_Tn']
            l_min = float(val_liq.dropna().min())
            l_max = float(val_liq.dropna().max())
            liq_y_range = st.slider("净流动性 Y 轴范围 (万亿 USD)", round(l_min - 0.5, 2), round(l_max + 0.5, 2), (round(l_min, 2), round(l_max, 2)), 0.05, key="liq_slider")

        fig_liq = create_net_liquidity_chart(df_net_liq, y_range=liq_y_range)
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
        if st.checkbox("手动设置 NFCI Y 轴范围", key="nfci_manual_y"):
            val_n = df_nfci['NFCI']
            n_min = float(val_n.dropna().min())
            n_max = float(val_n.dropna().max())
            nfci_y_range = st.slider("NFCI Y 轴范围", round(n_min - 0.5, 2), round(n_max + 0.5, 2), (round(n_min, 2), round(n_max, 2)), 0.05, key="nfci_slider")

        fig_nfci = create_nfci_chart(df_nfci, y_range=nfci_y_range)
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
        if st.checkbox("手动设置信用利差 Y 轴范围", key="credit_manual_y"):
            val_hy = df_highyield['Value'] if 'Value' in df_highyield.columns else df_highyield.iloc[:, 1]
            hy_min = float(val_hy.dropna().min())
            hy_max = float(val_hy.dropna().max())
            credit_y_range = st.slider("信用利差 Y 轴范围 (%)", round(max(0.0, hy_min - 1.0), 1), round(hy_max + 2.0, 1), (round(hy_min, 1), round(hy_max, 1)), 0.1, key="credit_y_slider")

        fig_credit = create_credit_spread_chart(df_highyield, y_range=credit_y_range)
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
        if st.checkbox("手动设置失业率 Y 轴范围", key="unrate_manual_y"):
            val_unrate = df_unrate['Unemployment_Rate'] if 'Unemployment_Rate' in df_unrate.columns else df_unrate.iloc[:, 1]
            u_min = float(val_unrate.dropna().min())
            u_max = float(val_unrate.dropna().max())
            unrate_y_range = st.slider("失业率 Y 轴范围 (%)", round(max(0.0, u_min - 2.0), 1), round(u_max + 3.0, 1), (round(u_max, 1), round(u_max, 1)), 0.1, key="unrate_y_slider")

        fig_unrate = create_unemployment_chart(df_unrate, y_range=unrate_y_range)
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
        if st.checkbox("手动设置资产负债表 Y 轴范围", key="fed_manual_y"):
            val_fed = df_fed_bs['balance_sheet_tn'] if 'balance_sheet_tn' in df_fed_bs.columns else df_fed_bs.iloc[:, 1]
            f_min = float(val_fed.dropna().min())
            f_max = float(val_fed.dropna().max())
            fed_y_range = st.slider("资产负债表 Y 轴范围 (万亿美元)", round(max(0.0, f_min - 1.0), 2), round(f_max + 1.0, 2), (round(f_min, 2), round(f_max, 2)), 0.05, key="fed_y_slider")

        fig_fed_bs = create_fed_balance_sheet_chart(df_fed_bs, y_range=fed_y_range)
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
    if st.checkbox("手动设置金油比 Y 轴范围", key="go_manual_y"):
        val_go = df_gold_oil['gold_oil_ratio'] if 'gold_oil_ratio' in df_gold_oil.columns else df_gold_oil.iloc[:, -1]
        go_min = float(val_go.dropna().min())
        go_max = float(val_go.dropna().max())
        go_y_range = st.slider("金油比 Y 轴范围", round(max(0.0, go_min - 5.0), 1), round(go_max + 10.0, 1), (round(go_min, 1), round(go_max, 1)), 0.5, key="go_y_slider")

    fig_gold_oil = create_gold_oil_ratio_chart(df_gold_oil, y_range=go_y_range)
    if fig_gold_oil:
        st.plotly_chart(fig_gold_oil, use_container_width=True)

# --- 4. 策略指南卡片 ---
st.markdown("---")
with st.expander("📖 查看《见证逆潮》核心宏观逻辑与收益率曲线策略指南", expanded=False):
    st.markdown("""
    ### 模块一：《见证逆潮》核心宏观逻辑
    * **全球三级分工体系重塑**：生产国、消费国、资源国分化。
    * **债务与杠杆宿命**：杠杆驱动增长难以为继，带来 K 型社会分化与“利率病”。
    * **3D 时代挑战**：去全球化 (De-globalization)、人口老龄化 (Demographics)、高债务 (Debt)。
    * **大周期决定小周期**：宏观长波周期（康波周期）决定产业与中观周期。

    ---

    ### 模块二：国债收益率曲线形态与大类资产轮动策略
    1. **收益率曲线倒挂 (2Y > 10Y, 2s10s < 0)**
       * *含义*：经济过热/高通胀引致央行加息紧缩，长期增长承压，预示衰退。
       * *资产配置*：现金与短债为王；规避高估值高融资成长股；选择强现金流、低负债、高股息防御板块。
    2. **牛市陡峭化 (Bull Steepening, 2Y 快速大幅下降)**
       * *含义*：衰退/金融危机兑现，央行恐慌性大幅降息。
       * *资产配置*：做多长短期国债（胜率最高）；黄金主升浪（实际利率下行）；股市初段因 EPS 下修“杀业绩”暴跌，流动性注入后 V 型复苏。
    3. **熊市陡峭化 (Bear Steepening, 10Y 快速大幅上升)**
       * *含义*：逆潮时代特殊产物，长期通胀失控、供应链重构、主权债务超发，期限溢价飙升。
       * *资产配置*：长债灾难；高估值/长久期资产受创；拥抱硬资产（铜、原油等大宗商品）及上游资源类价值股。

    ---

    ### 模块三：量化跟踪与实操应对
    * **盯紧 2s10s 利差趋势**：跟踪利差回升（如 -1.0% 至 -0.2%），提前降低风险仓位。
    * **实际利率与通胀预期分离**：跟踪 TIPS 收益率与 Breakeven，区分债务/流动性担忧与通胀驱动。
    * **微观流动性验证**：结合高收益债利差（HYG）与 VIX 指数，利差陡峭化伴随信用利差走阔即确认流动性枯竭。
    """)
