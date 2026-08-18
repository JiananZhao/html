import os
import sys
import datetime
import json
import urllib.request
import re
import numpy as np
import pandas as pd
import streamlit as st
from zoneinfo import ZoneInfo

from data_processing import load_and_transform_data
from market_breadth_viz import render_market_breadth_ui

# ------------------------------------------------------------------
# 模块导入与热重载安全机制 (防止 Streamlit Cloud 内存模块缓存导致 ImportError)
# ------------------------------------------------------------------
try:
    import market_breadth_viz
    importlib.reload(market_breadth_viz)
    from market_breadth_viz import render_market_breadth_ui
except Exception:
    pass

try:
    import company_tab
    importlib.reload(company_tab)
    from company_tab import render_company_deep_dive_tab
except Exception:
    pass

from visualization import (
    create_treasury_chart,
    create_unemployment_chart,
    create_credit_spread_chart,
    create_fed_balance_sheet_chart,
    create_gold_oil_ratio_chart,
    create_real_yield_breakeven_chart,
    create_nfci_chart,
    create_net_liquidity_chart,
    create_sofr_iorb_chart,
    create_top10_concentration_chart,
    create_vix_chart,
    create_cnn_fear_greed_chart,
    create_stock_price_chart,
    create_relative_performance_chart,
    create_financial_trends_chart,
    create_pe_ps_band_chart,
    create_technical_momentum_chart,
    create_yield_spreads_chart,
    create_jobless_claims_chart,
    create_dxy_chart,
    create_inflation_wages_chart,
    create_sahm_rule_chart,
    create_core_capex_chart,
    create_m2_money_supply_chart,
    create_sloos_credit_chart
)


# ------------------------------------------------------------------
# 页面基础配置 (宽屏沉浸式布局)
# ------------------------------------------------------------------
st.set_page_config(
    page_title="Macro & Equity Quantitative Terminal",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 自定义 CSS 优化看板视觉层次
st.markdown("""
<style>
    .reportview-container {
        margin-top: -2em;
    }
    .metric-container {
        display: flex;
        justify-content: space-between;
        padding: 10px;
        background-color: #f8fafc;
        border-radius: 8px;
        border: 1px solid #e2e8f0;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 12px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 48px;
        white-space: pre-wrap;
        background-color: #f1f5f9;
        border-radius: 6px 6px 0px 0px;
        gap: 6px;
        padding-top: 10px;
        padding-bottom: 10px;
    }
    .stTabs [aria-selected="true"] {
        background-color: #e2e8f0;
        font-weight: 600;
    }
</style>
""", unsafe_allow_html=True)


# ------------------------------------------------------------------
# 辅助函数：严格转换为美东时间 (EDT)
# ------------------------------------------------------------------
def get_eastern_now_str():
    try:
        return datetime.datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %H:%M EDT")
    except Exception:
        tz_offset = datetime.timezone(datetime.timedelta(hours=-4))
        return datetime.datetime.now(tz_offset).strftime("%Y-%m-%d %H:%M EDT")

current_et_str = get_eastern_now_str()


def get_file_updated_time_eastern(filepath: str):
    """获取文件在美东时区的最后修改时间"""
    if not os.path.exists(filepath):
        return "N/A"
    try:
        mtime = os.path.getmtime(filepath)
        dt = datetime.datetime.fromtimestamp(mtime, tz=datetime.timezone.utc).astimezone(ZoneInfo("America/New_York"))
        return dt.strftime("%Y-%m-%d %H:%M EDT")
    except Exception:
        return "近期"


# ------------------------------------------------------------------
# 缓存数据加载层 (FRED 宏观指标与全量 CSV 数据)
# ------------------------------------------------------------------
@st.cache_data(ttl=60 * 60 * 2)
def load_all_macro_datasets():
    """
    加载由 GitHub Actions 每日自动抓取更新的宏观经济高频与领先指标数据集
    """
    datasets = {}
    csv_files = {
        "treasury": "daily-treasury-rates.csv",
        "market_breadth": "market_breadth.csv"
    }

    for key, fname in csv_files.items():
        if os.path.exists(fname):
            try:
                df = pd.read_csv(fname)
                if not df.empty:
                    # 标准化日期列
                    date_col = 'Date' if 'Date' in df.columns else ('date' if 'date' in df.columns else df.columns[0])
                    df['Date'] = pd.to_datetime(df[date_col])
                    datasets[key] = df
            except Exception as e:
                print(f"Error loading {fname}: {e}")

    return datasets


@st.cache_data(ttl=60 * 60 * 4)
def get_stock_historical_data(symbol: str, period: str = "5y"):
    """
    通过 yfinance 获取个股与 ETF 历史量价数据
    """
    clean_sym = symbol.strip().upper()
    try:
        import yfinance as yf
        ticker = yf.Ticker(clean_sym)
        df_hist = ticker.history(period=period, auto_adjust=True)
        if df_hist is not None and not df_hist.empty:
            df_hist = df_hist.reset_index()
            date_col = 'Date' if 'Date' in df_hist.columns else df_hist.columns[0]
            df_hist['Date'] = pd.to_datetime(df_hist[date_col]).dt.tz_localize(None)
            return df_hist
    except Exception as e:
        print(f"Error fetching historical data for {clean_sym}: {e}")

    return pd.DataFrame()


@st.cache_data(ttl=60 * 60 * 4)
def get_stock_fundamentals(symbol: str):
    """
    通过 yfinance 获取个股基本面、估值倍数与财务质量指标
    """
    clean_sym = symbol.strip().upper()
    try:
        import yfinance as yf
        ticker = yf.Ticker(clean_sym)
        info = ticker.info
        if info and isinstance(info, dict) and len(info) > 5:
            return info
    except Exception as e:
        print(f"Error fetching info for {clean_sym}: {e}")

    return {}


@st.cache_data(ttl=60 * 60)
def get_stock_financial_statements(symbol: str):
    """
    通过 yfinance 获取个股的季度与年度三大财务报表核心数据
    """
    clean_sym = symbol.strip().upper()
    try:
        import yfinance as yf
        ticker = yf.Ticker(clean_sym)
        
        q_inc = getattr(ticker, 'quarterly_income_stmt', None)
        if q_inc is None or q_inc.empty:
            q_inc = getattr(ticker, 'quarterly_financials', None)
            
        a_inc = getattr(ticker, 'income_stmt', None)
        if a_inc is None or a_inc.empty:
            a_inc = getattr(ticker, 'financials', None)

        q_bs = getattr(ticker, 'quarterly_balance_sheet', None)
        a_bs = getattr(ticker, 'balance_sheet', None)

        q_cf = getattr(ticker, 'quarterly_cashflow', None)
        if q_cf is None or q_cf.empty:
            q_cf = getattr(ticker, 'quarterly_cash_flow', None)
            
        a_cf = getattr(ticker, 'cashflow', None)
        if a_cf is None or a_cf.empty:
            a_cf = getattr(ticker, 'cash_flow', None)

        return {
            "quarterly_income": q_inc,
            "annual_income": a_inc,
            "quarterly_balance": q_bs,
            "annual_balance": a_bs,
            "quarterly_cashflow": q_cf,
            "annual_cashflow": a_cf
        }
    except Exception as e:
        print(f"Error fetching financial statements for {clean_sym}: {e}")
        return {}


# ------------------------------------------------------------------
# DCF 反向估值计算核心算法 (Reverse DCF Model)
# ------------------------------------------------------------------
def calculate_reverse_dcf(
    current_price: float,
    shares_out: float,
    base_fcf: float,
    wacc: float = 0.09,
    g: float = 0.025,
    years: int = 5,
    total_cash: float = 0.0,
    total_debt: float = 0.0
):
    """
    反向 DCF 核心引擎：根据当前股价与市值反推市场当前所隐含的未来复合自由现金流增速 (Implied CAGR)
    """
    if current_price <= 0 or shares_out <= 0 or base_fcf <= 0 or wacc <= g:
        return None

    market_cap = current_price * shares_out
    target_ev = market_cap + total_debt - total_cash

    # 目标函数：寻找折现净现值与当前 EV 相等的复合增速 cagr
    def pv_diff(cagr):
        pv_fcf = 0.0
        projected_fcf = base_fcf
        for t in range(1, years + 1):
            projected_fcf *= (1.0 + cagr)
            pv_fcf += projected_fcf / ((1.0 + wacc) ** t)
        
        terminal_val = (projected_fcf * (1.0 + g)) / (wacc - g)
        pv_terminal = terminal_val / ((1.0 + wacc) ** years)
        return (pv_fcf + pv_terminal) - target_ev

    # 二分法数值求解
    low, high = -0.50, 2.00
    implied_cagr = np.nan
    for _ in range(100):
        mid = (low + high) / 2.0
        diff = pv_diff(mid)
        if abs(diff) < 1e-2:
            implied_cagr = mid
            break
        if diff < 0:
            low = mid
        else:
            high = mid
    else:
        implied_cagr = mid

    # 生成敏感性分析矩阵 (Sensitivity Matrix: WACC vs CAGR 对公允股价的影响)
    wacc_range = [wacc - 0.02, wacc - 0.01, wacc, wacc + 0.01, wacc + 0.02]
    cagr_range = [implied_cagr - 0.05, implied_cagr - 0.02, implied_cagr, implied_cagr + 0.02, implied_cagr + 0.05]
    
    sens_matrix = []
    for r in wacc_range:
        row = {"WACC 折现率": f"{r*100:.1f}%"}
        for gr in cagr_range:
            if gr < -0.9 or r <= g:
                row[f"CAGR {gr*100:+.1f}%"] = "N/A"
                continue
            pv = 0.0
            cur_f = base_fcf
            for t in range(1, years + 1):
                cur_f *= (1.0 + gr)
                pv += cur_f / ((1.0 + r) ** t)
            tv = (cur_f * (1.0 + g)) / (r - g)
            pv_tv = tv / ((1.0 + r) ** years)
            fair_ev = pv + pv_tv
            fair_eq = fair_ev + total_cash - total_debt
            fair_p = fair_eq / shares_out
            row[f"CAGR {gr*100:+.1f}%"] = f"${fair_p:,.2f}" if fair_p > 0 else "$0.00"
        sens_matrix.append(row)

    sens_df = pd.DataFrame(sens_matrix)

    return {
        "target_ev": target_ev,
        "market_cap": market_cap,
        "implied_cagr": implied_cagr,
        "sensitivity_matrix": sens_df
    }


# ------------------------------------------------------------------
# 半导体核心资产池与代表性配置
# ------------------------------------------------------------------
SEMI_BASKET = [
    {"symbol": "SOXX", "name": "费城半导体 ETF (SOXX)", "role": "行业市值基准 ETF"},
    {"symbol": "NVDA", "name": "英伟达 (NVIDIA)", "role": "AI 算力 GPU / 数据中心龙头"},
    {"symbol": "TSM", "name": "台积电 (TSMC)", "role": "先进制程晶圆代工垄断"},
    {"symbol": "ASML", "name": "阿斯麦 (ASML)", "role": "EUV / High-NA 极紫外光刻机绝对霸主"},
    {"symbol": "AVGO", "name": "博通 (Broadcom)", "role": "网络交换芯片 / 自定义 ASIC 龙头"},
    {"symbol": "AMD", "name": "超威半导体 (AMD)", "role": "x86 CPU / GPU 第二极"},
    {"symbol": "QCOM", "name": "高通 (Qualcomm)", "role": "移动通信 SoC / 边缘端 AI 龙头"},
    {"symbol": "MU", "name": "美光科技 (Micron)", "role": "HBM3e / 存储芯片超级周期核心"},
    {"symbol": "AMAT", "name": "应用材料 (Applied Materials)", "role": "前道综合设备龙头"},
    {"symbol": "LRCX", "name": "泛林半导体 (Lam Research)", "role": "刻蚀与薄膜沉积设备供应商"},
    {"symbol": "KLAC", "name": "科磊 (KLA Corp)", "role": "过程控制与量检测设备垄断"},
    {"symbol": "MRVL", "name": "迈威尔科技 (Marvell)", "role": "定制化 AI 算力与光互联芯片"},
    {"symbol": "ARM", "name": "安谋 (Arm Holdings)", "role": "能效算力架构 IP 垄断"}
]


# ==================================================================
# 顶栏主标题与全局状态监控
# ==================================================================
st.title("🏛️ 美股与宏观经济深度量化决策终端")
st.caption(f"🚀 系统构建状态: **实时连通** | 数据最后刷新: **{current_et_str}** | 引擎支持: **FRED 宏观高频数据库** & **yfinance 全息实时流**")

# 顶级 Tab 导航栏
tab_macro, tab_stock, tab_semi, tab_company = st.tabs([
    "🌐 宏观与市场总览 (Macro & Breadth)",
    "🔍 个股量化与估值追踪 (Stock Tracker)",
    "⚡ 芯片半导体产业链 (Semiconductor Tracker)",
    "🏢 公司概览与财报全景 (Company Profile & Financials)"
])


# ==================================================================
# TAB 1: 宏观与市场总览 (Macro & Market Breadth)
# ==================================================================
with tab_macro:
    st.sidebar.header("⚙️ 宏观图表动态 Y 轴自动缩放控制")
    macro_tf = st.sidebar.radio(
        "选择宏观图表时间范围 (自动精细缩放 Y 轴):",
        ["1M", "3M", "6M", "1Y", "3Y", "5Y", "10Y", "ALL"],
        index=5,
        key="global_macro_timeframe"
    )

    # --- 1. 原版国债收益率曲线图表 ---
    st.header("📊 美债收益率曲线 (Yield Curve)")

    treasury_csv = "daily-treasury-rates.csv"
    treasury_updated = get_file_updated_time_eastern(treasury_csv)

    if os.path.exists(treasury_csv):
        df_treasury_raw = pd.read_csv(treasury_csv)
        if not df_treasury_raw.empty:
            date_col = 'Date' if 'Date' in df_treasury_raw.columns else df_treasury_raw.columns[0]
            df_treasury_raw['Date'] = pd.to_datetime(df_treasury_raw[date_col])
            
            fig_tr = create_treasury_chart(df_treasury_raw, timeframe=macro_tf, height=480)
            if fig_tr:
                st.plotly_chart(fig_tr, use_container_width=True)

            fig_spread = create_yield_spreads_chart(df_treasury_raw, timeframe=macro_tf, height=420)
            if fig_spread:
                st.plotly_chart(fig_spread, use_container_width=True)

    st.markdown("---")

    # --- 2. 宏观领先与先行指标网格 ---
    st.header("🌊 宏观高频体温计与先行指标系统")
    
    col_m1, col_m2 = st.columns(2)
    with col_m1:
        fig_sahm = create_sahm_rule_chart(timeframe=macro_tf, height=400)
        if fig_sahm:
            st.plotly_chart(fig_sahm, use_container_width=True)

        fig_claims = create_jobless_claims_chart(timeframe=macro_tf, height=400)
        if fig_claims:
            st.plotly_chart(fig_claims, use_container_width=True)

        fig_sloos = create_sloos_credit_chart(timeframe=macro_tf, height=400)
        if fig_sloos:
            st.plotly_chart(fig_sloos, use_container_width=True)

        fig_m2 = create_m2_money_supply_chart(timeframe=macro_tf, height=400)
        if fig_m2:
            st.plotly_chart(fig_m2, use_container_width=True)

    with col_m2:
        fig_net_liq = create_net_liquidity_chart(timeframe=macro_tf, height=400)
        if fig_net_liq:
            st.plotly_chart(fig_net_liq, use_container_width=True)

        fig_sofr = create_sofr_iorb_chart(timeframe=macro_tf, height=400)
        if fig_sofr:
            st.plotly_chart(fig_sofr, use_container_width=True)

        fig_capex = create_core_capex_chart(timeframe=macro_tf, height=400)
        if fig_capex:
            st.plotly_chart(fig_capex, use_container_width=True)

        fig_dxy = create_dxy_chart(timeframe=macro_tf, height=400)
        if fig_dxy:
            st.plotly_chart(fig_dxy, use_container_width=True)

    st.markdown("---")

    # --- 3. 市场广度与情绪指数 ---
    st.header("📈 美股市场广度与投资者情绪监控")
    render_market_breadth_ui()

    col_e1, col_e2 = st.columns(2)
    with col_e1:
        fig_top10 = create_top10_concentration_chart(height=420)
        if fig_top10:
            st.plotly_chart(fig_top10, use_container_width=True)

    with col_e2:
        fig_fg = create_cnn_fear_greed_chart(current_val=58.0, height=420)
        if fig_fg:
            st.plotly_chart(fig_fg, use_container_width=True)


# ==================================================================
# TAB 2: 个股量化与估值追踪 (Stock Tracker)
# ==================================================================
with tab_stock:
    st.header("🔍 个股深度量化与多因子估值追踪")
    st.caption(f"🕒 实时数据抓取 (美东时间): **{current_et_str}** | 整合量价趋势、PE Band 估值带、反向 DCF 增长率反推与财报全景")

    # 标的选择栏
    stock_col1, stock_col2, stock_col3, stock_col4 = st.columns([2, 2, 2, 2])

    popular_tickers = [
        "NVDA", "AAPL", "MSFT", "AMZN", "GOOGL", "META", "TSLA",
        "AVGO", "TSM", "AMD", "ASML", "BRK-B", "LLY", "JPM", "V", "PLTR"
    ]

    with stock_col1:
        selected_quick_ticker = st.selectbox("📌 快捷选择热门权重股:", popular_tickers, index=0)

    with stock_col2:
        custom_ticker_input = st.text_input("✍️ 或输入自定义美股 Ticker:", value="").strip().upper()

    ticker_to_analyze = custom_ticker_input if custom_ticker_input else selected_quick_ticker

    with stock_col3:
        chart_style = st.selectbox("📊 图表类型:", ["Candlestick (K线图)", "Line (收盘价折线)"], index=0)
        chart_type_val = "Candlestick" if "Candlestick" in chart_style else "Line"

    with stock_col4:
        stock_timeframe = st.selectbox("⏱️ 走势图时间窗口:", ["1M", "3M", "6M", "YTD", "1Y", "3Y", "5Y", "ALL"], index=4)

    st.markdown("---")

    with st.spinner(f"正在获取 {ticker_to_analyze} 实时行情、估值模型与财务数据..."):
        df_stock_hist = get_stock_historical_data(ticker_to_analyze, period="5y")
        stock_info = get_stock_fundamentals(ticker_to_analyze)
        fin_stmt_dict = get_stock_financial_statements(ticker_to_analyze)

    if stock_info:
        comp_name = stock_info.get("shortName") or stock_info.get("longName") or ticker_to_analyze
        sector = stock_info.get("sector", "N/A")
        industry = stock_info.get("industry", "N/A")
        cur_price = stock_info.get("currentPrice") or stock_info.get("regularMarketPrice") or stock_info.get("previousClose")
        prev_close = stock_info.get("regularMarketPreviousClose") or stock_info.get("previousClose")
        
        price_diff = (cur_price - prev_close) if (cur_price and prev_close) else 0.0
        price_diff_pct = (price_diff / prev_close * 100) if prev_close else 0.0

        st.subheader(f"🏢 {comp_name} ({ticker_to_analyze}) — {sector} | {industry}")
        
        # 1. 核心价格与估值 KPI 卡片
        kpi_r1_1, kpi_r1_2, kpi_r1_3, kpi_r1_4 = st.columns(4)
        
        if cur_price is not None:
            kpi_r1_1.metric(
                "最新市价 (USD)",
                f"${cur_price:,.2f}",
                delta=f"{price_diff:+,.2f} ({price_diff_pct:+.2f}%)"
            )
        
        mcap = stock_info.get("marketCap")
        kpi_r1_2.metric("总市值 (Market Cap)", f"${mcap/1e9:,.2f} B" if mcap else "N/A")

        pe_ttm = stock_info.get("trailingPE")
        kpi_r1_3.metric("滚动市盈率 (PE TTM)", f"{pe_ttm:.1f}x" if pe_ttm else "N/A")

        fwd_pe = stock_info.get("forwardPE")
        kpi_r1_4.metric("远期市盈率 (Forward PE)", f"{fwd_pe:.1f}x" if fwd_pe else "N/A")

        # 第二排核心指标
        kpi_r2_1, kpi_r2_2, kpi_r2_3, kpi_r2_4 = st.columns(4)
        ps_ttm = stock_info.get("priceToSalesTrailing12Months")
        kpi_r2_1.metric("市销率 (PS TTM)", f"{ps_ttm:.2f}x" if ps_ttm else "N/A")

        gm = stock_info.get("grossMargins")
        kpi_r2_2.metric("毛利率 (Gross Margin)", f"{gm*100:.1f}%" if gm is not None else "N/A")

        roe = stock_info.get("returnOnEquity")
        kpi_r2_3.metric("净资产收益率 (ROE)", f"{roe*100:.1f}%" if roe is not None else "N/A")

        beta = stock_info.get("beta")
        kpi_r2_4.metric("Beta 系数 (波动率)", f"{beta:.2f}" if beta is not None else "N/A")

    # 3. 交互式 K 线与均线副图
    if df_stock_hist is not None and not df_stock_hist.empty:
        fig_stock = create_stock_price_chart(
            df_stock_hist,
            symbol=ticker_to_analyze,
            chart_type=chart_type_val,
            timeframe=stock_timeframe
        )
        if fig_stock:
            st.plotly_chart(fig_stock, use_container_width=True)
    else:
        st.warning(f"未能获取 {ticker_to_analyze} 的历史价格图表数据。")

    # ==================================================================
    # 4. 扩展模块一：历史估值分位与 PE / PS Band (估值带走势)
    # ==================================================================
    st.markdown("---")
    st.subheader("📈 历史估值分位与 PE / PS Band (估值通道透视)")
    st.caption("叠加历史动态估值倍数通道，评估当前股价处于历史估值的折溢价状态与合理中枢")

    val_col1, val_col2 = st.columns([3, 1])
    with val_col2:
        val_type_choice = st.radio("选择估值带类型:", ["PE Band (市盈率)", "PS Band (市销率)"], index=0)
        val_type_code = "PE" if "PE" in val_type_choice else "PS"
        band_tf = st.selectbox("估值带时间跨度:", ["1Y", "3Y", "5Y", "ALL"], index=1, key="band_timeframe")

    with val_col1:
        cur_pe_val = stock_info.get("trailingPE") if stock_info else None
        cur_eps_val = stock_info.get("trailingEps") if stock_info else None

        if df_stock_hist is not None and not df_stock_hist.empty:
            fig_band = create_pe_ps_band_chart(
                df_stock_hist,
                symbol=ticker_to_analyze,
                current_eps=cur_eps_val,
                current_pe=cur_pe_val,
                valuation_type=val_type_code,
                timeframe=band_tf
            )
            if fig_band:
                st.plotly_chart(fig_band, use_container_width=True)
                with st.expander(f"💡 {val_type_code} Band 估值通道投资解读", expanded=False):
                    st.markdown(f"""
                    * **估值通道逻辑**：以公司当前盈利/营收能力为基准，绘制多个历史代表性估值倍数（如 0.6x、0.8x、1.0x、1.25x、1.5x 倍数通道）。
                    * **超买/超卖信号**：
                      * 股价触及或突破顶轨（高估值通道）：表明市场给予极高预期溢价，情绪可能过热。
                      * 股价回落至底轨（低估值通道）：通常对应基本面利空充分出清或悲观情绪超跌区间。
                    """)
        else:
            st.info("估值带图表数据加载中。")

    # ==================================================================
    # 5. 扩展模块二：反向 DCF 估值测算器 (Reverse DCF & Implied Growth)
    # ==================================================================
    st.markdown("---")
    st.subheader("🎯 反向 DCF 估值测算器 (Reverse DCF & Implied Growth)")
    st.caption("基于自由现金流折现模型，根据当前股价反推市场隐含的未来 5–10 年 FCF 复合年增长率 (Implied CAGR)")

    if stock_info:
        cur_p = stock_info.get("currentPrice") or stock_info.get("regularMarketPrice") or stock_info.get("previousClose") or 100.0
        shs = stock_info.get("sharesOutstanding")
        if not shs and mcap:
            shs = mcap / cur_p
        
        base_fcf_raw = stock_info.get("freeCashflow") or (mcap / (cur_pe_val if cur_pe_val else 25.0))
        base_fcf_bn = round(base_fcf_raw / 1e9, 2) if base_fcf_raw else 10.0
        
        tot_cash_bn = (stock_info.get("totalCash") or 0.0) / 1e9
        tot_debt_bn = (stock_info.get("totalDebt") or 0.0) / 1e9

        dcf_c1, dcf_c2, dcf_c3, dcf_c4 = st.columns(4)
        with dcf_c1:
            input_wacc = st.slider("加权资本成本 WACC 折现率 (%)", 6.0, 15.0, 9.0, 0.5) / 100.0
        with dcf_c2:
            input_g = st.slider("永续增长率 Terminal g (%)", 1.0, 4.0, 2.5, 0.25) / 100.0
        with dcf_c3:
            input_years = st.radio("显式预测期 (Years):", [5, 10], index=0)
        with dcf_c4:
            input_fcf = st.number_input("基准年自由现金流 ($B):", value=float(max(0.1, base_fcf_bn)), step=1.0) * 1e9

        dcf_result = calculate_reverse_dcf(
            current_price=cur_p,
            shares_out=shs,
            base_fcf=input_fcf,
            wacc=input_wacc,
            g=input_g,
            years=input_years,
            total_cash=tot_cash_bn * 1e9,
            total_debt=tot_debt_bn * 1e9
        )

        if dcf_result:
            implied_cagr = dcf_result["implied_cagr"]
            
            res_c1, res_c2, res_c3 = st.columns(3)
            if not np.isnan(implied_cagr):
                res_c1.metric(
                    "市场隐含未来 FCF 复合增速 (CAGR)",
                    f"{implied_cagr*100:+.2f}%",
                    delta=f"预测期: {input_years} 年 | WACC: {input_wacc*100:.1f}%"
                )
            else:
                res_c1.metric("市场隐含 FCF 复合增速 (CAGR)", "超出常规搜索收敛范围")

            res_c2.metric("当前企业价值 (EV)", f"${dcf_result['target_ev']/1e9:,.2f} B")
            res_c3.metric("净现金 / 净负债头寸", f"${(tot_cash_bn - tot_debt_bn):+,.2f} B")

            st.markdown("##### 📊 内在价值公允股价敏感性分析矩阵 (Sensitivity Matrix)")
            st.caption("纵轴为不同资本折现率 WACC，横轴为公司实际可能实现的未来 FCF 复合增速，单元格对应估算出的公允每股内在价值 ($)")
            sens_df = dcf_result.get("sensitivity_matrix")
            if sens_df is not None and not sens_df.empty:
                st.dataframe(sens_df, hide_index=True, use_container_width=True)
                with st.expander("💡 反向 DCF 估值测算逻辑与安全边际指引", expanded=False):
                    st.markdown(f"""
                    * **反向推导原理**：普通 DCF 往往受主观乐观假设影响过大；**反向 DCF** 则是探寻“**当前市价 (${cur_p:.2f}) 已经把未来多高的增长定价进去了 (Priced-in)**”。
                    * **安全边际判断**：
                      * 若市场隐含 CAGR (**{implied_cagr*100:+.1f}%**) 显著**低于**您对公司行业扩张与护城河的真实增长预期，则存在**安全边际 (Margin of Safety)**。
                      * 若市场隐含 CAGR 处于不可思议的超高位（如 $> 40\\%$ 且持续 5 年），则意味着估值容错率极低，任何业绩不及预期都将面临“杀估值”。
                    """)
        else:
            st.info("反向 DCF 测算需要基准自由现金流为正值且折现率大于永续增长率。")

    # ==================================================================
    # 6. 扩展模块三：技术面动量指标系统 (RSI, MACD & 200MA 年线偏离度)
    # ==================================================================
    st.markdown("---")
    st.subheader("⚡ 技术面动量指标系统 (RSI, MACD & 200MA 年线偏离度)")
    st.caption("综合跟踪 14 日强弱动量 RSI、MACD 趋势金叉/死叉与 200MA 均线乖离率 (Bias %)")

    if df_stock_hist is not None and not df_stock_hist.empty:
        latest_c = df_stock_hist['Close'].iloc[-1]
        ma200_val = df_stock_hist['Close'].rolling(200).mean().iloc[-1] if len(df_stock_hist) >= 200 else None
        bias_200 = ((latest_c - ma200_val) / ma200_val * 100) if ma200_val else None

        d_close = df_stock_hist['Close'].diff()
        g_s = (d_close.where(d_close > 0, 0.0)).fillna(0.0)
        l_s = (-d_close.where(d_close < 0, 0.0)).fillna(0.0)
        ag = g_s.ewm(alpha=1.0/14.0, min_periods=14, adjust=False).mean()
        al = l_s.ewm(alpha=1.0/14.0, min_periods=14, adjust=False).mean()
        rs_val = ag / al.replace(0, np.nan)
        rsi_series = (100.0 - (100.0 / (1.0 + rs_val))).fillna(50.0)
        latest_rsi = rsi_series.iloc[-1]

        e12 = df_stock_hist['Close'].ewm(span=12, adjust=False).mean()
        e26 = df_stock_hist['Close'].ewm(span=26, adjust=False).mean()
        macd_s = e12 - e26
        sig_s = macd_s.ewm(span=9, adjust=False).mean()
        hist_s = macd_s - sig_s
        latest_macd = macd_s.iloc[-1]
        latest_sig = sig_s.iloc[-1]

        t_c1, t_c2, t_c3 = st.columns(3)
        t_c1.metric(
            "14日相对强弱指标 (RSI 14)",
            f"{latest_rsi:.1f}",
            delta="超买警惕 (>70)" if latest_rsi > 70 else ("超卖机会 (<30)" if latest_rsi < 30 else "中性震荡"),
            delta_color="inverse" if latest_rsi > 70 else ("normal" if latest_rsi < 30 else "off")
        )

        t_c2.metric(
            "200MA 年线乖离率 (Bias %)",
            f"{bias_200:+.1f}%" if bias_200 else "N/A",
            delta="极端多头均线发散" if bias_200 and bias_200 > 25 else ("深幅跌破年线" if bias_200 and bias_200 < -15 else "稳健运行"),
            delta_color="normal" if bias_200 and bias_200 > 0 else "inverse"
        )

        t_c3.metric(
            "MACD (12, 26, 9) 柱状能量",
            f"{hist_s.iloc[-1]:+.2f}",
            delta="多头动能主导" if hist_s.iloc[-1] > 0 else "空头动能发酵",
            delta_color="normal" if hist_s.iloc[-1] > 0 else "inverse"
        )

        fig_tech = create_technical_momentum_chart(df_stock_hist, symbol=ticker_to_analyze, timeframe="1Y")
        if fig_tech:
            st.plotly_chart(fig_tech, use_container_width=True)
            with st.expander("💡 技术动量系统指标信号研判指引", expanded=False):
                st.markdown("""
                * **14 日 RSI**：
                  * $> 70$ 进入超买高热区，短线资金追高性价比恶化；
                  * $< 30$ 进入超跌冰点区，往往孕育情绪衰竭反弹。
                * **200MA 年线乖离率**：
                  * 当股价高于 200MA 超过 $+30\%$ 时，存在显著的“均值回归”回踩需求；
                  * 当股价回踩 200MA（$0\% \sim +5\%$）并企稳，通常是长线牛股理想的加仓防守点。
                * **MACD 动能柱**：
                  * 零轴上方红柱持续拉长为加速主升浪；红柱缩短或顶背离预警动能放缓。
                """)


# ==================================================================
# TAB 3: 芯片半导体产业链 (Semiconductor Tracker)
# ==================================================================
with tab_semi:
    st.header("⚡ 芯片半导体产业链深度追踪")
    st.caption(f"🕒 实时数据更新 (美东时间): **{current_et_str}** | 覆盖算力、晶圆代工、光刻设备、存储与模拟芯片全产业链")

    # 1. 行业基准与核心标的相对收益对比
    st.subheader("📈 半导体龙头多股累计收益率对比 (Relative Performance)")

    semi_symbols_all = [item["symbol"] for item in SEMI_BASKET]
    
    col_s1, col_s2 = st.columns([3, 1])
    with col_s1:
        default_selected_semi = ["NVDA", "TSM", "ASML", "AVGO", "AMD", "MU", "SOXX"]
        selected_semi_tickers = st.multiselect(
            "选择要进行收益率对比的标的:",
            semi_symbols_all,
            default=default_selected_semi
        )
    with col_s2:
        semi_timeframe = st.selectbox(
            "选择对比时间区间:",
            ["1M", "3M", "6M", "YTD", "1Y", "3Y", "5Y"],
            index=3,
            key="semi_timeframe_select"
        )

    if selected_semi_tickers:
        with st.spinner("正在抓取半导体标的历史价格并计算归一化收益率..."):
            df_semi_dict = {}
            for s in selected_semi_tickers:
                df_s = get_stock_historical_data(s, period="5y")
                if df_s is not None and not df_s.empty:
                    df_semi_dict[s] = df_s

        if df_semi_dict:
            fig_rel_perf = create_relative_performance_chart(df_semi_dict, base_symbol="SOXX", timeframe=semi_timeframe)
            if fig_rel_perf:
                st.plotly_chart(fig_rel_perf, use_container_width=True)

    st.markdown("---")

    # 2. 半导体产业链估值与成长性散点透视图
    st.subheader("🎯 半导体全产业链市值 vs PS / PE 估值气泡透视图")
    st.caption("横轴为市值规模，纵轴为滚动估值倍数，气泡大小对应营收规模")

    semi_metrics_list = []
    for s_info in SEMI_BASKET:
        sym = s_info["symbol"]
        info_d = get_stock_fundamentals(sym)
        if info_d:
            semi_metrics_list.append({
                "Symbol": sym,
                "Name": s_info["name"],
                "Role": s_info["role"],
                "MarketCap": info_d.get("marketCap", 0),
                "PE_TTM": info_d.get("trailingPE", np.nan),
                "PS_TTM": info_d.get("priceToSalesTrailing12Months", np.nan),
                "GrossMargin": info_d.get("grossMargins", np.nan),
                "Revenue": info_d.get("totalRevenue", 0)
            })

    if semi_metrics_list:
        df_semi_metrics = pd.DataFrame(semi_metrics_list)
        st.markdown("##### 📋 半导体产业链关键龙头核心量化指标跟踪表")
        st.dataframe(
            df_semi_metrics[[
                "Symbol", "Name", "Role", "MarketCap", "PE_TTM", "PS_TTM", "GrossMargin"
            ]].style.format({
                "MarketCap": lambda x: f"${x/1e9:,.1f} B" if pd.notna(x) and x > 0 else "N/A",
                "PE_TTM": lambda x: f"{x:.1f}x" if pd.notna(x) else "N/A",
                "PS_TTM": lambda x: f"{x:.2f}x" if pd.notna(x) else "N/A",
                "GrossMargin": lambda x: f"{x*100:.1f}%" if pd.notna(x) else "N/A"
            }),
            hide_index=True,
            use_container_width=True
        )


# ==================================================================
# TAB 4: 公司概览与财报全景 (Company Profile & Financials)
# ==================================================================
with tab_company:
    try:
        render_company_deep_dive_tab()
    except Exception as e:
        st.error(f"个股深度分析模块加载失败: {e}")
