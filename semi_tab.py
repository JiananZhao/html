"""
Semiconductor Industry & Peer Comparison Tab (Tab 3)
"""
import streamlit as st
import pandas as pd
import numpy as np

from data_service import (
    get_semiconductor_comparative_prices,
    get_semiconductor_matrix_data,
)
from visualization import create_relative_performance_chart

def render_semi_tab():
    st.header("⚡ 芯片半导体产业链深度追踪")
    st.markdown("全产业链龙头标的相对超额收益、多因子估值比选矩阵与行业周期深度分析。")

    # 1. 相对收益表现对比
    st.subheader("📈 半导体龙头多股累计收益率对比 (Relative Performance)")
    col_semi_tf, col_semi_select = st.columns([2, 5])
    with col_semi_tf:
        semi_timeframe = st.selectbox(
            "选择相对收益观察周期:",
            ["1M", "3M", "6M", "1Y", "2Y", "3Y", "5Y"],
            index=3,
            key="semi_perf_tf"
        )

    semi_default_universe = ["NVDA", "TSM", "ASML", "AVGO", "AMD", "SOXX", "SMH"]
    semi_all_candidates = ["NVDA", "TSM", "ASML", "AVGO", "AMD", "AMAT", "LRCX", "KLAC", "ARM", "SNPS", "CDNS", "MRVL", "MU", "TXN", "ADI", "QCOM", "SOXX", "SMH"]

    with col_semi_select:
        selected_semi_tickers = st.multiselect(
            "选择对比展示的标的 (默认包含行业龙头与基准 ETF):",
            options=semi_all_candidates,
            default=semi_default_universe,
            key="semi_tickers_multiselect"
        )

    if selected_semi_tickers:
        with st.spinner("正在获取半导体标的历史收盘价并归一化计算..."):
            semi_prices_df = get_semiconductor_comparative_prices(selected_semi_tickers, period="5y")

        if not semi_prices_df.empty:
            fig_semi_perf = create_relative_performance_chart(
                semi_prices_df,
                selected_semi_tickers,
                timeframe=semi_timeframe
            )
            if fig_semi_perf:
                st.plotly_chart(fig_semi_perf, use_container_width=True)
        else:
            st.info("正在聚合半导体行情数据...")

    st.markdown("---")

    # 2. 多因子估值与财务指标比选矩阵
    st.subheader("📊 半导体全产业链核心标的估值与财务比选矩阵")
    with st.spinner("正在抓取并聚合半导体产业链公司核心估值与财务指标..."):
        df_semi_matrix = get_semiconductor_matrix_data(semi_all_candidates[:-2])

    if not df_semi_matrix.empty:
        st.dataframe(
            df_semi_matrix.style.format({
                "Price ($)": "${:.2f}",
                "Trailing PE": "{:.1f}",
                "Forward PE": "{:.1f}",
                "P/S (TTM)": "{:.2f}",
                "YoY Rev Growth (%)": "{:.1f}%",
                "Gross Margin (%)": "{:.1f}%",
                "Operating Margin (%)": "{:.1f}%",
                "FCF Yield (%)": "{:.2f}%",
                "Market Cap ($B)": "${:.1f}B"
            }),
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info("正在加载半导体矩阵比选数据...")

    st.markdown("---")

    # 3. 半导体投研框架深度解析
    with st.expander("📖 查看《半导体产业周期、制程节点与 WFE 资本开支》投研分析指南", expanded=False):
        st.markdown("""
        ### 一、 半导体产业四大周期演进规律

        #### 1. 硅周期的四大阶段 (The Silicon Cycle)
        * **衰退出清期 (Downturn)**：下游消费电子/PC/手机需求萎缩，晶圆厂去库存降稼动率，存储芯片价格暴跌（如 2022H2–2023H1）。
        * **周期筑底期 (Bottoming)**：原厂主动削减资本开支 (Capex Cut) 与减产，渠道库存回归健康水位，现货价格企稳。
        * **复苏扩张期 (Expansion)**：新一轮科技创新周期（如 GenAI / 数据中心算力激增）拉动先进制程与 HBM 高价值量芯片需求，量价齐升。
        * **繁荣过热期 (Peak/Overheating)**：全产业链产能供不应求，原厂激进扩产，交期大幅拉长；需警惕双重下单 (Double Booking) 后的需求高位回落。

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

