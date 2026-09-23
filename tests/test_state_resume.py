import unittest
import pandas as pd
import numpy as np
import sys
import os

# Hack path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from true_accounting import UnitizedAccount
from shared_executor import SharedExecutor

class TestStateResume(unittest.TestCase):
    def setUp(self):
        dates = pd.date_range('2024-01-01', periods=5, freq='D')
        self.df_mock = pd.DataFrame({
            'date': dates,
            'close': [100.0, 105.0, 110.0, 90.0, 95.0]
        })

    def test_executor_state_resume(self):
        """测试从状态快照中精确恢复执行上下文"""
        
        # === 第1阶段：运行前两天，并获取状态 ===
        acc1 = UnitizedAccount(initial_cash=1000, initial_date=self.df_mock['date'].iloc[0])
        exec1 = SharedExecutor(acc1, fee_rate=0.0)
        
        # Day 0
        exec1.submit_order(1.0, "Buy All", self.df_mock['date'].iloc[0])
        exec1.step(self.df_mock['date'].iloc[0], self.df_mock['close'].iloc[0], self.df_mock['close'].iloc[0])
        
        # Day 1
        exec1.step(self.df_mock['date'].iloc[1], self.df_mock['close'].iloc[1], self.df_mock['close'].iloc[1], dca_amount=500.0)
        
        state1 = exec1.get_state()
        
        # === 第2阶段：使用获取的状态恢复一个全新的执行器 ===
        acc2 = UnitizedAccount(initial_cash=0, initial_date=pd.Timestamp('1900-01-01')) # 初始化参数会被覆盖
        exec2 = SharedExecutor(acc2, fee_rate=0.0)
        
        # 恢复状态
        exec2.restore_state(state1)
        
        # 验证恢复后的关键数据结构是否匹配
        self.assertEqual(exec2.acc.cash, exec1.acc.cash)
        self.assertEqual(exec2.acc.shares, exec1.acc.shares)
        self.assertEqual(exec2.pending_cash, exec1.pending_cash)
        # Note: daily_states is not restored from JSON, it's appended incrementally
        
        # Day 2
        exec2.step(self.df_mock['date'].iloc[2], self.df_mock['close'].iloc[2], self.df_mock['close'].iloc[2])
        exec1.step(self.df_mock['date'].iloc[2], self.df_mock['close'].iloc[2], self.df_mock['close'].iloc[2])
        
        # 验证断点续跑后，最新的状态与从未中断的执行器完全一致
        self.assertAlmostEqual(exec1.acc.cash, exec2.acc.cash, places=4)
        self.assertAlmostEqual(exec1.acc.shares, exec2.acc.shares, places=4)
        self.assertAlmostEqual(exec1.daily_states[-1]['equity'], exec2.daily_states[-1]['equity'], places=4)

if __name__ == '__main__':
    unittest.main()
