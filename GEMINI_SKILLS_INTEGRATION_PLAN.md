# 🚀 GeminiSkills 历史投研技能库与本地量化系统深度融合执行计划 (Integration Master Plan)

> **制定时间**：`2026-10-23`  
> **融合源目录**：`E:\AI\Github_AIProject\html\GeminiSkills`（共 13 个独立买方投研与量化估值 Skill 包）  
> **目标系统**：本地多源数据采集器 (`stock_data_harvester.py`) + 机构级量化排雷引擎 (`stock_quant_analyzer.py`) + Antigravity 深度投研技能 (`.agent/skills/stock-deep-research/SKILL.md`) + Streamlit 交互终端 (`stock_tab.py`, `company_tab.py`)  
> **核心原则**：100% 本地优先脱机闭环、零假设前置核验、反现价锚定（Anti-Anchoring）、双口径 FCF 强制披露、左右侧双轨制分流风控。

---

## 一、 融合背景与核心互补价值

通过对 `GeminiSkills` 目录下全部 13 个技能包（约 6.9 万字节）的拆解，我们提炼出 **6 大核心买方精髓**，与当前系统的 **SEC XBRL 原始财报引擎 + 索罗斯反身性动力学相空间** 形成完美的互补闭环：

| 痛点维度 | 融合前现状 | 融合 `GeminiSkills` 后的机构级升级 | 对应源 Skill 包 |
| :--- | :--- | :--- | :--- |
| **1. SEC 季报口径与科目深度** | 10-Q 存在 9M 累计值与 3M 单季值混用；缺少利息、税项、股东权益、D&A | **精确拆分 3M 单季值与 TTM（近4季滚动）值**；新增提取利息支出、所得税、股东权益、短期债务、折旧摊销（D&A） | `equity-ground-truth-verifier`<br>`single-stock-fundamental-engine` |
| **2. WACC 与正向 DCF 估值** | 硬编码 `WACC=9.0%`；仅算反向 DCF 隐含增速，易受现价锚定影响 | 接入本地 `daily-treasury-rates.csv` 实时 10Y 美债 $R_f$ 合成**动态 WACC**；新增**反锚定双口径三阶段正向 DCF（含/扣 SBC）+ 3×3 敏感性矩阵** | `single-stock-valuation-engine`<br>`valuation-preflight-verifier` |
| **3. 公司生命周期分流评估** | 对亏损/重资产爬坡股（如 `BE`）使用同一套 DCF/PE 模板，导致估值失效 | 新增**公司类型自动分流器（Archetype Router）**：自动区分「稳健白马」、「高 SBC 软件股」与「困境反转/重资产周期股」（启用 P/S Band、P/B 重置成本、正常化 EPS、现金跑道 Cash Runway） | `turnaround-cyclical-evaluator`<br>`equity-rating-engine`<br>`long-term-value-evaluator` |
| **4. 资本配置效率与股东回报** | 仅计算 SBC/OCF，未量化回购注销对冲效应与投入资本回报率 | 新增 **$\text{ROIC vs. WACC}$ 经济增加值（EVA）利差**、**基于 SEC 股本变动的真实净回购注销率（Net Buyback Yield）**、**$\text{Net Debt / EBITDA}$** 与 **利息保障倍数** | `single-stock-fundamental-engine`<br>`equityanalyzer` |
| **5. 微观动量与五维 100 分评分** | 仅有相空间坐标，缺少相对大盘 Alpha、历史估值分位与综合定量总分 | 新增 **5 年历史 PE/PS Band 分位数**、**12-1M 动量**、**相对 SPY 1M/3M/6M 超额 Alpha**、**14D ATR% 动态止损** 及 **五维 100 分制加权量化评分卡** | `single-stock-market-micro-engine`<br>`single-stock-quant-orchestrator` |
| **6. 交易风控与产业周期叙事** | 左侧抄底与右侧止损混杂；缺少对当季 Beat 但指引放缓的专项压力测试 | 引入 **左右侧双轨制价格网格与《破位矛盾处置协议》**；融合 **佩雷斯技术周期（Perez Cycle）** 与 **指引放缓估值乘数重构（Multiple Re-rating）压力测试** | `single-stock-quant-orchestrator`<br>`公司季度财报分析`<br>`industryanalyzer` |

---

## 二、 分阶段详细实施蓝图 (6-Phase Execution Blueprint)

### 🛠️ 第一阶段：数据采集层扩容与 SEC XBRL 单季/TTM 精确消歧 (`stock_data_harvester.py`)

1. **扩充 SEC US-GAAP XBRL 核心提取科目 (`harvest_sec_xbrl_facts`)**：
   在现有 15 个科目的基础上，新增提取以下 5 个关键财务科目：
   * `InterestExpense`: `["InterestExpense", "InterestExpenseDebt", "InterestAndDebtExpense"]`
   * `IncomeTaxExpense`: `["IncomeTaxExpenseBenefit"]`
   * `StockholdersEquity`: `["StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"]`
   * `ShortTermDebt`: `["ShortTermBorrowings", "DebtCurrent", "LongTermDebtCurrent"]`
   * `DepreciationAmortization`: `["DepreciationDepletionAndAmortization", "DepreciationAndAmortization"]`
2. **修复 10-Q 累计值（YTD）与单季值（3M）混用问题**：
   * 对于流量型科目（`Revenues`, `GrossProfit`, `OperatingIncome`, `NetIncome`, `OCF`, `CapEx`, `SBC`, `InterestExpense`, `IncomeTaxExpense`, `DepreciationAmortization`），检查 XBRL 条目的 `start` 与 `end` 日期天数差 `duration_days = (end - start).days`：
     * 在 `10-Q` 中优先绑定 `70 <= duration_days <= 105` 的纯单季（3M）数值；
     * 若某现金流科目在 Q2/Q3 仅披露 YTD 累计值（`160 <= duration_days <= 285`），则自动通过同财年上一季度累计值执行差分还原（$\text{Q}_t = \text{YTD}_t - \text{YTD}_{t-1}$），确保每一期记录均为纯粹的单季流量或标准年报流量。
   * 在生成的 `sec_financial_history.csv` 中，基于最近 4 个连续单季（或最新年报）自动计算 **TTM（过去 12 个月滚动）核心指标**。
3. **接入本地无风险利率底库与估值画像 (`harvest_market_options_and_macro`)**：
   * 直接读取工作区根目录下的 [`daily-treasury-rates.csv`](file:///e:/AI/Github_AIProject/html/daily-treasury-rates.csv)，提取最新交易日的 **10 年期美债收益率 (`10 Yr`, $R_f$)** 与 **3 个月美债收益率 (`3 Mo`)** 写入 `market_snapshot.json`；
   * 补充保存 `beta`、`bookValue`、`priceToBook`、`enterpriseToEbitda`、`enterpriseToRevenue`、`fiftyTwoWeekHigh`、`fiftyTwoWeekLow`、`dividendYield`。

---

### ⚙️ 第二阶段：基本面质量、偿债安全与资本配置效率引擎升级 (`stock_quant_analyzer.py` - 模块 1)

在 `analyze_fundamental_quality_and_forensics()` 中全面实现 `single-stock-fundamental-engine` 与 `long-term-value-evaluator` 的硬指标体系：

1. **双口径 TTM 自由现金流与营收动能**：
   * `ttm_revenues_b`（近 4 季滚动营收）与过去 4 个季度逐季 YoY 增速序列 `quarterly_rev_yoy_series`；
   * **口径 A（标准 FCF）**：$\text{TTM Standard FCF} = \text{TTM OCF} - \text{TTM CapEx}$（及 Standard FCF Margin %）；
   * **口径 B（扣除 SBC 股东真实 FCF）**：$\text{TTM Adj. FCF} = \text{TTM OCF} - \text{TTM CapEx} - \text{TTM SBC}$（及 Adj. FCF Margin %）；
   * `sbc_to_rev_pct`（SBC 占营收比重）与 `capex_to_rev_pct`（资本开支占营收比）。
2. **资产负债表与偿债安全度（Solvency & Cash Runway）**：
   * **净债务（Net Debt）**：$\text{Net Debt} = (\text{LongTermDebt} + \text{ShortTermDebt}) - \text{CashEquivalents}$（若 $<0$ 则标注为「净现金 Net Cash」）；
   * **净杠杆倍数（Net Debt / EBITDA）**：其中 $\text{EBITDA} = \text{TTM Operating Income} + \text{TTM D\&A}$；
   * **利息保障倍数（Interest Coverage）**：$\text{EBIT} / \text{Interest Expense}$；
   * **现金跑道（Cash Runway Quarters，专用于亏损/转型股）**：若 $\text{TTM Std FCF} < 0$，计算账面现金可支撑的季度数 $\text{Runway} = \frac{\text{Cash}}{|\text{TTM Std FCF}| / 4}$。
3. **资本分配效率（ROIC vs. WACC & 真实净回购注销率）**：
   * **投入资本回报率（ROIC）**：
     $$\text{NOPAT} = \text{TTM Operating Income} \times (1 - T_{\text{eff}}), \quad \text{Invested Capital} = \text{Total Debt} + \text{Stockholders Equity} - \max(0, \text{Cash} - 0.05 \times \text{TTM Rev})$$
     $$\text{ROIC} = \frac{\text{NOPAT}}{\text{Invested Capital}} \times 100\%$$
   * **经济增加值利差（EVA Spread）**：$\text{EVA Spread} = \text{ROIC} - \text{WACC}$；
   * **真实净股份注销回购率（Net Buyback Yield %）**：对比 SEC 最新股本与 4 个季度前的股本变化率：
     $$\text{Net Buyback Yield} = -\frac{\text{Shares}_{\text{latest}} - \text{Shares}_{t-4}}{\text{Shares}_{t-4}} \times 100\%$$
     （正值代表公司正在净注销股本增厚 EPS，负值代表公司在净增发稀释老股东）；
   * **股东总回报率（Total Shareholder Yield %）** = $\text{Net Buyback Yield} + \text{Dividend Yield}$。

---

### 💰 第三阶段：前置参数核验、公司类型分流与反锚定双口径 DCF 引擎 (`stock_quant_analyzer.py` - 模块 2)

在 `analyze_valuation_and_expectations_gap()` 中全面实现 `single-stock-valuation-engine` 与 `turnaround-cyclical-evaluator`：

1. **生成《估值前置参数核验卡》(Pre-Flight Parameter Audit Card)**：
   * 实时/本地无风险利率 $R_f$（取自 `daily-treasury-rates.csv` 10Y 美债收益率）；
   * 调整后 $\beta = \text{clip}(\frac{2}{3}\beta_{\text{raw}} + \frac{1}{3}\times 1.0, 0.65, 2.0)$；
   * 股权风险溢价 $\text{ERP} = 4.75\%$，股权成本 $R_e = R_f + \beta \times \text{ERP}$；
   * 债务成本 $R_d = \text{clip}(\frac{\text{Interest Expense}}{\text{Total Debt}}, R_f + 0.5\%, 12.0\%)$；
   * 按市值 $E$ 与总债务 $D$ 权重计算精确 **动态 WACC**。
2. **公司类型自动识别与评估模式分流器（Archetype Router）**：
   * **`WHITE_CHIP_COMPOUNDER`（稳健白马/现金牛模式）**：$\text{TTM Adj. FCF} > 0$ 且 $\text{ROIC} \ge \text{WACC}$；
   * **`HIGH_SBC_GROWTH`（高股权激励成长模式）**：$\text{TTM Std FCF} > 0$ 但 $\text{SBC / OCF} > 45\%$；
   * **`TURNAROUND_CYCLICAL`（困境反转/周期重资产模式）**：$\text{TTM Std FCF} \le 0$ 或营业利润率 $< 3\%$。
3. **反现价锚定·双口径三阶段正向 DCF 模型（3-Stage Forward DCF）**：
   * **增长率内生设定（严禁向当前股价锚定）**：
     * 第一阶段（1~5 年 $g_1$）：基于历史 3Y 营收/FCF 增速、ROIC 内生增长率，限制在 $[4.0\%, 22.0\%]$ 合理基本面区间；
     * 第二阶段（6~10 年 $g_2$）：从 $g_1$ 线性衰减收敛至长期名义 GDP 增速 $3.0\%$；
     * 第三阶段（永续期 $g_n$）：基准取 $2.5\%$。
   * **双口径每股价值输出**：
     * **口径 A（Standard FCF 口径）**：基准内在价值 $V_{\text{DCF, Std}}$ 与 $-20\%$ 安全边际价 $V_{\text{MOS, Std}}$；
     * **口径 B（Post-SBC Adj. FCF 口径，买方核心基准）**：基准内在价值 $V_{\text{DCF, Adj}}$ 与 $-20\%$ 安全边际价 $V_{\text{MOS, Adj}}$；
   * **3×3 敏感性矩阵（Sensitivity Matrix）**：输出 $\text{WACC} \in [\text{WACC}-0.5\%, \text{WACC}, \text{WACC}+0.5\%] \times g_n \in [2.0\%, 2.5\%, 3.0\%]$ 的 9 宫格每股公允价矩阵。
4. **5 年历史估值通道（PE / PS Band）与困境反转专项估值**：
   * 利用 5 年日线价格与 SEC 滚动 EPS/营收序列，计算过去 5 年 **PE Band 与 PS Band** 的 $[\mu - 2\sigma, \mu - 1\sigma, \mu, \mu + 1\sigma, \mu + 2\sigma]$ 对应股价及 **当前所处历史百分位（Percentile Rank %）**；
   * **估值乘数重构压力测试（Multiple Compression Floor）**：测算当增长放缓导致估值倍数压缩至 $\min(15\text{x PE}, \mu - 1.5\sigma)$ 时的下行底托价；
   * **困境反转专项指标（针对模式 C）**：计算 `P/B` 账面重置成本位、按 $12\%\sim15\%$ 行业中枢利润率还原的 `Normalized Mid-Cycle EPS` 及对应合理复苏目标价。

---

### 📈 第四阶段：微观动量、五维 100 分评分与左右侧双轨执行网格 (`stock_quant_analyzer.py` - 模块 3 & 5)

全面融合 `single-stock-market-micro-engine` 与 `single-stock-quant-orchestrator`：

1. **量价动量与相对大盘超额 Alpha (`analyze_reflexivity_and_sentiment` 扩展)**：
   * 计算 `SMA_20`, `SMA_50`, `SMA_200` 均线排列状态及乖离率 `Bias_20D %`, `Bias_200D %`；
   * 计算 **12-1M 经典动量 ($\text{MOM}_{12-1}$)**；
   * 对比本地 [`spy_ohlcv_local.csv`](file:///e:/AI/Github_AIProject/html/spy_ohlcv_local.csv)，计算过去 **1M / 3M / 6M 相对 SPY 的超额强弱收益 (`Alpha_vs_SPY_1M`, `3M`, `6M`)**；
   * 计算日线 `RSI(14)` 与 `14D ATR%`（自适应波动率）。
2. **五维 100 分制量化多因子打分矩阵 (`calculate_multi_factor_score_and_dual_track`)**：
   * **一、质量分 (Quality Score, 满分 30 分)**：营收/毛利趋势(8分) + Adj. FCF利润率与OCF/NI(10分) + 净杠杆与利息覆盖(6分) + ROIC>WACC与净回购(6分)；
   * **二、估值分 (Valuation Score, 满分 25 分)**：现价相对DCF安全边际(10分) + 5年PE/PS分位数(7分) + 反向DCF预期差(4分) + 华尔街目标空间(4分)；
   * **三、动量与相空间分 (Momentum & Phase Space, 满分 20 分)**：相空间象限与1Y历史胜率(10分) + 均线排列与相对SPY Alpha(6分) + RSI状态(4分)；
   * **四、筹码与期权分 (Positioning Score, 满分 15 分)**：期权Max Pain引力(5分) + PCR多空平衡(5分) + 做空比例与回补天数(5分)；
   * **五、基本面健康与催化分 (Health & Catalyst, 满分 10 分)**：Piotroski F-Score 与财报指引状态(10分)；
   * 输出 **Total Quant Score (0~100)** 与量化定级（`STRONG BUY [>=80]` / `ACCUMULATE [65~79]` / `HOLD [50~64]` / `TRIM [35~49]` / `AVOID [<35]`）。
3. **反锚定左右侧双轨制建仓与《破位矛盾处置协议》网格**：
   * **【轨道一：左侧内在价值安全边际网格 (Intrinsic Value Grid - 反现价锚定)】**：
     * `保守价值建仓线 (Safety Buy Line)`：取 $V_{\text{MOS, Adj}}$（或困境股的 PS Band 20% 分位价），**不随现价涨跌发生漂移**；
     * `极端悲观底托线 (Extreme Bear Floor)`：取乘数压缩压力测试底托价（Multiple Compression Floor）。
   * **【轨道二：右侧战术动量与相空间共振网格 (Tactical Momentum Grid)】**：
     * `战术突破/回踩入场位`：依托 `SMA_20 / SMA_50 / SMA_200` 与相空间象限切换位；
     * `动态 ATR 硬止损位`：$\text{Current Price} - 2.0 \times \text{ATR}_{14}$；
     * `高溢价背离警示 (Divergence Warning)`：当现价高于左侧安全建仓线 $>15\%$ 时，自动生成醒目风险提示：**“⚠️ 当前市价显著高于内在价值安全边际线，右侧买入属于高溢价趋势博弈，无内在价值安全垫保护，一旦跌破 2xATR 止损位必须机械离场！”**

---

### 📝 第五阶段：升级 Antigravity 深度投研技能规程 ([`.agent/skills/stock-deep-research/SKILL.md`](file:///e:/AI/Github_AIProject/html/.agent/skills/stock-deep-research/SKILL.md))

将 `.agent/skills/stock-deep-research/SKILL.md` 升级为融合 13 个 Skill 精髓的 **买方投委会 7 模块标准 SOP**：
1. **模块零：《估值前置参数核验卡》与五维量化多因子总分（0~100 分）**
2. **模块一：中观佩雷斯技术周期（Perez Cycle）与微观索罗斯反身性相空间定性（含历史相似样本 3M/6M/1Y 胜率）**
3. **模块二：基本面法务排雷、双口径 FCF、资本配置效率（ROIC vs. WACC、净回购注销率）与公司模式分流审计**
4. **模块三：当季业绩 Actuals vs. 未来指引（Guidance Softening）结构性拆解与估值乘数重构评估**
5. **模块四：反锚定双口径三阶段 DCF、3×3 敏感性矩阵、5 年 PE/PS Band 分位与三大情景目标区间**
6. **模块五：🕵️‍♂️ 红队做空排雷（Devil's Advocate Top 3 致命暗雷）**
7. **模块六：左右侧双轨制交易网格（Value Grid vs. Momentum Grid）、《破位矛盾处置协议》与下季财报硬性证伪锚点**

---

### 🖥️ 第六阶段：Streamlit 网页端看板升级与多标的实证回归验证 (`stock_tab.py` & `company_tab.py`)

1. **升级 `render_gemini_dossier_panel(ticker)` UI 面板**：
   * 顶部新增 **第 1 行核心卡片**：`五维量化总分 (Score/100 & 评级)`、`双口径 DCF 内在价值 (扣SBC基准 vs 标准口径)`、`ROIC vs WACC 价值创造利差`、`真实净股份注销率 (Shareholder Yield)`；
   * 保留并优化 **第 2 行核心卡片**：`真实 FCF 利润率 (扣SBC)`、`盈利含金量 (OCF/NI)`、`5年历史估值分位 (PE/PS Band Percentile)`、`历史相似相空间 1Y 真实胜率`；
   * 在折叠面板中新增展示 **《估值前置参数核验卡》、《3×3 DCF 敏感性矩阵》与《左右侧双轨制建仓与 ATR 止损网格》**。
2. **全量实证测试（遵守铁律第 2、4、10、12 条）**：
   * 在本地针对三大代表性公司类型运行 `python generate_stock_dossier.py --ticker <TICKER> --force`：
     * 稳健白马/低估现金牛：`CRM`, `ADBE`
     * 高增长龙头：`NVDA`
     * 高 SBC 软件股：`TEAM`
     * 重资产亏损/周期转型股：`BE`
   * 验证所有脚本 `Exit Code 0`，核对生成的 JSON 与 Markdown 底稿数值无 `KeyError/AttributeError`，并更新对应的 `_gemini_report.md`。
