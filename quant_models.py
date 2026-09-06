"""
Quantitative Valuation & Financial Models
"""
import numpy as np

def calculate_reverse_dcf(
    current_price: float,
    ttm_fcf_per_share: float,
    wacc: float = 0.09,
    terminal_growth: float = 0.03,
    forecast_years: int = 10
) -> float:
    """
    反向自由现金流折现模型 (Reverse DCF):
    通过二分法根据当前股价倒算市场隐含的未来 10 年自由现金流年化复合增长率 (CAGR %)
    """
    if ttm_fcf_per_share <= 0 or current_price <= 0:
        return np.nan
    low_g, high_g = -0.50, 1.00
    for _ in range(100):
        mid_g = (low_g + high_g) / 2.0
        pv = 0.0
        cf = ttm_fcf_per_share
        for t in range(1, forecast_years + 1):
            cf *= (1 + mid_g)
            pv += cf / ((1 + wacc) ** t)
        terminal_val = (cf * (1 + terminal_growth)) / (wacc - terminal_growth)
        pv += terminal_val / ((1 + wacc) ** forecast_years)
        if abs(pv - current_price) < 0.01:
            return mid_g * 100.0
        if pv > current_price:
            high_g = mid_g
        else:
            low_g = mid_g
    return mid_g * 100.0


# ==================================================================
# 中金公司「胜率 - 赔率」全景量化大类资产与行业板块模型 (v1 增强版)
# ==================================================================
import streamlit as st
import pandas as pd

CICC_SECTOR_UNIVERSE = [
    {"symbol": "SMH", "name": "芯片与半导体", "category": "💻 科技硬件与互联网", "desc": "AI算力与硬件供应链龙头 (NVDA, TSM, ASML, AVGO)"},
    {"symbol": "IGV", "name": "软件与SaaS云服务", "category": "💻 科技硬件与互联网", "desc": "企业级云订阅与软件服务 (MSFT, CRM, ADBE, PLTR)"},
    {"symbol": "XLK", "name": "科技全景核心", "category": "💻 科技硬件与互联网", "desc": "硬科技与数字化核心资产 (AAPL, MSFT, NVDA)"},
    {"symbol": "XLC", "name": "通信与数字媒体", "category": "💻 科技硬件与互联网", "desc": "社交广告、流媒体与数字内容 (META, GOOGL, NFLX)"},
    {"symbol": "XBI", "name": "生物科技创新药", "category": "💻 科技硬件与互联网", "desc": "高弹性创新药研发与利率敏感生命科学"},
    {"symbol": "XLY", "name": "非必需可选消费", "category": "🏭 顺周期与高端制造", "desc": "居民自主消费、电商与电动车 (AMZN, TSLA, HD)"},
    {"symbol": "XLF", "name": "传统金融与银行", "category": "🏭 顺周期与高端制造", "desc": "息差、投行交易与资产管理 (BRK.B, JPM, V, MA)"},
    {"symbol": "XLI", "name": "工业与高端制造", "category": "🏭 顺周期与高端制造", "desc": "机械装备、国防军工与再工业化 (GE, CAT, LMT)"},
    {"symbol": "XLB", "name": "基础材料与采矿", "category": "🏭 顺周期与高端制造", "desc": "工业原材料、金属采选与特种化学品 (LIN, SHW, FCX)"},
    {"symbol": "XLE", "name": "传统能源与油气", "category": "🏭 顺周期与高端制造", "desc": "原油综合勘探开采与炼化 (XOM, CVX, COP)"},
    {"symbol": "XLP", "name": "必需消费品 (防守)", "category": "🛡️ 防御、电力与内需", "desc": "抗周期日常刚需消费 (PG, COST, PEP, KO)"},
    {"symbol": "XLV", "name": "医疗保健与制药", "category": "🛡️ 防御、电力与内需", "desc": "大型成熟药企与医疗器械 (LLY, UNH, JNJ)"},
    {"symbol": "XLU", "name": "公用事业与电力电网", "category": "🛡️ 防御、电力与内需", "desc": "AI数据中心电力需求与电网公用 (NEE, CEG, VST)"},
    {"symbol": "XLRE", "name": "房地产与REITs", "category": "🛡️ 防御、电力与内需", "desc": "数据中心与物流仓储REITs (PLD, AMT, EQIX)"},
    {"symbol": "SPY", "name": "标普 500 大盘核心", "category": "🌐 宏观大类资产", "desc": "美股全市场整体基准"},
    {"symbol": "QQQ", "name": "纳斯达克 100 科技", "category": "🌐 宏观大类资产", "desc": "全球高增长科技先锋资产"},
    {"symbol": "IWM", "name": "罗素 2000 中小盘", "category": "🌐 宏观大类资产", "desc": "本土中小盘顺周期降息弹性资产"},
    {"symbol": "TLT", "name": "20Y+ 长端美国国债", "category": "🌐 宏观大类资产", "desc": "超长久期无风险利率债，衰退避险与期限溢价"},
    {"symbol": "IEF", "name": "7-10Y 中期美国国债", "category": "🌐 宏观大类资产", "desc": "中期防御性稳健票息国债"},
    {"symbol": "GLD", "name": "实物黄金现货", "category": "🌐 宏观大类资产", "desc": "抗通胀、去美元化与主权信用对冲"},
    {"symbol": "USO", "name": "WTI 原油大宗商品", "category": "🌐 宏观大类资产", "desc": "实体工业总需求与地缘博弈风向标"},
    {"symbol": "HYG", "name": "高收益美元企业债", "category": "🌐 宏观大类资产", "desc": "信用违约风险与流动性利差体温计"},
    {"symbol": "UUP", "name": "美元指数 ETF", "category": "🌐 宏观大类资产", "desc": "全球流动性虹吸与汇率抗跌对冲"}
]

@st.cache_data(ttl=60 * 60 * 6)
def calculate_cicc_sector_quadrant():
    """
    中金公司「胜率 - 赔率」全景量化计算引擎:
    1. 批量拉取 23 个细分板块与大类资产过去 5 年历史走势；
    2. 计算赔率评分 (0-100): 基于 5 年历史价格分位数、200MA 均线偏离与均值回归空间；
    3. 计算胜率评分 (0-100): 基于 12-1M 经典学术动量、中短期均线系统 (20MA/50MA/200MA) 排列强度与近 3M 相对强度；
    4. 划分四象限，生成五档估值高低估诊断与战术配置指引。
    """
    import yfinance as yf
    symbols = [item["symbol"] for item in CICC_SECTOR_UNIVERSE]
    
    try:
        df_raw = yf.download(symbols, period="5y", progress=False)['Close']
    except Exception as e:
        print(f"Batch download error for CICC quadrant: {e}")
        df_raw = pd.DataFrame()

    # 预先提取标普 500 (SPY) 基础走势用于跨板块相对估值与相对强弱对比
    spy_close = None
    spy_bias200 = 0.0
    spy_ret_3m = 0.0
    if df_raw is not None and not df_raw.empty and "SPY" in df_raw.columns:
        spy_close = df_raw["SPY"].dropna()
    else:
        try:
            spy_close = yf.Ticker("SPY").history(period="5y")['Close'].dropna()
        except Exception:
            pass

    if spy_close is not None and len(spy_close) > 60:
        ma200_spy = float(spy_close.rolling(200).mean().iloc[-1])
        curr_spy = float(spy_close.iloc[-1])
        spy_bias200 = float((curr_spy - ma200_spy) / ma200_spy * 100.0) if ma200_spy > 0 else 0.0
        idx_3m_spy = min(63, len(spy_close) - 1)
        spy_ret_3m = float((curr_spy - spy_close.iloc[-idx_3m_spy]) / spy_close.iloc[-idx_3m_spy] * 100.0)

    results = []
    for item in CICC_SECTOR_UNIVERSE:
        s = item["symbol"]
        name = item["name"]
        cat = item["category"]
        desc = item["desc"]

        if df_raw is not None and not df_raw.empty and s in df_raw.columns:
            close = df_raw[s].dropna()
        else:
            try:
                t = yf.Ticker(s)
                close = t.history(period="5y")['Close'].dropna()
            except Exception:
                close = pd.Series(dtype=float)

        if len(close) < 60:
            continue

        curr_price = float(close.iloc[-1])
        
        # -------------------------------------------------------------
        # 1. 赔率计算 (Odds Score, 0 ~ 100): 遵循中金相对估值与安全边际体系
        # -------------------------------------------------------------
        # A. 绝对价格历史分位 (5年分布) 与 200MA 乖离
        percentile_5y = float((close < curr_price).mean() * 100.0)
        ma200 = float(close.rolling(200).mean().iloc[-1]) if len(close) >= 200 else curr_price
        bias200 = float((curr_price - ma200) / ma200 * 100.0) if ma200 > 0 else 0.0

        # B. 相对大盘估值比价 (Relative Ratio vs SPY)
        # 中金核心方法论：在长期牛市中，名义价格普遍新高，行业估值性价比取决于相对大盘的折溢价历史分位
        rel_percentile_5y = percentile_5y
        rel_bias200 = bias200
        if spy_close is not None and len(spy_close) > 60:
            ratio_series = close / spy_close.reindex(close.index).ffill()
            ratio_series = ratio_series.dropna()
            if len(ratio_series) > 60:
                curr_ratio = float(ratio_series.iloc[-1])
                rel_percentile_5y = float((ratio_series < curr_ratio).mean() * 100.0)
                ma200_ratio = float(ratio_series.rolling(200).mean().iloc[-1])
                if ma200_ratio > 0:
                    rel_bias200 = float((curr_ratio - ma200_ratio) / ma200_ratio * 100.0)

        # C. 分资产类别计算赔率评分
        if s in ["TLT", "IEF"]:
            # 国债资产：利率债按价格折价与实际利率空间定价 (低价格 = 高到期收益率 = 高赔率)
            odds_score = float(np.clip(100.0 - percentile_5y - bias200 * 0.5, 5.0, 95.0))
        elif s in ["GLD", "USO", "UUP", "HYG"]:
            # 大宗商品、外汇与信用债：综合 5 年均值回归与 200MA 乖离
            odds_score = float(np.clip(100.0 - percentile_5y * 0.70 - bias200 * 0.80, 5.0, 95.0))
        elif s == "SPY":
            # 标普 500 大盘：按长期均线偏离度与估值透支度计算
            odds_score = float(np.clip(55.0 - spy_bias200 * 1.5, 20.0, 80.0))
        else:
            # 细分行业板块：中金核心标准——相对大盘折价分位 (70%) + 相对乖离反弹空间 (30%)
            odds_rel = 100.0 - rel_percentile_5y
            odds_bias = 50.0 - (rel_bias200 * 1.2)
            odds_score = float(np.clip(odds_rel * 0.70 + odds_bias * 0.30, 5.0, 95.0))

        # -------------------------------------------------------------
        # 2. 胜率计算 (Win Rate Score, 0 ~ 100): 衡量景气动能与顺风度 (右侧)
        # -------------------------------------------------------------
        # 12-1M 经典学术动量 (Jegadeesh & Titman: 剔除近月反转的纯净趋势)
        if len(close) >= 252:
            close_21 = float(close.iloc[-21])
            close_252 = float(close.iloc[-252])
            mom_12_1 = float((close_21 - close_252) / close_252 * 100.0) if close_252 > 0 else 0.0
        else:
            mom_12_1 = float((curr_price - close.iloc[0]) / close.iloc[0] * 100.0)

        # 近 3 个月绝对涨幅与相对超额 Alpha
        idx_3m = min(63, len(close) - 1)
        close_3m = float(close.iloc[-idx_3m])
        ret_3m = float((curr_price - close_3m) / close_3m * 100.0) if close_3m > 0 else 0.0
        rel_ret_3m = (ret_3m - spy_ret_3m) if s not in ["SPY", "TLT", "IEF", "GLD"] else 0.0

        # 均线多头排列趋势强度
        ma20 = float(close.rolling(20).mean().iloc[-1]) if len(close) >= 20 else curr_price
        ma50 = float(close.rolling(50).mean().iloc[-1]) if len(close) >= 50 else curr_price
        trend_pts = 0.0
        if curr_price > ma50: trend_pts += 5.0
        if ma50 > ma200: trend_pts += 5.0

        win_score = float(np.clip(
            50.0 + (mom_12_1 * 0.35) + (ret_3m * 0.30) + (rel_ret_3m * 0.25) + trend_pts,
            10.0, 95.0
        ))

        # -------------------------------------------------------------
        # 3. 象限划分与高低估诊断
        # -------------------------------------------------------------
        if win_score >= 50.0 and odds_score >= 50.0:
            quadrant = "第一象限: 戴维斯双击 (高胜率+低估值)"
            q_code = "Q1"
            action = "积极进攻 / 重仓配置"
        elif win_score >= 50.0 and odds_score < 50.0:
            quadrant = "第二象限: 动量顺势 (高胜率+高估值)"
            q_code = "Q2"
            action = "顺势持有 / 紧设止损防估值回调"
        elif win_score < 50.0 and odds_score < 50.0:
            quadrant = "第三象限: 戴维斯双杀 (低胜率+高估值)"
            q_code = "Q3"
            action = "坚决回避 / 减仓或对冲"
        else:
            quadrant = "第四象限: 价值洼地 (低胜率+低估值)"
            q_code = "Q4"
            action = "左侧定投 / 耐心等待拐点"

        # 五档估值诊断
        if odds_score >= 75.0:
            val_tag = "🟢🟢 深度低估 (Deep Value)"
        elif odds_score >= 55.0:
            val_tag = "🟢 相对低估 (Undervalued)"
        elif odds_score >= 45.0:
            val_tag = "⚪ 估值合理 (Fair Value)"
        elif odds_score >= 25.0:
            val_tag = "🟠 相对高估 (Overvalued)"
        else:
            val_tag = "🔴 极度高估 (Heavy Overvalued)"

        results.append({
            "ticker": s,
            "symbol": s,
            "name": name,
            "category": cat,
            "desc": desc,
            "price": curr_price,
            "odds_score": round(odds_score, 1),
            "win_score": round(win_score, 1),
            "quadrant": quadrant,
            "q_code": q_code,
            "valuation_tag": val_tag,
            "action": action,
            "mom_12_1": round(mom_12_1, 1),
            "bias_200": round(bias200, 1),
            "ret_3m": round(ret_3m, 1),
            "rel_percentile_5y": round(rel_percentile_5y, 1),
            "percentile_5y": round(percentile_5y, 1)
        })

    return pd.DataFrame(results)

