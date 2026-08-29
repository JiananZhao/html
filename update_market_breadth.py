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
BATCH_SIZE = 100

def get_retry_session():
    """配置带指数退避的 Resilient requests Session"""
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

def fetch_sp500_symbols_online():
    """从线上数据集或维基百科抓取最新标普 500 成分股列表"""
    urls = [
        "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/main/data/constituents.csv",
        "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    ]
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    session = get_retry_session()

    # 1. 尝试 Dataset CSV
    try:
        res = session.get(urls[0], headers=headers, timeout=15)
        if res.status_code == 200 and len(res.text) > 100:
            df = pd.read_csv(StringIO(res.text))
            if 'Symbol' in df.columns:
                symbols = [s.replace('.', '-') for s in df['Symbol'].dropna().astype(str).str.strip() if s]
                if len(symbols) > 400:
                    print(f"Loaded {len(symbols)} S&P 500 symbols from online dataset.")
                    return symbols
    except Exception as e:
        print(f"Online dataset fetch failed: {e}")

    # 2. 尝试 Wikipedia
    try:
        res = session.get(urls[1], headers=headers, timeout=15)
        if res.status_code == 200:
            tables = pd.read_html(StringIO(res.text))
            for tbl in tables:
                if 'Symbol' in tbl.columns:
                    symbols = [s.replace('.', '-') for s in tbl['Symbol'].dropna().astype(str).str.strip() if s]
                    if len(symbols) > 400:
                        print(f"Loaded {len(symbols)} S&P 500 symbols from Wikipedia.")
                        return symbols
    except Exception as e:
        print(f"Wikipedia fetch failed: {e}")

    return []

def load_symbols():
    """优先加载本地 sp500_symbols.csv，若无效则从线上抓取"""
    if os.path.exists(SYMBOLS_CSV) and os.path.getsize(SYMBOLS_CSV) > 500:
        try:
            df = pd.read_csv(SYMBOLS_CSV)
            col = 'Symbol' if 'Symbol' in df.columns else df.columns[0]
            symbols = [s.replace('.', '-') for s in df[col].dropna().astype(str).str.strip() if s]
            # 过滤明显错误的代码
            symbols = [s for s in symbols if s not in ['NXP', 'TME', 'HIMS', 'KFT', 'APT', 'EXE', 'HPC', 'KDX']]
            if 'NXPI' not in symbols:
                symbols.append('NXPI')
            if len(symbols) > 400:
                print(f"Successfully loaded {len(symbols)} symbols from local {SYMBOLS_CSV}")
                return symbols
        except Exception as e:
            print(f"Error reading local {SYMBOLS_CSV}: {e}")

    symbols = fetch_sp500_symbols_online()
    if len(symbols) > 400:
        pd.DataFrame(symbols, columns=['Symbol']).to_csv(SYMBOLS_CSV, index=False)
        print(f"Saved {len(symbols)} tickers to {SYMBOLS_CSV}")
        return symbols

    raise RuntimeError("Failed to obtain full S&P 500 constituent list (>400 stocks required).")

def fetch_data_in_batches(symbols, start_date):
    """分批下载行情，并对失败/缺失个股进行单股补充重试"""
    all_closes = []
    
    for i in range(0, len(symbols), BATCH_SIZE):
        batch = symbols[i:i + BATCH_SIZE]
        print(f"Downloading batch {i // BATCH_SIZE + 1}/{(len(symbols) - 1) // BATCH_SIZE + 1} ({len(batch)} symbols)...")
        try:
            df_batch = yf.download(batch, start=start_date, progress=False, threads=True)['Close']
            if isinstance(df_batch, pd.Series):
                df_batch = df_batch.to_frame()
            all_closes.append(df_batch)
        except Exception as e:
            print(f"Warning: Failed batch download ({i}-{i+BATCH_SIZE}): {e}")
        time.sleep(0.5)

    if not all_closes:
        return pd.DataFrame()

    combined = pd.concat(all_closes, axis=1)
    combined = combined.loc[:, ~combined.columns.duplicated()]

    # 兜底：检查并对缺失最新行数据的股票进行单独重试
    if not combined.empty:
        latest_valid_cols = combined.iloc[-1].notna()
        missing_latest = [s for s in symbols if s not in combined.columns or not latest_valid_cols.get(s, False)]
        
        if 0 < len(missing_latest) <= 60:
            print(f"Retrying {len(missing_latest)} symbols with missing latest data individually...")
            for sym in missing_latest:
                try:
                    df_single = yf.download(sym, start=start_date, progress=False)['Close']
                    if not df_single.empty:
                        combined[sym] = df_single
                except Exception:
                    pass
                time.sleep(0.1)

    return combined

def update_breadth():
    print("Loading full S&P 500 constituent list...")
    symbols = load_symbols()
    print(f"Tracking {len(symbols)} S&P 500 constituent symbols.")

    today = pd.to_datetime(datetime.date.today())
    # 10 年 + 300 天均线预热
    start_date = (today - datetime.timedelta(days=3650 + 300)).strftime('%Y-%m-%d')
    print(f"Fetching market data starting from {start_date}...")

    data = fetch_data_in_batches(symbols, start_date)

    if data.empty:
        print("No market data retrieved.")
        set_github_output("commit_needed", "false")
        return

    data = data.sort_index().dropna(how='all')

    # 熔断门禁：若最新交易日有效股票不足 400 只（盘后未完全结算），剔除该残缺日
    if len(data) > 0 and data.iloc[-1].notna().sum() < 400:
        print(f"Warning: Latest date {data.index[-1].strftime('%Y-%m-%d')} has only {data.iloc[-1].notna().sum()} valid tickers. Dropping incomplete day.")
        data = data.iloc[:-1]

    # 计算移动平均线
    ma20 = data.rolling(window=20, min_periods=15).mean()
    ma50 = data.rolling(window=50, min_periods=35).mean()
    ma200 = data.rolling(window=200, min_periods=150).mean()

    # 严格对齐分母：当日既有收盘价、又有有效 MA 均线的股票数量
    valid_ma20 = (data.notna() & ma20.notna()).sum(axis=1)
    valid_ma50 = (data.notna() & ma50.notna()).sum(axis=1)
    valid_ma200 = (data.notna() & ma200.notna()).sum(axis=1)

    # 站上均线百分比（有效样本数需 >= 100）
    pct_above_20 = ((data > ma20).sum(axis=1) / valid_ma20.replace(0, np.nan) * 100).where(valid_ma20 >= 100, np.nan)
    pct_above_50 = ((data > ma50).sum(axis=1) / valid_ma50.replace(0, np.nan) * 100).where(valid_ma50 >= 100, np.nan)
    pct_above_200 = ((data > ma200).sum(axis=1) / valid_ma200.replace(0, np.nan) * 100).where(valid_ma200 >= 100, np.nan)

    # 腾落指标
    daily_returns = data.pct_change()
    advances = (daily_returns > 0).sum(axis=1)
    declines = (daily_returns < 0).sum(axis=1)
    ad_ratio = (advances / declines.replace(0, np.nan)).fillna(0).round(2)

    breadth_df = pd.DataFrame({
        'date': data.index.strftime('%Y-%m-%d'),
        'pct_above_20ma': pct_above_20.round(2).values,
        'pct_above_50ma': pct_above_50.round(2).values,
        'pct_above_200ma': pct_above_200.round(2).values,
        'advances': advances.values,
        'declines': declines.values,
        'ad_ratio': ad_ratio.values
    })

    # 清除全 NaN 行
    breadth_df = breadth_df.dropna(subset=['pct_above_20ma', 'pct_above_50ma', 'pct_above_200ma'], how='all').reset_index(drop=True)

    # 保存
    breadth_df.to_csv(BREADTH_CSV, index=False)
    print(f"Successfully updated {BREADTH_CSV} ({len(breadth_df)} trading days)")

    set_github_output("commit_needed", "true")

def set_github_output(name, value):
    github_output = os.environ.get('GITHUB_OUTPUT')
    if github_output:
        with open(github_output, 'a') as f:
            f.write(f"{name}={value}\n")

if __name__ == "__main__":
    update_breadth()
