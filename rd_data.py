import os
import sys
import datetime
import json
import urllib.request
import importlib
import pandas as pd
import numpy as np
import streamlit as st
from zoneinfo import ZoneInfo

from data_processing import load_and_transform_data
from market_breadth_viz import render_market_breadth_ui

# ------------------------------------------------------------------
# 模块导入与热重载安全机制 (防止 Streamlit Cloud 内存模块缓存导致 ImportError)
# ------------------------------------------------------------------
try:
    import visualization
    importlib.reload(visualization)
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
    create_dcf_sensitivity_heatmap,
    create_radar_scorecard,
    create_risk_reward_scatter,
    create_market_regime_matrix,
    create_drawdown_chart,
    create_trailing_forward_pe_chart,
    create_fcf_conversion_chart,
    create_capex_revenue_scatter,
    create_margin_stability_chart,
    create_multi_stock_comparison_chart,
    create_semiconductor_cycle_dashboard,
    create_wafer_capacity_chart,
    create_hbm_pricing_chart,
    create_semiconductor_capex_tracker
)
from market_analysis import (
    get_unemployment_data,
    get_credit_spread_data,
    get_fed_balance_sheet_data,
    get_gold_oil_ratio_data,
    get_real_yield_breakeven_data,
    get_nfci_data,
    get_net_liquidity_data,
    get_sofr_iorb_data,
    get_top10_concentration_data,
    get_vix_data,
    get_cnn_fear_greed_data,
    get_stock_historical_prices,
    get_stock_quarterly_financials,
    get_stock_valuation_metrics,
    get_all_tracked_stocks_data,
    get_semiconductor_cycle_indicators,
    get_semiconductor_matrix_data,
    get_semiconductor_comparative_prices
)

# ------------------------------------------------------------------
# Streamlit 页面基础配置 (Page Configuration)
# ------------------------------------------------------------------
st.set_page_config(
    page_title="全球宏观流动性、美股量化估值与半导体产业链追踪平台",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 自定义全局 CSS 样式注入 (深色暗调高对比度财经终端风格)
st.markdown("""
<style>
    .metric-card {
        background-color: #1e293b;
        border-radius: 8px;
        padding: 16px;
        color: #f8fafc;
        border: 1px solid #334155;
    }
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        padding: 10px 20px;
        font-weight: 600;
        border-radius: 6px 6px 0px 0px;
    }
    .indicator-badge {
        display: inline-block;
        padding: 4px 8px;
        border-radius: 4px;
        font-size: 0.85em;
        font-weight: bold;
        margin-right: 6px;
    }
    .badge-bullish { background-color: #065f46; color: #34d399; }
    .badge-neutral { background-color: #1e293b; color: #94a3b8; }
    .badge-bearish { background-color: #7f1d1d; color: #f87171; }
    .badge-warning { background-color: #78350f; color: #fbbf24; }
</style>
""", unsafe_allow_html=True)


# ------------------------------------------------------------------
# 辅助工具函数：美东时间与文件更新时间解析
# ------------------------------------------------------------------
def get_current_time_str_eastern() -> str:
    """获取当前美东时间格式化字符串 (EDT/EST 自动处理)"""
    return datetime.datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %H:%M:%S %Z")


def get_file_updated_time_eastern(filepath: str) -> str:
    """获取本地文件的最新修改时间并转化为美东时间"""
    if os.path.exists(filepath):
        mtime = os.path.getmtime(filepath)
        dt_utc = datetime.datetime.fromtimestamp(mtime, tz=datetime.timezone.utc)
        dt_et = dt_utc.astimezone(ZoneInfo("America/New_York"))
        return dt_et.strftime("%Y-%m-%d %H:%M:%S %Z")
    return "未知"


# ------------------------------------------------------------------
# FRED API KEY 全局安全注入
# ------------------------------------------------------------------
FRED_API_KEY = os.environ.get("FRED_API_KEY", "")
if not FRED_API_KEY:
    try:
        FRED_API_KEY = st.secrets.get("FRED_API_KEY", "")
    except Exception:
        FRED_API_KEY = ""

if not FRED_API_KEY:
    st.sidebar.warning("⚠️ 未检测到 FRED_API_KEY，改用公开 FRED 数据源。")

current_et_str = get_current_time_str_eastern()

# 侧边栏：全局信息
st.sidebar.markdown(f"🕒 **美东时间 (EDT)**: `{current_et_str}`")
st.sidebar.markdown("---")

# 核心 Tab 顶层容器
tab_macro, tab_stock, tab_semi, tab_company = st.tabs([
    "🌐 宏观与市场总览 (Macro & Breadth)",
    "🔍 个股量化与估值追踪 (Stock Tracker)",
    "⚡ 芯片半导体产业链 (Semiconductor Tracker)",
    "🏢 个股深度与基本面剖析 (Company Profile & Financials)"
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

    with st.spinner("正在获取并转换国债收益率数据..."):
        df_long = load_and_transform_data()

    if df_long is not None and not df_long.empty:
        latest_date = df_long['Date'].max().strftime('%Y-%m-%d')
        st.caption(f"🕒 数据刷新时间 (美东时间): **{treasury_updated}** | 最新数据交易日: **{latest_date}**")
        fig_treasury = create_treasury_chart(df_long)
        if fig_treasury:
            st.plotly_chart(fig_treasury, use_container_width=True)
    else:
        st.warning("⚠️ 暂无美债收益率数据，请检查 daily-treasury-rates.csv 文件或数据接口。")

    st.markdown("---")

    # --- 2. 市场宽度体系可视化 ---
    st.header("🌊 美股市场宽度指标体系 (Market Breadth Dashboard)")
    breadth_csv = "market_breadth.csv"
    breadth_updated = get_file_updated_time_eastern(breadth_csv)
    st.caption(f"🕒 市场宽度数据更新时间 (美东时间): **{breadth_updated}**")

    # 调用 market_breadth_viz 模块进行图表渲染
    try:
        render_market_breadth_ui()
    except Exception as e:
        st.error(f"市场宽度看板渲染异常: {e}")

    st.markdown("---")

    # --- 3. 宏观流动性与经济先行指标 ---
    st.header("💧 宏观流动性、信用利差与通胀预期 (Macro Indicators)")

    col_m1, col_m2 = st.columns(2)

    with col_m1:
        st.subheader("1. 失业率与 Sahm Rule 衰退监测")
        with st.spinner("加载失业率与 Sahm Rule 指标..."):
            df_unemp = get_unemployment_data()
        if df_unemp is not None and not df_unemp.empty:
            fig_unemp = create_unemployment_chart(df_unemp, timeframe=macro_tf)
            if fig_unemp:
                st.plotly_chart(fig_unemp, use_container_width=True)
        else:
            st.info("失业率数据加载中...")

        st.subheader("3. 美联储资产负债表规模 (Fed Total Assets)")
        with st.spinner("加载美联储资产负债表数据..."):
            df_fed_bs = get_fed_balance_sheet_data()
        if df_fed_bs is not None and not df_fed_bs.empty:
            fig_fed = create_fed_balance_sheet_chart(df_fed_bs, timeframe=macro_tf)
            if fig_fed:
                st.plotly_chart(fig_fed, use_container_width=True)
        else:
            st.info("美联储资产负债表数据加载中...")

        st.subheader("5. 实际利率 (10Y TIPS) 与 盈亏平衡通胀率 (Breakeven)")
        with st.spinner("加载实际利率与通胀预期数据..."):
            df_tips = get_real_yield_breakeven_data()
        if df_tips is not None and not df_tips.empty:
            fig_tips = create_real_yield_breakeven_chart(df_tips, timeframe=macro_tf)
            if fig_tips:
                st.plotly_chart(fig_tips, use_container_width=True)
        else:
            st.info("实际利率数据加载中...")

        st.subheader("7. 纯净净流动性指标 (Net Liquidity)")
        st.caption("公式: 美联储总资产 - 财政部账户存款 (TGA) - 隔夜逆回购 (ON RRP)")
        with st.spinner("计算美联储净流动性..."):
            df_net_liq = get_net_liquidity_data()
        if df_net_liq is not None and not df_net_liq.empty:
            fig_net_liq = create_net_liquidity_chart(df_net_liq, timeframe=macro_tf)
            if fig_net_liq:
                st.plotly_chart(fig_net_liq, use_container_width=True)
        else:
            st.info("净流动性数据加载中...")

        st.subheader("9. 标普 500 前 10 大权重股集中度 (Top 10 Concentration)")
        with st.spinner("计算标普500集中度指标..."):
            df_top10 = get_top10_concentration_data()
        if df_top10 is not None and not df_top10.empty:
            fig_top10 = create_top10_concentration_chart(df_top10, timeframe=macro_tf)
            if fig_top10:
                st.plotly_chart(fig_top10, use_container_width=True)
        else:
            st.info("权重集中度数据加载中...")

        st.subheader("11. CNN 恐惧与贪婪指数 (CNN Fear & Greed Index)")
        with st.spinner("加载 CNN 恐惧与贪婪指数..."):
            df_fg = get_cnn_fear_greed_data()
        if df_fg is not None and not df_fg.empty:
            fig_fg = create_cnn_fear_greed_chart(df_fg)
            if fig_fg:
                st.plotly_chart(fig_fg, use_container_width=True)
        else:
            st.info("恐惧与贪婪指数加载中...")

    with col_m2:
        st.subheader("2. 投资级与高收益企业债信用利差 (Credit Spreads)")
        with st.spinner("加载信用利差数据..."):
            df_spread = get_credit_spread_data()
        if df_spread is not None and not df_spread.empty:
            fig_spread = create_credit_spread_chart(df_spread, timeframe=macro_tf)
            if fig_spread:
                st.plotly_chart(fig_spread, use_container_width=True)
        else:
            st.info("信用利差数据加载中...")

        st.subheader("4. 黄金/原油比价 (Gold / WTI Oil Ratio)")
        with st.spinner("加载黄金与原油比价数据..."):
            df_gold_oil = get_gold_oil_ratio_data()
        if df_gold_oil is not None and not df_gold_oil.empty:
            fig_go = create_gold_oil_ratio_chart(df_gold_oil, timeframe=macro_tf)
            if fig_go:
                st.plotly_chart(fig_go, use_container_width=True)
        else:
            st.info("金油比数据加载中...")

        st.subheader("6. 芝加哥联储全国金融状况指数 (NFCI)")
        with st.spinner("加载金融状况指数 (NFCI)..."):
            df_nfci = get_nfci_data()
        if df_nfci is not None and not df_nfci.empty:
            fig_nfci = create_nfci_chart(df_nfci, timeframe=macro_tf)
            if fig_nfci:
                st.plotly_chart(fig_nfci, use_container_width=True)
        else:
            st.info("NFCI 数据加载中...")

        st.subheader("8. 货币市场利率走廊: SOFR vs IORB 利差")
        st.caption("监测银行间短期流动性摩擦与回购市场利率倒挂风险")
        with st.spinner("加载 SOFR 与 IORB 利率走廊数据..."):
            df_sofr = get_sofr_iorb_data()
        if df_sofr is not None and not df_sofr.empty:
            fig_sofr = create_sofr_iorb_chart(df_sofr, timeframe=macro_tf)
            if fig_sofr:
                st.plotly_chart(fig_sofr, use_container_width=True)
        else:
            st.info("利率走廊数据加载中...")

        st.subheader("10. 芝加哥期权交易所波动率指数 (CBOE VIX)")
        with st.spinner("加载标普500波动率指数 (VIX)..."):
            df_vix = get_vix_data()
        if df_vix is not None and not df_vix.empty:
            fig_vix = create_vix_chart(df_vix, timeframe=macro_tf)
            if fig_vix:
                st.plotly_chart(fig_vix, use_container_width=True)
        else:
            st.info("VIX 数据加载中...")


# ==================================================================
# TAB 2: 个股量化与估值追踪 (Stock Tracker)
# ==================================================================
with tab_stock:
    st.header("🔍 美股核心标的量化深度透视与估值模型")
    st.caption("集成 DCF 现金流折现、历史估值通道 (PE/PS Band)、五维基本面雷达评分及财报质量归因")

    # 1. 股票代码输入与选择
    col_sel1, col_sel2 = st.columns([1, 3])
    with col_sel1:
        default_symbol = "NVDA"
        symbol_input = st.text_input(
            "输入美股代码 (Ticker):",
            value=default_symbol,
            key="stock_symbol_input"
        ).upper().strip()

    with col_sel2:
        st.markdown("**常用跟踪标的快捷选择:**")
        preset_symbols = ["NVDA", "AAPL", "MSFT", "AMAT", "TSM", "GOOGL", "AMZN", "META", "TSLA", "AVGO", "ASML", "AMD", "COST"]
        quick_cols = st.columns(len(preset_symbols))
        for idx, sym in enumerate(preset_symbols):
            if quick_cols[idx].button(sym, key=f"quick_sym_{sym}"):
                symbol_input = sym

    active_symbol = symbol_input if symbol_input else "NVDA"

    # 2. 抓取标的财务与市场数据
    with st.spinner(f"正在实时抓取 {active_symbol} 的财务数据、估值指标与历史价格..."):
        stock_prices = get_stock_historical_prices(active_symbol)
        stock_financials = get_stock_quarterly_financials(active_symbol)
        stock_valuation = get_stock_valuation_metrics(active_symbol)

    if stock_valuation:
        # 头部核心 KPI 指标展示
        c1, c2, c3, c4, c5, c6 = st.columns(6)
        c1.metric("公司代码", stock_valuation.get("ticker", active_symbol))
        c2.metric("当前股价", f"${stock_valuation.get('current_price', 0):.2f}")
        c3.metric("市值规模", f"${stock_valuation.get('market_cap', 0) / 1e9:.2f} B")
        c4.metric("TTM PE (市盈率)", f"{stock_valuation.get('pe_ratio', 0):.1f}x")
        c5.metric("Forward PE", f"{stock_valuation.get('forward_pe', 0):.1f}x")
        c6.metric("PS (市销率)", f"{stock_valuation.get('ps_ratio', 0):.1f}x")

    st.markdown("---")

    # 3. 股票历史走势与技术均线通道
    st.subheader(f"📈 {active_symbol} 历史股价走势与均线系统 (Price & Moving Averages)")
    price_tf = st.radio(
        "选择股价回溯周期:",
        ["1M", "3M", "6M", "YTD", "1Y", "3Y", "5Y", "MAX"],
        index=4,
        horizontal=True,
        key="stock_price_tf"
    )

    if stock_prices is not None and not stock_prices.empty:
        fig_price = create_stock_price_chart(stock_prices, ticker=active_symbol, timeframe=price_tf)
        if fig_price:
            st.plotly_chart(fig_price, use_container_width=True)
    else:
        st.info("股价历史数据加载中或未找到对应标的。")

    st.markdown("---")

    # 4. 估值通道分析 (PE / PS Band)
    st.subheader(f"🎯 {active_symbol} 历史估值通道 (Valuation Bands)")
    col_band1, col_band2 = st.columns([1, 1])

    with col_band1:
        st.markdown("**动态 PE 估值通道 (P/E Band)**")
        if stock_prices is not None and stock_financials is not None:
            fig_pe_band = create_pe_ps_band_chart(stock_prices, stock_financials, ticker=active_symbol, metric="PE")
            if fig_pe_band:
                st.plotly_chart(fig_pe_band, use_container_width=True)
        else:
            st.info("估值通道数据计算中...")

    with col_band2:
        st.markdown("**动态 PS 估值通道 (P/S Band)**")
        if stock_prices is not None and stock_financials is not None:
            fig_ps_band = create_pe_ps_band_chart(stock_prices, stock_financials, ticker=active_symbol, metric="PS")
            if fig_ps_band:
                st.plotly_chart(fig_ps_band, use_container_width=True)
        else:
            st.info("估值通道数据计算中...")

    st.markdown("---")

    # 5. 财务深度趋势与利润质量 (Financial Health & Margins)
    st.subheader(f"📑 {active_symbol} 季度财务趋势与盈利质量 (Financial Trajectory)")
    if stock_financials is not None and not stock_financials.empty:
        fig_fin_trend = create_financial_trends_chart(stock_financials, ticker=active_symbol)
        if fig_fin_trend:
            st.plotly_chart(fig_fin_trend, use_container_width=True)
    else:
        st.info("未获取到季度财务明细。")

    st.markdown("---")

    # 6. 动态 DCF 模型敏感性热力图与雷达综合评价
    st.subheader("⚖️ DCF 现金流折现敏感性分析与基本面综合雷达")
    col_dcf, col_radar = st.columns([1.2, 0.8])

    with col_dcf:
        st.markdown("**DCF 价值敏感性热力图 (WACC vs 永续增长率 g)**")
        fig_dcf = create_dcf_sensitivity_heatmap(active_symbol)
        if fig_dcf:
            st.plotly_chart(fig_dcf, use_container_width=True)
        else:
            st.info("DCF 敏感性模型计算中...")

    with col_radar:
        st.markdown("**五维基本面量化评分雷达 (Scorecard Radar)**")
        fig_radar = create_radar_scorecard(active_symbol)
        if fig_radar:
            st.plotly_chart(fig_radar, use_container_width=True)
        else:
            st.info("基本面评分雷达构建中...")


# ==================================================================
# TAB 3: 芯片半导体产业链 (Semiconductor Tracker)
# ==================================================================
with tab_semi:
    st.header("⚡ 芯片与半导体全产业链周期监测看板 (Semiconductor Industry)")
    st.caption("穿透晶圆制造、EDA/IP、光刻薄膜前道设备、先进封装与 AI 算力芯片核心景气循环")

    # 1. 行业宏观周期指标仪表盘
    st.subheader("🌐 全球半导体产业周期核心观测指标")
    with st.spinner("正在加载半导体周期高频前置指标..."):
        semi_indicators = get_semiconductor_cycle_indicators()

    if semi_indicators:
        fig_semi_dash = create_semiconductor_cycle_dashboard(semi_indicators)
        if fig_semi_dash:
            st.plotly_chart(fig_semi_dash, use_container_width=True)
    else:
        st.info("半导体高频前瞻数据汇总中...")

    st.markdown("---")

    # 2. 细分产业链龙头对比与多股走势
    st.subheader("🔬 半导体关键细分赛道标的收益率与估值横向比选")
    col_s1, col_s2 = st.columns([1, 1])

    with col_s1:
        default_semi_tickers = ["NVDA", "TSM", "ASML", "AMAT", "LRCX", "AVGO", "MU", "AMD"]
        selected_semi_tickers = st.multiselect(
            "选择半导体龙头标的进行历史相对收益率对比:",
            options=["NVDA", "TSM", "ASML", "AMAT", "LRCX", "KLAC", "AVGO", "QCOM", "MU", "AMD", "INTC", "TXN", "ARM", "MPWR", "MRVL", "SNPS", "CDNS"],
            default=default_semi_tickers,
            key="semi_tickers_multiselect"
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
            df_semi_prices = get_semiconductor_comparative_prices(selected_semi_tickers)
        
        if df_semi_prices is not None and not df_semi_prices.empty:
            fig_semi_rel = create_relative_performance_chart(
                df_semi_prices,
                tickers=selected_semi_tickers,
                timeframe=semi_timeframe
            )
            if fig_semi_rel:
                st.plotly_chart(fig_semi_rel, use_container_width=True)
        else:
            st.info("半导体标的历史价格数据加载中。")
    else:
        st.warning("请至少选择一个半导体标的进行对比展示。")

    # 2. 产业链估值与基本面横向比选矩阵
    st.markdown("---")
    st.subheader("📊 半导体全产业链核心标的估值与财务比选矩阵")
    st.caption("展示各环节龙头公司的最新市价、市值规模、PE/Forward PE、PS 估值倍数与毛利率")

    with st.spinner("正在汇总半导体产业链全量估值比选数据..."):
        df_matrix = get_semiconductor_matrix_data()

    if df_matrix is not None and not df_matrix.empty:
        st.dataframe(df_matrix, hide_index=True, use_container_width=True)
    else:
        st.info("比选矩阵数据加载中...")

    # 3. 半导体行业周期与 Capex 观察框架
    st.markdown("---")
    with st.expander("📖 查看《半导体产业周期、制程节点与 WFE 资本开支》投研分析指南", expanded=False):
        st.markdown("""
        ### 💡 半导体产业链四大核心投资与周期观察逻辑

        #### 1. 产业周期四阶段模型 (4-Stage Semiconductor Cycle)
        * **衰退出清期 (Downturn)**：下游消费电子/PC/手机需求萎缩，晶圆厂去库存降稼动率，存储芯片价格暴跌（如 2022H2–2023H1）。
        * **周期筑底期 (Bottoming)**：原厂主动削减资本开支 (Capex Cut) 与减产，渠道库存回归健康水位，现货价格企稳。
        * **复苏扩张期 (Expansion)**：新一轮科技创新周期（如 GenAI / 数据中心算力激增）拉动先进制程与 HBM 高价值量芯片需求，量价齐升。\n        * **繁荣过热期 (Peak/Overheating)**：全产业链产能供不应求，原厂激进扩产，交期大幅拉长；需警惕双重下单 (Double Booking) 后的需求高位回落。

        #### 2. 先进制程与设备前置指标 (WFE Capex as Leading Indicator)
        * **光刻与薄膜沉积设备 (ASML / AMAT / LRCX / KLAC)**：设备订单与出货通常**领先晶圆代工厂量产 6–12 个月**。
        * **台积电资本开支 (TSMC Capex)**：全球半导体景气度的绝对风向标，其中先进制程 (2nm/3nm) 与 CoWoS 先进封装产能分配直接决定 AI 算力供给上限。

        #### 3. 存储芯片高弹性杠杆 (DRAM / NAND & HBM Supercycle)
        * **存储芯片 (Micron / Samsung / SK Hynix)** 属于典型的大宗重资产周期品。在下行期由于固定资产折旧产生巨额亏损，但在景气上行期具备极强 EPS 盈利爆发弹性。
        * **HBM (高带宽内存)** 占用了大量 DRAM 晶圆晶片面积，对传统 DDR5 产生产能挤占效应，支撑整体存储价格中枢结构性上移。

        #### 4. 定制化芯片 ASIC vs 通用 GPU 架构博弈
        * **通用 GPU (NVDA / AMD)**：凭借 CUDA 生态与最高灵活性垄断大模型前沿训练与复杂推理。
        * **定制 ASIC (AVGO / MRVL)**：云厂商 (CSP) 为降低单 Token 成本自研推理芯片（如 Google TPU, AWS Trainium/Inferentia, Meta MTIA），博通作为芯片物理设计与 SerDes IP 独家合作伙伴长期受益。
        """)


# ==================================================================
# TAB 4: 个股深度与基本面剖析 (Company Profile & Financials)
# ==================================================================
with tab_company:
    try:
        render_company_deep_dive_tab()
    except Exception as e:
        st.error(f"个股深度分析模块加载失败: {e}")
