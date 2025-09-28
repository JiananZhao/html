# market_analysis.py

import yfinance as yf
import pandas as pd
import streamlit as st
from datetime import date, timedelta
import requests

# ----------------------------------------------------
# Function to get S&P 500 Symbols from Wikipedia
# ----------------------------------------------------
@st.cache_data(ttl=timedelta(days=1)) # Cache symbols for 1 day
def get_sp500_symbols():
    """
    Fetches the latest S&P 500 component list from Wikipedia.
    """
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    
    # CRITICAL FIX: Add User-Agent to bypass 403 Forbidden error
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        st.info("尝试从 Wikipedia 获取 S&P 500 成分股列表...")
        
        # Use requests to download content with headers
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status() 

        # Use pandas to read the HTML content (response.text)
        tables = pd.read_html(response.text)
        
        sp500_table = None
        for table in tables:
            if 'Symbol' in table.columns and 'Security' in table.columns:
                sp500_table = table
                break
        
        if sp500_table is None:
            st.error("无法在 Wikipedia 页面找到 S&P 500 成分股表格。")
            return []

        symbols = sp500_table['Symbol'].tolist()
        
        st.success(f"成功获取 {len(symbols)} 个 S&P 500 成分股代码。")
        return symbols

    except requests.exceptions.HTTPError as e:
        st.error(f"获取 S&P 500 成分股列表失败 (HTTP 错误: {e})。请检查 User-Agent 或目标 URL。")
        return []
    except requests.exceptions.RequestException as e:
        st.error(f"获取 S&P 500 成分股列表失败 (网络或超时错误): {e}")
        return []
    except Exception as e:
        st.error(f"解析 S&P 500 成分股列表失败: {e}")
        return []


# ----------------------------------------------------
# Function to download stock data
# ----------------------------------------------------
@st.cache_data(ttl=timedelta(hours=6)) # Cache stock data for 6 hours
def get_sp500_stock_data():
    """Downloads historical price data for all S&P 500 symbols."""
    
    sp500_symbols = get_sp500_symbols() 
    
    if not sp500_symbols:
        st.warning("未能获取 S&P 500 成分股列表，无法下载股票数据。")
        return None

    end_date = date.today()
    start_date = end_date - timedelta(days=90) # Need 90 days for 20 DMA calculation buffer

    st.write(f"📈 正在下载 {len(sp500_symbols)} 支 S&P 500 成分股历史价格数据... (初次运行较慢)")
    
    try:
        # 使用 concurrent downloads (threads) 来处理大符号列表
        data = yf.download(
            tickers=sp500_symbols,
            start=start_date,
            end=end_date,
            group_by='ticker',
            progress=False, 
            auto_adjust=True, 
            repair=True,
            # --- 关键修复：移除 'max_workers' 和 'threads' 参数 ---
            # yfinance 默认会进行线程下载，不需要额外设置这些参数
        )
        
        # Filter out tickers that failed to download or are entirely empty
        valid_tickers = [ticker for ticker in sp500_symbols if (ticker, 'Close') in data.columns]
        
        if len(valid_tickers) < len(sp500_symbols):
            st.warning(f"注意: {len(sp500_symbols) - len(valid_tickers)} 支股票数据未能完全下载。")
            
        return data

    except Exception as e:
        st.error(f"下载S&P 500数据失败: {e}")
        return None


# ----------------------------------------------------
# Function to calculate market breadth
# ----------------------------------------------------
def calculate_market_breadth(stock_data: pd.DataFrame):
    """
    计算有多少成分股的股价位于20日和60日均线上方。
    
    Returns:
        包含计数和百分比的数据字典，现包含 20 DMA 和 60 DMA 的结果。
    """
    
    sp500_symbols = get_sp500_symbols()

    if stock_data is None or stock_data.empty or not sp500_symbols:
        return {
            "eligible_total": 0,
            "20DMA_count": 0, "20DMA_percentage": 0,
            "60DMA_count": 0, "60DMA_percentage": 0,
        }

    above_20ma_count = 0
    above_60ma_count = 0
    total_eligible_stocks = 0 

    # 遍历每个股票代码
    for ticker in sp500_symbols:
        if (ticker, 'Close') in stock_data.columns:
            df_ticker = stock_data[ticker]['Close'].dropna()
            
            # Need at least 60 points for the 60 DMA
            if len(df_ticker) < 60:
                continue
            
            # 1. Calculate Moving Averages
            df_ticker_20ma = df_ticker.rolling(window=20).mean()
            df_ticker_60ma = df_ticker.rolling(window=60).mean()
            
            # 2. Get latest values
            latest_close = df_ticker.iloc[-1]
            latest_20ma = df_ticker_20ma.iloc[-1]
            latest_60ma = df_ticker_60ma.iloc[-1]
            
            if pd.isna(latest_close) or pd.isna(latest_20ma) or pd.isna(latest_60ma):
                continue

            # 3. Compare and Count
            if latest_close > latest_20ma:
                above_20ma_count += 1
            
            if latest_close > latest_60ma:
                above_60ma_count += 1
            
            total_eligible_stocks += 1
            
    # Calculate percentages
    pct_20ma = (above_20ma_count / total_eligible_stocks) * 100 if total_eligible_stocks > 0 else 0
    pct_60ma = (above_60ma_count / total_eligible_stocks) * 100 if total_eligible_stocks > 0 else 0
    
    return {
        "eligible_total": total_eligible_stocks,
        "20DMA_count": above_20ma_count, 
        "20DMA_percentage": pct_20ma,
        "60DMA_count": above_60ma_count, 
        "60DMA_percentage": pct_60ma,
    }
