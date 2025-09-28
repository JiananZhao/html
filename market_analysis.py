# market_analysis.py

import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import date, timedelta
import requests
from bs4 import BeautifulSoup
import numpy as np # Needed for some pandas operations/type hinting

# ------------------------------------------------------------------
# 1. Component List Retrieval
# ------------------------------------------------------------------

@st.cache_data(ttl=timedelta(days=7))
def get_sp500_symbols():
    """
    从 Wikipedia 获取 S&P 500 成分股代码列表。
    """
    st.info("尝试从 Wikipedia 获取 S&P 500 成分股列表...")
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    
    try:
        # 使用 requests 获取页面内容
        response = requests.get(url, timeout=10)
        response.raise_for_status() # 检查 HTTP 错误
        
        # 使用 BeautifulSoup 解析 HTML
        soup = BeautifulSoup(response.text, 'lxml')
        
        # 查找包含股票列表的表格 (通常是第一个带有 'wikitable' 类的表格)
        table = soup.find('table', {'class': 'wikitable sortable'})
        
        if not table:
            st.error("获取 S&P 500 成分股列表失败: 未找到维基百科表格。")
            return None
        
        tickers = []
        rows = table.find_all('tr')[1:] # 跳过表头
        
        for row in rows:
            cols = row.find_all('td')
            if cols:
                # 股票代码通常在第一列
                ticker = cols[0].text.strip()
                # 剔除尾部的换行符或空格
                if '\n' in ticker:
                    ticker = ticker.split('\n')[0].strip()
                tickers.append(ticker)
        
        if tickers:
            st.success(f"成功获取 {len(tickers)} 个 S&P 500 成分股代码。")
            return tickers
        else:
            st.error("获取 S&P 500 成分股列表失败: 表格为空或格式不匹配。")
            return None

    except requests.exceptions.RequestException as e:
        st.error(f"获取 S&P 500 成分股列表失败 (网络错误): {e}")
        return None
    except Exception as e:
        st.error(f"获取 S&P 500 成分股列表失败 (解析错误): {e}")
        return None

# ------------------------------------------------------------------
# 2. Stock Data Download
# ------------------------------------------------------------------

@st.cache_data(ttl=timedelta(hours=6))
def get_sp500_stock_data():
    """
    Downloads historical price data for all S&P 500 symbols for 5+ years.
    """
    
    sp500_symbols = get_sp500_symbols() 
    
    if not sp500_symbols:
        st.warning("未能获取 S&P 500 成分股列表，无法下载股票数据。")
        return None

    end_date = date.today()
    # 5.5 年的历史数据作为缓冲
    start_date = end_date - timedelta(days=2008) 

    st.info(f"正在下载 {len(sp500_symbols)} 支 S&P 500 成分股历史价格数据... (初次运行较慢)")
    
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
            # 确保移除了 max_workers 参数
        )
        
        # 检查下载的数据是否为空
        if data.empty:
            st.error("股票数据下载成功，但数据为空。")
            return None
            
        st.success("股票数据下载完成。")
        return data

    except Exception as e:
        st.error(f"下载 S&P 500 数据失败: {e}")
        return None


@st.cache_data(ttl=timedelta(hours=6)) 
def get_spy_data(start_date: date, end_date: date):
    """
    下载 SPY (S&P 500 ETF) 的历史收盘价。
    """
    ticker = "SPY"
    try:
        # 直接下载数据
        spy_df_raw = yf.download(
            tickers=ticker,
            start=start_date,
            end=end_date,
            progress=False,
            auto_adjust=True,
        )
        
        # 确保 'Close' 列存在
        if 'Close' not in spy_df_raw.columns:
             st.error("SPY 数据中未找到 'Close' 列。")
             return pd.DataFrame()

        # 只选择 'Close' 列，并将其重命名为 'SPY_Close'
        spy_df = spy_df_raw[['Close']].copy()
        spy_df.rename(columns={'Close': 'SPY_Close'}, inplace=True)
        
        # 返回 DataFrame
        return spy_df
        
    except Exception as e:
        st.error(f"下载 SPY 数据失败: {e}")
        return pd.DataFrame() 

# ------------------------------------------------------------------
# 3. Market Breadth Calculation
# ------------------------------------------------------------------

def calculate_market_breadth_history(stock_data: pd.DataFrame):
    """
    计算历史上每天有多少成分股的股价位于20日和60日均线上方。
    
    Returns:
        pd.DataFrame: 索引为日期，列为 '20DMA_Breadth', '60DMA_Breadth' 和 'Eligible_Count'。
    """
    
    sp500_symbols = get_sp500_symbols()
    
    # 获取所有收盘价数据列
    close_data = stock_data.xs('Close', level=1, axis=1)

    if close_data.empty or not sp500_symbols:
        return pd.DataFrame()

    # 确保只保留S&P 500成分股的列
    close_data = close_data.reindex(columns=sp500_symbols, fill_value=np.nan)
    
    # 1. 计算所有股票的历史移动平均线
    ma_20 = close_data.rolling(window=20).mean()
    ma_60 = close_data.rolling(window=60).mean()

    # 2. 比较：收盘价是否高于移动平均线 (得到 True/False DataFrame)
    # True 被视为 1, False 被视为 0
    above_20ma_df = (close_data > ma_20).astype(int)
    above_60ma_df = (close_data > ma_60).astype(int)

    # 3. 汇总：计算每天有多少股票高于MA
    daily_20ma_count = above_20ma_df.sum(axis=1)
    daily_60ma_count = above_60ma_df.sum(axis=1)

    # 4. 计算每天符合MA计算条件的股票总数
    # 只有当 Close 和 MA_60 都有值时，才认为该股票合格
    daily_eligible_count = (
        close_data.notna() & ma_60.notna()
    ).sum(axis=1)
    
    # 5. 计算百分比
    # 避免除以零，并移除计算初始阶段的 NaN 值
    breadth_history = pd.DataFrame({
        '20DMA_Breadth': (daily_20ma_count / daily_eligible_count) * 100,
        '60DMA_Breadth': (daily_60ma_count / daily_eligible_count) * 100,
        'Eligible_Count': daily_eligible_count
    }).dropna() # 移除所有包含 NaN 的行 (即在数据窗口期不足时)
    
    return breadth_history


def get_latest_breadth_snapshot(breadth_history: pd.DataFrame):
    """
    从历史数据中提取最新的市场宽度快照，用于侧边栏和快照图表显示。
    """
    if breadth_history.empty:
        return {
            "eligible_total": "N/A",
            "20DMA_count": "N/A", "20DMA_percentage": 0,
            "60DMA_count": "N/A", "60DMA_percentage": 0,
        }
    
    latest = breadth_history.iloc[-1]
    total = latest['Eligible_Count']
    
    latest_snapshot = {
        "eligible_total": int(total),
        "20DMA_percentage": latest['20DMA_Breadth'],
        "60DMA_percentage": latest['60DMA_Breadth'],
        # 推算 count：使用最新的百分比 * 总数
        "20DMA_count": int(round(latest['20DMA_Breadth'] / 100 * total)), 
        "60DMA_count": int(round(latest['60DMA_Breadth'] / 100 * total)),
    }
    return latest_snapshot
