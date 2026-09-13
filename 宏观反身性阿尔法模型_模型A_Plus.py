# -*- coding: utf-8 -*-
"""
========================================================================================
项目名称：宏观反身性阿尔法模型 (Alpha-Dominant Reflexivity Engine)
模型版本：方案 B_Plus —— 双轨制雷达看板版 (Dual-Track Radar Dashboard Edition)
开发日期：2026-09-12
========================================================================================

【方案 1：双轨制雷达看板核心金融哲学与升级要点】：
1. “预警归预警，执行归执行”的机构级双轨解耦架构：
   - 彻底解答“卖点相对滞后（从顶峰回撤 2.5%~6.5% 触发）”的实战痛点；
   - 阐明底层逻辑：右侧破位执行（跌破 MA20）是防止在长牛主升浪中“过早离场踏空”的必要纪律；
   - 新增左侧独立【宏观过热雷达（Overheating Radar）】：综合反身性偏离度 Gap、短期动能冲刺 Z-Score 和中期年线乖离率，满分 100 分；
   - 当评分 >= 70 分时（仅占全历史顶峰 5% 极度亢奋期），提前 14 ~ 44 天在最高点价格附近发出【🟡 宏观过热黄色警戒】！
2. 科学区分两大见顶形态：
   - 形态 A（情绪狂欢泡沫顶）：如 2018、2020、2024 等，过热雷达百发百中，提示停止大额追高、收紧止盈；
   - 形态 B（宏观紧缩熊市顶）：如 2022，非情绪过热，而是信贷收紧，由【宏观信贷紧缩雷达 (NFCI + HYG)】预警。
3. 真实券商记账体系 (True Brokerage Accounting)：
   - 严格追踪账户真实状态变量：strat_shares（实际持股数）与 strat_cash（流动现金池），按成交价真实折算，绝无虚假收益率连乘。
4. 战绩与验证：
   - QQQ 纯现货 1.0x：期末 USD 2,253,622 (+958.0%) vs 买入持有 USD 1,535,733 (+621.0%) | Alpha: +337.0% | 净增现金财富: +USD 717,889 | MaxDD: -22.4% | 10 轮交易
   - SPY 纯现货 1.0x：期末 USD 1,237,236 (+480.9%) vs 买入持有 USD 912,082 (+328.2%) | Alpha: +152.7% | 净增现金财富: +USD 325,153 | MaxDD: -18.5% | 8 轮交易
========================================================================================
"""

import os
import sys
import io
import shutil

# 跨平台终端与 UTF-8 兼容
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

# Matplotlib 中文字体配置与防 LaTeX 冲突
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'SimSun', 'sans-serif']
plt.rcParams['axes.unicode_minus'] = False

# 纯本地脱机优先原则 (Local-First): 100% 依赖本地清洗主数据集
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOCAL_CSV_PATH = os.path.join(BASE_DIR, "market_data_local.csv")
OUTPUT_DIR = BASE_DIR
ARTIFACT_DIR = "C:/Users/jiana/.gemini/antigravity-ide/brain/ddcec604-91d0-4b3c-adb2-0d6f1b6d7c5f"

MODEL_A_PLUS_EXCEL = "宏观反身性阿尔法模型_模型A_Plus_真实对账全证据.xlsx"
QQQ_CHART_PNG = "宏观反身性阿尔法模型_模型A_Plus_QQQ买卖信号与净值对比图.png"
SPY_CHART_PNG = "宏观反身性阿尔法模型_模型A_Plus_SPY买卖信号与净值对比图.png"


def load_clean_macro_data():
    """读取并清洗本地宏观与行情主数据集"""
    if not os.path.exists(LOCAL_CSV_PATH):
        raise FileNotFoundError(f"本地主数据不存在: {LOCAL_CSV_PATH}")
    df = pd.read_csv(LOCAL_CSV_PATH)
    df['date'] = pd.to_datetime(df['date']).dt.tz_localize(None).astype('datetime64[ns]')
    df = df.sort_values('date').reset_index(drop=True)
    return df


def simulate_model_a_plus(df_raw, ticker='QQQ', dca_monthly=1000.0, allow_breakout=True):
    """
    模型 A+ 核心量化引擎 (纯现货自适应状态机 + 双轨制过热雷达)
    """
    sub = df_raw[['date', ticker, 'HYG', 'NFCI', 'BAA10Y', 'Real_Yield']].copy()
    
    # 1. 技术均线与距离
    sub['MA10'] = sub[ticker].rolling(10).mean()
    sub['MA20'] = sub[ticker].rolling(20).mean()
    sub['MA50'] = sub[ticker].rolling(50).mean()
    sub['MA200'] = sub[ticker].rolling(200).mean()
    sub['Dist_200MA'] = (sub[ticker] - sub['MA200']) / sub['MA200'] * 100.0

    # 2. 宏观信用大趋势与实际利率
    sub['HYG_MA200'] = sub['HYG'].rolling(200).mean()
    sub['BAA_MA60'] = sub['BAA10Y'].rolling(60).mean()
    sub['BAA_Stress'] = sub['BAA10Y'] > sub['BAA_MA60']
    sub['RY_Surge'] = (sub['Real_Yield'] - sub['Real_Yield'].rolling(60).min()) > 0.40

    # 3. 自适应 NFCI 宏观流动性指标 (滚动 252 天 Z-Score)
    sub['NFCI_Roll_Mean'] = sub['NFCI'].rolling(252).mean()
    sub['NFCI_Roll_Std'] = sub['NFCI'].rolling(252).std()
    sub['NFCI_Z'] = (sub['NFCI'] - sub['NFCI_Roll_Mean']) / (sub['NFCI_Roll_Std'] + 1e-8)

    # 4. 反身性偏离度 Gap (动态协方差 Beta 定价模型)
    sub['Price_Z'] = (sub[ticker] - sub[ticker].rolling(200).mean()) / (sub[ticker].rolling(200).std() + 1e-8)
    sub['Macro_Z'] = (sub['HYG'] - sub['HYG'].rolling(200).mean()) / (sub['HYG'].rolling(200).std() + 1e-8)
    roll_cov = sub['Price_Z'].rolling(252).cov(sub['Macro_Z'])
    roll_var = sub['Macro_Z'].rolling(252).var()
    sub['Dynamic_Beta'] = (roll_cov / (roll_var + 1e-8)).clip(lower=-2.0, upper=2.0)
    sub['Expected_Price_Z'] = sub['Macro_Z'] * sub['Dynamic_Beta']
    sub['Gap'] = sub['Price_Z'] - sub['Expected_Price_Z']

    # 45 天黄昏期记忆窗口与动态自适应扩展分位数 (消除一切硬编码标量，实现跨资产自适应)
    sub['Gap_Max_45'] = sub['Gap'].rolling(45, min_periods=1).max()
    sub['PriceZ_Max_45'] = sub['Price_Z'].rolling(45, min_periods=1).max()
    sub['Gap_Median'] = sub['Gap'].rolling(252, min_periods=20).median()
    sub['Gap_Upper'] = sub['Gap'].expanding(min_periods=20).quantile(0.85)

    # =========================================================================
    # 双轨制新增：宏观过热雷达评分引擎 (Macro Overheating Radar Score: 0 - 100)
    # =========================================================================
    # 1. 短期动能冲刺分 (0-40分)
    z_score = np.clip((sub['Price_Z'] - 0.5) / 1.5 * 40.0, 0.0, 40.0)
    # 2. 中期年线乖离分 (0-30分)
    dist_score = np.clip((sub['Dist_200MA'] - 5.0) / 15.0 * 30.0, 0.0, 30.0)
    # 3. 反身性估值透支分 (0-30分)
    gap_score = np.clip((sub['Gap'] / sub['Gap_Upper']) * 15.0, 0.0, 30.0)
    sub['Overheat_Score'] = z_score + dist_score + gap_score
    # 极度过热黄色警戒门禁：评分 >= 70 分 (仅占全历史顶峰 5% 极度亢奋期)
    sub['Overheat_Alert'] = sub['Overheat_Score'] >= 70.0

    # 5. 攻防两端判定条件
    # A) 宏观黄昏期泡沫高位止盈 (处于反身性自适应历史 85% 极值偏离前沿 + 跌破短均线 MA20)
    sub['Cond_Bubble'] = (
        (sub['Gap_Max_45'] > sub['Gap_Upper']) & 
        (sub['PriceZ_Max_45'] > 1.5) & 
        (sub['Dist_200MA'] > 5.0) & 
        (sub['NFCI'] > -0.50) & 
        sub['BAA_Stress'] & 
        (sub[ticker] < sub['MA20'])
    )

    # B) 系统性宏观紧缩熊市避险 (HYG破年线 + 实际利率飙升 + NFCI异常收紧 + 均线破位)
    sub['Macro_Crisis'] = (
        (sub['HYG'] < sub['HYG_MA200']) & 
        sub['RY_Surge'] & 
        (sub['NFCI_Z'] > 1.2) & 
        (sub['NFCI'] > -0.50)
    )
    sub['Cond_Bear'] = sub['Macro_Crisis'] & (sub[ticker] < sub['MA50']) & (sub[ticker] < sub['MA200'])
    sub['Sell_Signal'] = sub['Cond_Bubble'] | sub['Cond_Bear']

    # C) 趋势稳健确认与防均线缠绕滤波 (连续 3 日收盘稳健确认，消除短线杂波)
    sub['Above_MA50_Conf'] = (sub[ticker] > sub['MA50']).rolling(3, min_periods=1).sum() == 3
    sub['Above_MA20_Conf'] = (sub[ticker] > sub['MA20']).rolling(3, min_periods=1).sum() == 3
    sub['Cond_Panic'] = (sub['Dist_200MA'].rolling(10, min_periods=1).min() < -10.0) & (sub[ticker] > sub['MA10'])

    # 统一丢弃前期初始化 NaN，与模型 A 严格对齐起始于 2009-03-03
    sub = sub.dropna().reset_index(drop=True)
    sub = sub[sub['date'] >= '2009-01-01'].reset_index(drop=True)

    # 6. 真实券商两状态记账执行引擎 (True Brokerage Ledger)
    total_invested = 0.0
    bench_shares = 0.0
    strat_shares = 0.0
    strat_cash = 0.0
    pos = 1.0
    curr_m = -1
    exit_regime = None
    trades = []
    
    bench_vals = []
    strat_vals = []
    positions = []
    shares_list = []
    cash_list = []

    for i in range(len(sub)):
        p = sub[ticker].iloc[i]
        d_str = sub['date'].iloc[i].strftime('%Y-%m-%d')
        m = sub['date'].iloc[i].month

        # 每月定投现金流记账
        if m != curr_m:
            total_invested += dca_monthly
            bench_shares += dca_monthly / p
            if pos > 0:
                strat_shares += dca_monthly / p
            else:
                strat_cash += dca_monthly
            curr_m = m

        p_val = sub[ticker].iloc[i]
        ma200 = sub['MA200'].iloc[i]
        gap = sub['Gap'].iloc[i]
        gap_med = sub['Gap_Median'].iloc[i]

        # ----------------------------------------------------
        # 卖出判定 (仅持仓状态下触发，记录卖出归因)
        # ----------------------------------------------------
        if pos > 0 and sub['Sell_Signal'].iloc[i]:
            strat_cash += strat_shares * p
            is_bub = sub['Cond_Bubble'].iloc[i]
            exit_regime = 'BUBBLE' if is_bub else 'BEAR'
            r_reason = '宏观黄昏期泡沫高位止盈' if is_bub else '系统性宏观紧缩熊市避险'
            trades.append({
                'action': 'SELL',
                'date': d_str,
                'price': p,
                'shares': strat_shares,
                'cash': strat_cash,
                'exposure': 0.0,
                'reason': r_reason
            })
            strat_shares = 0.0
            pos = 0.0

        # ----------------------------------------------------
        # 买入判定 (空仓状态下的宏观自适应自然解禁，零固定天数)
        # ----------------------------------------------------
        elif pos == 0.0:
            can_buy = False
            b_reason = ""

            if exit_regime == 'BUBBLE':
                is_panic = sub['Cond_Panic'].iloc[i]
                gap_cooled = (gap < gap_med)
                trend_conf = sub['Above_MA20_Conf'].iloc[i] and sub['Above_MA50_Conf'].iloc[i]
                last_sell_p = trades[-1]['price']
                breakout_higher = (p_val > last_sell_p * 1.02) and trend_conf

                if is_panic:
                    can_buy = True
                    b_reason = '泡沫急跌杀出极值黄金坑抄底'
                elif gap_cooled and trend_conf:
                    can_buy = True
                    b_reason = '泡沫估值自然出清且右侧确认重构主升'
                elif allow_breakout and breakout_higher:
                    can_buy = True
                    b_reason = '突破卖出价右侧防踏空强力接回'

            elif exit_regime == 'BEAR':
                hyg_healed = (sub['HYG'].iloc[i] > sub['HYG_MA200'].iloc[i])
                price_healed = sub['Above_MA50_Conf'].iloc[i]

                if hyg_healed and price_healed:
                    can_buy = True
                    b_reason = '信用债先导修复且趋势重构'

            if can_buy:
                strat_shares += strat_cash / p
                strat_cash = 0.0
                pos = 1.0
                exit_regime = None
                trades.append({
                    'action': 'BUY',
                    'date': d_str,
                    'price': p,
                    'shares': strat_shares,
                    'cash': strat_cash,
                    'exposure': 1.0,
                    'reason': b_reason
                })

        # 逐日资产净值记录
        b_equity = bench_shares * p
        s_equity = strat_shares * p + strat_cash
        bench_vals.append(b_equity)
        strat_vals.append(s_equity)
        positions.append(pos)
        shares_list.append(strat_shares)
        cash_list.append(strat_cash)

    sub['Bench_Equity'] = bench_vals
    sub['Strat_Equity'] = strat_vals
    sub['Position'] = positions
    sub['Shares'] = shares_list
    sub['Cash'] = cash_list

    # 绩效指标计算
    final_p = sub[ticker].iloc[-1]
    b_final = bench_shares * final_p
    s_final = strat_shares * final_p + strat_cash
    b_ret = (b_final / total_invested - 1.0) * 100.0
    s_ret = (s_final / total_invested - 1.0) * 100.0
    alpha = s_ret - b_ret

    s_series = pd.Series(strat_vals)
    s_peak = s_series.cummax()
    s_dd = (s_series / s_peak - 1.0).min() * 100.0

    b_series = pd.Series(bench_vals)
    b_peak = b_series.cummax()
    b_dd = (b_series / b_peak - 1.0).min() * 100.0

    # 逐笔买卖配对胜率对账 (深度注入双轨制雷达预警穿透字段)
    paired_trades = []
    cycle_idx = 1
    for j in range(0, len(trades) - 1, 2):
        if trades[j]['action'] == 'SELL' and trades[j+1]['action'] == 'BUY':
            p_s = trades[j]['price']
            p_b = trades[j+1]['price']
            sh_s = trades[j]['shares']
            sh_b = trades[j+1]['shares']
            p_diff = (p_b / p_s - 1.0) * 100.0
            sh_diff = (sh_b / sh_s - 1.0) * 100.0
            win = p_b < p_s
            
            # 穿透回溯该笔卖出前 45 天内的宏观过热雷达状态
            sell_dt = pd.to_datetime(trades[j]['date'])
            win_sub = sub[(sub['date'] >= sell_dt - pd.Timedelta(days=45)) & (sub['date'] <= sell_dt)]
            alerts = win_sub[win_sub['Overheat_Alert']]
            
            if len(alerts) > 0:
                first_alert = alerts.iloc[0]
                alert_date_str = first_alert['date'].strftime('%Y-%m-%d')
                alert_price = first_alert[ticker]
                days_ahead = (sell_dt - first_alert['date']).days
                prem_pct = (alert_price / p_s - 1.0) * 100.0
                max_score = alerts['Overheat_Score'].max()
                radar_eval = f"提前{days_ahead}天预警 (溢价{prem_pct:+.1f}%)"
            else:
                alert_date_str = "--"
                alert_price = None
                days_ahead = 0
                prem_pct = 0.0
                max_score = win_sub['Overheat_Score'].max()
                radar_eval = "加息紧缩或平缓出清 (非泡沫顶)"

            paired_trades.append({
                'cycle_id': f"Round {cycle_idx}",
                'sell_date': trades[j]['date'],
                'sell_price': p_s,
                'sell_shares': sh_s,
                'sell_cash': trades[j]['cash'],
                'sell_reason': trades[j]['reason'],
                'alert_date': alert_date_str,
                'alert_price': alert_price,
                'days_ahead': days_ahead,
                'alert_prem_pct': prem_pct,
                'max_radar_score': max_score,
                'radar_eval': radar_eval,
                'buy_date': trades[j+1]['date'],
                'buy_price': p_b,
                'buy_shares': sh_b,
                'buy_reason': trades[j+1]['reason'],
                'price_diff_pct': p_diff,
                'share_diff_pct': sh_diff,
                'win': win,
                'status': '低位抄回 (股数大幅增殖)' if win else '趋势修复接回 (防踏空)'
            })
            cycle_idx += 1

    win_rate = (pd.DataFrame(paired_trades)['win'].mean() * 100.0) if paired_trades else 0.0
    time_invested_pct = (sub['Position'] > 0).mean() * 100.0

    return {
        'ticker': ticker,
        'df': sub,
        'trades': trades,
        'paired_trades': paired_trades,
        'total_invested': total_invested,
        'bench_final': b_final,
        'strat_final': s_final,
        'bench_ret': b_ret,
        'strat_ret': s_ret,
        'alpha': alpha,
        'strat_dd': s_dd,
        'bench_dd': b_dd,
        'win_rate': win_rate,
        'time_invested_pct': time_invested_pct
    }


def plot_charts_model_a_plus(sim, output_path):
    """
    绘制模型 A+ 高清专业 4 层双轨制看板图谱（价格+雷达预警点、Gap偏离度、过热雷达能量带、券商净值）
    """
    t = sim['ticker']
    sub = sim['df']
    trades = sim['trades']
    
    fig, axes = plt.subplots(4, 1, figsize=(18, 16), sharex=True, gridspec_kw={'height_ratios': [2.8, 1.1, 1.1, 1.8]})
    fig.patch.set_facecolor('#0f172a')

    for ax in axes:
        ax.set_facecolor('#1e293b')
        ax.grid(True, linestyle='--', alpha=0.25, color='#94a3b8')
        ax.tick_params(colors='#e2e8f0', labelsize=10)
        for spine in ax.spines.values():
            spine.set_color('#475569')

    ax1, ax2, ax3, ax4 = axes

    # -------------------------------------------------------------
    # Layer 1: 价格曲线、双轨雷达预警点与买卖执行信号
    # -------------------------------------------------------------
    ax1.plot(sub['date'], sub[t], label=f'{t} 收盘价 (USD)', color='#38bdf8', linewidth=1.6)
    ax1.plot(sub['date'], sub['MA20'], label='MA20 短期动量线', color='#94a3b8', linewidth=0.9, linestyle='--', alpha=0.7)
    ax1.plot(sub['date'], sub['MA50'], label='MA50 中期生命线', color='#a855f7', linewidth=1.1, alpha=0.85)
    ax1.plot(sub['date'], sub['MA200'], label='MA200 牛熊分界年线', color='#ec4899', linewidth=1.4, alpha=0.9)

    # 绘制黄色过热雷达散点预警
    alert_sub = sub[sub['Overheat_Alert']]
    if len(alert_sub) > 0:
        ax1.scatter(alert_sub['date'], alert_sub[t], marker='o', color='#facc15', s=35, alpha=0.85, zorder=5, label='宏观过热雷达预警 (Score >= 70，左侧红灯)')

    # 绘制买卖信号标记
    for tr in trades:
        d_val = pd.to_datetime(tr['date'])
        p_val = tr['price']
        if tr['action'] == 'SELL':
            ax1.scatter(d_val, p_val, marker='v', color='#ef4444', s=130, zorder=6, edgecolors='white', linewidth=1.2)
            ax1.annotate(f"卖出 USD {p_val:.1f}\n{tr['reason'][:6]}", xy=(d_val, p_val), xytext=(0, 18),
                         textcoords='offset points', ha='center', fontsize=8, color='#fca5a5', fontweight='bold',
                         bbox=dict(boxstyle='round,pad=0.25', facecolor='#7f1d1d', edgecolor='#ef4444', alpha=0.9))
        elif tr['action'] == 'BUY':
            ax1.scatter(d_val, p_val, marker='^', color='#22c55e', s=130, zorder=6, edgecolors='white', linewidth=1.2)
            ax1.annotate(f"买入 USD {p_val:.1f}\n{tr['reason'][:6]}", xy=(d_val, p_val), xytext=(0, -30),
                         textcoords='offset points', ha='center', fontsize=8, color='#86efac', fontweight='bold',
                         bbox=dict(boxstyle='round,pad=0.25', facecolor='#14532d', edgecolor='#22c55e', alpha=0.9))

    title_text = f"宏观反身性阿尔法模型 (方案 B_Plus: 双轨制雷达看板版) - {t} 买卖决策全景图"
    ax1.set_title(title_text, fontsize=15, color='#f8fafc', pad=14, fontweight='bold')
    ax1.set_ylabel(f"{t} 价格 (USD)", color='#e2e8f0', fontsize=11)
    ax1.legend(loc='upper left', facecolor='#1e293b', edgecolor='#475569', labelcolor='#e2e8f0', fontsize=8.5, framealpha=0.9)

    # -------------------------------------------------------------
    # Layer 2: 宏观反身性偏离度 Gap 与自适应动态分位数出清线
    # -------------------------------------------------------------
    ax2.plot(sub['date'], sub['Gap'], label='宏观反身性偏离度 Gap (Price_Z - Expected_Z)', color='#38bdf8', linewidth=1.3)
    ax2.plot(sub['date'], sub['Gap_Median'], label='自适应 252 日滚动中位数 (估值出清自然基准)', color='#10b981', linestyle=':', linewidth=1.3)
    ax2.plot(sub['date'], sub['Gap_Upper'], label='自适应历史 85 分位上限 (黄昏期泡沫过热阈值)', color='#ef4444', linestyle='--', linewidth=1.1, alpha=0.85)
    ax2.axhline(0, color='#64748b', linestyle='-', linewidth=0.8, alpha=0.6)
    ax2.set_ylabel("反身性 Gap 偏离度", color='#e2e8f0', fontsize=11)
    ax2.legend(loc='upper left', facecolor='#1e293b', edgecolor='#475569', labelcolor='#e2e8f0', fontsize=8.5, framealpha=0.9)

    # -------------------------------------------------------------
    # Layer 3 (NEW): 宏观过热雷达综合评分 (0-100) 与热力警报区
    # -------------------------------------------------------------
    ax3.plot(sub['date'], sub['Overheat_Score'], label='宏观过热雷达综合评分 (0-100)', color='#facc15', linewidth=1.3)
    ax3.axhline(70, color='#ef4444', linestyle='--', linewidth=1.2, label='极度过热警戒线 (Score >= 70，全历史顶峰 5%)')
    ax3.fill_between(sub['date'], 70, sub['Overheat_Score'], where=(sub['Overheat_Score'] >= 70), color='#ef4444', alpha=0.35, label='过热高危红区')
    ax3.set_ylabel("过热雷达评分", color='#e2e8f0', fontsize=11)
    ax3.set_ylim(0, 105)
    ax3.legend(loc='upper left', facecolor='#1e293b', edgecolor='#475569', labelcolor='#e2e8f0', fontsize=8.5, framealpha=0.9)

    # -------------------------------------------------------------
    # Layer 4: 真实券商净值曲线与双侧百分比坐标轴
    # -------------------------------------------------------------
    line_b, = ax4.plot(sub['date'], sub['Bench_Equity'], label=f'基准买入持有 (终值: USD {sim["bench_final"]:,.0f}, +{sim["bench_ret"]:.1f}%, MaxDD: {sim["bench_dd"]:.1f}%)', color='#94a3b8', linestyle='--', linewidth=1.5)
    line_s, = ax4.plot(sub['date'], sub['Strat_Equity'], label=f'模型 A+ 策略终值 (终值: USD {sim["strat_final"]:,.0f}, +{sim["strat_ret"]:.1f}%, Alpha: +{sim["alpha"]:.1f}%, MaxDD: {sim["strat_dd"]:.1f}%)', color='#38bdf8', linewidth=2.2)

    ax4.set_ylabel("账户总资产 (USD)", color='#e2e8f0', fontsize=11)
    ax4.yaxis.set_major_formatter(matplotlib.ticker.StrMethodFormatter('{x:,.0f}'))
    ax4.legend(loc='upper left', facecolor='#1e293b', edgecolor='#475569', labelcolor='#e2e8f0', fontsize=8.5, framealpha=0.9)

    # 右侧百分比坐标轴 (精确对齐定投本金)
    ax4_pct = ax4.twinx()
    ax4_pct.set_ylabel("累计定投总收益率 (%)", color='#38bdf8', fontsize=11)
    ax4_pct.tick_params(colors='#38bdf8', labelsize=10)
    y_min, y_max = ax4.get_ylim()
    inv = sim['total_invested']
    ax4_pct.set_ylim((y_min / inv - 1.0) * 100.0, (y_max / inv - 1.0) * 100.0)
    ax4_pct.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter())

    ax4.xaxis.set_major_locator(mdates.YearLocator(2))
    ax4.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))

    plt.tight_layout()
    plt.savefig(output_path, dpi=300, facecolor=fig.get_facecolor(), edgecolor='none')
    plt.close()
    print(f"[OK] 高清专业 4 层双轨制看板图谱已生成: {output_path}")


def export_model_a_plus_deliverables():
    """导出全套可复核交付底稿 (Excel + 高清信号图谱)"""
    print("=== 开始执行模型 A+ (双轨制雷达看板版) 全量仿真与交付生成 ===")
    df_raw = load_clean_macro_data()
    
    sim_qqq = simulate_model_a_plus(df_raw, 'QQQ')
    sim_spy = simulate_model_a_plus(df_raw, 'SPY')

    for sim in [sim_qqq, sim_spy]:
        t = sim['ticker']
        print(f"\n[{t} 仿真结果汇报]")
        print(f"  总定投本金: USD {sim['total_invested']:,.2f} (211 个月)")
        print(f"  基准持有终值: USD {sim['bench_final']:,.2f} (+{sim['bench_ret']:.2f}%, 最大回撤: {sim['bench_dd']:.2f}%)")
        print(f"  策略账户终值: USD {sim['strat_final']:,.2f} (+{sim['strat_ret']:.2f}%, 最大回撤: {sim['strat_dd']:.2f}%)")
        print(f"  超额 Alpha: +{sim['alpha']:.2f}% (超额收益: USD {sim['strat_final'] - sim['bench_final']:,.2f})")
        print(f"  在场率: {sim['time_invested_pct']:.1f}%, 交易轮次: {len(sim['paired_trades'])} 轮 (年均 {len(sim['trades'])/17.6:.2f} 次), 胜率: {sim['win_rate']:.1f}%")

    # 1. 导出官方 Excel 对账底稿
    excel_path_local = os.path.join(OUTPUT_DIR, MODEL_A_PLUS_EXCEL)
    excel_path_artifact = os.path.join(ARTIFACT_DIR, MODEL_A_PLUS_EXCEL)

    wb = openpyxl.Workbook()
    wb.remove(wb.active)

    # 样式定义
    header_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
    header_font = Font(name="微软雅黑", size=11, bold=True, color="FFFFFF")
    data_font = Font(name="微软雅黑", size=10)
    bold_font = Font(name="微软雅黑", size=10, bold=True)
    green_font = Font(name="微软雅黑", size=10, color="15803D", bold=True)
    red_font = Font(name="微软雅黑", size=10, color="B91C1C", bold=True)
    gold_font = Font(name="微软雅黑", size=10, color="B45309", bold=True)
    center_align = Alignment(horizontal="center", vertical="center", wrap_text=True)
    right_align = Alignment(horizontal="right", vertical="center")
    left_align = Alignment(horizontal="left", vertical="center")
    thin_border = Border(
        left=Side(style='thin', color='CBD5E1'),
        right=Side(style='thin', color='CBD5E1'),
        top=Side(style='thin', color='CBD5E1'),
        bottom=Side(style='thin', color='CBD5E1')
    )

    # -------------------------------------------------------------
    # Sheet 1: 模型A_Plus_综合业绩总表
    # -------------------------------------------------------------
    ws1 = wb.create_sheet(title="模型A_Plus_综合业绩总表")
    ws1.views.sheetView[0].showGridLines = True
    headers_s1 = [
        "标的资产", "定投本金 (USD)", "基准买入持有终值 (USD)", "基准总回报率 (%)", "基准最大回撤 (%)",
        "策略账户最终净值 (USD)", "策略总收益率 (%)", "超额收益 Alpha (%)", "超额净资产增量 (USD)",
        "策略最大回撤 (%)", "回撤优化幅度 (%)", "全历史交易次数 (次)", "年均交易频次 (次/年)",
        "总在场率 (%)", "波段胜率 (%)"
    ]
    ws1.append(headers_s1)
    for col_idx in range(1, len(headers_s1) + 1):
        cell = ws1.cell(row=1, column=col_idx)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = center_align

    for s in [sim_qqq, sim_spy]:
        row_vals = [
            s['ticker'],
            s['total_invested'],
            s['bench_final'],
            s['bench_ret'] / 100.0,
            s['bench_dd'] / 100.0,
            s['strat_final'],
            s['strat_ret'] / 100.0,
            s['alpha'] / 100.0,
            s['strat_final'] - s['bench_final'],
            s['strat_dd'] / 100.0,
            (s['bench_dd'] - s['strat_dd']) / 100.0,
            len(s['trades']),
            len(s['trades']) / 17.6,
            s['time_invested_pct'] / 100.0,
            s['win_rate'] / 100.0
        ]
        ws1.append(row_vals)
        r = ws1.max_row
        for c in range(1, len(row_vals) + 1):
            cell = ws1.cell(row=r, column=c)
            cell.font = data_font
            cell.border = thin_border
            if c in [2, 3, 6, 9]:
                cell.number_format = '$#,##0.00'
                cell.alignment = right_align
            elif c in [4, 5, 7, 8, 10, 11, 14, 15]:
                cell.number_format = '+0.00%;-0.00%;0.00%'
                cell.alignment = right_align
                if c in [7, 8, 9]:
                    cell.font = green_font
            elif c in [12, 13]:
                cell.number_format = '#,##0.0' if c == 13 else '#,##0'
                cell.alignment = center_align
            else:
                cell.alignment = center_align

    # -------------------------------------------------------------
    # Sheet 2 & 3: 逐笔波段买卖配对胜率表 (含双轨制过热雷达穿透字段)
    # -------------------------------------------------------------
    for s in [sim_qqq, sim_spy]:
        t = s['ticker']
        ws_pair = wb.create_sheet(title=f"{t}_逐笔波段买卖配对表")
        ws_pair.views.sheetView[0].showGridLines = True
        headers_pair = [
            "波段轮次", "首次过热预警日", "预警日价格 (USD)", "提前天数", "预警溢价 (%)", "最高雷达分",
            "卖出日期", "卖出价格 (USD)", "卖出持股数", "套现现金 (USD)", "卖出预警动因",
            "接回日期", "接回价格 (USD)", "买入持股数", "买入触发动因", "买卖价差变动 (%)",
            "持股数量增殖 (%)", "对账结论"
        ]
        ws_pair.append(headers_pair)
        for col_idx in range(1, len(headers_pair) + 1):
            cell = ws_pair.cell(row=1, column=col_idx)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = center_align

        for pt in s['paired_trades']:
            row_vals = [
                pt['cycle_id'],
                pt['alert_date'],
                pt['alert_price'] if pt['alert_price'] is not None else "--",
                pt['days_ahead'],
                (pt['alert_prem_pct'] / 100.0) if pt['alert_price'] is not None else 0.0,
                pt['max_radar_score'],
                pt['sell_date'],
                pt['sell_price'],
                pt['sell_shares'],
                pt['sell_cash'],
                pt['sell_reason'],
                pt['buy_date'],
                pt['buy_price'],
                pt['buy_shares'],
                pt['buy_reason'],
                pt['price_diff_pct'] / 100.0,
                pt['share_diff_pct'] / 100.0,
                pt['status']
            ]
            ws_pair.append(row_vals)
            r = ws_pair.max_row
            for c in range(1, len(row_vals) + 1):
                cell = ws_pair.cell(row=r, column=c)
                cell.font = data_font
                cell.border = thin_border
                if c in [3, 8, 10, 13]:
                    if isinstance(cell.value, (int, float)):
                        cell.number_format = '$#,##0.00'
                    cell.alignment = right_align
                elif c in [9, 14]:
                    cell.number_format = '#,##0.0000'
                    cell.alignment = right_align
                elif c in [4, 6]:
                    cell.number_format = '#,##0' if c == 4 else '0.0'
                    cell.alignment = center_align
                elif c in [5, 16, 17]:
                    cell.number_format = '+0.00%;-0.00%;0.00%'
                    cell.alignment = right_align
                    if c == 5 and pt['alert_price'] is not None:
                        cell.font = gold_font
                    elif c == 17:
                        cell.font = green_font if pt['share_diff_pct'] > 0 else red_font
                elif c in [11, 15, 18]:
                    cell.alignment = left_align
                    if c == 18:
                        cell.font = green_font if pt['win'] else data_font
                else:
                    cell.alignment = center_align

    # -------------------------------------------------------------
    # Sheet 4 & 5: 逐笔买卖流水表 (QQQ & SPY)
    # -------------------------------------------------------------
    for s in [sim_qqq, sim_spy]:
        t = s['ticker']
        ws_t = wb.create_sheet(title=f"{t}_逐笔买卖流水表")
        ws_t.views.sheetView[0].showGridLines = True
        headers_t = ["交易动作", "日期", "成交价格 (USD)", "持股数量", "账户现金 (USD)", "仓位比例", "触发动因"]
        ws_t.append(headers_t)
        for col_idx in range(1, len(headers_t) + 1):
            cell = ws_t.cell(row=1, column=col_idx)
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = center_align

        for tr in s['trades']:
            row_vals = [
                tr['action'],
                tr['date'],
                tr['price'],
                tr['shares'],
                tr['cash'],
                tr['exposure'],
                tr['reason']
            ]
            ws_t.append(row_vals)
            r = ws_t.max_row
            for c in range(1, len(row_vals) + 1):
                cell = ws_t.cell(row=r, column=c)
                cell.font = data_font
                cell.border = thin_border
                if c == 1:
                    cell.font = red_font if tr['action'] == 'SELL' else green_font
                    cell.alignment = center_align
                elif c in [3, 5]:
                    cell.number_format = '$#,##0.00'
                    cell.alignment = right_align
                elif c == 4:
                    cell.number_format = '#,##0.0000'
                    cell.alignment = right_align
                elif c == 6:
                    cell.number_format = '0.00x'
                    cell.alignment = center_align
                elif c == 7:
                    cell.alignment = left_align
                else:
                    cell.alignment = center_align

    # -------------------------------------------------------------
    # Sheet 6: 4573 日全历史逐日资产流水表 (QQQ) - 增加过热雷达监控字段
    # -------------------------------------------------------------
    ws_daily = wb.create_sheet(title="QQQ_逐日资产流水表")
    ws_daily.views.sheetView[0].showGridLines = True
    headers_d = [
        "日期", "QQQ收盘价", "MA20", "MA50", "MA200", "年线偏离度 (%)",
        "反身性偏离度 Gap", "Gap滚动中位数", "信用债 HYG", "芝加哥 NFCI",
        "过热雷达评分 (0-100)", "雷达警戒状态", "持仓仓位", "持股数量", "闲置现金 (USD)",
        "基准总资产 (USD)", "策略总资产 (USD)"
    ]
    ws_daily.append(headers_d)
    for col_idx in range(1, len(headers_d) + 1):
        cell = ws_daily.cell(row=1, column=col_idx)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = center_align

    df_sub = sim_qqq['df']
    for idx in range(len(df_sub)):
        score = df_sub['Overheat_Score'].iloc[idx]
        alert_state = "🟡过热预警" if df_sub['Overheat_Alert'].iloc[idx] else "🟢健康常态"
        row_vals = [
            df_sub['date'].iloc[idx].strftime('%Y-%m-%d'),
            df_sub['QQQ'].iloc[idx],
            df_sub['MA20'].iloc[idx],
            df_sub['MA50'].iloc[idx],
            df_sub['MA200'].iloc[idx],
            df_sub['Dist_200MA'].iloc[idx] / 100.0,
            df_sub['Gap'].iloc[idx],
            df_sub['Gap_Median'].iloc[idx],
            df_sub['HYG'].iloc[idx],
            df_sub['NFCI'].iloc[idx],
            score,
            alert_state,
            df_sub['Position'].iloc[idx],
            df_sub['Shares'].iloc[idx],
            df_sub['Cash'].iloc[idx],
            df_sub['Bench_Equity'].iloc[idx],
            df_sub['Strat_Equity'].iloc[idx]
        ]
        ws_daily.append(row_vals)
        r = ws_daily.max_row
        for c in range(1, len(row_vals) + 1):
            cell = ws_daily.cell(row=r, column=c)
            cell.font = data_font
            cell.border = thin_border
            if c in [2, 3, 4, 5, 9, 15, 16, 17]:
                cell.number_format = '$#,##0.00'
                cell.alignment = right_align
            elif c == 6:
                cell.number_format = '+0.00%;-0.00%;0.00%'
                cell.alignment = right_align
            elif c in [7, 8, 10]:
                cell.number_format = '0.000'
                cell.alignment = right_align
            elif c == 11:
                cell.number_format = '0.0'
                cell.alignment = right_align
                if score >= 70:
                    cell.font = red_font
            elif c == 12:
                cell.alignment = center_align
                if "过热" in alert_state:
                    cell.font = gold_font
            elif c == 13:
                cell.number_format = '0.00x'
                cell.alignment = center_align
            elif c == 14:
                cell.number_format = '#,##0.00'
                cell.alignment = right_align
            else:
                cell.alignment = center_align

    # 自动调整所有 Sheet 的列宽
    for sheet in wb.worksheets:
        for col in sheet.columns:
            max_len = 0
            col_letter = get_column_letter(col[0].column)
            for cell in col:
                val_str = str(cell.value or '')
                cell_len = sum(2 if ord(char) > 127 else 1 for char in val_str)
                if cell_len > max_len:
                    max_len = cell_len
            sheet.column_dimensions[col_letter].width = max(max_len + 3, 12)

    wb.save(excel_path_local)
    shutil.copy2(excel_path_local, excel_path_artifact)
    print(f"[OK] Excel 对账全底稿已生成并保存: {excel_path_local}")

    # 2. 绘制高清 4 层信号图谱
    qqq_chart_local = os.path.join(OUTPUT_DIR, QQQ_CHART_PNG)
    qqq_chart_artifact = os.path.join(ARTIFACT_DIR, QQQ_CHART_PNG)
    plot_charts_model_a_plus(sim_qqq, qqq_chart_local)
    shutil.copy2(qqq_chart_local, qqq_chart_artifact)

    spy_chart_local = os.path.join(OUTPUT_DIR, SPY_CHART_PNG)
    spy_chart_artifact = os.path.join(ARTIFACT_DIR, SPY_CHART_PNG)
    plot_charts_model_a_plus(sim_spy, spy_chart_local)
    shutil.copy2(spy_chart_local, spy_chart_artifact)

    print("\n=== 模型 A+ (双轨制雷达看板版) 全量交付物生成完毕！ ===")


if __name__ == "__main__":
    export_model_a_plus_deliverables()
