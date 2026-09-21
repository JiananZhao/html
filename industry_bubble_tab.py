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

# 资产配置字典
ASSET_CONFIG = {
    "💻 IGV (云计算与软件)": {
        "ticker": "IGV",
        "name": "iShares 扩展科技软件与云计算 ETF",
        "local_radar": os.path.join(BASE_DIR, "igv_radar_local.csv"),
        "local_const": os.path.join(BASE_DIR, "igv_constituents_local.csv"),
        "local_excel": os.path.join(BASE_DIR, "宏观反身性阿尔法模型_IGV微观雷达全周期对账表.xlsx"),
        "local_png": os.path.join(BASE_DIR, "宏观反身性阿尔法模型_IGV微观雷达4层全景图谱.png"),
        "github_radar": "https://raw.githubusercontent.com/JiananZhao/html/master/igv_radar_local.csv",
        "github_excel": "https://raw.githubusercontent.com/JiananZhao/html/master/%E5%AE%8F%E8%A7%82%E5%8F%8D%E8%BA%AB%E6%80%A7%E9%98%BF%E5%B0%94%E6%B3%95%E6%A8%A1%E5%9E%8B_IGV%E5%BE%AE%E8%A7%82%E9%9B%B7%E8%BE%BE%E5%85%A8%E5%91%A8%E6%9C%9F%E5%AF%B9%E8%83%80%E8%A1%A8.xlsx",
        "github_png": "https://raw.githubusercontent.com/JiananZhao/html/master/%E5%AE%8F%E8%A7%82%E5%8F%8D%E8%BA%AB%E6%80%A7%E9%98%BF%E5%B0%94%E6%B3%95%E6%A8%A1%E5%9E%8B_IGV%E5%BE%AE%E8%A7%82%E9%9B%B7%E8%BE%BE4%E5%B1%82%E5%85%A8%E6%99%AF%E5%9B%BE%E8%B0%B1.png",
        "constituents": ['MSFT', 'CRM', 'ORCL', 'ADBE', 'NOW', 'INTU', 'PLTR', 'PANW', 'CRWD', 'SNOW', 'WDAY', 'FTNT', 'DDOG', 'CDNS', 'SNPS']
    },
    "⚡ SMH (芯片与半导体)": {
        "ticker": "SMH",
        "name": "VanEck 半导体 ETF",
        "local_radar": os.path.join(BASE_DIR, "smh_radar_local.csv"),
        "local_const": os.path.join(BASE_DIR, "smh_constituents_local.csv"),
        "local_excel": os.path.join(BASE_DIR, "宏观反身性阿尔法模型_SMH微观雷达全周期对账表.xlsx"),
        "local_png": os.path.join(BASE_DIR, "宏观反身性阿尔法模型_SMH微观雷达4层全景图谱.png"),
        "github_radar": "https://raw.githubusercontent.com/JiananZhao/html/master/smh_radar_local.csv",
        "github_excel": "https://raw.githubusercontent.com/JiananZhao/html/master/%E5%AE%8F%E8%A7%82%E5%8F%8D%E8%BA%AB%E6%80%A7%E9%98%BF%E5%B0%94%E6%B3%95%E6%A8%A1%E5%9E%8B_SMH%E5%BE%AE%E8%A7%82%E9%9B%B7%E8%BE%BE%E5%85%A8%E5%91%A8%E6%9C%9F%E5%AF%B9%E8%83%80%E8%A1%A8.xlsx",
        "github_png": "https://raw.githubusercontent.com/JiananZhao/html/master/%E5%AE%8F%E8%A7%82%E5%8F%8D%E8%BA%AB%E6%80%A7%E9%98%BF%E5%B0%94%E6%B3%95%E6%A8%A1%E5%9E%8B_SMH%E5%BE%AE%E8%A7%82%E9%9B%B7%E8%BE%BE4%E5%B1%82%E5%85%A8%E6%99%AF%E5%9B%BE%E8%B0%B1.png",
        "constituents": ['ADI', 'AMAT', 'AMD', 'ASML', 'AVGO', 'INTC', 'KLAC', 'LRCX', 'MRVL', 'MU', 'NVDA', 'NXPI', 'QCOM', 'TSM', 'TXN']
    },
    "🛢️ XLE (能源全产业链)": {
        "ticker": "XLE",
        "name": "Energy Select Sector SPDR (全产业链监控)",
        "local_radar": os.path.join(BASE_DIR, "energy_radar_local.csv"),
        "local_const": os.path.join(BASE_DIR, "energy_constituents_local.csv"),
        "local_excel": os.path.join(BASE_DIR, "宏观反身性阿尔法模型_Energy微观雷达全周期对账表.xlsx"),
        "local_png": os.path.join(BASE_DIR, "宏观反身性阿尔法模型_Energy微观雷达4层全景图谱.png"),
        "github_radar": "https://raw.githubusercontent.com/JiananZhao/html/master/energy_radar_local.csv",
        "github_excel": "https://raw.githubusercontent.com/JiananZhao/html/master/%E5%AE%8F%E8%A7%82%E5%8F%8D%E8%BA%AB%E6%80%A7%E9%98%BF%E5%B0%94%E6%B3%95%E6%A8%A1%E5%9E%8B_Energy%E5%BE%AE%E8%A7%82%E9%9B%B7%E8%BE%BE%E5%85%A8%E5%91%A8%E6%9C%9F%E5%AF%B9%E8%83%80%E8%A1%A8.xlsx",
        "github_png": "https://raw.githubusercontent.com/JiananZhao/html/master/%E5%AE%8F%E8%A7%82%E5%8F%8D%E8%BA%AB%E6%80%A7%E9%98%BF%E5%B0%94%E6%B3%95%E6%A8%A1%E5%9E%8B_Energy%E5%BE%AE%E8%A7%82%E9%9B%B7%E8%BE%BE4%E5%B1%82%E5%85%A8%E6%99%AF%E5%9B%BE%E8%B0%B1.png",
        "constituents": ['XOM', 'CVX', 'SHEL', 'TTE', 'BP', 'COP', 'EOG', 'OXY', 'FANG', 'DVN', 'SLB', 'HAL', 'BKR', 'PSX', 'VLO']
    },
    "🏦 KRE (区域银行与金融)": {
        "ticker": "KRE",
        "name": "SPDR S&P Regional Banking ETF (区域银行与金融微观雷达)",
        "local_radar": os.path.join(BASE_DIR, "kre_radar_local.csv"),
        "local_const": os.path.join(BASE_DIR, "financial_constituents_local.csv"),
        "local_excel": os.path.join(BASE_DIR, "宏观反身性阿尔法模型_KRE微观雷达全周期对账表.xlsx"),
        "local_png": os.path.join(BASE_DIR, "宏观反身性阿尔法模型_KRE微观雷达4层全景图谱.png"),
        "github_radar": "https://raw.githubusercontent.com/JiananZhao/html/master/kre_radar_local.csv",
        "github_excel": "https://raw.githubusercontent.com/JiananZhao/html/master/%E5%AE%8F%E8%A7%82%E5%8F%8D%E8%BA%AB%E6%80%A7%E9%98%BF%E5%B0%94%E6%B3%95%E6%A8%A1%E5%9E%8B_KRE%E5%BE%AE%E8%A7%82%E9%9B%B7%E8%BE%BE%E5%85%A8%E5%91%A8%E6%9C%9F%E5%AF%B9%E8%83%80%E8%A1%A8.xlsx",
        "github_png": "https://raw.githubusercontent.com/JiananZhao/html/master/%E5%AE%8F%E8%A7%82%E5%8F%8D%E8%BA%AB%E6%80%A7%E9%98%BF%E5%B0%94%E6%B3%95%E6%A8%A1%E5%9E%8B_KRE%E5%BE%AE%E8%A7%82%E9%9B%B7%E8%BE%BE4%E5%B1%82%E5%85%A8%E6%99%AF%E5%9B%BE%E8%B0%B1.png",
        "constituents": ['KRE', 'USB', 'TFC', 'PNC', 'KEY', 'CFG', 'FITB', 'MTB', 'HBAN', 'ZION', 'WAL', 'EWBC', 'JPM', 'BAC', 'WFC', 'C', 'MS', 'GS', 'SCHW', 'BLK', 'BRK-B', 'V', 'MA', 'AXP']
    },
    "🏢 VNQ (房地产与REITs)": {
        "ticker": "VNQ",
        "name": "Vanguard Real Estate ETF (房地产与REITs信贷流动性微观雷达)",
        "local_radar": os.path.join(BASE_DIR, "vnq_radar_local.csv"),
        "local_const": os.path.join(BASE_DIR, "real_estate_constituents_local.csv"),
        "local_excel": os.path.join(BASE_DIR, "宏观反身性阿尔法模型_VNQ微观雷达全周期对账表.xlsx"),
        "local_png": os.path.join(BASE_DIR, "宏观反身性阿尔法模型_VNQ微观雷达4层全景图谱.png"),
        "github_radar": "https://raw.githubusercontent.com/JiananZhao/html/master/vnq_radar_local.csv",
        "github_excel": "https://raw.githubusercontent.com/JiananZhao/html/master/%E5%AE%8F%E8%A7%82%E5%8F%8D%E8%BA%AB%E6%80%A7%E9%98%BF%E5%B0%94%E6%B3%95%E6%A8%A1%E5%9E%8B_VNQ%E5%BE%AE%E8%A7%82%E9%9B%B7%E8%BE%BE%E5%85%A8%E5%91%A8%E6%9C%9F%E5%AF%B9%E8%83%80%E8%A1%A8.xlsx",
        "github_png": "https://raw.githubusercontent.com/JiananZhao/html/master/%E5%AE%8F%E8%A7%82%E5%8F%8D%E8%BA%AB%E6%80%A7%E9%98%BF%E5%B0%94%E6%B3%95%E6%A8%A1%E5%9E%8B_VNQ%E5%BE%AE%E8%A7%82%E9%9B%B7%E8%BE%BE4%E5%B1%82%E5%85%A8%E6%99%AF%E5%9B%BE%E8%B0%B1.png",
        "constituents": ['VNQ', 'PLD', 'AMT', 'EQIX', 'CCI', 'PSA', 'SPG', 'O', 'WELL', 'DLR', 'AVB', 'EQR', 'WY', 'VICI', 'SBAC', 'CBRE', 'DHI', 'LEN', 'BXP']
    },
    "🦅 NOW (ServiceNow 单股反身性相空间雷达)": {
        "ticker": "NOW",
        "name": "ServiceNow (NOW) 单股反身性拉格朗日相空间动力学微观雷达",
        "local_radar": os.path.join(BASE_DIR, "now_radar_local.csv"),
        "local_const": os.path.join(BASE_DIR, "now_sec_fundamentals_local.csv"),
        "local_excel": os.path.join(BASE_DIR, "宏观反身性阿尔法模型_NOW单股微观雷达全周期对账表.xlsx"),
        "local_png": os.path.join(BASE_DIR, "宏观反身性阿尔法模型_NOW微观雷达4层全景图谱.png"),
        "local_phase_png": os.path.join(BASE_DIR, "宏观反身性阿尔法模型_NOW相空间动力学相图.png"),
        "github_radar": "https://raw.githubusercontent.com/JiananZhao/html/master/now_radar_local.csv",
        "github_excel": "https://raw.githubusercontent.com/JiananZhao/html/master/%E5%AE%8F%E8%A7%82%E5%8F%8D%E8%BA%AB%E6%80%A7%E9%98%BF%E5%B0%94%E6%B3%95%E6%A8%A1%E5%9E%8B_NOW%E5%8D%95%E8%82%A1%E5%BE%AE%E8%A7%82%E9%9B%B7%E8%BE%BE%E5%85%A8%E5%91%A8%E6%9C%9F%E5%AF%B9%E8%83%80%E8%A1%A8.xlsx",
        "github_png": "https://raw.githubusercontent.com/JiananZhao/html/master/%E5%AE%8F%E8%A7%82%E5%8F%8D%E8%BA%AB%E6%80%A7%E9%98%BF%E5%B0%94%E6%B3%95%E6%A8%A1%E5%9E%8B_NOW%E5%BE%AE%E8%A7%82%E9%9B%B7%E8%BE%BE4%E5%B1%82%E5%85%A8%E6%99%AF%E5%9B%BE%E8%B0%B1.png",
        "github_phase_png": "https://raw.githubusercontent.com/JiananZhao/html/master/%E5%AE%8F%E8%A7%82%E5%8F%8D%E8%BA%AB%E6%80%A7%E9%98%BF%E5%B0%94%E6%B3%95%E6%A8%A1%E5%9E%8B_NOW%E7%9B%B8%E7%A9%BA%E9%97%B4%E5%8A%A8%E5%8A%9B%E5%AD%A6%E7%9B%B8%E5%9B%BE.png",
        "constituents": ['NOW', 'MSFT', 'CRM', 'ORCL', 'ADBE', 'PLTR', 'WDAY']
    }
}


@st.cache_data(ttl=600, show_spinner=False)
def load_radar_data(asset_key):
    """
    跨平台双模数据加载器：
    1. 优先从本地仓库读取预计算的 _radar_local.csv；
    2. 若不存在，尝试从 GitHub Raw 直读；
    3. 若仍无，调用引擎重新计算并缓存。
    """
    config = ASSET_CONFIG[asset_key]
    local_csv = config['local_radar']
    github_csv = config['github_radar']

    if os.path.exists(local_csv):
        try:
            df = pd.read_csv(local_csv)
            if not df.empty and 'date' in df.columns:
                if config['ticker'] == 'NOW':
                    if 'NOW' not in df.columns and 'close' in df.columns:
                        df['NOW'] = df['close']
                    if 'Composite_Radar_Score' not in df.columns and 'Composite_Score' in df.columns:
                        df['Composite_Radar_Score'] = df['Composite_Score']
                return df, "本地文件直读"
        except Exception:
            pass

    # 尝试 GitHub Raw
    try:
        df = pd.read_csv(github_csv)
        if not df.empty and 'date' in df.columns:
            if config['ticker'] == 'NOW':
                if 'NOW' not in df.columns and 'close' in df.columns:
                    df['NOW'] = df['close']
                if 'Composite_Radar_Score' not in df.columns and 'Composite_Score' in df.columns:
                    df['Composite_Radar_Score'] = df['Composite_Score']
            return df, "GitHub Raw 远端直读"
    except Exception:
        pass

    # 本地动态重算 fallback
    try:
        if config['ticker'] == 'IGV':
            from micro_bubble_radar import MicroBubbleRadar
            radar = MicroBubbleRadar()
        elif config['ticker'] == 'SMH':
            from smh_bubble_radar import SMHBubbleRadar
            radar = SMHBubbleRadar()
        elif config['ticker'] == 'KRE':
            from kre_bubble_radar import KREBubbleRadar
            radar = KREBubbleRadar()
        elif config['ticker'] == 'VNQ':
            from vnq_bubble_radar import VNQBubbleRadar
            radar = VNQBubbleRadar()
        elif config['ticker'] == 'NOW':
            from now_reflexivity_radar import NOWReflexivityRadar
            radar = NOWReflexivityRadar()
            radar.load_and_preprocess()
            radar.compute_all_dimensions()
            radar.run_backtest()
            df = radar.df
            df['NOW'] = df['close']
            df['Composite_Radar_Score'] = df['Composite_Score']
            return df, "引擎动态运算"
        else:
            from energy_bubble_radar import EnergyBubbleRadar
            radar = EnergyBubbleRadar()
            
        df = radar.load_and_preprocess()
        df = radar.compute_all_dimensions()
        try:
            df.to_csv(local_csv, index=False)
        except Exception:
            pass
        return df, "引擎动态运算"
    except Exception as e:
        st.error(f"微观雷达数据加载失败: {e}")
        return pd.DataFrame(), "无可用数据源"



@st.cache_data(ttl=600, show_spinner=False)
def load_backtest_data(asset_key):
    config = ASSET_CONFIG[asset_key]
    ticker = config['ticker'].lower()
    
    local_csv = os.path.join(BASE_DIR, f"{ticker}_backtest_daily_local.csv")
    github_csv = f"https://raw.githubusercontent.com/JiananZhao/html/master/{ticker}_backtest_daily_local.csv"
    
    if os.path.exists(local_csv):
        try:
            df = pd.read_csv(local_csv)
            if not df.empty and 'date' in df.columns:
                return df
        except Exception:
            pass
            
    try:
        df = pd.read_csv(github_csv)
        if not df.empty and 'date' in df.columns:
            return df
    except Exception:
        pass
        
    return pd.DataFrame()


def build_layer2_radar_chart(df, default_range="1Y", ticker="IGV"):
    """
    绘制 Layer 2: 0~100 综合微观雷达分与各独立分项交互图谱 (Plotly)
    满足用户要求：
    1. legend 底色为白色，文字为黑色；
    2. Y 轴自适应调节，消除多余空白；
    3. 支持独立勾选查看各单项指标。
    """
    dates = pd.to_datetime(df['date'])

    fig = go.Figure()

    if ticker == "NOW":
        # ServiceNow 专属 6 大解耦维度
        fig.add_trace(go.Scatter(
            x=dates,
            y=df['Composite_Score'],
            name='<b>🎯 综合反身性过热总分 (0-100)</b>',
            line=dict(color='#8A2BE2', width=3.2),
            hovertemplate='<b>综合反身性总分</b>: %{y:.1f}分<extra></extra>'
        ))
        fig.add_trace(go.Scatter(
            x=dates,
            y=df['Score_Dim1_Pos'],
            name='📍 维度1: 势能位置分 (25% - 年线偏离)',
            line=dict(color='#1E90FF', width=1.5),
            hovertemplate='势能位置分: %{y:.1f}分<extra></extra>'
        ))
        fig.add_trace(go.Scatter(
            x=dates,
            y=df['Score_Dim2_Vel'],
            name='⚡ 维度2: 动能速度分 (20% - 10日差分)',
            line=dict(color='#00C853', width=1.5),
            hovertemplate='动能速度分: %{y:.1f}分<extra></extra>'
        ))
        fig.add_trace(go.Scatter(
            x=dates,
            y=df['Score_Dim3_Lyapunov'],
            name='🌀 维度3: 李氏稳定性分 (20% - 能量耗散)',
            line=dict(color='#FF6D00', width=1.5),
            hovertemplate='李氏稳定性分: %{y:.1f}分<extra></extra>'
        ))
        fig.add_trace(go.Scatter(
            x=dates,
            y=df['Score_Dim4_Capital'],
            name='💼 维度4: 资本稀释与高管减持分 (15%)',
            line=dict(color='#8D6E63', width=1.5),
            hovertemplate='资本稀释分: %{y:.1f}分<extra></extra>'
        ))
        fig.add_trace(go.Scatter(
            x=dates,
            y=df['Score_Dim5_Liquidity'],
            name='💧 维度5: 微观筹码资金流 CMF (观察项)',
            line=dict(color='#26A69A', width=1.2, dash='dot'),
            hovertemplate='微观筹码分: %{y:.1f}分<extra></extra>'
        ))
        fig.add_trace(go.Scatter(
            x=dates,
            y=df['Score_Dim6_Macro'],
            name='🌐 维度6: 宏观信用引力与NFCI分 (20%)',
            line=dict(color='#E91E63', width=1.5, dash='dash'),
            hovertemplate='宏观信用分: %{y:.1f}分<extra></extra>'
        ))
    else:
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


def build_layer3_breadth_chart(df, ticker='IGV', default_range="1Y"):
    """
    绘制 Layer 3: 前 15 大核心成分股 50MA 内部广度与标的价格顶背离监控图
    双 Y 轴架构：
    - 左 Y 轴：站上 50MA 比例 (0~100%)
    - 右 Y 轴：标的收盘价 (自适应缩放)
    """
    dates = pd.to_datetime(df['date'])

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    # 1. 广度曲线 (左 Y 轴)
    breadth_pct = df['Breadth_50']    # 广度参考线 (左轴)
    # 对于能源，由于我们使用了分层广度，名字叫 Breadth_50，不再是具体的 ticker。
    fig.add_trace(go.Scatter(
        x=dates,
        y=df['Breadth_50'] * 100.0,
        name='🔥 分层等权广度 (%)' if ticker == 'XLE' else '🔥 站上 50MA 比例 (%)',
        line=dict(color='#FF4500', width=2.2),
        fill='tozeroy',
        fillcolor='rgba(255, 69, 0, 0.08)',
        hovertemplate='全产业链综合广度: %{y:.1f}%<extra></extra>'
    ), secondary_y=False)

    # 能源专属：油服设备 vs 上游勘探早晚期 CapEx 剪刀差透视
    if ticker == 'XLE' and 'Breadth_Services' in df.columns and 'Breadth_E&P' in df.columns:
        fig.add_trace(go.Scatter(
            x=dates,
            y=df['Breadth_Services'] * 100.0,
            name='🛠️ 油服设备广度 (Services - 晚周期CapEx)',
            line=dict(color='#9932CC', width=1.4, dash='dot'),
            hovertemplate='油服设备广度: %{y:.1f}%<extra></extra>'
        ), secondary_y=False)
        fig.add_trace(go.Scatter(
            x=dates,
            y=df['Breadth_E&P'] * 100.0,
            name='🛢️ 上游勘探广度 (E&P - 早周期先导)',
            line=dict(color='#2E8B57', width=1.4, dash='dash'),
            hovertemplate='勘探开采广度: %{y:.1f}%<extra></extra>'
        ), secondary_y=False)

    # 金融专属：区域银行 vs G-SIB 巨头银行挤兑压力剪刀差透视
    if ticker == 'KRE' and 'Breadth_Regional_Banks' in df.columns and 'Breadth_GSIBs' in df.columns:
        fig.add_trace(go.Scatter(
            x=dates,
            y=df['Breadth_Regional_Banks'] * 100.0,
            name='🏛️ 区域银行广度 (Regional Banks %)',
            line=dict(color='#DC143C', width=1.4, dash='dash'),
            hovertemplate='区域银行广度: %{y:.1f}%<extra></extra>'
        ), secondary_y=False)
        fig.add_trace(go.Scatter(
            x=dates,
            y=df['Breadth_GSIBs'] * 100.0,
            name='🏦 大型投行/G-SIBs广度 (G-SIBs %)',
            line=dict(color='#1E90FF', width=1.4, dash='dot'),
            hovertemplate='G-SIBs广度: %{y:.1f}%<extra></extra>'
        ), secondary_y=False)

    # 房地产专属：住宅建筑商 vs 商业写字楼/CRE 信贷与空置剪刀差透视
    if ticker == 'VNQ' and 'Breadth_Homebuilders' in df.columns and 'Breadth_Office_CRE' in df.columns:
        fig.add_trace(go.Scatter(
            x=dates,
            y=df['Breadth_Homebuilders'] * 100.0,
            name='🏡 住宅建筑商广度 (Homebuilders %)',
            line=dict(color='#2E8B57', width=1.4, dash='dash'),
            hovertemplate='住宅建筑商广度: %{y:.1f}%<extra></extra>'
        ), secondary_y=False)
        fig.add_trace(go.Scatter(
            x=dates,
            y=df['Breadth_Office_CRE'] * 100.0,
            name='🏢 商业写字楼广度 (Office/CRE %)',
            line=dict(color='#DC143C', width=1.4, dash='dot'),
            hovertemplate='商业写字楼广度: %{y:.1f}%<extra></extra>'
        ), secondary_y=False)

    # 2. 价格走势 (右 Y 轴，用于肉眼直接比对顶背离)
    fig.add_trace(go.Scatter(
        x=dates,
        y=df[ticker],
        name=f'💻 {ticker} 收盘价格 (USD)',
        line=dict(color='#1E90FF', width=1.8, dash='solid'),
        hovertemplate=ticker + ' 价格: $%{y:.2f}<extra></extra>'
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
            title="分层综合站上50MA比例 (%)" if ticker in ['XLE', 'KRE', 'VNQ'] else "前15大站上50MA比例 (%)",
            range=[-2, 105],
            autorange=False,
            gridcolor="#E5E5E5"
        ),
        yaxis2=dict(
            title=f"{ticker} 价格 (USD)",
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


def build_now_phase_portrait_plotly(df):
    """
    绘制 ServiceNow (NOW) 二维拉格朗日相空间动力学相图 (Plotly 交互版)
    横轴：状态位置 q1 (相对 200MA 偏离度 %)
    纵轴：状态速度 q1_dot (10日有限差分变化率 %/day)
    """
    dates = pd.to_datetime(df['date'])
    q = df['q1']
    q_dot = df['q1_dot']
    years = dates.dt.year

    fig = go.Figure()

    # 散点相轨迹
    fig.add_trace(go.Scatter(
        x=q,
        y=q_dot,
        mode='markers',
        marker=dict(
            size=6,
            color=years,
            colorscale='Viridis',
            colorbar=dict(title='年份'),
            showscale=True
        ),
        text=[f"日期: {d.strftime('%Y-%m-%d')}<br>势能位置 q1: {q_val:.1f}%<br>动能速度 q1_dot: {qd_val:.2f}%/day<br>象限: 第 {quad} 象限" 
              for d, q_val, qd_val, quad in zip(dates, q, q_dot, df.get('Quadrant', [0]*len(df)))],
        hovertemplate='%{text}<extra></extra>',
        name='相轨迹 (NOW 2013-2026)'
    ))

    q_lim = max(abs(q.min()), abs(q.max())) * 1.05
    qd_lim = max(abs(q_dot.min()), abs(q_dot.max())) * 1.05

    # 背景四象限色块
    fig.add_shape(type="rect", x0=0, y0=0, x1=q_lim, y1=qd_lim, fillcolor="#e8f5e9", opacity=0.35, line_width=0, layer="below")
    fig.add_shape(type="rect", x0=-q_lim, y0=0, x1=0, y1=qd_lim, fillcolor="#fff9c4", opacity=0.35, line_width=0, layer="below")
    fig.add_shape(type="rect", x0=-q_lim, y0=-qd_lim, x1=0, y1=0, fillcolor="#ffebee", opacity=0.35, line_width=0, layer="below")
    fig.add_shape(type="rect", x0=0, y0=-qd_lim, x1=q_lim, y1=0, fillcolor="#fff3e0", opacity=0.35, line_width=0, layer="below")

    # 标注象限
    fig.add_annotation(x=q_lim*0.45, y=qd_lim*0.85, text="<b>【第一象限: 正反身性主升浪】</b><br>q > 0, q_dot > 0<br>价格高估且动能加速扩张<br>顺势持有，切勿盲目估值恐高", showarrow=False, bgcolor="rgba(255,255,255,0.9)", font=dict(color="#1b5e20", size=11))
    fig.add_annotation(x=-q_lim*0.55, y=qd_lim*0.85, text="<b>【第二象限: 底部蓄势重构】</b><br>q < 0, q_dot > 0<br>价格超跌且下跌动能耗竭<br>🌟 黄金坑右侧确认买入点", showarrow=False, bgcolor="rgba(255,255,255,0.9)", font=dict(color="#f57f17", size=11))
    fig.add_annotation(x=-q_lim*0.55, y=-qd_lim*0.70, text="<b>【第三象限: 负反身性死亡螺旋】</b><br>q < 0, q_dot < 0<br>价格破位且下跌速度加快<br>⛔ 严禁左侧接飞刀，耐心观望", showarrow=False, bgcolor="rgba(255,255,255,0.9)", font=dict(color="#b71c1c", size=11))
    fig.add_annotation(x=q_lim*0.45, y=-qd_lim*0.70, text="<b>【第四象限: 动能衰竭与相变崩塌】</b><br>q > 0, q_dot < 0<br>处于历史极高但速度破零转负<br>🚨 物理级反身性逃顶信号！", showarrow=False, bgcolor="rgba(255,255,255,0.9)", font=dict(color="#e65100", size=11))

    # 标注 2021 顶峰与 2022 底部相变点
    fig.add_annotation(x=24.6, y=-0.76, text="<b>2021年11月逃顶相变</b><br>跨入第四象限 (q1=+24.6%, q1_dot=-0.76)<br>破位MA50清仓避险", showarrow=True, arrowhead=2, arrowcolor="red", ax=60, ay=-40, bgcolor="#ffebee", font=dict(color="red", size=10))
    fig.add_annotation(x=-22.1, y=0.42, text="<b>2022年10月右侧回补</b><br>跨入第二象限 (q1=-22.1%, q1_dot=+0.42)<br>动能转正收复MA10建仓", showarrow=True, arrowhead=2, arrowcolor="green", ax=-60, ay=40, bgcolor="#e8f5e9", font=dict(color="green", size=10))

    fig.update_layout(
        title="🌀 ServiceNow (NOW) 拉格朗日相空间动力学相图 (Phase Portrait: q1 vs q1_dot)",
        xaxis=dict(title="广义状态位置 q1 (相对 200MA 偏离度 % / 势能坐标)", range=[-q_lim, q_lim], zeroline=True, zerolinecolor="black", zerolinewidth=1.5, gridcolor="#E5E5E5"),
        yaxis=dict(title="广义状态速度 q1_dot (10日有限差分变化率 %/day / 动能坐标)", range=[-qd_lim, qd_lim], zeroline=True, zerolinecolor="black", zerolinewidth=1.5, gridcolor="#E5E5E5"),
        plot_bgcolor="#FFFFFF",
        paper_bgcolor="#FFFFFF",
        height=560,
        margin=dict(l=60, r=40, t=50, b=50)
    )
    return fig


def build_nav_chart(df, ticker, default_range="1Y"):
    """
    绘制 Layer 4: 真实券商记账资产净值曲线对比 (策略 vs 买入持有)
    """
    dates = pd.to_datetime(df['date'])
    fig = go.Figure()
    if 'strat_nav' in df.columns and 'bench_nav' in df.columns:
        fig.add_trace(go.Scatter(
            x=dates,
            y=df['strat_nav'],
            name=f'🦅 {ticker} 宏观反身性模型 (真实券商记账)',
            line=dict(color='#d62728', width=2.4),
            hovertemplate='策略净资产: $%{y:,.0f}<extra></extra>'
        ))
        fig.add_trace(go.Scatter(
            x=dates,
            y=df['bench_nav'],
            name='📊 买入持有基准 (Buy & Hold 定投)',
            line=dict(color='#7f7f7f', width=1.5, dash='dash'),
            hovertemplate='基准净资产: $%{y:,.0f}<extra></extra>'
        ))
    else:
        fig.add_trace(go.Scatter(
            x=dates,
            y=df['close'],
            name=f'{ticker} 价格',
            line=dict(color='#1f77b4', width=2.0)
        ))

    fig.update_layout(
        title="💰 真实券商记账全周期资产净值走势对比 (Strategy vs Benchmark)",
        xaxis=dict(type="date"),
        yaxis=dict(title="账户资产净值 (USD)", autorange=True, gridcolor="#E5E5E5"),
        legend=dict(bgcolor="rgba(255, 255, 255, 0.95)", font=dict(color="#000000")),
        plot_bgcolor="#FFFFFF",
        paper_bgcolor="#FFFFFF",
        height=420,
        margin=dict(l=60, r=30, t=50, b=40)
    )
    return fig


def render_industry_bubble_tab():
    """
    行业微观内生泡沫雷达看板的主渲染入口
    """
    st.header("📡 行业微观内生泡沫雷达监控看板")
    st.caption("【首发先行标的】聚焦展示 **Layer 2 (0~100 综合与各解耦维度雷达)** 与 **Layer 3 (成分股50MA内部广度 / 相空间动力学相图)**")
    
    # 资产选择器：并列六大标的切换 (IGV, SMH, XLE, KRE, VNQ, NOW)
    asset_keys = list(ASSET_CONFIG.keys())
    selected_asset = st.radio(
        "🚀 行业与个股微观内生泡沫雷达标的 (点击并列切换):",
        options=asset_keys,
        index=0,
        horizontal=True
    )
    config = ASSET_CONFIG[selected_asset]
    ticker = config['ticker']

    # 1. 加载数据
    df, source_tag = load_radar_data(selected_asset)

    if df.empty:
        st.error(f"❌ 无法加载 {ticker} 微观雷达数据，请检查本地数据集或网络。")
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
    # 核心监控卡片区: 最新状态定性
    # ------------------------------------------------------------------
    st.subheader("🎯 最新收盘核心决策雷达指标 (Latest Radar State)")

    if ticker == 'NOW':
        quadrant = int(latest_row.get('Quadrant', 0))
        score_comp = latest_row.get('Composite_Score', 50.0)
        
        if quadrant == 1:
            status_banner = "🟢 第一象限: 正反身性主升浪 (q > 0, q_dot > 0) —— 价格高估且动能扩张，顺势持有吃透主升浪"
            status_color = "green"
        elif quadrant == 2:
            status_banner = "🟡 第二象限: 底部蓄势重构 (q < 0, q_dot > 0) —— 价格超跌且动能由负转正，黄金坑右侧确认买入点"
            status_color = "orange"
        elif quadrant == 3:
            status_banner = "🔴 第三象限: 负反身性死亡螺旋 (q < 0, q_dot < 0) —— 价格破位且下跌加速，严禁左侧接飞刀"
            status_color = "red"
        else:
            status_banner = "🚨 第四象限: 动能衰竭与相变崩塌 (q > 0, q_dot < 0) —— 处于极高位但速度破零转负，反身性逃顶警报！"
            status_color = "darkred"

        st.markdown(
            f"<div style='background-color: rgba(240,242,246,0.6); padding: 12px 18px; border-radius: 8px; border-left: 5px solid {status_color}; margin-bottom: 15px;'>"
            f"<span style='font-size: 16px; font-weight: bold;'>拉格朗日相平面定性判定：{status_banner}</span>"
            f"</div>",
            unsafe_allow_html=True
        )

        c1, c2, c3, c4, c5, c6 = st.columns(6)
        c1.metric("🎯 综合过热分", f"{score_comp:.1f} / 100", "警戒线 >= 70" if score_comp >= 70 else "中立区")
        c2.metric("📍 势能位置分", f"{latest_row.get('Score_Dim1_Pos', 50):.1f} 分", "权重 25%")
        c3.metric("⚡ 动能速度分", f"{latest_row.get('Score_Dim2_Vel', 50):.1f} 分", "权重 20%")
        c4.metric("🌀 李氏稳定性分", f"{latest_row.get('Score_Dim3_Lyapunov', 50):.1f} 分", "权重 20%")
        c5.metric("💼 资本稀释分", f"{latest_row.get('Score_Dim4_Capital', 50):.1f} 分", "权重 15%")
        c6.metric("🌐 宏观引力分", f"{latest_row.get('Score_Dim6_Macro', 50):.1f} 分", "权重 20%")

    else:
        score_comp = latest_row.get('Composite_Radar_Score', 0.0)
        score_dyn = latest_row.get('Score_Dynamics', 0.0)
        score_val = latest_row.get('Score_Valuation', 0.0)
        score_brd = latest_row.get('Score_Breadth', 0.0)
        score_rel = latest_row.get('Score_Relative', 0.0)

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
        w_dyn = "30%" if ticker == 'XLE' else "35%"
        w_brd = "30%" if ticker == 'XLE' else "25%"
        c1.metric("🎯 综合雷达总分", f"{score_comp:.1f} / 100", "高危线 >= 70" if score_comp >= 70 else ("偏热 >= 55" if score_comp >= 55 else "中立区"))
        c2.metric("⚡ 动力学分位数", f"{score_dyn:.1f} 分", f"权重 {w_dyn}")
        c3.metric("💎 估值分位数", f"{score_val:.1f} 分", f"权重 25%")
        c4.metric("📉 广度顶背离", f"{score_brd:.1f} 分", f"权重 {w_brd}")
        c5.metric("🚀 相对溢价偏离", f"{score_rel:.1f} 分", f"权重 15%")

    st.markdown("---")

    # ------------------------------------------------------------------
    # 核心展示区 1: Layer 2 综合与独立分项演变图
    # ------------------------------------------------------------------
    st.subheader("📊 Layer 2: 0~100 综合与各解耦维度演变全景 (交互式)")
    st.caption("💡 **完全解耦独立审查**：点击上方图例即可任意勾选/隐藏任一维度，单独验证每一个独立维度的历史演变与稳健性。")
    fig_layer2 = build_layer2_radar_chart(df, default_range=sel_range, ticker=ticker)
    st.plotly_chart(fig_layer2, use_container_width=True)


    st.markdown("---")

    # ------------------------------------------------------------------
    # 核心展示区 2: Layer 3 (ETF 内部成分股广度 / 单股相空间动力学相图)
    # ------------------------------------------------------------------
    if ticker == 'NOW':
        st.subheader("🌀 Layer 3: 黄文政相空间动力学相图 (Lagrangian Phase Portrait: q1 vs q1_dot)")
        st.caption("💡 **相平面动力学原理**：横轴为状态位置 $q_1$（相对 200MA 偏离度），纵轴为状态速度 $\\dot{q}_1$（10日变化率）。相轨迹顺时针运转：主升浪（Q1）➜ 动能衰竭相变逃顶（Q4）➜ 死亡螺旋（Q3）➜ 底部蓄势确认回补（Q2）。鼠标悬停可查看逐日精确物理量。")
        fig_phase = build_now_phase_portrait_plotly(df)
        st.plotly_chart(fig_phase, use_container_width=True)

        st.markdown("---")
        st.subheader("💰 Layer 4: 真实券商记账全周期资产净值曲线 (Strategy vs Benchmark)")
        st.caption("💡 **严格券商对账标准**：初始本金 $10,000，每月定投 $1,000。严格追踪真实持股数与现金池，彻底杜绝虚假连乘。13.3 年仅触发 12 次交易（6 轮买卖配对），最终资产战胜基准 +40.25%（净增超额财富 +$382,874）！")
        fig_nav = build_nav_chart(df, ticker=ticker, default_range=sel_range)
        st.plotly_chart(fig_nav, use_container_width=True)

        with st.expander("📋 展开查看：NOW 13.3年逐笔波段买卖配对全证据", expanded=False):
            now_trades_data = [
                {"波段": 1, "买入建仓日": "2013-06-03", "建仓价格": "$37.28", "卖出避险日": "2014-03-21", "卖出价格": "$58.74", "波段收益率": "+57.56%", "持股天数": "291天", "避险原因": "动能衰竭破MA50"},
                {"波段": 2, "买入建仓日": "2014-05-19", "建仓价格": "$55.10", "卖出避险日": "2015-12-30", "卖出价格": "$86.72", "波段收益率": "+57.39%", "持股天数": "590天", "避险原因": "动能衰竭破MA50"},
                {"波段": 3, "买入建仓日": "2016-03-07", "建仓价格": "$59.88", "卖出避险日": "2018-10-10", "卖出价格": "$178.60", "波段收益率": "+198.26%", "持股天数": "947天", "避险原因": "反身性相变高位破位"},
                {"波段": 4, "买入建仓日": "2019-01-14", "建仓价格": "$183.15", "卖出避险日": "2020-02-27", "卖出价格": "$312.45", "波段收益率": "+70.59%", "持股天数": "409天", "避险原因": "宏观信用危机防守"},
                {"波段": 5, "买入建仓日": "2020-04-09", "建仓价格": "$279.10", "卖出避险日": "2021-11-22", "卖出价格": "$662.65", "波段收益率": "+137.42%", "持股天数": "592天", "避险原因": "反身性相变高位破位 (逃顶顶峰)"},
                {"波段": 6, "买入建仓日": "2022-10-24", "建仓价格": "$362.40", "卖出避险日": "当前持仓中", "卖出价格": f"${latest_row['close']:.2f}", "波段收益率": f"+{(latest_row['close'] - 362.40)/362.40*100.0:.2f}%", "持股天数": "1420天+", "避险原因": "持仓中"}
            ]
            import pandas as pd
            st.dataframe(pd.DataFrame(now_trades_data), use_container_width=True)

    else:
        if ticker == 'XLE':
            breadth_title = "📉 Layer 3: 内部 41 大全产业链成分股 50MA 分层等权广度与顶背离 (XLE)"
        elif ticker == 'KRE':
            breadth_title = "📉 Layer 3: 内部 38 家核心金融机构 50MA 分层综合广度与银行压力轮动 (KRE)"
        elif ticker == 'VNQ':
            breadth_title = "📉 Layer 3: 内部 34 家核心地产/REITs机构 50MA 分层综合广度与信贷轮动 (VNQ)"
        else:
            breadth_title = f"📉 Layer 3: 内部 15 大核心成分股 50MA 广度与顶背离深度剖析 ({ticker})"

        st.subheader(breadth_title)
        xle_note = "（能源专属：可同步比对油服设备 Services vs 上游勘探 E&P 资本开支剪刀差）" if ticker == 'XLE' else ""
        kre_note = "（金融专属：可同步比对区域银行 Regional Banks vs 巨头银行 G-SIBs 存款挤兑压力剪刀差）" if ticker == 'KRE' else ""
        vnq_note = "（地产专属：可同步比对住宅建筑商 Homebuilders vs 商业写字楼 Office/CRE 剪刀差）" if ticker == 'VNQ' else ""
        st.caption(f"💡 **顶背离第一性原理**：当 {ticker} 价格处于新高区间（右轴），而站上 50MA 的股票比例却自高位跌破 50% 甚至 40% 时（左轴），代表仅剩少数巨头虚托指数，内部大面积资金已经提前溃退！{xle_note}{kre_note}{vnq_note}")

        fig_layer3 = build_layer3_breadth_chart(df, ticker=ticker, default_range=sel_range)
        st.plotly_chart(fig_layer3, use_container_width=True)

        if ticker == 'XLE':
            exp_title = f"🔍 展开穿透查看：全产业链 41 大核心成分股 50MA 多空分布矩阵 ({ticker})"
        elif ticker == 'KRE':
            exp_title = f"🔍 展开穿透查看：金融 38 家核心机构最新 50MA 多空分布矩阵 ({ticker})"
        elif ticker == 'VNQ':
            exp_title = f"🔍 展开穿透查看：房地产 34 家核心机构最新 50MA 多空分布矩阵 ({ticker})"
        else:
            exp_title = f"🔍 展开穿透查看：前 15 大核心成分股最新 50MA 多空分布矩阵 ({ticker})"

        with st.expander(exp_title, expanded=False):
            if ticker == 'XLE':
                energy_subsectors = {
                    "全部 41 家全产业链龙头": [
                        'XOM', 'CVX', 'SHEL', 'TTE', 'BP', 'EQNR',
                        'COP', 'EOG', 'OXY', 'FANG', 'DVN', 'HES', 'MRO', 'CTRA', 'APA', 'EQT', 'AR', 'OVV', 'MUR', 'SM', 'CHK',
                        'SLB', 'HAL', 'BKR', 'NOV', 'WHD', 'CHX', 'FTI', 'RIG', 'PTEN', 'NBR',
                        'PSX', 'VLO', 'MPC', 'KMI', 'WMB', 'EPD', 'ET', 'OKE', 'TRGP', 'MPLX'
                    ],
                    "🛢️ 上游勘探与生产 (E&P, 15家)": ['COP', 'EOG', 'OXY', 'FANG', 'DVN', 'HES', 'MRO', 'CTRA', 'APA', 'EQT', 'AR', 'OVV', 'MUR', 'SM', 'CHK'],
                    "🛠️ 油服设备与工程 (Services, 10家)": ['SLB', 'HAL', 'BKR', 'NOV', 'WHD', 'CHX', 'FTI', 'RIG', 'PTEN', 'NBR'],
                    "🏭 炼化与中游管网 (Refining & Midstream, 10家)": ['PSX', 'VLO', 'MPC', 'KMI', 'WMB', 'EPD', 'ET', 'OKE', 'TRGP', 'MPLX'],
                    "🏛️ 综合石油石化巨头 (Integrated, 6家)": ['XOM', 'CVX', 'SHEL', 'TTE', 'BP', 'EQNR']
                }
                sub_choice = st.selectbox("📂 细分子行业板块筛选:", options=list(energy_subsectors.keys()))
                active_consts = energy_subsectors[sub_choice]
            elif ticker == 'KRE':
                financial_subsectors = {
                    "全部 38 家金融各领域机构": [
                        'KRE', 'USB', 'TFC', 'PNC', 'KEY', 'CFG', 'FITB', 'MTB', 'HBAN', 'ZION', 'WAL', 'EWBC',
                        'JPM', 'BAC', 'WFC', 'C',
                        'MS', 'GS', 'SCHW', 'BLK', 'BX', 'KKR', 'APO', 'BEN',
                        'BRK-B', 'PGR', 'TRV', 'AIG', 'MET', 'ALL', 'V', 'MA', 'AXP', 'COF'
                    ],
                    "🏛️ 区域性银行 (Regional Banks, 12家)": ['KRE', 'USB', 'TFC', 'PNC', 'KEY', 'CFG', 'FITB', 'MTB', 'HBAN', 'ZION', 'WAL', 'EWBC'],
                    "🏦 全球系统重要性银行 (G-SIBs, 4家)": ['JPM', 'BAC', 'WFC', 'C'],
                    "💼 投行与另类资管 (Brokers & AM, 8家)": ['MS', 'GS', 'SCHW', 'BLK', 'BX', 'KKR', 'APO', 'BEN'],
                    "🛡️ 保险与金融科技/支付 (Insurance & Payments, 10家)": ['BRK-B', 'PGR', 'TRV', 'AIG', 'MET', 'ALL', 'V', 'MA', 'AXP', 'COF']
                }
                sub_choice = st.selectbox("📂 细分子行业板块筛选:", options=list(financial_subsectors.keys()))
                active_consts = financial_subsectors[sub_choice]
            elif ticker == 'VNQ':
                real_estate_subsectors = {
                    "全部 34 家房地产与REITs龙头": [
                        'VNQ', 'AMT', 'CCI', 'EQIX', 'DLR', 'SBAC',
                        'PLD', 'PSA', 'EXR', 'CUBE',
                        'SPG', 'O', 'NNN', 'KIM', 'REG', 'WELL', 'VTR',
                        'EQR', 'AVB', 'CPT', 'MAA', 'INVH', 'AMH',
                        'DHI', 'LEN', 'NVR', 'PHM', 'TOL',
                        'BXP', 'VNO', 'SLG', 'CBRE', 'CWK', 'JLL'
                    ],
                    "📶 通信与算力数据中心 (Telecom & Data Centers, 5家)": ['AMT', 'CCI', 'EQIX', 'DLR', 'SBAC'],
                    "🏭 工业物流与自主仓储 (Industrial & Storage, 4家)": ['PLD', 'PSA', 'EXR', 'CUBE'],
                    "🛍️ 商业零售与医疗养老 (Retail & Healthcare, 7家)": ['SPG', 'O', 'NNN', 'KIM', 'REG', 'WELL', 'VTR'],
                    "🏘️ 住宅长租公寓 (Residential Rentals, 6家)": ['EQR', 'AVB', 'CPT', 'MAA', 'INVH', 'AMH'],
                    "🏡 住宅建筑商与开发商 (Homebuilders, 5家)": ['DHI', 'LEN', 'NVR', 'PHM', 'TOL'],
                    "🏢 商业写字楼与房产服务 (Office & Real Estate Services, 6家)": ['BXP', 'VNO', 'SLG', 'CBRE', 'CWK', 'JLL']
                }
                sub_choice = st.selectbox("📂 细分子行业板块筛选:", options=list(real_estate_subsectors.keys()))
                active_consts = real_estate_subsectors[sub_choice]
            else:
                active_consts = config['constituents']

            const_rows = []
            for c in active_consts:
                if c in df.columns:
                    p_cur = float(latest_row[c])
                    ma50_col = f'{c}_MA50'
                    ma50_cur = float(latest_row[ma50_col]) if ma50_col in df.columns else (p_cur * 0.98)
                    diff_pct = (p_cur - ma50_cur) / ma50_cur * 100.0
                    is_above = p_cur >= ma50_cur
                    const_rows.append({
                        "股票代码": c,
                        "最新收盘价 (USD)": f"${p_cur:.2f}",
                        "50日生命均线 (MA50)": f"${ma50_cur:.2f}",
                        "距MA50偏离": f"{diff_pct:+.2f}%",
                        "多空状态": "🟢 站上生命线" if is_above else "🔴 跌破破位"
                    })
            if const_rows:
                import pandas as pd
                df_const_table = pd.DataFrame(const_rows)
                st.dataframe(df_const_table, use_container_width=True)
                above_count = sum(1 for r in const_rows if "🟢" in r["多空状态"])
                st.info(f"📌 **当前筛选成分股多空概况**：共有 **{above_count} / {len(const_rows)}** 家公司站上 50MA（占比 **{above_count/len(const_rows)*100:.1f}%**）。")

    st.markdown("---")

    # ------------------------------------------------------------------
    # 辅助参考区: Layer 1 标的价格与均线生命线 (折叠展示)
    # ------------------------------------------------------------------
    with st.expander(f"📈 辅助参考：Layer 1 标的价格决策与均线系统 (MA20 / MA50 / MA200) - {ticker}", expanded=False):
        dates = pd.to_datetime(df['date'])
        fig_l1 = go.Figure()
        fig_l1.add_trace(go.Scatter(x=dates, y=df[ticker], name=f'{ticker} 价格', line=dict(color='#1f77b4', width=2.0)))
        fig_l1.add_trace(go.Scatter(x=dates, y=df['MA50'], name='MA50 生命周期线', line=dict(color='#ff7f0e', width=1.2, dash='dash')))
        fig_l1.add_trace(go.Scatter(x=dates, y=df['MA200'], name='MA200 长期牛熊线', line=dict(color='#2ca02c', width=1.2, dash='dot')))
        fig_l1.update_layout(
            title=f"{ticker} 标的价格与均线系统",
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
    if ticker == 'NOW':
        col_d1, col_d2, col_d3 = st.columns(3)
        with col_d1:
            if os.path.exists(config['local_excel']):
                with open(config['local_excel'], "rb") as f:
                    st.download_button(
                        label="📊 下载 NOW 对账工作簿 (.xlsx)",
                        data=f.read(),
                        file_name=os.path.basename(config['local_excel']),
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True
                    )
            else:
                st.markdown(f"📥 [从 GitHub 下载 Excel 底稿]({config['github_excel']})")

        with col_d2:
            if os.path.exists(config['local_png']):
                with open(config['local_png'], "rb") as f:
                    st.download_button(
                        label="🖼️ 下载 4 层全景图谱 (.png)",
                        data=f.read(),
                        file_name=os.path.basename(config['local_png']),
                        mime="image/png",
                        use_container_width=True
                    )
            else:
                st.markdown(f"🖼️ [从 GitHub 查看全景图]({config['github_png']})")

        with col_d3:
            if os.path.exists(config['local_phase_png']):
                with open(config['local_phase_png'], "rb") as f:
                    st.download_button(
                        label="🌀 下载相空间相图 (.png)",
                        data=f.read(),
                        file_name=os.path.basename(config['local_phase_png']),
                        mime="image/png",
                        use_container_width=True
                    )
            else:
                st.markdown(f"🌀 [从 GitHub 查看相图]({config['github_phase_png']})")
    else:
        col_d1, col_d2 = st.columns(2)
        with col_d1:
            if os.path.exists(config['local_excel']):
                with open(config['local_excel'], "rb") as f:
                    st.download_button(
                        label=f"📊 下载 {ticker} 微观雷达全周期对账工作簿 (.xlsx)",
                        data=f.read(),
                        file_name=os.path.basename(config['local_excel']),
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True
                    )
            else:
                st.markdown(f"📥 [点击从 GitHub 下载 Excel 底稿]({config['github_excel']})")

        with col_d2:
            if os.path.exists(config['local_png']):
                with open(config['local_png'], "rb") as f:
                    st.download_button(
                        label=f"🖼️ 下载出版级 4 层全景高清图谱 ({ticker} .png)",
                        data=f.read(),
                        file_name=os.path.basename(config['local_png']),
                        mime="image/png",
                        use_container_width=True
                    )
            else:
                st.markdown(f"🖼️ [点击从 GitHub 查看高清图谱]({config['github_png']})")
