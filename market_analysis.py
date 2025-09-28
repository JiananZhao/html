# market_analysis.py

import yfinance as yf
import pandas as pd
import streamlit as st
from datetime import date, timedelta

# ----------------------------------------------------
# 辅助函数 1: 获取 S&P 500 成分股（符号列表）
# 注意：yfinance 不直接提供成分股列表，通常需要从外部爬取或使用预存列表。
# 为简化代码和保证运行，这里使用一个常用且较稳定的替代方法：
# 下载 SPY (S&P 500 ETF) 的持有股票列表（可能不完全准确，但数据量够大）
# 或者更简单：我们使用一个通用的、较小的股票列表作为示例。
# 实际生产环境需要一个可靠的S&P 500成分股列表来源。
# ----------------------------------------------------

# 使用一个可靠的外部列表或直接硬编码一个大列表作为示例：
SP500_SYMBOLS = [
    'AAPL', 'MSFT', 'GOOGL', 'AMZN', 'NVDA', 'TSLA', 'JPM', 'JNJ', 'V', 'PG',
    'UNH', 'HD', 'MA', 'DIS', 'NFLX', 'ADBE', 'CRM', 'KO', 'PEP', 'WMT',
    'XOM', 'CVX', 'LLY', 'MRNA', 'PFE', 'GS', 'BAC', 'WFC', 'MS', 'AXP'
] # 仅为示例，请替换为完整的 S&P 500 列表！

@st.cache_data(ttl=timedelta(hours=6))
def get_sp500_stock_data():
    """使用 yfinance 下载 S&P 500 成分股的历史价格数据。"""
    
    end_date = date.today()
    # 需要过去至少 30 个交易日的数据来计算 20 日均线
    start_date = end_date - timedelta(days=90) 
    
    st.write("📈 正在下载S&P 500成分股历史价格数据... (初次运行较慢)")
    
    try:
        # 使用 yf.download 一次性下载所有股票数据
        data = yf.download(
            tickers=SP500_SYMBOLS,
            start=start_date,
            end=end_date,
            group_by='ticker' # 按股票代码分组数据
        )
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
    
    if stock_data is None or stock_data.empty:
        return {"count": 0, "total": len(SP500_SYMBOLS), "percentage": 0}

    above_ma_count = 0
    total_stocks = 0
    
    # 遍历每个股票代码
    for ticker in SP500_SYMBOLS:
        # 提取当前股票的收盘价数据
        if ticker in stock_data.columns.get_level_values(0):
            df_ticker = stock_data[ticker]['Close'].dropna()
            
            if len(df_ticker) < 20:
                # 数据不足以计算 20 DMA，跳过
                continue
            
            # 1. 计算 20 日简单移动平均线 (20 DMA)
            df_ticker_ma = df_ticker.rolling(window=20).mean()
            
            # 2. 获取最新价格和最新均线值
            latest_close = df_ticker.iloc[-1]
            latest_ma = df_ticker_ma.iloc[-1]
            
            # 3. 比较
            if latest_close > latest_ma:
                above_ma_count += 1
            
            total_stocks += 1
            
    percentage = (above_ma_count / total_stocks) * 100 if total_stocks > 0 else 0
    
    return {
        "count": above_ma_count,
        "total": total_stocks,
        "percentage": percentage
    }
