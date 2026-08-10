import os
import datetime
import requests
import pandas as pd
import numpy as np
import yfinance as yf
import streamlit as st
from io import StringIO
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BREADTH_CSV = "market_breadth.csv"
SPY_DATA_CSV = "spy500_data.csv"
SYMBOLS_CSV = "sp500_symbols.csv"

def get_retry_session():
    """Configures a resilient requests session with exponential backoff retries."""
    session = requests.Session()
    retries = Retry(
        total=5,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        raise_on_status=False
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session

@st.cache_data(ttl=3600)
def get_sp500_symbols():
    """Retrieves S&P 500 symbol list with fallback to sp500_symbols.csv."""
    if os.path.exists(SYMBOLS_CSV) and os.path.getsize(SYMBOLS_CSV) > 10:
        try:
            df = pd.read_csv(SYMBOLS_CSV)
            if 'Symbol' in df.columns:
                return df['Symbol'].dropna().astype(str).str.strip().tolist()
            elif 'symbol' in df.columns:
                return df['symbol'].dropna().astype(str).str.strip().tolist()
        except Exception as e:
            print(f"Error loading {SYMBOLS_CSV}: {e}")

    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    headers = {'User-Agent': 'Mozilla/5.0'}
    try:
        session = get_retry_session()
        response = session.get(url, headers=headers, timeout=15)
        response.raise_for_status()
        tables = pd.read_html(StringIO(response.text))
        for table in tables:
            if 'Symbol' in table.columns:
                symbols = table['Symbol'].tolist()
                cleaned_symbols = [symbol.replace('.', '-') for symbol in symbols if isinstance(symbol, str)]
                return cleaned_symbols
    except Exception as e:
        print(f"Failed to fetch symbols online: {e}")

    return [
        "AAPL", "MSFT", "AMZN", "NVDA", "GOOGL", "META", "TSLA", "BRK-B", "UNH", "JNJ",
        "JPM", "XOM", "V", "PG", "MA", "HD", "CVX", "LLY", "ABBV", "MRK"
    ]

@st.cache_data(ttl=3600)
def get_sp500_stock_data():
    """
    优先直接读取 CSV 缓存文件 (market_breadth.csv 或 spy500_data.csv)。
    判断数据是否为最新：如果已是最新（截至当日或最新交易日），直接载入返回，避免重新下载；
    如果数据有缺失，则仅增量计算缺失日期的市场宽度并追加更新至 CSV。
    """
    today = pd.to_datetime(datetime.date.today())

    # 优先检查 market_breadth.csv
    if os.path.exists(BREADTH_CSV) and os.path.getsize(BREADTH_CSV) > 10:
        try:
            df_breadth = pd.read_csv(BREADTH_CSV)
            if 'date' in df_breadth.columns and len(df_breadth) > 0:
                df_breadth['date'] = pd.to_datetime(df_breadth['date'])
                df_breadth = df_breadth.sort_values('date').reset_index(drop=True)
                latest_date = df_breadth['date'].max()

                # 如果数据已是最新（同日或已覆盖最新交易日），直接秒读返回！
                if latest_date.date() >= today.date() or (today.weekday() >= 5 and (today - latest_date).days <= 3):
                    st.success(f"已直接读取预计算文件 `{BREADTH_CSV}`（最新日期: {latest_date.strftime('%Y-%m-%d')}）")
                    return df_breadth

                # 数据滞后，进行增量拉取与补全
                st.info(f"本地数据最新日期为 {latest_date.strftime('%Y-%m-%d')}，正在增量补全至最新交易日...")
                updated_df = _incremental_update_breadth(df_breadth, latest_date, today)
                return updated_df
        except Exception as e:
            st.warning(f"读取 {BREADTH_CSV} 异常 ({e})，尝试备用数据源...")

    # 备用检查 spy500_data.csv
    if os.path.exists(SPY_DATA_CSV) and os.path.getsize(SPY_DATA_CSV) > 10:
        try:
            df_spy = pd.read_csv(SPY_DATA_CSV)
            st.success(f"已直接从本地文件读取: `{SPY_DATA_CSV}`")
            return df_spy
        except Exception as e:
            st.warning(f"读取 {SPY_DATA_CSV} 异常: {e}")

    # 仅当本地彻底无 CSV 缓存时，才发起一次性全量数据拉取
    st.info("本地无历史 CSV 缓存文件，正在首次拉取成分股数据...")
    return _full_download_sp500_data(today)

def _incremental_update_breadth(df_existing, last_date, today):
    """只抓取从 last_date 到今天缺失的增量数据，追加并写入 CSV"""
    symbols = get_sp500_symbols()
    start_date = (last_date - datetime.timedelta(days=210)).strftime('%Y-%m-%d') # 保留200MA所需窗口

    try:
        data = yf.download(symbols, start=start_date, progress=False, threads=True)['Close']
        if not data.empty:
            ma20 = data.rolling(window=20).mean()
            ma50 = data.rolling(window=50).mean()
            ma200 = data.rolling(window=200).mean()

            valid_counts = data.notna().sum(axis=1)
            valid_mask = valid_counts > 0

            pct_above_20 = ((data > ma20).sum(axis=1) / valid_counts * 100).where(valid_mask, np.nan)
            pct_above_50 = ((data > ma50).sum(axis=1) / valid_counts * 100).where(valid_mask, np.nan)
            pct_above_200 = ((data > ma200).sum(axis=1) / valid_counts * 100).where(valid_mask, np.nan)

            daily_returns = data.pct_change()
            advances = (daily_returns > 0).sum(axis=1)
            declines = (daily_returns < 0).sum(axis=1)
            ad_ratio = advances / declines.replace(0, np.nan)

            breadth_new = pd.DataFrame({
                'date': data.index.strftime('%Y-%m-%d'),
                'pct_above_20ma': pct_above_20.round(2).values,
                'pct_above_50ma': pct_above_50.round(2).values,
                'pct_above_200ma': pct_above_200.round(2).values,
                'advances': advances.values,
                'declines': declines.values,
                'ad_ratio': ad_ratio.round(2).fillna(0).values
            })

            breadth_new['dt'] = pd.to_datetime(breadth_new['date'])
            new_records = breadth_new[breadth_new['dt'] > last_date].drop(columns=['dt'])

            if not new_records.empty:
                combined = pd.concat([df_existing, new_records]).drop_duplicates(subset=['date']).sort_values('date')
                combined.to_csv(BREADTH_CSV, index=False)
                st.success(f"已更新最新数据至 {combined['date'].iloc[-1]} 并保存至 `{BREADTH_CSV}`")
                return combined
    except Exception as e:
        st.warning(f"增量更新过程触发异常 ({e})，使用已有本地缓存展示。")

    return df_existing

def _full_download_sp500_data(today):
    """首次拉取数据"""
    symbols = get_sp500_symbols()
    start_date = (today - datetime.timedelta(days=3650)).strftime('%Y-%m-%d')
    try:
        data = yf.download(symbols, start=start_date, progress=False, threads=True)['Close']
        if not data.empty:
            ma20 = data.rolling(window=20).mean()
            ma50 = data.rolling(window=50).mean()
            ma200 = data.rolling(window=200).mean()

            valid_counts = data.notna().sum(axis=1)
            valid_mask = valid_counts > 0

            pct_above_20 = ((data > ma20).sum(axis=1) / valid_counts * 100).where(valid_mask, np.nan)
            pct_above_50 = ((data > ma50).sum(axis=1) / valid_counts * 100).where(valid_mask, np.nan)
            pct_above_200 = ((data > ma200).sum(axis=1) / valid_counts * 100).where(valid_mask, np.nan)

            daily_returns = data.pct_change()
            advances = (daily_returns > 0).sum(axis=1)
            declines = (daily_returns < 0).sum(axis=1)
            ad_ratio = advances / declines.replace(0, np.nan)

            breadth_df = pd.DataFrame({
                'date': data.index.strftime('%Y-%m-%d'),
                'pct_above_20ma': pct_above_20.round(2).values,
                'pct_above_50ma': pct_above_50.round(2).values,
                'pct_above_200ma': pct_above_200.round(2).values,
                'advances': advances.values,
                'declines': declines.values,
                'ad_ratio': ad_ratio.round(2).fillna(0).values
            })

            breadth_df.to_csv(BREADTH_CSV, index=False)
            st.success(f"已初始化 10 年历史市场宽度数据并保存至 `{BREADTH_CSV}`")
            return breadth_df
    except Exception as e:
        st.error(f"首次下载数据失败: {e}")

    return pd.DataFrame()

def _fetch_lbma_gold_data():
    """获取 LBMA 黄金历史数据"""
    urls = [
        "https://www.lbma.org.uk/prices-and-data/precious-metal-prices",
        "https://www.gold.org/goldhub/data/gold-prices"
    ]
    headers = {'User-Agent': 'Mozilla/5.0'}
    session = get_retry_session()

    for url in urls:
        try:
            response = session.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            tables = pd.read_html(StringIO(response.text))
            if tables:
                return tables[0]
        except Exception as e:
            print(f"Error fetching LBMA gold data: {e}")

    return None
