"""
====================================================================
区域性银行与金融板块 (KRE / XLF) 行业微观内生泡沫与信用危机雷达全流程模型
====================================================================
【核心量化目标】
1. 建立针对区域性银行 (Regional Banks) 与金融板块 (Financials) 的微观雷达监测架构；
2. 覆盖 4 个核心金融分层子领域 (共 38 家核心机构)：
   - 区域性银行 (Regional Banks: KRE, USB, TFC, PNC, KEY, CFG, FITB, MTB, HBAN, ZION, WAL, EWBC 等)
   - 全球系统重要性银行 (G-SIBs: JPM, BAC, WFC, C)
   - 投行与另类资管 (Brokers & Asset Managers: MS, GS, SCHW, BLK, BX, KKR, APO, BEN)
   - 保险与金融服务 (Insurance & Payments: BRK-B, PGR, TRV, AIG, MET, ALL, V, MA, AXP, COF)
3. 4 维度独立雷达分位数标定 (0 ~ 100 Uniform 分布)：
   - 动力学抛物线过热度 (Score_Dynamics)
   - KRE 相对宽基金融 XLF 估值扭曲度 (Score_Valuation)
   - 分层加权广度衰竭与银行压力剪刀差 (Score_Breadth)
   - 跨资产脱节分位数 (Score_Relative)
4. 真实券商记账体系 (追踪 strat_shares 与 strat_cash)，绝无虚假连乘；
5. 100% 本地脱机闭环读取 (financial_constituents_local.csv 与 market_data_local.csv)。
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


class KREBubbleRadar:
    def __init__(self, target_ticker='KRE'):
        self.target_ticker = target_ticker
        self.macro_file = 'market_data_local.csv'
        self.const_file = 'financial_constituents_local.csv'
        self.df = None

        # 4 大金融分层子领域构造成分
        self.financial_groups = {
            'Regional_Banks': ['KRE', 'USB', 'TFC', 'PNC', 'KEY', 'CFG', 'FITB', 'MTB', 'HBAN', 'ZION', 'WAL', 'EWBC'],
            'GSIBs': ['JPM', 'BAC', 'WFC', 'C'],
            'Brokers': ['MS', 'GS', 'SCHW', 'BLK', 'BX', 'KKR', 'APO', 'BEN'],
            'Insurance_Payments': ['BRK-B', 'PGR', 'TRV', 'AIG', 'MET', 'ALL', 'V', 'MA', 'AXP', 'COF']
        }

        # 宏观与系统性重要性权重
        self.group_weights = {
            'Regional_Banks': 0.40,
            'GSIBs': 0.25,
            'Brokers': 0.20,
            'Insurance_Payments': 0.15
        }

        # 4 维度雷达权重配置
        self.weights = {
            'dynamics': 0.35,
            'valuation': 0.25,
            'breadth': 0.25,
            'relative': 0.15
        }

    def load_and_preprocess(self):
        """100% 离线脱机闭环加载本地清洗好的金融与宏观数据"""
        if not os.path.exists(self.macro_file):
            raise FileNotFoundError(f"宏观主数据集缺失: {self.macro_file}")
        if not os.path.exists(self.const_file):
            raise FileNotFoundError(f"金融成分股主数据集缺失: {self.const_file}")

        df_m = pd.read_csv(self.macro_file)
        df_c = pd.read_csv(self.const_file)

        # 使用 left merge 保留所有个股成分最新报价，前向填充滞后的宏观数据
        df = pd.merge(df_c, df_m, on='date', how='left').sort_values('date').reset_index(drop=True)
        const_cols = [c for c in df_c.columns if c != 'date']
        
        self.fresh_mask = df[const_cols].notna()
        
        # 前向填充最多 5 天的宏观数据与部分缺失个股数据
        fill_cols = [c for c in df_m.columns if c != 'date'] + const_cols
        df[fill_cols] = df[fill_cols].ffill(limit=5)
        df = df.dropna(subset=['HYG', 'BAA10Y', 'NFCI', 'Real_Yield']).reset_index(drop=True)
        self.df = df
        self.const_cols = const_cols
        return df

    def compute_all_dimensions(self):
        """计算 4 维度独立指标、分层广度、银行压力剪刀差与加权复合雷达分"""
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
        # 维度 1: 动力学奇异度与抛物线过热 (Score_Dynamics, 35%)
        # -------------------------------------------------------------
        raw_dyn = df['Dist_200MA']
        df['Score_Dynamics'] = raw_dyn.rolling(504, min_periods=60).apply(
            lambda s: pd.Series(s).rank(pct=True).iloc[-1] * 100.0, raw=False
        )

        # -------------------------------------------------------------
        # 维度 2: KRE 相对宽基金融板块 XLF 相对估值脱节 (Score_Valuation, 25%)
        # -------------------------------------------------------------
        df['Ratio_XLF'] = df[ticker] / df['XLF']
        ratio_ma60 = df['Ratio_XLF'].rolling(60, min_periods=20).mean()
        raw_val = (df['Ratio_XLF'] - ratio_ma60) / ratio_ma60 * 100.0
        df['Score_Valuation'] = raw_val.rolling(504, min_periods=60).apply(
            lambda s: pd.Series(s).rank(pct=True).iloc[-1] * 100.0, raw=False
        )

        # -------------------------------------------------------------
        # 维度 3: 分层广度与银行挤兑压力剪刀差 (Score_Breadth, 25%)
        # -------------------------------------------------------------
        breadth_components = []
        for group_name, group_tickers in self.financial_groups.items():
            valid_tickers = [t for t in group_tickers if t in df.columns]
            if valid_tickers:
                above_50 = pd.DataFrame({c: df[c] > df[c].rolling(50, min_periods=20).mean() for c in valid_tickers})
                group_breadth = above_50.sum(axis=1) / above_50.notna().sum(axis=1)
                df[f'Breadth_{group_name}'] = group_breadth
                breadth_components.append(group_breadth * self.group_weights[group_name])

        # 跨维加权综合广度 (Stratified Breadth)
        df['Breadth_50'] = sum(breadth_components)

        # 银行压力剪刀差：G-SIB 广度相对区域银行广度的溢出 (资金由中小银行逃向巨头)
        df['Bank_Stress_Spread'] = df['Breadth_GSIBs'] - df['Breadth_Regional_Banks']

        df['High_60'] = df[ticker].rolling(60, min_periods=20).max()
        high_proximity = np.clip((df[ticker] / df['High_60'] - 0.90) / 0.10, 0.0, 1.0)
        raw_breadth_div = high_proximity * (1.0 - df['Breadth_50']) * 70.0 + np.clip(df['Bank_Stress_Spread'], 0.0, 1.0) * 30.0
        df['Score_Breadth'] = raw_breadth_div.rolling(504, min_periods=60).apply(
            lambda s: pd.Series(s).rank(pct=True).iloc[-1] * 100.0, raw=False
        )

        # -------------------------------------------------------------
        # 维度 4: 跨资产脱节分位数 (Score_Relative, 15%)
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

        # 动量与相对脱节跌幅
        df['KRE_Drop_10d'] = df[ticker].pct_change(10) * 100.0
        df['Ratio_XLF_Drop_10d'] = (df['Ratio_XLF'] - df['Ratio_XLF'].shift(10)) / df['Ratio_XLF'].shift(10) * 100.0

        # 信用利差指标
        baa_surge_60 = df['BAA10Y'] - df['BAA10Y'].rolling(60, min_periods=10).min()
        systemic_credit_stress = (df['BAA10Y'] > 3.0) & (baa_surge_60 > 0.40) & (df['NFCI'] > 0.10)

        # 极端出清黄金坑抄底信号
        df['Cond_Panic'] = (df['Dist_200MA'].rolling(10, min_periods=1).min() < -20.0) & (df[ticker] > df['MA10'])

        # -------------------------------------------------------------
        # 攻防两端信号定义 (深度纠偏与产业锚定)
        # -------------------------------------------------------------
        radar_win_30 = df['Composite_Radar_Score'].rolling(30, min_periods=1).max()
        dist_win_30 = df['Dist_200MA'].rolling(30, min_periods=1).max()
        ma50_broken = df['Below_MA50_3D'] & (df[ticker] < df['MA50'] * 0.98)
        ma200_danger = (df[ticker] < df['MA200'] * 1.01) & (df[ticker] < df['MA50'])

        # 1. 估值泡沫与流动性过热见顶
        df['Cond_Bubble'] = (
            (radar_win_30 >= 72.0) & 
            (dist_win_30 > 18.0) & 
            (ma50_broken | ma200_danger) & 
            (df['Breadth_50'] < 0.45)
        )

        # 2. 系统性信贷危机或突发挤兑崩盘
        # A: 2008 雷曼式全面宏观信贷紧缩危机
        systemic_bear = (
            systemic_credit_stress & 
            df['Below_MA50_3D'] & 
            (df[ticker] < df['MA200']) & 
            (df['Breadth_50'] < 0.30)
        )
        # B: 2023 硅谷银行 (SVB) 式区域银行急性挤兑崩塌
        acute_bank_run = (
            (df['Breadth_Regional_Banks'] <= 0.10) & 
            ((df['KRE_Drop_10d'] < -10.0) | (df['Ratio_XLF_Drop_10d'] < -8.0)) & 
            (df[ticker] < df['MA50'] * 0.96)
        )
        # C: 2020 疫情系统性流动性冻结
        covid_freeze = (df['NFCI'] > 0.20) & (df[ticker] < df['MA50']) & (df[ticker] < df['MA200'])

        df['Cond_Bear'] = (
            (systemic_bear | acute_bank_run | covid_freeze) & 
            (df['Dist_200MA'] > -22.0) # 坚决杜绝在年线负 22% 以下极度超跌底谷杀跌
        )

        df['Sell_Signal'] = df['Cond_Bubble'] | df['Cond_Bear']
        self.df = df
        return df


def run_brokerage_backtest(df, ticker='KRE', start_date='2009-01-01', dca_monthly=1000.0, cooldown_days=20, cost_config=0.0):
    from true_accounting import UnitizedAccount, calculate_xirr
    from shared_executor import SharedExecutor
    from core_engine.simulation_result import SimulationResult
    import pandas as pd
    
    sub_bt = df[df['date'] >= start_date].copy().reset_index(drop=True)
    if sub_bt.empty:
        return SimulationResult(pd.DataFrame(), pd.DataFrame(), [], [], [], pd.DataFrame(), {}, {})
        
    initial_dt = pd.to_datetime(sub_bt['date'].iloc[0])
    acc = UnitizedAccount(initial_cash=0.0, initial_date=initial_dt)
    bench_acc = UnitizedAccount(initial_cash=0.0, initial_date=initial_dt)
    
    executor = SharedExecutor(acc, fee_rate=cost_config, execution_mode='NEXT_CLOSE', account_type='strat')
    bench_executor = SharedExecutor(bench_acc, fee_rate=0.0, execution_mode='NEXT_CLOSE', account_type='bench')
    
    curr_m = -1
    exit_reg = None
    pos = 1.0
    last_buy_idx = -999
    
    df_len = len(sub_bt)
    total_invested = 0.0
    
    bench_eqs = []
    strat_eqs = []
    positions = []
    
    for i in range(df_len):
        d_str = sub_bt['date'].iloc[i]
        p = sub_bt[ticker].iloc[i]
        
        try:
            dt = pd.Timestamp(d_str)
        except:
            dt = pd.to_datetime(d_str)
            
        m = dt.month
        
        # 定投及买入 (按收盘价)
        dca_amount = 0.0
        if m != curr_m:
            curr_m = m
            dca_amount = dca_monthly
            total_invested += dca_monthly

        executor.step(dt, p, p, dca_amount=dca_amount)
        bench_executor.step(dt, p, p, dca_amount=dca_amount)
        
        # T 日收盘后产生新信号，传给 T+1
        # T 日收盘后产生新信号，传给 T+1
        is_bub = sub_bt['Cond_Bubble'].iloc[i]
        is_bear = sub_bt['Cond_Bear'].iloc[i]
        
        if pos > 0 and (is_bub or is_bear) and (i - last_buy_idx >= cooldown_days):
            exit_reg = 'BUBBLE' if is_bub else 'BEAR'
            pending_reason = '微观雷达泡沫与信贷过热' if is_bub else ('区域银行急性挤兑' if sub_bt['Breadth_Regional_Banks'].iloc[i] <= 0.10 else '系统性信贷紧缩危机')
            pos = 0.0
            executor.submit_order(pos, pending_reason, dt)
        elif pos == 0.0:
            can_buy = False
            b_reason = ""
            
            # 获取最后一次卖出价
            last_sell_p = executor.last_sell_p if executor.last_sell_p is not None else p
            
            if sub_bt['Cond_Panic'].iloc[i]:
                can_buy = True
                b_reason = '极端出清黄金坑抄底'
            elif (p > last_sell_p * 1.02) and sub_bt['Above_MA20_Conf'].iloc[i] and sub_bt['Above_MA50_Conf'].iloc[i]:
                can_buy = True
                b_reason = '突破卖出价右侧防踏空接回'
            elif sub_bt['Above_MA20_Conf'].iloc[i] and sub_bt['Above_MA50_Conf'].iloc[i]:
                if exit_reg == 'BUBBLE':
                    radar_cooled = sub_bt['Composite_Radar_Score'].iloc[i] < 50.0
                    if radar_cooled:
                        can_buy = True
                        b_reason = '微观雷达降温且右侧重构'
                elif exit_reg == 'BEAR':
                    rb_repaired = (sub_bt['Breadth_Regional_Banks'].iloc[i] > 0.40) or (sub_bt['Dist_200MA'].iloc[i] > 0.0)
                    if rb_repaired:
                        can_buy = True
                        b_reason = '金融信贷舒缓且区域银行广度修复'
            if can_buy:
                pos = 1.0
                last_buy_idx = i
                executor.submit_order(pos, b_reason, dt)
        else:
            executor.submit_order(pos, "Standing Order / DCA", dt)
        bench_executor.submit_order(1.0, "Bench Standing Order / DCA", dt)
            
        bench_eqs.append(bench_executor.acc.shares * p + bench_executor.acc.cash)
        strat_eqs.append(executor.acc.shares * p + executor.acc.cash)
        positions.append(pos)
        
    sub_bt['Bench_Equity'] = bench_eqs
    sub_bt['Strat_Equity'] = strat_eqs
    sub_bt['Position'] = positions
    
    all_states = executor.daily_states + bench_executor.daily_states
    daily_accounts = pd.DataFrame(all_states)
    
    b_final = sub_bt['Bench_Equity'].iloc[-1]
    s_final = sub_bt['Strat_Equity'].iloc[-1]
    b_ret = (b_final - total_invested) / total_invested * 100.0 if total_invested > 0 else 0
    s_ret = (s_final - total_invested) / total_invested * 100.0 if total_invested > 0 else 0
    
    final_date = pd.Timestamp(sub_bt['date'].iloc[-1])
    b_cagr = calculate_xirr([(pd.Timestamp(d), a) for d, a in bench_executor.acc.cash_flows], b_final, final_date) * 100.0
    s_cagr = calculate_xirr([(pd.Timestamp(d), a) for d, a in executor.acc.cash_flows], s_final, final_date) * 100.0
    
    alpha = s_cagr - b_cagr
    
    b_dd = (daily_accounts[daily_accounts['type'] == 'bench']['unit_nav'] / daily_accounts[daily_accounts['type'] == 'bench']['unit_nav'].cummax() - 1).min() * 100.0
    s_dd = (daily_accounts[daily_accounts['type'] == 'strat']['unit_nav'] / daily_accounts[daily_accounts['type'] == 'strat']['unit_nav'].cummax() - 1).min() * 100.0

    from core_engine.export_utils import generate_trade_pairs
    trade_pairs_df = generate_trade_pairs(executor.orders_history, executor.fills, sub_bt, ticker)

    metrics = {
        'total_invested': total_invested,
        'bench_final': b_final,
        'strat_final': s_final,
        'bench_return': b_cagr,
        'strat_return': s_cagr,
        'alpha': alpha,
        'bench_max_dd': b_dd,
        'strat_max_dd': s_dd,
        'trade_count': len(executor.fills),
        'trade_rounds': len(trade_pairs_df),
        'win_rounds': sum(1 for p in trade_pairs_df.to_dict('records') if '✅' in p.get('波段是否有效避险', '')) if not trade_pairs_df.empty else 0,
        'win_rate': (sum(1 for p in trade_pairs_df.to_dict('records') if '✅' in p.get('波段是否有效避险', '')) / max(1, len(trade_pairs_df)) * 100.0) if not trade_pairs_df.empty else 0.0
    }
    
    result = SimulationResult(
        features=sub_bt,
        signals=sub_bt[['date', 'Position', 'Sell_Signal', 'Cond_Bubble', 'Cond_Bear']],
        orders=executor.orders_history + executor.pending_orders,
        fills=executor.fills,
        cashflows=executor.cashflows,
        daily_accounts=daily_accounts,
        metrics=metrics,
        metadata={'ticker': ticker, 'start_date': start_date, 'end_date': sub_bt['date'].iloc[-1]}
    )
    
    return result


from core_engine.export_utils import export_deliverables, generate_trade_pairs

def plot_radar_chart(result):
    sub_bt = result.features
    df_daily = result.daily_accounts
    metrics = result.metrics
    ticker = result.metadata.get('ticker', 'KRE')
    df_pairs = generate_trade_pairs(result.orders, result.fills, sub_bt, ticker)
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
    ax2.plot(dates, sub_bt['Score_Dynamics'], color='#e67e22', label='动力学奇异度 (35%)', lw=0.9, alpha=0.7)
    ax2.plot(dates, sub_bt['Score_Valuation'], color='#16a085', label='KRE/XLF估值溢价 (25%)', lw=0.9, alpha=0.7)
    ax2.plot(dates, sub_bt['Score_Breadth'], color='#c0392b', label='广度与银行压力差 (25%)', lw=0.9, alpha=0.7)
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

    # Layer 3: 内部真实广度与银行挤兑压力剪刀差
    ax3 = axes[2]
    ax3.plot(dates, sub_bt['Breadth_50'] * 100.0, color='#d35400', label='金融 38 股分层综合广度 (Stratified Breadth %)', lw=1.6)
    if 'Breadth_Regional_Banks' in sub_bt.columns:
        ax3.plot(dates, sub_bt['Breadth_Regional_Banks'] * 100.0, color='#e74c3c', label='区域银行广度 (Regional Banks %)', lw=1.1, alpha=0.8, ls='-')
    if 'Breadth_GSIBs' in sub_bt.columns:
        ax3.plot(dates, sub_bt['Breadth_GSIBs'] * 100.0, color='#2980b9', label='大型投行/G-SIBs广度 (G-SIBs %)', lw=1.0, alpha=0.75, ls=':')
    ax3.axhline(50, color='#e74c3c', ls='--', lw=1.0, label='多空平衡线 (50%)')
    ax3.axhline(20, color='#c0392b', ls=':', lw=1.2, label='广度坍塌警戒线 (20%)')
    ax3.axhspan(0, 20, color='#c0392b', alpha=0.08)
    ax3.set_ylabel('站上50MA比例 (%)', fontsize=11)
    ax3.set_ylim(-2, 102)
    ax3.set_title('【Layer 3】金融 38 股内部广度与系统性银行压力轮动监控 (G-SIBs vs Regional Banks)', fontsize=13, fontweight='bold')
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
    png_path = '宏观反身性阿尔法模型_KRE微观雷达4层全景图谱.png'
    plt.savefig(png_path, dpi=200)
    plt.close()
    print(f"📈 高清 4 层对齐全景图谱已生成: {os.path.abspath(png_path)}")


def main():
    print("🚀 启动区域性银行与金融板块 (KRE / XLF) 行业微观内生泡沫雷达量化全流程...")
    radar = KREBubbleRadar(target_ticker='KRE')
    radar.load_and_preprocess()
    print("✅ 离线数据加载与对齐完成")

    radar.compute_all_dimensions()
    print("✅ 4 维度统一分位数标定与分层加权雷达总分计算完成")

    radar.df.to_csv('kre_radar_local.csv', index=False)
    print(f"💾 预计算指标已固化至: kre_radar_local.csv (共 {len(radar.df)} 行)")

    result = run_brokerage_backtest(radar.df, ticker='KRE', start_date='2009-01-01')
    
    sub_bt = result.features
    df_daily = result.daily_accounts
    metrics = result.metrics
    from core_engine.export_utils import generate_trade_pairs
    df_pairs = generate_trade_pairs(result.orders, result.fills, sub_bt, 'KRE')

    print("\n==================================================")
    print("🎯 KRE 区域性银行微观雷达全周期实证对账审计报告 (2009 - 2026)")
    print("==================================================")
    print(f"定投总本金: USD {metrics['total_invested']:,.2f}")
    print(f"买入持有基准终值: USD {metrics['bench_final']:,.2f} (+{metrics['bench_return']:.2f}%), 最大回撤: {metrics['bench_max_dd']:.2f}%")
    print(f"微观雷达策略终值: USD {metrics['strat_final']:,.2f} (+{metrics['strat_return']:.2f}%), 最大回撤: {metrics['strat_max_dd']:.2f}%")
    print(f"超额 Alpha: {metrics['alpha']:+.2f}% | 净多赚现金财富: USD {metrics['strat_final'] - metrics['bench_final']:,.2f}")
    print(f"最大回撤改善幅度: {metrics['strat_max_dd'] - metrics['bench_max_dd']:+.2f}%")
    print(f"全周期调仓: {metrics['trade_count']} 笔 ({metrics['trade_rounds']} 轮)")
    print(f"波段胜率 (有效低买高卖/防踏空): {metrics['win_rate']:.1f}%")
    print("==================================================\n")

    # Print df_pairs directly if it exists
    if not df_pairs.empty:
        print("=== 逐笔买卖配对详细对账 ===")
        print(df_pairs.to_string(index=False))

    export_deliverables(result, "区域性银行与金融板块综合基准")
    plot_radar_chart(result)
    print("🎉 KRE 微观雷达全套交付物本地生成完毕！")


if __name__ == '__main__':
    main()
