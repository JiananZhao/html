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


def generate_trade_pairs(orders, sub_bt, ticker):
    """从 SharedExecutor 的 orders_history 中提取买卖配对"""
    trade_pairs = []
    discretionary = [o for o in orders if o.get('reason') not in ("Standing Order / DCA", "Bench Standing Order / DCA")]
    
    for k in range(0, len(discretionary) - 1, 2):
        s_o = discretionary[k]
        b_o = discretionary[k+1]
        
        if s_o['target'] == 0.0 and b_o['target'] == 1.0:
            s_dt = pd.to_datetime(s_o['actual_dt'] if s_o['actual_dt'] else s_o['submit_dt'])
            b_dt = pd.to_datetime(b_o['actual_dt'] if b_o['actual_dt'] else b_o['submit_dt'])
            
            s_p = sub_bt.loc[sub_bt['date'] == s_dt.strftime('%Y-%m-%d'), ticker].values
            b_p = sub_bt.loc[sub_bt['date'] == b_dt.strftime('%Y-%m-%d'), ticker].values
            
            s_p = s_p[0] if len(s_p) > 0 else 0
            b_p = b_p[0] if len(b_p) > 0 else 0
            
            if s_p > 0:
                p_drop = (b_p - s_p) / s_p * 100.0
            else:
                p_drop = 0.0
            
            trade_pairs.append({
                '轮次': len(trade_pairs) + 1,
                '卖出日期': s_dt.strftime('%Y-%m-%d'),
                '卖出价格': round(s_p, 2),
                '卖出诱因': s_o['reason'],
                '买入日期': b_dt.strftime('%Y-%m-%d'),
                '买入价格': round(b_p, 2),
                '买回诱因': b_o['reason'],
                '期间绝对跌幅': f"{p_drop:+.2f}%",
                '波段是否有效避险': "✅ 有效" if p_drop < 0 else "❌ 踏空磨损"
            })
            
    return pd.DataFrame(trade_pairs)


def run_brokerage_backtest(df, ticker='XLE', start_date='2009-01-01', dca_monthly=1000.0, cost_config=0.0):
    """
    券商级真实记账回测引擎 (基于 SharedExecutor + UnitizedAccount)
    保留能源专属策略逻辑：OIL/DXY 宏观锚、CapEx 剪刀差、油价成本线判定
    """
    from true_accounting import UnitizedAccount, calculate_xirr
    from shared_executor import SharedExecutor
    from core_engine.simulation_result import SimulationResult

    sub_bt = df[df['date'] >= start_date].copy().reset_index(drop=True)
    if sub_bt.empty:
        return SimulationResult(pd.DataFrame(), pd.DataFrame(), [], [], [], pd.DataFrame(), {}, {})

    # 预计算 OIL 的 200 日均线 (策略买回条件需要)
    sub_bt['OIL_MA200'] = sub_bt['OIL'].rolling(200, min_periods=1).mean()

    initial_dt = pd.to_datetime(sub_bt['date'].iloc[0])
    acc = UnitizedAccount(initial_cash=0.0, initial_date=initial_dt)
    bench_acc = UnitizedAccount(initial_cash=0.0, initial_date=initial_dt)

    executor = SharedExecutor(acc, fee_rate=cost_config, execution_mode='NEXT_CLOSE', account_type='strat')
    bench_executor = SharedExecutor(bench_acc, fee_rate=0.0, execution_mode='NEXT_CLOSE', account_type='bench')

    curr_m = -1
    exit_reg = None
    pos = 1.0
    total_invested = 0.0

    bench_eqs = []
    strat_eqs = []
    positions = []

    df_len = len(sub_bt)

    for i in range(df_len):
        d_str = sub_bt['date'].iloc[i]
        p = sub_bt[ticker].iloc[i]

        try:
            dt = pd.Timestamp(d_str)
        except:
            dt = pd.to_datetime(d_str)

        m = dt.month
        score = sub_bt['Composite_Radar_Score'].iloc[i]

        # 定投
        dca_amount = 0.0
        if m != curr_m:
            curr_m = m
            dca_amount = dca_monthly
            total_invested += dca_monthly

        executor.step(dt, p, p, dca_amount=dca_amount)
        bench_executor.step(dt, p, p, dca_amount=dca_amount)

        # T 日收盘后产生新信号
        if i < df_len - 1:
            is_bub = sub_bt['Cond_Bubble'].iloc[i]
            is_bear = sub_bt['Cond_Bear'].iloc[i]

            if pos > 0 and (is_bub or is_bear):
                exit_reg = 'BUBBLE' if is_bub else 'BEAR'
                pending_reason = '微观雷达泡沫与CapEx过热' if is_bub else '油价击穿成本线与宏观熊市'
                pos = 0.0
                executor.submit_order(pos, pending_reason, dt)
            elif pos == 0.0:
                can_buy = False
                b_reason = ""

                # 1. 极端出清黄金坑抄底
                if sub_bt['Cond_Panic'].iloc[i]:
                    can_buy = True
                    b_reason = '极端出清黄金坑抄底'
                # 2. 突破卖出价右侧防踏空接回
                elif executor.last_sell_p and (p > executor.last_sell_p * 1.02) and sub_bt['Above_MA20_Conf'].iloc[i] and sub_bt['Above_MA50_Conf'].iloc[i]:
                    can_buy = True
                    b_reason = '突破卖出价右侧防踏空接回'
                # 3. 体制分化精准重构
                elif sub_bt['Above_MA20_Conf'].iloc[i] and sub_bt['Above_MA50_Conf'].iloc[i]:
                    if exit_reg == 'BUBBLE':
                        radar_cooled = score < 45.0
                        if radar_cooled:
                            can_buy = True
                            b_reason = '微观雷达降温且右侧重构'
                    elif exit_reg == 'BEAR':
                        oil_val = sub_bt['OIL'].iloc[i]
                        oil_ma = sub_bt['OIL_MA200'].iloc[i]
                        if (oil_val >= 60.0) or (oil_val > oil_ma):
                            can_buy = True
                            b_reason = '油价企稳成本线且趋势重构'

                if can_buy:
                    pos = 1.0
                    executor.submit_order(pos, b_reason, dt)
            else:
                executor.submit_order(pos, "Standing Order / DCA", dt)
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

    final_date = pd.Timestamp(sub_bt['date'].iloc[-1])
    b_cagr = calculate_xirr([(pd.Timestamp(d), a) for d, a in bench_executor.acc.cash_flows], b_final, final_date) * 100.0
    s_cagr = calculate_xirr([(pd.Timestamp(d), a) for d, a in executor.acc.cash_flows], s_final, final_date) * 100.0

    alpha = s_cagr - b_cagr

    b_dd = (daily_accounts[daily_accounts['type'] == 'bench']['unit_nav'] / daily_accounts[daily_accounts['type'] == 'bench']['unit_nav'].cummax() - 1).min() * 100.0
    s_dd = (daily_accounts[daily_accounts['type'] == 'strat']['unit_nav'] / daily_accounts[daily_accounts['type'] == 'strat']['unit_nav'].cummax() - 1).min() * 100.0

    trade_pairs_df = generate_trade_pairs(executor.orders_history, sub_bt, ticker)

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


def export_deliverables(result):
    sub_bt = result.features
    df_daily = result.daily_accounts
    metrics = result.metrics
    ticker = result.metadata.get('ticker', 'XLE')
    df_pairs = generate_trade_pairs(result.orders, sub_bt, ticker)
    """
    导出机构级 Excel 审计全底稿与高清 4 层对齐图谱
    """
    excel_path = '宏观反身性阿尔法模型_Energy微观雷达全周期对账表.xlsx'
    with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
        df_overview = pd.DataFrame([{
            '标的资产': ticker,
            '资产名称': '能源全产业链综合基准',
            '定投总本金 (USD)': metrics.get('total_invested', 0),
            '买入持有 (B&H) 终值 (USD)': metrics.get('bench_final', 0),
            '买入持有累计回报率': f"{metrics.get('bench_return', 0):.2f}%",
            '买入持有最大回撤': f"{metrics.get('bench_max_dd', 0):.2f}%",
            '微观雷达策略终值 (USD)': metrics.get('strat_final', 0),
            '微观雷达策略总回报率': f"{metrics.get('strat_return', 0):.2f}%",
            '策略最大回撤': f"{metrics.get('strat_max_dd', 0):.2f}%",
            '超额回报率 (Alpha)': f"{metrics.get('alpha', 0):+.2f}%",
            '净多赚现金财富 (USD)': metrics.get('strat_final', 0) - metrics.get('bench_final', 0),
            '回撤改善幅度': f"{metrics.get('strat_max_dd', 0) - metrics.get('bench_max_dd', 0):+.2f}%",
            '全周期调仓轮次': metrics.get('trade_rounds', 0),
            '波段操作胜率': f"{metrics.get('win_rate', 0):.1f}%"
        }])
        df_overview.to_excel(writer, sheet_name='全周期业绩总表', index=False)
        df_pairs.to_excel(writer, sheet_name='逐笔买卖配对对账表', index=False)
        df_daily.to_excel(writer, sheet_name='逐日流水底稿表', index=False)
        df_pairs.to_csv(f'{ticker.lower()}_backtest_paired_local.csv', index=False)
        sub_bt.to_csv(f'{ticker.lower()}_backtest_daily_local.csv', index=False)
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
    ax4.plot(dates, sub_bt['Bench_Equity'], color='#7f8c8d', label=f'买入持有基准 (B&H 终值: USD {metrics.get("bench_final", 0):,.0f})', lw=1.5, ls='--')
    ax4.plot(dates, sub_bt['Strat_Equity'], color='#27ae60', label=f'微观雷达策略 (策略终值: USD {metrics.get("strat_final", 0):,.0f} | Alpha: {metrics.get("alpha", 0):+.1f}%)', lw=2.0)
    ax4.set_ylabel('账户资产净值 (USD)', fontsize=11)
    ax4.set_title(f'【Layer 4】真实券商记账资产增殖对比 (定投总本金 USD {metrics.get("total_invested", 0):,.0f} | 净多赚现金财富 USD {metrics.get("strat_final", 0) - metrics.get("bench_final", 0):,.0f})', fontsize=13, fontweight='bold')
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

    result = run_brokerage_backtest(radar.df, ticker='XLE', start_date='2009-01-01')
    sub_bt = result.features
    df_daily = result.daily_accounts
    metrics = result.metrics
    df_pairs = generate_trade_pairs(result.orders, sub_bt, 'XLE')

    print("\n==================================================")
    print("🎯 Energy 能源全产业链微观雷达全周期实证对账审计报告 (2009 - 2026)")
    print("==================================================")
    print(f"定投总本金: USD {metrics.get('total_invested', 0):,.2f}")
    print(f"买入持有基准终值: USD {metrics.get('bench_final', 0):,.2f} (+{metrics.get('bench_return', 0):.2f}%), 最大回撤: {metrics.get('bench_max_dd', 0):.2f}%")
    print(f"微观雷达策略终值: USD {metrics.get('strat_final', 0):,.2f} (+{metrics.get('strat_return', 0):.2f}%), 最大回撤: {metrics.get('strat_max_dd', 0):.2f}%")
    print(f"超额 Alpha: {metrics.get('alpha', 0):+.2f}% | 净多赚现金财富: USD {metrics.get('strat_final', 0) - metrics.get('bench_final', 0):,.2f}")
    print(f"最大回撤改善幅度: {metrics.get('strat_max_dd', 0) - metrics.get('bench_max_dd', 0):+.2f}%")
    print(f"全周期调仓: {metrics.get('trade_count', 0)} 笔 ({metrics.get('trade_rounds', 0)} 轮)")
    print(f"波段胜率 (有效低买高卖/防踏空): {metrics.get('win_rate', 0):.1f}%")
    print("==================================================\n")

    export_deliverables(result)
    print("🎉 Energy 微观雷达全套交付物本地生成完毕！")


if __name__ == '__main__':
    main()
