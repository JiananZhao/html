import os
import sys
import io
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta

# Force utf-8
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

def clean_index_tz(df):
    """统一剥离时区信息并规范化日期"""
    if df is not None and not df.empty:
        if getattr(df.index, 'tz', None) is not None:
            df.index = df.index.tz_localize(None)
        df.index = pd.to_datetime(df.index).normalize()
    return df

def update_etf_constituents(csv_file):
    """增量更新 ETF 成分股收盘价数据集"""
    if not os.path.exists(csv_file):
        print(f"File not found: {csv_file}")
        return
        
    df = pd.read_csv(csv_file)
    if 'date' not in df.columns:
        return
        
    tickers = [col for col in df.columns if col != 'date']
    max_date_str = df['date'].max()
    max_date = pd.to_datetime(max_date_str)
    
    # 增加2天的重叠期以防时区问题，之后去重
    start_date = (max_date - timedelta(days=2)).strftime('%Y-%m-%d')
    print(f"Updating {csv_file} from {start_date} for {len(tickers)} tickers...")
    
    try:
        data = yf.download(tickers, start=start_date, progress=False, auto_adjust=True)
        if 'Close' in data.columns:
            new_df = data['Close']
        else:
            new_df = data
            
        new_df = clean_index_tz(new_df)
        new_df = new_df.reset_index()
        if 'Date' in new_df.columns:
            new_df = new_df.rename(columns={'Date': 'date'})
            
        new_df['date'] = pd.to_datetime(new_df['date']).dt.strftime('%Y-%m-%d')
        
        # 仅保留大于已知最大日期的新数据
        new_df = new_df[new_df['date'] > max_date_str].copy()
        
        if not new_df.empty:
            # 保证列的顺序一致
            for t in tickers:
                if t not in new_df.columns:
                    new_df[t] = pd.NA
                    
            new_df = new_df[['date'] + tickers]
            
            combined = pd.concat([df, new_df], ignore_index=True)
            combined = combined.drop_duplicates(subset=['date'], keep='last').sort_values('date').reset_index(drop=True)
            combined.to_csv(csv_file, index=False)
            print(f"✅ Successfully appended {len(new_df)} new rows to {csv_file}.")
        else:
            print(f"ℹ️ No new data needed for {csv_file}.")
            
    except Exception as e:
        print(f"❌ Failed to update {csv_file}: {e}")

def update_single_stock_ohlcv(csv_file, ticker):
    """增量更新单只股票的高精度 OHLCV 数据"""
    if not os.path.exists(csv_file):
        print(f"File not found: {csv_file}")
        return
        
    df = pd.read_csv(csv_file)
    if 'date' not in df.columns:
        return
        
    max_date_str = df['date'].max()
    max_date = pd.to_datetime(max_date_str)
    start_date = (max_date - timedelta(days=2)).strftime('%Y-%m-%d')
    print(f"Updating {csv_file} ({ticker}) from {start_date}...")
    
    try:
        data = yf.download(ticker, start=start_date, progress=False, auto_adjust=True)
        if data.empty:
            return
            
        data = clean_index_tz(data)
        data = data.reset_index()
        if 'Date' in data.columns:
            data = data.rename(columns={'Date': 'date'})
            
        # 重命名列以匹配现有格式 (小写)
        rename_map = {}
        for col in data.columns:
            if col != 'date':
                new_col = col[0] if isinstance(col, tuple) else col
                rename_map[col] = str(new_col).lower()
        data = data.rename(columns=rename_map)
        
        data['date'] = pd.to_datetime(data['date']).dt.strftime('%Y-%m-%d')
        
        # 仅保留大于已知最大日期的新数据
        new_df = data[data['date'] > max_date_str].copy()
        
        if not new_df.empty:
            # 保证列的对齐
            expected_cols = list(df.columns)
            for col in expected_cols:
                if col not in new_df.columns:
                    new_df[col] = pd.NA
            new_df = new_df[expected_cols]
            
            combined = pd.concat([df, new_df], ignore_index=True)
            combined = combined.drop_duplicates(subset=['date'], keep='last').sort_values('date').reset_index(drop=True)
            combined.to_csv(csv_file, index=False)
            print(f"✅ Successfully appended {len(new_df)} new rows to {csv_file}.")
        else:
            print(f"ℹ️ No new data needed for {csv_file}.")
            
    except Exception as e:
        print(f"❌ Failed to update {csv_file}: {e}")

def main():
    # 增量更新单股 OHLCV
    update_single_stock_ohlcv('now_ohlcv_local.csv', 'NOW')
    
    # 增量更新 ETF 成分股矩阵
    etf_files = [
        'smh_constituents_local.csv',
        'igv_constituents_local.csv',
        'energy_constituents_local.csv',
        'financial_constituents_local.csv',
        'real_estate_constituents_local.csv'
    ]
    
    for etf_file in etf_files:
        update_etf_constituents(etf_file)

if __name__ == "__main__":
    main()
