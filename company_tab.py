import sys
import os
import datetime
import json
import urllib.request
import re
import pandas as pd
import numpy as np
import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo

# ------------------------------------------------------------------
# 模块导入与热重载安全机制 (防止 Streamlit Cloud 模块缓存导致 ImportError)
# ------------------------------------------------------------------
try:
    import visualization
    from visualization import create_financial_trends_chart
except Exception:
    create_financial_trends_chart = None

HAS_PLOTLY = True

def format_large_number(val, prefix="$"):
    if val is None or pd.isna(val) or val == "" or val == "N/A":
        return "N/A"
    try:
        num = float(val)
        abs_num = abs(num)
        sign = "-" if num < 0 else ""
        if abs_num >= 1e12:
            return f"{sign}{prefix}{abs_num / 1e12:.2f} T"
        elif abs_num >= 1e9:
            return f"{sign}{prefix}{abs_num / 1e9:.2f} B"
        elif abs_num >= 1e6:
            return f"{sign}{prefix}{abs_num / 1e6:.2f} M"
        elif abs_num >= 1e3:
            return f"{sign}{prefix}{abs_num / 1e3:.2f} K"
        else:
            return f"{sign}{prefix}{abs_num:.2f}"
    except (ValueError, TypeError):
        return str(val)

def format_percent(val):
    if val is None or pd.isna(val) or val == "" or val == "N/A":
        return "N/A"
    try:
        num = float(val)
        return f"{num * 100:.2f}%" if abs(num) <= 1.0 else f"{num:.2f}%"
    except (ValueError, TypeError):
        return str(val)

def format_timestamp(ts):
    if not ts:
        return "近期"
    try:
        if isinstance(ts, (int, float)):
            dt = datetime.datetime.fromtimestamp(ts, tz=datetime.timezone.utc).astimezone(ZoneInfo("America/New_York"))
            return dt.strftime("%Y-%m-%d %H:%M EDT")
        elif isinstance(ts, str):
            dt = pd.to_datetime(ts).tz_convert(ZoneInfo("America/New_York"))
            return dt.strftime("%Y-%m-%d %H:%M EDT")
    except Exception:
        pass
    return str(ts)[:16]

# =====================================================================
# 1. 结构化新闻解析与富媒体卡片生成器
# =====================================================================
def parse_and_enrich_news(ticker_obj, ticker_symbol: str, company_name: str = ""):
    news_list = []
    
    # 1. 优先解析 yfinance 原生新闻
    if hasattr(ticker_obj, "news") and ticker_obj.news:
        try:
            for item in ticker_obj.news:
                if not isinstance(item, dict):
                    continue

                # 兼容新版 yfinance (0.2.40+) 的 nested content 结构
                content = item.get("content")
                if isinstance(content, dict):
                    title = content.get("title") or ""
                    pub_date = content.get("pubDate") or ""
                    provider_dict = content.get("provider") or {}
                    publisher = provider_dict.get("displayName") if isinstance(provider_dict, dict) else str(provider_dict)
                    
                    canonical_url = content.get("canonicalUrl") or {}
                    link = canonical_url.get("url") if isinstance(canonical_url, dict) else str(canonical_url)
                    if not link or link == "{}":
                        link = content.get("clickThroughUrl", {}).get("url") or "#"

                    if title:
                        news_list.append({
                            "title": title,
                            "publisher": publisher or "财经快讯",
                            "link": link,
                            "pub_time": format_timestamp(pub_date),
                            "relatedTickers": [ticker_symbol]
                        })
                        continue

                # 兼容老版 yfinance 的 flat 结构
                title = item.get("title")
                if title:
                    publisher = item.get("publisher") or "财经快讯"
                    link = item.get("link") or "#"
                    raw_ts = item.get("providerPublishTime")
                    pub_time = format_timestamp(raw_ts)
                    tickers = item.get("relatedTickers", [ticker_symbol])
                    news_list.append({
                        "title": title,
                        "publisher": publisher,
                        "link": link,
                        "pub_time": pub_time,
                        "relatedTickers": tickers
                    })
        except Exception as e:
            print(f"yfinance news parsing warning: {e}")

    # 2. 如果 yfinance 未能获取新闻，自动启用高可用 RSS 实时新闻引擎
    if not news_list:
        try:
            query = f"{ticker_symbol}+stock"
            if company_name and company_name != ticker_symbol:
                short_name = company_name.split()[0].replace(",", "")
                query = f"{short_name}+{ticker_symbol}+stock"
                
            rss_url = f"https://news.google.com/rss/search?q={query}&hl=en-US&gl=US&ceid=US:en"
            headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            req = urllib.request.Request(rss_url, headers=headers)
            with urllib.request.urlopen(req, timeout=5) as resp:
                xml_data = resp.read()
                root = ET.fromstring(xml_data)
                for item in root.findall(".//item")[:10]:
                    title = item.findtext("title") or ""
                    link = item.findtext("link") or "#"
                    pub_date = item.findtext("pubDate") or ""
                    source_elem = item.find("source")
                    publisher = source_elem.text if source_elem is not None else "Google News"

                    if " - " in title:
                        parts = title.rsplit(" - ", 1)
                        title = parts[0]
                        if publisher == "Google News":
                            publisher = parts[1]

                    if title:
                        news_list.append({
                            "title": title,
                            "publisher": publisher,
                            "link": link,
                            "pub_time": format_timestamp(pub_date),
                            "relatedTickers": [ticker_symbol]
                        })
        except Exception as e_rss:
            print(f"RSS news fallback warning: {e_rss}")

    return news_list

# =====================================================================
# 3. 过去 4-5 周期/年度核心财务报表全景解析器 (Multi-Period Statements)
# =====================================================================
def extract_multi_period_statements(ticker_obj):
    """
    抓取个股的季度与年度三大财务报表并生成完整的 12 项财务指标结构化透视表
    """
    q_inc = getattr(ticker_obj, 'quarterly_income_stmt', None)
    if q_inc is None or q_inc.empty:
        q_inc = getattr(ticker_obj, 'quarterly_financials', None)

    a_inc = getattr(ticker_obj, 'income_stmt', None)
    if a_inc is None or a_inc.empty:
        a_inc = getattr(ticker_obj, 'financials', None)

    q_bs = getattr(ticker_obj, 'quarterly_balance_sheet', None)
    a_bs = getattr(ticker_obj, 'balance_sheet', None)

    q_cf = getattr(ticker_obj, 'quarterly_cashflow', None)
    if q_cf is None or q_cf.empty:
        q_cf = getattr(ticker_obj, 'quarterly_cash_flow', None)

    a_cf = getattr(ticker_obj, 'cashflow', None)
    if a_cf is None or a_cf.empty:
        a_cf = getattr(ticker_obj, 'cash_flow', None)

    def _process(inc_df, bs_df, cf_df, is_quarterly=True):
        if inc_df is None or inc_df.empty:
            return pd.DataFrame(), pd.DataFrame()

        cols = [c for c in inc_df.columns]
        cols_sorted = sorted(cols)
        dates_str = [pd.to_datetime(c).strftime('%Y-%m' if is_quarterly else '%Y') if hasattr(c, 'strftime') else str(c)[:10] for c in cols_sorted]

        def _get_val(df, candidates, date_col):
            if df is None or df.empty:
                return np.nan
            target_col = None
            date_str_target = pd.to_datetime(date_col).strftime('%Y-%m-%d') if hasattr(date_col, 'strftime') else str(date_col)[:10]
            for c in df.columns:
                c_str = pd.to_datetime(c).strftime('%Y-%m-%d') if hasattr(c, 'strftime') else str(c)[:10]
                if c_str == date_str_target:
                    target_col = c
                    break
            if target_col is None:
                if date_col in df.columns:
                    target_col = date_col
                else:
                    return np.nan
            index_map = {str(idx).strip().lower(): idx for idx in df.index}
            for cand in candidates:
                cand_lower = cand.strip().lower()
                if cand_lower in index_map:
                    orig_k = index_map[cand_lower]
                    try:
                        val = df.loc[orig_k, target_col]
                        if isinstance(val, pd.Series):
                            val = val.iloc[0]
                        if pd.notna(val) and val != '':
                            return float(val)
                    except Exception:
                        pass
            return np.nan

        rev_list, gp_list, op_inc_list, net_inc_list = [], [], [], []
        eps_list, cfo_list, capex_list, fcf_list = [], [], [], []
        cash_list, debt_list, eq_list = [], [], []

        for col in cols_sorted:
            r = _get_val(inc_df, ['Total Revenue', 'Operating Revenue', 'Revenue', 'Gross Sales', 'Total Net Revenue'], col)
            rev_list.append(r)
            gp = _get_val(inc_df, ['Gross Profit', 'Gross Margin'], col)
            gp_list.append(gp)
            op = _get_val(inc_df, ['Operating Income', 'Operating Profit', 'EBIT', 'Operating Revenue'], col)
            op_inc_list.append(op)
            ni = _get_val(inc_df, ['Net Income Common Stockholders', 'Net Income', 'Net Income From Continuing Operation Net Minority Interest'], col)
            net_inc_list.append(ni)
            eps = _get_val(inc_df, ['Diluted EPS', 'Basic EPS', 'Diluted Average Shares'], col)
            eps_list.append(eps)

            cfo = _get_val(cf_df, ['Operating Cash Flow', 'Cash Flowsfromusedin Operating Activities', 'Cash Flow From Continuing Operating Activities'], col)
            cfo_list.append(cfo)
            capex = _get_val(cf_df, ['Capital Expenditure', 'Capital Expenditures', 'Purchase Of Property Plant And Equipment'], col)
            capex_list.append(capex)
            fcf = _get_val(cf_df, ['Free Cash Flow'], col)
            if np.isnan(fcf) and not np.isnan(cfo):
                fcf = cfo - (abs(capex) if not np.isnan(capex) else 0.0)
            fcf_list.append(fcf)

            cash = _get_val(bs_df, ['Cash Cash Equivalents And Short Term Investments', 'Cash And Cash Equivalents', 'Cash Financial'], col)
            cash_list.append(cash)
            debt = _get_val(bs_df, ['Total Debt', 'Long Term Debt And Capital Securities', 'Current Debt And Capital Lease Obligation'], col)
            debt_list.append(debt)
            eq = _get_val(bs_df, ['Stockholders Equity', 'Common Stock Equity', 'Total Equity Gross Minority Interest'], col)
            eq_list.append(eq)

        summary_records = []
        
        # 1. 营收
        row_rev = {"指标 (Metric)": "营业总收入 (Total Revenue)"}
        for d, r in zip(dates_str, rev_list):
            row_rev[d] = f"${r/1e9:,.2f} B" if not np.isnan(r) else "N/A"
        summary_records.append(row_rev)

        # 2. 营收同比增速
        row_growth = {"指标 (Metric)": "营收同比增速 (YoY Growth)"}
        for i, d in enumerate(dates_str):
            lag = 4 if is_quarterly else 1
            if i >= lag and not np.isnan(rev_list[i]) and not np.isnan(rev_list[i-lag]) and rev_list[i-lag] != 0:
                g = (rev_list[i] - rev_list[i-lag]) / abs(rev_list[i-lag]) * 100
                row_growth[d] = f"{g:+.2f}%"
            else:
                row_growth[d] = "N/A"
        summary_records.append(row_growth)

        # 3. 毛利润 & 毛利率
        row_gp = {"指标 (Metric)": "毛利润 (Gross Profit)"}
        row_gm = {"指标 (Metric)": "毛利率 (Gross Margin %)"}
        for d, gp, r in zip(dates_str, gp_list, rev_list):
            row_gp[d] = f"${gp/1e9:,.2f} B" if not np.isnan(gp) else "N/A"
            row_gm[d] = f"{(gp/r)*100:.2f}%" if not np.isnan(gp) and not np.isnan(r) and r != 0 else "N/A"
        summary_records.append(row_gp)
        summary_records.append(row_gm)

        # 4. 营业利润 & 营业利润率
        row_op = {"指标 (Metric)": "营业利润 (Operating Income / EBIT)"}
        row_opm = {"指标 (Metric)": "营业利润率 (Operating Margin %)"}
        for d, op, r in zip(dates_str, op_inc_list, rev_list):
            row_op[d] = f"${op/1e9:,.2f} B" if not np.isnan(op) else "N/A"
            row_opm[d] = f"{(op/r)*100:.2f}%" if not np.isnan(op) and not np.isnan(r) and r != 0 else "N/A"
        summary_records.append(row_op)
        summary_records.append(row_opm)

        # 5. 净利润 & 净利率
        row_ni = {"指标 (Metric)": "净利润 (Net Income)"}
        row_npm = {"指标 (Metric)": "净利润率 (Net Margin %)"}
        for d, ni, r in zip(dates_str, net_inc_list, rev_list):
            row_ni[d] = f"${ni/1e9:,.2f} B" if not np.isnan(ni) else "N/A"
            row_npm[d] = f"{(ni/r)*100:.2f}%" if not np.isnan(ni) and not np.isnan(r) and r != 0 else "N/A"
        summary_records.append(row_ni)
        summary_records.append(row_npm)

        # 6. 稀释 EPS
        row_eps = {"指标 (Metric)": "稀释每股收益 (Diluted EPS)"}
        for d, eps in zip(dates_str, eps_list):
            row_eps[d] = f"${eps:.2f}" if not np.isnan(eps) else "N/A"
        summary_records.append(row_eps)

        # 7. 现金流
        row_cfo = {"指标 (Metric)": "经营活动现金流 (Operating Cash Flow)"}
        row_fcf = {"指标 (Metric)": "自由现金流 (Free Cash Flow)"}
        row_fcfm = {"指标 (Metric)": "自由现金流转化率 (FCF Margin %)"}
        for d, cfo, fcf, r in zip(dates_str, cfo_list, fcf_list, rev_list):
            row_cfo[d] = f"${cfo/1e9:,.2f} B" if not np.isnan(cfo) else "N/A"
            row_fcf[d] = f"${fcf/1e9:,.2f} B" if not np.isnan(fcf) else "N/A"
            row_fcfm[d] = f"{(fcf/r)*100:.2f}%" if not np.isnan(fcf) and not np.isnan(r) and r != 0 else "N/A"
        summary_records.append(row_cfo)
        summary_records.append(row_fcf)
        summary_records.append(row_fcfm)

        # 8. 资产负债
        row_cash = {"指标 (Metric)": "现金及短期投资 (Cash & Short Term Inv.)"}
        row_debt = {"指标 (Metric)": "总负债 (Total Debt)"}
        row_eq = {"指标 (Metric)": "股东权益 / 净资产 (Stockholders' Equity)"}
        for d, cash, debt, eq in zip(dates_str, cash_list, debt_list, eq_list):
            row_cash[d] = f"${cash/1e9:,.2f} B" if not np.isnan(cash) else "N/A"
            row_debt[d] = f"${debt/1e9:,.2f} B" if not np.isnan(debt) else "N/A"
            row_eq[d] = f"${eq/1e9:,.2f} B" if not np.isnan(eq) else "N/A"
        summary_records.append(row_cash)
        summary_records.append(row_debt)
        summary_records.append(row_eq)

        df_summary = pd.DataFrame(summary_records)
        seen = set()
        unique_dates_reversed = []
        for d in reversed(dates_str):
            if d not in seen:
                seen.add(d)
                unique_dates_reversed.append(d)
        df_summary = df_summary[["指标 (Metric)"] + unique_dates_reversed]

        df_trends = pd.DataFrame({
            "Period": dates_str,
            "Revenue ($M)": [r/1e6 if not np.isnan(r) else 0.0 for r in rev_list],
            "Gross Margin (%)": [(gp/r)*100 if not np.isnan(gp) and not np.isnan(r) and r != 0 else np.nan for gp, r in zip(gp_list, rev_list)],
            "Operating Margin (%)": [(op/r)*100 if not np.isnan(op) and not np.isnan(r) and r != 0 else np.nan for op, r in zip(op_inc_list, rev_list)],
            "Net Margin (%)": [(ni/r)*100 if not np.isnan(ni) and not np.isnan(r) and r != 0 else np.nan for ni, r in zip(net_inc_list, rev_list)],
            "Net Income ($M)": [ni/1e6 if not np.isnan(ni) else 0.0 for ni in net_inc_list],
            "Operating Cash Flow ($M)": [cfo/1e6 if not np.isnan(cfo) else 0.0 for cfo in cfo_list],
            "CapEx ($M)": [capex/1e6 if not np.isnan(capex) else 0.0 for capex in capex_list],
            "Free Cash Flow ($M)": [f/1e6 if not np.isnan(f) else 0.0 for f in fcf_list],
            "R&D Expenses ($M)": [0.0]*len(dates_str),
            "R&D / Rev (%)": [0.0]*len(dates_str)
        })

        return df_summary, df_trends

    q_sum, q_trend = _process(q_inc, q_bs, q_cf, is_quarterly=True)
    a_sum, a_trend = _process(a_inc, a_bs, a_cf, is_quarterly=False)

    return {
        "q_summary": q_sum,
        "q_trends": q_trend,
        "a_summary": a_sum,
        "a_trends": a_trend
    }

# =====================================================================
# 4. 单季度 P&L 支出拆解与瀑布流数据生成器
# =====================================================================
def extract_single_quarter_pnl(ticker_obj, info: dict):
    stmt_df = None
    period_label = "最新季度财报"

    try:
        q_inc = getattr(ticker_obj, 'quarterly_income_stmt', None)
        if q_inc is not None and not q_inc.empty:
            stmt_df = q_inc
            period_label = "最新季度财报"
        else:
            q_inc_alt = getattr(ticker_obj, 'quarterly_financials', None)
            if q_inc_alt is not None and not q_inc_alt.empty:
                stmt_df = q_inc_alt
                period_label = "最新季度财报"
    except Exception:
        pass

    if stmt_df is None or stmt_df.empty:
        try:
            a_inc = getattr(ticker_obj, 'income_stmt', None)
            if a_inc is not None and not a_inc.empty:
                stmt_df = a_inc
                period_label = "最新财年财报"
            else:
                a_inc_alt = getattr(ticker_obj, 'financials', None)
                if a_inc_alt is not None and not a_inc_alt.empty:
                    stmt_df = a_inc_alt
                    period_label = "最新财年财报"
        except Exception:
            pass

    if stmt_df is not None and not stmt_df.empty:
        valid_cols = [c for c in stmt_df.columns if stmt_df[c].dropna().count() >= 3]
        latest_col = valid_cols[0] if valid_cols else stmt_df.columns[0]
        latest_date_str = pd.to_datetime(latest_col).strftime("%Y-%m-%d") if hasattr(latest_col, 'strftime') else str(latest_col)[:10]

        index_map = {str(idx).lower().strip().replace("_", " "): idx for idx in stmt_df.index}

        def get_val(aliases):
            if isinstance(aliases, str):
                aliases = [aliases]
            for a in aliases:
                norm_a = a.lower().strip().replace("_", " ")
                if norm_a in index_map:
                    orig_k = index_map[norm_a]
                    try:
                        v = stmt_df.loc[orig_k, latest_col]
                        if isinstance(v, pd.Series):
                            v = v.iloc[0]
                        if pd.notna(v) and v != 0 and v != "":
                            return float(v)
                    except Exception:
                        date_str_tgt = pd.to_datetime(latest_col).strftime('%Y-%m-%d') if hasattr(latest_col, 'strftime') else str(latest_col)[:10]
                        for c in stmt_df.columns:
                            if (pd.to_datetime(c).strftime('%Y-%m-%d') if hasattr(c, 'strftime') else str(c)[:10]) == date_str_tgt:
                                try:
                                    v = stmt_df.loc[orig_k, c]
                                    if isinstance(v, pd.Series):
                                        v = v.iloc[0]
                                    if pd.notna(v) and v != 0 and v != "":
                                        return float(v)
                                except Exception:
                                    pass
            return 0.0

        total_rev = get_val([
            "Total Revenue", "Operating Revenue", "Revenue", "Gross Sales",
            "Total Net Revenue", "Net Interest Income", "Interest And Dividend Income",
            "Total Revenues", "Revenues", "Net Revenue", "Gross Revenue"
        ])

        if total_rev > 0:
            cogs = get_val([
                "Cost Of Revenue", "Reconciled Cost Of Revenue", "Cost of Goods Sold",
                "Cost of Goods and Services Sold", "Cost of Services", "Policyholder Benefits And Claims",
                "Net Policyholder Claims And Benefits", "Benefits Losses And Expenses", "Operating Expense"
            ])

            gross_profit = get_val(["Gross Profit", "Gross Margin"])
            if gross_profit == 0.0 and cogs > 0:
                gross_profit = total_rev - cogs

            rd = get_val([
                "Research And Development", "Research & Development", "Research Development",
                "Research Development Expense", "Research and Development"
            ])

            sga = get_val([
                "Selling General And Administration", "Selling General & Administrative",
                "Selling General and Administrative Expense", "Selling General Administrative"
            ])
            if sga == 0.0:
                sm = get_val(["Selling And Marketing Expense", "Selling and Marketing", "Sales And Marketing", "Marketing Expense", "Sales & Marketing"])
                ga = get_val(["General And Administrative Expense", "General and Administrative", "Administrative Expense", "General Administrative", "General & Administrative"])
                sga = sm + ga

            non_interest_exp = get_val([
                "Non Interest Expense", "Non-Interest Expense", "Total Noninterest Expense",
                "Salaries And Employee Benefits", "Other Non Interest Expense"
            ])
            credit_loss = get_val([
                "Provision For Credit Losses", "Provision For Loan Losses", "Credit Loss Provision"
            ])

            opex = get_val(["Operating Expense", "Total Operating Expenses", "Operating Expenses", "Total Operating Expense"])
            op_income = get_val(["Operating Income", "Operating Profit", "EBIT", "Operating Revenue", "Net Income Before Taxes", "Operating Gain Loss"])
            interest_exp = get_val(["Interest Expense", "Interest Expense Non Operating", "Total Interest Expense"])
            tax = get_val(["Tax Provision", "Provision For Income Tax", "Income Tax Expense", "Taxes", "Tax Expense"])
            net_inc = get_val([
                "Net Income", "Net Income Common Stockholders",
                "Net Income From Continuing Operation Net Minority Interest", "Net Income Including Noncontrolling Interests",
                "Net Income Continuous Operations"
            ])

            if op_income == 0.0:
                if opex > 0:
                    op_income = total_rev - cogs - opex
                elif net_inc != 0.0:
                    op_income = net_inc + tax + interest_exp

            expense_dict = {}
            if cogs > 0:
                expense_dict["营业成本 / 销货成本 (COGS)"] = cogs
            if rd > 0:
                expense_dict["研发支出 (R&D)"] = rd
            if sga > 0:
                expense_dict["销售与行政费用 (SG&A)"] = sga
            if non_interest_exp > 0 and sga == 0:
                expense_dict["非利息运营支出 (Non-Interest Exp.)"] = non_interest_exp
            if credit_loss > 0:
                expense_dict["信贷坏账拨备 (Credit Loss Provision)"] = credit_loss

            known_op = rd + sga + (non_interest_exp if sga == 0 else 0) + credit_loss
            if opex > known_op:
                other_op = opex - known_op
                if other_op > 0:
                    expense_dict["其他运营管理开支 (Other OpEx)"] = other_op
            elif (total_rev - cogs - op_income) > known_op:
                other_op = (total_rev - cogs - op_income) - known_op
                if other_op > 0:
                    expense_dict["其他运营开支 (Other OpEx)"] = other_op

            if not expense_dict and opex > 0:
                expense_dict["总营业与运营支出 (Total OpEx)"] = opex

            if tax > 0:
                expense_dict["所得税费用 (Income Tax)"] = tax
            if interest_exp > 0:
                expense_dict["利息支出 (Interest Expense)"] = interest_exp

            return {
                "source_type": period_label,
                "latest_date_str": f"{latest_date_str} ({period_label})",
                "total_revenue": total_rev,
                "cost_of_revenue": cogs,
                "gross_profit": gross_profit,
                "rd_expense": rd,
                "sga_expense": sga,
                "operating_income": op_income,
                "tax_provision": tax,
                "net_income": net_inc,
                "expense_dict": expense_dict
            }

    # 兜底：从 info TTM 重建
    if info and isinstance(info, dict):
        total_rev = float(info.get("totalRevenue") or 0.0)
        if total_rev > 0:
            gm = float(info.get("grossMargins") or 0.0)
            opm = float(info.get("operatingMargins") or 0.0)
            npm = float(info.get("profitMargins") or 0.0)

            gross_profit = total_rev * gm if gm > 0 else 0.0
            cogs = total_rev - gross_profit if gm > 0 else 0.0
            op_income = total_rev * opm if opm != 0 else 0.0
            net_inc = total_rev * npm if npm != 0 else 0.0
            total_opex = gross_profit - op_income if (gross_profit > 0 and op_income != 0) else max(0.0, total_rev - cogs - op_income)

            expense_dict = {}
            if cogs > 0:
                expense_dict["营业成本 / 销货成本 (COGS)"] = cogs
            if total_opex > 0:
                expense_dict["运营管理与研发开支 (Total Operating Expenses)"] = total_opex

            tax_or_other = max(0.0, op_income - net_inc) if op_income > net_inc else 0.0
            if tax_or_other > 0:
                expense_dict["所得税与非经常性项目 (Taxes & Other)"] = tax_or_other

            return {
                "source_type": "TTM 滚动近12个月财报 (基于官方指标核算)",
                "latest_date_str": "TTM 滚动近12个月 (官方财务数据归纳)",
                "total_revenue": total_rev,
                "cost_of_revenue": cogs,
                "gross_profit": gross_profit,
                "rd_expense": 0.0,
                "sga_expense": 0.0,
                "operating_income": op_income,
                "tax_provision": tax_or_other,
                "net_income": net_inc,
                "expense_dict": expense_dict
            }

    return {}

# =====================================================================
# 5. 主数据加载函数 (带缓存)
# =====================================================================
@st.cache_data(ttl=1800, show_spinner=False)
def fetch_company_data(ticker_symbol: str):
    try:
        import yfinance as yf
    except ImportError:
        return {"status": "error", "message": "未安装 yfinance 库，请在 requirements.txt 中添加 yfinance。"}

    ticker_symbol = ticker_symbol.strip().upper()
    try:
        ticker = yf.Ticker(ticker_symbol)
        info = ticker.info or {}

        if not info or ("shortName" not in info and "longName" not in info and "symbol" not in info):
            return {"status": "error", "message": f"未找到标的 `{ticker_symbol}` 的信息，请检查美股代码是否输入正确。"}

        company_name = info.get("shortName") or info.get("longName") or ticker_symbol
        statements_dict = extract_multi_period_statements(ticker)
        single_pnl = extract_single_quarter_pnl(ticker, info)
        news_list = parse_and_enrich_news(ticker, ticker_symbol, company_name)

        return {
            "status": "success",
            "info": info,
            "statements_dict": statements_dict,
            "single_pnl": single_pnl,
            "news_list": news_list,
            "company_name": company_name,
            "ticker_symbol": ticker_symbol
        }
    except Exception as e:
        return {"status": "error", "message": f"拉取数据发生异常: {str(e)}"}

# =====================================================================
# 6. Tab 4 主界面入口函数
# =====================================================================
def render_company_deep_dive_tab():
    st.header("🏢 公司画像与深度财报拆解分析 (Company Deep Dive & Financials)")
    st.markdown("全方位剖析公司主营业务构成、核心高管阵列、治理结构、P&L 利润流向瀑布图、多期财务明细与实时新闻动态。")

    # 美股代码搜索输入框
    col_input, _ = st.columns([1.5, 2.5])
    with col_input:
        default_sym = "NVDA"
        if "tab4_active_ticker" not in st.session_state:
            st.session_state["tab4_active_ticker"] = default_sym

        input_ticker = st.text_input(
            "输入美股代码 (Ticker):",
            value=st.session_state.get("tab4_active_ticker", default_sym),
            key="tab4_ticker_text_input"
        ).strip().upper()

        if input_ticker and input_ticker != st.session_state["tab4_active_ticker"]:
            st.session_state["tab4_active_ticker"] = input_ticker

    active_ticker = st.session_state.get("tab4_active_ticker", "NVDA")

    with st.spinner(f"正在全量解析 {active_ticker} 核心画像与财务三张表..."):
        data = fetch_company_data(active_ticker)

    if data.get("status") == "error":
        st.error(data.get("message"))
        return

    info = data["info"]
    company_name = data["company_name"]
    single_pnl = data["single_pnl"]
    statements_dict = data["statements_dict"]
    news_list = data["news_list"]

    # 1. 顶部基础画像 Card
    st.markdown(f"### 🏢 {company_name} ({active_ticker}) 核心概览")

    col_meta1, col_meta2, col_meta3, col_meta4 = st.columns(4)
    col_meta1.metric("当前实时股价", format_large_number(info.get("currentPrice") or info.get("regularMarketPrice")))
    col_meta2.metric("公司总市值", format_large_number(info.get("marketCap")))
    col_meta3.metric("滚动市盈率 (PE TTM)", f"{info.get('trailingPE'):.1f}x" if info.get('trailingPE') else "N/A")
    col_meta4.metric("动态市销率 (P/S TTM)", f"{info.get('priceToSalesTrailing12Months'):.2f}x" if info.get('priceToSalesTrailing12Months') else "N/A")

    st.markdown("---")

    # 2. 主营业务与公司商业模式
    st.markdown("### 📖 1. 商业模式与公司主营业务 (Business Profile)")
    col_desc, col_model = st.columns([1.6, 1])

    with col_desc:
        long_desc = info.get("longBusinessSummary", "暂无公司详细业务描述。")
        st.markdown(f"<div style='background-color:#f8fafc;padding:15px;border-radius:8px;border-left:4px solid #3b82f6;font-size:0.92rem;line-height:1.6;'>{long_desc}</div>", unsafe_allow_html=True)
        
        website = info.get("website", "")
        ir_url = info.get("irWebsite", "")
        links = []
        if website:
            links.append(f"🔗 [官方主页]({website})")
        if ir_url:
            links.append(f"📈 [投资者关系 (IR)]({ir_url})")
        if links:
            st.markdown(" | ".join(links))

    with col_model:
        sector = info.get("sector", "N/A")
        industry = info.get("industry", "N/A")
        currency = info.get("currency", "USD")
        st.markdown(
            f"""
            - **结算币种**: `{currency}`
            - **所属行业**: `{industry}`
            - **历史毛利率水平**: `{format_percent(info.get('grossMargins'))}`
            - **净利润率水平**: `{format_percent(info.get('profitMargins'))}`
            - **股息收益率**: `{format_percent(info.get('dividendYield'))}`
            - **总流通股本**: `{format_large_number(info.get('sharesOutstanding'), prefix='')}`
            """
        )

    st.markdown("---")

    # 3. 最新财报拆解：单期支出与成本构成 (自适应全行业)
    st.markdown("### 📊 2. 最新财报财务拆解：收入与支出构成 (Financial Breakdown)")

    if single_pnl and single_pnl.get("total_revenue", 0) > 0:
        latest_date_str = single_pnl["latest_date_str"]
        total_revenue = single_pnl["total_revenue"]
        cost_of_revenue = single_pnl["cost_of_revenue"]
        gross_profit = single_pnl["gross_profit"]
        rd_expense = single_pnl["rd_expense"]
        sga_expense = single_pnl["sga_expense"]
        operating_income = single_pnl["operating_income"]
        net_income = single_pnl["net_income"]
        expense_dict = single_pnl["expense_dict"]

        rev_base = total_revenue if total_revenue > 0 else 1.0

        st.info(f"📅 财务数据源: **{single_pnl.get('source_type', '最新财报')}** (核算基准: **{latest_date_str}**)")

        c_kpi1, c_kpi2, c_kpi3, c_kpi4, c_kpi5 = st.columns(5)
        c_kpi1.metric("期内总营收 (Revenue)", format_large_number(total_revenue))
        if gross_profit > 0:
            c_kpi2.metric("毛利率 (Gross Margin)", f"{(gross_profit / rev_base) * 100:.1f}%")
        else:
            c_kpi2.metric("毛利率 (Gross Margin)", "不适用 (金融/服务)")
        c_kpi3.metric("研发费用率 (R&D / Rev)", f"{(rd_expense / rev_base) * 100:.1f}%" if rd_expense > 0 else "无单独R&D")
        c_kpi4.metric("营业利润率 (Op Margin)", f"{(operating_income / rev_base) * 100:.1f}%" if operating_income != 0 else "N/A")
        c_kpi5.metric("净利润率 (Net Margin)", f"{(net_income / rev_base) * 100:.1f}%" if net_income != 0 else "N/A")

        col_charts_left, col_charts_right = st.columns([1, 1])

        # 1. 支出构成环形图
        with col_charts_left:
            st.markdown("#### 💰 支出与成本构成 (Expense Breakdown)")
            if expense_dict:
                df_exp = pd.DataFrame(list(expense_dict.items()), columns=["支出科目", "金额 ($)"])
                df_exp["占总营收比例"] = df_exp["金额 ($)"].apply(lambda x: f"{(x / rev_base) * 100:.1f}%")
                df_exp["格式化金额"] = df_exp["金额 ($)"].apply(format_large_number)

                if HAS_PLOTLY:
                    fig_donut = px.pie(
                        df_exp,
                        values="金额 ($)",
                        names="支出科目",
                        hole=0.45,
                        color_discrete_sequence=px.colors.qualitative.Pastel
                    )
                    fig_donut.update_traces(textposition='inside', textinfo='percent+label')
                    fig_donut.update_layout(margin=dict(t=10, b=10, l=10, r=10), showlegend=False, height=340)
                    st.plotly_chart(fig_donut, use_container_width=True)
                else:
                    st.bar_chart(df_exp.set_index("支出科目")["金额 ($)"])

                st.dataframe(df_exp[["支出科目", "格式化金额", "占总营收比例"]], use_container_width=True, hide_index=True)
            else:
                st.info("暂无可拆解的细分支出项。")

        # 2. 动态自适应利润流向瀑布图
        with col_charts_right:
            st.markdown("#### 🌊 营收至净利润流向瀑布图 (P&L Waterfall)")
            if HAS_PLOTLY and total_revenue > 0:
                wf_x = ["总营收"]
                wf_y = [total_revenue]
                wf_types = ["relative"]
                wf_text = [format_large_number(total_revenue)]

                for k, v in expense_dict.items():
                    if v > 0:
                        short_k = k.split("(")[0].strip() if "(" in k else k[:8]
                        wf_x.append(short_k)
                        wf_y.append(-v)
                        wf_types.append("relative")
                        wf_text.append(f"-{format_large_number(v)}")

                wf_x.append("净利润")
                wf_y.append(0)
                wf_types.append("total")
                wf_text.append(format_large_number(net_income))

                fig_wf = go.Figure(go.Waterfall(
                    name="P&L Flow",
                    orientation="v",
                    measure=wf_types,
                    x=wf_x,
                    textposition="outside",
                    text=wf_text,
                    y=wf_y,
                    connector={"line": {"color": "rgb(63, 63, 63)"}},
                    decreasing={"marker": {"color": "#ef4444"}},
                    increasing={"marker": {"color": "#10b981"}},
                    totals={"marker": {"color": "#3b82f6"}}
                ))
                fig_wf.update_layout(height=340, margin=dict(t=20, b=10, l=10, r=10), showlegend=False)
                st.plotly_chart(fig_wf, use_container_width=True)

            summary_table = [
                {"科目": "1. 营业总收入 (Total Revenue)", "金额": format_large_number(total_revenue), "占营收比重": "100.0%"}
            ]
            for exp_name, exp_val in expense_dict.items():
                summary_table.append({
                    "科目": f"扣除: {exp_name}",
                    "金额": f"-{format_large_number(exp_val)}",
                    "占营收比重": format_percent(exp_val / rev_base)
                })
            summary_table.append({
                "科目": "最终: 归母净利润 (Net Income)",
                "金额": format_large_number(net_income),
                "占营收比重": format_percent(net_income / rev_base)
            })
            st.dataframe(pd.DataFrame(summary_table), use_container_width=True, hide_index=True)
    else:
        st.warning("暂未获取到该公司的单期财务拆解数据。")

    st.markdown("---")

    # 4. 多季度/年度核心财务报表深度透视 (过去 4-5 期结构化总览与趋势图)
    st.markdown("### 📑 3. 核心财务报表深度透视 (季度与年度过去 4–5 期全量明细与趋势图)")
    st.caption("覆盖营业总收入、营收同比增速、毛利润/毛利率、营业利润 (EBIT)、净利润、稀释 EPS、经营现金流、自由现金流 (FCF) 与资产负债核心结构")

    if statements_dict:
        fin_tab_q, fin_tab_a = st.tabs(["📊 季度财务报表明细 (Quarterly Financials)", "📅 年度财务报表明细 (Annual Financials)"])

        with fin_tab_q:
            df_q_sum = statements_dict.get("q_summary")
            df_q_trend = statements_dict.get("q_trends")

            if df_q_sum is not None and not df_q_sum.empty:
                st.markdown("##### 季度核心财务指标精选总览 (最近 5 个季度)")
                st.dataframe(df_q_sum, hide_index=True, use_container_width=True)

                if df_q_trend is not None and not df_q_trend.empty and create_financial_trends_chart:
                    fig_q_trend = create_financial_trends_chart(df_q_trend, symbol=active_ticker, period_type="季度")
                    if fig_q_trend:
                        st.plotly_chart(fig_q_trend, use_container_width=True)
            else:
                st.info("暂无季度结构化多期财务报表数据。")

        with fin_tab_a:
            df_a_sum = statements_dict.get("a_summary")
            df_a_trend = statements_dict.get("a_trends")

            if df_a_sum is not None and not df_a_sum.empty:
                st.markdown("##### 年度核心财务指标精选总览 (最近 4 个财年)")
                st.dataframe(df_a_sum, hide_index=True, use_container_width=True)

                if df_a_trend is not None and not df_a_trend.empty and create_financial_trends_chart:
                    fig_a_trend = create_financial_trends_chart(df_a_trend, symbol=active_ticker, period_type="年度")
                    if fig_a_trend:
                        st.plotly_chart(fig_a_trend, use_container_width=True)
            else:
                st.info("暂无年度结构化多期财务报表数据。")
    else:
        st.info("未能提取该公司的多期财务报表明细。")

    st.markdown("---")

    # 5. 公司近期重要新闻动态 (带外链跳转)
    st.markdown("### 📰 4. 公司近期重要新闻与重大动态 (Key News & Market Catalysts)")

    if news_list and len(news_list) > 0:
        for item in news_list[:8]:
            title = item.get("title", "新闻标题未提供")
            publisher = item.get("publisher", "财经快讯")
            link = item.get("link", "#")
            pub_time = item.get("pub_time", "近期")
            related_symbols = item.get("relatedTickers", [active_ticker])
            symbols_tag = " ".join([f"`{s}`" for s in related_symbols[:4]])

            with st.container():
                st.markdown(f"**[{title}]({link})**")
                st.caption(f"🏛️ 来源: **{publisher}** | ⏰ 时间: `{pub_time}` | 🏷️ 标的: {symbols_tag}")
                st.markdown("")
    else:
        st.info("暂无近期重大公开新闻动态。")
