import unittest
import pandas as pd
from datetime import datetime, timedelta
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from true_accounting import UnitizedAccount
from shared_executor import SharedExecutor

class TestExecutionRules(unittest.TestCase):
    def test_submit_dt_less_than_fill_dt(self):
        acc = UnitizedAccount(initial_cash=1000, initial_date=pd.Timestamp('2023-01-01'))
        executor = SharedExecutor(acc, fee_rate=0.0, execution_mode='NEXT_OPEN')
        
        # Submit on Day 1
        dt1 = pd.Timestamp('2023-01-02')
        executor.submit_order(0.5, "Test Order", dt1)
        
        # Try to execute on Day 1 (should not execute)
        executor.step(dt1, p_open=100, p_close=100)
        self.assertEqual(executor.pending_orders[0]['status'], 'PENDING')
        self.assertEqual(acc.shares, 0.0)
        
        # Execute on Day 2
        dt2 = pd.Timestamp('2023-01-03')
        executor.step(dt2, p_open=100, p_close=100)
        self.assertEqual(len(executor.pending_orders), 0)
        self.assertEqual(acc.shares, 5.0)

    def test_dca_injection_timing(self):
        # NEXT_OPEN mode should inject DCA at p_open
        acc = UnitizedAccount(initial_cash=1000, initial_date=pd.Timestamp('2023-01-01'))
        executor = SharedExecutor(acc, fee_rate=0.0, execution_mode='NEXT_OPEN')
        
        dt1 = pd.Timestamp('2023-01-02')
        executor.step(dt1, p_open=100, p_close=200, dca_amount=100)
        
        # In NEXT_OPEN, it uses p_open for injection
        # Current NAV is 1.0. Amount is 100. Should issue 100 / 1.0 = 100 units.
        self.assertEqual(acc.cash, 1100)
        self.assertEqual(acc.units, 1100) # Initial 1000 + 100 DCA

    def test_missing_price_fallback(self):
        acc = UnitizedAccount(initial_cash=1000, initial_date=pd.Timestamp('2023-01-01'))
        executor = SharedExecutor(acc, fee_rate=0.0, execution_mode='NEXT_OPEN')
        
        dt1 = pd.Timestamp('2023-01-02')
        executor.submit_order(1.0, "Buy All", dt1)
        
        # Day 2: p_open is missing (NaN), p_close is available
        dt2 = pd.Timestamp('2023-01-03')
        executor.step(dt2, p_open=float('nan'), p_close=100)
        
        # Order should NOT be filled because NEXT_OPEN doesn't fall back to NEXT_CLOSE
        self.assertEqual(executor.pending_orders[0]['status'], 'PENDING')
        self.assertEqual(acc.shares, 0.0)
        
        # Day 3: p_open is valid
        dt3 = pd.Timestamp('2023-01-04')
        executor.step(dt3, p_open=100, p_close=100)
        self.assertEqual(len(executor.pending_orders), 0)
        self.assertEqual(acc.shares, 10.0)

    def test_state_serialization(self):
        acc = UnitizedAccount(initial_cash=1000, initial_date=pd.Timestamp('2023-01-01'))
        executor = SharedExecutor(acc, fee_rate=0.0, execution_mode='NEXT_OPEN')
        
        dt1 = pd.Timestamp('2023-01-02')
        executor.step(dt1, p_open=100, p_close=100, dca_amount=100)
        
        state = executor.get_state()
        
        # Ensure cashflows is in the state and preserved
        self.assertIn('cash_flows', state['account_state'])
        self.assertEqual(len(state['account_state']['cash_flows']), 2) # initial + dca
        
        # Restore
        acc2 = UnitizedAccount()
        executor2 = SharedExecutor(acc2, fee_rate=0.0, execution_mode='NEXT_OPEN')
        executor2.restore_state(state)
        
        self.assertEqual(executor2.acc.cash, 1100)
        self.assertEqual(len(executor2.acc.cash_flows), 2)
        
if __name__ == '__main__':
    unittest.main()
