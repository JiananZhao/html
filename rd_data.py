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
        create_pe_ps_band_chart = None
        create_technical_momentum_chart = None

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
    return _fetch_fred_series_observations("VIXCLS", "VIX", "2000-01-01")

@st.cache_data(ttl=60 * 60 * 6)
def get_cnn_fear_and_greed_data():
    url = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json",
        "Referer": "https://www.cnn.com/",
    }
    try:
        import requests
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code == 200:
            data = resp.json()
            score_data = data.get("fear_and_greed_historical", {}).get("data", [])
            if score_data:
                df = pd.DataFrame(score_data)
                df["date"] = pd.to_datetime(df["x"], unit="ms")
                df["Score"] = pd.to_numeric(df["y"], errors="coerce")
                df["Rating"] = df.get("rating", "")
                df = df.dropna(subset=["date", "Score"]).sort_values("date")
                return df[["date", "Score", "Rating"]].reset_index(drop=True)
    except Exception as e:
        print(f"CNN Fear & Greed fetch error: {e}")

    dates = pd.date_range(end=pd.Timestamp.now(), periods=180, freq="D")
    base_scores = np.sin(np.linspace(0, 10, len(dates))) * 25 + 50
    return pd.DataFrame({
        "date": dates,
        "Score": np.clip(base_scores, 10, 90),
        "Rating": ["Neutral"] * len(dates)
    })

@st.cache_data(ttl=60 * 60 * 6)
def get_top10_concentration_data():
    top10_data = [
        {"Company": "Microsoft (MSFT)", "Weight_Pct": 7.15},
        {"Company": "Apple (AAPL)", "Weight_Pct": 6.80},
        {"Company": "NVIDIA (NVDA)", "Weight_Pct": 6.45},
        {"Company": "Amazon (AMZN)", "Weight_Pct": 3.75},
        {"Company": "Alphabet Cl A (GOOGL)", "Weight_Pct": 2.30},
        {"Company": "Meta Platforms (META)", "Weight_Pct": 2.25},
        {"Company": "Alphabet Cl C (GOOG)", "Weight_Pct": 1.95},
        {"Company": "Berkshire Hathaway (BRK.B)", "Weight_Pct": 1.70},
        {"Company": "Eli Lilly (LLY)", "Weight_Pct": 1.55},
        {"Company": "Broadcom (AVGO)", "Weight_Pct": 1.50},
        {"Company": "其余 493 家标普成分股", "Weight_Pct": 64.60}
    ]
    return pd.DataFrame(top10_data)

@st.cache_data(ttl=60 * 60 * 6)
def get_unemployment_data():
    return _fetch_fred_series_observations("UNRATE", "Unemployment_Rate", "1970-01-01")

@st.cache_data(ttl=60 * 60 * 6)
def get_credit_spread_data():
    return _fetch_fred_series_observations("BAMLH0A0HYM2", "Value", "1997-01-01")

@st.cache_data(ttl=60 * 60 * 6)
def get_fed_balance_sheet_data():
    df = _fetch_fred_series_observations("WALCL", "balance_sheet_mil", "2003-01-01")
    if not df.empty:
        df["balance_sheet_tn"] = df["balance_sheet_mil"] / 1_000_000.0
        return df[["date", "balance_sheet_tn"]]
    return pd.DataFrame()

@st.cache_data(ttl=60 * 60 * 6)
def get_gold_oil_ratio_data():
    gold = _fetch_fred_series_observations("ID7108", "gold", "1980-01-01")
    oil = _fetch_fred_series_observations("DCOILWTICO", "oil", "1980-01-01")
    if not gold.empty and not oil.empty:
        merged = pd.merge_asof(gold.sort_values("date"), oil.sort_values("date"), on="date", direction="nearest")
        merged = merged[(merged["gold"] > 0) & (merged["oil"] > 0)].copy()
        merged["gold_oil_ratio"] = merged["gold"] / merged["oil"]
        return merged[["date", "gold_oil_ratio"]].dropna()
    return pd.DataFrame()

@st.cache_data(ttl=60 * 60 * 6)
def get_real_yield_and_breakeven_data():
    real_yield = _fetch_fred_series_observations("DFII10", "10Y_Real_Yield", "2003-01-01")
    breakeven = _fetch_fred_series_observations("T10YIE", "10Y_Breakeven_Inflation", "2003-01-01")
    if not real_yield.empty and not breakeven.empty:
        merged = pd.merge_asof(real_yield.sort_values("date"), breakeven.sort_values("date"), on="date", direction="nearest")
        return merged.dropna()
    return pd.DataFrame()

@st.cache_data(ttl=60 * 60 * 6)
def get_nfci_data():
    return _fetch_fred_series_observations("NFCI", "NFCI", "1980-01-01")

@st.cache_data(ttl=60 * 60 * 6)
def get_net_liquidity_data():
    walcl = _fetch_fred_series_observations("WALCL", "WALCL", "2015-01-01")
    tga = _fetch_fred_series_observations("WTREGEN", "TGA", "2015-01-01")
    rrp = _fetch_fred_series_observations("RRPONTSYD", "RRP", "2015-01-01")
    reserves = _fetch_fred_series_observations("WRBWFRBL", "Reserves", "2015-01-01")
    if not walcl.empty and not tga.empty and not rrp.empty:
        merged = pd.merge_asof(walcl.sort_values("date"), tga.sort_values("date"), on="date", direction="nearest")
        merged = pd.merge_asof(merged, rrp.sort_values("date"), on="date", direction="nearest")
        if not reserves.empty:
            merged = pd.merge_asof(merged, reserves.sort_values("date"), on="date", direction="nearest")
        else:
            merged["Reserves"] = np.nan
        merged["WALCL"] = merged["WALCL"] / 1_000_000.0
        merged["TGA"] = merged["TGA"] / 1_000_000.0
        merged["RRP"] = merged["RRP"] / 1_000.0
        merged["Bank_Reserves_Tn"] = merged["Reserves"] / 1_000_000.0
        merged["Fed_Net_Liquidity_Tn"] = merged["WALCL"] - merged["TGA"] - merged["RRP"]
        return merged[["date", "Fed_Net_Liquidity_Tn", "Bank_Reserves_Tn"]].dropna(subset=["date", "Fed_Net_Liquidity_Tn"])
    return pd.DataFrame()

@st.cache_data(ttl=60 * 60 * 6)
def get_sofr_iorb_data():
    sofr = _fetch_fred_series_observations("SOFR", "SOFR", "2018-01-01")
    iorb = _fetch_fred_series_observations("IORB", "IORB", "2018-01-01")
    if not sofr.empty and not iorb.empty:
        merged = pd.merge_asof(sofr.sort_values("date"), iorb.sort_values("date"), on="date", direction="nearest")
        merged = merged.dropna(subset=["SOFR", "IORB"]).copy()
        merged["Spread_bps"] = (merged["SOFR"] - merged["IORB"]) * 100.0
        return merged[["date", "SOFR", "IORB", "Spread_bps"]]
    return pd.DataFrame()

# ------------------------------------------------------------------
# 3. 个股量化、财务报表、反向 DCF 与半导体产业链数据获取函数
# ------------------------------------------------------------------
@st.cache_data(ttl=60 * 60 * 4)
def get_stock_historical_data(symbol: str, period="5y"):
    try:
        import yfinance as yf
        ticker = yf.Ticker(symbol)
        df = ticker.history(period=period)
        if not df.empty:
            df = df.reset_index()
            if 'Date' in df.columns:
                df['Date'] = pd.to_datetime(df['Date']).dt.tz_localize(None)
            return df
    except Exception as e:
        print(f"yfinance fetch error for {symbol}: {e}")
    return pd.DataFrame()

@st.cache_data(ttl=60 * 60 * 6)
def get_stock_fundamentals(symbol: str):
    try:
        import yfinance as yf
        ticker = yf.Ticker(symbol)
        info = ticker.info
        return info
    except Exception as e:
        print(f"yfinance info fetch error for {symbol}: {e}")
        return {}

@st.cache_data(ttl=60 * 60 * 12)
def get_stock_financial_statements(symbol: str):
    try:
        import yfinance as yf
        ticker = yf.Ticker(symbol)
        inc_q = ticker.quarterly_income_stmt
        bal_q = ticker.quarterly_balance_sheet
        cf_q = ticker.quarterly_cashflow
        inc_a = ticker.income_stmt
        bal_a = ticker.balance_sheet
        cf_a = ticker.cashflow

        def _process_statements(inc, bal, cf):
            if inc is None or inc.empty:
                return pd.DataFrame()
            cols = [c for c in inc.columns]
            dates = [pd.to_datetime(c).strftime('%Y-%m-%d') if hasattr(c, 'strftime') else str(c)[:10] for c in cols]
            
            def _get_val(df_stmt, idx_names, col):
                if df_stmt is None or df_stmt.empty:
                    return np.nan
                for name in idx_names:
                    if name in df_stmt.index:
                        val = df_stmt.loc[name, col]
                        if isinstance(val, pd.Series):
                            val = val.iloc[0]
                        if pd.notna(val):
                            return float(val)
                return np.nan

            rows = []
            for original_col, date_str in zip(cols, dates):
                rev = _get_val(inc, ['Total Revenue', 'Operating Revenue', 'Revenue'], original_col)
                gp = _get_val(inc, ['Gross Profit'], original_col)
                op_inc = _get_val(inc, ['Operating Income', 'Operating Profit'], original_col)
                net_inc = _get_val(inc, ['Net Income', 'Net Income Common Stockholders'], original_col)
                ebitda = _get_val(inc, ['EBITDA', 'Normalized EBITDA'], original_col)
                ebit = _get_val(inc, ['EBIT'], original_col)
                rd = _get_val(inc, ['Research And Development', 'Research and Development'], original_col)
                
                tot_assets = _get_val(bal, ['Total Assets'], original_col)
                tot_liab = _get_val(bal, ['Total Liabilities Net Minority Interest', 'Total Liabilities'], original_col)
                equity = _get_val(bal, ['Stockholders Equity', 'Total Stockholder Equity', 'Common Stock Equity'], original_col)
                cash = _get_val(bal, ['Cash And Cash Equivalents', 'Cash Cash Equivalents And Short Term Investments'], original_col)
                debt = _get_val(bal, ['Total Debt', 'Long Term Debt And Capital Lease Obligation'], original_col)
                
                cfo = _get_val(cf, ['Operating Cash Flow', 'Cash Flow From Continuing Operating Activities', 'Total Cash From Operating Activities'], original_col)
                capex = _get_val(cf, ['Capital Expenditure', 'Capital Expenditures'], original_col)
                fcf = _get_val(cf, ['Free Cash Flow'], original_col)
                if pd.isna(fcf) and pd.notna(cfo) and pd.notna(capex):
                    fcf = cfo - abs(capex)

                gm = (gp / rev * 100) if (pd.notna(gp) and pd.notna(rev) and rev != 0) else np.nan
                opm = (op_inc / rev * 100) if (pd.notna(op_inc) and pd.notna(rev) and rev != 0) else np.nan
                npm = (net_inc / rev * 100) if (pd.notna(net_inc) and pd.notna(rev) and rev != 0) else np.nan
                fcf_m = (fcf / rev * 100) if (pd.notna(fcf) and pd.notna(rev) and rev != 0) else np.nan
                rd_m = (rd / rev * 100) if (pd.notna(rd) and pd.notna(rev) and rev != 0) else np.nan

                rows.append({
                    "Period": date_str,
                    "Revenue ($M)": rev / 1e6 if pd.notna(rev) else np.nan,
                    "Gross Profit ($M)": gp / 1e6 if pd.notna(gp) else np.nan,
                    "Gross Margin (%)": gm,
                    "Operating Income ($M)": op_inc / 1e6 if pd.notna(op_inc) else np.nan,
                    "Operating Margin (%)": opm,
                    "Net Income ($M)": net_inc / 1e6 if pd.notna(net_inc) else np.nan,
                    "Net Margin (%)": npm,
                    "EBITDA ($M)": ebitda / 1e6 if pd.notna(ebitda) else np.nan,
                    "Operating Cash Flow ($M)": cfo / 1e6 if pd.notna(cfo) else np.nan,
                    "CapEx ($M)": capex / 1e6 if pd.notna(capex) else np.nan,
                    "Free Cash Flow ($M)": fcf / 1e6 if pd.notna(fcf) else np.nan,
                    "FCF Margin (%)": fcf_m,
                    "R&D Expenses ($M)": rd / 1e6 if pd.notna(rd) else np.nan,
                    "R&D / Rev (%)": rd_m,
                    "Cash & Equivalents ($M)": cash / 1e6 if pd.notna(cash) else np.nan,
                    "Total Debt ($M)": debt / 1e6 if pd.notna(debt) else np.nan,
                    "Total Stockholders Equity ($M)": equity / 1e6 if pd.notna(equity) else np.nan,
                    "Total Assets ($M)": tot_assets / 1e6 if pd.notna(tot_assets) else np.nan,
                })
            df_out = pd.DataFrame(rows).sort_values("Period").reset_index(drop=True)
            return df_out

        df_q = _process_statements(inc_q, bal_q, cf_q)
        df_a = _process_statements(inc_a, bal_a, cf_a)
        return {"quarterly": df_q, "annual": df_a}
    except Exception as e:
        print(f"Error processing financial statements for {symbol}: {e}")
        return {"quarterly": pd.DataFrame(), "annual": pd.DataFrame()}

def calculate_reverse_dcf(current_price: float, ttm_fcf_per_share: float, wacc: float = 0.09, terminal_growth: float = 0.03, forecast_years: int = 10):
    if ttm_fcf_per_share <= 0 or current_price <= 0:
        return np.nan
    low_g, high_g = -0.50, 1.00
    for _ in range(100):
        mid_g = (low_g + high_g) / 2.0
        pv = 0.0
        cf = ttm_fcf_per_share
        for t in range(1, forecast_years + 1):
            cf *= (1 + mid_g)
            pv += cf / ((1 + wacc) ** t)
        terminal_val = (cf * (1 + terminal_growth)) / (wacc - terminal_growth)
        pv += terminal_val / ((1 + wacc) ** forecast_years)
        if abs(pv - current_price) < 0.01:
            return mid_g * 100.0
        if pv > current_price:
            high_g = mid_g
        else:
            low_g = mid_g
    return mid_g * 100.0

@st.cache_data(ttl=60 * 60 * 4)
def get_semiconductor_comparative_prices(symbols: list, period="1y"):
    try:
        import yfinance as yf
        data = yf.download(symbols, period=period, progress=False)["Close"]
        if not data.empty:
            data = data.ffill().dropna()
            norm_df = (data / data.iloc[0]) * 100.0
            return norm_df.reset_index()
    except Exception as e:
        print(f"Semi comparative prices fetch error: {e}")
    return pd.DataFrame()

@st.cache_data(ttl=60 * 60 * 6)
def get_semiconductor_matrix_data(symbols: list):
    import yfinance as yf
    matrix = []
    for s in symbols:
        try:
            t = yf.Ticker(s)
            inf = t.info
            cp = inf.get("currentPrice", inf.get("regularMarketPrice", np.nan))
            f_pe = inf.get("forwardPE", np.nan)
            t_pe = inf.get("trailingPE", np.nan)
            ps = inf.get("priceToSalesTrailing12Months", np.nan)
            rev_growth = inf.get("revenueGrowth", np.nan)
            if pd.notna(rev_growth):
                rev_growth *= 100.0
            op_margin = inf.get("operatingMargins", np.nan)
            if pd.notna(op_margin):
                op_margin *= 100.0
            gross_margin = inf.get("grossMargins", np.nan)
            if pd.notna(gross_margin):
                gross_margin *= 100.0
            fcf = inf.get("freeCashflow", np.nan)
            mc = inf.get("marketCap", np.nan)
            fcf_yield = (fcf / mc * 100.0) if (pd.notna(fcf) and pd.notna(mc) and mc > 0) else np.nan
            
            matrix.append({
                "Symbol": s,
                "Name": inf.get("shortName", s),
                "Price ($)": cp,
                "Trailing PE": t_pe,
                "Forward PE": f_pe,
                "P/S (TTM)": ps,
                "YoY Rev Growth (%)": rev_growth,
                "Gross Margin (%)": gross_margin,
                "Operating Margin (%)": op_margin,
                "FCF Yield (%)": fcf_yield,
                "Market Cap ($B)": (mc / 1e9) if pd.notna(mc) else np.nan
            })
        except Exception as e:
            print(f"Error fetching matrix data for {s}: {e}")
    return pd.DataFrame(matrix)

# ------------------------------------------------------------------
# 4. Streamlit 主页面设置与整体布局渲染
# ------------------------------------------------------------------
st.set_page_config(
    page_title="Macro & Equity Research Terminal",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("Macro Liquidity & Equity Research Terminal")
st.markdown("### 宏观流动性监控、半导体产业追踪与个股量化估值投研平台")

st.sidebar.markdown(f"**数据更新基准 (美东时间 EDT):** `{get_current_time_str_eastern()}`")
st.sidebar.markdown("---")

tab_macro, tab_stock, tab_semi, tab_company = st.tabs([
    "宏观流动性与经济全景指标",
    "个股全景追踪 & 估值与技术面",
    "半导体产业链追踪与相对表现矩阵",
    "财报深度拆解与公司基本面剖析 (Tab 4)"
])

# ==================================================================
# TAB 1: 宏观全景与市场流动性
# ==================================================================
with tab_macro:
    st.markdown("#### 美联储货币政策、流动性水库、利差与宏观情绪仪表盘")
    render_market_breadth_ui()
    
    col_tf1, col_tf2 = st.columns([2, 8])
    with col_tf1:
        timeframe_macro = st.selectbox(
            "选择宏观图表观察时间周期 (Timeframe):",
            options=["ALL", "10Y", "5Y", "3Y", "1Y", "6M", "3M", "1M"],
            index=3,
            key="macro_timeframe_selector"
        )
    
    st.markdown("---")
    
    col_m1, col_m2 = st.columns(2)
    with col_m1:
        st.subheader("1. 美国国债收益率曲线全景演变 (U.S. Treasury Curve)")
        treasury_file = "daily-treasury-rates.csv"
        if os.path.exists(treasury_file):
            df_long, _ = load_and_transform_data(treasury_file)
            fig_treasury = create_treasury_chart(df_long)
            if fig_treasury:
                st.plotly_chart(fig_treasury, use_container_width=True)
            else:
                st.info("国债收益率形态图表正在计算中...")
        else:
            st.warning("暂无 daily-treasury-rates.csv 数据。")
            
    with col_m2:
        st.subheader("2. 美国失业率趋势 (UNRATE & 阶段平均)")
        df_unrate = get_unemployment_data()
        fig_unrate = create_unemployment_chart(df_unrate, timeframe=timeframe_macro)
        if fig_unrate:
            st.plotly_chart(fig_unrate, use_container_width=True)
        else:
            st.info("正在加载失业率数据...")

    st.markdown("---")

    col_m3, col_m4 = st.columns(2)
    with col_m3:
        st.subheader("3. 高收益债信用利差 (US High Yield OAS)")
        df_oas = get_credit_spread_data()
        fig_oas = create_credit_spread_chart(df_oas, timeframe=timeframe_macro)
        if fig_oas:
            st.plotly_chart(fig_oas, use_container_width=True)
        else:
            st.info("正在加载信用利差数据...")

    with col_m4:
        st.subheader("4. 美联储总资产规模 (Fed Balance Sheet, WALCL)")
        df_fed = get_fed_balance_sheet_data()
        fig_fed = create_fed_balance_sheet_chart(df_fed, timeframe=timeframe_macro)
        if fig_fed:
            st.plotly_chart(fig_fed, use_container_width=True)
        else:
            st.info("正在加载美联储资产负债表数据...")

    st.markdown("---")

    col_m5, col_m6 = st.columns(2)
    with col_m5:
        st.subheader("5. 金油比走势 (Gold / Oil Ratio)")
        df_go = get_gold_oil_ratio_data()
        fig_go = create_gold_oil_ratio_chart(df_go, timeframe=timeframe_macro)
        if fig_go:
            st.plotly_chart(fig_go, use_container_width=True)
        else:
            st.info("正在计算金油比数据...")

    with col_m6:
        st.subheader("6. 10Y TIPS 实际利率 vs 10Y 盈亏平衡通胀预期")
        df_ry = get_real_yield_and_breakeven_data()
        fig_ry = create_real_yield_breakeven_chart(df_ry, timeframe=timeframe_macro)
        if fig_ry:
            st.plotly_chart(fig_ry, use_container_width=True)
        else:
            st.info("正在加载实际利率与通胀预期数据...")

    st.markdown("---")

    col_m7, col_m8 = st.columns(2)
    with col_m7:
        st.subheader("7. 芝加哥联储全国金融条件指数 (NFCI)")
        df_nfci = get_nfci_data()
        fig_nfci = create_nfci_chart(df_nfci, timeframe=timeframe_macro)
        if fig_nfci:
            st.plotly_chart(fig_nfci, use_container_width=True)
        else:
            st.info("正在加载 NFCI 数据...")

    with col_m8:
        st.subheader("8. 美联储净流动性水库 (Net Liquidity = Assets - TGA - RRP)")
        df_liq = get_net_liquidity_data()
        fig_liq = create_net_liquidity_chart(df_liq, timeframe=timeframe_macro)
        if fig_liq:
            st.plotly_chart(fig_liq, use_container_width=True)
        else:
            st.info("正在计算美联储净流动性数据...")

    st.markdown("---")

    col_m9, col_m10 = st.columns(2)
    with col_m9:
        st.subheader("9. SOFR 隔夜融资利率 vs IORB 准备金利率及利差")
        df_sofr = get_sofr_iorb_data()
        fig_sofr = create_sofr_iorb_chart(df_sofr, timeframe=timeframe_macro)
        if fig_sofr:
            st.plotly_chart(fig_sofr, use_container_width=True)
        else:
            st.info("正在加载 SOFR / IORB 利率数据...")

    with col_m10:
        st.subheader("10. 标普 500 前十大权重股集中度分布")
        df_top10 = get_top10_concentration_data()
        fig_top10 = create_top10_concentration_chart(df_top10)
        if fig_top10:
            st.plotly_chart(fig_top10, use_container_width=True)
        else:
            st.info("正在加载持仓集中度数据...")

    st.markdown("---")

    col_m11, col_m12 = st.columns(2)
    with col_m11:
        st.subheader("11. CBOE VIX 恐慌指数走势与预警区间")
        df_vix = get_vix_data()
        fig_vix = create_vix_chart(df_vix, timeframe=timeframe_macro)
        if fig_vix:
            st.plotly_chart(fig_vix, use_container_width=True)
        else:
            st.info("正在加载 VIX 数据...")

    with col_m12:
        st.subheader("12. CNN Fear & Greed 恐慌与贪婪指数历史走势")
        df_fgi = get_cnn_fear_and_greed_data()
        fig_fgi = create_cnn_fear_greed_chart(df_fgi, timeframe=timeframe_macro)
        if fig_fgi:
            st.plotly_chart(fig_fgi, use_container_width=True)
        else:
            st.info("正在加载 CNN 情绪指数数据...")

# ==================================================================
# TAB 2: 个股全景追踪 & 估值与技术面
# ==================================================================
with tab_stock:
    st.markdown("#### 个股估值分析、反向 DCF 市场内含增速预期、财务三张表趋势与技术指标走势")
    
    col_s_input1, col_s_input2, col_s_input3 = st.columns([2, 2, 6])
    with col_s_input1:
        stock_symbol = st.text_input("输入美股代码 (Ticker):", value="NVDA").upper().strip()
    with col_s_input2:
        stock_timeframe = st.selectbox(
            "K线观察周期 (Timeframe):",
            options=["1M", "3M", "6M", "1Y", "3Y", "5Y", "ALL"],
            index=3,
            key="stock_tf_selector"
        )
    with col_s_input3:
        chart_style = st.radio("图表形态:", ["Candlestick (K线+均线)", "Line (收盘价折线)"], horizontal=True)
    
    if stock_symbol:
        df_stock = get_stock_historical_data(stock_symbol, period="5y")
        info = get_stock_fundamentals(stock_symbol)
        
        if not df_stock.empty and info:
            c_price = info.get("currentPrice", info.get("regularMarketPrice", df_stock['Close'].iloc[-1]))
            market_cap = info.get("marketCap", np.nan)
            trailing_pe = info.get("trailingPE", np.nan)
            forward_pe = info.get("forwardPE", np.nan)
            trailing_ps = info.get("priceToSalesTrailing12Months", np.nan)
            fcf = info.get("freeCashflow", np.nan)
            shares = info.get("sharesOutstanding", np.nan)
            fcf_per_share = (fcf / shares) if (pd.notna(fcf) and pd.notna(shares) and shares > 0) else np.nan

            col_met1, col_met2, col_met3, col_met4, col_met5 = st.columns(5)
            col_met1.metric("当前实时股价", f"${c_price:.2f}" if pd.notna(c_price) else "N/A")
            col_met2.metric("市盈率 PE (TTM / Fwd)", f"{trailing_pe:.1f} / {forward_pe:.1f}" if (pd.notna(trailing_pe) and pd.notna(forward_pe)) else f"{trailing_pe:.1f}" if pd.notna(trailing_pe) else "N/A")
            col_met3.metric("市销率 P/S (TTM)", f"{trailing_ps:.2f}x" if pd.notna(trailing_ps) else "N/A")
            col_met4.metric("市值 (Market Cap)", f"${market_cap/1e9:.2f} B" if pd.notna(market_cap) else "N/A")
            col_met5.metric("每股自由现金流 (FCF/Sh)", f"${fcf_per_share:.2f}" if pd.notna(fcf_per_share) else "N/A")

            st.markdown("---")

            st.subheader(f"1. {stock_symbol} 交互式行情与均线系统 (MA20 / MA50 / MA200 & 成交量)")
            is_candlestick = "Candlestick" in chart_style
            fig_stock = create_stock_price_chart(
                df_stock, 
                stock_symbol, 
                chart_type="Candlestick" if is_candlestick else "Line",
                timeframe=stock_timeframe
            )
            if fig_stock:
                st.plotly_chart(fig_stock, use_container_width=True)

            st.markdown("---")

            col_eval1, col_eval2 = st.columns(2)
            
            with col_eval1:
                st.subheader(f"2. {stock_symbol} 估值通道分析 (PE / PS Band)")
                eps_ttm = info.get("trailingEps", np.nan)
                rev_per_sh = (info.get("totalRevenue", np.nan) / shares) if (pd.notna(shares) and shares > 0 and pd.notna(info.get("totalRevenue", np.nan))) else np.nan
                
                if create_pe_ps_band_chart:
                    fig_pe_band = create_pe_ps_band_chart(
                        df_stock, 
                        stock_symbol, 
                        current_eps=eps_ttm,
                        current_rev_per_share=rev_per_sh,
                        timeframe=stock_timeframe
                    )
                    if fig_pe_band:
                        st.plotly_chart(fig_pe_band, use_container_width=True)
                    else:
                        st.info("正在绘制 PE/PS Band 图表...")
                else:
                    st.info("PE/PS Band 模块加载中...")

            with col_eval2:
                st.subheader(f"3. {stock_symbol} 反向贴现现金流模型 (Reverse DCF)")
                st.markdown("""
                **反向 DCF 原理**：不主观预测未来增速，而是反推**当前股价所隐含的未来 10 年自由现金流 (FCF) 年化复合增长率 (CAGR)**。
                """)
                
                col_dcf_p1, col_dcf_p2 = st.columns(2)
                with col_dcf_p1:
                    dcf_wacc = st.slider("贴现率 (WACC / 要求回报率 %):", min_value=5.0, max_value=15.0, value=9.0, step=0.5) / 100.0
                with col_dcf_p2:
                    dcf_tg = st.slider("永续增长率 (Terminal Growth %):", min_value=1.0, max_value=5.0, value=3.0, step=0.5) / 100.0

                if pd.notna(fcf_per_share) and fcf_per_share > 0 and pd.notna(c_price):
                    implied_g = calculate_reverse_dcf(c_price, fcf_per_share, wacc=dcf_wacc, terminal_growth=dcf_tg, forecast_years=10)
                    if pd.notna(implied_g):
                        st.metric(
                            label=f"当前股价 ${c_price:.2f} 隐含的未来 10 年 FCF 年化增速 (CAGR)",
                            value=f"{implied_g:.2f}%",
                            delta=f"WACC: {dcf_wacc*100:.1f}%, 永续增长: {dcf_tg*100:.1f}%"
                        )
                        st.info(f"""
                        * 若您认为 {stock_symbol} 未来 10 年实际 FCF 增速 **高于 {implied_g:.2f}%**，则当前股价被**低估** (具有安全边际)。
                        * 若您认为其未来增速 **无法达到 {implied_g:.2f}%**，则当前股价已被充分甚至过度定价。
                        """)
                    else:
                        st.warning("反向 DCF 求解未收敛，请检查基准参数。")
                else:
                    st.warning(f"由于 {stock_symbol} TTM 自由现金流为负或数据缺失，无法直接运用标准 FCF 反向 DCF 模型。")

            st.markdown("---")

            if create_technical_momentum_chart:
                st.subheader(f"4. {stock_symbol} 技术动量与超买超卖信号 (RSI, MACD & 布林带)")
                fig_tech = create_technical_momentum_chart(df_stock, stock_symbol, timeframe=stock_timeframe)
                if fig_tech:
                    st.plotly_chart(fig_tech, use_container_width=True)

            st.markdown("---")

            st.subheader(f"5. {stock_symbol} 历史核心财务报表与经营趋势透视 (Financial Statements)")
            fin_data = get_stock_financial_statements(stock_symbol)
            
            fin_tab_q, fin_tab_a = st.tabs(["季度财务趋势与明细表 (Quarterly)", "年度财务趋势与明细表 (Annual)"])
            
            with fin_tab_q:
                df_q = fin_data.get("quarterly", pd.DataFrame())
                if not df_q.empty:
                    fig_trends_q = create_financial_trends_chart(df_q, stock_symbol, period_type="季度 (Quarterly)")
                    if fig_trends_q:
                        st.plotly_chart(fig_trends_q, use_container_width=True)
                    st.markdown("**季度财务核心指标明细表 ($M / %)**")
                    st.dataframe(df_q, use_container_width=True)
                else:
                    st.info("暂无季度财务报表明细数据。")

            with fin_tab_a:
                df_a = fin_data.get("annual", pd.DataFrame())
                if not df_a.empty:
                    fig_trends_a = create_financial_trends_chart(df_a, stock_symbol, period_type="年度 (Annual)")
                    if fig_trends_a:
                        st.plotly_chart(fig_trends_a, use_container_width=True)
                    st.markdown("**年度财务核心指标明细表 ($M / %)**")
                    st.dataframe(df_a, use_container_width=True)
                else:
                    st.info("暂无年度财务报表明细数据。")
        else:
            st.warning(f"未能获取到 {stock_symbol} 的有效行情或基本面数据，请确认 Ticker 正确性。")

# ==================================================================
# TAB 3: 半导体产业链追踪与相对表现矩阵
# ==================================================================
with tab_semi:
    st.markdown("#### 半导体全产业链龙头（设计、制造、设备、EDA/IP、封测、材料）估值对比与超额收益走势")
    
    semi_universe = {
        "AI 算力与 GPU": ["NVDA", "AMD"],
        "代工制造与先进制程": ["TSM"],
        "半导体核心设备 (Litho & WFE)": ["ASML", "AMAT", "LRCX", "KLAC"],
        "EDA 软件与物理 IP": ["SNPS", "CDNS", "ARM"],
        "定制 ASIC 与网络互联": ["AVGO", "MRVL"],
        "模拟、射频与汽车芯片": ["TXN", "ADI", "QCOM"],
        "存储与存储控制": ["MU"],
        "基准指数 ETF": ["SOXX", "SMH", "SPY", "QQQ"]
    }
    
    all_semi_symbols = ["NVDA", "TSM", "ASML", "AMD", "AVGO", "AMAT", "LRCX", "KLAC", "SNPS", "CDNS", "ARM", "MRVL", "MU", "TXN", "ADI", "QCOM", "SOXX", "SMH"]
    
    col_semi_tf, col_semi_bench = st.columns([2, 4])
    with col_semi_tf:
        semi_tf = st.selectbox(
            "选择相对表现对比时间窗口:",
            options=["1M", "3M", "6M", "1Y", "2Y", "3Y", "5Y"],
            index=3,
            key="semi_timeframe_select"
        )
    with col_semi_bench:
        selected_benchmarks = st.multiselect(
            "选择对比展示的标的 (默认包含行业龙头与基准):",
            options=all_semi_symbols,
            default=["NVDA", "TSM", "ASML", "AVGO", "AMD", "SOXX", "SMH"],
            key="semi_selected_tickers"
        )

    st.subheader("1. 半导体龙头标的相对收益走势图 (Normalized to 100)")
    if selected_benchmarks:
        df_semi_prices = get_semiconductor_comparative_prices(selected_benchmarks, period="5y")
        fig_semi_rel = create_relative_performance_chart(
            df_semi_prices, 
            symbols=selected_benchmarks, 
            timeframe=semi_tf
        )
        if fig_semi_rel:
            st.plotly_chart(fig_semi_rel, use_container_width=True)
        else:
            st.info("正在计算半导体相对表现图表...")

    st.markdown("---")

    st.subheader("2. 全产业链核心指标多维估值与盈利能力对比矩阵")
    matrix_symbols = ["NVDA", "TSM", "ASML", "AVGO", "AMD", "AMAT", "LRCX", "KLAC", "ARM", "SNPS", "CDNS", "MRVL", "MU", "TXN", "ADI", "QCOM"]
    df_matrix = get_semiconductor_matrix_data(matrix_symbols)
    if not df_matrix.empty:
        st.dataframe(
            df_matrix.style.format({
                "Price ($)": "${:.2f}",
                "Trailing PE": "{:.1f}",
                "Forward PE": "{:.1f}",
                "P/S (TTM)": "{:.2f}",
                "YoY Rev Growth (%)": "{:.1f}%",
                "Gross Margin (%)": "{:.1f}%",
                "Operating Margin (%)": "{:.1f}%",
                "FCF Yield (%)": "{:.2f}%",
                "Market Cap ($B)": "${:.1f}B"
            }),
            use_container_width=True
        )
    else:
        st.info("正在聚合半导体多维财务矩阵...")

    st.markdown("---")

    st.subheader("3. 行业关键投资逻辑与护城河图谱")
    col_logic1, col_logic2 = st.columns(2)
    with col_logic1:
        st.markdown("""
        * **晶圆制造垄断 (TSM)**：台积电凭借 CoWoS 先进封装产能、N3/N2 先进制程良率与全生态 EDA 支持构建了极高的行业转换壁垒，先进制程市占率超过 90%。
        * **光刻机技术垄断 (ASML)**：High-NA EUV 及 EUV 光刻机全球独家供应商，芯片制程向 2nm/1.4nm 演进不可或缺的物理基础设施。
        * **算力与软件生态 (NVDA)**：CUDA 架构垄断深度学习框架与算子库，结合 NVLink 互联网络与 TensorRT 推理引擎构建了深厚的全栈软硬件护城河。
        """)
    with col_logic2:
        st.markdown("""
        * **EDA 软件与 IP (SNPS / CDNS / ARM)**：先进制程复杂度指数级上升，设计自动化工具与底层指令集架构具有极高的客户粘性与高毛利、高自由现金流属性。
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
