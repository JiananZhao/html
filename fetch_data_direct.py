import os
import sys
import io
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
import requests
import pandas as pd
from datetime import datetime, timedelta
import yfinance as yf

def fetch_fred_series(api_key, series_id, value_col, start_date="2005-01-01"):
    url = "https://api.stlouisfed.org/fred/series/observations"
    params = {
        "series_id": series_id,
        "api_key": api_key,
        "file_type": "json",
        "observation_start": start_date,
        "sort_order": "asc",
    }
    print(f"[*] 正在抓取 FRED 系列: {series_id} -> {value_col}...")
    resp = requests.get(url, params=params, timeout=15)
    if resp.status_code != 200:
        print(f"[!] 警告: {series_id} 返回状态码 {resp.status_code}: {resp.text}")
        return pd.DataFrame()
    
    data = resp.json().get("observations", [])
    df = pd.DataFrame(data)
    if df.empty or "value" not in df.columns:
        print(f"[!] 警告: {series_id} 无数据返回")
        return pd.DataFrame()
        
    df = df[df["value"] != "."].copy()
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df[value_col] = pd.to_numeric(df["value"], errors="coerce")
    df = df.dropna(subset=["date", value_col])
    print(f"[+] {series_id} ({value_col}) 抓取成功: {len(df)} 行数据 (最早: {df['date'].iloc[0].strftime('%Y-%m-%d')}, 最新: {df['date'].iloc[-1].strftime('%Y-%m-%d')})")
    return df[["date", value_col]].reset_index(drop=True)

def main(api_key):
    print("="*70)
    print("开始全量下载 15+ 年宏观因子与标的价格数据并保存至本地...")
    print("="*70)
    
    # 1. FRED 宏观因子
    # 信用利差: BAA10Y (全历史 21年), BAMLH0A0HYM2 (近3年)
    baa = fetch_fred_series(api_key, "BAA10Y", "BAA10Y", "2005-01-01")
    hy_oas = fetch_fred_series(api_key, "BAMLH0A0HYM2", "HY_OAS_3Y", "2005-01-01")
    # 联储金融状况: NFCI
    nfci = fetch_fred_series(api_key, "NFCI", "NFCI", "2005-01-01")
    # 实际利率: DFII10
    real_yield = fetch_fred_series(api_key, "DFII10", "Real_Yield", "2005-01-01")
    # 美元指数: DTWEXBGS
    dxy = fetch_fred_series(api_key, "DTWEXBGS", "DXY", "2005-01-01")
    # 经济景气度: CFNAI (芝加哥联储经济景气) 与 INDPRO (工业产出同比)
    cfnai = fetch_fred_series(api_key, "CFNAI", "CFNAI", "2005-01-01")
    indpro = fetch_fred_series(api_key, "INDPRO", "INDPRO", "2004-01-01")
    if not indpro.empty:
        indpro["INDPRO_YoY"] = indpro["INDPRO"].pct_change(12) * 100.0
        indpro = indpro.dropna(subset=["INDPRO_YoY"])[["date", "INDPRO_YoY"]]
    
    # 2. Yahoo Finance 市场数据
    print("\n[*] 正在从 Yahoo Finance 抓取铜金比 (HG=F, GC=F)、高收益债 ETF (HYG) 与标的 (SPY, QQQ)...")
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365 * 21)
    
    # 铜金比
    metals = yf.download(["HG=F", "GC=F"], start=start_date.strftime("%Y-%m-%d"), progress=False)['Close']
    cg = pd.DataFrame()
    cg['date'] = pd.to_datetime(metals.index).tz_localize(None)
    cg['Copper_Gold'] = (metals["HG=F"] / metals["GC=F"]).values
    cg = cg.dropna()
    print(f"[+] 铜金比 (Copper_Gold) 抓取成功: {len(cg)} 行数据")
    
    # HYG (高收益债价格，可用于长期高收益信用度量)
    hyg_df = yf.download("HYG", start="2007-01-01", progress=False)['Close']
    hyg = pd.DataFrame()
    hyg['date'] = pd.to_datetime(hyg_df.index).tz_localize(None)
    hyg['HYG'] = hyg_df.values
    hyg = hyg.dropna()
    print(f"[+] 高收益债 ETF (HYG) 抓取成功: {len(hyg)} 行数据")
    
    # SPY & QQQ
    tickers = yf.download(["SPY", "QQQ"], start="2005-01-01", progress=False)['Close']
    prices = pd.DataFrame()
    prices['date'] = pd.to_datetime(tickers.index).tz_localize(None)
    prices['SPY'] = tickers['SPY'].values
    prices['QQQ'] = tickers['QQQ'].values
    prices = prices.dropna()
    print(f"[+] SPY & QQQ 价格抓取成功: {len(prices)} 行数据")
    
    # 3. 对齐并合并数据 (以日历日基准进行 backward asof merge)
    print("\n[*] 正在进行全量数据日期对齐与前向填充 (ffill)...")
    base_dates = pd.DataFrame({'date': pd.date_range(start="2005-01-01", end=datetime.now())})
    base_dates['date'] = pd.to_datetime(base_dates['date']).dt.tz_localize(None)
    
    df_list = [baa, hy_oas, nfci, real_yield, dxy, cfnai, indpro, cg, hyg, prices]
    for df in df_list:
        if not df.empty and 'date' in df.columns:
            df['date'] = pd.to_datetime(df['date']).dt.tz_localize(None)
            base_dates = pd.merge_asof(base_dates, df.sort_values('date'), on='date', direction='backward')
            
    merged = base_dates.dropna(subset=['SPY', 'QQQ']).reset_index(drop=True)
    
    out_path1 = "e:/AI/Github_AIProject/html/scratch_macro_data.csv"
    out_path2 = "C:/Users/jiana/.gemini/antigravity-ide/brain/ddcec604-91d0-4b3c-adb2-0d6f1b6d7c5f/scratch/raw_macro_market_data.csv"
    
    merged.to_csv(out_path1, index=False)
    merged.to_csv(out_path2, index=False)
    
    print("="*70)
    print(f"[SUCCESS] 数据抓取完成并已成功写入以下两处本地路径：")
    print(f" 1. {out_path1}")
    print(f" 2. {out_path2}")
    print(f"数据总行数: {len(merged)} 行")
    print(f"时间跨度: {merged['date'].iloc[0].strftime('%Y-%m-%d')} 至 {merged['date'].iloc[-1].strftime('%Y-%m-%d')}")
    print(f"字段列表: {list(merged.columns)}")
    print("="*70)

if __name__ == "__main__":
    key = "a39da0075f8676c83d4346320c8140d6"
    main(key)
