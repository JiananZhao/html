"""
Macro & Liquidity Tab (Tab 1)
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
)

def render_macro_tab():
    st.markdown("#### 美联储货币政策、流动性水库、利差与宏观情绪仪表盘")
    render_market_breadth_ui()

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
            with st.expander("💡 美债收益率曲线 (Yield Curve) 解读指南", expanded=False):
                st.markdown("""
                * **形态演变比较**：对比最新曲线、1个月前及1年前曲线。
                * **倒挂阶段 (Inversion, 2Y > 10Y)**：短端政策利率高企压低长端衰退预期，预示银行净息差受挤压与信用紧缩。
                * **陡峭化阶段 (Steepening)**：
                  * **牛陡 (Bull Steepening)**：降息周期开启，短端利率急跌，恢复正利差（通常伴随衰退后期的流动性修复）。
                  * **熊陡 (Bear Steepening)**：长端利率飙升，由通胀中枢上移、美债供给冲击或期限溢价走高驱动。
                """)

        st.sidebar.header("国债数据信息")
        st.sidebar.markdown(f"刷新时间 (美东): **{treasury_updated}**")
        st.sidebar.markdown(f"最新日期: **{latest_date}**")
        st.sidebar.markdown(f"总数据点: **{len(df_long)//12}**")
    else:
        st.warning("暂无 daily-treasury-rates.csv 数据。")

    st.markdown("---")

    # --- 2. 市场情绪量化指标 ---
    st.header("📊 市场情绪量化指标 (VIX & CNN Fear/Greed Index)")
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("CBOE VIX 恐慌指数")
        with st.spinner("正在从 FRED 加载 VIX 恐慌指数..."):
            df_vix = get_vix_data()
        if not df_vix.empty:
            latest_vix = df_vix["VIX"].dropna().iloc[-1]
            latest_vix_date = df_vix.dropna(subset=["VIX"])["date"].iloc[-1].strftime("%Y-%m-%d")
            st.metric(
                label=f"最新 VIX 指数 ({latest_vix_date})",
                value=f"{latest_vix:.2f}",
                delta="极度恐慌 (>30)" if latest_vix > 30 else ("情绪警惕 (20-30)" if latest_vix > 20 else "市场平稳 (<20)"),
                delta_color="inverse" if latest_vix > 20 else "normal"
            )
            fig_vix = create_vix_chart(df_vix, timeframe=macro_tf)
            if fig_vix:
                st.plotly_chart(fig_vix, use_container_width=True)
                with st.expander("💡 CBOE VIX 恐慌指数解读指南", expanded=False):
                    st.markdown("""
                    * **< 15 (极度自满/低波动)**：市场处于平静期或牛市主升段，但衍生品防范尾部风险的对冲成本极低。
                    * **15 - 20 (中性平稳)**：美股历史常态波动区间。
                    * **20 - 30 (风险警惕/情绪承压)**：市场开始消化加息、地缘政治或财报不确定性，抛压逐渐释放。
                    * **> 30 (高恐慌预警/流动性踩踏)**：波动率脉冲式飙升，通常对应恐慌性抛售或历史级左侧买点。
                    """)
        else:
            st.info("正在加载或暂无 VIX 数据...")

    with col2:
        st.subheader("CNN 恐慌与贪婪指数 (Fear & Greed)")
        with st.spinner("正在获取 CNN 恐慌与贪婪指数..."):
            df_fgi = get_cnn_fear_and_greed_data()
        if not df_fgi.empty:
            latest_row = df_fgi.dropna(subset=["Score"]).iloc[-1]
            score_val = latest_row["Score"]
            rating_val = latest_row["Rating"]
            date_str = latest_row["date"].strftime("%Y-%m-%d")
            st.metric(
                label=f"最新情绪得分 ({date_str})",
                value=f"{score_val:.1f} / 100",
                delta=f"评级: {rating_val}",
                delta_color="normal" if score_val > 50 else "inverse"
            )
            fig_fgi = create_cnn_fear_greed_chart(df_fgi, timeframe=macro_tf)
            if fig_fgi:
                st.plotly_chart(fig_fgi, use_container_width=True)
                with st.expander("💡 CNN 恐慌与贪婪指数解读指南", expanded=False):
                    st.markdown("""
                    * **0 - 25 (Extreme Fear, 极度恐慌)**：投资者极度悲观，往往预示市场严重超卖，提供逆向价值买入机会。
                    * **25 - 45 (Fear, 恐慌)**：避险情绪主导，资金流向国债等防御性资产。
                    * **45 - 55 (Neutral, 中性)**：市场多空处于博弈均衡状态。
                    * **55 - 75 (Greed, 贪婪)**：风险偏好回暖，股市动能与广度扩张。
                    * **75 - 100 (Extreme Greed, 极度贪婪)**：FOMO (错失恐惧) 情绪蔓延，杠杆与估值泡沫积聚，需警惕回调风险。
                    """)
        else:
            st.info("正在加载或暂无 CNN 恐慌与贪婪指数数据...")

    # ==================================================================
    # 4. 股权风险溢价 (Equity Risk Premium, ERP) - 方案 2 动态版
    # ==================================================================
    st.markdown("---")
    st.header("📊 股权风险溢价 (Equity Risk Premium, ERP)")

    # 允许在前端动态微调 NTM EPS 预期（默认设置为当前华尔街基准 288.0 美元）
    col_ctrl, _ = st.columns([2.5, 7.5])
    with col_ctrl:
        custom_eps = st.number_input(
            "华尔街标普 500 NTM EPS 一致预期 ($):",
            min_value=200.0, max_value=400.0, value=288.0, step=1.0,
            help="未来 12 个月一致预期每股收益。调高 EPS 预期意味着盈利更乐观，Forward P/E 降低，ERP 提升。"
        )

    erp_data = get_erp_data(base_ntm_eps=custom_eps)

    if erp_data:
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("当前 ERP 风险溢价", f"{erp_data['current_erp']:+.2f}%", 
                  help="ERP = 远期盈利收益率 - 10Y美债收益率。<0.5% 提示美股相对债券性价比较低")
        c2.metric("远期盈利收益率 (Fwd EY)", f"{erp_data['current_ey']:.2f}%",
                  help=f"计算公式: EPS (${erp_data['ntm_eps']:.0f}) / SPX (${erp_data['spx_price']:,.1f})")
        c3.metric("标普实时远期 P/E", f"{erp_data['fwd_pe']:.1f}x",
                  help=f"标普点位 ({erp_data['spx_price']:,.1f}) / NTM EPS (${erp_data['ntm_eps']:.0f})")
        c4.metric("10Y 美债无风险收益率", f"{erp_data['latest_yield']:.2f}%")

        fig_erp = create_erp_chart(erp_data, timeframe=macro_tf)
        if fig_erp:
            st.plotly_chart(fig_erp, use_container_width=True)
            with st.expander("💡 股权风险溢价 (ERP) 与远期估值决策指南", expanded=False):
                st.markdown(f"""
                * **当前核算基准**：S&P 500 实时点位 **${erp_data['spx_price']:,.1f}**，华尔街 NTM EPS 一致预期 **${erp_data['ntm_eps']:.1f}**。
                * **ERP 估值含义**：
                  * **$\text{{ERP}} < 0\%$（极端倒挂）**：股票盈利收益率低于 10 年期无风险美债，历史上多见于泡沫末期，权益资产抗风险缓冲极低。
                  * **$0\% \le \text{{ERP}} \le 1.0\%$（低性价比）**：美股处于估值偏高状态，防守型资产比重宜适当提升。
                  * **$\text{{ERP}} > 2.5\% \sim 3.0\%$（高吸引力）**：股票资产具备充足的安全边际，通常对应市场超跌反弹或牛市初期的优质买点。
                """)

    # ==================================================================
    # 5. CBOE SKEW 黑天鹅指数与暗池 DIX
    # ==================================================================
    st.markdown("---")
    st.header("📊 机构极端情绪与暗池资金 (SKEW & Dark Pool DIX)")

    skew_dix_dict = get_skew_dix_data()
    if skew_dix_dict:
        df_skew = skew_dix_dict.get("df_skew", pd.DataFrame())
        df_dix = skew_dix_dict.get("df_dix", pd.DataFrame())

        sk1, sk2 = st.columns(2)
        if not df_skew.empty:
            cur_skew = df_skew['SKEW'].iloc[-1]
            sk1.metric("最新 CBOE SKEW 指数", f"{cur_skew:.1f}", 
                       delta="高防守警戒: 140", delta_color="inverse" if cur_skew > 140 else "normal")
        if not df_dix.empty:
            cur_dix = df_dix['DIX_pct'].iloc[-1]
            sk2.metric("最新暗池买入比 (DIX)", f"{cur_dix:.1f}%", 
                       delta="主力吸筹线: 45%", delta_color="normal" if cur_dix > 45.0 else "off")

        fig_skew_dix = create_skew_dix_chart(skew_dix_dict, timeframe=macro_tf)
        if fig_skew_dix:
            st.plotly_chart(fig_skew_dix, use_container_width=True)
            with st.expander("💡 SKEW 与暗池 DIX 解读指南", expanded=False):
                st.markdown("""
                * **CBOE SKEW**：衡量虚值 Put 溢价。若 VIX 处于低位但 SKEW 飙升突破 140，意味着大资金正在隐秘抢购崩盘保险。
                * **暗池 DIX**：衡量大机构挂单成交做多比例。DIX > 45%（绿色警戒线）往往预示着中短期多头底部买点成立。
                """)

    # ==================================================================
    # 6. 跨资产避险/风险偏好比率 (Copper/Gold & HYG/TLT)
    # ==================================================================
    st.markdown("---")
    st.header("📊 跨资产避险与风险偏好比率 (Risk-on / Risk-off)")

    df_ratios = get_risk_ratios_data()
    if df_ratios is not None and not df_ratios.empty:
        r1, r2 = st.columns(2)
        if 'Copper_Gold_Ratio' in df_ratios.columns:
            r1.metric("铜金比率 (Copper/Gold)", f"{df_ratios['Copper_Gold_Ratio'].dropna().iloc[-1]:.2f}")
        if 'HYG_TLT_Ratio' in df_ratios.columns:
            r2.metric("信用利差风险比率 (HYG/TLT)", f"{df_ratios['HYG_TLT_Ratio'].dropna().iloc[-1]:.3f}")

        fig_ratios = create_cross_asset_ratios_chart(df_ratios, timeframe=macro_tf)
        if fig_ratios:
            st.plotly_chart(fig_ratios, use_container_width=True)
            with st.expander("💡 跨资产比率解读指南", expanded=False):
                st.markdown("""
                * **铜金比**：宏观经济增长与大宗商品周期的风向标。比率突破 50 日均线上行代表周期复苏与 Risk-on。
                * **HYG / TLT**：高收益债与长期国债比值。比值坚挺上行说明信贷息差稳定、风险偏好良好；破位下行则是股市调整前夕的早期预警信号。
                """)

    st.markdown("---")

    # --- 3. 资金面体温计 & 指数结构集中度 ---
    st.header("📊 资金面体温计 & 指数结构集中度")
    col_sofr, col_top10 = st.columns(2)

    with col_sofr:
        st.subheader("SOFR - IORB 资金面体温计")
        with st.spinner("正在计算 SOFR - IORB 利差数据..."):
            df_sofr = get_sofr_iorb_data()
        if not df_sofr.empty:
            latest_sofr = df_sofr.dropna(subset=["Spread_bps"]).iloc[-1]
            spread_val = latest_sofr["Spread_bps"]
            sofr_rate = latest_sofr["SOFR"]
            iorb_rate = latest_sofr["IORB"]
            sofr_date = latest_sofr["date"].strftime("%Y-%m-%d")
            st.metric(
                label=f"SOFR - IORB 利差 ({sofr_date})",
                value=f"{spread_val:+.1f} bps",
                delta=f"SOFR: {sofr_rate:.2f}% | IORB: {iorb_rate:.2f}%",
                delta_color="inverse" if spread_val > 0 else "normal"
            )
            fig_sofr = create_sofr_iorb_chart(df_sofr, timeframe=macro_tf)
            if fig_sofr:
                st.plotly_chart(fig_sofr, use_container_width=True)
                with st.expander("💡 SOFR - IORB 资金面体温计解读指南", expanded=False):
                    st.markdown("""
                    * **指标定位**：**SOFR**（有担保隔夜融资利率，代表市场借钱成本）减去 **IORB**（准备金余额利率，美联储付给银行的无风险利率）。
                    * **< 0 bps (常态充裕)**：银行宁可把多余钱存回美联储拿 IORB，市场流动性极为宽松。
                    * **0 ~ +5 bps (轻度偏紧/临界点)**：银行间市场资金开始出现结构性摩擦，短期借贷成本抬升。
                    * **> +10 bps (钱荒/流动性危机警报)**：类似 2019 年 9 月隔夜回购利率飙升危机，表明银行超额准备金已接近甚至跌破最低舒适水平 (LCLoR)，美联储可能被迫提前终止量化紧缩 (QT) 或开启流动性注入。
                    """)
        else:
            st.info("正在加载或暂无 SOFR / IORB 数据...")

    with col_top10:
        st.subheader("S&P 500 前十大持仓集中度")
        with st.spinner("正在加载标普500前十大持仓集中度..."):
            df_top10 = get_top10_concentration_data()
        if not df_top10.empty:
            fig_top10 = create_top10_concentration_chart(df_top10)
            if fig_top10:
                st.plotly_chart(fig_top10, use_container_width=True)
                with st.expander("💡 S&P 500 前十大持仓集中度解读指南", expanded=False):
                    st.markdown("""
                    * **集中度含义**：前 10 大超级权重巨头（Mega-Caps，如 MSFT, AAPL, NVDA, GOOGL, AMZN, META）占指数整体市值的比重已接近 **35% - 40%**，创下近 50 年历史极值。
                    * **市场脆弱性**：当集中度过高时，大盘指数（SPY/QQQ）的涨跌实质上被极少数几家科技巨头绑架。即使底层 490 只股票普遍下跌，只要巨头拉升指数即可掩盖市场疲弱；一旦巨头补跌，大盘将面临剧烈共振回撤。
                    """)
        else:
            st.info("正在加载或暂无前十大持仓集中度数据...")

    st.markdown("---")

    # --- 4. 宏观指标与流动性追踪 ---
    st.header("📊 宏观指标与流动性追踪")

    # 第一组：实际利率 & 净流动性
    col3, col4 = st.columns(2)
    with col3:
        st.subheader("10Y TIPS 实际利率 & 通胀预期")
        with st.spinner("正在从 FRED 加载 10Y TIPS 实际利率与通胀预期..."):
            df_ry = get_real_yield_and_breakeven_data()
        if not df_ry.empty:
            fig_ry = create_real_yield_breakeven_chart(df_ry, timeframe=macro_tf)
            if fig_ry:
                st.plotly_chart(fig_ry, use_container_width=True)
                with st.expander("💡 10Y TIPS 实际利率 & 通胀预期解读指南", expanded=False):
                    st.markdown("""
                    * **10Y TIPS 实际利率 (DFII10)**：全球无风险资产的**真实资本回报率**，亦是全球风险资产（尤其高估值成长股）估值折现率的核心分母。实际利率走高往往导致成长股 PE 承压。
                    * **10Y 盈亏平衡通胀预期 (T10YIE)**：名义美债利率与 TIPS 利率之差，代表债券市场定价的未来 10 年平均年化通胀率。维持在 2.0% - 2.5% 表明美联储抗通胀信誉良好。
                    """)
        else:
            st.info("正在加载或暂无实际利率与通胀预期数据...")

    with col4:
        st.subheader("美联储净流动性 & 银行准备金")
        with st.spinner("正在从 FRED 计算美联储净流动性与准备金余额..."):
            df_liq = get_net_liquidity_data()
        if not df_liq.empty:
            fig_liq = create_net_liquidity_chart(df_liq, timeframe=macro_tf)
            if fig_liq:
                st.plotly_chart(fig_liq, use_container_width=True)
                with st.expander("💡 美联储净流动性 & 银行准备金解读指南", expanded=False):
                    st.markdown("""
                    * **净流动性公式**：`Net Liquidity = 美联储总资产 (WALCL) - 财政部现金账户 (TGA) - 隔夜逆回购 (RRP)`。
                    * **与美股高度正相关**：净流动性是驱动风险资产水位的核心流动性水龙头。当 TGA 充水或联储缩表时流动性被吸干；当 RRP 资金释放或 TGA 泄洪时注入流动性，通常领先美股 1-2 周走势。
                    * **银行准备金 (Bank Reserves)**：金融系统的底层真正结算血液。准备金充裕保障信用扩张，跌破阈值易触发金融管道流动性摩擦。
                    """)
        else:
            st.info("正在加载或暂无净流动性数据...")

    st.markdown("---")

    # 第二组：金融条件 (NFCI) & 高收益债信用利差
    col5, col6 = st.columns(2)
    with col5:
        st.subheader("芝加哥联储全国金融条件指数 (NFCI)")
        with st.spinner("正在从 FRED 加载芝加哥联储 NFCI 指数..."):
            df_nfci = get_nfci_data()
        if not df_nfci.empty:
            fig_nfci = create_nfci_chart(df_nfci, timeframe=macro_tf)
            if fig_nfci:
                st.plotly_chart(fig_nfci, use_container_width=True)
                with st.expander("💡 芝加哥联储全国金融条件指数 (NFCI) 解读指南", expanded=False):
                    st.markdown("""
                    * **指标含义**：综合涵盖货币市场、债券市场、股票市场及影子银行系统的 105 项高频金融指标。
                    * **0 轴为历史常态基准**：
                      * **< 0 (宽松 Financial Conditions Loose)**：信贷容易获取，资产价格受到支撑。
                      * **> 0 (紧缩 Financial Conditions Tight)**：融资环境严苛，违约风险与信贷利差扩大，压制宏观经济扩张。
                    """)
        else:
            st.info("正在加载或暂无 NFCI 数据...")

    with col6:
        st.subheader("高收益债信用利差 (US High Yield Spread)")
        with st.spinner("正在从 FRED 加载高收益债信用利差..."):
            df_oas = get_credit_spread_data()
        if not df_oas.empty:
            fig_oas = create_credit_spread_chart(df_oas, timeframe=macro_tf)
            if fig_oas:
                st.plotly_chart(fig_oas, use_container_width=True)
                with st.expander("💡 高收益债信用利差 (US High Yield Spread) 解读指南", expanded=False):
                    st.markdown("""
                    * **指标定义 (BAML Option-Adjusted Spread)**：垃圾债收益率与无风险国债收益率的利差。
                    * **信用风险晴雨表**：
                      * **< 3.5% (极度健康/无违约担忧)**：企业偿债能力强，信贷充裕。
                      * **3.5% ~ 5.0% (中性承压)**：宏观增速放缓，需甄选优质资产。
                      * **> 5.5% (信用风暴预警)**：违约率攀升，企业债务展期受阻，往往预示经济衰退或流动性危机来临。
                    """)
        else:
            st.info("正在加载或暂无信用利差数据...")

    st.markdown("---")

    # 第三组：失业率 & 美联储资产负债表
    col7, col8 = st.columns(2)
    with col7:
        st.subheader("美国失业率 (UNRATE)")
        with st.spinner("正在从 FRED 加载失业率数据..."):
            df_unrate = get_unemployment_data()
        if not df_unrate.empty:
            fig_unrate = create_unemployment_chart(df_unrate, timeframe=macro_tf)
            if fig_unrate:
                st.plotly_chart(fig_unrate, use_container_width=True)
                with st.expander("💡 美国失业率 (UNRATE) 解读指南", expanded=False):
                    st.markdown("""
                    * **双重使命支柱 (Dual Mandate)**：美联储货币政策决策核心。当失业率处于低位时，央行可专注于抗击通胀；失业率快速抬头则迫使美联储转入降息宽松周期。
                    * **非线性跃升特征**：历史上失业率一旦见底反弹超过 0.5%，往往出现自强化的非线性快速上升（萨姆规则）。
                    """)
        else:
            st.info("正在加载或暂无失业率数据...")

    with col8:
        st.subheader("美联储资产负债表 (WALCL)")
        with st.spinner("正在从 FRED 加载美联储资产负债表数据..."):
            df_fed = get_fed_balance_sheet_data()
        if not df_fed.empty:
            fig_fed = create_fed_balance_sheet_chart(df_fed, timeframe=macro_tf)
            if fig_fed:
                st.plotly_chart(fig_fed, use_container_width=True)
                with st.expander("💡 美联储总资产 (WALCL) 解读指南", expanded=False):
                    st.markdown("""
                    * **QE (量化宽松)**：央行大规模购债扩表，向金融体系直接注入基础货币，推高所有风险资产估值。
                    * **QT (量化紧缩)**：央行通过国债/MBS 到期不续做进行缩表回收流动性，给金融体系带来隐性持续紧缩压力。
                    """)
        else:
            st.info("正在加载或暂无美联储资产负债表数据...")

    st.markdown("---")

    # 第四组：金油比
    col9, _ = st.columns(2)
    with col9:
        st.subheader("Gold / Oil Ratio (金油比)")
        with st.spinner("正在计算金油比历史数据..."):
            df_go = get_gold_oil_ratio_data()
        if not df_go.empty:
            fig_go = create_gold_oil_ratio_chart(df_go, timeframe=macro_tf)
            if fig_go:
                st.plotly_chart(fig_go, use_container_width=True)
                with st.expander("💡 Gold / Oil Ratio (金油比) 解读指南", expanded=False):
                    st.markdown("""
                    * **指标定义**：1 盎司黄金能购买的原油桶数（黄金代表终极避险与信用对冲，原油代表实体经济工业需求与总需求活力）。
                    * **> 25 - 30 (高风险/衰退预警)**：通常发生在经济衰退、实体总需求暴跌（油价下跌）且地缘/金融恐慌避险升温（金价上涨）阶段（如 2008 年次贷危机、2020 年疫情大跌）。
                    * **< 15 (经济过热/通胀高企)**：工业总需求旺盛，大宗商品通胀上行。
                    """)
        else:
            st.info("正在加载或暂无金油比数据...")

    st.markdown("---")

    # --- 5. 收益率曲线利差与衰退定量模型 ---
    st.header("📊 收益率曲线利差与衰退定量模型 (Curve Spreads & Recession Gauges)")
    col_spr, col_sahm = st.columns(2)

    with col_spr:
        st.subheader("10Y-2Y & 10Y-3M 美债期限利差")
        with st.spinner("正在加载国债期限利差数据..."):
            df_spreads = get_yield_spreads_data()
        if not df_spreads.empty:
            fig_spreads = create_yield_spreads_chart(df_spreads, timeframe=macro_tf)
            if fig_spreads:
                st.plotly_chart(fig_spreads, use_container_width=True)
                with st.expander("💡 10Y-2Y & 10Y-3M 美债期限利差解读指南", expanded=False):
                    st.markdown("""
                    * **10Y-2Y 利差 (T10Y2Y)**：市场交易降息预期与中期经济周期的核心定价基准。
                    * **10Y-3M 利差 (T10Y3M)**：美联储官方最青睐的经济衰退预测利差指标，倒挂深幅度预示未来 12 个月经济衰退概率大幅攀升。
                    * **真正风险点在“解挂恢复” (Un-inversion)**：历史表明股市最大跌幅往往不发生在倒挂最深处，而发生在**曲线从倒挂重新快速陡峭化（牛陡）**并进入实质性衰退降息的初期。
                    """)
        else:
            st.info("正在加载或暂无期限利差数据...")

    with col_sahm:
        st.subheader("萨姆法则衰退指标 (Sahm Rule)")
        with st.spinner("正在加载萨姆法则指标..."):
            df_sahm = get_sahm_rule_data()
        if not df_sahm.empty:
            latest_sahm = df_sahm.dropna(subset=["Sahm_Rule"]).iloc[-1]
            sahm_val = latest_sahm["Sahm_Rule"]
            sahm_date = latest_sahm["date"].strftime("%Y-%m-%d")
            st.metric(
                label=f"当前萨姆衰退指标值 ({sahm_date})",
                value=f"{sahm_val:.2f}",
                delta="触发衰退警报 (≥0.50)" if sahm_val >= 0.50 else "经济处于非衰退状态 (<0.50)",
                delta_color="inverse" if sahm_val >= 0.50 else "normal"
            )
            fig_sahm = create_sahm_rule_chart(df_sahm, timeframe=macro_tf)
            if fig_sahm:
                st.plotly_chart(fig_sahm, use_container_width=True)
                with st.expander("💡 萨姆法则衰退指标 (Sahm Rule) 解读指南", expanded=False):
                    st.markdown("""
                    * **萨姆法则定义 (Sahm Rule)**：当美国 3 个月移动平均失业率相比过去 12 个月的最低点上升 **0.50 个百分点 (0.50%)** 或以上时，标志着经济已陷入实质性衰退。
                    * **历史 100% 准确率**：自 1970 年以来的历次美国官方经济衰退中，萨姆法则均在衰退发生初期精准发出信号，且从未产生过假阳性误报。
                    """)
        else:
            st.info("正在加载或暂无萨姆法则数据...")

    st.markdown("---")

    # --- 6. 实体经济景气与高频就业追踪 ---
    st.header("📊 实体经济景气与高频就业追踪 (Leading Growth & Labor Market)")
    col_claims, col_capex = st.columns(2)

    with col_claims:
        st.subheader("美国周度初请失业金人数 (Jobless Claims)")
        with st.spinner("正在加载失业金申请高频数据..."):
            df_claims = get_jobless_claims_data()
        if not df_claims.empty:
            fig_claims = create_jobless_claims_chart(df_claims, timeframe=macro_tf)
            if fig_claims:
                st.plotly_chart(fig_claims, use_container_width=True)
                with st.expander("💡 周度初请失业金人数 (Jobless Claims) 解读指南", expanded=False):
                    st.markdown("""
                    * **初请失业金人数 (Initial Claims, 领先指标)**：每周公布的高频裁员晴雨表，通常超过 **25–26 万人** 表明劳动力市场边际松动，超过 **30 万人** 为深度疲弱信号。
                    * **续请失业金人数 (Continued Claims, 同期指标)**：反映被裁员工重新找到新工作的难易程度。续请持续走高表明失业周期拉长，再就业市场趋于冻结。
                    """)
        else:
            st.info("正在加载或暂无失业金申请数据...")

    with col_capex:
        st.subheader("核心资本品新订单 (Core CapEx Orders)")
        with st.spinner("正在加载核心资本品新订单数据..."):
            df_capex = get_core_capex_data()
        if not df_capex.empty:
            fig_capex = create_core_capex_chart(df_capex, timeframe=macro_tf)
            if fig_capex:
                st.plotly_chart(fig_capex, use_container_width=True)
                with st.expander("💡 核心资本品新订单 (Core CapEx Orders) 解读指南", expanded=False):
                    st.markdown("""
                    * **指标定义**：扣除国防与飞机的非国防资本品新订单（Nondefense Capital Goods Excluding Aircraft），反映美国实体企业对未来设备更新与生产扩张的**前瞻性资本开支意愿**。
                    * **同比增速 (YoY)**：长期领先美国私人投资与企业盈利周期，同比转负通常伴随着企业投资收缩与经济降速。
                    """)
        else:
            st.info("正在加载或暂无核心资本品订单数据...")

    st.markdown("---")

    # --- 7. 通胀中枢、广义货币与全球美元水温 ---
    st.header("📊 通胀中枢、广义货币与全球美元水温 (Inflation & Broad Liquidity)")
    col_cpi, col_dxy = st.columns(2)

    with col_cpi:
        st.subheader("核心 PCE 通胀同比 vs. 时薪增速")
        with st.spinner("正在加载核心通胀与时薪数据..."):
            df_inf_w = get_inflation_wages_data()
        if not df_inf_w.empty:
            fig_inf_w = create_inflation_wages_chart(df_inf_w, timeframe=macro_tf)
            if fig_inf_w:
                st.plotly_chart(fig_inf_w, use_container_width=True)
                with st.expander("💡 核心 PCE 通胀同比 vs. 时薪增速解读指南", expanded=False):
                    st.markdown("""
                    * **薪资-通胀螺旋 (Wage-Price Spiral)**：当平均时薪同比增速持续高于核心通胀时，居民实际购买力改善；但若薪资增速远超生产率增长，易推动服务业通胀粘性与二次通胀风险。
                    * **美联储 2.0% 锚定**：核心通胀回落至 2.0%-2.5% 区间是美联储确立降息周期的核心前置条件。
                    """)
        else:
            st.info("正在加载或暂无通胀与薪资数据...")

    with col_dxy:
        st.subheader("美元指数 (U.S. Dollar Index / DXY)")
        with st.spinner("正在加载美元指数数据..."):
            df_dxy = get_dxy_data()
        if not df_dxy.empty:
            fig_dxy = create_dxy_chart(df_dxy, timeframe=macro_tf)
            if fig_dxy:
                st.plotly_chart(fig_dxy, use_container_width=True)
                with st.expander("💡 美元指数 (DXY) 解读指南", expanded=False):
                    st.markdown("""
                    * **全球金融条件总闸门**：美元走强对全球非美经济体及跨国企业产生汇率紧缩效应，压制美股海外营收折算与新兴市场流动性。
                    * **避险属性 (Dollar Smile)**：在美联储极度鹰派加息或全球发生流动性危机时，美元呈现强避险上涨特征。
                    """)
        else:
            st.info("正在加载或暂无美元指数数据...")

    st.markdown("---")

    # --- 8. 商业银行信贷标准与 M2 货币供应 ---
    st.header("📊 商业银行信贷标准与 M2 货币供应 (Credit Standards & Money Supply)")
    col_sloos, col_m2 = st.columns(2)

    with col_sloos:
        st.subheader("美联储银行信贷标准调查 (SLOOS)")
        with st.spinner("正在加载银行贷款标准净收紧比例 (SLOOS)..."):
            df_sloos = get_sloos_credit_data()
        if not df_sloos.empty:
            fig_sloos = create_sloos_credit_chart(df_sloos, timeframe=macro_tf)
            if fig_sloos:
                st.plotly_chart(fig_sloos, use_container_width=True)
                with st.expander("💡 银行贷款标准 (SLOOS) 解读指南", expanded=False):
                    st.markdown("""
                    * **指标定义 (Senior Loan Officer Opinion Survey)**：对大中型企业工商业贷款 (C&I Loans) 标准净收紧的银行百分比。
                    * **极强前瞻性**：银行信贷收紧通常**领先企业违约率与实际信贷萎缩 2–4 个季度**。净收紧比例超过 +20%~+40% 标志着信贷紧缩周期，对中小企业资本开支与再融资构成严峻考验。
                    """)
        else:
            st.info("正在加载或暂无 SLOOS 数据...")

    with col_m2:
        st.subheader("广义货币供应量 M2 同比增速")
        with st.spinner("正在加载 M2 货币供应量数据..."):
            df_m2 = get_m2_money_supply_data()
        if not df_m2.empty:
            fig_m2 = create_m2_money_supply_chart(df_m2, timeframe=macro_tf)
            if fig_m2:
                st.plotly_chart(fig_m2, use_container_width=True)
                with st.expander("💡 广义货币供应量 M2 同比增速解读指南", expanded=False):
                    st.markdown("""
                    * **实体购买力总蓄水池**：M2 包括流通中现金、活期与定期存款、货币市场基金等。
                    * **同比负增长 (罕见收缩)**：2022-2023 年出现的 M2 同比负增长为近百年罕见，反映美联储激进加息与 QT 对商业银行存款体系的强力抽水效应；M2 同比重新企稳回升预示金融再通胀周期的启动。
                    """)
        else:
            st.info("正在加载或暂无 M2 数据...")

    st.markdown("---")

    # --- 9. 宏观策略与周期框架总览 (深度研究附录) ---
    with st.expander("📖 查看《见证逆潮》核心宏观逻辑与收益率曲线策略指南（深度解析版）", expanded=False):
        st.markdown("""
        ### 一、 宏观流动性与收益率曲线的三大定律

        #### 1. 收益率曲线形态与经济周期四阶段
        * **牛平 (Bull Flattening)**：经济过热后期，长端利率下行快于短端（预示远期增长降速与通胀见顶），适合超配长久期国债。
        * **熊平 (Bear Flattening)**：央行抗通胀激进加息，短端利率急升压平甚至倒挂曲线，权益市场承受估值杀跌。
        * **牛陡 (Bull Steepening)**：衰退显现，央行开启大幅降息，短端利率领跌，曲线快速脱离倒挂（**历史上美股最大主跌浪与出清阶段通常发生于此**）。
        * **熊陡 (Bear Steepening)**：经济强劲复苏或财政债务赤字失控，长端发债供给过剩推升期限溢价，顺周期价值股与大宗商品跑赢成长股。

        #### 2. 美联储流动性水库三大闸门联动机制
        * **流动性平衡公式**：$$\\text{Net Liquidity} = \\text{WALCL (美联储总资产)} - \\text{TGA (财政部现金)} - \\text{RRP (隔夜逆回购)}$$
        * **RRP 的缓冲垫作用**：2023 年美联储 QT 期间，财政部大量发债并未冲击市场，原因在于 2 万亿美元的 RRP 逆回购资金流出承接了美债供给，形成了隐性的“流动性释放”。当 RRP 耗尽至低位后，财政部再发债将直接抽取商业银行准备金，触发真实流动性紧缩。

        #### 3. 信用利差与金融条件的断崖效应
        * 信用利差（High Yield OAS）在经济扩张期具备漫长平稳的**低波动钝化期**，但一旦突破 4.0%~4.5% 临界水平，利差呈现快速脉冲式非线性放大。
        """)

