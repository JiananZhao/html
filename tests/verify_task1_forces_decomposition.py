# -*- coding: utf-8 -*-
"""
Verification Script for Sub-Task 1:
Four Forces Decomposition, Dominant Driver Identification & Forward Guidance
"""
import sys
import os
import unittest
import numpy as np

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, r"e:\AI\Github_AIProject\html")
from core_engine.huang_dynamics_engine import HuangDynamicsEngine


class TestFourForcesDecomposition(unittest.TestCase):
    def test_multi_asset_decomposition(self):
        tickers = ['NOW', 'COIN', 'MSFT', 'AVGO']
        results = []

        print("\n" + "="*80)
        print("【子任务 1 自动化实证检验】四大基本作用力动态分解与前瞻指引")
        print("="*80)

        for tk in tickers:
            engine = HuangDynamicsEngine(ticker=tk)
            engine.load_and_compute()
            prof = engine.fundamental_profile
            
            self.assertIsNotNone(prof, f"Profile must not be None for {tk}")
            self.assertIn('w_macro', prof)
            self.assertIn('w_sector', prof)
            self.assertIn('w_fund', prof)
            self.assertIn('w_reflexive', prof)
            self.assertIn('dominant_driver', prof)
            self.assertIn('forward_guidance_state', prof)
            self.assertIn('forward_guidance_desc', prof)
            self.assertIn('forward_action_advice', prof)

            # 1. 检验四力加总严格等于 100%
            tot = prof['w_macro'] + prof['w_sector'] + prof['w_fund'] + prof['w_reflexive']
            self.assertAlmostEqual(tot, 100.0, places=1, msg=f"Four forces sum must be 100% for {tk}")

            # 2. 检验评级绝无 5 星 (严禁虚妄自满)
            self.assertNotIn("5/5", prof['rating'])
            self.assertNotIn("⭐⭐⭐⭐⭐", prof['rating_stars'])

            # 3. 检验 COIN 识别出特质主导与警示
            if tk == 'COIN':
                self.assertIn("1/5", prof['rating'])
                self.assertEqual(prof['forward_guidance_state'], "HIGH_IDIO_GAMBLE")
                self.assertGreaterEqual(prof['w_reflexive'], 50.0)

            # 4. 检验 NOW 识别为宏观/产业共振 (<= 4 星)
            if tk == 'NOW':
                self.assertIn("4/5", prof['rating'])
                self.assertGreaterEqual(prof['w_macro'] + prof['w_sector'], 50.0)

            results.append({
                '标的代码': tk,
                '商业分类': prof['category'],
                '宏观系统力': f"{prof['w_macro']}%",
                '产业供求力': f"{prof['w_sector']}%",
                '微观做功力': f"{prof['w_fund']}%",
                '反身性动能': f"{prof['w_reflexive']}%",
                '当前主要矛盾': prof['dominant_driver'],
                '前瞻状态': prof['forward_guidance_state'],
                '适用评级': prof['rating_stars']
            })

            print(f"\n▶ 标的: {tk} ({prof['category']}) | 适用评级: {prof['rating_stars']}")
            print(f"  • 受力分解: 宏观力 {prof['w_macro']}% | 产业力 {prof['w_sector']}% | 估值做功 {prof['w_fund']}% | 情绪动能 {prof['w_reflexive']}% (合计: {tot:.1f}%)")
            print(f"  • 主要矛盾: 【{prof['dominant_driver']}】")
            print(f"  • 前瞻态势: {prof['forward_guidance_desc']}")
            print(f"  • 操作指引: {prof['forward_action_advice']}")

        print("\n" + "="*80)
        print("✅ 子任务 1 验证成功：四力方差分解数学自洽、主要矛盾识别准确、前瞻指引清晰！")
        print("="*80 + "\n")


if __name__ == '__main__':
    unittest.main()
