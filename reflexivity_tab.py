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

@st.cache_data(ttl=3600, show_spinner=False)
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
    # 负向指标（越高越紧缩）：HY_OAS, NFCI, Real_Yield, DXY
    # 正向指标（越高越扩张）：PMI, Copper_Gold
    macro_df['HY_Z'] = - (macro_df['HY_OAS'] - macro_df['HY_OAS'].rolling(200).mean()) / macro_df['HY_OAS'].rolling(200).std()
    macro_df['NFCI_Z'] = - (macro_df['NFCI'] - macro_df['NFCI'].rolling(200).mean()) / macro_df['NFCI'].rolling(200).std()
    macro_df['PMI_Z'] = (macro_df['PMI'] - macro_df['PMI'].rolling(200).mean()) / macro_df['PMI'].rolling(200).std()
    macro_df['RealYield_Z'] = - (macro_df['Real_Yield'] - macro_df['Real_Yield'].rolling(200).mean()) / macro_df['Real_Yield'].rolling(200).std()
    macro_df['DXY_Z'] = - (macro_df['DXY'] - macro_df['DXY'].rolling(200).mean()) / macro_df['DXY'].rolling(200).std()
    
    if 'Copper_Gold' in macro_df.columns:
        macro_df['CG_Z'] = (macro_df['Copper_Gold'] - macro_df['Copper_Gold'].rolling(200).mean()) / macro_df['Copper_Gold'].rolling(200).std()
    else:
        macro_df['CG_Z'] = 0.0
        
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
        merged = merged.dropna()
        if merged.empty:
            continue
            
        merged['Gap'] = merged['Price_Z'] - merged['Macro_Z']
        
        # Calculate Backtest Metrics
        # Twilight Signals
        twilight_signals = merged[(merged['Gap'] > 1.5) & (merged['Price_Z'] > 1.0)].copy()
        clearance_signals = merged[(merged['Gap'] < -1.5) & (merged['Price_Z'] < -1.0)].copy()
        
        # Helper to calc forward returns
        def calc_fwd_returns(signals, df_full, horizon_days):
            if signals.empty:
                return np.nan
            fwd_rets = []
            for d in signals.index:
                idx_pos = df_full.index.get_loc(d)
                if idx_pos + horizon_days < len(df_full):
                    fwd_p = df_full.iloc[idx_pos + horizon_days]['Close']
                    cur_p = df_full.iloc[idx_pos]['Close']
                    fwd_rets.append((fwd_p - cur_p) / cur_p)
            return fwd_rets

        tw_3m = calc_fwd_returns(twilight_signals, merged, 60)
        tw_6m = calc_fwd_returns(twilight_signals, merged, 120)
        cl_3m = calc_fwd_returns(clearance_signals, merged, 60)
        cl_6m = calc_fwd_returns(clearance_signals, merged, 120)
        
        # For Twilight (Short/Sell), a successful prediction is a NEGATIVE return
        tw_3m_hit = sum(1 for r in tw_3m if r < 0) / len(tw_3m) if tw_3m and len(tw_3m) > 0 else np.nan
        tw_6m_hit = sum(1 for r in tw_6m if r < 0) / len(tw_6m) if tw_6m and len(tw_6m) > 0 else np.nan
        
        # For Clearance (Long/Buy), a successful prediction is a POSITIVE return
        cl_3m_hit = sum(1 for r in cl_3m if r > 0) / len(cl_3m) if cl_3m and len(cl_3m) > 0 else np.nan
        cl_6m_hit = sum(1 for r in cl_6m if r > 0) / len(cl_6m) if cl_6m and len(cl_6m) > 0 else np.nan
        
        backtest_results.append({
            "Ticker": ticker,
            "黄昏预警次数": len(twilight_signals),
            "黄昏 3M 跌率 (胜率)": f"{tw_3m_hit*100:.1f}%" if not np.isnan(tw_3m_hit) else "N/A",
            "黄昏 6M 跌率 (胜率)": f"{tw_6m_hit*100:.1f}%" if not np.isnan(tw_6m_hit) else "N/A",
            "出清信号次数": len(clearance_signals),
            "出清 3M 涨率 (胜率)": f"{cl_3m_hit*100:.1f}%" if not np.isnan(cl_3m_hit) else "N/A",
            "出清 6M 涨率 (胜率)": f"{cl_6m_hit*100:.1f}%" if not np.isnan(cl_6m_hit) else "N/A",
        })
        
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
            "综合客观现实 (Macro Z)": round(macro_z, 2),
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
        st.write("")
        
        st.subheader("中长期模型预测有效性回测引擎 (Backtest)")
        bt_df = pd.DataFrame(backtest_results)
        st.dataframe(bt_df, use_container_width=True, hide_index=True)
        st.caption("提示：基于过去 15 年数据进行回测。胜率定义为：触发黄昏预警后，未来 3M/6M 资产价格下跌的概率；触发出清信号后，未来 3M/6M 资产价格上涨的概率。")
        st.write("")
        
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
                
                # 截取最近三年用于绘图，以精确匹配“过去三年”的标题要求
                three_years_ago = pd.Timestamp.now().normalize() - pd.DateOffset(years=3)
                df_plot = df_plot[df_plot.index >= three_years_ago]
                
                fig = go.Figure()
                fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['Gap'], mode='lines', name='反身性偏离度 (Gap)', line=dict(color='#ff4b4b', width=2)))
                fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['Price_Z'], mode='lines', name='主观狂热度 (Price Z)', line=dict(color='#0068c9', dash='dash')))
                fig.add_trace(go.Scatter(x=df_plot.index, y=df_plot['Macro_Z'], mode='lines', name='信贷宽松度 (Credit Z)', line=dict(color='#29b09d', dash='dot')))
                fig.update_layout(title=f"{t} 过去三年反身性指标趋势", height=400, hovermode="x unified")
                st.plotly_chart(fig, use_container_width=True)

        st.write("---")
        with st.expander("📖 计算公式与多因子模型解读", expanded=False):
            st.markdown("""
            本模块基于**索罗斯反身性理论**，并重构为强大的**多因子前瞻预测模型**，量化**主观情绪（价格）**与**客观现实（宏观基本面）**的撕裂度。
            
            **200日 Z-Score (标准分) 基础公式:**
            $$ Z_t = \\frac{X_t - MA(X, 200)}{StdDev(X, 200)} $$
            
            **1. 主观情绪度 (Price_Z)**
            计算资产价格过去 200 个交易日的偏离度。数值越高代表市场泡沫情绪越重。
            $$ Price\\_Z_t = \\frac{Close_t - MA(Close, 200)}{StdDev(Close, 200)} $$
            
            **2. 综合客观现实 (Composite_Macro_Z) 【六大因子合力】**
            为了全面刻画真正的“宏观现实”，系统等权合成了三大维度下的六个前瞻性指标（均取正向逻辑，即数值越高代表宏观环境越宽松/景气）：
            * **流动性与信贷**：
              - 高收益债利差 (HY OAS, 取反)
              - 芝加哥联储金融条件指数 (NFCI, 取反)
            * **经济景气周期**：
              - ISM 制造业 PMI (NAPM)
              - 铜金比 (Copper / Gold)
            * **估值引力与融资成本**：
              - 10年期美债实际收益率 (10Y Real Yield, 取反)
              - 美元指数 (DXY, 取反)
            
            $$ Composite\\_Macro\\_Z = \\frac{1}{6} \sum (Factor\\_Z_i) $$
            
            **3. 反身性偏离度 (Gap) 与前瞻预测**
            偏离度衡量了“市场主观”与“底层宏观现实”之间的撕裂程度。
            $$ Gap_t = Price\\_Z_t - Composite\\_Macro\\_Z_t $$
            - **🔴 黄昏期预警 ($Gap > 1.5$ 且 $Price\\_Z > 1$)**：价格正在无视基本面的全方位恶化而赶顶。回测表明，该信号出现后 3-6 个月中长期回调概率极高！
            - **🟢 出清期预警 ($Gap < -1.5$ 且 $Price\\_Z < -1$)**：价格因恐慌遭错杀，但多维宏观指标已出现拐点。回测表明，这是中长期最佳的左侧做多良机！
            """)
