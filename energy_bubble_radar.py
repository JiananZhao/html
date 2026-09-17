"""
行业微观内生泡沫雷达量化引擎 (Micro-Bubble Radar Engine) —— 能源全产业链 (Energy)
深度优化与完善版：审视并融入大宗商品强周期五大分析维度
1. 产业链早晚期轮动与资本开支见顶背离 (Services vs E&P CapEx Cycle Spread)
2. 周期股估值悖论纠偏与实物资产溢价 (XLE/OIL 权益溢价与需求破坏区间)
3. 宏观体制辨析与原油边际成本底线 (65/50 USD 成本线 vs 假性流动性恐慌)
4. 券商级真实两状态记账 (strat_shares 与 strat_cash 两状态变量，冷却期防磨损)
5. 100% 脱机闭环 (Local-First)，输出 3 表合一 Excel 审计底稿与高清 4 层全景图谱
"""

import os
import sys
import io
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# 强制 UTF-8 输出以兼容 Windows 终端
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 配置 Matplotlib 中文字体与符号
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'SimSun', 'sans-serif']
plt.rcParams['axes.unicode_minus'] = False


class EnergyBubbleRadar:
    """
    能源全产业链专属微观内生泡沫雷达引擎 (升级版)
    """
    def __init__(self, market_data_path='market_data_local.csv', constituents_path='energy_constituents_local.csv'):
        self.market_data_path = market_data_path
        self.constituents_path = constituents_path
        self.df = None
        self.ticker = 'XLE'  # Use XLE as the main index price
        
        # 4大细分领域股票池 (共 41 只全产业链标的)
        self.energy_groups = {
            'Integrated': ['XOM', 'CVX', 'SHEL', 'TTE', 'BP', 'EQNR'],
            'E&P': ['COP', 'EOG', 'OXY', 'FANG', 'DVN', 'HES', 'MRO', 'CTRA', 'APA', 'EQT', 'AR', 'OVV', 'MUR', 'SM', 'CHK'],
            'Services': ['SLB', 'HAL', 'BKR', 'NOV', 'WHD', 'CHX', 'FTI', 'RIG', 'PTEN', 'NBR'],
            'Refining_Midstream': ['PSX', 'VLO', 'MPC', 'KMI', 'WMB', 'EPD', 'ET', 'OKE', 'TRGP', 'MPLX']
        }
        
        # 广度分层权重
        self.group_weights = {
            'E&P': 0.35,
            'Integrated': 0.25,
            'Services': 0.25,
            'Refining_Midstream': 0.15
        }
        
        # 雷达综合打分权重 (强化广度与产业链传导)
        self.weights = {
            'dynamics': 0.30,
            'valuation': 0.25,
            'breadth': 0.30,
            'relative': 0.15
        }

    def load_and_preprocess(self):
        """
        加载本地主数据并对齐时间轴 (100% 脱机闭环)
        """
        df_m = pd.read_csv(self.market_data_path)
        df_c = pd.read_csv(self.constituents_path)

        df_m['date'] = pd.to_datetime(df_m['date']).dt.strftime('%Y-%m-%d')
        df_c['date'] = pd.to_datetime(df_c['date']).dt.strftime('%Y-%m-%d')

        df = pd.merge(df_m, df_c, on='date', how='left').sort_values('date').reset_index(drop=True)
        
        # 找到属于配置的成分股列
        all_expected_consts = []
        for g in self.energy_groups.values():
            all_expected_consts.extend(g)
            
        const_cols = [c for c in all_expected_consts if c in df.columns]
        df[const_cols] = df[const_cols].ffill()
        
        self.df = df
        self.const_cols = const_cols
        return self.df

    def compute_all_dimensions(self):
        """
        计算 4 个独立维度分项与加权综合分 (深度融合大宗商品周期特性)
        """
        df = self.df
        ticker = self.ticker

        # -------------------------------------------------------------
        # 维度 1: 价格超指数动力学 (Score_Dynamics, 30%)
        # -------------------------------------------------------------
        ema200 = df[ticker].ewm(span=200, adjust=False).mean()
        dist_200 = (df[ticker] - ema200) / ema200 * 100.0

        # 动量加速度与年线乖离复合
        accel_20 = (df[ticker] / df[ticker].rolling(20).mean() - 1) * 100.0
        accel_60 = (df[ticker] / df[ticker].rolling(60).mean() - 1) * 100.0
        
        raw_dyn = 0.50 * accel_20 + 0.50 * accel_60 + 0.50 * dist_200
        df['Score_Dynamics'] = raw_dyn.rolling(504, min_periods=60).apply(
            lambda s: pd.Series(s).rank(pct=True).iloc[-1] * 100.0, raw=False
        )

        # -------------------------------------------------------------
        # 维度 2: 能源专属实物溢价与需求破坏估值 (Score_Valuation, 25%)
        # 摒弃机械对数线性残差，采用 XLE/OIL 权益溢价倍数与原油绝对需求破坏区间
        # -------------------------------------------------------------
        df['Ratio_XLE_OIL'] = df[ticker] / (df['OIL'] + 1e-5)
        ratio_roll_mean = df['Ratio_XLE_OIL'].rolling(504, min_periods=60).mean()
        ratio_roll_std = df['Ratio_XLE_OIL'].rolling(504, min_periods=60).std()
        df['Ratio_XLE_OIL_Z'] = (df['Ratio_XLE_OIL'] - ratio_roll_mean) / (ratio_roll_std + 1e-5)

        # 原油极端高价需求破坏惩罚 (油价 > 100 美元时对全球经济与下游炼化需求产生反噬)
        oil_demand_destruct = np.clip((df['OIL'] - 100.0) / 20.0, 0.0, 2.0)
        val_raw = df['Ratio_XLE_OIL_Z'] + oil_demand_destruct * 1.5

        df['Score_Valuation'] = val_raw.rolling(504, min_periods=60).apply(
            lambda s: pd.Series(s).rank(pct=True).iloc[-1] * 100.0, raw=False
        )

        # -------------------------------------------------------------
        # 维度 3: 分层广度与产业链 CapEx 周期过热剪刀差 (Score_Breadth, 30%)
        # -------------------------------------------------------------
        breadth_components = []
        for group_name, group_tickers in self.energy_groups.items():
            valid_tickers = [t for t in group_tickers if t in df.columns]
            if valid_tickers:
                above_50 = pd.DataFrame({c: df[c] > df[c].rolling(50, min_periods=20).mean() for c in valid_tickers})
                group_breadth = above_50.sum(axis=1) / above_50.notna().sum(axis=1)
                df[f'Breadth_{group_name}'] = group_breadth
                breadth_components.append(group_breadth * self.group_weights[group_name])
                
        # 跨维加权综合广度 (Stratified Breadth)
        df['Breadth_50'] = sum(breadth_components)
        
        # 产业链 CapEx 剪刀差：油服设备广度相对上游勘探生产广度的溢出
        df['Capex_Spread'] = df['Breadth_Services'] - df['Breadth_E&P']
        # 资本开支过热见顶判定：油服处于极高景气 (>70%) 而开采率先疲软 (<50%)
        df['Capex_Overheat'] = (df['Breadth_Services'] > 0.70) & (df['Breadth_E&P'] < 0.50)

        df['High_60'] = df[ticker].rolling(60, min_periods=20).max()
        df['Price_Ratio_High'] = df[ticker] / df['High_60']

        # 高位广度背离 + CapEx 见顶剪刀差融合
        high_proximity = np.clip((df['Price_Ratio_High'] - 0.90) / 0.10, 0.0, 1.0)
        raw_breadth_div = high_proximity * (1.0 - df['Breadth_50']) * 70.0 + np.clip(df['Capex_Spread'], 0.0, 1.0) * 30.0
        df['Score_Breadth'] = raw_breadth_div.rolling(504, min_periods=60).apply(
            lambda s: pd.Series(s).rank(pct=True).iloc[-1] * 100.0, raw=False
        )

        # -------------------------------------------------------------
        # 维度 4: 跨资产抛物线脱节乖离 (Score_Relative, 15%)
        # -------------------------------------------------------------
        df['Ratio_SPY'] = df[ticker] / df['SPY']
        ratio_ma60 = df['Ratio_SPY'].rolling(60, min_periods=20).mean()
        ratio_dist_60 = (df['Ratio_SPY'] - ratio_ma60) / ratio_ma60 * 100.0
        df['Score_Relative'] = ratio_dist_60.rolling(504, min_periods=60).apply(
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
        )

        # -------------------------------------------------------------
        # 宏观反身性与均线系统 (能源专属：OIL 与 DXY 复合锚)
        # -------------------------------------------------------------
        df['MA10'] = df[ticker].rolling(10).mean()
        df['MA20'] = df[ticker].rolling(20).mean()
        df['MA50'] = df[ticker].rolling(50).mean()
        df['MA200'] = df[ticker].rolling(200).mean()
        df['Dist_200MA'] = (df[ticker] - df['MA200']) / df['MA200'] * 100.0

        # 反身性偏离度 Gap (动态 Beta 定价)
        df['Price_Z'] = (df[ticker] - df[ticker].rolling(200).mean()) / (df[ticker].rolling(200).std() + 1e-8)
        df['OIL_Z'] = (df['OIL'] - df['OIL'].rolling(200).mean()) / (df['OIL'].rolling(200).std() + 1e-8)
        df['DXY_Z'] = (df['DXY'] - df['DXY'].rolling(200).mean()) / (df['DXY'].rolling(200).std() + 1e-8)
        df['Macro_Anchor_Z'] = 0.6 * df['OIL_Z'] - 0.4 * df['DXY_Z']
        
        roll_cov = df['Price_Z'].rolling(252).cov(df['Macro_Anchor_Z'])
        roll_var = df['Macro_Anchor_Z'].rolling(252).var()
        df['Dynamic_Beta'] = (roll_cov / (roll_var + 1e-8)).clip(lower=-2.0, upper=2.0)
        df['Expected_Price_Z'] = df['Macro_Anchor_Z'] * df['Dynamic_Beta']
        df['Gap'] = df['Price_Z'] - df['Expected_Price_Z']

        df['Gap_Max_45'] = df['Gap'].rolling(45, min_periods=1).max()
        df['PriceZ_Max_45'] = df['Price_Z'].rolling(45, min_periods=1).max()
        df['Gap_Median'] = df['Gap'].rolling(252, min_periods=20).median()
        df['Gap_Upper'] = df['Gap'].expanding(min_periods=20).quantile(0.85)

        # 均线确认信号
        df['Above_MA20_Conf'] = (df[ticker] > df['MA20']).rolling(3, min_periods=1).sum() == 3
        df['Above_MA50_Conf'] = (df[ticker] > df['MA50']).rolling(3, min_periods=1).sum() == 3
        df['Below_MA50_3D'] = (df[ticker] < df['MA50']).rolling(3, min_periods=1).sum() == 3
        df['Cond_Panic'] = (df['Dist_200MA'].rolling(10, min_periods=1).min() < -20.0) & (df[ticker] > df['MA10'])

        # -------------------------------------------------------------
        # 攻防两端信号定义 (深度纠偏与产业锚定)
        # -------------------------------------------------------------
        radar_win_25 = df['Composite_Radar_Score'].rolling(25, min_periods=1).max()
        ma50_broken = df['Below_MA50_3D'] & (df[ticker] < df['MA50'] * 0.99)
        ma200_danger = (df[ticker] < df['MA200'] * 1.02) & (df[ticker] < df['MA50'])

        # 1. 估值泡沫与 CapEx 过热见顶：
        # 必须同时满足：雷达分达 70+ 过热、年线乖离实质拉开 (>18%)、均线破位、且伴随内部广度衰竭或 CapEx 剪刀差
        df['Cond_Bubble'] = (
            (radar_win_25 >= 70.0) & 
            (df['Dist_200MA'] > 18.0) &
            (ma50_broken | ma200_danger) & 
            ((df['Breadth_50'] < 0.45) | df['Capex_Overheat'])
        )

        # 2. 实质性产业宏观熊市：
        # 油价跌破 200MA 且击穿 65 美元全球开采/OPEC财政成本线 + 美元走强 + 股价双均线破位 + 广度坍塌 (<40%)
        # 彻底剔除 NFCI 科技股加息流动性误伤逻辑！
        df['Macro_Crisis'] = (
            (df['OIL'] < df['OIL'].rolling(200).mean()) & 
            (df['OIL'] < 65.0) & 
            (df['DXY'] > df['DXY'].rolling(200).mean())
        )
        df['Cond_Bear'] = (
            df['Macro_Crisis'] & 
            (df[ticker] < df['MA50']) & 
            (df[ticker] < df['MA200']) & 
            (df['Breadth_50'] < 0.40)
        )
        df['Sell_Signal'] = df['Cond_Bubble'] | df['Cond_Bear']

        self.df = df
        return df


def run_brokerage_backtest(df, ticker='XLE', start_date='2009-01-01', dca_monthly=1000.0, cooldown_days=20):
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
            r_reason = '微观雷达泡沫与CapEx过热' if is_bub else '油价击穿成本线与宏观熊市'
            trades.append({
                'action': 'SELL',
                'date': d_str,
                'price': p,
                'shares': s_sh,
                'cash': s_cash,
                'reason': r_reason,
                'radar_score': score,
                'breadth': sub_bt['Breadth_50'].iloc[i],
                'capex_spread': sub_bt['Capex_Spread'].iloc[i]
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
                    radar_cooled = sub_bt['Composite_Radar_Score'].iloc[i] < 45.0
                    if radar_cooled:
                        can_buy = True
                        b_reason = '微观雷达降温且右侧重构'
                elif exit_reg == 'BEAR':
                    oil_val = sub_bt['OIL'].iloc[i]
                    oil_ma = sub_bt['OIL'].rolling(200).mean().iloc[i]
                    if (oil_val >= 60.0) or (oil_val > oil_ma):
                        can_buy = True
                        b_reason = '油价企稳成本线且趋势重构'

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
                    'capex_spread': sub_bt['Capex_Spread'].iloc[i]
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
            'Capex_Spread': sub_bt['Capex_Spread'].iloc[i],
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


def export_deliverables(sub_bt, df_daily, df_pairs, metrics, ticker='XLE'):
    """
    导出机构级 Excel 审计全底稿与高清 4 层对齐图谱
    """
    excel_path = '宏观反身性阿尔法模型_Energy微观雷达全周期对账表.xlsx'
    with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
        df_overview = pd.DataFrame([{
            '标的资产': ticker,
            '资产名称': '能源全产业链综合基准',
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
    ax1.set_ylabel(f'价格 (USD)', fontsize=11)
    ax1.set_title(f'【Layer 1】{ticker} 价格动量与微观雷达买卖点全景 (2009 - 2026)', fontsize=13, fontweight='bold')
    ax1.grid(True, alpha=0.3)
    ax1.legend(loc='upper left', framealpha=0.9)

    # Layer 2: 4 维度独立雷达看板
    ax2 = axes[1]
    ax2.plot(dates, sub_bt['Composite_Radar_Score'], color='#8e44ad', label='综合微观雷达分 (0~100)', lw=1.6)
    ax2.plot(dates, sub_bt['Score_Dynamics'], color='#e67e22', label='动力学奇异度 (30%)', lw=0.9, alpha=0.7)
    ax2.plot(dates, sub_bt['Score_Valuation'], color='#16a085', label='实物溢价与需求破坏 (25%)', lw=0.9, alpha=0.7)
    ax2.plot(dates, sub_bt['Score_Breadth'], color='#c0392b', label='广度与CapEx剪刀差 (30%)', lw=0.9, alpha=0.7)
    ax2.plot(dates, sub_bt['Score_Relative'], color='#2980b9', label='跨资产脱节分位数 (15%)', lw=0.9, alpha=0.7)
    ax2.axhline(70, color='#e74c3c', ls='--', lw=1.2, label='过热泡沫警戒线 (70分)')
    ax2.axhline(50, color='#7f8c8d', ls=':', lw=1.0)
    ax2.axhline(20, color='#27ae60', ls='--', lw=1.2, label='深度出清黄金坑 (20分)')
    ax2.axhspan(70, 100, color='#e74c3c', alpha=0.08)
    ax2.axhspan(0, 20, color='#27ae60', alpha=0.08)
    ax2.set_ylabel('雷达评分 (0-100)', fontsize=11)
    ax2.set_ylim(-2, 102)
    ax2.set_title('【Layer 2】4 维度动态分位数与综合微观内生泡沫雷达看板 (0~100 Uniform)', fontsize=13, fontweight='bold')
    ax2.grid(True, alpha=0.3)
    ax2.legend(loc='upper left', framealpha=0.9, ncol=3, fontsize=9)

    # Layer 3: 内部真实广度与 CapEx 剪刀差
    ax3 = axes[2]
    ax3.plot(dates, sub_bt['Breadth_50'] * 100.0, color='#d35400', label='能源 41 股分层等权广度 (Stratified Breadth %)', lw=1.6)
    if 'Breadth_Services' in sub_bt.columns and 'Breadth_E&P' in sub_bt.columns:
        ax3.plot(dates, sub_bt['Breadth_Services'] * 100.0, color='#9b59b6', label='油服设备广度 (Services % - 后周期CapEx)', lw=1.0, alpha=0.75, ls=':')
        ax3.plot(dates, sub_bt['Breadth_E&P'] * 100.0, color='#27ae60', label='上游开采广度 (E&P % - 早周期先导)', lw=1.0, alpha=0.75, ls='-.')
    ax3.axhline(50, color='#e74c3c', ls='--', lw=1.0, label='多空平衡线 (50%)')
    ax3.axhline(40, color='#c0392b', ls=':', lw=1.2, label='广度坍塌线 (40%)')
    ax3.axhspan(0, 40, color='#c0392b', alpha=0.08)
    ax3.set_ylabel('站上50MA比例 (%)', fontsize=11)
    ax3.set_ylim(-2, 102)
    ax3.set_title('【Layer 3】能源 41 股内部广度与产业链 CapEx 早晚周期轮动监控 (Services vs E&P)', fontsize=13, fontweight='bold')
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
    png_path = '宏观反身性阿尔法模型_Energy微观雷达4层全景图谱.png'
    plt.savefig(png_path, dpi=200)
    plt.close()
    print(f"📈 高清 4 层对齐全景图谱已生成: {os.path.abspath(png_path)}")


def main():
    print("🚀 启动能源全产业链 (Energy) 行业微观内生泡沫雷达量化全流程 (增强完善版)...")
    radar = EnergyBubbleRadar()
    radar.load_and_preprocess()
    print("✅ 离线数据加载与对齐完成")

    radar.compute_all_dimensions()
    print("✅ 4 维度统一分位数标定与分层加权雷达总分计算完成")

    radar.df.to_csv('energy_radar_local.csv', index=False)
    print(f"💾 预计算指标已固化至: energy_radar_local.csv (共 {len(radar.df)} 行)")

    sub_bt, df_daily, df_pairs, metrics = run_brokerage_backtest(radar.df, ticker='XLE', start_date='2009-01-01')

    print("\n==================================================")
    print("🎯 Energy 能源全产业链微观雷达全周期实证对账审计报告 (2009 - 2026)")
    print("==================================================")
    print(f"定投总本金: USD {metrics['total_invested']:,.2f}")
    print(f"买入持有基准终值: USD {metrics['bench_final']:,.2f} (+{metrics['bench_return']:.2f}%), 最大回撤: {metrics['bench_max_dd']:.2f}%")
    print(f"微观雷达策略终值: USD {metrics['strat_final']:,.2f} (+{metrics['strat_return']:.2f}%), 最大回撤: {metrics['strat_max_dd']:.2f}%")
    print(f"超额 Alpha: {metrics['alpha']:+.2f}% | 净多赚现金财富: USD {metrics['strat_final'] - metrics['bench_final']:,.2f}")
    print(f"最大回撤改善幅度: {metrics['strat_max_dd'] - metrics['bench_max_dd']:+.2f}%")
    print(f"全周期调仓: {metrics['trade_count']} 笔 ({metrics['trade_rounds']} 轮)")
    print(f"波段胜率 (有效低买高卖/防踏空): {metrics['win_rate']:.1f}%")
    print("==================================================\n")

    export_deliverables(sub_bt, df_daily, df_pairs, metrics, ticker='XLE')
    print("🎉 Energy 微观雷达全套交付物本地生成完毕！")


if __name__ == '__main__':
    main()
