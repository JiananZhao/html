import os
import datetime
import pandas as pd
import numpy as np
import yfinance as yf

BREADTH_CSV = "market_breadth.csv"
SYMBOLS_CSV = "sp500_symbols.csv"

def load_symbols():
    if os.path.exists(SYMBOLS_CSV) and os.path.getsize(SYMBOLS_CSV) > 10:
        try:
            df = pd.read_csv(SYMBOLS_CSV)
            if 'Symbol' in df.columns:
                return df['Symbol'].dropna().tolist()
            elif 'symbol' in df.columns:
                return df['symbol'].dropna().tolist()
            else:
                return df.iloc[:, 0].dropna().tolist()
        except Exception as e:
            print(f"Error loading {SYMBOLS_CSV}: {e}")
    
    # Default S&P 500 top components as fallback
    return [
        "AAPL", "MSFT", "AMZN", "NVDA", "GOOGL", "META", "TSLA", "BRK-B", "UNH", "JNJ",
        "JPM", "XOM", "V", "PG", "MA", "HD", "CVX", "LLY", "ABBV", "MRK",
        "PEP", "KO", "BAC", "WMT", "TMO", "MCD", "CSCO", "ACN", "ABT", "PFE"
    ]

def get_last_processed_date():
    if os.path.exists(BREADTH_CSV) and os.path.getsize(BREADTH_CSV) > 10:
        try:
            df = pd.read_csv(BREADTH_CSV)
            if 'date' in df.columns and len(df) > 0:
                df['date'] = pd.to_datetime(df['date'])
                return df['date'].max()
        except Exception as e:
            print(f"Error reading {BREADTH_CSV}: {e}")
    return None

def update_breadth():
    last_date = get_last_processed_date()
    today = pd.to_datetime(datetime.date.today())

    if last_date is not None and last_date.date() >= today.date():
        print(f"Market breadth data is up-to-date ({last_date.strftime('%Y-%m-%d')}). No update needed.")
        set_github_output("commit_needed", "false")
        return

    print("Loading symbols...")
    symbols = load_symbols()
    print(f"Tracking {len(symbols)} symbols.")

    # Download 1-2 years of price history to calculate 200MA accurately
    start_date = (today - datetime.timedelta(days=400)).strftime('%Y-%m-%d')
    print(f"Fetching market data from {start_date}...")
    
    try:
        data = yf.download(symbols, start=start_date, progress=False)['Close']
    except Exception as e:
        print(f"Failed to download data from yfinance: {e}")
        set_github_output("commit_needed", "false")
        return

    if data.empty:
        print("No market data retrieved.")
        set_github_output("commit_needed", "false")
        return

    # Compute moving averages
    ma20 = data.rolling(window=20).mean()
    ma50 = data.rolling(window=50).mean()
    ma200 = data.rolling(window=200).mean()

    pct_above_20 = (data > ma20).sum(axis=1) / data.notna().sum(axis=1) * 100
    pct_above_50 = (data > ma50).sum(axis=1) / data.notna().sum(axis=1) * 100
    pct_above_200 = (data > ma200).sum(axis=1) / data.notna().sum(axis=1) * 100

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

    # Filter for new dates
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
    print(f"Successfully updated {BREADTH_CSV} with latest date: {latest_date_str}")

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
