# -*- coding: utf-8 -*-
"""
Verification Script for Sub-Task 2:
Forward-Looking Guidance State Machine & Scenario Verification
"""
import sys
import os
import unittest

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, r"e:\AI\Github_AIProject\html")
from core_engine.huang_dynamics_engine import HuangDynamicsEngine


class TestForwardGuidanceStateMachine(unittest.TestCase):
    def test_forward_guidance_scenarios(self):
        print("\n" + "="*80)
        print("【子任务 2 自动化实证检验】前瞻状态机识别与实盘决策指引")
        print("="*80)

        # -------------------------------------------------------------
        # 1. 验证 2021 年底 NOW 触发相变失稳逃顶预警 (Phase Instability Top)
        # -------------------------------------------------------------
        now_engine = HuangDynamicsEngine(ticker="NOW")
        now_engine.load_and_compute()
        prof_now_2021 = now_engine.compute_fundamental_profile(as_of_date="2021-11-15")
        
        print("\n▶ [实证场景 1: 历史大顶相变失稳] NOW @ 2021-11-15 (历史极值高位)")
        print(f"  • 前瞻状态: {prof_now_2021['forward_guidance_state']}")
        print(f"  • 态势描述: {prof_now_2021['forward_guidance_desc']}")
        print(f"  • 决策指引: {prof_now_2021['forward_action_advice']}")
        
        self.assertEqual(prof_now_2021['forward_guidance_state'], "PHASE_INSTABILITY",
                         "NOW 在 2021 年 11 月过热高位必须触发 PHASE_INSTABILITY (相变失稳逃顶预警)")
        self.assertIn("逃顶", prof_now_2021['forward_action_advice'])

        # -------------------------------------------------------------
        # 2. 验证 2022 年底 META 准确预警微观价值陷阱 (Value Trap / Dead Cat Bounce)
        # -------------------------------------------------------------
        meta_engine = HuangDynamicsEngine(ticker="META")
        meta_engine.load_and_compute()
        prof_meta_2022 = meta_engine.compute_fundamental_profile(as_of_date="2022-10-31")

        print("\n▶ [实证场景 2: 深度暴跌与死猫跳陷阱] META @ 2022-10-31 (跌破 $95)")
        print(f"  • 前瞻状态: {prof_meta_2022['forward_guidance_state']}")
        print(f"  • 态势描述: {prof_meta_2022['forward_guidance_desc']}")
        print(f"  • 决策指引: {prof_meta_2022['forward_action_advice']}")

        self.assertEqual(prof_meta_2022['forward_guidance_state'], "VALUE_TRAP",
                         "META 在 2022 年 10 月底暴跌时必须触发 VALUE_TRAP (价值陷阱/死猫跳预警)，防止盲目接飞刀")
        self.assertIn("抄底", prof_meta_2022['forward_action_advice'])

        # -------------------------------------------------------------
        # 3. 验证 COIN 准确识别特质博弈与无统计学优势 (High Idiosyncratic Gamble)
        # -------------------------------------------------------------
        coin_engine = HuangDynamicsEngine(ticker="COIN")
        coin_engine.load_and_compute()
        prof_coin = coin_engine.fundamental_profile

        print("\n▶ [实证场景 3: 宏观脱节与特质博弈] COIN (加密资产高特质标的)")
        print(f"  • 前瞻状态: {prof_coin['forward_guidance_state']}")
        print(f"  • 态势描述: {prof_coin['forward_guidance_desc']}")
        print(f"  • 决策指引: {prof_coin['forward_action_advice']}")

        self.assertEqual(prof_coin['forward_guidance_state'], "HIGH_IDIO_GAMBLE",
                         "COIN 必须识别为 HIGH_IDIO_GAMBLE，宏观信贷指标脱节")

        # -------------------------------------------------------------
        # 4. 验证稳态主升浪 (Expansion Trend): AVGO 最新截面 & NOW 2024-06-01
        # -------------------------------------------------------------
        avgo_engine = HuangDynamicsEngine(ticker="AVGO")
        avgo_engine.load_and_compute()
        prof_avgo = avgo_engine.fundamental_profile
        print("\n▶ [实证场景 4A: 稳态主升浪] AVGO @ 最新截面")
        print(f"  • 前瞻状态: {prof_avgo['forward_guidance_state']}")
        print(f"  • 态势描述: {prof_avgo['forward_guidance_desc']}")
        print(f"  • 决策指引: {prof_avgo['forward_action_advice']}")
        self.assertEqual(prof_avgo['forward_guidance_state'], "EXPANSION_TREND",
                         "AVGO 在最新截面应处于 EXPANSION_TREND (稳态主升浪)")

        prof_now_2024 = now_engine.compute_fundamental_profile(as_of_date="2024-06-01")
        print("\n▶ [实证场景 4B: 稳态主升浪] NOW @ 2024-06-01")
        print(f"  • 前瞻状态: {prof_now_2024['forward_guidance_state']}")
        print(f"  • 态势描述: {prof_now_2024['forward_guidance_desc']}")
        print(f"  • 决策指引: {prof_now_2024['forward_action_advice']}")
        self.assertEqual(prof_now_2024['forward_guidance_state'], "EXPANSION_TREND",
                         "NOW 在 2024 年 6 月应处于 EXPANSION_TREND (稳态主升浪)")

        print("\n" + "="*80)
        print("✅ 子任务 2 验证成功：前瞻状态机能够准确识别相变大顶、价值陷阱与无胜率博弈期！")
        print("="*80 + "\n")


if __name__ == '__main__':
    unittest.main()
