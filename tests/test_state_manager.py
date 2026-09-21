import unittest
import os
import json
import shutil
import pandas as pd
import sys

# Hack path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core_engine.state_manager import StateManager

class TestStateManager(unittest.TestCase):
    def setUp(self):
        self.test_dir = ".test_states"
        self.sm = StateManager(base_dir=self.test_dir)
        self.strategy_id = "test_strat"
        self.symbol = "TEST"
        self.config_hash = "v1"

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_save_and_load_checkpoint(self):
        """测试正常保存和加载检查点"""
        state_data = {
            "last_processed_date": "2024-01-01",
            "accounts_state": {"shares": 100, "cash": 5000}
        }
        
        self.sm.save_checkpoint(
            self.strategy_id, 
            self.symbol, 
            self.config_hash, 
            "chk_001", 
            state_data
        )
        
        loaded = self.sm.load_latest_checkpoint(self.strategy_id, self.symbol, self.config_hash)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["last_processed_date"], "2024-01-01")
        self.assertEqual(loaded["accounts_state"]["shares"], 100)

    def test_load_non_existent(self):
        """测试加载不存在的检查点"""
        loaded = self.sm.load_latest_checkpoint("non_existent", "NON", "v1")
        self.assertIsNone(loaded)

    def test_atomic_overwrite(self):
        """测试新检查点覆盖旧检查点逻辑（latest 更新）"""
        state1 = {"val": 1}
        self.sm.save_checkpoint(self.strategy_id, self.symbol, self.config_hash, "chk_1", state1)
        
        state2 = {"val": 2}
        self.sm.save_checkpoint(self.strategy_id, self.symbol, self.config_hash, "chk_2", state2)
        
        loaded = self.sm.load_latest_checkpoint(self.strategy_id, self.symbol, self.config_hash)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded["val"], 2)

if __name__ == '__main__':
    unittest.main()
