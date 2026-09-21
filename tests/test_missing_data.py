import unittest
import pandas as pd
import numpy as np
import sys
import os

# Hack path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from true_accounting import UnitizedAccount
from shared_executor import SharedExecutor

class TestMissingDataProtection(unittest.TestCase):
    def setUp(self):
        # 构造带有缺失值的数据
        dates = pd.date_range('2024-01-01', periods=5, freq='D')
        self.df_mock = pd.DataFrame({
            'date': dates,
            'close': [100.0, 102.0, np.nan, 105.0, 110.0]
        })

    def test_stale_pricing_handling(self):
        """测试遇到缺失价格时使用暂估价格，并在之后恢复"""
        acc = UnitizedAccount(initial_cash=1000, initial_date=self.df_mock['date'].iloc[0])
        executor = SharedExecutor(acc, fee_rate=0.0)
        
        # Day 0: Price = 100, execute Buy
        executor.submit_order(1.0, "Init Buy", self.df_mock['date'].iloc[0])
        executor.step(self.df_mock['date'].iloc[0], self.df_mock['close'].iloc[0], self.df_mock['close'].iloc[0])
        
        self.assertEqual(acc.shares, 10.0)
        self.assertEqual(executor.daily_states[-1]['unit_nav'], 1.0)
        self.assertEqual(executor.daily_states[-1]['equity'], 1000.0)
        self.assertEqual(executor.daily_states[-1].get('valuation_quality'), 'good') # first day is not stale

        # Day 1: Price = 102
        executor.step(self.df_mock['date'].iloc[1], self.df_mock['close'].iloc[1], self.df_mock['close'].iloc[1])
        self.assertEqual(acc.shares, 10.0)
        self.assertEqual(executor.daily_states[-1]['unit_nav'], 1.02)
        self.assertEqual(executor.daily_states[-1]['equity'], 1020.0)
        self.assertEqual(executor.daily_states[-1].get('valuation_quality'), 'good')

        # Day 2: Price = NaN (Missing)
        executor.step(self.df_mock['date'].iloc[2], self.df_mock['close'].iloc[2], self.df_mock['close'].iloc[2])
        # Expected: use Day 1 nav for valuation (1.02), equity = 1020.0, quality = 'stale'
        self.assertEqual(acc.shares, 10.0) # Not changed
        self.assertEqual(executor.daily_states[-1]['unit_nav'], 1.02)
        self.assertEqual(executor.daily_states[-1]['equity'], 1020.0)
        self.assertEqual(executor.daily_states[-1].get('valuation_quality'), 'stale')

        # Day 3: Price = 105 (Recovery)
        executor.step(self.df_mock['date'].iloc[3], self.df_mock['close'].iloc[3], self.df_mock['close'].iloc[3])
        self.assertEqual(executor.daily_states[-1]['unit_nav'], 1.05)
        self.assertEqual(executor.daily_states[-1]['equity'], 1050.0)
        self.assertEqual(executor.daily_states[-1].get('valuation_quality'), 'good') # No longer stale

    def test_prevent_dca_on_stale(self):
        """测试在暂估状态下严禁将新资金转换为份额，资金应挂起直到恢复"""
        acc = UnitizedAccount(initial_cash=0, initial_date=self.df_mock['date'].iloc[0])
        executor = SharedExecutor(acc, fee_rate=0.0)
        
        # Day 0: Price = 100
        executor.step(self.df_mock['date'].iloc[0], self.df_mock['close'].iloc[0], self.df_mock['close'].iloc[0], dca_amount=1000)
        self.assertEqual(executor.daily_states[-1]['equity'], 1000.0)
        
        # Buy on Day 0
        executor.submit_order(1.0, "Init Buy", self.df_mock['date'].iloc[0])
        
        # Day 1: Price = 102
        executor.step(self.df_mock['date'].iloc[1], self.df_mock['close'].iloc[1], self.df_mock['close'].iloc[1])
        self.assertEqual(acc.shares, 1000 / 102.0)

        # Day 2: Price = NaN, Inject DCA
        executor.step(self.df_mock['date'].iloc[2], self.df_mock['close'].iloc[2], self.df_mock['close'].iloc[2], dca_amount=500)
        
        # In stale mode, the DCA shouldn't convert to units immediately
        self.assertEqual(executor.pending_cash, 500)
        self.assertAlmostEqual(executor.daily_states[-1]['equity'], 1000.0, places=4) # Equity remains 1000 because shares are valued at stale price 102 (1000/102 * 102 = 1000)
        
        # Day 3: Price = 105, recovery, pending cash should be injected
        executor.step(self.df_mock['date'].iloc[3], self.df_mock['close'].iloc[3], self.df_mock['close'].iloc[3], dca_amount=0)
        self.assertEqual(executor.pending_cash, 0)
        
        # Total equity should now be: value of shares (1000/102 * 105) + 500 (newly injected cash)
        expected_equity = (1000 / 102.0) * 105.0 + 500.0
        self.assertAlmostEqual(executor.daily_states[-1]['equity'], expected_equity, places=4)

if __name__ == '__main__':
    unittest.main()
