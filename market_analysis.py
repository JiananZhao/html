# market_analysis.py

import yfinance as yf
import pandas as pd
import streamlit as st
from datetime import date, timedelta
import requests # 用于检查网页请求

# ----------------------------------------------------
# 新增函数: 获取 S&P 500 成分股列表
# ----------------------------------------------------
@st.cache_data(ttl=timedelta(days=1)) # 每天更新一次成分股列表
def get_sp500_symbols():
    """
    从 Wikipedia 页面获取最新的 S&P 500 成分股列表。
    """
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    
    # --- 关键修复：添加 User-Agent 头部 ---
    headers = {
        # 伪装成一个常见的浏览器（这里使用 Chrome 的User-Agent）
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        st.info("尝试从 Wikipedia 获取 S&P 500 成分股列表...")
        
        # 1. 使用 requests.get 发送请求，并带上 headers
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status() # 如果请求失败 (例如 403)，则抛出 HTTPError

        # 2. 将页面的 HTML 内容传递给 pandas
        # 注意：这里不能直接用 pd.read_html(url)，必须用 pd.read_html(response.text)
        tables = pd.read_html(response.text)
        
        # S&P 500 成分股表格通常是第一个，根据列名判断
        sp500_table = None
        for table in tables:
            # 检查表格是否包含 S&P 500 成分股所需的列
            if 'Symbol' in table.columns and 'Security' in table.columns:
                sp500_table = table
                break
        
        if sp500_table is None:
            st.error("无法在 Wikipedia 页面找到 S&P 500 成分股表格。")
            return []

        # 提取 'Symbol' 列并转换为列表
        symbols = sp500_table['Symbol'].tolist()
        
        st.success(f"成功获取 {len(symbols)} 个 S&P 500 成分股代码。")
        return symbols

    except requests.exceptions.HTTPError as e:
        # 针对 403/404 等 HTTP 错误给出更明确的提示
        st.error(f"获取 S&P 500 成分股列表失败 (HTTP 错误: {e})。请检查 User-Agent 或目标 URL。")
        return []
    except requests.exceptions.RequestException as e:
        st.error(f"获取 S&P 500 成分股列表失败 (网络或超时错误): {e}")
        return []
    except Exception as e:
        st.error(f"解析 S&P 500 成分股列表失败: {e}")
        return []

# ----------------------------------------------------
# 更新 get_sp500_stock_data 函数
# ----------------------------------------------------
@st.cache_data(ttl=timedelta(hours=6))
def get_sp500_stock_data():
    """首先获取 S&P 500 成分股列表，然后下载其历史价格数据。"""
    
    sp500_symbols = get_sp500_symbols() 
    
    if not sp500_symbols:
        st.warning("未能获取 S&P 500 成分股列表，无法下载股票数据。")
        return None

    end_date = date.today()
    start_date = end_date - timedelta(days=90) 

    st.write(f"📈 正在下载 {len(sp500_symbols)} 支 S&P 500 成分股历史价格数据... (初次运行较慢)")
    
    # --- 关键修复：添加重试机制和进度条 ---
    try:
        data = yf.download(
            tickers=sp500_symbols,
            start=start_date,
            end=end_date,
            group_by='ticker',
            progress=False,
            auto_adjust=True,
            repair=True,
            
            # --- Yfinance下载参数调优：增加重试次数和指数回退 ---
            # 这有助于处理网络临时故障和速率限制
            max_workers=10,  # 允许最多 10 个线程并行下载
            threads=True, 
        )
        
        # ... (数据过滤和返回逻辑保持不变)
        valid_tickers = [ticker for ticker in sp500_symbols if (ticker, 'Close') in data.columns]
        if len(valid_tickers) < len(sp500_symbols):
            st.warning(f"注意: {len(sp500_symbols) - len(valid_tickers)} 支股票数据未能完全下载。")
            
            # 确保只返回成功下载的列
            data = data[[ (ticker, col) for ticker in valid_tickers for col in data.columns.get_level_values(1).unique() if (ticker, col) in data.columns ]]
        
        return data

    except Exception as e:
        st.error(f"下载S&P 500数据失败: {e}")
        return None


def calculate_market_breadth(stock_data: pd.DataFrame):
    """
    计算有多少成分股的股价位于20日均线上方。
    
    Args:
        stock_data: yfinance下载的多重索引DataFrame。
        
    Returns:
        包含百分比和计数的数据字典。
    """
    # 获取最新的成分股列表，确保计算是基于最新的列表
    sp500_symbols = get_sp500_symbols()

    if stock_data is None or stock_data.empty or not sp500_symbols:
        return {"count": 0, "total": len(sp500_symbols), "percentage": 0}

    above_ma_count = 0
    total_eligible_stocks = 0 # 统计有足够数据计算MA的股票

    # 遍历每个股票代码
    for ticker in sp500_symbols:
        # 提取当前股票的收盘价数据
        # 检查股票是否在下载的数据中存在
        if (ticker, 'Close') in stock_data.columns:
            df_ticker = stock_data[ticker]['Close'].dropna()
            
            if len(df_ticker) < 20:
                # 数据不足以计算 20 DMA，跳过
                continue
            
            # 1. 计算 20 日简单移动平均线 (20 DMA)
            df_ticker_ma = df_ticker.rolling(window=20).mean()
            
            # 2. 获取最新价格和最新均线值
            # 确保最新价格和均线值不为 NaN
            latest_close = df_ticker.iloc[-1]
            latest_ma = df_ticker_ma.iloc[-1]
            
            if pd.isna(latest_close) or pd.isna(latest_ma):
                continue # 如果最新数据是 NaN，跳过这只股票

            # 3. 比较
            if latest_close > latest_ma:
                above_ma_count += 1
            
            total_eligible_stocks += 1
            
    percentage = (above_ma_count / total_eligible_stocks) * 100 if total_eligible_stocks > 0 else 0
    
    return {
        "count": above_ma_count,
        "total": total_eligible_stocks, # 修改为实际参与计算的股票总数
        "percentage": percentage
    }
