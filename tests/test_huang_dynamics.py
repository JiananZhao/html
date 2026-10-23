# -*- coding: utf-8 -*-
import unittest
import pandas as pd
from core_engine.huang_dynamics_engine import HuangDynamicsEngine


class TestHuangDynamicsEngine(unittest.TestCase):
    def setUp(self):
        self.engine = HuangDynamicsEngine(ticker="NOW")
        self.engine.load_and_compute()

    def test_dynamics_computation(self):
        df = self.engine.df
        self.assertIsNotNone(df)
        self.assertIn('q', df.columns)
        self.assertIn('q_dot', df.columns)
        self.assertIn('k_stiffness', df.columns)
        self.assertIn('gamma_damping', df.columns)
        self.assertIn('LLE', df.columns)
        self.assertIn('Energy_V', df.columns)
        self.assertGreater(len(df), 2000)

    def test_simulation_and_evaluation(self):
        df_bt = self.engine.run_simulation(start_date='2013-06-01', initial_capital=10000.0, dca_monthly=1000.0)
        self.assertIsNotNone(df_bt)
        rep = self.engine.eval_report
        
        # 1. 财富增值 Alpha 测试 (必须跑赢买入持有基准)
        self.assertGreater(rep["超额累积净财富 (Alpha $)"], 0.0)
        self.assertGreater(rep["策略最终财富"], rep["基准最终财富"])
        
        # 2. 交易信噪比测试 (13年配对轮次不得超过 15 轮，防止高频均线磨损)
        self.assertLessEqual(rep["总交易配对轮次"], 15)
        
        # 3. 现金拖累测试 (全周期持股比例 >= 85%)
        self.assertGreaterEqual(rep["全周期持股比例(%)"], 85.0)
        
        # 4. 样本外泛化超额收益 (2019-2026 OOS Alpha > 0)
        self.assertGreater(rep["2019-2026样本外超额收益(%)"], 0.0)

    def test_fundamental_profile(self):
        prof = self.engine.fundamental_profile
        self.assertIsNotNone(prof)
        self.assertIn('category', prof)
        self.assertIn('rating', prof)
        self.assertIn('ann_vol', prof)
        self.assertIn('idiosyncratic_pct', prof)
        self.assertIn('w_macro', prof)
        self.assertIn('w_sector', prof)
        self.assertIn('w_fund', prof)
        self.assertIn('w_reflexive', prof)
        self.assertEqual(prof['ticker'], "NOW")
        self.assertIn("科技", prof['category'])

        # Verify COIN profile
        coin_engine = HuangDynamicsEngine(ticker="COIN")
        coin_engine.load_and_compute()
        c_prof = coin_engine.fundamental_profile
        self.assertIn("特质", c_prof['category'])
        self.assertGreater(c_prof['ann_vol'], 60.0)
        self.assertGreater(c_prof['idiosyncratic_pct'], 60.0)

    def test_tab7_import(self):
        import huang_dynamics_tab
        self.assertTrue(callable(huang_dynamics_tab.render_huang_dynamics_tab))


if __name__ == '__main__':
    unittest.main()

