# -*- coding: utf-8 -*-
"""
========================================================================================
个股全景投研底稿一键总控引擎 (Generate Stock Dossier)
文件名称：generate_stock_dossier.py
核心功能：
1. 一键总控串联：数据采集 (stock_data_harvester.py) -> 定量精算与排雷 (stock_quant_analyzer.py)
2. 严格践行“本地优先 (Local-First)”：若 24 小时内本地已存在有效底稿，秒级返回，杜绝高频网络滥用
3. 生成供 Gemini 深度推理阅读的 {TICKER}_quant_dossier.json 与 {TICKER}_gemini_context.md
========================================================================================
"""

import os
import sys
import time
import argparse

# 兼容控制台 UTF-8 输出
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

from stock_data_harvester import StockDataHarvester
from stock_quant_analyzer import StockQuantAnalyzer

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOSSIERS_DIR = os.path.join(BASE_DIR, "dossiers")


def generate_dossier(ticker: str, force: bool = False, cache_ttl_hours: float = 24.0) -> dict:
    """
    一键生成或更新指定个股的全景量化投研底稿
    """
    ticker = ticker.upper().strip()
    target_json = os.path.join(DOSSIERS_DIR, ticker, f"{ticker}_quant_dossier.json")
    target_md = os.path.join(DOSSIERS_DIR, ticker, f"{ticker}_gemini_context.md")

    # 本地优先缓存命中检验
    if not force and os.path.exists(target_json) and os.path.exists(target_md):
        mtime = os.path.getmtime(target_json)
        age_hours = (time.time() - mtime) / 3600.0
        if age_hours < cache_ttl_hours:
            print(f"[*] 发现 {ticker} 本地有效量化底稿 (生成于 {age_hours:.1f} 小时前，在 {cache_ttl_hours}h 缓存窗口内)")
            print(f"    - JSON 底稿: {target_json}")
            print(f"    - Gemini 专用上下文: {target_md}")
            return {
                "status": "cached",
                "ticker": ticker,
                "json_path": target_json,
                "md_path": target_md,
                "age_hours": age_hours
            }

    print(f"==================================================================")
    print(f"🚀 正在为标的 {ticker} 生成最新全景量化投研底稿 (强制刷新: {force})...")
    print(f"==================================================================")

    # 1. 数据采集阶段
    harvester = StockDataHarvester(ticker=ticker)
    harvest_summary = harvester.harvest_all(force=force)

    # 2. 定量建模与排雷分析阶段
    analyzer = StockQuantAnalyzer(ticker=ticker)
    analysis_data = analyzer.run_full_analysis()

    return {
        "status": "success",
        "ticker": ticker,
        "json_path": target_json,
        "md_path": target_md,
        "harvest_summary": harvest_summary,
        "analysis_meta": analysis_data.get("meta", {})
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="一键生成个股量化投研底稿与 Gemini 上下文")
    parser.add_argument("--ticker", type=str, default="NVDA", help="股票代码 (如 NVDA, AAPL)")
    parser.add_argument("--force", action="store_true", help="强制忽略本地缓存全量重抓")
    args = parser.parse_args()

    res = generate_dossier(ticker=args.ticker, force=args.force)
    print(f"🎉 任务完成! 状态: {res.get('status')}")
