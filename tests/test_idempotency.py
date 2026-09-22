import unittest
import os
import json
import shutil
import pandas as pd
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from core_engine.state_manager import StateManager

class TestIdempotency(unittest.TestCase):
    def setUp(self):
        self.base_dir = "test_states_tmp"
        if os.path.exists(self.base_dir):
            shutil.rmtree(self.base_dir)
        self.sm = StateManager(base_dir=self.base_dir)

    def tearDown(self):
        if os.path.exists(self.base_dir):
            shutil.rmtree(self.base_dir)

    def test_save_and_load_checkpoint_with_prefix_hash(self):
        strategy_id = "TEST_STRAT"
        symbol = "TEST"
        config_hash = "conf123"
        checkpoint_id = "cp_001"
        prefix_hash = "prefix_abc123"
        
        state_data = {
            "last_processed_date": "2023-01-01",
            "is_complete": True,
            "config_hash": config_hash
        }
        
        # Save checkpoint
        self.sm.save_checkpoint(strategy_id, symbol, config_hash, checkpoint_id, state_data.copy(), prefix_hash)
        
        # Check if the file is named correctly
        state_dir = self.sm.get_state_dir(strategy_id, symbol, config_hash)
        snapshot_filename = f"{strategy_id}_{prefix_hash}.json"
        snapshot_path = os.path.join(state_dir, "snapshots", snapshot_filename)
        self.assertTrue(os.path.exists(snapshot_path))
        
        # Load latest
        loaded = self.sm.load_latest_checkpoint(strategy_id, symbol, config_hash)
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded['prefix_hash'], prefix_hash)
        self.assertEqual(loaded['last_processed_date'], "2023-01-01")

    def test_verify_checkpoint(self):
        state_data = {
            "is_complete": True,
            "config_hash": "conf123",
            "prefix_hash": "hash_xyz"
        }
        
        # Valid resume
        self.assertTrue(self.sm.verify_checkpoint(state_data, "conf123", "hash_xyz"))
        
        # Invalid config hash
        self.assertFalse(self.sm.verify_checkpoint(state_data, "conf_wrong", "hash_xyz"))
        
        # Invalid prefix hash
        self.assertFalse(self.sm.verify_checkpoint(state_data, "conf123", "hash_wrong"))
        
        # Incomplete state
        state_data["is_complete"] = False
        self.assertFalse(self.sm.verify_checkpoint(state_data, "conf123", "hash_xyz"))

if __name__ == '__main__':
    unittest.main()
