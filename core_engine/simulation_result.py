import pandas as pd
from dataclasses import dataclass
from typing import List, Dict, Any
import numpy as np

@dataclass
class SimulationResult:
    """
    统一的数据契约对象 (Data Contract)
    作为底层引擎计算结果向前端、导出脚本交付的唯一凭证。
    严禁调用方在此对象外自发重建交易历史或二次核算净值。
    """
    features: pd.DataFrame
    signals: pd.DataFrame
    orders: List[Dict[str, Any]]
    fills: List[Dict[str, Any]]
    cashflows: List[Dict[str, Any]]
    daily_accounts: pd.DataFrame
    metrics: Dict[str, Any]
    metadata: Dict[str, Any]

    def validate(self, tolerance: float = 1e-6):
        """
        验证结果数据的参照完整性与时序账本一致性
        """
        # 1. 验证 daily_accounts 结构与唯一性
        req_account_cols = ['date', 'shares', 'cash', 'units', 'unit_nav', 'equity', 'type', 'valuation_quality']
        missing_acc_cols = [c for c in req_account_cols if c not in self.daily_accounts.columns]
        if missing_acc_cols:
            raise ValueError(f"daily_accounts 缺失必要列: {missing_acc_cols}")
        
        # date + type 必须唯一
        dup_keys = self.daily_accounts.duplicated(subset=['date', 'type'])
        if dup_keys.any():
            raise ValueError("daily_accounts 中存在重复的 (date, type) 联合主键！")

        # 2. 验证时序单调性
        # 对每一种 type 的账户，时间必须单调递增
        for acc_type, group in self.daily_accounts.groupby('type'):
            dates = pd.to_datetime(group['date'])
            if not dates.is_monotonic_increasing:
                raise ValueError(f"账户类型 '{acc_type}' 的时间序列不严格单调递增！")

        # 3. 验证 orders 与 fills 的引用完整性与结构
        req_order_keys = {'order_id', 'status', 'submit_dt', 'planned_dt', 'target', 'reason', 'validity'}
        order_ids = set()
        for o in self.orders:
            missing_keys = req_order_keys - set(o.keys())
            if missing_keys:
                raise ValueError(f"Order 缺少必填字段: {missing_keys}, Order: {o}")
            order_ids.add(o['order_id'])

        req_fill_keys = {'fill_id', 'order_id', 'dt', 'price', 'signed_shares', 'fee', 'direction'}
        for f in self.fills:
            missing_keys = req_fill_keys - set(f.keys())
            if missing_keys:
                raise ValueError(f"Fill 缺少必填字段: {missing_keys}, Fill: {f}")
            if f['order_id'] not in order_ids:
                raise ValueError(f"Fill 引用了不存在的 order_id: {f['order_id']}")

        # 4. 验证 cashflows 结构
        req_cf_keys = {'flow_id', 'planned_dt', 'actual_dt', 'amount', 'status'}
        for cf in self.cashflows:
            missing_keys = req_cf_keys - set(cf.keys())
            if missing_keys:
                raise ValueError(f"Cashflow 缺少必填字段: {missing_keys}, Cashflow: {cf}")

        # 5. 验证账本数学约束
        # units * unit_nav 应该非常接近 equity (容许浮点误差)
        eq_diff = np.abs(self.daily_accounts['units'] * self.daily_accounts['unit_nav'] - self.daily_accounts['equity'])
        if (eq_diff > tolerance).any():
            bad_idx = self.daily_accounts[eq_diff > tolerance].index
            raise ValueError(f"daily_accounts 中 units * unit_nav 与 equity 不匹配 (超过容差 {tolerance})，异常行:\n{self.daily_accounts.loc[bad_idx]}")

        return True
