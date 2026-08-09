import os
import datetime
import time
import pandas as pd
import numpy as np
import yfinance as yf
import requests
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

def load_symbols():
    """Loads tickers from sp500_symbols.csv or returns top S&P 500 components as fallback."""
    if os.path.exists(SYMBOLS_CSV) and os.path.getsize(SYMBOLS_CSV) > 10:
        try:
            df = pd.read_csv(SYMBOLS_CSV)
            if 'Symbol' in df.columns:
                symbols = df['Symbol'].dropna().astype(str).str.strip().tolist()
            elif 'symbol' in df.columns:
                symbols = df['symbol'].dropna().astype(str).str.strip().tolist()
            else:
                symbols = df.iloc[:, 0].dropna().astype(str).str.strip().tolist()
            
            # Clean symbols for yfinance (replace dots with hyphens, e.g. BRK.B -> BRK-B)
            symbols = [s.replace('.', '-') for s in symbols if s]
            if len(symbols) > 0:
                return symbols
        except Exception as e:
            print(f"Error loading {SYMBOLS_CSV}: {e}")

    return [
        "AAPL", "MSFT", "AMZN", "NVDA", "GOOGL", "META", "TSLA", "BRK-B", "UNH", "JNJ",
        "JPM", "XOM", "V", "PG", "MA", "HD", "CVX", "LLY", "ABBV", "MRK",
        "PEP", "KO", "BAC", "WMT", "TMO", "MCD", "CSCO", "ACN", "ABT", "PFE"
    ]

def get_last_processed_date():
    """Returns the latest datetime recorded in market_breadth.csv."""
    if os.path.exists(BREADTH_CSV) and os.path.getsize(BREADTH_CSV) > 10:
        try:
            df = pd.read_csv(BREADTH_CSV)
            if 'date' in df.columns and len(df) > 0:
                df['date'] = pd.to_datetime(df['date'])
                return df['date'].max()
        except Exception as e:
            print(f"Error reading {BREADTH_CSV}: {e}")
    return None

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
    last_date = get_last_processed_date()
    today = pd.to_datetime(datetime.date.today())

    if last_date is not None and last_date.date() >= today.date():
        print(f"Market breadth data is up-to-date ({last_date.strftime('%Y-%m-%d')}). No update needed.")
        set_github_output("commit_needed", "false")
        return

    symbols = load_symbols()
    print(f"Tracking {len(symbols)} symbols.")

    start_date = (today - datetime.timedelta(days=3650)).strftime('%Y-%m-%d')
    print(f"Fetching 10 years of market data starting from {start_date}...")

    data = fetch_data_in_batches(symbols, start_date)

    if data.empty:
        print("No market data retrieved.")
        set_github_output("commit_needed", "false")
        return

    data = data.sort_index().dropna(how='all')

    # Compute moving averages
    ma20 = data.rolling(window=20, min_periods=10).mean()
    ma50 = data.rolling(window=50, min_periods=25).mean()
    ma200 = data.rolling(window=200, min_periods=100).mean()

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

    # Drop rows where all MA percentages are NaN (e.g. invalid dates)
    breadth_df = breadth_df.dropna(subset=['pct_above_20ma', 'pct_above_50ma', 'pct_above_200ma'], how='all')

    if last_date is not None:
        breadth_df['dt'] = pd.to_datetime(breadth_df['date'])
        new_records = breadth_df[breadth_df['dt'] > last_date].drop(columns=['dt'])
    else:
        new_records = breadth_df

    if new_records.empty:
        print("No new breadth records generated.")
        set_github_output("commit_needed", "false")
        return

    if os.path.exists(BREADTH_CSV) and os.path.getsize(BREADTH_CSV) > 10:
        df_existing = pd.read_csv(BREADTH_CSV)
        combined = pd.concat([df_existing, new_records]).drop_duplicates(subset=['date']).sort_values('date')
    else:
        combined = new_records

    combined.to_csv(BREADTH_CSV, index=False)
    latest_date_str = combined['date'].iloc[-1]
    print(f"Successfully updated {BREADTH_CSV} (total rows: {len(combined)}) with latest date: {latest_date_str}")

    set_github_output("commit_needed", "true")
    set_github_env("LATEST_DATE", latest_date_str)

def set_github_output(name, value):
    github_output = os.environ.get('GITHUB_OUTPUT')
    if github_output:
        with open(github_output, 'a') as f:
            f.write(f"{name}={value}\n")

def set_github_env(name, value):
    github_env = os.environ.get('GITHUB_ENV')
    if github_env:
        with open(github_env, 'a') as f:
            f.write(f"{name}={value}\n")

if __name__ == "__main__":
    update_breadth()
