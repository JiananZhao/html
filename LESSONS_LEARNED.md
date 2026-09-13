# 量化与数据处理避坑指南 (Lessons Learned)

这份文档总结了在过去代码编写和模型迭代中犯过的关键错误。在后续开发新功能、处理数据拼接或升级图表时，必须首先查阅此文档，坚决杜绝同类错误的二次发生！

## 1. Pandas 数据拼接与时间轴对齐 (Fatal Error)
- **错误场景**：使用 pd.merge_asof() 进行多个异构数据源拼接时报错 incompatible merge keys [0] dtype('<M8[us]') and dtype('<M8[s]')。
- **根本原因**：Pandas 2.0+ 对 merge_asof 的数据类型校验极其严格。不同 API 传回的日期精度不同，且带时区与不带时区的混用，导致底层无法比较。
- **强制规范**：在合并任何时间序列前，**必须强制统一时间戳的精度和剥离时区**：
  df['date'] = pd.to_datetime(df['date']).dt.tz_localize(None).astype('datetime64[ns]')

## 2. 移动平均（Rolling）造成的前置数据截断 (Logical Bug)
- **错误场景**：在图表展示“过去 3 年”指标，但只拉取了 3 年数据，导致前 200 日因为 olling(200) 计算变 NaN 而丢弃，图表只剩 2 年。
- **强制规范**：计算 N 日滚动均线，数据拉取起点必须向前提早 N 个交易日（约增加1年），计算完后再按时间截取。

## 3. Python 字符串与 LaTeX 渲染的转义冲突 (UI Bug)
- **错误场景**：st.markdown("""  Z = \frac{x}{y}  """) 公式乱码。
- **根本原因**：Python 字符串将 \f 解析为换页符。
- **强制规范**：写 LaTeX 必须使用原始字符串前缀 """...""" 或 \\frac。

## 4. Pandas API 弃用崩溃 (Deprecation Error)
- **错误场景**：df.style.applymap() 报错。
- **强制规范**：Pandas 2.1.0 已废弃 applymap，全部改用 df.style.map()。

## 5. API 返回列名大小写敏感 (KeyError)
- **错误场景**：FRED 返回 date，Yahoo 返回 Date，直接执行 set_index('Date') 崩溃。
- **强制规范**：set_index 前必须做防御性重命名：if 'date' in df.columns: df = df.rename(columns={'date': 'Date'})。

## 6. 布尔逻辑判断与 np.nan 造成的隐式崩溃 (TypeError)
- **错误场景**：在评估回测胜率时，写了 sum(...) / len(tw_3m) if tw_3m and len(tw_3m) > 0 else np.nan。当没有信号时，函数返回了 np.nan。导致执行 len(np.nan) 直接宕机。
- **根本原因**：在 Python 中，bool(np.nan) 的值是 True！这导致 if tw_3m 判定通过，随后强行对一个 float 执行 len() 操作。
- **强制规范**：
  1. 如果下游逻辑期待一个列表，那么在无数据时绝对**不能返回 np.nan**，必须返回空列表 []。
  2. 永远不要使用 if variable: 来判断一个可能为 np.nan 的对象是否有效，应使用明确的类型检测 isinstance(var, list) 或 pd.isna(var)。

## 7. 外部 API 滥用与本地主数据缺失 (Local-First Failure)
- **错误场景**：在已经拉取并整理好本地数据后，脚本和测试代码依然残留调用 yf.download()，导致遇到网络限流、超时卡死半小时，并吐出海量进度条废话日志，严重浪费 Context Token。
- **根本原因**：编写代码时存在惰性，直接复制了带网络请求的代码模板，没有践行“本地优先（Local-First）”原则。
- **强制规范**：
  1. 必须建立标准统一的本地主数据集（如 market_data_local.csv），后续所有回测、绘图与计算**一律强制 100% 读本地文件**。
  2. 严禁在计算脚本中裸调外部网络 API！

## 8. 盲目自我感动与牛市现金拖累陷阱 (Complacency & Cash Drag Trap)
- **错误场景**：在长达 17 年的超级牛市中，策略因为在黄昏期持有 25% 现金、去杠杆期持有 65% 现金，导致总收益被腰斩（+308% 跌至 +144%），却盲目吹嘘“回撤砍半、极其亮眼”。
- **根本原因**：只看风险指标，忽视了长牛市中现金机会成本（Cash Drag）的毁灭性打击，严重脱离权益投资的核心目标（财富积累与超额 Alpha）。
- **强制规范**：
  1. 必须时刻对真实最终资产负责，严禁将总回报大幅跑输 Buy & Hold 的策略作为最终成果交付！
  2. 在正常牛市扩张期必须保持 100% 满仓，唯有在极端系统性泡沫破裂和流动性危机时才可战术避险，并在恐慌极值深度抄底以获取真正超额收益。

## 9. Matplotlib 绘制含 '$' 符号与中文时的 LaTeX 转义与字体冲突 (UI Glyph Bug)
- **错误场景**：在 Matplotlib 图表标题或标签中写入 $ 符号（如 $192,000）且包含中文，终端报错 Font 'rm' does not have a glyph for [U+XXXX] 并产生方块乱码。
- **根本原因**：Matplotlib 将 $ 符号自动解析为 LaTeX Math Mode 入口，而 LaTeX 默认字体（'rm'）不包含中文字符集。
- **强制规范**：
  1. 在含有中文的标题和坐标轴文本中，严禁直接使用裸 $ 符号，应写作 USD 192,000 或使用转义 \\$。
  2. 绘图脚本必须显式设置：
     plt.rcParams['font.sans-serif'] = ['SimHei', 'Microsoft YaHei', 'SimSun', 'sans-serif']
     plt.rcParams['axes.unicode_minus'] = False

## 10. 虚假收益率连乘与真实券商记账脱节 (Phantom Compounding Bug)
- **错误场景**：使用 strat_balance *= (1 + daily_return) 简单模拟仓位，忽略了空仓买回时的股价高低和持股股数稀释，得出虚假的“跑赢基准”假象。
- **强制规范**：
  必须使用券商级两状态变量记账：strat_shares（实际持股数）与 strat_cash（流动现金池）。每一笔交易均按成交价严格折算，真实反映股数增减。
