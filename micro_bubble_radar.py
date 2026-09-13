"""
微观泡沫雷达量化引擎 (Micro-Bubble Radar Engine) —— IGV 先行验证标的
支持 4 维度独立度量与加权复合生成 0~100 微观雷达分：
1. 价格动力学与 LPPLS 奇异度 (Score_Dynamics, 0~100)
2. 行业内生估值分位数与久期折现惩罚 (Score_Valuation, 0~100)
3. 内部成分股广度坍塌与顶背离 (Score_Breadth, 0~100)
4. 跨资产剪刀差与相对强度溢价 (Score_Relative, 0~100)

包含：
- 逐日计算 4 个独立分项与加权总分
- 券商级真实两状态记账回测 (追踪真实股数与现金池)
- 导出机构级三层 Excel 对账总表 (绩效、逐笔配对、逐日流水)
- 导出高清 4 层对齐信号与净值对比图谱
"""

import os
import sys
import io
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

# 强制 UTF-8 输出
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 配置 Matplotlib 中文字体与符号 (Lesson 9)
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'SimSun', 'sans-serif']
plt.rcParams['axes.unicode_minus'] = False


class MicroBubbleRadar:
    """
    微观泡沫雷达引擎 (以 IGV 为先行标的)
    """
    def __init__(self, market_data_path='market_data_local.csv', constituents_path='igv_constituents_local.csv'):
        self.market_data_path = market_data_path
        self.constituents_path = constituents_path
        self.df = None
        self.ticker = 'IGV'
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

        df = pd.merge(df_m, df_c, on='date', how='inner').sort_values('date').reset_index(drop=True)
        self.df = df
        self.const_cols = [c for c in df_c.columns if c != 'date']
        return self.df

    def compute_all_dimensions(self):
        """
        计算 4 个独立维度分项与加权综合分
        """
        df = self.df
        ticker = self.ticker

        # -------------------------------------------------------------
        # 维度 1: 价格动力学与 LPPLS 奇异度 (Score_Dynamics, 0~100)
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
                for m in [0.3, 0.6, 0.8]:
                    for omega in [6.0, 9.0, 13.0]:
                        f = (tc - t_series) ** m
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
        log_p = np.log(df[ticker])
        t_full = np.arange(len(df))
        slope, intercept = np.polyfit(t_full, log_p, 1)
        df['Log_Trend'] = slope * t_full + intercept
        df['Valuation_Residual'] = (log_p - df['Log_Trend']) * 100.0

        # 实际利率久期惩罚 (软件平均久期 15-20 年)
        yield_surge = np.clip((df['Real_Yield'] - df['Real_Yield'].rolling(60, min_periods=20).min()) / 0.40, 0.0, 1.0)
        val_raw = df['Valuation_Residual'] + yield_surge * 15.0

        # 滚动 3 年 (756 交易日) 自适应分位数标定
        df['Score_Valuation'] = val_raw.rolling(756, min_periods=100).apply(lambda s: pd.Series(s).rank(pct=True).iloc[-1] * 100.0, raw=False)

        # -------------------------------------------------------------
        # 维度 3: 内部成分股广度高位顶背离 (Score_Breadth, 0~100，彻底剔除底部污染)
        # -------------------------------------------------------------
        above = pd.DataFrame({c: df[c] > df[c].rolling(50, min_periods=20).mean() for c in self.const_cols})
        df['Breadth_50'] = above.sum(axis=1) / above.notna().sum(axis=1)
        df['High_60'] = df[ticker].rolling(60, min_periods=20).max()
        df['Price_Ratio_High'] = df[ticker] / df['High_60']

        # 修正：当且仅当价格处于高位区间 (距离60日高点不足10%) 时，衡量广度缺失；超跌后背离度严格归零
        high_proximity = np.clip((df['Price_Ratio_High'] - 0.90) / 0.10, 0.0, 1.0)
        raw_div = high_proximity * (1.0 - df['Breadth_50']) * 100.0
        # 滚动 2 年分位数标定
        df['Score_Breadth'] = raw_div.rolling(504, min_periods=60).apply(lambda s: pd.Series(s).rank(pct=True).iloc[-1] * 100.0, raw=False)

        # -------------------------------------------------------------
        # 维度 4: 跨资产抛物线脱节乖离 (Score_Relative, 0~100，动量与泡沫解耦)
        # -------------------------------------------------------------
        df['Ratio_QQQ'] = df[ticker] / df['QQQ']
        ratio_ma60 = df['Ratio_QQQ'].rolling(60, min_periods=20).mean()
        ratio_dist_60 = (df['Ratio_QQQ'] - ratio_ma60) / ratio_ma60 * 100.0
        # 滚动 2 年分位数标定：仅在相对 60MA 发生抛物线垂直拉升时计分
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

        # 辅助均线与确认
        df['MA10'] = df[ticker].rolling(10).mean()
        df['MA20'] = df[ticker].rolling(20).mean()
        df['MA50'] = df[ticker].rolling(50).mean()
        df['MA200'] = df[ticker].rolling(200).mean()
        df['Dist_200MA'] = (df[ticker] - df['MA200']) / df['MA200'] * 100.0
        df['Above_MA20_Conf'] = (df[ticker] > df['MA20']).rolling(3, min_periods=1).sum() == 3
        df['Above_MA50_Conf'] = (df[ticker] > df['MA50']).rolling(3, min_periods=1).sum() == 3
        df['Below_MA50_3D'] = (df[ticker] < df['MA50']).rolling(3, min_periods=1).sum() == 3
        df['Cond_Panic'] = (df['Dist_200MA'].rolling(10, min_periods=1).min() < -10.0) & (df[ticker] > df['MA10'])

        # 攻防信号：25日记忆窗口 + 实质性破位确认 (击穿MA50达1%或跌破MA200) + 广度实质收缩 (<45%)
        radar_win_25 = df['Composite_Radar_Score'].rolling(25, min_periods=1).max()
        ma50_broken = df['Below_MA50_3D'] & (df[ticker] < df['MA50'] * 0.99)
        ma200_danger = (df[ticker] < df['MA200'] * 1.02) & (df[ticker] < df['MA50'])
        df['Cond_Bubble'] = (radar_win_25 >= 70.0) & (ma50_broken | ma200_danger) & (df['Breadth_50'] < 0.45)
        df['Cond_Bear'] = False
        df['Sell_Signal'] = df['Cond_Bubble']

        self.df = df
        return df


def run_brokerage_backtest(df, ticker='IGV', start_date='2012-01-01', dca_monthly=1000.0, cooldown_days=20):
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
    last_buy_idx = -999

    for i in range(len(sub_bt)):
        p = sub_bt[ticker].iloc[i]
        d_str = sub_bt['date'].iloc[i]
        m = int(d_str.split('-')[1])
        score = sub_bt['Composite_Radar_Score'].iloc[i]

        # 月定投注入
        if m != curr_m:
            tot_inv += dca_monthly
            b_sh += dca_monthly / p
            if pos > 0:
                s_sh += dca_monthly / p
            else:
                s_cash += dca_monthly
            curr_m = m

        is_bub = sub_bt['Cond_Bubble'].iloc[i]
        is_bear = sub_bt['Cond_Bear'].iloc[i]
        action_today = 'HOLD'

        # 卖出判定 (增加买入后冷却期，防止刚刚接回又因单日波动被假摔震出)
        if pos > 0 and (is_bub or is_bear) and (i - last_buy_idx >= cooldown_days):
            s_cash += s_sh * p
            exit_reg = 'BUBBLE' if is_bub else 'BEAR'
            r_reason = '微观雷达泡沫与广度坍塌止盈' if is_bub else '宏观系统性紧缩避险'
            trades.append({
                'action': 'SELL',
                'date': d_str,
                'price': p,
                'shares': s_sh,
                'cash': s_cash,
                'reason': r_reason,
                'score': score,
                'score_dyn': sub_bt['Score_Dynamics'].iloc[i],
                'score_val': sub_bt['Score_Valuation'].iloc[i],
                'score_brd': sub_bt['Score_Breadth'].iloc[i],
                'score_rel': sub_bt['Score_Relative'].iloc[i]
            })
            action_today = 'SELL'
            s_sh = 0.0
            pos = 0.0

        elif pos == 0:
            can_buy = False
            b_reason = ""

            if exit_reg == 'BUBBLE':
                radar_cooled = sub_bt['Composite_Radar_Score'].iloc[i] < 35.0
                if sub_bt['Cond_Panic'].iloc[i]:
                    can_buy = True
                    b_reason = '极值黄金坑抄底'
                elif radar_cooled and sub_bt['Above_MA50_Conf'].iloc[i]:
                    can_buy = True
                    b_reason = '微观雷达估值出清且右侧重构'
                elif (p > trades[-1]['price'] * 1.02) and sub_bt['Above_MA20_Conf'].iloc[i] and sub_bt['Above_MA50_Conf'].iloc[i]:
                    can_buy = True
                    b_reason = '突破卖出价右侧防踏空接回'

            elif exit_reg == 'BEAR':
                macro_healed = (sub_bt['HYG'].iloc[i] > sub_bt['Macro_MA200'].iloc[i])
                price_healed = sub_bt['Above_MA50_Conf'].iloc[i]
                if macro_healed and price_healed:
                    can_buy = True
                    b_reason = '宏观锚先导修复且趋势重构'

            if can_buy:
                s_sh += s_cash / p
                s_cash = 0.0
                pos = 1.0
                exit_reg = None
                action_today = 'BUY'
                last_buy_idx = i
                trades.append({
                    'action': 'BUY',
                    'date': d_str,
                    'price': p,
                    'shares': s_sh,
                    'cash': s_cash,
                    'reason': b_reason,
                    'score': score,
                    'score_dyn': sub_bt['Score_Dynamics'].iloc[i],
                    'score_val': sub_bt['Score_Valuation'].iloc[i],
                    'score_brd': sub_bt['Score_Breadth'].iloc[i],
                    'score_rel': sub_bt['Score_Relative'].iloc[i]
                })

        b_val = b_sh * p
        s_val = s_sh * p + s_cash
        bench_vals.append(b_val)
        strat_vals.append(s_val)

        daily_records.append({
            '日期': d_str,
            '收盘价': p,
            '当日操作': action_today,
            '持仓状态': pos,
            '策略持股数': s_sh,
            '策略现金池': s_cash,
            '基准净值': b_val,
            '策略净值': s_val,
            '动力学得分': sub_bt['Score_Dynamics'].iloc[i],
            '估值分位数得分': sub_bt['Score_Valuation'].iloc[i],
            '广度背离得分': sub_bt['Score_Breadth'].iloc[i],
            '跨资产相对溢价得分': sub_bt['Score_Relative'].iloc[i],
            '复合雷达总分': score,
            '成分股50MA广度': sub_bt['Breadth_50'].iloc[i]
        })

    # 配对交易表
    paired_trades = []
    round_id = 1
    for k in range(0, len(trades) - 1, 2):
        if trades[k]['action'] == 'SELL' and trades[k+1]['action'] == 'BUY':
            s_t = trades[k]
            b_t = trades[k+1]
            p_chg = (b_t['price'] - s_t['price']) / s_t['price'] * 100.0
            sh_chg = (b_t['shares'] - s_t['shares']) / s_t['shares'] * 100.0
            paired_trades.append({
                '轮次': round_id,
                '卖出日期': s_t['date'],
                '卖出价格': s_t['price'],
                '卖出原因': s_t['reason'],
                '卖出雷达分': s_t['score'],
                '卖出动力学分': s_t['score_dyn'],
                '卖出估值分': s_t['score_val'],
                '卖出广度分': s_t['score_brd'],
                '卖出相对分': s_t['score_rel'],
                '买入日期': b_t['date'],
                '买入价格': b_t['price'],
                '买入原因': b_t['reason'],
                '买入雷达分': b_t['score'],
                '期间标的涨跌': f"{p_chg:+.2f}%",
                '持股增益幅度': f"{sh_chg:+.2f}%",
                '是否实现低买高卖': '✅ 是' if b_t['price'] < s_t['price'] else '⚠️ 防踏空'
            })
            round_id += 1

    b_fin = bench_vals[-1]
    s_fin = strat_vals[-1]
    b_ret = (b_fin - tot_inv) / tot_inv * 100.0
    s_ret = (s_fin - tot_inv) / tot_inv * 100.0
    alpha = s_ret - b_ret

    b_s = pd.Series(bench_vals)
    s_s = pd.Series(strat_vals)
    b_dd = ((b_s - b_s.cummax()) / b_s.cummax()).min() * 100.0
    s_dd = ((s_s - s_s.cummax()) / s_s.cummax()).min() * 100.0

    metrics = {
        'tot_inv': tot_inv,
        'b_fin': b_fin,
        's_fin': s_fin,
        'b_ret': b_ret,
        's_ret': s_ret,
        'alpha': alpha,
        'b_dd': b_dd,
        's_dd': s_dd,
        'rounds': len(paired_trades)
    }

    return metrics, pd.DataFrame(paired_trades), pd.DataFrame(daily_records)


def export_deliverables(df, metrics, df_paired, df_daily, ticker='IGV'):
    """
    导出 Excel 交付底稿与 4 层高清对齐图谱
    """
    excel_path = f"宏观反身性阿尔法模型_{ticker}微观雷达全周期对账表.xlsx"
    plot_path = f"宏观反身性阿尔法模型_{ticker}微观雷达4层全景图谱.png"

    print(f"📊 正在导出 Excel 全底稿: {excel_path} ...")
    with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
        df_summary = pd.DataFrame([{
            '标的代码': ticker,
            '资产全称': 'iShares 扩展科技软件与云计算 ETF',
            '定投总本金 (USD)': metrics['tot_inv'],
            '基准终值 (USD)': metrics['b_fin'],
            '基准总回报率': f"{metrics['b_ret']:+.2f}%",
            '基准最大回撤': f"{metrics['b_dd']:.2f}%",
            '策略终值 (USD)': metrics['s_fin'],
            '策略总回报率': f"{metrics['s_ret']:+.2f}%",
            '策略最大回撤': f"{metrics['s_dd']:.2f}%",
            '超额阿尔法 (Alpha)': f"{metrics['alpha']:+.2f}%",
            '超额净财富增量 (USD)': metrics['s_fin'] - metrics['b_fin'],
            '总调仓轮次': metrics['rounds'],
            '有效低吸胜率': f"{(df_paired['是否实现低买高卖'] == '✅ 是').sum() / len(df_paired) * 100:.1f}%"
        }])
        df_summary.to_excel(writer, sheet_name='绩效总览表', index=False)
        df_paired.to_excel(writer, sheet_name='逐笔买卖配对表', index=False)
        df_daily.to_excel(writer, sheet_name='逐日分项流水总账', index=False)
    print(f"✅ Excel 导出成功: {excel_path}")

    # 绘制 4 层高清图谱
    print(f"🎨 正在绘制 4 层高清对齐图谱: {plot_path} ...")
    dates = pd.to_datetime(df_daily['日期'])
    
    fig, axes = plt.subplots(4, 1, figsize=(18, 16), sharex=True, gridspec_kw={'height_ratios': [2.5, 1.8, 1.8, 2.0]})
    fig.patch.set_facecolor('#ffffff')

    # Panel 1: 价格与买卖点标记
    ax1 = axes[0]
    ax1.set_facecolor('#fcfcfc')
    ax1.plot(dates, df_daily['收盘价'], label=f'{ticker} 价格', color='#1f77b4', lw=2.0)
    ma50_series = df_daily['收盘价'].rolling(50).mean()
    ma200_series = df_daily['收盘价'].rolling(200).mean()
    ax1.plot(dates, ma50_series, label='MA50 生命周期线', color='#ff7f0e', ls='--', lw=1.2, alpha=0.8)
    ax1.plot(dates, ma200_series, label='MA200 长期牛熊线', color='#2ca02c', ls='-.', lw=1.2, alpha=0.8)

    # 标记买卖点
    sells = df_daily[df_daily['当日操作'] == 'SELL']
    buys = df_daily[df_daily['当日操作'] == 'BUY']
    ax1.scatter(pd.to_datetime(sells['日期']), sells['收盘价'], marker='v', color='#d62728', s=90, zorder=5, label='微观雷达泡沫/避险清仓 (SELL)')
    ax1.scatter(pd.to_datetime(buys['日期']), buys['收盘价'], marker='^', color='#2ca02c', s=90, zorder=5, label='估值出清/黄金坑接回 (BUY)')
    ax1.set_title(f"【Layer 1】{ticker} 软件板块价格决策与买卖点 (14.5年实证)", fontsize=13, fontweight='bold')
    ax1.set_ylabel("价格 (USD)", fontsize=11)
    ax1.grid(True, linestyle=':', alpha=0.5)
    ax1.legend(loc='upper left', framealpha=0.9)

    # Panel 2: 0~100 综合微观雷达分
    ax2 = axes[1]
    ax2.set_facecolor('#fcfcfc')
    radar_vals = df_daily['复合雷达总分']
    ax2.plot(dates, radar_vals, color='#9467bd', lw=1.8, label='微观综合雷达分 (0~100)')
    ax2.axhline(60, color='#d62728', ls='--', lw=1.2, alpha=0.8, label='过热预警线 (60分)')
    ax2.axhline(35, color='#2ca02c', ls='--', lw=1.2, alpha=0.8, label='估值出清买回线 (35分)')
    ax2.axhline(20, color='#17becf', ls=':', lw=1.2, alpha=0.8, label='极限黄金坑 (20分)')
    ax2.fill_between(dates, 60, radar_vals, where=(radar_vals >= 60), color='#d62728', alpha=0.25, label='极度泡沫危险区')
    ax2.fill_between(dates, 0, radar_vals, where=(radar_vals <= 20), color='#17becf', alpha=0.25, label='极限出清超跌区')
    ax2.set_ylim(-5, 105)
    ax2.set_title("【Layer 2】0~100 综合微观雷达分与四色阈值区间", fontsize=13, fontweight='bold')
    ax2.set_ylabel("雷达评分 (0-100)", fontsize=11)
    ax2.grid(True, linestyle=':', alpha=0.5)
    ax2.legend(loc='upper left', framealpha=0.9)

    # Panel 3: 内部成分股 50MA 广度与背离
    ax3 = axes[2]
    ax3.set_facecolor('#fcfcfc')
    breadth_pct = df_daily['成分股50MA广度'] * 100.0
    ax3.plot(dates, breadth_pct, color='#8c564b', lw=1.5, label='前15大成分股站上50MA比例 (%)')
    ax3.axhline(50, color='#e377c2', ls='--', lw=1.2, label='多空平衡中枢线 (50%)')
    ax3.fill_between(dates, 0, breadth_pct, where=(breadth_pct < 45), color='#d62728', alpha=0.2, label='微观广度严重坍塌区 (<45%)')
    ax3.set_ylim(-5, 105)
    ax3.set_title("【Layer 3】内部 15 大核心成分股 50MA 广度演变", fontsize=13, fontweight='bold')
    ax3.set_ylabel("站上50MA比例 (%)", fontsize=11)
    ax3.grid(True, linestyle=':', alpha=0.5)
    ax3.legend(loc='upper left', framealpha=0.9)

    # Panel 4: 真实券商净值对比与 4 独立分项
    ax4 = axes[3]
    ax4.set_facecolor('#fcfcfc')
    ax4.plot(dates, df_daily['策略净值'], label=f"策略终值: USD {metrics['s_fin']:,.0f} (+{metrics['s_ret']:.1f}%)", color='#d62728', lw=2.2)
    ax4.plot(dates, df_daily['基准净值'], label=f"基准终值: USD {metrics['b_fin']:,.0f} (+{metrics['b_ret']:.1f}%)", color='#7f7f7f', lw=1.5, ls='--')
    ax4.set_title(f"【Layer 4】真实券商账户财富累积对比 (Alpha: {metrics['alpha']:+.2f}%, 最大回撤: {metrics['s_dd']:.1f}% vs {metrics['b_dd']:.1f}%)", fontsize=13, fontweight='bold')
    ax4.set_ylabel("资产净值 (USD)", fontsize=11)
    ax4.set_xlabel("交易日期", fontsize=11)
    ax4.grid(True, linestyle=':', alpha=0.5)
    ax4.legend(loc='upper left', framealpha=0.9)

    plt.tight_layout()
    plt.savefig(plot_path, dpi=200)
    plt.close()
    print(f"✅ 图谱保存成功: {plot_path}")


if __name__ == '__main__':
    radar = MicroBubbleRadar()
    print("🚀 正在加载本地数据并运算 4 维度微观雷达分...")
    df = radar.load_and_preprocess()
    df = radar.compute_all_dimensions()

    print("⚡ 正在执行真实券商记账回测...")
    metrics, df_paired, df_daily = run_brokerage_backtest(df, ticker='IGV')

    print("📦 正在导出交付物...")
    export_deliverables(df, metrics, df_paired, df_daily, ticker='IGV')
    print("🎉 全部本地开发与交付物生成已顺利完成！")
