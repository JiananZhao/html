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
        
        # 为了缺价时暂估
        self.last_valid_price = None
        
        self.daily_states = []

    def _generate_id(self):
        return str(uuid.uuid4())[:8]

    def step(self, dt: pd.Timestamp, p_open: float, p_close: float, dca_amount: float = 0.0):
        """
        每日循环步进。遵循严格时序。
        """
        is_p_close_valid = pd.notna(p_close) and p_close > 0
        is_p_open_valid = pd.notna(p_open) and p_open > 0
        
        if is_p_close_valid:
            self.last_valid_price = p_close
            
        valuation_price = p_close if is_p_close_valid else None
        valuation_stale = (valuation_price is None)

        # 1. 计划外部资金流 (DCA)
        if dca_amount > 0:
            flow_id = f"cf_{self.account_type}_{dt.strftime('%Y%m%d')}"
            # Deduplicate: Only append if this flow_id is not already PENDING or COMPLETED
            if not any(cf['flow_id'] == flow_id for cf in self.cashflows):
                self.cashflows.append({
                    'flow_id': flow_id,
                    'planned_dt': dt.strftime('%Y-%m-%d'),
                    'actual_dt': None,
                    'amount': dca_amount,
                    'status': 'PENDING',
                    'reason': 'Scheduled DCA'
                })
                self.pending_cash += dca_amount

        # 2. 执行模型路由
        if self.execution_mode == 'NEXT_OPEN':
            # NEXT_OPEN: 开盘价有效时 -> 按开盘价入金 -> 执行未决订单 -> 收盘估值
            if is_p_open_valid:
                if self.pending_cash > 0:
                    self.acc.inject_cash(self.pending_cash, dt, p_open)
                    for cf in self.cashflows:
                        if cf['status'] in ['PENDING', 'DELAYED_DUE_TO_MISSING_PRICE']:
                            cf['status'] = 'COMPLETED'
                            cf['actual_dt'] = dt.strftime('%Y-%m-%d')
                    self.pending_cash = 0.0
                    
                if len(self.pending_orders) > 0:
                    self._execute_orders(dt, p_open, 'NEXT_OPEN')
            else:
                if self.pending_cash > 0:
                    for cf in self.cashflows:
                        if cf['status'] == 'PENDING':
                            cf['status'] = 'DELAYED_DUE_TO_MISSING_PRICE'

        elif self.execution_mode == 'NEXT_CLOSE':
            # NEXT_CLOSE: 收盘价有效时 -> 按收盘价入金 -> 执行未决订单 -> 收盘估值
            if is_p_close_valid:
                if self.pending_cash > 0:
                    self.acc.inject_cash(self.pending_cash, dt, p_close)
                    for cf in self.cashflows:
                        if cf['status'] in ['PENDING', 'DELAYED_DUE_TO_MISSING_PRICE']:
                            cf['status'] = 'COMPLETED'
                            cf['actual_dt'] = dt.strftime('%Y-%m-%d')
                    self.pending_cash = 0.0
                    
                if len(self.pending_orders) > 0:
                    self._execute_orders(dt, p_close, 'NEXT_CLOSE')
            else:
                if self.pending_cash > 0:
                    for cf in self.cashflows:
                        if cf['status'] == 'PENDING':
                            cf['status'] = 'DELAYED_DUE_TO_MISSING_PRICE'

        # 3. 收盘估值与记录
        if valuation_stale:
            current_shares = self.acc.shares
            current_cash = self.acc.cash
            current_units = self.acc.units
            
            if self.last_valid_price is not None:
                stale_equity = current_shares * self.last_valid_price + current_cash
            else:
                # 极端边界：如果没有有效收盘价，但是有开盘成交或者初始资金，不能强行估值为 0。
                # 尝试用开盘价暂估，如果也没有，保留现金价值。
                fallback_price = p_open if is_p_open_valid else None
                if fallback_price is not None:
                    stale_equity = current_shares * fallback_price + current_cash
                else:
                    stale_equity = current_cash
                
            stale_nav = (stale_equity / current_units) if current_units > 0 else 1.0
            
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
        current_date_str = dt.strftime('%Y-%m-%d')
        for order in self.pending_orders:
            if order['status'] != 'PENDING':
                remaining_orders.append(order)
                continue
                
            if current_date_str <= order['submit_dt']:
                remaining_orders.append(order)
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
                fill_id = f"fill_{self.account_type}_{dt.strftime('%Y%m%d')}_{self._generate_id()[:4]}"
                
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
            if o['status'] == 'PENDING':
                o['status'] = 'CANCELLED'
                self.orders_history.append(o)
        self.pending_orders.clear()
        
        # 使用 account_type 和 date 构造确定性主键，实现防重入
        order_id = f"ord_{self.account_type}_{dt.strftime('%Y%m%d')}"
        
        # Deduplicate: 如果历史记录中已经提交过这笔订单，不再重复添加
        if any(o['order_id'] == order_id for o in self.orders_history):
            return

        order = {
            'order_id': order_id,
            'status': 'PENDING',
            'submit_dt': dt.strftime('%Y-%m-%d'),
            'planned_dt': None, # Depends on execution_mode
            'target': target_position,
            'reason': reason,
            'validity': 'GTC'
        }
        
        # 在 appending 之前，检查 pending_orders 是否已经有了，防止多次调用
        if not any(o['order_id'] == order_id for o in self.pending_orders):
            self.pending_orders.append(order)

    def get_state(self) -> Dict[str, Any]:
        """提取可序列化的内部执行状态"""
        return {
            'pending_orders': self.pending_orders,
            'cashflows': self.cashflows,
            'last_sell_p': self.last_sell_p,
            'last_sell_date': self.last_sell_date.isoformat() if self.last_sell_date else None,
            'last_buy_p': self.last_buy_p,
            'last_buy_date': self.last_buy_date.isoformat() if self.last_buy_date else None,
            'pending_cash': self.pending_cash,
            'last_valid_price': self.last_valid_price,
            'account_state': self.acc.get_state()
        }
        
    def restore_state(self, state: Dict[str, Any]):
        """从状态恢复执行器"""
        self.pending_orders = state['pending_orders']
        self.cashflows = state.get('cashflows', [])
        # We explicitly DO NOT restore history from JSON, they remain empty lists in this instance.
        self.last_sell_p = state['last_sell_p']
        self.last_sell_date = pd.Timestamp(state['last_sell_date']) if state['last_sell_date'] else None
        self.last_buy_p = state['last_buy_p']
        self.last_buy_date = pd.Timestamp(state['last_buy_date']) if state['last_buy_date'] else None
        self.pending_cash = state['pending_cash']
        self.last_valid_price = state.get('last_valid_price', None)
        
        self.acc.load_state(state['account_state'])
