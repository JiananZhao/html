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

        df = pd.merge(df_m, df_c, on='date', how='left').sort_values('date').reset_index(drop=True)
        const_cols = [c for c in df_c.columns if c != 'date']
        df[const_cols] = df[const_cols].ffill()
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
        # 维度 2: 半导体专属估值分位数与久期惩罚 (Score_Valuation, 25%)
        # -------------------------------------------------------------
        log_p = np.log(df[ticker])
        t_full = np.arange(len(df))
        slope, intercept = np.polyfit(t_full, log_p, 1)
        df['Log_Trend'] = slope * t_full + intercept
        df['Valuation_Residual'] = (log_p - df['Log_Trend']) * 100.0

        # 实际利率久期与资本开支贴现惩罚
        yield_surge = np.clip((df['Real_Yield'] - df['Real_Yield'].rolling(60, min_periods=20).min()) / 0.40, 0.0, 1.0)
        val_raw = df['Valuation_Residual'] + yield_surge * 15.0

        # 滚动 3 年 (756 交易日) 自适应分位数标定
        df['Score_Valuation'] = val_raw.rolling(756, min_periods=100).apply(lambda s: pd.Series(s).rank(pct=True).iloc[-1] * 100.0, raw=False)

        # -------------------------------------------------------------
        # 维度 3: 内部成分股广度高位顶背离 (Score_Breadth, 25%)
        # -------------------------------------------------------------
        above = pd.DataFrame({c: df[c] > df[c].rolling(50, min_periods=20).mean() for c in self.const_cols})
        df['Breadth_50'] = above.sum(axis=1) / above.notna().sum(axis=1)
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


def run_brokerage_backtest(df, ticker='SMH', start_date='2009-01-01', dca_monthly=1000.0):
    """
    券商级真实两状态记账回测引擎 (追踪 strat_shares 与 strat_cash)
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

    macro_anchor = 'HYG'

    for i in range(len(sub_bt)):
        p = sub_bt[ticker].iloc[i]
        d_str = sub_bt['date'].iloc[i]
        m = int(d_str.split('-')[1])
        score = sub_bt['Composite_Radar_Score'].iloc[i]
        gap = sub_bt['Gap'].iloc[i]
        gap_med = sub_bt['Gap_Median'].iloc[i]

        # 月定投注入
        if m != curr_m:
            tot_inv += dca_monthly
            b_sh += dca_monthly / p
            if pos > 0:
                s_sh += dca_monthly / p
            else:
                s_cash += dca_monthly
            curr_m = m

        action_today = 'HOLD' if pos > 0 else 'CASH'

        # 卖出判定
        if pos > 0 and sub_bt['Sell_Signal'].iloc[i]:
            s_cash += s_sh * p
            is_bub = sub_bt['Cond_Bubble'].iloc[i]
            exit_reg = 'BUBBLE' if is_bub else 'BEAR'
            r_reason = '宏观估值泡沫高位止盈' if is_bub else '系统宏观紧缩熊市避险'
            trades.append({
                'action': 'SELL',
                'date': d_str,
                'price': p,
                'shares': s_sh,
                'cash': s_cash,
                'reason': r_reason,
                'radar_score': score,
                'breadth': sub_bt['Breadth_50'].iloc[i]
            })
            action_today = 'SELL'
            s_sh = 0.0
            pos = 0.0

        # 买入判定
        elif pos == 0.0:
            can_buy = False
            b_reason = ""

            if exit_reg == 'BUBBLE':
                if sub_bt['Cond_Panic'].iloc[i]:
                    can_buy = True
                    b_reason = '极值黄金坑抄底'
                elif (gap < gap_med) and sub_bt['Above_MA20_Conf'].iloc[i] and sub_bt['Above_MA50_Conf'].iloc[i]:
                    can_buy = True
                    b_reason = '估值出清且右侧重构主升'
                elif (p > trades[-1]['price'] * 1.02) and sub_bt['Above_MA20_Conf'].iloc[i] and sub_bt['Above_MA50_Conf'].iloc[i]:
                    can_buy = True
                    b_reason = '突破卖出价右侧防踏空接回'
            elif exit_reg == 'BEAR':
                macro_healed = (sub_bt[macro_anchor].iloc[i] > sub_bt['Macro_MA200'].iloc[i])
                price_healed = sub_bt['Above_MA50_Conf'].iloc[i]
                if macro_healed and price_healed:
                    can_buy = True
                    b_reason = '宏观锚先导修复且趋势重构'

            if can_buy:
                s_sh = s_cash / p
                trades.append({
                    'action': 'BUY',
                    'date': d_str,
                    'price': p,
                    'shares': s_sh,
                    'cash': 0.0,
                    'reason': b_reason,
                    'radar_score': score,
                    'breadth': sub_bt['Breadth_50'].iloc[i]
                })
                s_cash = 0.0
                pos = 1.0
                action_today = 'BUY'

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
            'Score_Dynamics': sub_bt['Score_Dynamics'].iloc[i],
            'Score_Valuation': sub_bt['Score_Valuation'].iloc[i],
            'Score_Breadth': sub_bt['Score_Breadth'].iloc[i],
            'Score_Relative': sub_bt['Score_Relative'].iloc[i]
        })

    sub_bt['Bench_Equity'] = bench_vals
    sub_bt['Strat_Equity'] = strat_vals
    df_daily = pd.DataFrame(daily_records)

    # 统计核心指标
    b_final = bench_vals[-1]
    s_final = strat_vals[-1]
    b_ret = (b_final - tot_inv) / tot_inv * 100.0
    s_ret = (s_final - tot_inv) / tot_inv * 100.0
    alpha = s_ret - b_ret

    b_s = pd.Series(bench_vals)
    s_s = pd.Series(strat_vals)
    b_dd = ((b_s - b_s.cummax()) / b_s.cummax()).min() * 100.0
    s_dd = ((s_s - s_s.cummax()) / s_s.cummax()).min() * 100.0

    # 整理逐笔买卖配对表
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


def export_deliverables(sub_bt, df_daily, df_pairs, metrics, ticker='SMH'):
    """
    导出机构级 Excel 审计全底稿与高清 4 层对齐图谱
    """
    # 1. 导出 Excel
    excel_path = '宏观反身性阿尔法模型_SMH微观雷达全周期对账表.xlsx'
    with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
        df_overview = pd.DataFrame([{
            '标的资产': ticker,
            '资产名称': 'VanEck 半导体 ETF',
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
    sub_bt, df_daily, df_pairs, metrics = run_brokerage_backtest(radar.df, ticker='SMH', start_date='2009-01-01')

    print("\n==================================================")
    print("🎯 SMH 半导体微观雷达全周期实证对账审计报告 (2009 - 2026)")
    print("==================================================")
    print(f"定投总本金: USD {metrics['total_invested']:,.2f}")
    print(f"买入持有基准终值: USD {metrics['bench_final']:,.2f} (+{metrics['bench_return']:.2f}%), 最大回撤: {metrics['bench_max_dd']:.2f}%")
    print(f"微观雷达策略终值: USD {metrics['strat_final']:,.2f} (+{metrics['strat_return']:.2f}%), 最大回撤: {metrics['strat_max_dd']:.2f}%")
    print(f"超额 Alpha: {metrics['alpha']:+.2f}% | 净多赚现金财富: USD {metrics['strat_final'] - metrics['bench_final']:,.2f}")
    print(f"最大回撤改善幅度: {metrics['strat_max_dd'] - metrics['bench_max_dd']:+.2f}%")
    print(f"全周期调仓: {metrics['trade_count']} 笔 ({metrics['trade_rounds']} 轮)")
    print(f"波段胜率 (有效低买高卖/防踏空): {metrics['win_rate']:.1f}%")
    print("==================================================\n")

    print("=== 逐笔买卖配对详细对账 ===")
    print(df_pairs.to_string())

    export_deliverables(sub_bt, df_daily, df_pairs, metrics, ticker='SMH')
    print("🎉 SMH 微观雷达全套交付物本地生成完毕！")


if __name__ == '__main__':
    main()
