# -*- coding: utf-8 -*-
"""
========================================================================================
项目名称：宏观反身性阿尔法模型 (方案 B_Plus: 双轨制雷达看板版)
文件名称：reflexivity_tab.py
========================================================================================
"""

import os
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime

# 导入每日监控与增量同步引擎
try:
    from daily_market_monitor import sync_latest_market_data, compute_latest_signals, LOCAL_CSV_PATH
except ImportError:
    LOCAL_CSV_PATH = "e:/AI/Github_AIProject/html/market_data_local.csv"
    sync_latest_market_data = None
    compute_latest_signals = None

EXCEL_DELIVERABLE_PATH = "e:/AI/Github_AIProject/html/宏观反身性阿尔法模型_模型A_Plus_真实对账全证据.xlsx"
QQQ_CHART_PATH = "e:/AI/Github_AIProject/html/宏观反身性阿尔法模型_模型A_Plus_QQQ买卖信号与净值对比图.png"
SPY_CHART_PATH = "e:/AI/Github_AIProject/html/宏观反身性阿尔法模型_模型A_Plus_SPY买卖信号与净值对比图.png"


def render_reflexivity_tab():
    st.header("🦅 索罗斯宏观反身性阿尔法模型 (双轨制雷达看板版)")
    st.caption("【机构级纯现货大类资产配置】信用先导熊市出清 · 动态扩展分位数自适应 · 0~100分宏观过热预警雷达")
    
    # -------------------------------------------------------------
    # 1. 顶部控制栏与一键同步数据按钮
    # -------------------------------------------------------------
    col_sync, col_status = st.columns([2, 5])
    
    with col_sync:
        if st.button("🔄 立即同步最新数据", use_container_width=True, help="点击从 FRED 与 Yahoo 增量拉取最新交易日数据并自动追加到本地数据库"):
            if sync_latest_market_data is not None:
                with st.spinner("正在增量同步最新行情与宏观因子至本地数据库..."):
                    res = sync_latest_market_data(force=True)
                    if res.get("status") == "updated":
                        st.success(f"同步成功！追加 {res.get('new_rows')} 行，最新日期: {res.get('last_date')}")
                    elif res.get("status") == "up_to_date":
                        st.info(f"本地数据库已是最新（基准日: {res.get('last_date')}），无需更新。")
                    else:
                        st.warning(f"同步状态: {res.get('status')}")
                    st.rerun()
            else:
                st.error("未找到 daily_market_monitor 模块。")

    with col_status:
        if os.path.exists(LOCAL_CSV_PATH):
            df_local = pd.read_csv(LOCAL_CSV_PATH)
            last_date_str = str(df_local['date'].iloc[-1])[:10]
            st.markdown(
                f"**本地微型真理库状态:** `🟢 正常运行` | **数据基准日:** `{last_date_str}` | **历史样本量:** `{len(df_local)} 交易日`"
            )
        else:
            st.error(f"本地数据库缺失: {LOCAL_CSV_PATH}")

    st.markdown("---")

    # -------------------------------------------------------------
    # 2. 今日双轨决策雷达监控卡片 (SPY & QQQ)
    # -------------------------------------------------------------
    st.subheader("📡 今日收盘实时决策雷达看板 (Daily Decision Dashboard)")

    if compute_latest_signals is not None:
        try:
            signals = compute_latest_signals()
        except Exception as e:
            st.error(f"信号计算异常: {e}")
            signals = {}
    else:
        signals = {}

    if signals:
        col_qqq, col_spy = st.columns(2)
        
        # QQQ 卡片
        with col_qqq:
            q = signals.get('QQQ', {})
            st.markdown("### 💻 QQQ (纳斯达克100 ETF)")
            
            # 状态指示横幅
            tag = q.get('status_tag', '🟢 健康常态持仓')
            if "🔴" in tag:
                st.error(f"**系统信号:** {tag}")
            elif "🟡" in tag:
                st.warning(f"**系统信号:** {tag}")
            else:
                st.success(f"**系统信号:** {tag}")
                
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("收盘价 (USD)", f"${q.get('price', 0.0):.2f}")
            m2.metric("年线乖离率", f"{q.get('dist_200', 0.0):+.1f}%")
            m3.metric("反身性 Gap", f"{q.get('gap', 0.0):.2f}", f"阈值: {q.get('gap_upper', 0.0):.2f}")
            score_q = q.get('overheat_score', 0.0)
            m4.metric("过热雷达分", f"{score_q:.1f}/100", "[高危 >= 70]" if score_q >= 70 else "安全区")
            
            st.markdown(f"**💡 实操行为指引:** {q.get('action_desc', '')}")
            st.markdown(
                f"<small style='color:gray;'>均线参考: MA20=${q.get('ma20',0):.1f} | MA50=${q.get('ma50',0):.1f} | MA200=${q.get('ma200',0):.1f} | 建议仓位: <b>{q.get('rec_pos',1)*100:.0f}%</b></small>",
                unsafe_allow_html=True
            )

        # SPY 卡片
        with col_spy:
            s = signals.get('SPY', {})
            st.markdown("### 🇺🇸 SPY (标普500 ETF)")
            
            tag_s = s.get('status_tag', '🟢 健康常态持仓')
            if "🔴" in tag_s:
                st.error(f"**系统信号:** {tag_s}")
            elif "🟡" in tag_s:
                st.warning(f"**系统信号:** {tag_s}")
            else:
                st.success(f"**系统信号:** {tag_s}")
                
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("收盘价 (USD)", f"${s.get('price', 0.0):.2f}")
            m2.metric("年线乖离率", f"{s.get('dist_200', 0.0):+.1f}%")
            m3.metric("反身性 Gap", f"{s.get('gap', 0.0):.2f}", f"阈值: {s.get('gap_upper', 0.0):.2f}")
            score_s = s.get('overheat_score', 0.0)
            m4.metric("过热雷达分", f"{score_s:.1f}/100", "[高危 >= 70]" if score_s >= 70 else "安全区")
            
            st.markdown(f"**💡 实操行为指引:** {s.get('action_desc', '')}")
            st.markdown(
                f"<small style='color:gray;'>均线参考: MA20=${s.get('ma20',0):.1f} | MA50=${s.get('ma50',0):.1f} | MA200=${s.get('ma200',0):.1f} | 建议仓位: <b>{s.get('rec_pos',1)*100:.0f}%</b></small>",
                unsafe_allow_html=True
            )

    st.markdown("---")

    # -------------------------------------------------------------
    # 3. 高清 4 层双轨制决策图谱展示
    # -------------------------------------------------------------
    st.subheader("📈 17.6 年全历史买卖信号与净值全景图谱")
    tab_chart_q, tab_chart_s, tab_audit = st.tabs(["💻 QQQ 全景图谱 (4层对齐)", "🇺🇸 SPY 全景图谱 (4层对齐)", "📊 官方全周期对账数据"])

    with tab_chart_q:
        if os.path.exists(QQQ_CHART_PATH):
            st.image(QQQ_CHART_PATH, caption="QQQ 宏观反身性双轨制雷达看板（顶层黄色过热预警散点 + 第3层过热雷达能量带）", use_container_width=True)
        else:
            st.warning("QQQ 高清图谱生成中...")

    with tab_chart_s:
        if os.path.exists(SPY_CHART_PATH):
            st.image(SPY_CHART_PATH, caption="SPY 宏观反身性双轨制雷达看板（顶层黄色过热预警散点 + 第3层过热雷达能量带）", use_container_width=True)
        else:
            st.warning("SPY 高清图谱生成中...")

    with tab_audit:
        st.markdown("#### 17.6 年全周期定投绩效审计总表 (纯现货 1.0x 真实券商记账)")
        perf_data = {
            "标的资产": ["QQQ (纳指100)", "SPY (标普500)"],
            "定投总本金": ["$213,000", "$213,000"],
            "基准买入持有终值": ["$1,535,733 (+621.0%)", "$912,082 (+328.2%)"],
            "策略账户最终净值": ["$2,253,622 (+958.0%)", "$1,237,236 (+480.9%)"],
            "超额收益 Alpha": ["+337.04%", "+152.65%"],
            "多赚现金财富": ["+$717,889", "+$325,153"],
            "最大回撤 (策略 vs 基准)": ["-22.41% (改善 +11.6%)", "-18.49% (改善 +15.0%)"],
            "全历史交易轮次": ["10 轮 (年均 1.14 次)", "8 轮 (年均 0.91 次)"],
            "波段胜率": ["60.0%", "50.0%"]
        }
        st.table(pd.DataFrame(perf_data))
        
        if os.path.exists(EXCEL_DELIVERABLE_PATH):
            with open(EXCEL_DELIVERABLE_PATH, "rb") as f:
                st.download_button(
                    label="📥 下载官方 6 表真实对账全证据 Excel 底稿 (.xlsx)",
                    data=f.read(),
                    file_name="宏观反身性阿尔法模型_模型A_Plus_真实对账全证据.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
