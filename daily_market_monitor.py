# -*- coding: utf-8 -*-
"""
========================================================================================
项目名称：宏观反身性阿尔法模型 —— 每日增量更新与双轨信号监控引擎
文件名称：daily_market_monitor.py
开发日期：2026-09-12
========================================================================================

【系统定位与运行逻辑】：
1. 纯本地微型数据库维护 (Local-First Micro-DB):
   - 基于 e:/AI/Github_AIProject/html/market_data_local.csv 作为唯一真理库；
   - 每日美股收盘后运行，自动检查最新记录日期，仅拉取增量当天的 SPY、QQQ、HYG 与宏观数据；
   - 绝不重新全量下载 17 年历史数据，计算耗时仅需 0.1 秒！
2. 毫秒级双轨决策雷达运算 (Sub-Second Dual-Track Radar):
   - 计算 0~100 分宏观过热雷达分（反身性 Gap + 动量 Z-Score + 200MA 乖离度）；
   - 评分 >= 70 分：触发 🟡 宏观过热黄色预警（提示停止大额追高、收紧止损）；
   - 跌破关键均线：触发 🔴 卖出清仓避险；
   - 恐慌极值黄金坑：触发 🟢 极值抄底信号（持股股数大幅增殖）；
   - 正常牛市主升：保持 🟢 健康常态持仓；
3. 输出形态：
   - 格式化终端每日决策简报；
   - 自动追加记录至 daily_signal_log.csv；
   - 可供 Streamlit 前端、Windows 任务计划程序、批处理脚本一键调用。
========================================================================================
"""

import os
import sys
import io
import argparse
from datetime import datetime, timedelta

# 兼容 Windows 控制台 UTF-8
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

import pandas as pd
import numpy as np
import requests

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOCAL_CSV_PATH = os.path.join(BASE_DIR, "market_data_local.csv")
SIGNAL_LOG_PATH = os.path.join(BASE_DIR, "daily_signal_log.csv")
GITHUB_RAW_CSV_URL = "https://raw.githubusercontent.com/JiananZhao/html/master/market_data_local.csv"
FRED_API_KEY = "a39da0075f8676c83d4346320c8140d6"


def fetch_fred_single_series(api_key, series_id, start_date):
    """拉取 FRED 宏观指标增量数据"""
    url = "https://api.stlouisfed.org/fred/series/observations"
    params = {
        "series_id": series_id,
        "api_key": api_key,
        "file_type": "json",
        "observation_start": start_date,
        "sort_order": "asc"
    }
    try:
        resp = requests.get(url, params=params, timeout=12)
        if resp.status_code == 200:
            obs = resp.json().get("observations", [])
            df = pd.DataFrame(obs)
            if not df.empty and 'value' in df.columns:
                df = df[df['value'] != '.'].copy()
                df['date'] = pd.to_datetime(df['date']).dt.tz_localize(None).astype('datetime64[ns]')
                df['value'] = pd.to_numeric(df['value'], errors='coerce')
                df = df.dropna(subset=['date', 'value'])
                return df[['date', 'value']].rename(columns={'value': series_id})
    except Exception as e:
        print(f"[!] FRED {series_id} 增量拉取失败: {e}")
    return pd.DataFrame()


def sync_latest_market_data(force=False):
    """
    增量同步最新行情与宏观数据至本地 CSV 数据库 (支持跨平台与 GitHub 自动初始化)
    返回同步状态与最新数据总行数
    """
    if not os.path.exists(LOCAL_CSV_PATH):
        try:
            print(f"[*] 本地真理库不存在，正在从 GitHub 拉取基准数据库: {GITHUB_RAW_CSV_URL}")
            df_init = pd.read_csv(GITHUB_RAW_CSV_URL)
            if not df_init.empty and 'date' in df_init.columns:
                df_init.to_csv(LOCAL_CSV_PATH, index=False)
                print(f"[+] 成功从 GitHub 初始化本地真理库: {LOCAL_CSV_PATH}")
        except Exception as e:
            raise FileNotFoundError(f"本地真理库不存在且无法从 GitHub 初始化: {e}")

    df_local = pd.read_csv(LOCAL_CSV_PATH)
    df_local['date'] = pd.to_datetime(df_local['date']).dt.tz_localize(None).astype('datetime64[ns]')
    df_local = df_local.sort_values('date').reset_index(drop=True)
    
    last_date = df_local['date'].iloc[-1]
    today = pd.to_datetime(datetime.now().strftime('%Y-%m-%d'))
    
    print(f"[*] 本地数据库最新日期: {last_date.strftime('%Y-%m-%d')} | 今日日期: {today.strftime('%Y-%m-%d')}")
    
    if last_date >= today and not force:
        print("[+] 本地数据库已是最新，无需增量网络请求 (Local-First 保护生效)！")
        return {"status": "up_to_date", "last_date": last_date.strftime('%Y-%m-%d'), "rows": len(df_local)}

    # 需要拉取增量数据
    start_str = (last_date - timedelta(days=5)).strftime('%Y-%m-%d')
    print(f"[*] 正在拉取从 {start_str} 至今日的增量行情与宏观因子...")

    try:
        import yfinance as yf
        # 批量拉取 SPY, QQQ, HYG
        tickers = ['SPY', 'QQQ', 'HYG']
        yf_data = yf.download(tickers, start=start_str, progress=False)
        if yf_data.empty:
            print("[!] yfinance 暂无最新数据（可能未开盘或非交易日）")
            return {"status": "no_new_data", "last_date": last_date.strftime('%Y-%m-%d'), "rows": len(df_local)}

        # 提取收盘价
        if isinstance(yf_data.columns, pd.MultiIndex):
            close_df = yf_data['Close'].copy()
        else:
            close_df = yf_data[['Close']].copy()
            close_df.columns = tickers

        close_df = close_df.reset_index()
        close_df['date'] = pd.to_datetime(close_df['Date']).dt.tz_localize(None).astype('datetime64[ns]')
        close_df = close_df.drop(columns=['Date'], errors='ignore')

        # 拉取 FRED 核心宏观因子增量
        baa_df = fetch_fred_single_series(FRED_API_KEY, "BAA10Y", start_str)
        nfci_df = fetch_fred_single_series(FRED_API_KEY, "NFCI", start_str)
        ry_df = fetch_fred_single_series(FRED_API_KEY, "DFII10", start_str)

        # 合并增量
        inc_df = close_df[['date', 'SPY', 'QQQ', 'HYG']].copy()
        if not baa_df.empty:
            inc_df = pd.merge_asof(inc_df.sort_values('date'), baa_df.sort_values('date'), on='date', direction='backward')
        if not nfci_df.empty:
            inc_df = pd.merge_asof(inc_df.sort_values('date'), nfci_df.sort_values('date'), on='date', direction='backward')
        if not ry_df.empty:
            ry_df = ry_df.rename(columns={'DFII10': 'Real_Yield'})
            inc_df = pd.merge_asof(inc_df.sort_values('date'), ry_df.sort_values('date'), on='date', direction='backward')

        # 对齐现有本地数据库列
        for col in df_local.columns:
            if col not in inc_df.columns:
                # 前向填充已有特征
                inc_df[col] = df_local[col].iloc[-1]

        inc_df = inc_df[df_local.columns].copy()
        # 仅追加大于 last_date 的新行
        new_rows = inc_df[inc_df['date'] > last_date].copy()
        
        if len(new_rows) > 0:
            combined = pd.concat([df_local, new_rows], ignore_index=True)
            combined = combined.drop_duplicates(subset=['date']).sort_values('date').reset_index(drop=True)
            combined.to_csv(LOCAL_CSV_PATH, index=False)
            print(f"[SUCCESS] 成功追加 {len(new_rows)} 行最新数据！当前数据库总行数: {len(combined)}, 最新日期: {combined['date'].iloc[-1].strftime('%Y-%m-%d')}")
            return {"status": "updated", "new_rows": len(new_rows), "last_date": combined['date'].iloc[-1].strftime('%Y-%m-%d'), "rows": len(combined)}
        else:
            print("[+] 未发现更高交易日数据，数据库已保持最新。")
            return {"status": "up_to_date", "last_date": last_date.strftime('%Y-%m-%d'), "rows": len(df_local)}

    except Exception as e:
        print(f"[!] 增量同步异常: {e}")
        return {"status": "error", "error": str(e), "last_date": last_date.strftime('%Y-%m-%d')}


def compute_latest_signals(df_input=None):
    """
    毫秒级快速计算 SPY 与 QQQ 的今日最新状态与双轨制预警信号
    支持直接传入 DataFrame，或从本地路径/GitHub 远端读取
    """
    if df_input is not None and not df_input.empty:
        df = df_input.copy()
    elif os.path.exists(LOCAL_CSV_PATH):
        df = pd.read_csv(LOCAL_CSV_PATH)
    else:
        try:
            df = pd.read_csv(GITHUB_RAW_CSV_URL)
        except Exception as e:
            raise FileNotFoundError(f"本地与 GitHub 数据源皆不可用: {e}")

    df['date'] = pd.to_datetime(df['date']).dt.tz_localize(None).astype('datetime64[ns]')
    df = df.sort_values('date').reset_index(drop=True)

    results = {}

    for ticker in ['QQQ', 'SPY']:
        sub = df[['date', ticker, 'HYG', 'NFCI', 'BAA10Y', 'Real_Yield']].copy()
        
        # 基础指标
        sub['MA10'] = sub[ticker].rolling(10).mean()
        sub['MA20'] = sub[ticker].rolling(20).mean()
        sub['MA50'] = sub[ticker].rolling(50).mean()
        sub['MA200'] = sub[ticker].rolling(200).mean()
        sub['Dist_200MA'] = (sub[ticker] - sub['MA200']) / sub['MA200'] * 100.0

        sub['HYG_MA200'] = sub['HYG'].rolling(200).mean()
        sub['BAA_MA60'] = sub['BAA10Y'].rolling(60).mean()
        sub['BAA_Stress'] = sub['BAA10Y'] > sub['BAA_MA60']
        sub['RY_Surge'] = (sub['Real_Yield'] - sub['Real_Yield'].rolling(60).min()) > 0.40

        # NFCI Z-Score
        sub['NFCI_Roll_Mean'] = sub['NFCI'].rolling(252).mean()
        sub['NFCI_Roll_Std'] = sub['NFCI'].rolling(252).std()
        sub['NFCI_Z'] = (sub['NFCI'] - sub['NFCI_Roll_Mean']) / (sub['NFCI_Roll_Std'] + 1e-8)

        # 反身性 Gap
        sub['Price_Z'] = (sub[ticker] - sub[ticker].rolling(200).mean()) / (sub[ticker].rolling(200).std() + 1e-8)
        sub['Macro_Z'] = (sub['HYG'] - sub['HYG'].rolling(200).mean()) / (sub['HYG'].rolling(200).std() + 1e-8)
        roll_cov = sub['Price_Z'].rolling(252).cov(sub['Macro_Z'])
        roll_var = sub['Macro_Z'].rolling(252).var()
        sub['Dynamic_Beta'] = (roll_cov / (roll_var + 1e-8)).clip(lower=-2.0, upper=2.0)
        sub['Expected_Price_Z'] = sub['Macro_Z'] * sub['Dynamic_Beta']
        sub['Gap'] = sub['Price_Z'] - sub['Expected_Price_Z']

        # 自适应扩展分位数与记忆窗口
        sub['Gap_Max_45'] = sub['Gap'].rolling(45, min_periods=1).max()
        sub['PriceZ_Max_45'] = sub['Price_Z'].rolling(45, min_periods=1).max()
        sub['Gap_Upper'] = sub['Gap'].expanding(min_periods=20).quantile(0.85)

        # 宏观过热雷达综合评分 (0-100)
        z_score = np.clip((sub['Price_Z'] - 0.5) / 1.5 * 40.0, 0.0, 40.0)
        dist_score = np.clip((sub['Dist_200MA'] - 5.0) / 15.0 * 30.0, 0.0, 30.0)
        gap_score = np.clip((sub['Gap'] / sub['Gap_Upper']) * 15.0, 0.0, 30.0)
        sub['Overheat_Score'] = z_score + dist_score + gap_score
        sub['Overheat_Alert'] = sub['Overheat_Score'] >= 70.0

        # 右侧核心判定
        sub['Cond_Bubble'] = (
            (sub['Gap_Max_45'] > sub['Gap_Upper']) & 
            (sub['PriceZ_Max_45'] > 1.5) & 
            (sub['Dist_200MA'] > 5.0) & 
            (sub['NFCI'] > -0.50) & 
            sub['BAA_Stress'] & 
            (sub[ticker] < sub['MA20'])
        )

        sub['Macro_Crisis'] = (
            (sub['HYG'] < sub['HYG_MA200']) & 
            sub['RY_Surge'] & 
            (sub['NFCI_Z'] > 1.2) & 
            (sub['NFCI'] > -0.50)
        )
        sub['Cond_Bear'] = sub['Macro_Crisis'] & (sub[ticker] < sub['MA50']) & (sub[ticker] < sub['MA200'])
        sub['Sell_Signal'] = sub['Cond_Bubble'] | sub['Cond_Bear']

        # 抄底信号
        sub['Cond_Panic'] = (sub['Dist_200MA'].rolling(10, min_periods=1).min() < -10.0) & (sub[ticker] > sub['MA10'])

        # 提取最新一天的快照
        latest = sub.iloc[-1]
        cur_price = latest[ticker]
        ma20 = latest['MA20']
        ma50 = latest['MA50']
        ma200 = latest['MA200']
        dist_200 = latest['Dist_200MA']
        gap = latest['Gap']
        gap_upper = latest['Gap_Upper']
        overheat_score = latest['Overheat_Score']
        is_overheat = latest['Overheat_Alert']
        is_sell = latest['Sell_Signal']
        is_panic_buy = latest['Cond_Panic']

        # 判定决策状态与指引 (极值抄底使用绿色 🟢)
        if is_sell:
            status_tag = "🔴 避险清仓"
            action_desc = "触发右侧破位（泡沫破裂或宏观紧缩），建议 100% 空仓防守，回避回撤！"
            rec_pos = 0.0
        elif is_overheat:
            status_tag = "🟡 宏观过热黄色警戒"
            action_desc = "评分达到极值狂欢区 (Score >= 70)，严禁大额单笔追高！收紧止盈，激进者可左侧减仓 20%~30% 锁定利润。"
            rec_pos = 1.0  # 底仓继续持有，等待右侧破位或主动减仓
        elif is_panic_buy:
            status_tag = "🟢 极值抄底 (黄金坑)"
            action_desc = "市场恐慌绝望超跌出清，且右侧拐点确认，全力满仓接回，增殖股数！"
            rec_pos = 1.0
        else:
            status_tag = "🟢 健康常态持仓"
            action_desc = "宏观流动性健康，趋势向上，放心持有并继续按部就班执行常规定投。"
            rec_pos = 1.0

        results[ticker] = {
            'date': latest['date'].strftime('%Y-%m-%d'),
            'price': cur_price,
            'ma20': ma20,
            'ma50': ma50,
            'ma200': ma200,
            'dist_200': dist_200,
            'gap': gap,
            'gap_upper': gap_upper,
            'overheat_score': overheat_score,
            'is_overheat': is_overheat,
            'is_sell': is_sell,
            'is_panic_buy': is_panic_buy,
            'status_tag': status_tag,
            'action_desc': action_desc,
            'rec_pos': rec_pos,
            'hyg': latest['HYG'],
            'nfci': latest['NFCI'],
            'baa10y': latest['BAA10Y']
        }

    return results


def log_daily_record(signals):
    """持久化保存每日决策流水"""
    rows = []
    for ticker, data in signals.items():
        rows.append({
            'date': data['date'],
            'ticker': ticker,
            'price': round(data['price'], 2),
            'overheat_score': round(data['overheat_score'], 1),
            'status_tag': data['status_tag'],
            'rec_position': data['rec_pos'],
            'action_desc': data['action_desc'],
            'gap': round(data['gap'], 3),
            'dist_200ma_pct': round(data['dist_200'], 2),
            'nfci': round(data['nfci'], 3),
            'hyg': round(data['hyg'], 2),
            'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        })
    df_new = pd.DataFrame(rows)
    
    if os.path.exists(SIGNAL_LOG_PATH):
        df_old = pd.read_csv(SIGNAL_LOG_PATH)
        df_combined = pd.concat([df_old, df_new], ignore_index=True)
        # 去重保证每个交易日每个 ticker 仅一条记录
        df_combined = df_combined.drop_duplicates(subset=['date', 'ticker'], keep='last').reset_index(drop=True)
    else:
        df_combined = df_new

    df_combined.to_csv(SIGNAL_LOG_PATH, index=False)
    print(f"[OK] 每日信号已持久化归档至: {SIGNAL_LOG_PATH}")


def print_daily_dashboard(signals):
    """终端优雅打印每日决策看板"""
    print("\n" + "="*86)
    print(" 🦅 宏观反身性阿尔法模型 (双轨制雷达看板版) —— 每日收盘决策简报")
    print("="*86)
    print(f" 运行时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} (美东收盘核验)")
    print("-" * 86)
    
    for ticker, d in signals.items():
        print(f"\n【{ticker} 标的监控状态】 (数据基准日: {d['date']})")
        print(f"  • 当前收盘价: USD {d['price']:.2f}")
        print(f"  • 关键均线体系: MA20 = USD {d['ma20']:.2f} | MA50 = USD {d['ma50']:.2f} | MA200 = USD {d['ma200']:.2f} (偏离年线: {d['dist_200']:+.1f}%)")
        print(f"  • 宏观偏离度 Gap: {d['gap']:.2f} (自适应 85% 泡沫阈值: {d['gap_upper']:.2f})")
        print(f"  • 今日过热雷达评分: {d['overheat_score']:.1f} / 100 分  {'[高危警报 >= 70]' if d['overheat_score']>=70 else '[健康安全区间]'}")
        print(f"  • 宏观支撑底色: HYG = {d['hyg']:.2f}, NFCI = {d['nfci']:.3f}, BAA10Y = {d['baa10y']:.2f}%")
        print(f"  • 当前系统状态: {d['status_tag']} (建议仓位: {d['rec_pos']*100:.0f}%)")
        print(f"  • 实战操作建议: {d['action_desc']}")
        print("-" * 86)
    print("="*86 + "\n")


def main():
    parser = argparse.ArgumentParser(description="宏观反身性阿尔法模型每日增量监控脚本")
    parser.add_argument("--check-only", action="store_true", help="仅离线计算当前本地数据信号，不触发网络拉取")
    parser.add_argument("--force-sync", action="store_true", help="强制触发网络更新")
    args = parser.parse_args()

    print("=== 启动宏观反身性模型每日收盘监控程序 ===")
    
    if not args.check_only:
        sync_latest_market_data(force=args.force_sync)
    else:
        print("[*] 以 --check-only 模式运行：100% 离线计算最新本地信号...")

    signals = compute_latest_signals()
    print_daily_dashboard(signals)
    log_daily_record(signals)


if __name__ == "__main__":
    main()
