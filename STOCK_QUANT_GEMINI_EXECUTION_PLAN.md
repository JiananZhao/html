# 个股中长期量化分析与 Gemini 智能投研系统 —— 详细执行计划书

> **文档路径**：`e:\AI\Github_AIProject\html\STOCK_QUANT_GEMINI_EXECUTION_PLAN.md`  
> **核心定位**：面向美股中长期价值与趋势持仓，构建一套**“Python 多源数据采集（含 SEC 官方财报与电话会纪要） $\rightarrow$ 本地确定性量化模型精算（基本面排雷 + 估值预期差 + 相空间情绪动力学） $\rightarrow$ Antigravity 对话框/CLI 内置 Gemini 自动读取并深度推理 $\rightarrow$ Streamlit 网页端宽屏可视化呈现”**的零额外 API 成本全自动投研闭环。

---

## 一、 核心设计哲学与系统架构图

### 1. 为什么要采用“Python 本地精算 + 对话框 Gemini 直读”架构？
1. **零额外 API 费用**：完全复用你现有的 Google Gemini Pro（Antigravity IDE 对话框 / `agy` CLI）权限，无需在代码中额外付费购买高并发 LLM API Token。
2. **杜绝大模型算术幻觉（Zero Arithmetic Hallucination）**：所有涉及财务比率、现金流折现（Reverse DCF）、滚动分位数、李雅普诺夫相空间导数、历史相似样本胜率回溯的数学运算，100% 由本地 Python 脚本精确计算。
3. **高信噪比上下文注入（High-SNR Context Injection）**：原始 SEC 10-K 年报动辄 150 页、10 年日线行情逾 2500 行。Python 脚本负责前置清洗与结构化提炼，将数万行原始数据压缩为**高信息密度的结构化定量 JSON + 关键定性文本切片（MD&A、风险因素、电话会 Q&A）**，再由 Gemini 读取并执行跨维度逻辑推理与红队风险排雷（Red-Teaming）。

### 2. 全链路自动化数据流向图

```
┌──────────────────────────────────────────────────────────────────────────────┐
│ 【触发层】你在当前 Antigravity 对话框（或 CLI）输入：“深度分析 NVDA”           │
└───────────────────────────────────────┬──────────────────────────────────────┘
                                        ▼ (Gemini 自动调用终端 run_command)
┌──────────────────────────────────────────────────────────────────────────────┐
│ 【Step A：多源数据采集层 (stock_data_harvester.py)】                           │
│  1. SEC EDGAR 官方库：10-K/10-Q 章节、8-K 业绩公告、XBRL 历史财务库、Form 4   │
│  2. 财报电话会议纪要 (Transcripts)：管理层 Guidance 陈述 + 分析师 Q&A 问答     │
│  3. 行情与宏观底库：优先读取本地 CSV + 增量同步最新 OHLCV 与 FRED 宏观利差     │
│  4. 衍生品与微观博弈：期权链 (PCR / Max Pain / IV Skew)、空头持仓 (Short%)     │
│  5. 行业与同业对标：所属板块 ETF (如 SMH/IGV/SPY) 相对强弱与估值对比           │
└───────────────────────────────────────┬──────────────────────────────────────┘
                                        ▼ (原始数据自动落盘至 dossiers/{TICKER}/raw/)
┌──────────────────────────────────────────────────────────────────────────────┐
│ 【Step B：确定性量化精算层 (stock_quant_analyzer.py)】                         │
│  1. 基本面质量与财务排雷：真实 FCF (扣 SBC)、盈利含金量、应收/存货异动、ROIC   │
│  2. 估值与预期差模型：Reverse DCF 隐含增速 vs 历史增速、5年 PE/PS 动态分位     │
│  3. 多维情绪与反身性雷达：相空间四象限 (q1, q1_dot, v_dot)、0~100 综合得分    │
│  4. 历史相似相空间回溯：同估值+同象限历史样本下未来 3M/6M/1Y 真实胜率与回撤    │
└───────────────────────────────────────┬──────────────────────────────────────┘
                                        ▼ (汇总输出 dossiers/{TICKER}/quant_dossier.json)
┌──────────────────────────────────────────────────────────────────────────────┐
│ 【Step C：Gemini 深度推理与红队排雷层 (当前对话框自动 read_file & write_file)】 │
│  Gemini 自动读取本地 quant_dossier.json + SEC/电话会核心文本切片，执行：        │
│  - [基本面护城河定性] 财报数字与管理层电话会口径交叉验证                       │
│  - [情绪与估值共振诊断] 当前处于“恐慌错杀黄金坑”、“健康蓄势”还是“高危泡沫”     │
│  - [红队做空排雷 (Devil's Advocate)] 揪出 Top 3 潜在财务/业务/宏观暗雷          │
│  - [中长期持仓预案 (If-Then Playbook)] 明确下季财报核心观测点与相空间止损锚    │
└───────────────────────────────────────┬──────────────────────────────────────┘
                                        ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│ 【Step D：双端同步呈现】                                                       │
│  1. 在当前对话框内直接输出深度报告，支持你随时针对细节连续追问                 │
│  2. 自动写入 dossiers/{TICKER}/gemini_report.md，Streamlit 宽屏网页同步渲染！  │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 二、 Python 脚本具体要获取哪些数据？（七大核心数据支柱详解）

为了支撑**中长期持有**决策，单看 K 线和简单市盈率远远不够。Python 采集脚本将从互联网公开权威渠道自动获取并本地化存储以下 **7 大类核心数据**：

### 支柱 1：SEC EDGAR 官方监管申报文件（一手权威基本面与排雷源）
> **获取方式**：直接调用美国证监会官方免费接口 `data.sec.gov`（无需付费 API Key，仅需设置合规 `User-Agent` 头，通过官方 `company_tickers.json` 自动将股票代码转换为 10 位 `CIK` 编号）。

1. **SEC XBRL 全历史结构化财务事实库 (`api/xbrl/companyfacts/CIK{cik}.json`)**
   * **解决痛点**：突破免费行情接口通常只返回最近 4~5 期财报的限制，直接获取长达 5~10 年的官方标准化 GAAP 财务数据。
   * **核心抓取科目**：
     * 利润表：营业收入（Revenues）、毛利（Gross Profit）、研发费用（R&D）、销售与管理费用（SG&A）、营业利润（Operating Income）、净利润（Net Income）、稀释每股收益（Diluted EPS）。
     * 现金流量表：经营活动现金流（OCF）、资本开支（CapEx）、**股权激励费用（Stock-Based Compensation, SBC）**、股票回购金额（Share Repurchases）与分红。
     * 资产负债表与前瞻指标：现金及短期投资、**应收账款（Accounts Receivable）**、**存货（Inventory）**、**递延收入与剩余履约义务（Deferred Revenue / RPO —— 衡量未来业绩锁定度的黄金领先指标）**、总有息债务（Short/Long-term Debt）。
2. **10-K（年报）与 10-Q（季报）核心文本章节提取**
   * 脚本自动下载最新一期 10-K 和最近两期 10-Q 的 HTML/文本，通过正则与 DOM 解析精准截取高价值章节（过滤冗长格式套话）：
     * **Item 1A - Risk Factors（风险因素）**：重点提取公司披露的供应链依赖、客户集中度、地缘政治/出口管制、监管诉讼及竞争加剧描述。
     * **Item 7 / Item 2 - MD&A（管理层讨论与分析）**：提取各业务分部（Segments）收入增速拆解、毛利率变动原因说明、订单积压（Backlog）及资本开支计划。
3. **8-K 重大事件披露（Current Reports，近 6~12 个月）**
   * 自动扫描并标记关键事件代码：
     * `Item 2.02`：最新财报业绩新闻稿（Earnings Release 原文及附表，含 Non-GAAP 调节表与官方下季度 Guidance 指引）；
     * `Item 5.02`：核心高管（CEO / CFO / 首席会计官）离职或变动；
     * `Item 4.01 / 4.02`：更换会计师事务所或**历史财报重述（Restatement，最高级别财务暴雷信号）**；
     * `Item 1.01 / 2.01`：重大并购、资产出售或大额商业合同签署。
4. **Form 4 内部人交易明细（Insider Transactions，近 6 个月）**
   * 提取公司高管与董事在公开市场的真实买卖记录，区分**高管自掏腰包公开市场买入（Strong Bullish Signal）**与常规期权行权/预设计划减持。

---

### 支柱 2：财报电话会议纪要（Earnings Call Transcripts）与管理层前瞻指引
> **为什么必不可少**：财务报表反映的是过去，而电话会议上管理层的开场陈述（Prepared Remarks）和华尔街分析师的尖锐追问（Q&A）直接决定了中长期叙事逻辑是否依然成立。

1. **需要提取的核心内容**：
   * **官方业绩指引（Forward Guidance）**：管理层对下一季度及全年的营收范围、Non-GAAP 毛利率、运营费用率及资本开支的具体数字预期；
   * **核心叙事与战略重心**：新产品商业化进度（如新架构芯片量产时间、AI 软件商业化变现率）、产能扩张或成本削减进展；
   * **分析师 Q&A 攻防细节**：高管在面对分析师关于“竞争对手抢份额”、“客户推迟下单”、“毛利率下滑压力”等尖锐问题时的正面回应或回避态度。
2. **Python 脚本多通道获取策略（三级容错机制）**：
   * **通道 1（官方 8-K Exhibit 99.1 直取）**：自动从最新财报日提交的 SEC 8-K 附件中提取完整 Earnings Release 新闻稿与 CFO 业绩评论；
   * **通道 2（公开财报纪要网页自动检索与解析）**：脚本通过公开财经源检索提取最近 1~2 个季度的 Earnings Call Transcript 全文段落与 Q&A 实录；
   * **通道 3（本地纪要投喂接口）**：支持读取 `dossiers/{TICKER}/transcripts/` 下的任意本地文本文档，并在必要时由对话框内的 Gemini 配合 `search_web` 实时补全最新季度电话会要点。

---

### 支柱 3：华尔街一致预期、盈利修正与同业对标数据（Consensus & Peer Benchmark）
1. **盈利超预期历史（Earnings Surprise History）**：过去 4~8 个季度实际 EPS / 营收对比华尔街一致预期的 Beat / Miss 百分比（检验公司是否具备持续“低预期指引、高实际交付”的优秀管理层基因）。
2. **前瞻一致预期（Forward Estimates）**：当前及下一财年的 Consensus EPS、Consensus Revenue、长期预估增长率（LT Growth Rate）以及分析师目标价区间（High / Mean / Low）。
3. **同行业横向对标（Sector & Peer Relative Metrics）**：
   * 自动匹配标的所属行业 ETF（如半导体 `SMH`、软件 `IGV`、金融 `KRE`、能源 `XLE`、大盘 `SPY`/`QQQ`）及 3~5 家核心同行公司，对比营收增速、毛利率、ROE 与 Forward PE，判断该股在行业内是享受龙头溢价还是被折价。

---

### 支柱 4：衍生品期权微观结构与空头博弈数据（Options & Short Sentiment）
1. **期权链博弈分布（复用并扩展项目现有 [`get_stock_options_sentiment`](file:///e:/AI/Github_AIProject/html/data_service.py)）**：
   * 近月汇总（前 6 个到期日）的未平仓认沽/认购比（`PCR_OI`）与成交量比（`PCR_Vol`）；
   * 做市商最大痛点（`Max Pain`）、上方最大看涨持仓阻力位（Call Wall）与下方最大看跌持仓支撑位（Put Wall）。
2. **空头拥挤度（Short Interest）**：
   * 卖空占流通股比例（`Short % of Float`）、空头回补天数（`Days to Cover / Short Ratio`）及较上月变化率（识别机构是否在暗中集结做空）。
3. **机构持股比例与近期大单资金流**：
   * 机构持股占比（`Held Percent Institutions`）、20日蔡金资金流向（`CMF20`）与 50日相对放量倍数（`Vol_Ratio50`）。

---

### 支柱 5：宏观流动性锚与索罗斯反身性相空间数据（Macro & Phase Space）
1. **本地宏观主数据库（直接读取 [market_data_local.csv](file:///e:/AI/Github_AIProject/html/market_data_local.csv) 并增量同步）**：
   * 高收益企业债 ETF（`HYG`）、穆迪 BAA 企业债与 10 年美债利差（`BAA10Y`）、芝加哥联储金融状况指数（`NFCI`）、10 年期 TIPS 实际利率（`Real_Yield`）。
2. **个股相空间动力学状态向量（调用 [`run_universal_reflexivity_radar`](file:///e:/AI/Github_AIProject/html/reflexivity_engine.py#L8-L318)）**：
   * 位置 $q_1$（200MA 偏离度）、速度 $\dot{q}_1$、加速度 $\ddot{q}_1$、李雅普诺夫能量导数 $\dot{V}$、反身性认知偏差 `Gap`、相空间象限（Quadrant 1~4）以及 0~100 综合过热雷达分（`Composite_Score`）。

---

### 支柱 6：近期重大新闻与行业催化剂（Catalysts & News Stream）
* 自动聚合最近 15~30 天的高相关性财经新闻标题、发布时间、来源与摘要（复用并增强 [company_tab.py](file:///e:/AI/Github_AIProject/html/company_tab.py#L112-L160) 的 [`parse_and_enrich_news`](file:///e:/AI/Github_AIProject/html/company_tab.py#L112)），供 Gemini 与定量指标做事件归因交叉验证。

---

## 三、 从最开始到最后一步的详细执行计划（Step-by-Step Roadmap）

整个开发与落地过程共分为 **6 个阶段（Step 1 ~ Step 6）**，每一步均遵循“先查接口 $\rightarrow$ 编写代码 $\rightarrow$ 本地 `python -c` 实证跑通（Exit Code 0） $\rightarrow$ 汇报证据”的严格工程规范。

---

### 【Step 1】前端网页布局拓宽与导航 Tab 视觉升级
* **目标**：解决当前页面两侧留白较多、顶部主导航 Tab 与子 Tab 偏紧凑的问题，并为即将接入的《🤖 Gemini 深度量化投研与风险体检报告》预留宽敞、清晰的展示面板。
* **涉及文件**：
  * [charts/theme.py](file:///e:/AI/Github_AIProject/html/charts/theme.py)
  * [rd_data.py](file:///e:/AI/Github_AIProject/html/rd_data.py)
* **具体执行内容**：
  1. 在 [charts/theme.py](file:///e:/AI/Github_AIProject/html/charts/theme.py) 的深色模式与日间模式 CSS 中，优化 `.block-container` 的最大宽度与左右内边距（如 `max-width: 96% !important; padding-left: 2rem !important; padding-right: 2rem !important;`），充分释放宽屏显示器空间。
  2. 将主导航条（`div[data-testid="stSegmentedControl"]` / `stButtonGroup`）与子标签栏（`div[data-testid="stTabs"]`）升级为**弹性拓宽布局**：
     * 按钮开启 `flex: 1 1 auto !important; justify-content: center !important;`；
     * 按钮内边距从 `10px 18px` 加宽至 `12px 26px`，字号提升至 `16px`，间距（`gap`）提升至 `10px`，确保深浅双模式下所有 Tab 宽敞醒目、绝不拥挤或重叠。
* **本地验证标准**：运行语法与样式渲染验证脚本，确保深色/浅色主题 CSS 输出无误（Exit Code 0）。

---

### 【Step 2】开发多源投研数据采集器 `stock_data_harvester.py`
* **目标**：编写独立、强健、遵循“本地缓存优先 + 增量拉取”原则的数据抓取脚本，一键将目标个股（如 `NVDA`）的 7 大支柱原始数据下载并持久化到本地目录 `dossiers/{TICKER}/raw/`。
* **新建文件**：`e:\AI\Github_AIProject\html\stock_data_harvester.py`
* **核心功能模块**：
  1. `fetch_sec_edgar_data(ticker)`：
     * 自动查询并缓存 `CIK` 映射表；
     * 拉取 SEC XBRL 历史财务事实 JSON（提取多期营收、毛利、R&D、OCF、FCF、SBC、应收账款、存货、递延收入/RPO、债务与股本）；
     * 拉取最近期 10-K / 10-Q 申报元数据与核心章节文本（Item 1A 风险因素、MD&A 管理层讨论），以及最近 6 个月的 8-K 事件列表（含最新财报 Exhibit 99.1 官方业绩新闻稿）和 Form 4 内部人交易汇总。
  2. `fetch_earnings_transcript_and_guidance(ticker)`：
     * 自动从最新 8-K Exhibit 99.1 及公开财报纪要渠道提取管理层业绩指引（Guidance）、高管核心陈述与分析师 Q&A 关键问答，同时扫描 `dossiers/{TICKER}/transcripts/` 本地补充文件。
  3. `fetch_market_and_options_snapshot(ticker)`：
     * 调用本地优先行情服务（[`get_stock_price_data`](file:///e:/AI/Github_AIProject/html/core_engine/stock_data_service.py)、[`get_stock_profile`](file:///e:/AI/Github_AIProject/html/core_engine/stock_data_service.py)、[`get_stock_options_sentiment`](file:///e:/AI/Github_AIProject/html/data_service.py)），汇总最新估值倍数、空头持仓（Short Interest）、分析师预期、期权 PCR/Max Pain 及近期重要新闻。
* **本地验证标准**：在终端执行 `python stock_data_harvester.py --ticker NVDA`，验证 `dossiers/NVDA/raw/` 下成功生成完整的 SEC 数据、财报文本切片与市场数据 JSON 文件，且具备完善的超时保护与本地降级机制。

---

### 【Step 3】开发机构级基本面排雷与情绪定量引擎 `stock_quant_analyzer.py`
* **目标**：读取 Step 2 采集的本地原始数据，在纯本地环境下（100% 脱离网络依赖）完成所有高阶定量建模与风险排雷指标计算。
* **新建文件**：`e:\AI\Github_AIProject\html\stock_quant_analyzer.py`
* **核心定量模型与计算清单**：
  1. **基本面质量与财务排雷评分（Fundamental & Forensic Score, 0~100）**：
     * **盈利含金量（Cash Conversion）**：$\text{OCF} / \text{Net Income}$ 及扣除股权激励后的**真实自由现金流率（$(\text{FCF} - \text{SBC}) / \text{Revenue}$）**；
     * **营收质量排雷（Receivables & Inventory Red Flags）**：计算应收账款同比增速与营收同比增速之差（$\Delta \text{AR} - \Delta \text{Rev}$）、存货同比增速与营业成本增速之差（$\Delta \text{Inv} - \Delta \text{COGS}$），一旦超阈值自动标记“塞渠道/存货积压警告”；
     * **护城河趋势斜率（Moat Trajectory）**：过去 8 个季度毛利率（Gross Margin）、营业利润率（Operating Margin）与 ROIC 的最小二乘线性回归斜率；
     * **Piotroski F-Score（0~9分）** 与 **资产负债抗风险度（Net Cash / Debt-to-EBITDA）**。
  2. **估值安全边际与预期差模型（Valuation & Expectations Gap）**：
     * 调用 [`calculate_reverse_dcf`](file:///e:/AI/Github_AIProject/html/quant_models.py) 算出当前股价隐含未来 10 年 FCF 复合增速 $g_{\text{implied}}$；
     * 计算**预期差（Expectation Spread）**：$g_{\text{implied}} - g_{\text{historical\_3y}}$，定量判定当前股价处于“折价安全区”、“合理定价区”还是“高预期透支区”；
     * 计算过去 5 年 PE / PS / P-FCF 的历史动态分位数。
  3. **多维情绪面与反身性相空间合成（Sentiment & Reflexivity Matrix）**：
     * 调用 [`run_universal_reflexivity_radar`](file:///e:/AI/Github_AIProject/html/reflexivity_engine.py#L8-L318)，提取最新相空间位置 $q_1$、速度 $\dot{q}_1$、加速度 $\ddot{q}_1$、李雅普诺夫导数 $\dot{V}$、反身性偏离度 `Gap`、当前所处象限（Quadrant）与综合得分 `Composite_Score`；
     * 整合期权情绪（`PCR_OI`、`Max Pain` 偏离度）、微观资金流（`CMF20`）与空头挤压指标（`Short % of Float`）。
  4. **历史相似相空间样本胜率回溯（Historical Analogue Backtest）**：
     * 在该股历史序列中检索与当前 `(Composite_Score ± 10, Dist_200MA 区间, 宏观信用状态)` 最相似的历史状态点，严格统计其后 **3个月、6个月、12个月** 的真实持有胜率（Win Rate %）、中位数收益率、平均盈亏比与最大回撤。
  5. **规则化风险警报器（Automated Red-Flag Detector）**：
     * 自动输出机器初筛的硬性风险标签列表（如：`[财务预警] SBC 占 FCF 比例高达 X%`、`[情绪预警] 相空间进入第四象限高位动能衰竭`、`[治理预警] 近期存在 8-K 高管变动或内部人集中减持` 等）。

---

### 【Step 4】开发一键总控脚本 `generate_stock_dossier.py`
* **目标**：将 Step 2（数据采集）与 Step 3（定量精算）串联为单一入口命令，自动生成专门供 Gemini 深度阅读的标准化投研底稿包。
* **新建文件**：`e:\AI\Github_AIProject\html\generate_stock_dossier.py`
* **命令行接口**：
  ```bash
  python generate_stock_dossier.py --ticker NVDA [--force-refresh]
  ```
* **标准输出产物（保存在 `e:\AI\Github_AIProject\html\dossiers\{TICKER}\`）**：
  1. `{TICKER}_quant_dossier.json`：包含所有定量指标、分位数、历史相似胜率、排雷警报与元数据，供前端图表与程序直接调用；
  2. `{TICKER}_gemini_context.md`：将定量精算结果表、SEC 10-K/10-Q 核心风险与 MD&A 摘录、8-K 重大事件、电话会议 Guidance 与 Q&A 纪要、近期催化剂新闻排版为高信噪比 Markdown 底稿，供当前对话框或 CLI 中的 Gemini 毫秒级直接读取。

---

### 【Step 5】配置 Antigravity 专属自动化投研技能（Skill）与 Gemini 分析规程
* **目标**：让你在当前对话框（或 Antigravity CLI）中只需输入一句*“帮我深度分析 NVDA”*，Gemini 就能自动按机构级买方投委会标准完成全套动作，绝不输出空洞套话。
* **新建文件**：`e:\AI\Github_AIProject\html\.agent\skills\stock-deep-research\SKILL.md`
* **技能内嵌的标准执行流（SOP）**：
  1. **自动执行脚本**：Gemini 自动运行 `python generate_stock_dossier.py --ticker <TICKER>`；
  2. **自动读取底稿**：Gemini 自动调用 `read_file` 读取 `dossiers/<TICKER>/<TICKER>_gemini_context.md`（若发现最新季度电话会纪要需要补充细节，自动配合 `search_web` 检索核实最新财报电话会 Q&A 原话）；
  3. **执行五维深度投研与红队排雷推理**：
     * **模块一：中长期核心投资定性（Executive Thesis & Conviction Rating）**——综合量化基本面得分、估值预期差与相空间位置，给出明确的所处周期定性；
     * **模块二：基本面护城河与 SEC/电话会交叉验证**——对比管理层在电话会上的乐观指引与 SEC 财报中真实 FCF、毛利率斜率、RPO 递延收入、应收/存货周转是否一致（揭穿“嘴上乐观、身体诚实”的背离）；
     * **模块三：情绪面、估值安全边际与历史胜率锚定**——结合 Reverse DCF 隐含增速、期权 PCR/Max Pain 与相空间历史相似样本的 6M/1Y 真实胜率，评估当前买点的赔率与胜率；
     * **模块四：🕵️‍♂️ 红队风控官排雷（Devil's Advocate / Top 3 Red Flags）**——强制站在做空机构视角，从 SEC 10-K 风险变化、SBC 股权稀释、客户集中度、行业竞争及宏观利差中，列出最可能证伪中长期逻辑的 3 大潜在风险及量化证据；
     * **模块五：中长期持仓行动预案（If-Then Playbook）**——给出下季度财报必须跟踪的 2~3 个硬性数值阈值，以及相空间动力学下的加仓区与止损防线。
  4. **双端输出保存**：Gemini 在当前对话框直接向你汇报完整分析的同时，自动将报告写入 `dossiers/<TICKER>/<TICKER>_gemini_report.md`（及结构化摘要 JSON）。

---

### 【Step 6】Streamlit 网页端集成《🤖 Gemini 深度投研与风险体检中心》并完成端到端验收
* **目标**：在你的 Streamlit 网页端（[stock_tab.py](file:///e:/AI/Github_AIProject/html/stock_tab.py) 与 [company_tab.py](file:///e:/AI/Github_AIProject/html/company_tab.py)）无缝展示定量排雷看板与 Gemini 生成的深度报告。
* **涉及文件**：
  * [stock_tab.py](file:///e:/AI/Github_AIProject/html/stock_tab.py)
  * [company_tab.py](file:///e:/AI/Github_AIProject/html/company_tab.py)
* **具体界面功能**：
  1. 新增**「🛡️ 中长期基本面排雷与多维情绪量化体检卡」**：直观展示盈利含金量（True FCF）、应收/存货健康度、Reverse DCF 预期差、相空间综合分以及**历史相似状态未来 6M/1Y 胜率与盈亏比**；
  2. 新增**「🤖 Gemini 深度投研与红队风险体检报告」**面板：
     * 提供**「🔄 一键生成/刷新本地量化底稿 (Generate Quant Dossier)」**按钮：点击即可在网页后台跑完 `generate_stock_dossier.py`；
     * 自动检测并精美渲染 `dossiers/{TICKER}/{TICKER}_gemini_report.md` 中的最新 Gemini 深度分析报告（包含基本面×电话会交叉验证、Top 3 潜在暗雷、中长期持仓预案），并显示报告生成时间戳与所依据的 SEC 财报期数。
* **端到端实证验收**：
  * 以代表性个股（如 `NVDA`、`MSFT`）跑通 Step 1 ~ Step 6 完整闭环，输出本地终端运行证据与网页渲染验证结果。

---

## 四、 日常使用体验预览（建成之后你平时怎么用？）

系统搭建完成后，你的日常投研工作流将变得极其简单高效：

1. **方式 A（纯对话框一句话驱动）**：
   你打开 Antigravity，直接在当前对话框对我说：*“帮我跑一下 NVDA（或 AMD、META）的最新量化底稿并做中长期风险排查”*。我会自动运行脚本抓取最新 SEC 财报、电话会纪要与期权行情 $\rightarrow$ 完成定量精算 $\rightarrow$ 在对话框直接输出深度报告 $\rightarrow$ 同步更新到你的 Streamlit 网页。
2. **方式 B（针对特定问题深度追问）**：
   看完报告后，你可以直接在对话框追问：*“NVDA 最新 10-Q 里应收账款增加了多少？管理层在电话会 Q&A 里是怎么解释 Blackwell 产能爬坡对毛利率影响的？”* 我会直接调取本地已抓好的 SEC XBRL 明细与电话会文本切片为你精准作答。
3. **方式 C（持仓组合定期巡检）**：
   你可以随时让我批量扫描你中长期持有的 3~5 只股票，一键对比哪只股票基本面与情绪面处于最佳“黄金击球区”，哪只股票出现了潜在基本面恶化信号。
