import os
import sys
import datetime
import json
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
    create_vix_chart,
    create_cnn_fear_greed_chart,
    create_stock_price_chart,
    create_relative_performance_chart,
    create_financial_trends_chart,
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
            json_data = resp.json()
            fng = json_data.get("fear_and_greed", {})
            hist_obj = json_data.get("fear_and_greed_historical", {})
            hist_data = hist_obj.get("data", []) if isinstance(hist_obj, dict) else []
            
            latest_score = fng.get("score")
            latest_rating = fng.get("rating")
            
            df_hist = pd.DataFrame()
            if hist_data:
                df_hist = pd.DataFrame(hist_data)
                if "x" in df_hist.columns and "y" in df_hist.columns:
                    df_hist["date"] = pd.to_datetime(df_hist["x"], unit="ms", errors="coerce")
                    df_hist["Score"] = pd.to_numeric(df_hist["y"], errors="coerce")
                    df_hist = df_hist.dropna(subset=["date", "Score"]).sort_values("date").reset_index(drop=True)
            
            return {
                "latest_score": latest_score,
                "latest_rating": latest_rating,
                "previous_close": fng.get("previous_close"),
                "previous_1_week": fng.get("previous_1_week"),
                "previous_1_month": fng.get("previous_1_month"),
                "previous_1_year": fng.get("previous_1_year"),
                "df_hist": df_hist
            }
    except Exception as e:
        print(f"Error fetching CNN Fear and Greed Index: {e}")

    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            fng = data.get("fear_and_greed", {})
            hist_data = data.get("fear_and_greed_historical", {}).get("data", [])
            df_hist = pd.DataFrame()
            if hist_data:
                df_hist = pd.DataFrame(hist_data)
                df_hist["date"] = pd.to_datetime(df_hist["x"], unit="ms", errors="coerce")
                df_hist["Score"] = pd.to_numeric(df_hist["y"], errors="coerce")
                df_hist = df_hist.dropna(subset=["date", "Score"]).sort_values("date").reset_index(drop=True)
            return {
                "latest_score": fng.get("score"),
                "latest_rating": fng.get("rating"),
                "previous_close": fng.get("previous_close"),
                "previous_1_week": fng.get("previous_1_week"),
                "previous_1_month": fng.get("previous_1_month"),
                "previous_1_year": fng.get("previous_1_year"),
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
    """美联储净流动性 (WALCL - TGA - ON RRP) 与 银行准备金 (WRESBAL/WRBWFRBL)"""
    df_walcl = _fetch_fred_series_observations("WALCL", "walcl", "2015-01-01")
    df_tga = _fetch_fred_series_observations("WTREGEN", "tga", "2015-01-01")
    df_rrp = _fetch_fred_series_observations("RRPONTSYD", "rrp", "2015-01-01")
    
    df_res = _fetch_fred_series_observations("WRESBAL", "reserves", "2015-01-01")
    if df_res.empty:
        df_res = _fetch_fred_series_observations("WRBWFRBL", "reserves", "2015-01-01")
    if df_res.empty:
        df_res = _fetch_fred_series_observations("TOTRESNS", "reserves", "2015-01-01")

    if df_walcl.empty:
        return pd.DataFrame()

    dfs = [df_walcl]
    if not df_tga.empty:
        dfs.append(df_tga)
    if not df_rrp.empty:
        dfs.append(df_rrp)
    if not df_res.empty:
        dfs.append(df_res)

    merged = dfs[0]
    for d in dfs[1:]:
        merged = pd.merge(merged, d, on="date", how="outer")

    merged["date"] = pd.to_datetime(merged["date"])
    merged = merged.sort_values("date").reset_index(drop=True)

    for col in ["walcl", "tga", "rrp", "reserves"]:
        if col not in merged.columns:
            merged[col] = 0.0

    merged[["walcl", "tga", "rrp", "reserves"]] = merged[["walcl", "tga", "rrp", "reserves"]].ffill().bfill().fillna(0.0)
    merged = merged[merged["walcl"] > 0].copy()

    walcl_tn = merged["walcl"] / 1_000_000.0
    tga_tn = merged["tga"] / 1_000_000.0

    rrp_mean = merged["rrp"].mean()
    if rrp_mean > 1000:
        rrp_tn = merged["rrp"] / 1_000_000.0
    else:
        rrp_tn = merged["rrp"] / 1_000.0

    res_mean = merged["reserves"].mean()
    if res_mean > 100_000:
        res_tn = merged["reserves"] / 1_000_000.0
    elif res_mean > 10:
        res_tn = merged["reserves"] / 1_000.0
    else:
        res_tn = merged["reserves"]

    merged["Fed_Net_Liquidity_Tn"] = walcl_tn - tga_tn - rrp_tn
    merged["Bank_Reserves_Tn"] = res_tn

    return merged[["date", "Fed_Net_Liquidity_Tn", "Bank_Reserves_Tn"]].dropna().reset_index(drop=True)

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
# 3. 个股追踪与基本面/估值/财报数据抓取函数
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
    通过 yfinance 获取个股的季度与年度三大财务报表核心数据 (利润表、资产负债表、现金流量表)
    返回结构化的 quarterly_df 与 annual_df
    """
    clean_sym = symbol.strip().upper()
    try:
        import yfinance as yf
        ticker = yf.Ticker(clean_sym)
        
        # 1. 利润表 (Income Statement)
        q_inc = getattr(ticker, 'quarterly_income_stmt', None)
        if q_inc is None or q_inc.empty:
            q_inc = getattr(ticker, 'quarterly_financials', None)
            
        a_inc = getattr(ticker, 'income_stmt', None)
        if a_inc is None or a_inc.empty:
            a_inc = getattr(ticker, 'financials', None)

        # 2. 资产负债表 (Balance Sheet)
        q_bs = getattr(ticker, 'quarterly_balance_sheet', None)
        a_bs = getattr(ticker, 'balance_sheet', None)

        # 3. 现金流量表 (Cash Flow Statement)
        q_cf = getattr(ticker, 'quarterly_cashflow', None)
        if q_cf is None or q_cf.empty:
            q_cf = getattr(ticker, 'quarterly_cash_flow', None)
            
        a_cf = getattr(ticker, 'cashflow', None)
        if a_cf is None or a_cf.empty:
            a_cf = getattr(ticker, 'cash_flow', None)

        def _process_statements(inc_df, bs_df, cf_df, is_quarterly=True):
            if inc_df is None or inc_df.empty:
                return pd.DataFrame(), pd.DataFrame()
            
            # 获取日期列并排序（从旧到新计算增长率，展示时从新到旧）
            cols = [c for c in inc_df.columns]
            cols_sorted = sorted(cols)
            
            dates_str = [pd.to_datetime(c).strftime('%Y-%m' if is_quarterly else '%Y') for c in cols_sorted]
            
            def _get_val(df, candidates, date_col):
                if df is None or df.empty or date_col not in df.columns:
                    return np.nan
                for cand in candidates:
                    for idx in df.index:
                        if str(idx).strip().lower() == cand.strip().lower():
                            val = df.loc[idx, date_col]
                            if isinstance(val, pd.Series):
                                val = val.iloc[0]
                            try:
                                return float(val)
                            except (ValueError, TypeError):
                                pass
                return np.nan

            rev_list = []
            gp_list = []
            op_inc_list = []
            net_inc_list = []
            eps_list = []
            fcf_list = []
            cfo_list = []
            capex_list = []
            cash_list = []
            debt_list = []
            equity_list = []
            assets_list = []

            for col in cols_sorted:
                # Revenue
                rev = _get_val(inc_df, ['Total Revenue', 'Operating Revenue', 'Revenue'], col)
                rev_list.append(rev)
                
                # Gross Profit
                gp = _get_val(inc_df, ['Gross Profit', 'Gross Margin'], col)
                gp_list.append(gp)
                
                # Operating Income
                op = _get_val(inc_df, ['Operating Income', 'Operating Profit', 'EBIT', 'Operating Revenue'], col)
                op_inc_list.append(op)
                
                # Net Income
                ni = _get_val(inc_df, ['Net Income Common Stockholders', 'Net Income', 'Net Income From Continuing Operation Net Minority Interest'], col)
                net_inc_list.append(ni)
                
                # EPS
                eps = _get_val(inc_df, ['Diluted EPS', 'Basic EPS', 'Diluted Average Shares'], col)
                eps_list.append(eps)
                
                # Cash Flow
                cfo = _get_val(cf_df, ['Operating Cash Flow', 'Cash Flowsfromusedin Operating Activities', 'Cash Flow From Continuing Operating Activities'], col)
                cfo_list.append(cfo)
                
                capex = _get_val(cf_df, ['Capital Expenditure', 'Capital Expenditures', 'Purchase Of Property Plant And Equipment'], col)
                capex_list.append(capex)
                
                fcf = _get_val(cf_df, ['Free Cash Flow'], col)
                if np.isnan(fcf) and not np.isnan(cfo):
                    fcf = cfo - (abs(capex) if not np.isnan(capex) else 0.0)
                fcf_list.append(fcf)
                
                # Balance Sheet
                cash = _get_val(bs_df, ['Cash Cash Equivalents And Short Term Investments', 'Cash And Cash Equivalents', 'Cash Financial'], col)
                cash_list.append(cash)
                
                debt = _get_val(bs_df, ['Total Debt', 'Total Non Current Liabilities Net Minority Interest', 'Long Term Debt'], col)
                debt_list.append(debt)
                
                eq = _get_val(bs_df, ['Stockholders Equity', 'Common Stock Equity', 'Total Equity Gross Minority Interest'], col)
                equity_list.append(eq)
                
                ast_val = _get_val(bs_df, ['Total Assets'], col)
                assets_list.append(ast_val)

            # 构建结构化表格
            summary_records = []
            
            # 1. 营收 ($B)
            row_rev = {"指标 (Metric)": "营业总收入 (Total Revenue)"}
            for d, r in zip(dates_str, rev_list):
                row_rev[d] = f"${r/1e9:,.2f} B" if not np.isnan(r) else "N/A"
            summary_records.append(row_rev)

            # 2. 营收同比增速 (%)
            row_rev_growth = {"指标 (Metric)": "营收同比增速 (YoY Growth)"}
            for i, d in enumerate(dates_str):
                lag = 4 if is_quarterly else 1
                if i >= lag and not np.isnan(rev_list[i]) and not np.isnan(rev_list[i - lag]) and rev_list[i - lag] != 0:
                    g = (rev_list[i] - rev_list[i - lag]) / abs(rev_list[i - lag]) * 100.0
                    row_rev_growth[d] = f"{g:+.1f}%"
                else:
                    row_rev_growth[d] = "N/A"
            summary_records.append(row_rev_growth)

            # 3. 毛利润 & 毛利率
            row_gp = {"指标 (Metric)": "毛利润 (Gross Profit)"}
            row_gm = {"指标 (Metric)": "毛利率 (Gross Margin %)"}
            for d, gp, r in zip(dates_str, gp_list, rev_list):
                row_gp[d] = f"${gp/1e9:,.2f} B" if not np.isnan(gp) else "N/A"
                row_gm[d] = f"{(gp/r*100):.1f}%" if (not np.isnan(gp) and not np.isnan(r) and r > 0) else "N/A"
            summary_records.append(row_gp)
            summary_records.append(row_gm)

            # 4. 营业利润 & 营业利润率
            row_op = {"指标 (Metric)": "营业利润 (Operating Income / EBIT)"}
            row_opm = {"指标 (Metric)": "营业利润率 (Operating Margin %)"}
            for d, op, r in zip(dates_str, op_inc_list, rev_list):
                row_op[d] = f"${op/1e9:,.2f} B" if not np.isnan(op) else "N/A"
                row_opm[d] = f"{(op/r*100):.1f}%" if (not np.isnan(op) and not np.isnan(r) and r > 0) else "N/A"
            summary_records.append(row_op)
            summary_records.append(row_opm)

            # 5. 净利润 & 净利率
            row_ni = {"指标 (Metric)": "净利润 (Net Income)"}
            row_npm = {"指标 (Metric)": "净利润率 (Net Margin %)"}
            for d, ni, r in zip(dates_str, net_inc_list, rev_list):
                row_ni[d] = f"${ni/1e9:,.2f} B" if not np.isnan(ni) else "N/A"
                row_npm[d] = f"{(ni/r*100):.1f}%" if (not np.isnan(ni) and not np.isnan(r) and r > 0) else "N/A"
            summary_records.append(row_ni)
            summary_records.append(row_npm)

            # 6. 稀释 EPS
            row_eps = {"指标 (Metric)": "稀释每股收益 (Diluted EPS)"}
            for d, eps in zip(dates_str, eps_list):
                row_eps[d] = f"${eps:.2f}" if not np.isnan(eps) else "N/A"
            summary_records.append(row_eps)

            # 7. 经营现金流 & 自由现金流
            row_cfo = {"指标 (Metric)": "经营活动现金流 (Operating Cash Flow)"}
            row_fcf = {"指标 (Metric)": "自由现金流 (Free Cash Flow)"}
            row_fcfm = {"指标 (Metric)": "自由现金流转化率 (FCF Margin %)"}
            for d, cfo, fcf, r in zip(dates_str, cfo_list, fcf_list, rev_list):
                row_cfo[d] = f"${cfo/1e9:,.2f} B" if not np.isnan(cfo) else "N/A"
                row_fcf[d] = f"${fcf/1e9:,.2f} B" if not np.isnan(fcf) else "N/A"
                row_fcfm[d] = f"{(fcf/r*100):.1f}%" if (not np.isnan(fcf) and not np.isnan(r) and r > 0) else "N/A"
            summary_records.append(row_cfo)
            summary_records.append(row_fcf)
            summary_records.append(row_fcfm)

            # 8. 资产负债结构
            row_cash = {"指标 (Metric)": "现金及短期投资 (Cash & Short Term Inv.)"}
            row_debt = {"指标 (Metric)": "总负债 (Total Debt)"}
            row_eq = {"指标 (Metric)": "股东权益 / 净资产 (Stockholders' Equity)"}
            for d, c, dt, eq in zip(dates_str, cash_list, debt_list, equity_list):
                row_cash[d] = f"${c/1e9:,.2f} B" if not np.isnan(c) else "N/A"
                row_debt[d] = f"${dt/1e9:,.2f} B" if not np.isnan(dt) else "N/A"
                row_eq[d] = f"${eq/1e9:,.2f} B" if not np.isnan(eq) else "N/A"
            summary_records.append(row_cash)
            summary_records.append(row_debt)
            summary_records.append(row_eq)

            df_summary = pd.DataFrame(summary_records)
            
            # 列排序：将最新日期排在前面（指标列在第0列，其余列倒序）
            date_cols_reversed = list(reversed(dates_str))
            df_summary = df_summary[["指标 (Metric)"] + date_cols_reversed]

            # 提取趋势图表用的原始数值 DataFrame
            df_trends = pd.DataFrame({
                "Period": dates_str,
                "Revenue_Bn": [r/1e9 if not np.isnan(r) else 0.0 for r in rev_list],
                "NetIncome_Bn": [ni/1e9 if not np.isnan(ni) else 0.0 for ni in net_inc_list],
                "FCF_Bn": [f/1e9 if not np.isnan(f) else 0.0 for f in fcf_list],
                "GrossMargin_Pct": [(gp/r*100) if (not np.isnan(gp) and not np.isnan(r) and r > 0) else np.nan for gp, r in zip(gp_list, rev_list)],
                "OperatingMargin_Pct": [(op/r*100) if (not np.isnan(op) and not np.isnan(r) and r > 0) else np.nan for op, r in zip(op_inc_list, rev_list)],
                "NetMargin_Pct": [(ni/r*100) if (not np.isnan(ni) and not np.isnan(r) and r > 0) else np.nan for ni, r in zip(net_inc_list, rev_list)],
            })

            return df_summary, df_trends

        q_summary, q_trends = _process_statements(q_inc, q_bs, q_cf, is_quarterly=True)
        a_summary, a_trends = _process_statements(a_inc, a_bs, a_cf, is_quarterly=False)

        return {
            "quarterly_summary": q_summary,
            "quarterly_trends": q_trends,
            "annual_summary": a_summary,
            "annual_trends": a_trends
        }
    except Exception as e:
        print(f"Error processing financial statements for {clean_sym}: {e}")

    return {}


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
tab_macro, tab_stock, tab_semi = st.tabs([
    "🌐 宏观与市场总览 (Macro & Breadth)",
    "🔍 个股量化与估值追踪 (Stock Tracker)",
    "⚡ 芯片半导体产业链 (Semiconductor Tracker)"
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

            credit_y_range = None
            if st.checkbox("手动自定义信用利差 Y 轴范围", key="credit_manual_y"):
                val_hy = df_highyield['Value'] if 'Value' in df_highyield.columns else df_highyield.iloc[:, 1]
                hy_min = float(val_hy.dropna().min())
                hy_max = float(val_hy.dropna().max())
                credit_y_range = st.slider("信用利差 Y 轴范围 (%)", round(max(0.0, hy_min - 1.0), 1), round(hy_max + 2.0, 1), (round(hy_min, 1), round(hy_max, 1)), 0.1, key="credit_y_slider")

            fig_credit = create_credit_spread_chart(df_highyield, y_range=credit_y_range, timeframe=macro_tf)
            if fig_credit:
                st.plotly_chart(fig_credit, use_container_width=True)
                with st.expander("💡 高收益债信用利差 (US High Yield Spread) 解读指南", expanded=False):
                    st.markdown("""
                    * **指标含义**：美债高收益垃圾债（High Yield）收益率相对于同期限国债收益率的期权调整利差 (OAS)。
                    * **预警红线 (500 bps / 5.0%)**：
                      * **利差 $< 3.5\\%$**：市场风险偏好处于极度乐观状态。
                      * **利差走阔并 $> 500$ bps**：违约风险升温，信用风险向实体经济扩散。
                    """)
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
                with st.expander("💡 美国失业率 (UNRATE) 解读指南", expanded=False):
                    st.markdown("""
                    * **核心指标**：美联储双重目标（充分就业与物价稳定）的核心评估依据，历史均值约 5.6%。
                    * **萨姆规则 (Sahm Rule)**：当失业率 3 个月移动平均值较过去 12 个月低点升高 0.5 个百分点时，预示经济进入衰退期，倒逼央行降息。
                    """)
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
                with st.expander("💡 美联储总资产 (WALCL) 解读指南", expanded=False):
                    st.markdown("""
                    * **指标含义**：美联储资产负债表总规模（万亿美元）。QE 扩表注入流动性，QT 缩表回收流动性。
                    * **量化紧缩 (QT) 减速**：关注美联储慢速缩表（QT Taper）及停止缩表节点，总资产规模是央行资产负债表政策的直接反映。
                    """)
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
            with st.expander("💡 Gold / Oil Ratio (金油比) 解读指南", expanded=False):
                st.markdown("""
                * **指标含义**：1 盎司黄金可购买的原油桶数（黄金现价 / WTI 或布伦特原油现价）。
                * **避险与衰退预警**：金油比 $> 25\text{–}30$ 通常反映强避险需求（金价强）或大宗商品需求疲软（油价弱），是地缘政治风险或全球衰退危机的指示器。
                """)

    # --- 6. 深度策略指南卡片 ---
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


# ==================================================================
# TAB 2: 个股量化与估值追踪 (Individual Stock Tracker)
# ==================================================================
with tab_stock:
    st.header("🔍 个股深度量化与多因子估值追踪")
    st.caption(f"🕒 实时数据抓取 (美东时间): **{current_et_str}** | 支持任意美股 Ticker 分析与基本面体检")

    # 标的选择栏
    stock_col1, stock_col2, stock_col3, stock_col4 = st.columns([2, 2, 2, 2])

    popular_tickers = [
        "NVDA", "AAPL", "MSFT", "AMZN", "GOOGL", "META", "TSLA",
        "AVGO", "TSM", "AMD", "ASML", "BRK-B", "LLY", "JPM", "V", "PLTR"
    ]

    with stock_col1:
        selected_quick_ticker = st.selectbox("📌 快捷选择热门权重股:", popular_tickers, index=0)

    with stock_col2:
        custom_ticker_input = st.text_input("✍️ 或输入自定义美股 Ticker:", value="").strip().upper()

    ticker_to_analyze = custom_ticker_input if custom_ticker_input else selected_quick_ticker

    with stock_col3:
        chart_style = st.selectbox("📊 图表类型:", ["Candlestick (K线图)", "Line (收盘价折线)"], index=0)
        chart_type_val = "Candlestick" if "Candlestick" in chart_style else "Line"

    with stock_col4:
        stock_timeframe = st.selectbox("⏱️ 走势图时间窗口:", ["1M", "3M", "6M", "YTD", "1Y", "3Y", "5Y", "ALL"], index=4)

    st.markdown("---")

    with st.spinner(f"正在获取 {ticker_to_analyze} 实时行情与基本面财务数据..."):
        df_stock_hist = get_stock_historical_data(ticker_to_analyze, period="5y")
        stock_info = get_stock_fundamentals(ticker_to_analyze)
        fin_stmt_dict = get_stock_financial_statements(ticker_to_analyze)

    if stock_info:
        comp_name = stock_info.get("shortName") or stock_info.get("longName") or ticker_to_analyze
        sector = stock_info.get("sector", "N/A")
        industry = stock_info.get("industry", "N/A")
        cur_price = stock_info.get("currentPrice") or stock_info.get("regularMarketPrice") or stock_info.get("previousClose")
        prev_close = stock_info.get("regularMarketPreviousClose") or stock_info.get("previousClose")
        
        price_diff = (cur_price - prev_close) if (cur_price and prev_close) else 0.0
        price_diff_pct = (price_diff / prev_close * 100) if prev_close else 0.0

        st.subheader(f"🏢 {comp_name} ({ticker_to_analyze}) — {sector} | {industry}")
        
        # 1. 核心价格与估值 KPI 卡片
        kpi_r1_1, kpi_r1_2, kpi_r1_3, kpi_r1_4 = st.columns(4)
        
        if cur_price is not None:
            kpi_r1_1.metric(
                "最新市价 (USD)",
                f"${cur_price:,.2f}",
                delta=f"{price_diff:+,.2f} ({price_diff_pct:+.2f}%)"
            )
        
        mcap = stock_info.get("marketCap")
        if mcap:
            kpi_r1_2.metric("总市值 (Market Cap)", f"${mcap/1e9:,.2f} B")
        else:
            kpi_r1_2.metric("总市值 (Market Cap)", "N/A")

        pe_ttm = stock_info.get("trailingPE")
        pe_fwd = stock_info.get("forwardPE")
        kpi_r1_3.metric(
            "市盈率 PE (TTM)",
            f"{pe_ttm:.2f}x" if pe_ttm else "N/A",
            delta=f"Forward PE: {pe_fwd:.2f}x" if pe_fwd else None
        )

        ps_ttm = stock_info.get("priceToSalesTrailing12Months")
        kpi_r1_4.metric("市销率 PS (TTM)", f"{ps_ttm:.2f}x" if ps_ttm else "N/A")

        # 2. 第二排基本面与风险指标
        kpi_r2_1, kpi_r2_2, kpi_r2_3, kpi_r2_4 = st.columns(4)
        
        gm = stock_info.get("grossMargins")
        kpi_r2_1.metric("毛利率 (Gross Margin)", f"{gm*100:.1f}%" if gm is not None else "N/A")

        opm = stock_info.get("operatingMargins")
        kpi_r2_2.metric("营业利润率 (Operating Margin)", f"{opm*100:.1f}%" if opm is not None else "N/A")

        roe = stock_info.get("returnOnEquity")
        kpi_r2_3.metric("净资产收益率 (ROE)", f"{roe*100:.1f}%" if roe is not None else "N/A")

        beta = stock_info.get("beta")
        kpi_r2_4.metric("Beta 系数 (波动率)", f"{beta:.2f}" if beta is not None else "N/A")

    # 3. 交互式 K 线与均线副图
    if df_stock_hist is not None and not df_stock_hist.empty:
        fig_stock = create_stock_price_chart(
            df_stock_hist,
            symbol=ticker_to_analyze,
            chart_type=chart_type_val,
            timeframe=stock_timeframe
        )
        if fig_stock:
            st.plotly_chart(fig_stock, use_container_width=True)
    else:
        st.warning(f"未能获取 {ticker_to_analyze} 的历史价格图表数据。")

    # 4. 核心财务报表透视 (季度与年度财报主要数据)
    st.markdown("---")
    st.subheader("📑 核心财务报表深度透视 (季度与年度财报主要数据)")
    st.caption("覆盖营业总收入、营收同比增速、毛利润/毛利率、营业利润 (EBIT)、净利润、稀释 EPS、经营现金流、自由现金流 (FCF) 与资产负债核心结构")

    if fin_stmt_dict:
        fin_tab_q, fin_tab_a = st.tabs([
            "📅 季度财报主要数据 (Quarterly Financials)",
            "📆 年度财报主要数据 (Annual Financials)"
        ])

        with fin_tab_q:
            q_trends = fin_stmt_dict.get("quarterly_trends")
            q_summary = fin_stmt_dict.get("quarterly_summary")

            if q_trends is not None and not q_trends.empty:
                fig_q_trends = create_financial_trends_chart(q_trends, period_type="季度")
                if fig_q_trends:
                    st.plotly_chart(fig_q_trends, use_container_width=True)

            if q_summary is not None and not q_summary.empty:
                st.markdown("##### 📋 最近 4–8 个季度财务指标结构表")
                st.dataframe(q_summary, hide_index=True, use_container_width=True)
            else:
                st.info(f"未能获取 {ticker_to_analyze} 的季度报表详细指标。")

        with fin_tab_a:
            a_trends = fin_stmt_dict.get("annual_trends")
            a_summary = fin_stmt_dict.get("annual_summary")

            if a_trends is not None and not a_trends.empty:
                fig_a_trends = create_financial_trends_chart(a_trends, period_type="年度")
                if fig_a_trends:
                    st.plotly_chart(fig_a_trends, use_container_width=True)

            if a_summary is not None and not a_summary.empty:
                st.markdown("##### 📋 最近 4–5 个会计年度财务指标结构表")
                st.dataframe(a_summary, hide_index=True, use_container_width=True)
            else:
                st.info(f"未能获取 {ticker_to_analyze} 的年度报表详细指标。")
    else:
        st.info(f"未能提取 {ticker_to_analyze} 的财务报表数据。")

    # 5. 详细财务结构与分析师目标价扩展表
    if stock_info:
        with st.expander("📋 查看分析师评级、目标价与资本结构补充数据", expanded=False):
            f_col1, f_col2 = st.columns(2)
            
            with f_col1:
                st.markdown("#### 🎯 分析师评级与目标价")
                target_mean = stock_info.get("targetMeanPrice")
                target_high = stock_info.get("targetHighPrice")
                target_low = stock_info.get("targetLowPrice")
                rec_key = stock_info.get("recommendationKey", "N/A").upper()
                
                tgt_df = pd.DataFrame([
                    {"项目": "分析师共识评级", "数值": rec_key},
                    {"项目": "平均目标价 (Target Mean)", "数值": f"${target_mean:.2f}" if target_mean else "N/A"},
                    {"项目": "最高目标价 (Target High)", "数值": f"${target_high:.2f}" if target_high else "N/A"},
                    {"项目": "最低目标价 (Target Low)", "数值": f"${target_low:.2f}" if target_low else "N/A"},
                    {"项目": "52 周最高价", "数值": f"${stock_info.get('fiftyTwoWeekHigh', 0):.2f}"},
                    {"项目": "52 周最低价", "数值": f"${stock_info.get('fiftyTwoWeekLow', 0):.2f}"},
                ])
                st.dataframe(tgt_df, hide_index=True, use_container_width=True)

            with f_col2:
                st.markdown("#### 💵 现金流与资产负债表概况")
                rev = stock_info.get("totalRevenue")
                rev_growth = stock_info.get("revenueGrowth")
                fcf = stock_info.get("freeCashflow")
                cash = stock_info.get("totalCash")
                debt = stock_info.get("totalDebt")
                
                fin_df = pd.DataFrame([
                    {"项目": "年度总营收 (Revenue)", "数值": f"${rev/1e9:,.2f} B" if rev else "N/A"},
                    {"项目": "季度营收同比增速", "数值": f"{rev_growth*100:+.1f}%" if rev_growth is not None else "N/A"},
                    {"项目": "自由现金流 (Free Cash Flow)", "数值": f"${fcf/1e9:,.2f} B" if fcf else "N/A"},
                    {"项目": "总现金及等价物 (Total Cash)", "数值": f"${cash/1e9:,.2f} B" if cash else "N/A"},
                    {"项目": "总负债 (Total Debt)", "数值": f"${debt/1e9:,.2f} B" if debt else "N/A"},
                    {"项目": "股息率 (Dividend Yield)", "数值": f"{stock_info.get('dividendYield', 0)*100:.2f}%" if stock_info.get('dividendYield') else "0.00%"},
                ])
                st.dataframe(fin_df, hide_index=True, use_container_width=True)


# ==================================================================
# TAB 3: 芯片半导体产业链追踪 (Semiconductor Industry Tracker)
# ==================================================================
with tab_semi:
    st.header("⚡ 芯片半导体产业链深度追踪")
    st.caption(f"🕒 实时数据更新 (美东时间): **{current_et_str}** | 覆盖算力、晶圆代工、光刻设备、存储与模拟芯片全产业链")

    # 1. 行业基准与核心标的相对收益对比
    st.subheader("📈 半导体龙头多股累计收益率对比 (Relative Performance)")

    semi_symbols_all = [item["symbol"] for item in SEMI_BASKET]
    
    col_s1, col_s2 = st.columns([3, 1])
    with col_s1:
        default_selected_semi = ["NVDA", "TSM", "ASML", "AVGO", "AMD", "MU", "SOXX"]
        selected_semi_tickers = st.multiselect(
            "选择要进行收益率对比的标的:",
            semi_symbols_all,
            default=default_selected_semi
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
