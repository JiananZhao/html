# -*- coding: utf-8 -*-
"""
========================================================================================
项目名称：宏观反身性阿尔法模型 (多资产/多行业ETF 全周期对账与交付物生成引擎)
标的资产：QQQ (科技巨头), SPY (标普500), SMH (半导体), SOXX (半导体费城), IGV (软件SaaS), XLE (能源)
数据源：100% 脱机闭环读取 market_data_local.csv
交付物：
  1. 宏观反身性阿尔法模型_多资产全周期对账总表.xlsx (包含绩效总表、逐笔对账表、逐日流水表)
  2. 4 张高清 4 层信号与净值图谱 (SMH, SOXX, IGV, XLE)
========================================================================================
"""

import sys
import os
sys.stdout.reconfigure(encoding='utf-8')

import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

# 强制规范：中文字体与负号设置 (杜绝 LaTeX 冲突与乱码)
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans', 'sans-serif']
plt.rcParams['axes.unicode_minus'] = False

BASE_DIR = "e:/AI/Github_AIProject/html"
DATA_FILE = os.path.join(BASE_DIR, "market_data_local.csv")
EXCEL_OUTPUT = os.path.join(BASE_DIR, "宏观反身性阿尔法模型_多资产全周期对账总表.xlsx")

df_raw = pd.read_csv(DATA_FILE)
df_raw['date'] = pd.to_datetime(df_raw['date']).dt.tz_localize(None)
df_raw = df_raw.sort_values('date').reset_index(drop=True)

# 资产配置矩阵与参数定义
ASSET_CONFIG = {
    'QQQ': {
        'name': '纳斯达克100 ETF',
        'type': '核心科技成长',
        'macro_anchor': 'HYG',
        'dist_bubble_th': 5.0,
        'price_filter': 'MA20',
        'is_energy': False
    },
    'SPY': {
        'name': '标普500 ETF',
        'type': '宽基大盘底仓',
        'macro_anchor': 'HYG',
        'dist_bubble_th': 5.0,
        'price_filter': 'MA20',
        'is_energy': False
    },
    'SMH': {
        'name': 'VanEck 半导体 ETF',
        'type': '高贝塔半导体',
        'macro_anchor': 'HYG',
        'dist_bubble_th': 15.0,
        'price_filter': 'MA50',
        'is_energy': False
    },
    'SOXX': {
        'name': 'iShares 半导体 ETF',
        'type': '高贝塔半导体',
        'macro_anchor': 'HYG',
        'dist_bubble_th': 15.0,
        'price_filter': 'MA50',
        'is_energy': False
    },
    'IGV': {
        'name': 'iShares 扩展科技软件 ETF',
        'type': '云计算与SaaS',
        'macro_anchor': 'HYG',
        'dist_bubble_th': 10.0,
        'price_filter': 'MA50',
        'is_energy': False
    },
    'XLE': {
        'name': '能源精选行业 SPDR ETF',
        'type': '大宗商品与能源',
        'macro_anchor': 'OIL',
        'dist_bubble_th': 30.0,
        'price_filter': 'MA50',
        'is_energy': True
    }
}

def simulate_asset(ticker, cfg):
    macro_anchor = cfg['macro_anchor']
    is_energy = cfg['is_energy']
    dist_bubble_th = cfg['dist_bubble_th']
    price_filter = cfg['price_filter']

    sub = df_raw[['date', ticker, macro_anchor, 'NFCI', 'BAA10Y', 'Real_Yield', 'DXY']].copy()
    sub['MA10'] = sub[ticker].rolling(10).mean()
    sub['MA20'] = sub[ticker].rolling(20).mean()
    sub['MA50'] = sub[ticker].rolling(50).mean()
    sub['MA200'] = sub[ticker].rolling(200).mean()
    sub['Dist_200MA'] = (sub[ticker] - sub['MA200']) / sub['MA200'] * 100.0
    sub['MA200_Slope20'] = (sub['MA200'] - sub['MA200'].shift(20)) / sub['MA200'].shift(20) * 100.0

    sub['Macro_MA50'] = sub[macro_anchor].rolling(50).mean()
    sub['Macro_MA200'] = sub[macro_anchor].rolling(200).mean()
    sub['BAA_MA60'] = sub['BAA10Y'].rolling(60).mean()
    sub['BAA_Stress'] = sub['BAA10Y'] > sub['BAA_MA60']
    sub['RY_Surge'] = (sub['Real_Yield'] - sub['Real_Yield'].rolling(60).min()) > 0.40

    sub['NFCI_Roll_Mean'] = sub['NFCI'].rolling(252).mean()
    sub['NFCI_Roll_Std'] = sub['NFCI'].rolling(252).std()
    sub['NFCI_Z'] = (sub['NFCI'] - sub['NFCI_Roll_Mean']) / (sub['NFCI_Roll_Std'] + 1e-8)

    # 反身性偏离度 Gap (动态 Beta 定价)
    sub['Price_Z'] = (sub[ticker] - sub[ticker].rolling(200).mean()) / (sub[ticker].rolling(200).std() + 1e-8)
    sub['Macro_Z'] = (sub[macro_anchor] - sub[macro_anchor].rolling(200).mean()) / (sub[macro_anchor].rolling(200).std() + 1e-8)
    roll_cov = sub['Price_Z'].rolling(252).cov(sub['Macro_Z'])
    roll_var = sub['Macro_Z'].rolling(252).var()
    sub['Dynamic_Beta'] = (roll_cov / (roll_var + 1e-8)).clip(lower=-2.0, upper=2.0)
    sub['Expected_Price_Z'] = sub['Macro_Z'] * sub['Dynamic_Beta']
    sub['Gap'] = sub['Price_Z'] - sub['Expected_Price_Z']

    sub['Gap_Max_45'] = sub['Gap'].rolling(45, min_periods=1).max()
    sub['PriceZ_Max_45'] = sub['Price_Z'].rolling(45, min_periods=1).max()
    sub['Gap_Median'] = sub['Gap'].rolling(252, min_periods=20).median()
    sub['Gap_Upper'] = sub['Gap'].expanding(min_periods=20).quantile(0.85)

    # 宏观过热雷达分 (0 - 100)
    z_score = np.clip((sub['Price_Z'] - 0.5) / 1.5 * 40.0, 0.0, 40.0)
    dist_score = np.clip((sub['Dist_200MA'] - 5.0) / 15.0 * 30.0, 0.0, 30.0)
    gap_score = np.clip((sub['Gap'] / sub['Gap_Upper']) * 15.0, 0.0, 30.0)
    sub['Overheat_Score'] = z_score + dist_score + gap_score
    sub['Overheat_Alert'] = sub['Overheat_Score'] >= 70.0

    # 攻防两端信号定义
    if not is_energy:
        # 宽基与科技类资产
        sub['Cond_Bubble'] = (
            (sub['Gap_Max_45'] > sub['Gap_Upper']) & 
            (sub['PriceZ_Max_45'] > 1.5) & 
            (sub['Dist_200MA'] > dist_bubble_th) & 
            (sub['NFCI'] > -0.50) & 
            sub['BAA_Stress'] & 
            (sub[ticker] < sub[price_filter])
        )
        sub['Macro_Crisis'] = (
            (sub[macro_anchor] < sub['Macro_MA200']) & 
            sub['RY_Surge'] & 
            (sub['NFCI_Z'] > 1.2) & 
            (sub['NFCI'] > -0.50)
        )
        sub['Cond_Bear'] = sub['Macro_Crisis'] & (sub[ticker] < sub['MA50']) & (sub[ticker] < sub['MA200'])
    else:
        # 能源专属结构性商品周期模型
        sub['Cond_Bubble'] = False # 能源股中长期受大宗商品与现金流主导，非成长股估值泡沫
        # 结构性大宗死叉熊市：原油死叉 + XLE死叉 + 200MA明确下行斜率 + 破位
        sub['Structural_Energy_Bear'] = (
            (sub['Macro_MA50'] < sub['Macro_MA200']) & 
            (sub['MA50'] < sub['MA200']) & 
            (sub['MA200_Slope20'] < -1.2) & 
            (sub['Dist_200MA'] < -5.0)
        )
        # 流动性暴跌危机 (如2020负油价/流动性冻结)
        hyg_200 = df_raw['HYG'].rolling(200).mean()
        sub['Crisis_Crash'] = (
            (df_raw['HYG'] < hyg_200) & 
            (sub[macro_anchor] < sub['Macro_MA200']) & 
            (sub['Dist_200MA'] < -15.0) & 
            (sub[ticker] < sub['MA50'])
        )
        sub['Cond_Bear'] = sub['Structural_Energy_Bear'] | sub['Crisis_Crash']

    sub['Sell_Signal'] = sub['Cond_Bubble'] | sub['Cond_Bear']

    # 买入滤波
    sub['Above_MA50_Conf'] = (sub[ticker] > sub['MA50']).rolling(3, min_periods=1).sum() == 3
    sub['Above_MA20_Conf'] = (sub[ticker] > sub['MA20']).rolling(3, min_periods=1).sum() == 3
    sub['Cond_Panic'] = (sub['Dist_200MA'].rolling(10, min_periods=1).min() < -10.0) & (sub[ticker] > sub['MA10'])

    # 真实券商记账 (从 2009-01-01 开始，涵盖完整 17.6 年)
    s_sub = sub[sub['date'] >= '2009-01-01'].reset_index(drop=True)
    dca_monthly = 1000.0
    tot_inv = 0.0
    b_sh = 0.0
    s_sh = 0.0
    s_cash = 0.0
    pos = 1.0
    curr_m = -1
    exit_reg = None
    trades = []
    
    bench_vals = []
    strat_vals = []
    positions = []
    daily_actions = []

    for i in range(len(s_sub)):
        p = s_sub[ticker].iloc[i]
        d_str = s_sub['date'].iloc[i].strftime('%Y-%m-%d')
        m = s_sub['date'].iloc[i].month

        # 月度定投资金注入
        if m != curr_m:
            tot_inv += dca_monthly
            b_sh += dca_monthly / p
            if pos > 0:
                s_sh += dca_monthly / p
            else:
                s_cash += dca_monthly
            curr_m = m

        p_val = s_sub[ticker].iloc[i]
        gap = s_sub['Gap'].iloc[i]
        gap_med = s_sub['Gap_Median'].iloc[i]
        action_today = 'HOLD' if pos > 0 else 'CASH'

        # 卖出判定
        if pos > 0 and s_sub['Sell_Signal'].iloc[i]:
            s_cash += s_sh * p
            is_bub = s_sub['Cond_Bubble'].iloc[i]
            exit_reg = 'BUBBLE' if is_bub else 'BEAR'
            r_reason = '宏观估值泡沫高位止盈' if is_bub else ('结构性大宗死叉熊市避险' if is_energy else '系统宏观紧缩熊市避险')
            trades.append({
                'ticker': ticker,
                'action': 'SELL',
                'date': d_str,
                'price': p,
                'shares': s_sh,
                'cash': s_cash,
                'reason': r_reason
            })
            action_today = 'SELL'
            s_sh = 0.0
            pos = 0.0

        # 买入判定
        elif pos == 0.0:
            can_buy = False
            b_reason = ""

            if not is_energy:
                if exit_reg == 'BUBBLE':
                    if s_sub['Cond_Panic'].iloc[i]:
                        can_buy = True
                        b_reason = '极值黄金坑抄底'
                    elif (gap < gap_med) and s_sub['Above_MA20_Conf'].iloc[i] and s_sub['Above_MA50_Conf'].iloc[i]:
                        can_buy = True
                        b_reason = '估值出清且右侧重构主升'
                    elif (p_val > trades[-1]['price'] * 1.02) and s_sub['Above_MA20_Conf'].iloc[i] and s_sub['Above_MA50_Conf'].iloc[i]:
                        can_buy = True
                        b_reason = '突破卖出价右侧防踏空接回'
                elif exit_reg == 'BEAR':
                    macro_healed = (s_sub[macro_anchor].iloc[i] > s_sub['Macro_MA200'].iloc[i])
                    price_healed = s_sub['Above_MA50_Conf'].iloc[i]
                    if macro_healed and price_healed:
                        can_buy = True
                        b_reason = '宏观锚先导修复且趋势重构'
            else:
                # 能源股右侧买入：确立右侧金叉反转 或 站稳年线且年线停止下行
                ma50 = s_sub['MA50'].iloc[i]
                ma200 = s_sub['MA200'].iloc[i]
                slope20 = s_sub['MA200_Slope20'].iloc[i]
                golden_cross = (ma50 > ma200) and (p_val > ma50)
                reversal_confirmed = (p_val > ma200) and (slope20 >= -0.1) and s_sub['Above_MA50_Conf'].iloc[i]
                if golden_cross or reversal_confirmed:
                    can_buy = True
                    b_reason = '确立右侧金叉反转'

            if can_buy:
                s_sh += s_cash / p
                s_cash = 0.0
                pos = 1.0
                exit_reg = None
                action_today = 'BUY'
                trades.append({
                    'ticker': ticker,
                    'action': 'BUY',
                    'date': d_str,
                    'price': p,
                    'shares': s_sh,
                    'cash': s_cash,
                    'reason': b_reason
                })

        b_equity = b_sh * p
        s_equity = s_sh * p + s_cash
        bench_vals.append(b_equity)
        strat_vals.append(s_equity)
        positions.append(pos)
        daily_actions.append(action_today)

    s_sub['Bench_Shares'] = b_sh # final
    s_sub['Bench_Equity'] = bench_vals
    s_sub['Strat_Equity'] = strat_vals
    s_sub['Position'] = positions
    s_sub['Action'] = daily_actions

    final_p = s_sub[ticker].iloc[-1]
    b_fin = b_sh * final_p
    s_fin = s_sh * final_p + s_cash
    b_ret = (b_fin / tot_inv - 1.0) * 100.0
    s_ret = (s_fin / tot_inv - 1.0) * 100.0
    alpha = s_ret - b_ret
    net_alpha_cash = s_fin - b_fin

    b_s = pd.Series(bench_vals)
    s_s = pd.Series(strat_vals)
    b_dd = (b_s / b_s.cummax() - 1.0).min() * 100.0
    s_dd = (s_s / s_s.cummax() - 1.0).min() * 100.0

    # 配对交易分析
    paired_trades = []
    for j in range(0, len(trades) - 1, 2):
        if trades[j]['action'] == 'SELL' and trades[j+1]['action'] == 'BUY':
            s_tr = trades[j]
            b_tr = trades[j+1]
            p_sell = s_tr['price']
            p_buy = b_tr['price']
            sh_sell = s_tr['shares']
            sh_buy = b_tr['shares']
            share_delta_pct = (sh_buy / (sh_sell + 1e-8) - 1.0) * 100.0
            price_change_pct = (p_buy / p_sell - 1.0) * 100.0
            
            d_sell = pd.to_datetime(s_tr['date'])
            d_buy = pd.to_datetime(b_tr['date'])
            holding_days = (d_buy - d_sell).days

            paired_trades.append({
                '资产代码': ticker,
                '资产名称': cfg['name'],
                '轮次': j // 2 + 1,
                '卖出日期': s_tr['date'],
                '卖出价格': round(p_sell, 2),
                '卖出原因': s_tr['reason'],
                '卖出股数': round(sh_sell, 2),
                '买入日期': b_tr['date'],
                '买入价格': round(p_buy, 2),
                '买入原因': b_tr['reason'],
                '买入股数': round(sh_buy, 2),
                '避险持币天数': holding_days,
                '期间标的涨跌': f"{price_change_pct:+.2f}%",
                '持股增益幅度': f"{share_delta_pct:+.2f}%",
                '是否实现低买高卖': '✅ 是' if p_buy < p_sell else '⚠️ 防踏空'
            })

    # 计算胜率 (低买高卖比例)
    win_count = sum(1 for pt in paired_trades if pt['买入价格'] < pt['卖出价格'])
    win_rate = (win_count / len(paired_trades) * 100.0) if paired_trades else 0.0

    perf_summary = {
        '标的资产': ticker,
        '资产名称': cfg['name'],
        '资产类别': cfg['type'],
        '宏观基准锚': cfg['macro_anchor'],
        '定投本金 (USD)': tot_inv,
        '基准终值 (USD)': b_fin,
        '基准总回报率': b_ret,
        '基准最大回撤': b_dd,
        '策略终值 (USD)': s_fin,
        '策略总回报率': s_ret,
        '策略最大回撤': s_dd,
        '超额阿尔法 (Alpha)': alpha,
        '最终超额财富 (USD)': net_alpha_cash,
        '回撤改善幅度': abs(b_dd) - abs(s_dd),
        '调仓轮次': len(paired_trades),
        '交易胜率 (有效低吸)': win_rate
    }

    return {
        'perf': perf_summary,
        'paired_trades': paired_trades,
        'trades': trades,
        'sub': s_sub
    }

def plot_4layer_chart(ticker, cfg, res):
    sub = res['sub']
    trades = res['trades']
    perf = res['perf']

    fig, axes = plt.subplots(4, 1, figsize=(16, 14), sharex=True, 
                             gridspec_kw={'height_ratios': [2.2, 1.0, 1.0, 1.2], 'hspace': 0.08})

    dates = pd.to_datetime(sub['date'])
    p = sub[ticker]

    # Panel 1: Price, MA, and Trades
    ax1 = axes[0]
    ax1.plot(dates, p, label=f'{ticker} 收盘价', color='#2d3436', linewidth=1.5)
    ax1.plot(dates, sub['MA20'], label='MA20 短期线', color='#0984e3', linewidth=1.0, alpha=0.7)
    ax1.plot(dates, sub['MA50'], label='MA50 中期趋势线', color='#e17055', linewidth=1.1, alpha=0.8)
    ax1.plot(dates, sub['MA200'], label='MA200 长期生命线', color='#6c5ce7', linewidth=1.4)

    # 标记买卖点
    sells = [t for t in trades if t['action'] == 'SELL']
    buys = [t for t in trades if t['action'] == 'BUY']
    if sells:
        s_d = pd.to_datetime([t['date'] for t in sells])
        s_p = [t['price'] for t in sells]
        ax1.scatter(s_d, s_p, color='#d63031', s=70, marker='v', zorder=5, label='策略卖出 (避险/止盈)')
    if buys:
        b_d = pd.to_datetime([t['date'] for t in buys])
        b_p = [t['price'] for t in buys]
        ax1.scatter(b_d, b_p, color='#00b894', s=70, marker='^', zorder=5, label='策略买入 (金叉/出清)')

    ax1.set_title(f"① {ticker} ({cfg['name']}) 价格与买卖决策点 | 终值: USD {perf['策略终值 (USD)']:,.0f} vs 基准 USD {perf['基准终值 (USD)']:,.0f} (Alpha: {perf['超额阿尔法 (Alpha)']:+.2f}%)", 
                  fontsize=13, fontweight='bold', pad=10)
    ax1.legend(loc='upper left', framealpha=0.9, facecolor='white', edgecolor='#b2bec3', fontsize=9)
    ax1.grid(True, linestyle='--', alpha=0.4)
    ax1.set_ylabel('价格 (USD)', fontsize=10)

    # Panel 2: Gap vs Upper Threshold
    ax2 = axes[1]
    ax2.plot(dates, sub['Gap'], label='宏观反身性偏离度 Gap', color='#6c5ce7', linewidth=1.2)
    ax2.plot(dates, sub['Gap_Upper'], label='自适应 85% 泡沫阈值', color='#d63031', linestyle='--', linewidth=1.1)
    ax2.axhline(0, color='gray', linestyle=':', alpha=0.5)
    ax2.set_title(f"② 宏观偏离度 Gap vs 估值泡沫上轨 (宏观先导锚: {cfg['macro_anchor']})", fontsize=11, fontweight='bold', pad=6)
    ax2.legend(loc='upper left', framealpha=0.9, facecolor='white', edgecolor='#b2bec3', fontsize=9)
    ax2.grid(True, linestyle='--', alpha=0.4)
    ax2.set_ylabel('Gap (Z-Score)', fontsize=10)

    # Panel 3: Overheat Radar Score
    ax3 = axes[2]
    ax3.plot(dates, sub['Overheat_Score'], label='综合过热雷达分 (0-100)', color='#e67e22', linewidth=1.2)
    ax3.axhline(70, color='#e74c3c', linestyle='--', linewidth=1.2, label='70分高危警报线')
    ax3.fill_between(dates, 70, sub['Overheat_Score'], where=(sub['Overheat_Score'] >= 70), color='#e74c3c', alpha=0.25)
    ax3.set_title("③ 0~100 宏观过热雷达分 (Overheat Radar Score)", fontsize=11, fontweight='bold', pad=6)
    ax3.legend(loc='upper left', framealpha=0.9, facecolor='white', edgecolor='#b2bec3', fontsize=9)
    ax3.grid(True, linestyle='--', alpha=0.4)
    ax3.set_ylabel('雷达评分', fontsize=10)
    ax3.set_ylim(0, 105)

    # Panel 4: Equity Curve
    ax4 = axes[3]
    ax4.plot(dates, sub['Strat_Equity'], label=f"反身性模型策略 (终值: USD {perf['策略终值 (USD)']:,.0f}, 回报 {perf['策略总回报率']:+.1f}%, 回撤 {perf['策略最大回撤']:.1f}%)", color='#e74c3c', linewidth=1.8)
    ax4.plot(dates, sub['Bench_Equity'], label=f"Buy & Hold 基准 (终值: USD {perf['基准终值 (USD)']:,.0f}, 回报 {perf['基准总回报率']:+.1f}%, 回撤 {perf['基准最大回撤']:.1f}%)", color='#7f8c8d', linestyle='--', linewidth=1.4)
    ax4.set_title("④ 真实券商定投净值对账曲线 (月定投 USD 1,000, 杜绝虚假复利)", fontsize=11, fontweight='bold', pad=6)
    ax4.legend(loc='upper left', framealpha=0.9, facecolor='white', edgecolor='#b2bec3', fontsize=9)
    ax4.grid(True, linestyle='--', alpha=0.4)
    ax4.set_ylabel('账户资产 (USD)', fontsize=10)
    ax4.xaxis.set_major_locator(mdates.YearLocator(2))
    ax4.xaxis.set_major_formatter(mdates.DateFormatter('%Y'))

    chart_filename = os.path.join(BASE_DIR, f"宏观反身性阿尔法模型_{ticker}买卖信号与净值对比图.png")
    plt.savefig(chart_filename, dpi=200, bbox_inches='tight')
    plt.close()
    print(f"✅ 图谱已生成: {chart_filename}")

def main():
    print("=" * 80)
    print("🚀 开始运行宏观反身性阿尔法模型多资产全量仿真...")
    print("=" * 80)

    perf_list = []
    all_paired_trades = []
    all_daily_records = []

    for ticker, cfg in ASSET_CONFIG.items():
        print(f"正在计算标的: {ticker} ({cfg['name']}) ...")
        res = simulate_asset(ticker, cfg)
        perf_list.append(res['perf'])
        all_paired_trades.extend(res['paired_trades'])

        # 整理逐日流水表
        sub_d = res['sub'][['date', ticker, 'MA20', 'MA50', 'MA200', 'Gap', 'Overheat_Score', 
                            'Action', 'Position', 'Strat_Equity', 'Bench_Equity']].copy()
        sub_d.insert(1, '标的代码', ticker)
        sub_d.insert(2, '资产名称', cfg['name'])
        sub_d = sub_d.rename(columns={
            'date': '交易日期',
            ticker: '收盘价 (USD)',
            'Action': '当日操作信号',
            'Position': '持仓状态 (1=满仓, 0=空仓)',
            'Strat_Equity': '策略总资产 (USD)',
            'Bench_Equity': '基准总资产 (USD)',
            'Overheat_Score': '宏观过热雷达分'
        })
        all_daily_records.append(sub_d)

        # 为 4 个新资产绘制高清图谱
        if ticker in ['SMH', 'SOXX', 'IGV', 'XLE']:
            plot_4layer_chart(ticker, cfg, res)

    # 导出 Excel 工作簿
    df_perf = pd.DataFrame(perf_list)
    df_paired = pd.DataFrame(all_paired_trades)
    df_daily = pd.concat(all_daily_records, ignore_index=True)

    with pd.ExcelWriter(EXCEL_OUTPUT, engine='openpyxl') as writer:
        df_perf.to_excel(writer, sheet_name='全资产绩效总览', index=False)
        df_paired.to_excel(writer, sheet_name='逐笔买卖配对表', index=False)
        df_daily.to_excel(writer, sheet_name='逐日真实券商流水总账', index=False)

    print(f"✅ 交付物总表已成功导出: {EXCEL_OUTPUT}")
    print("=" * 110)
    print(f"{'标的代码':<6} | {'资产名称':<12} | {'定投本金':<10} | {'基准终值 (回报)':<22} | {'策略终值 (回报)':<22} | {'Alpha':<10} | {'最大回撤 (策略 vs 基准)':<22} | {'轮次'}")
    print("=" * 110)
    for p in perf_list:
        b_str = f"USD {p['基准终值 (USD)']:,.0f} ({p['基准总回报率']:+.1f}%)"
        s_str = f"USD {p['策略终值 (USD)']:,.0f} ({p['策略总回报率']:+.1f}%)"
        dd_str = f"{p['策略最大回撤']:.1f}% vs {p['基准最大回撤']:.1f}%"
        print(f"{p['标的资产']:<6} | {p['资产名称']:<12} | USD {p['定投本金 (USD)']:<7,.0f} | {b_str:<22} | {s_str:<22} | {p['超额阿尔法 (Alpha)']:+9.2f}% | {dd_str:<22} | {p['调仓轮次']} 轮")
    print("=" * 110)

if __name__ == '__main__':
    main()
