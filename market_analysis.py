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
def calculate_market_breadth_history(stock_data: pd.DataFrame):
    """
    计算历史上每天有多少成分股的股价位于20日和60日均线上方。
    
    Returns:
        pd.DataFrame: 索引为日期，列为 '20DMA_Breadth' 和 '60DMA_Breadth' 百分比。
    """
    
    sp500_symbols = get_sp500_symbols()
    
    # 获取所有收盘价数据列
    close_data = stock_data.xs('Close', level=1, axis=1)

    if close_data.empty or not sp500_symbols:
        return pd.DataFrame()

    # 确保只保留S&P 500成分股的列
    close_data = close_data[sp500_symbols]
    
    # 1. 计算所有股票的历史移动平均线
    ma_20 = close_data.rolling(window=20).mean()
    ma_60 = close_data.rolling(window=60).mean()

    # 2. 比较：收盘价是否高于移动平均线 (得到 True/False DataFrame)
    # True 被视为 1, False 被视为 0
    above_20ma_df = (close_data > ma_20).astype(int)
    above_60ma_df = (close_data > ma_60).astype(int)

    # 3. 汇总：计算每天有多少股票高于MA
    # (即按行求和)
    daily_20ma_count = above_20ma_df.sum(axis=1)
    daily_60ma_count = above_60ma_df.sum(axis=1)

    # 4. 计算每天符合MA计算条件的股票总数
    # 如果收盘价或MA是NaN，则该股票不合格 (即 rolling window 不足)
    daily_eligible_count = (
        close_data.notna() & ma_60.notna()
    ).sum(axis=1)
    
    # 5. 计算百分比
    # 避免除以零
    breadth_history = pd.DataFrame({
        '20DMA_Breadth': (daily_20ma_count / daily_eligible_count) * 100,
        '60DMA_Breadth': (daily_60ma_count / daily_eligible_count) * 100,
        'Eligible_Count': daily_eligible_count
    }).dropna()
    
    return breadth_history

# ----------------------------------------------------------------------
# IMPORTANT: New function for getting the LATEST SNAPSHOT (for sidebar)
# ----------------------------------------------------------------------

def get_latest_breadth_snapshot(breadth_history: pd.DataFrame):
    """
    从历史数据中提取最新的市场宽度快照，用于侧边栏显示。
    """
    if breadth_history.empty:
        return {
            "eligible_total": "N/A",
            "20DMA_count": "N/A", "20DMA_percentage": 0,
            "60DMA_count": "N/A", "60DMA_percentage": 0,
        }
    
    latest = breadth_history.iloc[-1]
    total = latest['Eligible_Count']
    
    # 计算最新的计数 (需要回到原始逻辑，或者将计数存储在历史DF中)
    # 为简单起见，这里假设我们只展示百分比。
    # 如果要展示计数，最好在历史DF中存储计数，或者回到原始计算方式获取最新快照。
    # 鉴于我们已重写历史DF，我们只使用百分比和总数。
    
    # 注意：为了让 rd_data.py 的侧边栏能够继续工作，我们需要重新包装数据结构。
    latest_snapshot = {
        "eligible_total": int(total),
        "20DMA_percentage": latest['20DMA_Breadth'],
        "60DMA_percentage": latest['60DMA_Breadth'],
        # 由于 historical calculation 过程复杂化了 count 提取，
        # 暂时使用百分比和总数来推算 count。
        "20DMA_count": int(latest['20DMA_Breadth'] / 100 * total), 
        "60DMA_count": int(latest['60DMA_Breadth'] / 100 * total),
    }
    return latest_snapshot
