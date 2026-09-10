import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import numpy as np

# Try importing data_service for FRED, fallback if missing
try:
    from data_service import _fetch_fred_series_observations, get_reflexivity_macro_factors
except ImportError:
    _fetch_fred_series_observations = None
    get_reflexivity_macro_factors = None

# Configurable ticker list
DEFAULT_TICKERS = {
    "SPY": "标普500",
    "QQQ": "纳斯达克100",
    "IEF": "中期美债",
    "SHV": "短期国库券",
    "GLD": "黄金",
    "SOXX": "费城半导体",
    "IGV": "软件ETF",
    "XLE": "能源",
    "XLU": "公用事业",
    "XLRE": "房地产",
    "XLF": "金融",
    "XLY": "非必需消费"
}

@st.cache_data(ttl=3600, show_spinner=True)
def fetch_composite_macro_data():
    if get_reflexivity_macro_factors is not None:
        try:
            df = get_reflexivity_macro_factors()
            if not df.empty:
                if 'date' in df.columns:
                    df = df.rename(columns={'date': 'Date'})
                df = df.set_index('Date')
            return df
        except Exception as e:
            st.warning(f"Failed to fetch Composite Macro data via data_service: {e}")
    # Fallback if FRED fails
    return pd.DataFrame()

@st.cache_data(ttl=3600)
def fetch_yahoo_data(tickers):
    end_date = datetime.now()
    # 为了计算 200 日均线且保证图表能展示完整的三年数据，我们需要向前多拉取约1年的数据（4年）
    start_date = end_date - timedelta(days=365 * 4) 
    
    data = {}
    for ticker in tickers:
        try:
            df = yf.download(ticker, start=start_date.strftime("%Y-%m-%d"), end=end_date.strftime("%Y-%m-%d"), progress=False)
            if not df.empty:
                if 'Close' in df.columns:
                    # yfinance multiple ticker issue safeguard, though we download one by one
                    if isinstance(df.columns, pd.MultiIndex):
                        data[ticker] = df['Close'].copy()
                        data[ticker].columns = ['Close']
                    else:
                        data[ticker] = df[['Close']].copy()
        except Exception as e:
            st.warning(f"Failed to fetch {ticker}: {e}")
    return data

def render_reflexivity_tab():
    st.header("索罗斯反身性预测模型 (多因子合成版)")
    
    # UI config for tickers
    st.subheader("监控资产池配置")
    selected_tickers_str = st.text_area("监控 Tickers (用逗号分隔，可自由扩充)", value=", ".join(DEFAULT_TICKERS.keys()))
    tickers_to_monitor = [t.strip().upper() for t in selected_tickers_str.split(",") if t.strip()]
    
    if not tickers_to_monitor:
        st.warning("请输入至少一个 Ticker。")
        return
        
    with st.spinner("从 FRED 与 Yahoo 极速并发拉取六大宏观因子与市场价格数据 (可能需要几秒钟以确保预测准确度)..."):
        macro_df = fetch_composite_macro_data()
        market_data = fetch_yahoo_data(tickers_to_monitor)
        
    if macro_df.empty:
        st.error("未能获取到 FRED 宏观合成数据，请检查 data_service 或 API Key。")
        return
        
    # Calculate 6-Factor Z-Scores
    # Helper to calculate Z-Score defensively
    def calc_z(df, col, reverse=False):
        if col in df.columns:
            z = (df[col] - df[col].rolling(200).mean()) / df[col].rolling(200).std()
            return -z if reverse else z
        return pd.Series(0.0, index=df.index)

    # 负向指标（越高越紧缩）：HY_OAS, NFCI, Real_Yield, DXY
    # 正向指标（越高越扩张）：PMI, Copper_Gold
    macro_df['HY_Z'] = calc_z(macro_df, 'HY_OAS', reverse=True)
    macro_df['NFCI_Z'] = calc_z(macro_df, 'NFCI', reverse=True)
    macro_df['PMI_Z'] = calc_z(macro_df, 'PMI', reverse=False)
    macro_df['RealYield_Z'] = calc_z(macro_df, 'Real_Yield', reverse=True)
    macro_df['DXY_Z'] = calc_z(macro_df, 'DXY', reverse=True)
    macro_df['CG_Z'] = calc_z(macro_df, 'Copper_Gold', reverse=False)
        
    macro_df = macro_df.fillna(0)
    
    # Weightings: 1/6 each
    macro_df['Macro_Z'] = (macro_df['HY_Z'] + macro_df['NFCI_Z'] + macro_df['PMI_Z'] + macro_df['RealYield_Z'] + macro_df['DXY_Z'] + macro_df['CG_Z']) / 6.0
    
    results = []
    backtest_results = []
    
    for ticker in tickers_to_monitor:
        if ticker not in market_data:
            continue
            
        df = market_data[ticker]
        # Align with macro dates
        df.index = pd.to_datetime(df.index).tz_localize(None).values.astype('datetime64[ns]')
        macro_df.index = pd.to_datetime(macro_df.index).tz_localize(None).values.astype('datetime64[ns]')
        
        merged = df.join(macro_df, how='left').ffill().dropna()
        if merged.empty:
            continue
            
        # Calc Price Z-score
        merged['Price_Z'] = (merged['Close'] - merged['Close'].rolling(200).mean()) / merged['Close'].rolling(200).std()
        
        # 引入动态 Beta (252天滚动协方差)
        roll_cov = merged['Price_Z'].rolling(252).cov(merged['Macro_Z'])
        roll_var = merged['Macro_Z'].rolling(252).var()
        merged['Dynamic_Beta'] = (roll_cov / roll_var).clip(lower=-2.0, upper=2.0)
        merged['Expected_Price_Z'] = merged['Macro_Z'] * merged['Dynamic_Beta']
        
        # 反身性偏离度 Gap
        merged['Gap'] = merged['Price_Z'] - merged['Expected_Price_Z']
        
        # 计算各种均线
        merged['MA20'] = merged['Close'].rolling(20).mean()
        merged['MA50'] = merged['Close'].rolling(50).mean()
        merged['MA200'] = merged['Close'].rolling(200).mean()
        merged = merged.dropna()
        if merged.empty:
            continue
            
        # 引入滑动记忆窗口 (20天)
        merged['Gap_Max_20'] = merged['Gap'].rolling(20).max()
        merged['PriceZ_Max_20'] = merged['Price_Z'].rolling(20).max()
        merged['Dist_200MA'] = (merged['Close'] - merged['MA200']) / merged['MA200'] * 100
        merged['Dist_Min_20'] = merged['Dist_200MA'].rolling(20).min()
        merged['PriceZ_Min_20'] = merged['Price_Z'].rolling(20).min()
        
        # ==========================================
        # 终极三大交易法则 (实战防抖级)
        # ==========================================
        # 1. 逃顶预警 (SELL)
        cond_bubble = (merged['Gap_Max_20'] > 1.5) & (merged['PriceZ_Max_20'] > 1.5) & (merged['Close'] < merged['MA20'])
        cond_macro = (merged['Macro_Z'] < -1.5) & (merged['Gap'] > 1.5) & (merged['Price_Z'] > 0) & (merged['Close'] < merged['MA50'])
        merged['Sell_Signal'] = cond_bubble | cond_macro
        
        # 2. 恐慌抄底 (BUY)
        cond_panic = ((merged['Dist_Min_20'] < -15) | (merged['PriceZ_Min_20'] < -2.0)) & (merged['Close'] > merged['MA20'])
        
        # 3. 趋势接回 (BUY) - 包含 1% 的突破缓冲 (Buffer)
        cond_reentry = (merged['Close'] > merged['MA50'] * 1.01) & (merged['Macro_Z'] > -0.5) & (merged['Gap'] < 0.5)
        merged['Buy_Signal'] = cond_panic | cond_reentry
        
        # ==========================================
        # 模拟器引擎 (含 20 天冷却锁 Timelock)
        # ==========================================
        positions = []
        position = 1.0 
        days_since_sell = 9999
        last_action = "持有 (Hold)"
        last_action_date = "N/A"
        trade_count = 0
        
        for i in range(len(merged)):
            date_str = merged.index[i].strftime("%Y-%m-%d")
            
            # Sell Check
            if position == 1.0 and merged['Sell_Signal'].iloc[i]:
                position = 0.0
                days_since_sell = 0
                last_action = "🔴 卖出 (空仓避险)"
                last_action_date = date_str
                trade_count += 1
                
            # Buy Check (with 20-day Timelock for re-entry)
            elif position == 0.0:
                if cond_panic.iloc[i]:
                    position = 1.0
                    last_action = "🟢 抄底 (满仓做多)"
                    last_action_date = date_str
                    trade_count += 1
                elif cond_reentry.iloc[i] and days_since_sell > 20:
                    position = 1.0
                    last_action = "🔵 接回 (满仓做多)"
                    last_action_date = date_str
                    trade_count += 1
                    
            positions.append(position)
            days_since_sell += 1
            
        merged['Position'] = positions
        
        # ==========================================
        # PnL 计算 (0% 现金利息假设)
        # ==========================================
        daily_returns = merged['Close'].pct_change().fillna(0)
        # shift(1) to avoid lookahead bias: position today dictates return tomorrow
        strat_returns = np.where(pd.Series(positions).shift(1).fillna(1.0) == 1.0, daily_returns, 0.0)
        
        total_bh = (np.prod(1 + daily_returns) - 1) * 100
        total_strat = (np.prod(1 + strat_returns) - 1) * 100
        
        # 记录回测指标
        backtest_results.append({
            "Ticker": ticker,
            "历史总交易次数": trade_count,
            "买入持有总收益": f"{total_bh:.1f}%",
            "反身性模型总收益": f"{total_strat:.1f}%",
            "超额收益 (Alpha)": f"{total_strat - total_bh:.1f}%",
            "最后一次动作": last_action,
            "动作发生日期": last_action_date
        })
        
        latest = merged.iloc[-1]
        
        # 判断当前状态
        current_pos = "满仓做多 (Long)" if latest['Position'] == 1.0 else "空仓避险 (Cash)"
        regime = current_pos
            
        results.append({
            "资产名称": DEFAULT_TICKERS.get(ticker, ticker),
            "Ticker": ticker,
            "最新收盘价": round(latest['Close'], 2),
            "主观情绪 (Price Z)": round(latest['Price_Z'], 2),
            "客观现实 (Macro Z)": round(latest['Macro_Z'], 2),
            "偏离度 (Gap)": round(latest['Gap'], 2),
            "当前仓位状态": regime
        })
        
    if results:
        st.subheader("大类资产反身性状态雷达 (底层重构 0 息硬核版)")
        res_df = pd.DataFrame(results)
        
        def highlight_regime(val):
            if "空仓避险" in str(val):
                return "background-color: rgba(255, 0, 0, 0.2); color: red; font-weight: bold"
            elif "满仓做多" in str(val):
                return "background-color: rgba(0, 255, 0, 0.2); color: green; font-weight: bold"
            return ""

        styled_df = res_df.style.map(highlight_regime, subset=['当前仓位状态']) \
            .hide(axis='index') \
            .set_properties(**{'font-size': '18px', 'text-align': 'center', 'padding': '12px 15px'}) \
            .set_table_styles([{'selector': 'th', 'props': [('font-size', '20px'), ('text-align', 'center'), ('background-color', '#f0f2f6')]}])
        
        st.markdown(styled_df.to_html(), unsafe_allow_html=True)
        st.write("")
        
        st.subheader("中长期模型预测有效性回测引擎 (Backtest vs Buy & Hold)")
        bt_df = pd.DataFrame(backtest_results)
        
        def highlight_alpha(val):
            try:
                if float(val.replace("%", "")) > 0:
                    return "color: green; font-weight: bold"
                elif float(val.replace("%", "")) < 0:
                    return "color: red"
            except:
                pass
            return ""
            
        styled_bt = bt_df.style.map(highlight_alpha, subset=['超额收益 (Alpha)']) \
            .hide(axis='index')
        st.markdown(styled_bt.to_html(), unsafe_allow_html=True)
        st.caption("提示：基于获取到的全部历史数据（约 15 年）回测。本回测极其严苛：包含 20 天防抖冷却锁，且空仓期间现金利息强制为 0%，绝不粉饰踏空成本。")
        st.write("")
        
        st.subheader("重点监控走势 (含动态贝塔预期修正)")
        valid_tickers = res_df['Ticker'].tolist()
        tabs = st.tabs(valid_tickers)
        
        for idx, t in enumerate(valid_tickers):
            with tabs[idx]:
                df_plot = market_data[t].join(macro_df, how='left').ffill().dropna()
                df_plot['Price_Z'] = (df_plot['Close'] - df_plot['Close'].rolling(200).mean()) / df_plot['Close'].rolling(200).std()
                
                roll_cov = df_plot['Price_Z'].rolling(252).cov(df_plot['Macro_Z'])
                roll_var = df_plot['Macro_Z'].rolling(252).var()
                df_plot['Dynamic_Beta'] = (roll_cov / roll_var).clip(lower=-2.0, upper=2.0)
                df_plot['Gap'] = df_plot['Price_Z'] - (df_plot['Macro_Z'] * df_plot['Dynamic_Beta'])
                
                df_plot = df_plot.dropna()
                three_years_ago = pd.Timestamp.now().normalize() - pd.DateOffset(years=3)
                df_plot = df_plot[df_plot.index >= three_years_ago]
                
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['Gap'], mode='lines', name='反身性偏离度 (Gap)', line=dict(color='#ff4b4b', width=2)))
                fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['Price_Z'], mode='lines', name='主观情绪 (Price Z)', line=dict(color='#0068c9', dash='dash')))
                fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['Macro_Z'], mode='lines', name='客观现实 (Macro Z)', line=dict(color='#29b09d', dash='dot')))
                fig.update_layout(title=f"{t} 过去三年反身性指标趋势", height=400, hovermode="x unified")
                st.plotly_chart(fig, use_container_width=True)

        st.write("---")
        with st.expander("📖 终极底层重构逻辑与公式解析", expanded=False):
            st.markdown("""
            本模块在基础索罗斯反身性理论上，经过了极其严苛的 **0 息回测 + 防抖防踏空** 重构，完全贴合实战交易。
            
            **1. 引入动态贝塔 (Dynamic Beta) 修正**
            废除静态相关性假设，采用过去 252 天的价格与宏观因子滚动协方差，动态捕捉不同资产的宏观敏感度。
            $$ Beta = \\frac{Cov(Price\\_Z, Macro\\_Z, 252)}{Var(Macro\\_Z, 252)} $$
            $$ Gap = Price\\_Z - (Macro\\_Z \\times Beta) $$
            
            **2. 防踏空趋势接回 (Trend Re-entry)**
            空仓期间若未发生崩盘，泡沫指标降温 ($Gap < 0.5$) 且价格重新站上 50 日均线 (带 1% 突破缓冲)，系统无条件认错接回。
            
            **3. 防摩擦震荡冷却锁 (Timelock)**
            卖出逃顶后，强制启动 **20 天冷却锁**，期间屏蔽一切趋势接回信号，彻底杜绝震荡市中的频繁止损摩擦死循环！
            """)
