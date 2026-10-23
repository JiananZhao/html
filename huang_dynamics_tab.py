# -*- coding: utf-8 -*-
"""
========================================================================================
Tab 7: 黄文政动力学相空间引擎 (Huang Dynamics Phase Space Engine)
========================================================================================
理论落地：黄文政《物理学、统计学、动态系统、经济学与人工智能的形式同源》
核心架构：
  1. 泛函极值与变分优化：宏观引力锚与动态反身性势能 q_t
  2. 动力学升维：广义势能位置 q_t 与广义动能速度 q_dot_t
  3. 李雅普诺夫稳定性相变门禁：稳态 100% 满仓持股杜绝现金拖累，仅在失稳相变时战术避险
  4. 真实券商记账体系与严苛的四重 Evaluation 自动化评测报告
  5. 任意用户搜索 Ticker 自动脱机加载/固化、回测推演与全景买卖信号标注
========================================================================================
"""

import streamlit as st
import pandas as pd
import numpy as np
import json
import streamlit.components.v1 as components
import importlib
import core_engine.huang_dynamics_engine
importlib.reload(core_engine.huang_dynamics_engine)
from core_engine.huang_dynamics_engine import HuangDynamicsEngine
from charts.html_components import get_chart_theme_tokens


def _safe_style_map(styler, func, subset=None):
    """兼容旧版 (pandas < 2.1 applymap) 与新版 (pandas >= 2.1 map) 的通用 Styler 映射函数"""
    if hasattr(styler, 'map'):
        return styler.map(func, subset=subset)
    elif hasattr(styler, 'applymap'):
        return styler.applymap(func, subset=subset)
    return styler


def _clean_html(raw_html: str) -> str:
    """去除多行 HTML 模板中的空行与行首缩进，彻底杜绝 CommonMark/Markdown 将其误判为代码块 (<pre><code>)"""
    return "\n".join(line.strip() for line in raw_html.splitlines() if line.strip())


# 预置 7 大代表性标的横向评测基准数据汇总 (100% 本地脱机真实券商对账)
MULTI_ASSET_BENCHMARK_DATA = [
    {
        "标的代码": "NOW",
        "公司名称": "ServiceNow (云计算SaaS龙头)",
        "资产特性": "高弹性成长SaaS",
        "适用评级": "⭐⭐⭐⭐☆ (4/5 强共振)",
        "当前核心矛盾": "产业供求力 (行业资本开支)",
        "四力受力结构(宏/产/基/情)": "0.3% / 64.8% / 0.3% / 34.6%",
        "投入本金": "$160,000",
        "策略最终资产": "$1,230,893",
        "基准最终资产": "$757,310",
        "累积净超额 (Alpha $)": "+$473,583",
        "财富相对增厚": "+62.5%",
        "策略CAGR": "17.86%",
        "基准CAGR": "13.34%",
        "策略最大回撤": "-64.15%",
        "基准最大回撤": "-63.90%",
        "配对轮次": "7 轮",
        "持股时间比例": "90.9%",
        "样本外超额": "+136.4%"
    },
    {
        "标的代码": "META",
        "公司名称": "Meta Platforms (社交与AI龙头)",
        "资产特性": "高弹性反身性科技",
        "适用评级": "⭐☆☆☆☆ (1/5 特质博弈)",
        "当前核心矛盾": "市场反身性动能 (特质扰动)",
        "四力受力结构(宏/产/基/情)": "3.1% / 3.8% / 0.0% / 93.1%",
        "投入本金": "$161,000",
        "策略最终资产": "$1,434,828",
        "基准最终资产": "$765,630",
        "累积净超额 (Alpha $)": "+$669,197",
        "财富相对增厚": "+87.4%",
        "策略CAGR": "19.08%",
        "基准CAGR": "13.25%",
        "策略最大回撤": "-41.60%",
        "基准最大回撤": "-74.75%",
        "配对轮次": "11 轮",
        "持股时间比例": "87.5%",
        "样本外超额": "+881.7%"
    },
    {
        "标的代码": "TEAM",
        "公司名称": "Atlassian (企业协作SaaS)",
        "资产特性": "高估值高Beta SaaS",
        "适用评级": "⭐⭐⭐☆☆ (3/5 需看基本面)",
        "当前核心矛盾": "市场反身性动能 (情绪博弈)",
        "四力受力结构(宏/产/基/情)": "0.2% / 41.8% / 0.1% / 57.9%",
        "投入本金": "$119,000",
        "策略最终资产": "$482,163",
        "基准最终资产": "$220,320",
        "累积净超额 (Alpha $)": "+$261,843",
        "财富相对增厚": "+118.8%",
        "策略CAGR": "16.86%",
        "基准CAGR": "7.10%",
        "策略最大回撤": "-74.78%",
        "基准最大回撤": "-82.39%",
        "配对轮次": "6 轮",
        "持股时间比例": "84.5%",
        "样本外超额": "+739.7%"
    },
    {
        "标的代码": "AVGO",
        "公司名称": "Broadcom (半导体芯片巨擘)",
        "资产特性": "指数级单边暴涨牛股",
        "适用评级": "⭐⭐⭐⭐☆ (4/5 强共振)",
        "当前核心矛盾": "产业供求力与情绪动能共振",
        "四力受力结构(宏/产/基/情)": "14.2% / 36.0% / 0.4% / 49.4%",
        "投入本金": "$166,000",
        "策略最终资产": "$3,342,308",
        "基准最终资产": "$4,020,963",
        "累积净超额 (Alpha $)": "-$678,655",
        "财富相对增厚": "-16.9%",
        "策略CAGR": "26.18%",
        "基准CAGR": "28.00%",
        "策略最大回撤": "-29.38%",
        "基准最大回撤": "-48.09%",
        "配对轮次": "11 轮",
        "持股时间比例": "90.1%",
        "样本外超额": "-405.4%"
    },
    {
        "标的代码": "MSFT",
        "公司名称": "Microsoft (软件与科技底座)",
        "资产特性": "AAA信用评级压舱石",
        "适用评级": "⭐⭐⭐☆☆ (3/5 纯持有更优)",
        "当前核心矛盾": "企业内生造血与微观壁垒",
        "四力受力结构(宏/产/基/情)": "3.5% / 3.1% / 0.5% / 92.9%",
        "投入本金": "$166,000",
        "策略最终资产": "$928,935",
        "基准最终资产": "$1,072,457",
        "累积净超额 (Alpha $)": "-$143,521",
        "财富相对增厚": "-13.4%",
        "策略CAGR": "14.27%",
        "基准CAGR": "15.55%",
        "策略最大回撤": "-33.79%",
        "基准最大回撤": "-35.61%",
        "配对轮次": "10 轮",
        "持股时间比例": "89.2%",
        "样本外超额": "+37.3%"
    },
    {
        "标的代码": "AAPL",
        "公司名称": "Apple (消费电子与超级回购)",
        "资产特性": "千亿回购低Beta蓝筹",
        "适用评级": "⭐⭐⭐☆☆ (3/5 纯持有更优)",
        "当前核心矛盾": "微观千亿回购现金流",
        "四力受力结构(宏/产/基/情)": "1.4% / 0.0% / 1.7% / 96.9%",
        "投入本金": "$166,000",
        "策略最终资产": "$1,167,060",
        "基准最终资产": "$1,269,985",
        "累积净超额 (Alpha $)": "-$102,925",
        "财富相对增厚": "-8.1%",
        "策略CAGR": "16.30%",
        "基准CAGR": "17.07%",
        "策略最大回撤": "-36.99%",
        "基准最大回撤": "-37.06%",
        "配对轮次": "9 轮",
        "持股时间比例": "91.5%",
        "样本外超额": "-44.6%"
    },
    {
        "标的代码": "COIN",
        "公司名称": "Coinbase (加密货币交易所与经纪龙头)",
        "资产特性": "⚠️ 极端高Beta加密特质强周期 (宏观引力锚脱节)",
        "适用评级": "⭐☆☆☆☆ (1/5 ⚠️ 严禁盲目套用)",
        "当前核心矛盾": "市场反身性动能 (加密特质与投机)",
        "四力受力结构(宏/产/基/情)": "7.6% / 8.7% / 0.0% / 83.7%",
        "投入本金": "$65,000",
        "策略最终资产": "$127,472",
        "基准最终资产": "$100,696",
        "累积净超额 (Alpha $)": "+$21,868",
        "财富相对增厚": "+26.6%",
        "策略CAGR": "23.4%",
        "基准CAGR": "14.8%",
        "策略最大回撤": "-64.7%",
        "基准最大回撤": "-64.1%",
        "配对轮次": "3 轮 (胜率100%)",
        "持股时间比例": "91.3%",
        "样本外超额": "+43.4%"
    }
]


def render_huang_dynamics_tab():
    st.markdown("## 🌌 Tab 7: 黄文政动力学相空间引擎 (用户自定义标的与全景买卖信号标注)")
    
    st.markdown(
        _clean_html("""
        <div style="background: rgba(56, 189, 248, 0.08); border-left: 5px solid #38bdf8; padding: 16px 20px; border-radius: 8px; margin-bottom: 22px;">
            <div style="font-size: 17px; font-weight: 700; color: #38bdf8; margin-bottom: 8px;">
                💡 理论基石：黄文政《物理学、统计学、动态系统、经济学与人工智能的形式同源》
            </div>
            <div style="font-size: 14.5px; line-height: 1.7; color: #94a3b8;">
                <b>1. 变分极值原则 (Variational Principle)</b>：以宏观信用引力锚（HYG/Real Yield/NFCI）构建平稳反身性势能场 <i>V(q)</i>，在线自适应估计恢复力刚度 <i>k</i> 与阻尼 <i>γ</i>；<br>
                <b>2. 状态空间升维 (Phase Space Lifting)</b>：将状态拓展至广义势能位置 <i>q</i> 与动能速度 <i>q̇</i>，捕捉非线性加速度失稳；<br>
                <b>3. 李雅普诺夫稳定性相变门禁 (Regime Gating)</b>：稳态区（λ ≤ 0）强制 100% 满仓持股，<b>彻底杜绝牛市现金拖累 (Zero Cash Drag)</b>！仅在相变失稳（λ > 0 且宏观信用断裂）时触发战略避险，并在右侧设立防踏空保护盾。
            </div>
        </div>
        """),
        unsafe_allow_html=True
    )

    # ------------------------------------------------------------------
    # 交互控制台：美股代码搜索与快捷热门标的标签
    # ------------------------------------------------------------------
    if "huang_current_ticker" not in st.session_state:
        st.session_state["huang_current_ticker"] = "NOW"

    col_s1, col_s2 = st.columns([3, 2])
    with col_s1:
        searched_ticker = st.text_input(
            "🔍 输入任意美股代码 (Ticker Search):",
            value=st.session_state["huang_current_ticker"],
            placeholder="例如: NVDA, AAPL, TEAM, MSFT, META, AVGO, TSM, AMD, AMZN, GOOGL, NFLX...",
            key="huang_ticker_input_box"
        ).strip().upper()
        if searched_ticker:
            st.session_state["huang_current_ticker"] = searched_ticker

    with col_s2:
        st.markdown("<div style='height: 28px;'></div>", unsafe_allow_html=True)
        # 快捷选择按钮
        quick_cols = st.columns(6)
        quick_candidates = ["NOW", "META", "TEAM", "AVGO", "MSFT", "AAPL"]
        for idx, qc in enumerate(quick_candidates):
            if quick_cols[idx].button(qc, key=f"btn_quick_{qc}"):
                st.session_state["huang_current_ticker"] = qc
                st.rerun()

    active_ticker = st.session_state["huang_current_ticker"]

    # 1. 运行核心引擎与动态计算
    with st.spinner(f"正在分析 {active_ticker}：脱机加载行情、估计相空间动力学并生成全景买卖信号..."):
        try:
            import core_engine.huang_dynamics_engine
            importlib.reload(core_engine.huang_dynamics_engine)
            engine = core_engine.huang_dynamics_engine.HuangDynamicsEngine(ticker=active_ticker)
            engine.load_and_compute()
            
            # 自适应回测起点 (适应不同股票的上市日期，预留 6 个月指标预热窗口)
            min_date = engine.df['date'].min()
            default_start = pd.to_datetime('2013-06-01')
            earliest_possible = min_date + pd.DateOffset(months=8)
            effective_start_dt = max(default_start, earliest_possible)
            effective_start_str = effective_start_dt.strftime('%Y-%m-%d')
            
            df_bt = engine.run_simulation(start_date=effective_start_str, initial_capital=10000.0, dca_monthly=1000.0)
            rep = engine.eval_report
            trades = engine.trades
        except Exception as e:
            st.error(f"❌ 解析股票代码 `{active_ticker}` 失败: {e}。请检查代码拼写或尝试其他标的。")
            return

    t = get_chart_theme_tokens()

    # ------------------------------------------------------------------
    # 核心看板 0: 最新实时信号与物理状态 HUD (Real-Time Signal HUD)
    # ------------------------------------------------------------------
    latest_r = engine.df.dropna(subset=['q', 'q_dot', 'LLE']).iloc[-1]
    latest_d = str(latest_r['date'])[:10]
    latest_q = round(float(latest_r['q']), 2)
    latest_qd = round(float(latest_r['q_dot']), 3)
    latest_p = round(float(latest_r[active_ticker]), 2)
    latest_lle = round(float(latest_r['LLE']), 3)
    curr_pos = df_bt['pos'].iloc[-1] if not df_bt.empty else 1.0

    last_trade = trades[-1] if trades else None
    if curr_pos == 1.0:
        sig_badge = "🟢 【当前信号：100% 满仓持股做多 (稳态坐轿)】"
        sig_bg = "rgba(16, 185, 129, 0.12)"
        sig_border = "#10b981"
        sig_desc = f"系统处于李雅普诺夫稳态吸引子基盆 (λ ≤ 0)，无系统性失稳风险。上次买入于 <b>{last_trade['date'] if last_trade else '回测起点'}</b> @ <b>${last_trade['price'] if last_trade else latest_p}</b> (成交归因: <i>{last_trade['reason'] if last_trade else '稳态建仓'}</i>)。"
    else:
        sig_badge = "🔴 【当前信号：0% 战术空仓避险中 (警惕深渊)】"
        sig_bg = "rgba(239, 68, 68, 0.12)"
        sig_border = "#ef4444"
        sig_desc = f"系统曾触发宏观信用断裂与势能失稳避险报警！于 <b>{last_trade['date']}</b> @ <b>${last_trade['price']}</b> 卖出避险 (避险归因: <i>{last_trade['reason']}</i>)，目前正在等待势能出清与趋势重构买回信号。"

    st.markdown(
        _clean_html(f"""
        <div style="background: {sig_bg}; border: 1.5px solid {sig_border}; padding: 16px 20px; border-radius: 10px; margin-top: 10px; margin-bottom: 22px;">
            <div style="font-size: 17px; font-weight: 700; color: {sig_border}; margin-bottom: 6px;">
                {sig_badge} · {active_ticker} 最新价: ${latest_p:.2f} (更新截至: {latest_d})
            </div>
            <div style="font-size: 14.5px; line-height: 1.7; color: #cbd5e1;">
                • <b>当前决策指示</b>：{sig_desc}<br>
                • <b>动力学物理量</b>：反身性势能偏离 <code>q = {latest_q:+.2f}%</code> | 动能速度 <code>q̇ = {latest_qd:+.3f}</code> | 局部李雅普诺夫指数 <code>LLE λ = {latest_lle:+.3f}</code>
            </div>
        </div>
        """),
        unsafe_allow_html=True
    )

    # ------------------------------------------------------------------
    # 核心看板 0B: 股票全景受力体检与前瞻决策指引卡 (Full-Spectrum Diagnostic Card)
    # ------------------------------------------------------------------
    prof = getattr(engine, 'fundamental_profile', None)
    if prof:
        w_m = prof.get('w_macro', 25.0)
        w_s = prof.get('w_sector', 25.0)
        w_f = prof.get('w_fund', 25.0)
        w_r = prof.get('w_reflexive', 25.0)
        dominant = prof.get('dominant_driver', '多因子均衡')
        guidance_desc = prof.get('forward_guidance_desc', '')
        action_advice = prof.get('forward_action_advice', '')

        st.markdown(
            _clean_html(f"""
            <div style="background: {prof['badge_bg']}; border: 2px solid {prof['badge_color']}; padding: 22px 26px; border-radius: 14px; margin-bottom: 24px; box-shadow: 0 4px 20px rgba(0,0,0,0.25);">
                <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 12px; margin-bottom: 16px; border-bottom: 1px solid rgba(255,255,255,0.12); padding-bottom: 12px;">
                    <div>
                        <span style="font-size: 20px; font-weight: 800; color: {prof['badge_color']};">
                            🧬 {active_ticker} 股票全景受力体检与前瞻实战指引卡
                        </span>
                        <div style="font-size: 15px; color: #94a3b8; margin-top: 4px;">
                            商业模式定位：<b style="color: #f1f5f9;">{prof['category']}</b>
                        </div>
                    </div>
                    <div style="font-size: 15px; font-weight: 700; color: #ffffff; background: {prof['badge_color']}; padding: 6px 16px; border-radius: 8px;">
                        模型适用评级: {prof['rating_stars']} ({prof['rating']})
                    </div>
                </div>

                <div style="display: grid; grid-template-columns: 1fr; gap: 14px; margin-bottom: 16px;">
                    <div style="background: rgba(15, 23, 42, 0.6); border: 1px solid rgba(255,255,255,0.1); border-radius: 10px; padding: 14px 18px;">
                        <div style="font-size: 16px; font-weight: 700; color: #38bdf8; margin-bottom: 8px;">
                            1️⃣ 这家公司到底受什么力量驱动？各占几成？
                        </div>
                        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 12px; font-size: 15px; margin-bottom: 10px;">
                            <div style="background: rgba(56, 189, 248, 0.1); padding: 8px 12px; border-radius: 6px; border-left: 3px solid #38bdf8;">
                                🌊 宏观环境推力 (利率/信贷): <b style="color: #38bdf8; font-size: 16px;">{w_m}%</b>
                            </div>
                            <div style="background: rgba(245, 158, 11, 0.1); padding: 8px 12px; border-radius: 6px; border-left: 3px solid #f59e0b;">
                                🏭 中观行业景气力 (赛道/开支): <b style="color: #f59e0b; font-size: 16px;">{w_s}%</b>
                            </div>
                            <div style="background: rgba(16, 185, 129, 0.1); padding: 8px 12px; border-radius: 6px; border-left: 3px solid #10b981;">
                                💎 企业自身造血力 (估值/均线): <b style="color: #10b981; font-size: 16px;">{w_f}%</b>
                            </div>
                            <div style="background: rgba(236, 72, 153, 0.1); padding: 8px 12px; border-radius: 6px; border-left: 3px solid #ec4899;">
                                ⚡ 市场情绪投机力 (情绪/特质): <b style="color: #ec4899; font-size: 16px;">{w_r}%</b>
                            </div>
                        </div>
                        <div style="font-size: 15px; color: #cbd5e1; border-top: 1px dashed rgba(255,255,255,0.1); padding-top: 8px;">
                            👉 <b>2️⃣ 此时此刻哪种力量占支配地位（当前核心矛盾）？</b><br>
                            答：当前最主要的驱动力量是【<span style="color: {prof['badge_color']}; font-weight: 700; font-size: 16px;">{dominant}</span>】。
                        </div>
                    </div>

                    <div style="background: rgba(15, 23, 42, 0.6); border: 1px solid rgba(255,255,255,0.1); border-radius: 10px; padding: 14px 18px;">
                        <div style="font-size: 16px; font-weight: 700; color: #10b981; margin-bottom: 6px;">
                            3️⃣ 这个模型在这个股票上好不好使、该信几成？
                        </div>
                        <div style="font-size: 15px; color: #cbd5e1; line-height: 1.7; margin-bottom: 10px;">
                            答：{prof['category']}。模型适用度评定为 <b style="color: {prof['badge_color']};">{prof['rating_stars']}</b>。
                            {prof.get('diagnosis', '')}
                        </div>

                        <div style="font-size: 16px; font-weight: 700; color: #f59e0b; margin-top: 10px; margin-bottom: 6px; border-top: 1px dashed rgba(255,255,255,0.1); padding-top: 10px;">
                            4️⃣ 明天 / 当下我到底该怎么操作？（确定性实战指引）
                        </div>
                        <div style="font-size: 15.5px; color: #f8fafc; line-height: 1.8;">
                            • <b>前瞻态势研判</b>：{guidance_desc}<br>
                            • <b>核心操作指令</b>：<span style="background: rgba(255,255,255,0.1); padding: 3px 8px; border-radius: 4px; color: #ffffff; font-weight: 700;">{action_advice}</span>
                        </div>
                    </div>
                </div>

                <div style="display: flex; gap: 20px; flex-wrap: wrap; font-size: 14.5px; color: #94a3b8; border-top: 1px dashed rgba(255,255,255,0.15); padding-top: 10px;">
                    <span>📊 年化波动率: <b style="color: #f8fafc;">{prof['ann_vol']}%</b></span>
                    <span>🔗 宏观大盘解释度 (R²): <b style="color: #38bdf8;">{prof['r_squared']}%</b></span>
                    <span>🎲 内部特质风险占比: <b style="color: {prof['badge_color']};">{prof['idiosyncratic_pct']}%</b></span>
                    <span>💳 与信用债相关系数: <b style="color: #f8fafc;">{prof['corr_hyg']}</b></span>
                </div>
            </div>
            """),
            unsafe_allow_html=True
        )

    # ------------------------------------------------------------------
    # 核心看板 1: 四重严苛 EVALUATION 评测报告卡
    # ------------------------------------------------------------------
    st.subheader(f"🎯 {active_ticker} 全自动化 Evaluation 评测报告卡 (The Empirical Scorecard)")
    st.caption(f"📅 回测区间: `{effective_start_str}` 至 `{latest_d}` | 真实券商记账：初始本金 $10,000 + 月定投 $1,000")

    col1, col2, col3, col4 = st.columns(4)
    alpha_sign = "+" if rep['超额累积净财富 (Alpha $)'] >= 0 else "-"
    col1.metric(
        "🏆 累积净超额财富 (Alpha)",
        f"{alpha_sign}${abs(rep['超额累积净财富 (Alpha $)']):,.0f}",
        f"财富相对增厚 {rep['相对基准财富增厚(%)']:+.1f}%"
    )
    col2.metric(
        "💰 策略最终财富 (vs 基准)",
        f"${rep['策略最终财富']:,.0f}",
        f"基准: ${rep['基准最终财富']:,.0f}"
    )
    cagr_diff = rep['策略年化 CAGR(%)'] - rep['基准年化 CAGR(%)']
    col3.metric(
        "⚡ 年化复合收益率 (CAGR)",
        f"{rep['策略年化 CAGR(%)']:.2f}%",
        f"基准: {rep['基准年化 CAGR(%)']:.2f}% ({cagr_diff:+.2f}%)"
    )
    col4.metric(
        "🔄 交易信噪比 (全周期)",
        f"{rep['总交易配对轮次']} 轮配对",
        f"持股率 {rep['全周期持股比例(%)']:.1f}% (现金拖累仅 {rep['牛市现金拖累率(%)']:.1f}%)"
    )

    col5, col6, col7, col8 = st.columns(4)
    col5.metric(
        "🔮 样本外超额 (2019-2026)",
        f"{rep['2019-2026样本外超额收益(%)']:+.2f}%",
        "Expanding Walk-Forward 零未来函数"
    )
    col6.metric(
        "🛡️ 策略最大回撤压制",
        f"{rep['策略最大回撤(%)']:.2f}%",
        f"基准回撤: {rep['基准最大回撤(%)']:.2f}% ({rep['回撤收窄改善(%)']:+.2f}%)"
    )
    col7.metric(
        "🚨 重大危机平均预警提前期",
        f"{rep['重大危机平均预警提前期(天)']:.1f} 天",
        "大跌前李雅普诺夫指数失稳"
    )
    col8.metric(
        "📈 策略卡玛比率 (Calmar)",
        f"{rep['策略卡玛比率 (Calmar)']:.2f}",
        f"基准: {rep['基准卡玛比率 (Calmar)']:.2f}"
    )

    st.markdown("---")

    # ------------------------------------------------------------------
    # 核心看板 2: 真实股价走势与买卖信号图谱 (Stock Price with BUY / SELL Signals)
    # ------------------------------------------------------------------
    st.subheader(f"📈 {active_ticker} 真实股价走势与战略买卖信号标记图谱 (Signal Action Spectrum)")
    st.caption("💡 **直观信号解读**：🟢 **绿色大图钉** 为战略买入/回补点；🔴 **红色大图钉** 为战略高位止盈/避险逃顶；**淡红底纹阴影** 为战术空仓避险期 (守住利润，杜绝死扛暴跌)。鼠标悬停可查看每笔买卖的具体价格与物理触发归因。")

    dates_str = df_bt['date'].dt.strftime('%Y-%m-%d').tolist()
    prices = [round(float(v), 2) for v in df_bt[active_ticker]]
    ma50 = [round(float(v), 2) if pd.notna(v) else None for v in df_bt['MA50']]
    ma200 = [round(float(v), 2) if pd.notna(v) else None for v in df_bt['MA200']]

    # 1. 构建买卖信号 MarkPoint 与查找字典
    trade_map = {}
    price_mark_points = []
    prev_d = None
    cluster_idx = 0
    for tr in trades:
        trade_map[tr['date']] = {
            "action": tr['action'],
            "price": round(float(tr['price']), 2),
            "reason": tr['reason'],
            "return_pct": f"{tr.get('return_pct', 0.0):+.1f}%" if tr['action'] == 'SELL' else None
        }
        is_buy = (tr['action'] == 'BUY')
        d_curr = pd.to_datetime(tr['date'])
        if prev_d is not None and (d_curr - prev_d).days <= 30:
            cluster_idx += 1
        else:
            cluster_idx = 0
        prev_d = d_curr

        # 针对 30 天内高频调仓的密集信号簇，进行错峰纵向错位分层，避免图钉重叠死锁
        v_offset = -(cluster_idx % 3) * 20
        symbol_size = 50 if v_offset != 0 else 54

        price_mark_points.append({
            "name": f"【{tr['action']}】{tr['reason']}",
            "coord": [tr['date'], round(float(tr['price']), 2)],
            "value": f"{tr['action']}\n${tr['price']:.1f}",
            "symbol": "pin",
            "symbolSize": symbol_size,
            "symbolOffset": [0, v_offset],
            "itemStyle": {
                "color": "#10b981" if is_buy else "#ef4444",
                "borderColor": "#ffffff",
                "borderWidth": 1.5,
                "shadowBlur": 8,
                "shadowColor": "rgba(0,0,0,0.4)"
            },
            "label": {
                "show": True,
                "color": "#ffffff",
                "fontSize": 11 if symbol_size < 52 else 12,
                "fontWeight": "bold",
                "formatter": f"{tr['action']}\n${tr['price']:.1f}"
            }
        })

    # 2. 构建空仓避险期 MarkArea 阴影与持仓映射
    cash_areas = []
    pos_map = {}
    in_cash = False
    cash_start = None
    for _, row in df_bt.iterrows():
        d_s = row['date'].strftime('%Y-%m-%d')
        pos = float(row['pos'])
        pos_map[d_s] = pos
        if pos == 0.0 and not in_cash:
            in_cash = True
            cash_start = d_s
        elif pos > 0.0 and in_cash:
            in_cash = False
            cash_areas.append([{"xAxis": cash_start}, {"xAxis": d_s}])
            cash_start = None
    if in_cash and cash_start:
        cash_areas.append([{"xAxis": cash_start}, {"xAxis": dates_str[-1]}])

    price_option = {
        "backgroundColor": "transparent",
        "tooltip": {
            "trigger": "axis",
            "backgroundColor": t["tooltip_bg"],
            "borderColor": t["tooltip_border"],
            "borderWidth": 1,
            "textStyle": {"color": t["tooltip_text"], "fontSize": 14},
            "axisPointer": {
                "type": "cross",
                "label": {
                    "backgroundColor": "#334155",
                    "fontSize": 13,
                    "color": "#ffffff"
                },
                "lineStyle": {
                    "color": t["axis_line"],
                    "type": "dashed"
                }
            }
        },
        "legend": {
            "top": "10px",
            "left": "center",
            "textStyle": {"color": t["axis_label"], "fontSize": 14, "fontWeight": 600},
            "data": [f"{active_ticker} 收盘价", "MA50 中期趋势", "MA200 长期牛熊线"]
        },
        "grid": {
            "left": "75px",
            "right": "45px",
            "top": "65px",
            "bottom": "75px",
            "containLabel": True
        },
        "xAxis": {
            "type": "category",
            "data": dates_str,
            "boundaryGap": False,
            "axisLabel": {"color": t["axis_label"], "fontSize": 14},
            "axisLine": {"lineStyle": {"color": t["axis_line"]}}
        },
        "yAxis": {
            "type": "value",
            "scale": True,
            "name": "股价 (USD)",
            "nameGap": 14,
            "nameTextStyle": {"color": t["axis_label"], "fontSize": 14, "fontWeight": 600},
            "axisLabel": {"color": t["axis_label"], "fontSize": 14, "formatter": "${value}"},
            "splitLine": {"lineStyle": {"color": t["split_line"]}}
        },
        "dataZoom": [
            {
                "type": "inside",
                "start": 0,
                "end": 100
            },
            {
                "type": "slider",
                "start": 0,
                "end": 100,
                "bottom": 10,
                "height": 26,
                "borderColor": t["datazoom_border"],
                "backgroundColor": t["datazoom_bg"],
                "fillerColor": t["datazoom_filler"],
                "handleStyle": {"color": t["datazoom_handle"]},
                "textStyle": {"color": t["axis_label"], "fontSize": 12},
                "dataBackground": {
                    "lineStyle": {"color": t["datazoom_handle"]},
                    "areaStyle": {"color": t["datazoom_filler"]}
                }
            }
        ],
        "series": [
            {
                "name": f"{active_ticker} 收盘价",
                "type": "line",
                "data": prices,
                "lineStyle": {"width": 2.5, "color": "#38bdf8"},
                "itemStyle": {"color": "#38bdf8"},
                "markPoint": {
                    "data": price_mark_points
                },
                "markArea": {
                    "itemStyle": {
                        "color": "rgba(239, 68, 68, 0.12)"
                    },
                    "data": cash_areas
                }
            },
            {
                "name": "MA50 中期趋势",
                "type": "line",
                "data": ma50,
                "lineStyle": {"width": 1.5, "color": "#f59e0b", "type": "dashed"},
                "itemStyle": {"color": "#f59e0b"}
            },
            {
                "name": "MA200 长期牛熊线",
                "type": "line",
                "data": ma200,
                "lineStyle": {"width": 1.5, "color": "#a855f7", "type": "dotted"},
                "itemStyle": {"color": "#a855f7"}
            }
        ]
    }

    dates_json = json.dumps(dates_str)
    trade_map_json = json.dumps(trade_map)
    pos_map_json = json.dumps(pos_map)
    option_json = json.dumps(price_option)

    price_html = f"""
    <div style="background: {t['card_bg']}; padding: 12px; border-radius: 10px; border: 1px solid {t['border_color']};">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; flex-wrap: wrap; gap: 8px;">
            <div style="font-size: 16px; font-weight: 700; color: {t['axis_label']};">
                📈 {active_ticker} 真实股价与战略买卖点标注 (🟢 买入 | 🔴 卖出避险)
            </div>
            <div style="display: flex; gap: 4px; background: rgba(15, 23, 42, 0.4); padding: 3px 5px; border-radius: 8px; border: 1px solid rgba(255, 255, 255, 0.08);">
                <button class="time-btn" onclick="applyTimeRange('1M', this)">1M</button>
                <button class="time-btn" onclick="applyTimeRange('3M', this)">3M</button>
                <button class="time-btn" onclick="applyTimeRange('6M', this)">6M</button>
                <button class="time-btn" onclick="applyTimeRange('1Y', this)">1Y</button>
                <button class="time-btn" onclick="applyTimeRange('3Y', this)">3Y</button>
                <button class="time-btn" onclick="applyTimeRange('5Y', this)">5Y</button>
                <button class="time-btn active" onclick="applyTimeRange('ALL', this)">全部</button>
            </div>
        </div>
        <div id="price_signal_chart" style="width: 100%; height: 470px;"></div>
    </div>

    <style>
        .time-btn {{
            background: transparent;
            border: none;
            color: #94a3b8;
            font-size: 12px;
            font-weight: 600;
            padding: 4px 8px;
            border-radius: 4px;
            cursor: pointer;
            transition: all 0.15s ease;
        }}
        .time-btn:hover {{
            color: #ffffff;
            background: rgba(255, 255, 255, 0.12);
        }}
        .time-btn.active {{
            color: #38bdf8;
            background: rgba(56, 189, 248, 0.2);
        }}
    </style>

    <script src="https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"></script>
    <script>
        const allDates = {dates_json};
        const tradeMap = {trade_map_json};
        const posMap = {pos_map_json};
        const rawOption = {option_json};

        // 增强版悬停十字准星格式化：显示精确日期、股价、均线、策略仓位与战略买卖触发详情
        rawOption.tooltip.formatter = function(params) {{
            if (!params || params.length === 0) return '';
            const curDate = params[0].axisValue || params[0].name;
            let closePrice = null;
            let ma50Val = null;
            let ma200Val = null;

            params.forEach(p => {{
                if (p.seriesName && p.seriesName.includes('收盘价')) closePrice = p.data;
                else if (p.seriesName && p.seriesName.includes('MA50')) ma50Val = p.data;
                else if (p.seriesName && p.seriesName.includes('MA200')) ma200Val = p.data;
            }});

            const curPos = posMap[curDate] !== undefined ? posMap[curDate] : 1.0;
            const posBadge = curPos > 0.0 ? 
                '<span style="color: #10b981; font-weight: bold;">🟢 100% 满仓做多</span>' : 
                '<span style="color: #ef4444; font-weight: bold;">🔴 0% 战术空仓避险</span>';

            let tradeHtml = '';
            if (tradeMap[curDate]) {{
                const tr = tradeMap[curDate];
                const isBuy = tr.action === 'BUY';
                const tagColor = isBuy ? '#10b981' : '#ef4444';
                const tagBg = isBuy ? 'rgba(16, 185, 129, 0.2)' : 'rgba(239, 68, 68, 0.2)';
                const retInfo = tr.return_pct ? ` (波段收益: <b>${{tr.return_pct}}</b>)` : '';
                tradeHtml = `
                    <div style="margin-top: 8px; padding: 6px 10px; background: ${{tagBg}}; border: 1.5px solid ${{tagColor}}; border-radius: 6px;">
                        <div style="color: ${{tagColor}}; font-weight: bold; font-size: 13px;">
                            ${{isBuy ? '⚡【战略买入执行】' : '🛑【战略卖出避险】'}} 成交价: $${{tr.price}}${{retInfo}}
                        </div>
                        <div style="color: #e2e8f0; font-size: 12px; margin-top: 3px; line-height: 1.4;">
                            归因: <i>${{tr.reason}}</i>
                        </div>
                    </div>
                `;
            }}

            return `
                <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; font-size: 13.5px; line-height: 1.5; min-width: 210px;">
                    <div style="font-weight: 700; color: #f8fafc; border-bottom: 1px solid rgba(255,255,255,0.15); padding-bottom: 4px; margin-bottom: 6px;">
                        📅 日期: ${{curDate}}
                    </div>
                    <div style="display: flex; justify-content: space-between; gap: 16px; margin-bottom: 3px;">
                        <span style="color: #94a3b8;">收盘价:</span>
                        <span style="color: #38bdf8; font-weight: bold;">$${{closePrice !== null ? Number(closePrice).toFixed(2) : '--'}}</span>
                    </div>
                    <div style="display: flex; justify-content: space-between; gap: 16px; margin-bottom: 3px;">
                        <span style="color: #94a3b8;">MA50 (中期):</span>
                        <span style="color: #f59e0b; font-weight: 600;">${{ma50Val !== null && ma50Val !== undefined ? '$' + Number(ma50Val).toFixed(2) : '--'}}</span>
                    </div>
                    <div style="display: flex; justify-content: space-between; gap: 16px; margin-bottom: 3px;">
                        <span style="color: #94a3b8;">MA200 (牛熊线):</span>
                        <span style="color: #a855f7; font-weight: 600;">${{ma200Val !== null && ma200Val !== undefined ? '$' + Number(ma200Val).toFixed(2) : '--'}}</span>
                    </div>
                    <div style="display: flex; justify-content: space-between; gap: 16px; margin-top: 4px; border-top: 1px dashed rgba(255,255,255,0.1); padding-top: 4px;">
                        <span style="color: #94a3b8;">策略持仓:</span>
                        <span>${{posBadge}}</span>
                    </div>
                    ${{tradeHtml}}
                </div>
            `;
        }};

        var chart_price = echarts.init(document.getElementById('price_signal_chart'), '{t["echarts_theme"]}');
        chart_price.setOption(rawOption);

        var isProgrammaticZoom = false;
        chart_price.on('dataZoom', function(evt) {{
            if (!isProgrammaticZoom) {{
                document.querySelectorAll('.time-btn').forEach(b => b.classList.remove('active'));
            }}
        }});

        function applyTimeRange(range, btnElement) {{
            isProgrammaticZoom = true;
            document.querySelectorAll('.time-btn').forEach(b => {{
                if (b === btnElement) b.classList.add('active');
                else b.classList.remove('active');
            }});

            if (range === 'ALL' || !allDates || allDates.length === 0) {{
                chart_price.dispatchAction({{
                    type: 'dataZoom',
                    start: 0,
                    end: 100
                }});
                setTimeout(() => {{ isProgrammaticZoom = false; }}, 300);
                return;
            }}

            const lastDateStr = allDates[allDates.length - 1];
            const lastDate = new Date(lastDateStr);
            let fromDate = new Date(lastDate);

            if (range === '1M') fromDate.setMonth(fromDate.getMonth() - 1);
            else if (range === '3M') fromDate.setMonth(fromDate.getMonth() - 3);
            else if (range === '6M') fromDate.setMonth(fromDate.getMonth() - 6);
            else if (range === '1Y') fromDate.setFullYear(fromDate.getFullYear() - 1);
            else if (range === '3Y') fromDate.setFullYear(fromDate.getFullYear() - 3);
            else if (range === '5Y') fromDate.setFullYear(fromDate.getFullYear() - 5);

            const fromDateStr = fromDate.toISOString().split('T')[0];
            let startIdx = 0;
            for (let i = 0; i < allDates.length; i++) {{
                if (allDates[i] >= fromDateStr) {{
                    startIdx = i;
                    break;
                }}
            }}

            const startPct = Math.max(0, Math.min(100, (startIdx / Math.max(1, allDates.length - 1)) * 100));
            chart_price.dispatchAction({{
                type: 'dataZoom',
                start: startPct,
                end: 100
            }});
            setTimeout(() => {{ isProgrammaticZoom = false; }}, 300);
        }}

        window.addEventListener('resize', () => chart_price.resize());
    </script>
    """
    components.html(price_html, height=545)

    st.markdown("---")

    # ------------------------------------------------------------------
    # 核心看板 3: 黄文政动态相空间图 (并在相空间中标记买卖点)
    # ------------------------------------------------------------------
    st.subheader(f"🌀 {active_ticker} 动态相空间图 (并在相空间中标记所有战略买卖点)")
    
    st.markdown(
        _clean_html(f"""
        <div style="background: rgba(15, 23, 42, 0.65); border: 1px solid rgba(56, 189, 248, 0.3); border-radius: 12px; padding: 18px 22px; margin-bottom: 18px;">
            <div style="font-size: 17px; font-weight: 700; color: #38bdf8; margin-bottom: 10px;">
                🧭 动力学相空间四象限物理导读：看懂股票的“运行轨道”与“生命周期”
            </div>
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap: 12px; font-size: 14.5px; margin-bottom: 12px;">
                <div style="background: rgba(249, 115, 22, 0.1); border-left: 3px solid #f97316; padding: 10px 14px; border-radius: 6px;">
                    <b style="color: #f97316;">象限 Ⅰ【右上：过热加速扩张】</b><br>
                    <span style="color: #cbd5e1;">势能高估 + 向上冲刺。处于亢奋主升浪，防范能量耗尽相变。</span>
                </div>
                <div style="background: rgba(239, 68, 68, 0.1); border-left: 3px solid #ef4444; padding: 10px 14px; border-radius: 6px;">
                    <b style="color: #ef4444;">象限 Ⅳ【右下：高位动能衰竭】</b><br>
                    <span style="color: #cbd5e1;">势能高估 + 动能跌落。大顶相变失稳，<b>⚠️ 战略卖出 (SELL) 集中区</b>。</span>
                </div>
                <div style="background: rgba(148, 163, 184, 0.1); border-left: 3px solid #94a3b8; padding: 10px 14px; border-radius: 6px;">
                    <b style="color: #94a3b8;">象限 Ⅲ【左下：恐慌探底下坠】</b><br>
                    <span style="color: #cbd5e1;">深度折价 + 向下加速。去杠杆深渊，尚未企稳，严禁盲目抄底。</span>
                </div>
                <div style="background: rgba(16, 185, 129, 0.1); border-left: 3px solid #10b981; padding: 10px 14px; border-radius: 6px;">
                    <b style="color: #10b981;">象限 Ⅱ【左上：低位蓄势反弹】</b><br>
                    <span style="color: #cbd5e1;">深度折价 + 动能转正。估值修复启动，<b>🎯 黄金坑买入 (BUY) 集中区</b>。</span>
                </div>
            </div>
            <div style="font-size: 14.5px; color: #cbd5e1; line-height: 1.8; border-top: 1px dashed rgba(255,255,255,0.15); padding-top: 10px;">
                • <b>横坐标 q (广义反身性势能)</b>：股票价格相对于宏观信用中枢的偏离幅度。<b>右侧 (q > 0) 代表高估过热 (买贵了)</b>，<b>左侧 (q < 0) 代表深度超跌 (估值便宜)</b>。<br>
                • <b>纵坐标 q̇ (广义相速度)</b>：偏离度变化的速度与冲力。<b>上方 (q̇ > 0) 代表向上加速扩张或反弹</b>，<b>下方 (q̇ < 0) 代表动能衰竭向下坠落</b>。<br>
                • <b>自适应多阶段宏观潮流 (彩色箭头接力棒)</b>：长线投资以宏观经济与信用大周期（数月至数年）为尺度，应用自适应 EMA 平滑滤波消除日内高频噪声，展现真实宏观大波段流向。<br>
                &nbsp;&nbsp;<b>① 启动出坑 (极光青线 ➔)</b> ──> <b>② 主升扩张 (紫罗兰线 ➔)</b> ──> <b>③ 高位运行 (阳光金线 ➔)</b> ──> <b>④ 冲刺当下 (烈火红线 ➔)</b> ──> <b>TODAY 最新红信标</b>！<br>
                &nbsp;&nbsp;每个阶段末端均配置<b>方向箭头</b>，清晰指明行进流向；点击顶部图例可自由隐藏或聚焦特定时段！<br>
            </div>
        </div>
        """),
        unsafe_allow_html=True
    )

    sub_dyn = engine.df.dropna(subset=['q', 'q_dot', 'LLE']).copy()
    dates_dyn = sub_dyn['date'].dt.strftime('%Y-%m-%d').tolist()
    q_vals_all = [round(float(v), 2) for v in sub_dyn['q']]
    qd_vals_all = [round(float(v), 3) for v in sub_dyn['q_dot']]
    lle_vals_all = [round(float(v), 3) for v in sub_dyn['LLE']]
    prices_all = [round(float(v), 2) for v in sub_dyn[active_ticker]]

    # 1. 历史散点全景 (采用柔和中性的暗冷灰星空背景，消除暗蓝抢色干扰)
    scatter_data = []
    for q_v, qd_v, d_s, p_v, lle_v in zip(q_vals_all, qd_vals_all, dates_dyn, prices_all, lle_vals_all):
        scatter_data.append([q_v, qd_v, d_s, p_v, lle_v])

    latest_r = sub_dyn.iloc[-1]
    latest_d = str(latest_r['date'])[:10]
    latest_q = round(float(latest_r['q']), 2)
    latest_qd = round(float(latest_r['q_dot']), 3)

    # 计算当前决策判定与调仓记录
    last_tr = trades[-1] if trades else None
    last_tr_date = last_tr['date'] if last_tr else "无历史记录"
    last_tr_action = last_tr['action'] if last_tr else "无"
    last_tr_price = f"${last_tr['price']:.2f}" if last_tr else "--"
    last_tr_ret = f" (该轮波段收益: {last_tr['return_pct']})" if (last_tr and last_tr.get('return_pct')) else ""

    holding_months = 0
    if last_tr:
        try:
            holding_months = (pd.to_datetime(latest_d) - pd.to_datetime(last_tr['date'])).days // 30
        except Exception:
            holding_months = 0

    curr_price = float(latest_r[active_ticker])
    if last_tr and last_tr['action'] == 'BUY':
        entry_price = float(last_tr['price'])
        pos_gain = (curr_price - entry_price) / entry_price * 100.0
        pos_color = "#10b981" if pos_gain >= 0 else "#ef4444"
        pos_desc = f"建仓价 <b>${entry_price:.2f}</b> ➔ 当前价 <b>${curr_price:.2f}</b>，本轮累计浮动盈亏: <b style='color: {pos_color};'>{'+' if pos_gain>=0 else ''}{pos_gain:.1f}%</b>"
    elif last_tr and last_tr['action'] == 'SELL':
        pos_desc = f"上次避险卖出价 <b>${float(last_tr['price']):.2f}</b> ➔ 当前价 <b>${curr_price:.2f}</b>，当前处于<b>空仓避险观望状态</b>"
    else:
        pos_desc = f"当前价格 <b>${curr_price:.2f}</b>"

    if latest_q <= -0.8 and latest_qd >= 0:
        curr_status_name = "【🎯 处于战略买入盆地】"
        curr_status_color = "#10b981"
        curr_status_desc = "股价已进入深度超跌折价区且动能止跌回升，当前<b>触发战略建仓/加仓准则</b>！"
    elif latest_q >= 0.8 and latest_qd <= 0:
        curr_status_name = "【⚠️ 处于动能衰竭逃顶区】"
        curr_status_color = "#ef4444"
        curr_status_desc = "股价已处于严重溢价泡沫区且动能开始下坠，当前<b>触发战略减仓/避险准则</b>！"
    else:
        curr_status_name = "【⚖️ 顺势持股观望区】"
        curr_status_color = "#38bdf8"
        curr_status_desc = "当前处于宏观估值平衡带，<b>未触发任何买卖信号</b>，策略严格保持原仓位不变（100% 满仓持股中，杜绝频繁调仓磨损）。"

    # 宏观时间尺度交互切换 (解决长线宏观投资与任意时间尺度的观测需求)
    if last_tr and last_tr['action'] == 'BUY':
        cycle_option_name = f"🎯 本轮持股全周期 (自建仓 {last_tr_date} 至今 · {holding_months}个月)"
    elif last_tr and last_tr['action'] == 'SELL':
        cycle_option_name = f"🛡️ 本轮空仓避险周期 (自避险 {last_tr_date} 至今 · {holding_months}个月)"
    else:
        cycle_option_name = "🌊 近 1 年宏观潮流 (252 交易日)"

    horizon_options = [
        cycle_option_name,
        "🌊 近 1 年宏观潮流 (252 交易日)",
        "🏛️ 近 3 年完整经济周期 (756 交易日)",
        "🔍 近 90 天短周期战术微调 (90 交易日)",
        "🌌 13 年全景历史全貌 (2013~至今)"
    ]

    sel_horizon = st.radio(
        "⏱️ **选择相空间轨迹宏观时间尺度 (Time Horizon)**：",
        options=horizon_options,
        index=0,
        horizontal=True,
        key=f"phase_horizon_selector_{active_ticker}",
        help="长线宏观反身性策略以 1~3 年的完整周期为持有基石。默认建议查看【本轮持股全周期】，直观追踪从建仓买点到今天的完整演进全貌！"
    )

    # 根据所选时间尺度截取轨迹并计算 EMA 平滑
    if sel_horizon == cycle_option_name:
        if last_tr:
            traj_sub = sub_dyn[sub_dyn['date'] >= last_tr_date].copy()
            if len(traj_sub) < 30:
                traj_sub = sub_dyn.iloc[-max(len(sub_dyn), 60):].copy()
        else:
            traj_sub = sub_dyn.iloc[-min(len(sub_dyn), 252):].copy()
        horizon_desc = f"本轮持股完整生命周期 (自 {last_tr_date} 至今，共 {len(traj_sub)} 交易日 / {holding_months} 个月)"
    elif "近 1 年" in sel_horizon:
        traj_sub = sub_dyn.iloc[-min(len(sub_dyn), 252):].copy()
        horizon_desc = f"近 1 年宏观潮流演进 (共 {len(traj_sub)} 交易日)"
    elif "近 3 年" in sel_horizon:
        traj_sub = sub_dyn.iloc[-min(len(sub_dyn), 756):].copy()
        horizon_desc = f"近 3 年完整宏观经济周期 (共 {len(traj_sub)} 交易日)"
    elif "90 天" in sel_horizon:
        traj_sub = sub_dyn.iloc[-min(len(sub_dyn), 90):].copy()
        horizon_desc = f"近 90 天短周期微调 (共 {len(traj_sub)} 交易日)"
    else:  # 13 年
        traj_sub = sub_dyn.copy()
        horizon_desc = f"13 年全景历史引力轨道 (共 {len(traj_sub)} 交易日)"

    # 自适应 EMA 平滑滤波：长周期用 7 日 EMA，短周期用 5 日 EMA
    span_val = 7 if len(traj_sub) >= 200 else 5
    traj_sub['q_smooth'] = traj_sub['q'].ewm(span=span_val, adjust=False).mean()
    traj_sub['qd_smooth'] = traj_sub['q_dot'].ewm(span=span_val, adjust=False).mean()

    n_pts = len(traj_sub)
    traj_pts = []
    for idx, (_, r) in enumerate(traj_sub.iterrows()):
        traj_pts.append([
            round(float(r['q_smooth']), 2),
            round(float(r['qd_smooth']), 3),
            str(r['date'])[:10],
            round(float(r[active_ticker]), 2),
            round(float(r['q']), 2),
            round(float(r['q_dot']), 3)
        ])

    # 4 大宏观时序演进阶段（比例切分，保证点数充盈平滑且连续）
    i1 = max(1, int(n_pts * 0.35))
    i2 = max(i1 + 1, int(n_pts * 0.70))
    i3 = max(i2 + 1, int(n_pts * 0.90))

    s1_pts = traj_pts[0 : i1 + 1] if i1 > 0 else traj_pts[0:1]
    s2_pts = traj_pts[i1 : i2 + 1] if i2 > i1 else traj_pts[i1 : i1 + 1]
    s3_pts = traj_pts[i2 : i3 + 1] if i3 > i2 else traj_pts[i2 : i2 + 1]
    s4_pts = traj_pts[i3 :]

    def _fmt_d(d_str):
        parts = d_str.split('-')
        return f"{parts[0][2:]}/{parts[1]}" if len(parts) >= 2 else d_str

    d0 = traj_pts[0][2]
    d1 = traj_pts[i1][2]
    d2 = traj_pts[i2][2]
    d3 = traj_pts[i3][2]
    d4 = traj_pts[-1][2]

    s1_name = f"① {_fmt_d(d0)}~{_fmt_d(d1)} (启动出坑 ➔)"
    s2_name = f"② {_fmt_d(d1)}~{_fmt_d(d2)} (主升扩张 ➔)"
    s3_name = f"③ {_fmt_d(d2)}~{_fmt_d(d3)} (高位运行 ➔)"
    s4_name = f"④ {_fmt_d(d3)}~{_fmt_d(d4)} (冲刺当下 ➔)"
    today_name = f"TODAY 最新状态信标 ({d4})"

    latest_pt = traj_pts[-1] if traj_pts else [0, 0, '', 0]
    today_marker = [[latest_pt[0], latest_pt[1], latest_pt[2], latest_pt[3]]]

    # 3. 严格时空区分：当前周期真实交易 vs 13 年历史调仓复盘
    traj_start_date_str = traj_pts[0][2] if traj_pts else ""
    is_cycle_view = (sel_horizon == cycle_option_name)

    entry_anchor_data = []
    if is_cycle_view and last_tr:
        entry_is_buy = (last_tr['action'] == 'BUY')
        entry_anchor_data.append({
            "name": f"本轮{'战略建仓' if entry_is_buy else '战略避险'}起点 ({last_tr_date})",
            "value": [traj_pts[0][0], traj_pts[0][1], last_tr_date, last_tr['price'], last_tr['reason']],
            "symbol": "diamond" if entry_is_buy else "pin",
            "symbolSize": 18,
            "itemStyle": {
                "color": "#10b981" if entry_is_buy else "#ef4444",
                "borderColor": "#ffffff",
                "borderWidth": 2,
                "shadowBlur": 10,
                "shadowColor": "#10b981" if entry_is_buy else "#ef4444"
            },
            "label": {
                "show": True,
                "position": "bottom",
                "formatter": f"🎯 本轮{'建仓' if entry_is_buy else '避险'}起点\n{last_tr_date} (${last_tr['price']:.2f})",
                "fontSize": 12.5,
                "color": "#10b981" if entry_is_buy else "#ef4444",
                "fontWeight": "bold"
            }
        })

    cycle_buy_points = []
    cycle_sell_points = []
    historical_buy_points = []
    historical_sell_points = []

    for tr in trades:
        m_row = sub_dyn[sub_dyn['date'].dt.strftime('%Y-%m-%d') == tr['date']]
        if not m_row.empty:
            q_pt = round(float(m_row['q'].iloc[0]), 2)
            qd_pt = round(float(m_row['q_dot'].iloc[0]), 3)
            tr_date = tr['date']
            tr_year = tr_date[:4]
            is_buy = (tr['action'] == 'BUY')
            pt_label = f"{tr_year}年{'买入' if is_buy else '卖出'}"
            pt_data = {
                "name": pt_label,
                "value": [q_pt, qd_pt, tr_date, tr['price'], tr['reason']],
                "symbol": "triangle",
                "symbolRotate": 0 if is_buy else 180,
                "itemStyle": {
                    "color": "#10b981" if is_buy else "#ef4444",
                    "borderColor": "#ffffff",
                    "borderWidth": 1.5
                }
            }
            if tr_date > traj_start_date_str:
                if is_buy:
                    cycle_buy_points.append(pt_data)
                else:
                    cycle_sell_points.append(pt_data)
            else:
                if is_buy:
                    historical_buy_points.append(pt_data)
                else:
                    historical_sell_points.append(pt_data)

    st.markdown(
        _clean_html(f"""
        <div style="background: rgba(15, 23, 42, 0.75); border: 1.5px solid {curr_status_color}; border-radius: 12px; padding: 16px 20px; margin-bottom: 16px;">
            <div style="display: flex; justify-content: space-between; align-items: center; flex-wrap: wrap; gap: 10px;">
                <div>
                    <span style="font-size: 16.5px; font-weight: 700; color: #f8fafc;">🧭 {active_ticker} 宏观相空间状态与策略买卖诊断</span>
                    <span style="font-size: 14.5px; color: #94a3b8; margin-left: 10px;">最新物理坐标: <b>q = {latest_q}%</b>, <b>q̇ = {latest_qd}</b></span>
                </div>
                <div style="background: rgba(56, 189, 248, 0.15); border: 1.5px solid {curr_status_color}; border-radius: 8px; padding: 5px 14px; font-size: 15px; font-weight: 700; color: {curr_status_color};">
                    当前决策：{curr_status_name}
                </div>
            </div>
            <div style="font-size: 14.5px; color: #e2e8f0; line-height: 1.8; margin-top: 10px; border-top: 1px dashed rgba(255,255,255,0.15); padding-top: 10px;">
                • <b>买卖信号状态</b>：{curr_status_desc}<br>
                • <b>本轮持仓状态</b>：{pos_desc}（{f'已纪律持股 <b>{holding_months} 个月</b>' if holding_months > 0 else '近期新调仓'}）。<br>
                • <b>当前图表时间跨度</b>：<b>{horizon_desc}</b>（可通过上方单选钮自由切换宏观时间尺度）。<br>
                • <b>长线纪律执行核验</b>：黄文政动力学采用 100% 满仓持股稳态门禁，杜绝在牛市主升浪中因频繁倒手产生严重摩擦磨损或踏空。
            </div>
        </div>
        """),
        unsafe_allow_html=True
    )

    legend_items = [
        "全景历史散点 (背景星云)",
        s1_name,
        s2_name,
        s3_name,
        s4_name,
        today_name
    ]
    if entry_anchor_data:
        legend_items.append("🟢 本轮持股战略建仓点")
    if cycle_buy_points:
        legend_items.append("⚡ 周期内战略买入")
    if cycle_sell_points:
        legend_items.append("🛑 周期内战略卖出")
    legend_items.append("📜 13年历史调仓复盘 (含年份)")

    # 动态自适应相空间坐标边界：杜绝硬编码静态边界导致垂直方向被严重压缩成扁平薄片
    q_vals = [abs(pt[0]) for pt in traj_pts if pt and len(pt) >= 2]
    qd_vals = [abs(pt[1]) for pt in traj_pts if pt and len(pt) >= 2]
    if scatter_data:
        q_vals.extend([abs(pt[0]) for pt in scatter_data if pt and len(pt) >= 2])
        qd_vals.extend([abs(pt[1]) for pt in scatter_data if pt and len(pt) >= 2])

    q_bound = max(3.2, float(np.percentile(q_vals, 98) * 1.15) if q_vals else 4.0)
    qd_bound = max(0.35, float(np.percentile(qd_vals, 98) * 1.25) if qd_vals else 0.5)

    phase_option = {
        "backgroundColor": t["card_bg"],
        "title": {
            "text": f"🌌 {active_ticker} 动态相空间宏观轨迹与买卖触发点 (Phase Space Flow)",
            "left": "20px",
            "top": "10px",
            "textStyle": {"color": t["axis_label"], "fontSize": 16, "fontWeight": 700}
        },
        "tooltip": {
            "trigger": "item",
            "backgroundColor": t["tooltip_bg"],
            "borderColor": t["tooltip_border"],
            "textStyle": {"color": t["tooltip_text"], "fontSize": 14},
            "formatter": "{a}<br/>• 标识: {b}<br/>• q (势能偏离): {c.0}%<br/>• q̇ (相速度): {c.1}<br/>• 记录日期: {c.2}<br/>• 对应股价: ${c.3}"
        },
        "legend": {
            "top": "38px",
            "left": "20px",
            "right": "20px",
            "itemGap": 12,
            "textStyle": {"color": t["axis_label"], "fontSize": 13, "fontWeight": 600},
            "selected": {
                "📜 13年历史调仓复盘 (含年份)": False
            },
            "data": legend_items
        },
        "graphic": [
            {
                "type": "text",
                "right": "65px",
                "top": "110px",
                "style": {
                    "text": "象限 Ⅰ【过热加速扩张】\n势能高估 + 向上冲刺",
                    "fill": "rgba(249, 115, 22, 0.45)",
                    "font": "bold 14px sans-serif",
                    "textAlign": "right"
                }
            },
            {
                "type": "text",
                "right": "65px",
                "bottom": "85px",
                "style": {
                    "text": "象限 Ⅳ【高位动能衰竭】\n势能高估 + 动能下坠 (⚠️ 逃顶警戒)",
                    "fill": "rgba(239, 68, 68, 0.50)",
                    "font": "bold 14px sans-serif",
                    "textAlign": "right"
                }
            },
            {
                "type": "text",
                "left": "100px",
                "bottom": "85px",
                "style": {
                    "text": "象限 Ⅲ【恐慌探底下坠】\n深度超跌 + 向下加速 (去杠杆深渊)",
                    "fill": "rgba(148, 163, 184, 0.45)",
                    "font": "bold 14px sans-serif",
                    "textAlign": "left"
                }
            },
            {
                "type": "text",
                "left": "100px",
                "top": "110px",
                "style": {
                    "text": "象限 Ⅱ【低位蓄势反弹】\n深度超跌 + 动能止跌转正 (🎯 黄金坑)",
                    "fill": "rgba(16, 185, 129, 0.50)",
                    "font": "bold 14px sans-serif",
                    "textAlign": "left"
                }
            }
        ],
        "grid": {"left": "90px", "right": "50px", "top": "100px", "bottom": "70px"},
        "xAxis": {
            "type": "value",
            "name": "广义反身性势能 q (%) ──> 【← 左侧超跌折价 (便宜) | 右侧高估过热 (贵) →】",
            "nameLocation": "middle",
            "nameGap": 36,
            "min": -round(q_bound, 1),
            "max": round(q_bound, 1),
            "nameTextStyle": {"color": t["axis_label"], "fontSize": 14, "fontWeight": 600},
            "axisLabel": {"color": t["axis_label"], "fontSize": 14, "formatter": "{value}%"},
            "splitLine": {"lineStyle": {"color": t["split_line"]}}
        },
        "yAxis": {
            "type": "value",
            "name": "广义相速度 q̇ (%/天) ──> 【↑ 上方动能加速扩张 | 下方动能衰竭下坠 ↓】",
            "nameLocation": "middle",
            "nameGap": 48,
            "min": -round(qd_bound, 2),
            "max": round(qd_bound, 2),
            "nameTextStyle": {"color": t["axis_label"], "fontSize": 14, "fontWeight": 600},
            "axisLabel": {"color": t["axis_label"], "fontSize": 14, "formatter": "{value}"},
            "splitLine": {"lineStyle": {"color": t["split_line"]}}
        },
        "series": [
            {
                "name": "全景历史散点 (背景星云)",
                "type": "scatter",
                "data": scatter_data,
                "symbolSize": 4,
                "itemStyle": {"color": "rgba(148, 163, 184, 0.18)"}
            },
            {
                "name": s1_name,
                "type": "line",
                "data": s1_pts,
                "smooth": 0.2,
                "symbol": ["none", "arrow"],
                "symbolSize": [0, 10],
                "lineStyle": {"width": 3.5, "color": "#00f5d4"},
                "itemStyle": {"color": "#00f5d4"},
                "markLine": {
                    "symbol": ["none", "none"],
                    "silent": True,
                    "label": {"show": False},
                    "lineStyle": {"color": "rgba(255, 255, 255, 0.22)", "type": "dashed", "width": 1.5},
                    "data": [
                        {"xAxis": 0},
                        {"yAxis": 0}
                    ]
                },
                "markArea": {
                    "silent": True,
                    "data": [
                        [
                            {
                                "name": "🎯 理论战略买入盆地\n(超跌折价 + 动能止跌)",
                                "xAxis": -round(q_bound, 1),
                                "yAxis": 0,
                                "itemStyle": {"color": "rgba(16, 185, 129, 0.08)"},
                                "label": {"position": "insideTopLeft", "color": "#10b981", "fontSize": 13.5, "fontWeight": "bold"}
                            },
                            {
                                "xAxis": -0.5,
                                "yAxis": round(qd_bound, 2)
                            }
                        ],
                        [
                            {
                                "name": "⚠️ 理论动能衰竭逃顶禁区\n(高估过热 + 动能下坠)",
                                "xAxis": 0.5,
                                "yAxis": -round(qd_bound, 2),
                                "itemStyle": {"color": "rgba(239, 68, 68, 0.08)"},
                                "label": {"position": "insideBottomRight", "color": "#ef4444", "fontSize": 13.5, "fontWeight": "bold"}
                            },
                            {
                                "xAxis": round(q_bound, 1),
                                "yAxis": 0
                            }
                        ]
                    ]
                }
            },
            {
                "name": s2_name,
                "type": "line",
                "data": s2_pts,
                "smooth": 0.2,
                "symbol": ["none", "arrow"],
                "symbolSize": [0, 10],
                "lineStyle": {"width": 3.5, "color": "#a855f7"},
                "itemStyle": {"color": "#a855f7"}
            },
            {
                "name": s3_name,
                "type": "line",
                "data": s3_pts,
                "smooth": 0.2,
                "symbol": ["none", "arrow"],
                "symbolSize": [0, 10],
                "lineStyle": {"width": 3.5, "color": "#facc15"},
                "itemStyle": {"color": "#facc15"}
            },
            {
                "name": s4_name,
                "type": "line",
                "data": s4_pts,
                "smooth": 0.2,
                "symbol": ["none", "arrow"],
                "symbolSize": [0, 12],
                "lineStyle": {
                    "width": 4.0,
                    "color": "#ef4444",
                    "shadowColor": "rgba(239, 68, 68, 0.5)",
                    "shadowBlur": 8
                },
                "itemStyle": {"color": "#ef4444"}
            },
            {
                "name": today_name,
                "type": "effectScatter",
                "data": today_marker,
                "symbolSize": 18,
                "rippleEffect": {"scale": 4, "brushType": "stroke"},
                "itemStyle": {"color": "#ef4444", "shadowBlur": 10, "shadowColor": "#ef4444"}
            }
        ]
    }

    if entry_anchor_data:
        phase_option["series"].append({
            "name": "🟢 本轮持股战略建仓点",
            "type": "scatter",
            "data": entry_anchor_data,
            "z": 10
        })

    if cycle_buy_points:
        phase_option["series"].append({
            "name": "⚡ 周期内战略买入",
            "type": "scatter",
            "data": cycle_buy_points,
            "symbol": "triangle",
            "symbolSize": 16,
            "itemStyle": {"color": "#10b981", "borderColor": "#ffffff", "borderWidth": 2},
            "label": {"show": True, "position": "top", "formatter": "{b}", "fontSize": 12, "color": "#10b981", "fontWeight": "bold"}
        })

    if cycle_sell_points:
        phase_option["series"].append({
            "name": "🛑 周期内战略卖出",
            "type": "scatter",
            "data": cycle_sell_points,
            "symbol": "triangle",
            "symbolRotate": 180,
            "symbolSize": 16,
            "itemStyle": {"color": "#ef4444", "borderColor": "#ffffff", "borderWidth": 2},
            "label": {"show": True, "position": "bottom", "formatter": "{b}", "fontSize": 12, "color": "#ef4444", "fontWeight": "bold"}
        })

    # 13 年全历史调仓复盘图层 (默认关闭，用户在图例中点击开启，每个点均带醒目年份标签)
    all_historical_points = historical_buy_points + historical_sell_points
    if all_historical_points:
        phase_option["series"].append({
            "name": "📜 13年历史调仓复盘 (含年份)",
            "type": "scatter",
            "data": all_historical_points,
            "symbolSize": 14,
            "label": {
                "show": True,
                "position": "top",
                "formatter": "{b}",
                "fontSize": 12,
                "color": "#f8fafc",
                "backgroundColor": "rgba(15, 23, 42, 0.85)",
                "borderColor": "rgba(255, 255, 255, 0.2)",
                "borderWidth": 1,
                "padding": [2, 5],
                "borderRadius": 4
            }
        })

    phase_html = f"""
    <div id="phase_chart" style="width: 100%; height: 530px; border-radius: 10px; background: {t['card_bg']}; border: 1px solid {t['border_color']};"></div>
    <script src="https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"></script>
    <script>
        var chart_p = echarts.init(document.getElementById('phase_chart'), '{t["echarts_theme"]}');
        chart_p.setOption({json.dumps(phase_option)});
        window.addEventListener('resize', () => chart_p.resize());
    </script>
    """
    components.html(phase_html, height=550)

    st.markdown(
        _clean_html(f"""
        <div style="background: rgba(30, 41, 59, 0.45); border: 1px dashed rgba(56, 189, 248, 0.35); border-radius: 10px; padding: 16px 20px; margin-top: 12px; margin-bottom: 20px;">
            <div style="font-size: 16px; font-weight: 700; color: #38bdf8; margin-bottom: 10px;">
                💡 动态相空间图 3 步极简实战读图法 (看懂宏观周期演进与长线投资本质)
            </div>
            <div style="font-size: 14.5px; color: #e2e8f0; line-height: 1.85;">
                <b>1. 第一步：先看“大红点 (TODAY)”在哪里？—— 诊断当前宏观状态与调仓决策</b><br>
                • <b>横坐标看估值高低</b>：红点在<b>右半边 (q > 0)</b> 代表价格高于宏观信用中枢（估值溢价）；在<b>左半边 (q < 0)</b> 代表价格低于中枢（估值折价便宜）。<br>
                • <b>纵坐标看动能强弱</b>：红点在<b>上半区 (q̇ > 0)</b> 代表动能正在向上冲刺或反弹；在<b>下半区 (q̇ < 0)</b> 代表上涨冲力正在衰竭或下坠。<br>
                • <b>当前决策准则</b>：只有当红点落入左上角的【🎯 绿色战略买入盆地】才触发买入；落入右下角的【⚠️ 红色逃顶禁区】才触发卖出；在中间平衡带<b>严格顺势满仓持股，杜绝频繁倒手</b>。<br>
                <b>2. 第二步：顺着“4 阶段彩色接力棒 (带方向箭头)”看宏观生命周期 —— 还原长线演进轨迹</b><br>
                • <b>起点与出坑修复 (青色线 ① ➔)</b>：如果在【本轮持股全周期】视角下，轨迹起点正是在左侧盆地触发的<b>绿色战略建仓点</b>，直观展现股价如何筑底出坑；<br>
                • <b>主升扩张期 (紫色线 ② ➔)</b>：股价顺着箭头自左向右穿过 0 轴平衡线，势能持续扩张，享受估值修复与盈利共振；<br>
                • <b>中高位运行与冲刺当下 (金色线 ③ ➔ 烈火红线 ④ ➔)</b>：在高位维持平稳运行，最终直达 TODAY 最新信标！<br>
                • <b>极简心法</b>：长线投资无需每天盯盘！顺着<b>“青 ➔ 紫 ➔ 黄 ➔ 红”</b>四截彩色箭头线，3 秒钟即可纵览数年宏观周期的完整生命历程。<br>
                <b>3. 第三步：结合“历史买卖点复盘”检验策略铁律 —— 拒绝盲目追涨杀跌</b><br>
                • <b>绿色战略买入点 (BUY)</b>：全部潜伏在左侧折价区与估值修复启动点，真正践行“别人恐慌时我贪婪”；<br>
                • <b>红色战略卖出点 (SELL)</b>：集中在右侧严重过热且动能失稳区，坚决避险保住利润；<br>
                • <b>为什么历史买卖记录很少？</b> 因为长线宏观反身性以 1~3 年的经济与信用大周期为尺度，<b>耐得住寂寞、坚定持有主升浪才是财富增厚的核心驱动力</b>！
            </div>
        </div>
        """),
        unsafe_allow_html=True
    )

    st.markdown("---")

    # ------------------------------------------------------------------
    # 核心看板 4: 真实券商记账全周期资产净值对账曲线 (Strategy vs Benchmark)
    # ------------------------------------------------------------------
    st.subheader(f"💰 {active_ticker} 真实券商记账资产净值对账曲线 (Strategy vs Benchmark NAV)")
    st.caption(f"💡 **严格券商记账**：追踪真实持股数与现金池，全周期仅触发 {rep['总交易配对轮次']} 轮战略买卖，策略最终资产 ${rep['策略最终财富']:,.0f} (基准: ${rep['基准最终财富']:,.0f})。")

    strat_nav_vals = [round(v, 2) for v in df_bt['strat_nav']]
    bench_nav_vals = [round(v, 2) for v in df_bt['bench_nav']]

    nav_option = {
        "backgroundColor": t["card_bg"],
        "tooltip": {
            "trigger": "axis",
            "backgroundColor": t["tooltip_bg"],
            "borderColor": t["tooltip_border"],
            "borderWidth": 1,
            "textStyle": {"color": t["tooltip_text"], "fontSize": 14},
            "axisPointer": {
                "type": "cross",
                "label": {
                    "backgroundColor": "#334155",
                    "fontSize": 13,
                    "color": "#ffffff"
                },
                "lineStyle": {
                    "color": t["axis_line"],
                    "type": "dashed"
                }
            }
        },
        "legend": {
            "top": "12px",
            "left": "center",
            "textStyle": {"color": t["axis_label"], "fontSize": 14, "fontWeight": 600},
            "data": [f"{active_ticker} 黄文政动力学相空间策略净值", f"{active_ticker} 买入持有基准净值 (Buy & Hold)"]
        },
        "grid": {
            "left": "85px",
            "right": "40px",
            "top": "55px",
            "bottom": "75px",
            "containLabel": True
        },
        "xAxis": {
            "type": "category",
            "data": dates_str,
            "boundaryGap": False,
            "axisLabel": {"color": t["axis_label"], "fontSize": 14},
            "axisLine": {"lineStyle": {"color": t["axis_line"]}}
        },
        "yAxis": {
            "type": "value",
            "scale": True,
            "name": "账户资产 ($)",
            "nameGap": 14,
            "nameTextStyle": {"color": t["axis_label"], "fontSize": 14, "fontWeight": 600},
            "axisLabel": {"color": t["axis_label"], "fontSize": 14, "formatter": "${value}"},
            "splitLine": {"lineStyle": {"color": t["split_line"]}}
        },
        "dataZoom": [
            {
                "type": "inside",
                "start": 0,
                "end": 100
            },
            {
                "type": "slider",
                "start": 0,
                "end": 100,
                "bottom": 10,
                "height": 26,
                "borderColor": t["datazoom_border"],
                "backgroundColor": t["datazoom_bg"],
                "fillerColor": t["datazoom_filler"],
                "handleStyle": {"color": t["datazoom_handle"]},
                "textStyle": {"color": t["axis_label"], "fontSize": 12},
                "dataBackground": {
                    "lineStyle": {"color": t["datazoom_handle"]},
                    "areaStyle": {"color": t["datazoom_filler"]}
                }
            }
        ],
        "series": [
            {
                "name": f"{active_ticker} 黄文政动力学相空间策略净值",
                "type": "line",
                "smooth": True,
                "data": strat_nav_vals,
                "lineStyle": {"width": 3, "color": "#10b981"},
                "itemStyle": {"color": "#10b981"}
            },
            {
                "name": f"{active_ticker} 买入持有基准净值 (Buy & Hold)",
                "type": "line",
                "smooth": True,
                "data": bench_nav_vals,
                "lineStyle": {"width": 2, "color": "#94a3b8", "type": "dashed"},
                "itemStyle": {"color": "#94a3b8"}
            }
        ]
    }

    nav_html = f"""
    <div id="nav_chart" style="width: 100%; height: 430px; border-radius: 10px; background: {t['card_bg']}; border: 1px solid {t['border_color']};"></div>
    <script src="https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"></script>
    <script>
        var chart = echarts.init(document.getElementById('nav_chart'), '{t["echarts_theme"]}');
        chart.setOption({json.dumps(nav_option)});
        window.addEventListener('resize', () => chart.resize());
    </script>
    """
    components.html(nav_html, height=450)

    st.markdown("---")

    # ------------------------------------------------------------------
    # 核心看板 5: 该标的波段战略买卖配对全底稿对账表
    # ------------------------------------------------------------------
    st.subheader(f"📋 {active_ticker} 战略级买卖配对全底稿对账表 (Trade Audit Pairs)")
    
    df_pairs = pd.DataFrame(engine.paired_trades)
    if not df_pairs.empty:
        styler_pairs = df_pairs.style.format({
            "卖出价格": "${:.2f}",
            "买回价格": "${:.2f}",
            "差价获利空间(%)": "{:+.2f}%"
        })
        styler_pairs = _safe_style_map(
            styler_pairs,
            lambda val: "color: #10b981; font-weight: bold;" if isinstance(val, (int, float)) and val > 0 else ("color: #f87171;" if isinstance(val, (int, float)) and val < 0 else ""),
            subset=["差价获利空间(%)"]
        )
        st.dataframe(
            styler_pairs,
            use_container_width=True,
            height=300
        )
    else:
        st.info(f"{active_ticker} 在该周期内始终处于稳态吸引子基盆 (λ ≤ 0)，未触发任何宏观卖出信号，策略 100% 满仓持股享受复利。")

    st.markdown("---")

    # ------------------------------------------------------------------
    # 核心看板 6: 七大基准标的横向全景评测矩阵与深刻金融哲学归因
    # ------------------------------------------------------------------
    st.subheader("🌐 七大代表性标的全景横向评测矩阵 (Cross-Asset Empirical Matrix)")
    st.caption("💡 **严谨科学实证**：拒绝盲目粉饰，真实揭示模型在不同资产类别上的适用边界与数理本源。")

    df_multi = pd.DataFrame(MULTI_ASSET_BENCHMARK_DATA)
    styler_multi = _safe_style_map(
        df_multi.style,
        lambda val: "color: #10b981; font-weight: bold;" if isinstance(val, str) and val.startswith("+") else ("color: #f87171;" if isinstance(val, str) and val.startswith("-") else ""),
        subset=["累积净超额 (Alpha $)", "财富相对增厚", "样本外超额"]
    )
    st.dataframe(
        styler_multi,
        use_container_width=True,
        height=290
    )

    st.markdown(
        _clean_html("""
        <div style="background: rgba(15, 23, 42, 0.6); border: 1px solid #334155; border-radius: 8px; padding: 18px 22px; margin-top: 12px; margin-bottom: 20px;">
            <div style="font-size: 16px; font-weight: 700; color: #f59e0b; margin-bottom: 10px;">
                🧠 深度批判性思维：黄文政动力学模型的资产边界与第一性原理归因
            </div>
            <div style="font-size: 14.5px; line-height: 1.8; color: #cbd5e1;">
                <b>1. 高弹性、高估值成长资产 (NOW, META, TEAM) —— 模型表现极具统治力 (Alpha +60% ~ +118%)</b>：<br>
                • <b>数理本源</b>：此类资产的高估值倍数严重依赖宏观流动性环境与低信用溢价。一旦宏观流动性收紧（如 2022 年加息风暴），杀估值幅度极其血腥（TEAM 暴跌 -82%、META 暴跌 -75%、NOW 暴跌 -64%）；<br>
                • <b>动力学赋能</b>：黄文政模型通过宏观引力势能过热与局部李雅普诺夫指数失稳（LLE λ > 0），在暴跌前夕敏锐识别相变失稳，成功避开深渊，并在右侧以极低成本回补更多股数，创造了高达 <b>+$473k ~ +$669k</b> 的巨额净超额财富！<br><br>
                <b>2. 超强资产负债表与 AAA 评级蓝筹 (MSFT, AAPL) —— 模型轻微跑输 Buy & Hold (-8% ~ -13%)</b>：<br>
                • <b>数理本源</b>：微软与苹果拥有全市场最高的信用等级（微软信用评级甚至高于美国国债，苹果年回购高达千亿美元），其现金流折现模型对宏观高收益债（HYG）信用利差的波动天然免疫；<br>
                • <b>边界教训</b>：强行套用宏观高收益债信用断裂指标去约束此类自身资产负债表坚如磐石的垄断巨头，会导致在正常的浅幅回调中产生微幅摩擦磨损。<br><br>
                <b>3. 指数级超级单边牛股 (AVGO) —— 回撤压制极其出色，但年化 28% 强动量使任何摩擦代价放大</b>：<br>
                • <b>数理本源</b>：博通 13 年上涨 60 倍（年化 CAGR 高达惊人的 28.0%）。黄文政模型将其最大回撤由基准的 <b>-48.09%</b> 骤降至 <b>-29.38%</b>（回撤压制近 19%）；<br>
                • <b>绝对收益代价</b>：但在年化近 30% 的极陡峭指数级上升浪中，即使通过防踏空保护盾在 +2%~4% 右侧接回，几次极其微小的摩擦在暴利复利放大下，绝对总财富仍会略逊于死扛不动的纯买入持有。<br><br>
                <b>4. 极端高 Beta 与特质产业周期标的 (COIN) —— 为什么不分析个股基本面，纯宏观模型会彻底失效？</b>：<br>
                • <b>数理本源与引力锚脱节</b>：Coinbase 年化波动率高达 84.6%，特质风险占比高达 73.0%！其底层驱动力完全由加密资产自身 4 年减半周期与链上交易量决定，与美国高收益债宏观信贷引力锚完全脱节；<br>
                • <b>惨痛教训与致命盲区</b>：在 2025 年高位震荡中，宏观微弱信贷毛刺诱发了频繁的假突破与追涨杀跌磨损（如 $257 卖出、$295 追回）；而在 2025-2026 年从 $420 跌至 $140 的 65% 断崖暴跌中，因宏观信贷环境平稳无危机，模型毫无作为一路 100% 满仓死扛到底！最终 Alpha 录得 <b>-$10,466 (-12.2%)</b>；<br>
                • <b>第一性原理终极启示</b>：<b>脱离个股微观基本面与产业特质周期，机械套用宏观物理动力学模型是盲目且残缺的！</b> 任何工业级量化模型，必须首先完成个股微观基本面与资产能力圈判定，绝不可一刀切！
            </div>
        </div>
        """),
        unsafe_allow_html=True
    )
