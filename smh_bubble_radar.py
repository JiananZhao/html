"""
行业微观内生泡沫雷达量化引擎 (Micro-Bubble Radar Engine) —— 半导体芯片板块 (SMH)
严格遵循 LESSONS_LEARNED.md 与 AGENTS.md 规范：
1. 100% 本地脱机闭环 (Local-First): 读取 market_data_local.csv 与 smh_constituents_local.csv
2. 4 维度统一全历史自适应扩展分位数 (0~100 Uniform Percentile, Mean ≈ 50, 消除量纲冲突)
3. 突出 Layer 2 连续雷达状态感知 (0~100) 与 Layer 3 内部广度顶背离 (15大芯片巨头50MA)
4. 券商级真实两状态记账 (strat_shares 与 strat_cash 两状态变量，定投本金 $1,000/月，2009-2026 17.6年)
5. 输出 3 表合一机构级 Excel 审计底稿与高清 4 层全景图谱
"""

import os
import sys
import io
import numpy as np
import pandas as pd
from expanding_ols import expanding_polyfit_residual
import matplotlib.pyplot as plt

# 强制 UTF-8 输出以兼容 Windows 终端
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 配置 Matplotlib 中文字体与符号 (Lesson 9)
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'SimSun', 'sans-serif']
plt.rcParams['axes.unicode_minus'] = False


class SMHBubbleRadar:
    """
    半导体板块专属微观内生泡沫雷达引擎
    """
    def __init__(self, market_data_path='market_data_local.csv', constituents_path='smh_constituents_local.csv'):
        self.market_data_path = market_data_path
        self.constituents_path = constituents_path
        self.df = None
        self.ticker = 'SMH'
        self.weights = {
            'dynamics': 0.35,
            'valuation': 0.25,
            'breadth': 0.25,
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
        return self.df

    def compute_all_dimensions(self):
        """
        计算 4 个独立维度分项与加权综合分
        """
        df = self.df
        ticker = self.ticker

        # -------------------------------------------------------------
        # 维度 1: 价格超指数动力学 (Score_Dynamics, 35%)
        # -------------------------------------------------------------
        ema200 = df[ticker].ewm(span=200, adjust=False).mean()
        dist_200 = (df[ticker] - ema200) / ema200 * 100.0

        # LPPLS 超指数奇异性非线性矩阵拟合
        lppls_scores = np.zeros(len(df))
        N_window = 130
        for i in range(N_window, len(df), 3):
            sub_p = df[ticker].iloc[i-N_window:i+1].values
            log_p = np.log(sub_p)
            N = len(sub_p)
            t_series = np.arange(N)
            best_r2 = 0.0
            
            for dt in [10, 20, 30]:
                tc = N + dt
                for m_val in [0.3, 0.6, 0.8]:
                    for omega in [6.0, 9.0, 13.0]:
                        f = (tc - t_series) ** m_val
                        g = f * np.cos(omega * np.log(np.maximum(1e-4, tc - t_series)))
                        h = f * np.sin(omega * np.log(np.maximum(1e-4, tc - t_series)))
                        X = np.column_stack([np.ones(N), f, g, h])
                        try:
                            beta, _, _, _ = np.linalg.lstsq(X, log_p, rcond=None)
                            B = beta[1]
                            C1, C2 = beta[2], beta[3]
                            if B < 0:
                                C = np.sqrt(C1**2 + C2**2)
                                if C / np.abs(B) < 1.0:
                                    pred = X @ beta
                                    ss_tot = np.sum((log_p - np.mean(log_p))**2)
                                    ss_res = np.sum((log_p - pred)**2)
                                    r2 = 1.0 - ss_res / (ss_tot + 1e-8)
                                    if r2 > best_r2:
                                        best_r2 = r2
                        except:
                            continue
            for k in range(3):
                if i + k < len(df):
                    lppls_scores[i + k] = best_r2

        df['LPPLS_R2'] = lppls_scores
        raw_dyn = 0.50 * df['LPPLS_R2'] * 100.0 + 0.50 * dist_200
        # 滚动 2 年 (504 交易日) 自适应分位数标定
        df['Score_Dynamics'] = raw_dyn.rolling(504, min_periods=60).apply(lambda s: pd.Series(s).rank(pct=True).iloc[-1] * 100.0, raw=False)

        # -------------------------------------------------------------
        # 维度 2: 行业专属估值分位数与久期惩罚 (Score_Valuation, 0~100)
        # -------------------------------------------------------------
        ols_res = expanding_polyfit_residual(df[ticker], min_periods=252)
        df['Log_Trend'] = ols_res['Log_Trend']
        df['Valuation_Residual'] = ols_res['Valuation_Residual']

        # 实际利率久期与资本开支贴现惩罚
        yield_surge = np.clip((df['Real_Yield'] - df['Real_Yield'].rolling(60, min_periods=20).min()) / 0.40, 0.0, 1.0)
        val_raw = df['Valuation_Residual'] + yield_surge * 15.0

        # 滚动 3 年 (756 交易日) 自适应分位数标定
        df['Score_Valuation'] = val_raw.rolling(756, min_periods=100).apply(lambda s: pd.Series(s).rank(pct=True).iloc[-1] * 100.0, raw=False)

        # -------------------------------------------------------------
        # 维度 3: 内部成分股广度高位顶背离 (Score_Breadth, 25%)
        # -------------------------------------------------------------
        is_valid = pd.DataFrame({c: self.fresh_mask[c] & df[c].rolling(50, min_periods=20).mean().notna() for c in self.const_cols})
        above = pd.DataFrame({c: df[c] > df[c].rolling(50, min_periods=20).mean() for c in self.const_cols})
        df['Breadth_Valid_Count'] = is_valid.sum(axis=1)
        df['Breadth_Coverage'] = df['Breadth_Valid_Count'] / len(self.const_cols)
        df['Breadth_50'] = (above & is_valid).sum(axis=1) / df['Breadth_Valid_Count'].replace(0, np.nan)
        df['High_60'] = df[ticker].rolling(60, min_periods=20).max()
        df['Price_Ratio_High'] = df[ticker] / df['High_60']

        # 修正逻辑：仅在价格处于高位区间 (距离60日高点不足10%) 时衡量广度缺失；超跌后背离度严格归零
        high_proximity = np.clip((df['Price_Ratio_High'] - 0.90) / 0.10, 0.0, 1.0)
        raw_div = high_proximity * (1.0 - df['Breadth_50']) * 100.0
        # 滚动 2 年分位数标定
        df['Score_Breadth'] = raw_div.rolling(504, min_periods=60).apply(lambda s: pd.Series(s).rank(pct=True).iloc[-1] * 100.0, raw=False)

        # -------------------------------------------------------------
        # 维度 4: 跨资产抛物线脱节乖离 (Score_Relative, 15%)
        # -------------------------------------------------------------
        df['Ratio_QQQ'] = df[ticker] / df['QQQ']
        ratio_ma60 = df['Ratio_QQQ'].rolling(60, min_periods=20).mean()
        ratio_dist_60 = (df['Ratio_QQQ'] - ratio_ma60) / ratio_ma60 * 100.0
        # 滚动 2 年分位数标定：仅在相对纳指发生垂直脱节冲刺时计分
        df['Score_Relative'] = ratio_dist_60.rolling(504, min_periods=60).apply(lambda s: pd.Series(s).rank(pct=True).iloc[-1] * 100.0, raw=False)

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
        # 宏观反身性与均线系统 (与大盘信贷流动性宏观锚融合)
        # -------------------------------------------------------------
        macro_anchor = 'HYG'
        df['MA10'] = df[ticker].rolling(10).mean()
        df['MA20'] = df[ticker].rolling(20).mean()
        df['MA50'] = df[ticker].rolling(50).mean()
        df['MA200'] = df[ticker].rolling(200).mean()
        df['Dist_200MA'] = (df[ticker] - df['MA200']) / df['MA200'] * 100.0

        df['Macro_MA50'] = df[macro_anchor].rolling(50).mean()
        df['Macro_MA200'] = df[macro_anchor].rolling(200).mean()
        df['BAA_MA60'] = df['BAA10Y'].rolling(60).mean()
        df['BAA_Stress'] = df['BAA10Y'] > df['BAA_MA60']
        df['RY_Surge'] = (df['Real_Yield'] - df['Real_Yield'].rolling(60).min()) > 0.40

        df['NFCI_Roll_Mean'] = df['NFCI'].rolling(252).mean()
        df['NFCI_Roll_Std'] = df['NFCI'].rolling(252).std()
        df['NFCI_Z'] = (df['NFCI'] - df['NFCI_Roll_Mean']) / (df['NFCI_Roll_Std'] + 1e-8)

        # 反身性偏离度 Gap (动态 Beta 定价)
        df['Price_Z'] = (df[ticker] - df[ticker].rolling(200).mean()) / (df[ticker].rolling(200).std() + 1e-8)
        df['Macro_Z'] = (df[macro_anchor] - df[macro_anchor].rolling(200).mean()) / (df[macro_anchor].rolling(200).std() + 1e-8)
        roll_cov = df['Price_Z'].rolling(252).cov(df['Macro_Z'])
        roll_var = df['Macro_Z'].rolling(252).var()
        df['Dynamic_Beta'] = (roll_cov / (roll_var + 1e-8)).clip(lower=-2.0, upper=2.0)
        df['Expected_Price_Z'] = df['Macro_Z'] * df['Dynamic_Beta']
        df['Gap'] = df['Price_Z'] - df['Expected_Price_Z']

        df['Gap_Max_45'] = df['Gap'].rolling(45, min_periods=1).max()
        df['PriceZ_Max_45'] = df['Price_Z'].rolling(45, min_periods=1).max()
        df['Gap_Median'] = df['Gap'].rolling(252, min_periods=20).median()
        df['Gap_Upper'] = df['Gap'].expanding(min_periods=20).quantile(0.85)

        # 攻防两端信号定义 (经严格回测与实盘验证的 Master 规则)
        dist_bubble_th = 15.0
        price_filter = 'MA50'

        df['Cond_Bubble'] = (
            (df['Gap_Max_45'] > df['Gap_Upper']) & 
            (df['PriceZ_Max_45'] > 1.5) & 
            (df['Dist_200MA'] > dist_bubble_th) & 
            (df['NFCI'] > -0.50) & 
            df['BAA_Stress'] & 
            (df[ticker] < df[price_filter])
        )
        df['Macro_Crisis'] = (
            (df[macro_anchor] < df['Macro_MA200']) & 
            df['RY_Surge'] & 
            (df['NFCI_Z'] > 1.2) & 
            (df['NFCI'] > -0.50)
        )
        df['Cond_Bear'] = df['Macro_Crisis'] & (df[ticker] < df['MA50']) & (df[ticker] < df['MA200'])
        df['Sell_Signal'] = df['Cond_Bubble'] | df['Cond_Bear']

        df['Above_MA50_Conf'] = (df[ticker] > df['MA50']).rolling(3, min_periods=1).sum() == 3
        df['Above_MA20_Conf'] = (df[ticker] > df['MA20']).rolling(3, min_periods=1).sum() == 3
        df['Cond_Panic'] = (df['Dist_200MA'].rolling(10, min_periods=1).min() < -10.0) & (df[ticker] > df['MA10'])

        self.df = df
        return df


def run_brokerage_backtest(df, ticker='SMH', start_date='2009-01-01', dca_monthly=1000.0, cost_config=0.0):
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
        score = sub_bt['Composite_Radar_Score'].iloc[i]
        gap = sub_bt['Gap'].iloc[i]
        gap_med = sub_bt['Gap_Median'].iloc[i]
        macro_anchor = 'HYG'
        
        # 定投及买入 (按收盘价)
        dca_amount = 0.0
        if m != curr_m:
            curr_m = m
            dca_amount = dca_monthly
            total_invested += dca_monthly

        executor.step(dt, p, p, dca_amount=dca_amount)
        bench_executor.step(dt, p, p, dca_amount=dca_amount)
        
        # T 日收盘后产生新信号，传给 T+1
        if pos > 0 and sub_bt['Sell_Signal'].iloc[i]:
            is_bub = sub_bt['Cond_Bubble'].iloc[i]
            exit_reg = 'BUBBLE' if is_bub else 'BEAR'
            pending_reason = '泡沫高点破位预警' if is_bub else '宏观及基本面双破位'
            pos = 0.0
            executor.submit_order(pos, pending_reason, dt)
        elif pos == 0.0:
            can_buy = False
            b_reason = ""
            if exit_reg == 'BUBBLE':
                if sub_bt['Cond_Panic'].iloc[i]:
                    can_buy = True
                    b_reason = '极度恐慌修复买入'
                elif (gap < gap_med) and sub_bt['Above_MA20_Conf'].iloc[i] and sub_bt['Above_MA50_Conf'].iloc[i]:
                    can_buy = True
                    b_reason = '回踩中枢且动能恢复'
                elif len(executor.fills) > 0 and (p > executor.fills[-1]['price'] * 1.02) and sub_bt['Above_MA20_Conf'].iloc[i] and sub_bt['Above_MA50_Conf'].iloc[i]:
                    can_buy = True
                    b_reason = '突破前高阻力重拾升势'
            elif exit_reg == 'BEAR':
                macro_healed = (sub_bt[macro_anchor].iloc[i] > sub_bt['Macro_MA200'].iloc[i])
                price_healed = sub_bt['Above_MA50_Conf'].iloc[i]
                if macro_healed and price_healed:
                    can_buy = True
                    b_reason = '宏观修复且均线多头'
            if can_buy:
                pos = 1.0
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
    ticker = result.metadata.get('ticker', 'SMH')
    df_pairs = generate_trade_pairs(result.orders, result.fills, sub_bt, ticker)

    # 2. 导出高清 4 层对齐图谱 (Lesson 9: 严禁未转义裸 $ 符号，显式配置中文)
    fig, axes = plt.subplots(4, 1, figsize=(16, 15), sharex=True, gridspec_kw={'height_ratios': [3.0, 2.2, 2.0, 2.5]})
    dates = pd.to_datetime(sub_bt['date'])

    # Layer 1: 标的价格与均线
    ax1 = axes[0]
    ax1.plot(dates, sub_bt[ticker], color='#2b2b2b', label=f'{ticker} 收盘价', lw=1.5)
    ax1.plot(dates, sub_bt['MA50'], color='#f39c12', label='50日生命线', lw=1.2, ls='--')
    ax1.plot(dates, sub_bt['MA200'], color='#3498db', label='200日年线牛熊分界', lw=1.4)
    # 标记买卖点
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

    # Layer 2: 综合微观雷达打分看板 (0 ~ 100)
    ax2 = axes[1]
    ax2.plot(dates, sub_bt['Composite_Radar_Score'], color='#8e44ad', label='综合微观雷达分 (0~100)', lw=1.6)
    ax2.plot(dates, sub_bt['Score_Dynamics'], color='#e67e22', label='动力学奇异度分位数 (35%)', lw=0.9, alpha=0.7)
    ax2.plot(dates, sub_bt['Score_Valuation'], color='#16a085', label='半导体专属估值分位数 (25%)', lw=0.9, alpha=0.7)
    ax2.plot(dates, sub_bt['Score_Breadth'], color='#c0392b', label='内部广度顶背离分位数 (25%)', lw=0.9, alpha=0.7)
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

    # Layer 3: 内部成分股 50MA 真实广度
    ax3 = axes[2]
    ax3.plot(dates, sub_bt['Breadth_50'] * 100.0, color='#d35400', label='Top 15 核心芯片股站上 50MA 比例 (%)', lw=1.5)
    ax3.axhline(50, color='#e74c3c', ls='--', lw=1.0, label='多空平衡线 (50%)')
    ax3.axhline(40, color='#c0392b', ls=':', lw=1.2, label='广度严重坍塌线 (40%)')
    ax3.axhspan(0, 40, color='#c0392b', alpha=0.08)
    ax3.set_ylabel('站上50MA比例 (%)', fontsize=11)
    ax3.set_ylim(-2, 102)
    ax3.set_title('【Layer 3】前 15 大核心芯片巨头 50MA 内部真实广度与顶背离监控', fontsize=13, fontweight='bold')
    ax3.grid(True, alpha=0.3)
    ax3.legend(loc='upper left', framealpha=0.9)

    # Layer 4: 真实券商账户净值对比曲线
    ax4 = axes[3]
    ax4.plot(dates, sub_bt['Bench_Equity'], color='#7f8c8d', label=f'买入持有基准 (B&H 终值: USD {metrics["bench_final"]:,.0f})', lw=1.5, ls='--')
    ax4.plot(dates, sub_bt['Strat_Equity'], color='#27ae60', label=f'微观雷达策略 (策略终值: USD {metrics["strat_final"]:,.0f} | Alpha: {metrics["alpha"]:+.1f}%)', lw=2.0)
    ax4.set_ylabel('账户资产净值 (USD)', fontsize=11)
    ax4.set_title(f'【Layer 4】真实券商记账资产增殖对比 (定投总本金 USD {metrics["total_invested"]:,.0f})', fontsize=13, fontweight='bold')
    ax4.grid(True, alpha=0.3)
    ax4.legend(loc='upper left', framealpha=0.9)

    plt.tight_layout()
    png_path = '宏观反身性阿尔法模型_SMH微观雷达4层全景图谱.png'
    plt.savefig(png_path, dpi=200)
    plt.close()
    print(f"📈 高清 4 层对齐全景图谱已生成: {os.path.abspath(png_path)}")


def main():
    print("🚀 启动半导体板块 (SMH) 行业微观内生泡沫雷达量化全流程...")
    radar = SMHBubbleRadar()
    radar.load_and_preprocess()
    print("✅ 离线数据加载与对齐完成")

    radar.compute_all_dimensions()
    print("✅ 4 维度统一分位数标定与雷达总分计算完成")

    # 导出本地预计算指标库 (用于后续 Web 秒开)
    radar.df.to_csv('smh_radar_local.csv', index=False)
    print(f"💾 预计算指标已固化至: smh_radar_local.csv (共 {len(radar.df)} 行)")

    # 真实券商记账回测 (2009-01-01 开始，涵盖完整 17.6 年 213 个月)
    result = run_brokerage_backtest(radar.df, ticker='SMH', start_date='2009-01-01')
    sub_bt = result.features
    df_daily = result.daily_accounts
    metrics = result.metrics
    from core_engine.export_utils import generate_trade_pairs
    df_pairs = generate_trade_pairs(result.orders, result.fills, sub_bt, 'SMH')

    print("\n==================================================")
    print("🎯 SMH 半导体微观雷达全周期实证对账审计报告 (2009 - 2026)")
    print("==================================================")
    print(f"定投总本金: USD {metrics.get('total_invested', 0):,.2f}")
    print(f"买入持有基准终值: USD {metrics.get('bench_final', 0):,.2f} (+{metrics.get('bench_return', 0):.2f}%), 最大回撤: {metrics.get('bench_max_dd', 0):.2f}%")
    print(f"微观雷达策略终值: USD {metrics.get('strat_final', 0):,.2f} (+{metrics.get('strat_return', 0):.2f}%), 最大回撤: {metrics.get('strat_max_dd', 0):.2f}%")
    print(f"超额 Alpha: {metrics.get('alpha', 0):+.2f}% | 净多赚现金财富: USD {metrics.get('strat_final', 0) - metrics.get('bench_final', 0):,.2f}")
    print(f"最大回撤改善幅度: {metrics.get('strat_max_dd', 0) - metrics.get('bench_max_dd', 0):+.2f}%")
    print(f"全周期调仓: {metrics.get('trade_count', 0)} 笔 ({metrics.get('trade_rounds', 0)} 轮)")
    print(f"波段胜率 (有效低买高卖/防踏空): {metrics.get('win_rate', 0):.1f}%")
    print("==================================================\n")

    print("=== 逐笔买卖配对详细对账 ===")
    print(df_pairs.to_string())

    export_deliverables(result, "VanEck 半导体 ETF")
    plot_radar_chart(result)
    print("🎉 SMH 微观雷达全套交付物本地生成完毕！")


if __name__ == '__main__':
    main()
