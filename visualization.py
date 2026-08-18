import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

# ------------------------------------------------------------------
# 1. 核心国债收益率曲线图表 (U.S. Treasury Yield Curve Comparison)
# ------------------------------------------------------------------
def create_treasury_chart(df_long: pd.DataFrame):
    if df_long is None or df_long.empty:
        return None

    df = df_long.copy()
    if 'Date' in df.columns:
        df['Date'] = pd.to_datetime(df['Date'])
        latest_date = df['Date'].max()
    else:
        return None

    mat_col = 'Maturity_Years' if 'Maturity_Years' in df.columns else ('Maturity_Label' if 'Maturity_Label' in df.columns else 'Maturity')

    date_1m = latest_date - pd.DateOffset(months=1)
    date_1y = latest_date - pd.DateOffset(years=1)

    available_dates = df['Date'].unique()
    
    def _find_nearest_date(target):
        past_dates = [d for d in available_dates if d <= target]
        return max(past_dates) if past_dates else min(available_dates)

    target_dates = [
        latest_date,
        _find_nearest_date(date_1m),
        _find_nearest_date(date_1y)
    ]

    df_filtered = df[df['Date'].isin(target_dates)].copy()
    df_filtered['Date_Str'] = df_filtered['Date'].dt.strftime('%Y-%m-%d')

    fig = px.line(
        df_filtered,
        x=mat_col,
        y='Yield',
        color='Date_Str',
        title='U.S. Treasury Yield Curve Comparison',
        labels={mat_col: '期限 (Maturity Years)', 'Yield': '收益率 (%)', 'Date_Str': '日期'},
        template='plotly_white'
    )

    fig.update_traces(mode='lines+markers', marker=dict(size=6))
    fig.update_layout(
        height=500,
        hovermode='x unified',
        uirevision='treasury_yield_chart',
        yaxis_title='收益率 (%)'
    )
    fig.update_yaxes(autorange=True, fixedrange=False)
    return fig


# ------------------------------------------------------------------
# 辅助函数：根据选定时间范围切片 DataFrame
# ------------------------------------------------------------------
def filter_by_timeframe(df: pd.DataFrame, date_col: str, timeframe: str = "ALL"):
    if df is None or df.empty or not timeframe or timeframe == "ALL":
        return df

    df_sorted = df.sort_values(date_col)
    last_date = df_sorted[date_col].max()

    tf_map = {
        "1M": pd.DateOffset(months=1),
        "3M": pd.DateOffset(months=3),
        "6M": pd.DateOffset(months=6),
        "1Y": pd.DateOffset(years=1),
        "3Y": pd.DateOffset(years=3),
        "5Y": pd.DateOffset(years=5),
        "10Y": pd.DateOffset(years=10),
    }

    if timeframe in tf_map:
        start_date = last_date - tf_map[timeframe]
        return df_sorted[df_sorted[date_col] >= start_date].copy()

    return df


# ------------------------------------------------------------------
# 2. 失业率趋势图表 (UNRATE)
# ------------------------------------------------------------------
def create_unemployment_chart(df_unrate: pd.DataFrame, y_range=None, timeframe="ALL"):
    if df_unrate is None or df_unrate.empty:
        return None

    df = df_unrate.copy()
    if 'date' in df.columns:
        df['date'] = pd.to_datetime(df['date'])
        df = filter_by_timeframe(df, 'date', timeframe)
        x_col = 'date'
    elif 'Date' in df.columns:
        df['Date'] = pd.to_datetime(df['Date'])
        df = filter_by_timeframe(df, 'Date', timeframe)
        x_col = 'Date'
    else:
        return None

    if df.empty:
        return None

    val_col = 'Unemployment_Rate' if 'Unemployment_Rate' in df.columns else ('value' if 'value' in df.columns else df.columns[1])

    fig = px.line(
        df,
        x=x_col,
        y=val_col,
        title=f'U.S. Unemployment Rate (UNRATE) - [{timeframe}]',
        labels={x_col: '日期', val_col: '失业率 (%)'},
        template='plotly_white'
    )
    fig.update_layout(
        height=450,
        hovermode='x unified',
        uirevision=f'unemp_chart_{timeframe}',
        yaxis_title='失业率 (%)'
    )

    if y_range is not None:
        fig.update_yaxes(range=y_range)
    else:
        fig.update_yaxes(autorange=True, fixedrange=False)

    return fig


# ------------------------------------------------------------------
# 3. 高收益债信用利差走势图表 (Credit Spread)
# ------------------------------------------------------------------
def create_credit_spread_chart(df_data: pd.DataFrame, y_range=None, timeframe="ALL"):
    if df_data is None or df_data.empty:
        return None

    df = df_data.copy()
    x_col = 'date' if 'date' in df.columns else ('Date' if 'Date' in df.columns else df.columns[0])
    df[x_col] = pd.to_datetime(df[x_col])
    df = filter_by_timeframe(df, x_col, timeframe)
    if df.empty:
        return None

    val_col = 'Credit_Spread' if 'Credit_Spread' in df.columns else ('Value' if 'Value' in df.columns else df.columns[1])

    fig = px.line(
        df,
        x=x_col,
        y=val_col,
        title=f'U.S. High Yield Option-Adjusted Spread (BAML OAS) - [{timeframe}]',
        labels={x_col: '日期', val_col: '信用利差 (%)'},
        template='plotly_white'
    )
    fig.update_layout(
        height=450,
        hovermode='x unified',
        uirevision=f'credit_spread_{timeframe}',
        yaxis_title='利差 (%)'
    )

    if y_range is not None:
        fig.update_yaxes(range=y_range)
    else:
        fig.update_yaxes(autorange=True, fixedrange=False)

    return fig


# ------------------------------------------------------------------
# 4. 美联储资产负债表总资产走势图表 (Fed Balance Sheet)
# ------------------------------------------------------------------
def create_fed_balance_sheet_chart(df_fed: pd.DataFrame, y_range=None, timeframe="ALL"):
    if df_fed is None or df_fed.empty:
        return None

    df = df_fed.copy()
    x_col = 'date' if 'date' in df.columns else ('Date' if 'Date' in df.columns else df.columns[0])
    df[x_col] = pd.to_datetime(df[x_col])
    df = filter_by_timeframe(df, x_col, timeframe)
    if df.empty:
        return None

    val_col = 'Total_Assets' if 'Total_Assets' in df.columns else ('Value' if 'Value' in df.columns else df.columns[1])
    
    # 转换为万亿美元 ($ Trillion)
    df['Total_Assets_Trillion'] = df[val_col] / 1e6 if df[val_col].max() > 1e5 else df[val_col]

    fig = px.line(
        df,
        x=x_col,
        y='Total_Assets_Trillion',
        title=f'Federal Reserve Total Assets (WALCL) - [{timeframe}]',
        labels={x_col: '日期', 'Total_Assets_Trillion': '总资产 ($ Trillion)'},
        template='plotly_white'
    )
    fig.update_layout(
        height=450,
        hovermode='x unified',
        uirevision=f'fed_bs_{timeframe}',
        yaxis_title='规模 ($ Trillion)'
    )

    if y_range is not None:
        fig.update_yaxes(range=y_range)
    else:
        fig.update_yaxes(autorange=True, fixedrange=False)

    return fig


# ------------------------------------------------------------------
# 5. 金油比历史走势图表 (Gold / Oil Ratio)
# ------------------------------------------------------------------
def create_gold_oil_ratio_chart(df_ratio: pd.DataFrame, y_range=None, timeframe="ALL"):
    if df_ratio is None or df_ratio.empty:
        return None

    df = df_ratio.copy()
    x_col = 'date' if 'date' in df.columns else ('Date' if 'Date' in df.columns else df.columns[0])
    df[x_col] = pd.to_datetime(df[x_col])
    df = filter_by_timeframe(df, x_col, timeframe)
    if df.empty:
        return None

    val_col = 'Ratio' if 'Ratio' in df.columns else df.columns[1]

    fig = px.line(
        df,
        x=x_col,
        y=val_col,
        title=f'Gold / WTI Oil Price Ratio - [{timeframe}]',
        labels={x_col: '日期', val_col: '金油比 (Gold/Oil Ratio)'},
        template='plotly_white'
    )
    fig.update_layout(
        height=450,
        hovermode='x unified',
        uirevision=f'gold_oil_{timeframe}',
        yaxis_title='比率'
    )

    if y_range is not None:
        fig.update_yaxes(range=y_range)
    else:
        fig.update_yaxes(autorange=True, fixedrange=False)

    return fig


# ------------------------------------------------------------------
# 6. 10Y TIPS 实际利率与盈亏平衡通胀预期
# ------------------------------------------------------------------
def create_real_yield_breakeven_chart(df_data: pd.DataFrame, y_range=None, timeframe="ALL"):
    if df_data is None or df_data.empty:
        return None

    df = df_data.copy()
    x_col = 'date' if 'date' in df.columns else ('Date' if 'Date' in df.columns else df.columns[0])
    df[x_col] = pd.to_datetime(df[x_col])
    df = filter_by_timeframe(df, x_col, timeframe)
    if df.empty:
        return None

    fig = go.Figure()

    if 'DFII10' in df.columns:
        fig.add_trace(go.Scatter(
            x=df[x_col],
            y=df['DFII10'],
            mode='lines',
            name='10Y TIPS 实际利率 (DFII10)',
            line=dict(color='#7c3aed', width=2)
        ))

    if 'T10YIE' in df.columns:
        fig.add_trace(go.Scatter(
            x=df[x_col],
            y=df['T10YIE'],
            mode='lines',
            name='10Y 平衡通胀预期 (T10YIE)',
            line=dict(color='#0284c7', width=1.5, dash='dash')
        ))

    fig.update_layout(
        title=f'10Y Real Yield (DFII10) & 10Y Breakeven Inflation (T10YIE) - [{timeframe}]',
        xaxis_title='日期',
        yaxis_title='百分比 (%)',
        template='plotly_white',
        height=450,
        hovermode='x unified',
        uirevision=f'real_yield_{timeframe}'
    )

    if y_range is not None:
        fig.update_yaxes(range=y_range)
    else:
        fig.update_yaxes(autorange=True, fixedrange=False)

    return fig


# ------------------------------------------------------------------
# 7. 芝加哥联储全国金融状况指数 (NFCI)
# ------------------------------------------------------------------
def create_nfci_chart(df_nfci: pd.DataFrame, y_range=None, timeframe="ALL"):
    if df_nfci is None or df_nfci.empty:
        return None

    df = df_nfci.copy()
    x_col = 'date' if 'date' in df.columns else ('Date' if 'Date' in df.columns else df.columns[0])
    df[x_col] = pd.to_datetime(df[x_col])
    df = filter_by_timeframe(df, x_col, timeframe)
    if df.empty:
        return None

    val_col = 'NFCI' if 'NFCI' in df.columns else ('Value' if 'Value' in df.columns else df.columns[1])

    fig = px.line(
        df,
        x=x_col,
        y=val_col,
        title=f'Chicago Fed National Financial Conditions Index (NFCI) - [{timeframe}]',
        labels={x_col: '日期', val_col: 'NFCI 指数'},
        template='plotly_white'
    )
    
    # 0 轴分界线
    fig.add_hline(y=0.0, line_dash="dash", line_color="#0f172a", annotation_text="0.0 历史中性线 (上方紧缩 / 下方宽松)")

    fig.update_layout(
        height=450,
        hovermode='x unified',
        uirevision=f'nfci_{timeframe}',
        yaxis_title='指数读数'
    )

    if y_range is not None:
        fig.update_yaxes(range=y_range)
    else:
        fig.update_yaxes(autorange=True, fixedrange=False)

    return fig


# ------------------------------------------------------------------
# 8. 美联储宏观净流动性水龙头走势图表
# ------------------------------------------------------------------
def create_net_liquidity_chart(df_liq: pd.DataFrame, y_range=None, timeframe="ALL"):
    if df_liq is None or df_liq.empty:
        return None

    df = df_liq.copy()
    x_col = 'date' if 'date' in df.columns else ('Date' if 'Date' in df.columns else df.columns[0])
    df[x_col] = pd.to_datetime(df[x_col])
    df = filter_by_timeframe(df, x_col, timeframe)
    if df.empty:
        return None

    val_col = 'Fed_Net_Liquidity_Tn' if 'Fed_Net_Liquidity_Tn' in df.columns else ('Net_Liquidity' if 'Net_Liquidity' in df.columns else df.columns[1])

    fig = px.line(
        df,
        x=x_col,
        y=val_col,
        title=f'Fed Net Liquidity (WALCL - TGA - RRP) - [{timeframe}]',
        labels={x_col: '日期', val_col: '净流动性 ($ Trillion)'},
        template='plotly_white'
    )
    fig.update_layout(
        height=450,
        hovermode='x unified',
        uirevision=f'net_liq_{timeframe}',
        yaxis_title='流动性规模 ($ Trillion)'
    )

    if y_range is not None:
        fig.update_yaxes(range=y_range)
    else:
        fig.update_yaxes(autorange=True, fixedrange=False)

    return fig


# ------------------------------------------------------------------
# 9. SOFR - IORB 隔夜资金面微观体温计
# ------------------------------------------------------------------
def create_sofr_iorb_chart(df_sofr: pd.DataFrame, y_range=None, timeframe="ALL"):
    if df_sofr is None or df_sofr.empty:
        return None

    df = df_sofr.copy()
    x_col = 'date' if 'date' in df.columns else ('Date' if 'Date' in df.columns else df.columns[0])
    df[x_col] = pd.to_datetime(df[x_col])
    df = filter_by_timeframe(df, x_col, timeframe)
    if df.empty:
        return None

    val_col = 'Spread_bps' if 'Spread_bps' in df.columns else df.columns[1]

    fig = px.line(
        df,
        x=x_col,
        y=val_col,
        title=f'SOFR - IORB Spread (Overnight Liquidity Friction) - [{timeframe}]',
        labels={x_col: '日期', val_col: '利差 (bps)'},
        template='plotly_white'
    )
    fig.add_hline(y=3.0, line_dash="dash", line_color="#ef4444", annotation_text="微观摩擦警戒线 (+3 bps)")

    fig.update_layout(
        height=450,
        hovermode='x unified',
        uirevision=f'sofr_{timeframe}',
        yaxis_title='利差 (基点 bps)'
    )

    if y_range is not None:
        fig.update_yaxes(range=y_range)
    else:
        fig.update_yaxes(autorange=True, fixedrange=False)

    return fig


# ------------------------------------------------------------------
# 10. 标普 500 前十大持仓集中度分析饼图
# ------------------------------------------------------------------
def create_top10_concentration_chart(df_top10: pd.DataFrame):
    if df_top10 is None or df_top10.empty:
        return None

    fig = px.pie(
        df_top10,
        values='Weight',
        names='Symbol',
        title='S&P 500 Top 10 Holdings Weight Concentration',
        template='plotly_white',
        hole=0.35,
        color_discrete_sequence=px.colors.sequential.Blues_r
    )
    fig.update_traces(textposition='inside', textinfo='percent+label')
    fig.update_layout(height=480, margin=dict(l=20, r=20, t=50, b=20))
    return fig


# ------------------------------------------------------------------
# 11. CBOE VIX 恐慌指数走势图表
# ------------------------------------------------------------------
def create_vix_chart(df_vix: pd.DataFrame, y_range=None, timeframe="ALL"):
    if df_vix is None or df_vix.empty:
        return None

    df = df_vix.copy()
    x_col = 'date' if 'date' in df.columns else ('Date' if 'Date' in df.columns else df.columns[0])
    df[x_col] = pd.to_datetime(df[x_col])
    df = filter_by_timeframe(df, x_col, timeframe)
    if df.empty:
        return None

    val_col = 'VIX' if 'VIX' in df.columns else ('Value' if 'Value' in df.columns else df.columns[1])

    fig = px.line(
        df,
        x=x_col,
        y=val_col,
        title=f'CBOE Volatility Index (VIX) - [{timeframe}]',
        labels={x_col: '日期', val_col: 'VIX 读数'},
        template='plotly_white'
    )
    fig.add_hline(y=20.0, line_dash="dash", line_color="#f59e0b", annotation_text="情绪分界 (20.0)")
    fig.add_hline(y=30.0, line_dash="dash", line_color="#ef4444", annotation_text="高恐慌警戒 (30.0)")

    fig.update_layout(
        height=450,
        hovermode='x unified',
        uirevision=f'vix_{timeframe}',
        yaxis_title='VIX'
    )

    if y_range is not None:
        fig.update_yaxes(range=y_range)
    else:
        fig.update_yaxes(autorange=True, fixedrange=False)

    return fig


# ------------------------------------------------------------------
# 12. CNN 恐惧与贪婪指数走势图表
# ------------------------------------------------------------------
def create_cnn_fear_greed_chart(df_fgi: pd.DataFrame, y_range=None, timeframe="ALL", current_score=None):
    if df_fgi is None or df_fgi.empty:
        return None

    df = df_fgi.copy()
    x_col = 'date' if 'date' in df.columns else ('Date' if 'Date' in df.columns else df.columns[0])
    df[x_col] = pd.to_datetime(df[x_col])
    df = filter_by_timeframe(df, x_col, timeframe)
    if df.empty:
        return None

    val_col = 'score' if 'score' in df.columns else ('Value' if 'Value' in df.columns else df.columns[1])

    fig = px.line(
        df,
        x=x_col,
        y=val_col,
        title=f'CNN Fear & Greed Historical Trend - [{timeframe}]',
        labels={x_col: '日期', val_col: '情绪评分 (0 - 100)'},
        template='plotly_white'
    )
    fig.add_hline(y=75.0, line_dash="dash", line_color="#ef4444", annotation_text="极度贪婪 (75)")
    fig.add_hline(y=25.0, line_dash="dash", line_color="#10b981", annotation_text="极度恐惧 (25)")

    fig.update_layout(
        height=450,
        hovermode='x unified',
        uirevision=f'fgi_{timeframe}',
        yaxis_title='评分'
    )

    if y_range is not None:
        fig.update_yaxes(range=y_range)
    else:
        fig.update_yaxes(range=[0, 100], fixedrange=False)

    return fig


# ------------------------------------------------------------------
# 13. 个股交互式 K 线与均线图表 (Stock Price Candlestick & MA)
# ------------------------------------------------------------------
def create_stock_price_chart(df_stock: pd.DataFrame, symbol: str, chart_type: str = "Candlestick", timeframe: str = "1Y"):
    if df_stock is None or df_stock.empty:
        return None

    df = df_stock.copy()
    if 'Date' not in df.columns:
        if isinstance(df.index, pd.DatetimeIndex):
            df = df.reset_index()
            df.rename(columns={'index': 'Date'}, inplace=True)
        elif 'date' in df.columns:
            df.rename(columns={'date': 'Date'}, inplace=True)
        else:
            return None

    df['Date'] = pd.to_datetime(df['Date'])
    df = filter_by_timeframe(df, 'Date', timeframe)
    if df.empty:
        return None

    df['MA20'] = df['Close'].rolling(20).mean()
    df['MA50'] = df['Close'].rolling(50).mean()
    df['MA200'] = df['Close'].rolling(200).mean()

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.04, row_heights=[0.75, 0.25])

    if chart_type == "Candlestick" and all(c in df.columns for c in ['Open', 'High', 'Low', 'Close']):
        fig.add_trace(go.Candlestick(
            x=df['Date'],
            open=df['Open'],
            high=df['High'],
            low=df['Low'],
            close=df['Close'],
            name=f"{symbol} K线"
        ), row=1, col=1)
    else:
        fig.add_trace(go.Scatter(
            x=df['Date'],
            y=df['Close'],
            mode='lines',
            name=f"{symbol} 股价",
            line=dict(color='#1e293b', width=2)
        ), row=1, col=1)

    fig.add_trace(go.Scatter(x=df['Date'], y=df['MA20'], mode='lines', name='20 MA', line=dict(color='#3b82f6', width=1.2)), row=1, col=1)
    fig.add_trace(go.Scatter(x=df['Date'], y=df['MA50'], mode='lines', name='50 MA', line=dict(color='#f59e0b', width=1.2)), row=1, col=1)
    fig.add_trace(go.Scatter(x=df['Date'], y=df['MA200'], mode='lines', name='200 MA (牛熊分界)', line=dict(color='#ef4444', width=1.8)), row=1, col=1)

    if 'Volume' in df.columns:
        colors = ['#22c55e' if c >= o else '#ef4444' for c, o in zip(df['Close'], df['Open'] if 'Open' in df.columns else df['Close'])]
        fig.add_trace(go.Bar(x=df['Date'], y=df['Volume'], name='成交量', marker_color=colors), row=2, col=1)

    fig.update_layout(
        title=f"{symbol} 历史量价走势与关键均线系统 - [{timeframe}]",
        xaxis_rangeslider_visible=False,
        template="plotly_white",
        hovermode="x unified",
        height=550,
        margin=dict(l=40, r=40, t=50, b=40)
    )

    return fig


# ------------------------------------------------------------------
# 14. 多股相对基准累计收益对比走势图表
# ------------------------------------------------------------------
def create_relative_performance_chart(df_prices: pd.DataFrame, tickers: list = None, timeframe: str = "YTD", base_symbol: str = "SOXX"):
    if df_prices is None:
        return None

    # 支持 dict 输入
    if isinstance(df_prices, dict):
        df_dict = df_prices
    else:
        df_dict = {}

    if not df_dict:
        return None

    fig = go.Figure()
    colors = ['#2563eb', '#dc2626', '#16a34a', '#f59e0b', '#8b5cf6', '#06b6d4', '#d97706', '#ec4899', '#64748b', '#10b981']

    idx = 0
    for sym, df_s in df_dict.items():
        if df_s is None or df_s.empty:
            continue

        df = df_s.copy()
        if 'Date' not in df.columns:
            if isinstance(df.index, pd.DatetimeIndex):
                df = df.reset_index()
                df.rename(columns={'index': 'Date'}, inplace=True)
            elif 'date' in df.columns:
                df.rename(columns={'date': 'Date'}, inplace=True)
            else:
                continue

        df['Date'] = pd.to_datetime(df['Date'])
        df = filter_by_timeframe(df, 'Date', timeframe)
        if df.empty or len(df) < 5:
            continue

        close_col = 'Close' if 'Close' in df.columns else ('close' if 'close' in df.columns else df.columns[1])
        base_p = df[close_col].iloc[0]
        if base_p <= 0:
            continue
        rel_return = ((df[close_col] - base_p) / base_p) * 100

        is_bench = (sym == base_symbol)
        line_w = 3.0 if is_bench else 1.8
        dash_style = 'solid' if is_bench else ('dash' if idx % 3 == 1 else 'solid')
        color = '#1e293b' if is_bench else colors[idx % len(colors)]

        fig.add_trace(
            go.Scatter(
                x=df['Date'],
                y=rel_return,
                mode='lines',
                name=f"{sym} {'(基准)' if is_bench else ''}",
                line=dict(color=color, width=line_w, dash=dash_style if dash_style != 'solid' else None),
                hovertemplate=f"<b>{sym}</b>: %{{y:+.2f}}%<extra></extra>"
            )
        )
        idx += 1

    fig.add_hline(
        y=0.0,
        line_dash="dot",
        line_color="#94a3b8",
        annotation_text="0% 基准线",
        annotation_position="bottom right"
    )

    fig.update_layout(
        title=f"核心标的相对区间基准日累计收益率对比走势 - [{timeframe}]",
        xaxis_title="日期",
        yaxis_title="累计收益率 (%)",
        template="plotly_white",
        hovermode="x unified",
        height=520,
        margin=dict(l=40, r=40, t=50, b=40),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        uirevision=f"rel_perf_{base_symbol}_{timeframe}"
    )

    return fig


# ------------------------------------------------------------------
# 15. 多周期核心财务报表趋势图表 (Financial Trends Chart)
# ------------------------------------------------------------------
def create_financial_trends_chart(df_trends: pd.DataFrame, period_type: str = "季度"):
    if df_trends is None or df_trends.empty:
        return None

    fig = make_subplots(specs=[[{"secondary_y": True}]])

    if 'Revenue_Bn' in df_trends.columns:
        fig.add_trace(go.Bar(
            x=df_trends['Period'],
            y=df_trends['Revenue_Bn'],
            name='营业收入 ($B)',
            marker_color='#93c5fd'
        ), secondary_y=False)

    if 'NetIncome_Bn' in df_trends.columns:
        fig.add_trace(go.Bar(
            x=df_trends['Period'],
            y=df_trends['NetIncome_Bn'],
            name='净利润 ($B)',
            marker_color='#3b82f6'
        ), secondary_y=False)

    if 'GrossMargin_Pct' in df_trends.columns:
        fig.add_trace(go.Scatter(
            x=df_trends['Period'],
            y=df_trends['GrossMargin_Pct'],
            name='毛利率 (%)',
            mode='lines+markers',
            line=dict(color='#10b981', width=2.5)
        ), secondary_y=True)

    if 'OperatingMargin_Pct' in df_trends.columns:
        fig.add_trace(go.Scatter(
            x=df_trends['Period'],
            y=df_trends['OperatingMargin_Pct'],
            name='营业利润率 (%)',
            mode='lines+markers',
            line=dict(color='#f59e0b', width=2.5)
        ), secondary_y=True)

    fig.update_layout(
        title=f"{period_type} 营收、净利润规模与核心盈利能力走势",
        template="plotly_white",
        hovermode="x unified",
        barmode='group',
        height=480
    )
    fig.update_yaxes(title_text="金额 ($ Billion)", secondary_y=False)
    fig.update_yaxes(title_text="利润率 (%)", secondary_y=True)

    return fig


# ------------------------------------------------------------------
# 16. 个股历史 PE / PS Band 估值通道走势图
# ------------------------------------------------------------------
def create_pe_ps_band_chart(df_stock: pd.DataFrame, symbol: str, current_eps: float = None, current_pe: float = None, valuation_type: str = "PE", timeframe: str = "3Y"):
    """
    绘制个股历史股价与动态 PE / PS 估值带 (PE/PS Band) 叠加走势图
    """
    if df_stock is None or df_stock.empty:
        return None

    df = df_stock.copy()
    if 'Date' not in df.columns:
        if isinstance(df.index, pd.DatetimeIndex):
            df = df.reset_index()
            df.rename(columns={'index': 'Date'}, inplace=True)
        elif 'date' in df.columns:
            df.rename(columns={'date': 'Date'}, inplace=True)
        else:
            return None

    df['Date'] = pd.to_datetime(df['Date'])
    df = filter_by_timeframe(df, 'Date', timeframe)
    if df.empty or len(df) < 5:
        return None

    close_col = 'Close' if 'Close' in df.columns else ('close' if 'close' in df.columns else df.columns[1])
    
    # 估值基准指标 (PE对应每股收益EPS, PS对应每股营收SPS)
    if current_eps and current_eps > 0:
        base_metric = float(current_eps)
    elif current_pe and current_pe > 0:
        base_metric = float(df[close_col].iloc[-1]) / float(current_pe)
    else:
        default_mult = 25.0 if valuation_type == "PE" else 5.0
        base_metric = float(df[close_col].mean()) / default_mult

    # 生成估值乘数阶梯 (如 0.6x, 0.8x, 1.0x, 1.25x, 1.5x 估值基准)
    if current_pe and current_pe > 0:
        anchor_mult = float(current_pe)
    else:
        anchor_mult = 25.0 if valuation_type == "PE" else 5.0

    multiples = [
        round(anchor_mult * 0.6, 1 if valuation_type == "PE" else 2),
        round(anchor_mult * 0.8, 1 if valuation_type == "PE" else 2),
        round(anchor_mult * 1.0, 1 if valuation_type == "PE" else 2),
        round(anchor_mult * 1.25, 1 if valuation_type == "PE" else 2),
        round(anchor_mult * 1.5, 1 if valuation_type == "PE" else 2),
    ]

    fig = go.Figure()

    # 绘制估值带虚线通道 (绿、蓝、紫中轨、橙、红顶轨)
    colors = [
        'rgba(16, 185, 129, 0.75)',
        'rgba(59, 130, 246, 0.75)',
        'rgba(139, 92, 246, 0.85)',
        'rgba(245, 158, 11, 0.75)',
        'rgba(239, 68, 68, 0.75)'
    ]
    
    for mult, color in zip(multiples, colors):
        band_price = mult * base_metric
        fig.add_trace(
            go.Scatter(
                x=df['Date'],
                y=[band_price] * len(df),
                mode='lines',
                name=f"{mult}x {valuation_type} (${band_price:.2f})",
                line=dict(color=color, width=1.5, dash='dot'),
                hovertemplate=f"{mult}x {valuation_type} 估值线: ${band_price:.2f}<extra></extra>"
            )
        )

    # 绘制真实股价走势
    fig.add_trace(
        go.Scatter(
            x=df['Date'],
            y=df[close_col],
            mode='lines',
            name=f"{symbol} 真实股价",
            line=dict(color='#1e293b', width=2.5),
            hovertemplate=f"<b>{symbol} 股价</b>: $%{{y:.2f}}<extra></extra>"
        )
    )

    fig.update_layout(
        title=f"{symbol} 动态 {valuation_type} Band 估值通道走势 - [{timeframe}]",
        xaxis_title="日期",
        yaxis_title="价格 (USD)",
        template="plotly_white",
        hovermode="x unified",
        height=500,
        margin=dict(l=40, r=40, t=50, b=40),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        uirevision=f"pe_band_{symbol}_{valuation_type}_{timeframe}"
    )

    return fig


# ------------------------------------------------------------------
# 17. 个股技术面动量指标系统 (K线 + MACD + RSI + 200MA偏离度)
# ------------------------------------------------------------------
def create_technical_momentum_chart(df_stock: pd.DataFrame, symbol: str, timeframe: str = "1Y"):
    if df_stock is None or df_stock.empty:
        return None

    df = df_stock.copy()
    if 'Date' not in df.columns:
        if isinstance(df.index, pd.DatetimeIndex):
            df = df.reset_index()
            df.rename(columns={'index': 'Date'}, inplace=True)
        elif 'date' in df.columns:
            df.rename(columns={'date': 'Date'}, inplace=True)
        else:
            return None

    df['Date'] = pd.to_datetime(df['Date'])
    df = filter_by_timeframe(df, 'Date', timeframe)
    if df.empty or len(df) < 30:
        return None

    d_close = df['Close'].diff()
    g_s = (d_close.where(d_close > 0, 0.0)).fillna(0.0)
    l_s = (-d_close.where(d_close < 0, 0.0)).fillna(0.0)
    ag = g_s.ewm(alpha=1.0/14.0, min_periods=14, adjust=False).mean()
    al = l_s.ewm(alpha=1.0/14.0, min_periods=14, adjust=False).mean()
    rs_val = ag / al.replace(0, np.nan)
    df['RSI'] = (100.0 - (100.0 / (1.0 + rs_val))).fillna(50.0)

    e12 = df['Close'].ewm(span=12, adjust=False).mean()
    e26 = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = e12 - e26
    df['MACD_Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['MACD_Hist'] = df['MACD'] - df['MACD_Signal']

    df['MA200'] = df['Close'].rolling(200).mean()

    fig = make_subplots(
        rows=3,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.04,
        row_heights=[0.55, 0.25, 0.20],
        subplot_titles=[
            f"{symbol} 价格走势与 200MA 年线通道",
            "14日强弱动量指标 (RSI 14)",
            "MACD (12, 26, 9) 趋势动能柱"
        ]
    )

    fig.add_trace(
        go.Scatter(
            x=df['Date'],
            y=df['Close'],
            mode='lines',
            name='收盘价',
            line=dict(color='#1e293b', width=2.0),
            hovertemplate='<b>收盘价</b>: $%{y:.2f}<extra></extra>'
        ),
        row=1, col=1
    )
    if 'MA200' in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df['Date'],
                y=df['MA200'],
                mode='lines',
                name='200MA (年线基准)',
                line=dict(color='#dc2626', width=1.8, dash='dash'),
                hovertemplate='<b>200MA</b>: $%{y:.2f}<extra></extra>'
            ),
            row=1, col=1
        )

    fig.add_trace(
        go.Scatter(
            x=df['Date'],
            y=df['RSI'],
            mode='lines',
            name='RSI 14',
            line=dict(color='#8b5cf6', width=1.8),
            hovertemplate='<b>RSI</b>: %{y:.1f}<extra></extra>'
        ),
        row=2, col=1
    )
    fig.add_hline(y=70, line_dash="dash", line_color="#ef4444", line_width=1, row=2, col=1)
    fig.add_hline(y=30, line_dash="dash", line_color="#10b981", line_width=1, row=2, col=1)

    colors_hist = ['#10b981' if h >= 0 else '#ef4444' for h in df['MACD_Hist']]
    fig.add_trace(
        go.Bar(
            x=df['Date'],
            y=df['MACD_Hist'],
            name='MACD 柱',
            marker_color=colors_hist,
            hovertemplate='<b>动能柱</b>: %{y:+.2f}<extra></extra>'
        ),
        row=3, col=1
    )
    fig.add_trace(
        go.Scatter(
            x=df['Date'],
            y=df['MACD'],
            mode='lines',
            name='DIF (快线)',
            line=dict(color='#2563eb', width=1.2),
            hovertemplate='<b>DIF</b>: %{y:.2f}<extra></extra>'
        ),
        row=3, col=1
    )
    fig.add_trace(
        go.Scatter(
            x=df['Date'],
            y=df['MACD_Signal'],
            mode='lines',
            name='DEA (慢线)',
            line=dict(color='#f59e0b', width=1.2),
            hovertemplate='<b>DEA</b>: %{y:.2f}<extra></extra>'
        ),
        row=3, col=1
    )

    fig.update_layout(
        template="plotly_white",
        hovermode="x unified",
        height=680,
        margin=dict(l=40, r=40, t=50, b=40),
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        ),
        uirevision=f"tech_mom_{symbol}_{timeframe}"
    )

    return fig


# ------------------------------------------------------------------
# 18. 美债期限利差多周期走势图表 (2s10s & 3m10s)
# ------------------------------------------------------------------
def create_yield_spreads_chart(df_spreads: pd.DataFrame, y_range=None, timeframe="ALL"):
    if df_spreads is None or df_spreads.empty:
        return None

    df = df_spreads.copy()
    x_col = 'date' if 'date' in df.columns else ('Date' if 'Date' in df.columns else df.columns[0])
    df[x_col] = pd.to_datetime(df[x_col])
    df = filter_by_timeframe(df, x_col, timeframe)
    if df.empty:
        return None

    fig = go.Figure()

    if '10Y_2Y_Spread' in df.columns:
        fig.add_trace(go.Scatter(
            x=df[x_col],
            y=df['10Y_2Y_Spread'],
            mode='lines',
            name='10Y - 2Y 利差 (2s10s)',
            line=dict(color='#2563eb', width=2)
        ))

    if '10Y_3M_Spread' in df.columns:
        fig.add_trace(go.Scatter(
            x=df[x_col],
            y=df['10Y_3M_Spread'],
            mode='lines',
            name='10Y - 3M 衰退利差',
            line=dict(color='#dc2626', width=1.5, dash='dash')
        ))

    fig.add_hline(y=0.0, line_dash="solid", line_color="#0f172a", line_width=1.2, annotation_text="0.00% 倒挂分界线")

    fig.update_layout(
        title=f'U.S. Treasury Yield Spreads (10Y-2Y & 10Y-3M) - [{timeframe}]',
        xaxis_title='日期',
        yaxis_title='利差 (%)',
        template='plotly_white',
        height=450,
        hovermode='x unified',
        uirevision=f'spreads_{timeframe}'
    )

    if y_range is not None:
        fig.update_yaxes(range=y_range)
    else:
        fig.update_yaxes(autorange=True, fixedrange=False)

    return fig


# ------------------------------------------------------------------
# 19. 周度初请失业金 4周移动均线
# ------------------------------------------------------------------
def create_jobless_claims_chart(df_claims: pd.DataFrame, y_range=None, timeframe="ALL"):
    if df_claims is None or df_claims.empty:
        return None

    df = df_claims.copy()
    x_col = 'date' if 'date' in df.columns else ('Date' if 'Date' in df.columns else df.columns[0])
    df[x_col] = pd.to_datetime(df[x_col])
    df = filter_by_timeframe(df, x_col, timeframe)
    if df.empty:
        return None

    val_col = 'Claims_4W' if 'Claims_4W' in df.columns else ('Value' if 'Value' in df.columns else df.columns[1])

    fig = px.line(
        df,
        x=x_col,
        y=val_col,
        title=f'Initial Jobless Claims 4-Week Moving Average (IC4WSA) - [{timeframe}]',
        labels={x_col: '日期', val_col: '初请人数 (人)'},
        template='plotly_white'
    )
    fig.add_hline(y=250000, line_dash="dash", line_color="#ef4444", annotation_text="25.0 万人失业扩散预警线")

    fig.update_layout(
        height=450,
        hovermode='x unified',
        uirevision=f'claims_{timeframe}',
        yaxis_title='人数'
    )

    if y_range is not None:
        fig.update_yaxes(range=y_range)
    else:
        fig.update_yaxes(autorange=True, fixedrange=False)

    return fig


# ------------------------------------------------------------------
# 20. 美元指数 (DXY) 全球流动性走势图表
# ------------------------------------------------------------------
def create_dxy_chart(df_dxy: pd.DataFrame, y_range=None, timeframe="ALL"):
    if df_dxy is None or df_dxy.empty:
        return None

    df = df_dxy.copy()
    x_col = 'date' if 'date' in df.columns else ('Date' if 'Date' in df.columns else df.columns[0])
    df[x_col] = pd.to_datetime(df[x_col])
    df = filter_by_timeframe(df, x_col, timeframe)
    if df.empty:
        return None

    val_col = 'DXY' if 'DXY' in df.columns else ('Value' if 'Value' in df.columns else df.columns[1])

    fig = px.line(
        df,
        x=x_col,
        y=val_col,
        title=f'U.S. Dollar Index (DTWEXBGS) - [{timeframe}]',
        labels={x_col: '日期', val_col: '美元指数'},
        template='plotly_white'
    )
    fig.update_layout(
        height=450,
        hovermode='x unified',
        uirevision=f'dxy_{timeframe}',
        yaxis_title='指数'
    )

    if y_range is not None:
        fig.update_yaxes(range=y_range)
    else:
        fig.update_yaxes(autorange=True, fixedrange=False)

    return fig


# ------------------------------------------------------------------
# 21. 核心 PCE 与时薪螺旋走势图表 (Inflation & Wages)
# ------------------------------------------------------------------
def create_inflation_wages_chart(df_data: pd.DataFrame, y_range=None, timeframe="ALL"):
    if df_data is None or df_data.empty:
        return None

    df = df_data.copy()
    x_col = 'date' if 'date' in df.columns else ('Date' if 'Date' in df.columns else df.columns[0])
    df[x_col] = pd.to_datetime(df[x_col])
    df = filter_by_timeframe(df, x_col, timeframe)
    if df.empty:
        return None

    fig = go.Figure()

    if 'PCE' in df.columns:
        fig.add_trace(go.Scatter(
            x=df[x_col],
            y=df['PCE'],
            mode='lines+markers',
            name='核心 PCE 同比增速 (%)',
            line=dict(color='#dc2626', width=2)
        ))

    if 'Wages' in df.columns:
        fig.add_trace(go.Scatter(
            x=df[x_col],
            y=df['Wages'],
            mode='lines+markers',
            name='平均时薪同比增速 (%)',
            line=dict(color='#059669', width=2)
        ))

    fig.add_hline(y=2.0, line_dash="dot", line_color="#94a3b8", annotation_text="美联储 2% 目标")

    fig.update_layout(
        title=f'Core PCE YoY vs Average Hourly Earnings YoY - [{timeframe}]',
        xaxis_title='日期',
        yaxis_title='同比增速 (%)',
        template='plotly_white',
        height=450,
        hovermode='x unified',
        uirevision=f'pce_wages_{timeframe}'
    )

    if y_range is not None:
        fig.update_yaxes(range=y_range)
    else:
        fig.update_yaxes(autorange=True, fixedrange=False)

    return fig


# ------------------------------------------------------------------
# 22. 萨姆法则实时衰退预警指标图表 (SAHM Rule)
# ------------------------------------------------------------------
def create_sahm_rule_chart(df_sahm: pd.DataFrame, y_range=None, timeframe="ALL"):
    if df_sahm is None or df_sahm.empty:
        return None

    df = df_sahm.copy()
    x_col = 'date' if 'date' in df.columns else ('Date' if 'Date' in df.columns else df.columns[0])
    df[x_col] = pd.to_datetime(df[x_col])
    df = filter_by_timeframe(df, x_col, timeframe)
    if df.empty:
        return None

    val_col = 'SAHM' if 'SAHM' in df.columns else ('Value' if 'Value' in df.columns else df.columns[1])

    fig = px.line(
        df,
        x=x_col,
        y=val_col,
        title=f'Sahm Rule Real-Time Recession Indicator (SAHMREALTIME) - [{timeframe}]',
        labels={x_col: '日期', val_col: '萨姆读数 (%)'},
        template='plotly_white'
    )
    fig.add_hline(y=0.50, line_dash="dash", line_color="#ef4444", annotation_text="衰退确立警戒红线 (+0.50%)")

    fig.update_layout(
        height=450,
        hovermode='x unified',
        uirevision=f'sahm_{timeframe}',
        yaxis_title='读数 (%)'
    )

    if y_range is not None:
        fig.update_yaxes(range=y_range)
    else:
        fig.update_yaxes(autorange=True, fixedrange=False)

    return fig


# ------------------------------------------------------------------
# 23. 核心资本品新订单走势图表 (Core CapEx Orders)
# ------------------------------------------------------------------
def create_core_capex_chart(df_capex: pd.DataFrame, y_range=None, timeframe="ALL"):
    if df_capex is None or df_capex.empty:
        return None

    df = df_capex.copy()
    x_col = 'date' if 'date' in df.columns else ('Date' if 'Date' in df.columns else df.columns[0])
    df[x_col] = pd.to_datetime(df[x_col])
    df = filter_by_timeframe(df, x_col, timeframe)
    if df.empty:
        return None

    val_col = 'Orders' if 'Orders' in df.columns else ('Value' if 'Value' in df.columns else df.columns[1])

    fig = px.line(
        df,
        x=x_col,
        y=val_col,
        title=f'Core Capital Goods Orders Nondefense Ex Air (NEWORDER) - [{timeframe}]',
        labels={x_col: '日期', val_col: '订单规模 ($ Millions)'},
        template='plotly_white'
    )
    fig.update_layout(
        height=450,
        hovermode='x unified',
        uirevision=f'capex_{timeframe}',
        yaxis_title='金额 ($M)'
    )

    if y_range is not None:
        fig.update_yaxes(range=y_range)
    else:
        fig.update_yaxes(autorange=True, fixedrange=False)

    return fig


# ------------------------------------------------------------------
# 24. 广义货币供应量 M2 同比走势图表 (M2 Money Supply)
# ------------------------------------------------------------------
def create_m2_money_supply_chart(df_m2: pd.DataFrame, y_range=None, timeframe="ALL"):
    if df_m2 is None or df_m2.empty:
        return None

    df = df_m2.copy()
    x_col = 'date' if 'date' in df.columns else ('Date' if 'Date' in df.columns else df.columns[0])
    df[x_col] = pd.to_datetime(df[x_col])
    df = filter_by_timeframe(df, x_col, timeframe)
    if df.empty:
        return None

    val_col = 'M2_YoY' if 'M2_YoY' in df.columns else ('Value' if 'Value' in df.columns else df.columns[1])

    fig = px.line(
        df,
        x=x_col,
        y=val_col,
        title=f'U.S. M2 Money Supply YoY Growth (M2SL) - [{timeframe}]',
        labels={x_col: '日期', val_col: 'M2 同比增速 (%)'},
        template='plotly_white'
    )
    fig.add_hline(y=0.0, line_dash="solid", line_color="#0f172a", line_width=1)

    fig.update_layout(
        height=450,
        hovermode='x unified',
        uirevision=f'm2_{timeframe}',
        yaxis_title='同比 (%)'
    )

    if y_range is not None:
        fig.update_yaxes(range=y_range)
    else:
        fig.update_yaxes(autorange=True, fixedrange=False)

    return fig


# ------------------------------------------------------------------
# 25. 美联储高级信贷调查 (SLOOS 银行贷款净收紧比例)
# ------------------------------------------------------------------
def create_sloos_credit_chart(df_sloos: pd.DataFrame, y_range=None, timeframe="ALL"):
    if df_sloos is None or df_sloos.empty:
        return None

    df = df_sloos.copy()
    x_col = 'date' if 'date' in df.columns else ('Date' if 'Date' in df.columns else df.columns[0])
    df[x_col] = pd.to_datetime(df[x_col])
    df = filter_by_timeframe(df, x_col, timeframe)
    if df.empty:
        return None

    val_col = 'Tightening_Pct' if 'Tightening_Pct' in df.columns else ('Value' if 'Value' in df.columns else df.columns[1])

    fig = px.bar(
        df,
        x=x_col,
        y=val_col,
        title=f'Fed SLOOS Net % of Domestic Banks Tightening Standards - [{timeframe}]',
        labels={x_col: '日期', val_col: '净收紧比例 (%)'},
        template='plotly_white'
    )
    fig.add_hline(y=0.0, line_dash="solid", line_color="#0f172a", line_width=1)

    fig.update_layout(
        height=450,
        hovermode='x unified',
        uirevision=f'sloos_{timeframe}',
        yaxis_title='比例 (%)'
    )

    if y_range is not None:
        fig.update_yaxes(range=y_range)
    else:
        fig.update_yaxes(autorange=True, fixedrange=False)

    return fig
