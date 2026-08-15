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

def get_file_updated_time_eastern(file_path):
    if os.path.exists(file_path):
        mtime = os.path.getmtime(file_path)
        dt_utc = datetime.datetime.fromtimestamp(mtime, tz=datetime.timezone.utc)
        dt_eastern = dt_utc.astimezone(ZoneInfo("America/New_York"))
        return dt_eastern.strftime("%Y-%m-%d %H:%M:%S EDT")
    return "未知"

def get_current_time_str_eastern():
    return get_eastern_now().strftime("%Y-%m-%d %H:%M:%S EDT")

def _get_fred_api_key():
    # 优先从环境变量或 Streamlit secrets 读取
    api_key = os.environ.get("FRED_API_KEY", "")
    if not api_key:
        try:
            api_key = st.secrets.get("FRED_API_KEY", "")
        except Exception:
            api_key = ""
    return api_key

@st.cache_data(ttl=60 * 60 * 6)
def _fetch_fred_series_observations(series_id, value_col, observation_start="2000-01-01"):
    api_key = _get_fred_api_key()
    if api_key:
        url = f"https://api.stlouisfed.org/fred/series/observations?series_id={series_id}&api_key={api_key}&file_type=json&observation_start={observation_start}"
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
                            records.append({'date': o['date'], value_col: float(val)})
                        except Exception:
                            continue
                df = pd.DataFrame(records)
                if not df.empty:
                    df['date'] = pd.to_datetime(df['date'])
                    return df.sort_values('date').reset_index(drop=True)
        except Exception as e:
            print(f"Error fetching {series_id} with API: {e}")

    # Fallback: 无 API Key 时直接下载公开 CSV
    csv_url = f"https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}&cosd={observation_start}"
    try:
        req = urllib.request.Request(csv_url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=10) as response:
            df = pd.read_csv(response)
            if not df.empty:
                df.columns = ['date', value_col]
                df['date'] = pd.to_datetime(df['date'])
                df[value_col] = pd.to_numeric(df[value_col], errors='coerce')
                df = df.dropna().sort_values('date').reset_index(drop=True)
                return df
    except Exception as e:
        print(f"Error fetching {series_id} fallback CSV: {e}")

    return pd.DataFrame()

# ------------------------------------------------------------------
# 2. 宏观核心指标数据获取与缓存
# ------------------------------------------------------------------
@st.cache_data(ttl=60 * 60 * 6)
def get_vix_data():
    return _fetch_fred_series_observations("VIXCLS", "VIX", "2010-01-01")

@st.cache_data(ttl=60 * 30)
def get_cnn_fear_and_greed_data():
    url = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Referer": "https://www.cnn.com/markets/fear-and-greed",
        "Accept": "application/json"
    }
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=8) as response:
            res_data = json.loads(response.read().decode('utf-8'))
            
            fg_data = res_data.get("fear_and_greed", {})
            hist_data = res_data.get("fear_and_greed_historical", {}).get("data", [])
            
            score = fg_data.get("score")
            rating = fg_data.get("rating")
            previous_close = fg_data.get("previous_close")
            previous_1_week = fg_data.get("previous_1_week")
            
            df_hist = pd.DataFrame(hist_data)
            if not df_hist.empty:
                df_hist["date"] = pd.to_datetime(df_hist["x"], unit="ms").dt.tz_localize(None)
                df_hist["Score"] = df_hist["y"].astype(float)
                df_hist = df_hist[["date", "Score", "rating"]].sort_values("date").reset_index(drop=True)
            
            return {
                "latest_score": score,
                "latest_rating": rating,
                "previous_close": previous_close,
                "previous_1_week": previous_1_week,
                "df_hist": df_hist
            }
    except Exception as e:
        print(f"Error fetching CNN Fear & Greed: {e}")
        
    try:
        import requests
        r = requests.get(url, headers=headers, timeout=8)
        if r.status_code == 200:
            res_data = r.json()
            fg_data = res_data.get("fear_and_greed", {})
            hist_data = res_data.get("fear_and_greed_historical", {}).get("data", [])
            score = fg_data.get("score")
            rating = fg_data.get("rating")
            previous_close = fg_data.get("previous_close")
            previous_1_week = fg_data.get("previous_1_week")
            df_hist = pd.DataFrame(hist_data)
            if not df_hist.empty:
                df_hist["date"] = pd.to_datetime(df_hist["x"], unit="ms").dt.tz_localize(None)
                df_hist["Score"] = df_hist["y"].astype(float)
                df_hist = df_hist[["date", "Score", "rating"]].sort_values("date").reset_index(drop=True)
            return {
                "latest_score": score,
                "latest_rating": rating,
                "previous_close": previous_close,
                "previous_1_week": previous_1_week,
                "df_hist": df_hist
            }
    except Exception as e2:
        print(f"Fallback requests error for CNN Fear & Greed: {e2}")

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
        df_iorb['date'] = pd.to_datetime(df_sofr['date']) if df_iorb.empty else pd.to_datetime(df_iorb['date'])
        merged = pd.merge(df_sofr, df_iorb, on="date", how="inner").sort_values("date")
        if not merged.empty:
            merged["Spread_bps"] = (merged["SOFR"] - merged["IORB"]) * 100
            return merged.reset_index(drop=True)
    elif not df_sofr.empty:
        df_sofr['date'] = pd.to_datetime(df_sofr['date'])
        return df_sofr
    return pd.DataFrame()

@st.cache_data(ttl=60 * 60 * 6)
def get_fed_net_liquidity_data():
    df_walcl = _fetch_fred_series_observations("WALCL", "WALCL", "2018-01-01")
    df_tga = _fetch_fred_series_observations("WTREGEN", "TGA", "2018-01-01")
    df_rrp = _fetch_fred_series_observations("RRPONTSYD", "RRP", "2018-01-01")
    df_reserves = _fetch_fred_series_observations("WRBWFRBL", "Reserves", "2018-01-01")
    
    if not df_walcl.empty:
        df_walcl['date'] = pd.to_datetime(df_walcl['date'])
        df_tga['date'] = pd.to_datetime(df_tga['date']) if not df_tga.empty else pd.Series(dtype='datetime64[ns]')
        df_rrp['date'] = pd.to_datetime(df_rrp['date']) if not df_rrp.empty else pd.Series(dtype='datetime64[ns]')
        df_reserves['date'] = pd.to_datetime(df_reserves['date']) if not df_reserves.empty else pd.Series(dtype='datetime64[ns]')
        
        merged = df_walcl.copy()
        if not df_tga.empty:
            merged = pd.merge(merged, df_tga, on="date", how="outer")
        else:
            merged["TGA"] = 0.0
            
        if not df_rrp.empty:
            merged = pd.merge(merged, df_rrp, on="date", how="outer")
        else:
            merged["RRP"] = 0.0
            
        if not df_reserves.empty:
            merged = pd.merge(merged, df_reserves, on="date", how="outer")
        else:
            merged["Reserves"] = np.nan
            
        merged = merged.sort_values("date").reset_index(drop=True)
        merged["WALCL"] = merged["WALCL"].ffill()
        merged["TGA"] = merged["TGA"].ffill().fillna(0.0)
        merged["RRP"] = merged["RRP"].ffill().fillna(0.0)
        
        # TGA 原始数据为百万美元，需统一为百万美元基准计算后转换为万亿美元
        merged["Fed_Net_Liquidity_Tn"] = (merged["WALCL"] - (merged["TGA"] / 1.0) - (merged["RRP"] * 1000.0 if merged["RRP"].max() < 5000 else merged["RRP"])) / 1_000_000.0
        
        if "Reserves" in merged.columns and not merged["Reserves"].dropna().empty:
            merged["Bank_Reserves_Tn"] = merged["Reserves"].ffill() / 1_000_000.0
            
        merged = merged.dropna(subset=["Fed_Net_Liquidity_Tn"]).reset_index(drop=True)
        return merged
    return pd.DataFrame()

@st.cache_data(ttl=60 * 60 * 6)
def get_gold_oil_ratio_data():
    # 黄金：GC=F，原油：CL=F
    try:
        import yfinance as yf
        gold = yf.Ticker("GC=F").history(period="10y")
        oil = yf.Ticker("CL=F").history(period="10y")
        
        if not gold.empty and not oil.empty:
            df_g = gold[['Close']].reset_index()
            df_g['date'] = pd.to_datetime(df_g['Date']).dt.tz_localize(None)
            df_g = df_g[['date', 'Close']].rename(columns={'Close': 'Gold'})
            
            df_o = oil[['Close']].reset_index()
            df_o['date'] = pd.to_datetime(df_o['Date']).dt.tz_localize(None)
            df_o = df_o[['date', 'Close']].rename(columns={'Close': 'Oil'})
            
            merged = pd.merge(df_g, df_o, on='date', how='inner')
            merged['gold_oil_ratio'] = merged['Gold'] / merged['Oil']
            return merged.dropna().sort_values('date').reset_index(drop=True)
    except Exception as e:
        print(f"Error calculating Gold/Oil Ratio: {e}")
        
    return pd.DataFrame()

@st.cache_data(ttl=60 * 60 * 12)
def get_top10_holdings_data():
    # S&P 500 前十大持仓股及最新真实近似权重数据 (总计约 ~39.30%)
    data = [
        {"Company": "NVIDIA (NVDA)", "Weight_Pct": 7.90},
        {"Company": "Apple (AAPL)", "Weight_Pct": 7.10},
        {"Company": "Microsoft (MSFT)", "Weight_Pct": 6.80},
        {"Company": "Amazon (AMZN)", "Weight_Pct": 4.10},
        {"Company": "Meta Platforms (META)", "Weight_Pct": 3.20},
        {"Company": "Alphabet Cl A (GOOGL)", "Weight_Pct": 2.60},
        {"Company": "Alphabet Cl C (GOOG)", "Weight_Pct": 2.20},
        {"Company": "Berkshire Hathaway (BRK.B)", "Weight_Pct": 1.90},
        {"Company": "Broadcom (AVGO)", "Weight_Pct": 1.80},
        {"Company": "Eli Lilly (LLY)", "Weight_Pct": 1.70},
    ]
    df = pd.DataFrame(data)
    df["Cum_Weight"] = df["Weight_Pct"].cumsum()
    return df


# ------------------------------------------------------------------
# 3. 个股追踪与基本面/估值数据抓取函数
# ------------------------------------------------------------------
@st.cache_data(ttl=60 * 30)
def get_stock_historical_data(symbol: str, period: str = "5y"):
    """
    通过 yfinance 获取单只股票的历史 OHLCV 价格数据
    """
    try:
        import yfinance as yf
        ticker = yf.Ticker(symbol.strip().upper())
        df = ticker.history(period=period, auto_adjust=True)
        if df is not None and not df.empty:
            df = df.reset_index()
            if 'Date' in df.columns:
                df['Date'] = pd.to_datetime(df['Date']).dt.tz_localize(None)
            elif 'date' in df.columns:
                df.rename(columns={'date': 'Date'}, inplace=True)
                df['Date'] = pd.to_datetime(df['Date']).dt.tz_localize(None)
            return df
    except Exception as e:
        print(f"Error fetching historical data for {symbol}: {e}")

    try:
        import yfinance as yf
        df = yf.download(symbol.strip().upper(), period=period, progress=False, auto_adjust=True)
        if df is not None and not df.empty:
            df = df.reset_index()
            if 'Date' in df.columns:
                df['Date'] = pd.to_datetime(df['Date']).dt.tz_localize(None)
            return df
    except Exception as e:
        print(f"Fallback download error for {symbol}: {e}")

    return pd.DataFrame()

@st.cache_data(ttl=60 * 60)
def get_stock_fundamentals(symbol: str):
    """
    通过 yfinance 获取个股基本面、估值倍数与财务质量指标
    """
    clean_sym = symbol.strip().upper()
    try:
        import yfinance as yf
        ticker = yf.Ticker(clean_sym)
        info = ticker.info
        if info and isinstance(info, dict) and len(info) > 5:
            return info
    except Exception as e:
        print(f"Error fetching info for {clean_sym}: {e}")

    return {}

@st.cache_data(ttl=60 * 60)
def get_stock_financial_statements(symbol: str):
    """
    抓取个股的季度与年度三大财务报表 (Income Statement, Balance Sheet, Cash Flow)
    并标准化提取：总营收、营收同比增速、毛利润、毛利率、营业利润、净利润、稀释EPS、
    经营现金流、资本开支、自由现金流、现金储备、总负债与股东权益。
    """
    clean_sym = symbol.strip().upper()
    try:
        import yfinance as yf
        ticker = yf.Ticker(clean_sym)
        
        q_inc = ticker.quarterly_income_stmt
        a_inc = ticker.income_stmt
        
        q_bs = ticker.quarterly_balance_sheet
        a_bs = ticker.balance_sheet
        
        q_cf = ticker.quarterly_cashflow
        a_cf = ticker.cashflow

        def _process_statements(inc_df, bs_df, cf_df, is_quarterly=True):
            if inc_df is None or inc_df.empty:
                return pd.DataFrame(), pd.DataFrame()
            
            cols = [c for c in inc_df.columns]
            cols_sorted = sorted(cols)
            
            dates_str = [pd.to_datetime(c).strftime("%Y-%m-%d") for c in cols_sorted]
            
            def _get_val(df, candidates, date_col):
                if df is None or df.empty:
                    return np.nan
                for cand in candidates:
                    if cand in df.index:
                        val = df.loc[cand, date_col]
                        if pd.notna(val):
                            try:
                                return float(val)
                            except Exception:
                                pass
                    lower_map = {str(k).lower().strip(): k for k in df.index}
                    if cand.lower().strip() in lower_map:
                        orig_k = lower_map[cand.lower().strip()]
                        val = df.loc[orig_k, date_col]
                        if pd.notna(val):
                            try:
                                return float(val)
                            except Exception:
                                pass
                return np.nan

            rev_list = []
            gp_list = []
            op_inc_list = []
            net_inc_list = []
            eps_list = []
            cfo_list = []
            capex_list = []
            fcf_list = []
            cash_list = []
            debt_list = []
            equity_list = []
            assets_list = []

            for col in cols_sorted:
                rev = _get_val(inc_df, ['Total Revenue', 'Operating Revenue', 'Revenue'], col)
                rev_list.append(rev)
                
                gp = _get_val(inc_df, ['Gross Profit', 'Gross Margin'], col)
                gp_list.append(gp)
                
                op = _get_val(inc_df, ['Operating Income', 'Operating Profit', 'EBIT', 'Operating Revenue'], col)
                op_inc_list.append(op)
                
                ni = _get_val(inc_df, ['Net Income Common Stockholders', 'Net Income', 'Net Income From Continuing Operation Net Minority Interest'], col)
                net_inc_list.append(ni)
                
                eps = _get_val(inc_df, ['Diluted EPS', 'Basic EPS', 'Diluted Average Shares'], col)
                eps_list.append(eps)
                
                cfo = _get_val(cf_df, ['Operating Cash Flow', 'Cash Flowsfromusedin Operating Activities', 'Cash Flow From Continuing Operating Activities'], col)
                cfo_list.append(cfo)
                
                capex = _get_val(cf_df, ['Capital Expenditure', 'Capital Expenditures', 'Purchase Of Property Plant And Equipment'], col)
                capex_list.append(capex)
                
                fcf = _get_val(cf_df, ['Free Cash Flow'], col)
                if np.isnan(fcf) and not np.isnan(cfo):
                    fcf = cfo - (abs(capex) if not np.isnan(capex) else 0.0)
                fcf_list.append(fcf)
                
                cash = _get_val(bs_df, ['Cash Cash Equivalents And Short Term Investments', 'Cash And Cash Equivalents', 'Cash Financial'], col)
                cash_list.append(cash)
                
                debt = _get_val(bs_df, ['Total Debt', 'Long Term Debt And Capital Securities', 'Current Debt And Capital Lease Obligation'], col)
                debt_list.append(debt)
                
                eq = _get_val(bs_df, ['Stockholders Equity', 'Common Stock Equity', 'Total Equity Gross Minority Interest'], col)
                equity_list.append(eq)
                
                ast_val = _get_val(bs_df, ['Total Assets'], col)
                assets_list.append(ast_val)

            summary_records = []
            
            row_rev = {"指标 (Metric)": "营业总收入 (Total Revenue)"}
            for d, r in zip(dates_str, rev_list):
                row_rev[d] = f"${r/1e9:,.2f} B" if not np.isnan(r) else "N/A"
            summary_records.append(row_rev)
            
            row_rev_growth = {"指标 (Metric)": "营收同比增速 (YoY Growth)"}
            for i, d in enumerate(dates_str):
                lag = 4 if is_quarterly else 1
                if i >= lag and not np.isnan(rev_list[i]) and not np.isnan(rev_list[i - lag]) and rev_list[i - lag] != 0:
                    growth = (rev_list[i] - rev_list[i - lag]) / abs(rev_list[i - lag]) * 100
                    row_rev_growth[d] = f"{growth:+.2f}%"
                else:
                    row_rev_growth[d] = "N/A"
            summary_records.append(row_rev_growth)
            
            row_gp = {"指标 (Metric)": "毛利润 (Gross Profit)"}
            row_gm = {"指标 (Metric)": "毛利率 (Gross Margin %)"}
            for d, gp, r in zip(dates_str, gp_list, rev_list):
                row_gp[d] = f"${gp/1e9:,.2f} B" if not np.isnan(gp) else "N/A"
                row_gm[d] = f"{(gp/r)*100:.2f}%" if not np.isnan(gp) and not np.isnan(r) and r != 0 else "N/A"
            summary_records.append(row_gp)
            summary_records.append(row_gm)
            
            row_op = {"指标 (Metric)": "营业利润 (Operating Income / EBIT)"}
            row_opm = {"指标 (Metric)": "营业利润率 (Operating Margin %)"}
            for d, op, r in zip(dates_str, op_inc_list, rev_list):
                row_op[d] = f"${op/1e9:,.2f} B" if not np.isnan(op) else "N/A"
                row_opm[d] = f"{(op/r)*100:.2f}%" if not np.isnan(op) and not np.isnan(r) and r != 0 else "N/A"
            summary_records.append(row_op)
            summary_records.append(row_opm)
            
            row_ni = {"指标 (Metric)": "净利润 (Net Income)"}
            row_npm = {"指标 (Metric)": "净利润率 (Net Margin %)"}
            for d, ni, r in zip(dates_str, net_inc_list, rev_list):
                row_ni[d] = f"${ni/1e9:,.2f} B" if not np.isnan(ni) else "N/A"
                row_npm[d] = f"{(ni/r)*100:.2f}%" if not np.isnan(ni) and not np.isnan(r) and r != 0 else "N/A"
            summary_records.append(row_ni)
            summary_records.append(row_npm)
            
            row_eps = {"指标 (Metric)": "稀释每股收益 (Diluted EPS)"}
            for d, eps in zip(dates_str, eps_list):
                row_eps[d] = f"${eps:.2f}" if not np.isnan(eps) else "N/A"
            summary_records.append(row_eps)
            
            row_cfo = {"指标 (Metric)": "经营活动现金流 (Operating Cash Flow)"}
            row_fcf = {"指标 (Metric)": "自由现金流 (Free Cash Flow)"}
            row_fcfm = {"指标 (Metric)": "自由现金流转化率 (FCF Margin %)"}
            for d, cfo, fcf, r in zip(dates_str, cfo_list, fcf_list, rev_list):
                row_cfo[d] = f"${cfo/1e9:,.2f} B" if not np.isnan(cfo) else "N/A"
                row_fcf[d] = f"${fcf/1e9:,.2f} B" if not np.isnan(fcf) else "N/A"
                row_fcfm[d] = f"{(fcf/r)*100:.2f}%" if not np.isnan(fcf) and not np.isnan(r) and r != 0 else "N/A"
            summary_records.append(row_cfo)
            summary_records.append(row_fcf)
            summary_records.append(row_fcfm)
            
            row_cash = {"指标 (Metric)": "现金及短期投资 (Cash & Short Term Inv.)"}
            row_debt = {"指标 (Metric)": "总负债 (Total Debt)"}
            row_eq = {"指标 (Metric)": "股东权益 / 净资产 (Stockholders' Equity)"}
            for d, cash, debt, eq in zip(dates_str, cash_list, debt_list, equity_list):
                row_cash[d] = f"${cash/1e9:,.2f} B" if not np.isnan(cash) else "N/A"
                row_debt[d] = f"${debt/1e9:,.2f} B" if not np.isnan(debt) else "N/A"
                row_eq[d] = f"${eq/1e9:,.2f} B" if not np.isnan(eq) else "N/A"
            summary_records.append(row_cash)
            summary_records.append(row_debt)
            summary_records.append(row_eq)

            df_summary = pd.DataFrame(summary_records)
            date_cols_reversed = list(reversed(dates_str))
            df_summary = df_summary[["指标 (Metric)"] + date_cols_reversed]

            df_trends = pd.DataFrame({
                "Period": dates_str,
                "Revenue_Bn": [r/1e9 if not np.isnan(r) else 0.0 for r in rev_list],
                "GrossProfit_Bn": [gp/1e9 if not np.isnan(gp) else 0.0 for gp in gp_list],
                "OperatingIncome_Bn": [op/1e9 if not np.isnan(op) else 0.0 for op in op_inc_list],
                "NetIncome_Bn": [ni/1e9 if not np.isnan(ni) else 0.0 for ni in net_inc_list],
                "FCF_Bn": [f/1e9 if not np.isnan(f) else 0.0 for f in fcf_list],
                "GrossMargin_Pct": [(gp/r)*100 if not np.isnan(gp) and not np.isnan(r) and r != 0 else np.nan for gp, r in zip(gp_list, rev_list)],
                "OperatingMargin_Pct": [(op/r)*100 if not np.isnan(op) and not np.isnan(r) and r != 0 else np.nan for op, r in zip(op_inc_list, rev_list)],
                "NetMargin_Pct": [(ni/r)*100 if not np.isnan(ni) and not np.isnan(r) and r != 0 else np.nan for ni, r in zip(net_inc_list, rev_list)],
            })

            return df_summary, df_trends

        q_summary, q_trends = _process_statements(q_inc, q_bs, q_cf, is_quarterly=True)
        a_summary, a_trends = _process_statements(a_inc, a_bs, a_cf, is_quarterly=False)

        return {
            "q_summary": q_summary,
            "q_trends": q_trends,
            "a_summary": a_summary,
            "a_trends": a_trends
        }
    except Exception as e:
        print(f"Error fetching statements for {clean_sym}: {e}")

    return {}

def calculate_reverse_dcf(current_price: float, shares_out: float, base_fcf: float, wacc: float = 0.09, g: float = 0.025, years: int = 5, total_cash: float = 0.0, total_debt: float = 0.0):
    """
    反向 DCF 计算器：根据当前股价反推市场隐含的 FCF 复合年增长率 (Implied FCF CAGR)
    并生成不同 WACC 与不同增长率假设下的公允价值敏感性分析矩阵
    """
    if not current_price or current_price <= 0 or not shares_out or shares_out <= 0:
        return None

    target_equity_value = current_price * shares_out
    target_ev = target_equity_value - (total_cash - total_debt)

    if base_fcf <= 0 or wacc <= g:
        return None

    low, high = -0.50, 2.00
    implied_cagr = np.nan
    for _ in range(120):
        mid = (low + high) / 2.0
        pv_fcf = 0.0
        for t in range(1, years + 1):
            fcf_t = base_fcf * ((1.0 + mid) ** t)
            pv_fcf += fcf_t / ((1.0 + wacc) ** t)
        
        final_fcf = base_fcf * ((1.0 + mid) ** years)
        tv = (final_fcf * (1.0 + g)) / (wacc - g)
        pv_tv = tv / ((1.0 + wacc) ** years)
        calc_ev = pv_fcf + pv_tv
        
        if abs(calc_ev - target_ev) / target_ev < 1e-4:
            implied_cagr = mid
            break
        elif calc_ev < target_ev:
            low = mid
        else:
            high = mid

    wacc_list = [round(wacc - 0.015 + i * 0.005, 3) for i in range(7)]
    cagr_list = [round(0.05 + i * 0.05, 2) for i in range(8)]

    matrix_rows = []
    for w in wacc_list:
        if w <= g:
            continue
        row_dict = {"折现率 WACC": f"{w*100:.1f}%"}
        for c in cagr_list:
            pv_f = 0.0
            for t in range(1, years + 1):
                f_t = base_fcf * ((1.0 + c) ** t)
                pv_f += f_t / ((1.0 + w) ** t)
            f_end = base_fcf * ((1.0 + c) ** years)
            term_val = (f_end * (1.0 + g)) / (w - g)
            pv_t = term_val / ((1.0 + w) ** years)
            fair_ev = pv_f + pv_t
            fair_equity = fair_ev + (total_cash - total_debt)
            fair_price = fair_equity / shares_out
            row_dict[f"CAGR {c*100:.0f}%"] = f"${fair_price:.2f}"
        matrix_rows.append(row_dict)

    sensitivity_df = pd.DataFrame(matrix_rows)

    return {
        "implied_cagr": implied_cagr,
        "target_equity_value": target_equity_value,
        "target_ev": target_ev,
        "sensitivity_matrix": sensitivity_df
    }


# ------------------------------------------------------------------
# 4. 半导体产业链核心标的与横向比选数据
# ------------------------------------------------------------------
SEMI_BASKET = [
    {"symbol": "NVDA", "name": "NVIDIA", "role": "GPU & AI 训练/推理算力霸主"},
    {"symbol": "TSM", "name": "台积电 (TSMC)", "role": "全球晶圆代工龙头 & CoWoS 先进封装"},
    {"symbol": "ASML", "name": "ASML", "role": "High-NA EUV / DUV 光刻机独家垄断"},
    {"symbol": "AVGO", "name": "博通 (Broadcom)", "role": "AI 数据中心交换芯片 & 定制 ASIC 龙头"},
    {"symbol": "AMD", "name": "AMD", "role": "CPU / MI300 GPU 算力挑战者"},
    {"symbol": "MU", "name": "美光科技 (Micron)", "role": "HBM3e / DRAM / NAND 存储周期龙头"},
    {"symbol": "AMAT", "name": "应用材料 (AMAT)", "role": "薄膜沉积 / 刻蚀 / CMP 综合设备巨头"},
    {"symbol": "LRCX", "name": "泛林集团 (Lam Research)", "role": "3D NAND 垂直刻蚀与沉积设备霸主"},
    {"symbol": "KLAC", "name": "科磊 (KLA Corp)", "role": "芯片前道良率检测与过程控制垄断"},
    {"symbol": "QCOM", "name": "高通 (Qualcomm)", "role": "端侧 AI / 骁龙处理器 / 智能车载芯片"},
    {"symbol": "ARM", "name": "ARM Holdings", "role": "低功耗 CPU 架构指令集 & IP 授权"},
    {"symbol": "TXN", "name": "德州仪器 (TI)", "role": "模拟芯片 / 工业与汽车电源管理基石"},
    {"symbol": "INTC", "name": "英特尔 (Intel)", "role": "x86 数据中心 CPU & IFS 晶圆制造转型"},
    {"symbol": "SOXX", "name": "费城半导体 ETF (SOXX)", "role": "半导体行业整体市值基准 ETF"},
    {"symbol": "SMH", "name": "VanEck 半导体 ETF (SMH)", "role": "半导体头部加权龙头指数 ETF"},
]

@st.cache_data(ttl=60 * 30)
def get_semiconductor_comparative_prices(symbols_list: list):
    """
    获取半导体标的的历史收盘价序列，用于计算归一化累计收益率对比
    """
    try:
        import yfinance as yf
        data = yf.download(symbols_list, period="5y", progress=False, auto_adjust=True)
        if data is not None and not data.empty:
            if 'Close' in data:
                close_df = data['Close'].copy()
            else:
                close_df = data.copy()
            close_df = close_df.reset_index()
            if 'Date' in close_df.columns:
                close_df['Date'] = pd.to_datetime(close_df['Date']).dt.tz_localize(None)
            return close_df
    except Exception as e:
        print(f"Error fetching semiconductor prices: {e}")

    return pd.DataFrame()

@st.cache_data(ttl=60 * 60)
def get_semiconductor_matrix_data():
    """
    抓取半导体核心标的的核心估值指标与财务比选矩阵
    """
    matrix_rows = []
    import yfinance as yf
    
    for item in SEMI_BASKET:
        sym = item["symbol"]
        role = item["role"]
        name = item["name"]
        
        info = {}
        try:
            t = yf.Ticker(sym)
            info = t.info or {}
        except Exception:
            pass

        price = info.get("currentPrice") or info.get("regularMarketPrice") or info.get("previousClose")
        mcap = info.get("marketCap")
        mcap_b = (mcap / 1e9) if mcap else None
        
        pe_ttm = info.get("trailingPE")
        pe_fwd = info.get("forwardPE")
        ps_ttm = info.get("priceToSalesTrailing12Months")
        gm = info.get("grossMargins")
        gm_pct = (gm * 100) if gm is not None else None
        
        wk52_change = info.get("52WeekChange")
        change_pct = (wk52_change * 100) if wk52_change is not None else None
        
        matrix_rows.append({
            "代码 (Symbol)": sym,
            "公司名称": name,
            "细分定位 / 产业链角色": role,
            "最新价 (USD)": f"${price:.2f}" if price else "N/A",
            "市值 ($B)": f"${mcap_b:,.1f}B" if mcap_b else "N/A",
            "PE (TTM)": f"{pe_ttm:.1f}x" if pe_ttm else "N/A",
            "Forward PE": f"{pe_fwd:.1f}x" if pe_fwd else "N/A",
            "PS (TTM)": f"{ps_ttm:.1f}x" if ps_ttm else "N/A",
            "毛利率 (%)": f"{gm_pct:.1f}%" if gm_pct is not None else "N/A",
            "近1年涨跌幅": f"{change_pct:+.1f}%" if change_pct is not None else "N/A"
        })

    return pd.DataFrame(matrix_rows)


# ------------------------------------------------------------------
# 5. Streamlit 主页面应用渲染 (多 Tab 容器架构)
# ------------------------------------------------------------------
st.set_page_config(page_title="Macro & Equity Quantitative Dashboard", layout="wide", page_icon="📈")

st.title("📈 美股宏观经济、市场宽度与产业量化看板")

FRED_API_KEY = _get_fred_api_key()
if not FRED_API_KEY:
    st.sidebar.warning("⚠️ 未检测到 FRED_API_KEY，改用公开 FRED 数据源。")

current_et_str = get_current_time_str_eastern()

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
        st.error("未能加载国债收益率数据。")

    # --- 2. S&P 500 市场宽度广度 ---
    st.markdown("---")
    render_market_breadth_ui()

    # --- 3. 市场情绪量化指标：CBOE VIX 恐慌指数 & CNN 恐慌与贪婪指数 ---
    st.markdown("---")
    st.header("📊 市场情绪量化指标 (VIX & CNN Fear/Greed Index)")

    e_col1, e_col2 = st.columns(2)

    with e_col1:
        st.subheader("CBOE VIX 恐慌指数")
        df_vix = get_vix_data()
        if not df_vix.empty:
            latest_vix_date = pd.to_datetime(df_vix['date'].iloc[-1]).strftime('%Y-%m-%d')
            latest_vix_val = df_vix['VIX'].iloc[-1]
            
            st.caption(f"🕒 数据刷新时间 (美东时间): **{current_et_str}** | 最新公布日期: **{latest_vix_date}**")
            
            vc1, vc2 = st.columns(2)
            vc1.metric("最新 VIX 指数", f"{latest_vix_val:.2f}", delta="情绪分界: 20.0", delta_color="inverse" if latest_vix_val > 20.0 else "normal")
            vc2.metric("高恐慌警戒线", "30.00")

            vix_y_range = None
            if st.checkbox("手动自定义 VIX Y 轴范围", key="vix_manual_y"):
                val_vix = df_vix['VIX']
                v_min = float(val_vix.dropna().min())
                v_max = float(val_vix.dropna().max())
                vix_y_range = st.slider("VIX Y 轴范围", round(max(0.0, v_min - 5.0), 1), round(v_max + 10.0, 1), (round(v_min, 1), round(v_max, 1)), 0.5, key="vix_y_slider")

            fig_vix = create_vix_chart(df_vix, y_range=vix_y_range, timeframe=macro_tf)
            if fig_vix:
                st.plotly_chart(fig_vix, use_container_width=True)
                with st.expander("💡 CBOE VIX 恐慌指数解读指南", expanded=False):
                    st.markdown("""
                    * **指标含义**：芝加哥期权交易所 (CBOE) 波动率指数 (VIX)，反映市场对未来 30 天 S&P 500 年化波动率的预判。
                    * **情绪分界 (20.0)**：
                      * **VIX $< 15$**：低波动、高风险偏好阶段。
                      * **$15 \\le \\text{VIX} < 20$**：常态合理波动区间。
                      * **$\\text{VIX} \\ge 20$**：情绪焦虑升温，避险需求增加。
                      * **$\\text{VIX} \\ge 30$**：高恐慌预警，对应急跌抛售或阶段性恐慌底探明。
                    """)
        else:
            st.info("VIX 恐慌指数数据加载中或不可用。")

    with e_col2:
        st.subheader("CNN 恐慌与贪婪指数 (Fear & Greed)")
        cnn_dict = get_cnn_fear_and_greed_data()
        if cnn_dict:
            score = cnn_dict.get("latest_score")
            rating = str(cnn_dict.get("latest_rating", "")).title()
            prev_close = cnn_dict.get("previous_close")
            prev_1w = cnn_dict.get("previous_1_week")
            df_fgi = cnn_dict.get("df_hist")

            st.caption(f"🕒 数据刷新时间 (美东时间): **{current_et_str}** | CNN 官方实时指数")

            fc1, fc2, fc3 = st.columns(3)
            if score is not None:
                fc1.metric("当前分值 (0-100)", f"{score:.1f}", delta=f"状态: {rating}")
            if prev_close is not None:
                fc2.metric("前一交易日收盘", f"{prev_close:.1f}")
            if prev_1w is not None:
                fc3.metric("1 周前得分", f"{prev_1w:.1f}")

            fgi_y_range = None
            if st.checkbox("手动自定义 CNN 指数 Y 轴范围", key="fgi_manual_y"):
                fgi_y_range = st.slider("FGI Y 轴范围", 0.0, 100.0, (0.0, 100.0), 5.0, key="fgi_y_slider")

            if df_fgi is not None and not df_fgi.empty:
                fig_fgi = create_cnn_fear_greed_chart(df_fgi, y_range=fgi_y_range, timeframe=macro_tf)
                if fig_fgi:
                    st.plotly_chart(fig_fgi, use_container_width=True)
                    with st.expander("💡 CNN 恐慌与贪婪指数解读指南", expanded=False):
                        st.markdown("""
                        * **指标构成**：综合了市场动量 (Market Momentum)、股价强度 (Stock Price Strength)、股价广度 (Stock Price Breadth)、认沽/认购期权比率 (Put/Call Ratio)、垃圾债利差 (Junk Bond Demand)、避险需求 (Safe Haven Demand) 和市场波动率 (Market Volatility) 7 维指标。
                        * **分值区间 (0 - 100)**：
                          * **0 – 25 (极度恐慌 Extreme Fear)**：情绪陷于极度悲观，常对应逆向投资博弈买点。
                          * **25 – 45 (恐慌 Fear)**：避险情绪主导。
                          * **45 – 55 (中性 Neutral)**：情绪相对均衡。
                          * **55 – 75 (贪婪 Greed)**：风险偏好升温。
                          * **75 – 100 (极度贪婪 Extreme Greed)**：市场情绪过热自满，需警惕回调风险。
                        """)
            else:
                st.info("CNN 恐慌与贪婪指数历史趋势加载中。")
        else:
            st.info("CNN 恐慌与贪婪指数实时数据加载中或不可用。")

    # --- 4. SOFR - IORB 利差 & 前十大持仓集中度模块 ---
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
                with st.expander("💡 SOFR - IORB 资金面体温计解读指南", expanded=False):
                    st.markdown("""
                    * **指标构成**：
                      * **SOFR (担保隔夜融资利率)**：回购市场非银及银行的真实隔夜借贷成本。
                      * **IORB (准备金利率)**：美联储向商业银行存放于央行的准备金支付的利息（政策锚点）。
                    * **解读逻辑**：
                      * **正常区间 ($\le 0$ 或 $< +3$ bps)**：商业银行体系准备金充裕，隔夜批发市场资金供需平稳。
                      * **预警信号 (利差 $> +3$ bps)**：非银与银行资金需求激增或银行出借意愿降低，提示隔夜微观流动性出现结构性摩擦或紧缺。
                    """)
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
                with st.expander("💡 SOFR - IORB 资金面体温计解读指南", expanded=False):
                    st.markdown("""
                    * **指标构成**：
                      * **SOFR (担保隔夜融资利率)**：回购市场非银及银行的真实隔夜借贷成本。
                      * **IORB (准备金利率)**：美联储向商业银行存放于央行的准备金支付的利息（政策锚点）。
                    * **解读逻辑**：
                      * **正常区间 ($\le 0$ 或 $< +3$ bps)**：商业银行体系准备金充裕，隔夜批发市场资金供需平稳。
                      * **预警信号 (利差 $> +3$ bps)**：非银与银行资金需求激增或银行出借意愿降低，提示隔夜微观流动性出现结构性摩擦或紧缺。
                    """)
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
                with st.expander("💡 S&P 500 前十大持仓集中度解读指南", expanded=False):
                    st.markdown("""
                    * **指标含义**：前十大持仓股（NVDA, AAPL, MSFT, AMZN, META, GOOGL, GOOG, BRK-B, AVGO, LLY）在标普 500 指数中的合计权重占比（目前约 ~39.30%）。
                    * **预警红线 (39.00%)**：集中度处于历史极高位表明指数涨幅高度依赖极少数巨头（Top-heavy），大盘整体易受单一巨头财报波动冲击；关注等权重指数 (RSP) 与市值权重指数的背离。
                    """)
        else:
            st.info("前十大持仓集中度数据加载中。")

    # --- 5. FRED 宏观指标与流动性追踪 ---
    st.markdown("---")
    st.header("📊 宏观指标与流动性追踪")

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
                with st.expander("💡 10Y TIPS 实际利率 & 通胀预期解读指南", expanded=False):
                    st.markdown("""
                    * **费雪拆解**：$\\text{10Y 名义收益率} = \\text{10Y TIPS 实际利率} + \\text{10Y 盈亏平衡通胀率}$。
                    * **10Y TIPS 实际利率 (Real Yield)**：
                      * 代表全社会真实无风险资本成本（资产定价之锚）。
                      * **估值挤压**：当 10Y 实际利率 $> 2.0\\%$ 或快速上行时，无风险真实折现率升高，压制科技股等高估值资产。
                    * **通胀预期 (Breakeven Inflation)**：
                      * 反映市场交易出的未来 10 年平均通胀中枢。若实际利率升而通胀预期降，说明货币紧缩在真实压制通胀。
                    """)
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
                with st.expander("💡 美联储净流动性 & 银行准备金解读指南", expanded=False):
                    st.markdown("""
                    * **计算公式**：$\\text{美联储净流动性} = \\text{美联储总资产 (WALCL)} - \\text{财政部账户 (TGA)} - \\text{隔夜逆回购 (RRP)}$。
                    * **传导机制**：
                      * **TGA / RRP 上升**：资金抽离市场（流动性收紧）。
                      * **WALCL 扩表 / RRP 释放**：资金注入银行体系（流动性改善）。
                    * **股市先行指标**：美联储净流动性增减拐点通常**领先标普 500 指数 2–4 周**，是量化微观流动性宽裕度的核心先行指标。
                    """)
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
                with st.expander("💡 芝加哥联储全国金融条件指数 (NFCI) 解读指南", expanded=False):
                    st.markdown("""
                    * **指标含义**：综合了货币市场、股权市场、债权市场以及传统/影子银行体系的 100+ 个微观金融指标。
                    * **零轴分界**：
                      * **NFCI $< 0$**：全美金融条件比历史平均水平更宽松。
                      * **NFCI $> 0$**：金融条件处于紧缩状态，陡峭上行提示信用紧缩与市场波动率上升。
                    """)
        else:
            st.info("NFCI 数据加载中或不可用。")

    with m_col4:
        df_highyield = get_highyield_data()
        if not df_highyield.empty:
            latest_hy_date = pd.to_datetime(df_highyield['date'].iloc[-1]).strftime('%Y-%m-%d') if 'date' in df_highyield.columns else "最新"
            st.subheader("高收益债信用利差 (US High Yield Spread)")
            st.caption(f"🕒 数据刷新时间 (美东时间): **{current_et_str}** | 最新公布日期: **{latest_hy_date}**")

            hy_y_range = None
            if st.checkbox("手动自定义高收益债利差 Y 轴范围", key="hy_manual_y"):
                val_h = df_highyield['Value'] if 'Value' in df_highyield.columns else df_highyield.iloc[:, 1]
                h_min = float(val_h.dropna().min())
                h_max = float(val_h.dropna().max())
                hy_y_range = st.slider("高收益债利差 Y 轴范围 (%)", round(h_min - 1.0, 1), round(h_max + 1.0, 1), (round(h_min, 1), round(h_max, 1)), 0.1, key="hy_slider")

            fig_hy = create_credit_spread_chart(df_highyield, y_range=hy_y_range, timeframe=macro_tf)
            if fig_hy:
                st.plotly_chart(fig_hy, use_container_width=True)
                with st.expander("💡 高收益债信用利差解读指南", expanded=False):
                    st.markdown("""
                    * **指标含义**：ICE BofA 美国高收益企业债指数期权调整利差 (OAS)，反映投机级企业违约风险补偿要求。
                    * **风险阈值**：
                      * **利差 $< 3.5\\%$**：市场风险偏好极高，流动性泛滥。
                      * **利差 $3.5\\% - 5.0\\%$**：常态周期区间。
                      * **利差 $> 5.0\\%$ (突破警戒线)**：企业再融资压力显著加大，提示信用收缩或经济衰退风险。
                    """)
        else:
            st.info("高收益债信用利差数据加载中或不可用。")

    # 第三排：失业率 + 美联储总资产
    m_col5, m_col6 = st.columns(2)

    with m_col5:
        df_unrate = get_unemployment_data()
        if not df_unrate.empty:
            latest_unemp_date = pd.to_datetime(df_unrate['date'].iloc[-1]).strftime('%Y-%m-%d')
            st.subheader("美国失业率 (UNRATE)")
            st.caption(f"🕒 数据刷新时间 (美东时间): **{current_et_str}** | 最新公布日期: **{latest_unemp_date}**")

            unrate_y_range = None
            if st.checkbox("手动自定义失业率 Y 轴范围", key="unrate_manual_y"):
                val_u = df_unrate['Unemployment_Rate'] if 'Unemployment_Rate' in df_unrate.columns else df_unrate.iloc[:, 1]
                u_min = float(val_u.dropna().min())
                u_max = float(val_u.dropna().max())
                unrate_y_range = st.slider("失业率 Y 轴范围 (%)", round(max(0.0, u_min - 1.0), 1), round(u_max + 1.0, 1), (round(u_min, 1), round(u_max, 1)), 0.1, key="unrate_slider")

            fig_unemp = create_unemployment_chart(df_unrate, y_range=unrate_y_range, timeframe=macro_tf)
            if fig_unemp:
                st.plotly_chart(fig_unemp, use_container_width=True)
                with st.expander("💡 美国失业率 (UNRATE) 解读指南", expanded=False):
                    st.markdown("""
                    * **自然失业率基准 (~4.0%)**：长期中枢水平。
                    * **萨姆规则衰退指标 (Sahm Rule)**：当失业率的 3 个月移动平均值较过去 12 个月的最低点上升 **0.50 个百分点或以上**时，标志着经济已步入衰退早期阶段。
                    """)
        else:
            st.info("失业率数据加载中或不可用。")

    with m_col6:
        df_fed = get_fed_balance_sheet_data()
        if not df_fed.empty:
            latest_fed_date = pd.to_datetime(df_fed['date'].iloc[-1]).strftime('%Y-%m-%d')
            st.subheader("美联储资产负债表 (WALCL)")
            st.caption(f"🕒 数据刷新时间 (美东时间): **{current_et_str}** | 最新公布日期: **{latest_fed_date}**")

            fed_y_range = None
            if st.checkbox("手动自定义美联储总资产 Y 轴范围", key="fed_manual_y"):
                val_f = df_fed['balance_sheet_tn']
                f_min = float(val_f.dropna().min())
                f_max = float(val_f.dropna().max())
                fed_y_range = st.slider("总资产 Y 轴范围 (万亿 USD)", round(f_min - 0.5, 2), round(f_max + 0.5, 2), (round(f_min, 2), round(f_max, 2)), 0.05, key="fed_slider")

            fig_fed = create_fed_balance_sheet_chart(df_fed, y_range=fed_y_range, timeframe=macro_tf)
            if fig_fed:
                st.plotly_chart(fig_fed, use_container_width=True)
                with st.expander("💡 美联储资产负债表解读指南", expanded=False):
                    st.markdown("""
                    * **量化紧缩 (QT) 缩表**：美联储通过被动到期不续买入国债与 MBS，压缩资产负债表规模，回收长期基础货币。
                    * **准备金充裕度下限**：关注银行准备金是否接近 GDP 的 10%~11% 警戒区间，防止重演 2019 年 9 月回购流动性危机。
                    """)
        else:
            st.info("美联储资产负债表数据加载中或不可用。")

    # 第四排：金油比
    m_col7, _ = st.columns([1, 1])
    with m_col7:
        df_go = get_gold_oil_ratio_data()
        if not df_go.empty:
            latest_go_date = pd.to_datetime(df_go['date'].iloc[-1]).strftime('%Y-%m-%d')
            st.subheader("Gold / Oil Ratio (金油比)")
            st.caption(f"🕒 数据刷新时间 (美东时间): **{current_et_str}** | 纽约商业交易所期货")

            go_y_range = None
            if st.checkbox("手动自定义金油比 Y 轴范围", key="go_manual_y"):
                val_go = df_go['gold_oil_ratio']
                go_min = float(val_go.dropna().min())
                go_max = float(val_go.dropna().max())
                go_y_range = st.slider("金油比 Y 轴范围", round(max(0.0, go_min - 5.0), 1), round(go_max + 5.0, 1), (round(go_min, 1), round(go_max, 1)), 0.5, key="go_slider")

            fig_go = create_gold_oil_ratio_chart(df_go, y_range=go_y_range, timeframe=macro_tf)
            if fig_go:
                st.plotly_chart(fig_go, use_container_width=True)
                with st.expander("💡 Gold / Oil Ratio (金油比) 解读指南", expanded=False):
                    st.markdown("""
                    * **指标含义**：一盎司黄金可以购买的原油桶数（黄金代表终极信用避险与真实利率，原油代表全球工业与经济总需求）。
                    * **周期分水岭**：
                      * **金油比 $< 15$**：全球经济扩张过热，工业大宗商品需求旺盛。
                      * **金油比 $15 - 25$**：常态中性均衡区间。
                      * **金油比 $> 25$ (飙升阶段)**：避险情绪高涨或全球制造业总需求萎缩，常对应滞胀后期或严重衰退危机。
                    """)
        else:
            st.info("金油比数据加载中或不可用。")


# ==================================================================
# TAB 2: 个股量化与估值追踪 (Stock Tracker)
# ==================================================================
with tab_stock:
    st.header("🔍 个股深度量化与多因子估值追踪")
    st.caption(f"🕒 实时数据抓取 (美东时间): **{current_et_str}** | 整合量价趋势、PE Band 估值带、反向 DCF 增长率反推与财报全景")

    # 标的选择栏
    stock_col1, stock_col2, stock_col3, stock_col4 = st.columns([2, 2, 2, 2])
    with stock_col1:
        preset_choice = st.selectbox(
            "选择预设观察标的:",
            ["自定义输入 (Custom)", "NVDA (英伟达)", "AAPL (苹果)", "MSFT (微软)", "AMAT (应用材料)", "TSM (台积电)", "GOOGL (谷歌)", "AMZN (亚马逊)", "META (Meta)", "TSLA (特斯拉)", "AVGO (博通)", "ASML (阿斯麦)", "AMD (超威)", "COST (开市客)"],
            index=1
        )

    with stock_col2:
        if preset_choice.startswith("自定义"):
            ticker_input = st.text_input("输入美股代码 (Ticker):", value="NVDA").strip().upper()
            ticker_to_analyze = ticker_input if ticker_input else "NVDA"
        else:
            ticker_to_analyze = preset_choice.split()[0].strip().upper()

    with stock_col3:
        stock_timeframe = st.selectbox("选择价格回溯周期:", ["1M", "3M", "6M", "YTD", "1Y", "3Y", "5Y", "ALL"], index=4, key="stock_timeframe")

    with stock_col4:
        stock_chart_type = st.radio("价格图表类型:", ["K线图 (Candlestick)", "折线图 (Line)"], index=0, horizontal=True)

    st.markdown("---")

    with st.spinner(f"正在获取 {ticker_to_analyze} 实时行情、估值模型与财务数据..."):
        df_stock_hist = get_stock_historical_data(ticker_to_analyze, period="5y")
        stock_info = get_stock_fundamentals(ticker_to_analyze)
        fin_stmt_dict = get_stock_financial_statements(ticker_to_analyze)

    if stock_info:
        comp_name = stock_info.get("longName") or stock_info.get("shortName") or ticker_to_analyze
        cur_price = stock_info.get("currentPrice") or stock_info.get("regularMarketPrice") or stock_info.get("previousClose")
        mcap = stock_info.get("marketCap")
        mcap_str = f"${mcap/1e9:,.2f} B" if mcap else "N/A"
        pe_val = stock_info.get("trailingPE")
        fwd_pe = stock_info.get("forwardPE")
        ps_val = stock_info.get("priceToSalesTrailing12Months")
        gm_val = stock_info.get("grossMargins")
        opm_val = stock_info.get("operatingMargins")
        f52_l = stock_info.get("fiftyTwoWeekLow")
        f52_h = stock_info.get("fiftyTwoWeekHigh")
        sector = stock_info.get("sector", "N/A")
        industry = stock_info.get("industry", "N/A")

        st.subheader(f"🏢 {comp_name} ({ticker_to_analyze}) — {sector} | {industry}")

        # 核心指标看板
        kpi1, kpi2, kpi3, kpi4, kpi5, kpi6 = st.columns(6)
        kpi1.metric("当前实时股价", f"${cur_price:.2f}" if cur_price else "N/A")
        kpi2.metric("总市值 (Market Cap)", mcap_str)
        kpi3.metric("滚动市盈率 (TTM PE)", f"{pe_val:.1f}x" if pe_val else "N/A")
        kpi4.metric("远期市盈率 (Forward PE)", f"{fwd_pe:.1f}x" if fwd_pe else "N/A")
        kpi5.metric("市销率 (TTM PS)", f"{ps_val:.1f}x" if ps_val else "N/A")
        kpi6.metric("毛利率 (Gross Margin)", f"{gm_val*100:.1f}%" if gm_val else "N/A")

    # 3. 股票价格走势与均线系统
    st.markdown("---")
    st.subheader(f"📊 {ticker_to_analyze} 量价走势与均线系统 (20MA / 50MA / 200MA)")

    if df_stock_hist is not None and not df_stock_hist.empty:
        c_type_code = "Candlestick" if "K线" in stock_chart_type else "Line"
        fig_stock_price = create_stock_price_chart(df_stock_hist, symbol=ticker_to_analyze, chart_type=c_type_code, timeframe=stock_timeframe)
        if fig_stock_price:
            st.plotly_chart(fig_stock_price, use_container_width=True)
            with st.expander(f"💡 {ticker_to_analyze} 量价走势解读与关键均线位置", expanded=False):
                st.markdown("""
                * **20MA (短期生命线 - 绿色)**：短线多空分界与强弱动量支撑位。
                * **50MA (中期趋势线 - 橙色)**：机构主力建仓与波段行情分水岭。
                * **200MA (长期牛熊年线 - 红色)**：长期牛熊牛熊转换警戒线。站稳 200MA 确立长牛格局，跌破则提示深度调整风险。
                """)
    else:
        st.warning(f"未能获取 {ticker_to_analyze} 的历史价格图表数据。")

    # ==================================================================
    # 4. 扩展模块一：历史估值分位与 PE / PS Band (估值带走势)
    # ==================================================================
    st.markdown("---")
    st.subheader("📈 历史估值分位与 PE / PS Band (估值通道透视)")
    st.caption("叠加历史动态估值倍数通道，评估当前股价处于历史估值的折溢价状态与合理中枢")

    val_col1, val_col2 = st.columns([3, 1])
    with val_col2:
        val_type_choice = st.radio("选择估值带类型:", ["PE Band (市盈率)", "PS Band (市销率)"], index=0)
        val_type_code = "PE" if "PE" in val_type_choice else "PS"
        band_tf = st.selectbox("估值带时间跨度:", ["1Y", "3Y", "5Y", "ALL"], index=1, key="band_timeframe")

    with val_col1:
        cur_pe_val = stock_info.get("trailingPE") if stock_info else None
        cur_eps_val = stock_info.get("trailingEps") if stock_info else None

        if df_stock_hist is not None and not df_stock_hist.empty:
            fig_band = create_pe_ps_band_chart(
                df_stock_hist,
                symbol=ticker_to_analyze,
                current_eps=cur_eps_val,
                current_pe=cur_pe_val,
                valuation_type=val_type_code,
                timeframe=band_tf
            )
            if fig_band:
                st.plotly_chart(fig_band, use_container_width=True)
                with st.expander(f"💡 {val_type_code} Band 估值通道投资解读", expanded=False):
                    st.markdown(f"""
                    * **估值通道逻辑**：以公司当前盈利/营收能力为基准，绘制多个历史代表性估值倍数（如 0.6x、0.8x、1.0x、1.25x、1.5x 倍数通道）。
                    * **超买/超卖信号**：
                      * 股价触及或突破顶轨（高估值通道）：表明市场给予极高预期溢价，情绪可能过热。
                      * 股价回落至底轨（低估值通道）：通常对应基本面利空充分出清或悲观情绪超跌区间。
                    """)
        else:
            st.info("估值带图表数据加载中。")

    # ==================================================================
    # 5. 扩展模块二：反向 DCF 估值测算器 (Reverse DCF & Implied Growth)
    # ==================================================================
    st.markdown("---")
    st.subheader("🎯 反向 DCF 估值测算器 (Reverse DCF & Implied Growth)")
    st.caption("基于自由现金流折现模型，根据当前股价反推市场隐含的未来 5–10 年 FCF 复合年增长率 (Implied CAGR)")

    if stock_info:
        cur_p = stock_info.get("currentPrice") or stock_info.get("regularMarketPrice") or stock_info.get("previousClose") or 100.0
        shs = stock_info.get("sharesOutstanding")
        if not shs and mcap:
            shs = mcap / cur_p
        
        base_fcf_raw = stock_info.get("freeCashflow") or (mcap / (cur_pe_val if cur_pe_val else 25.0))
        base_fcf_bn = round(base_fcf_raw / 1e9, 2) if base_fcf_raw else 10.0
        
        tot_cash_bn = (stock_info.get("totalCash") or 0.0) / 1e9
        tot_debt_bn = (stock_info.get("totalDebt") or 0.0) / 1e9

        dcf_c1, dcf_c2, dcf_c3, dcf_c4 = st.columns(4)
        with dcf_c1:
            input_wacc = st.slider("加权资本成本 WACC 折现率 (%)", 6.0, 15.0, 9.0, 0.5) / 100.0
        with dcf_c2:
            input_g = st.slider("永续增长率 Terminal g (%)", 1.0, 4.0, 2.5, 0.25) / 100.0
        with dcf_c3:
            input_years = st.radio("显式预测期 (Years):", [5, 10], index=0)
        with dcf_c4:
            input_fcf = st.number_input("基准年自由现金流 ($B):", value=float(max(0.1, base_fcf_bn)), step=1.0) * 1e9

        dcf_result = calculate_reverse_dcf(
            current_price=cur_p,
            shares_out=shs,
            base_fcf=input_fcf,
            wacc=input_wacc,
            g=input_g,
            years=input_years,
            total_cash=tot_cash_bn * 1e9,
            total_debt=tot_debt_bn * 1e9
        )

        if dcf_result:
            implied_cagr = dcf_result["implied_cagr"]
            
            res_c1, res_c2, res_c3 = st.columns(3)
            if not np.isnan(implied_cagr):
                res_c1.metric(
                    "市场隐含未来 FCF 复合增速 (CAGR)",
                    f"{implied_cagr*100:+.2f}%",
                    delta=f"预测期: {input_years} 年 | WACC: {input_wacc*100:.1f}%"
                )
            else:
                res_c1.metric("市场隐含 FCF 复合增速 (CAGR)", "超出常规搜索收敛范围")

            res_c2.metric("当前企业价值 (EV)", f"${dcf_result['target_ev']/1e9:,.2f} B")
            res_c3.metric("净现金 / 净负债头寸", f"{(tot_cash_bn - tot_debt_bn):+,.2f} B")

            st.markdown("##### 📊 内在价值公允股价敏感性分析矩阵 (Sensitivity Matrix)")
            st.caption("纵轴为不同资本折现率 WACC，横轴为公司实际可能实现的未来 FCF 复合增速，单元格对应估算出的公允每股内在价值 ($)")
            sens_df = dcf_result.get("sensitivity_matrix")
            if sens_df is not None and not sens_df.empty:
                st.dataframe(sens_df, hide_index=True, use_container_width=True)
                with st.expander("💡 反向 DCF 估值测算逻辑与安全边际指引", expanded=False):
                    st.markdown(f"""
                    * **反向推导原理**：普通 DCF 往往受主观乐观假设影响过大；**反向 DCF** 则是探寻“**当前市价 (${cur_p:.2f}) 已经把未来多高的增长定价进去了 (Priced-in)**”。
                    * **安全边际判断**：
                      * 若市场隐含 CAGR (**{implied_cagr*100:+.1f}%**) 显著**低于**您对公司行业扩张与护城河的真实增长预期，则存在**安全边际 (Margin of Safety)**。
                      * 若市场隐含 CAGR 处于不可思议的超高位（如 $> 40\\%$ 且持续 5 年），则意味着估值容错率极低，任何业绩不及预期都将面临“杀估值”。
                    """)
        else:
            st.info("反向 DCF 测算需要基准自由现金流为正值且折现率大于永续增长率。")

    # ==================================================================
    # 6. 扩展模块三：技术面动量指标系统 (RSI, MACD & 200MA 年线偏离度)
    # ==================================================================
    st.markdown("---")
    st.subheader("⚡ 技术面动量指标系统 (RSI, MACD & 200MA 年线偏离度)")
    st.caption("综合跟踪 14 日强弱动量 RSI、MACD 趋势金叉/死叉与 200MA 均线乖离率 (Bias %)")

    if df_stock_hist is not None and not df_stock_hist.empty:
        latest_c = df_stock_hist['Close'].iloc[-1]
        ma200_val = df_stock_hist['Close'].rolling(200).mean().iloc[-1] if len(df_stock_hist) >= 200 else None
        bias_200 = ((latest_c - ma200_val) / ma200_val * 100) if ma200_val else None

        d_close = df_stock_hist['Close'].diff()
        g_s = (d_close.where(d_close > 0, 0.0)).fillna(0.0)
        l_s = (-d_close.where(d_close < 0, 0.0)).fillna(0.0)
        ag = g_s.ewm(alpha=1.0/14.0, min_periods=14, adjust=False).mean()
        al = l_s.ewm(alpha=1.0/14.0, min_periods=14, adjust=False).mean()
        rs_val = ag / al.replace(0, np.nan)
        rsi_series = (100.0 - (100.0 / (1.0 + rs_val))).fillna(50.0)
        latest_rsi = rsi_series.iloc[-1]

        e12 = df_stock_hist['Close'].ewm(span=12, adjust=False).mean()
        e26 = df_stock_hist['Close'].ewm(span=26, adjust=False).mean()
        macd_s = e12 - e26
        macd_sig_s = macd_s.ewm(span=9, adjust=False).mean()
        macd_h_s = macd_s - macd_sig_s
        latest_macd_h = macd_h_s.iloc[-1]

        tech_kpi1, tech_kpi2, tech_kpi3 = st.columns(3)
        
        rsi_state = "超买区间 (>70)" if latest_rsi > 70 else ("超卖区间 (<30)" if latest_rsi < 30 else "常态中性")
        tech_kpi1.metric("RSI (14) 强弱指标", f"{latest_rsi:.1f}", delta=f"状态: {rsi_state}")

        macd_state = "多头动能柱 (金叉/上行)" if latest_macd_h >= 0 else "空头调整柱 (死叉/下行)"
        tech_kpi2.metric("MACD (12, 26, 9) 柱线", f"{latest_macd_h:+.2f}", delta=f"动能: {macd_state}")

        if bias_200 is not None:
            bias_state = "年线上方强势" if bias_200 >= 0 else "年线下方承压"
            tech_kpi3.metric("200MA 年线偏离度 (Bias)", f"{bias_200:+.2f}%", delta=f"200MA: ${ma200_val:.2f} ({bias_state})")
        else:
            tech_kpi3.metric("200MA 年线偏离度", "历史数据不足 200 日")

        fig_tech = create_technical_momentum_chart(df_stock_hist, symbol=ticker_to_analyze, timeframe=stock_timeframe)
        if fig_tech:
            st.plotly_chart(fig_tech, use_container_width=True)
            with st.expander("💡 技术面动量指标系统解读指南", expanded=False):
                st.markdown("""
                * **RSI (14)**：
                  * **RSI $> 70$**：进入超买过热区，提示短线回调或高位震荡风险。
                  * **RSI $< 30$**：进入超卖恐慌区，常伴随左侧博弈性超跌反弹买点。
                * **MACD (12, 26, 9)**：
                  * **DIF 上穿 DEA (零轴上方金叉)**：主升浪确认，多头动能强劲。
                  * **DIF 下穿 DEA (零轴下方死叉)**：空头主导，调整周期尚未结束。
                * **200MA 年线偏离度 (200DMA Bias %)**：
                  * 长期牛熊分界线。偏离年线超过 **+30% ~ +40%** 通常意味着股价与长期均线严重脱节，存在均值回归引力。
                """)
    else:
        st.info("技术动量指标数据加载中。")

    # ==================================================================
    # 7. 核心财务报表透视 (季度与年度财报主要数据)
    # ==================================================================
    st.markdown("---")
    st.subheader("📑 核心财务报表深度透视 (季度与年度财报主要数据)")
    st.caption("覆盖营业总收入、营收同比增速、毛利润/毛利率、营业利润 (EBIT)、净利润、稀释 EPS、经营现金流、自由现金流 (FCF) 与资产负债核心结构")

    if fin_stmt_dict:
        fin_tab_q, fin_tab_a = st.tabs(["📊 季度财务报表明细 (Quarterly Financials)", "📅 年度财务报表明细 (Annual Financials)"])

        with fin_tab_q:
            df_q_sum = fin_stmt_dict.get("q_summary")
            df_q_trend = fin_stmt_dict.get("q_trends")

            if df_q_sum is not None and not df_q_sum.empty:
                st.markdown("##### 季度核心财务指标精选总览 (最近 5 个季度)")
                st.dataframe(df_q_sum, hide_index=True, use_container_width=True)

                if df_q_trend is not None and not df_q_trend.empty:
                    fig_q_trend = create_financial_trends_chart(df_q_trend, period_type="季度")
                    if fig_q_trend:
                        st.plotly_chart(fig_q_trend, use_container_width=True)
            else:
                st.info("暂无季度结构化财务报表数据。")

        with fin_tab_a:
            df_a_sum = fin_stmt_dict.get("a_summary")
            df_a_trend = fin_stmt_dict.get("a_trends")

            if df_a_sum is not None and not df_a_sum.empty:
                st.markdown("##### 年度核心财务指标精选总览 (最近 4 个财年)")
                st.dataframe(df_a_sum, hide_index=True, use_container_width=True)

                if df_a_trend is not None and not df_a_trend.empty:
                    fig_a_trend = create_financial_trends_chart(df_a_trend, period_type="年度")
                    if fig_a_trend:
                        st.plotly_chart(fig_a_trend, use_container_width=True)
            else:
                st.info("暂无年度结构化财务报表数据。")
    else:
        st.info(f"未能提取 {ticker_to_analyze} 的财务报表数据。")

    # 8. 详细财务结构与分析师目标价扩展表
    if stock_info:
        with st.expander("📋 查看分析师评级、目标价与资本结构补充数据", expanded=False):
            f_col1, f_col2 = st.columns(2)
            with f_col1:
                st.markdown("**【分析师目标价与评级】**")
                target_mean = stock_info.get("targetMeanPrice")
                target_high = stock_info.get("targetHighPrice")
                target_low = stock_info.get("targetLowPrice")
                rec_key = stock_info.get("recommendationKey", "N/A")
                st.write(f"- **一致推荐评级**: `{str(rec_key).upper()}`")
                st.write(f"- **分析师平均目标价**: `${target_mean:.2f}`" if target_mean else "- **平均目标价**: `N/A`")
                st.write(f"- **最高/最低目标价区间**: `${target_low:.2f} ~ ${target_high:.2f}`" if target_low and target_high else "- **目标价区间**: `N/A`")
                st.write(f"- **52 周最高/最低价**: `${f52_l:.2f} ~ ${f52_h:.2f}`" if f52_l and f52_h else "- **52 周区间**: `N/A`")

            with f_col2:
                st.markdown("**【资本与现金流头寸】**")
                total_cash = stock_info.get("totalCash")
                total_debt = stock_info.get("totalDebt")
                fcf_val = stock_info.get("freeCashflow")
                ebitda = stock_info.get("ebitda")
                st.write(f"- **现金储备及等价物**: `${total_cash/1e9:,.2f} B`" if total_cash else "- **现金储备**: `N/A`")
                st.write(f"- **总计有息负债**: `${total_debt/1e9:,.2f} B`" if total_debt else "- **总计有息负债**: `N/A`")
                st.write(f"- **最近十二个月自由现金流 (FCF)**: `${fcf_val/1e9:,.2f} B`" if fcf_val else "- **自由现金流**: `N/A`")
                st.write(f"- **EBITDA 息税折旧前利润**: `${ebitda/1e9:,.2f} B`" if ebitda else "- **EBITDA**: `N/A`")


# ==================================================================
# TAB 3: 芯片半导体产业链 (Semiconductor Tracker)
# ==================================================================
with tab_semi:
    st.header("⚡ 芯片半导体产业链深度追踪")
    st.caption(f"🕒 实时数据抓取 (美东时间): **{current_et_str}** | 覆盖算力 GPU/CPU、晶圆制造、光刻设备、存储 HBM 与 EDA 全产业链")

    # 1. 行业龙头相对收益率走势图 (Normalised Relative Performance)
    st.subheader("📈 半导体龙头多股累计收益率对比 (Relative Performance)")
    st.caption("基准日股价归一化为 0%，对比不同龙头在选定区间内的真实 Alpha 超额收益")

    semi_col1, semi_col2 = st.columns([3, 1])
    with semi_col2:
        semi_tf = st.selectbox("选择对比时间周期:", ["1M", "3M", "6M", "YTD", "1Y", "3Y", "5Y"], index=3, key="semi_timeframe")
        all_semi_symbols = [item["symbol"] for item in SEMI_BASKET]
        default_selected_semi = ["NVDA", "TSM", "ASML", "AVGO", "AMD", "MU", "AMAT", "SOXX"]
        selected_semi_syms = st.multiselect("选择要对比的标的:", all_semi_symbols, default=default_selected_semi)

    with semi_col1:
        if selected_semi_syms:
            with st.spinner("正在获取所选半导体标的历史收盘价数据..."):
                df_semi_prices = get_semiconductor_comparative_prices(selected_semi_syms)

            if df_semi_prices is not None and not df_semi_prices.empty:
                fig_semi_rel = create_relative_performance_chart(df_semi_prices, tickers=selected_semi_syms, timeframe=semi_tf)
                if fig_semi_rel:
                    st.plotly_chart(fig_semi_rel, use_container_width=True)
                    with st.expander("💡 相对收益率走势分析与周期轮动指南", expanded=False):
                        st.markdown("""
                        * **算力先导 (NVDA / AVGO)**：通常在 AI 资本开支上行周期前半场率先拉升。
                        * **制造与先进封装 (TSM / ASML)**：先进制程稼动率与扩产进度决定算力供应上限。
                        * **存储高贝塔弹性 (MU)**：大宗存储价格反转通常在周期中段爆发极高股价弹性。
                        * **后周期通用设备 (AMAT / LRCX / KLAC)**：在晶圆厂 Capex 落地与装机阶段获得持续现金流支撑。
                        """)
            else:
                st.warning("未能获取半导体标的对比图表数据。")
        else:
            st.info("请在右侧选择至少一只半导体标的进行走势对比。")

    # 2. 产业链核心龙头横向比选矩阵表格
    st.markdown("---")
    st.subheader("📊 半导体全产业链核心标的估值与财务比选矩阵")
    st.caption("包含实时股价、市值体量、PE/PS 估值分位、毛利率水平与近 1 年涨跌幅，方便横向比选高性价比环节")

    with st.spinner("正在拉取半导体产业链标的实时估值矩阵..."):
        df_semi_matrix = get_semiconductor_matrix_data()

    if df_semi_matrix is not None and not df_semi_matrix.empty:
        st.dataframe(
            df_semi_matrix,
            hide_index=True,
            use_container_width=True
        )
    else:
        st.info("半导体产业链矩阵数据加载中。")

    # 3. 产业链四大核心逻辑解读指南
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
