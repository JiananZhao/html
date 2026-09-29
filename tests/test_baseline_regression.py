import unittest
import sys
import os

# Hack path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from now_reflexivity_radar import NOWReflexivityRadar

class TestBaselineRegression(unittest.TestCase):
    def test_now_reflexivity_baseline(self):
        """
        对照 P0/P1-A 版本的核心基线结果进行浮点容差断言。
        确保在统一使用 SharedExecutor 和 SimulationResult 后，
        历史业绩轨迹没有发生非预期的偏移或被幽灵复利污染。
        """
        radar = NOWReflexivityRadar()
        
        # 使用冻结数据集进行基线回归测试，以避免每日数据增量导致终值漂移
        frozen_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 
                                  'audit_artifacts', 'gemini_review_20260923', 'v2_3_independent_review', 'frozen_inputs')
        if os.path.exists(frozen_dir):
            radar.ohlcv_file = os.path.join(frozen_dir, 'now_ohlcv_local.csv')
            radar.market_data_path = os.path.join(frozen_dir, 'market_data_local.csv')
            
        radar.load_and_preprocess()
        radar.compute_all_dimensions()
        
        # 只跑回测，不需要绘图
        result = radar.run_backtest()
        
        # 预期的基线结果（来自 P1-A 稳定版或已知正确日志）
        expected_strat_end = 911834.97
        expected_bench_end = 956183.65
        expected_strat_cagr = 21.69
        expected_bench_cagr = 22.27
        expected_trades = 168
        
        # 获取实际结果
        metrics = result.metrics
        
        self.assertAlmostEqual(metrics['strat_final'], expected_strat_end, delta=2000.0, msg="策略终值发生意外偏离！")
        self.assertAlmostEqual(metrics['bench_final'], expected_bench_end, delta=2000.0, msg="基准终值发生意外偏离！")
        self.assertAlmostEqual(metrics['strat_cagr'], expected_strat_cagr, delta=0.5, msg="策略年化收益率发生意外偏离！")
        self.assertAlmostEqual(metrics['bench_cagr'], expected_bench_cagr, delta=0.5, msg="基准年化收益率发生意外偏离！")
        
        # 交易频次容忍小幅度策略边界调整，但大偏离说明逻辑损坏
        self.assertTrue(abs(len(result.fills) - expected_trades) <= 5, msg=f"交易笔数异常！期望 {expected_trades} 笔，实际 {len(result.fills)} 笔。")

if __name__ == '__main__':
    unittest.main()
