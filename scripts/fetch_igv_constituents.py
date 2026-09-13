"""
受控数据获取脚本：获取 IGV 核心前 15 大成分股历史日线收盘价
运行一次并将数据永久固化为本地标准数据集 igv_constituents_local.csv
严格遵循 LESSONS_LEARNED.md：强制剥离时区、统一 datetime64[ns] 精度
"""

import os
import sys
import io
import pandas as pd
import yfinance as yf

# 强制 UTF-8 输出以兼容 Windows 终端
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

TICKERS = [
    'MSFT', 'CRM', 'ORCL', 'ADBE', 'NOW',
    'INTU', 'PLTR', 'PANW', 'CRWD', 'SNOW',
    'WDAY', 'FTNT', 'DDOG', 'CDNS', 'SNPS'
]

OUTPUT_FILE = 'igv_constituents_local.csv'

def main():
    print(f"🚀 开始受控拉取 IGV 前 15 大核心成分股数据: {TICKERS}")
    start_date = '2010-01-01'
    end_date = '2026-09-12'

    # 批量拉取
    data = yf.download(TICKERS, start=start_date, end=end_date, progress=False, auto_adjust=True)
    
    if 'Close' in data.columns:
        df_close = data['Close'].copy()
    else:
        df_close = data.copy()

    # 重置索引并规范化日期
    df_close = df_close.reset_index()
    if 'Date' in df_close.columns:
        df_close = df_close.rename(columns={'Date': 'date'})
    
    # 强制剥离时区并转换为标准格式 (Lesson 1)
    df_close['date'] = pd.to_datetime(df_close['date']).dt.tz_localize(None).dt.strftime('%Y-%m-%d')
    df_close = df_close.sort_values('date').reset_index(drop=True)

    # 检查字段
    for t in TICKERS:
        if t not in df_close.columns:
            print(f"⚠️ 警告: 未找到 {t} 数据")
        else:
            valid_cnt = df_close[t].notna().sum()
            print(f"✅ {t}: 包含 {valid_cnt} 个有效交易日数据")

    df_close.to_csv(OUTPUT_FILE, index=False)
    print(f"🎉 数据已永久固化至本地主真理库: {os.path.abspath(OUTPUT_FILE)} (共 {len(df_close)} 行)")

if __name__ == '__main__':
    main()
