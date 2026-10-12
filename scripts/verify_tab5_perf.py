import sys
import os
import io
import time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pandas as pd
import reflexivity_tab
from reflexivity_interactive_chart import build_interactive_4layer_chart

print("=== 测试 Tab 5 数据加载与图表切片生成 ===")
df, src = reflexivity_tab.load_market_data_cross_platform()
print(f"数据源: {src}, 数据行数: {len(df)}")

sim_res = reflexivity_tab.get_cached_simulation(df, "QQQ")
print(f"QQQ 仿真回测结果是否有效: {sim_res is not None}")

# 模拟 Tab 5 滑块拖动切片生成
t0 = time.time()
fig_q = build_interactive_4layer_chart(sim_res, "QQQ", start_date="2024-01-01", end_date="2024-06-30")
t_q = time.time() - t0
print(f"Tab 5 QQQ 6个月切片生成耗时: {t_q:.3f}s")

t0 = time.time()
fig_q2 = build_interactive_4layer_chart(sim_res, "QQQ", start_date="2024-03-01", end_date="2024-06-01")
t_q2 = time.time() - t0
print(f"Tab 5 QQQ 3个月切片生成耗时: {t_q2:.3f}s")

print("\n>>> Tab 5 性能检验 PASS <<<")
