# -*- coding: utf-8 -*-
"""
Verification Script for Sub-Task 3:
Full-Spectrum Diagnostic Card UI Rendering & Plain Q&A Verification
"""
import sys
import os
import unittest
from unittest.mock import MagicMock, patch

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, r"e:\AI\Github_AIProject\html")
from core_engine.huang_dynamics_engine import HuangDynamicsEngine
import huang_dynamics_tab


class TestRenderDiagnosticHUD(unittest.TestCase):
    def test_multi_asset_benchmark_matrix_schema(self):
        print("\n" + "="*80)
        print("【子任务 3 自动化实证检验 - 第 1 部分】七大代表性标的横向评测矩阵完整性")
        print("="*80)

        data = huang_dynamics_tab.MULTI_ASSET_BENCHMARK_DATA
        self.assertEqual(len(data), 7, "必须覆盖 7 大代表性标的")
        
        required_keys = [
            "标的代码", "公司名称", "资产特性", "适用评级", "当前核心矛盾",
            "四力受力结构(宏/产/基/情)", "投入本金", "策略最终资产", "基准最终资产",
            "累积净超额 (Alpha $)", "财富相对增厚", "策略CAGR", "基准CAGR",
            "策略最大回撤", "基准最大回撤", "配对轮次", "持股时间比例", "样本外超额"
        ]

        for item in data:
            tk = item["标的代码"]
            for rk in required_keys:
                self.assertIn(rk, item, f"标的 {tk} 缺少必要字段 {rk}")
            print(f"✔ 标的 {tk:4s} | 评级: {item['适用评级']:<20s} | 核心矛盾: {item['当前核心矛盾']}")

    def test_diagnostic_card_rendering_and_qa(self):
        print("\n" + "="*80)
        print("【子任务 3 自动化实证检验 - 第 2 部分】通俗易懂全景体检卡 Q&A 与适老化大字排版")
        print("="*80)

        test_tickers = ["NOW", "COIN", "META", "MSFT", "AVGO"]

        for tk in test_tickers:
            captured_markdowns = []

            # Mock streamlit context
            with patch.object(huang_dynamics_tab.st, 'session_state', {"huang_current_ticker": tk}), \
                 patch.object(huang_dynamics_tab.st, 'markdown', side_effect=lambda content, **kwargs: captured_markdowns.append(content)), \
                 patch.object(huang_dynamics_tab.st, 'columns', side_effect=lambda spec: [MagicMock() for _ in range(len(spec) if isinstance(spec, list) else spec)]), \
                 patch.object(huang_dynamics_tab.st, 'text_input', return_value=tk), \
                 patch.object(huang_dynamics_tab.st, 'spinner', MagicMock()), \
                 patch.object(huang_dynamics_tab.st, 'subheader', MagicMock()), \
                 patch.object(huang_dynamics_tab.st, 'caption', MagicMock()), \
                 patch.object(huang_dynamics_tab.st, 'dataframe', MagicMock()), \
                 patch.object(huang_dynamics_tab.st, 'info', MagicMock()), \
                 patch.object(huang_dynamics_tab.components, 'html', MagicMock()):

                huang_dynamics_tab.render_huang_dynamics_tab()

            # 检索包含体检卡 HTML 的 markdown 内容
            hud_card_html = None
            for md in captured_markdowns:
                if "股票全景受力体检与前瞻实战指引卡" in md:
                    hud_card_html = md
                    break

            self.assertIsNotNone(hud_card_html, f"标的 {tk} 必须成功渲染体检指引卡")

            # 1. 验证 4 大核心直白问题全部涵盖
            self.assertIn("1️⃣ 这家公司到底受什么力量驱动？各占几成？", hud_card_html)
            self.assertIn("2️⃣ 此时此刻哪种力量占支配地位（当前核心矛盾）？", hud_card_html)
            self.assertIn("3️⃣ 这个模型在这个股票上好不好使、该信几成？", hud_card_html)
            self.assertIn("4️⃣ 明天 / 当下我到底该怎么操作？（确定性实战指引）", hud_card_html)

            # 2. 验证字体大小符合适老化大字规范 (>= 14px / >= 14pt)
            import re
            font_sizes = re.findall(r'font-size:\s*([0-9\.]+)px', hud_card_html)
            for fs in font_sizes:
                val = float(fs)
                self.assertGreaterEqual(val, 14.0, f"体检卡字体大小 {val}px 必须 >= 14px (Rule 11 适老化大字红线)")

            # 3. 验证无商业化或过度夸大词汇
            banned_jargon = ["硬编码", "动态HUD", "三层门禁"]
            for bj in banned_jargon:
                self.assertNotIn(bj, hud_card_html, f"体检卡严禁出现生硬商业黑话: {bj}")

            # 4. 关键验证：确保 CommonMark / Markdown 绝对不会将其渲染为缩进代码块 (<pre><code>)
            try:
                import markdown
                compiled_html = markdown.markdown(hud_card_html)
                self.assertNotIn("<pre><code>", compiled_html, "体检卡绝不能被 Markdown 误判为代码块 (<pre><code>)")
            except ImportError:
                pass

            print(f"✔ 标的 {tk:4s} 体检卡渲染验证 100% 通过 (4个直白问题解答完整，字体均 >= 14px)")

        print("\n" + "="*80)
        print("✅ 子任务 3 验证成功：通俗全景体检卡结构直白、四问清晰、适老化排版达标！")
        print("="*80 + "\n")


if __name__ == '__main__':
    unittest.main()
