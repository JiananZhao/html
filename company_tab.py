"""
Company Profile & Financial Breakdown Tab for Streamlit App (Universal Industry Version)
========================================================================================
Supports Tech, Manufacturing, Banks, Financial Services, Insurance, Energy, REITs & ADRs.
"""

import streamlit as st
import pandas as pd
import numpy as np
import datetime

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
    """转换 Unix 时间戳为友好日期格式"""
    if not ts:
        return "近期"
    try:
        if isinstance(ts, (int, float)):
            dt = datetime.datetime.fromtimestamp(ts)
            return dt.strftime("%Y-%m-%d %H:%M")
        return str(ts)[:16]
    except Exception:
        return str(ts)


# =====================================================================
# 2. 数据获取与缓存机制
# =====================================================================
@st.cache_data(ttl=1800, show_spinner=False)
def fetch_company_data(ticker_symbol: str):
    """
    通过 yfinance 获取公司核心概况、最新季度利润表与最新新闻
    """
    if not yf:
        return {"status": "error", "message": "未安装 yfinance 库，请在 requirements.txt 中添加 yfinance。"}

    ticker_symbol = ticker_symbol.strip().upper()
    try:
        ticker = yf.Ticker(ticker_symbol)
        info = ticker.info or {}

        if not info or ("shortName" not in info and "longName" not in info and "symbol" not in info):
            return {"status": "error", "message": f"未找到标的代码 '{ticker_symbol}' 的有效数据，请检查拼写。"}

        # 提取最新季度利润表
        try:
            q_income = ticker.quarterly_income_stmt
            if q_income is None or q_income.empty:
                q_income = ticker.quarterly_financials
        except Exception:
            q_income = pd.DataFrame()

        # 提取新闻
        try:
            news = ticker.news or []
        except Exception:
            news = []

        return {
            "status": "success",
            "info": info,
            "quarterly_income": q_income,
            "news": news
        }
    except Exception as e:
        return {"status": "error", "message": f"数据获取异常: {str(e)}"}


# =====================================================================
# 3. 前端样式增强
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
# 4. 全行业智能财务科目提取器 (Universal P&L Extractor)
# =====================================================================
def extract_universal_income_data(q_income: pd.DataFrame):
    """
    智能解析科技、制造、金融银行、保险、能源与公共事业等全行业损益表
    """
    if q_income is None or q_income.empty:
        return {}

    # 寻找包含最多非空数据的有效最新季度列
    valid_cols = [c for c in q_income.columns if q_income[c].dropna().count() > 3]
    latest_date = valid_cols[0] if valid_cols else q_income.columns[0]
    latest_date_str = pd.to_datetime(latest_date).strftime("%Y-%m-%d") if hasattr(latest_date, 'strftime') else str(latest_date)[:10]

    # 构建不区分大小写和下划线的索引字典
    index_map = {str(idx).lower().strip().replace("_", " "): idx for idx in q_income.index}

    def get_val(aliases):
        if isinstance(aliases, str):
            aliases = [aliases]
        for a in aliases:
            norm_a = a.lower().strip().replace("_", " ")
            if norm_a in index_map:
                orig_key = index_map[norm_a]
                v = q_income.loc[orig_key, latest_date]
                if pd.notna(v) and v != 0:
                    try:
                        return float(v)
                    except Exception:
                        pass
        return 0.0

    # 1. 营业总收入 (Total Revenue / Net Interest Income + Non-Interest Income)
    total_revenue = get_val([
        "Total Revenue", "Operating Revenue", "Revenue", "Gross Sales",
        "Net Interest Income", "Interest And Dividend Income", "Total Net Revenue"
    ])

    # 2. 营业成本 / 主营直接业务成本 (COGS / Cost of Services / Policy Claims)
    cost_of_revenue = get_val([
        "Cost Of Revenue", "Reconciled Cost Of Revenue", "Cost of Goods Sold",
        "Cost of Goods and Services Sold", "Cost of Services", "Policyholder Benefits And Claims",
        "Net Policyholder Claims And Benefits", "Benefits Losses And Expenses"
    ])

    # 3. 毛利润 (Gross Profit)
    gross_profit = get_val(["Gross Profit", "Gross Margin"])
    if gross_profit == 0.0 and total_revenue > 0 and cost_of_revenue > 0:
        gross_profit = total_revenue - cost_of_revenue

    # 4. 研发费用 (R&D)
    rd_expense = get_val([
        "Research And Development", "Research & Development", "Research Development",
        "Research Development Expense", "Research and Development"
    ])

    # 5. 销售与管理费用 (SG&A) 或 分开列报的销售/行政费用
    sga_expense = get_val([
        "Selling General And Administration", "Selling General & Administrative",
        "Selling General and Administrative Expense", "Selling General Administrative"
    ])
    if sga_expense == 0.0:
        sm = get_val(["Selling And Marketing Expense", "Selling and Marketing", "Sales And Marketing", "Marketing Expense"])
        ga = get_val(["General And Administrative Expense", "General and Administrative", "Administrative Expense", "General Administrative"])
        sga_expense = sm + ga

    # 6. 金融/银行业专属开支 (Non-Interest Expense & Credit Losses)
    non_interest_exp = get_val([
        "Non Interest Expense", "Non-Interest Expense", "Total Noninterest Expense",
        "Salaries And Employee Benefits", "Other Non Interest Expense"
    ])
    credit_loss_provision = get_val([
        "Provision For Credit Losses", "Provision For Loan Losses", "Credit Loss Provision"
    ])

    # 7. 营业总费用 (Operating Expense) & 营业利润 (Operating Income / EBIT)
    operating_expense = get_val(["Operating Expense", "Total Operating Expenses", "Operating Expenses"])
    operating_income = get_val(["Operating Income", "Operating Profit", "EBIT", "Operating Revenue", "Net Income Before Taxes"])

    # 8. 利息支出、税费与净利润
    interest_expense = get_val(["Interest Expense", "Interest Expense Non Operating", "Total Interest Expense"])
    tax_provision = get_val(["Tax Provision", "Provision For Income Tax", "Income Tax Expense", "Taxes"])
    net_income = get_val([
        "Net Income", "Net Income Common Stockholders",
        "Net Income From Continuing Operation Net Minority Interest", "Net Income Including Noncontrolling Interests"
    ])

    # 如果没有营业利润但有总营收和总费用，尝试推算
    if operating_income == 0.0 and total_revenue > 0:
        if operating_expense > 0:
            operating_income = total_revenue - cost_of_revenue - operating_expense
        elif net_income > 0:
            operating_income = net_income + tax_provision + interest_expense

    # -------------------------------------------------------------
    # 动态组装全行业支出细分字典 (Dynamic Expense Map)
    # -------------------------------------------------------------
    expense_dict = {}
    if cost_of_revenue > 0:
        expense_dict["营业成本 (COGS / Cost of Sales)"] = cost_of_revenue
    if rd_expense > 0:
        expense_dict["研发支出 (R&D)"] = rd_expense
    if sga_expense > 0:
        expense_dict["销售与行政费用 (SG&A)"] = sga_expense
    if non_interest_exp > 0 and sga_expense == 0:
        expense_dict["非利息运营支出 (Non-Interest Exp.)"] = non_interest_exp
    if credit_loss_provision > 0:
        expense_dict["信贷坏账拨备 (Credit Loss Provision)"] = credit_loss_provision

    # 残差推算其他运营开支
    known_opex = rd_expense + sga_expense + (non_interest_exp if sga_expense == 0 else 0) + credit_loss_provision
    if operating_expense > known_opex:
        other_op = operating_expense - known_opex
        if other_op > 0:
            expense_dict["其他运营及管理费用 (Other OpEx)"] = other_op
    elif total_revenue > 0 and operating_income > 0:
        calc_total_op = total_revenue - cost_of_revenue - operating_income
        if calc_total_op > known_opex:
            other_op = calc_total_op - known_opex
            if other_op > 0:
                expense_dict["其他运营开支 (Other OpEx)"] = other_op

    # 如果依然没有任何细分，但存在总运营费用，则作为打包项
    if not expense_dict and operating_expense > 0:
        expense_dict["总营业与运营支出 (Total OpEx)"] = operating_expense

    if tax_provision > 0:
        expense_dict["所得税费用 (Income Tax)"] = tax_provision
    if interest_expense > 0:
        expense_dict["利息支出 (Interest Expense)"] = interest_expense

    return {
        "latest_date_str": latest_date_str,
        "total_revenue": total_revenue,
        "cost_of_revenue": cost_of_revenue,
        "gross_profit": gross_profit,
        "rd_expense": rd_expense,
        "sga_expense": sga_expense,
        "non_interest_exp": non_interest_exp,
        "credit_loss_provision": credit_loss_provision,
        "operating_expense": operating_expense,
        "operating_income": operating_income,
        "interest_expense": interest_expense,
        "tax_provision": tax_provision,
        "net_income": net_income,
        "expense_dict": expense_dict
    }


# =====================================================================
# 5. Tab 核心渲染函数
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
            placeholder="例如: NVDA, AAPL, JPM, XOM, TSM...",
            help="输入美股标的代码后按 Enter 键刷新数据"
        ).strip().upper()

        if search_input and search_input != st.session_state["selected_ticker"]:
            st.session_state["selected_ticker"] = search_input

    with col_quick:
        st.markdown("<div style='font-size:0.85rem; color:#64748b; margin-bottom:4px; font-weight:600;'>快捷热门标的:</div>", unsafe_allow_html=True)
        popular_tickers = ["NVDA", "AAPL", "MSFT", "AMAT", "TSM", "GOOGL", "AMZN", "META", "TSLA", "JPM", "XOM", "COST"]
        quick_cols = st.columns(len(popular_tickers))
        for idx, sym in enumerate(popular_tickers):
            if quick_cols[idx].button(sym, key=f"quick_btn_{sym}", use_container_width=True):
                st.session_state["selected_ticker"] = sym
                st.rerun()

    active_ticker = st.session_state["selected_ticker"]

    # 2. 抓取数据
    with st.spinner(f"正在实时检索 {active_ticker} 的公司档案、最新季报与新闻资讯..."):
        data = fetch_company_data(active_ticker)

    if data["status"] == "error":
        st.error(data["message"])
        return

    info = data["info"]
    q_income = data["quarterly_income"]
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

    # 5. 最新季报财务拆解：全行业自适应收入与支出构成
    st.markdown("### 📊 2. 最新季报财务拆解：收入与支出构成 (Financial Breakdown)")

    pnl_data = extract_universal_income_data(q_income)

    if pnl_data and pnl_data.get("total_revenue", 0) > 0:
        latest_date_str = pnl_data["latest_date_str"]
        total_revenue = pnl_data["total_revenue"]
        cost_of_revenue = pnl_data["cost_of_revenue"]
        gross_profit = pnl_data["gross_profit"]
        rd_expense = pnl_data["rd_expense"]
        sga_expense = pnl_data["sga_expense"]
        operating_income = pnl_data["operating_income"]
        tax_provision = pnl_data["tax_provision"]
        net_income = pnl_data["net_income"]
        expense_dict = pnl_data["expense_dict"]

        rev_base = total_revenue if total_revenue > 0 else 1.0

        st.info(f"📅 以下财务科目提取自 **{active_ticker}** 最新发布的季度利润表 (报告截止期: **{latest_date_str}**)")

        # 核心比率 KPI 卡片
        c_kpi1, c_kpi2, c_kpi3, c_kpi4, c_kpi5 = st.columns(5)
        c_kpi1.metric("单季总营收 (Revenue)", format_large_number(total_revenue))
        if gross_profit > 0:
            c_kpi2.metric("毛利率 (Gross Margin)", f"{(gross_profit / rev_base) * 100:.1f}%")
        else:
            c_kpi2.metric("毛利率 (Gross Margin)", "不适用 (金融/服务)")
        c_kpi3.metric("研发费用率 (R&D / Rev)", f"{(rd_expense / rev_base) * 100:.1f}%" if rd_expense > 0 else "无单独R&D")
        c_kpi4.metric("营业利润率 (Op Margin)", f"{(operating_income / rev_base) * 100:.1f}%" if operating_income != 0 else "N/A")
        c_kpi5.metric("净利润率 (Net Margin)", f"{(net_income / rev_base) * 100:.1f}%" if net_income != 0 else "N/A")

        col_charts_left, col_charts_right = st.columns([1, 1])

        # 1. 支出构成环形图 (Expense Donut Chart)
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
                st.info("该公司最新季报暂无详细的二级费用细分项（仅披露了总额或属于快报期）。")

        # 2. 动态自适应利润流向瀑布图 (Dynamic P&L Waterfall Chart)
        with col_charts_right:
            st.markdown("#### 🌊 营收至净利润流向瀑布图 (P&L Waterfall)")
            if HAS_PLOTLY and total_revenue > 0:
                wf_x = ["总营收"]
                wf_y = [total_revenue]
                wf_types = ["relative"]
                wf_text = [format_large_number(total_revenue)]

                # 根据实际存在的支出项目动态构建流向节点
                for k, v in expense_dict.items():
                    if v > 0:
                        short_k = k.split("(")[0].strip() if "(" in k else k[:8]
                        wf_x.append(short_k)
                        wf_y.append(-v)
                        wf_types.append("relative")
                        wf_text.append(f"-{format_large_number(v)}")

                # 最终净利润终点
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

            # 结构化利润表明细表
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

        # 3. 历史多季度趋势对比
        with st.expander("📈 查看历史多季度营收与利润演变趋势 (Historical Quarters Trend)"):
            dates = [col for col in q_income.columns]
            if len(dates) > 1:
                hist_data = []
                for d in dates[:6]:
                    d_str = pd.to_datetime(d).strftime("%Y-%m-%d") if hasattr(d, 'strftime') else str(d)[:10]
                    r = q_income.loc["Total Revenue", d] if "Total Revenue" in q_income.index else (q_income.loc["Operating Revenue", d] if "Operating Revenue" in q_income.index else 0)
                    op = q_income.loc["Operating Income", d] if "Operating Income" in q_income.index else 0
                    ni = q_income.loc["Net Income", d] if "Net Income" in q_income.index else (q_income.loc["Net Income Common Stockholders", d] if "Net Income Common Stockholders" in q_income.index else 0)
                    hist_data.append({
                        "季度截止日": d_str,
                        "总营收 ($)": float(r) if pd.notna(r) else 0,
                        "营业利润 ($)": float(op) if pd.notna(op) else 0,
                        "净利润 ($)": float(ni) if pd.notna(ni) else 0,
                    })
                df_hist = pd.DataFrame(hist_data).sort_values("季度截止日")
                st.line_chart(df_hist.set_index("季度截止日"))
            else:
                st.write("历史季度数据较少，仅展示单季数据。")
    else:
        st.warning("暂未获取到该公司的详细季度利润表数据，请稍后刷新或检查标的代码。")

    st.markdown("---")

    # 6. 公司近期重要新闻动态
    st.markdown("### 📰 3. 公司近期重要新闻与重大动态 (Key News & Market Catalysts)")

    if news_list and len(news_list) > 0:
        for item in news_list[:8]:
            title = item.get("title", "新闻标题未提供")
            publisher = item.get("publisher", "财经资讯")
            link = item.get("link", "#")
            pub_time = format_timestamp(item.get("providerPublishTime"))
            related_symbols = item.get("relatedTickers", [])
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
        st.info("暂未检索到该标的的近期最新新闻动态。")
