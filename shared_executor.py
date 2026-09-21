import pandas as pd
import numpy as np
from typing import List, Dict, Any
from true_accounting import UnitizedAccount
import uuid

class SharedExecutor:
    """
    通用执行引擎。
    管理交易日循环、待执行订单排队、资金流顺序、费用及延迟成交逻辑。
    将策略业务逻辑与 UnitizedAccount 彻底隔离。
    """
    def __init__(self, acc: UnitizedAccount, fee_rate: float = 0.0, execution_mode: str = 'NEXT_CLOSE', account_type: str = 'strat'):
        if execution_mode not in ['NEXT_OPEN', 'NEXT_CLOSE']:
            raise ValueError("execution_mode 必须是 'NEXT_OPEN' 或 'NEXT_CLOSE'")
            
        self.acc = acc
        self.fee_rate = fee_rate
        self.execution_mode = execution_mode
        self.account_type = account_type
        
        self.pending_orders = [] # 待执行订单队列
        self.orders_history = [] # 历史订单记录
        self.fills = [] # 实际成交明细
        self.cashflows = [] # 资金流记录
        
        self.last_sell_p = None
        self.last_sell_date = None
        self.last_buy_p = None
        self.last_buy_date = None
        
        # 为了处理挂起的 DCA
        self.pending_cash = 0.0
        
        self.daily_states = []

    def _generate_id(self):
        return str(uuid.uuid4())[:8]

    def step(self, dt: pd.Timestamp, p_open: float, p_close: float, dca_amount: float = 0.0):
        """
        每日循环步进。遵循严格时序。
        """
        is_p_close_valid = pd.notna(p_close) and p_close > 0
        is_p_open_valid = pd.notna(p_open) and p_open > 0
        
        # 确定当期估值价
        valuation_price = p_close if is_p_close_valid else None
        valuation_stale = False
        if valuation_price is None:
            # 尝试使用最后有效估值价进行暂估展示
            if len(self.daily_states) > 0:
                valuation_price = self.daily_states[-1]['unit_nav'] # 这里暂时用最后的单价？不对，应该是最后有效资产价格
                # Wait, UnitizedAccount 需要 current_price
                # 我们应当让 acc 记住上一次的有效价格
            valuation_stale = True

        # 1. 尝试执行 NEXT_OPEN 订单
        if self.execution_mode == 'NEXT_OPEN' and len(self.pending_orders) > 0:
            if is_p_open_valid:
                self._execute_orders(dt, p_open, 'NEXT_OPEN')
            else:
                # 缺价保留在队列
                pass

        # 2. 处理资金流 (DCA)
        # 将新资金计入 pending_cash
        if dca_amount > 0:
            flow_id = f"cf_{self._generate_id()}"
            self.cashflows.append({
                'flow_id': flow_id,
                'planned_dt': dt.strftime('%Y-%m-%d'),
                'actual_dt': None,
                'amount': dca_amount,
                'status': 'PENDING'
            })
            self.pending_cash += dca_amount

        # 处理 pending_cash 注入
        if self.pending_cash > 0:
            if valuation_stale:
                # 严禁使用暂估价申购份额，挂起
                pass
            else:
                self.acc.inject_cash(self.pending_cash, dt, p_close)
                # 更新 cashflows 状态
                for cf in self.cashflows:
                    if cf['status'] == 'PENDING':
                        cf['status'] = 'COMPLETED'
                        cf['actual_dt'] = dt.strftime('%Y-%m-%d')
                self.pending_cash = 0.0

        # 3. 尝试执行 NEXT_CLOSE 订单
        if self.execution_mode == 'NEXT_CLOSE' and len(self.pending_orders) > 0:
            if is_p_close_valid:
                self._execute_orders(dt, p_close, 'NEXT_CLOSE')
            else:
                pass

        # 4. 当期估值与记录
        if valuation_stale:
            # 使用上一个交易日的 NAV 和 Equity 暂估
            last_record = self.acc.history[-1] if len(self.acc.history) > 0 else None
            if last_record:
                current_shares = self.acc.shares
                current_cash = self.acc.cash
                current_units = self.acc.units
                stale_nav = last_record['Unit_NAV']
                stale_equity = current_units * stale_nav
                
                self.daily_states.append({
                    'date': dt.strftime('%Y-%m-%d'),
                    'shares': current_shares,
                    'cash': current_cash,
                    'units': current_units,
                    'unit_nav': stale_nav,
                    'equity': stale_equity,
                    'type': self.account_type,
                    'valuation_quality': 'stale'
                })
            else:
                # 初始化第一天就缺价
                self.daily_states.append({
                    'date': dt.strftime('%Y-%m-%d'),
                    'shares': 0.0,
                    'cash': 0.0,
                    'units': 0.0,
                    'unit_nav': 1.0,
                    'equity': 0.0,
                    'type': self.account_type,
                    'valuation_quality': 'stale'
                })
        else:
            self.acc.calculate_nav(p_close)
            self.acc.record_daily_state(dt, p_close)
            last_state = self.acc.history[-1]
            self.daily_states.append({
                'date': dt.strftime('%Y-%m-%d'),
                'shares': last_state['Shares'],
                'cash': last_state['Cash'],
                'units': last_state['Units'],
                'unit_nav': last_state['Unit_NAV'],
                'equity': last_state['Total_Asset'],
                'type': self.account_type,
                'valuation_quality': 'good'
            })

    def _execute_orders(self, dt: pd.Timestamp, execute_price: float, mode: str):
        remaining_orders = []
        for order in self.pending_orders:
            if order['status'] != 'PENDING':
                continue
                
            target_pos = order['target']
            total_asset = self.acc.shares * execute_price + self.acc.cash
            target_value = total_asset * target_pos
            current_value = self.acc.shares * execute_price
            
            value_delta = target_value - current_value
            shares_delta = value_delta / execute_price
            
            if abs(shares_delta) > 1e-6:
                actual_shares_delta = self.acc.execute_trade(execute_price, shares_delta, self.fee_rate)
                fee = abs(actual_shares_delta * execute_price) * self.fee_rate
                
                direction = 'BUY' if actual_shares_delta > 0 else 'SELL'
                fill_id = f"fill_{self._generate_id()}"
                
                self.fills.append({
                    'fill_id': fill_id,
                    'order_id': order['order_id'],
                    'dt': dt.strftime('%Y-%m-%d'),
                    'price': execute_price,
                    'signed_shares': actual_shares_delta,
                    'fee': fee,
                    'direction': direction
                })
                
                if direction == 'SELL':
                    self.last_sell_p = execute_price
                    self.last_sell_date = dt
                elif direction == 'BUY':
                    self.last_buy_p = execute_price
                    self.last_buy_date = dt
            
            order['status'] = 'FILLED'
            order['actual_dt'] = dt.strftime('%Y-%m-%d')
            self.orders_history.append(order)
            
        self.pending_orders = remaining_orders

    def submit_order(self, target_position: float, reason: str, dt: pd.Timestamp):
        """
        提交目标仓位订单意图
        """
        # 取消之前所有的 pending 订单（同一时间只能有一个最终仓位目标）
        for o in self.pending_orders:
            o['status'] = 'CANCELLED'
            self.orders_history.append(o)
        self.pending_orders.clear()
        
        order_id = f"ord_{self._generate_id()}"
        order = {
            'order_id': order_id,
            'status': 'PENDING',
            'submit_dt': dt.strftime('%Y-%m-%d'),
            'planned_dt': None, # Depends on execution_mode
            'target': target_position,
            'reason': reason,
            'validity': 'GTC'
        }
        self.pending_orders.append(order)

    def get_state(self) -> Dict[str, Any]:
        """提取可序列化的内部执行状态"""
        return {
            'pending_orders': self.pending_orders,
            'orders_history': self.orders_history,
            'fills': self.fills,
            'cashflows': self.cashflows,
            'last_sell_p': self.last_sell_p,
            'last_sell_date': self.last_sell_date.isoformat() if self.last_sell_date else None,
            'last_buy_p': self.last_buy_p,
            'last_buy_date': self.last_buy_date.isoformat() if self.last_buy_date else None,
            'pending_cash': self.pending_cash,
            'daily_states': self.daily_states,
            'account_state': {
                'shares': self.acc.shares,
                'cash': self.acc.cash,
                'units': self.acc.units,
                'unit_nav': self.acc.unit_nav,
                'is_initialized': self.acc.is_initialized,
                'history': self.acc.history,
                'cash_flows': [(d.isoformat(), a) for d, a in self.acc.cash_flows]
            }
        }
        
    def restore_state(self, state: Dict[str, Any]):
        """从状态恢复执行器"""
        self.pending_orders = state['pending_orders']
        self.orders_history = state['orders_history']
        self.fills = state['fills']
        self.cashflows = state['cashflows']
        self.last_sell_p = state['last_sell_p']
        self.last_sell_date = pd.Timestamp(state['last_sell_date']) if state['last_sell_date'] else None
        self.last_buy_p = state['last_buy_p']
        self.last_buy_date = pd.Timestamp(state['last_buy_date']) if state['last_buy_date'] else None
        self.pending_cash = state['pending_cash']
        self.daily_states = state['daily_states']
        
        acc_st = state['account_state']
        self.acc.shares = acc_st['shares']
        self.acc.cash = acc_st['cash']
        self.acc.units = acc_st['units']
        self.acc.unit_nav = acc_st['unit_nav']
        self.acc.is_initialized = acc_st['is_initialized']
        self.acc.history = acc_st['history']
        self.acc.cash_flows = [(pd.Timestamp(d), a) for d, a in acc_st['cash_flows']]
