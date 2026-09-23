# -*- coding: utf-8 -*-
"""
========================================================================================
ServiceNow (NOW) 单股反身性相空间动力学量化模型与微观雷达全流程引擎
========================================================================================
【核心量化目标与理论体系】
1. 形式同源理论升维（黄文政老师洞见）：
   - 将索罗斯反身性理论（Reflexivity Theory）从传统的零阶静态截面偏离度（位置 q），
     全面升维至拉格朗日相空间动力学 (q, q_dot)；
   - 状态位置 q：相对 200MA 的结构性累积偏离（广义势能坐标）；
   - 状态速度 q_dot：10日有限差分变化率，反映认知偏差与资金加速/减速（广义动能坐标）；
   - 广义加速度 q_ddot：5日二阶差分，刻画驱动外力边际枯竭；
   - 相空间能量变化率代理指标 V_dot：V_dot = q_dot * (q + tau * q_ddot)，刻画系统自激失稳与能量耗散分岔。
2. 六大维度完全解耦（Decoupled Observables）：
   - Dim 1: 广义位置状态 (q1 偏离度)
   - Dim 2: 广义速度状态 (q1_dot 变化率)
   - Dim 3: 系统稳定性与加速度 (q1_ddot & V_dot)
   - Dim 4: 资本稀释与内部人交易 (SBC & Insider Net Flow)
   - Dim 5: 微观资金流向与筹码异动 (CMF & Volume Ratio)
   - Dim 6: 宏观信用引力与金融条件 (HYG / BAA10Y / NFCI)
3. 真实两状态券商记账体系（True Brokerage Accounting）：
   - 严格追踪 strat_shares 与 strat_cash，杜绝虚假连乘（Phantom Compounding）；
   - 验证真实财富 Alpha > 0 与最大回撤显著收窄；
4. 100% 本地脱机闭环运行：
   - 严格从 now_ohlcv_local.csv, market_data_local.csv, now_sec_fundamentals_local.csv 读取。
========================================================================================
"""

import os
import sys
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates

from core_engine.simulation_result import SimulationResult
from shared_executor import SharedExecutor
from true_accounting import UnitizedAccount
from true_accounting import calculate_xirr

# 保证 Windows 控制台 UTF-8 输出正常
if sys.platform == 'win32':
    import io
    if sys.stdout and hasattr(sys.stdout, 'buffer'):
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 配置 Matplotlib 中文字体，严格杜绝未转义的 $ 符号，防止 LaTeX 乱码
plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'DejaVu Sans', 'Arial Unicode MS']
plt.rcParams['axes.unicode_minus'] = False

BASE_DIR = os.path.dirname(os.path.abspath(__file__))


def generate_trade_pairs(orders, sub_bt, ticker='NOW'):
    """从 SharedExecutor 的 orders_history 中提取买卖配对"""
    trade_pairs = []
    discretionary = [o for o in orders if o.get('reason') not in ("Standing Order / DCA", "Bench Standing Order / DCA")]
    
    for k in range(0, len(discretionary) - 1, 2):
        s_o = discretionary[k]
        b_o = discretionary[k+1]
        
        if s_o['target'] == 0.0 and b_o['target'] == 1.0:
            import pandas as pd
            s_dt = pd.to_datetime(s_o['actual_dt'] if s_o['actual_dt'] else s_o['submit_dt'])
            b_dt = pd.to_datetime(b_o['actual_dt'] if b_o['actual_dt'] else b_o['submit_dt'])
            
            s_p = sub_bt.loc[sub_bt['date'] == s_dt.strftime('%Y-%m-%d'), 'NOW'].values
            b_p = sub_bt.loc[sub_bt['date'] == b_dt.strftime('%Y-%m-%d'), 'NOW'].values
            
            s_p = s_p[0] if len(s_p) > 0 else 0
            b_p = b_p[0] if len(b_p) > 0 else 0
            
            if s_p > 0:
                p_drop = (b_p - s_p) / s_p * 100.0
            else:
                p_drop = 0.0
            
            trade_pairs.append({
                '波段轮次': len(trade_pairs) + 1,
                '卖出避险日期': s_dt.strftime('%Y-%m-%d'),
                '卖出逃顶价格': round(s_p, 2),
                '变现闲置现金(USD)': 0.0,
                '逃顶触发原因': s_o['reason'],
                '低位回补日期': b_dt.strftime('%Y-%m-%d'),
                '回补买入价格': round(b_p, 2),
                '买入持股数量': 0.0,
                '回补建仓原因': b_o['reason'],
                '逃顶回补差价空间(%)': round(p_drop, 2) * -1,
                '状态': '超额成功' if p_drop < 0 else '震荡平保'
            })
    return pd.DataFrame(trade_pairs)

class NOWReflexivityRadar:
    def __init__(self):
        self.ohlcv_file = os.path.join(BASE_DIR, "now_ohlcv_local.csv")
        self.macro_file = os.path.join(BASE_DIR, "market_data_local.csv")
        self.sec_file = os.path.join(BASE_DIR, "now_sec_fundamentals_local.csv")
        
        self.output_csv = os.path.join(BASE_DIR, "now_radar_local.csv")
        self.output_xlsx = os.path.join(BASE_DIR, "宏观反身性阿尔法模型_NOW单股微观雷达全周期对账表.xlsx")
        self.output_panoramic_png = os.path.join(BASE_DIR, "宏观反身性阿尔法模型_NOW微观雷达4层全景图谱.png")
        self.output_phase_png = os.path.join(BASE_DIR, "宏观反身性阿尔法模型_NOW相空间动力学相图.png")
        
        self.df = None
        self.df_bt = None
        self.trades = []
        self.perf_metrics = {}

    def load_and_preprocess(self):
        """100% 离线脱机加载本地日线行情、宏观指标与 SEC 基本面数据"""
        print("📂 正在加载本地主数据集 (100% 脱机优先闭环)...")
        if not os.path.exists(self.ohlcv_file):
            raise FileNotFoundError(f"缺少行情文件: {self.ohlcv_file}")
        if not os.path.exists(self.macro_file):
            raise FileNotFoundError(f"缺少宏观文件: {self.macro_file}")
        if not os.path.exists(self.sec_file):
            raise FileNotFoundError(f"缺少SEC基本面文件: {self.sec_file}")

        df_p = pd.read_csv(self.ohlcv_file)
        df_p['date'] = pd.to_datetime(df_p['date'])

        df_m = pd.read_csv(self.macro_file)
        df_m['date'] = pd.to_datetime(df_m['date']).dt.tz_localize(None)

        df_s = pd.read_csv(self.sec_file)
        df_s['date'] = pd.to_datetime(df_s['date'])

        df = pd.merge(df_p, df_m[['date', 'SPY', 'HYG', 'BAA10Y', 'NFCI', 'Real_Yield']], on='date', how='inner')
        df = pd.merge(df, df_s, on='date', how='left')
        df.rename(columns={'close': 'NOW'}, inplace=True)
        df = df.sort_values('date').reset_index(drop=True)

        print(f"✅ 成功合并数据，跨度从 {df['date'].iloc[0].strftime('%Y-%m-%d')} 到 {df['date'].iloc[-1].strftime('%Y-%m-%d')} (共 {len(df)} 个交易日)")
        self.df = df
        return df

    def compute_all_dimensions(self):
        """完全解耦计算 6 大独立维度、相空间变量与综合过热得分"""
        df = self.df
        print("⚙️ 正在计算相空间动力学 (q, q_dot, q_ddot, V_dot) 与 6 维解耦分位数...")

        # 1. 基础技术指标与均线系统
        df['MA10'] = df['NOW'].rolling(10).mean()
        df['MA20'] = df['NOW'].rolling(20).mean()
        df['MA50'] = df['NOW'].rolling(50).mean()
        df['MA200'] = df['NOW'].rolling(200).mean()
        df['Dist_200MA'] = (df['NOW'] - df['MA200']) / (df['MA200'] + 1e-8) * 100.0

        # 2. 宏观信用环境与流动性状态
        df['Macro_MA50'] = df['HYG'].rolling(50).mean()
        df['Macro_MA200'] = df['HYG'].rolling(200).mean()
        df['BAA_MA60'] = df['BAA10Y'].rolling(60).mean()
        df['BAA_Stress'] = df['BAA10Y'] > df['BAA_MA60']
        df['RY_Surge'] = (df['Real_Yield'] - df['Real_Yield'].rolling(60).min()) > 0.35

        # 3. 反身性认知偏差（Reflexive Gap）
        df['Price_Z'] = (df['NOW'] - df['NOW'].rolling(200).mean()) / (df['NOW'].rolling(200).std() + 1e-8)
        df['Macro_Z'] = (df['HYG'] - df['HYG'].rolling(200).mean()) / (df['HYG'].rolling(200).std() + 1e-8)
        roll_cov = df['Price_Z'].rolling(252).cov(df['Macro_Z'])
        roll_var = df['Macro_Z'].rolling(252).var()
        df['Dynamic_Beta'] = (roll_cov / (roll_var + 1e-8)).clip(lower=-2.0, upper=2.0)
        df['Expected_Price_Z'] = df['Macro_Z'] * df['Dynamic_Beta']
        df['Gap'] = df['Price_Z'] - df['Expected_Price_Z']
        df['Gap_Max_45'] = df['Gap'].rolling(45, min_periods=1).max()
        df['Gap_Upper'] = df['Gap'].expanding(min_periods=50).quantile(0.85)

        # 4 & 5. 黄文政拉格朗日相空间动力学 & 相平面四象限动力学标记
        from core_engine.phase_space import PhaseSpaceFilter
        df = PhaseSpaceFilter.compute_dynamics(df, price_col='NOW', ma_col='MA200', tau=100.0, vel_window=10, acc_window=5)

        # 6. 微观资金流向 (CMF 20) 与换手率
        # CLV = [(Close - Low) - (High - Close)] / (High - Low)
        high_low_range = df['high'] - df['low']
        high_low_range = high_low_range.replace(0, np.nan)
        clv = (2 * df['NOW'] - (df['high'] + df['low'])) / high_low_range
        clv = clv.fillna(0.0)
        vol_clv = clv * df['volume']
        df['CMF20'] = vol_clv.rolling(20).sum() / (df['volume'].rolling(20).sum() + 1e-8)
        df['Vol_Ratio50'] = df['volume'] / (df['volume'].rolling(50).mean() + 1e-8)

        # 7. 6 大独立解耦分位数转换 (0 ~ 100 Uniform 标定)
        import bisect
        def expanding_rank(s, min_periods=100):
            vals = s.values
            n = len(vals)
            res = np.full(n, np.nan)
            sorted_arr = []
            for i in range(n):
                v = vals[i]
                if np.isnan(v):
                    continue
                pos_left = bisect.bisect_left(sorted_arr, v)
                pos_right = bisect.bisect_right(sorted_arr, v)
                sorted_arr.insert(pos_right, v)
                N_t = len(sorted_arr)
                if N_t >= min_periods:
                    E_t = pos_right - pos_left + 1
                    res[i] = 100.0 * (pos_left + 0.5 * E_t) / N_t
            return pd.Series(res, index=s.index)

        # 维度 1: 势能位置
        df['Score_Dim1_Pos'] = expanding_rank(df['q1'])
        # 维度 2: 动能速度
        df['Score_Dim2_Vel'] = expanding_rank(df['q1_dot'])
        # 维度 3: 李雅普诺夫加速度
        df['Score_Dim3_Lyapunov'] = expanding_rank(df['v_dot'])
        # 维度 4: 资本稀释与高管减持
        insider_roll = df['insider_net_flow_m'].rolling(60).sum()
        shares_growth = df['diluted_shares_m'].pct_change(252)
        df['Score_Dim4_Capital'] = (
            expanding_rank(-insider_roll) * 0.6 + expanding_rank(shares_growth) * 0.4
        ).fillna(50.0)
        # 维度 5: 微观筹码与资金流向
        df['Score_Dim5_Liquidity'] = (
            expanding_rank(df['CMF20']) * 0.6 + expanding_rank(df['Vol_Ratio50']) * 0.4
        )
        # 维度 6: 宏观信用与金融条件收紧
        df['Score_Dim6_Macro'] = (
            expanding_rank(df['BAA10Y']) * 0.5 + expanding_rank(df['NFCI']) * 0.5
        )

        # 8. 综合反身性过热得分 (Composite Overheat Score)
        df['Composite_Score'] = (
            df['Score_Dim1_Pos'] * 0.25 +
            df['Score_Dim2_Vel'] * 0.20 +
            df['Score_Dim3_Lyapunov'] * 0.20 +
            df['Score_Dim4_Capital'] * 0.15 +
            df['Score_Dim6_Macro'] * 0.20
        )

        self.df = df
        return df

    def run_backtest(self, start_date='2013-06-01', initial_capital=10000.0, dca_monthly=1000.0):
        """
        真实券商记账体系模拟 (True Brokerage Accounting)
        严格维护两个账户状态：
          - strat_shares：当前持有的真实股数；
          - strat_cash：当前闲置的现金池（美元）。
        """
        print(f"📊 启动真实券商记账回测 (回测起点: {start_date}, 初始本金: ${initial_capital:,.0f}, 月定投: ${dca_monthly:,.0f})...")
        df = self.df
        df_bt = df[df['date'] >= start_date].copy().reset_index(drop=True)

        # -------------------------------------------------------------
        # 信号判定逻辑
        # -------------------------------------------------------------
        # 1. 反身性高位泡沫破裂卖出信号：
        #    - 过去 45 天内经历高认知偏差或综合高过热 (Gap > 85% 分位 或 Composite >= 70)
        #    - 年线偏离度仍在较高位置 (Dist_200MA > 12%)
        #    - 相空间跨入第四象限 (q1 >= 0 且 q1_dot < 0，动能衰竭转负)
        #    - 跌破 50 日均线 (close < MA50)
        #    - 宏观信用环境承压 (NFCI > -0.50 且 BAA10Y 处于扩张期)
        cond_bubble = (
            ((df_bt['Gap_Max_45'] > df_bt['Gap_Upper']) | (df_bt['Composite_Score'].rolling(30).max() >= 70.0)) &
            (df_bt['Dist_200MA'] > 12.0) &
            (df_bt['Quadrant'] == 4) &
            (df_bt['NOW'] < df_bt['MA50']) &
            (df_bt['NFCI'] > -0.50) &
            df_bt['BAA_Stress']
        )

        # 2. 宏观信用海啸 / 科技熊市卖出信号：
        #    - 高收益债跌破年线 (HYG < MA200)
        #    - 真实利率急速飙升 (RY_Surge) 且金融条件骤紧 (NFCI > -0.45)
        #    - 股价双均线破位 (close < MA50 且 close < MA200)
        macro_crisis = (
            (df_bt['HYG'] < df_bt['Macro_MA200']) &
            df_bt['RY_Surge'] &
            (df_bt['NFCI'] > -0.45)
        )
        cond_bear = macro_crisis & (df_bt['NOW'] < df_bt['MA50']) & (df_bt['NOW'] < df_bt['MA200'])

        # Execution signals are now tied directly to the robust Radar Triggers
        # which properly decouple individual stock crashes from macro dependencies.        # -------------------------------------------------------------
        # 核心解耦：客观雷达高信噪比观测信号层 (Pure High-SNR Observational Signals)
        # 第一性原理设计：
        # 1. 严格状态门禁 (Regime Gating): 彻底杜绝在牛市高位打“抄底”，杜绝在熊市深渊打“逃顶”！
        # 2. 动能拐点精确识别 (Inflection Trigger): 仅在相空间导数初次转正/转负时打点，拒绝缠绕！
        # 3. 迟滞波段去噪 (Hysteresis & Cooldown): 消除微观日线级别的高频假信号，提供真正机构级指导！
        # -------------------------------------------------------------
        df_bt['MA20'] = df_bt['NOW'].rolling(20).mean()
        df_bt['Dist_50MA'] = (df_bt['NOW'] - df_bt['MA50']) / df_bt['MA50'] * 100.0
        df_bt['MA200_Slope'] = (df_bt['MA200'] - df_bt['MA200'].shift(10)) / df_bt['MA200'].shift(10) * 100.0

        # -------------------------------------------------------------
        # 核心解耦：客观雷达高信噪比观测信号层 (4-Quadrant Symmetric Reflexive System)
        # 第一性原理设计 (严格基于索罗斯反身性理论与黄文政相空间动力学)：
        #
        # 【象限 I：反身性极度恐慌底 (Type A: Panic Crash Bottom)】
        # 经济学机理：自由落体式崩盘、流动性践踏危机、负偏离远场极值区 (Dist_200MA < -10% 或 Score < 32)。
        # 状态约束：处于真实折价状态 (Dist_200MA <= 0% 或 close < MA50)，且相空间速度 q1_dot 初次由负转正。
        regime_panic = (df_bt['Dist_200MA'].rolling(20).min() < -15.0) | (df_bt['Dist_200MA'] < -10.0) | (df_bt['Composite_Score'] < 32.0)
        gate_panic = (df_bt['Dist_200MA'] <= 0.0) | (df_bt['NOW'] < df_bt['MA50'])
        inflection_panic = (
            (df_bt['NOW'] > df_bt['MA10']) & (df_bt['q1_dot'] > 0) & (df_bt['q1_dot'].shift(1) <= 0)
        ) | (
            (df_bt['Dist_200MA'] < -25.0) & (df_bt['q1_dot'] > 0) & (df_bt['q1_dot'].shift(1) <= 0)
        )
        raw_panic = regime_panic & gate_panic & inflection_panic

        # 宏观信用危机/承压：高收益债跌破年线且金融条件紧缩 (NFCI > -0.40 或 RY_Surge)
        macro_crisis_regime = (df_bt['HYG'] < df_bt['Macro_MA200']) & ((df_bt['NFCI'] > -0.40) | df_bt['RY_Surge'])

        # 【象限 II：反身性牛市阶段蓄势底 / 均衡考验确认 (Type B: Stage Consolidation Bottom)】
        # 经济学机理：索罗斯“考验期 (Period of Testing)”。
        # 宏观结构：处于上升或平稳牛市结构 (MA200斜率 >= -0.05%, MA50 >= MA200 * 0.96)，绝非宏观信用危机期 (~macro_crisis_regime)。
        # 几何物理约束：必须是从上方回踩中枢均线，绝不能是从深渊崩盘向上反抽阻力位的“死猫跳” (not_rebounding_from_crash)。
        # 中枢回踩：股价回踩中长期均衡中枢带 (Dist_200MA 在 -12% ~ +8% 或回踩 50MA 附近)。
        # 能量冷却：李雅普诺夫过热能量宣泄完毕 (Composite Score <= 60 或近期低点 <= 50)。
        # 动能重启：相空间广义动能由负转正 (q1_dot > 0 且前一日 <= 0)。
        not_rebounding_from_crash = df_bt['Dist_200MA'].rolling(90).min() >= -12.0
        bull_structure = (df_bt['MA200_Slope'] >= -0.05) & (df_bt['MA50'] >= df_bt['MA200'] * 0.96) & (~macro_crisis_regime) & not_rebounding_from_crash
        equilibrium_test = ((df_bt['Dist_200MA'] >= -12.0) & (df_bt['Dist_200MA'] <= 8.0)) | ((df_bt['Dist_50MA'].abs() <= 3.5) & (df_bt['Dist_200MA'] <= 10.0))
        cool_score = (df_bt['Composite_Score'].rolling(10).min() <= 50.0) | (df_bt['Composite_Score'] <= 60.0)
        inflection_stage = (df_bt['NOW'] > df_bt['MA10']) & (df_bt['q1_dot'] > 0) & (df_bt['q1_dot'].shift(1) <= 0)
        raw_stage = bull_structure & equilibrium_test & cool_score & inflection_stage & (~raw_panic)

        # 【象限 III：反身性牛市极度泡沫顶 (Type C1: Bull Bubble Climax Top)】
        # 经济学机理：正反馈认知偏离极峰 (Climax)。Composite >= 70 或偏离年线 > 22%，
        # 且处于高位真实区间 (Dist_200MA >= 10%)，相空间跨入第四象限破位或跌破20MA月线动能加速转负。
        regime_bubble_top = (df_bt['Composite_Score'] >= 70.0) | (df_bt['Dist_200MA'] > 22.0)
        gate_bubble_top = df_bt['Dist_200MA'] >= 10.0
        inflection_bubble_top = (
            (df_bt['NOW'] < df_bt['MA50']) & (df_bt['q1_dot'] < 0) & (df_bt['Quadrant'] == 4)
        ) | (
            (df_bt['Dist_200MA'] > 20.0) & (df_bt['NOW'] < df_bt['MA20']) & (df_bt['q1_dot'] < -0.3) & (df_bt['NOW'].shift(1) >= df_bt['MA20'].shift(1))
        )
        raw_bubble_top = regime_bubble_top & gate_bubble_top & inflection_bubble_top

        # 【象限 IV：反身性熊市反弹衰竭顶 (Type C2: Bear Rebound Exhaustion Top)】
        # 经济学机理：索罗斯“犹豫期假复苏 (False Dawn)”。
        # 熊市/宏观信用破位格局下 (close < MA200 或 宏观危机 或 刚经历严重崩盘)，
        # 经历过超跌反弹后遇阻，相空间广义动能由正转负 (q1_dot < 0 且前一日 >= 0)，价格跌破短期均线支撑。
        # 彻底补齐熊市中“毫无黄色防守预警点”的盲区！
        bear_regime = (df_bt['NOW'] < df_bt['MA200']) | macro_crisis_regime | (df_bt['Dist_200MA'].rolling(60).min() < -12.0)
        recently_bounced = df_bt['Dist_200MA'].rolling(15).min() < -8.0
        exhaustion_inflection = (df_bt['q1_dot'] < 0) & (df_bt['q1_dot'].shift(1) >= 0) & ((df_bt['NOW'] < df_bt['MA10']) | (df_bt['NOW'] < df_bt['MA50']))
        raw_bear_top = bear_regime & recently_bounced & exhaustion_inflection & (df_bt['Dist_200MA'] < 8.0)

        # 迟滞去噪滤波 (Hysteresis & Cooldown)
        from core_engine.phase_space import PhaseSpaceFilter
        df_bt['Trigger_Panic'] = PhaseSpaceFilter.apply_hysteresis(df_bt, raw_panic, min_days=15, price_step=0.07, is_top=False, price_col='NOW')
        df_bt['Trigger_Stage'] = PhaseSpaceFilter.apply_hysteresis(df_bt, raw_stage, min_days=20, price_step=0.06, is_top=False, price_col='NOW')
        df_bt['Trigger_Bubble_Top'] = PhaseSpaceFilter.apply_hysteresis(df_bt, raw_bubble_top, min_days=25, price_step=0.08, is_top=True, price_col='NOW')
        df_bt['Trigger_Bear_Top'] = PhaseSpaceFilter.apply_hysteresis(df_bt, raw_bear_top, min_days=20, price_step=0.06, is_top=True, price_col='NOW')
        df_bt['Trigger_Top'] = df_bt['Trigger_Bubble_Top'] | df_bt['Trigger_Bear_Top']
        df_bt['Trigger_Overbought'] = df_bt['Trigger_Top']
        df_bt['Trigger_Oversold'] = df_bt['Trigger_Panic'] | df_bt['Trigger_Stage']
        df_bt['Signal_Oversold'] = regime_panic | (bull_structure & equilibrium_test & cool_score)
        df_bt['Signal_Overbought'] = regime_bubble_top | bear_regime

        # 详细记录客观雷达预警诱因
        alert_types = []
        alert_reasons = []
        for i in range(len(df_bt)):
            if df_bt['Trigger_Panic'].iloc[i]:
                alert_types.append("极度恐慌底")
                alert_reasons.append(f"熊市崩盘超跌耗竭(偏离年线{df_bt['Dist_200MA'].iloc[i]:.1f}%, 得分{df_bt['Composite_Score'].iloc[i]:.1f})且相空间动能初次转正(q_dot={df_bt['q1_dot'].iloc[i]:.2f})")
            elif df_bt['Trigger_Stage'].iloc[i]:
                alert_types.append("牛市阶段蓄势底")
                alert_reasons.append(f"牛市中枢考验确认(偏离年线{df_bt['Dist_200MA'].iloc[i]:.1f}%, 得分{df_bt['Composite_Score'].iloc[i]:.1f})且相空间动能重启(q_dot={df_bt['q1_dot'].iloc[i]:.2f})")
            elif df_bt['Trigger_Bubble_Top'].iloc[i]:
                alert_types.append("牛市极度泡沫顶")
                alert_reasons.append(f"牛市高位极端泡沫(偏离年线+{df_bt['Dist_200MA'].iloc[i]:.1f}%, 得分{df_bt['Composite_Score'].iloc[i]:.1f})且相变破位衰竭(q_dot={df_bt['q1_dot'].iloc[i]:.2f})")
            elif df_bt['Trigger_Bear_Top'].iloc[i]:
                alert_types.append("熊市反弹衰竭顶")
                alert_reasons.append(f"熊市反抽遇阻衰竭(偏离年线{df_bt['Dist_200MA'].iloc[i]:.1f}%, 得分{df_bt['Composite_Score'].iloc[i]:.1f})且动能破位转负(q_dot={df_bt['q1_dot'].iloc[i]:.2f})")
            else:
                alert_types.append("无")
                alert_reasons.append("正常跟踪中")

        df_bt['Radar_Alert_Type'] = alert_types
        df_bt['Radar_Alert_Reason'] = alert_reasons

        # -------------------------------------------------------------
        # Rebuild Execution layer decoupling macro crisis constraints
        # -------------------------------------------------------------
        core_cols = ['Composite_Score', 'Gap_Max_45', 'Dist_200MA', 'NFCI', 'BAA10Y', 'HYG', 'Real_Yield', 'NOW', 'MA200', 'MA50', 'MA10']
        df_bt['signal_ready'] = df_bt[core_cols].notna().all(axis=1)

        # Ensure cond_trend is properly computed
        cond_trend = (df_bt['NOW'] > df_bt['MA50']).rolling(3).sum() == 3

        # Update execution variables to use the unified Triggers
        # Triggers already have hysteresis and cool-down applied!
        raw_sell = (df_bt['Trigger_Bubble_Top'] | df_bt['Trigger_Bear_Top']) & df_bt['signal_ready']
        raw_buy = (df_bt['Trigger_Panic'] | cond_trend) & df_bt['signal_ready']

        # -------------------------------------------------------------
        # 逐日记账循环 (SharedExecutor)
        # -------------------------------------------------------------
        bench_acc = UnitizedAccount(initial_cash=initial_capital, initial_date=df_bt['date'].iloc[0])
        strat_acc = UnitizedAccount(initial_cash=initial_capital, initial_date=df_bt['date'].iloc[0])

        executor = SharedExecutor(strat_acc, fee_rate=0.0, execution_mode='NEXT_CLOSE', account_type='strat')
        bench_executor = SharedExecutor(bench_acc, fee_rate=0.0, execution_mode='NEXT_CLOSE', account_type='bench')

        curr_m = -1
        pos = 1.0
        total_injected = initial_capital

        bench_eqs = []
        strat_eqs = []
        positions = []
        action_hist = []

        df_len = len(df_bt)

        for i in range(df_len):
            dt = df_bt['date'].iloc[i]
            p = df_bt['NOW'].iloc[i]
            
            s = raw_sell.iloc[i]
            b = raw_buy.iloc[i]

            m = dt.month

            # 每月定投注入
            dca_amount = 0.0
            if m != curr_m:
                curr_m = m
                dca_amount = dca_monthly
                total_injected += dca_monthly

            executor.step(dt, p, p, dca_amount=dca_amount)
            bench_executor.step(dt, p, p, dca_amount=dca_amount)

            action = 'HOLD'
            action_taken = False
            if df_bt['signal_ready'].iloc[i]:
                if pos > 0 and s:
                    reason = "极度泡沫破裂" if df_bt['Trigger_Bubble_Top'].iloc[i] else "熊市反弹衰竭"
                    pos = 0.0
                    executor.submit_order(pos, reason, dt)
                    action = 'SELL'
                    action_taken = True
                elif pos == 0.0 and b:
                    reason = "恐慌左侧耗竭拐点回补" if df_bt['Trigger_Panic'].iloc[i] else "均线右侧牛市确认建仓"
                    pos = 1.0
                    executor.submit_order(pos, reason, dt)
                    action = 'BUY'
                    action_taken = True
            else:
                action = 'WAITING'

            if not action_taken and dca_amount > 0:
                # 仅在定投日发送维持仓位订单，处理闲置定投资金
                executor.submit_order(pos, "Standing Order / DCA", dt)

            action_hist.append(action)

            # 基准始终满仓，仅在首日或定投日发送订单
            if i == 0 or dca_amount > 0:
                bench_executor.submit_order(1.0, "Bench Standing Order / DCA", dt)

            bench_eqs.append(bench_executor.acc.shares * p + bench_executor.acc.cash)
            strat_eqs.append(executor.acc.shares * p + executor.acc.cash)
            positions.append(pos)

        df_bt['bench_nav'] = bench_eqs
        df_bt['strat_nav'] = strat_eqs
        df_bt['Position'] = positions
        df_bt['action'] = action_hist

        all_states = executor.daily_states + bench_executor.daily_states
        daily_accounts = pd.DataFrame(all_states)

        # 把缺失的列补上为了向前兼容雷达明细表（这里用 shares 和 cash 替代 strat_shares）
        df_bt['strat_shares'] = [s['shares'] for s in executor.daily_states]
        df_bt['strat_cash'] = [s['cash'] for s in executor.daily_states]

        # -------------------------------------------------------------
        # 绩效统计
        # -------------------------------------------------------------
        bench_end = bench_eqs[-1]
        strat_end = strat_eqs[-1]
        
        strat_nav_series = daily_accounts[daily_accounts['type'] == 'strat']['unit_nav'].reset_index(drop=True)
        bench_nav_series = daily_accounts[daily_accounts['type'] == 'bench']['unit_nav'].reset_index(drop=True)
        
        bench_cummax = bench_nav_series.cummax()
        bench_dd = ((bench_nav_series - bench_cummax) / bench_cummax.clip(lower=1e-8)).min() * 100.0

        strat_cummax = strat_nav_series.cummax()
        strat_dd = ((strat_nav_series - strat_cummax) / strat_cummax.clip(lower=1e-8)).min() * 100.0

        final_date = pd.Timestamp(df_bt['date'].iloc[-1])
        bench_cagr = calculate_xirr([(pd.Timestamp(d), a) for d, a in bench_executor.acc.cash_flows], bench_end, final_date) * 100.0
        strat_cagr = calculate_xirr([(pd.Timestamp(d), a) for d, a in executor.acc.cash_flows], strat_end, final_date) * 100.0

        alpha = strat_cagr - bench_cagr
        bench_total_ret = (bench_end - total_injected) / max(total_injected, 1e-8) * 100.0
        strat_total_ret = (strat_end - total_injected) / max(total_injected, 1e-8) * 100.0

        metrics = {
            'total_invested': total_injected,
            'bench_final': bench_end,
            'strat_final': strat_end,
            'bench_return': bench_total_ret,
            'strat_return': strat_total_ret,
            'bench_cagr': bench_cagr,
            'strat_cagr': strat_cagr,
            'bench_max_dd': bench_dd,
            'strat_max_dd': strat_dd,
            'alpha': alpha,
            'trade_count': len(executor.fills),
            'trade_rounds': len(executor.fills) // 2
        }

        self.perf_metrics = metrics
        self.df_bt = df_bt
        
        self.result = SimulationResult(
            features=df_bt,
            signals=df_bt[['date', 'Position', 'Radar_Alert_Type', 'Radar_Alert_Reason']],
            orders=executor.orders_history + executor.pending_orders,
            fills=executor.fills,
            cashflows=executor.cashflows,
            daily_accounts=daily_accounts,
            metrics=metrics,
            metadata={'ticker': 'NOW', 'start_date': start_date, 'end_date': df_bt['date'].iloc[-1]}
        )

        print("---------------------------------------------------------------")
        print(f"💰 总体绩效报告 [ServiceNow (NOW) 反身性雷达 2013-2026]")
        print(f"总投入本金:       ${total_injected:,.2f}")
        print(f"基准最终资产:     ${bench_end:,.2f} (总收益: {bench_total_ret:+.2f}%, 年化CAGR: {bench_cagr:.2f}%, 最大回撤: {bench_dd:.2f}%)")
        print(f"策略最终资产:     ${strat_end:,.2f} (总收益: {strat_total_ret:+.2f}%, 年化CAGR: {strat_cagr:.2f}%, 最大回撤: {strat_dd:.2f}%)")
        print(f"超额收益 Alpha:   {alpha:+.2f}% (净增财富: +${strat_end - bench_end:,.2f})")
        print(f"最大回撤改善:     {bench_dd - strat_dd:+.2f}%")
        print(f"交易频次:         共 {len(executor.fills)} 次触发")
        print("---------------------------------------------------------------")
        return self.result

    def plot_panoramic_chart(self):
        """生成 4 层对齐高清时间序列全景图谱"""
        print(f"🎨 正在绘制 4 层对齐时间序列图谱至: {self.output_panoramic_png}...")
        df_bt = self.df_bt
        dates = df_bt['date']

        fig, axes = plt.subplots(4, 1, figsize=(16, 18), sharex=True, gridspec_kw={'height_ratios': [3.0, 2.2, 2.2, 2.6]})
        fig.suptitle("ServiceNow (NOW) 单股反身性相空间微观雷达全景图谱 (2013-2026)", fontsize=18, fontweight='bold', y=0.995)

        # -------------------------------------------------------------
        # 第 1 层：价格与买卖点标记 (四象限对称客观预警 vs 账户实盘交易)
        # -------------------------------------------------------------
        ax1 = axes[0]
        ax1.plot(dates, df_bt['NOW'], label='NOW 收盘价 (USD)', color='#1f77b4', lw=1.8, zorder=2)
        ax1.plot(dates, df_bt['MA50'], label='50 日机构均线 (MA50)', color='#ff7f0e', lw=1.2, ls='--', zorder=2)
        ax1.plot(dates, df_bt['MA200'], label='200 日牛熊生命线 (MA200)', color='#2ca02c', lw=1.2, ls=':', zorder=2)

        # 1. 客观雷达信号标记 (不受仓位和现金限制，高信噪比四象限体系)
        # 象限 I：极度恐慌底 (亮青色钻石点)
        panic_pts = df_bt[df_bt['Trigger_Panic']]
        ax1.scatter(panic_pts['date'], panic_pts['NOW'], color='#00e5ff', edgecolors='#0091ea', marker='D', s=70, alpha=0.95, zorder=5, label=f'[客观极度恐慌底] 崩盘超卖耗竭 (共 {len(panic_pts)} 次)')

        # 象限 II：牛市阶段蓄势底 (宝蓝色钻石点)
        stage_pts = df_bt[df_bt['Trigger_Stage']]
        ax1.scatter(stage_pts['date'], stage_pts['NOW'], color='#2979ff', edgecolors='#1a237e', marker='D', s=65, alpha=0.95, zorder=5, label=f'[客观阶段蓄势底] 均衡回踩确认 (共 {len(stage_pts)} 次)')

        # 象限 III：牛市极度泡沫顶 (亮橙红色钻石点)
        bubble_pts = df_bt[df_bt['Trigger_Bubble_Top']]
        ax1.scatter(bubble_pts['date'], bubble_pts['NOW'], color='#ff9100', edgecolors='#d50000', marker='D', s=75, alpha=0.95, zorder=5, label=f'[客观极度泡沫顶] 泡沫衰竭防守 (共 {len(bubble_pts)} 次)')

        # 象限 IV：熊市反弹衰竭顶 (亮黄色钻石点)
        bear_top_pts = df_bt[df_bt['Trigger_Bear_Top']]
        ax1.scatter(bear_top_pts['date'], bear_top_pts['NOW'], color='#ffd600', edgecolors='#e65100', marker='D', s=65, alpha=0.95, zorder=5, label=f'[客观熊市衰竭顶] 诱多破位防守 (共 {len(bear_top_pts)} 次)')

        # 2. 策略实盘记账买卖点 (真实账户交易变动)
        sells = df_bt[df_bt['action'] == 'SELL']
        buys = df_bt[df_bt['action'] == 'BUY']
        ax1.scatter(sells['date'], sells['NOW'], color='#d62728', marker='v', s=140, zorder=7, label=f'[实盘卖出] 策略减仓变现 (共 {len(sells)} 次, 仓位清零)')
        ax1.scatter(buys['date'], buys['NOW'], color='#00c853', marker='^', s=140, zorder=7, label=f'[实盘买入] 策略低位建仓 (共 {len(buys)} 次, 满仓买入)')

        # 3. 背景真实深度超跌体制区间微弱高亮
        ax1.fill_between(dates, df_bt['NOW'].min()*0.85, df_bt['NOW'].max()*1.1, where=(df_bt['Dist_200MA'] <= -10.0), color='#00e5ff', alpha=0.06, label='深度超跌体制区 (Dist_200MA <= -10%)')

        ax1.set_title("Layer 1: 股价微观雷达双层信号图谱 (高信噪比客观预警 vs 账户实盘买卖执行)", fontsize=13, fontweight='bold')
        ax1.set_ylabel("价格 (USD)", fontsize=11)
        ax1.grid(True, alpha=0.3)
        ax1.legend(loc='upper left', frameon=True, fontsize=9.5, ncol=2)

        # -------------------------------------------------------------
        # 第 2 层：相空间动力学 (速度 q_dot, 加速度 q_ddot, 能量导数 V_dot)
        # -------------------------------------------------------------
        ax2 = axes[1]
        ax2.plot(dates, df_bt['q1_dot'], label='广义速度 q1_dot (10日有限差分 %/day)', color='#9467bd', lw=1.5)
        ax2.axhline(0, color='gray', lw=0.8, ls='--')
        ax2.fill_between(dates, df_bt['q1_dot'], 0, where=(df_bt['q1_dot'] > 0), color='#9467bd', alpha=0.2, label='动能扩张区')
        ax2.fill_between(dates, df_bt['q1_dot'], 0, where=(df_bt['q1_dot'] <= 0), color='#e377c2', alpha=0.2, label='动能衰竭区')

        ax2_sub = ax2.twinx()
        ax2_sub.plot(dates, df_bt['v_dot'], label='相空间能量变化率代理指标 V_dot', color='#d62728', lw=1.0, alpha=0.7)
        ax2_sub.set_ylabel("能量导数 V_dot", fontsize=10, color='#d62728')

        ax2.set_title("Layer 2: 黄文政相空间物理量 (广义动能 q1_dot 与 李雅普诺夫稳定性导数 V_dot)", fontsize=13, fontweight='bold')
        ax2.set_ylabel("速度 (%/day)", fontsize=11)
        ax2.grid(True, alpha=0.3)
        ax2.legend(loc='upper left', frameon=True, fontsize=9)

        # -------------------------------------------------------------
        # 第 3 层：6 大解耦分位数与综合过热得分
        # -------------------------------------------------------------
        ax3 = axes[2]
        ax3.plot(dates, df_bt['Score_Dim1_Pos'], label='Dim 1: 势能位置分', color='#1f77b4', lw=1.0, alpha=0.6)
        ax3.plot(dates, df_bt['Score_Dim2_Vel'], label='Dim 2: 动能速度分', color='#2ca02c', lw=1.0, alpha=0.6)
        ax3.plot(dates, df_bt['Score_Dim3_Lyapunov'], label='Dim 3: 李氏稳定性分', color='#9467bd', lw=1.0, alpha=0.6)
        ax3.plot(dates, df_bt['Score_Dim4_Capital'], label='Dim 4: 内部人减持分', color='#8c564b', lw=1.0, alpha=0.6)
        ax3.plot(dates, df_bt['Score_Dim6_Macro'], label='Dim 6: 宏观信用分', color='#e377c2', lw=1.0, alpha=0.6)
        ax3.plot(dates, df_bt['Composite_Score'], label='综合反身性过热得分 (Composite)', color='#d62728', lw=2.2)

        ax3.axhline(70, color='#d62728', ls='--', lw=1.2, label='过热临界线 (70分)')
        ax3.axhline(30, color='#2ca02c', ls='--', lw=1.2, label='恐慌超卖线 (30分)')
        ax3.axhspan(70, 100, color='#ff7f0e', alpha=0.12, label='过热警戒区 (Score >= 70)')
        ax3.axhspan(0, 30, color='#00e5ff', alpha=0.12, label='恐慌超卖区 (Score <= 30)')
        ax3.set_title("Layer 3: 六大解耦维度分位数 (0-100) 与反身性综合过热得分", fontsize=13, fontweight='bold')
        ax3.set_ylabel("分位数得分 (0-100)", fontsize=11)
        ax3.grid(True, alpha=0.3)
        ax3.legend(loc='upper left', ncol=3, frameon=True, fontsize=8.5)

        # -------------------------------------------------------------
        # 第 4 层：真实券商净值对比 (策略 vs 买入持有)
        # -------------------------------------------------------------
        ax4 = axes[3]
        ax4.plot(dates, df_bt['strat_nav'], label=f"反身性相空间策略 (终值: ${df_bt['strat_nav'].iloc[-1]:,.0f}, CAGR: {self.perf_metrics['strat_cagr']:.1f}%)", color='#d62728', lw=2.2)
        ax4.plot(dates, df_bt['bench_nav'], label=f"买入持有基准 (终值: ${df_bt['bench_nav'].iloc[-1]:,.0f}, CAGR: {self.perf_metrics['bench_cagr']:.1f}%)", color='#7f7f7f', lw=1.5, ls='--')

        ax4.set_title(f"Layer 4: 真实券商记账资产净值曲线对比 (Alpha: {self.perf_metrics['alpha']:+.2f}%, 净超额: +${self.perf_metrics['strat_final'] - self.perf_metrics['bench_final']:,.0f})", fontsize=13, fontweight='bold')
        ax4.set_ylabel("账户净资产 (USD)", fontsize=11)
        ax4.grid(True, alpha=0.3)
        ax4.legend(loc='upper left', frameon=True, fontsize=10)

        # 横坐标日期格式化
        ax4.xaxis.set_major_locator(mdates.YearLocator(2))
        ax4.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m'))
        plt.setp(ax4.xaxis.get_majorticklabels(), rotation=0, ha='center')

        plt.tight_layout()
        plt.savefig(self.output_panoramic_png, dpi=200, bbox_inches='tight')
        plt.close()
        print(f"✅ 4 层全景图谱绘制完成: {self.output_panoramic_png}")

    def plot_phase_portrait(self):
        """生成二维拉格朗日相空间动力学相图 (q1 vs q1_dot)"""
        print(f"🌀 正在绘制二维相空间动力学相图至: {self.output_phase_png}...")
        df_bt = self.df_bt

        fig, ax = plt.subplots(figsize=(12, 10))

        q = df_bt['q1']
        q_dot = df_bt['q1_dot']

        # 绘制背景四象限
        q_lim = max(abs(q.min()), abs(q.max())) * 1.05
        qd_lim = max(abs(q_dot.min()), abs(q_dot.max())) * 1.05

        # 象限填充与标注
        ax.fill_between([0, q_lim], 0, qd_lim, color='#e8f5e9', alpha=0.5) # Q1
        ax.fill_between([-q_lim, 0], 0, qd_lim, color='#fff9c4', alpha=0.5) # Q2
        ax.fill_between([-q_lim, 0], -qd_lim, 0, color='#ffebee', alpha=0.5) # Q3
        ax.fill_between([0, q_lim], -qd_lim, 0, color='#fff3e0', alpha=0.5) # Q4

        ax.axhline(0, color='black', lw=1.2)
        ax.axvline(0, color='black', lw=1.2)

        # 象限文字说明
        ax.text(q_lim * 0.45, qd_lim * 0.85, "【第一象限: 正反身性主升浪】\nq > 0, q_dot > 0\n价格高估且动能加速扩张\n顺势持有，切勿盲目估值恐高", fontsize=11, color='#1b5e20', fontweight='bold', bbox=dict(boxstyle='round,pad=0.5', facecolor='white', alpha=0.8))
        ax.text(-q_lim * 0.90, qd_lim * 0.85, "【第二象限: 底部蓄势重构】\nq < 0, q_dot > 0\n价格超跌且下跌动能耗竭\n黄金坑右侧确认买入点", fontsize=11, color='#f57f17', fontweight='bold', bbox=dict(boxstyle='round,pad=0.5', facecolor='white', alpha=0.8))
        ax.text(-q_lim * 0.90, -qd_lim * 0.70, "【第三象限: 负反身性死亡螺旋】\nq < 0, q_dot < 0\n价格破位且下跌速度加快\n严禁左侧接飞刀，耐心观望", fontsize=11, color='#b71c1c', fontweight='bold', bbox=dict(boxstyle='round,pad=0.5', facecolor='white', alpha=0.8))
        ax.text(q_lim * 0.45, -qd_lim * 0.70, "【第四象限: 动能衰竭与相变崩塌】\nq > 0, q_dot < 0\n处于历史极高但速度破零转负\n【警报】物理级反身性逃顶信号！", fontsize=11, color='#e65100', fontweight='bold', bbox=dict(boxstyle='round,pad=0.5', facecolor='white', alpha=0.8))

        # 散点相轨迹（按年份渐变颜色）
        years = df_bt['date'].dt.year
        scatter = ax.scatter(q, q_dot, c=years, cmap='viridis', s=18, alpha=0.6, edgecolors='none', label='相轨迹 (NOW 2013-2026)')
        cbar = plt.colorbar(scatter, ax=ax, pad=0.02)
        cbar.set_label("历史年份", fontsize=11)

        # 标记重大历史拐点
        # 1. 2021 年顶峰相变点 (2021-11)
        nov21 = df_bt[df_bt['date'] == '2021-11-22']
        if len(nov21) > 0:
            ax.annotate("2021年11月泡沫逃顶相变\n(q1=+24.6%, q1_dot=-0.76)",
                        xy=(nov21['q1'].iloc[0], nov21['q1_dot'].iloc[0]),
                        xytext=(nov21['q1'].iloc[0] + 10, nov21['q1_dot'].iloc[0] - 0.8),
                        arrowprops=dict(facecolor='red', shrink=0.05, width=2, headwidth=8),
                        fontsize=10, fontweight='bold', color='red',
                        bbox=dict(boxstyle='round,pad=0.3', facecolor='yellow', alpha=0.9))

        # 2. 2022 年底恐慌大底相变点 (2022-10)
        oct22 = df_bt[df_bt['date'] == '2022-10-24']
        if len(oct22) > 0:
            ax.annotate("2022年10月黄金坑右侧确认\n(q1=-22.1%, q1_dot=+0.42)",
                        xy=(oct22['q1'].iloc[0], oct22['q1_dot'].iloc[0]),
                        xytext=(oct22['q1'].iloc[0] - 25, oct22['q1_dot'].iloc[0] + 0.6),
                        arrowprops=dict(facecolor='green', shrink=0.05, width=2, headwidth=8),
                        fontsize=10, fontweight='bold', color='green',
                        bbox=dict(boxstyle='round,pad=0.3', facecolor='#e8f5e9', alpha=0.9))

        ax.set_xlim(-q_lim, q_lim)
        ax.set_ylim(-qd_lim, qd_lim)
        ax.set_title("ServiceNow (NOW) 拉格朗日相空间动力学相图 (Phase Portrait: q1 vs q1_dot)", fontsize=14, fontweight='bold')
        ax.set_xlabel("广义状态位置 q1 (相对 200MA 偏离度 % / 势能坐标)", fontsize=12)
        ax.set_ylabel("广义状态速度 q1_dot (10日有限差分变化率 %/day / 动能坐标)", fontsize=12)
        ax.grid(True, alpha=0.3)

        plt.tight_layout()
        plt.savefig(self.output_phase_png, dpi=200, bbox_inches='tight')
        plt.close()
        print(f"✅ 相空间动力学相图绘制完成: {self.output_phase_png}")

    def run_all(self):
        """一键全流程执行流水线"""
        print("================================================================================")
        print("🚀 启动 ServiceNow (NOW) 单股反身性相空间动力学量化引擎")
        print("================================================================================")
        self.load_and_preprocess()
        self.compute_all_dimensions()
        
        # Save local radar
        self.df.to_csv('now_radar_local.csv', index=False)
        print(f"💾 预计算指标已固化至: now_radar_local.csv (共 {len(self.df)} 行)")
        
        self.run_backtest()
        
        from core_engine.export_utils import export_deliverables
        export_deliverables(self.result, "ServiceNow (NOW)")
        
        self.plot_panoramic_chart()
        self.plot_phase_portrait()
        print("================================================================================")
        print("🎉 全部任务已圆满完成！所有机构级对账表、全景图谱与相图均已生成！")
        print("================================================================================")

if __name__ == "__main__":
    radar = NOWReflexivityRadar()
    radar.run_all()
