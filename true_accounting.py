import numpy as np
import pandas as pd
from datetime import datetime
from scipy.optimize import newton

class UnitizedAccount:
    """
    公募基金级单位化净值账本。
    严格维护 shares, cash, units, unit_nav 四个状态变量。
    遵循恒等式：Total Asset = shares * P + cash
    NAV = Total Asset / units
    """
    def __init__(self, initial_cash: float = 0.0):
        self.shares = 0.0
        self.cash = 0.0
        self.units = 0.0
        self.unit_nav = 1.0 # 初始净值固定为 1.0
        self.is_initialized = False
        
        self.history = [] # 记录每日状态字典
        self.cash_flows = [] # 记录投资者外部出入金用于 XIRR 计算: (date, amount_inflow_to_account)
        
        if initial_cash > 0:
            self.inject_cash(initial_cash, pd.Timestamp('1970-01-01')) # 初始化现金时不改变净值
            self.cash_flows = [] # 清空初始的虚拟历史以配合真实的业务逻辑记录
            
    def inject_cash(self, amount: float, date: pd.Timestamp):
        """处理预定外部资金流 (增加现金与份额，NAV保持绝对不变)"""
        if amount <= 0: return
        
        if not self.is_initialized:
            # 首次注资，NAV=1.0
            self.cash += amount
            self.units += amount
            self.unit_nav = 1.0
            self.is_initialized = True
        else:
            # 根据当前 NAV 增发份额
            if self.unit_nav <= 0:
                raise ValueError(f"严重异常：单位净值 <= 0 ({self.unit_nav})，无法进行申购。")
            delta_units = amount / self.unit_nav
            self.cash += amount
            self.units += delta_units
            
        self.cash_flows.append((date, amount))
        
    def withdraw_cash(self, amount: float, date: pd.Timestamp):
        """处理外部提款 (销毁份额，扣减现金，NAV不变)"""
        if amount <= 0: return
        if amount > self.cash:
            raise ValueError(f"异常：提款金额 {amount} 大于可用现金 {self.cash}")
            
        if self.unit_nav <= 0:
            raise ValueError(f"严重异常：单位净值 <= 0 ({self.unit_nav})，无法进行赎回。")
            
        delta_units = amount / self.unit_nav
        self.cash -= amount
        self.units -= delta_units
        if self.units < 0:
            self.units = 0.0 # 精度修正
            
        self.cash_flows.append((date, -amount)) # 提款对账户是资金流出
        
    def execute_trade(self, price: float, target_shares_delta: float, fee_rate: float = 0.001):
        """
        执行待定订单。
        target_shares_delta: >0 买入，<0 卖出。
        """
        if target_shares_delta == 0:
            return 0.0
            
        trade_value = abs(target_shares_delta) * price
        fee = trade_value * fee_rate
        
        if target_shares_delta > 0: # 买入
            total_cost = trade_value + fee
            if total_cost > self.cash:
                # 现金不足，自动按可用现金按比例降级买入 (保留一点点防溢出)
                actual_cost = self.cash
                trade_value_allowed = actual_cost / (1 + fee_rate)
                target_shares_delta = trade_value_allowed / price
                fee = trade_value_allowed * fee_rate
                
            self.cash -= (trade_value_allowed + fee) if 'trade_value_allowed' in locals() else (trade_value + fee)
            self.shares += target_shares_delta
            return target_shares_delta
            
        else: # 卖出
            # 不能卖出超过持有的数量
            if abs(target_shares_delta) > self.shares:
                target_shares_delta = -self.shares
                trade_value = abs(target_shares_delta) * price
                fee = trade_value * fee_rate
                
            self.shares += target_shares_delta # target_shares_delta 是负数
            self.cash += (trade_value - fee)
            return target_shares_delta

    def calculate_nav(self, current_price: float):
        """计算 T 或 T+1 收盘时的净值，并更新内部状态"""
        if not self.is_initialized or self.units == 0:
            return 1.0
            
        # 允许极端情况，只要不违背数学运算
        total_asset = self.shares * current_price + self.cash
        self.unit_nav = total_asset / self.units
        return self.unit_nav
        
    def record_daily_state(self, date: pd.Timestamp, current_price: float, notes: str = ""):
        nav = self.calculate_nav(current_price)
        total_asset = self.shares * current_price + self.cash
        self.history.append({
            'Date': date,
            'Price': current_price,
            'Shares': self.shares,
            'Cash': self.cash,
            'Total_Asset': total_asset,
            'Units': self.units,
            'Unit_NAV': nav,
            'Notes': notes
        })
        
    def get_history_df(self) -> pd.DataFrame:
        if not self.history:
            return pd.DataFrame()
        df = pd.DataFrame(self.history)
        df.set_index('Date', inplace=True)
        return df

def calculate_xirr(cash_flows, final_value, final_date):
    """
    计算内部收益率 (XIRR)。
    cash_flows: List of (date, amount_injected_into_account)
    amount_injected_into_account 为正代表投资者投入本金（从投资者钱包流出，内部计算时记为负 cash flow）
    amount_injected_into_account 为负代表投资者提取资金（流入投资者钱包，记为正 cash flow）
    final_value: 期末资产总值（代表投资者最终可以拿回的钱，记为正 cash flow）
    """
    if not cash_flows:
        return np.nan
        
    # 将内部账户资金流转为投资者视角的现金流
    # 投资者投入 = 现金流出 (-)，投资者提取/期末清算 = 现金流入 (+)
    cf_dates = [cf[0] for cf in cash_flows]
    cf_amounts = [-cf[1] for cf in cash_flows] 
    
    # 加入期末价值
    cf_dates.append(final_date)
    cf_amounts.append(final_value)
    
    # 检查是否有正有负
    if max(cf_amounts) <= 0 or min(cf_amounts) >= 0:
        return np.nan # 无法计算
        
    # XIRR 计算公式求根
    def xnpv(rate):
        if rate <= -1.0:
            return float('inf')
        result = 0.0
        for d, a in zip(cf_dates, cf_amounts):
            # 将天数差转为年
            days = (d - cf_dates[0]).days
            result += a / ((1.0 + rate) ** (days / 365.0))
        return result
        
    try:
        # 使用牛顿法寻找零点
        res = newton(xnpv, 0.1, tol=1e-5, maxiter=100)
        return res
    except:
        return np.nan
