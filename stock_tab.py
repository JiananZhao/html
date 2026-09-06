"""
Stock Analysis & Valuation Tab (Tab 2)
"""
import streamlit as st
import pandas as pd
import numpy as np

from data_service import (
    get_stock_historical_data,
    get_stock_fundamentals,
    get_stock_financial_statements,
)
from quant_models import calculate_reverse_dcf
from visualization import (
    create_stock_price_chart,
    create_pe_ps_band_chart,
    create_technical_momentum_chart,
    create_financial_trends_chart,
)

def render_stock_tab():
    st.header("🔍 个股深度量化与多因子估值追踪")
    st.markdown("集成实时行情、PE/PS Band 动态估值通道、反向 DCF 市场预期测算、技术动量及财务三张表明细。")

    # 1. 股票代码输入与基础信息
    col_input1, col_input2, col_input3 = st.columns([2, 2, 4])
    with col_input1:
        ticker_to_analyze = st.text_input("输入美股代码 (Ticker):", value="NVDA").upper().strip()
    with col_input2:
        stock_tf = st.selectbox(
            "选择行情观察时间周期:",
            ["1M", "3M", "6M", "1Y", "3Y", "5Y", "ALL"],
            index=3,
            key="stock_timeframe_select"
        )
    with col_input3:
        chart_mode = st.radio("选择行情主图模式:", ["K线图 (Candlestick + 均线)", "折线图 (Line)"], horizontal=True)

    if ticker_to_analyze:
        with st.spinner(f"正在拉取 {ticker_to_analyze} 实时行情与基本面数据..."):
            stock_df = get_stock_historical_data(ticker_to_analyze, period="5y")
            stock_info = get_stock_fundamentals(ticker_to_analyze)

        if not stock_df.empty and stock_info:
            curr_price = stock_info.get("currentPrice", stock_info.get("regularMarketPrice", stock_df["Close"].iloc[-1]))
            comp_name = stock_info.get("shortName", ticker_to_analyze)
            sector = stock_info.get("sector", "N/A")
            industry = stock_info.get("industry", "N/A")
            pe_ttm = stock_info.get("trailingPE", np.nan)
            pe_fwd = stock_info.get("forwardPE", np.nan)
            ps_ttm = stock_info.get("priceToSalesTrailing12Months", np.nan)
            pb_ratio = stock_info.get("priceToBook", np.nan)
            market_cap = stock_info.get("marketCap", np.nan)
            fcf = stock_info.get("freeCashflow", np.nan)
            shares_out = stock_info.get("sharesOutstanding", np.nan)
            eps_ttm = stock_info.get("trailingEps", np.nan)
            beta = stock_info.get("beta", np.nan)
            fcf_per_share = (fcf / shares_out) if (pd.notna(fcf) and pd.notna(shares_out) and shares_out > 0) else np.nan

            st.subheader(f"🏢 {comp_name} ({ticker_to_analyze}) — {sector} | {industry}")

            # 核心估值卡片
            kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
            kpi1.metric("当前实时股价", f"${curr_price:.2f}" if pd.notna(curr_price) else "N/A")
            kpi2.metric("市盈率 PE (TTM / Fwd)", f"{pe_ttm:.1f} / {pe_fwd:.1f}" if (pd.notna(pe_ttm) and pd.notna(pe_fwd)) else (f"{pe_ttm:.1f}" if pd.notna(pe_ttm) else "N/A"))
            kpi3.metric("市销率 P/S (TTM)", f"{ps_ttm:.2f}x" if pd.notna(ps_ttm) else "N/A")
            kpi4.metric("总市值 (Market Cap)", f"${market_cap/1e9:.2f} B" if pd.notna(market_cap) else "N/A")
            kpi5.metric("每股自由现金流 (FCF/Sh)", f"${fcf_per_share:.2f}" if pd.notna(fcf_per_share) else "N/A")

            st.markdown("---")

            # 2. 个股行情与均线系统 (MA20 / MA50 / MA200 & 成交量副图)
            st.subheader(f"📈 {ticker_to_analyze} 交互式行情走势 (MA20 / MA50 / MA200 均线系统)")
            chart_type_arg = "Candlestick" if "Candlestick" in chart_mode else "Line"
            fig_stock_price = create_stock_price_chart(stock_df, ticker_to_analyze, chart_type=chart_type_arg, timeframe=stock_tf)
            if fig_stock_price:
                st.plotly_chart(fig_stock_price, use_container_width=True)

            st.markdown("---")

            # 3. 动态 PE / PS 估值通道 (PE / PS Band)
            # ==================================================================
            st.markdown("---")
            st.subheader("📈 历史估值分位与 PE / PS Band (估值通道透视)")
            st.caption("叠加历史动态估值倍数通道，评估当前股价处于历史估值的折溢价状态与合理中枢")

            # 1. 修复：必须传入列宽比例或列数 [3, 1]
            val_col1, val_col2 = st.columns([3, 1])

            with val_col2:
                val_type_choice = st.radio(
                    "选择通道基准估值模型:", 
                    ["PE Band (基于 TTM EPS)", "PS Band (基于 TTM 每股营收)"], 
                    index=0,
                    key="pe_ps_val_mode_choice"
                )
                is_pe_mode = "PE" in val_type_choice
                val_type_code = "PE" if is_pe_mode else "PS"
                band_tf = st.selectbox("估值带时间跨度:", ["1Y", "3Y", "5Y", "ALL"], index=1, key="band_timeframe")

            with val_col1:
                cur_p = stock_info.get("currentPrice") or stock_info.get("regularMarketPrice") or stock_info.get("previousClose") or 100.0
                cur_pe_val = stock_info.get("trailingPE") if stock_info else None
                cur_eps_val = stock_info.get("trailingEps") if stock_info else None
                cur_ps_val = stock_info.get("priceToSalesTrailing12Months") if stock_info else None

                # 计算每股营收 SPS (Sales Per Share)
                rev_raw = stock_info.get("totalRevenue") if stock_info else None
                shs_out = stock_info.get("sharesOutstanding") if stock_info else None
                cur_sps_val = (rev_raw / shs_out) if (rev_raw and shs_out and shs_out > 0) else ((cur_p / cur_ps_val) if (cur_p and cur_ps_val) else None)

                # 检查是否满足绘图条件
                if is_pe_mode and (not cur_eps_val or cur_eps_val <= 0):
                    st.warning(f"⚠️ **{ticker_to_analyze}** 当前滚动每股收益 (TTM EPS: ${cur_eps_val if cur_eps_val is not None else 'N/A'}) 为负或暂未实现盈利，无法绘制 PE 市盈率通道。请在右侧单选框切换至 **PS Band (基于 TTM 每股营收)** 评估其营收估值水位。")
                else:
                    val_metric_val = cur_eps_val if is_pe_mode else cur_sps_val
                    val_multiple_val = cur_pe_val if is_pe_mode else cur_ps_val

                    # 2. 修复：使用当前作用域中的实际 DataFrame 变量 stock_df
                    if stock_df is not None and not stock_df.empty and val_metric_val and val_metric_val > 0:
                        fig_band = create_pe_ps_band_chart(
                            stock_df,
                            symbol=ticker_to_analyze,
                            current_eps=val_metric_val if is_pe_mode else None,
                            current_rev_per_share=val_metric_val if not is_pe_mode else None,
                            timeframe=band_tf
                        )
                        if fig_band:
                            st.plotly_chart(fig_band, use_container_width=True)
                            with st.expander(f"💡 {val_type_code} Band 估值通道投资解读", expanded=False):
                                metric_name = "每股收益 (EPS)" if is_pe_mode else "每股营收 (SPS)"
                                st.markdown(f"""
                                * **估值通道逻辑**：以公司当前{metric_name}（${val_metric_val:.2f}）为基准，绘制 5 条历史代表性估值倍数通道（0.6x、0.8x、1.0x、1.25x、1.5x）。
                                * **超买/超卖信号**：
                                  * 股价触及或突破顶轨（高估值通道）：表明市场给予极高预期溢价，情绪可能过热。
                                  * 股价回落至底轨（低估值通道）：通常对应基本面利空充分出清或悲观情绪超跌区间。
                                """)
                    else:
                        st.info(f"未能获取 {ticker_to_analyze} 足够的估值数据用于绘制通道。")

            # 4. 反向 DCF 估值测算器 (Reverse DCF)
            st.subheader("🎯 反向 DCF 估值测算器 (Reverse DCF & Implied Growth)")
            st.markdown("""
            **经典买方思考范式**：不尝试主观预测未来极其不确定的增长率，而是反推**当前股价所严格内含的未来 10 年自由现金流 (FCF) 年化复合增长率 (CAGR)**。
            """)
            col_dcf_in1, col_dcf_in2, col_dcf_in3 = st.columns(3)
            with col_dcf_in1:
                wacc_in = st.slider("贴现率 (WACC / 投资人要求回报率 %):", min_value=6.0, max_value=15.0, value=9.0, step=0.5) / 100.0
            with col_dcf_in2:
                tg_in = st.slider("永续年化增长率 (Terminal Growth %):", min_value=1.0, max_value=4.5, value=3.0, step=0.25) / 100.0
            with col_dcf_in3:
                years_in = st.selectbox("预测显性增长年限:", [5, 7, 10], index=2)

            if pd.notna(fcf_per_share) and fcf_per_share > 0 and pd.notna(curr_price):
                implied_growth = calculate_reverse_dcf(
                    curr_price,
                    fcf_per_share,
                    wacc=wacc_in,
                    terminal_growth=tg_in,
                    forecast_years=years_in
                )
                if pd.notna(implied_growth):
                    res_col1, res_col2 = st.columns(2)
                    with res_col1:
                        st.metric(
                            label=f"当前股价 ${curr_price:.2f} 隐含的未来 {years_in} 年 FCF 年化增速",
                            value=f"{implied_growth:.2f}%",
                            delta=f"基准 WACC: {wacc_in*100:.1f}% | 永续: {tg_in*100:.1f}%"
                        )
                    with res_col2:
                        st.info(f"""
                        * 若您研判 {ticker_to_analyze} 未来实际 FCF 复合增速 **高于 {implied_growth:.2f}%**，则当前估值具备**安全边际 (Undervalued)**。
                        * 若您认为未来增速 **难以维持 {implied_growth:.2f}%**，则当前市场定价已偏乐观，需警惕预期落空风险。
                        """)
                else:
                    st.warning("反向 DCF 求解未收敛，请检查基准参数。")
            else:
                st.warning(f"由于 {ticker_to_analyze} TTM 自由现金流为负或数据缺失，无法应用标准 FCF 反向 DCF 模型。")

            with st.expander("💡 反向 DCF 估值测算逻辑与安全边际指引", expanded=False):
                st.markdown("""
                * **巴菲特 / 芒格自由现金流逻辑**：内在价值是企业在剩余生命周期内所能产生的全部自由现金流的折现值。
                * **安全边际核心**：通过反向推导市场预期，识别市场是处于过度悲观的“低预期陷阱”还是过度亢奋的“高预期泡沫”。
                """)

            st.markdown("---")

            # 5. 技术面动量指标系统 (RSI, MACD, 200MA)
            st.subheader("⚡ 技术面动量指标系统 (RSI, MACD & 200MA 年线偏离度)")
            fig_tech_mom = create_technical_momentum_chart(stock_df, ticker_to_analyze, timeframe=stock_tf)
            if fig_tech_mom:
                st.plotly_chart(fig_tech_mom, use_container_width=True)
                with st.expander("💡 技术面动量指标系统解读指南", expanded=False):
                    st.markdown("""
                    * **RSI (14) 超买超卖**：RSI > 70 表明短期动量过热易发生均值回归；RSI < 30 进入超卖区间。
                    * **MACD (12, 26, 9) 金叉死叉**：零轴之上的金叉为强势顺势进攻信号；零轴之下的死叉表明下跌动能延续。
                    * **布林带 (Bollinger Bands)**：价格跌破下轨伴随缩量企稳为典型超卖技术反弹点位。
                    """)

            st.markdown("---")

            # 6. 核心财务报表深度透视 (季度与年度财报主要数据)
            st.subheader("📑 核心财务报表深度透视 (季度与年度过去 4–5 期全量明细与趋势图)")
            with st.spinner(f"正在聚合 {ticker_to_analyze} 核心财务三张表趋势明细..."):
                fin_stmts_dict = get_stock_financial_statements(ticker_to_analyze)

            fin_tab_q, fin_tab_a = st.tabs([
                "📊 季度财务报表明细 (Quarterly Financials)",
                "📅 年度财务报表明细 (Annual Financials)"
            ])

            with fin_tab_q:
                df_q_data = fin_stmts_dict.get("quarterly", pd.DataFrame())
                if not df_q_data.empty:
                    fig_fin_q = create_financial_trends_chart(df_q_data, ticker_to_analyze, period_type="季度 (Quarterly)")
                    if fig_fin_q:
                        st.plotly_chart(fig_fin_q, use_container_width=True)
                    st.markdown(f"##### {ticker_to_analyze} 季度核心财务指标全景明细表 ($M / %)")
                    st.dataframe(df_q_data, use_container_width=True, hide_index=True)
                else:
                    st.info(f"暂无 {ticker_to_analyze} 季度结构化财务报表明细。")

            with fin_tab_a:
                df_a_data = fin_stmts_dict.get("annual", pd.DataFrame())
                if not df_a_data.empty:
                    fig_fin_a = create_financial_trends_chart(df_a_data, ticker_to_analyze, period_type="年度 (Annual)")
                    if fig_fin_a:
                        st.plotly_chart(fig_fin_a, use_container_width=True)
                    st.markdown(f"##### {ticker_to_analyze} 年度核心财务指标全景明细表 ($M / %)")
                    st.dataframe(df_a_data, use_container_width=True, hide_index=True)
                else:
                    st.info(f"暂无 {ticker_to_analyze} 年度结构化财务报表明细。")

            st.markdown("---")

            # 7. 机构目标价与分析师共识
            with st.expander("📋 查看分析师评级、目标价与资本结构补充数据", expanded=False):
                col_extra1, col_extra2, col_extra3 = st.columns(3)
                target_mean = stock_info.get("targetMeanPrice", np.nan)
                target_high = stock_info.get("targetHighPrice", np.nan)
                target_low = stock_info.get("targetLowPrice", np.nan)
                num_analysts = stock_info.get("numberOfAnalystOpinions", np.nan)
                recom_key = stock_info.get("recommendationKey", "N/A").upper()

                with col_extra1:
                    st.markdown("##### 🎯 华尔街目标价共识")
                    st.write(f"* **均价目标价**: ${target_mean:.2f}" if pd.notna(target_mean) else "* 均价目标价: N/A")
                    st.write(f"* **最高目标价**: ${target_high:.2f}" if pd.notna(target_high) else "* 最高目标价: N/A")
                    st.write(f"* **最低目标价**: ${target_low:.2f}" if pd.notna(target_low) else "* 最低目标价: N/A")
                    st.write(f"* **覆盖分析师数**: {num_analysts}" if pd.notna(num_analysts) else "* 覆盖分析师数: N/A")
                    st.write(f"* **综合评级**: `{recom_key}`")

                with col_extra2:
                    st.markdown("##### 💼 资本结构与偿债能力")
                    tot_debt = stock_info.get("totalDebt", np.nan)
                    tot_cash = stock_info.get("totalCash", np.nan)
                    quick_r = stock_info.get("quickRatio", np.nan)
                    curr_r = stock_info.get("currentRatio", np.nan)
                    st.write(f"* **总现金储备**: ${tot_cash/1e9:.2f} B" if pd.notna(tot_cash) else "* 总现金储备: N/A")
                    st.write(f"* **总有息负债**: ${tot_debt/1e9:.2f} B" if pd.notna(tot_debt) else "* 总有息负债: N/A")
                    st.write(f"* **流动比率**: {curr_r:.2f}" if pd.notna(curr_r) else "* 流动比率: N/A")
                    st.write(f"* **速动比率**: {quick_r:.2f}" if pd.notna(quick_r) else "* 速动比率: N/A")

                with col_extra3:
                    st.markdown("##### 💰 股利与盈利回报")
                    div_rate = stock_info.get("dividendRate", np.nan)
                    div_yield = stock_info.get("dividendYield", np.nan)
                    roe = stock_info.get("returnOnEquity", np.nan)
                    roa = stock_info.get("returnOnAssets", np.nan)
                    st.write(f"* **年度股息**: ${div_rate:.2f}" if pd.notna(div_rate) else "* 年度股息: 无 / N/A")
                    st.write(f"* **股息率**: {div_yield*100:.2f}%" if pd.notna(div_yield) else "* 股息率: 0.00%")
                    st.write(f"* **净资产收益率 (ROE)**: {roe*100:.2f}%" if pd.notna(roe) else "* ROE: N/A")
                    st.write(f"* **总资产回报率 (ROA)**: {roa*100:.2f}%" if pd.notna(roa) else "* ROA: N/A")
        else:
            st.warning(f"未能获取到 {ticker_to_analyze} 的有效行情或基本面数据，请确认代码正确性。")

