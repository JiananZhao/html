"""
Data Service Layer for Macro & Equity Research Terminal
Provides cached data fetching from FRED, yfinance, CNN, SqueezeMetrics, and time helpers.
"""
import os
import datetime
import urllib.request
from zoneinfo import ZoneInfo
import pandas as pd
import numpy as np
import streamlit as st

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
        import requests
        import io
        url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
        resp = requests.get(url, headers=headers, timeout=12)
        if resp.status_code == 200 and resp.text:
            df = pd.read_csv(io.StringIO(resp.text))
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

# ==================================================================
# 宏观新指标 1: 股权风险溢价 (方案 2: SPX 实时点位 / 远期 NTM EPS)
# ==================================================================
@st.cache_data(ttl=60 * 60 * 4)
def get_erp_data(base_ntm_eps: float = 288.0):
    try:
        import yfinance as yf
        spx = yf.download("^GSPC", period="5y", progress=False)['Close']
        tnx = yf.download("^TNX", period="5y", progress=False)['Close']
        
        if spx.empty or tnx.empty:
            return {}
            
        spx_series = spx.squeeze().dropna()
        tnx_series = tnx.squeeze().dropna()
        
        latest_spx_price = float(spx_series.iloc[-1])
        latest_yield = float(tnx_series.iloc[-1])
        
        ntm_eps = float(base_ntm_eps)
        fwd_pe = latest_spx_price / ntm_eps
        current_ey = (ntm_eps / latest_spx_price) * 100.0
        current_erp = current_ey - latest_yield
        
        df = pd.DataFrame({'SPX': spx_series, '10Y_Yield': tnx_series}).dropna()
        df['Earnings_Yield'] = (ntm_eps / df['SPX']) * 100.0
        df['ERP'] = df['Earnings_Yield'] - df['10Y_Yield']
        
        df = df.reset_index()
        df.rename(columns={'Date': 'date', 'index': 'date'}, inplace=True)
        df['date'] = pd.to_datetime(df['date']).dt.tz_localize(None)
        
        return {
            "current_erp": current_erp,
            "current_ey": current_ey,
            "fwd_pe": fwd_pe,
            "ntm_eps": ntm_eps,
            "spx_price": latest_spx_price,
            "latest_yield": latest_yield,
            "df_history": df[['date', '10Y_Yield', 'Earnings_Yield', 'ERP']]
        }
    except Exception as e:
        print(f"Error calculating dynamic ERP: {e}")
        return {}

# ==================================================================
# 宏观新指标 2: CBOE SKEW 指数 与 SqueezeMetrics 暗池指数 (DIX)
# ==================================================================
@st.cache_data(ttl=60 * 60 * 6)
def get_skew_dix_data():
    res = {"df_skew": pd.DataFrame(), "df_dix": pd.DataFrame()}
    try:
        import yfinance as yf
        df_skew = yf.download("^SKEW", period="5y", progress=False)
        if not df_skew.empty:
            df_skew = df_skew[['Close']].reset_index()
            df_skew.columns = ['date', 'SKEW']
            df_skew['date'] = pd.to_datetime(df_skew['date']).dt.tz_localize(None)
            res["df_skew"] = df_skew.dropna()
    except Exception as e:
        print(f"Error fetching SKEW: {e}")

    try:
        import urllib.request
        url = "https://squeezemetrics.com/monitor/static/DIX.csv"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=12) as resp:
            df_dix = pd.read_csv(resp)
            if not df_dix.empty and 'date' in df_dix.columns and 'dix' in df_dix.columns:
                df_dix['date'] = pd.to_datetime(df_dix['date'])
                df_dix['DIX_pct'] = df_dix['dix'] * 100.0
                if 'gex' in df_dix.columns:
                    df_dix['GEX'] = df_dix['gex'] / 1e9
                res["df_dix"] = df_dix[['date', 'price', 'DIX_pct'] + (['GEX'] if 'GEX' in df_dix.columns else [])].dropna()
    except Exception as e:
        print(f"Error fetching DIX: {e}")

    return res

# ==================================================================
# 宏观新指标 3: 跨资产避险/风险偏好比率 (铜金比 & HYG/TLT)
# ==================================================================
@st.cache_data(ttl=60 * 60 * 6)
def get_risk_ratios_data():
    try:
        import yfinance as yf
        tickers = ["HG=F", "GC=F", "HYG", "TLT"]
        df_raw = yf.download(tickers, period="5y", progress=False)['Close']
        if df_raw is not None and not df_raw.empty:
            df = df_raw.copy().reset_index()
            df.columns = [str(c[0] if isinstance(c, tuple) else c) for c in df.columns]
            df.rename(columns={'Date': 'date'}, inplace=True)
            df['date'] = pd.to_datetime(df['date']).dt.tz_localize(None)
            
            if 'HG=F' in df.columns and 'GC=F' in df.columns:
                df['Copper_Gold_Ratio'] = (df['HG=F'] / df['GC=F']) * 1000.0
                df['CG_MA50'] = df['Copper_Gold_Ratio'].rolling(50).mean()
            
            if 'HYG' in df.columns and 'TLT' in df.columns:
                df['HYG_TLT_Ratio'] = df['HYG'] / df['TLT']
                df['HT_MA50'] = df['HYG_TLT_Ratio'].rolling(50).mean()
                
            return df.dropna(subset=['date']).reset_index(drop=True)
    except Exception as e:
        print(f"Error fetching Risk-on / Risk-off ratios: {e}")
    return pd.DataFrame()

# ------------------------------------------------------------------
# 3. 个股量化、财务报表与半导体产业链数据获取函数
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
# 4. 个股期权微观情绪 (Put/Call Ratio 与 Max Pain 最大痛点)
# ------------------------------------------------------------------
@st.cache_data(ttl=60 * 60 * 2)
def get_stock_option_expirations(symbol: str):
    """
    快速获取个股所有可用的期权到期日列表
    """
    try:
        import yfinance as yf
        ticker = yf.Ticker(symbol)
        return list(ticker.options) if ticker.options else []
    except Exception as e:
        print(f"Error fetching option expirations for {symbol}: {e}")
        return []


@st.cache_data(ttl=60 * 60 * 2)
def get_stock_options_sentiment(symbol: str, target_expiration: str = None):
    """
    根据用户选定的到期日（或全部近月汇总）获取期权链数据，
    计算对应的 Put/Call Ratio (OI 与 Volume) 以及 Max Pain 最大痛点
    """
    try:
        import yfinance as yf
        ticker = yf.Ticker(symbol)
        expirations = list(ticker.options) if ticker.options else []
        if not expirations:
            return None

        is_aggregated = (target_expiration and "汇总" in target_expiration)

        if is_aggregated:
            # 聚合前 6 个核心活跃到期日的数据
            active_exps = expirations[:6]
            all_calls = []
            all_puts = []
            for exp in active_exps:
                try:
                    c = ticker.option_chain(exp)
                    if c.calls is not None and not c.calls.empty:
                        all_calls.append(c.calls[['strike', 'openInterest', 'volume']])
                    if c.puts is not None and not c.puts.empty:
                        all_puts.append(c.puts[['strike', 'openInterest', 'volume']])
                except Exception:
                    continue

            if not all_calls or not all_puts:
                return None

            df_calls_raw = pd.concat(all_calls).groupby('strike').sum().reset_index()
            df_puts_raw = pd.concat(all_puts).groupby('strike').sum().reset_index()
            active_exp_label = f"全市场近月汇总 (前 {len(active_exps)} 个交割日)"
        else:
            # 单一指定到期日（若未指定或不在列表中，默认使用最近的到期日）
            if not target_expiration or target_expiration not in expirations:
                selected_exp = expirations[0]
            else:
                selected_exp = target_expiration

            chain = ticker.option_chain(selected_exp)
            df_calls_raw = chain.calls.copy() if chain.calls is not None else pd.DataFrame()
            df_puts_raw = chain.puts.copy() if chain.puts is not None else pd.DataFrame()
            active_exp_label = selected_exp

        call_oi_total = df_calls_raw['openInterest'].sum() if ('openInterest' in df_calls_raw.columns) else 0
        put_oi_total = df_puts_raw['openInterest'].sum() if ('openInterest' in df_puts_raw.columns) else 0
        call_vol_total = df_calls_raw['volume'].sum() if ('volume' in df_calls_raw.columns) else 0
        put_vol_total = df_puts_raw['volume'].sum() if ('volume' in df_puts_raw.columns) else 0

        pcr_oi = (put_oi_total / call_oi_total) if call_oi_total > 0 else np.nan
        pcr_vol = (put_vol_total / call_vol_total) if call_vol_total > 0 else np.nan

        # 合并各行权价的未平仓合约数与成交量
        calls_sub = df_calls_raw[['strike', 'openInterest', 'volume']].rename(columns={'openInterest': 'call_oi', 'volume': 'call_vol'})
        puts_sub = df_puts_raw[['strike', 'openInterest', 'volume']].rename(columns={'openInterest': 'put_oi', 'volume': 'put_vol'})
        df_strikes = pd.merge(calls_sub, puts_sub, on='strike', how='outer').fillna(0).sort_values('strike').reset_index(drop=True)

        # 计算 Max Pain (期权买方总体收益最低点，即做市商损失最小点)
        strikes = df_strikes['strike'].values
        call_oi = df_strikes['call_oi'].values
        put_oi = df_strikes['put_oi'].values

        total_losses = []
        for s in strikes:
            call_payoff = np.sum(np.maximum(0, s - strikes) * call_oi)
            put_payoff = np.sum(np.maximum(0, strikes - s) * put_oi)
            total_losses.append(call_payoff + put_payoff)

        df_strikes['buyer_payoff'] = total_losses
        min_loss_idx = int(np.argmin(total_losses))
        max_pain_price = float(strikes[min_loss_idx])

        return {
            "symbol": symbol,
            "expiration": active_exp_label,
            "all_expirations": expirations,
            "call_oi_total": int(call_oi_total),
            "put_oi_total": int(put_oi_total),
            "pcr_oi": float(pcr_oi) if pd.notna(pcr_oi) else np.nan,
            "pcr_vol": float(pcr_vol) if pd.notna(pcr_vol) else np.nan,
            "max_pain_price": max_pain_price,
            "df_strikes": df_strikes
        }
    except Exception as e:
        print(f"Error fetching options sentiment for {symbol}: {e}")
        return None


# ------------------------------------------------------------------
# 5. 微观量价动量与波动率风控指标计算
# ------------------------------------------------------------------
def calculate_momentum_metrics(df_stock: pd.DataFrame):
    """
    计算微观量价动量与波动率风控指标:
    - ATR(14) 与 ATR%
    - Chandelier Exit 动态吊灯多头追踪止损位
    - 20D 均线偏离度 (Bias Ratio %)
    - 布林带带宽 (BandWidth %) 与 %B
    - 12-1M 经典学术动量 (Jegadeesh-Titman)
    """
    if df_stock is None or df_stock.empty or 'Close' not in df_stock.columns:
        return None

    df = df_stock.copy()
    if 'Date' not in df.columns and isinstance(df.index, pd.DatetimeIndex):
        df = df.reset_index().rename(columns={'index': 'Date'})

    high = df['High'] if 'High' in df.columns else df['Close']
    low = df['Low'] if 'Low' in df.columns else df['Close']
    close = df['Close']
    prev_close = close.shift(1)

    # 1. 真实波幅 (True Range) 与 14日 ATR
    tr1 = high - low
    tr2 = (high - prev_close).abs()
    tr3 = (low - prev_close).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr14 = tr.rolling(window=14).mean()
    atr_pct = (atr14 / close) * 100.0

    # 2. 吊灯止损 (Chandelier Exit): 过去 22 天最高价 - 3 * ATR14
    highest_22 = high.rolling(window=22).max()
    chandelier_exit = highest_22 - 3 * atr14

    # 3. 20D 均线偏离度 (Bias Ratio %)
    ma20 = close.rolling(window=20).mean()
    bias20 = ((close - ma20) / ma20) * 100.0

    # 4. 布林带带宽挤压 (BandWidth %) 与 %B
    std20 = close.rolling(window=20).std()
    bb_upper = ma20 + 2 * std20
    bb_lower = ma20 - 2 * std20
    bandwidth = ((bb_upper - bb_lower) / ma20) * 100.0
    pct_b = (close - bb_lower) / (bb_upper - bb_lower + 1e-9)

    # 5. 12-1M 经典学术动量 (剔除最近 1 个月短期反转噪音)
    mom_12_1 = np.nan
    if len(close) >= 252:
        close_t21 = close.iloc[-21]
        close_t252 = close.iloc[-252]
        if close_t252 > 0:
            mom_12_1 = ((close_t21 - close_t252) / close_t252) * 100.0
    elif len(close) >= 30:
        close_t21 = close.iloc[-21]
        close_start = close.iloc[0]
        if close_start > 0:
            mom_12_1 = ((close_t21 - close_start) / close_start) * 100.0

    df['ATR14'] = atr14
    df['ATR_Pct'] = atr_pct
    df['Chandelier_Exit'] = chandelier_exit
    df['Bias20'] = bias20
    df['BandWidth'] = bandwidth
    df['Pct_B'] = pct_b

    return {
        "latest_close": float(close.iloc[-1]),
        "latest_atr": float(atr14.iloc[-1]) if pd.notna(atr14.iloc[-1]) else np.nan,
        "latest_atr_pct": float(atr_pct.iloc[-1]) if pd.notna(atr_pct.iloc[-1]) else np.nan,
        "latest_chandelier": float(chandelier_exit.iloc[-1]) if pd.notna(chandelier_exit.iloc[-1]) else np.nan,
        "latest_bias20": float(bias20.iloc[-1]) if pd.notna(bias20.iloc[-1]) else np.nan,
        "latest_bandwidth": float(bandwidth.iloc[-1]) if pd.notna(bandwidth.iloc[-1]) else np.nan,
        "latest_pct_b": float(pct_b.iloc[-1]) if pd.notna(pct_b.iloc[-1]) else np.nan,
        "mom_12_1": float(mom_12_1) if pd.notna(mom_12_1) else np.nan,
        "df_metrics": df
    }


# ==================================================================
# 6. 新增 5 大宏观前瞻先导指标数据服务
# ==================================================================
@st.cache_data(ttl=60 * 60 * 4)
def get_move_index_data():
    """获取 ICE BofA MOVE 债市恐慌指数 (Yahoo Finance: ^MOVE)"""
    try:
        import yfinance as yf
        ticker = yf.Ticker("^MOVE")
        df = ticker.history(period="5y")
        if not df.empty:
            df = df.reset_index()
            if 'Date' in df.columns:
                df['date'] = pd.to_datetime(df['Date']).dt.tz_localize(None)
            df.rename(columns={'Close': 'MOVE'}, inplace=True)
            df['MOVE_MA20'] = df['MOVE'].rolling(20).mean()
            return df[['date', 'MOVE', 'MOVE_MA20']].dropna(subset=['date', 'MOVE']).reset_index(drop=True)
    except Exception as e:
        print(f"Error fetching MOVE index: {e}")
    return pd.DataFrame()


@st.cache_data(ttl=60 * 60 * 6)
def get_term_premium_data():
    """获取纽约联储 ACM 10 年期期限溢价 (THREEFYTP10) 与 10Y 名义收益率 (DGS10)"""
    try:
        df_tp = _fetch_fred_series_observations("THREEFYTP10", "Term_Premium", "2000-01-01")
        df_10y = _fetch_fred_series_observations("DGS10", "DGS10", "2000-01-01")
        if not df_tp.empty and not df_10y.empty:
            merged = pd.merge(df_tp, df_10y, on="date", how="inner").sort_values("date").reset_index(drop=True)
            merged["Risk_Neutral_Rate"] = merged["DGS10"] - merged["Term_Premium"]
            return merged
        elif not df_tp.empty:
            return df_tp
    except Exception as e:
        print(f"Error fetching Term Premium data: {e}")
    return pd.DataFrame()


@st.cache_data(ttl=60 * 60 * 6)
def get_epu_data():
    """获取经济政策不确定性指数 (USEPUINDXD) 并计算 30D 移动平滑均线"""
    try:
        df = _fetch_fred_series_observations("USEPUINDXD", "EPU", "2000-01-01")
        if not df.empty:
            df["EPU_MA30"] = df["EPU"].rolling(30).mean()
            return df
    except Exception as e:
        print(f"Error fetching EPU data: {e}")
    return pd.DataFrame()


@st.cache_data(ttl=60 * 60 * 6)
def get_commercial_loans_data():
    """获取全美商业银行工商业贷款规模 (BUSLOANS) 与 YoY 同比增速"""
    try:
        df = _fetch_fred_series_observations("BUSLOANS", "Loans_Billion", "2000-01-01")
        if not df.empty:
            df["YoY_pct"] = df["Loans_Billion"].pct_change(12) * 100.0
            return df
    except Exception as e:
        print(f"Error fetching Commercial Loans data: {e}")
    return pd.DataFrame()


@st.cache_data(ttl=60 * 60 * 6)
def get_personal_saving_rate_data():
    """获取美国居民个人储蓄率 (PSAVERT) 与 12 个月移动均线"""
    try:
        df = _fetch_fred_series_observations("PSAVERT", "Saving_Rate", "2000-01-01")
        if not df.empty:
            df["Saving_MA12"] = df["Saving_Rate"].rolling(12).mean()
            return df
    except Exception as e:
        print(f"Error fetching Personal Saving Rate data: {e}")
    return pd.DataFrame()


