"""
Macro & Liquidity Tab (Tab 1)
Structured into a high-level KPI Cockpit + 5 Thematic Sub-Tabs for streamlined browsing.
"""
import streamlit as st
import pandas as pd
import numpy as np

from data_processing import load_and_transform_data
from market_breadth_viz import render_market_breadth_ui
from data_service import (
    get_file_updated_time_eastern,
    get_vix_data,
    get_cnn_fear_and_greed_data,
    get_yield_spreads_data,
    get_credit_spread_data,
    get_unemployment_data,
    get_jobless_claims_data,
    get_inflation_wages_data,
    get_sahm_rule_data,
    get_core_capex_data,
    get_m2_money_supply_data,
    get_sloos_credit_data,
    get_fed_balance_sheet_data,
    get_net_liquidity_data,
    get_sofr_iorb_data,
    get_real_yield_and_breakeven_data,
    get_nfci_data,
    get_dxy_data,
    get_gold_oil_ratio_data,
    get_top10_concentration_data,
    get_erp_data,
    get_skew_dix_data,
    get_risk_ratios_data,
    get_move_index_data,
    get_term_premium_data,
    get_epu_data,
    get_commercial_loans_data,
    get_personal_saving_rate_data,
)
from visualization import (
    create_treasury_chart,
    create_vix_chart,
    create_cnn_fear_greed_chart,
    create_yield_spreads_chart,
    create_credit_spread_chart,
    create_unemployment_chart,
    create_jobless_claims_chart,
    create_inflation_wages_chart,
    create_sahm_rule_chart,
    create_core_capex_chart,
    create_m2_money_supply_chart,
    create_sloos_credit_chart,
    create_fed_balance_sheet_chart,
    create_net_liquidity_chart,
    create_sofr_iorb_chart,
    create_real_yield_breakeven_chart,
    create_nfci_chart,
    create_dxy_chart,
    create_gold_oil_ratio_chart,
    create_top10_concentration_chart,
    create_erp_chart,
    create_skew_dix_chart,
    create_cross_asset_ratios_chart,
    create_move_chart,
    create_term_premium_chart,
    create_epu_chart,
    create_commercial_loans_chart,
    create_personal_saving_rate_chart,
)


def _render_kpi_cockpit():
    """顶部宏观核心体温驾驶舱：5 个全局红绿灯指标卡"""
    st.markdown("##### 🚦 宏观全局体温驾驶舱 (Macro Core KPI Cockpit)")
    c1, c2, c3, c4, c5 = st.columns(5)

    # 1. 流动性水库与体温计
    with c1:
        latest_liq = np.nan
        sofr_spread = np.nan
        try:
            df_liq = get_net_liquidity_data()
            if df_liq is not None and not df_liq.empty:
                for col in ["Fed_Net_Liquidity_Tn", "Net_Liquidity_Trillion"]:
                    if col in df_liq.columns:
                        s = df_liq[col].dropna()
                        if not s.empty:
                            latest_liq = float(s.iloc[-1])
                            break
        except Exception:
            pass

        try:
            df_sofr = get_sofr_iorb_data()
            if df_sofr is not None and not df_sofr.empty and "Spread_bps" in df_sofr.columns:
                s = df_sofr["Spread_bps"].dropna()
                if not s.empty:
                    sofr_spread = float(s.iloc[-1])
        except Exception:
            pass

        st.metric(
            label="💧 美联储净流动性",
            value=f"${latest_liq:.2f} T" if pd.notna(latest_liq) else "N/A",
            delta=f"SOFR利差: {sofr_spread:+.1f} bps" if pd.notna(sofr_spread) else None,
            delta_color="normal" if (sofr_spread or 0) <= 0 else "inverse",
            help="美联储净流动性 = WALCL - TGA - RRP。SOFR-IORB利差反映银行间准备金摩擦。"
        )

    # 2. 股债恐慌联动
    with c2:
        latest_vix = np.nan
        latest_move = np.nan
        try:
            df_vix = get_vix_data()
            if df_vix is not None and not df_vix.empty and "VIX" in df_vix.columns:
                s = df_vix["VIX"].dropna()
                if not s.empty:
                    latest_vix = float(s.iloc[-1])
        except Exception:
            pass

        try:
            df_move = get_move_index_data()
            if df_move is not None and not df_move.empty and "MOVE" in df_move.columns:
                s = df_move["MOVE"].dropna()
                if not s.empty:
                    latest_move = float(s.iloc[-1])
        except Exception:
            pass

        st.metric(
            label="⚡ 股市 VIX / 债市 MOVE",
            value=f"{latest_vix:.1f} / {latest_move:.0f}" if (pd.notna(latest_vix) and pd.notna(latest_move)) else ("N/A" if (pd.isna(latest_vix) and pd.isna(latest_move)) else (f"{latest_vix:.1f} / N/A" if pd.notna(latest_vix) else f"N/A / {latest_move:.0f}")),
            delta="高波动警戒" if ((latest_vix or 0) > 22 or (latest_move or 0) > 115) else "波动平稳常态",
            delta_color="inverse" if ((latest_vix or 0) > 22 or (latest_move or 0) > 115) else "normal",
            help="VIX为股市恐慌指标；MOVE为债市利率期权隐含波动率（全球金融抵押品母恐慌指数）。"
        )

    # 3. 衰退预警模型
    with c3:
        sahm_val = np.nan
        t10y2y = np.nan
        try:
            df_sahm = get_sahm_rule_data()
            if df_sahm is not None and not df_sahm.empty and "Sahm_Rule" in df_sahm.columns:
                s = df_sahm["Sahm_Rule"].dropna()
                if not s.empty:
                    sahm_val = float(s.iloc[-1])
        except Exception:
            pass

        try:
            df_spr = get_yield_spreads_data()
            if df_spr is not None and not df_spr.empty:
                for col in ["Spread_10Y2Y", "T10Y2Y"]:
                    if col in df_spr.columns:
                        s = df_spr[col].dropna()
                        if not s.empty:
                            t10y2y = float(s.iloc[-1])
                            break
        except Exception:
            pass

        is_sahm_alarm = (sahm_val or 0) >= 0.50
        st.metric(
            label="🛡️ 萨姆法则衰退指标",
            value=f"{sahm_val:.2f}" if pd.notna(sahm_val) else "N/A",
            delta="🚨 衰退警报触发 (≥0.50)" if is_sahm_alarm else (f"10Y-2Y: {t10y2y:+.2f}%" if pd.notna(t10y2y) else None),
            delta_color="inverse" if is_sahm_alarm else "normal",
            help="萨姆法则≥0.50%历史100%对应经济衰退。10Y-2Y解除倒挂陡峭化阶段为衰退敏感窗口。"
        )

    # 4. 标普股权风险溢价 ERP
    with c4:
        cur_erp = np.nan
        fwd_pe = np.nan
        try:
            erp_data = get_erp_data(base_ntm_eps=288.0)
            if erp_data:
                cur_erp = erp_data.get("current_erp", np.nan)
                fwd_pe = erp_data.get("fwd_pe", np.nan)
        except Exception:
            pass

        st.metric(
            label="🎯 标普 500 ERP 风险溢价",
            value=f"{cur_erp:+.2f}%" if pd.notna(cur_erp) else "N/A",
            delta=f"Forward PE: {fwd_pe:.1f}x" if pd.notna(fwd_pe) else None,
            delta_color="normal" if (cur_erp or 0) > 1.0 else "inverse",
            help="ERP = 标普远期盈利收益率 - 10Y美债收益率。<0.5% 代表美股相对于无风险债券性价比偏低。"
        )

    # 5. 信用利差与金融条件
    with c5:
        cur_oas = np.nan
        cur_nfci = np.nan
        try:
            df_oas = get_credit_spread_data()
            if df_oas is not None and not df_oas.empty:
                for col in ["Value", "High_Yield_Spread"]:
                    if col in df_oas.columns:
                        s = df_oas[col].dropna()
                        if not s.empty:
                            cur_oas = float(s.iloc[-1])
                            break
        except Exception:
            pass

        try:
            df_nfci = get_nfci_data()
            if df_nfci is not None and not df_nfci.empty and "NFCI" in df_nfci.columns:
                s = df_nfci["NFCI"].dropna()
                if not s.empty:
                    cur_nfci = float(s.iloc[-1])
        except Exception:
            pass

        st.metric(
            label="🏦 高收益债利差 / NFCI",
            value=f"{cur_oas:.2f}%" if pd.notna(cur_oas) else "N/A",
            delta=f"NFCI条件: {cur_nfci:+.2f}" if pd.notna(cur_nfci) else None,
            delta_color="inverse" if ((cur_oas or 0) > 4.5 or (cur_nfci or 0) > 0) else "normal",
            help="高收益债OAS>4.5%或芝加哥联储NFCI>0提示企业融资环境紧缩与违约风险蔓延。"
        )
    st.markdown("---")



# ==================================================================
# 专题 1: 💧 流动性总闸门与央行水库
# ==================================================================
def _render_theme_liquidity(df_long: pd.DataFrame, macro_tf: str):
    st.markdown("### 💧 专题 1：流动性总闸门与央行水库 (Liquidity & Fed Balance Sheet)")
    st.caption("透视美联储资产负债表扩张/收缩、TGA与RRP吞吐量、准备金管道摩擦与广义货币供应。")

    # 1. 国债收益率曲线
    treasury_csv = "daily-treasury-rates.csv"
    treasury_updated = get_file_updated_time_eastern(treasury_csv)
    if df_long is not None and not df_long.empty:
        latest_date = df_long['Date'].max().strftime('%Y-%m-%d')
        st.caption(f"🕒 数据刷新时间 (美东时间): **{treasury_updated}** | 最新数据交易日: **{latest_date}**")
        fig_treasury = create_treasury_chart(df_long)
        if fig_treasury:
            st.plotly_chart(fig_treasury, use_container_width=True)
            with st.expander("💡 美债收益率曲线 (Yield Curve) 解读指南", expanded=False):
                st.markdown("""
                * **倒挂阶段 (Inversion, 2Y > 10Y)**：短端政策利率高企压低长端衰退预期，预示银行净息差受挤压与信用紧缩。
                * **牛陡 (Bull Steepening)**：降息周期开启，短端利率急跌，恢复正利差（通常伴随衰退后期的流动性修复）。
                * **熊陡 (Bear Steepening)**：长端利率飙升，由通胀中枢上移、美债供给冲击或期限溢价走高驱动。
                """)

    col_l1, col_l2 = st.columns(2)
    with col_l1:
        st.subheader("美联储净流动性 & 银行准备金")
        with st.spinner("正在计算美联储净流动性与准备金余额..."):
            df_liq = get_net_liquidity_data()
        if not df_liq.empty:
            fig_liq = create_net_liquidity_chart(df_liq, timeframe=macro_tf)
            if fig_liq:
                st.plotly_chart(fig_liq, use_container_width=True)
                with st.expander("💡 美联储净流动性 & 银行准备金解读指南", expanded=False):
                    st.markdown("""
                    * **净流动性公式**：`Net Liquidity = 美联储总资产 (WALCL) - 财政部现金账户 (TGA) - 隔夜逆回购 (RRP)`。
                    * **与美股高度正相关**：是驱动风险资产水位的核心流动性水龙头。领先美股 1-2 周走势。
                    * **银行准备金 (Bank Reserves)**：金融系统的底层真正结算血液。跌破阈值易触发金融管道流动性摩擦。
                    """)
        else:
            st.info("暂无净流动性数据...")

    with col_l2:
        st.subheader("SOFR - IORB 资金面体温计")
        with st.spinner("正在计算 SOFR - IORB 利差数据..."):
            df_sofr = get_sofr_iorb_data()
        if not df_sofr.empty:
            fig_sofr = create_sofr_iorb_chart(df_sofr, timeframe=macro_tf)
            if fig_sofr:
                st.plotly_chart(fig_sofr, use_container_width=True)
                with st.expander("💡 SOFR - IORB 资金面体温计解读指南", expanded=False):
                    st.markdown("""
                    * **指标定位**：SOFR（市场隔夜抵押融资利率）减去 IORB（美联储付给银行准备金利率）。
                    * **< 0 bps (常态充裕)**：市场流动性极为宽松。
                    * **> +10 bps (钱荒预警)**：超额准备金跌破舒适水平，易触发隔夜流动性挤兑。
                    """)
        else:
            st.info("暂无 SOFR / IORB 数据...")

    col_l3, col_l4 = st.columns(2)
    with col_l3:
        st.subheader("美联储资产负债表 (WALCL)")
        with st.spinner("正在从 FRED 加载美联储资产负债表数据..."):
            df_fed = get_fed_balance_sheet_data()
        if not df_fed.empty:
            fig_fed = create_fed_balance_sheet_chart(df_fed, timeframe=macro_tf)
            if fig_fed:
                st.plotly_chart(fig_fed, use_container_width=True)
                with st.expander("💡 美联储总资产 (WALCL) 解读指南", expanded=False):
                    st.markdown("""
                    * **QE (量化宽松)**：央行大规模购债扩表，直接注入基础货币，推高所有风险资产估值。
                    * **QT (量化紧缩)**：央行到期不续做进行缩表回收流动性，带来隐性持续紧缩压力。
                    """)
        else:
            st.info("暂无美联储资产负债表数据...")

    with col_l4:
        st.subheader("广义货币供应量 M2 同比增速")
        with st.spinner("正在加载 M2 货币供应量数据..."):
            df_m2 = get_m2_money_supply_data()
        if not df_m2.empty:
            fig_m2 = create_m2_money_supply_chart(df_m2, timeframe=macro_tf)
            if fig_m2:
                st.plotly_chart(fig_m2, use_container_width=True)
                with st.expander("💡 广义货币供应量 M2 同比增速解读指南", expanded=False):
                    st.markdown("""
                    * **实体购买力总蓄水池**：包含现金、活期/定期存款及货币基金。
                    * **负增长拐点**：M2 同比企稳回升通常预示金融再通胀周期的启动。
                    """)
        else:
            st.info("暂无 M2 数据...")


# ==================================================================
# 专题 2: ⚡ 恐慌波动率与极端博弈 (含 MOVE & EPU)
# ==================================================================
def _render_theme_volatility(macro_tf: str):
    st.markdown("### ⚡ 专题 2：恐慌波动率与极端博弈 (Volatility, Sentiment & Tail Risk)")
    st.caption("综合追踪美股情绪恐慌 (VIX / CNN)、全球金融抵押品母恐慌 (MOVE)、黑天鹅偏度与政策不确定性 (EPU)。")

    col_v1, col_v2 = st.columns(2)
    with col_v1:
        st.subheader("CBOE VIX 股市恐慌指数")
        with st.spinner("正在从 FRED 加载 VIX 恐慌指数..."):
            df_vix = get_vix_data()
        if not df_vix.empty:
            fig_vix = create_vix_chart(df_vix, timeframe=macro_tf)
            if fig_vix:
                st.plotly_chart(fig_vix, use_container_width=True)
                with st.expander("💡 CBOE VIX 恐慌指数解读指南", expanded=False):
                    st.markdown("""
                    * **< 15 (极度自满/低波动)**：市场处于平静期或牛市主升段。
                    * **20 - 30 (风险警惕)**：抛压逐渐释放，情绪承压。
                    * **> 30 (高恐慌/流动性踩踏)**：脉冲式飙升，通常对应恐慌性抛售或历史级左侧买点。
                    """)
        else:
            st.info("暂无 VIX 数据...")

    with col_v2:
        st.subheader("🔥 ICE BofA MOVE 债市恐慌指数 (母恐慌指标)")
        with st.spinner("正在加载 MOVE 债市波动率指数..."):
            df_move = get_move_index_data()
        if not df_move.empty:
            fig_move = create_move_chart(df_move, timeframe=macro_tf)
            if fig_move:
                st.plotly_chart(fig_move, use_container_width=True)
                with st.expander("💡 ICE BofA MOVE 债市恐慌指数解读指南", expanded=False):
                    st.markdown("""
                    * **金融体系“母恐慌指数”**：美债是全球通用抵押品基石。当 MOVE 飙升 (>120~140) 时，量化宏观基金（Risk Parity / CTA）会被迫提高 VAR 保证金并被动抛售股票去杠杆。
                    * **先行性**：在 2023 硅谷银行危机爆发前 2 周、2022 股债双杀初期，**MOVE 均比标普 VIX 提前数周剧烈脉冲上冲**。若 MOVE 居高不下而 VIX 低迷，预示股市在虚假平静中酝酿补跌。
                    """)
        else:
            st.info("暂无 MOVE 指数数据...")

    col_v3, col_v4 = st.columns(2)
    with col_v3:
        st.subheader("CNN 恐慌与贪婪指数 (Fear & Greed)")
        with st.spinner("正在获取 CNN 恐慌与贪婪指数..."):
            df_fgi = get_cnn_fear_and_greed_data()
        if not df_fgi.empty:
            fig_fgi = create_cnn_fear_greed_chart(df_fgi, timeframe=macro_tf)
            if fig_fgi:
                st.plotly_chart(fig_fgi, use_container_width=True)
                with st.expander("💡 CNN 恐慌与贪婪指数解读指南", expanded=False):
                    st.markdown("""
                    * **0 - 25 (Extreme Fear)**：市场严重超卖，提供逆向价值买入机会。
                    * **75 - 100 (Extreme Greed)**：FOMO 情绪蔓延，杠杆积聚，需警惕回调。
                    """)
        else:
            st.info("暂无 CNN 恐慌指数数据...")

    with col_v4:
        st.subheader("🔥 美国经济政策不确定性指数 (EPU)")
        with st.spinner("正在从 FRED 加载经济政策不确定性指数..."):
            df_epu = get_epu_data()
        if not df_epu.empty:
            fig_epu = create_epu_chart(df_epu, timeframe=macro_tf)
            if fig_epu:
                st.plotly_chart(fig_epu, use_container_width=True)
                with st.expander("💡 经济政策不确定性指数 (EPU) 解读指南", expanded=False):
                    st.markdown("""
                    * **指标定义 (Baker, Bloom & Davis)**：量化媒体报道、税收法案到期与专业预测分歧中的经济政策不确定性。
                    * **应用场景**：大选周期、贸易关税加征、债务上限谈判等窗口期。当 30D 均线突破 150~200 时，企业通常延缓雇佣与资本开支，压制股市估值中枢。
                    """)
        else:
            st.info("暂无 EPU 数据...")

    # SKEW 与 DIX 暗池
    st.subheader("CBOE SKEW 黑天鹅指数与暗池 DIX")
    skew_dix_dict = get_skew_dix_data()
    if skew_dix_dict:
        fig_skew_dix = create_skew_dix_chart(skew_dix_dict, timeframe=macro_tf)
        if fig_skew_dix:
            st.plotly_chart(fig_skew_dix, use_container_width=True)
            with st.expander("💡 SKEW 与暗池 DIX 解读指南", expanded=False):
                st.markdown("""
                * **CBOE SKEW**：衡量虚值 Put 溢价。若 VIX 处于低位但 SKEW 飙升突破 140，意味着大资金正在隐秘抢购尾部崩盘保险。
                * **暗池 DIX**：衡量大机构挂单成交做多比例。DIX > 45% 往往预示着中短期多头底部买点确立。
                """)


# ==================================================================
# 专题 3: 🎯 利率微观、期限溢价与资产估值 (含 ACM Term Premium)
# ==================================================================
def _render_theme_rates_valuation(macro_tf: str):
    st.markdown("### 🎯 专题 3：利率微观、期限溢价与资产估值 (Rates, Term Premium & Valuation)")
    st.caption("拆解美债 10Y 收益率底层构成、TIPS 实际利率分母、标普 ERP 风险溢价与跨资产偏好比率。")

    col_r1, col_r2 = st.columns(2)
    with col_r1:
        st.subheader("🔥 纽约联储 ACM 10 年期期限溢价 (Term Premium)")
        with st.spinner("正在计算纽约联储 ACM 期限溢价与期望利率拆解..."):
            df_tp = get_term_premium_data()
        if not df_tp.empty:
            fig_tp = create_term_premium_chart(df_tp, timeframe=macro_tf)
            if fig_tp:
                st.plotly_chart(fig_tp, use_container_width=True)
                with st.expander("💡 纽约联储 ACM 10 年期期限溢价解读指南", expanded=False):
                    st.markdown("""
                    * **核心原理**：10 年期美债名义收益率 = **未来 10 年短端利率期望均值 (Risk-neutral Rate) + 期限溢价 (Term Premium)**。
                    * **驱动力**：2023 年秋季美债利率冲上 5% 以及财政赤字担忧，核心推手正是期限溢价由负转正。
                    * **> 0%**：投资者要求对美国政府债务膨胀与供给冲击做出额外补偿；
                    * **> +1.0%**：纯粹的流动性供给紧缩冲击，对长久期高估值科技股估值构成直接压制。
                    """)
        else:
            st.info("暂无期限溢价数据...")

    with col_r2:
        st.subheader("10Y TIPS 实际利率 & 通胀预期")
        with st.spinner("正在从 FRED 加载 10Y TIPS 实际利率与通胀预期..."):
            df_ry = get_real_yield_and_breakeven_data()
        if not df_ry.empty:
            fig_ry = create_real_yield_breakeven_chart(df_ry, timeframe=macro_tf)
            if fig_ry:
                st.plotly_chart(fig_ry, use_container_width=True)
                with st.expander("💡 10Y TIPS 实际利率 & 通胀预期解读指南", expanded=False):
                    st.markdown("""
                    * **10Y TIPS 实际利率 (DFII10)**：全球无风险资产的真实资本回报率，亦是高估值成长股现金流折现的核心分母。
                    * **10Y 盈亏平衡通胀预期 (T10YIE)**：名义美债与 TIPS 之差，维持在 2.0% - 2.5% 表明通胀预期锚定良好。
                    """)
        else:
            st.info("暂无实际利率与通胀预期数据...")

    # 标普 ERP 风险溢价
    st.subheader("标普 500 股权风险溢价 (Equity Risk Premium, ERP - 动态版)")
    col_ctrl, _ = st.columns([3, 7])
    with col_ctrl:
        custom_eps = st.number_input(
            "华尔街标普 500 NTM EPS 一致预期 ($):",
            min_value=200.0, max_value=400.0, value=288.0, step=1.0,
            help="未来 12 个月一致预期每股收益。调高 EPS 预期意味着盈利更乐观，Forward P/E 降低，ERP 提升。"
        )
    erp_data = get_erp_data(base_ntm_eps=custom_eps)
    if erp_data:
        fig_erp = create_erp_chart(erp_data, timeframe=macro_tf)
        if fig_erp:
            st.plotly_chart(fig_erp, use_container_width=True)
            with st.expander("💡 股权风险溢价 (ERP) 与远期估值决策指南", expanded=False):
                st.markdown(f"""
                * **当前核算基准**：S&P 500 点位 **${erp_data['spx_price']:,.1f}**，NTM EPS **${erp_data['ntm_eps']:.1f}**。
                * **ERP < 0% (极端倒挂)**：股票盈利收益率低于无风险国债，权益安全边际极窄。
                * **ERP > 2.5% ~ 3.0% (高性价比)**：股票资产具备充足安全边际，通常对应优质左侧买点。
                """)

    col_r3, col_r4 = st.columns(2)
    with col_r3:
        st.subheader("S&P 500 前十大持仓集中度")
        with st.spinner("正在加载标普500前十大持仓集中度..."):
            df_top10 = get_top10_concentration_data()
        if not df_top10.empty:
            fig_top10 = create_top10_concentration_chart(df_top10)
            if fig_top10:
                st.plotly_chart(fig_top10, use_container_width=True)
                with st.expander("💡 S&P 500 前十大持仓集中度解读指南", expanded=False):
                    st.markdown("""
                    * **集中度含义**：前 10 大超级权重巨头占指数市值逼近 **35% - 40%** 历史极值。
                    * **脆弱性**：底层多数股票下跌若被巨头掩盖，一旦巨头补跌，大盘将面临剧烈共振回撤。
                    """)
        else:
            st.info("暂无集中度数据...")

    with col_r4:
        st.subheader("跨资产避险/风险偏好比率 (Copper/Gold & HYG/TLT)")
        df_ratios = get_risk_ratios_data()
        if df_ratios is not None and not df_ratios.empty:
            fig_ratios = create_cross_asset_ratios_chart(df_ratios, timeframe=macro_tf)
            if fig_ratios:
                st.plotly_chart(fig_ratios, use_container_width=True)
                with st.expander("💡 跨资产比率解读指南", expanded=False):
                    st.markdown("""
                    * **铜金比**：比率突破 50 日均线上行代表经济复苏与 Risk-on。
                    * **HYG / TLT**：高收益债与长期国债比值。破位下行则是股市调整前夕的早期预警信号。
                    """)
        else:
            st.info("暂无跨资产比率数据...")


# ==================================================================
# 专题 4: 🏦 商业银行、信贷周期与金融条件 (含 BUSLOANS)
# ==================================================================
def _render_theme_credit_banking(macro_tf: str):
    st.markdown("### 🏦 专题 4：商业银行、信贷周期与金融条件 (Credit & Banking Health)")
    st.caption("跟踪商业银行贷款供给意愿 (SLOOS)、实际工商业贷款创造 (BUSLOANS)、高收益债信用利差与宏观金融条件。")

    col_b1, col_b2 = st.columns(2)
    with col_b1:
        st.subheader("芝加哥联储全国金融条件指数 (NFCI)")
        with st.spinner("正在从 FRED 加载芝加哥联储 NFCI 指数..."):
            df_nfci = get_nfci_data()
        if not df_nfci.empty:
            fig_nfci = create_nfci_chart(df_nfci, timeframe=macro_tf)
            if fig_nfci:
                st.plotly_chart(fig_nfci, use_container_width=True)
                with st.expander("💡 芝加哥联储全国金融条件指数 (NFCI) 解读指南", expanded=False):
                    st.markdown("""
                    * **< 0 (宽松)**：信贷容易获取，资产价格受到支撑。
                    * **> 0 (紧缩)**：融资环境严苛，违约风险与利差扩大，压制宏观扩张。
                    """)
        else:
            st.info("暂无 NFCI 数据...")

    with col_b2:
        st.subheader("高收益债信用利差 (US High Yield Spread)")
        with st.spinner("正在从 FRED 加载高收益债信用利差..."):
            df_oas = get_credit_spread_data()
        if not df_oas.empty:
            fig_oas = create_credit_spread_chart(df_oas, timeframe=macro_tf)
            if fig_oas:
                st.plotly_chart(fig_oas, use_container_width=True)
                with st.expander("💡 高收益债信用利差 (US High Yield Spread) 解读指南", expanded=False):
                    st.markdown("""
                    * **< 3.5% (极度健康/无违约担忧)**：企业偿债能力强，信贷充裕。
                    * **> 5.5% (信用风暴预警)**：企业债务展期受阻，预示衰退或流动性危机来临。
                    """)
        else:
            st.info("暂无信用利差数据...")

    col_b3, col_b4 = st.columns(2)
    with col_b3:
        st.subheader("美联储银行信贷标准调查 (SLOOS)")
        with st.spinner("正在加载银行贷款标准净收紧比例 (SLOOS)..."):
            df_sloos = get_sloos_credit_data()
        if not df_sloos.empty:
            fig_sloos = create_sloos_credit_chart(df_sloos, timeframe=macro_tf)
            if fig_sloos:
                st.plotly_chart(fig_sloos, use_container_width=True)
                with st.expander("💡 银行贷款标准 (SLOOS) 解读指南", expanded=False):
                    st.markdown("""
                    * **前瞻性极强**：银行信贷收紧通常**领先企业违约率与实际信贷萎缩 2–4 个季度**。
                    * 净收紧比例超过 +20%~+40% 标志着信贷紧缩周期，对中小企业资本开支构成考验。
                    """)
        else:
            st.info("暂无 SLOOS 数据...")

    with col_b4:
        st.subheader("🔥 全美商业银行工商业贷款规模与增速 (BUSLOANS)")
        with st.spinner("正在加载商业银行贷款总额与同比增速..."):
            df_loans = get_commercial_loans_data()
        if not df_loans.empty:
            fig_loans = create_commercial_loans_chart(df_loans, timeframe=macro_tf)
            if fig_loans:
                st.plotly_chart(fig_loans, use_container_width=True)
                with st.expander("💡 商业银行工商业贷款 (BUSLOANS) 解读指南", expanded=False):
                    st.markdown("""
                    * **实体信贷落地验证**：SLOOS 衡量的是银行贷款“意愿”，而 BUSLOANS 衡量的是实体经济中真正发生的“信贷创造规模”。
                    * **YoY 同比增速转负 (<-2%)**：历史上均对应企业信贷紧缩与去库存周期；YoY > 5% 确认宽信用健康扩张。
                    """)
        else:
            st.info("暂无商业贷款数据...")


# ==================================================================
# 专题 5: 🛡️ 衰退定量、实体经济与居民韧性 (含 PSAVERT)
# ==================================================================
def _render_theme_recession_economy(macro_tf: str):
    st.markdown("### 🛡️ 专题 5：衰退定量、实体经济与居民韧性 (Recession & Real Economy)")
    st.caption("综合研判期限利差解挂阶段、萨姆法则硬衰退阈值、高频失业申请、核心订单、通胀粘性与居民储蓄率。")

    col_e1, col_e2 = st.columns(2)
    with col_e1:
        st.subheader("10Y-2Y & 10Y-3M 美债期限利差")
        with st.spinner("正在加载国债期限利差数据..."):
            df_spreads = get_yield_spreads_data()
        if not df_spreads.empty:
            fig_spreads = create_yield_spreads_chart(df_spreads, timeframe=macro_tf)
            if fig_spreads:
                st.plotly_chart(fig_spreads, use_container_width=True)
                with st.expander("💡 10Y-2Y & 10Y-3M 美债期限利差解读指南", expanded=False):
                    st.markdown("""
                    * **真正风险点在“解挂恢复” (Un-inversion)**：历史上美股最大跌幅往往不发生在倒挂最深处，而发生在**曲线从倒挂重新快速陡峭化（牛陡）**并进入实质性衰退降息的初期。
                    """)
        else:
            st.info("暂无期限利差数据...")

    with col_e2:
        st.subheader("萨姆法则衰退指标 (Sahm Rule)")
        with st.spinner("正在加载萨姆法则指标..."):
            df_sahm = get_sahm_rule_data()
        if not df_sahm.empty:
            fig_sahm = create_sahm_rule_chart(df_sahm, timeframe=macro_tf)
            if fig_sahm:
                st.plotly_chart(fig_sahm, use_container_width=True)
                with st.expander("💡 萨姆法则衰退指标 (Sahm Rule) 解读指南", expanded=False):
                    st.markdown("""
                    * **萨姆法则定义**：美国 3 个月移动平均失业率相比过去 12 个月最低点上升 **0.50%** 或以上时，标志着经济已陷入实质性衰退。自 1970 年以来从未出现假阳性误报。
                    """)
        else:
            st.info("暂无萨姆法则数据...")

    col_e3, col_e4 = st.columns(2)
    with col_e3:
        st.subheader("美国周度初请与续请失业金人数 (Jobless Claims)")
        with st.spinner("正在加载失业金申请高频数据..."):
            df_claims = get_jobless_claims_data()
        if not df_claims.empty:
            fig_claims = create_jobless_claims_chart(df_claims, timeframe=macro_tf)
            if fig_claims:
                st.plotly_chart(fig_claims, use_container_width=True)
                with st.expander("💡 周度初请失业金人数解读指南", expanded=False):
                    st.markdown("""
                    * **初请 (领先指标)**：通常超过 **25–26 万人** 表明劳动力市场边际松动，超过 **30 万人** 为深度疲弱信号。
                    * **续请 (同期指标)**：持续走高表明失业周期拉长，再就业市场趋于冻结。
                    """)
        else:
            st.info("暂无失业金申请数据...")

    with col_e4:
        st.subheader("核心资本品新订单 (Core CapEx Orders)")
        with st.spinner("正在加载核心资本品新订单数据..."):
            df_capex = get_core_capex_data()
        if not df_capex.empty:
            fig_capex = create_core_capex_chart(df_capex, timeframe=macro_tf)
            if fig_capex:
                st.plotly_chart(fig_capex, use_container_width=True)
                with st.expander("💡 核心资本品新订单解读指南", expanded=False):
                    st.markdown("""
                    * **前瞻性资本开支意愿**：长期领先美国私人投资与企业盈利周期，同比转负通常伴随着企业投资收缩与经济降速。
                    """)
        else:
            st.info("暂无核心资本品订单数据...")

    col_e5, col_e6 = st.columns(2)
    with col_e5:
        st.subheader("🔥 美国居民个人储蓄率 (PSAVERT)")
        with st.spinner("正在加载美国居民个人储蓄率数据..."):
            df_save = get_personal_saving_rate_data()
        if not df_save.empty:
            fig_save = create_personal_saving_rate_chart(df_save, timeframe=macro_tf)
            if fig_save:
                st.plotly_chart(fig_save, use_container_width=True)
                with st.expander("💡 美国居民个人储蓄率 (PSAVERT) 解读指南", expanded=False):
                    st.markdown("""
                    * **消费终极蓄水池**：美国 GDP 约 70% 由居民消费驱动。储蓄率衡量居民可支配收入中用于储蓄的真实比例。
                    * **3.5% 预警红线**：跌破 3.5% 表明超额储蓄缓冲垫基本耗尽，中低收入群体必须依赖借贷与薪资维系支出，消费抗风险韧性极为脆弱。
                    """)
        else:
            st.info("暂无个人储蓄率数据...")

    with col_e6:
        st.subheader("核心 PCE 通胀同比 vs. 时薪增速")
        with st.spinner("正在加载核心通胀与时薪数据..."):
            df_inf_w = get_inflation_wages_data()
        if not df_inf_w.empty:
            fig_inf_w = create_inflation_wages_chart(df_inf_w, timeframe=macro_tf)
            if fig_inf_w:
                st.plotly_chart(fig_inf_w, use_container_width=True)
                with st.expander("💡 核心 PCE 通胀同比 vs. 时薪增速解读指南", expanded=False):
                    st.markdown("""
                    * **薪资-通胀螺旋 (Wage-Price Spiral)**：时薪增速远超生产率增长易推动服务业通胀粘性与二次通胀风险。
                    """)
        else:
            st.info("暂无通胀与薪资数据...")

    col_e7, col_e8 = st.columns(2)
    with col_e7:
        st.subheader("美国失业率 (UNRATE)")
        with st.spinner("正在从 FRED 加载失业率数据..."):
            df_unrate = get_unemployment_data()
        if not df_unrate.empty:
            fig_unrate = create_unemployment_chart(df_unrate, timeframe=macro_tf)
            if fig_unrate:
                st.plotly_chart(fig_unrate, use_container_width=True)
                with st.expander("💡 美国失业率 (UNRATE) 解读指南", expanded=False):
                    st.markdown("""
                    * **美联储货币政策决策核心**：失业率一旦见底反弹超过 0.5%，往往出现自强化的非线性快速上升。
                    """)
        else:
            st.info("暂无失业率数据...")

    with col_e8:
        st.subheader("Gold / Oil Ratio (金油比)")
        with st.spinner("正在计算金油比历史数据..."):
            df_go = get_gold_oil_ratio_data()
        if not df_go.empty:
            fig_go = create_gold_oil_ratio_chart(df_go, timeframe=macro_tf)
            if fig_go:
                st.plotly_chart(fig_go, use_container_width=True)
                with st.expander("💡 Gold / Oil Ratio (金油比) 解读指南", expanded=False):
                    st.markdown("""
                    * **指标定义**：1 盎司黄金能购买的原油桶数。
                    * **> 25 - 30 (高风险/衰退预警)**：实体总需求暴跌且恐慌避险升温。
                    * **< 15 (过热/通胀高企)**：工业总需求旺盛。
                    """)
        else:
            st.info("暂无金油比数据...")

    # 美元指数 DXY
    st.subheader("美元指数 (U.S. Dollar Index / DXY)")
    with st.spinner("正在加载美元指数数据..."):
        df_dxy = get_dxy_data()
    if not df_dxy.empty:
        fig_dxy = create_dxy_chart(df_dxy, timeframe=macro_tf)
        if fig_dxy:
            st.plotly_chart(fig_dxy, use_container_width=True)
            with st.expander("💡 美元指数 (DXY) 解读指南", expanded=False):
                st.markdown("""
                * **全球金融条件总闸门**：美元走强对全球非美经济体产生汇率紧缩效应，压制跨国企业海外营收折算。
                * **避险属性 (Dollar Smile)**：在全球流动性危机时呈现强避险上涨特征。
                """)
    else:
        st.info("暂无美元指数数据...")


# ==================================================================
# 宏观 Tab 主入口渲染函数
# ==================================================================
def render_macro_tab():
    st.markdown("#### 美联储货币政策、流动性水库、利差与宏观情绪仪表盘")
    render_market_breadth_ui()

    # 侧边栏时间范围控制
    st.sidebar.header("⚙️ 宏观图表动态 Y 轴自动缩放控制")
    macro_tf = st.sidebar.radio(
        "选择宏观图表时间范围 (自动精细缩放 Y 轴):",
        ["1M", "3M", "6M", "1Y", "3Y", "5Y", "10Y", "ALL"],
        index=5,
        key="global_macro_timeframe"
    )

    # 预加载美债收益率基础数据
    with st.spinner("正在获取并转换国债收益率数据..."):
        df_long = load_and_transform_data()

    if df_long is not None and not df_long.empty:
        latest_date = df_long['Date'].max().strftime('%Y-%m-%d')
        treasury_updated = get_file_updated_time_eastern("daily-treasury-rates.csv")
        st.sidebar.header("国债数据信息")
        st.sidebar.markdown(f"刷新时间 (美东): **{treasury_updated}**")
        st.sidebar.markdown(f"最新日期: **{latest_date}**")
        st.sidebar.markdown(f"总数据点: **{len(df_long)//12}**")

    # 1. 顶部全局体温驾驶舱 (5 张核心红绿灯指标卡)
    _render_kpi_cockpit()

    # 2. 浏览视图模式控制 (解决信息过载)
    col_mode_sel, col_mode_tip = st.columns([3, 7])
    with col_mode_sel:
        view_mode = st.radio(
            "选择宏观浏览视图模式:",
            ["📑 分类聚焦视图 (推荐)", "📜 完整平铺视图"],
            index=0,
            horizontal=True,
            label_visibility="collapsed"
        )
    with col_mode_tip:
        st.caption("💡 **分类聚焦视图**：将 28 项核心指标归类至 5 大深度主题子标签，消除滚屏疲劳；切换至**完整平铺视图**可一次性向下通读全部图表。")

    st.markdown("---")

    # 3. 根据视图模式渲染内容
    if "分类聚焦" in view_mode:
        t1, t2, t3, t4, t5 = st.tabs([
            "💧 1. 流动性总闸门与央行水库",
            "⚡ 2. 恐慌波动率与极端博弈",
            "🎯 3. 利率微观、期限溢价与估值",
            "🏦 4. 商业银行、信贷周期与金融条件",
            "🛡️ 5. 衰退定量、实体经济与居民韧性"
        ])
        with t1:
            _render_theme_liquidity(df_long, macro_tf)
        with t2:
            _render_theme_volatility(macro_tf)
        with t3:
            _render_theme_rates_valuation(macro_tf)
        with t4:
            _render_theme_credit_banking(macro_tf)
        with t5:
            _render_theme_recession_economy(macro_tf)
    else:
        # 完整平铺视图
        _render_theme_liquidity(df_long, macro_tf)
        st.markdown("---")
        _render_theme_volatility(macro_tf)
        st.markdown("---")
        _render_theme_rates_valuation(macro_tf)
        st.markdown("---")
        _render_theme_credit_banking(macro_tf)
        st.markdown("---")
        _render_theme_recession_economy(macro_tf)

    st.markdown("---")

    # 4. 宏观策略与周期框架总览 (深度研究附录)
    with st.expander("📖 查看《见证逆潮》核心宏观逻辑与收益率曲线策略指南（深度解析版）", expanded=False):
        st.markdown("""
        ### 一、 宏观流动性与收益率曲线的三大定律

        #### 1. 收益率曲线形态与经济周期四阶段
        * **牛平 (Bull Flattening)**：经济过热后期，长端利率下行快于短端，适合超配长久期国债。
        * **熊平 (Bear Flattening)**：央行抗通胀激进加息，短端利率急升压平甚至倒挂曲线，权益市场承受估值杀跌。
        * **牛陡 (Bull Steepening)**：衰退显现，央行开启大幅降息，短端利率领跌，曲线快速脱离倒挂（**历史上美股最大主跌浪与出清阶段通常发生于此**）。
        * **熊陡 (Bear Steepening)**：经济强劲复苏或财政债务赤字失控，长端发债供给过剩推升期限溢价，顺周期价值股跑赢成长股。

        #### 2. 美联储流动性水库三大闸门联动机制
        * **流动性平衡公式**：$$\\text{Net Liquidity} = \\text{WALCL (美联储总资产)} - \\text{TGA (财政部现金)} - \\text{RRP (隔夜逆回购)}$$
        * **RRP 的缓冲垫作用**：当 RRP 逆回购资金流出时能承接美债供给，形成隐性流动性释放；当 RRP 耗尽至低位后，财政部再发债将直接抽取商业银行准备金，触发真实流动性紧缩。

        #### 3. 信用利差与金融条件的断崖效应
        * 信用利差（High Yield OAS）在经济扩张期具备漫长平稳的**低波动钝化期**，但一旦突破 4.0%~4.5% 临界水平，利差呈现快速脉冲式非线性放大。
        """)
