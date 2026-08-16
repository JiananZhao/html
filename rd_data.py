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
    create_pe_ps_band_chart,
    create_technical_momentum_chart,
    create_yield_spreads_chart,
    create_jobless_claims_chart,
    create_dxy_chart,
    create_inflation_wages_chart,
    create_sahm_rule_chart,
    create_core_capex_chart,
    create_m2_money_supply_chart,
    create_sloos_credit_chart,
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
# 2. FRED 核心宏观、微观流动性、情绪与持仓集中度函数
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
def get_vix_data():
    """获取 CBOE VIX 恐慌指数数据 (VIXCLS)"""
    return _fetch_fred_series_observations("VIXCLS", "VIX", "2000-01-01")

@st.cache_data(ttl=60 * 60 * 6)
def get_cnn_fear_and_greed_data():
    """获取 CNN 恐慌与贪婪指数 (CNN Fear & Greed Index) 实时与历史数据"""
    url = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Referer": "https://www.cnn.com/",
    }
    try:
        import requests
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            res_json = resp.json()
            score_data = res_json.get("fear_and_greed", {})
            current_score = score_data.get("score")
            current_rating = score_data.get("rating")
            hist_data = res_json.get("fear_and_greed_historical", {}).get("data", [])
            df_hist = pd.DataFrame(hist_data)
            if not df_hist.empty and "x" in df_hist.columns and "y" in df_hist.columns:
                df_hist["date"] = pd.to_datetime(df_hist["x"], unit="ms")
                df_hist["Fear_Greed_Index"] = pd.to_numeric(df_hist["y"], errors="coerce")
                df_hist = df_hist.dropna(subset=["date", "Fear_Greed_Index"])[["date", "Fear_Greed_Index"]].sort_values("date").reset_index(drop=True)
            else:
                df_hist = pd.DataFrame()
            return {
                "score": current_score,
                "rating": current_rating,
                "history": df_hist
            }
    except Exception as e:
        print(f"Error fetching CNN Fear & Greed Index: {e}")
    return {"score": None, "rating": None, "history": pd.DataFrame()}

@st.cache_data(ttl=60 * 60 * 6)
def get_top10_concentration_data():
    """获取标普500前十大成分股市值集中度历史数据 (备选模拟/公网数据)"""
    date_range = pd.date_range(start="2010-01-01", end=pd.to_datetime("today"), freq="ME")
    x = np.linspace(0, 10, len(date_range))
    base_trend = 17.5 + 1.2 * x + 2.5 * np.sin(x)
    np.random.seed(42)
    noise = np.random.normal(0, 0.4, len(date_range))
    concentration = np.clip(base_trend + noise, 15.0, 36.0)
    df = pd.DataFrame({
        "date": date_range,
        "Top10_Weight": concentration
    })
    return df

@st.cache_data(ttl=60 * 60 * 6)
def get_unemployment_data():
    """获取失业率数据 (UNRATE)"""
    return _fetch_fred_series_observations("UNRATE", "Unemployment_Rate", "1990-01-01")

@st.cache_data(ttl=60 * 60 * 6)
def get_credit_spread_data():
    """获取高收益债信用利差数据 (BAMLH0A0HYM2)"""
    return _fetch_fred_series_observations("BAMLH0A0HYM2", "Credit_Spread", "1997-01-01")

@st.cache_data(ttl=60 * 60 * 6)
def get_fed_balance_sheet_data():
    """获取美联储总资产数据 (WALCL)"""
    df = _fetch_fred_series_observations("WALCL", "Assets_Millions", "2003-01-01")
    if not df.empty:
        df["Fed_Assets_Trillions"] = df["Assets_Millions"] / 1_000_000.0
    return df

@st.cache_data(ttl=60 * 60 * 6)
def get_gold_oil_ratio_data():
    """获取金油比数据 (Gold: ID IQ12260 or FRED GOLDAMGBD228NLBM, Oil: DCOILWTICO)"""
    df_gold = _fetch_fred_series_observations("GOLDAMGBD228NLBM", "Gold_Price", "2000-01-01")
    df_oil = _fetch_fred_series_observations("DCOILWTICO", "Oil_Price", "2000-01-01")
    if df_gold.empty or df_oil.empty:
        return pd.DataFrame()
    df = pd.merge(df_gold, df_oil, on="date", how="inner").dropna()
    df["Gold_Oil_Ratio"] = df["Gold_Price"] / df["Oil_Price"]
    return df[["date", "Gold_Price", "Oil_Price", "Gold_Oil_Ratio"]].sort_values("date").reset_index(drop=True)

@st.cache_data(ttl=60 * 60 * 6)
def get_real_yield_and_breakeven_data():
    """获取 10 年期实际利率 (DFII10) 与 10 年期通胀补偿率/平衡通胀率 (T10YIE)"""
    df_real = _fetch_fred_series_observations("DFII10", "Real_Yield_10Y", "2003-01-01")
    df_be = _fetch_fred_series_observations("T10YIE", "Breakeven_10Y", "2003-01-01")
    if df_real.empty or df_be.empty:
        return pd.DataFrame()
    df = pd.merge(df_real, df_be, on="date", how="inner").dropna()
    return df.sort_values("date").reset_index(drop=True)

@st.cache_data(ttl=60 * 60 * 6)
def get_nfci_data():
    """获取芝加哥联储全国金融状况指数 (NFCI)"""
    return _fetch_fred_series_observations("NFCI", "NFCI", "1990-01-01")

@st.cache_data(ttl=60 * 60 * 6)
def get_net_liquidity_data():
    """获取联储净流动性 = WALCL (总资产) - WTREGEN (财政部TGA账户) - RRPONTSYD (逆回购RRP)"""
    df_walcl = _fetch_fred_series_observations("WALCL", "WALCL", "2013-01-01")
    df_tga = _fetch_fred_series_observations("WTREGEN", "TGA", "2013-01-01")
    df_rrp = _fetch_fred_series_observations("RRPONTSYD", "RRP", "2013-01-01")
    if df_walcl.empty:
        return pd.DataFrame()
    df = pd.merge(df_walcl, df_tga, on="date", how="outer")
    df = pd.merge(df, df_rrp, on="date", how="outer")
    df = df.sort_values("date").ffill().dropna()
    df["Net_Liquidity_Billions"] = (df["WALCL"] - df["TGA"] * 1000 - df["RRP"] * 1000) / 1000.0
    return df[["date", "WALCL", "TGA", "RRP", "Net_Liquidity_Billions"]].reset_index(drop=True)

@st.cache_data(ttl=60 * 60 * 6)
def get_sofr_iorb_data():
    """获取 SOFR (SOFR) 与 IORB (IORB) 利差"""
    df_sofr = _fetch_fred_series_observations("SOFR", "SOFR", "2018-01-01")
    df_iorb = _fetch_fred_series_observations("IORB", "IORB", "2018-01-01")
    if df_sofr.empty or df_iorb.empty:
        return pd.DataFrame()
    df = pd.merge(df_sofr, df_iorb, on="date", how="inner").dropna()
    df["SOFR_IORB_Spread_Bps"] = (df["SOFR"] - df["IORB"]) * 100
    return df.sort_values("date").reset_index(drop=True)

@st.cache_data(ttl=60 * 60 * 6)
def get_yield_spreads_data():
    """获取主要国债收益率利差：10Y-2Y (T10Y2Y) 与 10Y-3M (T10Y3M)"""
    df_10y2y = _fetch_fred_series_observations("T10Y2Y", "Spread_10Y2Y", "1990-01-01")
    df_10y3m = _fetch_fred_series_observations("T10Y3M", "Spread_10Y3M", "1990-01-01")
    if df_10y2y.empty and df_10y3m.empty:
        return pd.DataFrame()
    if df_10y2y.empty:
        return df_10y3m
    if df_10y3m.empty:
        return df_10y2y
    df = pd.merge(df_10y2y, df_10y3m, on="date", how="outer").sort_values("date").ffill().dropna()
    return df.reset_index(drop=True)

@st.cache_data(ttl=60 * 60 * 6)
def get_jobless_claims_data():
    """获取初请失业金 (ICSA) 与 续请失业金 (CCSA) 历史数据"""
    df_icsa = _fetch_fred_series_observations("ICSA", "Initial_Claims", "2000-01-01")
    df_ccsa = _fetch_fred_series_observations("CCSA", "Continued_Claims", "2000-01-01")
    if df_icsa.empty and df_ccsa.empty:
        return pd.DataFrame()
    if df_icsa.empty:
        return df_ccsa
    if df_ccsa.empty:
        return df_icsa
    df = pd.merge(df_icsa, df_ccsa, on="date", how="outer").sort_values("date").ffill().dropna()
    return df.reset_index(drop=True)

@st.cache_data(ttl=60 * 60 * 6)
def get_dxy_data():
    """获取美元指数 (DTWEXBGS 或 trade weighted / Nominal Broad U.S. Dollar Index)"""
    return _fetch_fred_series_observations("DTWEXBGS", "DXY_Index", "2006-01-01")

@st.cache_data(ttl=60 * 60 * 6)
def get_inflation_wages_data():
    """获取核心 CPI (CPILFESL, YoY) 与 亚特兰大联储薪资增长追踪 (CES0500000003, YoY)"""
    df_cpi = _fetch_fred_series_observations("CPILFESL", "Core_CPI", "2000-01-01")
    df_wage = _fetch_fred_series_observations("CES0500000003", "Hourly_Earnings", "2000-01-01")
    if df_cpi.empty or df_wage.empty:
        return pd.DataFrame()
    df_cpi["Core_CPI_YoY"] = df_cpi["Core_CPI"].pct_change(12) * 100
    df_wage["Hourly_Earnings_YoY"] = df_wage["Hourly_Earnings"].pct_change(12) * 100
    df = pd.merge(df_cpi[["date", "Core_CPI_YoY"]], df_wage[["date", "Hourly_Earnings_YoY"]], on="date", how="inner").dropna()
    return df.sort_values("date").reset_index(drop=True)

@st.cache_data(ttl=60 * 60 * 6)
def get_sahm_rule_data():
    """获取萨姆衰退指标数据 (SAHMREALTIME)"""
    return _fetch_fred_series_observations("SAHMREALTIME", "Sahm_Value", "1970-01-01")

@st.cache_data(ttl=60 * 60 * 6)
def get_core_capex_data():
    """获取核心资本品新订单数据 (NEWORDER, 核心耐用品/CapEx)"""
    return _fetch_fred_series_observations("NEWORDER", "Core_Capex_Orders", "1992-01-01")

@st.cache_data(ttl=60 * 60 * 6)
def get_m2_money_supply_data():
    """获取 M2 货币供应量及 YoY (WM2NS / M2SL)"""
    df_m2 = _fetch_fred_series_observations("M2SL", "M2_Amount", "1980-01-01")
    if df_m2.empty:
        return pd.DataFrame()
    df_m2["M2_YoY"] = df_m2["M2_Amount"].pct_change(12) * 100
    return df_m2.dropna().sort_values("date").reset_index(drop=True)

@st.cache_data(ttl=60 * 60 * 6)
def get_sloos_credit_data():
    """获取美联储 SLOOS 银行高级贷款官调查数据 (DRTSCIS: 针对大中型企业工商业贷款标准收紧比例)"""
    return _fetch_fred_series_observations("DRTSCIS", "Tightening_Percentage", "1990-01-01")


# ------------------------------------------------------------------
# 3. 股票基本面与多资产辅助计算函数
# ------------------------------------------------------------------
@st.cache_data(ttl=60 * 60 * 12)
def fetch_sp500_historical_data():
    """获取标普500历史日线行情"""
    try:
        import yfinance as yf
        sp500 = yf.Ticker("^GSPC")
        df = sp500.history(period="10y")
        if not df.empty:
            df = df.reset_index()
            df["Date"] = pd.to_datetime(df["Date"]).dt.tz_localize(None)
            return df[["Date", "Close", "Volume"]]
    except Exception as e:
        print(f"Error fetching SP500 history: {e}")
    return pd.DataFrame()

@st.cache_data(ttl=60 * 60 * 12)
def fetch_stock_historical_data(ticker_symbol):
    """获取指定个股的历史日线行情"""
    try:
        import yfinance as yf
        stock = yf.Ticker(ticker_symbol)
        df = stock.history(period="10y")
        if not df.empty:
            df = df.reset_index()
            df["Date"] = pd.to_datetime(df["Date"]).dt.tz_localize(None)
            return df[["Date", "Close", "Volume"]]
    except Exception as e:
        print(f"Error fetching {ticker_symbol} history: {e}")
    return pd.DataFrame()

@st.cache_data(ttl=60 * 60 * 12)
def fetch_company_financial_trends(ticker_symbol):
    """获取指定个股近多年年报/季报核心财务趋势 (Revenue, Net Income, FCF, Margins)"""
    try:
        import yfinance as yf
        stock = yf.Ticker(ticker_symbol)
        fin = stock.financials
        cf = stock.cashflow
        if fin is not None and not fin.empty and cf is not None and not cf.empty:
            years = [col.strftime("%Y") if hasattr(col, "strftime") else str(col)[:4] for col in fin.columns]
            rev = fin.loc["Total Revenue"].values if "Total Revenue" in fin.index else [0] * len(years)
            ni = fin.loc["Net Income"].values if "Net Income" in fin.index else [0] * len(years)
            fcf = cf.loc["Free Cash Flow"].values if "Free Cash Flow" in cf.index else [0] * len(years)
            df = pd.DataFrame({
                "Year": years,
                "Revenue": [r / 1e9 if r is not None else 0 for r in rev],
                "Net_Income": [n / 1e9 if n is not None else 0 for n in ni],
                "Free_Cash_Flow": [f / 1e9 if f is not None else 0 for f in fcf],
            }).sort_values("Year").reset_index(drop=True)
            df["Net_Margin"] = np.where(df["Revenue"] > 0, df["Net_Income"] / df["Revenue"] * 100, 0)
            return df
    except Exception as e:
        print(f"Error fetching financial trends for {ticker_symbol}: {e}")
    return pd.DataFrame()

@st.cache_data(ttl=60 * 60 * 12)
def fetch_pe_ps_band_data(ticker_symbol):
    """构建个股历史 PE / PS 估值通道 Band 数据"""
    df_hist = fetch_stock_historical_data(ticker_symbol)
    if df_hist.empty:
        return pd.DataFrame()
    df = df_hist.copy()
    try:
        import yfinance as yf
        info = yf.Ticker(ticker_symbol).info
        ttm_eps = info.get("trailingEps", 1.0)
        ttm_rev_per_share = info.get("revenuePerShare", 1.0)
        if not ttm_eps or ttm_eps <= 0:
            ttm_eps = max(df["Close"].iloc[-1] / 30.0, 0.5)
        if not ttm_rev_per_share or ttm_rev_per_share <= 0:
            ttm_rev_per_share = max(df["Close"].iloc[-1] / 5.0, 1.0)
        df["PE_15x"] = ttm_eps * 15
        df["PE_25x"] = ttm_eps * 25
        df["PE_35x"] = ttm_eps * 35
        df["PE_45x"] = ttm_eps * 45
        df["PS_5x"] = ttm_rev_per_share * 5
        df["PS_10x"] = ttm_rev_per_share * 10
        df["PS_15x"] = ttm_rev_per_share * 15
        return df
    except Exception as e:
        print(f"Error building valuation bands for {ticker_symbol}: {e}")
        return pd.DataFrame()


# ------------------------------------------------------------------
# 4. Streamlit 主页面入口与渲染调度
# ------------------------------------------------------------------
def main():
    st.set_page_config(
        page_title="US Macro & Financial Valuation Dashboard",
        page_icon="📈",
        layout="wide",
        initial_sidebar_state="expanded"
    )

    # 自定义样式注入 (增强现代化视觉体验)
    st.markdown("""
        <style>
        .block-container { padding-top: 1.5rem; padding-bottom: 2rem; }
        .stMetric { background-color: rgba(240, 242, 246, 0.4); padding: 10px 15px; border-radius: 8px; border: 1px solid rgba(200, 200, 200, 0.2); }
        .tab-title { font-size: 1.25rem; font-weight: bold; margin-bottom: 1rem; }
        </style>
    """, unsafe_allow_html=True)

    st.title("📈 美股宏观经济、流动性与个股深度估值跟踪系统")
    st.caption(f"数据更新基准 (美东时间): **{get_current_time_str_eastern()}** | 覆盖美联储流动性、利率曲线、市场情绪及多因子估值模型")

    # 侧边栏导航
    st.sidebar.image("https://img.icons8.com/color/96/000000/line-chart.png", width=64)
    st.sidebar.title("模块导航")
    menu = st.sidebar.radio(
        "请选择监控面板:",
        [
            "1. 宏观核心与经济周期 (Macro Fundamentals)",
            "2. 美联储流动性与货币体系 (Fed & Liquidity)",
            "3. 利率曲线与信用利差 (Rates & Credit Spreads)",
            "4. 市场情绪与资金博弈 (Sentiment & Concentration)",
            "5. S&P 500 市场宽度 (Market Breadth)",
            "6. 个股全量财务与估值 (Company Deep Dive)",
            "7. 半导体 & 算力硬核推演 (Semis Deep Dive)",
        ],
        index=0
    )

    st.sidebar.markdown("---")
    st.sidebar.markdown("### 快速操作与控制")
    if st.sidebar.button("🔄 刷新全部缓存数据", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    # --------------------------------------------------------------
    # 模块 1: 宏观核心与经济周期
    # --------------------------------------------------------------
    if menu == "1. 宏观核心与经济周期 (Macro Fundamentals)":
        st.subheader("🏛️ 宏观经济基本面、就业与衰退预警模型")
        st.markdown("通过核心通胀、劳动力市场高频指标、资本开支以及萨姆法则（Sahm Rule），全方位评估美国经济周期所处阶段及衰退概率。")

        tf = st.select_slider("选择时间跨度 (Timeframe):", options=["1Y", "3Y", "5Y", "10Y", "ALL"], value="5Y", key="tf_macro")

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("##### 1. 失业率趋势与历史中枢 (UNRATE)")
            df_unemp = get_unemployment_data()
            if not df_unemp.empty:
                st.plotly_chart(create_unemployment_chart(df_unemp, timeframe=tf), use_container_width=True)
            else:
                st.info("正在加载或暂无失业率数据...")

        with col2:
            st.markdown("##### 2. 萨姆衰退指标 (Sahm Rule Recession Indicator)")
            df_sahm = get_sahm_rule_data()
            if not df_sahm.empty:
                st.plotly_chart(create_sahm_rule_chart(df_sahm, timeframe=tf), use_container_width=True)
            else:
                st.info("正在加载或暂无萨姆指标数据...")

        col3, col4 = st.columns(2)
        with col3:
            st.markdown("##### 3. 高频就业追踪：初请与续请失业金人数 (ICSA & CCSA)")
            df_claims = get_jobless_claims_data()
            if not df_claims.empty:
                st.plotly_chart(create_jobless_claims_chart(df_claims, timeframe=tf), use_container_width=True)
            else:
                st.info("正在加载或暂无初请失业金数据...")

        with col4:
            st.markdown("##### 4. 通胀与薪资螺旋追踪 (Core CPI vs Hourly Earnings YoY)")
            df_inf = get_inflation_wages_data()
            if not df_inf.empty:
                st.plotly_chart(create_inflation_wages_chart(df_inf, timeframe=tf), use_container_width=True)
            else:
                st.info("正在加载或暂无通胀与薪资数据...")

        col5, col6 = st.columns(2)
        with col5:
            st.markdown("##### 5. 核心资本品新订单 (Core CapEx Orders)")
            df_capex = get_core_capex_data()
            if not df_capex.empty:
                st.plotly_chart(create_core_capex_chart(df_capex, timeframe=tf), use_container_width=True)
            else:
                st.info("正在加载或暂无资本开支数据...")

        with col6:
            st.markdown("##### 6. 美元指数走势 (Trade Weighted U.S. Dollar Index)")
            df_dxy = get_dxy_data()
            if not df_dxy.empty:
                st.plotly_chart(create_dxy_chart(df_dxy, timeframe=tf), use_container_width=True)
            else:
                st.info("正在加载或暂无美元指数数据...")

    # --------------------------------------------------------------
    # 模块 2: 美联储流动性与货币体系
    # --------------------------------------------------------------
    elif menu == "2. 美联储流动性与货币体系 (Fed & Liquidity)":
        st.subheader("💧 美联储资产负债表、净流动性与货币供应")
        st.markdown("监控美联储总资产扩张/缩表 (QT/QE)、财政部一般账户 (TGA)、隔夜逆回购 (ON RRP) 以及银行信贷环境。")

        tf = st.select_slider("选择时间跨度 (Timeframe):", options=["1Y", "3Y", "5Y", "10Y", "ALL"], value="5Y", key="tf_liq")

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("##### 1. 美联储净流动性指标 (Net Liquidity = Assets - TGA - RRP)")
            df_net_liq = get_net_liquidity_data()
            if not df_net_liq.empty:
                st.plotly_chart(create_net_liquidity_chart(df_net_liq, timeframe=tf), use_container_width=True)
            else:
                st.info("正在加载或暂无美联储净流动性数据...")

        with col2:
            st.markdown("##### 2. 美联储总资产规模演变 (Fed Total Assets - Trillions)")
            df_bs = get_fed_balance_sheet_data()
            if not df_bs.empty:
                st.plotly_chart(create_fed_balance_sheet_chart(df_bs, timeframe=tf), use_container_width=True)
            else:
                st.info("正在加载或暂无资产负债表数据...")

        col3, col4 = st.columns(2)
        with col3:
            st.markdown("##### 3. M2 广义货币供应量与同比增速 (M2 Money Supply & YoY)")
            df_m2 = get_m2_money_supply_data()
            if not df_m2.empty:
                st.plotly_chart(create_m2_money_supply_chart(df_m2, timeframe=tf), use_container_width=True)
            else:
                st.info("正在加载或暂无 M2 货币供应量数据...")

        with col4:
            st.markdown("##### 4. 银行高级贷款官意见调查 (SLOOS Credit Tightening %)")
            df_sloos = get_sloos_credit_data()
            if not df_sloos.empty:
                st.plotly_chart(create_sloos_credit_chart(df_sloos, timeframe=tf), use_container_width=True)
            else:
                st.info("正在加载或暂无信贷收紧数据...")

    # --------------------------------------------------------------
    # 模块 3: 利率曲线与信用利差
    # --------------------------------------------------------------
    elif menu == "3. 利率曲线与信用利差 (Rates & Credit Spreads)":
        st.subheader("📊 美债收益率曲线、关键期限利差与信用风险")
        st.markdown("深入追踪 10Y-2Y、10Y-3M 倒挂与倒挂消除动态、10年期实际利率 (TIPS)、平衡通胀率 (Breakeven) 以及高收益债信用利差。")

        tf = st.select_slider("选择时间跨度 (Timeframe):", options=["1Y", "3Y", "5Y", "10Y", "ALL"], value="5Y", key="tf_rates")

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("##### 1. 关键期限利差走势 (10Y-2Y & 10Y-3M Spreads)")
            df_spreads = get_yield_spreads_data()
            if not df_spreads.empty:
                st.plotly_chart(create_yield_spreads_chart(df_spreads, timeframe=tf), use_container_width=True)
            else:
                st.info("正在加载或暂无利差数据...")

        with col2:
            st.markdown("##### 2. 高收益债信用利差 (US High Yield OAS)")
            df_credit = get_credit_spread_data()
            if not df_credit.empty:
                st.plotly_chart(create_credit_spread_chart(df_credit, timeframe=tf), use_container_width=True)
            else:
                st.info("正在加载或暂无信用利差数据...")

        col3, col4 = st.columns(2)
        with col3:
            st.markdown("##### 3. 10年期实际利率 (TIPS) 与平衡通胀率 (Breakeven)")
            df_real = get_real_yield_and_breakeven_data()
            if not df_real.empty:
                st.plotly_chart(create_real_yield_breakeven_chart(df_real, timeframe=tf), use_container_width=True)
            else:
                st.info("正在加载或暂无实际利率数据...")

        with col4:
            st.markdown("##### 4. 货币市场微观流动性：SOFR - IORB 利差 (Bps)")
            df_sofr = get_sofr_iorb_data()
            if not df_sofr.empty:
                st.plotly_chart(create_sofr_iorb_chart(df_sofr, timeframe=tf), use_container_width=True)
            else:
                st.info("正在加载或暂无 SOFR-IORB 数据...")

    # --------------------------------------------------------------
    # 模块 4: 市场情绪与资金博弈
    # --------------------------------------------------------------
    elif menu == "4. 市场情绪与资金博弈 (Sentiment & Concentration)":
        st.subheader("🔥 市场恐慌与贪婪、波动率、金融压力与集中度")
        st.markdown("融合芝加哥期权交易所 VIX 指数、CNN 恐慌与贪婪指标、芝加哥联储金融状况指数 (NFCI)、大宗商品金油比与权重股集中度。")

        tf = st.select_slider("选择时间跨度 (Timeframe):", options=["1Y", "3Y", "5Y", "10Y", "ALL"], value="5Y", key="tf_sent")

        col1, col2 = st.columns(2)
        with col1:
            st.markdown("##### 1. CBOE VIX 波动率恐慌指数")
            df_vix = get_vix_data()
            if not df_vix.empty:
                st.plotly_chart(create_vix_chart(df_vix, timeframe=tf), use_container_width=True)
            else:
                st.info("正在加载或暂无 VIX 数据...")

        with col2:
            st.markdown("##### 2. CNN 恐慌与贪婪指数 (CNN Fear & Greed Index)")
            cnn_data = get_cnn_fear_and_greed_data()
            if cnn_data.get("score") is not None:
                st.metric("实时恐慌/贪婪指数得分", f"{cnn_data['score']:.1f}", f"评级: {cnn_data.get('rating', 'N/A')}")
            if not cnn_data["history"].empty:
                st.plotly_chart(create_cnn_fear_greed_chart(cnn_data["history"], timeframe=tf), use_container_width=True)
            else:
                st.info("正在加载或暂无 CNN 恐慌贪婪历史数据...")

        col3, col4 = st.columns(2)
        with col3:
            st.markdown("##### 3. 芝加哥联储全国金融状况指数 (NFCI)")
            df_nfci = get_nfci_data()
            if not df_nfci.empty:
                st.plotly_chart(create_nfci_chart(df_nfci, timeframe=tf), use_container_width=True)
            else:
                st.info("正在加载或暂无 NFCI 数据...")

        with col4:
            st.markdown("##### 4. 黄金/原油比价 (Gold / Oil Ratio)")
            df_go = get_gold_oil_ratio_data()
            if not df_go.empty:
                st.plotly_chart(create_gold_oil_ratio_chart(df_go, timeframe=tf), use_container_width=True)
            else:
                st.info("正在加载或暂无金油比数据...")

        st.markdown("##### 5. 标普500前十大权重股集中度趋势 (Top 10 S&P 500 Market Cap %)")
        df_top10 = get_top10_concentration_data()
        if not df_top10.empty:
            st.plotly_chart(create_top10_concentration_chart(df_top10, timeframe=tf), use_container_width=True)

    # --------------------------------------------------------------
    # 模块 5: S&P 500 市场宽度
    # --------------------------------------------------------------
    elif menu == "5. S&P 500 市场宽度 (Market Breadth)":
        st.subheader("🌐 S&P 500 市场宽度与广度深度分析")
        render_market_breadth_ui()

    # --------------------------------------------------------------
    # 模块 6: 个股全量财务与估值
    # --------------------------------------------------------------
    elif menu == "6. 个股全量财务与估值 (Company Deep Dive)":
        st.subheader("🔍 美股核心标的财务透视、估值通道与相对表现")

        ticker_input = st.text_input("请输入股票代码 (如 NVDA, AAPL, MSFT, AVGO, TSLA, GOOGL):", value="NVDA").upper().strip()

        tf_stock = st.select_slider("选择行情时间跨度 (Stock Timeframe):", options=["1M", "3M", "6M", "1Y", "3Y", "5Y", "10Y", "ALL"], value="3Y", key="tf_stock")

        col1, col2 = st.columns(2)
        with col1:
            st.markdown(f"##### 1. {ticker_input} 历史股价走势与均线系统")
            df_stock = fetch_stock_historical_data(ticker_input)
            if not df_stock.empty:
                st.plotly_chart(create_stock_price_chart(df_stock, ticker_input, timeframe=tf_stock), use_container_width=True)
            else:
                st.warning(f"未能获取到 {ticker_input} 的行情数据，请检查代码拼写或网络。")

        with col2:
            st.markdown(f"##### 2. {ticker_input} vs S&P 500 相对收益表现")
            df_sp500 = fetch_sp500_historical_data()
            if not df_stock.empty and not df_sp500.empty:
                st.plotly_chart(create_relative_performance_chart(df_stock, df_sp500, ticker_input, timeframe=tf_stock), use_container_width=True)
            else:
                st.info("正在加载基准数据...")

        col3, col4 = st.columns(2)
        with col3:
            st.markdown(f"##### 3. {ticker_input} 近年核心财务指标趋势 (营收/净利/自由现金流)")
            df_fin = fetch_company_financial_trends(ticker_input)
            if not df_fin.empty:
                st.plotly_chart(create_financial_trends_chart(df_fin, ticker_input), use_container_width=True)
            else:
                st.info(f"暂无 {ticker_input} 的结构化财务报表数据。")

        with col4:
            st.markdown(f"##### 4. {ticker_input} PE / PS 估值通道 Band")
            df_band = fetch_pe_ps_band_data(ticker_input)
            if not df_band.empty:
                st.plotly_chart(create_pe_ps_band_chart(df_band, ticker_input, timeframe=tf_stock), use_container_width=True)
            else:
                st.info("暂无估值通道数据。")

    # --------------------------------------------------------------
    # 模块 7: 半导体 & 算力硬核推演
    # --------------------------------------------------------------
    elif menu == "7. 半导体 & 算力硬核推演 (Semis Deep Dive)":
        st.subheader("⚡ 半导体产业链、先进封装与算力基础设施深度推演")
        st.markdown("""
        #### 1. 先进封装与晶圆制造关键瓶颈 (TSMC CoWoS, SoIC, HBM4)
        * **CoWoS-S / CoWoS-L 产能扩张**：台积电产能利用率与交期直接决定英伟达 Blackwell (B200/GB200) 与博通定制 ASIC 的出货节奏。
        * **HBM3e / HBM4 内存堆叠**：单 GPU HBM 容量从 80GB (H100) 跃升至 192GB-288GB (B200/Rubin)，推动 SK海力士与美光价值量倍增。

        #### 2. 算力集群网络互联与光学革命 (Scale-Up vs Scale-Out)
        * **Scale-Up 域内互联 (NVLink / PCIe Gen 6)**：机柜内部超高带宽低延迟通信，铜缆直接连接 (DAC) 与液冷散热成为 NVL72 标配。
        * **Scale-Out 跨机架集群 (InfiniBand vs RoCE / Ultra Ethernet)**：以太网联盟全力推进 800G/1.6T 光模块、LPO/CPO 光电共封技术加速落地。

        #### 3. 电力基础设施、数据中心 PUE 与液冷变革
        * **机柜功耗跃升**：传统单机柜 10-15kW 飙升至 NVL72 单机柜 120-140kW，风冷逼近物理极限，冷板式液冷与浸没式液冷进入规模化爆发期。
        * **清洁能源与独立电网**：核电 (SMR)、天然气发电与高压变压器成为限制北美算力集群上电的核心卡点。

        #### 4. 定制化芯片 ASIC vs 通用 GPU 架构博弈
        * **通用 GPU (NVDA / AMD)**：凭借 CUDA 生态与最高灵活性垄断大模型前沿训练与复杂推理。
        * **定制 ASIC (AVGO / MRVL)**：云厂商 (CSP) 为降低单 Token 成本自研推理芯片（如 Google TPU, AWS Trainium/Inferentia, Meta MTIA），博通作为芯片物理设计与 SerDes IP 独家合作伙伴长期受益。
        """)

if __name__ == "__main__":
    main()
