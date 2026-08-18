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

@st.cache_data(ttl=60 * 60 * 6)
def get_yield_spreads_data():
    df_10y2y = _fetch_fred_series_observations("T10Y2Y", "Spread_10Y2Y", "1990-01-01")
    df_10y3m = _fetch_fred_series_observations("T10Y3M", "Spread_10Y3M", "1990-01-01")
    if not df_10y2y.empty and not df_10y3m.empty:
        merged = pd.merge_asof(df_10y2y.sort_values("date"), df_10y3m.sort_values("date"), on="date", direction="nearest")
        return merged.dropna()
    return pd.DataFrame()

@st.cache_data(ttl=60 * 60 * 6)
def get_jobless_claims_data():
    icsa = _fetch_fred_series_observations("ICSA", "Initial_Claims", "2000-01-01")
    ccsa = _fetch_fred_series_observations("CCSA", "Continued_Claims", "2000-01-01")
    if not icsa.empty and not ccsa.empty:
        merged = pd.merge_asof(icsa.sort_values("date"), ccsa.sort_values("date"), on="date", direction="nearest")
        return merged.dropna()
    return pd.DataFrame()

@st.cache_data(ttl=60 * 60 * 6)
def get_dxy_data():
    return _fetch_fred_series_observations("DTWEXBGS", "DXY", "2006-01-01")

@st.cache_data(ttl=60 * 60 * 6)
def get_inflation_wages_data():
    cpi = _fetch_fred_series_observations("CPILFESL", "Core_CPI", "2000-01-01")
    wages = _fetch_fred_series_observations("CES0500000003", "Hourly_Earnings", "2000-01-01")
    if not cpi.empty and not wages.empty:
        cpi["Core_CPI_YoY"] = cpi["Core_CPI"].pct_change(12) * 100.0
        wages["Wages_YoY"] = wages["Hourly_Earnings"].pct_change(12) * 100.0
        merged = pd.merge_asof(cpi.dropna().sort_values("date"), wages.dropna().sort_values("date"), on="date", direction="nearest")
        return merged[["date", "Core_CPI_YoY", "Wages_YoY"]].dropna()
    return pd.DataFrame()

@st.cache_data(ttl=60 * 60 * 6)
def get_sahm_rule_data():
    return _fetch_fred_series_observations("SAHMREALTIME", "Sahm_Rule", "1970-01-01")

@st.cache_data(ttl=60 * 60 * 6)
def get_core_capex_data():
    df = _fetch_fred_series_observations("NEWORDER", "Core_CapEx", "1992-01-01")
    if not df.empty:
        df["Core_CapEx_YoY"] = df["Core_CapEx"].pct_change(12) * 100.0
        return df.dropna()
    return pd.DataFrame()

@st.cache_data(ttl=60 * 60 * 6)
def get_m2_money_supply_data():
    df = _fetch_fred_series_observations("M2SL", "M2", "1980-01-01")
    if not df.empty:
        df["M2_YoY"] = df["M2"].pct_change(12) * 100.0
        return df.dropna()
    return pd.DataFrame()

@st.cache_data(ttl=60 * 60 * 6)
def get_sloos_credit_data():
    return _fetch_fred_series_observations("DRTSCIS", "Tightening_Net_Pct", "1990-01-01")

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
    "🌐 宏观流动性与经济全景指标",
    "📈 个股全景追踪 & 估值与技术面",
    "⚡ 芯片半导体全产业链追踪",
    "🏢 财报深度拆解与公司基本面剖析 (Tab 4)"
])

# ==================================================================
# TAB 1: 宏观全景与市场流动性
# ==================================================================
with tab_macro:
    st.markdown("#### 美联储货币政策、流动性水库、利差与宏观情绪仪表盘")
    render_market_breadth_ui()
    
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
            with st.expander("💡 美债收益率曲线 (Yield Curve) 解读指南", expanded=False):
                st.markdown("""
                * **形态演变比较**：对比最新曲线、1个月前及1年前曲线。
                * **倒挂阶段 (Inversion, 2Y > 10Y)**：短端政策利率高企压低长端衰退预期，预示银行净息差受挤压与信用紧缩。
                * **陡峭化阶段 (Steepening)**：
                  * **牛陡 (Bull Steepening)**：降息周期开启，短端利率急跌，恢复正利差（通常伴随衰退后期的流动性修复）。
                  * **熊陡 (Bear Steepening)**：长端利率飙升，由通胀中枢上移、美债供给冲击或期限溢价走高驱动。
                """)
        
        st.sidebar.header("国债数据信息")
        st.sidebar.markdown(f"刷新时间 (美东): **{treasury_updated}**")
        st.sidebar.markdown(f"最新日期: **{latest_date}**")
        st.sidebar.markdown(f"总数据点: **{len(df_long)//12}**")
    else:
        st.warning("暂无 daily-treasury-rates.csv 数据。")

    st.markdown("---")

    # --- 2. 市场情绪量化指标 ---
    st.header("📊 市场情绪量化指标 (VIX & CNN Fear/Greed Index)")
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("CBOE VIX 恐慌指数")
        with st.spinner("正在从 FRED 加载 VIX 恐慌指数..."):
            df_vix = get_vix_data()
        if not df_vix.empty:
            latest_vix = df_vix["VIX"].dropna().iloc[-1]
            latest_vix_date = df_vix.dropna(subset=["VIX"])["date"].iloc[-1].strftime("%Y-%m-%d")
            st.metric(
                label=f"最新 VIX 指数 ({latest_vix_date})",
                value=f"{latest_vix:.2f}",
                delta="极度恐慌 (>30)" if latest_vix > 30 else ("情绪警惕 (20-30)" if latest_vix > 20 else "市场平稳 (<20)"),
                delta_color="inverse" if latest_vix > 20 else "normal"
            )
            fig_vix = create_vix_chart(df_vix, timeframe=macro_tf)
            if fig_vix:
                st.plotly_chart(fig_vix, use_container_width=True)
                with st.expander("💡 CBOE VIX 恐慌指数解读指南", expanded=False):
                    st.markdown("""
                    * **< 15 (极度自满/低波动)**：市场处于平静期或牛市主升段，但衍生品防范尾部风险的对冲成本极低。
                    * **15 - 20 (中性平稳)**：美股历史常态波动区间。
                    * **20 - 30 (风险警惕/情绪承压)**：市场开始消化加息、地缘政治或财报不确定性，抛压逐渐释放。
                    * **> 30 (高恐慌预警/流动性踩踏)**：波动率脉冲式飙升，通常对应恐慌性抛售或历史级左侧买点。
                    """)
        else:
            st.info("正在加载或暂无 VIX 数据...")

    with col2:
        st.subheader("CNN 恐慌与贪婪指数 (Fear & Greed)")
        with st.spinner("正在获取 CNN 恐慌与贪婪指数..."):
            df_fgi = get_cnn_fear_and_greed_data()
        if not df_fgi.empty:
            latest_row = df_fgi.dropna(subset=["Score"]).iloc[-1]
            score_val = latest_row["Score"]
            rating_val = latest_row["Rating"]
            date_str = latest_row["date"].strftime("%Y-%m-%d")
            st.metric(
                label=f"最新情绪得分 ({date_str})",
                value=f"{score_val:.1f} / 100",
                delta=f"评级: {rating_val}",
                delta_color="normal" if score_val > 50 else "inverse"
            )
            fig_fgi = create_cnn_fear_greed_chart(df_fgi, timeframe=macro_tf)
            if fig_fgi:
                st.plotly_chart(fig_fgi, use_container_width=True)
                with st.expander("💡 CNN 恐慌与贪婪指数解读指南", expanded=False):
                    st.markdown("""
                    * **0 - 25 (Extreme Fear, 极度恐慌)**：投资者极度悲观，往往预示市场严重超卖，提供逆向价值买入机会。
                    * **25 - 45 (Fear, 恐慌)**：避险情绪主导，资金流向国债等防御性资产。
                    * **45 - 55 (Neutral, 中性)**：市场多空处于博弈均衡状态。
                    * **55 - 75 (Greed, 贪婪)**：风险偏好回暖，股市动能与广度扩张。
                    * **75 - 100 (Extreme Greed, 极度贪婪)**：FOMO (错失恐惧) 情绪蔓延，杠杆与估值泡沫积聚，需警惕回调风险。
                    """)
        else:
            st.info("正在加载或暂无 CNN 恐慌与贪婪指数数据...")

    st.markdown("---")

    # --- 3. 资金面体温计 & 指数结构集中度 ---
    st.header("📊 资金面体温计 & 指数结构集中度")
    col_sofr, col_top10 = st.columns(2)

    with col_sofr:
        st.subheader("SOFR - IORB 资金面体温计")
        with st.spinner("正在计算 SOFR - IORB 利差数据..."):
            df_sofr = get_sofr_iorb_data()
        if not df_sofr.empty:
            latest_sofr = df_sofr.dropna(subset=["Spread_bps"]).iloc[-1]
            spread_val = latest_sofr["Spread_bps"]
            sofr_rate = latest_sofr["SOFR"]
            iorb_rate = latest_sofr["IORB"]
            sofr_date = latest_sofr["date"].strftime("%Y-%m-%d")
            st.metric(
                label=f"SOFR - IORB 利差 ({sofr_date})",
                value=f"{spread_val:+.1f} bps",
                delta=f"SOFR: {sofr_rate:.2f}% | IORB: {iorb_rate:.2f}%",
                delta_color="inverse" if spread_val > 0 else "normal"
            )
            fig_sofr = create_sofr_iorb_chart(df_sofr, timeframe=macro_tf)
            if fig_sofr:
                st.plotly_chart(fig_sofr, use_container_width=True)
                with st.expander("💡 SOFR - IORB 资金面体温计解读指南", expanded=False):
                    st.markdown("""
                    * **指标定位**：**SOFR**（有担保隔夜融资利率，代表市场借钱成本）减去 **IORB**（准备金余额利率，美联储付给银行的无风险利率）。
                    * **< 0 bps (常态充裕)**：银行宁可把多余钱存回美联储拿 IORB，市场流动性极为宽松。
                    * **0 ~ +5 bps (轻度偏紧/临界点)**：银行间市场资金开始出现结构性摩擦，短期借贷成本抬升。
                    * **> +10 bps (钱荒/流动性危机警报)**：类似 2019 年 9 月隔夜回购利率飙升危机，表明银行超额准备金已接近甚至跌破最低舒适水平 (LCLoR)，美联储可能被迫提前终止量化紧缩 (QT) 或开启流动性注入。
                    """)
        else:
            st.info("正在加载或暂无 SOFR / IORB 数据...")

    with col_top10:
        st.subheader("S&P 500 前十大持仓集中度")
        with st.spinner("正在加载标普500前十大持仓集中度..."):
            df_top10 = get_top10_concentration_data()
        if not df_top10.empty:
            fig_top10 = create_top10_concentration_chart(df_top10)
            if fig_top10:
                st.plotly_chart(fig_top10, use_container_width=True)
                with st.expander("💡 S&P 500 前十大持仓集中度解读指南", expanded=False):
                    st.markdown("""
                    * **集中度含义**：前 10 大超级权重巨头（Mega-Caps，如 MSFT, AAPL, NVDA, GOOGL, AMZN, META）占指数整体市值的比重已接近 **35% - 40%**，创下近 50 年历史极值。
                    * **市场脆弱性**：当集中度过高时，大盘指数（SPY/QQQ）的涨跌实质上被极少数几家科技巨头绑架。即使底层 490 只股票普遍下跌，只要巨头拉升指数即可掩盖市场疲弱；一旦巨头补跌，大盘将面临剧烈共振回撤。
                    """)
        else:
            st.info("正在加载或暂无前十大持仓集中度数据...")

    st.markdown("---")

    # --- 4. 宏观指标与流动性追踪 ---
    st.header("📊 宏观指标与流动性追踪")

    # 第一组：实际利率 & 净流动性
    col3, col4 = st.columns(2)
    with col3:
        st.subheader("10Y TIPS 实际利率 & 通胀预期")
        with st.spinner("正在从 FRED 加载 10Y TIPS 实际利率与通胀预期..."):
            df_ry = get_real_yield_and_breakeven_data()
        if not df_ry.empty:
            fig_ry = create_real_yield_breakeven_chart(df_ry, timeframe=macro_tf)
            if fig_ry:
                st.plotly_chart(fig_ry, use_container_width=True)
                with st.expander("💡 10Y TIPS 实际利率 & 通胀预期解读指南", expanded=False):
                    st.markdown("""
                    * **10Y TIPS 实际利率 (DFII10)**：全球无风险资产的**真实资本回报率**，亦是全球风险资产（尤其高估值成长股）估值折现率的核心分母。实际利率走高往往导致成长股 PE 承压。
                    * **10Y 盈亏平衡通胀预期 (T10YIE)**：名义美债利率与 TIPS 利率之差，代表债券市场定价的未来 10 年平均年化通胀率。维持在 2.0% - 2.5% 表明美联储抗通胀信誉良好。
                    """)
        else:
            st.info("正在加载或暂无实际利率与通胀预期数据...")

    with col4:
        st.subheader("美联储净流动性 & 银行准备金")
        with st.spinner("正在从 FRED 计算美联储净流动性与准备金余额..."):
            df_liq = get_net_liquidity_data()
        if not df_liq.empty:
            fig_liq = create_net_liquidity_chart(df_liq, timeframe=macro_tf)
            if fig_liq:
                st.plotly_chart(fig_liq, use_container_width=True)
                with st.expander("💡 美联储净流动性 & 银行准备金解读指南", expanded=False):
                    st.markdown("""
                    * **净流动性公式**：`Net Liquidity = 美联储总资产 (WALCL) - 财政部现金账户 (TGA) - 隔夜逆回购 (RRP)`。
                    * **与美股高度正相关**：净流动性是驱动风险资产水位的核心流动性水龙头。当 TGA 充水或联储缩表时流动性被吸干；当 RRP 资金释放或 TGA 泄洪时注入流动性，通常领先美股 1-2 周走势。
                    * **银行准备金 (Bank Reserves)**：金融系统的底层真正结算血液。准备金充裕保障信用扩张，跌破阈值易触发金融管道流动性摩擦。
                    """)
        else:
            st.info("正在加载或暂无净流动性数据...")

    st.markdown("---")

    # 第二组：金融条件 (NFCI) & 高收益债信用利差
    col5, col6 = st.columns(2)
    with col5:
        st.subheader("芝加哥联储全国金融条件指数 (NFCI)")
        with st.spinner("正在从 FRED 加载芝加哥联储 NFCI 指数..."):
            df_nfci = get_nfci_data()
        if not df_nfci.empty:
            fig_nfci = create_nfci_chart(df_nfci, timeframe=macro_tf)
            if fig_nfci:
                st.plotly_chart(fig_nfci, use_container_width=True)
                with st.expander("💡 芝加哥联储全国金融条件指数 (NFCI) 解读指南", expanded=False):
                    st.markdown("""
                    * **指标含义**：综合涵盖货币市场、债券市场、股票市场及影子银行系统的 105 项高频金融指标。
                    * **0 轴为历史常态基准**：
                      * **< 0 (宽松 Financial Conditions Loose)**：信贷容易获取，资产价格受到支撑。
                      * **> 0 (紧缩 Financial Conditions Tight)**：融资环境严苛，违约风险与信贷利差扩大，压制宏观经济扩张。
                    """)
        else:
            st.info("正在加载或暂无 NFCI 数据...")

    with col6:
        st.subheader("高收益债信用利差 (US High Yield Spread)")
        with st.spinner("正在从 FRED 加载高收益债信用利差..."):
            df_oas = get_credit_spread_data()
        if not df_oas.empty:
            fig_oas = create_credit_spread_chart(df_oas, timeframe=macro_tf)
            if fig_oas:
                st.plotly_chart(fig_oas, use_container_width=True)
                with st.expander("💡 高收益债信用利差 (US High Yield Spread) 解读指南", expanded=False):
                    st.markdown("""
                    * **指标定义 (BAML Option-Adjusted Spread)**：垃圾债收益率与无风险国债收益率的利差。
                    * **信用风险晴雨表**：
                      * **< 3.5% (极度健康/无违约担忧)**：企业偿债能力强，信贷充裕。
                      * **3.5% ~ 5.0% (中性承压)**：宏观增速放缓，需甄选优质资产。
                      * **> 5.5% (信用风暴预警)**：违约率攀升，企业债务展期受阻，往往预示经济衰退或流动性危机来临。
                    """)
        else:
            st.info("正在加载或暂无信用利差数据...")

    st.markdown("---")

    # 第三组：失业率 & 美联储资产负债表
    col7, col8 = st.columns(2)
    with col7:
        st.subheader("美国失业率 (UNRATE)")
        with st.spinner("正在从 FRED 加载失业率数据..."):
            df_unrate = get_unemployment_data()
        if not df_unrate.empty:
            fig_unrate = create_unemployment_chart(df_unrate, timeframe=macro_tf)
            if fig_unrate:
                st.plotly_chart(fig_unrate, use_container_width=True)
                with st.expander("💡 美国失业率 (UNRATE) 解读指南", expanded=False):
                    st.markdown("""
                    * **双重使命支柱 (Dual Mandate)**：美联储货币政策决策核心。当失业率处于低位时，央行可专注于抗击通胀；失业率快速抬头则迫使美联储转入降息宽松周期。
                    * **非线性跃升特征**：历史上失业率一旦见底反弹超过 0.5%，往往出现自强化的非线性快速上升（萨姆规则）。
                    """)
        else:
            st.info("正在加载或暂无失业率数据...")

    with col8:
        st.subheader("美联储资产负债表 (WALCL)")
        with st.spinner("正在从 FRED 加载美联储资产负债表数据..."):
            df_fed = get_fed_balance_sheet_data()
        if not df_fed.empty:
            fig_fed = create_fed_balance_sheet_chart(df_fed, timeframe=macro_tf)
            if fig_fed:
                st.plotly_chart(fig_fed, use_container_width=True)
                with st.expander("💡 美联储总资产 (WALCL) 解读指南", expanded=False):
                    st.markdown("""
                    * **QE (量化宽松)**：央行大规模购债扩表，向金融体系直接注入基础货币，推高所有风险资产估值。
                    * **QT (量化紧缩)**：央行通过国债/MBS 到期不续做进行缩表回收流动性，给金融体系带来隐性持续紧缩压力。
                    """)
        else:
            st.info("正在加载或暂无美联储资产负债表数据...")

    st.markdown("---")

    # 第四组：金油比
    col9, _ = st.columns(2)
    with col9:
        st.subheader("Gold / Oil Ratio (金油比)")
        with st.spinner("正在计算金油比历史数据..."):
            df_go = get_gold_oil_ratio_data()
        if not df_go.empty:
            fig_go = create_gold_oil_ratio_chart(df_go, timeframe=macro_tf)
            if fig_go:
                st.plotly_chart(fig_go, use_container_width=True)
                with st.expander("💡 Gold / Oil Ratio (金油比) 解读指南", expanded=False):
                    st.markdown("""
                    * **指标定义**：1 盎司黄金能购买的原油桶数（黄金代表终极避险与信用对冲，原油代表实体经济工业需求与总需求活力）。
                    * **> 25 - 30 (高风险/衰退预警)**：通常发生在经济衰退、实体总需求暴跌（油价下跌）且地缘/金融恐慌避险升温（金价上涨）阶段（如 2008 年次贷危机、2020 年疫情大跌）。
                    * **< 15 (经济过热/通胀高企)**：工业总需求旺盛，大宗商品通胀上行。
                    """)
        else:
            st.info("正在加载或暂无金油比数据...")

    st.markdown("---")

    # --- 5. 收益率曲线利差与衰退定量模型 ---
    st.header("📊 收益率曲线利差与衰退定量模型 (Curve Spreads & Recession Gauges)")
    col_spr, col_sahm = st.columns(2)

    with col_spr:
        st.subheader("10Y-2Y & 10Y-3M 美债期限利差")
        with st.spinner("正在加载国债期限利差数据..."):
            df_spreads = get_yield_spreads_data()
        if not df_spreads.empty:
            fig_spreads = create_yield_spreads_chart(df_spreads, timeframe=macro_tf)
            if fig_spreads:
                st.plotly_chart(fig_spreads, use_container_width=True)
                with st.expander("💡 10Y-2Y & 10Y-3M 美债期限利差解读指南", expanded=False):
                    st.markdown("""
                    * **10Y-2Y 利差 (T10Y2Y)**：市场交易降息预期与中期经济周期的核心定价基准。
                    * **10Y-3M 利差 (T10Y3M)**：美联储官方最青睐的经济衰退预测利差指标，倒挂深幅度预示未来 12 个月经济衰退概率大幅攀升。
                    * **真正风险点在“解挂恢复” (Un-inversion)**：历史表明股市最大跌幅往往不发生在倒挂最深处，而发生在**曲线从倒挂重新快速陡峭化（牛陡）**并进入实质性衰退降息的初期。
                    """)
        else:
            st.info("正在加载或暂无期限利差数据...")

    with col_sahm:
        st.subheader("萨姆法则衰退指标 (Sahm Rule)")
        with st.spinner("正在加载萨姆法则指标..."):
            df_sahm = get_sahm_rule_data()
        if not df_sahm.empty:
            latest_sahm = df_sahm.dropna(subset=["Sahm_Rule"]).iloc[-1]
            sahm_val = latest_sahm["Sahm_Rule"]
            sahm_date = latest_sahm["date"].strftime("%Y-%m-%d")
            st.metric(
                label=f"当前萨姆衰退指标值 ({sahm_date})",
                value=f"{sahm_val:.2f}",
                delta="触发衰退警报 (≥0.50)" if sahm_val >= 0.50 else "经济处于非衰退状态 (<0.50)",
                delta_color="inverse" if sahm_val >= 0.50 else "normal"
            )
            fig_sahm = create_sahm_rule_chart(df_sahm, timeframe=macro_tf)
            if fig_sahm:
                st.plotly_chart(fig_sahm, use_container_width=True)
                with st.expander("💡 萨姆法则衰退指标 (Sahm Rule) 解读指南", expanded=False):
                    st.markdown("""
                    * **萨姆法则定义 (Sahm Rule)**：当美国 3 个月移动平均失业率相比过去 12 个月的最低点上升 **0.50 个百分点 (0.50%)** 或以上时，标志着经济已陷入实质性衰退。
                    * **历史 100% 准确率**：自 1970 年以来的历次美国官方经济衰退中，萨姆法则均在衰退发生初期精准发出信号，且从未产生过假阳性误报。
                    """)
        else:
            st.info("正在加载或暂无萨姆法则数据...")

    st.markdown("---")

    # --- 6. 实体经济景气与高频就业追踪 ---
    st.header("📊 实体经济景气与高频就业追踪 (Leading Growth & Labor Market)")
    col_claims, col_capex = st.columns(2)

    with col_claims:
        st.subheader("美国周度初请失业金人数 (Jobless Claims)")
        with st.spinner("正在加载失业金申请高频数据..."):
            df_claims = get_jobless_claims_data()
        if not df_claims.empty:
            fig_claims = create_jobless_claims_chart(df_claims, timeframe=macro_tf)
            if fig_claims:
                st.plotly_chart(fig_claims, use_container_width=True)
                with st.expander("💡 周度初请失业金人数 (Jobless Claims) 解读指南", expanded=False):
                    st.markdown("""
                    * **初请失业金人数 (Initial Claims, 领先指标)**：每周公布的高频裁员晴雨表，通常超过 **25–26 万人** 表明劳动力市场边际松动，超过 **30 万人** 为深度疲弱信号。
                    * **续请失业金人数 (Continued Claims, 同期指标)**：反映被裁员工重新找到新工作的难易程度。续请持续走高表明失业周期拉长，再就业市场趋于冻结。
                    """)
        else:
            st.info("正在加载或暂无失业金申请数据...")

    with col_capex:
        st.subheader("核心资本品新订单 (Core CapEx Orders)")
        with st.spinner("正在加载核心资本品新订单数据..."):
            df_capex = get_core_capex_data()
        if not df_capex.empty:
            fig_capex = create_core_capex_chart(df_capex, timeframe=macro_tf)
            if fig_capex:
                st.plotly_chart(fig_capex, use_container_width=True)
                with st.expander("💡 核心资本品新订单 (Core CapEx Orders) 解读指南", expanded=False):
                    st.markdown("""
                    * **指标定义**：扣除国防与飞机的非国防资本品新订单（Nondefense Capital Goods Excluding Aircraft），反映美国实体企业对未来设备更新与生产扩张的**前瞻性资本开支意愿**。
                    * **同比增速 (YoY)**：长期领先美国私人投资与企业盈利周期，同比转负通常伴随着企业投资收缩与经济降速。
                    """)
        else:
            st.info("正在加载或暂无核心资本品订单数据...")

    st.markdown("---")

    # --- 7. 通胀中枢、广义货币与全球美元水温 ---
    st.header("📊 通胀中枢、广义货币与全球美元水温 (Inflation & Broad Liquidity)")
    col_cpi, col_dxy = st.columns(2)

    with col_cpi:
        st.subheader("核心 PCE 通胀同比 vs. 时薪增速")
        with st.spinner("正在加载核心通胀与时薪数据..."):
            df_inf_w = get_inflation_wages_data()
        if not df_inf_w.empty:
            fig_inf_w = create_inflation_wages_chart(df_inf_w, timeframe=macro_tf)
            if fig_inf_w:
                st.plotly_chart(fig_inf_w, use_container_width=True)
                with st.expander("💡 核心 PCE 通胀同比 vs. 时薪增速解读指南", expanded=False):
                    st.markdown("""
                    * **薪资-通胀螺旋 (Wage-Price Spiral)**：当平均时薪同比增速持续高于核心通胀时，居民实际购买力改善；但若薪资增速远超生产率增长，易推动服务业通胀粘性与二次通胀风险。
                    * **美联储 2.0% 锚定**：核心通胀回落至 2.0%-2.5% 区间是美联储确立降息周期的核心前置条件。
                    """)
        else:
            st.info("正在加载或暂无通胀与薪资数据...")

    with col_dxy:
        st.subheader("美元指数 (U.S. Dollar Index / DXY)")
        with st.spinner("正在加载美元指数数据..."):
            df_dxy = get_dxy_data()
        if not df_dxy.empty:
            fig_dxy = create_dxy_chart(df_dxy, timeframe=macro_tf)
            if fig_dxy:
                st.plotly_chart(fig_dxy, use_container_width=True)
                with st.expander("💡 美元指数 (DXY) 解读指南", expanded=False):
                    st.markdown("""
                    * **全球金融条件总闸门**：美元走强对全球非美经济体及跨国企业产生汇率紧缩效应，压制美股海外营收折算与新兴市场流动性。
                    * **避险属性 (Dollar Smile)**：在美联储极度鹰派加息或全球发生流动性危机时，美元呈现强避险上涨特征。
                    """)
        else:
            st.info("正在加载或暂无美元指数数据...")

    st.markdown("---")

    # --- 8. 商业银行信贷标准与 M2 货币供应 ---
    st.header("📊 商业银行信贷标准与 M2 货币供应 (Credit Standards & Money Supply)")
    col_sloos, col_m2 = st.columns(2)

    with col_sloos:
        st.subheader("美联储银行信贷标准调查 (SLOOS)")
        with st.spinner("正在加载银行贷款标准净收紧比例 (SLOOS)..."):
            df_sloos = get_sloos_credit_data()
        if not df_sloos.empty:
            fig_sloos = create_sloos_credit_chart(df_sloos, timeframe=macro_tf)
            if fig_sloos:
                st.plotly_chart(fig_sloos, use_container_width=True)
                with st.expander("💡 银行贷款标准 (SLOOS) 解读指南", expanded=False):
                    st.markdown("""
                    * **指标定义 (Senior Loan Officer Opinion Survey)**：对大中型企业工商业贷款 (C&I Loans) 标准净收紧的银行百分比。
                    * **极强前瞻性**：银行信贷收紧通常**领先企业违约率与实际信贷萎缩 2–4 个季度**。净收紧比例超过 +20%~+40% 标志着信贷紧缩周期，对中小企业资本开支与再融资构成严峻考验。
                    """)
        else:
            st.info("正在加载或暂无 SLOOS 数据...")

    with col_m2:
        st.subheader("广义货币供应量 M2 同比增速")
        with st.spinner("正在加载 M2 货币供应量数据..."):
            df_m2 = get_m2_money_supply_data()
        if not df_m2.empty:
            fig_m2 = create_m2_money_supply_chart(df_m2, timeframe=macro_tf)
            if fig_m2:
                st.plotly_chart(fig_m2, use_container_width=True)
                with st.expander("💡 广义货币供应量 M2 同比增速解读指南", expanded=False):
                    st.markdown("""
                    * **实体购买力总蓄水池**：M2 包括流通中现金、活期与定期存款、货币市场基金等。
                    * **同比负增长 (罕见收缩)**：2022-2023 年出现的 M2 同比负增长为近百年罕见，反映美联储激进加息与 QT 对商业银行存款体系的强力抽水效应；M2 同比重新企稳回升预示金融再通胀周期的启动。
                    """)
        else:
            st.info("正在加载或暂无 M2 数据...")

    st.markdown("---")

    # --- 9. 宏观策略与周期框架总览 (深度研究附录) ---
    with st.expander("📖 查看《见证逆潮》核心宏观逻辑与收益率曲线策略指南（深度解析版）", expanded=False):
        st.markdown("""
        ### 一、 宏观流动性与收益率曲线的三大定律

        #### 1. 收益率曲线形态与经济周期四阶段
        * **牛平 (Bull Flattening)**：经济过热后期，长端利率下行快于短端（预示远期增长降速与通胀见顶），适合超配长久期国债。
        * **熊平 (Bear Flattening)**：央行抗通胀激进加息，短端利率急升压平甚至倒挂曲线，权益市场承受估值杀跌。
        * **牛陡 (Bull Steepening)**：衰退显现，央行开启大幅降息，短端利率领跌，曲线快速脱离倒挂（**历史上美股最大主跌浪与出清阶段通常发生于此**）。
        * **熊陡 (Bear Steepening)**：经济强劲复苏或财政债务赤字失控，长端发债供给过剩推升期限溢价，顺周期价值股与大宗商品跑赢成长股。

        #### 2. 美联储流动性水库三大闸门联动机制
        * **流动性平衡公式**：$$\\text{Net Liquidity} = \\text{WALCL (美联储总资产)} - \\text{TGA (财政部现金)} - \\text{RRP (隔夜逆回购)}$$
        * **RRP 的缓冲垫作用**：2023 年美联储 QT 期间，财政部大量发债并未冲击市场，原因在于 2 万亿美元的 RRP 逆回购资金流出承接了美债供给，形成了隐性的“流动性释放”。当 RRP 耗尽至低位后，财政部再发债将直接抽取商业银行准备金，触发真实流动性紧缩。

        #### 3. 信用利差与金融条件的断崖效应
        * 信用利差（High Yield OAS）在经济扩张期具备漫长平稳的**低波动钝化期**，但一旦突破 4.0%~4.5% 临界水平，利差呈现快速脉冲式非线性放大。
        """)

# ==================================================================
# TAB 2: 个股全景追踪 & 估值与技术面
# ==================================================================
with tab_stock:
    st.header("🔍 个股深度量化与多因子估值追踪")
    st.markdown("集成实时行情、PE/PS Band 动态估值通道、反向 DCF 市场预期测算、技术动量及财务三张表明细。")

    # 1. 股票代码输入与基础信息
    col_input1, col_input2, col_input3 = st.columns([2, 2, 4])
    with col_input1:
        ticker_to_analyze = st.text_input("输入美股代码 (Ticker):", value="NVDA").upper().strip()
    with col_input2:
        stock_tf = st.selectbox(
            "选择行情观察时间周期:",
            ["1M", "3M", "6M", "1Y", "3Y", "5Y", "ALL"],
            index=3,
            key="stock_timeframe_select"
        )
    with col_input3:
        chart_mode = st.radio("选择行情主图模式:", ["K线图 (Candlestick + 均线)", "折线图 (Line)"], horizontal=True)

    if ticker_to_analyze:
        with st.spinner(f"正在拉取 {ticker_to_analyze} 实时行情与基本面数据..."):
            stock_df = get_stock_historical_data(ticker_to_analyze, period="5y")
            stock_info = get_stock_fundamentals(ticker_to_analyze)

        if not stock_df.empty and stock_info:
            curr_price = stock_info.get("currentPrice", stock_info.get("regularMarketPrice", stock_df["Close"].iloc[-1]))
            comp_name = stock_info.get("shortName", ticker_to_analyze)
            sector = stock_info.get("sector", "N/A")
            industry = stock_info.get("industry", "N/A")
            pe_ttm = stock_info.get("trailingPE", np.nan)
            pe_fwd = stock_info.get("forwardPE", np.nan)
            ps_ttm = stock_info.get("priceToSalesTrailing12Months", np.nan)
            pb_ratio = stock_info.get("priceToBook", np.nan)
            market_cap = stock_info.get("marketCap", np.nan)
            fcf = stock_info.get("freeCashflow", np.nan)
            shares_out = stock_info.get("sharesOutstanding", np.nan)
            eps_ttm = stock_info.get("trailingEps", np.nan)
            beta = stock_info.get("beta", np.nan)
            fcf_per_share = (fcf / shares_out) if (pd.notna(fcf) and pd.notna(shares_out) and shares_out > 0) else np.nan

            st.subheader(f"🏢 {comp_name} ({ticker_to_analyze}) — {sector} | {industry}")

            # 核心估值卡片
            kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
            kpi1.metric("当前实时股价", f"${curr_price:.2f}" if pd.notna(curr_price) else "N/A")
            kpi2.metric("市盈率 PE (TTM / Fwd)", f"{pe_ttm:.1f} / {pe_fwd:.1f}" if (pd.notna(pe_ttm) and pd.notna(pe_fwd)) else (f"{pe_ttm:.1f}" if pd.notna(pe_ttm) else "N/A"))
            kpi3.metric("市销率 P/S (TTM)", f"{ps_ttm:.2f}x" if pd.notna(ps_ttm) else "N/A")
            kpi4.metric("总市值 (Market Cap)", f"${market_cap/1e9:.2f} B" if pd.notna(market_cap) else "N/A")
            kpi5.metric("每股自由现金流 (FCF/Sh)", f"${fcf_per_share:.2f}" if pd.notna(fcf_per_share) else "N/A")

            st.markdown("---")

            # 2. 个股行情与均线系统 (MA20 / MA50 / MA200 & 成交量副图)
            st.subheader(f"📈 {ticker_to_analyze} 交互式行情走势 (MA20 / MA50 / MA200 均线系统)")
            chart_type_arg = "Candlestick" if "Candlestick" in chart_mode else "Line"
            fig_stock_price = create_stock_price_chart(stock_df, ticker_to_analyze, chart_type=chart_type_arg, timeframe=stock_tf)
            if fig_stock_price:
                st.plotly_chart(fig_stock_price, use_container_width=True)

            st.markdown("---")

            # 3. 动态 PE / PS 估值通道 (PE / PS Band)
            # ==================================================================
            # 4. 扩展模块一：历史估值分位与 PE / PS Band (估值通道透视)
            # ==================================================================
            st.markdown("---")
            st.subheader("📈 历史估值分位与 PE / PS Band (估值通道透视)")
            st.caption("叠加历史动态估值倍数通道，评估当前股价处于历史估值的折溢价状态与合理中枢")
        
            val_col1, val_col2 = st.columns()
            with val_col2:
                val_type_choice = st.radio("选择通道基准估值模型:", ["PE Band (基于 TTM EPS)", "PS Band (基于 TTM 每股营收)"], index=0)
                is_pe_mode = "PE" in val_type_choice
                val_type_code = "PE" if is_pe_mode else "PS"
                band_tf = st.selectbox("估值带时间跨度:", ["1Y", "3Y", "5Y", "ALL"], index=1, key="band_timeframe")
        
            with val_col1:
                cur_p = stock_info.get("currentPrice") or stock_info.get("regularMarketPrice") or stock_info.get("previousClose") or 100.0
                cur_pe_val = stock_info.get("trailingPE") if stock_info else None
                cur_eps_val = stock_info.get("trailingEps") if stock_info else None
                cur_ps_val = stock_info.get("priceToSalesTrailing12Months") if stock_info else None
                
                # 计算每股营收 SPS (Sales Per Share)
                rev_raw = stock_info.get("totalRevenue") if stock_info else None
                shs_out = stock_info.get("sharesOutstanding") if stock_info else None
                cur_sps_val = (rev_raw / shs_out) if (rev_raw and shs_out and shs_out > 0) else ((cur_p / cur_ps_val) if (cur_p and cur_ps_val) else None)
        
                # 检查是否满足绘图条件
                if is_pe_mode and (not cur_eps_val or cur_eps_val <= 0):
                    st.warning(f"⚠️ **{ticker_to_analyze}** 当前滚动每股收益 (TTM EPS: ${cur_eps_val if cur_eps_val is not None else 'N/A'}) 为负或暂未实现盈利，无法绘制 PE 市盈率通道。请在右侧单选框切换至 **PS Band (基于 TTM 每股营收)** 评估其营收估值水位。")
                else:
                    val_metric_val = cur_eps_val if is_pe_mode else cur_sps_val
                    val_multiple_val = cur_pe_val if is_pe_mode else cur_ps_val
        
                    if df_stock_hist is not None and not df_stock_hist.empty and val_metric_val and val_metric_val > 0:
                        fig_band = create_pe_ps_band_chart(
                            df_stock_hist,
                            symbol=ticker_to_analyze,
                            current_eps=val_metric_val,
                            current_pe=val_multiple_val,
                            valuation_type=val_type_code,
                            timeframe=band_tf
                        )
                        if fig_band:
                            st.plotly_chart(fig_band, use_container_width=True)
                            with st.expander(f"💡 {val_type_code} Band 估值通道投资解读", expanded=False):
                                metric_name = "每股收益 (EPS)" if is_pe_mode else "每股营收 (SPS)"
                                st.markdown(f"""
                                * **估值通道逻辑**：以公司当前{metric_name}（${val_metric_val:.2f}）为基准，绘制 5 条历史代表性估值倍数通道（0.6x、0.8x、1.0x、1.25x、1.5x）。
                                * **超买/超卖信号**：
                                  * 股价触及或突破顶轨（高估值通道）：表明市场给予极高预期溢价，情绪可能过热。
                                  * 股价回落至底轨（低估值通道）：通常对应基本面利空充分出清或悲观情绪超跌区间。
                                """)
                    else:
                        st.info(f"未能获取 {ticker_to_analyze} 足够的估值数据用于绘制通道。")

            # 4. 反向 DCF 估值测算器 (Reverse DCF)
            st.subheader("🎯 反向 DCF 估值测算器 (Reverse DCF & Implied Growth)")
            st.markdown("""
            **经典买方思考范式**：不尝试主观预测未来极其不确定的增长率，而是反推**当前股价所严格内含的未来 10 年自由现金流 (FCF) 年化复合增长率 (CAGR)**。
            """)
            col_dcf_in1, col_dcf_in2, col_dcf_in3 = st.columns(3)
            with col_dcf_in1:
                wacc_in = st.slider("贴现率 (WACC / 投资人要求回报率 %):", min_value=6.0, max_value=15.0, value=9.0, step=0.5) / 100.0
            with col_dcf_in2:
                tg_in = st.slider("永续年化增长率 (Terminal Growth %):", min_value=1.0, max_value=4.5, value=3.0, step=0.25) / 100.0
            with col_dcf_in3:
                years_in = st.selectbox("预测显性增长年限:", [5, 7, 10], index=2)

            if pd.notna(fcf_per_share) and fcf_per_share > 0 and pd.notna(curr_price):
                implied_growth = calculate_reverse_dcf(
                    curr_price,
                    fcf_per_share,
                    wacc=wacc_in,
                    terminal_growth=tg_in,
                    forecast_years=years_in
                )
                if pd.notna(implied_growth):
                    res_col1, res_col2 = st.columns(2)
                    with res_col1:
                        st.metric(
                            label=f"当前股价 ${curr_price:.2f} 隐含的未来 {years_in} 年 FCF 年化增速",
                            value=f"{implied_growth:.2f}%",
                            delta=f"基准 WACC: {wacc_in*100:.1f}% | 永续: {tg_in*100:.1f}%"
                        )
                    with res_col2:
                        st.info(f"""
                        * 若您研判 {ticker_to_analyze} 未来实际 FCF 复合增速 **高于 {implied_growth:.2f}%**，则当前估值具备**安全边际 (Undervalued)**。
                        * 若您认为未来增速 **难以维持 {implied_growth:.2f}%**，则当前市场定价已偏乐观，需警惕预期落空风险。
                        """)
                else:
                    st.warning("反向 DCF 求解未收敛，请检查基准参数。")
            else:
                st.warning(f"由于 {ticker_to_analyze} TTM 自由现金流为负或数据缺失，无法应用标准 FCF 反向 DCF 模型。")

            with st.expander("💡 反向 DCF 估值测算逻辑与安全边际指引", expanded=False):
                st.markdown("""
                * **巴菲特 / 芒格自由现金流逻辑**：内在价值是企业在剩余生命周期内所能产生的全部自由现金流的折现值。
                * **安全边际核心**：通过反向推导市场预期，识别市场是处于过度悲观的“低预期陷阱”还是过度亢奋的“高预期泡沫”。
                """)

            st.markdown("---")

            # 5. 技术面动量指标系统 (RSI, MACD, 200MA)
            st.subheader("⚡ 技术面动量指标系统 (RSI, MACD & 200MA 年线偏离度)")
            fig_tech_mom = create_technical_momentum_chart(stock_df, ticker_to_analyze, timeframe=stock_tf)
            if fig_tech_mom:
                st.plotly_chart(fig_tech_mom, use_container_width=True)
                with st.expander("💡 技术面动量指标系统解读指南", expanded=False):
                    st.markdown("""
                    * **RSI (14) 超买超卖**：RSI > 70 表明短期动量过热易发生均值回归；RSI < 30 进入超卖区间。
                    * **MACD (12, 26, 9) 金叉死叉**：零轴之上的金叉为强势顺势进攻信号；零轴之下的死叉表明下跌动能延续。
                    * **布林带 (Bollinger Bands)**：价格跌破下轨伴随缩量企稳为典型超卖技术反弹点位。
                    """)

            st.markdown("---")

            # 6. 核心财务报表深度透视 (季度与年度财报主要数据)
            st.subheader("📑 核心财务报表深度透视 (季度与年度过去 4–5 期全量明细与趋势图)")
            with st.spinner(f"正在聚合 {ticker_to_analyze} 核心财务三张表趋势明细..."):
                fin_stmts_dict = get_stock_financial_statements(ticker_to_analyze)

            fin_tab_q, fin_tab_a = st.tabs([
                "📊 季度财务报表明细 (Quarterly Financials)",
                "📅 年度财务报表明细 (Annual Financials)"
            ])

            with fin_tab_q:
                df_q_data = fin_stmts_dict.get("quarterly", pd.DataFrame())
                if not df_q_data.empty:
                    fig_fin_q = create_financial_trends_chart(df_q_data, ticker_to_analyze, period_type="季度 (Quarterly)")
                    if fig_fin_q:
                        st.plotly_chart(fig_fin_q, use_container_width=True)
                    st.markdown(f"##### {ticker_to_analyze} 季度核心财务指标全景明细表 ($M / %)")
                    st.dataframe(df_q_data, use_container_width=True, hide_index=True)
                else:
                    st.info(f"暂无 {ticker_to_analyze} 季度结构化财务报表明细。")

            with fin_tab_a:
                df_a_data = fin_stmts_dict.get("annual", pd.DataFrame())
                if not df_a_data.empty:
                    fig_fin_a = create_financial_trends_chart(df_a_data, ticker_to_analyze, period_type="年度 (Annual)")
                    if fig_fin_a:
                        st.plotly_chart(fig_fin_a, use_container_width=True)
                    st.markdown(f"##### {ticker_to_analyze} 年度核心财务指标全景明细表 ($M / %)")
                    st.dataframe(df_a_data, use_container_width=True, hide_index=True)
                else:
                    st.info(f"暂无 {ticker_to_analyze} 年度结构化财务报表明细。")

            st.markdown("---")

            # 7. 机构目标价与分析师共识
            with st.expander("📋 查看分析师评级、目标价与资本结构补充数据", expanded=False):
                col_extra1, col_extra2, col_extra3 = st.columns(3)
                target_mean = stock_info.get("targetMeanPrice", np.nan)
                target_high = stock_info.get("targetHighPrice", np.nan)
                target_low = stock_info.get("targetLowPrice", np.nan)
                num_analysts = stock_info.get("numberOfAnalystOpinions", np.nan)
                recom_key = stock_info.get("recommendationKey", "N/A").upper()

                with col_extra1:
                    st.markdown("##### 🎯 华尔街目标价共识")
                    st.write(f"* **均价目标价**: ${target_mean:.2f}" if pd.notna(target_mean) else "* 均价目标价: N/A")
                    st.write(f"* **最高目标价**: ${target_high:.2f}" if pd.notna(target_high) else "* 最高目标价: N/A")
                    st.write(f"* **最低目标价**: ${target_low:.2f}" if pd.notna(target_low) else "* 最低目标价: N/A")
                    st.write(f"* **覆盖分析师数**: {num_analysts}" if pd.notna(num_analysts) else "* 覆盖分析师数: N/A")
                    st.write(f"* **综合评级**: `{recom_key}`")

                with col_extra2:
                    st.markdown("##### 💼 资本结构与偿债能力")
                    tot_debt = stock_info.get("totalDebt", np.nan)
                    tot_cash = stock_info.get("totalCash", np.nan)
                    quick_r = stock_info.get("quickRatio", np.nan)
                    curr_r = stock_info.get("currentRatio", np.nan)
                    st.write(f"* **总现金储备**: ${tot_cash/1e9:.2f} B" if pd.notna(tot_cash) else "* 总现金储备: N/A")
                    st.write(f"* **总有息负债**: ${tot_debt/1e9:.2f} B" if pd.notna(tot_debt) else "* 总有息负债: N/A")
                    st.write(f"* **流动比率**: {curr_r:.2f}" if pd.notna(curr_r) else "* 流动比率: N/A")
                    st.write(f"* **速动比率**: {quick_r:.2f}" if pd.notna(quick_r) else "* 速动比率: N/A")

                with col_extra3:
                    st.markdown("##### 💰 股利与盈利回报")
                    div_rate = stock_info.get("dividendRate", np.nan)
                    div_yield = stock_info.get("dividendYield", np.nan)
                    roe = stock_info.get("returnOnEquity", np.nan)
                    roa = stock_info.get("returnOnAssets", np.nan)
                    st.write(f"* **年度股息**: ${div_rate:.2f}" if pd.notna(div_rate) else "* 年度股息: 无 / N/A")
                    st.write(f"* **股息率**: {div_yield*100:.2f}%" if pd.notna(div_yield) else "* 股息率: 0.00%")
                    st.write(f"* **净资产收益率 (ROE)**: {roe*100:.2f}%" if pd.notna(roe) else "* ROE: N/A")
                    st.write(f"* **总资产回报率 (ROA)**: {roa*100:.2f}%" if pd.notna(roa) else "* ROA: N/A")
        else:
            st.warning(f"未能获取到 {ticker_to_analyze} 的有效行情或基本面数据，请确认代码正确性。")

# ==================================================================
# TAB 3: 半导体产业链追踪与相对表现矩阵
# ==================================================================
with tab_semi:
    st.header("⚡ 芯片半导体产业链深度追踪")
    st.markdown("全产业链龙头标的相对超额收益、多因子估值比选矩阵与行业周期深度分析。")

    # 1. 相对收益表现对比
    st.subheader("📈 半导体龙头多股累计收益率对比 (Relative Performance)")
    col_semi_tf, col_semi_select = st.columns([2, 5])
    with col_semi_tf:
        semi_timeframe = st.selectbox(
            "选择相对收益观察周期:",
            ["1M", "3M", "6M", "1Y", "2Y", "3Y", "5Y"],
            index=3,
            key="semi_perf_tf"
        )

    semi_default_universe = ["NVDA", "TSM", "ASML", "AVGO", "AMD", "SOXX", "SMH"]
    semi_all_candidates = ["NVDA", "TSM", "ASML", "AVGO", "AMD", "AMAT", "LRCX", "KLAC", "ARM", "SNPS", "CDNS", "MRVL", "MU", "TXN", "ADI", "QCOM", "SOXX", "SMH"]

    with col_semi_select:
        selected_semi_tickers = st.multiselect(
            "选择对比展示的标的 (默认包含行业龙头与基准 ETF):",
            options=semi_all_candidates,
            default=semi_default_universe,
            key="semi_tickers_multiselect"
        )

    if selected_semi_tickers:
        with st.spinner("正在获取半导体标的历史收盘价并归一化计算..."):
            semi_prices_df = get_semiconductor_comparative_prices(selected_semi_tickers, period="5y")

        if not semi_prices_df.empty:
            fig_semi_perf = create_relative_performance_chart(
                semi_prices_df,
                selected_semi_tickers,
                timeframe=semi_timeframe
            )
            if fig_semi_perf:
                st.plotly_chart(fig_semi_perf, use_container_width=True)
        else:
            st.info("正在聚合半导体行情数据...")

    st.markdown("---")

    # 2. 多因子估值与财务指标比选矩阵
    st.subheader("📊 半导体全产业链核心标的估值与财务比选矩阵")
    with st.spinner("正在抓取并聚合半导体产业链公司核心估值与财务指标..."):
        df_semi_matrix = get_semiconductor_matrix_data(semi_all_candidates[:-2])

    if not df_semi_matrix.empty:
        st.dataframe(
            df_semi_matrix.style.format({
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
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("正在加载半导体矩阵比选数据...")

    st.markdown("---")

    # 3. 半导体投研框架深度解析
    with st.expander("📖 查看《半导体产业周期、制程节点与 WFE 资本开支》投研分析指南", expanded=False):
        st.markdown("""
        ### 一、 半导体产业四大周期演进规律

        #### 1. 硅周期的四大阶段 (The Silicon Cycle)
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
