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

def fetch_sp500_symbols_online():
    """Fetches full S&P 500 component ticker list from Wikipedia and online datasets."""
    urls = [
        "https://raw.githubusercontent.com/datasets/s-and-p-500-companies/main/data/constituents.csv",
        "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    ]
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    session = get_retry_session()

    # 1. Try dataset CSV first
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

    # 2. Try Wikipedia
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
    """Loads symbols from online sources, saves to sp500_symbols.csv, or loads from existing local file."""
    symbols = fetch_sp500_symbols_online()
    if len(symbols) > 400:
        pd.DataFrame(symbols, columns=['Symbol']).to_csv(SYMBOLS_CSV, index=False)
        print(f"Saved {len(symbols)} tickers to {SYMBOLS_CSV}")
        return symbols

    if os.path.exists(SYMBOLS_CSV) and os.path.getsize(SYMBOLS_CSV) > 500:
        try:
            df = pd.read_csv(SYMBOLS_CSV)
            col = 'Symbol' if 'Symbol' in df.columns else df.columns[0]
            symbols = [s.replace('.', '-') for s in df[col].dropna().astype(str).str.strip() if s]
            if len(symbols) > 400:
                print(f"Loaded {len(symbols)} tickers from {SYMBOLS_CSV}")
                return symbols
        except Exception as e:
            print(f"Error reading {SYMBOLS_CSV}: {e}")

    raise RuntimeError("Failed to obtain full S&P 500 constituent list (>400 stocks required).")

def fetch_data_in_batches(symbols, start_date):
    """Downloads price data in batches of BATCH_SIZE to avoid HTTP 429 rate limits."""
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
    return combined

def update_breadth():
    print("Loading full S&P 500 constituent list...")
    symbols = load_symbols()
    print(f"Successfully tracking {len(symbols)} S&P 500 constituent symbols.")

    today = pd.to_datetime(datetime.date.today())
    # 10 years + 300 days for 200MA warmup
    start_date = (today - datetime.timedelta(days=3650 + 300)).strftime('%Y-%m-%d')
    print(f"Re-calculating full 10-year market breadth starting from {start_date}...")

    data = fetch_data_in_batches(symbols, start_date)

    if data.empty:
        print("No market data retrieved.")
        set_github_output("commit_needed", "false")
        return

    data = data.sort_index().dropna(how='all')

    # Compute moving averages across ALL 500+ constituents
    ma20 = data.rolling(window=20, min_periods=15).mean()
    ma50 = data.rolling(window=50, min_periods=35).mean()
    ma200 = data.rolling(window=200, min_periods=150).mean()

    # Count valid (non-NaN) prices per date across constituents
    valid_counts = data.notna().sum(axis=1)
    valid_mask = valid_counts >= 100  # Must have at least 100 constituents active on trading day

    pct_above_20 = ((data > ma20).sum(axis=1) / valid_counts * 100).where(valid_mask, np.nan)
    pct_above_50 = ((data > ma50).sum(axis=1) / valid_counts * 100).where(valid_mask, np.nan)
    pct_above_200 = ((data > ma200).sum(axis=1) / valid_counts * 100).where(valid_mask, np.nan)

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

    # Drop dates where moving averages are incomplete
    breadth_df = breadth_df.dropna(subset=['pct_above_20ma', 'pct_above_50ma', 'pct_above_200ma'], how='all').reset_index(drop=True)

    # Save complete 10-year market_breadth.csv
    breadth_df.to_csv(BREADTH_CSV, index=False)
    print(f"Successfully generated 10-year market breadth dataset ({len(breadth_df)} trading days) and saved to {BREADTH_CSV}")

    set_github_output("commit_needed", "true")

def set_github_output(name, value):
    github_output = os.environ.get('GITHUB_OUTPUT')
    if github_output:
        with open(github_output, 'a') as f:
            f.write(f"{name}={value}\n")

if __name__ == "__main__":
    update_breadth()
