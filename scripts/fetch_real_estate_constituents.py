import os
import sys
import io
import yfinance as yf
import pandas as pd

# 保证控制台在 Windows 下 UTF-8 输出正常
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# 6 大细分功能支柱股票池 (共 34 只核心标的 + VNQ / IYR / XLRE 3大基准)
REAL_ESTATE_GROUPS = {
    'Benchmarks': ['VNQ', 'IYR', 'XLRE'],
    'Telecom_DataCenters': ['AMT', 'CCI', 'EQIX', 'DLR'],
    'Industrial_Storage': ['PLD', 'PSA', 'EXR', 'REXR'],
    'Retail_Healthcare': ['SPG', 'O', 'KIM', 'WELL', 'VTR', 'NNN'],
    'Residential': ['AVB', 'EQR', 'INVH', 'MAA', 'ESS'],
    'Homebuilders': ['DHI', 'LEN', 'NVR', 'PHM', 'TOL'],
    'Office_CRE': ['BXP', 'VNO', 'SLG', 'ARE', 'KRC']
}

def main():
    print("🚀 开始受控拉取房地产与 REITs 板块 (VNQ / XLRE) 35 只核心标的历史数据...")
    all_tickers = []
    for group, tickers in REAL_ESTATE_GROUPS.items():
        all_tickers.extend(tickers)
    # 去重
    all_tickers = sorted(list(set(all_tickers)))
        
    start_date = '2006-01-01'
    print(f"[*] 标的池总计: {len(all_tickers)} 只标的 (起始日期: {start_date})")
    print(f"[*] 标的列表: {all_tickers}")
    
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
    
    out_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'real_estate_constituents_local.csv')
    close_df.to_csv(out_path, index=False)
    
    print(f"✅ 拉取完成！已成功保存 {len(close_df)} 个交易日、{len(cols)-1} 个标的的数据至:")
    print(f"   {out_path}")

if __name__ == "__main__":
    main()
