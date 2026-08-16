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
from zoneinfo import ZoneInfo

# ------------------------------------------------------------------
# 模块导入与热重载安全机制 (防止 Streamlit Cloud 模块缓存导致 ImportError)
# ------------------------------------------------------------------
try:
    import visualization
    from visualization import create_financial_trends_chart
except Exception:
    create_financial_trends_chart = None

# ------------------------------------------------------------------
# 1. 辅助函数：严格转换为美东时间 (EDT) 与数据抓取封装
# ------------------------------------------------------------------
def get_eastern_now_str():
    try:
        return datetime.datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %H:%M EDT")
    except Exception:
        tz_offset = datetime.timezone(datetime.timedelta(hours=-4))
        return datetime.datetime.now(tz_offset).strftime("%Y-%m-%d %H:%M EDT")

@st.cache_data(ttl=60 * 60 * 4)
def fetch_company_profile_data(symbol: str):
    """
    通过 yfinance 获取公司核心 Profile 与结构化基本面数据
    """
    try:
        import yfinance as yf
        ticker = yf.Ticker(symbol)
        info = ticker.info
        return info
    except Exception as e:
        print(f"Error fetching company info for {symbol}: {e}")
        return {}

@st.cache_data(ttl=60 * 60 * 6)
def fetch_multi_tier_financials(symbol: str):
    """
    多层级财务报表提取引擎：自动适配科技、半导体、工业、SaaS、消费等跨行业 P&L 科目
    """
    try:
        import yfinance as yf
        ticker = yf.Ticker(symbol)
        inc_q = ticker.quarterly_income_stmt
        inc_a = ticker.income_stmt
        bal_q = ticker.quarterly_balance_sheet
        bal_a = ticker.balance_sheet
        cf_q = ticker.quarterly_cashflow
        cf_a = ticker.cashflow

        return {
            "inc_q": inc_q, "inc_a": inc_a,
            "bal_q": bal_q, "bal_a": bal_a,
            "cf_q": cf_q, "cf_a": cf_a
        }
    except Exception as e:
        print(f"Error fetching financials for {symbol}: {e}")
        return {}

@st.cache_data(ttl=60 * 60 * 2)
def fetch_company_news_feed(symbol: str, company_name: str = ""):
    """
    双模式新闻引擎：yfinance 原生新闻 + Google News RSS 实时兜底，确保新闻列表永不落空
    """
    news_items = []
    
    # 1. 优先尝试 yfinance 原生新闻
    try:
        import yfinance as yf
        ticker = yf.Ticker(symbol)
        yf_news = ticker.news
        if yf_news and isinstance(yf_news, list):
            for item in yf_news:
                # 兼容 yfinance 新旧双 schema
                title = item.get("title", "")
                link = item.get("link", "")
                publisher = item.get("publisher", "")
                pub_time = item.get("providerPublishTime", None)

                # 新版 yfinance 嵌套在 content 结构中
                if not title and "content" in item:
                    content = item.get("content", {})
                    title = content.get("title", "")
                    publisher = content.get("provider", {}).get("displayName", "")
                    canonical = content.get("canonicalUrl", {})
                    link = canonical.get("url", "") if isinstance(canonical, dict) else str(canonical)
                    pub_time = content.get("pubDate", None)

                if title and link:
                    time_str = ""
                    if pub_time:
                        try:
                            if isinstance(pub_time, (int, float)):
                                dt = datetime.datetime.fromtimestamp(pub_time, tz=datetime.timezone.utc).astimezone(ZoneInfo("America/New_York"))
                                time_str = dt.strftime("%Y-%m-%d %H:%M EDT")
                            else:
                                dt = pd.to_datetime(pub_time).tz_convert(ZoneInfo("America/New_York"))
                                time_str = dt.strftime("%Y-%m-%d %H:%M EDT")
                        except Exception:
                            time_str = str(pub_time)[:16]

                    news_items.append({
                        "title": title,
                        "link": link,
                        "publisher": publisher if publisher else "Financial Media",
                        "time": time_str
                    })
    except Exception as e:
        print(f"yfinance news error for {symbol}: {e}")

    # 2. 若原生新闻为空，触发 Google News RSS 兜底
    if not news_items:
        try:
            query = f"{symbol}+{company_name}+stock" if company_name else f"{symbol}+stock"
            rss_url = f"https://news.google.com/rss/search?q={urllib.parse.quote(query)}&hl=en-US&gl=US&ceid=US:en"
            req = urllib.request.Request(rss_url, headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'})
            with urllib.request.urlopen(req, timeout=10) as resp:
                xml_data = resp.read().decode('utf-8')
                items = re.findall(r'<item>(.*?)</item>', xml_data, re.DOTALL)
                for it in items[:8]:
                    t_match = re.search(r'<title>(.*?)</title>', it)
                    l_match = re.search(r'<link>(.*?)</link>', it)
                    p_match = re.search(r'<pubDate>(.*?)</pubDate>', it)
                    s_match = re.search(r'<source[^>]*>(.*?)</source>', it)
                    
                    if t_match and l_match:
                        t_clean = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', t_match.group(1)).strip()
                        l_clean = l_match.group(1).strip()
                        p_str = p_match.group(1).strip() if p_match else ""
                        s_clean = s_match.group(1).strip() if s_match else "Google News"
                        
                        try:
                            dt = pd.to_datetime(p_str).tz_convert(ZoneInfo("America/New_York"))
                            formatted_time = dt.strftime("%Y-%m-%d %H:%M EDT")
                        except Exception:
                            formatted_time = p_str[:16]

                        news_items.append({
                            "title": t_clean,
                            "link": l_clean,
                            "publisher": s_clean,
                            "time": formatted_time
                        })
        except Exception as e:
            print(f"Google News RSS fallback error for {symbol}: {e}")

    return news_items[:10]

# ------------------------------------------------------------------
# 2. 核心报表解析与多行业兼容提取引擎
# ------------------------------------------------------------------
def _extract_val(df_stmt, candidate_keys, col_name):
    """
    跨行业科目安全提取器：支持多别名、多变体与不同会计准则
    """
    if df_stmt is None or df_stmt.empty:
        return np.nan
    for k in candidate_keys:
        if k in df_stmt.index:
            v = df_stmt.loc[k, col_name]
            if isinstance(v, pd.Series):
                v = v.iloc[0]
            if pd.notna(v) and v != "":
                try:
                    return float(v)
                except Exception:
                    pass
    return np.nan

def parse_income_statement_waterfall(inc_stmt):
    """
    通用利润表瀑布图结构解析器：自动拆解 Revenue -> COGS -> GP -> R&D -> SG&A -> OpInc -> Tax/Interest -> NetInc
    """
    if inc_stmt is None or inc_stmt.empty:
        return None, {}

    latest_col = inc_stmt.columns[0]
    period_label = latest_col.strftime("%Y-%m-%d") if hasattr(latest_col, "strftime") else str(latest_col)[:10]

    rev = _extract_val(inc_stmt, ["Total Revenue", "Operating Revenue", "Revenue"], latest_col)
    cogs = _extract_val(inc_stmt, ["Cost Of Revenue", "Cost of Goods Sold", "Cost of Revenue", "Operating Expense"], latest_col)
    gp = _extract_val(inc_stmt, ["Gross Profit"], latest_col)
    rd = _extract_val(inc_stmt, ["Research And Development", "Research and Development", "Research & Development"], latest_col)
    sga = _extract_val(inc_stmt, ["Selling General And Administration", "Selling, General and Administrative", "Selling General & Administrative"], latest_col)
    op_inc = _extract_val(inc_stmt, ["Operating Income", "Operating Profit", "Total Operating Income"], latest_col)
    net_inc = _extract_val(inc_stmt, ["Net Income", "Net Income Common Stockholders", "Net Income From Continuing Operation Net Minority Interest"], latest_col)

    if pd.isna(gp) and pd.notna(rev) and pd.notna(cogs):
        gp = rev - abs(cogs)
    if pd.isna(cogs) and pd.notna(rev) and pd.notna(gp):
        cogs = rev - gp

    # 兜底其余各项费用
    other_opex = 0.0
    if pd.notna(gp) and pd.notna(op_inc):
        known_opex = (abs(rd) if pd.notna(rd) else 0.0) + (abs(sga) if pd.notna(sga) else 0.0)
        calculated_opex = gp - op_inc
        if calculated_opex > known_opex:
            other_opex = calculated_opex - known_opex

    other_non_op = 0.0
    if pd.notna(op_inc) and pd.notna(net_inc):
        other_non_op = net_inc - op_inc

    metrics = {
        "period": period_label,
        "revenue": rev,
        "cogs": cogs,
        "gross_profit": gp,
        "rd": rd,
        "sga": sga,
        "other_opex": other_opex,
        "operating_income": op_inc,
        "other_non_op": other_non_op,
        "net_income": net_inc
    }

    # 构造 Plotly 瀑布图数据
    labels = ["营业总收入 (Revenue)"]
    measures = ["absolute"]
    values = [rev / 1e6 if pd.notna(rev) else 0]

    if pd.notna(cogs) and cogs != 0:
        labels.append("营业成本 (COGS)")
        measures.append("relative")
        values.append(-abs(cogs) / 1e6)

    if pd.notna(gp):
        labels.append("毛利润 (Gross Profit)")
        measures.append("total")
        values.append(gp / 1e6)

    if pd.notna(rd) and rd > 0:
        labels.append("研发费用 (R&D)")
        measures.append("relative")
        values.append(-abs(rd) / 1e6)

    if pd.notna(sga) and sga > 0:
        labels.append("销售管理费用 (SG&A)")
        measures.append("relative")
        values.append(-abs(sga) / 1e6)

    if other_opex > 0:
        labels.append("其他营业支出 (Other OpEx)")
        measures.append("relative")
        values.append(-abs(other_opex) / 1e6)

    if pd.notna(op_inc):
        labels.append("营业利润 (Operating Income)")
        measures.append("total")
        values.append(op_inc / 1e6)

    if other_non_op != 0:
        labels.append("利息/税费/其他非经常损益")
        measures.append("relative")
        values.append(other_non_op / 1e6)

    if pd.notna(net_inc):
        labels.append("净利润 (Net Income)")
        measures.append("total")
        values.append(net_inc / 1e6)

    fig = go.Figure(go.Waterfall(
        name="P&L Breakdown",
        orientation="v",
        measure=measures,
        x=labels,
        textposition="outside",
        text=[f"${v:,.1f}M" for v in values],
        y=values,
        connector={"line": {"color": "rgb(63, 63, 63)", "width": 1.5}},
        decreasing={"marker": {"color": "#ef4444"}},
        increasing={"marker": {"color": "#22c55e"}},
        totals={"marker": {"color": "#3b82f6"}}
    ))

    fig.update_layout(
        title=f"最新报告期 ({period_label}) 损益表现金流向与利润漏斗瀑布图 ($ Millions)",
        template="plotly_white",
        height=500,
        showlegend=False,
        hovermode="x unified"
    )

    return fig, metrics

def process_multi_period_statements_table(inc, bal, cf):
    """
    处理多期（4-5期）财务报表，输出规范对比表格与可视化 DataFrame
    """
    if inc is None or inc.empty:
        return None, None

    cols = [c for c in inc.columns]
    dates = [c.strftime("%Y-%m-%d") if hasattr(c, "strftime") else str(c)[:10] for c in cols]

    summary_rows = []
    trend_rows = []

    for orig_col, d_str in zip(cols, dates):
        rev = _extract_val(inc, ["Total Revenue", "Operating Revenue", "Revenue"], orig_col)
        gp = _extract_val(inc, ["Gross Profit"], orig_col)
        op_inc = _extract_val(inc, ["Operating Income", "Operating Profit"], orig_col)
        net_inc = _extract_val(inc, ["Net Income", "Net Income Common Stockholders"], orig_col)
        eps = _extract_val(inc, ["Diluted EPS", "Basic EPS"], orig_col)
        ebitda = _extract_val(inc, ["EBITDA", "Normalized EBITDA"], orig_col)
        rd = _extract_val(inc, ["Research And Development", "Research and Development"], orig_col)
        
        cfo = _extract_val(cf, ["Operating Cash Flow", "Cash Flow From Continuing Operating Activities"], orig_col)
        capex = _extract_val(cf, ["Capital Expenditure", "Capital Expenditures"], orig_col)
        fcf = _extract_val(cf, ["Free Cash Flow"], orig_col)
        if pd.isna(fcf) and pd.notna(cfo) and pd.notna(capex):
            fcf = cfo - abs(capex)

        cash = _extract_val(bal, ["Cash And Cash Equivalents", "Cash Cash Equivalents And Short Term Investments"], orig_col)
        debt = _extract_val(bal, ["Total Debt", "Long Term Debt And Capital Lease Obligation"], orig_col)
        equity = _extract_val(bal, ["Stockholders Equity", "Total Stockholder Equity"], orig_col)

        gm = (gp / rev * 100) if (pd.notna(gp) and pd.notna(rev) and rev != 0) else np.nan
        opm = (op_inc / rev * 100) if (pd.notna(op_inc) and pd.notna(rev) and rev != 0) else np.nan
        npm = (net_inc / rev * 100) if (pd.notna(net_inc) and pd.notna(rev) and rev != 0) else np.nan
        fcf_m = (fcf / rev * 100) if (pd.notna(fcf) and pd.notna(rev) and rev != 0) else np.nan

        summary_rows.append({
            "报告期 (Period)": d_str,
            "总营收 ($M)": f"${rev/1e6:,.1f}" if pd.notna(rev) else "-",
            "毛利润 ($M)": f"${gp/1e6:,.1f}" if pd.notna(gp) else "-",
            "毛利率 (%)": f"{gm:.1f}%" if pd.notna(gm) else "-",
            "营业利润 ($M)": f"${op_inc/1e6:,.1f}" if pd.notna(op_inc) else "-",
            "营业利润率 (%)": f"{opm:.1f}%" if pd.notna(opm) else "-",
            "净利润 ($M)": f"${net_inc/1e6:,.1f}" if pd.notna(net_inc) else "-",
            "净利率 (%)": f"{npm:.1f}%" if pd.notna(npm) else "-",
            "稀释 EPS ($)": f"${eps:.2f}" if pd.notna(eps) else "-",
            "经营现金流 ($M)": f"${cfo/1e6:,.1f}" if pd.notna(cfo) else "-",
            "资本开支 ($M)": f"${capex/1e6:,.1f}" if pd.notna(capex) else "-",
            "自由现金流 ($M)": f"${fcf/1e6:,.1f}" if pd.notna(fcf) else "-",
            "FCF 利润率 (%)": f"{fcf_m:.1f}%" if pd.notna(fcf_m) else "-",
            "现金储备 ($M)": f"${cash/1e6:,.1f}" if pd.notna(cash) else "-",
            "总负债 ($M)": f"${debt/1e6:,.1f}" if pd.notna(debt) else "-",
            "股东权益 ($M)": f"${equity/1e6:,.1f}" if pd.notna(equity) else "-"
        })

        trend_rows.append({
            "Period": d_str,
            "Revenue ($M)": rev / 1e6 if pd.notna(rev) else np.nan,
            "Gross Margin (%)": gm,
            "Operating Margin (%)": opm,
            "Net Margin (%)": npm,
            "Net Income ($M)": net_inc / 1e6 if pd.notna(net_inc) else np.nan,
            "Operating Cash Flow ($M)": cfo / 1e6 if pd.notna(cfo) else np.nan,
            "CapEx ($M)": capex / 1e6 if pd.notna(capex) else np.nan,
            "Free Cash Flow ($M)": fcf / 1e6 if pd.notna(fcf) else np.nan,
            "R&D Expenses ($M)": rd / 1e6 if pd.notna(rd) else np.nan,
            "R&D / Rev (%)": (rd / rev * 100) if (pd.notna(rd) and pd.notna(rev) and rev != 0) else np.nan
        })

    df_summary = pd.DataFrame(summary_rows)
    df_trend = pd.DataFrame(trend_rows).sort_values("Period").reset_index(drop=True)
    return df_summary, df_trend

# ------------------------------------------------------------------
# 3. Tab 4 主界面入口函数
# ------------------------------------------------------------------
def render_company_deep_dive_tab():
    st.header("🏢 公司画像与深度财报拆解分析 (Company Deep Dive & Financials)")
    st.markdown("全方位剖析公司主营业务构成、核心高管阵列、治理结构、P&L 利润流向瀑布图、多期财务明细与实时新闻动态。")

    # 1. 代码输入与主配置
    col_in1, col_in2, col_in3 = st.columns([2, 2, 4])
    with col_in1:
        company_symbol = st.text_input("输入待分析美股代码 (Ticker):", value="NVDA", key="tab4_company_ticker_input").upper().strip()
    with col_in2:
        period_view = st.selectbox("核心财报展示维度:", ["最新季度 (Quarterly)", "最新年度 (Annual)"], index=0, key="tab4_period_view_select")
    with col_in3:
        st.markdown(f"**数据更新基准**: `{get_eastern_now_str()}`")

    if not company_symbol:
        st.info("请输入美股代码以开始深度分析。")
        return

    with st.spinner(f"正在拉取 {company_symbol} 完整画像、高管、治理与财务报表数据..."):
        info = fetch_company_profile_data(company_symbol)
        raw_fin = fetch_multi_tier_financials(company_symbol)

    if not info:
        st.warning(f"未能获取到 {company_symbol} 的有效数据，请核对 Ticker 是否正确。")
        return

    # 2. 公司基础画像与核心指标
    comp_name = info.get("shortName", company_symbol)
    long_name = info.get("longName", comp_name)
    sector = info.get("sector", "N/A")
    industry = info.get("industry", "N/A")
    country = info.get("country", "N/A")
    city = info.get("city", "N/A")
    state = info.get("state", "N/A")
    website = info.get("website", "")
    full_time_emp = info.get("fullTimeEmployees", np.nan)
    curr_price = info.get("currentPrice", info.get("regularMarketPrice", np.nan))
    mkt_cap = info.get("marketCap", np.nan)
    fwd_pe = info.get("forwardPE", np.nan)
    trail_pe = info.get("trailingPE", np.nan)
    ps_ttm = info.get("priceToSalesTrailing12Months", np.nan)

    st.subheader(f"📌 {long_name} ({company_symbol})")
    
    # 顶部 KPI 矩阵
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("当前实时股价", f"${curr_price:.2f}" if pd.notna(curr_price) else "N/A")
    c2.metric("所属行业板块", sector)
    c3.metric("细分产业赛道", industry)
    c4.metric("公司总市值", f"${mkt_cap/1e9:.2f} B" if pd.notna(mkt_cap) else "N/A")
    c5.metric("全球员工总数", f"{full_time_emp:,} 人" if pd.notna(full_time_emp) else "N/A")

    st.markdown("---")

    # 3. 业务描述与主营构成
    st.subheader("1. 商业模式与主营业务全景 (Business Overview)")
    business_summary = info.get("longBusinessSummary", "暂无公司详细业务描述。")
    st.markdown(f"> {business_summary}")

    if website:
        st.markdown(f"🔗 **官方主页**: [{website}]({website}) | 📍 **总部地址**: {city}, {state}, {country}")

    st.markdown("---")

    # 4. 核心高管团队与薪酬
    st.subheader("2. 核心管理层与高管阵列 (Key Executives & Leadership)")
    exec_list = info.get("companyOfficers", [])
    if exec_list and isinstance(exec_list, list):
        exec_rows = []
        for officer in exec_list[:8]:
            o_name = officer.get("name", "N/A")
            o_title = officer.get("title", "N/A")
            o_age = officer.get("age", "-")
            o_pay = officer.get("totalPay", None)
            o_exercised = officer.get("exercisedValue", None)
            
            pay_str = f"${o_pay:,.0f}" if (o_pay and pd.notna(o_pay) and o_pay > 0) else "未单独披露"
            exec_rows.append({
                "高管姓名 (Name)": o_name,
                "职务头衔 (Title)": o_title,
                "年龄": o_age,
                "年度披露总薪酬 (Total Pay)": pay_str
            })
        st.dataframe(pd.DataFrame(exec_rows), hide_index=True, use_container_width=True)
    else:
        st.info("暂无高管公开披露明细。")

    st.markdown("---")

    # 5. 公司治理与股东结构
    st.subheader("3. 公司治理、审计与内部人持股 (Governance & Ownership)")
    col_gov1, col_gov2 = st.columns(2)
    with col_gov1:
        st.markdown("##### 🏛️ 机构与内部人持股比例")
        insider_pct = info.get("heldPercentInsiders", np.nan)
        inst_pct = info.get("heldPercentInstitutions", np.nan)
        float_shares = info.get("floatShares", np.nan)
        shares_out = info.get("sharesOutstanding", np.nan)
        short_ratio = info.get("shortRatio", np.nan)
        short_pct_float = info.get("shortPercentOfFloat", np.nan)

        st.write(f"* **管理层/内部人持股比例**: {insider_pct*100:.2f}%" if pd.notna(insider_pct) else "* 管理层/内部人持股: N/A")
        st.write(f"* **机构投资者持股比例**: {inst_pct*100:.2f}%" if pd.notna(inst_pct) else "* 机构投资者持股: N/A")
        st.write(f"* **总发行股数**: {shares_out/1e9:.2f} B 股" if pd.notna(shares_out) else "* 总发行股数: N/A")
        st.write(f"* **自由流通股数**: {float_shares/1e9:.2f} B 股" if pd.notna(float_shares) else "* 自由流通股数: N/A")
        st.write(f"* **空头做空比例 (Short % of Float)**: {short_pct_float*100:.2f}%" if pd.notna(short_pct_float) else "* 做空比例: N/A")
        st.write(f"* **做空回补天数 (Short Ratio)**: {short_ratio:.1f} 天" if pd.notna(short_ratio) else "* 做空回补天数: N/A")

    with col_gov2:
        st.markdown("##### ⚖️ ISS 机构治理评分指标 (1 为最优风险最低，10 为最高风险)")
        audit_risk = info.get("auditRisk", "N/A")
        board_risk = info.get("boardRisk", "N/A")
        comp_risk = info.get("compensationRisk", "N/A")
        shr_risk = info.get("shareHolderRightsRisk", "N/A")
        ovr_risk = info.get("overallRisk", "N/A")

        st.write(f"* **审计与风控风险分 (Audit Risk)**: `{audit_risk}`")
        st.write(f"* **董事会独立性风险分 (Board Risk)**: `{board_risk}`")
        st.write(f"* **高管薪酬合理性风险分 (Compensation Risk)**: `{comp_risk}`")
        st.write(f"* **股东权利保护风险分 (Shareholder Rights)**: `{shr_risk}`")
        st.write(f"* **综合治理风险评级 (Overall Risk)**: `{ovr_risk}`")

    st.markdown("---")

    # 6. P&L 损益流向瀑布图分析
    st.subheader("4. 利润漏斗与损益流向瀑布图拆解 (P&L Waterfall Breakdown)")
    target_inc = raw_fin.get("inc_q") if "Quarterly" in period_view else raw_fin.get("inc_a")
    fig_waterfall, metrics = parse_income_statement_waterfall(target_inc)

    if fig_waterfall:
        st.plotly_chart(fig_waterfall, use_container_width=True)
        
        # 补充利润率结构诊断
        rev_val = metrics.get("revenue", np.nan)
        gp_val = metrics.get("gross_profit", np.nan)
        op_val = metrics.get("operating_income", np.nan)
        ni_val = metrics.get("net_income", np.nan)
        rd_val = metrics.get("rd", np.nan)
        sga_val = metrics.get("sga", np.nan)

        if pd.notna(rev_val) and rev_val > 0:
            m_col1, m_col2, m_col3, m_col4 = st.columns(4)
            m_col1.metric("当期毛利率 (Gross Margin)", f"{(gp_val/rev_val*100):.1f}%" if pd.notna(gp_val) else "N/A")
            m_col2.metric("当期营业利润率 (Operating Margin)", f"{(op_val/rev_val*100):.1f}%" if pd.notna(op_val) else "N/A")
            m_col3.metric("当期净利率 (Net Margin)", f"{(ni_val/rev_val*100):.1f}%" if pd.notna(ni_val) else "N/A")
            m_col4.metric("研发费用率 (R&D / Revenue)", f"{(rd_val/rev_val*100):.1f}%" if pd.notna(rd_val) else "0.0%")
    else:
        st.info("暂无详细损益表结构化科目数据。")

    st.markdown("---")

    # 7. 多期财务报表明细与趋势图
    st.subheader("5. 历史多期财务报表对比与核心指标走势 (Multi-Period Financial Statements)")
    
    inc_q = raw_fin.get("inc_q")
    bal_q = raw_fin.get("bal_q")
    cf_q = raw_fin.get("cf_q")
    inc_a = raw_fin.get("inc_a")
    bal_a = raw_fin.get("bal_a")
    cf_a = raw_fin.get("cf_a")

    df_q_sum, df_q_trend = process_multi_period_statements_table(inc_q, bal_q, cf_q)
    df_a_sum, df_a_trend = process_multi_period_statements_table(inc_a, bal_a, cf_a)

    fin_tab_q, fin_tab_a = st.tabs([
        "📊 季度多期财务明细与走势 (Quarterly)",
        "📅 年度多期财务明细与走势 (Annual)"
    ])

    with fin_tab_q:
        if df_q_sum is not None and not df_q_sum.empty:
            if df_q_trend is not None and not df_q_trend.empty and create_financial_trends_chart:
                fig_q = create_financial_trends_chart(df_q_trend, symbol=company_symbol, period_type="季度 (Quarterly)")
                if fig_q:
                    st.plotly_chart(fig_q, use_container_width=True)
            st.markdown("##### 季度核心财务指标全景对比表 ($M / %)")
            st.dataframe(df_q_sum, hide_index=True, use_container_width=True)
        else:
            st.info("暂无季度结构化多期财务报表数据。")

    with fin_tab_a:
        if df_a_sum is not None and not df_a_sum.empty:
            if df_a_trend is not None and not df_a_trend.empty and create_financial_trends_chart:
                fig_a = create_financial_trends_chart(df_a_trend, symbol=company_symbol, period_type="年度 (Annual)")
                if fig_a:
                    st.plotly_chart(fig_a, use_container_width=True)
            st.markdown("##### 年度核心财务指标全景对比表 ($M / %)")
            st.dataframe(df_a_sum, hide_index=True, use_container_width=True)
        else:
            st.info("暂无年度结构化多期财务报表数据。")

    st.markdown("---")

    # 8. 公司近期重要新闻动态 (带外链跳转)
    st.subheader(f"6. {company_symbol} 实时重要新闻动态与市场关注 (News Feed)")
    with st.spinner("正在获取实时新闻资讯..."):
        news_items = fetch_company_news_feed(company_symbol, company_name=comp_name)

    if news_items:
        for idx, item in enumerate(news_items):
            title = item.get("title", "")
            link = item.get("link", "")
            pub = item.get("publisher", "")
            time_s = item.get("time", "")

            with st.container():
                st.markdown(f"**{idx+1}. [{title}]({link})**")
                st.caption(f"📰 来源: `{pub}` | 🕒 时间: `{time_s}`")
                st.markdown("")
    else:
        st.info("暂无近期重大公开新闻动态。")
