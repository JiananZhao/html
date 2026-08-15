"""
Company Profile & Financial Breakdown Tab for Streamlit App (Ultra-Robust Edition)
==================================================================================
Features:
- Dual-schema News Parser (supports both modern yfinance nested content and legacy flat news)
- Real-time RSS News Fallback (ensures news is never blank)
- Multi-tier Financial Statement Engine (Quarterly -> Annual -> ticker.info TTM reconstruction)
- Universal Industry Accounting (Tech, Manufacturing, Financials/Banks, Energy, REITs, ADRs)
- Dynamic Adaptive P&L Waterfall & Expense Donut Charts
"""

import streamlit as st
import pandas as pd
import numpy as np
import datetime
import urllib.request
import json
import xml.etree.ElementTree as ET

# 尝试导入金融与图表库（带容错回退）
try:
    import yfinance as yf
except ImportError:
    yf = None

try:
    import plotly.graph_objects as go
    import plotly.express as px
    HAS_PLOTLY = True
except ImportError:
    HAS_PLOTLY = False


# =====================================================================
# 1. 格式化工具函数
# =====================================================================
def format_large_number(val, prefix="$", precision=2):
    """格式化大额数字为 T/B/M/K 字符串"""
    if val is None or pd.isna(val) or val == 0:
        return "N/A"
    try:
        val = float(val)
        abs_val = abs(val)
        sign = "-" if val < 0 else ""
        if abs_val >= 1e12:
            return f"{sign}{prefix}{abs_val / 1e12:.{precision}f}T"
        elif abs_val >= 1e9:
            return f"{sign}{prefix}{abs_val / 1e9:.{precision}f}B"
        elif abs_val >= 1e6:
            return f"{sign}{prefix}{abs_val / 1e6:.{precision}f}M"
        elif abs_val >= 1e3:
            return f"{sign}{prefix}{abs_val / 1e3:.{precision}f}K"
        else:
            return f"{sign}{prefix}{abs_val:.{precision}f}"
    except Exception:
        return str(val)


def format_percent(val, is_ratio=True):
    """格式化百分比"""
    if val is None or pd.isna(val):
        return "N/A"
    try:
        val = float(val)
        if is_ratio and abs(val) <= 1.0:
            return f"{val * 100:.2f}%"
        return f"{val:.2f}%"
    except Exception:
        return str(val)


def format_timestamp(ts):
    """转换 Unix 时间戳或 ISO 字符串为友好日期格式"""
    if not ts:
        return "近期"
    try:
        if isinstance(ts, (int, float)):
            dt = datetime.datetime.fromtimestamp(ts)
            return dt.strftime("%Y-%m-%d %H:%M")
        return str(ts)[:16].replace("T", " ")
    except Exception:
        return str(ts)


# =====================================================================
# 2. 深度新闻解析器 (兼顾 yfinance 新老版本结构及 RSS 自动兜底)
# =====================================================================
def parse_and_enrich_news(ticker_obj, ticker_symbol: str, company_name: str = ""):
    """
    自适应解析 yfinance 嵌套/扁平结构新闻；若为空则自动触发实时 RSS 新闻流
    """
    news_list = []
    
    # 1. 尝试从 yfinance 提取并解析
    if ticker_obj:
        try:
            raw_news = ticker_obj.news or []
            for item in raw_news:
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
# 3. 多层级财务损益表提取引擎 (Multi-Tier P&L Engine)
# =====================================================================
def extract_robust_pnl_data(ticker_obj, info: dict):
    """
    三层容错财务提取架构：
    1. 优先提取最新季度利润表 (Quarterly Income Statement)
    2. 次选提取最新年度/已审利润表 (Annual Income Statement)
    3. 兜底通过 ticker.info 核心财务字段重建全量 P&L 结构与瀑布流
    """
    # -------------------------------------------------------------
    # 策略 1 & 2: 从 DataFrame 结构化财报中提取
    # -------------------------------------------------------------
    stmt_df = None
    period_label = "最新季度财报"

    try:
        # 尝试季度报表
        q_inc = ticker_obj.quarterly_income_stmt
        if q_inc is not None and not q_inc.empty and q_inc.shape[1] > 0:
            stmt_df = q_inc
            period_label = "最新季度财报"
        else:
            q_inc_alt = ticker_obj.quarterly_financials
            if q_inc_alt is not None and not q_inc_alt.empty:
                stmt_df = q_inc_alt
                period_label = "最新季度财报"
    except Exception:
        pass

    # 若季度报表为空，自动回退至年度利润表 (例如 TEAM 或财报归档窗口期的公司)
    if stmt_df is None or stmt_df.empty:
        try:
            a_inc = ticker_obj.income_stmt
            if a_inc is not None and not a_inc.empty:
                stmt_df = a_inc
                period_label = "最新财年财报 (Annual Financials)"
            else:
                a_inc_alt = ticker_obj.financials
                if a_inc_alt is not None and not a_inc_alt.empty:
                    stmt_df = a_inc_alt
                    period_label = "最新财年财报 (Annual Financials)"
        except Exception:
            pass

    # 如果成功获取到 DataFrame 表格，执行通用全行业科目提取
    if stmt_df is not None and not stmt_df.empty:
        # 寻找包含有效数字最多的最新一列
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
                    v = stmt_df.loc[orig_k, latest_col]
                    if pd.notna(v) and v != 0:
                        try:
                            return float(v)
                        except Exception:
                            pass
            return 0.0

        total_rev = get_val([
            "Total Revenue", "Operating Revenue", "Revenue", "Gross Sales",
            "Net Interest Income", "Interest And Dividend Income", "Total Net Revenue"
        ])

        if total_rev > 0:
            cogs = get_val([
                "Cost Of Revenue", "Reconciled Cost Of Revenue", "Cost of Goods Sold",
                "Cost of Goods and Services Sold", "Cost of Services", "Policyholder Benefits And Claims",
                "Net Policyholder Claims And Benefits", "Benefits Losses And Expenses"
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
                sm = get_val(["Selling And Marketing Expense", "Selling and Marketing", "Sales And Marketing", "Marketing Expense"])
                ga = get_val(["General And Administrative Expense", "General and Administrative", "Administrative Expense", "General Administrative"])
                sga = sm + ga

            non_interest_exp = get_val([
                "Non Interest Expense", "Non-Interest Expense", "Total Noninterest Expense",
                "Salaries And Employee Benefits", "Other Non Interest Expense"
            ])
            credit_loss = get_val([
                "Provision For Credit Losses", "Provision For Loan Losses", "Credit Loss Provision"
            ])

            opex = get_val(["Operating Expense", "Total Operating Expenses", "Operating Expenses"])
            op_income = get_val(["Operating Income", "Operating Profit", "EBIT", "Operating Revenue", "Net Income Before Taxes"])

            interest_exp = get_val(["Interest Expense", "Interest Expense Non Operating", "Total Interest Expense"])
            tax = get_val(["Tax Provision", "Provision For Income Tax", "Income Tax Expense", "Taxes"])
            net_inc = get_val([
                "Net Income", "Net Income Common Stockholders",
                "Net Income From Continuing Operation Net Minority Interest", "Net Income Including Noncontrolling Interests"
            ])

            if op_income == 0.0:
                if opex > 0:
                    op_income = total_rev - cogs - opex
                elif net_inc != 0.0:
                    op_income = net_inc + tax + interest_exp

            # 动态生成支出细分字典
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
                "expense_dict": expense_dict,
                "history_df": stmt_df
            }

    # -------------------------------------------------------------
    # 策略 3: 终极兜底方案 (从 ticker.info 的 TTM 财务指标中重建)
    # -------------------------------------------------------------
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
                "expense_dict": expense_dict,
                "history_df": pd.DataFrame()
            }

    return {}


# =====================================================================
# 4. 数据获取主函数 (带缓存)
# =====================================================================
@st.cache_data(ttl=1800, show_spinner=False)
def fetch_company_data(ticker_symbol: str):
    """
    通过 yfinance 获取公司核心概况、结构化财务与新闻资讯
    """
    if not yf:
        return {"status": "error", "message": "未安装 yfinance 库，请在 requirements.txt 中添加 yfinance。"}

    ticker_symbol = ticker_symbol.strip().upper()
    try:
        ticker = yf.Ticker(ticker_symbol)
        info = ticker.info or {}

        if not info or ("shortName" not in info and "longName" not in info and "symbol" not in info):
            return {"status": "error", "message": f"未找到标的代码 '{ticker_symbol}' 的有效数据，请核对代码拼写。"}

        company_name = info.get("longName") or info.get("shortName") or ticker_symbol

        # 解析新闻（自适应嵌套结构 + 自动 RSS 兜底）
        news_list = parse_and_enrich_news(ticker, ticker_symbol, company_name)

        # 多层级提取财务结构
        pnl_data = extract_robust_pnl_data(ticker, info)

        return {
            "status": "success",
            "info": info,
            "pnl_data": pnl_data,
            "news": news_list
        }
    except Exception as e:
        return {"status": "error", "message": f"数据获取异常: {str(e)}"}


# =====================================================================
# 5. 前端样式定义
# =====================================================================
def inject_custom_css():
    st.markdown(
        """
        <style>
        .company-header-card {
            background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
            border-radius: 12px;
            padding: 24px;
            margin-bottom: 20px;
            color: #ffffff;
            border: 1px solid #334155;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.2);
        }
        .metric-badge {
            display: inline-block;
            background-color: #3b82f6;
            color: #ffffff;
            font-size: 0.8rem;
            font-weight: 600;
            padding: 3px 10px;
            border-radius: 9999px;
            margin-right: 8px;
            margin-bottom: 6px;
        }
        .metric-badge-secondary {
            display: inline-block;
            background-color: #475569;
            color: #f1f5f9;
            font-size: 0.8rem;
            font-weight: 500;
            padding: 3px 10px;
            border-radius: 9999px;
            margin-right: 8px;
            margin-bottom: 6px;
        }
        .news-card {
            background-color: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 10px;
            padding: 16px 20px;
            margin-bottom: 12px;
            transition: all 0.2s ease-in-out;
            box-shadow: 0 1px 3px rgba(0,0,0,0.05);
        }
        .news-card:hover {
            border-color: #3b82f6;
            box-shadow: 0 4px 12px rgba(59, 130, 246, 0.15);
            transform: translateY(-2px);
        }
        .news-title {
            font-size: 1.02rem;
            font-weight: 600;
            color: #1e293b;
            text-decoration: none;
            display: block;
            margin-bottom: 6px;
        }
        .news-title:hover {
            color: #2563eb;
            text-decoration: underline;
        }
        .news-meta {
            font-size: 0.8rem;
            color: #64748b;
            display: flex;
            align-items: center;
            gap: 14px;
        }
        </style>
        """,
        unsafe_allow_html=True
    )


# =====================================================================
# 6. Tab 渲染核心主函数
# =====================================================================
def render_company_deep_dive_tab():
    inject_custom_css()

    st.markdown("## 🏢 个股深度与基本面剖析 (Company Profile & Financials)")
    st.caption("全景透视上市公司：公司档案、主营业务、最新季报收入与支出构成剖析、关键财务比率及实时新闻动态。")

    # 1. 搜索框与常用标的快捷切换
    if "selected_ticker" not in st.session_state:
        st.session_state["selected_ticker"] = "NVDA"

    col_input, col_quick = st.columns([1.2, 2.8])

    with col_input:
        search_input = st.text_input(
            "🔍 输入美股代码 (Ticker):",
            value=st.session_state["selected_ticker"],
            key="input_ticker_box",
            placeholder="例如: NVDA, AAPL, TEAM, JPM, TSM...",
            help="输入美股标的代码后按 Enter 键刷新数据"
        ).strip().upper()

        if search_input and search_input != st.session_state["selected_ticker"]:
            st.session_state["selected_ticker"] = search_input

    with col_quick:
        st.markdown("<div style='font-size:0.85rem; color:#64748b; margin-bottom:4px; font-weight:600;'>快捷热门标的:</div>", unsafe_allow_html=True)
        popular_tickers = ["NVDA", "AAPL", "MSFT", "TEAM", "AMAT", "TSM", "GOOGL", "AMZN", "META", "TSLA", "JPM", "COST"]
        quick_cols = st.columns(len(popular_tickers))
        for idx, sym in enumerate(popular_tickers):
            if quick_cols[idx].button(sym, key=f"quick_btn_{sym}", use_container_width=True):
                st.session_state["selected_ticker"] = sym
                st.rerun()

    active_ticker = st.session_state["selected_ticker"]

    # 2. 抓取数据
    with st.spinner(f"正在实时检索 {active_ticker} 的公司档案、财务损益表与新闻资讯..."):
        data = fetch_company_data(active_ticker)

    if data["status"] == "error":
        st.error(data["message"])
        return

    info = data["info"]
    pnl_data = data["pnl_data"]
    news_list = data["news"]

    # 3. 头部信息卡片与核心量化指标
    company_name = info.get("longName") or info.get("shortName") or active_ticker
    sector = info.get("sector", "N/A")
    industry = info.get("industry", "N/A")
    exchange = info.get("exchange", "N/A")
    currency = info.get("currency", "USD")
    website = info.get("website", "")
    city = info.get("city", "")
    country = info.get("country", "")
    employees = info.get("fullTimeEmployees")
    emp_str = f"{employees:,}" if employees else "N/A"
    location_str = f"{city}, {country}" if city and country else (city or country or "N/A")

    st.markdown(
        f"""
        <div class="company-header-card">
            <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap;">
                <div>
                    <h1 style="margin: 0; font-size: 1.8rem; font-weight: 700; color:#ffffff;">
                        {company_name} <span style="font-size: 1.3rem; color: #93c5fd;">({active_ticker})</span>
                    </h1>
                    <div style="margin-top: 10px;">
                        <span class="metric-badge">板块: {sector}</span>
                        <span class="metric-badge">行业: {industry}</span>
                        <span class="metric-badge-secondary">交易所: {exchange}</span>
                        <span class="metric-badge-secondary">总部: {location_str}</span>
                        <span class="metric-badge-secondary">员工规模: {emp_str}</span>
                    </div>
                </div>
                <div style="text-align: right; margin-top: 8px;">
                    {f'<a href="{website}" target="_blank" style="color: #60a5fa; text-decoration: none; font-size: 0.9rem; font-weight: 600; border: 1px solid #3b82f6; padding: 6px 14px; border-radius: 6px; background: rgba(59,130,246,0.1);">🌐 访问官网 ↗</a>' if website else ''}
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )

    market_cap = info.get("marketCap")
    current_price = info.get("currentPrice") or info.get("regularMarketPrice")
    trailing_pe = info.get("trailingPE")
    forward_pe = info.get("forwardPE")
    fifty_two_low = info.get("fiftyTwoWeekLow")
    fifty_two_high = info.get("fiftyTwoWeekHigh")
    beta = info.get("beta")

    m_col1, m_col2, m_col3, m_col4, m_col5, m_col6 = st.columns(6)
    m_col1.metric("当前股价", f"${current_price:.2f}" if current_price else "N/A")
    m_col2.metric("公司总市值", format_large_number(market_cap))
    m_col3.metric("滚动市盈率 (TTM PE)", f"{trailing_pe:.1f}x" if trailing_pe else "N/A")
    m_col4.metric("远期市盈率 (Fwd PE)", f"{forward_pe:.1f}x" if forward_pe else "N/A")
    m_col5.metric("52周价格区间", f"${fifty_two_low:.1f} - ${fifty_two_high:.1f}" if fifty_two_low and fifty_two_high else "N/A")
    m_col6.metric("Beta (波动系数)", f"{beta:.2f}" if beta else "N/A")

    st.markdown("---")

    # 4. 公司简介与业务内容
    st.markdown("### 📋 1. 公司简介与业务模式 (Business Operations)")
    summary_text = info.get("longBusinessSummary", "暂无该公司官方业务简介。")

    col_desc, col_model = st.columns([1.6, 1])
    with col_desc:
        st.markdown("**【核心业务简介】**")
        st.markdown(f"<div style='line-height: 1.7; color: #334155; text-align: justify;'>{summary_text}</div>", unsafe_allow_html=True)

    with col_model:
        st.markdown("**【基本面速览】**")
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

    # 5. 最新财报拆解：收入与支出构成 (自适应全行业)
    st.markdown("### 📊 2. 最新财报财务拆解：收入与支出构成 (Financial Breakdown)")

    if pnl_data and pnl_data.get("total_revenue", 0) > 0:
        latest_date_str = pnl_data["latest_date_str"]
        total_revenue = pnl_data["total_revenue"]
        cost_of_revenue = pnl_data["cost_of_revenue"]
        gross_profit = pnl_data["gross_profit"]
        rd_expense = pnl_data["rd_expense"]
        sga_expense = pnl_data["sga_expense"]
        operating_income = pnl_data["operating_income"]
        net_income = pnl_data["net_income"]
        expense_dict = pnl_data["expense_dict"]
        history_df = pnl_data.get("history_df", pd.DataFrame())

        rev_base = total_revenue if total_revenue > 0 else 1.0

        st.info(f"📅 财务数据源: **{pnl_data.get('source_type', '最新财报')}** (核算基准: **{latest_date_str}**)")

        # 核心比率卡片
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

        # 3. 历史多期趋势对比
        if history_df is not None and not history_df.empty and history_df.shape[1] > 1:
            with st.expander("📈 查看历史多期营收与利润演变趋势 (Historical Quarters Trend)"):
                dates = [col for col in history_df.columns]
                hist_data = []
                for d in dates[:6]:
                    d_str = pd.to_datetime(d).strftime("%Y-%m-%d") if hasattr(d, 'strftime') else str(d)[:10]
                    r = history_df.loc["Total Revenue", d] if "Total Revenue" in history_df.index else (history_df.loc["Operating Revenue", d] if "Operating Revenue" in history_df.index else 0)
                    op = history_df.loc["Operating Income", d] if "Operating Income" in history_df.index else 0
                    ni = history_df.loc["Net Income", d] if "Net Income" in history_df.index else (history_df.loc["Net Income Common Stockholders", d] if "Net Income Common Stockholders" in history_df.index else 0)
                    hist_data.append({
                        "报告期": d_str,
                        "总营收 ($)": float(r) if pd.notna(r) else 0,
                        "营业利润 ($)": float(op) if pd.notna(op) else 0,
                        "净利润 ($)": float(ni) if pd.notna(ni) else 0,
                    })
                df_hist = pd.DataFrame(hist_data).sort_values("报告期")
                st.line_chart(df_hist.set_index("报告期"))
    else:
        st.warning("暂未获取到该公司的财务报表数据，请稍后刷新或核对标的代码。")

    st.markdown("---")

    # 6. 公司近期重要新闻动态 (带外链跳转)
    st.markdown("### 📰 3. 公司近期重要新闻与重大动态 (Key News & Market Catalysts)")

    if news_list and len(news_list) > 0:
        for item in news_list[:8]:
            title = item.get("title", "新闻标题未提供")
            publisher = item.get("publisher", "财经快讯")
            link = item.get("link", "#")
            pub_time = item.get("pub_time", "近期")
            related_symbols = item.get("relatedTickers", [active_ticker])
            symbols_tag = " ".join([f"<span class='metric-badge-secondary'>{s}</span>" for s in related_symbols[:4]])

            st.markdown(
                f"""
                <div class="news-card">
                    <a href="{link}" target="_blank" class="news-title">{title} ↗</a>
                    <div class="news-meta">
                        <span>🏛️ 来源: <b>{publisher}</b></span>
                        <span>⏰ 时间: {pub_time}</span>
                        {f"<span>🏷️ 相关标的: {symbols_tag}</span>" if symbols_tag else ""}
                    </div>
                </div>
                """,
                unsafe_allow_html=True
            )
    else:
        st.info("暂未检索到该标的的近期新闻资讯。")
