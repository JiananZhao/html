# Phase 1 Refined 验收报告

日期：2026-09-22。基于当前未提交工作区，HEAD为53c98e6。仅核验并新增审查文件，未修改生产模型、主数据、缓存或策略状态。

## 结论

部分准确完成，但验收不通过，不能冻结为Phase 2基线。局部排名与广度公式正确，宏观策略执行引入了阻断性回归；有效性门禁和缓存重置声明也不成立。不能从本次局部修复推导出“全部数学漏洞和前视偏差已消除”。

复现：`python audit_artifacts/model_focus_20260922/verify_refined.py`。
输出：`refined_verification.json`。脚本退出码0表示审查完成，不表示被审模型全部通过；其中主动捕获并记录了模型异常与反例。
测试使用本地数据，禁用网络；完整调用了QQQ/SPY宏观模拟函数，其他案例通过提取生产AST执行。未生成新生产交付物。

## 已通过的修复

- NOW、single_stock、reflexivity_engine三处expanding_rank：200个常数得50，预热期保留NaN。
- 四处Gap排名：200个常数得15/30，即百分制50；前59个有效观测不足及当前Gap缺失时输出NaN，不再补0。
- SMH当日fresh_mask：合成两个成分、其中一个当日缺价的案例，有效数量正确为1，填充报价不再计入当日分母。历史均线仍依赖填充序列，本测试不证明历史行情质量或历史成分股无偏。
- 交互宏观入口确实去掉了全局dropna；负Gap解释已在用户提供的Walkthrough中更正。

## 阻断问题

### P1-1：宏观回测新增运行中断及状态机分支错误

位置：reflexivity_interactive_chart.py:158、186、193。

can_buy仅在`elif pos == 0.0`中赋值，之后却对所有signal_ready日期执行`if can_buy`。实际读取本地market_data_local.csv调用run_reflexivity_simulation：

| 资产 | 日期 | 行号 | 错误 |
|---|---|---|---|
| QQQ | 2009-03-24 | 193 | UnboundLocalError: local variable 'can_buy' referenced before assignment |
| SPY | 2009-03-24 | 193 | 同上 |

不仅需要初始化变量：`elif exit_regime == 'BEAR'`与`elif pos == 0.0`同级，空仓时已经进入后者，正常熊市回补分支不可达。直接执行实际决策AST、设置空仓且信用和价格均已修复，结果仍无订单。

建议每个交易日显式重置决策临时变量，将BUBBLE/BEAR作为空仓分支内的同级退出原因分支，避免跨日残留变量触发错误订单；随后运行完整QQQ/SPY模拟。

### P1-2：allow_breakout配置被移除，改变策略语义

位置：reflexivity_interactive_chart.py:182。

本次diff将`elif allow_breakout and breakout_higher`改成`elif breakout_higher`。合成泡沫退出、无恐慌、Gap未冷却、价格突破卖价且趋势确认的场景，明确设置allow_breakout=False后仍产生“突破卖出价右侧防踏空接回”买单。

这是Phase 1不应引入的交易政策变化，会污染Phase 2对照实验。恢复配置约束，并验证开关两种取值的区别。

### P1-3：signal_ready尚未建立完整数据依赖门禁

位置：reflexivity_interactive_chart.py:100、197；now_reflexivity_radar.py:277、282、425附近；single_stock同类分支。

当前门禁检查Overheat_Score、Cond_Bubble、Cond_Bear是否非空。然而缺失数值经比较后往往已变为False，False.notna()仍为True。将本地主数据2020-01-01的NFCI置NaN后，signal_ready依然为True。

此外，signal_ready=False的else分支仍每天生成Standing Order / DCA。100天全部未预热的合成输入中，ready_days=0，策略生成100个订单并有5笔成交。预先确定的定投可以作为独立政策例外，但必须显式定义；这不支持“未就绪期间不生成新交易决策”的现有声明，也不能将初始满仓意图当作已确认信号。

NOW、single_stock及其他被检查入口没有统一signal_ready门禁。删除Composite填充值后，独立的cond_bear、cond_trend、OR分支仍可能触发，因此“NaN比较为False”不能替代依赖校验。NOW及single_stock的资本分项也仍保留fillna(50.0)。CLV的fillna(0.0)属于不同业务定义，不能不加区分地全局删除。

应按每条决策的必要原始特征建立有效性规则；既定入金、已提交订单和新信号分别处理。测试至少覆盖单个NFCI/BAA缺失、预热、已有订单执行与没有已有订单的初始阶段。

### P2-4：缓存重置删除目标与实际持久化目录不符

位置：core_engine/state_manager.py:13，energy_bubble_radar.py:262，.github/workflows/data_updater.yml:37。

engine_state/当前不存在，但StateManager默认目录是.states/，能源入口也使用默认目录。现场.states/仍有5个旧文件，位于energy_radar/XLE/energy_radar_v2下；CI同样缓存.states/，并使用不含模型版本的restore前缀。

这些旧文件路径是否会被某一当前配置命中应另行核对，不能仅凭存在就宣称已经污染本次QQQ/SPY模拟。但“已清除全局有效缓存、任何策略必然重建”未得到证实。应将特征/策略版本纳入缓存与快照兼容性规则，验证升级后的恢复拒绝与历史重放；不要继续猜目录删除。

## 后续验收顺序

1. 先修宏观循环控制流及allow_breakout语义回归。
2. 按原始特征建立有效性门禁，明确独立定投例外；保留已排队订单及资金事件的执行时钟。
3. 核对实际状态路径与版本隔离，加入受控tests。
4. 完整跑通QQQ/SPY，再做缺失期间交易、熊市回补、开关语义、前缀一致性及新旧信号差异验收。
5. 以上通过后再冻结对照版本，启动Phase 2；本阶段不要夹带策略参数优化。
