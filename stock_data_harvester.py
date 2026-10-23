# -*- coding: utf-8 -*-
"""
========================================================================================
个股多源投研数据采集器 (Stock Data Harvester)
文件名称：stock_data_harvester.py
核心功能：
1. SEC EDGAR 官方一手监管申报 (XBRL 财务事实、10-K/10-Q 风险与 MD&A、8-K 重大事件、Form 4 内部人)
2. 财报电话会议纪要与管理层前瞻指引 (Earnings Call Transcripts & Forward Guidance)
3. 衍生品期权链微观情绪 (PCR、Max Pain、持仓分布)、空头持仓 (Short % of Float)
4. 本地优先行情序列、宏观信用重力底色与近期重要催化剂新闻
5. 结果自动持久化至 dossiers/{TICKER}/raw/，严格遵循本地优先与故障降级原则
========================================================================================
"""

import os
import sys
import time
import json
import re
import datetime
import urllib.request
import urllib.parse
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional, Tuple, List

# 兼容控制台 UTF-8 输出
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOSSIERS_DIR = os.path.join(BASE_DIR, "dossiers")
SEC_TICKERS_CACHE = os.path.join(DOSSIERS_DIR, "sec_company_tickers.json")

# SEC EDGAR 官方合规 User-Agent
SEC_USER_AGENT = "MacroEquityResearchTerminal/1.0 (academic-research@terminal.local)"


class StockDataHarvester:
    """个股多源全景数据采集引擎"""

    def __init__(self, ticker: str, cache_dir: Optional[str] = None):
        self.ticker = ticker.upper().strip()
        self.cache_dir = cache_dir or os.path.join(DOSSIERS_DIR, self.ticker, "raw")
        self.transcripts_dir = os.path.join(DOSSIERS_DIR, self.ticker, "transcripts")
        os.makedirs(self.cache_dir, exist_ok=True)
        os.makedirs(self.transcripts_dir, exist_ok=True)
        self.cik = self._resolve_cik()

    def _http_get_json(self, url: str, headers: Optional[Dict[str, str]] = None, timeout: int = 12) -> Optional[Dict[str, Any]]:
        """具备重试与异常保护的 HTTP GET 请求"""
        req_headers = {"User-Agent": SEC_USER_AGENT}
        if headers:
            req_headers.update(headers)
        try:
            req = urllib.request.Request(url, headers=req_headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if resp.status == 200:
                    data = resp.read().decode("utf-8")
                    return json.loads(data)
        except Exception as e:
            print(f"[!] HTTP GET 失败 ({url}): {e}")
        return None

    def _http_get_text(self, url: str, headers: Optional[Dict[str, str]] = None, timeout: int = 15) -> Optional[str]:
        """具备重试与异常保护的 HTTP GET 文本请求"""
        req_headers = {"User-Agent": SEC_USER_AGENT}
        if headers:
            req_headers.update(headers)
        try:
            req = urllib.request.Request(url, headers=req_headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                if resp.status == 200:
                    return resp.read().decode("utf-8", errors="replace")
        except Exception as e:
            print(f"[!] HTTP GET 文本失败 ({url}): {e}")
        return None

    def _resolve_cik(self) -> Optional[str]:
        """将股票代码映射为 SEC 官方 10 位补零 CIK 编码"""
        # 1. 优先读取本地缓存
        tickers_map = {}
        if os.path.exists(SEC_TICKERS_CACHE):
            try:
                with open(SEC_TICKERS_CACHE, "r", encoding="utf-8") as f:
                    tickers_map = json.load(f)
            except Exception:
                tickers_map = {}

        if not tickers_map:
            print("[*] 正在从 SEC EDGAR 拉取全球公司 Ticker <-> CIK 映射表...")
            url = "https://www.sec.gov/files/company_tickers.json"
            data = self._http_get_json(url)
            if data:
                tickers_map = data
                try:
                    with open(SEC_TICKERS_CACHE, "w", encoding="utf-8") as f:
                        json.dump(tickers_map, f, ensure_ascii=False)
                except Exception as e:
                    print(f"[!] 写入 CIK 缓存失败: {e}")

        for _, item in tickers_map.items():
            if item.get("ticker", "").upper() == self.ticker:
                cik_int = item.get("cik_str")
                return str(cik_int).zfill(10)

        print(f"[!] 未能在 SEC 官方映射表中定位 {self.ticker} 的 CIK。")
        return None

    # =========================================================================
    # 支柱 1：SEC EDGAR 官方 XBRL 财务事实与核心章节提取
    # =========================================================================
    def harvest_sec_xbrl_facts(self) -> Dict[str, Any]:
        """获取并解析 SEC 官方 XBRL 标准化财务序列 (GAAP)"""
        output_path = os.path.join(self.cache_dir, "sec_facts.json")
        facts_summary_path = os.path.join(self.cache_dir, "sec_financial_history.csv")

        data = None
        if os.path.exists(output_path) and (time.time() - os.path.getmtime(output_path) < 86400 * 3):
            try:
                with open(output_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                data = None

        if not data and self.cik:
            url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{self.cik}.json"
            print(f"[*] 正在从 SEC EDGAR 获取 {self.ticker} (CIK: {self.cik}) 官方 XBRL 财务历史...")
            data = self._http_get_json(url)
            if data:
                with open(output_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False)

        if not data:
            return {"status": "error", "message": "无法从 SEC 获取 XBRL 财务事实"}

        # 解析 US-GAAP 核心科目
        gaap = data.get("facts", {}).get("us-gaap", {})
        
        # 目标提取科目映射表 (概念名优先级列表)
        metric_candidates = {
            "Revenues": ["RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues", "SalesRevenueNet", "TotalRevenuesAndOtherIncome"],
            "GrossProfit": ["GrossProfit"],
            "RD_Expense": ["ResearchAndDevelopmentExpense", "ResearchAndDevelopmentExpenseExcludingAcquiredInProcessCost"],
            "OperatingIncome": ["OperatingIncomeLoss"],
            "NetIncome": ["NetIncomeLoss"],
            "DilutedEPS": ["EarningsPerShareDiluted", "DilutedEarningsPerShare"],
            "OCF": ["NetCashProvidedByUsedInOperatingActivities"],
            "CapEx": ["PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsToAcquireProductiveAssets"],
            "SBC": ["ShareBasedCompensation", "AllocatedShareBasedCompensationExpense"],
            "InterestExpense": ["InterestExpense", "InterestExpenseDebt", "InterestExpenseNonoperating", "InterestAndDebtExpense"],
            "IncomeTaxExpense": ["IncomeTaxExpenseBenefit"],
            "DepreciationAmortization": ["DepreciationDepletionAndAmortization", "DepreciationAndAmortization"],
            "AccountsReceivable": ["AccountsReceivableNetCurrent", "ReceivablesNetCurrent"],
            "Inventory": ["InventoryNet"],
            "ContractLiabilities": ["ContractWithCustomerLiabilityCurrent", "DeferredRevenueCurrent"],
            "TotalDebt": ["LongTermDebtNoncurrent", "LongTermDebtAndCapitalLeaseObligations"],
            "ShortTermDebt": ["ShortTermBorrowings", "DebtCurrent", "LongTermDebtCurrent"],
            "CashEquivalents": ["CashAndCashEquivalentsAtCarryingValue", "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"],
            "StockholdersEquity": ["StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"],
            "SharesOutstanding": ["CommonStockSharesOutstanding", "WeightedAverageNumberOfDilutedSharesOutstanding"]
        }

        point_in_time_metrics = {"AccountsReceivable", "Inventory", "ContractLiabilities", "TotalDebt", "ShortTermDebt", "CashEquivalents", "StockholdersEquity", "SharesOutstanding"}

        records_by_quarter: Dict[str, Dict[str, Any]] = {}

        for metric_name, tag_list in metric_candidates.items():
            for tag in tag_list:
                if tag in gaap:
                    units_dict = gaap[tag].get("units", {})
                    # 优先取 USD 或 shares
                    unit_key = "USD" if "USD" in units_dict else ("shares" if "shares" in units_dict else (list(units_dict.keys())[0] if units_dict else None))
                    if not unit_key:
                        continue
                    rows = units_dict.get(unit_key, [])
                    for r in rows:
                        # 仅保留季度 10-Q 与年度 10-K 正规申报
                        form = r.get("form", "")
                        if form not in ["10-Q", "10-K", "10-Q/A", "10-K/A"]:
                            continue
                        fp = r.get("fp", "")
                        fy = r.get("fy")
                        val = r.get("val")
                        end_date = r.get("end", "")
                        start_date = r.get("start", "")
                        if not end_date or val is None or not fy:
                            continue
                        
                        period_key = f"{fy}-{fp}" if (fy and fp) else end_date[:7]
                        if period_key not in records_by_quarter:
                            records_by_quarter[period_key] = {"period": period_key, "date": end_date, "form": form, "fy": fy, "fp": fp}
                        
                        days = (pd.to_datetime(end_date) - pd.to_datetime(start_date)).days if start_date else 0
                        
                        if metric_name in point_in_time_metrics:
                            if metric_name not in records_by_quarter[period_key]:
                                records_by_quarter[period_key][metric_name] = val
                        else:
                            if fp in ["Q1", "Q2", "Q3"] or form == "10-Q":
                                if 65 <= days <= 115:
                                    if metric_name not in records_by_quarter[period_key]:
                                        records_by_quarter[period_key][metric_name] = val
                                elif days > 115:
                                    if f"{metric_name}_YTD" not in records_by_quarter[period_key]:
                                        records_by_quarter[period_key][f"{metric_name}_YTD"] = val
                            elif fp == "FY" or form == "10-K":
                                if days >= 330:
                                    if f"{metric_name}_FY" not in records_by_quarter[period_key]:
                                        records_by_quarter[period_key][f"{metric_name}_FY"] = val
                                    if metric_name not in records_by_quarter[period_key]:
                                        records_by_quarter[period_key][metric_name] = val
                    # 不执行 break，允许后续候选标签回填历史或缺失期间 (例如 ASC 606 转换前后的 Revenues)

        df_facts = pd.DataFrame(list(records_by_quarter.values()))
        if not df_facts.empty:
            df_facts["date"] = pd.to_datetime(df_facts["date"])
            df_facts = df_facts.sort_values("date").reset_index(drop=True)

            # 跨期消歧：利用 YTD 累计值做差分还原单季度数据 (Q2 = YTD_Q2 - YTD_Q1, Q3 = YTD_Q3 - YTD_Q2)
            flow_metrics = ["Revenues", "GrossProfit", "RD_Expense", "OperatingIncome", "NetIncome", "OCF", "CapEx", "SBC", "InterestExpense", "IncomeTaxExpense", "DepreciationAmortization"]
            for m in flow_metrics:
                ytd_col = f"{m}_YTD"
                if ytd_col in df_facts.columns:
                    for i in range(len(df_facts)):
                        if m not in df_facts.columns or pd.isna(df_facts.loc[i, m]):
                            fp = df_facts.loc[i, "fp"]
                            fy = df_facts.loc[i, "fy"]
                            if fp == "Q1" and pd.notna(df_facts.loc[i, ytd_col]):
                                df_facts.loc[i, m] = df_facts.loc[i, ytd_col]
                            elif fp in ["Q2", "Q3"] and pd.notna(df_facts.loc[i, ytd_col]):
                                prev_fp = "Q1" if fp == "Q2" else "Q2"
                                prev_matches = df_facts[(df_facts["fy"] == fy) & (df_facts["fp"] == prev_fp)]
                                if not prev_matches.empty and ytd_col in prev_matches.columns and pd.notna(prev_matches.iloc[-1][ytd_col]):
                                    df_facts.loc[i, m] = df_facts.loc[i, ytd_col] - prev_matches.iloc[-1][ytd_col]
                                elif not prev_matches.empty and m in prev_matches.columns and pd.notna(prev_matches.iloc[-1][m]):
                                    df_facts.loc[i, m] = df_facts.loc[i, ytd_col] - prev_matches.iloc[-1][m]

            # 计算单季衍生指标: Standard FCF 与 True FCF
            if "OCF" in df_facts.columns:
                capex = df_facts["CapEx"] if "CapEx" in df_facts.columns else 0.0
                sbc = df_facts["SBC"] if "SBC" in df_facts.columns else 0.0
                df_facts["FCF_Standard"] = df_facts["OCF"] - capex.fillna(0.0)
                df_facts["True_FCF_Net_SBC"] = df_facts["FCF_Standard"] - sbc.fillna(0.0)

            # 滚动计算 TTM (过去 4 季累加) 指标
            # 过滤只保留季报行以做滚动计算
            quarter_mask = df_facts["fp"].isin(["Q1", "Q2", "Q3", "Q4"])
            if quarter_mask.sum() >= 4:
                for col in ["Revenues", "NetIncome", "OperatingIncome", "OCF", "CapEx", "SBC", "FCF_Standard", "True_FCF_Net_SBC", "InterestExpense"]:
                    if col in df_facts.columns:
                        # 仅对单季度行计算 rolling 4 sum，再 reindex 回总表
                        q_series = df_facts.loc[quarter_mask, col]
                        df_facts[f"TTM_{col}"] = q_series.rolling(4, min_periods=4).sum()
                        # 若当前行为 FY 且 TTM 为空，直接用 FY 对应年度值填补
                        if f"{col}_FY" in df_facts.columns:
                            df_facts[f"TTM_{col}"] = df_facts[f"TTM_{col}"].fillna(df_facts[f"{col}_FY"])
            else:
                for col in ["Revenues", "NetIncome", "OperatingIncome", "OCF", "CapEx", "SBC", "FCF_Standard", "True_FCF_Net_SBC"]:
                    if col in df_facts.columns:
                        df_facts[f"TTM_{col}"] = df_facts[col]

            df_facts.to_csv(facts_summary_path, index=False)
            print(f"[+] 成功提炼 {self.ticker} SEC XBRL 历史财务事实 ({len(df_facts)} 期) 至 {facts_summary_path}")

        return {
            "status": "success",
            "cik": self.cik,
            "entity_name": data.get("entityName", self.ticker),
            "num_periods": len(df_facts),
            "latest_period": df_facts["period"].iloc[-1] if not df_facts.empty else "N/A",
            "latest_date": str(df_facts["date"].iloc[-1].date()) if not df_facts.empty else "N/A",
            "df_facts": df_facts
        }

    def harvest_sec_filings_metadata(self) -> Dict[str, Any]:
        """获取 SEC EDGAR 申报文件列表 (10-K, 10-Q, 8-K, Form 4)"""
        output_path = os.path.join(self.cache_dir, "sec_submissions.json")
        data = None
        if os.path.exists(output_path) and (time.time() - os.path.getmtime(output_path) < 86400 * 2):
            try:
                with open(output_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                data = None

        if not data and self.cik:
            url = f"https://data.sec.gov/submissions/CIK{self.cik}.json"
            print(f"[*] 正在从 SEC EDGAR 拉取 {self.ticker} 最新申报文档清单...")
            data = self._http_get_json(url)
            if data:
                with open(output_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False)

        if not data:
            return {"status": "error", "message": "无法获取 SEC 申报列表"}

        recent = data.get("filings", {}).get("recent", {})
        forms = recent.get("form", [])
        filing_dates = recent.get("filingDate", [])
        accessions = recent.get("accessionNumber", [])
        primary_docs = recent.get("primaryDocument", [])
        items_list = recent.get("items", [])
        descriptions = recent.get("primaryDocDescription", [])

        extracted_filings = {
            "latest_10k": None,
            "latest_10q": None,
            "recent_8k": [],
            "recent_form4_count": 0
        }

        for i in range(min(100, len(forms))):
            f = forms[i]
            acc = accessions[i]
            pdoc = primary_docs[i]
            fdate = filing_dates[i]
            items = items_list[i] if i < len(items_list) else []
            desc = descriptions[i] if i < len(descriptions) else ""

            # 构造官方档案直链 URL
            # 规则: https://www.sec.gov/Archives/edgar/data/{cik}/{acc_no_hyphen}/{pdoc}
            cik_int = str(int(self.cik))
            acc_clean = acc.replace("-", "")
            doc_url = f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{acc_clean}/{pdoc}"

            info = {
                "form": f,
                "date": fdate,
                "accession": acc,
                "primary_doc": pdoc,
                "doc_url": doc_url,
                "items": items,
                "desc": desc
            }

            if f == "10-K" and not extracted_filings["latest_10k"]:
                extracted_filings["latest_10k"] = info
            elif f == "10-Q" and not extracted_filings["latest_10q"]:
                extracted_filings["latest_10q"] = info
            elif f == "8-K" and len(extracted_filings["recent_8k"]) < 8:
                extracted_filings["recent_8k"].append(info)
            elif f in ["4", "4/A"]:
                extracted_filings["recent_form4_count"] += 1

        summary_path = os.path.join(self.cache_dir, "sec_filings_summary.json")
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(extracted_filings, f, ensure_ascii=False, indent=2)

        print(f"[+] 提取完成: 最新 10-K ({extracted_filings['latest_10k'].get('date') if extracted_filings['latest_10k'] else '无'}), "
              f"最新 10-Q ({extracted_filings['latest_10q'].get('date') if extracted_filings['latest_10q'] else '无'}), "
              f"近期 8-K 申报 ({len(extracted_filings['recent_8k'])} 项)")
        return extracted_filings

    # =========================================================================
    # 支柱 2：财报电话会议纪要 (Transcripts) 与管理层前瞻业绩指引
    # =========================================================================
    def harvest_earnings_guidance_and_transcripts(self, filings_meta: Dict[str, Any]) -> Dict[str, Any]:
        """抓取并结构化提取业绩新闻稿与电话会议管理层前瞻指引"""
        output_path = os.path.join(self.cache_dir, "earnings_guidance.json")

        guidance_data = {
            "status": "success",
            "ticker": self.ticker,
            "has_local_transcript": False,
            "transcript_excerpts": [],
            "official_8k_guidance_text": "",
            "cfo_commentary_summary": ""
        }

        # 1. 优先检查本地自定义投喂目录 dossiers/{TICKER}/transcripts/
        local_files = [f for f in os.listdir(self.transcripts_dir) if f.endswith((".txt", ".md", ".json"))]
        if local_files:
            print(f"[*] 发现本地专属电话会议纪要文件: {local_files}")
            guidance_data["has_local_transcript"] = True
            for lf in local_files[:3]:
                fpath = os.path.join(self.transcripts_dir, lf)
                try:
                    with open(fpath, "r", encoding="utf-8", errors="replace") as tf:
                        guidance_data["transcript_excerpts"].append({
                            "source_file": lf,
                            "content": tf.read()[:8000] # 保留前 8000 字高密度精选段落
                        })
                except Exception as e:
                    print(f"[!] 读取本地纪要 {lf} 失败: {e}")

        # 2. 从官方 8-K (Item 2.02: Results of Operations and Financial Condition) 抓取官方 Earnings Release
        recent_8k = filings_meta.get("recent_8k", [])
        earnings_8k = None
        for item in recent_8k:
            items_str = str(item.get("items", ""))
            if "2.02" in items_str:
                earnings_8k = item
                break

        if earnings_8k:
            print(f"[*] 正在从官方 8-K 业绩公告提取核心指引与管理层陈述 ({earnings_8k.get('date')})...")
            doc_url = earnings_8k.get("doc_url", "")
            raw_html = self._http_get_text(doc_url)
            if raw_html:
                # 简单剥离 HTML 标签，提取干净文本
                clean_text = re.sub(r'<[^>]+>', ' ', raw_html)
                clean_text = re.sub(r'\s+', ' ', clean_text).strip()
                
                # 正则寻找包含 Outlook / Guidance / Expectations 的核心段落
                guidance_match = re.search(r'(?:Outlook|Financial Outlook|Business Outlook|Guidance)[\s\S]{100,2500}(?=(?:Non-GAAP|Conference Call|About |Investor Relations))', clean_text, re.IGNORECASE)
                if guidance_match:
                    guidance_data["official_8k_guidance_text"] = guidance_match.group(0).strip()
                else:
                    guidance_data["official_8k_guidance_text"] = clean_text[:2000]

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(guidance_data, f, ensure_ascii=False, indent=2)

        print(f"[+] 电话会纪要与业绩指引结构化提取完成，已保存至 {output_path}")
        return guidance_data

    # =========================================================================
    # 支柱 3~7：行情、估值、期权衍生品、空头拥挤度与宏观信用背景
    # =========================================================================
    def harvest_market_options_and_macro(self) -> Dict[str, Any]:
        """聚合行情、估值倍数、期权持仓情绪与宏观流动性数据"""
        snapshot_path = os.path.join(self.cache_dir, "market_snapshot.json")
        price_csv_path = os.path.join(self.cache_dir, "prices.csv")

        # 1. 行情与估值画像
        from core_engine.stock_data_service import get_stock_price_data, get_stock_profile
        from data_service import get_stock_options_sentiment

        print(f"[*] 正在拉取 {self.ticker} 行情序列与期权博弈持仓结构...")
        df_price, price_meta = get_stock_price_data(self.ticker, period="5y")
        if df_price is not None and not df_price.empty:
            df_price.to_csv(price_csv_path)

        profile_res = get_stock_profile(self.ticker)
        profile_data = profile_res.get("data", {})

        # 2. 期权链微观博弈与最大痛点
        options_sentiment = {}
        try:
            res_opt = get_stock_options_sentiment(self.ticker)
            if res_opt and isinstance(res_opt, dict):
                options_sentiment = res_opt
                if "df_strikes" in options_sentiment and isinstance(options_sentiment["df_strikes"], pd.DataFrame):
                    # 剥离 DataFrame 以便序列化为 JSON
                    options_sentiment["strikes_summary"] = options_sentiment["df_strikes"].head(10).to_dict(orient="records")
                    del options_sentiment["df_strikes"]
        except Exception as e:
            print(f"[!] 期权数据提取警告: {e}")
            options_sentiment = {}
        if not options_sentiment:
            options_sentiment = {}

        # 3. 本地宏观真理底库提取 (HYG, BAA10Y, NFCI, Real_Yield, 10Y/3M 国债利率)
        macro_csv = os.path.join(BASE_DIR, "market_data_local.csv")
        treasury_csv = os.path.join(BASE_DIR, "daily-treasury-rates.csv")
        macro_summary = {
            "treasury_10y_yield": 4.25, # 默认安全底线
            "treasury_3m_yield": 4.50,
            "treasury_2y_yield": 4.20
        }
        if os.path.exists(treasury_csv):
            try:
                df_tb = pd.read_csv(treasury_csv)
                if not df_tb.empty and "10 Yr" in df_tb.columns:
                    last_tb = df_tb.iloc[-1]
                    macro_summary["treasury_10y_yield"] = float(last_tb.get("10 Yr", 4.25))
                    macro_summary["treasury_3m_yield"] = float(last_tb.get("3 Mo", 4.50))
                    macro_summary["treasury_2y_yield"] = float(last_tb.get("2 Yr", 4.20))
                    macro_summary["treasury_date"] = str(last_tb.get("Date", ""))
            except Exception as e:
                print(f"[!] 读取本地国债收益率数据失败: {e}")

        if os.path.exists(macro_csv):
            try:
                df_macro = pd.read_csv(macro_csv)
                if not df_macro.empty and "date" in df_macro.columns:
                    last_row = df_macro.iloc[-1]
                    macro_summary.update({
                        "date": str(last_row.get("date")),
                        "HYG_close": float(last_row.get("HYG", 0.0)),
                        "BAA10Y_spread": float(last_row.get("BAA10Y", 0.0)),
                        "NFCI": float(last_row.get("NFCI", 0.0)),
                        "Real_Yield": float(last_row.get("Real_Yield", 0.0))
                    })
            except Exception as e:
                print(f"[!] 读取本地宏观数据失败: {e}")

        # 4. 组装市场快照
        snapshot = {
            "status": "success",
            "ticker": self.ticker,
            "timestamp": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "price_meta": price_meta,
            "latest_close": float(df_price["Close"].iloc[-1]) if (df_price is not None and not df_price.empty) else np.nan,
            "profile": {
                "shortName": profile_data.get("shortName", self.ticker),
                "sector": profile_data.get("sector", "N/A"),
                "industry": profile_data.get("industry", "N/A"),
                "marketCap": profile_data.get("marketCap", np.nan),
                "trailingPE": profile_data.get("trailingPE", np.nan),
                "forwardPE": profile_data.get("forwardPE", np.nan),
                "priceToSales": profile_data.get("priceToSalesTrailing12Months", np.nan),
                "freeCashflow": profile_data.get("freeCashflow", np.nan),
                "sharesOutstanding": profile_data.get("sharesOutstanding", np.nan),
                "beta": profile_data.get("beta", np.nan),
                "bookValue": profile_data.get("bookValue", np.nan),
                "priceToBook": profile_data.get("priceToBook", np.nan),
                "enterpriseToEbitda": profile_data.get("enterpriseToEbitda", np.nan),
                "enterpriseToRevenue": profile_data.get("enterpriseToRevenue", np.nan),
                "fiftyTwoWeekHigh": profile_data.get("fiftyTwoWeekHigh", np.nan),
                "fiftyTwoWeekLow": profile_data.get("fiftyTwoWeekLow", np.nan),
                "dividendYield": profile_data.get("dividendYield", 0.0),
                "heldPercentInsiders": profile_data.get("heldPercentInsiders", np.nan),
                "shortPercentOfFloat": profile_data.get("shortPercentOfFloat", np.nan),
                "shortRatio": profile_data.get("shortRatio", np.nan), # 空头回补天数
                "targetMeanPrice": profile_data.get("targetMeanPrice", np.nan),
                "targetHighPrice": profile_data.get("targetHighPrice", np.nan),
                "targetLowPrice": profile_data.get("targetLowPrice", np.nan),
                "recommendationKey": profile_data.get("recommendationKey", "N/A")
            },
            "options_sentiment": {
                "pcr_oi": options_sentiment.get("pcr_oi", np.nan),
                "pcr_vol": options_sentiment.get("pcr_vol", np.nan),
                "max_pain_price": options_sentiment.get("max_pain_price", np.nan),
                "call_oi_total": options_sentiment.get("call_oi_total", 0),
                "put_oi_total": options_sentiment.get("put_oi_total", 0)
            },
            "macro_backdrop": macro_summary
        }

        with open(snapshot_path, "w", encoding="utf-8") as f:
            json.dump(snapshot, f, ensure_ascii=False, indent=2)

        print(f"[+] 市场、期权与宏观快照提取完成，已保存至 {snapshot_path}")
        return snapshot

    # =========================================================================
    # 总控流程：一键全量采集
    # =========================================================================
    def harvest_all(self, force: bool = False) -> Dict[str, Any]:
        """全流程一键采集"""
        print(f"==================================================================")
        print(f"🚀 开始采集标的 {self.ticker} 多源全景投研数据...")
        print(f"==================================================================")
        
        # 1. SEC XBRL 财务历史
        sec_facts = self.harvest_sec_xbrl_facts()
        
        # 2. SEC 申报列表
        filings_meta = self.harvest_sec_filings_metadata()
        
        # 3. 电话会纪要与指引
        guidance = self.harvest_earnings_guidance_and_transcripts(filings_meta)
        
        # 4. 行情、估值、期权与宏观
        market = self.harvest_market_options_and_macro()
        
        summary = {
            "status": "success",
            "ticker": self.ticker,
            "cik": self.cik,
            "sec_facts_periods": sec_facts.get("num_periods", 0),
            "latest_10k_date": filings_meta.get("latest_10k", {}).get("date") if filings_meta.get("latest_10k") else "N/A",
            "latest_10q_date": filings_meta.get("latest_10q", {}).get("date") if filings_meta.get("latest_10q") else "N/A",
            "has_guidance": bool(guidance.get("official_8k_guidance_text")),
            "latest_price": market.get("latest_close", np.nan),
            "output_dir": self.cache_dir
        }
        
        print(f"==================================================================")
        print(f"✅ {self.ticker} 数据全量采集完成！")
        print(f"   - SEC 官方历史财报: {summary['sec_facts_periods']} 期")
        print(f"   - 最新 10-Q 日期: {summary['latest_10q_date']} | 最新 10-K: {summary['latest_10k_date']}")
        print(f"   - 缓存目录: {self.cache_dir}")
        print(f"==================================================================")
        return summary


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="个股多源投研数据采集器")
    parser.add_argument("--ticker", type=str, default="NVDA", help="股票代码 (如 NVDA, AAPL)")
    parser.add_argument("--force", action="store_true", help="强制忽略本地缓存全量重抓")
    args = parser.parse_args()

    harvester = StockDataHarvester(ticker=args.ticker)
    harvester.harvest_all(force=args.force)
