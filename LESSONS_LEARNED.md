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
