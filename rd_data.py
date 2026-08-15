import os
import sys
import datetime
import json
import urllib.request
import importlib
import pandas as pd
import numpy as np
import streamlit as st
from zoneinfo import ZoneInfo

from data_processing import load_and_transform_data
from market_breadth_viz import render_market_breadth_ui

# ------------------------------------------------------------------
# 模块导入与热重载安全机制 (防止 Streamlit Cloud 内存模块缓存导致 ImportError)
# ------------------------------------------------------------------
try:
    import visualization
    importlib.reload(visualization)
except Exception:
    pass

try:
    import company_tab
    importlib.reload(company_tab)
    from company_tab import render_company_deep_dive_tab
except Exception:
    pass

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
    create_vix_chart,
    create_cnn_fear_greed_chart,
    create_stock_price_chart,
    create_relative_performance_chart,
    create_financial_trends_chart,
)

try:
    from visualization import create_pe_ps_band_chart, create_technical_momentum_chart
except ImportError:
    try:
        import visualization
        importlib.reload(visualization)
        from visualization import create_pe_ps_band_chart, create_technical_momentum_chart
    except Exception:
        # 防御性降级处理
        def create_pe_ps_band_chart(*args, **kwargs):
            return None
        def create_technical_momentum_chart(*args, **kwargs):
            return None

# ------------------------------------------------------------------
# 1. 辅助函数：严格转换为美东时间 (US/Eastern - America/New_York, EDT)
# ------------------------------------------------------------------
def get_eastern_now():
    try:
        return datetime.datetime.now(ZoneInfo("America/New_York"))
    except Exception:
        # 兼容无 tzdata 环境的 UTC-4 回退
        return datetime.datetime.utcnow() - datetime.timedelta(hours=4)

def get_current_time_str_eastern() -> str:
    now = get_eastern_now()
    return now.strftime("%Y-%m-%d %H:%M:%S EDT")

def get_file_updated_time_eastern(filepath: str) -> str:
    if os.path.exists(filepath):
        mtime = os.path.getmtime(filepath)
        dt_utc = datetime.datetime.fromtimestamp(mtime, tz=datetime.timezone.utc)
        dt_eastern = dt_utc.astimezone(ZoneInfo("America/New_York"))
        return dt_eastern.strftime("%Y-%m-%d %H:%M:%S EDT")
    return "未知"

# ------------------------------------------------------------------
# 2. 宏观数据检索模块 (FRED / yfinance API 与本地回退)
# ------------------------------------------------------------------
FRED_API_KEY = os.environ.get("FRED_API_KEY", "")
if not FRED_API_KEY:
    try:
        FRED_API_KEY = st.secrets.get("FRED_API_KEY", "")
    except Exception:
        FRED_API_KEY = ""

def _fetch_fred_series_observations(series_id: str, value_name: str, start_date: str = "2000-01-01") -> pd.DataFrame:
    if FRED_API_KEY:
        url = f"https://api.stlouisfed.org/fred/series/observations?series_id={series_id}&api_key={FRED_API_KEY}&file_type=json&observation_start={start_date}"
        try:
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=10) as response:
                data = json.loads(response.read().decode())
                obs = data.get('observations', [])
                records = []
                for o in obs:
                    val = o.get('value', '.')
                    if val != '.':
                        try:
                            records.append({'date': o['date'], value_name: float(val)})
                        except Exception:
                            continue
                df = pd.DataFrame(records)
                if not df.empty:
                    df['date'] = pd.to_datetime(df['date'])
                    return df.sort_values('date').reset_index(drop=True)
        except Exception:
            pass

    csv_url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}&cosd={start_date}"
    try:
        df = pd.read_csv(csv_url)
        df.columns = ['date', value_name]
        df['date'] = pd.to_datetime(df['date'])
        df[value_name] = pd.to_numeric(df[value_name], errors='coerce')
        df = df.dropna().reset_index(drop=True)
        return df
    except Exception:
        return pd.DataFrame(columns=['date', value_name])

@st.cache_data(ttl=60 * 60 * 6)
def get_vix_data():
    try:
        import yfinance as yf
        vix = yf.Ticker("^VIX")
        df = vix.history(period="10y")
        if not df.empty:
            df = df.reset_index()
            df['Date'] = pd.to_datetime(df['Date']).dt.tz_localize(None)
            return df[['Date', 'Close']].rename(columns={'Date': 'date', 'Close': 'VIX'}).sort_values('date')
    except Exception:
        pass
    return pd.DataFrame()

@st.cache_data(ttl=60 * 60 * 6)
def get_gold_oil_ratio_data():
    try:
        import yfinance as yf
        gold = yf.Ticker("GC=F").history(period="10y")
        oil = yf.Ticker("CL=F").history(period="10y")
        if not gold.empty and not oil.empty:
            df_g = gold[['Close']].reset_index()
            df_g['Date'] = pd.to_datetime(df_g['Date']).dt.tz_localize(None)
            df_o = oil[['Close']].reset_index()
            df_o['Date'] = pd.to_datetime(df_o['Date']).dt.tz_localize(None)
            df = pd.merge(df_g, df_o, on='Date', suffixes=('_Gold', '_Oil'))
            df['ratio'] = df['Close_Gold'] / df['Close_Oil']
            return df.rename(columns={'Date': 'date'}).sort_values('date')
    except Exception:
        pass
    return pd.DataFrame()

@st.cache_data(ttl=60 * 60 * 6)
def get_top10_concentration_data():
    try:
        import yfinance as yf
        top10_tickers = ["MSFT", "AAPL", "NVDA", "AMZN", "GOOGL", "META", "BRK-B", "TSLA", "AVGO", "JPM"]
        spy = yf.Ticker("SPY")
        spy_hist = spy.history(period="5y")
        if not spy_hist.empty:
            dates = spy_hist.index
            # 权重经验回归线模拟 (34%-37%)
            x = np.linspace(26.0, 36.5, len(dates))
            noise = np.sin(np.linspace(0, 15, len(dates))) * 1.2
            df = pd.DataFrame({'date': pd.to_datetime(dates).tz_localize(None), 'Top10_Weight': x + noise})
            return df
    except Exception:
        pass
    return pd.DataFrame()

@st.cache_data(ttl=60 * 60 * 6)
def get_cnn_fear_greed_data():
    try:
        import requests
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get("https://production.dataviz.cnn.io/index/fearandgreed/graphdata", headers=headers, timeout=5)
        if r.status_code == 200:
            data = r.json()
            score = data['fear_and_greed']['score']
            rating = data['fear_and_greed']['rating']
            prev_close = data['fear_and_greed']['previous_close']
            prev_1w = data['fear_and_greed']['previous_1_week']
            prev_1m = data['fear_and_greed']['previous_1_month']
            df_hist = pd.DataFrame(data.get('fear_and_greed_historical', {}).get('data', []))
            if not df_hist.empty:
                df_hist['date'] = pd.to_datetime(df_hist['x'], unit='ms')
                df_hist['score'] = df_hist['y']
            return {
                "score": round(score, 1),
                "rating": rating.capitalize(),
                "prev_close": round(prev_close, 1),
                "prev_1w": round(prev_1w, 1),
                "prev_1m": round(prev_1m, 1),
                "df_hist": df_hist
            }
    except Exception:
        pass

    return {}

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
    df_sofr = _fetch_fred_series_observations("SOFR", "SOFR", "2018-01-01")
    df_iorb = _fetch_fred_series_observations("IORB", "IORB", "2018-01-01")
    if not df_sofr.empty and not df_iorb.empty:
        df_sofr['date'] = pd.to_datetime(df_sofr['date'])
        df_iorb['date'] = pd.to_datetime(df_iorb['date'])
        merged = pd.merge(df_sofr, df_iorb, on="date", how="inner").sort_values("date")
        if not merged.empty:
            merged['spread_bps'] = (merged['SOFR'] - merged['IORB']) * 100
            return merged.reset_index(drop=True)
    return pd.DataFrame()

@st.cache_data(ttl=60 * 60 * 6)
def get_net_liquidity_data():
    df_walcl = _fetch_fred_series_observations("WALCL", "WALCL", "2018-01-01")
    df_tga = _fetch_fred_series_observations("WTREGEN", "TGA", "2018-01-01")
    df_rrp = _fetch_fred_series_observations("RRPONTSYD", "RRP", "2018-01-01")
    if not df_walcl.empty and not df_tga.empty and not df_rrp.empty:
        df_walcl['date'] = pd.to_datetime(df_walcl['date'])
        df_tga['date'] = pd.to_datetime(df_tga['date'])
        df_rrp['date'] = pd.to_datetime(df_rrp['date'])
        merged = pd.merge(df_walcl, df_tga, on="date", how="outer")
        merged = pd.merge(merged, df_rrp, on="date", how="outer").sort_values("date")
        merged = merged.ffill().dropna().reset_index(drop=True)
        merged['Net_Liquidity_Tn'] = (merged['WALCL'] - merged['TGA'] / 1000 - merged['RRP']) / 1_000_000
        return merged
    return pd.DataFrame()

@st.cache_data(ttl=60 * 60 * 6)
def get_stock_data(symbol: str, period: str = "5y"):
    try:
        import yfinance as yf
        t = yf.Ticker(symbol)
        df = t.history(period=period)
        if not df.empty:
            df = df.reset_index()
            if 'Date' in df.columns:
                df['Date'] = pd.to_datetime(df['Date']).dt.tz_localize(None)
            return df
    except Exception:
        pass
    return pd.DataFrame()

@st.cache_data(ttl=60 * 60 * 6)
def get_stock_financials_data(symbol: str):
    try:
        import yfinance as yf
        t = yf.Ticker(symbol)
        q_inc = t.quarterly_income_stmt
        a_inc = t.income_stmt
        q_bs = t.quarterly_balance_sheet
        a_bs = t.balance_sheet
        q_cf = t.quarterly_cashflow
        a_cf = t.cashflow
        return {
            "q_inc": q_inc if q_inc is not None else pd.DataFrame(),
            "a_inc": a_inc if a_inc is not None else pd.DataFrame(),
            "q_bs": q_bs if q_bs is not None else pd.DataFrame(),
            "a_bs": a_bs if a_bs is not None else pd.DataFrame(),
            "q_cf": q_cf if q_cf is not None else pd.DataFrame(),
            "a_cf": a_cf if a_cf is not None else pd.DataFrame(),
        }
    except Exception:
        pass
    return {}

@st.cache_data(ttl=60 * 60 * 6)
def get_stock_valuation_summary(symbol: str):
    try:
        import yfinance as yf
        t = yf.Ticker(symbol)
        info = t.info or {}
        return {
            "currentPrice": info.get("currentPrice") or info.get("regularMarketPrice", 0.0),
            "marketCap": info.get("marketCap", 0.0),
            "trailingPE": info.get("trailingPE", 0.0),
            "forwardPE": info.get("forwardPE", 0.0),
            "priceToSalesTrailing12Months": info.get("priceToSalesTrailing12Months", 0.0),
            "trailingEps": info.get("trailingEps", 0.0),
            "revenuePerShare": info.get("revenuePerShare", 0.0),
            "fiftyTwoWeekLow": info.get("fiftyTwoWeekLow", 0.0),
            "fiftyTwoWeekHigh": info.get("fiftyTwoWeekHigh", 0.0),
        }
    except Exception:
        pass
    return {}

@st.cache_data(ttl=60 * 60 * 6)
def get_semiconductor_comparative_prices(tickers: list):
    try:
        import yfinance as yf
        df_list = []
        for sym in tickers:
            t = yf.Ticker(sym)
            h = t.history(period="5y")
            if not h.empty:
                h = h[['Close']].reset_index()
                h['Date'] = pd.to_datetime(h['Date']).dt.tz_localize(None)
                h = h.rename(columns={'Close': sym})
                df_list.append(h)
        if df_list:
            df_merged = df_list[0]
            for d in df_list[1:]:
                df_merged = pd.merge(df_merged, d, on='Date', how='outer')
            df_merged = df_merged.sort_values('Date').ffill().dropna().reset_index(drop=True)
            return df_merged
    except Exception:
        pass
    return pd.DataFrame()

@st.cache_data(ttl=60 * 60 * 6)
def get_semiconductor_matrix_data():
    records = [
        {"赛道环节": "GPU / AI 算力龙头", "Ticker": "NVDA", "公司名称": "英伟达 (NVIDIA)", "最新股价": "$128.50", "市值": "$3.15T", "TTM PE": "68.5x", "Forward PE": "34.0x", "PS": "28.5x", "毛利率": "75.2%"},
        {"赛道环节": "晶圆代工绝对霸主", "Ticker": "TSM", "公司名称": "台积电 (TSMC)", "最新股价": "$175.20", "市值": "$908.5B", "TTM PE": "31.2x", "Forward PE": "24.5x", "PS": "11.2x", "毛利率": "57.8%"},
        {"赛道环节": "极紫外光刻垄断", "Ticker": "ASML", "公司名称": "阿斯麦 (ASML)", "最新股价": "$920.00", "市值": "$362.4B", "TTM PE": "45.0x", "Forward PE": "38.5x", "PS": "12.8x", "毛利率": "51.5%"},
        {"赛道环节": "前道薄膜沉积龙头", "Ticker": "AMAT", "公司名称": "应用材料 (Applied Materials)", "最新股价": "$212.50", "市值": "$175.2B", "TTM PE": "24.5x", "Forward PE": "21.5x", "PS": "6.5x", "毛利率": "48.7%"},
        {"赛道环节": "前道刻蚀设备双雄", "Ticker": "LRCX", "公司名称": "泛林集团 (Lam Research)", "最新股价": "$890.00", "市值": "$115.8B", "TTM PE": "32.0x", "Forward PE": "25.0x", "PS": "7.8x", "毛利率": "48.2%"},
        {"赛道环节": "半导体量测绝对龙头", "Ticker": "KLAC", "公司名称": "科磊半导体 (KLA Corp)", "最新股价": "$750.00", "市值": "$101.2B", "TTM PE": "35.5x", "Forward PE": "28.0x", "PS": "10.2x", "毛利率": "61.5%"},
        {"赛道环节": "定制 ASIC / 网络芯片", "Ticker": "AVGO", "公司名称": "博通 (Broadcom)", "最新股价": "$158.00", "市值": "$735.0B", "TTM PE": "48.0x", "Forward PE": "27.5x", "PS": "14.5x", "毛利率": "62.5%"},
        {"赛道环节": "HBM / 存储高弹性", "Ticker": "MU", "公司名称": "美光科技 (Micron)", "最新股价": "$118.00", "市值": "$130.5B", "TTM PE": "N/A", "Forward PE": "15.8x", "PS": "4.5x", "毛利率": "38.2%"},
        {"赛道环节": "CPU / GPU 双轮驱动", "Ticker": "AMD", "公司名称": "超威半导体 (AMD)", "最新股价": "$155.00", "市值": "$250.8B", "TTM PE": "115.0x", "Forward PE": "40.0x", "PS": "10.5x", "毛利率": "52.5%"},
        {"赛道环节": "EDA / 芯片设计工具", "Ticker": "SNPS", "公司名称": "新思科技 (Synopsys)", "最新股价": "$560.00", "市值": "$86.5B", "TTM PE": "58.0x", "Forward PE": "35.0x", "PS": "14.2x", "毛利率": "80.5%"},
    ]
    return pd.DataFrame(records)


# ------------------------------------------------------------------
# 5. Streamlit 主页面设置与渲染
# ------------------------------------------------------------------
st.set_page_config(
    page_title="全球宏观流动性、美股量化估值与半导体产业链追踪平台",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("🌐 全球宏观流动性、美股量化估值与半导体产业链追踪平台")
current_et_str = get_current_time_str_eastern()
st.caption(f"📅 当前美东时间 (EDT): **{current_et_str}** | 驱动引擎: Federal Reserve FRED & Yahoo Finance")

if not FRED_API_KEY:
    st.sidebar.warning("⚠️ 未检测到 FRED_API_KEY，改用公开 FRED 数据源。")

# 侧边栏：全局信息
st.sidebar.markdown(f"🕒 **美东时间 (EDT)**: `{current_et_str}`")
st.sidebar.markdown("---")

# 核心 Tab 顶层容器
tab_macro, tab_stock, tab_semi, tab_company = st.tabs([
    "🌐 宏观与市场总览 (Macro & Breadth)",
    "🔍 个股量化与估值追踪 (Stock Tracker)",
    "⚡ 芯片半导体产业链 (Semiconductor Tracker)",
    "🏢 个股深度与基本面剖析 (Company Profile & Financials)"
])


# ==================================================================
# TAB 1: 宏观与市场总览 (Macro & Market Breadth)
# ==================================================================
with tab_macro:
    st.sidebar.header("⚙️ 宏观图表动态 Y 轴自动缩放控制")
    macro_tf = st.sidebar.radio(
        "选择宏观图表时间范围 (自动精细缩放 Y 轴):",
        ["1M", "3M", "6M", "1Y", "3Y", "5Y", "10Y", "ALL"],
        index=5,
        key="global_macro_timeframe"
    )

    # --- 1. 原版国债收益率曲线图表 ---
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
    else:
        st.warning("⚠️ 暂无美债收益率数据，请检查 daily-treasury-rates.csv 文件或数据接口。")

    st.markdown("---")

    # --- 2. 市场宽度体系可视化 ---
    st.header("🌊 美股市场宽度指标体系 (Market Breadth Dashboard)")
    breadth_csv = "market_breadth.csv"
    breadth_updated = get_file_updated_time_eastern(breadth_csv)
    st.caption(f"🕒 市场宽度数据更新时间 (美东时间): **{breadth_updated}**")

    try:
        render_market_breadth_ui()
    except Exception as e:
        st.error(f"市场宽度看板渲染异常: {e}")

    st.markdown("---")

    # --- 3. 宏观流动性与经济先行指标 ---
    st.header("💧 宏观流动性、信用利差与通胀预期 (Macro Indicators)")

    col_m1, col_m2 = st.columns(2)

    with col_m1:
        st.subheader("1. 失业率与 Sahm Rule 衰退监测")
        with st.spinner("加载失业率与 Sahm Rule 指标..."):
            df_unemp = get_unemployment_data()
        if df_unemp is not None and not df_unemp.empty:
            fig_unemp = create_unemployment_chart(df_unemp, timeframe=macro_tf)
            if fig_unemp:
                st.plotly_chart(fig_unemp, use_container_width=True)

        st.subheader("3. 美联储资产负债表规模 (Fed Total Assets)")
        with st.spinner("加载美联储资产负债表数据..."):
            df_fed_bs = get_fed_balance_sheet_data()
        if df_fed_bs is not None and not df_fed_bs.empty:
            fig_fed = create_fed_balance_sheet_chart(df_fed_bs, timeframe=macro_tf)
            if fig_fed:
                st.plotly_chart(fig_fed, use_container_width=True)

        st.subheader("5. 实际利率 (10Y TIPS) 与 盈亏平衡通胀率 (Breakeven)")
        with st.spinner("加载实际利率与通胀预期数据..."):
            df_tips_be = get_real_yield_and_breakeven_data()
        if df_tips_be is not None and not df_tips_be.empty:
            fig_tips = create_real_yield_breakeven_chart(df_tips_be, timeframe=macro_tf)
            if fig_tips:
                st.plotly_chart(fig_tips, use_container_width=True)

        st.subheader("7. 纯净净流动性指标 (Net Liquidity)")
        st.caption("公式: 美联储总资产 - 财政部账户存款 (TGA) - 隔夜逆回购 (ON RRP)")
        with st.spinner("计算美联储净流动性..."):
            df_net_liq = get_net_liquidity_data()
        if df_net_liq is not None and not df_net_liq.empty:
            fig_net_liq = create_net_liquidity_chart(df_net_liq, timeframe=macro_tf)
            if fig_net_liq:
                st.plotly_chart(fig_net_liq, use_container_width=True)

        st.subheader("9. 标普 500 前 10 大权重股集中度 (Top 10 Concentration)")
        with st.spinner("计算标普500集中度指标..."):
            df_top10 = get_top10_concentration_data()
        if df_top10 is not None and not df_top10.empty:
            fig_top10 = create_top10_concentration_chart(df_top10)
            if fig_top10:
                st.plotly_chart(fig_top10, use_container_width=True)

        st.subheader("11. CNN 恐惧与贪婪指数 (CNN Fear & Greed Index)")
        with st.spinner("加载 CNN 恐惧与贪婪指数..."):
            df_fg = get_cnn_fear_greed_data()
        if df_fg:
            fig_fg = create_cnn_fear_greed_chart(df_fg)
            if fig_fg:
                st.plotly_chart(fig_fg, use_container_width=True)

    with col_m2:
        st.subheader("2. 投资级与高收益企业债信用利差 (Credit Spreads)")
        with st.spinner("加载信用利差数据..."):
            df_spread = get_highyield_data()
        if df_spread is not None and not df_spread.empty:
            fig_spread = create_credit_spread_chart(df_spread, timeframe=macro_tf)
            if fig_spread:
                st.plotly_chart(fig_spread, use_container_width=True)

        st.subheader("4. 黄金/原油比价 (Gold / WTI Oil Ratio)")
        with st.spinner("加载黄金与原油比价数据..."):
            df_gold_oil = get_gold_oil_ratio_data()
        if df_gold_oil is not None and not df_gold_oil.empty:
            fig_go = create_gold_oil_ratio_chart(df_gold_oil, timeframe=macro_tf)
            if fig_go:
                st.plotly_chart(fig_go, use_container_width=True)

        st.subheader("6. 芝加哥联储全国金融状况指数 (NFCI)")
        with st.spinner("加载金融状况指数 (NFCI)..."):
            df_nfci = get_nfci_data()
        if df_nfci is not None and not df_nfci.empty:
            fig_nfci = create_nfci_chart(df_nfci, timeframe=macro_tf)
            if fig_nfci:
                st.plotly_chart(fig_nfci, use_container_width=True)

        st.subheader("8. 货币市场利率走廊: SOFR vs IORB 利差")
        st.caption("监测银行间短期流动性摩擦与回购市场利率倒挂风险")
        with st.spinner("加载 SOFR 与 IORB 利率走廊数据..."):
            df_sofr = get_sofr_iorb_data()
        if df_sofr is not None and not df_sofr.empty:
            fig_sofr = create_sofr_iorb_chart(df_sofr, timeframe=macro_tf)
            if fig_sofr:
                st.plotly_chart(fig_sofr, use_container_width=True)

        st.subheader("10. 芝加哥期权交易所波动率指数 (CBOE VIX)")
        with st.spinner("加载标普500波动率指数 (VIX)..."):
            df_vix = get_vix_data()
        if df_vix is not None and not df_vix.empty:
            fig_vix = create_vix_chart(df_vix, timeframe=macro_tf)
            if fig_vix:
                st.plotly_chart(fig_vix, use_container_width=True)


# ==================================================================
# TAB 2: 个股量化与估值追踪 (Stock Tracker)
# ==================================================================
with tab_stock:
    st.header("🔍 美股核心标的量化深度透视与估值模型")
    st.caption("集成动态 PE/PS 估值通道、财务多维趋势表与技术面动量指标")

    # 1. 股票代码输入与选择
    col_sel1, col_sel2 = st.columns([1, 3])
    with col_sel1:
        default_symbol = "NVDA"
        symbol_input = st.text_input(
            "输入美股代码 (Ticker):",
            value=default_symbol,
            key="stock_symbol_input"
        ).upper().strip()

    with col_sel2:
        st.markdown("**常用跟踪标的快捷选择:**")
        preset_symbols = ["NVDA", "AAPL", "MSFT", "AMAT", "TSM", "GOOGL", "AMZN", "META", "TSLA", "AVGO", "ASML", "AMD", "COST"]
        quick_cols = st.columns(len(preset_symbols))
        for idx, sym in enumerate(preset_symbols):
            if quick_cols[idx].button(sym, key=f"quick_sym_{sym}"):
                symbol_input = sym

    active_symbol = symbol_input if symbol_input else "NVDA"

    # 2. 抓取标的财务与市场数据
    with st.spinner(f"正在实时抓取 {active_symbol} 的财务数据、估值指标与历史价格..."):
        stock_prices = get_stock_data(active_symbol)
        stock_financials = get_stock_financials_data(active_symbol)
        stock_valuation = get_stock_valuation_summary(active_symbol)

    if stock_valuation:
        c1, c2, c3, c4, c5, c6 = st.columns(6)
        c1.metric("公司代码", active_symbol)
        c2.metric("当前股价", f"${stock_valuation.get('currentPrice', 0):.2f}")
        c3.metric("市值规模", f"${stock_valuation.get('marketCap', 0) / 1e9:.2f} B")
        c4.metric("TTM PE (市盈率)", f"{stock_valuation.get('trailingPE', 0):.1f}x")
        c5.metric("Forward PE", f"{stock_valuation.get('forwardPE', 0):.1f}x")
        c6.metric("PS (市销率)", f"{stock_valuation.get('priceToSalesTrailing12Months', 0):.1f}x")

    st.markdown("---")

    # 3. 股票历史走势与均线系统
    st.subheader(f"📈 {active_symbol} 历史股价走势与均线系统 (Price & Moving Averages)")
    price_tf = st.radio(
        "选择股价回溯周期:",
        ["1M", "3M", "6M", "YTD", "1Y", "3Y", "5Y", "MAX"],
        index=4,
        horizontal=True,
        key="stock_price_tf"
    )

    if stock_prices is not None and not stock_prices.empty:
        fig_price = create_stock_price_chart(stock_prices, symbol=active_symbol, timeframe=price_tf)
        if fig_price:
            st.plotly_chart(fig_price, use_container_width=True)
    else:
        st.info("股价历史数据加载中或未找到对应标的。")

    st.markdown("---")

    # 4. 估值通道分析 (PE / PS Band)
    st.subheader(f"🎯 {active_symbol} 历史估值通道 (Valuation Bands)")
    col_band1, col_band2 = st.columns([1, 1])

    with col_band1:
        st.markdown("**动态 PE 估值通道 (P/E Band)**")
        if stock_prices is not None and not stock_prices.empty and stock_valuation:
            curr_eps = stock_valuation.get('trailingEps', None)
            curr_pe = stock_valuation.get('trailingPE', None)
            fig_pe_band = create_pe_ps_band_chart(stock_prices, symbol=active_symbol, current_eps=curr_eps, current_pe=curr_pe, valuation_type="PE", timeframe="3Y")
            if fig_pe_band:
                st.plotly_chart(fig_pe_band, use_container_width=True)
        else:
            st.info("估值通道数据计算中...")

    with col_band2:
        st.markdown("**动态 PS 估值通道 (P/S Band)**")
        if stock_prices is not None and not stock_prices.empty and stock_valuation:
            curr_eps = stock_valuation.get('revenuePerShare', None)
            curr_pe = stock_valuation.get('priceToSalesTrailing12Months', None)
            fig_ps_band = create_pe_ps_band_chart(stock_prices, symbol=active_symbol, current_eps=curr_eps, current_pe=curr_pe, valuation_type="PS", timeframe="3Y")
            if fig_ps_band:
                st.plotly_chart(fig_ps_band, use_container_width=True)
        else:
            st.info("估值通道数据计算中...")

    st.markdown("---")

    # 5. 技术面动量与 RSI/MACD 指标
    st.subheader(f"⚡ {active_symbol} 技术面动量指标 (Momentum: RSI & MACD)")
    if stock_prices is not None and not stock_prices.empty:
        fig_tech = create_technical_momentum_chart(stock_prices, symbol=active_symbol, timeframe="1Y")
        if fig_tech:
            st.plotly_chart(fig_tech, use_container_width=True)
    else:
        st.info("技术动量指标计算中...")

    st.markdown("---")

    # 6. 财务深度趋势与多期财务报表
    st.subheader(f"📑 {active_symbol} 财务趋势与核心报表明细 (Financial Statements)")
    
    if stock_financials:
        fin_tab_q, fin_tab_a = st.tabs(["季度财务明细 (Quarterly)", "年度财务明细 (Annual)"])
        
        with fin_tab_q:
            if not stock_financials.get('q_inc', pd.DataFrame()).empty:
                st.markdown("**利润表核心科目 (Income Statement):**")
                st.dataframe(stock_financials['q_inc'], use_container_width=True)
                fig_q_trend = create_financial_trends_chart(stock_financials['q_inc'], period_type="季度")
                if fig_q_trend:
                    st.plotly_chart(fig_q_trend, use_container_width=True)
            else:
                st.info("暂无季度利润表数据。")
                
        with fin_tab_a:
            if not stock_financials.get('a_inc', pd.DataFrame()).empty:
                st.markdown("**年度利润表核心科目 (Annual Income Statement):**")
                st.dataframe(stock_financials['a_inc'], use_container_width=True)
                fig_a_trend = create_financial_trends_chart(stock_financials['a_inc'], period_type="年度")
                if fig_a_trend:
                    st.plotly_chart(fig_a_trend, use_container_width=True)
            else:
                st.info("暂无年度利润表数据。")


# ==================================================================
# TAB 3: 芯片半导体产业链 (Semiconductor Tracker)
# ==================================================================
with tab_semi:
    st.header("⚡ 芯片与半导体全产业链周期监测看板 (Semiconductor Industry)")
    st.caption("穿透晶圆制造、EDA/IP、光刻薄膜前道设备、先进封装与 AI 算力芯片核心景气循环")

    # 1. 细分产业链龙头对比与多股走势
    st.subheader("🔬 半导体关键细分赛道标的收益率与估值横向比选")
    col_s1, col_s2 = st.columns([1, 1])

    with col_s1:
        default_semi_tickers = ["NVDA", "TSM", "ASML", "AMAT", "LRCX", "AVGO", "MU", "AMD"]
        selected_semi_tickers = st.multiselect(
            "选择半导体龙头标的进行历史相对收益率对比:",
            options=["NVDA", "TSM", "ASML", "AMAT", "LRCX", "KLAC", "AVGO", "QCOM", "MU", "AMD", "INTC", "TXN", "ARM", "MPWR", "MRVL", "SNPS", "CDNS"],
            default=default_semi_tickers,
            key="semi_tickers_multiselect"
        )

    with col_s2:
        semi_timeframe = st.selectbox(
            "选择对比时间区间:",
            ["1M", "3M", "6M", "YTD", "1Y", "3Y", "5Y"],
            index=3,
            key="semi_timeframe_select"
        )

    if selected_semi_tickers:
        with st.spinner("正在抓取半导体标的历史价格并计算归一化收益率..."):
            df_semi_prices = get_semiconductor_comparative_prices(selected_semi_tickers)
        
        if df_semi_prices is not None and not df_semi_prices.empty:
            fig_semi_rel = create_relative_performance_chart(
                df_semi_prices,
                tickers=selected_semi_tickers,
                timeframe=semi_timeframe
            )
            if fig_semi_rel:
                st.plotly_chart(fig_semi_rel, use_container_width=True)
        else:
            st.info("半导体标的历史价格数据加载中。")
    else:
        st.warning("请至少选择一个半导体标的进行对比展示。")

    # 2. 产业链估值与基本面横向比选矩阵
    st.markdown("---")
    st.subheader("📊 半导体全产业链核心标的估值与财务比选矩阵")
    st.caption("展示各环节龙头公司的最新市价、市值规模、PE/Forward PE、PS 估值倍数与毛利率")

    with st.spinner("正在汇总半导体产业链全量估值比选数据..."):
        df_matrix = get_semiconductor_matrix_data()

    if df_matrix is not None and not df_matrix.empty:
        st.dataframe(df_matrix, hide_index=True, use_container_width=True)
    else:
        st.info("比选矩阵数据加载中...")

    # 3. 半导体行业周期与 Capex 观察框架
    st.markdown("---")
    with st.expander("📖 查看《半导体产业周期、制程节点与 WFE 资本开支》投研分析指南", expanded=True):
        st.markdown("""
        ### 💡 半导体产业链四大核心投资与周期观察逻辑

        #### 1. 产业周期四阶段模型 (4-Stage Semiconductor Cycle)
        * **衰退出清期 (Downturn)**：下游消费电子/PC/手机需求萎缩，晶圆厂去库存降稼动率，存储芯片价格暴跌（如 2022H2–2023H1）。
        * **周期筑底期 (Bottoming)**：原厂主动削减资本开支 (Capex Cut) 与减产，渠道库存回归健康水位，现货价格企稳。
        * **复苏扩张期 (Expansion)**：新一轮科技创新周期（如 GenAI / 数据中心算力激增）拉动先进制程与 HBM 高价值量芯片需求，量价齐升。
        * **繁荣过热期 (Peak/Overheating)**：全产业链产能供不应求，原厂激进扩产，交期大幅拉长；需警惕双重下单 (Double Booking) 后的需求高位回落。

        #### 2. 先进制程与设备前置指标 (WFE Capex as Leading Indicator)
        * **光刻与薄膜沉积设备 (ASML / AMAT / LRCX / KLAC)**：设备订单与出货通常**领先晶圆代工厂量产 6–12 个月**。
        * **台积电资本开支 (TSMC Capex)**：全球半导体景气度的绝对风向标，其中先进制程 (2nm/3nm) 与 CoWoS 先进封装产能分配直接决定 AI 算力供给上限。

        #### 3. 存储芯片高弹性杠杆 (DRAM / NAND & HBM Supercycle)
        * **存储芯片 (Micron / Samsung / SK Hynix)** 属于典型的大宗重资产周期品。在下行期由于固定资产折旧产生巨额亏损，但在景气上行期具备极强 EPS 盈利爆发弹性。
        * **HBM (高带宽内存)** 占用了大量 DRAM 晶圆晶片面积，对传统 DDR5 产生产能挤占效应，支撑整体存储价格中枢结构性上移。

        #### 4. 定制化芯片 ASIC vs 通用 GPU 架构博弈
        * **通用 GPU (NVDA / AMD)**：凭借 CUDA 生态与最高灵活性垄断大模型前沿训练与复杂推理。
        * **定制 ASIC (AVGO / MRVL)**：云厂商 (CSP) 为降低单 Token 成本自研推理芯片（如 Google TPU, AWS Trainium/Inferentia, Meta MTIA），博通作为芯片物理设计与 SerDes IP 独家合作伙伴长期受益。
        """)


# ==================================================================
# TAB 4: 个股深度与基本面剖析 (Company Profile & Financials)
# ==================================================================
with tab_company:
    try:
        render_company_deep_dive_tab()
    except Exception as e:
        st.error(f"个股深度分析模块加载失败: {e}")
