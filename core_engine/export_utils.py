import os
import pandas as pd


def generate_trade_pairs(orders, sub_bt, ticker):
    """
    统一的交易波段配对生成器
    从 SharedExecutor 的 orders_history 中提取买卖配对 (过滤掉定投订单)
    """
    trade_pairs = []
    
    # 过滤掉非策略主观发出的订单 (如定投)
    discretionary = [o for o in orders if o.get('reason') not in ("Standing Order / DCA", "Bench Standing Order / DCA")]
    
    # 按照 卖出 -> 买回 的配对结构提取
    for k in range(0, len(discretionary) - 1, 2):
        s_o = discretionary[k]
        b_o = discretionary[k+1]
        
        if s_o['target'] == 0.0 and b_o['target'] == 1.0:
            s_dt = pd.to_datetime(s_o['actual_dt'] if s_o['actual_dt'] else s_o['submit_dt'])
            b_dt = pd.to_datetime(b_o['actual_dt'] if b_o['actual_dt'] else b_o['submit_dt'])
            
            s_p = sub_bt.loc[sub_bt['date'] == s_dt.strftime('%Y-%m-%d'), ticker].values
            b_p = sub_bt.loc[sub_bt['date'] == b_dt.strftime('%Y-%m-%d'), ticker].values
            
            s_p = s_p[0] if len(s_p) > 0 else 0
            b_p = b_p[0] if len(b_p) > 0 else 0
            
            if s_p > 0:
                p_drop = (b_p - s_p) / s_p * 100.0
            else:
                p_drop = 0.0
            
            trade_pairs.append({
                '轮次': len(trade_pairs) + 1,
                '卖出日期': s_dt.strftime('%Y-%m-%d'),
                '卖出价格': round(s_p, 2),
                '卖出诱因': s_o['reason'],
                '买入日期': b_dt.strftime('%Y-%m-%d'),
                '买入价格': round(b_p, 2),
                '买回诱因': b_o['reason'],
                '期间绝对跌幅': f"{p_drop:+.2f}%",
                '波段是否有效避险': "✅ 有效" if p_drop < 0 else "❌ 踏空磨损"
            })
            
    return pd.DataFrame(trade_pairs)


def export_deliverables(result, asset_name="综合基准"):
    """
    统一的数据合约交付方法 (Excel + CSVs)
    接受核心引擎标准输出 SimulationResult，生成标准对账底稿与前端需要的 CSV 文件
    """
    sub_bt = result.features.copy()
    df_daily = result.daily_accounts.copy()
    metrics = result.metrics
    ticker = result.metadata.get('ticker', 'UNKNOWN')
    df_pairs = generate_trade_pairs(result.orders, sub_bt, ticker)
    
    excel_path = f'宏观反身性阿尔法模型_{ticker}微观雷达全周期对账表.xlsx'
    
    # 防止 openpyxl 处理 datetime 报错，统一转为字符串格式
    for col in df_daily.columns:
        if pd.api.types.is_datetime64_any_dtype(df_daily[col]):
            df_daily[col] = df_daily[col].dt.strftime('%Y-%m-%d')
            
    for col in sub_bt.columns:
        if pd.api.types.is_datetime64_any_dtype(sub_bt[col]):
            sub_bt[col] = sub_bt[col].dt.strftime('%Y-%m-%d')
            
    # 导出 Excel 审计文件
    with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
        df_overview = pd.DataFrame([{
            '标的资产': ticker,
            '资产名称': asset_name,
            '定投总本金 (USD)': metrics.get('total_invested', 0),
            '买入持有 (B&H) 终值 (USD)': metrics.get('bench_final', 0),
            '买入持有累计回报率': f"{metrics.get('bench_return', 0):.2f}%",
            '买入持有最大回撤': f"{metrics.get('bench_max_dd', 0):.2f}%",
            '微观雷达策略终值 (USD)': metrics.get('strat_final', 0),
            '微观雷达策略总回报率': f"{metrics.get('strat_return', 0):.2f}%",
            '策略最大回撤': f"{metrics.get('strat_max_dd', 0):.2f}%",
            '超额回报率 (Alpha)': f"{metrics.get('alpha', 0):+.2f}%",
            '净多赚现金财富 (USD)': metrics.get('strat_final', 0) - metrics.get('bench_final', 0),
            '回撤改善幅度': f"{metrics.get('strat_max_dd', 0) - metrics.get('bench_max_dd', 0):+.2f}%",
            '全周期调仓轮次': metrics.get('trade_rounds', 0),
            '波段操作胜率': f"{metrics.get('win_rate', 0):.1f}%"
        }])
        df_overview.to_excel(writer, sheet_name='全周期业绩总表', index=False)
        df_pairs.to_excel(writer, sheet_name='逐笔买卖配对对账表', index=False)
        df_daily.to_excel(writer, sheet_name='逐日流水底稿表', index=False)
        
    # 导出 CSV 供前端 UI 读取
    # 强调使用 utf-8，解决 Windows 下中文乱码与 UnicodeEncodeError 问题
    df_pairs.to_csv(f'{ticker.lower()}_backtest_paired_local.csv', index=False, encoding='utf-8')
    sub_bt.to_csv(f'{ticker.lower()}_backtest_daily_local.csv', index=False, encoding='utf-8')
    
    print(f"📊 机构级 Excel 与 CSV 审计底稿已生成: {os.path.abspath(excel_path)}")
