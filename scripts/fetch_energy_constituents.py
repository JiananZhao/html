import os
import sys
import io
import yfinance as yf
import pandas as pd
from datetime import datetime

# 强制 UTF-8 输出以兼容 Windows 终端
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 4大细分领域股票池 (共 41 只)
ENERGY_CONSTITUENTS = {
    'Integrated': ['XOM', 'CVX', 'SHEL', 'TTE', 'BP', 'EQNR'],
    'E&P': ['COP', 'EOG', 'OXY', 'FANG', 'DVN', 'HES', 'MRO', 'CTRA', 'APA', 'EQT', 'AR', 'OVV', 'MUR', 'SM', 'CHK'],
    'Services': ['SLB', 'HAL', 'BKR', 'NOV', 'WHD', 'CHX', 'FTI', 'RIG', 'PTEN', 'NBR'],
    'Refining_Midstream': ['PSX', 'VLO', 'MPC', 'KMI', 'WMB', 'EPD', 'ET', 'OKE', 'TRGP', 'MPLX']
}

def main():
    print("🚀 开始拉取能源全产业链 41 只核心成份股历史数据...")
    all_tickers = []
    for group, tickers in ENERGY_CONSTITUENTS.items():
        all_tickers.extend(tickers)
        
    start_date = '2008-01-01'
    
    print(f"[*] 股票池总计: {len(all_tickers)} 只")
    
    # 批量下载
    df = yf.download(all_tickers, start=start_date, progress=True)
    
    if df.empty:
        print("❌ 下载失败")
        return
        
    # 提取收盘价
    if isinstance(df.columns, pd.MultiIndex):
        close_df = df['Close'].copy()
    else:
        close_df = df[['Close']].copy()
        
    # 处理索引
    close_df = close_df.reset_index()
    close_df['date'] = pd.to_datetime(close_df['Date']).dt.strftime('%Y-%m-%d')
    close_df = close_df.drop(columns=['Date'], errors='ignore')
    
    # 移动 date 到第一列
    cols = ['date'] + [c for c in close_df.columns if c != 'date']
    close_df = close_df[cols]
    
    # 填充空值 (前向填充)
    close_df = close_df.ffill()
    
    out_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'energy_constituents_local.csv')
    close_df.to_csv(out_path, index=False)
    
    print(f"✅ 拉取完成！已成功保存 {len(close_df)} 个交易日的数据至:")
    print(f"   {out_path}")

if __name__ == "__main__":
    main()
