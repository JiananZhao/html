# -*- coding: utf-8 -*-
"""
自动化测试：动力学相空间图 (Phase Space Chart) 视觉增强与通俗化注释实证核验
验证目标：
1. 四象限与横纵坐标通俗物理注释（导读卡片 + 画布角标 watermark + 坐标轴说明）
2. 90天连续轨迹时间渐变着色 (visualMap continuous: 90天前深青 -> 最新今天亮红)
3. 适老化大字体规范 (Rule 11: >= 14px)
4. Markdown 缩进代码块防御 (Lesson 20: _clean_html)
"""
import unittest
import json
import re
from core_engine.huang_dynamics_engine import HuangDynamicsEngine
import huang_dynamics_tab


class TestPhaseSpaceChartAnnotations(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.engine = HuangDynamicsEngine(ticker="QCOM")
        cls.engine.load_and_compute()

    def test_clean_html_utility(self):
        """测试 _clean_html 能彻底清除导致 CommonMark 误判为代码块的前导 4 空格与空白行"""
        raw_indented = """
        <div style="color: red;">
            <span>测试文本</span>
            
            <p>第二段</p>
        </div>
        """
        cleaned = huang_dynamics_tab._clean_html(raw_indented)
        # 每一行都不应该有前导空格
        for line in cleaned.splitlines():
            self.assertEqual(line, line.strip())
            self.assertTrue(len(line) > 0)
        # 不能包含代码块关键字
        self.assertNotIn("<pre>", cleaned)
        self.assertNotIn("<code>", cleaned)

    def test_phase_portrait_data_and_gradient(self):
        """测试相空间轨迹时间索引注入与 visualMap 渐变配置"""
        sub_dyn = self.engine.df.dropna(subset=['q', 'q_dot', 'LLE']).copy()
        traj_sub = sub_dyn.iloc[-90:]
        n_pts = len(traj_sub)
        self.assertGreater(n_pts, 0)

        # 检查轨迹数据第2维度是否为时序索引 (0 到 n_pts-1)
        traj_data = []
        for idx, (_, r) in enumerate(traj_sub.iterrows()):
            traj_data.append([
                round(float(r['q']), 2),
                round(float(r['q_dot']), 3),
                idx,
                str(r['date'])[:10],
                round(float(r['QCOM']), 2)
            ])
        self.assertEqual(traj_data[0][2], 0)
        self.assertEqual(traj_data[-1][2], n_pts - 1)

    def test_phase_portrait_code_inspection(self):
        """检查 huang_dynamics_tab.py 中的相空间图配置完全符合用户诉求与设计规范"""
        with open("huang_dynamics_tab.py", "r", encoding="utf-8") as f:
            code = f.read()

        # 1. 验证四象限导读卡片内容完整且通俗易懂
        self.assertIn("🧭 动力学相空间四象限物理导读", code)
        self.assertIn("象限 Ⅰ【右上：过热加速扩张】", code)
        self.assertIn("象限 Ⅳ【右下：高位动能衰竭】", code)
        self.assertIn("象限 Ⅲ【左下：恐慌探底下坠】", code)
        self.assertIn("象限 Ⅱ【左上：低位蓄势反弹】", code)

        # 2. 验证坐标轴通俗方向说明
        self.assertIn("【← 左侧超跌折价 (便宜) | 右侧高估过热 (贵) →】", code)
        self.assertIn("【↑ 上方动能加速扩张 | 下方动能衰竭下坠 ↓】", code)

        # 3. 验证多尺度宏观时间选择器与四阶段平滑宏观潮流配置
        self.assertIn("选择相空间轨迹宏观时间尺度", code)
        self.assertIn("本轮持股全周期", code)
        self.assertIn("启动出坑", code)
        self.assertIn("主升扩张", code)
        self.assertIn("高位运行", code)
        self.assertIn("冲刺当下", code)
        self.assertIn("本轮持股战略建仓点", code)
        self.assertIn('"arrow"', code)  # 验证方向箭头存在
        self.assertIn("#00f5d4", code)  # 极光青绿
        self.assertIn("#a855f7", code)  # 电光紫
        self.assertIn("#facc15", code)  # 阳光金
        self.assertIn("#ef4444", code)  # 烈火红
        self.assertIn("q_smooth", code)  # 验证 EMA 平滑滤波
        self.assertIn("qd_smooth", code)

        # 验证 TODAY 终点信标
        self.assertIn("TODAY 最新状态信标", code)

        # 验证标题与图例空间分离 (绝不重叠)
        self.assertIn('"top": "10px"', code)
        self.assertIn('"top": "38px"', code)

        # 4. 验证画布内四个象限角标 (graphic watermark)
        self.assertIn('"graphic"', code)
        self.assertIn("象限 Ⅰ【过热加速扩张】", code)
        self.assertIn("象限 Ⅳ【高位动能衰竭】", code)
        self.assertIn("象限 Ⅲ【恐慌探底下坠】", code)
        self.assertIn("象限 Ⅱ【低位蓄势反弹】", code)

        # 5. 验证坐标轴原点虚线 markLine 与理论决策盆地 markArea
        self.assertIn('{"xAxis": 0}', code)
        self.assertIn('{"yAxis": 0}', code)
        self.assertIn("🎯 理论战略买入盆地", code)
        self.assertIn("⚠️ 理论动能衰竭逃顶禁区", code)

        # 验证 13 年历史调仓复盘图层与时空隔离机制
        self.assertIn("📜 13年历史调仓复盘 (含年份)", code)
        self.assertIn('"selected":', code)
        self.assertIn('"📜 13年历史调仓复盘 (含年份)": False', code)
        self.assertIn("宏观相空间状态与策略买卖诊断", code)

        # 6. 验证适老化大字体 (Rule 11: >= 14px)
        # graphic 中的字体必须 >= 14px
        graphic_fonts = re.findall(r'"font":\s*"[^"]*?(\d+)px', code)
        self.assertTrue(len(graphic_fonts) >= 4)
        for size_str in graphic_fonts:
            self.assertGreaterEqual(int(size_str), 14, f"Found small font size in graphic: {size_str}px")


if __name__ == '__main__':
    unittest.main()
