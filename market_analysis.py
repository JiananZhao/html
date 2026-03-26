# market_analysis.py

import yfinance as yf
import pandas as pd
import streamlit as st
from datetime import date, timedelta, datetime
import requests
from fredapi import Fred
import os # file operation
from io import StringIO # 用于将下载的文本内容包装成文件对象

# ----------------------------------------------------
# Function to get S&P 500 Symbols from Wikipedia
# ----------------------------------------------------
@st.cache_data(ttl=timedelta(days=30)) # Cache symbols for 30 day
def get_sp500_symbols():
    OUTPUT_FILENAME = 'sp500_symbols.csv'
    temp_filename = "temp_download.csv" # 临时文件用于保存下载内容
    """
    Fetches the latest S&P 500 component list from Wikipedia.
    """
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    
    # CRITICAL FIX: Add User-Agent to bypass 403 Forbidden error
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    }
    
    try:
        # "尝试从 Wikipedia 获取 S&P 500 成分股列表..."
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

        # 核心替换逻辑：将所有点号 '.' 替换为连字符 '-'
        cleaned_symbols = [symbol.replace('.', '-') for symbol in symbols]
        #st.success(f"成功获取并清理 {len(cleaned_symbols)} 个 S&P 500 成分股代码。")
        df_symbols = pd.DataFrame(cleaned_symbols, columns=['Symbol'])
        #st.info(df_symbols)
        # 保存到 CSV 文件
        df_symbols.to_csv(OUTPUT_FILENAME, index=False)
        
        return cleaned_symbols
        
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
@st.cache_data(ttl=timedelta(days=1)) # Cache stock data everyday
def get_sp500_stock_data():
    """Downloads historical price data for all S&P 500 symbols."""
    FILE_PATH = 'spy500_data.csv'
    TTL_SECONDS = 60*0.1 # 60 minute Time-To-Live (TTL)
    sp500_symbols = get_sp500_symbols() 
    #st.info(sp500_symbols)
    if not sp500_symbols:
        st.warning("未能获取 S&P 500 成分股列表，无法下载股票数据。")
        return None
        
    # --- 1. Check if cached CSV exists and is fresh ---
    if os.path.exists(FILE_PATH):
        file_mod_time = os.path.getmtime(FILE_PATH)
        age_seconds = datetime.now().timestamp() - file_mod_time
        
        if age_seconds < TTL_SECONDS:
            # st.info(f"💾 从本地文件加载股票数据 ({FILE_PATH})...")
            try:
                # Load data from CSV, handling the MultiIndex header structure
                data = pd.read_csv(
                    FILE_PATH, 
                    header=[0, 1], 
                    index_col=0, 
                    parse_dates=True
                )
                st.success("数据加载成功。")
                return data
            except Exception as e:
                # If loading fails, log error and proceed to download
                st.error(f"加载本地文件失败: {e}")
        else:
            st.info(f"📅 本地数据已过期，将重新下载")
            
            end_date = date.today()
            start_date = end_date - timedelta(days=700)  # Set start date for required history (9000 days provides a long history)
        
            st.write(f"📈 正在下载 {len(sp500_symbols)} 支 S&P 500 成分股历史价格数据... (初次运行较慢)")
        
            data = None
            try:
                # 使用 concurrent downloads (threads) 来处理大符号列表
                data = yf.download(tickers=sp500_symbols, start=start_date, end=end_date, group_by='ticker', progress=False, auto_adjust=True, repair=True)
                downloaded_tickers = data.columns.get_level_values(0).unique().tolist()
                st.info(downloaded_tickers)
                # Filter out tickers that failed to download or are entirely empty
                valid_tickers = [ticker for ticker in sp500_symbols if (ticker, 'Close') in data.columns]
                #st.info(valid_tickers)
                if len(valid_tickers) < len(sp500_symbols):
                    st.warning(f"注意: {len(sp500_symbols) - len(valid_tickers)} 支股票数据未能完全下载。")
        
                # --- 3. Save to CSV before returning ---
                if data is not None:
                    # Save data to CSV, maintaining the MultiIndex structure
                    data.to_csv(FILE_PATH, index=True)
                    st.success(f"✅ 数据下载完成并已保存到本地文件: {FILE_PATH}")       
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

# --- 关键：从 Streamlit Secrets 获取 API Key ---
try:
    FRED_API_KEY = st.secrets["FRED_API_KEY"]
except KeyError:
    FRED_API_KEY = None
    st.error("无法找到 FRED_API_KEY。请将其添加为 Streamlit Secret 以获取失业率数据。")


@st.cache_data(ttl=timedelta(days=1))
def get_unemployment_data():
    """
    使用 fredapi 获取美国失业率 (UNRATE) 数据。
    """
    if not FRED_API_KEY:
        return pd.DataFrame()

    try:
        fred = Fred(api_key=FRED_API_KEY)
        
        # 获取 UNRATE 系列 (月度数据)
        unrate_series = fred.get_series('UNRATE') 
        
        if unrate_series is None or unrate_series.empty:
            st.warning("FRED API 返回的失业率数据为空。")
            return pd.DataFrame()
        
        # 转换为 DataFrame，并重命名列
        df_unrate = unrate_series.to_frame(name='Unemployment_Rate')
        
        # 确保索引是日期时间格式 (通常是自动的)
        df_unrate.index.name = 'Date' 
        
        # 为了与您的其他日线数据匹配，可能需要进行降采样或处理，但月度数据可以直接绘制
        return df_unrate
        
    except Exception as e:
        st.error(f"获取 FRED 失业率数据失败: {e}")
        return pd.DataFrame()

#@st.cache_data(ttl=timedelta(days=1))
def get_highyield_data():
    """
    使用 fredapi 获取指定 FRED 系列的数据。
    """
    # 1. 检查 API Key
    if not FRED_API_KEY:
        st.error("FRED API Key 未设置。请在 Streamlit Secrets 或代码中设置 FRED_API_KEY。")
        return pd.DataFrame()

    try:
        # 2. 初始化 Fred 客户端
        fred = Fred(api_key=FRED_API_KEY)
        
        # 3. 获取指定系列数据，并限制起始日期
        data_series = fred.get_series('BAMLH0A0HYM2')
        
        # 4. 检查数据是否为空
        if data_series is None or data_series.empty:
            st.warning(f"FRED API 返回的系列 '{series_id}' 数据为空或获取失败。")
            return pd.DataFrame()
        
        # 5. 转换为 DataFrame，并重命名列
        df_data = data_series.to_frame(name='Value')
        
        # 6. 设置索引名称
        df_data.index.name = 'Date'
        
        return df_data
        
    except Exception as e:
        st.error(f"获取 FRED 数据失败 (Series ID: {series_id}): {e}")
        return pd.DataFrame()

def _get_fred_api_key():
    try:
        return st.secrets["FRED_API_KEY"]
    except Exception:
        return os.getenv("FRED_API_KEY", "")


@st.cache_data(ttl=60 * 60 * 6)
def get_fed_balance_sheet_data():
    """
    FRED series:
    WALCL = Assets: Total Assets (Less Eliminations from Consolidation)
    单位: Millions of U.S. Dollars
    """
    fred_api_key = _get_fred_api_key()
    if not fred_api_key:
        return pd.DataFrame()

    url = "https://api.stlouisfed.org/fred/series/observations"
    params = {
        "series_id": "WALCL",
        "api_key": fred_api_key,
        "file_type": "json",
        "observation_start": "2008-01-01",
        "sort_order": "asc",
    }

    try:
        response = requests.get(url, params=params, timeout=30)
        response.raise_for_status()
        data = response.json().get("observations", [])

        if not data:
            return pd.DataFrame()

        df = pd.DataFrame(data)
        df = df[df["value"] != "."].copy()

        df["date"] = pd.to_datetime(df["date"])
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
        df = df.dropna(subset=["value"])

        # 原始单位是 million USD，这里转成 trillion USD
        df["balance_sheet_tn"] = df["value"] / 1_000_000

        return df[["date", "balance_sheet_tn"]].reset_index(drop=True)

    except Exception as e:
        print(f"Error fetching Fed balance sheet data: {e}")
        return pd.DataFrame()
