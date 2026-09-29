# 索罗斯反身性相空间模型：消融实验规格与基准评价口径 (Frozen Specification v2.0)

**状态**：已修订并正式冻结（Frozen Specification v2.0）  
**日期**：2026-09-23  
**定位**：纯脱机隔离研究规格，范围严格限定于 `audit_artifacts/gemini_review_20260923/`，生产代码保持 100% 不变。  
**核心原则**：以事实、证据与严格断言为准绳，严禁预设任何终值或优劣结论。

---

## 一、 因子消融设计 ($2^3 = 8$ 种正交组合)

消融实验针对三大独立因子开展全正交测试：
- **因子 A：评分解耦 (Score Decoupling)**
- **因子 B：恐慌记忆锁存 (Panic Memory Latch)**
- **因子 C：再入场状态机与止损 (Re-entry Handshake & Stop Loss)**

| 实验编号 | 因子 A (评分解耦) | 因子 B (恐慌记忆) | 因子 C (再入场约束) | 说明 |
|:---:|:---:|:---:|:---:|---|
| **C0** | ❌ (原版) | ❌ (原版) | ❌ (原版) | 统一执行框架下的研究基线 (Unified Research Baseline) |
| **C1** | ✅ | ❌ | ❌ | 仅解耦过热分与宏观压力分 |
| **C2** | ❌ | ✅ | ❌ | 仅引入恐慌记忆锁存机制 |
| **C3** | ❌ | ❌ | ✅ | 仅引入卖出后分类再入场与止损 |
| **C4** | ✅ | ✅ | ❌ | 评分解耦 + 恐慌记忆 |
| **C5** | ✅ | ❌ | ✅ | 评分解耦 + 再入场约束 |
| **C6** | ❌ | ✅ | ✅ | 恐慌记忆 + 再入场约束 |
| **C7** | ✅ | ✅ | ✅ | 全组合候选模型 |

> **对照组设定 (Dual Controls)**：
> 1. **生产基线 (Production Control)**：原样运行生产环境 `run_universal_reflexivity_radar`，严格保留生产固有预热门禁（`signal_ready`），作为生产现状参照物；
> 2. **统一研究基线 (C0)**：在统一记账、统一执行时点和统一参数下运行原版逻辑，作为消融对比的严密控制组。

---

## 二、 因子数学定义与边界规则（确定性算法，无模糊语义）

### 1. 因子 A：评分解耦 (Score Decoupling)
彻底消除非方向性导数与宏观压力的符号反转。

1. **上行偏离过热分 $S_{\text{overheat}} \in [0, 100]$**：
   $$S_{\text{overheat}} = 0.50 \cdot \text{Rank}(q_1) + 0.30 \cdot \text{Rank}(\max(\dot{q}_1, 0)) + 0.20 \cdot \text{Rank}(\max(q_1, 0) \cdot \max(\dot{q}_1, 0))$$
   - 速度项严格使用对正向速度的分位数；
   - 偏离度 $q_1 = (P - \text{MA200}) / \text{MA200} \times 100$ 纯粹衡量相对技术位置，不代表公允估值。
2. **宏观信用压力分 $S_{\text{macro}} \in [0, 100]$**：
   $$S_{\text{macro}} = 0.50 \cdot \text{Rank}(\text{BAA10Y}) + 0.50 \cdot \text{Rank}(\text{NFCI})$$
   - 独立保留作为外生风险维度，不并入过热分，亦不取反（金融宽松 $\ne$ 股票泡沫）。
3. **下行超卖深度分 $S_{\text{panic}} \in [0, 100]$**：
   $$S_{\text{panic}} = 0.60 \cdot \text{Rank}(-q_1) + 0.40 \cdot \text{Rank}(\max(-\dot{q}_1, 0))$$

---

### 2. 因子 B：恐慌记忆锁存 (Panic Memory Latch)
解决“崩盘最深处动能未转正、反弹动能转正时价格已脱离恐慌区”的时序错位问题。

- **状态变量**：布尔锁存 $L_t \in \{0, 1\}$，倒计时计数器 $T_t \in \mathbb{N}$，锚定参考价 $P_{\text{anchor}, t} \in \mathbb{R}^+$。
- **首次激活 (Trigger)**：
  当 $q_{1, t} < -10\%$ 或 $S_{\text{panic}, t} \ge 80\%$，且 $L_{t-1} == 0$：
  $$L_t \leftarrow 1, \quad T_t \leftarrow K_{\text{window}} = 15 \text{ 交易日}, \quad P_{\text{anchor}, t} \leftarrow P_t$$
- **创新低重置计时 (Reset on New Low)**：
  若 $L_{t-1} == 1$ 且收盘价创出新低 $P_t < P_{\text{anchor}, t-1} \times 0.98$（跌破前锚定点逾 2%）：
  - 判定恐慌延续，**重置锚定点并重新计时**：$P_{\text{anchor}, t} \leftarrow P_t, \quad T_t \leftarrow 15$。
- **倒计时递减与自然过期 (Expire)**：
  若未创新低，每日倒计时：$T_t \leftarrow T_{t-1} - 1$。当 $T_t \le 0$ 时，锁存自然失效：$L_t \leftarrow 0$。
- **消耗时点 (Latch Consumption)**：
  在通过全部信号过滤（即同时满足 $L_t == 1$、$\dot{q}_{1, t} > 0$ 严格为正、且 $P_t > \text{MA10}_t$）发出有效买入信号时，**立即在信号层将锁存消耗关闭**：$L_t \leftarrow 0$。后续依赖执行层待成交订单（Pending Order）防重，严禁重复提交。
- **硬性门禁 (Zero Bypass)**：
  严禁任何绕过 MA10 的深跌例外。发信号当日**瞬时动能必须严格正向 $\dot{q}_{1, t} > 0$ 且收盘价站上 MA10**。

---

### 3. 因子 C：再入场状态机与止损 (Re-entry Handshake & Stop Loss)
严格基于实际成交回报（Fills）维护退出状态，消除牛市次日买回与熊市滞后。

设持仓状态机模式 $E_t \in \{\text{HOLDING}, \text{NONE}, \text{AFTER\_BUBBLE}, \text{AFTER\_BEAR}\}$。

1. **状态流转基准**：
   - 仅当执行器实际完成卖出成交（Fill Direction == 'SELL'）的次日，才正式进入 `AFTER_BUBBLE` 或 `AFTER_BEAR` 状态；
   - 仅当实际完成买入成交（Fill Direction == 'BUY'）的次日，恢复为 `HOLDING`，同时记录再入场基准价 $P_{\text{reentry}} \leftarrow P_{\text{fill}}$，并启动再入场止损计数器 $T_{\text{stop}} \leftarrow 10$。
2. **极度泡沫顶卖出后恢复条件 (`AFTER_BUBBLE`)**：
   - 禁止仅凭 $P_t > \text{MA50}_t$ 立即买回；
   - 恢复入场需满足以下任一明确数学条件：
     - **路径 C1.1 (中枢回踩企稳)**：价格连续 2 个交易日处于 50MA 均线带附近（$|P_t - \text{MA50}_t| / \text{MA50}_t \le 0.025$ 连续 2 日），且当日 $P_t > \text{MA20}_t$ 且 $\dot{q}_{1, t} > 0$；
     - **路径 C1.2 (充分冷却后突破)**：空仓已持续至少 10 个交易日，且价格创出过去 20 个交易日新高（$P_t > \max_{1 \le i \le 20} P_{t-i}$）且 $\dot{q}_{1, t} > 0$。
3. **熊市反弹衰竭卖出后恢复条件 (`AFTER_BEAR`)**：
   - 必须满足宏观压力缓解（$S_{\text{macro}} < 60.0$ 或 $\text{HYG} > \text{MA200}_{\text{HYG}}$），且价格连续 3 个交易日收于 50MA 之上（$P_t > \text{MA50}_t$ 连续 3 日）且当日 $\dot{q}_{1, t} > 0$。
4. **恐慌底无条件覆盖**：
   - 无论处于 `AFTER_BUBBLE` 还是 `AFTER_BEAR`，只要发生真实的极度恐慌底确认信号（Trigger_Panic），允许无条件买入。
5. **入场后止损机制 (Stop Loss)**：
   - 在再入场成交后的 10 个交易日内（$T_{\text{stop}} > 0$），若当日收盘价较再入场成交价跌破逾 5%（$P_t < P_{\text{reentry}} \times 0.95$），触发止损卖出单；
   - 每日倒计时：$T_{\text{stop}} \leftarrow T_{\text{stop}} - 1$；
   - **日常定投加仓绝不重置 $T_{\text{stop}}$ 计时器或抬高止损基准价**。

---

## 三、 订单优先级与券商执行标准 (Brokerage & Order Precedence)

为杜绝定投订单覆盖风险卖单，严格定义每日时序：

```
每日时钟周期 (Daily Cycle at Date t):
---------------------------------------------------------------------------------
步骤 1: 执行前日待成交订单与当日现金流
        executor.step(dt, open_p, close_p, dca_amount=deposit)
        - 若前日有订单，在本日依模式撮合；
        - 若本日有 deposit，进入闲置现金池 (cash)。

步骤 2: 决策当日最终目标意图 (Target Position Intent)
        - 若触发卖出 (Risk Exit / Stop Loss): 意图 target_pos = 0.0
        - 若触发买入 (Panic Bottom / Trend / Re-entry): 意图 target_pos = 1.0
        - 若无交易信号:
            - 若当前账户已持仓 (pos > 0) 且本日有 deposit:
              为保证新增定投资金跟随持仓投资，意图 target_pos = 1.0
            - 若当前账户空仓 (pos == 0):
              定投资金继续保留在现金池，意图 target_pos = 0.0

步骤 3: 提交唯一有效意图订单
        若 target_pos 与当前实际持仓状态不符 (或有新增闲置现金需折算):
        submit_order(target_pos, reason, dt)
        (严禁同日多次调用 submit_order 互相覆盖！)
---------------------------------------------------------------------------------
```

- **基准账户投资**：
  - 初始提交 `submit_order(1.0)`；
  - 每次有 monthly deposit 入金时，提交 `submit_order(1.0)`；
  - 终值与现金自然结算：若最后一天有入金，现金与待成交单如实保留，不强制削足适履清零。

---

## 四、 评价口径与分类指标规范

### 1. 信号层分类评价 (Signal Layer)
- **极值真值定义**：以 $t \pm 20$ 交易日局部极值作为真值（$P_t = \min / \max_{s \in [t-20, t+20]} P_s$）。
- **极值匹配时间窗口 (严格纠正)**：
  - 对信号日 $S$，搜索极值日 $E$ 的范围为 $[S - 15, S + 5]$：
    $$\text{Hit} \iff E \in [S - 15, S + 5] \iff S \in [E - 5, E + 15]$$
    即：信号必须发生在极值点前 5 日至后 15 日内。
- **分类统计规则**：
  - **恐慌底抄底信号 (`Trigger_Panic`)**：专门核算极小值匹配率、误报率 (FDR) 与漏报率 (Miss Rate)；
  - **右侧趋势与再入场信号 (`TREND_BUY`, `REENTRY`)**：不强行以“抄在谷底”评价，单独核算入场后 20 日和 60 日的前向收益胜率与平均收益率；
  - **卖出信号 (`Trigger_Bubble_Top`, `Trigger_Bear_Top`)**：专门核算极大值匹配率与避险回撤幅度。
  - 末尾 60 个交易日样本不计入极值匹配分母。

### 2. 执行层资金加权收益与净值回撤 (Execution Layer)
- **收益率**：全面采用实际现金流内含报酬率 `calculate_xirr(cash_flows, final_value, final_date)`。
- **年化资金加权收益差 (Alpha Difference)**：
  $$\Delta \text{XIRR} = \text{XIRR}_{\text{strategy}} - \text{XIRR}_{\text{benchmark}} \quad (\text{单位: 百分点})$$
- **最大回撤**：强制基于单位净值 `unit_nav` 序列核算：$\min(NAV / NAV_{\text{cummax}} - 1) \times 100\%$。
- **短期往返率 (Short-term Round-trip Rate)**：
  - 统计开仓成交至平仓成交的**真实交易日间隔 $\le 5$ 交易日**的往返次数占比。
- **空仓期机会成本**：
  - 仅统计在 NEXT_CLOSE 机制下实际无持仓敞口期间，标的资产的复合收益变化。

### 3. 数据集与分段命名规范
- **开发样本 (NOW)**：
  - 全样本：2012-06-29 至 2026-09-14；
  - 早期开发段 (In-Sample Exploration)：2012-06-29 至 2019-12-31；
  - 历史分段验证 (Historical Segment Verification)：2020-01-01 至 2026-09-14（包含 2020 疫情冲击与 2022 加息熊市）。
- **跨资产验证 (QQQ, SPY)**：
  - 纯收盘价脱机对齐，严禁伪造高低价或成交量；
  - 分段核算与独立输出 CSV 底稿。
