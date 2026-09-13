# -*- coding: utf-8 -*-
"""
========================================================================================
项目名称：行业专属微观内生泡沫雷达看板 (聚焦 Layer 2 与 Layer 3 核心监控)
文件名称：industry_bubble_tab.py
标的资产：IGV (iShares 扩展科技软件与云计算 ETF)
跨平台支持：本地 Windows / Linux / Streamlit Community Cloud (支持本地与 GitHub Raw 直读)
========================================================================================
"""

import os
import io
import requests
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime

# 基础目录与相对路径定义 (杜绝绝对路径 e:/ 硬编码)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOCAL_RADAR_CSV = os.path.join(BASE_DIR, "igv_radar_local.csv")
LOCAL_CONST_CSV = os.path.join(BASE_DIR, "igv_constituents_local.csv")
LOCAL_EXCEL_PATH = os.path.join(BASE_DIR, "宏观反身性阿尔法模型_IGV微观雷达全周期对账表.xlsx")
LOCAL_CHART_PNG = os.path.join(BASE_DIR, "宏观反身性阿尔法模型_IGV微观雷达4层全景图谱.png")

# GitHub Raw 备用 URL
GITHUB_RAW_RADAR_CSV = "https://raw.githubusercontent.com/JiananZhao/html/master/igv_radar_local.csv"
GITHUB_RAW_EXCEL = "https://raw.githubusercontent.com/JiananZhao/html/master/%E5%AE%8F%E8%A7%82%E5%8F%8D%E8%BA%AB%E6%80%A7%E9%98%BF%E5%B0%94%E6%B3%95%E6%A8%A1%E5%9E%8B_IGV%E5%BE%AE%E8%A7%82%E9%9B%B7%E8%BE%BE%E5%85%A8%E5%91%A8%E6%9C%9F%E5%AF%B9%E8%83%80%E8%A1%A8.xlsx"
GITHUB_RAW_PNG = "https://raw.githubusercontent.com/JiananZhao/html/master/%E5%AE%8F%E8%A7%82%E5%8F%8D%E8%BA%AB%E6%80%A7%E9%98%BF%E5%B0%94%E6%B3%95%E6%A8%A1%E5%9E%8B_IGV%E5%BE%AE%E8%A7%82%E9%9B%B7%E8%BE%BE4%E5%B1%82%E5%85%A8%E6%99%AF%E5%9B%BE%E8%B0%B1.png"

# 15 大核心成分股列表
CORE_CONSTITUENTS = [
    'MSFT', 'CRM', 'ORCL', 'ADBE', 'NOW',
    'INTU', 'PLTR', 'PANW', 'CRWD', 'SNOW',
    'WDAY', 'FTNT', 'DDOG', 'CDNS', 'SNPS'
]


@st.cache_data(ttl=600, show_spinner=False)
def load_igv_radar_data():
    """
    跨平台双模数据加载器：
    1. 优先从本地仓库读取预计算的 igv_radar_local.csv；
    2. 若不存在，尝试从 GitHub Raw 直读；
    3. 若仍无，调用 micro_bubble_radar 引擎重新计算并缓存。
    """
    if os.path.exists(LOCAL_RADAR_CSV):
        try:
            df = pd.read_csv(LOCAL_RADAR_CSV)
            if not df.empty and 'date' in df.columns:
                return df, "本地文件直读"
        except Exception:
            pass

    # 尝试 GitHub Raw
    try:
        df = pd.read_csv(GITHUB_RAW_RADAR_CSV)
        if not df.empty and 'date' in df.columns:
            return df, "GitHub Raw 远端直读"
    except Exception:
        pass

    # 本地动态重算 fallback
    try:
        from micro_bubble_radar import MicroBubbleRadar
        radar = MicroBubbleRadar()
        df = radar.load_and_preprocess()
        df = radar.compute_all_dimensions()
        try:
            df.to_csv(LOCAL_RADAR_CSV, index=False)
        except Exception:
            pass
        return df, "引擎动态运算"
    except Exception as e:
        st.error(f"微观雷达数据加载失败: {e}")
        return pd.DataFrame(), "无可用数据源"


def build_layer2_radar_chart(df, default_range="1Y"):
    """
    绘制 Layer 2: 0~100 综合微观雷达分与 4 大独立分项交互图谱 (Plotly)
    满足用户要求：
    1. legend 底色为白色，文字为黑色；
    2. Y 轴自适应调节，消除多余空白；
    3. 支持独立勾选查看各单项指标。
    """
    dates = pd.to_datetime(df['date'])

    fig = go.Figure()

    # 1. 综合雷达分 (主曲线，加粗紫色)
    fig.add_trace(go.Scatter(
        x=dates,
        y=df['Composite_Radar_Score'],
        name='<b>🎯 综合微观雷达分 (0-100)</b>',
        line=dict(color='#8A2BE2', width=3.0),
        hovertemplate='<b>综合雷达总分</b>: %{y:.1f}分<extra></extra>'
    ))

    # 2. 动力学分项 (蓝色)
    fig.add_trace(go.Scatter(
        x=dates,
        y=df['Score_Dynamics'],
        name='⚡ 动力学奇异度分位数 (35%)',
        line=dict(color='#1E90FF', width=1.5),
        hovertemplate='动力学分项: %{y:.1f}分<extra></extra>'
    ))

    # 3. 估值分位数分项 (橙色)
    fig.add_trace(go.Scatter(
        x=dates,
        y=df['Score_Valuation'],
        name='💎 行业专属估值分位数 (25%)',
        line=dict(color='#FF8C00', width=1.5),
        hovertemplate='估值分项: %{y:.1f}分<extra></extra>'
    ))

    # 4. 广度顶背离分项 (红褐色)
    fig.add_trace(go.Scatter(
        x=dates,
        y=df['Score_Breadth'],
        name='📉 内部广度顶背离分位数 (25%)',
        line=dict(color='#DC143C', width=1.5),
        hovertemplate='广度顶背离分项: %{y:.1f}分<extra></extra>'
    ))

    # 5. 相对溢价脱节分项 (粉紫色)
    fig.add_trace(go.Scatter(
        x=dates,
        y=df['Score_Relative'],
        name='🚀 跨资产抛物线脱节分位数 (15%)',
        line=dict(color='#FF1493', width=1.5, dash='dot'),
        hovertemplate='相对溢价分项: %{y:.1f}分<extra></extra>'
    ))

    # 阈值水平参考线
    fig.add_hline(y=70, line=dict(color='#DC143C', width=1.5, dash='dash'), annotation_text="极度泡沫警戒线 (70分)", annotation_position="top right")
    fig.add_hline(y=50, line=dict(color='#A9A9A9', width=1.0, dash='dot'), annotation_text="中枢中立线 (50分)", annotation_position="top right")
    fig.add_hline(y=20, line=dict(color='#20B2AA', width=1.5, dash='dash'), annotation_text="深度出清买入区 (20分)", annotation_position="bottom right")

    # 危险区背景填充
    fig.add_hrect(y0=70, y1=100, fillcolor="#DC143C", opacity=0.08, line_width=0)
    fig.add_hrect(y0=0, y1=20, fillcolor="#20B2AA", opacity=0.08, line_width=0)

    # 初始聚焦时间范围设置
    end_date = dates.iloc[-1]
    if default_range == "1M":
        start_date = end_date - pd.DateOffset(months=1)
    elif default_range == "3M":
        start_date = end_date - pd.DateOffset(months=3)
    elif default_range == "6M":
        start_date = end_date - pd.DateOffset(months=6)
    elif default_range == "1Y":
        start_date = end_date - pd.DateOffset(years=1)
    elif default_range == "3Y":
        start_date = end_date - pd.DateOffset(years=3)
    elif default_range == "5Y":
        start_date = end_date - pd.DateOffset(years=5)
    else:
        start_date = dates.iloc[0]

    fig.update_layout(
        xaxis=dict(
            range=[start_date, end_date],
            rangeslider=dict(visible=True, thickness=0.04, bgcolor="#f1f2f6"),
            # 🌟 独立层级 1 (Top: y=1.14): 时间快捷缩放按钮组
            rangeselector=dict(
                buttons=[
                    dict(count=1, label="1月", step="month", stepmode="backward"),
                    dict(count=3, label="3月", step="month", stepmode="backward"),
                    dict(count=6, label="半年", step="month", stepmode="backward"),
                    dict(count=1, label="1年", step="year", stepmode="backward"),
                    dict(count=3, label="3年", step="year", stepmode="backward"),
                    dict(step="all", label="全部")
                ],
                x=0.0,
                y=1.14,
                xanchor="left",
                yanchor="bottom",
                bgcolor="#f5f6fa",
                bordercolor="#dcdde1",
                borderwidth=1,
                font=dict(color="#2f3542", size=11)
            ),
            type="date"
        ),
        yaxis=dict(
            title="雷达评分 (0 ~ 100 分)",
            range=[0, 105],
            autorange=False,
            gridcolor="#E5E5E5"
        ),
        # 🌟 独立层级 2 (Middle: y=1.02): 白底黑字图例卡片，零重叠
        legend=dict(
            bgcolor="rgba(255, 255, 255, 0.95)",
            bordercolor="#dcdde1",
            borderwidth=1.2,
            font=dict(color="#111111", size=11),
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="left",
            x=0.0
        ),
        plot_bgcolor="#FFFFFF",
        paper_bgcolor="#FFFFFF",
        hovermode="x unified",
        margin=dict(l=50, r=30, t=105, b=45),
        height=530
    )

    return fig


def build_layer3_breadth_chart(df, default_range="1Y"):
    """
    绘制 Layer 3: 前 15 大核心成分股 50MA 内部广度与标的价格顶背离监控图
    双 Y 轴架构：
    - 左 Y 轴：站上 50MA 比例 (0~100%)
    - 右 Y 轴：IGV 标的收盘价 (自适应缩放)
    """
    dates = pd.to_datetime(df['date'])

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    # 1. 广度曲线 (左 Y 轴)
    breadth_pct = df['Breadth_50'] * 100.0
    fig.add_trace(go.Scatter(
        x=dates,
        y=breadth_pct,
        name='<b>📊 15大成分股站上50MA比例 (%)</b>',
        line=dict(color='#8B4513', width=2.2),
        fill='tozeroy',
        fillcolor='rgba(139, 69, 19, 0.06)',
        hovertemplate='站上50MA比例: %{y:.1f}%<extra></extra>'
    ), secondary_y=False)

    # 2. IGV 价格走势 (右 Y 轴，用于肉眼直接比对顶背离)
    fig.add_trace(go.Scatter(
        x=dates,
        y=df['IGV'],
        name='💻 IGV 收盘价格 (USD)',
        line=dict(color='#1E90FF', width=1.8, dash='solid'),
        hovertemplate='IGV 价格: $%{y:.2f}<extra></extra>'
    ), secondary_y=True)

    # 广度参考线 (左轴)
    fig.add_hline(y=50, line=dict(color='#FF1493', width=1.2, dash='dash'), annotation_text="多空平衡线 (50%)", annotation_position="top left", secondary_y=False)
    fig.add_hline(y=40, line=dict(color='#DC143C', width=1.5, dash='dot'), annotation_text="广度严重坍塌线 (40%)", annotation_position="bottom left", secondary_y=False)
    fig.add_hrect(y0=0, y1=40, fillcolor="#DC143C", opacity=0.08, line_width=0, secondary_y=False)

    # 时间范围
    end_date = dates.iloc[-1]
    if default_range == "1M":
        start_date = end_date - pd.DateOffset(months=1)
    elif default_range == "3M":
        start_date = end_date - pd.DateOffset(months=3)
    elif default_range == "6M":
        start_date = end_date - pd.DateOffset(months=6)
    elif default_range == "1Y":
        start_date = end_date - pd.DateOffset(years=1)
    elif default_range == "3Y":
        start_date = end_date - pd.DateOffset(years=3)
    elif default_range == "5Y":
        start_date = end_date - pd.DateOffset(years=5)
    else:
        start_date = dates.iloc[0]

    fig.update_layout(
        xaxis=dict(
            range=[start_date, end_date],
            rangeslider=dict(visible=True, thickness=0.04, bgcolor="#f1f2f6"),
            # 🌟 独立层级 1 (Top: y=1.14): 时间快捷缩放按钮组
            rangeselector=dict(
                buttons=[
                    dict(count=1, label="1月", step="month", stepmode="backward"),
                    dict(count=3, label="3月", step="month", stepmode="backward"),
                    dict(count=6, label="半年", step="month", stepmode="backward"),
                    dict(count=1, label="1年", step="year", stepmode="backward"),
                    dict(count=3, label="3年", step="year", stepmode="backward"),
                    dict(step="all", label="全部")
                ],
                x=0.0,
                y=1.14,
                xanchor="left",
                yanchor="bottom",
                bgcolor="#f5f6fa",
                bordercolor="#dcdde1",
                borderwidth=1,
                font=dict(color="#2f3542", size=11)
            ),
            type="date"
        ),
        yaxis=dict(
            title="前15大站上50MA比例 (%)",
            range=[-2, 105],
            autorange=False,
            gridcolor="#E5E5E5"
        ),
        yaxis2=dict(
            title="IGV 价格 (USD)",
            autorange=True,
            showgrid=False
        ),
        # 🌟 独立层级 2 (Middle: y=1.02): 白底黑字图例卡片，零重叠
        legend=dict(
            bgcolor="rgba(255, 255, 255, 0.95)",
            bordercolor="#dcdde1",
            borderwidth=1.2,
            font=dict(color="#111111", size=11),
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="left",
            x=0.0
        ),
        plot_bgcolor="#FFFFFF",
        paper_bgcolor="#FFFFFF",
        hovermode="x unified",
        margin=dict(l=50, r=50, t=105, b=45),
        height=530
    )

    return fig


def render_industry_bubble_tab():
    """
    行业微观内生泡沫雷达看板的主渲染入口
    """
    st.header("📡 行业微观内生泡沫雷达监控看板 —— IGV (云计算与企业软件)")
    st.caption("【首发先行标的】聚焦展示 **Layer 2 (0~100 综合与4维度分项雷达)** 与 **Layer 3 (15大核心成分股50MA内部广度与顶背离)**")

    # 1. 加载数据
    df, source_tag = load_igv_radar_data()

    if df.empty:
        st.error("❌ 无法加载 IGV 微观雷达数据，请检查本地数据集或网络。")
        return

    # 2. 顶部时间范围筛选栏
    col_t1, col_t2 = st.columns([3, 5])
    with col_t1:
        range_label = st.selectbox(
            "⏱️ 初始图表聚焦视野 (自动自适应 Y 轴):",
            options=["近 1 年", "近 3 个月", "近 6 个月", "近 3 年", "近 5 年", "全历史 14.5 年"],
            index=0
        )
    range_map = {
        "近 3 个月": "3M",
        "近 6 个月": "6M",
        "近 1 年": "1Y",
        "近 3 年": "3Y",
        "近 5 年": "5Y",
        "全历史 14.5 年": "ALL"
    }
    sel_range = range_map[range_label]

    latest_row = df.iloc[-1]
    latest_date = str(latest_row['date'])[:10]

    with col_t2:
        st.markdown(
            f"<div style='padding-top: 25px; text-align: right; color: gray; font-size: 13px;'>"
            f"数据源状态: <code>🟢 {source_tag}</code> | 最新数据基准日: <b>{latest_date}</b> | 样本长度: <b>{len(df)} 交易日</b>"
            f"</div>",
            unsafe_allow_html=True
        )

    st.markdown("---")

    # ------------------------------------------------------------------
    # 核心监控卡片区: Layer 2 与 Layer 3 核心状态
    # ------------------------------------------------------------------
    st.subheader("🎯 最新收盘核心决策雷达指标 (Latest Radar State)")

    score_comp = latest_row.get('Composite_Radar_Score', 0.0)
    score_dyn = latest_row.get('Score_Dynamics', 0.0)
    score_val = latest_row.get('Score_Valuation', 0.0)
    score_brd = latest_row.get('Score_Breadth', 0.0)
    score_rel = latest_row.get('Score_Relative', 0.0)
    breadth_pct = latest_row.get('Breadth_50', 0.0) * 100.0

    # 状态定性
    if score_comp >= 70.0:
        status_banner = "🔴 极度泡沫危险区 (Extreme Bubble Zone) —— 结构脆弱，严防崩塌"
        status_color = "red"
    elif score_comp >= 55.0:
        status_banner = "🟡 偏热警戒区 (Overheating Warning) —— 密切观察成分股广度分化"
        status_color = "orange"
    elif score_comp <= 20.0:
        status_banner = "🔵 深度出清超跌区 (Deep Value / Clear-out) —— 潜在黄金坑区间"
        status_color = "blue"
    else:
        status_banner = "🟢 健康常态中枢 (Healthy Equilibrium) —— 顺势持有"
        status_color = "green"

    st.markdown(
        f"<div style='background-color: rgba(240,242,246,0.6); padding: 12px 18px; border-radius: 8px; border-left: 5px solid {status_color}; margin-bottom: 15px;'>"
        f"<span style='font-size: 16px; font-weight: bold;'>雷达定性判定：{status_banner}</span>"
        f"</div>",
        unsafe_allow_html=True
    )

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("🎯 综合雷达总分", f"{score_comp:.1f} / 100", "高危线 >= 70" if score_comp >= 70 else ("偏热 >= 55" if score_comp >= 55 else "中立区"))
    c2.metric("⚡ 动力学分位数", f"{score_dyn:.1f} 分", f"权重 35%")
    c3.metric("💎 估值分位数", f"{score_val:.1f} 分", f"权重 25%")
    c4.metric("📉 广度顶背离", f"{score_brd:.1f} 分", f"权重 25%")
    c5.metric("🚀 相对溢价偏离", f"{score_rel:.1f} 分", f"权重 15%")

    st.markdown("---")

    # ------------------------------------------------------------------
    # 核心展示区 1: Layer 2 综合与 4 大独立分项演变图
    # ------------------------------------------------------------------
    st.subheader("📊 Layer 2: 0~100 综合与 4 维度独立雷达演变全景 (交互式)")
    st.caption("💡 **交互技巧**：可点击上方图例任意勾选/隐藏分项，单独审查某一个单项指标的独立走势；鼠标悬停可查看逐日精确数值。")
    fig_layer2 = build_layer2_radar_chart(df, default_range=sel_range)
    st.plotly_chart(fig_layer2, use_container_width=True)

    st.markdown("---")

    # ------------------------------------------------------------------
    # 核心展示区 2: Layer 3 内部 15 大核心成分股 50MA 广度与顶背离图
    # ------------------------------------------------------------------
    st.subheader("📉 Layer 3: 内部 15 大核心成分股 50MA 广度与顶背离深度剖析")
    st.caption("💡 **顶背离第一性原理**：当 IGV 价格处于新高区间（右轴），而站上 50MA 的股票比例却自高位跌破 50% 甚至 40% 时（左轴），代表仅剩少数巨头虚托指数，内部大面积资金已经提前溃退！")

    fig_layer3 = build_layer3_breadth_chart(df, default_range=sel_range)
    st.plotly_chart(fig_layer3, use_container_width=True)

    # 15 大核心成分股最新穿透透视表
    with st.expander("🔍 展开穿透查看：前 15 大核心软件成分股最新 50MA 多空分布矩阵", expanded=False):
        st.markdown("下表实时展示 IGV 权重前 15 大核心成分股相对自身 50MA 的多空位置：")
        const_rows = []
        for c in CORE_CONSTITUENTS:
            if c in df.columns:
                p_cur = df[c].iloc[-1]
                ma50_cur = df[c].rolling(50).mean().iloc[-1]
                diff_pct = (p_cur - ma50_cur) / ma50_cur * 100.0
                is_above = p_cur > ma50_cur
                const_rows.append({
                    "股票代码": c,
                    "最新收盘价 (USD)": f"${p_cur:.2f}",
                    "50日生命均线 (MA50)": f"${ma50_cur:.2f}",
                    "距MA50偏离": f"{diff_pct:+.2f}%",
                    "多空状态": "🟢 站上生命线" if is_above else "🔴 跌破破位"
                })
        if const_rows:
            df_const_table = pd.DataFrame(const_rows)
            st.dataframe(df_const_table, use_container_width=True)
            above_count = sum(1 for r in const_rows if "🟢" in r["多空状态"])
            st.info(f"📌 **当前广度概况**：前 15 大成分股中，共有 **{above_count} / {len(const_rows)}** 家公司站上 50MA（占比 **{above_count/len(const_rows)*100:.1f}%**）。")

    st.markdown("---")

    # ------------------------------------------------------------------
    # 辅助参考区: Layer 1 标的价格与均线生命线 (折叠展示)
    # ------------------------------------------------------------------
    with st.expander("📈 辅助参考：Layer 1 标的价格决策与均线系统 (MA20 / MA50 / MA200)", expanded=False):
        dates = pd.to_datetime(df['date'])
        fig_l1 = go.Figure()
        fig_l1.add_trace(go.Scatter(x=dates, y=df['IGV'], name='IGV 价格', line=dict(color='#1f77b4', width=2.0)))
        fig_l1.add_trace(go.Scatter(x=dates, y=df['MA50'], name='MA50 生命周期线', line=dict(color='#ff7f0e', width=1.2, dash='dash')))
        fig_l1.add_trace(go.Scatter(x=dates, y=df['MA200'], name='MA200 长期牛熊线', line=dict(color='#2ca02c', width=1.2, dash='dot')))
        fig_l1.update_layout(
            title="IGV 标的价格与均线系统",
            xaxis=dict(type="date"),
            yaxis=dict(title="价格 (USD)", autorange=True),
            legend=dict(bgcolor="rgba(255, 255, 255, 0.95)", font=dict(color="#000000")),
            plot_bgcolor="#FFFFFF",
            paper_bgcolor="#FFFFFF",
            height=380
        )
        st.plotly_chart(fig_l1, use_container_width=True)

    # ------------------------------------------------------------------
    # 交付物与全周期审计底稿下载
    # ------------------------------------------------------------------
    st.subheader("📥 官方全周期实证对账底稿与高清图谱下载")
    col_d1, col_d2 = st.columns(2)

    with col_d1:
        if os.path.exists(LOCAL_EXCEL_PATH):
            with open(LOCAL_EXCEL_PATH, "rb") as f:
                st.download_button(
                    label="📊 下载 IGV 微观雷达全周期对账工作簿 (.xlsx)",
                    data=f.read(),
                    file_name="宏观反身性阿尔法模型_IGV微观雷达全周期对账表.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True
                )
        else:
            st.markdown(f"📥 [点击从 GitHub 下载 Excel 底稿]({GITHUB_RAW_EXCEL})")

    with col_d2:
        if os.path.exists(LOCAL_CHART_PNG):
            with open(LOCAL_CHART_PNG, "rb") as f:
                st.download_button(
                    label="🖼️ 下载出版级 4 层全景高清图谱 (.png)",
                    data=f.read(),
                    file_name="宏观反身性阿尔法模型_IGV微观雷达4层全景图谱.png",
                    mime="image/png",
                    use_container_width=True
                )
        else:
            st.markdown(f"🖼️ [点击从 GitHub 查看高清图谱]({GITHUB_RAW_PNG})")
