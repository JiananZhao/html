import pandas as pd
import numpy as np

class PhaseSpaceFilter:
    @staticmethod
    def compute_dynamics(df, price_col='close', ma_col='MA200', tau=100.0, vel_window=10, acc_window=5):
        """
        计算相空间动力学指标: q, q_dot, q_ddot, V_dot 和 Quadrant
        """
        # 广义位置 q: 相对偏离度
        df['q1'] = (df[price_col] - df[ma_col]) / (df[ma_col] + 1e-8) * 100.0
        
        # 广义速度 q_dot: 低通后向有限差分 (%/day)
        df['q1_dot'] = (df['q1'] - df['q1'].shift(vel_window)) / vel_window
        
        # 广义加速度 q_ddot: 二阶有限差分 (%/day^2)
        df['q1_ddot'] = (df['q1_dot'] - df['q1_dot'].shift(acc_window)) / acc_window
        
        # 相空间能量变化率代理指标: V_dot
        df['v_dot'] = df['q1_dot'] * (df['q1'] + tau * df['q1_ddot'])
        
        # 相平面四象限动力学标记
        df['Quadrant'] = 0
        df.loc[(df['q1'] >= 0) & (df['q1_dot'] >= 0), 'Quadrant'] = 1
        df.loc[(df['q1'] < 0) & (df['q1_dot'] >= 0), 'Quadrant'] = 2
        df.loc[(df['q1'] < 0) & (df['q1_dot'] < 0), 'Quadrant'] = 3
        df.loc[(df['q1'] >= 0) & (df['q1_dot'] < 0), 'Quadrant'] = 4
        
        return df

    @staticmethod
    def apply_hysteresis(df, raw_flags, min_days, price_step, is_top=False, price_col='close', date_col='date'):
        """
        迟滞波段去噪滤波 (Hysteresis & Cooldown)
        """
        final_flags = []
        last_dt = None
        last_p = -1 if is_top else 999999
        for i in range(len(df)):
            dt = df[date_col].iloc[i]
            p = df[price_col].iloc[i]
            flg = raw_flags.iloc[i]
            act = False
            if flg:
                try:
                    # handling datetime string or timestamp
                    dt_parsed = pd.to_datetime(dt)
                    last_dt_parsed = pd.to_datetime(last_dt) if last_dt else None
                    days = (dt_parsed - last_dt_parsed).days if last_dt_parsed else 999
                except:
                    days = 999
                
                if is_top:
                    if days > min_days or p > last_p * (1 + price_step):
                        act = True
                        last_dt = dt
                        last_p = p
                else:
                    if days > min_days or p < last_p * (1 - price_step):
                        act = True
                        last_dt = dt
                        last_p = p
            final_flags.append(act)
        return pd.Series(final_flags, index=df.index)
