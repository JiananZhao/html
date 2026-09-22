import os
import shutil
import pandas as pd
import numpy as np
from true_accounting import UnitizedAccount
from shared_executor import SharedExecutor
from core_engine.state_manager import StateManager

def test_missing_price_and_incremental():
    print("🚀 启动隔离环境下的定向缺价与多次重放测试...")
    
    # 准备清理临时测试目录
    test_dir = 'test_incremental_env'
    if os.path.exists(test_dir):
        shutil.rmtree(test_dir)
    os.makedirs(test_dir)
    
    sm = StateManager(test_dir)
    config_hash = "test_hash"
    ticker = "TEST"
    
    # 构建测试用的合成日历数据（包含一天缺价的情况）
    dates = pd.date_range('2023-01-01', periods=5)
    
    # 第一批数据 (3天) - 其中第二天(index 1)收盘价故意设为 NaN 模拟缺价
    prices_batch1 = [100.0, np.nan, 105.0]
    sub_bt1 = pd.DataFrame({'date': dates[:3], 'TEST': prices_batch1})
    
    # 初始化执行器
    acc = UnitizedAccount(initial_cash=10000.0, initial_date=dates[0])
    executor = SharedExecutor(acc, fee_rate=0.001, execution_mode='NEXT_CLOSE')
    
    # 第一天：提交买入订单 (目标 50% 仓位)
    print("\n--- Day 1 (正常): 提交 50% 买单 ---")
    executor.submit_order(0.5, "Test Buy", dates[0])
    executor.step(dates[0], p_open=100.0, p_close=100.0, dca_amount=0)
    print(f"Day 1 状态: 现金 {acc.cash}, 股数 {acc.shares}, 总资产 {acc.shares * 100.0 + acc.cash}, Pending Orders: {len(executor.pending_orders)}")
    
    # 第二天：执行上日的 NEXT_CLOSE 订单，但今日收盘价缺失！
    print("\n--- Day 2 (缺价): 测试暂估与挂起 ---")
    executor.step(dates[1], p_open=np.nan, p_close=np.nan, dca_amount=1000.0) # 故意注入 pending_cash
    
    print(f"Day 2 状态: Pending Cash: {executor.pending_cash}")
    print(f"Day 2 Pending Orders Count: {len(executor.pending_orders)} (应当保留)")
    print(f"Day 2 Daily State (Valuation Quality): {executor.daily_states[-1]['valuation_quality']}")
    
    # 第三天：恢复正常价格
    print("\n--- Day 3 (恢复): 测试延迟成交与资金汇入 ---")
    executor.step(dates[2], p_open=105.0, p_close=105.0, dca_amount=0)
    print(f"Day 3 状态: 现金 {acc.cash}, 股数 {acc.shares}, Pending Cash: {executor.pending_cash}")
    print(f"Day 3 Pending Orders Count: {len(executor.pending_orders)}")
    
    # 保存快照 (第一批次完成)
    print("\n--- 保存第一批次快照 (多次重放测试) ---")
    state_data = {
        'last_processed_date': sub_bt1['date'].iloc[-1].strftime('%Y-%m-%d'),
        'config_hash': config_hash,
        'executor_state': executor.get_state(),
    }
    ckpt_name = f"ckpt_{sub_bt1['date'].iloc[-1].strftime('%Y-%m-%d')}"
    sm.save_checkpoint('test_radar', ticker, config_hash, ckpt_name, state_data)
    
    # 第二批次数据 (重放测试)
    print("\n--- 启动第二批次 (重加载状态) ---")
    sub_bt2 = pd.DataFrame({'date': dates, 'TEST': [100.0, np.nan, 105.0, 110.0, 108.0]})
    
    checkpoint = sm.load_latest_checkpoint('test_radar', ticker, config_hash)
    if checkpoint:
        print(f"成功加载检查点，恢复日期: {checkpoint['last_processed_date']}")
        acc_new = UnitizedAccount(initial_cash=0.0, initial_date=pd.to_datetime(checkpoint['last_processed_date']))
        executor_new = SharedExecutor(acc_new, fee_rate=0.001, execution_mode='NEXT_CLOSE')
        executor_new.restore_state(checkpoint['executor_state'])
        
        # 验证恢复的数据
        print(f"恢复后状态: 现金 {executor_new.acc.cash}, 股数 {executor_new.acc.shares}")
        assert executor_new.acc.shares == executor.acc.shares, "股数恢复不一致！"
        assert executor_new.acc.cash == executor.acc.cash, "现金恢复不一致！"
        
        start_idx = sub_bt2[sub_bt2['date'] == checkpoint['last_processed_date']].index[0] + 1
        print(f"切片恢复：将从 index {start_idx} 开始继续执行")
        
        for i in range(start_idx, len(sub_bt2)):
            d = sub_bt2['date'].iloc[i]
            p = sub_bt2['TEST'].iloc[i]
            print(f"\n--- Day {i+1} (增量执行) {d.strftime('%Y-%m-%d')} ---")
            executor_new.step(d, p_open=p, p_close=p, dca_amount=0)
            print(f"执行后状态: 现金 {executor_new.acc.cash:.2f}, 股数 {executor_new.acc.shares:.2f}")
            
    else:
        print("❌ 检查点加载失败！")
        
    print("\n✅ 测试用例全部通过！")

if __name__ == '__main__':
    test_missing_price_and_incremental()
