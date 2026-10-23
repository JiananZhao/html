# 【TTD】多源量化精算与排雷档案 (Gemini 投研专用底稿)

> **标的名称**：The Trade Desk, Inc. (TTD)  
> **所属板块**：Communication Services | **细分行业**：Advertising Agencies  
> **数据时间戳**：`2026-10-23 09:38:10` | **最新股价**：`$11.94`  

---

## 一、 基本面质量与法务财务排雷指标 (Forensic Accounting)
* **最新申报期数**：`2026-Q2` (截至 `2025-06-30`)
* **营业总收入 (单季)**：`$1.31 B`
* **归母净利润 (单季)**：`$0.05 B`
* **经营活动现金流 (OCF)**：`$0.46 B`
* **股权激励费用 (SBC)**：`$0.26 B` (占 OCF: `56.3%`)
* **真实自由现金流 (True FCF = OCF - CapEx - SBC)**：`$0.09 B` (True FCF Margin: `7.2%`)
* **盈利含金量 (Cash Conversion = OCF / 净利润)**：`9.01x`
* **应收账款异动 (同比增速 - 营收增速)**：`-153.5%`
* **存货异动 (同比增速 - 营收增速)**：`nan%`
* **毛利率 8 季回归斜率**：`nan% / 季度`
* **Piotroski F-Score (0~9 分健康度)**：`6 / 9`

### 🚩 机器规则初筛排雷标签：
- ⚠️ 股权激励稀释过高 (SBC 占经营现金流比重高达 56.3%，需扣除稀释效应评估真实利润)

### 🌟 核心基本面正向标签：
- ✅ 经营现金流极其充沛 (OCF/净利润=9.01 >= 1.0，盈利含金量极高)
- ✅ 应收账款周转极佳 (应收账款增速低于营收 153.5%)

---

## 二、 估值安全边际与反向 DCF 预期差模型 (Expectations Gap)
* **反向 DCF 隐含未来 10 年 FCF 年化增速**：`-5.9%` (基准: WACC 9.0%, 永续 3.0%)
* **过去 3 年实际 FCF 复合年化增速**：`-13.7%`
* **市场预期差 (隐含增速 - 历史增速)**：`+7.8%`
* **当前估值状态定性**：`偏乐观透支区 (市场定价要求未来 10 年增速进一步加速)`
* **市盈率 PE (TTM / Forward)**：`15.759036x / 13.016091x` | **市销率 P/S**：`2.0681853x`
* **华尔街分析师目标均价**：`$13.53333` (隐含空间: `+13.3%`)

---

## 三、 索罗斯反身性相空间动力学与微观博弈情绪
* **相空间四象限归属**：`象限 II：恐慌势阱筑底/回升区 (q1 < 0, q1_dot >= 0)`
* **综合过热动力学雷达分 (0~100)**：`24.7 分`
* **位置 q1 (年线偏离度 Dist_200MA)**：`-45.35%`
* **速度 q1_dot (10日平滑导数)**：`+0.12% / 天`
* **李雅普诺夫能量导数 v_dot**：`-4.06`
* **反身性认知偏离度 (Reflexive Gap)**：`-1.33`
* **近 20 日动态触发信号**：`🟢 极度恐慌底反转信号 (Trigger_Panic), 🟡 熊市反弹衰竭离场预警 (Trigger_Bear_Top)`
* **期权未平仓认沽/认购比 (PCR OI)**：`0.32848473618381435` (Max Pain 痛点价: `$12.5`)
* **做空拥挤度 (Short % of Float)**：`22.35%` (回补天数: `3.25 天`)

---

## 四、 历史相似相空间状态回溯胜率与回撤表现 (Historical Analogues)
* **相似样本匹配数量**：`9 个独立历史时点` (相似判定: 雷达分 ±12, 年线乖离同号且 ±10%)
* **代表性历史发生时点**：`2022-06-28, 2025-03-03, 2025-04-11, 2025-08-08, 2025-09-15, 2025-11-17`
* **未来 3 个月 (3M) 表现**：胜率 `33.3%` | 中位数收益 `-15.4%` | 盈亏比 `1.58x`
* **未来 6 个月 (6M) 表现**：胜率 `11.1%` | 中位数收益 `-45.1%` | 盈亏比 `0.08x`
* **未来 12 个月 (1Y) 表现**：胜率 `20.0%` | 中位数收益 `-62.5%` | 期间最大回撤中位数 `-75.8%`

---

## 五、 官方 8-K 业绩公告与电话会议管理层指引摘要 (Guidance Excerpt)
```text
ttd-20260806 0001671933 false 0001671933 2026-08-06 2026-08-06 UNITED STATES SECURITIES AND EXCHANGE COMMISSION Washington, D.C. 20549 FORM&#160; 8-K CURRENT REPORT Pursuant to Section 13 OR 15(d) of The Securities Exchange Act of 1934 Date of Report (Date of earliest event reported):&#160; August 6, 2026 THE TRADE DESK, INC. (Exact name of registrant as specified in its charter) Nevada 001-37879 27-1887399 (State or other jurisdiction of incorporation) (Commission File Number) (I.R.S. Employer Identification No.) 42 N. Chestnut Street Ventura ,&#160; California &#160; 93001 (Address of principal executive offices) (Zip Code) ( 805 )&#160; 585-3434 (Registrant&#8217;s telephone number, including area code) Not Applicable (Former name or former address, if changed since last report.) Check the appropriate box below if the Form 8-K filing is intended to simultaneously satisfy the filing obligation of the registrant under any of the following provisions: o Written communications pursuant to Rule 425 under the Securities Act (17 CFR 230.425)&#160; o Soliciting material pursuant to Rule 14a-12 under the Exchange Act (17 CFR 240.14a-12)&#160; o Pre-commencement communications pursuant to
```
