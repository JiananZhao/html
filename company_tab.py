"""
Company Profile & Financial Breakdown Tab for Streamlit App
"""

import streamlit as st
import pandas as pd
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
# 4. Tab 核心渲染函数
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
            placeholder="例如: NVDA, AAPL, MSFT, AMAT...",
            help="输入美股标的代码后按 Enter 键刷新数据"
        ).strip().upper()

        if search_input and search_input != st.session_state["selected_ticker"]:
            st.session_state["selected_ticker"] = search_input

    with col_quick:
        st.markdown("<div style='font-size:0.85rem; color:#64748b; margin-bottom:4px; font-weight:600;'>快捷热门标的:</div>", unsafe_allow_html=True)
        popular_tickers = ["NVDA", "AAPL", "MSFT", "AMAT", "TSM", "GOOGL", "AMZN", "META", "TSLA", "AVGO", "ASML", "AMD"]
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
            - **财年截止月份**: `{info.get('fiscalYearEnd', 'N/A')}`
            - **历史毛利率水平**: `{format_percent(info.get('grossMargins'))}`
            - **净利润率水平**: `{format_percent(info.get('profitMargins'))}`
            - **股息收益率**: `{format_percent(info.get('dividendYield'))}`
            - **总流通股本**: `{format_large_number(info.get('sharesOutstanding'), prefix='')}`
            """
        )

    st.markdown("---")

    # 5. 最新季报财务拆解：收入与支出构成
    st.markdown("### 📊 2. 最新季报财务拆解：收入与支出构成 (Financial Breakdown)")

    if q_income is not None and not q_income.empty:
        dates = [col for col in q_income.columns]
        latest_date = dates[0]
        latest_date_str = pd.to_datetime(latest_date).strftime("%Y-%m-%d") if hasattr(latest_date, 'strftime') else str(latest_date)[:10]

        st.info(f"📅 以下数据提取自 **{active_ticker}** 最新发布的季度利润表 (报告截止期: **{latest_date_str}**)")

        def get_item(field_names):
            if isinstance(field_names, str):
                field_names = [field_names]
            for fn in field_names:
                if fn in q_income.index:
                    val = q_income.loc[fn, latest_date]
                    if pd.notna(val):
                        return float(val)
            return 0.0

        # 提取关键财务科目
        total_revenue = get_item(["Total Revenue", "Operating Revenue", "Revenue"])
        cost_of_revenue = get_item(["Cost Of Revenue", "Reconciled Cost Of Revenue", "Cost of Goods Sold", "Cost of Revenue"])
        gross_profit = get_item(["Gross Profit"]) or (total_revenue - cost_of_revenue)
        rd_expense = get_item(["Research And Development", "Research & Development", "Research Development"])
        sga_expense = get_item(["Selling General And Administration", "Selling General & Administrative", "Selling And Marketing Expense"])
        operating_expense = get_item(["Operating Expense", "Total Operating Expenses"])
        operating_income = get_item(["Operating Income", "Operating Profit"])
        interest_expense = get_item(["Interest Expense", "Interest Expense Non Operating"])
        tax_provision = get_item(["Tax Provision", "Provision For Income Tax", "Income Tax Expense"])
        net_income = get_item(["Net Income", "Net Income Common Stockholders", "Net Income From Continuing Operation Net Minority Interest"])

        other_opex = max(0.0, operating_expense - rd_expense - sga_expense) if operating_expense > 0 else max(0.0, (total_revenue - cost_of_revenue - operating_income - rd_expense - sga_expense))

        rev_base = total_revenue if total_revenue > 0 else 1.0

        # 关键费用率与利润率指标
        c_kpi1, c_kpi2, c_kpi3, c_kpi4, c_kpi5 = st.columns(5)
        c_kpi1.metric("单季总营收 (Revenue)", format_large_number(total_revenue))
        c_kpi2.metric("毛利率 (Gross Margin)", f"{(gross_profit / rev_base) * 100:.1f}%")
        c_kpi3.metric("研发费用率 (R&D / Rev)", f"{(rd_expense / rev_base) * 100:.1f}%" if rd_expense > 0 else "N/A")
        c_kpi4.metric("营业利润率 (Op Margin)", f"{(operating_income / rev_base) * 100:.1f}%")
        c_kpi5.metric("净利润率 (Net Margin)", f"{(net_income / rev_base) * 100:.1f}%")

        col_charts_left, col_charts_right = st.columns([1, 1])

        # 支出构成环形图
        with col_charts_left:
            st.markdown("#### 💰 支出与成本构成 (Expense Breakdown)")
            expense_dict = {}
            if cost_of_revenue > 0:
                expense_dict["营业成本 (COGS)"] = cost_of_revenue
            if rd_expense > 0:
                expense_dict["研发支出 (R&D)"] = rd_expense
            if sga_expense > 0:
                expense_dict["销售与行政 (SG&A)"] = sga_expense
            if other_opex > 0:
                expense_dict["其他营业费用 (Other OpEx)"] = other_opex
            if tax_provision > 0:
                expense_dict["所得税 (Tax)"] = tax_provision
            if interest_expense > 0:
                expense_dict["利息支出 (Interest)"] = interest_expense

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
                    fig_donut.update_layout(margin=dict(t=10, b=10, l=10, r=10), showlegend=False, height=320)
                    st.plotly_chart(fig_donut, use_container_width=True)
                else:
                    st.bar_chart(df_exp.set_index("支出科目")["金额 ($)"])

                st.dataframe(df_exp[["支出科目", "格式化金额", "占总营收比例"]], use_container_width=True, hide_index=True)
            else:
                st.write("暂无细分支出项数据。")

        # 利润流向瀑布图与科目表
        with col_charts_right:
            st.markdown("#### 🌊 营收至净利润流向瀑布图 (P&L Waterfall)")
            if HAS_PLOTLY and total_revenue > 0:
                waterfall_x = ["总营收", "营业成本", "研发费用", "销管费用", "营业利润", "税费/其他", "净利润"]
                measure_types = ["relative", "relative", "relative", "relative", "total", "relative", "total"]

                fig_wf = go.Figure(go.Waterfall(
                    name="P&L Flow",
                    orientation="v",
                    measure=measure_types,
                    x=waterfall_x,
                    textposition="outside",
                    text=[format_large_number(abs(v)) if v != 0 else "" for v in [total_revenue, cost_of_revenue, rd_expense, sga_expense, operating_income, (operating_income - net_income), net_income]],
                    y=[total_revenue, -cost_of_revenue, -rd_expense, -sga_expense, operating_income, -(operating_income - net_income), net_income],
                    connector={"line": {"color": "rgb(63, 63, 63)"}},
                    decreasing={"marker": {"color": "#ef4444"}},
                    increasing={"marker": {"color": "#10b981"}},
                    totals={"marker": {"color": "#3b82f6"}}
                ))
                fig_wf.update_layout(height=320, margin=dict(t=20, b=10, l=10, r=10), showlegend=False)
                st.plotly_chart(fig_wf, use_container_width=True)

            pnl_summary = [
                {"科目": "1. 营业总收入 (Total Revenue)", "金额": format_large_number(total_revenue), "占营收比重": "100.0%"},
                {"科目": "2. 营业成本 (Cost of Goods Sold)", "金额": f"-{format_large_number(cost_of_revenue)}", "占营收比重": format_percent(cost_of_revenue / rev_base)},
                {"科目": "3. 毛利润 (Gross Profit)", "金额": format_large_number(gross_profit), "占营收比重": format_percent(gross_profit / rev_base)},
                {"科目": "4. 研发费用 (R&D)", "金额": f"-{format_large_number(rd_expense)}", "占营收比重": format_percent(rd_expense / rev_base)},
                {"科目": "5. 销售与行政费用 (SG&A)", "金额": f"-{format_large_number(sga_expense)}", "占营收比重": format_percent(sga_expense / rev_base)},
                {"科目": "6. 营业利润 (Operating Income)", "金额": format_large_number(operating_income), "占营收比重": format_percent(operating_income / rev_base)},
                {"科目": "7. 净利润 (Net Income)", "金额": format_large_number(net_income), "占营收比重": format_percent(net_income / rev_base)}
            ]
            st.dataframe(pd.DataFrame(pnl_summary), use_container_width=True, hide_index=True)

        # 历史多季度趋势对比
        with st.expander("📈 查看历史多季度营收与费用演变趋势 (Historical Quarters Trend)"):
            if len(dates) > 1:
                hist_data = []
                for d in dates[:6]:
                    d_str = pd.to_datetime(d).strftime("%Y-%m-%d") if hasattr(d, 'strftime') else str(d)[:10]
                    r = q_income.loc["Total Revenue", d] if "Total Revenue" in q_income.index else 0
                    c = q_income.loc["Cost Of Revenue", d] if "Cost Of Revenue" in q_income.index else 0
                    op = q_income.loc["Operating Income", d] if "Operating Income" in q_income.index else 0
                    ni = q_income.loc["Net Income", d] if "Net Income" in q_income.index else 0
                    hist_data.append({
                        "季度截止日": d_str,
                        "总营收 ($)": float(r) if pd.notna(r) else 0,
                        "营业成本 ($)": float(c) if pd.notna(c) else 0,
                        "营业利润 ($)": float(op) if pd.notna(op) else 0,
                        "净利润 ($)": float(ni) if pd.notna(ni) else 0,
                    })
                df_hist = pd.DataFrame(hist_data).sort_values("季度截止日")
                st.line_chart(df_hist.set_index("季度截止日"))
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
