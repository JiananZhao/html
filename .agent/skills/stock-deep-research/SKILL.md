---
name: stock-deep-research
description: 执行美股个股全景量化精算、基本面排雷与 Gemini 深度投研分析。当用户要求分析某只个股（如 NVDA、AAPL、MSFT、CRM、TEAM、BE）或排查中长期持仓风险、索取估值范围与投资建议时触发此技能。
---

# 个股全景量化排雷与 Gemini 深度投研分析规程 (Stock Deep Research SOP · 机构升级版)

当用户在对话框或 CLI 中要求深度分析某只股票（例如“帮我深度分析 CRM，给出估值范围和投资建议”、“排查 TEAM 中长期风险”）时，必须严格执行以下标准买方投研流水线：

## 第一步：一键运行本地量化底稿总控脚本
在工作区终端运行：
```bash
python generate_stock_dossier.py --ticker <TICKER>
```
* 该脚本会自动检查本地缓存，若超过 24 小时或首次运行，将自动从 SEC EDGAR 拉取 XBRL 财务历史、申报文档、8-K 业绩指引，并融合美国 10 年期国债最新无风险利率 $R_f$ 动态测算 WACC、三阶段自由现金流 DCF 双口径估值、5 年 PE/PS 估值分位、相对 SPY Alpha、100 分量化评分卡以及反现价锚定的左右侧双轨建仓网格。

## 第二步：直读本地生成的精炼投研底稿
调用 `read_file` 工具读取：
* `dossiers/<TICKER>/<TICKER>_gemini_context.md`
* 若需查阅特定财务科目历史、敏感性矩阵或期权博弈细节，可查阅 `dossiers/<TICKER>/<TICKER>_quant_dossier.json`。

## 第三步：执行机构级七维深度买方投研推理 (严禁空洞套话)
必须严格按照以下七大结构化模块输出深度报告，**每一个论点与结论都必须引用第二步底稿中的具体量化数字作为实证支撑**：

1. **【模块一：估值前置参数核验卡与反现价锚定定性 (Pre-Flight Audit & Anti-Anchoring Thesis)】**
   - 列出前置核验卡关键硬参数：10Y 美债无风险利率 $R_f$、调整后 $\beta$、股权风险溢价 ERP、税后债务成本 $R_d$、综合动态 WACC 与稀释股本；
   - 引用**五维 100 分量化总分与机构评级**（如：`STRONG BUY` / `ACCUMULATE` / `HOLD` / `TRIM` / `AVOID`）及五维得分明细；
   - 确立**反现价锚定原则**：明确声明内在公允价值严格由未来现金流折现与资产负债表体质决定，绝不因即期市场亢奋或历史最高价而产生锚定漂移。

2. **【模块二：佩蕾丝技术周期与行业相空间定位 (Perez Cycle & Phase Space)】**
   - 判定技术革命周期所处阶段：导入期狂热（Installation / Frenzy）、转折点崩塌（Turning Point）、展开期协同（Deployment / Golden Age）还是成熟停滞期（Maturity）；
   - 结合微观反身性相空间象限（加速主升、亢奋见顶、恐慌出清、蓄势筑底），解读 20D/200D 偏离度 Bias、RSI(14) 与相对大盘 SPY 的 Alpha (1M/3M/6M) 表现；
   - 引用历史相似相空间状态下的**未来 6M / 1Y 真实胜率（Win Rate %）**与中位数预期收益。

3. **【模块三：商业模式分流体检与基本面法务排雷 (Archetype Routing & Forensic Audit)】**
   - 明确公司商业模式分流：
     * `WHITE_CHIP_COMPOUNDER` (稳健白马/现金牛)：重点审计 ROIC vs WACC 经济增加值利差 (EVA Spread)、真实自由现金流收益率 (FCF Yield) 与净股票回购收益率 (Net Buyback Yield)；
     * `HIGH_SBC_GROWTH` (高股权激励成长)：穿透扣除 SBC 后的 **True FCF** 与真实稀释成本，揭示每股股东权益是否被稀释侵蚀；
     * `TURNAROUND_CYCLICAL` (困境反转/重资产)：重点审计现金跑道 (Cash Runway)、利息覆盖倍数、存货与应收周转率改善迹象；
   - 交叉审计收入、应收账款与存货增速背离情况，评估 Piotroski F-Score (0-9 分) 财务体质变化。

4. **【模块四：业绩指引软化与估值戴维斯双杀排查 (Guidance Softening vs Re-Rating Risk)】**
   - 交叉比对 8-K 官方指引 / 管理层业绩公告陈述与 SEC 披露的真实硬指标；
   - 诊断是否存在“营收指引下调、订单能见度缩短、非 GAAP 调整激增”等估值倍数压缩 (Multiple Compression) 早期风险信号。

5. **【模块五：反锚定双口径 DCF 估值与敏感性矩阵 (Anti-Anchoring Dual-Caliber DCF)】**
   - 对比列出两大口径估值：
     * **标准报告口径 DCF**：公允价值与 20% 安全边际 (MOS) 买入价；
     * **扣除 SBC 调整后真实买方口径 DCF**：公允价值与 20% 安全边际 (MOS) 买入价；
   - 引用 **WACC 动态敏感性矩阵**（不同 WACC 与永续增长率 $g_n$ 组合下的股价矩阵）；
   - 对比 5 年历史 PE / PS Band 历史分位，并给出最严苛压力测试下的估值底托 (Stress-Test Floor)。

6. **【模块六：🕵️‍♂️ 红队做空反方对抗排雷 (Devil's Advocate / Top 3 Lethal Failure Modes)】**
   - **强制站在做空机构或对冲基金风险合规官视角**，绝不允许只讲好话；
   - 梳理出最可能击穿多头逻辑的 **Top 3 致命暗雷**（如：SBC 隐蔽稀释爆发、客户采购预算紧缩、技术替代侵蚀毛利、大宗负债再融资压力），并给出量化实证支撑。

7. **【模块七：双轨制战术执行网格与投资建议决策 (Dual-Track Tactical Execution & Playbook)】**
   - **轨道一：左侧价值投资者网格 (Value Accumulator Grid)**
     * 安全建仓线 (Safety Buy Line)：基于扣 SBC 后 DCF 20% MOS 或估值底托；
     * 极度悲观底托线 (Bear Case Floor)；
     * 执行法则：跌入安全线分批网格吸筹，无视短期均线破位。
   - **轨道二：右侧动量趋势交易者网格 (Momentum Trend-Follower Grid)**
     * 战术突破跟进位 (Tactical Entry)：$\max(\text{SMA20}, \text{SMA200})$；
     * 动态 ATR 吊灯止损位 (Dynamic 2xATR Stop Loss)；
     * 背离警报协议 (Paradox Protocol)：若即期市价显著高于左侧内在安全线，明确标注该交易为“高溢价右侧博弈，缺乏内在安全垫，破 ATR 止损位必须机械斩仓”；
   - **下季度核心证伪锚点 (Kill Switches)**：给出 2 个下季度财报必须盯紧的硬性数字阈值。

## 第四步：双端保存与同步
在对话框向用户输出完整买方研报的同时，**必须使用 `write_file` 工具将该报告完整保存到**：
`dossiers/<TICKER>/<TICKER>_gemini_report.md`
使 Streamlit 网页端在用户打开该个股或刷新页面时，能够永久保存并在“Gemini 深度投研”面板自动高品质呈现！
