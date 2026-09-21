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
        radar.load_and_preprocess()
        radar.compute_all_dimensions()
        
        # 只跑回测，不需要绘图
        result = radar.run_backtest()
        
        # 预期的基线结果（来自 P1-A 稳定版或已知正确日志）
        expected_strat_end = 910713.71
        expected_bench_end = 955174.81
        expected_strat_cagr = 21.67
        expected_bench_cagr = 22.26
        expected_trades = 168
        
        # 获取实际结果
        metrics = result.metrics
        
        self.assertAlmostEqual(metrics['strat_end'], expected_strat_end, delta=100.0, msg="策略终值发生意外偏离！")
        self.assertAlmostEqual(metrics['bench_end'], expected_bench_end, delta=100.0, msg="基准终值发生意外偏离！")
        self.assertAlmostEqual(metrics['strat_cagr'], expected_strat_cagr, delta=0.5, msg="策略年化收益率发生意外偏离！")
        self.assertAlmostEqual(metrics['bench_cagr'], expected_bench_cagr, delta=0.5, msg="基准年化收益率发生意外偏离！")
        
        # 交易频次容忍小幅度策略边界调整，但大偏离说明逻辑损坏
        self.assertTrue(abs(len(result.fills) - expected_trades) <= 5, msg=f"交易笔数异常！期望 {expected_trades} 笔，实际 {len(result.fills)} 笔。")

if __name__ == '__main__':
    unittest.main()
