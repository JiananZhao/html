import os
import sys
import io
import yfinance as yf
import pandas as pd

# 强制 UTF-8 输出以兼容 Windows 终端
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 4 大细分领域股票池 (共 38 只核心标的 + KRE & XLF 2大基准)
FINANCIAL_GROUPS = {
    'Benchmarks': ['KRE', 'XLF'],
    'Regional_Banks': [
        'USB', 'TFC', 'PNC', 'FITB', 'KEY', 'CFG', 'HBAN', 'MTB', 
        'WAL', 'ZION', 'CFR', 'CBSH', 'EWBC', 'FCNCA', 'BKU'
    ],
    'GSIBs': ['JPM', 'BAC', 'WFC', 'C', 'BK'],
    'Brokers_AssetMgrs': ['GS', 'MS', 'SCHW', 'BLK', 'CME', 'ICE', 'SPGI', 'MCO'],
    'Insurance_Payments': ['BRK-B', 'PGR', 'CB', 'MET', 'TRV', 'AIG', 'V', 'MA', 'AXP', 'COF']
}

def main():
    print("🚀 开始受控拉取区域性银行与综合金融板块 (KRE / XLF) 40 只核心标的历史数据...")
    all_tickers = []
    for group, tickers in FINANCIAL_GROUPS.items():
        all_tickers.extend(tickers)
        
    start_date = '2006-01-01'
    print(f"[*] 标的池总计: {len(all_tickers)} 只标的 (起始日期: {start_date})")
    
    # 批量受控下载
    df = yf.download(all_tickers, start=start_date, progress=True)
    
    if df.empty:
        print("❌ 数据下载失败")
        return
        
    # 提取收盘价
    if isinstance(df.columns, pd.MultiIndex):
        close_df = df['Close'].copy()
    else:
        close_df = df[['Close']].copy()
        
    # 重命名列名：将 BRK-B 重命名为 BRK_B 防止符号冲突
    if 'BRK-B' in close_df.columns:
        close_df = close_df.rename(columns={'BRK-B': 'BRK_B'})
        
    # 处理日期索引
    close_df = close_df.reset_index()
    if 'Date' in close_df.columns:
        close_df['date'] = pd.to_datetime(close_df['Date']).dt.strftime('%Y-%m-%d')
        close_df = close_df.drop(columns=['Date'])
    elif 'date' in close_df.columns:
        close_df['date'] = pd.to_datetime(close_df['date']).dt.strftime('%Y-%m-%d')
        
    # 移动 date 到第一列
    cols = ['date'] + [c for c in close_df.columns if c != 'date']
    close_df = close_df[cols]
    
    # 前向填充缺失值
    close_df = close_df.ffill()
    
    out_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'financial_constituents_local.csv')
    close_df.to_csv(out_path, index=False)
    
    print(f"✅ 拉取完成！已成功保存 {len(close_df)} 个交易日、{len(cols)-1} 个标的的数据至:")
    print(f"   {out_path}")

if __name__ == "__main__":
    main()
