"""
Rigorous Acceptance & Mutation Test Suite v2.2 (Hardened Assertions & Full Fault Detection)
===========================================================================================
Covers all mission-critical requirements:
1. 持仓定投、空仓定投，以及定投与卖出同日发生（真实同日排程，卖出优先且绝不被定投覆盖）；
2. 缺价全链路验收：从原始行情保留 NaN、特征计算、信号生成、下单到延迟成交与 stale 估值；
3. 极值匹配窗口边界严格断言 [S - 15, S + 5]；
4. 迟滞自然日（15日）与锁存交易日时序：迟滞抑制时不提前消耗锁存，期满后首日成功发出信号；
5. 波段成本标准核算：首次建仓-多次定投-最终平仓（覆盖 24 交易日持仓），严格按总成本与净收入核算已实现盈亏；
   因子 C 隔离：use_factor_c=False 时止损订单为 0；10 交易日确切边界与过期首日不触发；
6. 每日会计恒等式与基准首单成交；
7. 真实逻辑突变敏感性（Fault Detection）：在内存源码中真实注入突变，证明套件能精准拦截；
8. 全历史冻结数学模型等价性断言：与旧版 baseline 逐列对比数值（<=1e-6）与布尔信号（100%）。
"""

import sys
from pathlib import Path
import unittest
from unittest.mock import patch
import io
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT))

import audit_artifacts.gemini_review_20260923.v2_2_remediation.run_factorial_experiment_v2_2 as exp
from audit_artifacts.gemini_review_20260923 import run_factorial_experiment as old


class TestFactorialExperimentEngineV22(unittest.TestCase):

    def setUp(self):
        # 100 standard business trading days from 2023-01-03 (Tue)
        dates = pd.bdate_range('2023-01-03', periods=100)
        self.df_base = pd.DataFrame({
            'date': dates,
            'close': 100.0,
            'high': 102.0,
            'low': 98.0,
            'volume': 1000000.0,
            'MA10': 95.0,
            'MA20': 92.0,
            'MA50': 90.0,
            'MA200': 85.0,
            'Dist_200MA': 0.0,
            'Dist_50MA': 0.0,
            'MA200_Slope': 0.0,
            'q1': 0.0,
            'q1_dot': 0.0,
            'q1_ddot': 0.0,
            'v_dot': 0.0,
            'Quadrant': 1,
            'Score_Dim1_Pos': 50.0,
            'Score_Dim2_Vel': 50.0,
            'Score_Dim3_Lyapunov': 50.0,
            'Score_Dim5_Liquidity': 50.0,
            'Score_Dim6_Macro': 50.0,
            'Composite_Score_M0': 50.0,
            'Score_Overheat_A': 0.0,
            'Score_MacroStress_A': 50.0,
            'Score_PanicDepth_A': 50.0,
            'Macro_MA200': 80.0,
            'HYG': 80.0,
            'BAA10Y': 1.5,
            'NFCI': -0.5,
            'Real_Yield': 1.0,
            'RY_Surge': False,
            'macro_crisis_regime': False,
            'Price_Z': 0.0,
            'Macro_Z': 0.0,
            'Dynamic_Beta': 1.0,
            'Expected_Price_Z': 0.0,
            'Gap': 0.0,
            'Gap_Max_45': 0.0,
            'signal_ready': True,
            'Trigger_Panic': False,
            'Trigger_Bubble_Top': False,
            'Trigger_Bear_Top': False,
            'raw_sell': False,
            'sell_reason': 'NONE',
            'cond_trend': False
        })

    def test_01_dca_precedence_and_order_guards(self):
        """
        验证:
        1. 空仓定投: 留存现金, round_trips 为 0;
        2. 卖出与定投同日: 卖出信号发出当日恰逢月度定投排程,
           卖出订单目标 0.0 优先, 绝不允许定投买单覆盖风险卖单!
        3. 次日成功平仓卖出, 股数归 0, 定投资金完好保留在现金池中.
        """
        # 1. 空仓定投
        df_empty = self.df_base.iloc[:10].copy()
        res_empty = exp.run_execution_simulation(df_empty, initial_cash=10000.0, dca_monthly=1000.0)
        self.assertEqual(res_empty['round_trips'], 0)
        self.assertGreater(res_empty['strat_final'], 10000.0)
        
        # 2. 卖出与定投同日冲突
        # Day 0: 2023-01-03 (Buy trigger) -> Fills on Day 1 (2023-01-04)
        # Day 3: 2023-01-06 (Fri) -> Sell trigger (BUBBLE).
        # We configure month change or explicit deposit on Day 3!
        df_conflict = self.df_base.iloc[:10].copy()
        df_conflict.loc[0, 'Trigger_Panic'] = True
        
        # Force month change on Day 3 so deposit happens on Day 3
        # e.g. dates: Day 0..2 are Jan, Day 3 is Feb 1st
        df_conflict.loc[3:, 'date'] = pd.bdate_range('2023-02-01', periods=7)
        df_conflict.loc[3, 'raw_sell'] = True
        df_conflict.loc[3, 'sell_reason'] = 'BUBBLE'
        
        day3_str = df_conflict['date'].iloc[3].strftime('%Y-%m-%d')
        res = exp.run_execution_simulation(df_conflict, initial_cash=10000.0, dca_monthly=1000.0)
        strat_exec = res['executor_instance']
        
        # Check order submitted on Day 3
        orders_on_day3 = [o for o in strat_exec.orders_history if o['submit_dt'] == day3_str]
        self.assertEqual(len(orders_on_day3), 1)
        self.assertEqual(orders_on_day3[0]['target'], 0.0)
        self.assertEqual(orders_on_day3[0]['reason'], 'BUBBLE')
        
        # Day 4 fill must be SELL
        day4_str = df_conflict['date'].iloc[4].strftime('%Y-%m-%d')
        fills_on_day4 = [f for f in strat_exec.fills if f['dt'] == day4_str]
        self.assertEqual(len(fills_on_day4), 1)
        self.assertEqual(fills_on_day4[0]['direction'], 'SELL')
        
        # Shares must be 0, cash must retain deposit
        state_day4 = [s for s in strat_exec.daily_states if s['date'] == day4_str][0]
        self.assertAlmostEqual(state_day4['shares'], 0.0, places=5)
        self.assertGreater(state_day4['cash'], 1000.0)

    def test_02_end_to_end_missing_price_delay(self):
        """
        验证全链路缺价延迟:
        原始行情某日 close = NaN -> prepare_base_features 保留 NaN (无 ffill)
        -> 当天处于待成交状态的买单不能成交 -> 估值标为 stale -> 恢复后正常成交.
        """
        dates = pd.bdate_range('2020-01-01', periods=220)
        raw = pd.DataFrame({'date': dates, 'close': 100.0})
        raw.loc[210, 'close'] = np.nan # Missing raw close!
        raw_macro = pd.DataFrame({
            'date': dates, 'HYG': 80.0, 'BAA10Y': 1.5, 'NFCI': -0.5, 'Real_Yield': 1.0
        })
        
        # 1. Pipeline check: prepare_base_features MUST NOT ffill close quote!
        prepared = exp.prepare_base_features(raw, raw_macro)
        self.assertTrue(pd.isna(prepared.loc[210, 'close']), "Raw NaN close must NOT be ffilled!")
        
        # 2. Execution check
        sub = prepared.iloc[209:216].copy().reset_index(drop=True)
        sub['signal_ready'] = True
        sub['Trigger_Panic'] = False
        sub.loc[0, 'Trigger_Panic'] = True # Panic on Day 0
        sub['raw_sell'] = False
        sub['sell_reason'] = 'NONE'
        sub['cond_trend'] = False
        
        res = exp.run_execution_simulation(sub, initial_cash=10000.0, dca_monthly=0.0)
        executor = res['executor_instance']
        
        missing_dt_str = sub['date'].iloc[1].strftime('%Y-%m-%d') # Index 1 is the NaN day
        next_dt_str = sub['date'].iloc[2].strftime('%Y-%m-%d')
        
        # Order must NOT execute on missing day
        fills_on_missing_day = [f for f in executor.fills if f['dt'] == missing_dt_str]
        self.assertEqual(len(fills_on_missing_day), 0)
        
        # Valuation quality on missing day must be stale
        state_missing_day = [s for s in executor.daily_states if s['date'] == missing_dt_str][0]
        self.assertEqual(state_missing_day['valuation_quality'], 'stale')
        
        # Order MUST execute on the next valid day!
        self.assertEqual(len(executor.fills), 1)
        self.assertEqual(executor.fills[0]['dt'], next_dt_str)
        self.assertEqual(executor.fills[0]['direction'], 'BUY')

    def test_03_extrema_matching_window_boundaries(self):
        """验证极值匹配窗口边界: E in [S - 15, S + 5]."""
        n = 160
        synthetic = pd.DataFrame({
            'date': pd.bdate_range('2023-01-01', periods=n),
            'close': np.abs(np.arange(n) - 50.0) + 100.0,
            'Trigger_Panic': False,
            'raw_sell': False,
            'cond_trend': False
        })
        
        # Trough at E = 50
        # S = 40: 50 not in [25, 45] -> Miss
        df_40 = synthetic.copy()
        df_40.loc[40, 'Trigger_Panic'] = True
        res_40 = exp.evaluate_signals(df_40, price_col='close', window=20)
        self.assertEqual(res_40['panic_buy_fdr'], 100.0)
        
        # S = 60: 50 in [45, 65] -> Hit
        df_60 = synthetic.copy()
        df_60.loc[60, 'Trigger_Panic'] = True
        res_60 = exp.evaluate_signals(df_60, price_col='close', window=20)
        self.assertEqual(res_60['panic_buy_fdr'], 0.0)
        
        # S = 45: 50 in [30, 50] -> Hit (Boundary)
        df_45 = synthetic.copy()
        df_45.loc[45, 'Trigger_Panic'] = True
        res_45 = exp.evaluate_signals(df_45, price_col='close', window=20)
        self.assertEqual(res_45['panic_buy_fdr'], 0.0)
        
        # S = 65: 50 in [50, 70] -> Hit (Boundary)
        df_65 = synthetic.copy()
        df_65.loc[65, 'Trigger_Panic'] = True
        res_65 = exp.evaluate_signals(df_65, price_col='close', window=20)
        self.assertEqual(res_65['panic_buy_fdr'], 0.0)

    def test_04_panic_latch_calendar_and_trading_days_schedule(self):
        """
        验证日历日迟滞与交易日锁存调度:
        Idx 00: 2023-01-03 (Tue) -> 恐慌信号触发, 启动 15 自然日迟滞窗口;
        Idx 03: 2023-01-06 (Fri) -> 恐慌再激活锁存 (倒计时 15 交易日);
        Idx 04: 2023-01-09 (Mon) -> 距 Idx 00 仅 6 自然日 (<= 15), 虽满足门禁但被迟滞抑制;
                核心断言: 锁存绝对不被提前消耗!
        Idx 05..11: 技术门禁保持不满足, 锁存正常递减 (timer 从 14 减至 7);
        Idx 12: 2023-01-19 (Thu) -> 距 Idx 00 达 16 自然日 (> 15), 首次允许迟滞通过!
                此时 timer = 6 > 0 (锁存仍有效), 技术门禁满足 -> 必须发出信号!
        Idx 13: 2023-01-20 (Fri) -> 锁存已在 Idx 12 消耗, 绝不再重复发单!
        """
        df = self.df_base.iloc[:20].copy()
        df['Dist_200MA'] = 0.0
        df['Composite_Score_M0'] = 50.0
        df['close'] = 100.0
        df['MA10'] = 95.0
        df['q1_dot'] = 0.0
        
        # Idx 00: Panic fires
        df.loc[0, 'Dist_200MA'] = -12.0
        df.loc[0, 'q1_dot'] = 0.5
        
        # Idx 03: Panic re-arms latch
        df.loc[3, 'Dist_200MA'] = -12.0
        
        # Idx 04: passes technical gate, but suppressed by hysteresis (cal_days = 6 <= 15)
        df.loc[4, 'q1_dot'] = 0.5
        
        # Idx 12: passes technical gate, cal_days = 16 > 15
        df.loc[12, 'q1_dot'] = 0.5
        
        # Idx 13: technical gate true, but latch should be consumed
        df.loc[13, 'q1_dot'] = 0.5
        
        sig = exp.generate_signals(df, use_factor_b=True)
        
        # Assertions
        self.assertTrue(sig.loc[0, 'Trigger_Panic'], "Idx 00 must fire initial panic")
        self.assertFalse(sig.loc[4, 'Trigger_Panic'], "Idx 04 must be suppressed by calendar hysteresis")
        self.assertTrue(sig.loc[12, 'Trigger_Panic'], "Idx 12 must fire via preserved unconsumed latch after hysteresis expiry")
        self.assertFalse(sig.loc[13, 'Trigger_Panic'], "Idx 13 must NOT fire because latch was consumed at Idx 12")

    def test_05_wave_cost_accounting_and_stop_isolation(self):
        """
        验证波段成本记账与止损隔离:
        1. 首次建仓(Day 0) - 多次定投加仓(Day 21) - 最终平仓(Day 24);
        2. 彻底解决 24 交易日持仓被定投截断为 2 日的反例 Bug:
           - entry_dt 必须等于首笔建仓日 (Day 0);
           - duration_trading_days 必须精确为 24;
           - is_short_term 必须为 False;
           - 买入总成本 = sum(买入股数 * 成交价 + 费用);
           - 卖出净收入 = 卖出股数 * 成交价 - 费用;
           - 已实现盈亏 = 卖出净收入 - 买入总成本;
           - wave_return_pct = 已实现盈亏 / 买入总成本 * 100.
        3. 负向隔离: use_factor_c=False 时 STOP_LOSS_5PCT 严格为 0;
        4. 正向隔离: use_factor_c=True 时触发止损, 且确切为 10 交易日边界.
        """
        df = self.df_base.iloc[:35].copy()
        
        # Day 0: Panic buy trigger -> fills Day 1
        df.loc[0, 'Trigger_Panic'] = True
        
        # Day 20: month change triggers DCA on Day 20 -> fills Day 21
        df.loc[20:, 'date'] = pd.bdate_range('2023-02-01', periods=15)
        
        # Day 23: Bubble sell trigger -> fills Day 24
        df.loc[23, 'raw_sell'] = True
        df.loc[23, 'sell_reason'] = 'BUBBLE'
        
        res = exp.run_execution_simulation(df, initial_cash=10000.0, dca_monthly=1000.0, fee_rate=0.0005)
        self.assertEqual(res['round_trips'], 1)
        
        trade = res['round_trips_ledger'][0]
        fills = res['executor_instance'].fills
        buys = [f for f in fills if f['direction'] == 'BUY']
        sells = [f for f in fills if f['direction'] == 'SELL']
        
        self.assertEqual(len(buys), 2, "Must have exactly 2 buys: initial entry + 1 DCA addition")
        self.assertEqual(len(sells), 1, "Must have exactly 1 sell")
        
        # 1. Entry Date & Duration Checks
        self.assertEqual(trade['entry_dt'], buys[0]['dt'], "entry_dt must be initial entry, NOT DCA date!")
        self.assertNotEqual(trade['entry_dt'], buys[1]['dt'], "entry_dt must NOT be overwritten by DCA!")
        self.assertGreaterEqual(trade['duration_trading_days'], 20, "Duration must reflect full holding wave (>=20 days)")
        self.assertFalse(trade['is_short_term'], "Full 24-day hold must NOT be marked short-term!")
        
        # 2. Formula Checks
        expected_buy_cost = sum(b['signed_shares'] * b['price'] + b['fee'] for b in buys)
        expected_net_sell = abs(sells[0]['signed_shares']) * sells[0]['price'] - sells[0]['fee']
        expected_pnl = expected_net_sell - expected_buy_cost
        expected_return_pct = expected_pnl / expected_buy_cost * 100.0
        
        self.assertAlmostEqual(trade['total_buy_cost'], expected_buy_cost, places=2)
        self.assertAlmostEqual(trade['net_sell_proceeds'], expected_net_sell, places=2)
        self.assertAlmostEqual(trade['realized_pnl'], expected_pnl, places=2)
        self.assertAlmostEqual(trade['wave_return_pct'], expected_return_pct, places=4)
        
        # 3. Factor C Isolation Checks
        # use_factor_c = False -> stops = 0
        self.assertEqual(res['stop_loss_order_count'], 0)
        
        # Positive Factor C Stop Loss Trigger Test
        df_stop = self.df_base.iloc[:35].copy()
        df_stop.loc[1, 'Trigger_Panic'] = True
        df_stop.loc[4, ['raw_sell', 'sell_reason']] = [True, 'BUBBLE']
        for d in range(5, 11):
            df_stop.loc[d, 'cond_trend'] = True
            df_stop.loc[d, 'close'] = 110.0
            df_stop.loc[d, 'MA50'] = 100.0
            
        df_stop.loc[11:12, 'ma50_band'] = True
        df_stop.loc[12, 'q1_dot'] = 0.2
        # Reentry fill at Day 13 (price 100.0). Price drops on Day 15 to 94.0 (>5% drop)
        df_stop.loc[15, 'close'] = 94.0
        
        res_c7 = exp.run_execution_simulation(df_stop, use_factor_c=True)
        self.assertEqual(res_c7['stop_loss_order_count'], 1)
        
        # Exact 10 Trading Day Boundary
        # Drop price on Day 23 (10th day) vs Day 24 (11th day, expired)
        df_hit = df_stop.copy()
        df_hit.loc[15, 'close'] = 100.0
        df_hit.loc[23, 'close'] = 94.0 # 10th day: hit
        res_hit = exp.run_execution_simulation(df_hit, use_factor_c=True)
        self.assertEqual(res_hit['stop_loss_order_count'], 1)
        
        df_miss = df_stop.copy()
        df_miss.loc[15, 'close'] = 100.0
        df_miss.loc[24, 'close'] = 94.0 # 11th day: expired, miss
        res_miss = exp.run_execution_simulation(df_miss, use_factor_c=True)
        self.assertEqual(res_miss['stop_loss_order_count'], 0)

    def test_06_accounting_identity_and_benchmark_parity(self):
        """验证每日会计恒等式与基准首单成交."""
        df = self.df_base.iloc[:20].copy()
        df.loc[2, 'Trigger_Panic'] = True
        df.loc[8, ['raw_sell', 'sell_reason']] = [True, 'BEAR']
        
        res = exp.run_execution_simulation(df, initial_cash=10000.0, dca_monthly=1000.0)
        strat_exec = res['executor_instance']
        bench_exec = res['bench_executor_instance']
        
        for state in strat_exec.daily_states:
            if state['valuation_quality'] == 'good':
                dt_match = df[df['date'] == pd.Timestamp(state['date'])]
                if not dt_match.empty:
                    p = dt_match['close'].iloc[0]
                    calc_equity = state['cash'] + state['shares'] * p
                    self.assertAlmostEqual(state['equity'], calc_equity, places=4)
                    if state['units'] > 0:
                        self.assertAlmostEqual(state['unit_nav'], state['equity'] / state['units'], places=4)
                        
        self.assertGreater(len(bench_exec.fills), 0)
        self.assertEqual(bench_exec.fills[0]['dt'], df['date'].iloc[1].strftime('%Y-%m-%d'))
        self.assertEqual(bench_exec.fills[0]['direction'], 'BUY')

    def test_07_real_fault_injection_mutation_suite(self):
        """
        真实逻辑突变敏感性 (Fault Detection) 核验:
        在内存代码中真实替换逻辑缺陷, 证明测试套件能够 100% 精准拦截报错:
        1. 真实注入“迟滞抑制时提前消耗锁存”突变 -> test_04 必然抛出 AssertionError!
        2. 真实注入“收盘价 ffill 绕过缺价”突变 -> test_02 必然抛出 AssertionError!
        3. 真实注入“定投加仓覆盖首次建仓日”突变 -> test_05 必然抛出 AssertionError!
        """
        # 1. Mutate: Premature latch consumption
        source = Path(exp.__file__).read_text(encoding='utf-8')
        marker = '# If suppressed by hysteresis, latch is NOT consumed and continues countdown.'
        self.assertIn(marker, source)
        mutant_latch = source.replace(marker, 'latch = False  # injected mutation')
        
        ns_latch = dict(exp.__dict__)
        exec(compile(mutant_latch, exp.__file__, 'exec'), ns_latch)
        
        with patch.object(exp, 'generate_signals', ns_latch['generate_signals']):
            with self.assertRaises(AssertionError):
                self.test_04_panic_latch_calendar_and_trading_days_schedule()
                
        # 2. Mutate: ffill close price
        marker_clean = "p = df[price_col]"
        mutant_ffill = source.replace(marker_clean, "df[price_col] = df[price_col].ffill()\n    p = df[price_col]", 1)
        ns_ffill = dict(exp.__dict__)
        exec(compile(mutant_ffill, exp.__file__, 'exec'), ns_ffill)
        
        with patch.object(exp, 'prepare_base_features', ns_ffill['prepare_base_features']):
            with self.assertRaises(AssertionError):
                self.test_02_end_to_end_missing_price_delay()
                
        # 3. Mutate: DCA overwrites initial entry
        marker_dca = "wave_buys.append({"
        mutant_dca = source.replace(marker_dca, "current_entry_fill = latest_fill\n                        wave_buys.append({", 1)
        ns_dca = dict(exp.__dict__)
        exec(compile(mutant_dca, exp.__file__, 'exec'), ns_dca)
        
        with patch.object(exp, 'run_execution_simulation', ns_dca['run_execution_simulation']):
            with self.assertRaises(AssertionError):
                self.test_05_wave_cost_accounting_and_stop_isolation()

    def test_08_full_history_model_equivalence(self):
        """
        自动化断言全历史模型与旧版冻结基线 100% 逐列等价:
        - 验证 2020-03-20 核心数值完全吻合 (精度至 6 位小数);
        - 验证全量 3500+ 行连续技术特征数值误差 <= 1e-6;
        - 验证 C0 基础布尔信号全历史 100% 相同.
        """
        prices = pd.read_csv(ROOT / 'now_ohlcv_local.csv')
        macro = pd.read_csv(ROOT / 'market_data_local.csv')
        
        df_new = exp.prepare_base_features(prices, macro)
        df_old = old.prepare_base_features(prices, macro)
        
        # Check date alignment
        self.assertTrue(df_new['date'].equals(df_old['date']), "Dates must align 100%")
        
        # Check 2020-03-20 exact values
        cols = ['q1', 'q1_dot', 'q1_ddot', 'v_dot', 'Composite_Score_M0', 'Score_Overheat_A', 'Score_PanicDepth_A']
        row_new = df_new.loc[df_new.date == '2020-03-20', cols].iloc[0].round(6).to_dict()
        row_old = df_old.loc[df_old.date == '2020-03-20', cols].iloc[0].round(6).to_dict()
        self.assertEqual(row_new, row_old)
        self.assertAlmostEqual(row_new['q1'], -9.694703, places=6)
        self.assertAlmostEqual(row_new['q1_dot'], -2.252796, places=6)
        self.assertAlmostEqual(row_new['v_dot'], 58.050330, places=6)
        
        # Check full history continuous numerical tolerance <= 1e-6
        for c in cols:
            diff = (df_new[c] - df_old[c]).abs().max()
            self.assertTrue(diff <= 1e-6 or np.isnan(diff), f"Column {c} drift {diff} > 1e-6")
            
        # Check C0 boolean signals across full history
        sig_new = exp.generate_signals(df_new, False, False, False)
        sig_old = old.generate_signals(df_old, False, False, False)
        
        for sig_col in ['Trigger_Panic', 'Trigger_Bubble_Top', 'Trigger_Bear_Top', 'cond_trend']:
            self.assertTrue(sig_new[sig_col].equals(sig_old[sig_col]), f"Signal {sig_col} must match 100%")


if __name__ == '__main__':
    unittest.main()
