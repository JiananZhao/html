import os
import datetime
import time
import pandas as pd
import numpy as np
import yfinance as yf
import requests
from io import StringIO
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BREADTH_CSV = "market_breadth.csv"
SYMBOLS_CSV = "sp500_symbols.csv"
BATCH_SIZE = 50  # 调小 Batch 降低触发 Yahoo 限流概率

def get_retry_session():
    """配置带指数退避的 Resilient requests Session"""
    session = requests.Session()
    retries = Retry(
        total=5,
        backoff_factor=1.5,
        status_forcelist=[429, 500, 502, 503, 504],
        raise_on_status=False
    )
    adapter = HTTPAdapter(max_retries=retries)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session

def fetch_sp500_symbols_online():
    """从线上数据集抓取最新标普 500 成分股列表"""
    urls = [
        "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/main/data/constituents.csv",
        "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    ]
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    session = get_retry_session()

    try:
        res = session.get(urls[0], headers=headers, timeout=15)
        if res.status_code == 200 and len(res.text) > 100:
            df = pd.read_csv(StringIO(res.text))
            if 'Symbol' in df.columns:
                symbols = [s.replace('.', '-') for s in df['Symbol'].dropna().astype(str).str.strip() if s]
                if len(symbols) > 400:
                    return symbols
    except Exception:
        pass

    try:
        res = session.get(urls[1], headers=headers, timeout=15)
        if res.status_code == 200:
            tables = pd.read_html(StringIO(res.text))
            for tbl in tables:
                if 'Symbol' in tbl.columns:
                    symbols = [s.replace('.', '-') for s in tbl['Symbol'].dropna().astype(str).str.strip() if s]
                    if len(symbols) > 400:
                        return symbols
    except Exception:
        pass

    return []

def load_symbols():
    """优先加载本地 sp500_symbols.csv，并严格清洗无效代码"""
    if os.path.exists(SYMBOLS_CSV) and os.path.getsize(SYMBOLS_CSV) > 500:
        try:
            df = pd.read_csv(SYMBOLS_CSV)
            col = 'Symbol' if 'Symbol' in df.columns else df.columns[0]
            symbols = [s.replace('.', '-') for s in df[col].dropna().astype(str).str.strip() if s]
            invalid_set = {'NXP', 'TME', 'HIMS', 'KFT', 'APT', 'EXE', 'HPC', 'KDX', 'LNW'}
            symbols = [s for s in symbols if s not in invalid_set]
            if 'NXPI' not in symbols:
                symbols.append('NXPI')
            if len(symbols) > 400:
                print(f"Loaded {len(symbols)} clean S&P 500 constituent symbols.")
                return symbols
        except Exception as e:
            print(f"Error reading local {SYMBOLS_CSV}: {e}")

    symbols = fetch_sp500_symbols_online()
    if len(symbols) > 400:
        pd.DataFrame(symbols, columns=['Symbol']).to_csv(SYMBOLS_CSV, index=False)
        return symbols

    raise RuntimeError("Failed to obtain full S&P 500 constituent list.")

def clean_index_tz(df):
    """统一剥离时区信息并规范化日期，彻底解决索引对齐变 NaN 问题"""
    if df is not None and not df.empty:
        if getattr(df.index, 'tz', None) is not None:
            df.index = df.index.tz_localize(None)
        df.index = pd.to_datetime(df.index).normalize()
    return df

def fetch_data_in_batches(symbols, start_date):
    """分批下载行情，统一 auto_adjust=True，无上限自动重试所有缺失个股"""
    all_closes = []
    
    for i in range(0, len(symbols), BATCH_SIZE):
        batch = symbols[i:i + BATCH_SIZE]
        print(f"Downloading batch {i // BATCH_SIZE + 1}/{(len(symbols) - 1) // BATCH_SIZE + 1} ({len(batch)} symbols)...")
        try:
            df_batch = yf.download(batch, start=start_date, auto_adjust=True, progress=False, threads=True)
            if isinstance(df_batch, pd.DataFrame) and 'Close' in df_batch.columns:
                df_close = df_batch['Close']
            elif isinstance(df_batch, pd.Series):
                df_close = df_batch.to_frame()
            else:
                df_close = pd.DataFrame()
            
            df_close = clean_index_tz(df_close)
            all_closes.append(df_close)
        except Exception as e:
            print(f"Warning: Batch download exception: {e}")
        time.sleep(0.6)

    if not all_closes:
        return pd.DataFrame()

    combined = pd.concat(all_closes, axis=1)
    combined = combined.loc[:, ~combined.columns.duplicated()]

    # 彻底解除 60 只门禁：无上限自动补抓所有缺失最新数据的股票
    if not combined.empty and len(combined) > 0:
        latest_valid = combined.iloc[-1].notna()
        missing_latest = [s for s in symbols if s not in combined.columns or not latest_valid.get(s, False)]
        
        if len(missing_latest) > 0:
            print(f"Retrying all {len(missing_latest)} missing symbols individually...")
            for sym in missing_latest:
                try:
                    single = yf.download(sym, start=start_date, auto_adjust=True, progress=False)
                    if isinstance(single, pd.DataFrame) and 'Close' in single.columns:
                        s_series = single['Close']
                    elif isinstance(single, pd.Series):
                        s_series = single
                    else:
                        s_series = pd.Series(dtype=float)
                    
                    s_series = clean_index_tz(s_series)
                    if not s_series.empty:
                        combined[sym] = s_series
                except Exception:
                    pass
                time.sleep(0.1)

    return combined

def calculate_breadth_dataframe(data):
    """双重非空校验，严格对齐分子与分母"""
    data = data.sort_index().dropna(how='all')

    ma20 = data.rolling(window=20, min_periods=15).mean()
    ma50 = data.rolling(window=50, min_periods=35).mean()
    ma200 = data.rolling(window=200, min_periods=150).mean()

    # 严格对齐分母：当日既有收盘价、又有有效 MA 均线的有效股票数
    valid_ma20 = (data.notna() & ma20.notna()).sum(axis=1)
    valid_ma50 = (data.notna() & ma50.notna()).sum(axis=1)
    valid_ma200 = (data.notna() & ma200.notna()).sum(axis=1)

    pct_above_20 = ((data > ma20).sum(axis=1) / valid_ma20.replace(0, np.nan) * 100).where(valid_ma20 >= 100, np.nan)
    pct_above_50 = ((data > ma50).sum(axis=1) / valid_ma50.replace(0, np.nan) * 100).where(valid_ma50 >= 100, np.nan)
    pct_above_200 = ((data > ma200).sum(axis=1) / valid_ma200.replace(0, np.nan) * 100).where(valid_ma200 >= 100, np.nan)

    daily_returns = data.pct_change()
    advances = (daily_returns > 0).sum(axis=1)
    declines = (daily_returns < 0).sum(axis=1)
    ad_ratio = (advances / declines.replace(0, np.nan)).fillna(0).round(2)

    df_out = pd.DataFrame({
        'date': data.index.strftime('%Y-%m-%d'),
        'pct_above_20ma': pct_above_20.round(2).values,
        'pct_above_50ma': pct_above_50.round(2).values,
        'pct_above_200ma': pct_above_200.round(2).values,
        'advances': advances.values,
        'declines': declines.values,
        'ad_ratio': ad_ratio.values
    })

    return df_out.dropna(subset=['pct_above_20ma', 'pct_above_50ma', 'pct_above_200ma'], how='all').reset_index(drop=True)

def update_breadth():
    symbols = load_symbols()
    today = pd.to_datetime(datetime.date.today())
    
    # 策略优化：仅拉取过去 450 天（约 300 个交易日）计算滚动指标，彻底消除 Yahoo Finance 限流
    lookback_days = 450
    start_date = (today - datetime.timedelta(days=lookback_days)).strftime('%Y-%m-%d')
    print(f"Fetching recent market data starting from {start_date} for rolling updates...")

    recent_data = fetch_data_in_batches(symbols, start_date)
    if recent_data.empty:
        print("No market data retrieved.")
        set_github_output("commit_needed", "false")
        return

    # 熔断门禁：若最新交易日有效股票不足 450 只，剔除该未结算日期
    if len(recent_data) > 0 and recent_data.iloc[-1].notna().sum() < 450:
        print(f"Warning: Latest date {recent_data.index[-1].strftime('%Y-%m-%d')} has only {recent_data.iloc[-1].notna().sum()} valid tickers. Dropping incomplete day.")
        recent_data = recent_data.iloc[:-1]

    new_breadth_df = calculate_breadth_dataframe(recent_data)

    # 增量合并策略：保留历史数据，仅覆写最近计算的交易日
    if os.path.exists(BREADTH_CSV) and os.path.getsize(BREADTH_CSV) > 1000:
        try:
            hist_df = pd.read_csv(BREADTH_CSV)
            hist_df['date'] = hist_df['date'].astype(str)
            new_breadth_df['date'] = new_breadth_df['date'].astype(str)
            
            combined_df = pd.concat([hist_df, new_breadth_df]).drop_duplicates(subset=['date'], keep='last').sort_values('date').reset_index(drop=True)
            combined_df.to_csv(BREADTH_CSV, index=False)
            print(f"Successfully merged & updated {BREADTH_CSV} (Total trading days: {len(combined_df)})")
            set_github_output("commit_needed", "true")
            return
        except Exception as e:
            print(f"Error merging with existing CSV: {e}")

    new_breadth_df.to_csv(BREADTH_CSV, index=False)
    print(f"Successfully generated {BREADTH_CSV} ({len(new_breadth_df)} trading days)")
    set_github_output("commit_needed", "true")

def set_github_output(name, value):
    github_output = os.environ.get('GITHUB_OUTPUT')
    if github_output:
        with open(github_output, 'a') as f:
            f.write(f"{name}={value}\n")

if __name__ == "__main__":
    update_breadth()
