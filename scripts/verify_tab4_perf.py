import sys
import os
import io
import time
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pandas as pd
import company_tab
import charts.stock_charts as sc

print("=== 1. 测试底层数据与仿真缓存性能 ===")
t0 = time.time()
df_bt, meta = company_tab.load_and_cache_radar_simulation("NVDA")
t_load = time.time() - t0
print(f"首次/本地加载: {t_load:.3f}s, 数据行数: {len(df_bt)}")

t0 = time.time()
df_bt, meta = company_tab.load_and_cache_radar_simulation("NVDA")
t_cache = time.time() - t0
print(f"二次缓存命中加载: {t_cache:.4f}s")

print("\n=== 2. 测试时间切片与 4 层图表生成耗时 ===")
# 模拟滑块拖动到 6 个月区间
t0 = time.time()
fig1 = sc.create_interactive_reflexivity_radar(df_bt, "NVDA", start_date="2024-01-01", end_date="2024-06-30")
t_fig1 = time.time() - t0
print(f"滑块切片 [2024-01-01 至 2024-06-30] 图谱生成耗时: {t_fig1:.3f}s")

# 模拟滑块拖动到 3 个月区间
t0 = time.time()
fig2 = sc.create_interactive_reflexivity_radar(df_bt, "NVDA", start_date="2024-03-01", end_date="2024-06-01")
t_fig2 = time.time() - t0
print(f"滑块切片 [2024-03-01 至 2024-06-01] 图谱生成耗时: {t_fig2:.3f}s")

# 模拟预设一键切换至全部历史
t0 = time.time()
fig3 = sc.create_interactive_reflexivity_radar(df_bt, "NVDA", default_range="ALL")
t_fig3 = time.time() - t0
print(f"预设一键切换 [全部历史] 图谱生成耗时: {t_fig3:.3f}s")

print("\n=== 3. 验证 Y 轴自适应范围计算 ===")
y_p_range = fig2.layout.yaxis.range
print(f"3个月切片股价 Y 轴自适应区间: [{y_p_range[0]:.2f}, {y_p_range[1]:.2f}]")
assert y_p_range[0] > 0, "Y 轴价格下限应该大于 0"
assert y_p_range[1] > y_p_range[0], "Y 轴价格上限应大于下限"

print("\n>>> 全部性能与逻辑实证检验 PASS <<<")
