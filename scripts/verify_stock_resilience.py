# -*- coding: utf-8 -*-
"""
scripts/verify_stock_resilience.py
==================================
离线多场景行为实证脚本 (对应实施方案六大核心行为规范)

验收覆盖:
1. [CASE 1] 公司资料失败、行情成功 -> 行情与技术指标独立正常处理，基础资料客观降级
2. [CASE 2] 公司资料失败、财报成功 -> 财报透视表独立正常解析，打破一票否决
3. [CASE 3] 三张表中一张失败 (利润表为空) -> 资产负债表与现金流表仍能正常解析并展示
4. [CASE 4] 首次失败进入冷却 -> 模拟时钟推进后冷却过期，下一次请求成功，不被旧失败结果阻挡
5. [CASE 5] 连续刷新且持续 401 -> 请求次数受控拦截在冷却层内，不崩溃
6. [CASE 6] 仅有本地收盘价 (NVDA 离线兜底) -> 正确提取本地历史序列，锁定折线图，标明日期与来源，不伪造 OHLC

必须全程脱机，无任何外部网络依赖，Exit Code 0。
"""

import sys
import os
import time
from unittest.mock import patch, MagicMock
import pandas as pd
import numpy as np

# 设置标准输出编码为 UTF-8
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# 添加根目录至 sys.path
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from core_engine.stock_data_service import (
    StockCooldownManager,
    StockDataFetchError,
    cooldown_manager,
    get_stock_profile,
    get_stock_price_data,
    get_stock_statements,
    get_stock_news,
    get_local_stock_price_fallback
)
from company_tab import (
    extract_multi_period_statements,
    extract_single_quarter_pnl,
    fetch_company_data
)

def test_case_1_profile_fail_history_success():
    """Case 1: 公司资料失败、行情成功 -> 行情和技术图正常展示"""
    print("\n--- [CASE 1: 公司资料失败、行情成功] ---")
    cooldown_manager.reset()
    
    mock_price_df = pd.DataFrame({
        "Open": [100.0, 102.0, 105.0],
        "High": [103.0, 106.0, 108.0],
        "Low": [99.0, 101.0, 104.0],
        "Close": [102.0, 105.0, 107.5],
        "Volume": [1000000, 1200000, 1500000]
    }, index=pd.date_range("2026-09-01", periods=3))
    
    with patch("core_engine.stock_data_service._raw_fetch_stock_profile", side_effect=StockDataFetchError("401 Unauthorized", status_code=401)), \
         patch("core_engine.stock_data_service._raw_fetch_stock_history", return_value=mock_price_df):
        
        prof = get_stock_profile("TEST_SYM")
        df, meta = get_stock_price_data("TEST_SYM")
        
        assert prof["status"] == "FAILED", f"Profile status should be FAILED, got {prof['status']}"
        assert "401" in prof["technical_details"], "Technical details should record 401"
        assert not df.empty, "Price DataFrame should NOT be empty"
        assert meta["status"] == "SUCCESS", f"Price meta status should be SUCCESS, got {meta['status']}"
        assert len(df) == 3, f"Expected 3 price rows, got {len(df)}"
        print("  ✓ 公司资料受阻已优雅降级并记录 401 诊断信息")
        print("  ✓ 行情数据独立获取成功，未被资料缺失一票否决")

def test_case_2_profile_fail_statements_success():
    """Case 2: 公司资料失败、财报成功 -> 财报正常展示"""
    print("\n--- [CASE 2: 公司资料失败、财报成功] ---")
    cooldown_manager.reset()
    
    mock_dates = ["2026-06-30", "2026-03-31"]
    mock_inc = pd.DataFrame({
        mock_dates[0]: [30000000000.0, 15000000000.0],
        mock_dates[1]: [26000000000.0, 13000000000.0]
    }, index=["Total Revenue", "Operating Income"])
    
    mock_bs = pd.DataFrame({
        mock_dates[0]: [50000000000.0, 10000000000.0],
        mock_dates[1]: [45000000000.0, 10000000000.0]
    }, index=["Cash Cash Equivalents And Short Term Investments", "Total Debt"])
    
    mock_statements = {
        "q_inc": mock_inc, "a_inc": pd.DataFrame(),
        "q_bs": mock_bs, "a_bs": pd.DataFrame(),
        "q_cf": pd.DataFrame(), "a_cf": pd.DataFrame()
    }
    
    with patch("core_engine.stock_data_service._raw_fetch_stock_profile", side_effect=StockDataFetchError("Connection Timeout")), \
         patch("core_engine.stock_data_service._raw_fetch_stock_statements", return_value=mock_statements), \
         patch("core_engine.stock_data_service._raw_fetch_stock_news", return_value=[]):
        
        data = fetch_company_data("TEST_SYM")
        
        assert data["profile_status"] == "FAILED", "Profile status should be FAILED"
        assert data["company_name"] == "TEST_SYM", f"Company name should fall back to Ticker, got {data['company_name']}"
        assert data["statements_dict"] is not None and len(data["statements_dict"]) > 0, "Statements dict should not be empty"
        assert not data["statements_dict"]["q_summary"].empty, "Quarterly financial summary should be parsed successfully"
        print("  ✓ 资料缺失时标题安全回退至 Ticker (TEST_SYM)")
        print(f"  ✓ 财报数据成功解析: {len(data['statements_dict']['q_summary'])} 项指标透视正常生成")

def test_case_3_single_statement_failure_resilience():
    """Case 3: 三张表中一张失败 (如利润表故意置空) -> 资产负债表与现金流表仍能展示"""
    print("\n--- [CASE 3: 利润表为空时打破一票否决] ---")
    mock_dates = ["2026-06-30", "2026-03-31"]
    
    # 利润表置空 (None 或 empty DataFrame)
    mock_inc_empty = pd.DataFrame()
    
    # 资产负债表存在真实 0 负债与大量现金
    mock_bs = pd.DataFrame({
        mock_dates[0]: [50000000000.0, 0.0, 40000000000.0],
        mock_dates[1]: [45000000000.0, 0.0, 38000000000.0]
    }, index=["Cash Cash Equivalents And Short Term Investments", "Total Debt", "Stockholders Equity"])
    
    # 现金流表存在数据
    mock_cf = pd.DataFrame({
        mock_dates[0]: [12000000000.0, 10000000000.0],
        mock_dates[1]: [11000000000.0, 9000000000.0]
    }, index=["Operating Cash Flow", "Free Cash Flow"])
    
    statements_input = {
        "q_inc": mock_inc_empty, "a_inc": pd.DataFrame(),
        "q_bs": mock_bs, "a_bs": pd.DataFrame(),
        "q_cf": mock_cf, "a_cf": pd.DataFrame()
    }
    
    res = extract_multi_period_statements(statements_input)
    assert res is not None and "q_summary" in res, "Should successfully return statements dict"
    df_q = res["q_summary"]
    assert not df_q.empty, "Summary DataFrame must NOT be empty even if income statement is missing!"
    
    # 验证营收为 N/A，但资产负债表与现金流表成功展示
    rev_row = df_q[df_q["指标 (Metric)"].str.contains("营业总收入")].iloc[0]
    assert rev_row[mock_dates[0]] == "N/A", f"Expected N/A for missing revenue, got {rev_row[mock_dates[0]]}"
    
    cash_row = df_q[df_q["指标 (Metric)"].str.contains("现金及短期投资")].iloc[0]
    assert "$50.00 B" in str(cash_row[mock_dates[0]]), f"Expected $50.00 B cash, got {cash_row[mock_dates[0]]}"
    
    # 验证真实 0 值不丢失为 N/A (Requirement 3)
    debt_row = df_q[df_q["指标 (Metric)"].str.contains("总负债")].iloc[0]
    assert "$0.00 B" in str(debt_row[mock_dates[0]]), f"True zero debt must show $0.00 B, got {debt_row[mock_dates[0]]}"
    
    print("  ✓ 利润表缺失时未触发整表放弃，资产负债表与现金流表正常生成")
    print(f"  ✓ 真实 0 负债正确展示为 $0.00 B，未被误判为 N/A 缺失")

def test_case_4_failure_cooldown_and_recovery():
    """Case 4: 首次失败记入冷却 -> 冷却过期后自动恢复探测并成功缓存"""
    print("\n--- [CASE 4: 冷却机制与时钟推进后恢复探测] ---")
    cd_mgr = StockCooldownManager()
    
    sym = "TEST_CD"
    domain = "profile"
    
    # 1. 首次失败 (401 封锁)
    cd_secs = cd_mgr.record_failure(sym, domain, "HTTP 401", status_code=401)
    assert cd_secs == 300.0, f"401 should trigger 300s cooldown, got {cd_secs}"
    
    # 2. 立即检查：应处于冷却中
    in_cd, remain, reason = cd_mgr.is_in_cooldown(sym, domain)
    assert in_cd is True, "Should be in cooldown immediately after 401"
    assert remain > 290.0, f"Remaining cooldown should be near 300s, got {remain}"
    print(f"  ✓ 首次 401 触发 300s 阶梯保护冷却 (剩余: {remain:.1f}s)")
    
    # 3. 模拟时钟推进 305 秒 (冷却过期)
    with patch("time.time", return_value=time.time() + 305.0):
        in_cd_after, remain_after, _ = cd_mgr.is_in_cooldown(sym, domain)
        assert in_cd_after is False, "Cooldown should have expired after 305 seconds"
        print("  ✓ 模拟时钟推移 305 秒后，冷却安全解除")
        
        # 4. 下一次请求探测成功，清除冷却
        cd_mgr.record_success(sym, domain)
        in_cd_final, _, _ = cd_mgr.is_in_cooldown(sym, domain)
        assert in_cd_final is False, "Record should be completely cleared upon success"
        print("  ✓ 成功请求后冷却记录彻底清除，恢复正常长效缓存状态")

def test_case_5_repeated_refresh_401_rate_limited():
    """Case 5: 连续刷新且持续 401 -> 请求次数受控，页面不崩溃"""
    print("\n--- [CASE 5: 连续刷新受控拦截 (防雪崩保护)] ---")
    cooldown_manager.reset()
    
    fetch_counter = {"raw_calls": 0}
    def mock_failing_fetch(symbol):
        fetch_counter["raw_calls"] += 1
        raise StockDataFetchError("HTTP 401 Unauthorized", status_code=401)
        
    with patch("core_engine.stock_data_service._raw_fetch_stock_profile", side_effect=mock_failing_fetch):
        # 模拟连续刷新 10 次
        for i in range(10):
            res = get_stock_profile("STRESS_TEST")
            assert res["status"] in ["FAILED", "IN_COOLDOWN"], f"Unexpected status {res['status']}"
            
        # 验证：底层上游探测只被调用了 1 次，其余 9 次全部被内存冷却拦截，未轰炸上游
        assert fetch_counter["raw_calls"] == 1, f"Expected exactly 1 raw upstream call, got {fetch_counter['raw_calls']}"
        print(f"  ✓ 连续 10 次刷新期间，上游物理请求仅触发 {fetch_counter['raw_calls']} 次")
        print(f"  ✓ 其余 9 次请求被内存冷却状态机秒级拦截，完全杜绝了频繁刷新加剧封禁")

def test_case_6_local_offline_price_fallback():
    """Case 6: 仅有本地收盘价 (NVDA 离线兜底) -> 展示带日期的历史折线，不伪造实时价格或 K 线"""
    print("\n--- [CASE 6: NVDA 本地离线主数据集兜底与真实性约束] ---")
    cooldown_manager.reset()
    
    # 模拟上游完全无法访问 (抛出异常)
    with patch("core_engine.stock_data_service._raw_fetch_stock_history", side_effect=StockDataFetchError("Network Blocked", status_code=401)):
        df, meta = get_stock_price_data("NVDA", period="5y")
        
        assert not df.empty, "Local fallback DataFrame for NVDA must NOT be empty"
        assert meta["is_local_fallback"] is True, "Meta must flag is_local_fallback as True"
        assert meta["is_close_only"] is True, "Meta must strictly flag is_close_only as True"
        assert "smh_constituents_local.csv" in meta["source_file"], f"Expected smh file, got {meta['source_file']}"
        assert meta["last_date"] == "2026-09-11", f"Expected last_date 2026-09-11, got {meta['last_date']}"
        
        # 验证数据结构：必须只有 Date 和 Close，严禁伪造 Open, High, Low
        cols = df.columns.tolist()
        assert "Date" in cols and "Close" in cols, f"DataFrame must contain Date and Close, got {cols}"
        assert "Open" not in cols and "High" not in cols, "MUST NOT fabricate OHLC candles from close-only series!"
        
        # 验证价格标签与真实性约束
        assert "非实时" in meta["price_type"], "Price type label must explicitly state non-realtime"
        print(f"  ✓ 成功从 {meta['source_file']} 读取 NVDA 离线历史序列 ({len(df)} 交易日)")
        print(f"  ✓ 严格遵循真实性红线：仅包含收盘价序列，未伪造 OHLC K线，标明截至 {meta['last_date']}")

def main():
    print("==================================================================")
    print("开始执行个股高可用与容错降级行为实证测试 (Offline Test Suite)")
    print("==================================================================")
    
    try:
        test_case_1_profile_fail_history_success()
        test_case_2_profile_fail_statements_success()
        test_case_3_single_statement_failure_resilience()
        test_case_4_failure_cooldown_and_recovery()
        test_case_5_repeated_refresh_401_rate_limited()
        test_case_6_local_offline_price_fallback()
        
        print("\n==================================================================")
        print("🎉 ALL 6 BEHAVIORAL VERIFICATION TESTS PASSED! (Exit Code: 0)")
        print("==================================================================")
        return 0
    except AssertionError as e:
        print(f"\n❌ 断言失败: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"\n❌ 未捕获异常: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
