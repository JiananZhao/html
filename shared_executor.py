import pandas as pd
from true_accounting import UnitizedAccount

class SharedExecutor:
    """
    通用执行引擎。
    管理交易日循环、待执行订单排队、资金流顺序、费用及 NEXT_CLOSE 延迟成交逻辑。
    将策略业务逻辑与 UnitizedAccount 彻底隔离。
    """
    def __init__(self, acc: UnitizedAccount, fee_rate: float = 0.0):
        self.acc = acc
        self.fee_rate = fee_rate
        self.pending_target_pos = None # 取值范围 0.0 到 1.0，代表目标仓位
        self.pending_reason = ""
        
        self.last_sell_p = None
        self.last_sell_date = None
        self.last_buy_p = None
        self.last_buy_date = None
        
        self.trades = [] # 记录实际成交明细
        
    def step(self, dt: pd.Timestamp, p_open: float, p_close: float, dca_amount: float = 0.0):
        """
        每日循环步进。
        遵循严格时序：
        1. 当期估值
        2. 处理资金流 (DCA)
        3. 执行旧订单 (按 p_close 或者 p_open，由调用方传入目标价格，一般宏观 ETF 用 p_close)
        4. 记录状态
        """
        # 为了兼容性，如果没有传入 p_close，则默认使用 p_open
        if p_close is None or pd.isna(p_close):
            p_close = p_open
            
        # 1. 当期估值
        self.acc.calculate_nav(p_close)
        
        # 2. 处理资金流
        if dca_amount > 0:
            self.acc.inject_cash(dca_amount, dt, p_close)
            
        # 3. 执行旧订单 (NEXT_CLOSE)
        if self.pending_target_pos is not None:
            # 计算需要达到目标仓位所需的 target_shares
            # Target Position = (Shares * Price) / (Shares * Price + Cash)
            # 因为可能在 DCA 之后，Total Asset 变了
            total_asset = self.acc.shares * p_close + self.acc.cash
            target_value = total_asset * self.pending_target_pos
            current_value = self.acc.shares * p_close
            
            value_delta = target_value - current_value
            shares_delta = value_delta / p_close
            
            # 允许浮点误差
            if abs(shares_delta) > 1e-6:
                actual_shares_delta = self.acc.execute_trade(p_close, shares_delta, self.fee_rate)
                
                # 记录成交
                action = 'BUY' if actual_shares_delta > 0 else 'SELL'
                self.trades.append({
                    'date': dt.strftime('%Y-%m-%d'),
                    'action': action,
                    'price': p_close,
                    'shares_delta': actual_shares_delta,
                    'reason': self.pending_reason
                })
                
                # 维护最新的已成交状态，供策略机器使用
                if action == 'SELL':
                    self.last_sell_p = p_close
                    self.last_sell_date = dt
                elif action == 'BUY':
                    self.last_buy_p = p_close
                    self.last_buy_date = dt
            
            # 订单已执行，清空
            self.pending_target_pos = None
            self.pending_reason = ""
            
            # 4. 扣费后重新估值
            self.acc.calculate_nav(p_close)
            
        # 5. 记录每日状态
        self.acc.record_daily_state(dt, p_close)
        
    def submit_order(self, target_position: float, reason: str):
        """
        策略状态机调用此接口提交订单意图。
        target_position: 目标仓位比例 (0.0=空仓, 1.0=满仓)
        """
        self.pending_target_pos = target_position
        self.pending_reason = reason
