import unittest
import pandas as pd
import numpy as np

# 因为此时尚未在 sys.path 根目录，这里作简单 Hack 处理，以便能独立运行
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from true_accounting import UnitizedAccount
from shared_executor import SharedExecutor
from reflexivity_interactive_chart import run_reflexivity_simulation

class TestP1AMacroAccounting(unittest.TestCase):
    
    def setUp(self):
        # 构造一条极简测试数据
        dates = pd.date_range('2020-01-01', periods=10, freq='D')
        self.df_mock = pd.DataFrame({
            'date': dates,
            'QQQ': [100, 102, 98, 105, 110, 108, 115, 120, 118, 125],
            'HYG': [80]*10,
            'NFCI': [-0.6]*10,
            'BAA10Y': [4.0]*10,
            'Real_Yield': [1.0]*10
        })
        
    def test_initial_date_enforcement(self):
        """测试初始资金必须显式传入日期，不能'自动补充正确日期'"""
        with self.assertRaises(ValueError):
            # 不传 date 应当报错
            acc = UnitizedAccount(initial_cash=1000)
            
        acc2 = UnitizedAccount(initial_cash=1000, initial_date=pd.Timestamp('2020-01-01'))
        self.assertEqual(acc2.cash, 1000)
        self.assertEqual(acc2.unit_nav, 1.0)
        self.assertEqual(len(acc2.cash_flows), 1)

    def test_next_close_execution(self):
        """测试 NEXT_CLOSE 的状态流转"""
        acc = UnitizedAccount(initial_cash=1000, initial_date=self.df_mock['date'].iloc[0])
        executor = SharedExecutor(acc, fee_rate=0.0)
        
        # Day 0: No order, just cash
        executor.step(self.df_mock['date'].iloc[0], self.df_mock['QQQ'].iloc[0], self.df_mock['QQQ'].iloc[0], dca_amount=0)
        self.assertEqual(acc.shares, 0)
        
        # Day 0 End: Strategy decides to buy full position (1.0)
        executor.submit_order(1.0, "Testing Buy", self.df_mock['date'].iloc[0])
        
        # Day 1: Step executes the pending order at Day 1 price (102)
        executor.step(self.df_mock['date'].iloc[1], self.df_mock['QQQ'].iloc[1], self.df_mock['QQQ'].iloc[1], dca_amount=0)
        # Expected shares: 1000 / 102
        expected_shares = 1000 / 102
        self.assertAlmostEqual(acc.shares, expected_shares, places=4)
        self.assertEqual(executor.last_buy_p, 102)
        self.assertEqual(len(executor.fills), 1)
        
    def test_fee_rate_impact(self):
        """测试费用是否能够正确从资金池扣除"""
        acc = UnitizedAccount(initial_cash=1000, initial_date=self.df_mock['date'].iloc[0])
        executor = SharedExecutor(acc, fee_rate=0.01) # 1% fee for easy math
        
        executor.submit_order(1.0, "Buy", self.df_mock['date'].iloc[0])
        # Executes at price=100.
        # Total cost = Shares * P + Shares * P * fee_rate = Cash
        # Shares * P * 1.01 = 1000 => Shares * P = 1000 / 1.01
        # Shares = 1000 / (1.01 * 100) = 1000 / 101 = 9.90099
        executor.step(self.df_mock['date'].iloc[0], 100.0, 100.0)
        
        expected_shares = 1000 / 101.0
        self.assertAlmostEqual(acc.shares, expected_shares, places=4)
        
        # unit_nav should immediately drop because of fee
        self.assertTrue(acc.unit_nav < 1.0)

if __name__ == '__main__':
    unittest.main()
