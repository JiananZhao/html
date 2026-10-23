# -*- coding: utf-8 -*-
"""
========================================================================================
个股机构级基本面排雷、多维估值与情绪定量主控引擎 (Stock Quantitative Analyzer)
文件名称：stock_quant_analyzer.py
核心功能（全面融合 GeminiSkills 13 大投研精髓）：
1. 基本面质量与法务排雷：双口径 TTM 自由现金流(含/扣SBC)、盈利含金量、应收/存货异动、
   Piotroski F-Score、ROIC vs WACC 经济增加值、真实净股份注销率、偿债杠杆与现金跑道(Cash Runway)
2. 估值前置核验与反锚定双口径 DCF：
   - 动态 WACC 锚定本地 10Y 美债无风险利率 Rf 与个股 Beta
   - 公司类型自适应分流 (稳健白马 / 高 SBC 成长 / 困境反转重资产周期)
   - 反现价锚定三阶段正向 DCF 模型 (Standard FCF vs Post-SBC Adj. FCF) 与 3x3 敏感性矩阵
   - 5 年历史 PE/PS Band 分位数与乘数重构压力测试 (Multiple Compression Floor)
3. 相对强弱 Alpha 与微观动量：均线偏离、12-1M 动量、相对 SPY 1M/3M/6M 超额收益、RSI、14D ATR%
4. 索罗斯反身性相空间与期权微观博弈：四象限坐标 (q1, q1_dot, v_dot)、反身性偏离度 Gap、期权 PCR/Max Pain
5. 历史同构状态真实胜率回溯：检索历史相似状态，统计未来 3M/6M/1Y 真实胜率与回撤
6. 五维 100 分制量化评分卡与反锚定左右侧双轨制建仓/止损价格网格
========================================================================================
"""

import os
import sys
import json
import datetime
import pandas as pd
import numpy as np
from typing import Dict, Any, Optional, List, Tuple

# 兼容控制台 UTF-8 输出
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DOSSIERS_DIR = os.path.join(BASE_DIR, "dossiers")


class StockQuantAnalyzer:
    """个股机构级量化分析、估值建模与排雷核心总控引擎"""

    def __init__(self, ticker: str):
        self.ticker = ticker.upper().strip()
        self.raw_dir = os.path.join(DOSSIERS_DIR, self.ticker, "raw")
        self.output_dir = os.path.join(DOSSIERS_DIR, self.ticker)
        os.makedirs(self.output_dir, exist_ok=True)

        # 载入前置数据
        self.df_sec_facts = self._load_sec_facts()
        self.market_snapshot = self._load_market_snapshot()
        self.df_price = self._load_price_data()
        self.earnings_guidance = self._load_earnings_guidance()

    @staticmethod
    def _safe_float(val: Any, fallback: float = 0.0) -> float:
        """安全将可能为 NaN / None / 缺失的数据转换为 float，严格杜绝布尔真值陷阱"""
        if val is None or pd.isna(val):
            return fallback
        try:
            return float(val)
        except (ValueError, TypeError):
            return fallback

    def _get_latest_price(self) -> float:
        """获取最新收盘价，优先从快照获取，若受限则从本地 price 历史序列兜底"""
        p = self._safe_float(self.market_snapshot.get("latest_close"), np.nan)
        if pd.isna(p) or p <= 0:
            if not self.df_price.empty and "close" in self.df_price.columns:
                valid_close = self.df_price["close"].dropna()
                if not valid_close.empty:
                    p = self._safe_float(valid_close.iloc[-1], np.nan)
        return p

    def _load_sec_facts(self) -> pd.DataFrame:
        path = os.path.join(self.raw_dir, "sec_financial_history.csv")
        if os.path.exists(path):
            try:
                df = pd.read_csv(path)
                if "date" in df.columns:
                    df["date"] = pd.to_datetime(df["date"])
                    df = df.sort_values("date").reset_index(drop=True)
                    # 过滤只保留有效的 10-Q 和 10-K 正规财务报表期，剔除非财务申报 (如 DEF 14A, 8-K 等)
                    if "form" in df.columns and "Revenues" in df.columns:
                        valid_mask = df["form"].isin(["10-Q", "10-K", "10-Q/A", "10-K/A"]) & df["Revenues"].notna()
                        if valid_mask.any():
                            df = df[valid_mask].copy().reset_index(drop=True)
                    return df
            except Exception as e:
                print(f"[!] 载入 SEC 财务历史失败: {e}")
        return pd.DataFrame()

    def _load_market_snapshot(self) -> Dict[str, Any]:
        path = os.path.join(self.raw_dir, "market_snapshot.json")
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"[!] 载入市场快照失败: {e}")
        return {}

    def _load_price_data(self) -> pd.DataFrame:
        path = os.path.join(self.raw_dir, "prices.csv")
        if os.path.exists(path):
            try:
                df = pd.read_csv(path)
                if "Unnamed: 0" in df.columns:
                    df = df.drop(columns=["Unnamed: 0"])
                df.columns = [str(c).lower().strip() for c in df.columns]
                df = df.loc[:, ~df.columns.duplicated(keep="first")]

                date_col = next((c for c in df.columns if c in ["date", "datetime", "index"]), None)
                if date_col:
                    df["date"] = pd.to_datetime(df[date_col]).dt.tz_localize(None)
                    df = df.sort_values("date").reset_index(drop=True)
                return df
            except Exception as e:
                print(f"[!] 载入行情数据失败: {e}")
        return pd.DataFrame()

    def _load_earnings_guidance(self) -> Dict[str, Any]:
        path = os.path.join(self.raw_dir, "earnings_guidance.json")
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return {}

    # =========================================================================
    # 模块 1：基本面质量、法务排雷、偿债安全与资本配置效率
    # =========================================================================
    def analyze_fundamental_quality_and_forensics(self) -> Dict[str, Any]:
        """计算双口径 FCF、盈利含金量、应收/存货异动、Piotroski F-Score、ROIC vs WACC 与净回购率"""
        res = {
            "has_sec_data": False,
            "ttm_revenues_b": np.nan,
            "ttm_net_income_b": np.nan,
            "ttm_ocf_b": np.nan,
            "ttm_std_fcf_b": np.nan,
            "ttm_adj_fcf_b": np.nan,
            "std_fcf_margin": np.nan,
            "true_fcf_margin": np.nan,
            "sbc_to_ocf_ratio": np.nan,
            "sbc_to_rev_ratio": np.nan,
            "capex_to_rev_ratio": np.nan,
            "cash_conversion_ratio": np.nan,
            "receivables_yoy_diff": np.nan,
            "inventory_yoy_diff": np.nan,
            "gross_margin_slope_8q": np.nan,
            "piotroski_f_score": np.nan,
            "net_debt_b": np.nan,
            "is_net_cash": False,
            "net_debt_to_ebitda": np.nan,
            "interest_coverage": np.nan,
            "cash_runway_quarters": np.nan,
            "roic_pct": np.nan,
            "eva_spread_pct": np.nan,
            "net_buyback_yield_pct": np.nan,
            "dividend_yield_pct": np.nan,
            "total_shareholder_yield_pct": np.nan,
            "red_flags": [],
            "green_flags": [],
            "recent_metrics": {}
        }

        df = self.df_sec_facts
        if df.empty or len(df) < 4:
            return res

        res["has_sec_data"] = True
        valid_df = df.dropna(subset=["Revenues"]).copy() if "Revenues" in df.columns else df.copy()
        if len(valid_df) < 4:
            valid_df = df.copy()

        latest = valid_df.iloc[-1]
        prev_year = valid_df.iloc[-5] if len(valid_df) >= 5 else valid_df.iloc[0]

        # 1. 提取单季与 TTM 财务指标
        rev_q = latest.get("Revenues", np.nan)
        net_inc_q = latest.get("NetIncome", np.nan)
        ocf_q = latest.get("OCF", np.nan)
        sbc_q = latest.get("SBC", 0.0)
        capex_q = latest.get("CapEx", 0.0)
        true_fcf_q = latest.get("True_FCF_Net_SBC", (ocf_q - capex_q - sbc_q) if pd.notna(ocf_q) else np.nan)

        # 优先使用 TTM 滚动值，若无则使用最近 4 季累加
        def _get_ttm(col_name: str, fallback_series: pd.Series) -> float:
            ttm_col = f"TTM_{col_name}"
            if ttm_col in latest and pd.notna(latest[ttm_col]) and latest[ttm_col] != 0:
                return float(latest[ttm_col])
            # 否则手动取 valid_df 最近 4 季求和
            tail_4 = valid_df.tail(4)
            if col_name in tail_4.columns:
                vals = tail_4[col_name].dropna()
                if len(vals) >= 1:
                    return float(vals.sum())
            return np.nan

        ttm_rev = _get_ttm("Revenues", valid_df["Revenues"]) if "Revenues" in valid_df.columns else rev_q
        ttm_net_inc = _get_ttm("NetIncome", valid_df["NetIncome"]) if "NetIncome" in valid_df.columns else net_inc_q
        ttm_ocf = _get_ttm("OCF", valid_df["OCF"]) if "OCF" in valid_df.columns else ocf_q
        ttm_capex = _get_ttm("CapEx", valid_df["CapEx"]) if "CapEx" in valid_df.columns else capex_q
        ttm_sbc = _get_ttm("SBC", valid_df["SBC"]) if "SBC" in valid_df.columns else sbc_q

        ttm_std_fcf = (ttm_ocf - ttm_capex) if (pd.notna(ttm_ocf) and pd.notna(ttm_capex)) else np.nan
        ttm_adj_fcf = (ttm_std_fcf - (ttm_sbc if pd.notna(ttm_sbc) else 0.0)) if pd.notna(ttm_std_fcf) else np.nan

        res["ttm_revenues_b"] = round(ttm_rev / 1e9, 2) if pd.notna(ttm_rev) else np.nan
        res["ttm_net_income_b"] = round(ttm_net_inc / 1e9, 2) if pd.notna(ttm_net_inc) else np.nan
        res["ttm_ocf_b"] = round(ttm_ocf / 1e9, 2) if pd.notna(ttm_ocf) else np.nan
        res["ttm_std_fcf_b"] = round(ttm_std_fcf / 1e9, 2) if pd.notna(ttm_std_fcf) else np.nan
        res["ttm_adj_fcf_b"] = round(ttm_adj_fcf / 1e9, 2) if pd.notna(ttm_adj_fcf) else np.nan

        # 利润率指标
        if pd.notna(ttm_rev) and ttm_rev > 0:
            if pd.notna(ttm_std_fcf):
                res["std_fcf_margin"] = round((ttm_std_fcf / ttm_rev) * 100.0, 1)
            if pd.notna(ttm_adj_fcf):
                res["true_fcf_margin"] = round((ttm_adj_fcf / ttm_rev) * 100.0, 1)
            if pd.notna(ttm_sbc):
                res["sbc_to_rev_ratio"] = round((ttm_sbc / ttm_rev) * 100.0, 1)
            if pd.notna(ttm_capex):
                res["capex_to_rev_ratio"] = round((ttm_capex / ttm_rev) * 100.0, 1)

        # 盈利含金量 (Cash Conversion: TTM OCF / TTM Net Income)
        if pd.notna(ttm_ocf) and pd.notna(ttm_net_inc) and ttm_net_inc > 0:
            conv = ttm_ocf / ttm_net_inc
            res["cash_conversion_ratio"] = round(conv, 2)
            if conv < 0.75:
                res["red_flags"].append(f"盈利含金量不足 (OCF/净利润={conv:.2f} < 0.75，大量利润停留在应收账款或未转化为现金)")
            elif conv >= 1.05:
                res["green_flags"].append(f"经营现金流极其充沛 (OCF/净利润={conv:.2f} >= 1.05，盈利含金量极高)")

        # SBC 稀释率
        if pd.notna(ttm_sbc) and pd.notna(ttm_ocf) and ttm_ocf > 0:
            sbc_ratio = ttm_sbc / ttm_ocf
            res["sbc_to_ocf_ratio"] = round(sbc_ratio * 100, 1)
            if sbc_ratio > 0.40:
                res["red_flags"].append(f"股权激励稀释严重 (SBC 占经营现金流高达 {sbc_ratio*100:.1f}%，严重虚高标准 FCF)")
            elif sbc_ratio < 0.25:
                res["green_flags"].append(f"股权激励控制优异 (SBC 占 OCF 比重仅 {sbc_ratio*100:.1f}%)")

        # 2. 偿债安全度与现金跑道 (Solvency & Cash Runway)
        tot_debt = latest.get("TotalDebt", 0.0)
        st_debt = latest.get("ShortTermDebt", 0.0)
        tot_debt = (tot_debt if pd.notna(tot_debt) else 0.0) + (st_debt if pd.notna(st_debt) else 0.0)
        cash = latest.get("CashEquivalents", 0.0)
        cash = cash if pd.notna(cash) else 0.0
        net_debt = tot_debt - cash
        res["net_debt_b"] = round(net_debt / 1e9, 2)
        res["is_net_cash"] = bool(net_debt <= 0)

        if net_debt <= 0:
            res["green_flags"].append(f"资产负债表极度强健 (拥有净现金净额 ${abs(net_debt)/1e9:.2f} B，无偿债违约风险)")
        else:
            # 检验 Net Debt / EBITDA
            ebit = latest.get("TTM_OperatingIncome", latest.get("OperatingIncome", np.nan))
            dna = latest.get("TTM_DepreciationAmortization", latest.get("DepreciationAmortization", 0.0))
            ebitda = (ebit + (dna if pd.notna(dna) else 0.0)) if pd.notna(ebit) else np.nan
            if pd.notna(ebitda) and ebitda > 0:
                nd_ebitda = net_debt / ebitda
                res["net_debt_to_ebitda"] = round(nd_ebitda, 2)
                if nd_ebitda > 3.0:
                    res["red_flags"].append(f"净杠杆过高预警 (Net Debt / EBITDA = {nd_ebitda:.2f}x > 3.0x，高利率环境下利息负担沉重)")

        # 利息保障倍数
        int_exp = latest.get("TTM_InterestExpense", latest.get("InterestExpense", np.nan))
        ebit = latest.get("TTM_OperatingIncome", latest.get("OperatingIncome", np.nan))
        if pd.notna(ebit) and pd.notna(int_exp) and int_exp > 0:
            ic = ebit / int_exp
            res["interest_coverage"] = round(ic, 1)
            if ic < 3.0:
                res["red_flags"].append(f"利息保障倍数警戒 (EBIT / 利息支出 = {ic:.1f}x < 3.0x)")
            elif ic > 8.0:
                res["green_flags"].append(f"利息保障倍数极高 ({ic:.1f}x)")

        # 困境股现金跑道 (Cash Runway)
        if pd.notna(ttm_std_fcf) and ttm_std_fcf < 0 and cash > 0:
            quarterly_burn = abs(ttm_std_fcf) / 4.0
            runway = cash / quarterly_burn
            res["cash_runway_quarters"] = round(runway, 1)
            if runway < 6.0:
                res["red_flags"].append(f"现金失血流动性危机 (账面现金仅够维持 {runway:.1f} 季烧钱，面临股权大幅折价增发风险)")
            else:
                res["green_flags"].append(f"现金储备充裕 (支持当前烧钱速率 {runway:.1f} 个季度)")

        # 3. 资本配置效率 (ROIC vs WACC & 净回购注销率)
        equity = latest.get("StockholdersEquity", np.nan)
        if pd.notna(equity) and equity > 0 and pd.notna(ebit) and ebit > 0:
            excess_cash = max(0.0, cash - 0.05 * (ttm_rev if pd.notna(ttm_rev) else 0.0))
            invested_cap = tot_debt + equity - excess_cash
            tax_rate = 0.21
            tax_exp = latest.get("IncomeTaxExpense", np.nan)
            if pd.notna(tax_exp) and pd.notna(net_inc_q) and net_inc_q > 0:
                tax_rate = max(0.10, min(0.30, tax_exp / net_inc_q))
            nopat = ebit * (1.0 - tax_rate)
            if invested_cap > 0:
                roic = (nopat / invested_cap) * 100.0
                res["roic_pct"] = round(roic, 1)
                # 动态计算 WACC 对比
                wacc_ref = 8.5 # 基准参考
                eva = roic - wacc_ref
                res["eva_spread_pct"] = round(eva, 1)
                if roic >= 15.0:
                    res["green_flags"].append(f"投入资本回报率卓越 (ROIC = {roic:.1f}%，大幅跑赢资本成本，具备持久经济增加值)")
                elif roic < 6.5:
                    res["red_flags"].append(f"资本配置效率低下 (ROIC = {roic:.1f}% < WACC，业务扩张可能在毁灭股东财富)")

        # 真实净股份注销率 (Net Buyback Yield %)
        if "SharesOutstanding" in valid_df.columns:
            sh_curr = latest.get("SharesOutstanding", np.nan)
            sh_prev = prev_year.get("SharesOutstanding", np.nan)
            if pd.notna(sh_curr) and pd.notna(sh_prev) and sh_prev > 0:
                buyback_y = -((sh_curr - sh_prev) / sh_prev) * 100.0
                res["net_buyback_yield_pct"] = round(buyback_y, 2)
                div_y = self.market_snapshot.get("profile", {}).get("dividendYield", 0.0) or 0.0
                res["dividend_yield_pct"] = round(div_y * 100.0, 2)
                res["total_shareholder_yield_pct"] = round(buyback_y + (div_y * 100.0), 2)
                if buyback_y >= 1.5:
                    res["green_flags"].append(f"积极注销式股票回购 (过去 1 年净减少总股本 {buyback_y:.1f}%，持续增厚真实每股 EPS)")
                elif buyback_y <= -2.5:
                    res["red_flags"].append(f"股本恶性稀释预警 (过去 1 年总股本净增加 {-buyback_y:.1f}%，老股东价值被稀释)")

        # 4. 应收账款与存货异动排雷
        if "AccountsReceivable" in valid_df.columns and "Revenues" in valid_df.columns:
            ar_curr = latest.get("AccountsReceivable", np.nan)
            ar_prev = prev_year.get("AccountsReceivable", np.nan)
            rev_curr = latest.get("Revenues", np.nan)
            rev_prev = prev_year.get("Revenues", np.nan)
            if pd.notna(ar_curr) and pd.notna(ar_prev) and ar_prev > 0 and pd.notna(rev_curr) and pd.notna(rev_prev) and rev_prev > 0:
                ar_growth = (ar_curr - ar_prev) / ar_prev
                rev_growth = (rev_curr - rev_prev) / rev_prev
                ar_diff = (ar_growth - rev_growth) * 100.0
                res["receivables_yoy_diff"] = round(ar_diff, 1)
                if ar_diff > 18.0:
                    res["red_flags"].append(f"应收账款异动预警 (应收账款同比增速超越营收 {ar_diff:+.1f}%，警惕向渠道压货虚增收入)")
                elif ar_diff < -5.0:
                    res["green_flags"].append(f"应收账款周转极佳 (应收账款增速低于营收 {-ar_diff:.1f}%)")

        if "Inventory" in valid_df.columns:
            inv_curr = latest.get("Inventory", np.nan)
            inv_prev = prev_year.get("Inventory", np.nan)
            if pd.notna(inv_curr) and pd.notna(inv_prev) and inv_prev > 0 and pd.notna(rev_curr) and pd.notna(rev_prev) and rev_prev > 0:
                inv_growth = (inv_curr - inv_prev) / inv_prev
                inv_diff = (inv_growth - rev_growth) * 100.0
                res["inventory_yoy_diff"] = round(inv_diff, 1)
                if inv_diff > 25.0:
                    res["red_flags"].append(f"存货积压预警 (存货同比增速超越营收 {inv_diff:+.1f}%，警惕产品滞销与计提跌价减值)")

        # 5. 毛利率 8 季度斜率 (护城河定价权)
        if "GrossProfit" in valid_df.columns and "Revenues" in valid_df.columns:
            recent_8q = valid_df.tail(8).copy()
            gm_series = (recent_8q["GrossProfit"] / recent_8q["Revenues"].replace(0, np.nan) * 100.0).dropna()
            if len(gm_series) >= 4:
                x = np.arange(len(gm_series))
                slope, _ = np.polyfit(x, gm_series.values, 1)
                res["gross_margin_slope_8q"] = round(float(slope), 2)
                if slope > 0.4:
                    res["green_flags"].append(f"毛利率持续扩张 (过去 8 季斜率 {slope:+.2f}%/季，护城河定价权极强)")
                elif slope < -1.0:
                    res["red_flags"].append(f"毛利率持续承压 (过去 8 季斜率 {slope:+.2f}%/季，警惕竞争加剧)")

        # 6. Piotroski F-Score (精简稳健版，满分 9 分)
        f_score = 0
        if pd.notna(net_inc_q) and net_inc_q > 0: f_score += 1
        if pd.notna(ocf_q) and ocf_q > 0: f_score += 1
        if pd.notna(ocf_q) and pd.notna(net_inc_q) and ocf_q > net_inc_q: f_score += 1
        if pd.notna(net_inc_q) and pd.notna(prev_year.get("NetIncome")) and net_inc_q > prev_year.get("NetIncome", 0): f_score += 1
        if res.get("gross_margin_slope_8q", 0) >= 0: f_score += 1
        if res.get("receivables_yoy_diff", 0) <= 10: f_score += 1
        if tot_debt <= (prev_year.get("TotalDebt", 0.0) or 0.0): f_score += 1
        if res.get("net_buyback_yield_pct", 0) >= -2.0: f_score += 1
        if res.get("cash_conversion_ratio", 0) >= 0.8: f_score += 1

        res["piotroski_f_score"] = int(min(9, max(0, f_score)))
        if res["piotroski_f_score"] >= 7:
            res["green_flags"].append(f"基本面综合评级优秀 (Piotroski F-Score={res['piotroski_f_score']}/9)")
        elif res["piotroski_f_score"] <= 4:
            res["red_flags"].append(f"基本面综合评级偏弱 (Piotroski F-Score={res['piotroski_f_score']}/9)")

        res["recent_metrics"] = {
            "period": str(latest.get("period", "N/A")),
            "date": str(latest.get("date", "")).split()[0],
            "revenues_b": round(rev_q / 1e9, 2) if pd.notna(rev_q) else np.nan,
            "net_income_b": round(net_inc_q / 1e9, 2) if pd.notna(net_inc_q) else np.nan,
            "ocf_b": round(ocf_q / 1e9, 2) if pd.notna(ocf_q) else np.nan,
            "sbc_b": round(sbc_q / 1e9, 2) if pd.notna(sbc_q) else 0.0,
            "true_fcf_b": round(true_fcf_q / 1e9, 2) if pd.notna(true_fcf_q) else np.nan
        }
        return res

    # =========================================================================
    # 模块 2：估值前置核验卡、公司类型自适应分流与反锚定双口径三阶段 DCF
    # =========================================================================
    def analyze_valuation_and_expectations_gap(self) -> Dict[str, Any]:
        """前置核验参数、判定标的商业模式分流、运行反锚定双口径 DCF 与 5 年历史 PE/PS Band"""
        from quant_models import calculate_reverse_dcf

        res = {
            "preflight_audit": {},
            "company_archetype": "WHITE_CHIP_COMPOUNDER",
            "archetype_name": "稳健白马/现金牛成长模式",
            "implied_fcf_cagr_10y": np.nan,
            "hist_fcf_cagr_3y": np.nan,
            "expectations_gap": np.nan,
            "valuation_status": "未知",
            "trailing_pe": np.nan,
            "forward_pe": np.nan,
            "ps_ttm": np.nan,
            "pb_ratio": np.nan,
            "analyst_target_mean": np.nan,
            "analyst_upside_pct": np.nan,
            "dcf_standard": {},
            "dcf_post_sbc_adj": {},
            "dcf_sensitivity_matrix_adj": [],
            "pe_band_5y": {},
            "ps_band_5y": {},
            "stress_test_floor_price": np.nan,
            "turnaround_kpis": {}
        }

        profile = self.market_snapshot.get("profile", {})
        macro = self.market_snapshot.get("macro_backdrop", {})
        curr_price = self._get_latest_price()
        shares = self._safe_float(profile.get("sharesOutstanding"), np.nan)
        if pd.isna(shares) and not self.df_sec_facts.empty and "SharesOutstanding" in self.df_sec_facts.columns:
            sh_series = self.df_sec_facts["SharesOutstanding"].dropna()
            if not sh_series.empty:
                shares = float(sh_series.iloc[-1])

        mkt_cap = self._safe_float(profile.get("marketCap"), np.nan)
        if (pd.isna(mkt_cap) or mkt_cap <= 0) and pd.notna(curr_price) and pd.notna(shares) and shares > 0:
            mkt_cap = curr_price * shares

        res["trailing_pe"] = profile.get("trailingPE", np.nan)
        res["forward_pe"] = profile.get("forwardPE", np.nan)
        res["ps_ttm"] = profile.get("priceToSales", np.nan)
        res["pb_ratio"] = profile.get("priceToBook", np.nan)
        res["analyst_target_mean"] = profile.get("targetMeanPrice", np.nan)

        if pd.notna(curr_price) and pd.notna(res["analyst_target_mean"]) and curr_price > 0:
            res["analyst_upside_pct"] = round((res["analyst_target_mean"] - curr_price) / curr_price * 100.0, 1)

        # 1. 动态 WACC 前置参数核验卡 (Pre-Flight Audit Card)
        rf = float(macro.get("treasury_10y_yield", 4.25)) / 100.0
        beta_raw = float(profile.get("beta", np.nan))
        beta_adj = max(0.65, min(2.10, (2.0/3.0)*beta_raw + (1.0/3.0)*1.0)) if pd.notna(beta_raw) else 1.05
        erp = 0.0475 # Damodaran 权威美股 ERP
        re = rf + beta_adj * erp

        # 债务成本与总有息负债
        tot_debt = 0.0
        int_exp = 0.0
        if not self.df_sec_facts.empty:
            last_sec = self.df_sec_facts.iloc[-1]
            d1 = self._safe_float(last_sec.get("TotalDebt"), 0.0)
            d2 = self._safe_float(last_sec.get("ShortTermDebt"), 0.0)
            tot_debt = float(d1 + d2)
            int_exp = self._safe_float(last_sec.get("TTM_InterestExpense", last_sec.get("InterestExpense")), 0.0)

        rd = max(rf + 0.005, min(0.11, (int_exp / tot_debt))) if (tot_debt > 0 and int_exp > 0) else (rf + 0.015)
        tax_rate = 0.21
        e_val = mkt_cap if pd.notna(mkt_cap) and mkt_cap > 0 else (curr_price * shares if (pd.notna(curr_price) and pd.notna(shares)) else 1e11)
        v_tot = e_val + tot_debt
        wacc = (e_val / v_tot) * re + (tot_debt / v_tot) * rd * (1.0 - tax_rate)
        wacc = max(0.065, min(0.135, wacc))

        res["preflight_audit"] = {
            "rf_10y_treasury_pct": round(rf * 100, 2),
            "beta_adjusted": round(beta_adj, 2),
            "erp_pct": round(erp * 100, 2),
            "cost_of_equity_re_pct": round(re * 100, 2),
            "cost_of_debt_rd_pct": round(rd * 100, 2),
            "effective_tax_rate_pct": round(tax_rate * 100, 1),
            "wacc_dynamic_pct": round(wacc * 100, 2),
            "diluted_shares_m": round(shares / 1e6, 1) if pd.notna(shares) else np.nan,
            "market_cap_b": round(mkt_cap / 1e9, 2) if pd.notna(mkt_cap) else np.nan
        }

        # 2. 标的商业模式类型分流器 (Archetype Router)
        ttm_rev = np.nan
        ttm_net_inc = np.nan
        ttm_ocf = np.nan
        ttm_capex = 0.0
        ttm_sbc = 0.0
        ttm_std_fcf = np.nan
        ttm_adj_fcf = np.nan
        cash_equiv = 0.0

        if not self.df_sec_facts.empty:
            l = self.df_sec_facts.iloc[-1]
            ttm_rev = self._safe_float(l.get("TTM_Revenues", l.get("Revenues")), np.nan)
            ttm_net_inc = self._safe_float(l.get("TTM_NetIncome", l.get("NetIncome")), np.nan)
            ttm_ocf = self._safe_float(l.get("TTM_OCF", l.get("OCF")), np.nan)
            ttm_capex = self._safe_float(l.get("TTM_CapEx", l.get("CapEx")), 0.0)
            ttm_sbc = self._safe_float(l.get("TTM_SBC", l.get("SBC")), 0.0)

            # 优先读取已计算好的 TTM_FCF_Standard 与 TTM_True_FCF_Net_SBC
            fcf_std_saved = l.get("TTM_FCF_Standard", l.get("FCF_Standard"))
            if pd.notna(fcf_std_saved):
                ttm_std_fcf = float(fcf_std_saved)
            elif pd.notna(ttm_ocf):
                ttm_std_fcf = ttm_ocf - ttm_capex

            fcf_adj_saved = l.get("TTM_True_FCF_Net_SBC", l.get("True_FCF_Net_SBC"))
            if pd.notna(fcf_adj_saved):
                ttm_adj_fcf = float(fcf_adj_saved)
            elif pd.notna(ttm_std_fcf):
                ttm_adj_fcf = ttm_std_fcf - ttm_sbc

            cash_equiv = self._safe_float(l.get("CashEquivalents"), 0.0)

        # 模式判定
        if pd.isna(ttm_std_fcf) or ttm_std_fcf <= 0:
            res["company_archetype"] = "TURNAROUND_CYCLICAL"
            res["archetype_name"] = "困境反转/重资产产能爬坡模式"
        elif pd.notna(ttm_sbc) and pd.notna(ttm_ocf) and ttm_ocf > 0 and (ttm_sbc / ttm_ocf) > 0.45:
            res["company_archetype"] = "HIGH_SBC_GROWTH"
            res["archetype_name"] = "高股权激励稀释成长模式"
        else:
            res["company_archetype"] = "WHITE_CHIP_COMPOUNDER"
            res["archetype_name"] = "稳健白马/现金牛成长模式"

        # 3. 反向 DCF 市场预期差
        net_debt = tot_debt - cash_equiv
        fcf_per_share_std = (ttm_std_fcf / shares) if (pd.notna(ttm_std_fcf) and pd.notna(shares) and shares > 0 and ttm_std_fcf > 0) else np.nan
        if pd.notna(curr_price) and pd.notna(fcf_per_share_std) and fcf_per_share_std > 0:
            implied_g = calculate_reverse_dcf(curr_price, fcf_per_share_std, wacc=wacc, terminal_growth=0.025, forecast_years=10)
            if pd.notna(implied_g):
                res["implied_fcf_cagr_10y"] = round(float(implied_g), 1)

        # 过去 3 年实际 FCF 复合年化增速
        if not self.df_sec_facts.empty and len(self.df_sec_facts) >= 12:
            try:
                fcf_recent = self.df_sec_facts.tail(4)["OCF"].sum() - self.df_sec_facts.tail(4)["CapEx"].fillna(0).sum()
                fcf_3y_ago = self.df_sec_facts.iloc[-16:-12]["OCF"].sum() - self.df_sec_facts.iloc[-16:-12]["CapEx"].fillna(0).sum()
                if fcf_3y_ago > 0 and fcf_recent > 0:
                    hist_cagr = ((fcf_recent / fcf_3y_ago) ** (1.0 / 3.0) - 1.0) * 100.0
                    res["hist_fcf_cagr_3y"] = round(float(hist_cagr), 1)
            except Exception:
                pass

        if pd.notna(res["implied_fcf_cagr_10y"]) and pd.notna(res["hist_fcf_cagr_3y"]):
            gap = res["implied_fcf_cagr_10y"] - res["hist_fcf_cagr_3y"]
            res["expectations_gap"] = round(gap, 1)
            if gap <= -4.0:
                res["valuation_status"] = "安全边际/低预期区 (当前股价内含增速显著低于历史交付水平，赔率占优)"
            elif abs(gap) <= 4.0:
                res["valuation_status"] = "合理中枢定价 (市场隐含预期与历史增长动量基本相称)"
            elif gap <= 12.0:
                res["valuation_status"] = "偏乐观透支区 (市场要求未来 10 年增速进一步提速)"
            else:
                res["valuation_status"] = "极度高估泡沫区 (当前估值隐含增速超越历史基准 12% 以上，容错空间极小)"

        # 4. 反现价锚定·双口径三阶段正向 DCF 模型
        # 严格内生确定前 5 年增速：取历史 3Y CAGR 与行业合理中枢的保守折中，严禁向现价倒推
        g1_base = 0.08 # 默认 8%
        if pd.notna(res.get("hist_fcf_cagr_3y")):
            g1_base = max(0.04, min(0.22, res["hist_fcf_cagr_3y"] / 100.0))

        def _run_forward_dcf(fcf_base_val: float) -> Dict[str, Any]:
            if pd.isna(fcf_base_val) or fcf_base_val <= 0 or pd.isna(shares) or shares <= 0:
                return {"dcf_fair_price": np.nan, "mos_safety_price_20pct": np.nan}
            pv_fcfs = 0.0
            cf_t = fcf_base_val
            # 阶段 1 (1~5年)
            for t in range(1, 6):
                cf_t *= (1.0 + g1_base)
                pv_fcfs += cf_t / ((1.0 + wacc) ** t)
            # 阶段 2 (6~10年线性收敛至 3.0%)
            for t in range(6, 11):
                w = (t - 5) / 5.0
                step_g = g1_base * (1.0 - w) + 0.03 * w
                cf_t *= (1.0 + step_g)
                pv_fcfs += cf_t / ((1.0 + wacc) ** t)
            # 阶段 3 终值
            gn = 0.025
            tv10 = (cf_t * (1.0 + gn)) / max(0.015, (wacc - gn))
            pv_tv = tv10 / ((1.0 + wacc) ** 10)
            ev = pv_fcfs + pv_tv
            eq_val = ev - net_debt
            val_share = max(0.0, eq_val / shares)
            return {
                "dcf_fair_price": round(val_share, 2),
                "mos_safety_price_20pct": round(val_share * 0.80, 2),
                "growth_assumed_5y_pct": round(g1_base * 100, 1),
                "terminal_growth_pct": round(gn * 100, 1)
            }

        res["dcf_standard"] = _run_forward_dcf(ttm_std_fcf)
        res["dcf_post_sbc_adj"] = _run_forward_dcf(ttm_adj_fcf)

        # 3x3 敏感性矩阵 (基于 Post-SBC Adj. FCF 口径)
        matrix_rows = []
        if pd.notna(ttm_adj_fcf) and ttm_adj_fcf > 0 and pd.notna(shares) and shares > 0:
            for dw in [-0.005, 0.0, 0.005]:
                w_test = max(0.06, wacc + dw)
                row_item = {"wacc_label": f"{w_test*100:.1f}%"}
                for gn_test in [0.020, 0.025, 0.030]:
                    # 重算
                    pv_f = 0.0
                    cft = ttm_adj_fcf
                    for t in range(1, 6):
                        cft *= (1.0 + g1_base)
                        pv_f += cft / ((1.0 + w_test) ** t)
                    for t in range(6, 11):
                        w = (t - 5) / 5.0
                        cft *= (1.0 + (g1_base * (1.0 - w) + 0.03 * w))
                        pv_f += cft / ((1.0 + w_test) ** t)
                    tv = (cft * (1.0 + gn_test)) / max(0.015, (w_test - gn_test))
                    ev_test = pv_f + (tv / ((1.0 + w_test) ** 10))
                    val_p = max(0.0, (ev_test - net_debt) / shares)
                    row_item[f"gn_{gn_test*100:.1f}%"] = round(val_p, 2)
                matrix_rows.append(row_item)
        res["dcf_sensitivity_matrix_adj"] = matrix_rows

        # 5. 5 年历史 PE / PS Band 分位数与乘数重构压力测试 (Multiple Compression Floor)
        df_pr = self.df_price
        if not df_pr.empty and len(df_pr) >= 200:
            prices_series = df_pr["close"].dropna()
            # PS 估值通道测算 (每股营收 SPS)
            if pd.notna(ttm_rev) and ttm_rev > 0 and pd.notna(shares) and shares > 0:
                sps = ttm_rev / shares
                ps_series = (prices_series / sps).dropna()
                ps_mu = float(ps_series.mean())
                ps_sigma = float(ps_series.std())
                res["ps_band_5y"] = {
                    "mean_ps": round(ps_mu, 2),
                    "minus_2sigma_price": round(max(0.1, (ps_mu - 2 * ps_sigma) * sps), 2),
                    "minus_1sigma_price": round(max(0.1, (ps_mu - ps_sigma) * sps), 2),
                    "plus_1sigma_price": round((ps_mu + ps_sigma) * sps, 2),
                    "plus_2sigma_price": round((ps_mu + 2 * ps_sigma) * sps, 2),
                    "current_percentile_pct": round(float((ps_series < (curr_price / sps)).mean() * 100), 1)
                }

            # PE 估值通道测算
            if pd.notna(ttm_net_inc) and ttm_net_inc > 0 and pd.notna(shares) and shares > 0:
                eps = ttm_net_inc / shares
                pe_series = (prices_series / eps).dropna()
                pe_series = pe_series[(pe_series > 5) & (pe_series < 150)] # 剔除异常极值
                if len(pe_series) >= 100:
                    pe_mu = float(pe_series.mean())
                    pe_sigma = float(pe_series.std())
                    res["pe_band_5y"] = {
                        "mean_pe": round(pe_mu, 1),
                        "minus_2sigma_price": round(max(1.0, (pe_mu - 2 * pe_sigma) * eps), 2),
                        "minus_1sigma_price": round(max(1.0, (pe_mu - pe_sigma) * eps), 2),
                        "plus_1sigma_price": round((pe_mu + pe_sigma) * eps, 2),
                        "plus_2sigma_price": round((pe_mu + 2 * pe_sigma) * eps, 2),
                        "current_percentile_pct": round(float((pe_series < (curr_price / eps)).mean() * 100), 1)
                    }
                    # 杀估值乘数重构压力测试底托 (Multiple Compression Floor: 降速至成熟期 15x PE 或 -1.5sigma)
                    res["stress_test_floor_price"] = round(min(16.0, max(8.0, pe_mu - 1.5 * pe_sigma)) * eps, 2)

        # 若无 PE 压力测试价，用 PS -1.5sigma 代替
        if pd.isna(res["stress_test_floor_price"]) and "ps_band_5y" in res and "minus_1sigma_price" in res["ps_band_5y"]:
            res["stress_test_floor_price"] = res["ps_band_5y"]["minus_1sigma_price"]

        # 6. 针对困境反转股的重置成本与正常化盈利 (Turnaround KPIs)
        if res["company_archetype"] == "TURNAROUND_CYCLICAL":
            pb = profile.get("priceToBook", np.nan)
            book_val = profile.get("bookValue", np.nan)
            pb_support = float(book_val * 1.1) if (pd.notna(book_val) and book_val > 0) else np.nan
            # 正常化营运利润率 12% 测算的 Mid-cycle EPS
            norm_eps = (ttm_rev * 0.12 * (1.0 - tax_rate)) / shares if (pd.notna(ttm_rev) and pd.notna(shares) and shares > 0) else np.nan
            norm_price = float(norm_eps * 15.0) if (pd.notna(norm_eps) and norm_eps > 0) else np.nan
            res["turnaround_kpis"] = {
                "pb_support_price": round(pb_support, 2) if pd.notna(pb_support) else np.nan,
                "normalized_mid_cycle_eps": round(norm_eps, 2) if pd.notna(norm_eps) else np.nan,
                "normalized_fair_price": round(norm_price, 2) if pd.notna(norm_price) else np.nan
            }

        return res

    # =========================================================================
    # 模块 3：微观动量、相对大盘超额 Alpha 与相空间动力学
    # =========================================================================
    def analyze_reflexivity_and_sentiment(self) -> Dict[str, Any]:
        """运行反身性相空间动力学数学引擎并合成均线偏离、12-1M 动量、相对 SPY Alpha 与 14D ATR"""
        from reflexivity_engine import run_universal_reflexivity_radar

        res = {
            "has_radar_data": False,
            "quadrant": 0,
            "quadrant_name": "未知",
            "composite_score": np.nan,
            "q1_pos_dist200": np.nan,
            "q1_dot_velocity": np.nan,
            "v_dot_lyapunov": np.nan,
            "reflexive_gap": np.nan,
            "active_triggers": [],
            "options": self.market_snapshot.get("options_sentiment", {}),
            "short_interest": {
                "short_percent_of_float": self.market_snapshot.get("profile", {}).get("shortPercentOfFloat", np.nan),
                "short_ratio_days_to_cover": self.market_snapshot.get("profile", {}).get("shortRatio", np.nan)
            },
            "momentum_and_alpha": {
                "sma_20": np.nan,
                "sma_50": np.nan,
                "sma_200": np.nan,
                "ma_alignment": "未知",
                "bias_20d_pct": np.nan,
                "bias_200d_pct": np.nan,
                "mom_12_1_pct": np.nan,
                "alpha_vs_spy_1m_pct": np.nan,
                "alpha_vs_spy_3m_pct": np.nan,
                "alpha_vs_spy_6m_pct": np.nan,
                "rsi_14": np.nan,
                "atr_14": np.nan,
                "atr_pct": np.nan,
                "atr_stop_loss_price": np.nan
            },
            "df_radar": None
        }

        df_price = self.df_price
        macro_csv = os.path.join(BASE_DIR, "market_data_local.csv")

        if df_price.empty:
            return res

        # 1. 微观动量、均线形态与 ATR% 波动率计算
        try:
            closes = df_price["close"]
            curr_p = float(closes.iloc[-1])
            res["momentum_and_alpha"]["sma_20"] = round(float(closes.rolling(20).mean().iloc[-1]), 2)
            res["momentum_and_alpha"]["sma_50"] = round(float(closes.rolling(50).mean().iloc[-1]), 2)
            sma_200 = float(closes.rolling(200).mean().iloc[-1]) if len(closes) >= 200 else np.nan
            res["momentum_and_alpha"]["sma_200"] = round(sma_200, 2) if pd.notna(sma_200) else np.nan

            s20 = res["momentum_and_alpha"]["sma_20"]
            s50 = res["momentum_and_alpha"]["sma_50"]
            if pd.notna(s20) and pd.notna(s50) and pd.notna(sma_200):
                if curr_p > s20 > s50 > sma_200:
                    res["momentum_and_alpha"]["ma_alignment"] = "经典多头顺势排列 (Price > 20D > 50D > 200D)"
                elif curr_p < s20 < s50 < sma_200:
                    res["momentum_and_alpha"]["ma_alignment"] = "空头排列承压 (Price < 20D < 50D < 200D)"
                else:
                    res["momentum_and_alpha"]["ma_alignment"] = "均线交织纠缠整理"

            if pd.notna(s20) and s20 > 0:
                res["momentum_and_alpha"]["bias_20d_pct"] = round((curr_p - s20) / s20 * 100.0, 2)
            if pd.notna(sma_200) and sma_200 > 0:
                res["momentum_and_alpha"]["bias_200d_pct"] = round((curr_p - sma_200) / sma_200 * 100.0, 2)

            # 经典 12-1M 动量 (t-21 到 t-252 收益率)
            if len(closes) >= 252:
                p_t1m = float(closes.iloc[-21])
                p_t12m = float(closes.iloc[-252])
                if p_t12m > 0:
                    res["momentum_and_alpha"]["mom_12_1_pct"] = round((p_t1m - p_t12m) / p_t12m * 100.0, 1)

            # 日线 RSI(14)
            delta = closes.diff()
            gain = delta.clip(lower=0).rolling(14).mean()
            loss = (-delta.clip(upper=0)).rolling(14).mean()
            rs = gain / (loss + 1e-8)
            rsi = 100.0 - (100.0 / (1.0 + rs))
            res["momentum_and_alpha"]["rsi_14"] = round(float(rsi.iloc[-1]), 1)

            # 自适应波动率 ATR(14)
            if "high" in df_price.columns and "low" in df_price.columns:
                high = df_price["high"]
                low = df_price["low"]
                prev_close = df_price["close"].shift(1)
                tr = pd.concat([high - low, (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)
                atr_14 = float(tr.rolling(14).mean().iloc[-1])
                res["momentum_and_alpha"]["atr_14"] = round(atr_14, 2)
                res["momentum_and_alpha"]["atr_pct"] = round((atr_14 / curr_p) * 100.0, 2)
                res["momentum_and_alpha"]["atr_stop_loss_price"] = round(curr_p - 2.0 * atr_14, 2)
            else:
                std_20 = float(closes.pct_change().rolling(20).std().iloc[-1] or 0.02)
                res["momentum_and_alpha"]["atr_pct"] = round(std_20 * 100.0 * np.sqrt(252/14), 2)
                res["momentum_and_alpha"]["atr_stop_loss_price"] = round(curr_p * (1.0 - 2.0 * std_20), 2)

            # 相对大盘 SPY 超额收益 (Alpha vs SPY)
            spy_csv = os.path.join(BASE_DIR, "spy_ohlcv_local.csv")
            if os.path.exists(spy_csv):
                try:
                    df_spy = pd.read_csv(spy_csv)
                    spy_close_col = next((c for c in df_spy.columns if str(c).lower() == "close"), None)
                    if spy_close_col and len(df_spy) >= 126 and len(closes) >= 126:
                        spy_c = df_spy[spy_close_col]
                        def _calc_alpha(n_days: int) -> float:
                            ret_stock = (curr_p - float(closes.iloc[-n_days])) / float(closes.iloc[-n_days]) * 100.0
                            ret_spy = (float(spy_c.iloc[-1]) - float(spy_c.iloc[-n_days])) / float(spy_c.iloc[-n_days]) * 100.0
                            return ret_stock - ret_spy
                        res["momentum_and_alpha"]["alpha_vs_spy_1m_pct"] = round(_calc_alpha(21), 1)
                        res["momentum_and_alpha"]["alpha_vs_spy_3m_pct"] = round(_calc_alpha(63), 1)
                        res["momentum_and_alpha"]["alpha_vs_spy_6m_pct"] = round(_calc_alpha(126), 1)
                except Exception:
                    pass
        except Exception as e:
            print(f"[!] 微观动量指标计算警告: {e}")

        # 2. 索罗斯反身性相空间引擎运行
        if os.path.exists(macro_csv):
            try:
                df_macro = pd.read_csv(macro_csv)
                df_radar = run_universal_reflexivity_radar(self.ticker, df_price, df_macro)
                if df_radar is not None and not df_radar.empty and "Composite_Score" in df_radar.columns:
                    res["has_radar_data"] = True
                    res["df_radar"] = df_radar
                    last = df_radar.iloc[-1]
                    res["composite_score"] = round(float(last.get("Composite_Score", np.nan)), 1)
                    res["q1_pos_dist200"] = round(float(last.get("q1", np.nan)), 2)
                    res["q1_dot_velocity"] = round(float(last.get("q1_dot", np.nan)), 2)
                    res["v_dot_lyapunov"] = round(float(last.get("v_dot", np.nan)), 2)
                    res["reflexive_gap"] = round(float(last.get("Gap", np.nan)), 2)

                    q_idx = int(last.get("Quadrant", 0))
                    res["quadrant"] = q_idx
                    q_names = {
                        1: "象限 I：繁荣主升加速区 (q1 >= 0, q1_dot >= 0)",
                        2: "象限 II：恐慌势阱筑底/回升区 (q1 < 0, q1_dot >= 0)",
                        3: "象限 III：熊市自由落体释放区 (q1 < 0, q1_dot < 0)",
                        4: "象限 IV：高位滞胀动能衰竭区 (q1 >= 0, q1_dot < 0)"
                    }
                    res["quadrant_name"] = q_names.get(q_idx, "未分类")

                    recent_20 = df_radar.tail(20)
                    triggers = []
                    if recent_20["Trigger_Panic"].any(): triggers.append("🟢 极度恐慌底反转信号 (Trigger_Panic)")
                    if recent_20["Trigger_Stage"].any(): triggers.append("🔵 牛市中枢回踩蓄势加仓信号 (Trigger_Stage)")
                    if recent_20["Trigger_Bubble_Top"].any(): triggers.append("🔴 极度泡沫顶动能破位预警 (Trigger_Bubble_Top)")
                    if recent_20["Trigger_Bear_Top"].any(): triggers.append("🟡 熊市反弹衰竭离场预警 (Trigger_Bear_Top)")
                    res["active_triggers"] = triggers
            except Exception as e:
                print(f"[!] 反身性雷达引擎计算异常: {e}")

        return res

    # =========================================================================
    # 模块 4：历史相似相空间状态 3M/6M/1Y 真实胜率回溯引擎
    # =========================================================================
    def calculate_historical_analogue_win_rates(self, df_radar: Optional[pd.DataFrame]) -> Dict[str, Any]:
        """在历史相空间中检索最相似状态，严格按未来真实成交价统计胜率与回撤"""
        res = {
            "has_analogues": False,
            "sample_count": 0,
            "horizon_3m": {"win_rate_pct": np.nan, "median_ret_pct": np.nan, "max_dd_pct": np.nan, "profit_factor": np.nan},
            "horizon_6m": {"win_rate_pct": np.nan, "median_ret_pct": np.nan, "max_dd_pct": np.nan, "profit_factor": np.nan},
            "horizon_12m": {"win_rate_pct": np.nan, "median_ret_pct": np.nan, "max_dd_pct": np.nan, "profit_factor": np.nan},
            "sample_dates": []
        }

        if df_radar is None or df_radar.empty or len(df_radar) < 500:
            return res

        curr_score = df_radar["Composite_Score"].iloc[-1]
        curr_dist = df_radar["Dist_200MA"].iloc[-1]

        if pd.isna(curr_score) or pd.isna(curr_dist):
            return res

        max_idx = len(df_radar) - 126
        match_mask = (
            (df_radar["Composite_Score"].iloc[:max_idx] - curr_score).abs() <= 12.0
        ) & (
            np.sign(df_radar["Dist_200MA"].iloc[:max_idx]) == np.sign(curr_dist)
        ) & (
            (df_radar["Dist_200MA"].iloc[:max_idx] - curr_dist).abs() <= 10.0
        )

        match_indices = np.where(match_mask)[0]
        if len(match_indices) == 0:
            return res

        # 聚类降噪：相邻 25 个交易日内的同质信号仅取第一个，确保样本统计独立性
        filtered_indices = []
        last_idx = -999
        for idx in match_indices:
            if idx - last_idx >= 25:
                filtered_indices.append(idx)
                last_idx = idx

        if len(filtered_indices) < 3:
            return res

        ret_3m, ret_6m, ret_12m = [], [], []
        dd_12m = []
        prices = df_radar["close"].values
        n_len = len(prices)

        for idx in filtered_indices:
            p0 = prices[idx]
            dt_s = str(df_radar["date"].iloc[idx]).split()[0]
            res["sample_dates"].append(dt_s)

            if idx + 63 < n_len:
                ret_3m.append((prices[idx + 63] - p0) / p0 * 100.0)
            if idx + 126 < n_len:
                ret_6m.append((prices[idx + 126] - p0) / p0 * 100.0)
            if idx + 252 < n_len:
                p_future = prices[idx:idx + 252]
                ret_12m.append((prices[idx + 252] - p0) / p0 * 100.0)
                cum_max = np.maximum.accumulate(p_future)
                dd = (p_future - cum_max) / (cum_max + 1e-8) * 100.0
                dd_12m.append(float(np.min(dd)))

        def _calc_stats(arr):
            if not arr:
                return {"win_rate_pct": np.nan, "median_ret_pct": np.nan, "profit_factor": np.nan}
            arr = np.array(arr)
            win_cnt = np.sum(arr > 0)
            wr = win_cnt / len(arr) * 100.0
            pos = arr[arr > 0]
            neg = arr[arr < 0]
            avg_win = float(np.mean(pos)) if len(pos) > 0 else 0.0
            avg_loss = abs(float(np.mean(neg))) if len(neg) > 0 else 1.0
            pf = round(avg_win / avg_loss, 2) if avg_loss > 0 else np.nan
            return {
                "win_rate_pct": round(float(wr), 1),
                "median_ret_pct": round(float(np.median(arr)), 1),
                "profit_factor": pf
            }

        res["has_analogues"] = True
        res["sample_count"] = len(filtered_indices)
        res["horizon_3m"] = _calc_stats(ret_3m)
        res["horizon_6m"] = _calc_stats(ret_6m)
        res["horizon_12m"] = _calc_stats(ret_12m)
        if dd_12m:
            res["horizon_12m"]["max_dd_pct"] = round(float(np.median(dd_12m)), 1)

        return res

    # =========================================================================
    # 模块 5：五维 100 分制加权评分卡与反锚定双轨制执行网格
    # =========================================================================
    def calculate_multi_factor_score_and_dual_track(
        self,
        fund: Dict[str, Any],
        val: Dict[str, Any],
        refl: Dict[str, Any],
        hist: Dict[str, Any]
    ) -> Dict[str, Any]:
        """合成五维 100 分量化评分卡，并推导反现价锚定的左右侧双轨建仓/风控价格网格"""
        curr_p = self._get_latest_price()

        # 1. 维度一：质量分 (Quality Score, 满分 30 分)
        q_score = 0.0
        # 1.1 现金流品质与含金量 (10分)
        tf_margin = fund.get("true_fcf_margin", 0.0) or 0.0
        conv = fund.get("cash_conversion_ratio", 0.0) or 0.0
        if tf_margin > 25.0: q_score += 5.0
        elif tf_margin > 12.0: q_score += 3.5
        elif tf_margin > 0.0: q_score += 2.0
        if conv >= 1.05: q_score += 5.0
        elif conv >= 0.85: q_score += 3.5
        elif conv >= 0.65: q_score += 2.0

        # 1.2 偿债杠杆与资本安全 (8分)
        if fund.get("is_net_cash"): q_score += 4.0
        elif (fund.get("net_debt_to_ebitda", 5.0) or 5.0) < 2.0: q_score += 3.0
        elif (fund.get("net_debt_to_ebitda", 5.0) or 5.0) < 3.0: q_score += 1.5
        ic = fund.get("interest_coverage", 0.0) or 0.0
        if ic > 8.0: q_score += 4.0
        elif ic > 4.0: q_score += 2.5
        elif ic > 2.0: q_score += 1.0

        # 1.3 资本配置效率与股东回报 (6分)
        roic = fund.get("roic_pct", 0.0) or 0.0
        if roic > 18.0: q_score += 3.0
        elif roic > 10.0: q_score += 2.0
        buyback = fund.get("net_buyback_yield_pct", 0.0) or 0.0
        if buyback > 1.5: q_score += 3.0
        elif buyback > 0.0: q_score += 1.5

        # 1.4 毛利趋势与财报异动 (6分)
        slope = fund.get("gross_margin_slope_8q", 0.0) or 0.0
        if slope > 0.3: q_score += 3.0
        elif slope >= 0.0: q_score += 1.5
        if abs(fund.get("receivables_yoy_diff", 0.0) or 0.0) <= 8.0: q_score += 3.0

        q_score = min(30.0, max(0.0, q_score))

        # 2. 维度二：估值分 (Valuation Score, 满分 25 分)
        v_score = 0.0
        # 2.1 现价相对 DCF 安全边际折溢价 (10分)
        dcf_adj_mos = val.get("dcf_post_sbc_adj", {}).get("mos_safety_price_20pct", np.nan)
        if pd.notna(dcf_adj_mos) and dcf_adj_mos > 0 and pd.notna(curr_p) and curr_p > 0:
            if curr_p <= dcf_adj_mos: v_score += 10.0
            elif curr_p <= dcf_adj_mos * 1.15: v_score += 7.0
            elif curr_p <= dcf_adj_mos * 1.35: v_score += 4.0
        elif val.get("company_archetype") == "TURNAROUND_CYCLICAL":
            # 困境股看 PS Band 分位
            ps_perc = val.get("ps_band_5y", {}).get("current_percentile_pct", 50.0) or 50.0
            if ps_perc < 20.0: v_score += 10.0
            elif ps_perc < 40.0: v_score += 6.5

        # 2.2 5 年估值通道百分位 (7分)
        pe_perc = val.get("pe_band_5y", {}).get("current_percentile_pct", np.nan)
        if pd.notna(pe_perc):
            if pe_perc < 25.0: v_score += 7.0
            elif pe_perc < 50.0: v_score += 4.5
            elif pe_perc < 75.0: v_score += 2.0
        else:
            ps_p = val.get("ps_band_5y", {}).get("current_percentile_pct", 50.0) or 50.0
            if ps_p < 30.0: v_score += 7.0
            elif ps_p < 60.0: v_score += 4.0

        # 2.3 反向 DCF 预期差与华尔街空间 (8分)
        gap = val.get("expectations_gap", 0.0) or 0.0
        if gap <= -5.0: v_score += 4.0
        elif gap <= 2.0: v_score += 2.5
        upside = val.get("analyst_upside_pct", 0.0) or 0.0
        if upside > 20.0: v_score += 4.0
        elif upside > 10.0: v_score += 2.5

        v_score = min(25.0, max(0.0, v_score))

        # 3. 维度三：动量与反身性相空间分 (Momentum & Phase Space, 满分 20 分)
        m_score = 0.0
        # 3.1 历史 1Y 真实胜率与相空间 (10分)
        wr_1y = hist.get("horizon_12m", {}).get("win_rate_pct", np.nan)
        if pd.notna(wr_1y):
            if wr_1y >= 75.0: m_score += 7.0
            elif wr_1y >= 60.0: m_score += 5.0
            elif wr_1y >= 50.0: m_score += 3.0
        quad = refl.get("quadrant", 0)
        if quad in [1, 2]: m_score += 3.0 # 主升或恐慌筑底回升
        elif quad == 4: m_score += 1.5

        # 3.2 相对 SPY Alpha 与均线 (6分)
        alpha_3m = refl.get("momentum_and_alpha", {}).get("alpha_vs_spy_3m_pct", 0.0) or 0.0
        if alpha_3m > 10.0: m_score += 3.0
        elif alpha_3m > 0.0: m_score += 2.0
        if "多头" in refl.get("momentum_and_alpha", {}).get("ma_alignment", ""): m_score += 3.0
        elif "整理" in refl.get("momentum_and_alpha", {}).get("ma_alignment", ""): m_score += 1.5

        # 3.3 RSI 健康区间 (4分)
        rsi = refl.get("momentum_and_alpha", {}).get("rsi_14", 50.0) or 50.0
        if 40.0 <= rsi <= 65.0: m_score += 4.0
        elif 30.0 <= rsi < 40.0: m_score += 3.0 # 超卖低估区

        m_score = min(20.0, max(0.0, m_score))

        # 4. 维度四：筹码与期权微观分 (Positioning, 满分 15 分)
        p_score = 0.0
        opt = refl.get("options", {})
        mp = opt.get("max_pain_price", np.nan)
        if pd.notna(mp) and pd.notna(curr_p) and curr_p > 0:
            if curr_p <= mp: p_score += 5.0 # 做市商向上拉扯引力
            else: p_score += 2.5
        pcr = opt.get("pcr_oi", np.nan)
        if pd.notna(pcr):
            if 0.7 <= pcr <= 1.2: p_score += 5.0 # 均衡健康
            elif pcr > 1.2: p_score += 3.5 # 悲观过度对冲
        short_f = refl.get("short_interest", {}).get("short_percent_of_float", np.nan)
        if pd.notna(short_f):
            if short_f < 0.06: p_score += 5.0
            elif short_f < 0.12: p_score += 3.0
        else:
            p_score += 3.5

        p_score = min(15.0, max(0.0, p_score))

        # 5. 维度五：基本面健康度与财报催化 (Health & Catalyst, 满分 10 分)
        h_score = 0.0
        f_val = fund.get("piotroski_f_score", 5) or 5
        h_score += min(7.0, (f_val / 9.0) * 7.0)
        if bool(self.earnings_guidance.get("official_8k_guidance_text")): h_score += 3.0

        total_score = round(q_score + v_score + m_score + p_score + h_score, 1)

        # 评级映射
        if total_score >= 80.0: rating = "STRONG BUY (强烈买入 / 核心重仓)"
        elif total_score >= 68.0: rating = "ACCUMULATE (分批增持 / 逢低布局)"
        elif total_score >= 52.0: rating = "HOLD (持有观望 / 中枢平衡)"
        elif total_score >= 38.0: rating = "TRIM (逢高减仓 / 防御收缩)"
        else: rating = "AVOID (回避 / 破位清仓)"

        # 6. 反锚定左右侧双轨制执行网格 (Dual-Track Price Grids)
        # 轨道一：左侧内在价值安全边际网格 (Value Entry - 不受即期现价锚定漂移)
        safety_line = val.get("dcf_post_sbc_adj", {}).get("mos_safety_price_20pct", np.nan)
        if pd.isna(safety_line) or safety_line <= 0:
            safety_line = val.get("ps_band_5y", {}).get("minus_1sigma_price", np.nan)

        bear_floor = val.get("stress_test_floor_price", np.nan)
        if pd.isna(bear_floor) or bear_floor <= 0:
            bear_floor = safety_line * 0.85 if pd.notna(safety_line) else curr_p * 0.75

        # 轨道二：右侧战术动量与相空间突破网格 (Momentum Entry)
        s20 = refl.get("momentum_and_alpha", {}).get("sma_20", np.nan)
        s200 = refl.get("momentum_and_alpha", {}).get("sma_200", np.nan)
        tactical_entry = max(s20, s200) if (pd.notna(s20) and pd.notna(s200)) else curr_p
        atr_stop = refl.get("momentum_and_alpha", {}).get("atr_stop_loss_price", curr_p * 0.92)

        is_divergent = bool(pd.notna(safety_line) and curr_p > (safety_line * 1.15))

        return {
            "total_quant_score": total_score,
            "quant_rating": rating,
            "pillars_breakdown": {
                "quality_score_30": round(q_score, 1),
                "valuation_score_25": round(v_score, 1),
                "momentum_score_20": round(m_score, 1),
                "positioning_score_15": round(p_score, 1),
                "health_score_10": round(h_score, 1)
            },
            "dual_track_execution": {
                "track_1_value_grid": {
                    "safety_buy_line": round(safety_line, 2) if pd.notna(safety_line) else np.nan,
                    "bear_case_floor": round(bear_floor, 2) if pd.notna(bear_floor) else np.nan,
                    "principle": "反现价锚定：严格由扣SBC后DCF公允价×0.8或估值底托硬性决定，股价跌破安全线分批网格吸筹，无视均线破位。"
                },
                "track_2_momentum_grid": {
                    "tactical_entry_price": round(tactical_entry, 2) if pd.notna(tactical_entry) else np.nan,
                    "dynamic_atr_stop_loss": round(atr_stop, 2) if pd.notna(atr_stop) else np.nan,
                    "is_momentum_divergent": is_divergent,
                    "divergence_warning": "⚠️ 当前市价显著高于左侧内在安全建仓线 (>15%)，右侧买入属于高溢价趋势博弈，缺乏内在价值安全垫，一旦跌破 2xATR 止损位必须机械平仓！" if is_divergent else "✅ 当前市价靠近左侧安全边际，动量交易具备较强安全垫保护。"
                }
            }
        }

    # =========================================================================
    # 汇总输出：生成给 Gemini 与网页端的标准化全景量化底稿 (JSON + Markdown)
    # =========================================================================
    def run_full_analysis(self) -> Dict[str, Any]:
        """执行完整量化分析与排雷体系并保存产出"""
        print(f"==================================================================")
        print(f"⚙️ 启动 {self.ticker} 机构级基本面排雷与情绪量化精算引擎 (GeminiSkills 融合版)...")
        print(f"==================================================================")

        # 1. 基本面质量与排雷
        fund_res = self.analyze_fundamental_quality_and_forensics()

        # 2. 估值、前置核验与反锚定 DCF
        val_res = self.analyze_valuation_and_expectations_gap()

        # 3. 反身性相空间、微观动量与期权情绪
        refl_res = self.analyze_reflexivity_and_sentiment()

        # 4. 历史相似胜率回溯
        backtest_res = self.calculate_historical_analogue_win_rates(refl_res.get("df_radar"))

        # 5. 五维 100 分量化评分卡与双轨制价格网格
        scoring_res = self.calculate_multi_factor_score_and_dual_track(fund_res, val_res, refl_res, backtest_res)

        # 组装总决算 JSON
        dossier_data = {
            "meta": {
                "ticker": self.ticker,
                "analysis_time": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "latest_price": self._get_latest_price(),
                "company_name": self.market_snapshot.get("profile", {}).get("shortName", self.ticker),
                "sector": self.market_snapshot.get("profile", {}).get("sector", "N/A"),
                "industry": self.market_snapshot.get("profile", {}).get("industry", "N/A"),
                "company_archetype": val_res.get("company_archetype", "WHITE_CHIP_COMPOUNDER"),
                "archetype_name": val_res.get("archetype_name", "稳健白马/现金牛成长模式")
            },
            "preflight_audit_card": val_res.get("preflight_audit", {}),
            "multi_factor_scoring_and_rating": scoring_res,
            "fundamental_quality_and_forensics": fund_res,
            "valuation_and_expectations_gap": val_res,
            "reflexivity_phase_space": {
                "quadrant": refl_res["quadrant"],
                "quadrant_name": refl_res["quadrant_name"],
                "composite_score": refl_res["composite_score"],
                "q1_dist_200ma_pct": refl_res["q1_pos_dist200"],
                "q1_dot_velocity": refl_res["q1_dot_velocity"],
                "v_dot_lyapunov": refl_res["v_dot_lyapunov"],
                "reflexive_gap": refl_res["reflexive_gap"],
                "active_triggers": refl_res["active_triggers"],
                "options_sentiment": refl_res["options"],
                "short_interest": refl_res["short_interest"],
                "momentum_and_alpha": refl_res.get("momentum_and_alpha", {})
            },
            "historical_analogue_backtest": {
                "has_analogues": backtest_res["has_analogues"],
                "sample_count": backtest_res["sample_count"],
                "sample_dates_sample": backtest_res["sample_dates"][:6],
                "horizon_3m": backtest_res["horizon_3m"],
                "horizon_6m": backtest_res["horizon_6m"],
                "horizon_12m": backtest_res["horizon_12m"]
            },
            "earnings_guidance_snapshot": {
                "has_guidance": bool(self.earnings_guidance.get("official_8k_guidance_text")),
                "guidance_excerpt": self.earnings_guidance.get("official_8k_guidance_text", "")[:1200]
            }
        }

        # 写入 JSON 底稿
        json_path = os.path.join(self.output_dir, f"{self.ticker}_quant_dossier.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(dossier_data, f, ensure_ascii=False, indent=2)

        # 生成精炼 Markdown 投研底稿 (专门供 Gemini 读取)
        md_path = os.path.join(self.output_dir, f"{self.ticker}_gemini_context.md")
        self._generate_gemini_markdown_context(dossier_data, md_path)

        print(f"==================================================================")
        print(f"✅ {self.ticker} 量化精算底稿生成完毕！")
        print(f"   - 结构化 JSON 数据集: {json_path}")
        print(f"   - 高信噪比 Gemini 专用投研底稿: {md_path}")
        print(f"==================================================================")
        return dossier_data

    def _generate_gemini_markdown_context(self, d: Dict[str, Any], output_path: str):
        """生成格式规范、信息密度极高的新版买方投研底稿"""
        m = d["meta"]
        audit = d.get("preflight_audit_card", {})
        score = d.get("multi_factor_scoring_and_rating", {})
        pillars = score.get("pillars_breakdown", {})
        dt = score.get("dual_track_execution", {})
        f = d["fundamental_quality_and_forensics"]
        v = d["valuation_and_expectations_gap"]
        r = d["reflexivity_phase_space"]
        ma = r.get("momentum_and_alpha", {})
        b = d["historical_analogue_backtest"]
        g = d["earnings_guidance_snapshot"]

        red_flags_str = "\n".join([f"- ⚠️ {flag}" for flag in f.get("red_flags", [])]) or "- 暂无机器初筛严重排雷警报"
        green_flags_str = "\n".join([f"- ✅ {flag}" for flag in f.get("green_flags", [])]) or "- 暂无突出优势标签"
        triggers_str = ", ".join(r.get("active_triggers", [])) or "近 20 日常态持仓，无极端拐点触发"

        b_3m = b.get("horizon_3m", {})
        b_6m = b.get("horizon_6m", {})
        b_12m = b.get("horizon_12m", {})

        # 敏感性矩阵 Markdown 表格
        matrix_md = ""
        if v.get("dcf_sensitivity_matrix_adj"):
            matrix_md = "| WACC \\ 永续增长率 $g_n$ | 2.0% | 2.5% | 3.0% |\n| :--- | :--- | :--- | :--- |\n"
            for row in v["dcf_sensitivity_matrix_adj"]:
                matrix_md += f"| **{row.get('wacc_label')}** | ${row.get('gn_2.0%', 'N/A')} | **${row.get('gn_2.5%', 'N/A')}** | ${row.get('gn_3.0%', 'N/A')} |\n"

        md_content = f"""# 【{m['ticker']}】多源量化精算与排雷档案 (Gemini 投研专用底稿 · 升级版)

> **标的名称**：{m['company_name']} ({m['ticker']})  
> **所属板块**：{m['sector']} | **细分行业**：{m['industry']}  
> **商业模式分流**：`{m['archetype_name']} ({m['company_archetype']})`  
> **数据时间戳**：`{m['analysis_time']}` | **最新股价**：`${m['latest_price']:.2f}`  

---

## 零、 估值前置参数核验卡与五维量化总分 (Pre-Flight Audit & Quant Rating)
* **无风险利率 Rf (10Y美债)**：`{audit.get('rf_10y_treasury_pct', 'N/A')}%` | **调整后 Beta**：`{audit.get('beta_adjusted', 'N/A')}` | **股权溢价 ERP**：`{audit.get('erp_pct', 'N/A')}%`
* **股权成本 Re**：`{audit.get('cost_of_equity_re_pct', 'N/A')}%` | **债务成本 Rd**：`{audit.get('cost_of_debt_rd_pct', 'N/A')}%` | **动态合成 WACC**：`{audit.get('wacc_dynamic_pct', 'N/A')}%`
* **稀释后总股本**：`{audit.get('diluted_shares_m', 'N/A')} M` | **总市值**：`${audit.get('market_cap_b', 'N/A')} B`
* **【五维量化多因子总分】**：**`{score.get('total_quant_score', 'N/A')} / 100 分`**
* **【最终量化评级】**：**`{score.get('quant_rating', 'N/A')}`**
  * 质量分 (30%): `{pillars.get('quality_score_30', 'N/A')} / 30` | 估值分 (25%): `{pillars.get('valuation_score_25', 'N/A')} / 25`
  * 动量分 (20%): `{pillars.get('momentum_score_20', 'N/A')} / 20` | 筹码分 (15%): `{pillars.get('positioning_score_15', 'N/A')} / 15` | 健康分 (10%): `{pillars.get('health_score_10', 'N/A')} / 10`

---

## 一、 基本面质量、偿债安全与资本配置效率 (Forensic Audit & EVA)
* **最新申报期数**：`{f.get('recent_metrics', {}).get('period', 'N/A')}` (截至 `{f.get('recent_metrics', {}).get('date', 'N/A')}`)
* **TTM 滚动总营收**：`${f.get('ttm_revenues_b', 'N/A')} B` (单季: `${f.get('recent_metrics', {}).get('revenues_b', 'N/A')} B`)
* **TTM 归母净利润**：`${f.get('ttm_net_income_b', 'N/A')} B` (单季: `${f.get('recent_metrics', {}).get('net_income_b', 'N/A')} B`)
* **TTM 经营现金流 (OCF)**：`${f.get('ttm_ocf_b', 'N/A')} B` | **盈利含金量 (OCF/净利润)**：`{f.get('cash_conversion_ratio', 'N/A')}x`
* **【双口径 FCF 对比】**：
  * **标准 FCF (OCF - CapEx)**：`${f.get('ttm_std_fcf_b', 'N/A')} B` (Standard FCF Margin: `{f.get('std_fcf_margin', 'N/A')}%`)
  * **真实 Adj. FCF (扣除SBC)**：`${f.get('ttm_adj_fcf_b', 'N/A')} B` (True FCF Margin: `{f.get('true_fcf_margin', 'N/A')}%`)
  * **SBC 占 OCF 比重**：`{f.get('sbc_to_ocf_ratio', 'N/A')}%` | **SBC 占营收比重**：`{f.get('sbc_to_rev_ratio', 'N/A')}%`
* **偿债安全度与净杠杆**：
  * **净债务 (Net Debt)**：`${f.get('net_debt_b', 'N/A')} B` (`{"净现金状态 (Net Cash)" if f.get('is_net_cash') else "负债经营"}`)
  * **Net Debt / EBITDA**：`{f.get('net_debt_to_ebitda', 'N/A')}x` | **利息保障倍数**：`{f.get('interest_coverage', 'N/A')}x`
  * **现金跑道 (Cash Runway)**：`{f.get('cash_runway_quarters', 'N/A')} 个季度` (仅适用于失血转型期)
* **资本配置效率 (ROIC vs WACC)**：
  * **ROIC**：`{f.get('roic_pct', 'N/A')}%` vs **WACC**：`{audit.get('wacc_dynamic_pct', 'N/A')}%` (经济增加值利差: `{f.get('eva_spread_pct', 'N/A'):+}%`)
  * **真实净股份注销率 (Net Buyback Yield)**：`{f.get('net_buyback_yield_pct', 'N/A'):+}%` | **股息率**：`{f.get('dividend_yield_pct', 'N/A')}%` | **股东总回报率**：`{f.get('total_shareholder_yield_pct', 'N/A'):+}%`
* **营运排雷**：应收账款异动差 `{f.get('receivables_yoy_diff', 'N/A')}%` | 存货异动差 `{f.get('inventory_yoy_diff', 'N/A')}%` | 毛利率 8 季斜率 `{f.get('gross_margin_slope_8q', 'N/A')}%/季`
* **Piotroski F-Score 健康评分**：`{f.get('piotroski_f_score', 'N/A')} / 9`

### 🚩 机器排雷警报：
{red_flags_str}

### 🌟 核心优势标签：
{green_flags_str}

---

## 二、 反锚定双口径 DCF、估值通道与预期差模型 (Valuation Models)
* **反向 DCF 隐含 10 年 FCF 年化增速**：`{v.get('implied_fcf_cagr_10y', 'N/A')}%` vs 过去 3 年实际增速 `{v.get('hist_fcf_cagr_3y', 'N/A')}%` (预期差: `{v.get('expectations_gap', 'N/A'):+}%`)
* **当前估值状态定性**：`{v.get('valuation_status', 'N/A')}`
* **【三阶段正向 DCF 双口径公允价值】**：
  * **口径 A (标准 FCF)**：基准公允价 **`${v.get('dcf_standard', {}).get('dcf_fair_price', 'N/A')}`** | 20% 安全边际价 `${v.get('dcf_standard', {}).get('mos_safety_price_20pct', 'N/A')}`
  * **口径 B (全额扣除 SBC，买方核心基准)**：基准公允价 **`${v.get('dcf_post_sbc_adj', {}).get('dcf_fair_price', 'N/A')}`** | **20% 安全边际价 `${v.get('dcf_post_sbc_adj', {}).get('mos_safety_price_20pct', 'N/A')}`**
* **【Post-SBC Adj. FCF 3x3 敏感性矩阵】**：
{matrix_md}
* **5 年估值通道 (PE/PS Band)**：
  * **PE Band 分位**：`{v.get('pe_band_5y', {}).get('current_percentile_pct', 'N/A')}%` (均值PE: `{v.get('pe_band_5y', {}).get('mean_pe', 'N/A')}x`, -1σ: `${v.get('pe_band_5y', {}).get('minus_1sigma_price', 'N/A')}`)
  * **PS Band 分位**：`{v.get('ps_band_5y', {}).get('current_percentile_pct', 'N/A')}%` (均值PS: `{v.get('ps_band_5y', {}).get('mean_ps', 'N/A')}x`, -1σ: `${v.get('ps_band_5y', {}).get('minus_1sigma_price', 'N/A')}`)
  * **估值乘数重构压力测试底托价**：**`${v.get('stress_test_floor_price', 'N/A')}`**
* **市盈率 PE (TTM / Forward)**：`{v.get('trailing_pe', 'N/A')}x / {v.get('forward_pe', 'N/A')}x` | **华尔街目标均价**：`${v.get('analyst_target_mean', 'N/A')}` (空间: `{v.get('analyst_upside_pct', 'N/A'):+}%`)

---

## 三、 微观动量、相对 SPY Alpha、期权博弈与相空间动力学
* **均线形态**：`{ma.get('ma_alignment', 'N/A')}` (20D偏离: `{ma.get('bias_20d_pct', 'N/A'):+}%`, 200D偏离: `{ma.get('bias_200d_pct', 'N/A'):+}%`)
* **经典 12-1M 动量**：`{ma.get('mom_12_1_pct', 'N/A')}%` | **日线 RSI(14)**：`{ma.get('rsi_14', 'N/A')}`
* **相对大盘 SPY 超额收益**：1M Alpha `{ma.get('alpha_vs_spy_1m_pct', 'N/A'):+}%` | 3M Alpha `{ma.get('alpha_vs_spy_3m_pct', 'N/A'):+}%` | 6M Alpha `{ma.get('alpha_vs_spy_6m_pct', 'N/A'):+}%`
* **自适应波动率与跟踪止损**：14D ATR% `{ma.get('atr_pct', 'N/A')}%` | **动态 2xATR 止损参考位**：`${ma.get('atr_stop_loss_price', 'N/A')}`
* **相空间四象限归属**：`{r.get('quadrant_name', 'N/A')}` | **动力学雷达分**：`{r.get('composite_score', 'N/A')} 分`
* **李雅普诺夫导数 v_dot**：`{r.get('v_dot_lyapunov', 'N/A')}` | **反身性认知偏离度**：`{r.get('reflexive_gap', 'N/A')}`
* **期权市场微观情绪**：未平仓 PCR OI `{r.get('options_sentiment', {}).get('pcr_oi', 'N/A')}` | **Max Pain 痛点价**：`${r.get('options_sentiment', {}).get('max_pain_price', 'N/A')}`
* **做空拥挤度**：`{r.get('short_interest', {}).get('short_percent_of_float', 'N/A') * 100 if pd.notna(r.get('short_interest', {}).get('short_percent_of_float')) else 'N/A'}%` (回补天数: `{r.get('short_interest', {}).get('short_ratio_days_to_cover', 'N/A')} 天`)

---

## 四、 历史同构相空间状态回溯胜率与回撤表现 (Historical Analogues)
* **相似样本匹配数量**：`{b.get('sample_count', 0)} 个独立历史时点` (相似判定: 雷达分 ±12, 年线乖离同号且 ±10%)
* **未来 3 个月 (3M) 表现**：胜率 `{b_3m.get('win_rate_pct', 'N/A')}%` | 中位数收益 `{b_3m.get('median_ret_pct', 'N/A'):+}%` | 盈亏比 `{b_3m.get('profit_factor', 'N/A')}x`
* **未来 6 个月 (6M) 表现**：胜率 `{b_6m.get('win_rate_pct', 'N/A')}%` | 中位数收益 `{b_6m.get('median_ret_pct', 'N/A'):+}%` | 盈亏比 `{b_6m.get('profit_factor', 'N/A')}x`
* **未来 12 个月 (1Y) 表现**：胜率 `{b_12m.get('win_rate_pct', 'N/A')}%` | 中位数收益 `{b_12m.get('median_ret_pct', 'N/A'):+}%` | 期间最大回撤中位数 `-{abs(b_12m.get('max_dd_pct', 0.0)):.1f}%`

---

## 五、 反锚定左右侧双轨制建仓与风控执行价格网格 (Dual-Track Execution Grids)
* **【轨道一：左侧内在价值安全边际网格 (Value Track)】**：
  * **保守安全建仓线 (Safety Buy Line)**：**`${dt.get('track_1_value_grid', {}).get('safety_buy_line', 'N/A')}`** (DCF 扣SBC后公允价×0.8 或 估值底托)
  * **极端悲观底托线 (Bear Case Floor)**：**`${dt.get('track_1_value_grid', {}).get('bear_case_floor', 'N/A')}`** (乘数压缩压力测试价)
  * **执行原则**：只要公司 ROIC > WACC 且护城河稳固，跌破安全建仓线分批限价吸筹，无视短期均线破位。
* **【轨道二：右侧战术动量与相空间共振网格 (Momentum Track)】**：
  * **战术突破/回踩入场位**：**`${dt.get('track_2_momentum_grid', {}).get('tactical_entry_price', 'N/A')}`** (依托 20D/200D 均线或相空间切换)
  * **动态 2xATR 跟踪止损位**：**`${dt.get('track_2_momentum_grid', {}).get('dynamic_atr_stop_loss', 'N/A')}`**
  * **背离警示**：`{dt.get('track_2_momentum_grid', {}).get('divergence_warning', '')}`

---

## 六、 官方 8-K 业绩公告与电话会议管理层指引摘要 (Guidance Excerpt)
```text
{g.get('guidance_excerpt', '暂无官方指引原文')}
```
"""
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(md_content)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="个股机构级量化分析与排雷核心引擎 (GeminiSkills 融合版)")
    parser.add_argument("--ticker", type=str, default="NVDA", help="股票代码 (如 NVDA)")
    args = parser.parse_args()

    analyzer = StockQuantAnalyzer(ticker=args.ticker)
    analyzer.run_full_analysis()
