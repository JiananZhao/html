import streamlit as st
import pandas as pd
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
import numpy as np

# Try importing data_service for FRED, fallback if missing
try:
    from data_service import _fetch_fred_series_observations
except ImportError:
    _fetch_fred_series_observations = None

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

@st.cache_data(ttl=3600)
def fetch_macro_credit_spread():
    if _fetch_fred_series_observations is not None:
        try:
            df = _fetch_fred_series_observations("BAMLH0A0HYM2", "Value", "2000-01-01")
            if not df.empty:
                if 'date' in df.columns:
                    df = df.rename(columns={'date': 'Date'})
                df = df.set_index('Date')
            return df
        except Exception as e:
            st.warning(f"Failed to fetch FRED data via data_service: {e}")
    # Fallback/Mock if FRED fails
    return pd.DataFrame()

@st.cache_data(ttl=3600)
def fetch_yahoo_data(tickers):
    end_date = datetime.now()
    start_date = end_date - timedelta(days=365 * 3) # 3 years
    
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
    st.header("索罗斯反身性大类资产配置 (MVP)")
    
    # UI config for tickers
    st.subheader("监控资产池配置")
    selected_tickers_str = st.text_area("监控 Tickers (用逗号分隔，可自由扩充)", value=", ".join(DEFAULT_TICKERS.keys()))
    tickers_to_monitor = [t.strip().upper() for t in selected_tickers_str.split(",") if t.strip()]
    
    if not tickers_to_monitor:
        st.warning("请输入至少一个 Ticker。")
        return
        
    with st.spinner("拉取宏观信贷与市场价格数据..."):
        macro_df = fetch_macro_credit_spread()
        market_data = fetch_yahoo_data(tickers_to_monitor)
        
    if macro_df.empty:
        st.error("未能获取到 FRED 高收益债利差数据，请检查 data_service 或 API Key。")
        return
        
    # Calculate Macro Z-Score
    macro_df['Macro_Z'] = - (macro_df['Value'] - macro_df['Value'].rolling(200).mean()) / macro_df['Value'].rolling(200).std()
    
    results = []
    
    for ticker in tickers_to_monitor:
        if ticker not in market_data:
            continue
            
        df = market_data[ticker]
        # Align with macro dates
        df.index = pd.to_datetime(df.index).tz_localize(None)
        macro_df.index = pd.to_datetime(macro_df.index).tz_localize(None)
        
        merged = df.join(macro_df, how='left').ffill().dropna()
        if merged.empty:
            continue
            
        # Calc Price Z-score
        merged['Price_Z'] = (merged['Close'] - merged['Close'].rolling(200).mean()) / merged['Close'].rolling(200).std()
        merged = merged.dropna()
        if merged.empty:
            continue
            
        merged['Gap'] = merged['Price_Z'] - merged['Macro_Z']
        
        latest = merged.iloc[-1]
        
        # Determine Regime
        gap = latest['Gap']
        price_z = latest['Price_Z']
        macro_z = latest['Macro_Z']
        
        if gap > 1.5 and price_z > 1:
            regime = "🔴 黄昏期 (高危/泡沫)"
        elif gap < -1.5 and price_z < -1:
            regime = "🟢 出清期 (悲观/左侧机会)"
        elif price_z > 0 and macro_z > 0:
            regime = "🔥 繁荣期 (顺势做多)"
        elif price_z < 0 and macro_z < 0:
            regime = "❄️ 衰退期 (持币/防守)"
        else:
            regime = "🟡 震荡/复苏期"
            
        results.append({
            "资产名称": DEFAULT_TICKERS.get(ticker, ticker),
            "Ticker": ticker,
            "最新收盘价": round(latest['Close'], 2),
            "主观情绪 (Price Z)": round(price_z, 2),
            "客观现实 (Credit Z)": round(macro_z, 2),
            "反身性偏离度 (Gap)": round(gap, 2),
            "当前阶段": regime
        })
        
    if results:
        st.subheader("大类资产反身性状态雷达")
        res_df = pd.DataFrame(results)
        
        def highlight_regime(val):
            if "黄昏期" in str(val):
                return "background-color: rgba(255, 0, 0, 0.2); color: red; font-weight: bold"
            elif "出清期" in str(val):
                return "background-color: rgba(0, 255, 0, 0.2); color: green; font-weight: bold"
            return ""

        # 使用 HTML 渲染表格，以强制应用大字体和更紧凑的排版
        styled_df = res_df.style.map(highlight_regime, subset=['当前阶段']) \
            .hide(axis='index') \
            .set_properties(**{'font-size': '18px', 'text-align': 'center', 'padding': '12px 15px'}) \
            .set_table_styles([{'selector': 'th', 'props': [('font-size', '20px'), ('text-align', 'center'), ('background-color', '#f0f2f6')]}])
        
        st.markdown(styled_df.to_html(), unsafe_allow_html=True)
        st.write("") # Add a little spacing
        
        # Interactive Tabs for all assets
        st.subheader("重点监控走势")
        valid_tickers = res_df['Ticker'].tolist()
        tabs = st.tabs(valid_tickers)
        
        for idx, t in enumerate(valid_tickers):
            with tabs[idx]:
                df_plot = market_data[t].join(macro_df, how='left').ffill().dropna()
                df_plot['Price_Z'] = (df_plot['Close'] - df_plot['Close'].rolling(200).mean()) / df_plot['Close'].rolling(200).std()
                df_plot['Gap'] = df_plot['Price_Z'] - df_plot['Macro_Z']
                df_plot = df_plot.dropna()
                
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['Gap'], mode='lines', name='反身性偏离度 (Gap)', line=dict(color='#ff4b4b', width=2)))
                fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['Price_Z'], mode='lines', name='主观狂热度 (Price Z)', line=dict(color='#0068c9', dash='dash')))
                fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['Macro_Z'], mode='lines', name='信贷宽松度 (Credit Z)', line=dict(color='#29b09d', dash='dot')))
                fig.update_layout(title=f"{t} 过去三年反身性指标趋势", height=400, hovermode="x unified")
                st.plotly_chart(fig, use_container_width=True)

        st.write("---")
        with st.expander("📖 计算公式与指标详细解读", expanded=False):
            st.markdown("""
            本模块基于索罗斯反身性理论，量化**资产主观狂热度（价格）**与**客观信贷现实（高收益债利差）**的背离。
            
            - **主观认知 ($X_t$)**: 资产收盘价的 200日 Z-Score。
            - **客观现实 ($Y_t$)**: 高收益债利差的负向 200日 Z-Score（利差越低，信用越宽松）。
            - **反身性偏离度 ($Gap_t$)**: $X_t - Y_t$。偏离度过高预示**黄昏期（泡沫破裂风险）**。
            """)
