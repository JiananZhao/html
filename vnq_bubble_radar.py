"""
====================================================================
房地产与 REITs 板块 (VNQ / XLRE) 行业微观内生泡沫与信用危机雷达全流程模型
====================================================================
【核心量化目标】
1. 建立针对房地产与 REITs 板块 (Real Estate) 的微观雷达与宏观利率/信用风险监控架构；
2. 覆盖 6 大核心细分地产业态 (共 34 家核心标的)：
   - 基础设施与数字数据中心 (Telecom & Data: AMT, CCI, EQIX, DLR)
   - 工业物流与自存仓储 (Industrial & Storage: PLD, PSA, EXR, REXR)
   - 商业零售与医疗养老 (Retail & Healthcare: SPG, O, KIM, WELL, VTR, NNN)
   - 住宅公寓与独栋租赁 (Residential: AVB, EQR, INVH, MAA, ESS)
   - 独栋住宅建筑商 (Homebuilders: DHI, LEN, NVR, PHM, TOL —— 周期先行指标)
   - 写字楼与传统商业地产 (Office & CRE: BXP, VNO, SLG, ARE, KRC —— CRE 风险中枢)
3. 4 维度独立雷达分位数标定 (0 ~ 100 Uniform 分布)：
   - 动力学抛物线过热度 (Score_Dynamics, 30%)
   - 宏观真实利率与债务息差压力 (Score_Valuation, 25%)
   - 跨业态分层广度与建商/写字楼剪刀差 (Score_Breadth, 30%)
   - 跨资产脱节分位数 (Score_Relative, 15%)
4. 真实券商记账体系 (追踪 strat_shares 与 strat_cash)，绝无虚假连乘；
5. 100% 本地脱机闭环读取 (real_estate_constituents_local.csv 与 market_data_local.csv)。
"""

import os
import sys
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# 保证控制台在 Windows 下 UTF-8 输出正常
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# 配置中文字体与负号显示，防止乱码，绝无未转义的 $ 符号
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False


class VNQBubbleRadar:
    def __init__(self, target_ticker='VNQ'):
        self.target_ticker = target_ticker
        self.macro_file = 'market_data_local.csv'
        self.const_file = 'real_estate_constituents_local.csv'
        self.df = None

        # 6 大地产业态构造成分
        self.real_estate_groups = {
            'Telecom_Data': ['AMT', 'CCI', 'EQIX', 'DLR'],
            'Industrial_Storage': ['PLD', 'PSA', 'EXR', 'REXR'],
            'Retail_Health': ['SPG', 'O', 'KIM', 'WELL', 'VTR', 'NNN'],
            'Residential': ['AVB', 'EQR', 'INVH', 'MAA', 'ESS'],
            'Homebuilders': ['DHI', 'LEN', 'NVR', 'PHM', 'TOL'],
            'Office_CRE': ['BXP', 'VNO', 'SLG', 'ARE', 'KRC']
        }

        # 宏观与系统性重要性权重配置
        self.group_weights = {
            'Telecom_Data': 0.20,
            'Industrial_Storage': 0.20,
            'Retail_Health': 0.20,
            'Residential': 0.15,
            'Homebuilders': 0.15,
            'Office_CRE': 0.10
        }

        # 4 维度雷达权重配置
        self.weights = {
            'dynamics': 0.30,
            'valuation': 0.25,
            'breadth': 0.30,
            'relative': 0.15
        }

    def load_and_preprocess(self):
        """100% 离线脱机闭环加载本地清洗好的地产与宏观数据"""
        if not os.path.exists(self.macro_file):
            raise FileNotFoundError(f"宏观主数据集缺失: {self.macro_file}")
        if not os.path.exists(self.const_file):
            raise FileNotFoundError(f"地产成分股主数据集缺失: {self.const_file}")

        df_m = pd.read_csv(self.macro_file)
        df_c = pd.read_csv(self.const_file)

        df = pd.merge(df_m, df_c, on='date', how='inner').sort_values('date').reset_index(drop=True)
        self.df = df
        return df

    def compute_all_dimensions(self):
        """计算 4 维度独立指标、分层广度、建商/写字楼剪刀差与加权复合雷达分"""
        df = self.df
        ticker = self.target_ticker

        # -------------------------------------------------------------
        # 基础均线系统与年线乖离率
        # -------------------------------------------------------------
        df['MA10'] = df[ticker].rolling(10).mean()
        df['MA20'] = df[ticker].rolling(20).mean()
        df['MA50'] = df[ticker].rolling(50).mean()
        df['MA200'] = df[ticker].rolling(200).mean()
        df['Dist_200MA'] = (df[ticker] - df['MA200']) / df['MA200'] * 100.0

        # -------------------------------------------------------------
        # 维度 1: 动力学奇异度与抛物线过热 (Score_Dynamics, 30%)
        # -------------------------------------------------------------
        raw_dyn = df['Dist_200MA']
        df['Score_Dynamics'] = raw_dyn.rolling(504, min_periods=60).apply(
            lambda s: pd.Series(s).rank(pct=True).iloc[-1] * 100.0, raw=False
        )

        # -------------------------------------------------------------
        # 维度 2: 宏观真实利率与融资压力 (Score_Valuation, 25%)
        # -------------------------------------------------------------
        raw_rates = df['Real_Yield'] * 0.6 + df['BAA10Y'] * 0.4
        df['Score_Valuation'] = raw_rates.rolling(504, min_periods=60).apply(
            lambda s: pd.Series(s).rank(pct=True).iloc[-1] * 100.0, raw=False
        )

        # -------------------------------------------------------------
        # 维度 3: 分层广度衰竭与建商/写字楼剪刀差 (Score_Breadth, 30%)
        # -------------------------------------------------------------
        breadth_components = []
        for group_name, group_tickers in self.real_estate_groups.items():
            valid_tickers = [t for t in group_tickers if t in df.columns]
            if valid_tickers:
                above_50 = pd.DataFrame({c: df[c] > df[c].rolling(50, min_periods=20).mean() for c in valid_tickers})
                group_breadth = above_50.sum(axis=1) / above_50.notna().sum(axis=1)
                df[f'Breadth_{group_name}'] = group_breadth
                breadth_components.append(group_breadth * self.group_weights[group_name])

        # 跨维加权综合广度 (Stratified Breadth)
        df['Breadth_50'] = sum(breadth_components)

        # 剪刀差：住宅建商相对写字楼商业地产广度溢出
        df['Homebuilder_CRE_Spread'] = df['Breadth_Homebuilders'] - df['Breadth_Office_CRE']

        df['High_60'] = df[ticker].rolling(60, min_periods=20).max()
        high_proximity = np.clip((df[ticker] / df['High_60'] - 0.90) / 0.10, 0.0, 1.0)
        raw_breadth_div = high_proximity * (1.0 - df['Breadth_50']) * 70.0 + np.clip(df['Homebuilder_CRE_Spread'], 0.0, 1.0) * 30.0
        df['Score_Breadth'] = raw_breadth_div.rolling(504, min_periods=60).apply(
            lambda s: pd.Series(s).rank(pct=True).iloc[-1] * 100.0, raw=False
        )

        # -------------------------------------------------------------
        # 维度 4: 跨资产脱节分位数 vs SPY (Score_Relative, 15%)
        # -------------------------------------------------------------
        df['Ratio_SPY'] = df[ticker] / df['SPY']
        spy_ratio_ma60 = df['Ratio_SPY'].rolling(60, min_periods=20).mean()
        raw_rel = (df['Ratio_SPY'] - spy_ratio_ma60) / spy_ratio_ma60 * 100.0
        df['Score_Relative'] = raw_rel.rolling(504, min_periods=60).apply(
            lambda s: pd.Series(s).rank(pct=True).iloc[-1] * 100.0, raw=False
        )

        # -------------------------------------------------------------
        # 5. 加权复合微观雷达分 (Composite Radar Score, 0 ~ 100)
        # -------------------------------------------------------------
        w = self.weights
        df['Composite_Radar_Score'] = (
            w['dynamics'] * df['Score_Dynamics'] +
            w['valuation'] * df['Score_Valuation'] +
            w['breadth'] * df['Score_Breadth'] +
            w['relative'] * df['Score_Relative']
        ).round(1)

        # -------------------------------------------------------------
        # 均线确认信号与跌幅动量
        # -------------------------------------------------------------
        df['Below_MA50_3D'] = (df[ticker] < df['MA50']).rolling(3, min_periods=1).sum() == 3
        df['Below_MA200_3D'] = (df[ticker] < df['MA200']).rolling(3, min_periods=1).sum() == 3
        df['Above_MA20_Conf'] = (df[ticker] > df['MA20']).rolling(3, min_periods=1).sum() == 3
        df['Above_MA50_Conf'] = (df[ticker] > df['MA50']).rolling(3, min_periods=1).sum() == 3

        # 利率与信用冲击指标
        real_yield_surge_60 = df['Real_Yield'] - df['Real_Yield'].rolling(60, min_periods=10).min()
        baa_surge_60 = df['BAA10Y'] - df['BAA10Y'].rolling(60, min_periods=10).min()
        dxy_ma200 = df['DXY'].rolling(200, min_periods=50).mean()

        # 极端出清黄金坑抄底信号与底部保护
        df['Cond_Panic'] = (df['Dist_200MA'].rolling(10, min_periods=1).min() < -20.0) & (df[ticker] > df['MA10'])
        df['Recently_Crashed'] = df['Dist_200MA'].rolling(25, min_periods=1).min() < -20.0

        # -------------------------------------------------------------
        # 攻防两端信号定义 (深度纠偏与产业锚定)
        # -------------------------------------------------------------
        radar_win_30 = df['Composite_Radar_Score'].rolling(30, min_periods=1).max()
        dist_win_30 = df['Dist_200MA'].rolling(30, min_periods=1).max()
        ma50_broken = df['Below_MA50_3D'] & (df[ticker] < df['MA50'] * 0.98)
        ma200_danger = (df[ticker] < df['MA200'] * 1.01) & (df[ticker] < df['MA50'])

        # 1. 估值泡沫与狂欢见顶
        df['Cond_Bubble'] = (
            (radar_win_30 >= 72.0) & 
            (dist_win_30 > 15.0) & 
            (ma50_broken | ma200_danger) & 
            (df['Breadth_50'] < 0.45)
        )

        # 2. 宏观高息/信贷/流动性熊市
        systemic_bear = ((df['BAA10Y'] > 2.7) & (baa_surge_60 > 0.45)) & (df[ticker] < df['MA50']) & (df[ticker] < df['MA200']) & (df['Breadth_50'] < 0.35)
        rate_bear = (real_yield_surge_60 > 0.65) & (df['Real_Yield'] > 0.40) & (df['DXY'] > dxy_ma200) & (df['NFCI'] > -0.25) & (df[ticker] < df['MA50']) & (df[ticker] < df['MA200']) & (df['Breadth_50'] < 0.35)

        df['Cond_Bear'] = (
            (systemic_bear | rate_bear) & 
            (df['Dist_200MA'] > -22.0) & 
            (~df['Recently_Crashed']) # 绝不在刚发生暴跌的黄金坑区域追跌割肉！
        )

        df['Sell_Signal'] = df['Cond_Bubble'] | df['Cond_Bear']
        self.df = df
        return df


def run_brokerage_backtest(df, ticker='VNQ', start_date='2009-01-01', dca_monthly=1000.0, cooldown_days=20):
    """
    券商级真实两状态记账回测引擎 (追踪 strat_shares 与 strat_cash)
    设置买入后 20 日冷却期，杜绝牛熊震荡期的均线缠绕频繁磨损
    """
    sub_bt = df[df['date'] >= start_date].reset_index(drop=True)
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
    daily_records = []
    last_buy_idx = -999

    for i in range(len(sub_bt)):
        p = sub_bt[ticker].iloc[i]
        d_str = sub_bt['date'].iloc[i]
        m = int(d_str.split('-')[1])
        score = sub_bt['Composite_Radar_Score'].iloc[i]

        # 月度定投现金注入
        if m != curr_m:
            tot_inv += dca_monthly
            b_sh += dca_monthly / p
            if pos > 0:
                s_sh += dca_monthly / p
            else:
                s_cash += dca_monthly
            curr_m = m

        action_today = 'HOLD' if pos > 0 else 'CASH'
        is_bub = sub_bt['Cond_Bubble'].iloc[i]
        is_bear = sub_bt['Cond_Bear'].iloc[i]

        # 卖出判定 (增加冷却期保护)
        if pos > 0 and (is_bub or is_bear) and (i - last_buy_idx >= cooldown_days):
            s_cash += s_sh * p
            exit_reg = 'BUBBLE' if is_bub else 'BEAR'
            r_reason = '微观雷达泡沫与低息狂欢' if is_bub else '真实利率暴涨与信用危机'
            trades.append({
                'action': 'SELL',
                'date': d_str,
                'price': p,
                'shares': s_sh,
                'cash': s_cash,
                'reason': r_reason,
                'radar_score': score,
                'breadth': sub_bt['Breadth_50'].iloc[i],
                'cre_spread': sub_bt['Homebuilder_CRE_Spread'].iloc[i]
            })
            action_today = 'SELL'
            s_sh = 0.0
            pos = 0.0

        elif pos == 0.0:
            can_buy = False
            b_reason = ""
            last_sell_p = trades[-1]['price']

            # 1. 极端出清黄金坑抄底 (年线深度超跌 + 短期企稳)
            if sub_bt['Cond_Panic'].iloc[i]:
                can_buy = True
                b_reason = '极端出清黄金坑抄底'
            # 2. 突破卖出价右侧防踏空接回 (双均线金叉支撑)
            elif (p > last_sell_p * 1.02) and sub_bt['Above_MA20_Conf'].iloc[i] and sub_bt['Above_MA50_Conf'].iloc[i]:
                can_buy = True
                b_reason = '突破卖出价右侧防踏空接回'
            # 3. 体制分化精准重构
            elif sub_bt['Above_MA20_Conf'].iloc[i] and sub_bt['Above_MA50_Conf'].iloc[i]:
                if exit_reg == 'BUBBLE':
                    radar_cooled = sub_bt['Composite_Radar_Score'].iloc[i] < 50.0
                    if radar_cooled:
                        can_buy = True
                        b_reason = '微观雷达降温且右侧重构'
                elif exit_reg == 'BEAR':
                    broad_repaired = (sub_bt['Breadth_50'].iloc[i] > 0.40) or (sub_bt['Dist_200MA'].iloc[i] > 0.0)
                    if broad_repaired:
                        can_buy = True
                        b_reason = '利率环境舒缓且地产广度修复'

            if can_buy:
                s_sh = s_cash / p
                s_cash = 0.0
                pos = 1.0
                action_today = 'BUY'
                last_buy_idx = i
                trades.append({
                    'action': 'BUY',
                    'date': d_str,
                    'price': p,
                    'shares': s_sh,
                    'cash': 0.0,
                    'reason': b_reason,
                    'radar_score': score,
                    'breadth': sub_bt['Breadth_50'].iloc[i],
                    'cre_spread': sub_bt['Homebuilder_CRE_Spread'].iloc[i]
                })

        b_val = b_sh * p
        s_val = s_sh * p + s_cash
        bench_vals.append(b_val)
        strat_vals.append(s_val)

        daily_records.append({
            'date': d_str,
            ticker: p,
            'Action': action_today,
            'Position': pos,
            'Strat_Shares': s_sh,
            'Strat_Cash': s_cash,
            'Strat_Equity': s_val,
            'Bench_Shares': b_sh,
            'Bench_Equity': b_val,
            'Composite_Radar_Score': score,
            'Breadth_50': sub_bt['Breadth_50'].iloc[i],
            'Homebuilder_CRE_Spread': sub_bt['Homebuilder_CRE_Spread'].iloc[i],
            'Score_Dynamics': sub_bt['Score_Dynamics'].iloc[i],
            'Score_Valuation': sub_bt['Score_Valuation'].iloc[i],
            'Score_Breadth': sub_bt['Score_Breadth'].iloc[i],
            'Score_Relative': sub_bt['Score_Relative'].iloc[i]
        })

    sub_bt['Bench_Equity'] = bench_vals
    sub_bt['Strat_Equity'] = strat_vals
    df_daily = pd.DataFrame(daily_records)

    b_final = bench_vals[-1]
    s_final = strat_vals[-1]
    b_ret = (b_final - tot_inv) / tot_inv * 100.0
    s_ret = (s_final - tot_inv) / tot_inv * 100.0
    alpha = s_ret - b_ret

    b_s = pd.Series(bench_vals)
    s_s = pd.Series(strat_vals)
    b_dd = ((b_s - b_s.cummax()) / b_s.cummax()).min() * 100.0
    s_dd = ((s_s - s_s.cummax()) / s_s.cummax()).min() * 100.0

    trade_pairs = []
    for k in range(0, len(trades) - 1, 2):
        if trades[k]['action'] == 'SELL' and trades[k+1]['action'] == 'BUY':
            s_t = trades[k]
            b_t = trades[k+1]
            p_drop = (b_t['price'] - s_t['price']) / s_t['price'] * 100.0
            sh_gain = (b_t['shares'] - s_t['shares']) / s_t['shares'] * 100.0
            is_win = (b_t['price'] < s_t['price']) or (sh_gain > 0)
            trade_pairs.append({
                '轮次': len(trade_pairs) + 1,
                '卖出日期': s_t['date'],
                '卖出价格': round(s_t['price'], 2),
                '卖出原因': s_t['reason'],
                '卖出时雷达分': round(s_t['radar_score'], 1),
                '卖出时广度': f"{s_t['breadth']*100:.1f}%",
                '买入日期': b_t['date'],
                '买入价格': round(b_t['price'], 2),
                '买入原因': b_t['reason'],
                '期间标的跌幅': f"{p_drop:+.2f}%",
                '持股增益幅度': f"{sh_gain:+.2f}%",
                '是否实现低买高卖': "✅ 是" if is_win else "⚠️ 防踏空"
            })
    df_pairs = pd.DataFrame(trade_pairs)

    metrics = {
        'total_invested': tot_inv,
        'bench_final': b_final,
        'strat_final': s_final,
        'bench_return': b_ret,
        'strat_return': s_ret,
        'alpha': alpha,
        'bench_max_dd': b_dd,
        'strat_max_dd': s_dd,
        'trade_count': len(trades),
        'trade_rounds': len(trade_pairs),
        'win_rounds': sum(1 for p in trade_pairs if '✅' in p['是否实现低买高卖']),
        'win_rate': sum(1 for p in trade_pairs if '✅' in p['是否实现低买高卖']) / max(1, len(trade_pairs)) * 100.0
    }

    return sub_bt, df_daily, df_pairs, metrics


def export_deliverables(sub_bt, df_daily, df_pairs, metrics, ticker='VNQ'):
    """
    导出机构级 Excel 审计全底稿与高清 4 层对齐图谱
    """
    excel_path = '宏观反身性阿尔法模型_VNQ微观雷达全周期对账表.xlsx'
    with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
        df_overview = pd.DataFrame([{
            '标的资产': ticker,
            '资产名称': '房地产与REITs板块综合基准',
            '定投总本金 (USD)': metrics['total_invested'],
            '买入持有 (B&H) 终值 (USD)': metrics['bench_final'],
            '买入持有累计回报率': f"{metrics['bench_return']:.2f}%",
            '买入持有最大回撤': f"{metrics['bench_max_dd']:.2f}%",
            '微观雷达策略终值 (USD)': metrics['strat_final'],
            '微观雷达策略总回报率': f"{metrics['strat_return']:.2f}%",
            '策略最大回撤': f"{metrics['strat_max_dd']:.2f}%",
            '超额回报率 (Alpha)': f"{metrics['alpha']:+.2f}%",
            '净多赚现金财富 (USD)': metrics['strat_final'] - metrics['bench_final'],
            '回撤改善幅度': f"{metrics['strat_max_dd'] - metrics['bench_max_dd']:+.2f}%",
            '全周期调仓轮次': metrics['trade_rounds'],
            '波段操作胜率': f"{metrics['win_rate']:.1f}%"
        }])
        df_overview.to_excel(writer, sheet_name='全周期业绩总表', index=False)
        df_pairs.to_excel(writer, sheet_name='逐笔买卖配对对账表', index=False)
        df_daily.to_excel(writer, sheet_name='逐日流水底稿表', index=False)
    print(f"📊 机构级 Excel 审计底稿已生成: {os.path.abspath(excel_path)}")

    fig, axes = plt.subplots(4, 1, figsize=(16, 15), sharex=True, gridspec_kw={'height_ratios': [3.0, 2.2, 2.2, 2.5]})
    dates = pd.to_datetime(sub_bt['date'])

    # Layer 1: 价格动量与买卖点
    ax1 = axes[0]
    ax1.plot(dates, sub_bt[ticker], color='#2b2b2b', label=f'{ticker} 收盘价', lw=1.5)
    ax1.plot(dates, sub_bt['MA50'], color='#f39c12', label='50日生命线', lw=1.2, ls='--')
    ax1.plot(dates, sub_bt['MA200'], color='#3498db', label='200日年线牛熊分界', lw=1.4)
    sell_dates = pd.to_datetime(df_pairs['卖出日期'])
    sell_prices = df_pairs['卖出价格']
    buy_dates = pd.to_datetime(df_pairs['买入日期'])
    buy_prices = df_pairs['买入价格']
    ax1.scatter(sell_dates, sell_prices, color='#e74c3c', marker='v', s=100, zorder=5, label='微观雷达避险卖出点')
    ax1.scatter(buy_dates, buy_prices, color='#2ecc71', marker='^', s=100, zorder=5, label='出清修复接回点')
    ax1.set_ylabel('价格 (USD)', fontsize=11)
    ax1.set_title(f'【Layer 1】{ticker} 价格动量与微观雷达买卖点全景 (2009 - 2026)', fontsize=13, fontweight='bold')
    ax1.grid(True, alpha=0.3)
    ax1.legend(loc='upper left', framealpha=0.9)

    # Layer 2: 4 维度独立雷达看板
    ax2 = axes[1]
    ax2.plot(dates, sub_bt['Composite_Radar_Score'], color='#8e44ad', label='综合微观雷达分 (0~100)', lw=1.6)
    ax2.plot(dates, sub_bt['Score_Dynamics'], color='#e67e22', label='动力学奇异度 (30%)', lw=0.9, alpha=0.7)
    ax2.plot(dates, sub_bt['Score_Valuation'], color='#16a085', label='真实利率与债务息差 (25%)', lw=0.9, alpha=0.7)
    ax2.plot(dates, sub_bt['Score_Breadth'], color='#c0392b', label='广度与建商/CRE剪刀差 (30%)', lw=0.9, alpha=0.7)
    ax2.plot(dates, sub_bt['Score_Relative'], color='#2980b9', label='跨资产脱节分位数 (15%)', lw=0.9, alpha=0.7)
    ax2.axhline(72, color='#e74c3c', ls='--', lw=1.2, label='过热泡沫警戒线 (72分)')
    ax2.axhline(50, color='#7f8c8d', ls=':', lw=1.0)
    ax2.axhline(20, color='#27ae60', ls='--', lw=1.2, label='深度出清黄金坑 (20分)')
    ax2.axhspan(72, 100, color='#e74c3c', alpha=0.08)
    ax2.axhspan(0, 20, color='#27ae60', alpha=0.08)
    ax2.set_ylabel('雷达评分 (0-100)', fontsize=11)
    ax2.set_ylim(-2, 102)
    ax2.set_title('【Layer 2】4 维度动态分位数与综合微观内生泡沫雷达看板 (0~100 Uniform)', fontsize=13, fontweight='bold')
    ax2.grid(True, alpha=0.3)
    ax2.legend(loc='upper left', framealpha=0.9, ncol=3, fontsize=9)

    # Layer 3: 内部真实广度与建商/写字楼剪刀差
    ax3 = axes[2]
    ax3.plot(dates, sub_bt['Breadth_50'] * 100.0, color='#d35400', label='地产 34 股分层综合广度 (Stratified Breadth %)', lw=1.6)
    if 'Breadth_Homebuilders' in sub_bt.columns:
        ax3.plot(dates, sub_bt['Breadth_Homebuilders'] * 100.0, color='#27ae60', label='住宅建筑商广度 (Homebuilders % - 周期先导)', lw=1.1, alpha=0.8, ls='-')
    if 'Breadth_Office_CRE' in sub_bt.columns:
        ax3.plot(dates, sub_bt['Breadth_Office_CRE'] * 100.0, color='#8e44ad', label='写字楼商业地产广度 (Office CRE % - 风险中枢)', lw=1.0, alpha=0.75, ls=':')
    ax3.axhline(50, color='#e74c3c', ls='--', lw=1.0, label='多空平衡线 (50%)')
    ax3.axhline(20, color='#c0392b', ls=':', lw=1.2, label='广度坍塌警戒线 (20%)')
    ax3.axhspan(0, 20, color='#c0392b', alpha=0.08)
    ax3.set_ylabel('站上50MA比例 (%)', fontsize=11)
    ax3.set_ylim(-2, 102)
    ax3.set_title('【Layer 3】地产 34 股内部广度与结构性业态轮动监控 (Homebuilders vs Office CRE)', fontsize=13, fontweight='bold')
    ax3.grid(True, alpha=0.3)
    ax3.legend(loc='upper left', framealpha=0.9, ncol=2, fontsize=9)

    # Layer 4: 真实券商记账资产增值对比
    ax4 = axes[3]
    ax4.plot(dates, sub_bt['Bench_Equity'], color='#7f8c8d', label=f'买入持有基准 (B&H 终值: USD {metrics["bench_final"]:,.0f})', lw=1.5, ls='--')
    ax4.plot(dates, sub_bt['Strat_Equity'], color='#27ae60', label=f'微观雷达策略 (策略终值: USD {metrics["strat_final"]:,.0f} | Alpha: {metrics["alpha"]:+.1f}%)', lw=2.0)
    ax4.set_ylabel('账户资产净值 (USD)', fontsize=11)
    ax4.set_title(f'【Layer 4】真实券商记账资产增殖对比 (定投总本金 USD {metrics["total_invested"]:,.0f} | 净多赚现金财富 USD {metrics["strat_final"] - metrics["bench_final"]:,.0f})', fontsize=13, fontweight='bold')
    ax4.grid(True, alpha=0.3)
    ax4.legend(loc='upper left', framealpha=0.9)

    plt.tight_layout()
    png_path = '宏观反身性阿尔法模型_VNQ微观雷达4层全景图谱.png'
    plt.savefig(png_path, dpi=200)
    plt.close()
    print(f"📈 高清 4 层对齐全景图谱已生成: {os.path.abspath(png_path)}")


def main():
    print("🚀 启动房地产与 REITs 板块 (VNQ / XLRE) 行业微观内生泡沫雷达量化全流程...")
    radar = VNQBubbleRadar(target_ticker='VNQ')
    radar.load_and_preprocess()
    print("✅ 离线数据加载与对齐完成")

    radar.compute_all_dimensions()
    print("✅ 4 维度统一分位数标定与分层加权雷达总分计算完成")

    radar.df.to_csv('vnq_radar_local.csv', index=False)
    print(f"💾 预计算指标已固化至: vnq_radar_local.csv (共 {len(radar.df)} 行)")

    sub_bt, df_daily, df_pairs, metrics = run_brokerage_backtest(radar.df, ticker='VNQ', start_date='2009-01-01')

    print("\n==================================================")
    print("🎯 VNQ 房地产微观雷达全周期实证对账审计报告 (2009 - 2026)")
    print("==================================================")
    print(f"定投总本金: USD {metrics['total_invested']:,.2f}")
    print(f"买入持有基准终值: USD {metrics['bench_final']:,.2f} (+{metrics['bench_return']:.2f}%), 最大回撤: {metrics['bench_max_dd']:.2f}%")
    print(f"微观雷达策略终值: USD {metrics['strat_final']:,.2f} (+{metrics['strat_return']:.2f}%), 最大回撤: {metrics['strat_max_dd']:.2f}%")
    print(f"超额 Alpha: {metrics['alpha']:+.2f}% | 净多赚现金财富: USD {metrics['strat_final'] - metrics['bench_final']:,.2f}")
    print(f"最大回撤改善幅度: {metrics['strat_max_dd'] - metrics['bench_max_dd']:+.2f}%")
    print(f"全周期调仓: {metrics['trade_count']} 笔 ({metrics['trade_rounds']} 轮)")
    print(f"波段胜率 (有效低买高卖/防踏空): {metrics['win_rate']:.1f}%")
    print("==================================================\n")

    export_deliverables(sub_bt, df_daily, df_pairs, metrics, ticker='VNQ')
    print("🎉 VNQ 微观雷达全套交付物本地生成完毕！")


if __name__ == '__main__':
    main()
