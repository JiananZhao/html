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
- **强制规范**：写 LaTeX 必须使用原始字符串前缀 """...""" 或 \\frac。

## 4. Pandas API 弃用崩溃 (Deprecation Error)
- **错误场景**：df.style.applymap() 报错。
- **强制规范**：Pandas 2.1.0 已废弃 pplymap，全部改用 df.style.map()。

## 5. API 返回列名大小写敏感 (KeyError)
- **错误场景**：FRED 返回 date，Yahoo 返回 Date，直接执行 set_index('Date') 崩溃。
- **强制规范**：set_index 前必须做防御性重命名：if 'date' in df.columns: df = df.rename(columns={'date': 'Date'})。

## 6. 布尔逻辑判断与 np.nan 造成的隐式崩溃 (TypeError)
- **错误场景**：在评估回测胜率时，写了 sum(...) / len(tw_3m) if tw_3m and len(tw_3m) > 0 else np.nan。当没有信号时，函数返回了 
p.nan。导致执行 len(np.nan) 直接宕机。
- **根本原因**：在 Python 中，ool(np.nan) 的值是 True！这导致 if tw_3m 判定通过，随后强行对一个 float 执行 len() 操作。
- **强制规范**：
  1. 如果下游逻辑期待一个列表，那么在无数据时绝对**不能返回 
p.nan**，必须返回空列表 []。
  2. 永远不要使用 if variable: 来判断一个可能为 
p.nan 的对象是否有效，应使用明确的类型检测 isinstance(var, list) 或 pd.isna(var)。
