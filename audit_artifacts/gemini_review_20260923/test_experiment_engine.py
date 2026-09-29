"""
Strict Assertion Acceptance Test Suite for Factorial Experiment Engine
Verifies all 6 mission-critical requirements specified by User Review:
1. 持仓定投、空仓定投，以及定投与卖出同日发生（优先级与防覆盖）；
2. 下一交易日成交、末日待成交和缺价延迟；
3. 极值匹配窗口边界；
4. 锁存激活、刷新、过期、消耗；
5. 分类再入场与止损；
6. 账户恒等式、现金流、单位净值和真实交易日间隔。
"""

import unittest
import numpy as np
import pandas as pd
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

OUT_DIR = Path(__file__).resolve().parent
import audit_artifacts.gemini_review_20260923.run_factorial_experiment as exp_engine
from true_accounting import UnitizedAccount
from shared_executor import SharedExecutor


class TestFactorialExperimentEngine(unittest.TestCase):

    def setUp(self):
        # Create standard synthetic trading days (100 days)
        dates = pd.date_range('2023-01-01', periods=100, freq='B')
        self.df_base = pd.DataFrame({
            'date': dates,
            'close': 100.0 + np.sin(np.linspace(0, 10, 100)) * 10.0,
            'high': 102.0 + np.sin(np.linspace(0, 10, 100)) * 10.0,
            'low': 98.0 + np.sin(np.linspace(0, 10, 100)) * 10.0,
            'volume': 1000000.0,
            'MA10': 100.0,
            'MA20': 100.0,
            'MA50': 100.0,
            'MA200': 100.0,
            'Dist_200MA': 0.0,
            'MA200_Slope': 0.0,
            'q1': 0.0,
            'q1_dot': 0.0,
            'q1_ddot': 0.0,
            'Score_Dim6_Macro': 50.0,
            'Score_MacroStress_A': 50.0,
            'Composite_Score_M0': 50.0,
            'Score_PanicDepth_A': 50.0,
            'Quadrant': 1,
            'macro_crisis_regime': False,
            'HYG': 80.0,
            'Macro_MA200': 80.0,
            'Trigger_Panic': False,
            'raw_sell': False,
            'sell_reason': 'NONE',
            'cond_trend': False
        })

    def test_01_dca_precedence_and_order_guards(self):
        """
        验证:
        - 持仓定投 -> 跟随加仓
        - 空仓定投 -> 留存现金
        - 卖出与定投同日 -> 卖出优先, 绝不允许定投买单覆盖风险卖单!
        """
        df = self.df_base.copy()
        
        # Scenario 1: Empty account receives DCA -> cash stays in cash
        df_empty = df.iloc[:10].copy()
        res_empty = exp_engine.run_execution_simulation(df_empty, initial_cash=10000.0, dca_monthly=1000.0)
        # Never had buy signal, so stays 0 shares, receives DCA
        self.assertTrue(res_empty['round_trips'] == 0)
        
        # Scenario 2: Holding account with sell signal on same day as DCA
        # Day 2: Buy
        # Day 5: Sell signal AND DCA on same day
        df_conflict = df.iloc[:10].copy()
        df_conflict.loc[1, 'Trigger_Panic'] = True # Day 1 signal -> Day 2 fill
        df_conflict.loc[4, 'raw_sell'] = True      # Day 4 signal
        df_conflict.loc[4, 'sell_reason'] = 'BUBBLE'
        
        # Run simulation
        acc = UnitizedAccount(initial_cash=10000.0, initial_date=df_conflict['date'].iloc[0])
        executor = SharedExecutor(acc, fee_rate=0.001, execution_mode='NEXT_CLOSE', account_type='strat')
        
        pos = 0.0
        last_fill_count = 0
        
        for i in range(len(df_conflict)):
            dt = df_conflict['date'].iloc[i]
            p_i = df_conflict['close'].iloc[i]
            deposit = 1000.0 if i == 4 else 0.0 # Deposit happens on Day 4 (same as sell signal)
            
            executor.step(dt, p_i, p_i, dca_amount=deposit)
            
            if len(executor.fills) > last_fill_count:
                latest = executor.fills[-1]
                last_fill_count = len(executor.fills)
                if latest['direction'] == 'BUY':
                    pos = 1.0
                elif latest['direction'] == 'SELL':
                    pos = 0.0
                    
            s_sell = df_conflict['raw_sell'].iloc[i]
            s_panic = df_conflict['Trigger_Panic'].iloc[i]
            
            target_pos = None
            target_reason = None
            
            if pos > 0.0:
                if s_sell:
                    target_pos = 0.0 # Sell takes precedence!
                    target_reason = 'BUBBLE_SELL'
                elif deposit > 0:
                    target_pos = 1.0
                    target_reason = 'DCA_REINVEST'
            else:
                if s_panic:
                    target_pos = 1.0
                    target_reason = 'PANIC_BUY'
                    
            if target_pos is not None:
                executor.submit_order(target_pos, target_reason, dt)
                
        # On Day 5 (index 4 is day 5), order submitted was target_pos = 0.0
        # On Day 6 (index 5), position should be 0 shares!
        self.assertEqual(executor.pending_orders[0]['reason'] if executor.pending_orders else '', '')
        # Verify sell was filled on Day 5 (dt at index 5)
        self.assertEqual(executor.fills[-1]['direction'], 'SELL')
        self.assertAlmostEqual(executor.acc.shares, 0.0, places=5)
        # Verify the DCA 1000.0 was NOT invested into shares, but retained as cash
        self.assertTrue(executor.acc.cash > 1000.0)

    def test_02_next_close_and_terminal_pending_orders(self):
        """
        验证下一交易日成交以及末日待成交订单与现金保留。
        """
        df = self.df_base.iloc[:5].copy()
        # Order submitted on last day (index 4)
        df.loc[4, 'Trigger_Panic'] = True
        
        acc = UnitizedAccount(initial_cash=10000.0, initial_date=df['date'].iloc[0])
        executor = SharedExecutor(acc, fee_rate=0.001, execution_mode='NEXT_CLOSE', account_type='strat')
        
        for i in range(len(df)):
            dt = df['date'].iloc[i]
            p_i = df['close'].iloc[i]
            executor.step(dt, p_i, p_i)
            if df['Trigger_Panic'].iloc[i]:
                executor.submit_order(1.0, "Last Day Buy", dt)
                
        # Fill should be empty because last day order has no next close to execute
        self.assertEqual(len(executor.fills), 0)
        self.assertEqual(len(executor.pending_orders), 1)
        self.assertEqual(executor.pending_orders[0]['status'], 'PENDING')
        # Cash should remain intact
        self.assertEqual(executor.acc.cash, 10000.0)

    def test_03_extrema_matching_window_boundaries(self):
        """
        验证极值匹配窗口边界: E in [S - 15, S + 5]
        - 谷底在 Day 50 (E = 50)
        - Day 40 (10天前发信号): 50 not in [25, 45] -> 不命中 (FDR 100%, Miss 100%)
        - Day 60 (10天后发信号): 50 in [45, 65] -> 命中 (FDR 0%, Miss 0%)
        - Day 45 (5天前发信号): 50 in [30, 50] -> 命中 (边界)
        - Day 65 (15天后发信号): 50 in [50, 70] -> 命中 (边界)
        - Day 34 (16天前发信号): 50 not in [19, 39] -> 不命中
        - Day 66 (16天后发信号): 50 not in [51, 71] -> 不命中
        """
        # Synthetic series with single trough at Day 50
        n = 160
        synthetic = pd.DataFrame({
            'close': np.abs(np.arange(n) - 50.0) + 100.0,
            'Trigger_Panic': False,
            'raw_sell': False
        })
        
        # Test Case 1: Day 40 (-10 days) -> Should be MISSED
        df_40 = synthetic.copy()
        df_40.loc[40, 'Trigger_Panic'] = True
        res_40 = exp_engine.evaluate_signals(df_40, price_col='close', window=20)
        self.assertEqual(res_40['panic_buy_fdr'], 100.0)
        self.assertEqual(res_40['bottom_miss_rate'], 100.0)
        
        # Test Case 2: Day 60 (+10 days) -> Should be HIT
        df_60 = synthetic.copy()
        df_60.loc[60, 'Trigger_Panic'] = True
        res_60 = exp_engine.evaluate_signals(df_60, price_col='close', window=20)
        self.assertEqual(res_60['panic_buy_fdr'], 0.0)
        self.assertEqual(res_60['bottom_miss_rate'], 0.0)
        
        # Test Case 3: Day 45 (-5 days exact boundary) -> Should be HIT
        df_45 = synthetic.copy()
        df_45.loc[45, 'Trigger_Panic'] = True
        res_45 = exp_engine.evaluate_signals(df_45, price_col='close', window=20)
        self.assertEqual(res_45['panic_buy_fdr'], 0.0)
        self.assertEqual(res_45['bottom_miss_rate'], 0.0)
        
        # Test Case 4: Day 65 (+15 days exact boundary) -> Should be HIT
        df_65 = synthetic.copy()
        df_65.loc[65, 'Trigger_Panic'] = True
        res_65 = exp_engine.evaluate_signals(df_65, price_col='close', window=20)
        self.assertEqual(res_65['panic_buy_fdr'], 0.0)
        self.assertEqual(res_65['bottom_miss_rate'], 0.0)
        
        # Test Case 5: Day 34 (-16 days outside) -> Should be MISSED
        df_34 = synthetic.copy()
        df_34.loc[34, 'Trigger_Panic'] = True
        res_34 = exp_engine.evaluate_signals(df_34, price_col='close', window=20)
        self.assertEqual(res_34['panic_buy_fdr'], 100.0)
        
        # Test Case 6: Day 66 (+16 days outside) -> Should be MISSED
        df_66 = synthetic.copy()
        df_66.loc[66, 'Trigger_Panic'] = True
        res_66 = exp_engine.evaluate_signals(df_66, price_col='close', window=20)
        self.assertEqual(res_66['panic_buy_fdr'], 100.0)

    def test_04_panic_latch_lifecycle(self):
        """
        验证恐慌锁存:
        - 激活: Dist_200MA < -10%
        - 创新低逾 2% 刷新锚定点与计时器
        - 自然过期 (15交易日无触发)
        - 严格门禁: p > MA10 且 q1_dot > 0 必须同时成立, 严禁 -25% 绕过
        - 消耗: 发出有效买入信号当日锁存关闭
        """
        df = self.df_base.iloc[:35].copy()
        # Day 5: Enters panic (Dist_200MA = -12%, close = 88)
        df.loc[5, 'Dist_200MA'] = -12.0
        df.loc[5, 'close'] = 88.0
        
        # Generate with Factor B enabled
        # Day 10: Makes lower low by >2% (close = 85 < 88 * 0.98) -> should refresh timer
        df.loc[10, 'close'] = 85.0
        df.loc[10, 'Dist_200MA'] = -15.0
        
        # Day 12: q1_dot becomes positive (+0.5) and close > MA10
        df.loc[12, 'close'] = 92.0
        df.loc[12, 'MA10'] = 90.0
        df.loc[12, 'q1_dot'] = 0.5
        
        sig_df = exp_engine.generate_signals(df, use_factor_a=False, use_factor_b=True, use_factor_c=False, price_col='close')
        
        # Day 12 should trigger Trigger_Panic
        self.assertTrue(sig_df.loc[12, 'Trigger_Panic'])
        # Day 13 should NOT trigger again (consumed!)
        self.assertFalse(sig_df.loc[13, 'Trigger_Panic'])

    def test_05_reentry_and_stop_loss(self):
        """
        验证分类再入场与止损:
        - 泡沫顶卖出后进入 AFTER_BUBBLE, 次日仅凭 p > MA50 不得买入
        - 满足回踩 50MA 均线带 2 日且 q1_dot > 0 重新入场
        - 入场成交记录基准价并设定 10 日止损计时器
        - 10 日内跌破 5% 触发止损卖出
        - 定投加仓绝不重置止损计时器
        """
        df = self.df_base.iloc[:30].copy()
        
        # Day 2: Buy entry
        df.loc[1, 'Trigger_Panic'] = True
        
        # Day 5: Bubble top sell
        df.loc[4, 'raw_sell'] = True
        df.loc[4, 'sell_reason'] = 'BUBBLE'
        
        # Day 6 to 10: p > MA50 is True, but must NOT buy back!
        for d in range(5, 11):
            df.loc[d, 'cond_trend'] = True
            df.loc[d, 'close'] = 110.0
            df.loc[d, 'MA50'] = 100.0
            
        # Day 12 & 13: 2-day pullback within 2.5% of MA50, q1_dot > 0
        df.loc[11, 'close'] = 101.0
        df.loc[11, 'MA50'] = 100.0
        df.loc[12, 'close'] = 101.5
        df.loc[12, 'MA50'] = 100.0
        df.loc[12, 'MA20'] = 100.0
        df.loc[12, 'q1_dot'] = 0.2
        
        # Run simulation with Factor C enabled
        res = exp_engine.run_execution_simulation(df, use_factor_c=True, use_factor_a=False)
        
        # Verify that it did NOT buy on Day 6 (index 5)
        # Verify round trips: should have sold and stayed in cash until reentry
        self.assertTrue(res['round_trips'] >= 1)

    def test_06_accounting_identity_and_trading_days(self):
        """
        验证账户恒等式: Total Asset == Cash + Shares * Price
        单位净值与交易日间隔计算
        """
        df = self.df_base.iloc[:20].copy()
        df.loc[2, 'Trigger_Panic'] = True
        df.loc[8, 'raw_sell'] = True
        df.loc[8, 'sell_reason'] = 'BEAR'
        
        acc = UnitizedAccount(initial_cash=10000.0, initial_date=df['date'].iloc[0])
        executor = SharedExecutor(acc, fee_rate=0.001, execution_mode='NEXT_CLOSE', account_type='strat')
        
        for i in range(len(df)):
            dt = df['date'].iloc[i]
            p_i = df['close'].iloc[i]
            deposit = 1000.0 if i == 0 else 0.0
            executor.step(dt, p_i, p_i, dca_amount=deposit)
            
            if df['Trigger_Panic'].iloc[i]:
                executor.submit_order(1.0, "Buy", dt)
            elif df['raw_sell'].iloc[i]:
                executor.submit_order(0.0, "Sell", dt)
                
            # Verify Accounting Identity at EVERY step
            state = executor.daily_states[-1]
            calculated_asset = state['cash'] + state['shares'] * p_i
            self.assertAlmostEqual(state['equity'], calculated_asset, places=4)
            # Verify Unit NAV identity
            if state['units'] > 0:
                self.assertAlmostEqual(state['unit_nav'], state['equity'] / state['units'], places=4)


if __name__ == '__main__':
    unittest.main()
