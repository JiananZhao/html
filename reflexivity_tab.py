# -*- coding: utf-8 -*-
"""
========================================================================================
项目名称：宏观反身性阿尔法模型 (方案 B_Plus: 双轨制雷达看板版)
文件名称：reflexivity_tab.py
跨平台支持：本地 Windows / Linux / Streamlit Community Cloud (云端原生与 GitHub 直读)
========================================================================================
"""

import os
import io
import requests
import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime

# 基础目录与跨平台相对路径定义 (杜绝绝对路径 e:/ 硬编码)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOCAL_CSV_PATH = os.path.join(BASE_DIR, "market_data_local.csv")
GITHUB_RAW_CSV_URL = "https://raw.githubusercontent.com/JiananZhao/html/master/market_data_local.csv"

# 高清图谱与 Excel 相对路径
QQQ_CHART_LOCAL = os.path.join(BASE_DIR, "宏观反身性阿尔法模型_模型A_Plus_QQQ买卖信号与净值对比图.png")
SPY_CHART_LOCAL = os.path.join(BASE_DIR, "宏观反身性阿尔法模型_模型A_Plus_SPY买卖信号与净值对比图.png")
EXCEL_DELIVERABLE_LOCAL = os.path.join(BASE_DIR, "宏观反身性阿尔法模型_模型A_Plus_真实对账全证据.xlsx")

# GitHub Raw 备用 URL (云端环境图谱与数据自动 Fallback)
GITHUB_RAW_QQQ_CHART = "https://raw.githubusercontent.com/JiananZhao/html/master/%E5%AE%8F%E8%A7%82%E5%8F%8D%E8%BA%AB%E6%80%A7%E9%98%BF%E5%B0%94%E6%B3%95%E6%A8%A1%E5%9E%8B_%E6%A8%A1%E5%9E%8BA_Plus_QQQ%E4%B9%B0%E5%8D%96%E4%BF%A1%E5%8F%B7%E4%B8%8E%E5%87%80%E5%80%BC%E5%AF%B9%E6%AF%94%E5%9B%BE.png"
GITHUB_RAW_SPY_CHART = "https://raw.githubusercontent.com/JiananZhao/html/master/%E5%AE%8F%E8%A7%82%E5%8F%8D%E8%BA%AB%E6%80%A7%E9%98%BF%E5%B0%94%E6%B3%95%E6%A8%A1%E5%9E%8B_%E6%A8%A1%E5%9E%8BA_Plus_SPY%E4%B9%B0%E5%8D%96%E4%BF%A1%E5%8F%B7%E4%B8%8E%E5%87%80%E5%80%BC%E5%AF%B9%E6%AF%94%E5%9B%BE.png"
GITHUB_RAW_EXCEL = "https://raw.githubusercontent.com/JiananZhao/html/master/%E5%AE%8F%E8%A7%82%E5%8F%8D%E8%BA%AB%E6%80%A7%E9%98%BF%E5%B0%94%E6%B3%95%E6%A8%A1%E5%9E%8B_%E6%A8%A1%E5%9E%8BA_Plus_%E7%9C%9F%E5%AE%9E%E5%AF%B9%E8%83%80%E5%85%A8%E8%AF%81%E6%8D%AE.xlsx"

# 导入每日监控模块
try:
    from daily_market_monitor import sync_latest_market_data, compute_latest_signals
except ImportError:
    sync_latest_market_data = None
    compute_latest_signals = None


@st.cache_data(ttl=600, show_spinner=False)
def load_market_data_cross_platform():
    """
    跨平台双模数据加载器：
    1. 优先从本地仓库相对路径读取；
    2. 若本地文件不存在（如在 Streamlit Community Cloud 容器内），直接从 GitHub Raw 极速拉取。
    """
    if os.path.exists(LOCAL_CSV_PATH):
        try:
            df = pd.read_csv(LOCAL_CSV_PATH)
            if not df.empty and 'date' in df.columns:
                return df, "本地相对路径"
        except Exception:
            pass
            
    # 从 GitHub Raw 直读
    try:
        df = pd.read_csv(GITHUB_RAW_CSV_URL)
        if not df.empty and 'date' in df.columns:
            return df, "GitHub 远端直读"
    except Exception as e:
        st.error(f"从 GitHub 读取数据失败: {e}")
        
    return pd.DataFrame(), "无可用数据源"


def render_reflexivity_tab():
    st.header("🦅 索罗斯宏观反身性阿尔法模型 (双轨制雷达看板版)")
    st.caption("【机构级纯现货大类资产配置】信用先导熊市出清 · 动态扩展分位数自适应 · 0~100分宏观过热预警雷达")
    
    # -------------------------------------------------------------
    # 1. 顶部控制栏与一键同步数据按钮 (支持本地与 GitHub 状态)
    # -------------------------------------------------------------
    col_sync, col_status = st.columns([2, 5])
    
    with col_sync:
        if st.button("🔄 立即同步最新数据", use_container_width=True, help="增量更新数据并重新计算信号"):
            if sync_latest_market_data is not None:
                with st.spinner("正在同步最新行情与宏观因子..."):
                    res = sync_latest_market_data(force=True)
                    st.cache_data.clear()
                    if res.get("status") == "updated":
                        st.success(f"同步成功！追加 {res.get('new_rows')} 行，最新日期: {res.get('last_date')}")
                    elif res.get("status") == "up_to_date":
                        st.info(f"数据库已是最新（基准日: {res.get('last_date')}），无需更新。")
                    else:
                        st.warning(f"同步状态: {res.get('status')}")
                    st.rerun()
            else:
                st.cache_data.clear()
                st.info("已刷新数据缓存。")
                st.rerun()

    df_data, source_tag = load_market_data_cross_platform()

    with col_status:
        if not df_data.empty:
            last_date_str = str(df_data['date'].iloc[-1])[:10]
            st.markdown(
                f"**微型数据库状态:** `🟢 正常运行 ({source_tag})` | **数据基准日:** `{last_date_str}` | **历史样本量:** `{len(df_data)} 交易日`"
            )
        else:
            st.error(f"数据库加载失败，请检查网络或 GitHub 链接: {GITHUB_RAW_CSV_URL}")

    st.markdown("---")

    # -------------------------------------------------------------
    # 2. 今日双轨决策雷达监控卡片 (SPY & QQQ)
    # -------------------------------------------------------------
    st.subheader("📡 今日收盘实时决策雷达看板 (Daily Decision Dashboard)")

    signals = {}
    if compute_latest_signals is not None and not df_data.empty:
        try:
            signals = compute_latest_signals(df_input=df_data)
        except Exception as e:
            st.error(f"信号计算异常: {e}")

    if signals:
        col_qqq, col_spy = st.columns(2)
        
        # QQQ 卡片
        with col_qqq:
            q = signals.get('QQQ', {})
            st.markdown("### 💻 QQQ (纳斯达克100 ETF)")
            
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
    # 3. 高清 4 层双轨制决策图谱展示 (支持本地与云端直链)
    # -------------------------------------------------------------
    st.subheader("📈 17.6 年全历史买卖信号与净值全景图谱")
    tab_chart_q, tab_chart_s, tab_audit = st.tabs(["💻 QQQ 全景图谱 (4层对齐)", "🇺🇸 SPY 全景图谱 (4层对齐)", "📊 官方全周期对账数据"])

    with tab_chart_q:
        chart_src_q = QQQ_CHART_LOCAL if os.path.exists(QQQ_CHART_LOCAL) else GITHUB_RAW_QQQ_CHART
        st.image(chart_src_q, caption="QQQ 宏观反身性双轨制雷达看板（顶层黄色过热预警散点 + 第3层过热雷达能量带）", use_container_width=True)

    with tab_chart_s:
        chart_src_s = SPY_CHART_LOCAL if os.path.exists(SPY_CHART_LOCAL) else GITHUB_RAW_SPY_CHART
        st.image(chart_src_s, caption="SPY 宏观反身性双轨制雷达看板（顶层黄色过热预警散点 + 第3层过热雷达能量带）", use_container_width=True)

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
        
        # Excel 底稿下载 (本地优先，云端 fallback)
        if os.path.exists(EXCEL_DELIVERABLE_LOCAL):
            with open(EXCEL_DELIVERABLE_LOCAL, "rb") as f:
                st.download_button(
                    label="📥 下载官方 6 表真实对账全证据 Excel 底稿 (.xlsx)",
                    data=f.read(),
                    file_name="宏观反身性阿尔法模型_模型A_Plus_真实对账全证据.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
        else:
            st.markdown(f"📥 [点击从 GitHub 下载官方 Excel 底稿]({GITHUB_RAW_EXCEL})")
