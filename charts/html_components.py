"""
Interactive HTML/JS Chart Components for Macro & Equity Research Terminal
Provides TradingView Lightweight Charts & Apache ECharts with dynamic Y-axis auto-scaling.
"""
import json
import pandas as pd
import numpy as np
import streamlit as st
import streamlit.components.v1 as components
from charts.theme import filter_by_timeframe



def get_chart_theme_tokens(theme_mode: str = None) -> dict:
    """
    获取图表组件主题调色令牌 (Dark Mode vs Bright/Daytime Mode)
    自适应 session_state["theme_mode"]
    """
    if theme_mode is None:
        try:
            theme_mode = st.session_state.get("theme_mode", "dark")
        except Exception:
            theme_mode = "dark"

    if theme_mode == "light":
        return {
            "mode": "light",
            "body_bg": "#ffffff",
            "card_bg": "#ffffff",
            "border_color": "#e2e8f0",
            "box_shadow": "0 2px 12px rgba(0,0,0,0.06)",
            "title_color": "#0f172a",
            "subtitle_color": "#64748b",
            "text_color": "#1e293b",
            "legend_text": "#334155",
            "axis_line": "#cbd5e1",
            "axis_label": "#64748b",
            "split_line": "rgba(0, 0, 0, 0.06)",
            "tooltip_bg": "rgba(255, 255, 255, 0.96)",
            "tooltip_border": "#cbd5e1",
            "tooltip_text": "#0f172a",
            "echarts_theme": "light",
            "datazoom_bg": "#f8fafc",
            "datazoom_border": "#e2e8f0",
            "datazoom_filler": "rgba(37, 99, 235, 0.12)",
            "datazoom_handle": "#2563eb",
            "stock_line_color": "#0f172a",
            "tv_bg": "#ffffff",
            "tv_text": "#475569",
            "tv_vert_grid": "#f1f5f9",
            "tv_horz_grid": "#f1f5f9",
            "tv_border": "#e2e8f0",
            "tv_btn_bg": "rgba(241, 245, 249, 0.9)",
            "tv_btn_border": "#cbd5e1",
            "tv_btn_text": "#475569",
            "tv_btn_active_text": "#2563eb",
            "tv_btn_active_bg": "rgba(37, 99, 235, 0.12)",
            "hud_bg": "rgba(255, 255, 255, 0.92)",
            "hud_border": "#cbd5e1",
            "hud_text": "#0f172a",
            "hud_muted": "#64748b",
            "badge_bg": "rgba(37, 99, 235, 0.08)",
            "badge_color": "#1d4ed8",
            "badge_border": "rgba(37, 99, 235, 0.2)",
            "tag_bg": "rgba(16, 185, 129, 0.1)",
            "tag_color": "#059669",
            "tag_border": "rgba(16, 185, 129, 0.25)",
            "tag_mp_bg": "rgba(234, 179, 8, 0.15)",
            "tag_mp_color": "#b45309",
            "tag_mp_border": "rgba(234, 179, 8, 0.3)",
        }
    else:  # dark
        return {
            "mode": "dark",
            "body_bg": "#0b0e14",
            "card_bg": "#0b0e14",
            "border_color": "#1e293b",
            "box_shadow": "0 8px 24px rgba(0,0,0,0.35)",
            "title_color": "#f8fafc",
            "subtitle_color": "#94a3b8",
            "text_color": "#e2e8f0",
            "legend_text": "#cbd5e1",
            "axis_line": "#334155",
            "axis_label": "#94a3b8",
            "split_line": "rgba(255, 255, 255, 0.05)",
            "tooltip_bg": "rgba(15, 23, 42, 0.95)",
            "tooltip_border": "#334155",
            "tooltip_text": "#f8fafc",
            "echarts_theme": "dark",
            "datazoom_bg": "#0f172a",
            "datazoom_border": "#1e293b",
            "datazoom_filler": "rgba(56, 189, 248, 0.15)",
            "datazoom_handle": "#38bdf8",
            "stock_line_color": "#f8fafc",
            "tv_bg": "#0b0e14",
            "tv_text": "#94a3b8",
            "tv_vert_grid": "rgba(30, 41, 59, 0.5)",
            "tv_horz_grid": "rgba(30, 41, 59, 0.5)",
            "tv_border": "#1e293b",
            "tv_btn_bg": "rgba(30, 41, 59, 0.7)",
            "tv_btn_border": "rgba(255, 255, 255, 0.08)",
            "tv_btn_text": "#94a3b8",
            "tv_btn_active_text": "#38bdf8",
            "tv_btn_active_bg": "rgba(56, 189, 248, 0.2)",
            "hud_bg": "rgba(15, 23, 42, 0.85)",
            "hud_border": "#334155",
            "hud_text": "#f8fafc",
            "hud_muted": "#94a3b8",
            "badge_bg": "rgba(37, 99, 235, 0.2)",
            "badge_color": "#60a5fa",
            "badge_border": "rgba(37, 99, 235, 0.4)",
            "tag_bg": "rgba(16, 185, 129, 0.2)",
            "tag_color": "#34d399",
            "tag_border": "rgba(16, 185, 129, 0.4)",
            "tag_mp_bg": "rgba(234, 179, 8, 0.2)",
            "tag_mp_color": "#facc15",
            "tag_mp_border": "rgba(234, 179, 8, 0.4)",
        }


# ------------------------------------------------------------------
# 1. TradingView Lightweight Charts (个股 K线 / 折线 + 均线 + 成交量)
# ------------------------------------------------------------------
def render_tradingview_stock_chart(
    df_stock: pd.DataFrame,
    symbol: str,
    chart_type: str = "Candlestick",
    timeframe: str = "ALL",
    height: int = 600
):
    t = get_chart_theme_tokens()
    """
    使用 TradingView Lightweight Charts 渲染个股行情图
    特性:
    - 60 FPS HTML5 Canvas 极速流畅渲染
    - 视口 X 轴缩放/拖动时，Y 轴自动毫秒级紧密自适应 (autoScale: true)
    - 浮动实时 HUD 看板 (O, H, L, C, Volume, MA20, MA50, MA200)
    - 顶部时间跨度一键自适应按钮 (1M, 3M, 6M, 1Y, 3Y, 5Y, ALL)
    - 完美适配深色机构投研终端质感，遵从大字号规范 (14px+)
    """
    if df_stock is None or df_stock.empty:
        st.warning(f"标的 {symbol} 暂无有效历史行情数据。")
        return False

    df = df_stock.copy()
    if 'Date' not in df.columns:
        if isinstance(df.index, pd.DatetimeIndex):
            df = df.reset_index()
            df.rename(columns={'index': 'Date'}, inplace=True)
        elif 'date' in df.columns:
            df.rename(columns={'date': 'Date'}, inplace=True)
        else:
            st.error("行情数据缺少 Date 日期列。")
            return False

    df['Date'] = pd.to_datetime(df['Date'])
    col_map = {c: c.capitalize() for c in df.columns if c.lower() in ['open', 'high', 'low', 'close', 'volume']}
    df.rename(columns=col_map, inplace=True)

    # 排序与去重
    df = df.sort_values('Date').drop_duplicates(subset=['Date']).reset_index(drop=True)

    # 计算均线系统 (若数据充足)
    if 'Close' in df.columns:
        df['MA20'] = df['Close'].rolling(window=20, min_periods=5).mean()
        df['MA50'] = df['Close'].rolling(window=50, min_periods=10).mean()
        df['MA200'] = df['Close'].rolling(window=200, min_periods=20).mean()

    # 纯前端矢量 Canvas 引擎：将全部可用历史数据传入前端（5年/10年）
    # 用户在前端点击 1M/3M/6M/1Y/3Y/5Y/ALL 或滚轮缩放时，可无缝平滑查看全部历史，绝不截断丢弃历史数据
    df_view = df

    has_ohlc = all(col in df_view.columns for col in ['Open', 'High', 'Low', 'Close']) and chart_type == "Candlestick"
    has_volume = 'Volume' in df_view.columns and (df_view['Volume'].fillna(0) > 0).any()

    # 格式化数据为 JSON
    candles_data = []
    line_data = []
    volume_data = []
    ma20_data = []
    ma50_data = []
    ma200_data = []

    for _, row in df_view.iterrows():
        dt_str = row['Date'].strftime('%Y-%m-%d')
        close_val = float(row['Close']) if pd.notna(row.get('Close')) else None

        if close_val is None:
            continue

        if has_ohlc:
            o = float(row['Open']) if pd.notna(row.get('Open')) else close_val
            h = float(row['High']) if pd.notna(row.get('High')) else max(o, close_val)
            l = float(row['Low']) if pd.notna(row.get('Low')) else min(o, close_val)
            c = close_val
            candles_data.append({"time": dt_str, "open": o, "high": h, "low": l, "close": c})
        else:
            line_data.append({"time": dt_str, "value": close_val})

        if has_volume and pd.notna(row.get('Volume')):
            vol = float(row['Volume'])
            is_up = (row['Close'] >= row['Open']) if ('Open' in row and pd.notna(row['Open'])) else True
            volume_data.append({
                "time": dt_str,
                "value": vol,
                "color": 'rgba(16, 185, 129, 0.45)' if is_up else 'rgba(244, 63, 94, 0.45)'
            })

        if 'MA20' in row and pd.notna(row['MA20']):
            ma20_data.append({"time": dt_str, "value": round(float(row['MA20']), 2)})
        if 'MA50' in row and pd.notna(row['MA50']):
            ma50_data.append({"time": dt_str, "value": round(float(row['MA50']), 2)})
        if 'MA200' in row and pd.notna(row['MA200']):
            ma200_data.append({"time": dt_str, "value": round(float(row['MA200']), 2)})

    candles_json = json.dumps(candles_data)
    line_json = json.dumps(line_data)
    volume_json = json.dumps(volume_data)
    ma20_json = json.dumps(ma20_data)
    ma50_json = json.dumps(ma50_data)
    ma200_json = json.dumps(ma200_data)

    latest_close = df_view['Close'].iloc[-1] if 'Close' in df_view.columns and not df_view.empty else 0.0
    latest_dt = df_view['Date'].iloc[-1].strftime('%Y-%m-%d') if not df_view.empty else ''

    html_code = f"""
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <!-- 引入 TradingView Lightweight Charts -->
        <script src="https://unpkg.com/lightweight-charts@4.1.3/dist/lightweight-charts.standalone.production.js"></script>
        <style>
            * {{ box-sizing: border-box; }}
            body {{
                margin: 0;
                padding: 0;
                background-color: #0b0e14;
                color: #e2e8f0;
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
                overflow: hidden;
            }}
            #chart_wrapper {{
                position: relative;
                width: 100%;
                height: {height}px;
                background: #0b0e14;
                border: 1px solid #1e293b;
                border-radius: 12px;
                box-shadow: 0 8px 24px rgba(0,0,0,0.35);
            }}
            .toolbar {{
                position: absolute;
                top: 10px;
                left: 14px;
                right: 14px;
                z-index: 20;
                display: flex;
                justify-content: space-between;
                align-items: center;
                pointer-events: auto;
            }}
            .symbol-badge {{
                display: flex;
                align-items: center;
                gap: 8px;
                font-size: 15px;
                font-weight: 700;
                color: #f8fafc;
            }}
            .tag {{
                font-size: 12px;
                font-weight: 600;
                padding: 2px 8px;
                border-radius: 4px;
                background: rgba(37, 99, 235, 0.2);
                color: #60a5fa;
                border: 1px solid rgba(37, 99, 235, 0.4);
            }}
            .time-buttons {{
                display: flex;
                gap: 4px;
                background: rgba(30, 41, 59, 0.7);
                backdrop-filter: blur(8px);
                padding: 3px 5px;
                border-radius: 8px;
                border: 1px solid rgba(255, 255, 255, 0.08);
            }}
            .time-btn {{
                background: transparent;
                border: none;
                color: #94a3b8;
                font-size: 12px;
                font-weight: 600;
                padding: 4px 8px;
                border-radius: 5px;
                cursor: pointer;
                transition: all 0.15s ease;
            }}
            .time-btn:hover {{
                color: #ffffff;
                background: rgba(255, 255, 255, 0.1);
            }}
            .time-btn.active {{
                color: #38bdf8;
                background: rgba(56, 189, 248, 0.2);
            }}
            .hud-legend {{
                position: absolute;
                top: 48px;
                left: 14px;
                z-index: 15;
                font-size: 13px;
                color: #cbd5e1;
                display: flex;
                flex-wrap: wrap;
                gap: 12px;
                pointer-events: none;
                line-height: 1.4;
            }}
            .hud-val {{ font-weight: 700; }}
            .c-green {{ color: #10b981; }}
            .c-red {{ color: #f43f5e; }}
            .c-ma20 {{ color: #f59e0b; }}
            .c-ma50 {{ color: #8b5cf6; }}
            .c-ma200 {{ color: #ef4444; }}
            #tv_container {{
                width: 100%;
                height: 100%;
            }}
        </style>
    </head>
    <body>
        <div id="chart_wrapper">
            <div class="toolbar">
                <div class="symbol-badge">
                    <span>{symbol}</span>
                    <span class="tag">{'K 线走势' if has_ohlc else '折线走势'}</span>
                </div>
                <div class="time-buttons">
                    <button class="time-btn" onclick="applyRange('1M', this)">1M</button>
                    <button class="time-btn" onclick="applyRange('3M', this)">3M</button>
                    <button class="time-btn" onclick="applyRange('6M', this)">6M</button>
                    <button class="time-btn" onclick="applyRange('1Y', this)">1Y</button>
                    <button class="time-btn" onclick="applyRange('3Y', this)">3Y</button>
                    <button class="time-btn" onclick="applyRange('5Y', this)">5Y</button>
                    <button class="time-btn" onclick="applyRange('ALL', this)">ALL</button>
                </div>
            </div>

            <div class="hud-legend" id="hud_legend">
                <span>日期: <span id="hud_date" class="hud-val">{latest_dt}</span></span>
                <span>收盘: <span id="hud_close" class="hud-val">${latest_close:.2f}</span></span>
                {'<span>开: <span id="hud_open" class="hud-val">-</span></span>' if has_ohlc else ''}
                {'<span>高: <span id="hud_high" class="hud-val">-</span></span>' if has_ohlc else ''}
                {'<span>低: <span id="hud_low" class="hud-val">-</span></span>' if has_ohlc else ''}
                {'<span>量: <span id="hud_vol" class="hud-val">-</span></span>' if has_volume else ''}
                <span class="c-ma20">MA20: <span id="hud_ma20" class="hud-val">-</span></span>
                <span class="c-ma50">MA50: <span id="hud_ma50" class="hud-val">-</span></span>
                <span class="c-ma200">MA200: <span id="hud_ma200" class="hud-val">-</span></span>
            </div>

            <div id="tv_container"></div>
        </div>

        <script>
            const container = document.getElementById('tv_container');
            const chart = LightweightCharts.createChart(container, {{
                width: container.clientWidth,
                height: {height},
                layout: {{
                    background: {{ type: 'solid', color: '#0b0e14' }},
                    textColor: '#94a3b8',
                    fontSize: 14, // Rule 11: 满足大字号规范
                }},
                grid: {{
                    vertLines: {{ color: 'rgba(255, 255, 255, 0.04)' }},
                    horzLines: {{ color: 'rgba(255, 255, 255, 0.04)' }},
                }},
                crosshair: {{
                    mode: LightweightCharts.CrosshairMode.Normal,
                }},
                rightPriceScale: {{
                    borderColor: 'rgba(255, 255, 255, 0.12)',
                    autoScale: true, // 【核心】：X 轴拖动/缩放时，Y 轴自动重新计算当前视口的 min/max！
                    scaleMargins: {{ top: 0.12, bottom: {'0.22' if has_volume else '0.08'} }},
                }},
                timeScale: {{
                    borderColor: 'rgba(255, 255, 255, 0.12)',
                    timeVisible: true,
                    secondsVisible: false,
                }},
            }});

            let mainSeries = null;
            const hasOhlc = {'true' if has_ohlc else 'false'};
            const candleData = {candles_json};
            const lineData = {line_json};

            if (hasOhlc) {{
                mainSeries = chart.addCandlestickSeries({{
                    upColor: '#10b981',
                    downColor: '#f43f5e',
                    borderVisible: true,
                    borderColor: '#10b981',
                    borderUpColor: '#10b981',
                    borderDownColor: '#f43f5e',
                    wickUpColor: '#10b981',
                    wickDownColor: '#f43f5e',
                }});
                mainSeries.setData(candleData);
            }} else {{
                mainSeries = chart.addAreaSeries({{
                    topColor: 'rgba(56, 189, 248, 0.4)',
                    bottomColor: 'rgba(56, 189, 248, 0.0)',
                    lineColor: '#38bdf8',
                    lineWidth: 2,
                }});
                mainSeries.setData(lineData);
            }}

            // 均线系统
            const ma20Series = chart.addLineSeries({{ color: '#f59e0b', lineWidth: 1.5, title: 'MA20' }});
            ma20Series.setData({ma20_json});

            const ma50Series = chart.addLineSeries({{ color: '#8b5cf6', lineWidth: 1.5, title: 'MA50' }});
            ma50Series.setData({ma50_json});

            const ma200Series = chart.addLineSeries({{ color: '#ef4444', lineWidth: 2, title: 'MA200' }});
            ma200Series.setData({ma200_json});

            // 成交量副图 (附着在底部)
            const hasVolume = {'true' if has_volume else 'false'};
            let volumeSeries = null;
            if (hasVolume) {{
                volumeSeries = chart.addHistogramSeries({{
                    priceFormat: {{ type: 'volume' }},
                    priceScaleId: '', // 独立于价格坐标轴
                }});
                volumeSeries.priceScale().applyOptions({{
                    scaleMargins: {{ top: 0.80, bottom: 0 }},
                }});
                volumeSeries.setData({volume_json});
            }}

            // 十字光标移动时动态更新 HUD
            chart.subscribeCrosshairMove(param => {{
                if (!param || !param.time || !param.seriesData) return;
                const dt = typeof param.time === 'object' ? `${{param.time.year}}-${{String(param.time.month).padStart(2,'0')}}-${{String(param.time.day).padStart(2,'0')}}` : param.time;
                document.getElementById('hud_date').innerText = dt;

                const mData = param.seriesData.get(mainSeries);
                if (mData) {{
                    if (hasOhlc) {{
                        const c = mData.close;
                        const o = mData.open;
                        const elClose = document.getElementById('hud_close');
                        elClose.innerText = '$' + c.toFixed(2);
                        elClose.className = 'hud-val ' + (c >= o ? 'c-green' : 'c-red');
                        document.getElementById('hud_open').innerText = '$' + o.toFixed(2);
                        document.getElementById('hud_high').innerText = '$' + mData.high.toFixed(2);
                        document.getElementById('hud_low').innerText = '$' + mData.low.toFixed(2);
                    }} else {{
                        document.getElementById('hud_close').innerText = '$' + mData.value.toFixed(2);
                    }}
                }}

                if (hasVolume && volumeSeries) {{
                    const vData = param.seriesData.get(volumeSeries);
                    if (vData) {{
                        const volVal = vData.value;
                        const fmtVol = volVal >= 1e6 ? (volVal / 1e6).toFixed(2) + 'M' : (volVal >= 1e3 ? (volVal / 1e3).toFixed(1) + 'K' : volVal);
                        document.getElementById('hud_vol').innerText = fmtVol;
                    }}
                }}

                const ma20D = param.seriesData.get(ma20Series);
                if (ma20D) document.getElementById('hud_ma20').innerText = '$' + ma20D.value.toFixed(2);
                const ma50D = param.seriesData.get(ma50Series);
                if (ma50D) document.getElementById('hud_ma50').innerText = '$' + ma50D.value.toFixed(2);
                const ma200D = param.seriesData.get(ma200Series);
                if (ma200D) document.getElementById('hud_ma200').innerText = '$' + ma200D.value.toFixed(2);
            }});

            // 时间范围按钮逻辑 (毫秒级视口自适应，零后端网络开销)
            function applyRange(range, btnElement) {{
                document.querySelectorAll('.time-btn').forEach(b => {{
                    if (b.innerText === range || b === btnElement) {{
                        b.classList.add('active');
                    }} else {{
                        b.classList.remove('active');
                    }}
                }});

                if (range === 'ALL') {{
                    chart.timeScale().fitContent();
                    return;
                }}

                const allData = hasOhlc ? candleData : lineData;
                if (!allData || allData.length === 0) return;
                const lastItem = allData[allData.length - 1];
                const lastDate = new Date(lastItem.time);

                let fromDate = new Date(lastDate);
                if (range === '1M') fromDate.setMonth(fromDate.getMonth() - 1);
                else if (range === '3M') fromDate.setMonth(fromDate.getMonth() - 3);
                else if (range === '6M') fromDate.setMonth(fromDate.getMonth() - 6);
                else if (range === '1Y') fromDate.setFullYear(fromDate.getFullYear() - 1);
                else if (range === '3Y') fromDate.setFullYear(fromDate.getFullYear() - 3);
                else if (range === '5Y') fromDate.setFullYear(fromDate.getFullYear() - 5);

                const fromStr = fromDate.toISOString().split('T')[0];
                chart.timeScale().setVisibleRange({{
                    from: fromStr,
                    to: lastItem.time,
                }});
            }}

            // 初始化视口范围 (自动适配传入的 timeframe，默认展示全量历史)
            applyRange('{timeframe if timeframe in ["1M", "3M", "6M", "1Y", "3Y", "5Y", "ALL"] else "ALL"}');

            window.addEventListener('resize', () => {{
                chart.applyOptions({{ width: container.clientWidth }});
            }});
        </script>
    </body>
    </html>
    """

    components.html(html_code, height=height + 15, scrolling=False)
    return True


# ------------------------------------------------------------------
# 2. Apache ECharts 宏观时间序列通用自适应组件
# ------------------------------------------------------------------
def render_echarts_macro_chart(
    df: pd.DataFrame,
    date_col: str,
    series_configs: list,
    title: str,
    subtitle: str = "",
    yaxis_title: str = "",
    y2axis_title: str = "",
    height: int = 500,
    zero_line: bool = False,
    mark_lines: list = None,
    mark_areas: list = None,
    y_format: str = "{value}",
    y2_format: str = "{value}",
    timeframe: str = "ALL",
    initial_zoom_pct: int = 50
):
    t = get_chart_theme_tokens()
    """
    使用 Apache ECharts 渲染高品质宏观时间序列图
    特性:
    - 视口 X 轴缩放/拖动时，Y 轴自动自适应 (scale: true + dataZoom 联动)
    - 底部可视化拖动条 (slider) + 鼠标滚轮/触控板自由缩放 (inside)
    - 支持多序列叠加、双 Y 轴自适应、面积渐变透明度、零轴分界虚线、阈值警戒线与健康区间填充
    - 满足 Rule 11 大字号标准 (14px+) 与暗黑/白天模式双向自适应
    """
    if df is None or df.empty:
        st.warning(f"【{title}】暂无有效宏观数据。")
        return False

    df_clean = df.copy()
    if date_col not in df_clean.columns:
        df_clean = df_clean.reset_index()
        date_col = df_clean.columns[0]

    df_clean[date_col] = pd.to_datetime(df_clean[date_col])
    df_clean = df_clean.sort_values(date_col).dropna(subset=[date_col]).copy()

    # 纯前端矢量 Canvas 引擎：将全部可用历史数据传入前端（5年/10年/30年）
    # 用户在前端点击 1M/3M/6M/1Y/3Y/5Y/10Y/ALL 或滚轮缩放时，可无缝平滑查看全部历史，绝不截断丢弃历史数据
    # 初始视口范围由 timeframe 参数驱动前端 dataZoom 毫秒级自适应
    dates = df_clean[date_col].dt.strftime('%Y-%m-%d').tolist()

    # 构建各个系列的数据列表与配置
    echarts_series = []
    legend_names = []

    for sc in series_configs:
        col_name = sc.get('col')
        if col_name not in df_clean.columns:
            continue
        s_name = sc.get('name', col_name)
        legend_names.append(s_name)
        color = sc.get('color', '#38bdf8')
        use_area = sc.get('area', False)
        line_type = sc.get('line_type', 'solid')
        width = sc.get('width', 2.5)

        # 替换 NaN 为 None (JSON 序列化为 null)
        raw_vals = df_clean[col_name].replace({np.nan: None}).tolist()
        clean_vals = [round(float(v), 4) if (v is not None and not pd.isna(v)) else None for v in raw_vals]

        s_obj = {
            "name": s_name,
            "type": "line",
            "smooth": True,
            "showSymbol": False,
            "lineStyle": {"width": width, "color": color, "type": line_type},
            "data": clean_vals,
        }

        if sc.get("y_axis_index") is not None:
            s_obj["yAxisIndex"] = sc.get("y_axis_index")

        if use_area:
            s_obj["areaStyle"] = {
                "color": {
                    "type": "linear",
                    "x": 0, "y": 0, "x2": 0, "y2": 1,
                    "colorStops": [
                        {"offset": 0, "color": color.replace(')', ', 0.35)').replace('rgb', 'rgba') if 'rgb' in color else (color + '55' if color.startswith('#') else 'rgba(56, 189, 248, 0.35)')},
                        {"offset": 1, "color": "rgba(11, 14, 20, 0.0)"}
                    ]
                }
            }

        # 警戒线支持：针对特定系列的 sc.get('mark_lines') 或全局首系列的 mark_lines
        series_mls = sc.get('mark_lines') or (mark_lines if len(echarts_series) == 0 else None)
        if series_mls:
            ml_data = []
            for ml in series_mls:
                ml_data.append({
                    "yAxis": ml.get("yAxis", 0),
                    "lineStyle": {"color": ml.get("color", "#f43f5e"), "type": ml.get("type", "dashed"), "width": ml.get("width", 1.5)},
                    "label": {"formatter": ml.get("label", ""), "color": ml.get("color", "#f43f5e"), "fontSize": 12, "position": ml.get("position", "insideStartTop")}
                })
            s_obj["markLine"] = {
                "silent": True,
                "symbol": "none",
                "data": ml_data
            }
        elif zero_line and len(echarts_series) == 0:
            s_obj["markLine"] = {
                "silent": True,
                "symbol": "none",
                "label": {"position": "insideStartTop", "formatter": "0 轴基准线", "color": "#f43f5e", "fontSize": 12},
                "lineStyle": {"color": "#f43f5e", "type": "dashed", "width": 1.5},
                "data": [{"yAxis": 0}]
            }

        # 区域背景填充 (markArea)
        if mark_areas and len(echarts_series) == 0:
            ma_data = []
            for ma in mark_areas:
                ma_data.append([
                    {
                        "yAxis": ma.get("y0", 0),
                        "itemStyle": {"color": ma.get("color", "rgba(34, 197, 94, 0.12)")},
                        "label": {"position": "insideTopLeft", "formatter": ma.get("label", ""), "color": ma.get("label_color", "#10b981"), "fontSize": 13}
                    },
                    {
                        "yAxis": ma.get("y1", 0)
                    }
                ])
            s_obj["markArea"] = {
                "silent": True,
                "data": ma_data
            }

        echarts_series.append(s_obj)

    if not echarts_series:
        st.warning(f"【{title}】未匹配到指定指标列。")
        return False

    dates_json = json.dumps(dates)
    series_json = json.dumps(echarts_series)
    legend_json = json.dumps(legend_names)

    # 坐标轴配置 (单轴 vs 双轴自适应)
    if y2axis_title:
        yaxis_config = [
            {
                "type": "value",
                "name": yaxis_title,
                "nameTextStyle": {"color": t["axis_label"], "fontSize": 12, "padding": [0, 0, 4, 0]},
                "scale": True,
                "axisLine": {"show": False},
                "splitLine": {"lineStyle": {"color": t["split_line"]}},
                "axisLabel": {
                    "color": t["axis_label"],
                    "fontSize": 14,
                    "formatter": y_format
                }
            },
            {
                "type": "value",
                "name": y2axis_title,
                "nameTextStyle": {"color": t["axis_label"], "fontSize": 12, "padding": [0, 0, 4, 0]},
                "scale": True,
                "axisLine": {"show": False},
                "splitLine": {"show": False},
                "axisLabel": {
                    "color": t["axis_label"],
                    "fontSize": 14,
                    "formatter": y2_format
                }
            }
        ]
    else:
        yaxis_config = {
            "type": "value",
            "name": yaxis_title,
            "nameTextStyle": {"color": t["axis_label"], "fontSize": 12, "padding": [0, 0, 4, 0]},
            "scale": True,
            "axisLine": {"show": False},
            "splitLine": {"lineStyle": {"color": t["split_line"]}},
            "axisLabel": {
                "color": t["axis_label"],
                "fontSize": 14,
                "formatter": y_format
            }
        }
    yaxis_json = json.dumps(yaxis_config)

    # 初始显示比例：默认显示近期 40%~60% 的数据，方便观察局部细节
    default_start = 100 - initial_zoom_pct if (initial_zoom_pct and initial_zoom_pct < 100) else 0

    html_code = f"""
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <!-- 引入 Apache ECharts -->
        <script src="https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"></script>
        <style>
            * {{ box-sizing: border-box; }}
            body {{
                margin: 0;
                padding: 0;
                background-color: {t["body_bg"]};
                color: {t["text_color"]};
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
                overflow: hidden;
            }}
            #chart_container {{
                width: 100%;
                height: {height}px;
                background: {t["card_bg"]};
                border: 1px solid {t["border_color"]};
                border-radius: 12px;
                box-shadow: {t["box_shadow"]};
                position: relative;
                display: flex;
                flex-direction: column;
            }}
            .chart-header {{
                display: flex;
                justify-content: space-between;
                align-items: flex-start;
                padding: 12px 18px 4px 18px;
                gap: 12px;
                flex-shrink: 0;
            }}
            .chart-title-area {{
                flex: 1;
                min-width: 0;
            }}
            .chart-title {{
                font-size: 17px;
                font-weight: 700;
                color: {t["title_color"]};
                line-height: 1.35;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
            }}
            .chart-subtitle {{
                font-size: 13px;
                color: {t["subtitle_color"]};
                margin-top: 2px;
                line-height: 1.3;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
            }}
            .time-buttons {{
                display: flex;
                gap: 3px;
                background: rgba(30, 41, 59, 0.7);
                backdrop-filter: blur(8px);
                padding: 3px 5px;
                border-radius: 8px;
                border: 1px solid rgba(255, 255, 255, 0.08);
                flex-shrink: 0;
            }}
            .time-btn {{
                background: transparent;
                border: none;
                color: #94a3b8;
                font-size: 12px;
                font-weight: 600;
                padding: 3px 7px;
                border-radius: 4px;
                cursor: pointer;
                transition: all 0.15s ease;
            }}
            .time-btn:hover {{
                color: #ffffff;
                background: rgba(255, 255, 255, 0.12);
            }}
            .time-btn.active {{
                color: #38bdf8;
                background: rgba(56, 189, 248, 0.2);
            }}
            #ec_main {{
                width: 100%;
                flex: 1;
                min-height: 0;
            }}
        </style>
    </head>
    <body>
        <div id="chart_container">
            <div class="chart-header">
                <div class="chart-title-area">
                    <div class="chart-title">{title}</div>
                    {f'<div class="chart-subtitle">{subtitle}</div>' if subtitle else ''}
                </div>
                <div class="time-buttons">
                    <button class="time-btn" onclick="applyMacroRange('1M', this)">1M</button>
                    <button class="time-btn" onclick="applyMacroRange('3M', this)">3M</button>
                    <button class="time-btn" onclick="applyMacroRange('6M', this)">6M</button>
                    <button class="time-btn" onclick="applyMacroRange('1Y', this)">1Y</button>
                    <button class="time-btn" onclick="applyMacroRange('3Y', this)">3Y</button>
                    <button class="time-btn" onclick="applyMacroRange('5Y', this)">5Y</button>
                    <button class="time-btn" onclick="applyMacroRange('10Y', this)">10Y</button>
                    <button class="time-btn" onclick="applyMacroRange('ALL', this)">ALL</button>
                </div>
            </div>
            <div id="ec_main"></div>
        </div>

        <script>
            const chartDom = document.getElementById('ec_main');
            const myChart = echarts.init(chartDom, '{t["echarts_theme"]}');

            const option = {{
                backgroundColor: '{t["card_bg"]}',
                animationDuration: 400,
                tooltip: {{
                    trigger: 'axis',
                    backgroundColor: '{t["tooltip_bg"]}',
                    borderColor: '{t["tooltip_border"]}',
                    borderWidth: 1,
                    textStyle: {{ color: '{t["tooltip_text"]}', fontSize: 14 }}, // Rule 11
                    axisPointer: {{
                        type: 'cross',
                        label: {{ backgroundColor: '{t["tooltip_border"]}' }},
                        lineStyle: {{ color: '{t["axis_line"]}', type: 'dashed' }}
                    }}
                }},
                legend: {{
                    data: {legend_json},
                    top: '6px',
                    left: '130px',
                    right: '130px',
                    type: 'scroll',
                    textStyle: {{ color: '{t["legend_text"]}', fontSize: 13 }},
                    itemGap: 16,
                }},
                grid: {{
                    left: '55px',
                    right: '55px',
                    top: '46px',
                    bottom: '36px',
                    containLabel: true,
                }},
                xAxis: {{
                    type: 'category',
                    data: {dates_json},
                    boundaryGap: false,
                    axisLine: {{ lineStyle: {{ color: '{t["axis_line"]}' }} }},
                    axisLabel: {{ color: '{t["axis_label"]}', fontSize: 14 }},
                    splitLine: {{ show: false }}
                }},
                yAxis: {yaxis_json},
                dataZoom: [
                    // 1. 鼠标滚轮/触控板平滑缩放
                    {{
                        type: 'inside',
                        start: {default_start},
                        end: 100,
                    }},
                    // 2. 底部可视化拖动条
                    {{
                        type: 'slider',
                        start: {default_start},
                        end: 100,
                        bottom: 8,
                        height: 24,
                        borderColor: '{t["datazoom_border"]}',
                        backgroundColor: '{t["datazoom_bg"]}',
                        fillerColor: '{t["datazoom_filler"]}',
                        handleStyle: {{ color: '{t["datazoom_handle"]}' }},
                        textStyle: {{ color: '{t["axis_label"]}', fontSize: 12 }},
                        dataBackground: {{
                            lineStyle: {{ color: '{t["datazoom_handle"]}' }},
                            areaStyle: {{ color: '{t["datazoom_filler"]}' }}
                        }}
                    }}
                ],
                series: {series_json}
            }};

            myChart.setOption(option);

            const allDates = {dates_json};

            function applyMacroRange(range, btnElement) {{
                document.querySelectorAll('.time-btn').forEach(b => {{
                    if (b.innerText === range || b === btnElement) {{
                        b.classList.add('active');
                    }} else {{
                        b.classList.remove('active');
                    }}
                }});

                if (range === 'ALL' || !allDates || allDates.length === 0) {{
                    myChart.dispatchAction({{
                        type: 'dataZoom',
                        start: 0,
                        end: 100
                    }});
                    return;
                }}

                const lastDateStr = allDates[allDates.length - 1];
                const lastDate = new Date(lastDateStr);

                let fromDate = new Date(lastDate);
                if (range === '1M') fromDate.setMonth(fromDate.getMonth() - 1);
                else if (range === '3M') fromDate.setMonth(fromDate.getMonth() - 3);
                else if (range === '6M') fromDate.setMonth(fromDate.getMonth() - 6);
                else if (range === '1Y') fromDate.setFullYear(fromDate.getFullYear() - 1);
                else if (range === '3Y') fromDate.setFullYear(fromDate.getFullYear() - 3);
                else if (range === '5Y') fromDate.setFullYear(fromDate.getFullYear() - 5);
                else if (range === '10Y') fromDate.setFullYear(fromDate.getFullYear() - 10);

                const fromDateStr = fromDate.toISOString().split('T')[0];

                let startIdx = 0;
                for (let i = 0; i < allDates.length; i++) {{
                    if (allDates[i] >= fromDateStr) {{
                        startIdx = i;
                        break;
                    }}
                }}

                const startPct = Math.max(0, Math.min(100, (startIdx / Math.max(1, allDates.length - 1)) * 100));
                myChart.dispatchAction({{
                    type: 'dataZoom',
                    start: startPct,
                    end: 100
                }});
            }}

            // 初始化按传入的全局 timeframe 设置视口缩放与高亮按钮
            const initTf = '{timeframe if timeframe in ["1M", "3M", "6M", "1Y", "3Y", "5Y", "10Y", "ALL"] else "5Y"}';
            applyMacroRange(initTf);

            window.addEventListener('resize', () => myChart.resize());
        </script>
    </body>
    </html>
    """

    components.html(html_code, height=height + 15, scrolling=False)
    return True


# ------------------------------------------------------------------
# 3. 针对特定宏观图表的专用封装函数
# ------------------------------------------------------------------
def render_echarts_yield_spreads(df_spreads: pd.DataFrame, timeframe: str = "ALL", height: int = 480):
    """
    专门渲染 10Y-2Y 与 10Y-3M 国债期限利差 (ECharts 自适应版本)
    """
    date_col = 'date' if 'date' in df_spreads.columns else df_spreads.columns[0]
    series_configs = [
        {"col": "Spread_10Y2Y", "name": "10Y-2Y 期限利差 (%)", "color": "#38bdf8", "area": True, "width": 2.5},
        {"col": "Spread_10Y3M", "name": "10Y-3M 期限利差 (%)", "color": "#f43f5e", "line_type": "dashed", "width": 1.8},
    ]
    return render_echarts_macro_chart(
        df=df_spreads,
        date_col=date_col,
        series_configs=series_configs,
        title="10Y-2Y & 10Y-3M 美债期限利差对比",
        subtitle="倒挂与解挂预警 · 10Y-2Y 与 10Y-3M 深度对比",
        yaxis_title="利差 (%)",
        height=height,
        zero_line=True,
        y_format="{value} %",
        timeframe=timeframe,
        initial_zoom_pct=40
    )


def render_echarts_net_liquidity(df_liq: pd.DataFrame, timeframe: str = "ALL", height: int = 480):
    """
    专门渲染美联储净流动性与银行准备金 (ECharts 自适应版本)
    """
    date_col = 'date' if 'date' in df_liq.columns else df_liq.columns[0]
    series_configs = [
        {"col": "Fed_Net_Liquidity_Tn", "name": "美联储净流动性 (万亿美元)", "color": "#10b981", "area": True, "width": 2.5},
        {"col": "Bank_Reserves_Tn", "name": "银行准备金余额 (万亿美元)", "color": "#a855f7", "width": 2.0},
    ]
    return render_echarts_macro_chart(
        df=df_liq,
        date_col=date_col,
        series_configs=series_configs,
        title="美联储净流动性 & 银行准备金余额",
        subtitle="全球宏观流动性水龙头 · 资产负债表与准备金",
        yaxis_title="万亿美元 (Trillion USD)",
        height=height,
        zero_line=False,
        y_format="{value} T",
        timeframe=timeframe,
        initial_zoom_pct=40
    )


# ------------------------------------------------------------------
# 4. 美国国债收益率曲线 (Yield Curve) 5 条基准演变线对比组件
# ------------------------------------------------------------------
def render_echarts_treasury_curve(df_long: pd.DataFrame, height: int = 500):
    """
    使用 Apache ECharts 渲染 5 曲线对比的美国国债收益率曲线形态演变图 (Yield Curve)
    - 核心特性：横坐标基于真实期限时间长短 (Proportional Maturity Axis, 0 到 30年)，彻底解决等距失真问题
    - 严格保留全部 5 条核心周期基准演变线: 最新、1个月前、3个月前、6个月前、年初至今/最早
    - 支持毫秒级十字准星对准任意期限、深度自适应深色/日间双模式
    """
    t = get_chart_theme_tokens()
    if df_long is None or df_long.empty:
        st.warning("暂无国债收益率曲线数据。")
        return False

    df = df_long.copy()
    if 'Date' not in df.columns:
        return False
    df['Date'] = pd.to_datetime(df['Date'])
    latest_date = df['Date'].max()
    avail = sorted(df['Date'].unique())

    def _find_nearest_date(target):
        past_dates = [d for d in avail if d <= target]
        return max(past_dates) if past_dates else min(avail)

    target_defs = [
        ("最新", latest_date, "#38bdf8", 3.5, "solid", 8),
        ("1个月前", _find_nearest_date(latest_date - pd.DateOffset(months=1)), "#10b981", 2.2, "solid", 6),
        ("3个月前", _find_nearest_date(latest_date - pd.DateOffset(months=3)), "#f59e0b", 2.0, "dashed", 5),
        ("6个月前", _find_nearest_date(latest_date - pd.DateOffset(months=6)), "#a855f7", 2.0, "dashed", 5),
        ("年初至今", avail[0], "#f43f5e", 2.0, "dotted", 5)
    ]

    seen_dates = set()
    unique_targets = []
    for label, dt, color, width, line_type, symbol_size in target_defs:
        dt_val = pd.Timestamp(dt)
        if dt_val not in seen_dates:
            seen_dates.add(dt_val)
            unique_targets.append((label, dt_val, color, width, line_type, symbol_size))

    # 标准期限对应的时间长短（年数）
    mat_years_map = {
        '1 Mo': round(1/12, 4),   # ~0.0833
        '2 Mo': round(2/12, 4),   # ~0.1667
        '3 Mo': 0.25,
        '4 Mo': round(4/12, 4),   # ~0.3333
        '6 Mo': 0.5,
        '1 Yr': 1.0,
        '2 Yr': 2.0,
        '3 Yr': 3.0,
        '5 Yr': 5.0,
        '7 Yr': 7.0,
        '10 Yr': 10.0,
        '20 Yr': 20.0,
        '30 Yr': 30.0
    }
    mat_order = list(mat_years_map.keys())
    existing_mats = df['Maturity_Label'].unique() if 'Maturity_Label' in df.columns else []
    categories = [m for m in mat_order if m in existing_mats]
    if not categories:
        categories = mat_order

    series_list = []
    legend_data = []

    for label, dt_val, color, width, line_type, sym_size in unique_targets:
        dt_str = dt_val.strftime('%Y-%m-%d')
        series_name = f"{label} ({dt_str})"
        legend_data.append(series_name)

        sub = df[df['Date'] == dt_val].set_index('Maturity_Label')
        points = []
        for m in categories:
            if m in sub.index:
                val = sub.loc[m, 'Yield']
                if pd.notna(val):
                    yr_val = mat_years_map.get(m, 0.0)
                    points.append([yr_val, round(float(val), 2), m])

        series_list.append({
            "name": series_name,
            "type": "line",
            "smooth": 0.28,
            "data": points,
            "symbol": "circle",
            "symbolSize": sym_size,
            "lineStyle": {"width": width, "color": color, "type": line_type},
            "itemStyle": {"color": color}
        })

    series_json = json.dumps(series_list)
    legend_json = json.dumps(legend_data)

    html_code = f"""
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <script src="https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"></script>
        <style>
            * {{ box-sizing: border-box; }}
            body {{
                margin: 0;
                padding: 0;
                background-color: {t["body_bg"]};
                color: {t["text_color"]};
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
                overflow: hidden;
            }}
            .chart-card {{
                width: 100%;
                height: {height}px;
                background: {t["card_bg"]};
                border: 1px solid {t["border_color"]};
                border-radius: 12px;
                box-shadow: {t["box_shadow"]};
                position: relative;
                display: flex;
                flex-direction: column;
            }}
            .chart-header {{
                display: flex;
                justify-content: space-between;
                align-items: flex-start;
                padding: 12px 18px 4px 18px;
                gap: 12px;
                flex-shrink: 0;
            }}
            .chart-title-area {{
                flex: 1;
                min-width: 0;
            }}
            .chart-title {{
                font-size: 17px;
                font-weight: 700;
                color: {t["title_color"]};
                line-height: 1.35;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
            }}
            .chart-subtitle {{
                font-size: 13px;
                color: {t["subtitle_color"]};
                margin-top: 2px;
                line-height: 1.3;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
            }}
            .chart-body {{
                width: 100%;
                flex: 1;
                min-height: 0;
            }}
        </style>
    </head>
    <body>
        <div class="chart-card">
            <div class="chart-header">
                <div class="chart-title-area">
                    <div class="chart-title">U.S. Treasury Yield Curve 5条曲线演变对比 (真实时间长短轴)</div>
                    <div class="chart-subtitle">横轴按真实期限长短比例分布 (1M 到 30Y) · 涵盖最新、1M前、3M前、6M前及年初至今</div>
                </div>
            </div>
            <div id="yc_chart" class="chart-body"></div>
        </div>
        <script>
            const chart = echarts.init(document.getElementById('yc_chart'), '{t["echarts_theme"]}');
            const option = {{
                backgroundColor: '{t["card_bg"]}',
                tooltip: {{
                    trigger: 'axis',
                    axisPointer: {{
                        type: 'cross',
                        lineStyle: {{ color: '{t["axis_line"]}', width: 1, type: 'dashed' }}
                    }},
                    backgroundColor: '{t["tooltip_bg"]}',
                    borderColor: '{t["tooltip_border"]}',
                    borderWidth: 1,
                    textStyle: {{ color: '{t["tooltip_text"]}', fontSize: 14 }},
                    formatter: function(params) {{
                        if (!params || params.length === 0) return '';
                        const xVal = params[0].value[0];
                        const matLabels = {{
                            0.0833: '1 Mo', 0.1667: '2 Mo', 0.25: '3 Mo', 0.3333: '4 Mo', 0.5: '6 Mo',
                            1.0: '1 Yr', 2.0: '2 Yr', 3.0: '3 Yr', 5.0: '5 Yr', 7.0: '7 Yr',
                            10.0: '10 Yr', 20.0: '20 Yr', 30.0: '30 Yr'
                        }};
                        let closestMat = '';
                        let minDiff = 999;
                        for (const [k, v] of Object.entries(matLabels)) {{
                            const diff = Math.abs(parseFloat(k) - xVal);
                            if (diff < minDiff) {{ minDiff = diff; closestMat = v; }}
                        }}
                        const timeSpanStr = xVal >= 1 ? xVal.toFixed(1) + ' 年' : (xVal * 12).toFixed(0) + ' 个月';
                        let html = '<div style="font-weight:700;margin-bottom:4px;border-bottom:1px solid rgba(255,255,255,0.15);padding-bottom:3px;">期限: ' + closestMat + ' (' + timeSpanStr + ')</div>';
                        params.forEach(p => {{
                            const yVal = p.value[1];
                            html += '<div style="display:flex;justify-content:space-between;gap:12px;"><span>' + p.marker + ' ' + p.seriesName + '</span><b>' + (yVal != null ? Number(yVal).toFixed(2) + ' %' : '-') + '</b></div>';
                        }});
                        return html;
                    }}
                }},
                legend: {{
                    data: {legend_json},
                    top: '6px',
                    left: 'center',
                    type: 'scroll',
                    textStyle: {{ color: '{t["legend_text"]}', fontSize: 13 }},
                    itemGap: 16
                }},
                grid: {{ left: '4%', right: '5%', top: '46px', bottom: '10%', containLabel: true }},
                xAxis: {{
                    type: 'value',
                    name: '期限 (年数)',
                    nameLocation: 'end',
                    nameTextStyle: {{ color: '{t["axis_label"]}', fontSize: 14, padding: [0, 0, 0, 8] }},
                    min: 0,
                    max: 30,
                    interval: 5,
                    axisLine: {{ lineStyle: {{ color: '{t["axis_line"]}' }} }},
                    axisLabel: {{
                        color: '{t["axis_label"]}',
                        fontSize: 14,
                        fontWeight: 600,
                        formatter: function(val) {{
                            if (val === 0) return '0';
                            return val + ' Yr';
                        }}
                    }},
                    splitLine: {{ lineStyle: {{ color: '{t["split_line"]}' }} }}
                }},
                yAxis: {{
                    type: 'value',
                    name: '收益率 (%)',
                    nameTextStyle: {{ color: '{t["axis_label"]}', fontSize: 14, padding: [0, 0, 6, 0] }},
                    scale: true,
                    axisLine: {{ show: false }},
                    splitLine: {{ lineStyle: {{ color: '{t["split_line"]}' }} }},
                    axisLabel: {{ color: '{t["axis_label"]}', fontSize: 14, formatter: '{{value}} %' }}
                }},
                series: {series_json}
            }};
            chart.setOption(option);
            window.addEventListener('resize', () => chart.resize());
        </script>
    </body>
    </html>
    """
    components.html(html_code, height=height + 15, scrolling=False)
    return True


# ------------------------------------------------------------------
# 5. VIX、MOVE 与美元指数 DXY 的 ECharts 封装
# ------------------------------------------------------------------
def render_echarts_vix_chart(df_vix: pd.DataFrame, timeframe: str = "ALL", height: int = 480):
    """
    使用 ECharts 渲染 VIX 股市恐慌指数 (含 20/30 恐慌警戒线，自适应 Y 轴)
    """
    date_col = 'date' if 'date' in df_vix.columns else df_vix.columns[0]
    series_configs = [
        {"col": "VIX", "name": "CBOE VIX 恐慌指数", "color": "#f59e0b", "area": True, "width": 2.2},
    ]
    return render_echarts_macro_chart(
        df=df_vix,
        date_col=date_col,
        series_configs=series_configs,
        title="CBOE 标普500 波动率指数 (VIX)",
        subtitle="期权隐含波动率 · 20点中枢 / 30点恐慌警戒线",
        yaxis_title="点位",
        height=height,
        zero_line=False,
        timeframe=timeframe,
        initial_zoom_pct=40
    )


def render_echarts_move_chart(df_move: pd.DataFrame, timeframe: str = "ALL", height: int = 480):
    """
    使用 ECharts 渲染 ICE BofA MOVE 债市波动率指数 (全球金融抵押品母恐慌指标)
    """
    date_col = 'date' if 'date' in df_move.columns else df_move.columns[0]
    val_col = 'MOVE' if 'MOVE' in df_move.columns else df_move.columns[1]
    series_configs = [
        {"col": val_col, "name": "ICE BofA MOVE 债市波动率", "color": "#ec4899", "area": True, "width": 2.2},
    ]
    return render_echarts_macro_chart(
        df=df_move,
        date_col=date_col,
        series_configs=series_configs,
        title="ICE BofA MOVE 债市波动率指数 (母恐慌指标)",
        subtitle="美债期权隐含波动率 · 120警戒线",
        yaxis_title="点位",
        height=height,
        zero_line=False,
        timeframe=timeframe,
        initial_zoom_pct=40
    )


def render_echarts_dxy_chart(df_dxy: pd.DataFrame, timeframe: str = "ALL", height: int = 480):
    """
    使用 ECharts 渲染美元指数 (DXY)
    """
    date_col = 'date' if 'date' in df_dxy.columns else df_dxy.columns[0]
    val_col = 'DXY' if 'DXY' in df_dxy.columns else df_dxy.columns[1]
    series_configs = [
        {"col": val_col, "name": "美元指数 (DXY)", "color": "#38bdf8", "area": True, "width": 2.2},
    ]
    return render_echarts_macro_chart(
        df=df_dxy,
        date_col=date_col,
        series_configs=series_configs,
        title="Nominal Broad U.S. Dollar Index (美元指数)",
        subtitle="全球宏观货币锚 · 衡量美元对主要贸易伙伴汇率",
        yaxis_title="点位",
        height=height,
        zero_line=False,
        timeframe=timeframe,
        initial_zoom_pct=40
    )


# ------------------------------------------------------------------
# 6. PE / PS Band 动态估值通道组件 (ECharts 估值分位透视带)
# ------------------------------------------------------------------
def render_echarts_pe_ps_band(
    df_stock: pd.DataFrame,
    symbol: str,
    current_eps: float = None,
    current_rev_per_share: float = None,
    timeframe: str = "3Y",
    height: int = 540
):
    """
    使用 Apache ECharts 渲染高品质 PE / PS Band 动态估值通道
    - 5~7 条估值倍数线半透明色阶填充
    - 真实股价主线高亮显示，毫秒级 Y 轴动态缩放
    - 鼠标悬停纵向多指标透视 (当前折溢价与乘数位置)
    - 深度自适应全局主题模式 (Dark Mode / Bright Mode)
    """
    t = get_chart_theme_tokens()
    if df_stock is None or df_stock.empty or 'Close' not in df_stock.columns:
        st.warning(f"标的 {symbol} 暂无有效收盘价数据以绘制估值带。")
        return False

    df = df_stock.copy()
    if 'Date' not in df.columns:
        if isinstance(df.index, pd.DatetimeIndex):
            df = df.reset_index()
            df.rename(columns={'index': 'Date'}, inplace=True)
        elif 'date' in df.columns:
            df.rename(columns={'date': 'Date'}, inplace=True)

    df['Date'] = pd.to_datetime(df['Date'])
    df = filter_by_timeframe(df, 'Date', timeframe)
    if df.empty:
        st.warning(f"选定时间范围 [{timeframe}] 内无估值数据。")
        return False

    is_ps_mode = (current_rev_per_share is not None and current_rev_per_share > 0)
    is_pe_mode = (current_eps is not None and current_eps > 0)
    if not is_pe_mode and not is_ps_mode:
        st.info(f"标的 {symbol} 的 EPS 或 每股营收 缺失，无法构建估值通道。")
        return False

    val_type = "PS" if is_ps_mode else "PE"
    base_metric = current_rev_per_share if is_ps_mode else current_eps
    multiples = [1, 2, 4, 8, 16, 24, 32] if is_ps_mode else [5, 10, 20, 30, 45, 60, 80]
    colors = ['#8b5cf6', '#3b82f6', '#06b6d4', '#10b981', '#eab308', '#f97316', '#ef4444']

    dates = df['Date'].dt.strftime('%Y-%m-%d').tolist()
    close_prices = [round(float(p), 2) for p in df['Close']]

    series_list = []
    legend_data = []

    # 1. 添加各个倍数通道线
    for mult, color in zip(multiples, colors):
        band_price = round(float(base_metric * mult), 2)
        s_name = f"{val_type} {mult}x (${band_price:.1f})"
        legend_data.append(s_name)
        series_list.append({
            "name": s_name,
            "type": "line",
            "data": [band_price] * len(dates),
            "symbol": "none",
            "lineStyle": {"width": 1.5, "type": "dashed", "color": color},
            "itemStyle": {"color": color}
        })

    # 2. 添加实际股价主线 (置顶加粗高亮)
    stock_line_name = f"{symbol} 真实股价"
    legend_data.insert(0, stock_line_name)
    series_list.insert(0, {
        "name": stock_line_name,
        "type": "line",
        "data": close_prices,
        "symbol": "circle",
        "symbolSize": 5,
        "lineStyle": {"width": 3.0, "color": t["stock_line_color"], "shadowColor": "rgba(56, 189, 248, 0.4)", "shadowBlur": 8},
        "itemStyle": {"color": t["stock_line_color"]},
        "z": 10
    })

    dates_json = json.dumps(dates)
    series_json = json.dumps(series_list)
    legend_json = json.dumps(legend_data)

    html_code = f"""
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <script src="https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"></script>
        <style>
            * {{ box-sizing: border-box; }}
            body {{
                margin: 0;
                padding: 0;
                background-color: {t["body_bg"]};
                color: {t["text_color"]};
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
                overflow: hidden;
            }}
            .chart-card {{
                width: 100%;
                height: {height}px;
                background: {t["card_bg"]};
                border: 1px solid {t["border_color"]};
                border-radius: 12px;
                box-shadow: {t["box_shadow"]};
                position: relative;
                display: flex;
                flex-direction: column;
            }}
            .chart-header {{
                display: flex;
                justify-content: space-between;
                align-items: flex-start;
                padding: 12px 18px 4px 18px;
                gap: 12px;
                flex-shrink: 0;
            }}
            .chart-title-area {{
                flex: 1;
                min-width: 0;
            }}
            .chart-title {{
                font-size: 17px;
                font-weight: 700;
                color: {t["title_color"]};
                line-height: 1.35;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
            }}
            .chart-subtitle {{
                font-size: 13px;
                color: {t["subtitle_color"]};
                margin-top: 2px;
                line-height: 1.3;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
            }}
            .chart-body {{
                width: 100%;
                flex: 1;
                min-height: 0;
            }}
        </style>
    </head>
    <body>
        <div class="chart-card">
            <div class="chart-header">
                <div class="chart-title-area">
                    <div class="chart-title">{symbol} {val_type} 动态估值通道 ({val_type} Band)</div>
                    <div class="chart-subtitle">基准指标: {val_type} TTM每股数值 ${base_metric:.2f}</div>
                </div>
            </div>
            <div id="band_chart" class="chart-body"></div>
        </div>
        <script>
            const chart = echarts.init(document.getElementById('band_chart'), '{t["echarts_theme"]}');
            const option = {{
                backgroundColor: '{t["card_bg"]}',
                tooltip: {{
                    trigger: 'axis',
                    backgroundColor: '{t["tooltip_bg"]}',
                    borderColor: '{t["tooltip_border"]}',
                    borderWidth: 1,
                    textStyle: {{ color: '{t["tooltip_text"]}', fontSize: 14 }},
                    valueFormatter: (val) => val != null ? '$' + Number(val).toFixed(2) : '-'
                }},
                legend: {{
                    data: {legend_json},
                    top: '6px',
                    left: 'center',
                    type: 'scroll',
                    textStyle: {{ color: '{t["legend_text"]}', fontSize: 13 }},
                    itemGap: 14
                }},
                grid: {{ left: '4%', right: '4%', top: '44px', bottom: '16%', containLabel: true }},
                xAxis: {{
                    type: 'category',
                    data: {dates_json},
                    boundaryGap: false,
                    axisLine: {{ lineStyle: {{ color: '{t["axis_line"]}' }} }},
                    axisLabel: {{ color: '{t["axis_label"]}', fontSize: 14 }}
                }},
                yAxis: {{
                    type: 'value',
                    name: '价格 ($ USD)',
                    nameTextStyle: {{ color: '{t["axis_label"]}', fontSize: 14, padding: [0, 0, 6, 0] }},
                    scale: true,
                    axisLine: {{ show: false }},
                    splitLine: {{ lineStyle: {{ color: '{t["split_line"]}' }} }},
                    axisLabel: {{ color: '{t["axis_label"]}', fontSize: 14, formatter: '${{value}}' }}
                }},
                dataZoom: [
                    {{ type: 'inside', start: 0, end: 100 }},
                    {{
                        type: 'slider', bottom: '10px', height: 22,
                        borderColor: '{t["datazoom_border"]}', backgroundColor: '{t["datazoom_bg"]}',
                        fillerColor: '{t["datazoom_filler"]}',
                        textStyle: {{ color: '{t["axis_label"]}', fontSize: 12 }}
                    }}
                ],
                series: {series_json}
            }};
            chart.setOption(option);
            window.addEventListener('resize', () => chart.resize());
        </script>
    </body>
    </html>
    """
    components.html(html_code, height=height + 15, scrolling=False)
    return True


# ------------------------------------------------------------------
# 7. 期权 Max Pain 最大痛点与未平仓量 (OI) 分布组件
# ------------------------------------------------------------------
def render_echarts_max_pain(options_data: dict, current_price: float = None, height: int = 500):
    t = get_chart_theme_tokens()
    """
    使用 Apache ECharts 渲染经典期权多空持仓瀑布图与做市商最大痛点 (Max Pain)
    - 绿色 Call / 红色 Put 对称分组柱状图
    - Max Pain 黄金虚线与当前市价蓝线自动标注
    """
    if not options_data or "df_strikes" not in options_data:
        st.warning("暂无可用期权链数据。")
        return False
    df = options_data["df_strikes"].copy()
    if df.empty or 'strike' not in df.columns:
        st.warning("期权数据为空。")
        return False

    symbol = options_data.get("symbol", "")
    exp_date = options_data.get("expiration", "")
    max_pain = options_data.get("max_pain_price", None)

    if current_price is not None and current_price > 0:
        low_strike = current_price * 0.65
        high_strike = current_price * 1.35
        df_plot = df[(df['strike'] >= low_strike) & (df['strike'] <= high_strike)].copy()
        if len(df_plot) < 5:
            df_plot = df.copy()
    else:
        df_plot = df.copy()

    df_plot.sort_values('strike', inplace=True)
    strikes = [f"${s:.1f}" for s in df_plot['strike']]
    call_ois = [int(v) if pd.notna(v) else 0 for v in df_plot['call_oi']]
    put_ois = [int(v) if pd.notna(v) else 0 for v in df_plot['put_oi']]

    strikes_json = json.dumps(strikes)
    calls_json = json.dumps(call_ois)
    puts_json = json.dumps(put_ois)

    mp_val = f"${max_pain:.1f}" if (max_pain and pd.notna(max_pain)) else "N/A"
    cp_val = f"${current_price:.2f}" if (current_price and pd.notna(current_price)) else "N/A"

    html_code = f"""
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <script src="https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"></script>
        <style>
            * {{ box-sizing: border-box; }}
            body {{
                margin: 0;
                padding: 0;
                background-color: {t["body_bg"]};
                color: {t["text_color"]};
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
                overflow: hidden;
            }}
            .chart-card {{
                width: 100%;
                height: {height}px;
                background: {t["card_bg"]};
                border: 1px solid {t["border_color"]};
                border-radius: 12px;
                box-shadow: {t["box_shadow"]};
                position: relative;
                display: flex;
                flex-direction: column;
            }}
            .chart-header {{
                display: flex;
                justify-content: space-between;
                align-items: flex-start;
                padding: 12px 18px 4px 18px;
                gap: 12px;
                flex-shrink: 0;
            }}
            .chart-title-area {{
                flex: 1;
                min-width: 0;
            }}
            .chart-title {{
                font-size: 17px;
                font-weight: 700;
                color: {t["title_color"]};
                line-height: 1.35;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
            }}
            .chart-subtitle {{
                font-size: 13px;
                color: {t["subtitle_color"]};
                margin-top: 2px;
                line-height: 1.3;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
            }}
            .chart-body {{
                width: 100%;
                flex: 1;
                min-height: 0;
            }}
            .tag-mp {{ background: rgba(234, 179, 8, 0.2); color: #facc15; padding: 2px 8px; border-radius: 4px; border: 1px solid rgba(234, 179, 8, 0.4); font-size: 13px; font-weight: 600; }}
            .tag-cp {{ background: rgba(56, 189, 248, 0.2); color: #38bdf8; padding: 2px 8px; border-radius: 4px; border: 1px solid rgba(56, 189, 248, 0.4); font-size: 13px; font-weight: 600; }}
        </style>
    </head>
    <body>
        <div class="chart-card">
            <div class="chart-header">
                <div class="chart-title-area">
                    <div class="chart-title">{symbol} 期权未平仓量 (OI) 分布与做市商最大痛点</div>
                    <div class="chart-subtitle">到期日: [{exp_date}] · 绿色看涨 Call / 红色看跌 Put</div>
                </div>
                <div style="display:flex;gap:8px;align-items:center;flex-shrink:0;">
                    <span class="tag-mp">Max Pain: {mp_val}</span>
                    <span class="tag-cp">现价: {cp_val}</span>
                </div>
            </div>
            <div id="mp_chart" class="chart-body"></div>
        </div>
        <script>
            const chart = echarts.init(document.getElementById('mp_chart'), '{t["echarts_theme"]}');
            const option = {{
                backgroundColor: '{t["card_bg"]}',
                tooltip: {{
                    trigger: 'axis',
                    axisPointer: {{ type: 'shadow' }},
                    backgroundColor: 'rgba(15, 23, 42, 0.95)',
                    borderColor: '#334155', borderWidth: 1,
                    textStyle: {{ color: '#f8fafc', fontSize: 14 }}
                }},
                legend: {{
                    data: ['Call 看涨未平仓 (OI)', 'Put 看跌未平仓 (OI)'],
                    top: '6px',
                    left: 'center',
                    type: 'scroll',
                    textStyle: {{ color: '#cbd5e1', fontSize: 13 }},
                    itemGap: 16
                }},
                grid: {{ left: '4%', right: '4%', top: '44px', bottom: '16%', containLabel: true }},
                xAxis: {{
                    type: 'category',
                    name: '行权价',
                    nameTextStyle: {{ color: '#94a3b8', fontSize: 14 }},
                    data: {strikes_json},
                    axisLine: {{ lineStyle: {{ color: '#334155' }} }},
                    axisLabel: {{ color: '#94a3b8', fontSize: 14, rotate: 30 }}
                }},
                yAxis: {{
                    type: 'value',
                    name: '合约张数 (Contracts)',
                    nameTextStyle: {{ color: '#94a3b8', fontSize: 14, padding: [0, 0, 6, 0] }},
                    axisLine: {{ show: false }},
                    splitLine: {{ lineStyle: {{ color: 'rgba(255, 255, 255, 0.05)' }} }},
                    axisLabel: {{ color: '#94a3b8', fontSize: 14 }}
                }},
                dataZoom: [
                    {{ type: 'inside', start: 0, end: 100 }},
                    {{
                        type: 'slider', bottom: '10px', height: 20,
                        borderColor: '#1e293b', backgroundColor: '#0f172a',
                        fillerColor: 'rgba(56, 189, 248, 0.25)',
                        textStyle: {{ color: '#94a3b8', fontSize: 12 }}
                    }}
                ],
                series: [
                    {{
                        name: 'Call 看涨未平仓 (OI)',
                        type: 'bar',
                        data: {calls_json},
                        itemStyle: {{ color: '#10b981', borderRadius: [4, 4, 0, 0] }},
                        barGap: '10%'
                    }},
                    {{
                        name: 'Put 看跌未平仓 (OI)',
                        type: 'bar',
                        data: {puts_json},
                        itemStyle: {{ color: '#f43f5e', borderRadius: [4, 4, 0, 0] }}
                    }}
                ]
            }};
            chart.setOption(option);
            window.addEventListener('resize', () => chart.resize());
        </script>
    </body>
    </html>
    """
    components.html(html_code, height=height + 15, scrolling=False)
    return True


# ------------------------------------------------------------------
# 8. 个股技术动量与超买超卖信号组件 (Bollinger Bands, MACD, RSI)
# ------------------------------------------------------------------
def render_echarts_technical_momentum(df_stock: pd.DataFrame, symbol: str, timeframe: str = "1Y", height: int = 680):
    t = get_chart_theme_tokens()
    """
    使用 Apache ECharts 渲染三联协同技术动量分析图
    - Panel 1: 股价 + 布林带云层 (Bollinger Bands)
    - Panel 2: MACD 柱状图与信号线
    - Panel 3: RSI (14) 70/30 阈值线
    """
    if df_stock is None or df_stock.empty or 'Close' not in df_stock.columns:
        st.warning(f"标的 {symbol} 暂无有效技术面走势数据。")
        return False

    df = df_stock.copy()
    if 'Date' not in df.columns:
        if isinstance(df.index, pd.DatetimeIndex):
            df = df.reset_index()
            df.rename(columns={'index': 'Date'}, inplace=True)
        elif 'date' in df.columns:
            df.rename(columns={'date': 'Date'}, inplace=True)
    df['Date'] = pd.to_datetime(df['Date'])
    df.sort_values('Date', inplace=True)

    # 1. 计算指标
    delta = df['Close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14, min_periods=5).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14, min_periods=5).mean()
    rs = gain / (loss + 1e-9)
    df['RSI'] = 100 - (100 / (1 + rs))

    exp12 = df['Close'].ewm(span=12, adjust=False).mean()
    exp26 = df['Close'].ewm(span=26, adjust=False).mean()
    df['MACD'] = exp12 - exp26
    df['Signal'] = df['MACD'].ewm(span=9, adjust=False).mean()
    df['Hist'] = df['MACD'] - df['Signal']

    df['BB_Mid'] = df['Close'].rolling(window=20, min_periods=5).mean()
    df['BB_Std'] = df['Close'].rolling(window=20, min_periods=5).std()
    df['BB_Upper'] = df['BB_Mid'] + 2 * df['BB_Std']
    df['BB_Lower'] = df['BB_Mid'] - 2 * df['BB_Std']

    df = filter_by_timeframe(df, 'Date', timeframe)
    if df.empty:
        return False

    dates = df['Date'].dt.strftime('%Y-%m-%d').tolist()
    close_vals = [round(float(v), 2) for v in df['Close']]
    bb_mid = [round(float(v), 2) if pd.notna(v) else None for v in df['BB_Mid']]
    bb_upper = [round(float(v), 2) if pd.notna(v) else None for v in df['BB_Upper']]
    bb_lower = [round(float(v), 2) if pd.notna(v) else None for v in df['BB_Lower']]
    macd_vals = [round(float(v), 3) if pd.notna(v) else None for v in df['MACD']]
    sig_vals = [round(float(v), 3) if pd.notna(v) else None for v in df['Signal']]
    hist_vals = [round(float(v), 3) if pd.notna(v) else None for v in df['Hist']]
    rsi_vals = [round(float(v), 1) if pd.notna(v) else None for v in df['RSI']]

    dates_json = json.dumps(dates)
    close_json = json.dumps(close_vals)
    bb_mid_json = json.dumps(bb_mid)
    bb_up_json = json.dumps(bb_upper)
    bb_low_json = json.dumps(bb_lower)
    macd_json = json.dumps(macd_vals)
    sig_json = json.dumps(sig_vals)
    hist_json = json.dumps(hist_vals)
    rsi_json = json.dumps(rsi_vals)

    html_code = f"""
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <script src="https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"></script>
        <style>
            * {{ box-sizing: border-box; }}
            body {{
                margin: 0;
                padding: 0;
                background-color: {t["body_bg"]};
                color: {t["text_color"]};
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
                overflow: hidden;
            }}
            .chart-card {{
                width: 100%;
                height: {height}px;
                background: {t["card_bg"]};
                border: 1px solid {t["border_color"]};
                border-radius: 12px;
                box-shadow: {t["box_shadow"]};
                position: relative;
                display: flex;
                flex-direction: column;
            }}
            .chart-header {{
                display: flex;
                justify-content: space-between;
                align-items: flex-start;
                padding: 12px 18px 4px 18px;
                gap: 12px;
                flex-shrink: 0;
            }}
            .chart-title-area {{
                flex: 1;
                min-width: 0;
            }}
            .chart-title {{
                font-size: 17px;
                font-weight: 700;
                color: {t["title_color"]};
                line-height: 1.35;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
            }}
            .chart-subtitle {{
                font-size: 13px;
                color: {t["subtitle_color"]};
                margin-top: 2px;
                line-height: 1.3;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
            }}
            .chart-body {{
                width: 100%;
                flex: 1;
                min-height: 0;
            }}
        </style>
    </head>
    <body>
        <div class="chart-card">
            <div class="chart-header">
                <div class="chart-title-area">
                    <div class="chart-title">{symbol} 技术动量与超买超卖综合看板</div>
                    <div class="chart-subtitle">布林带 (20,2) · MACD (12,26,9) · RSI (14)</div>
                </div>
            </div>
            <div id="tm_chart" class="chart-body"></div>
        </div>
        <script>
            const chart = echarts.init(document.getElementById('tm_chart'), '{t["echarts_theme"]}');
            const dates = {dates_json};
            const histData = {hist_json};

            const option = {{
                backgroundColor: '{t["card_bg"]}',
                animationDuration: 300,
                tooltip: {{
                    trigger: 'axis',
                    axisPointer: {{ type: 'cross', lineStyle: {{ color: '#64748b', type: 'dashed' }} }},
                    backgroundColor: 'rgba(15, 23, 42, 0.95)',
                    borderColor: '#334155', borderWidth: 1,
                    textStyle: {{ color: '#f8fafc', fontSize: 14 }}
                }},
                legend: {{
                    data: ['{symbol} 股价', '20MA 中轨', '布林上轨', '布林下轨', 'MACD', 'Signal', 'RSI'],
                    top: '6px',
                    left: 'center',
                    type: 'scroll',
                    textStyle: {{ color: '#cbd5e1', fontSize: 13 }},
                    itemGap: 14
                }},
                axisPointer: {{ link: [{{ xAxisIndex: 'all' }}] }},
                grid: [
                    {{ left: '4%', right: '4%', top: '44px', height: '42%', containLabel: true }},
                    {{ left: '4%', right: '4%', top: '63%', height: '17%', containLabel: true }},
                    {{ left: '4%', right: '4%', top: '82%', height: '12%', containLabel: true }}
                ],
                xAxis: [
                    {{ type: 'category', data: dates, gridIndex: 0, axisLine: {{ lineStyle: {{ color: '#334155' }} }}, axisLabel: {{ show: false }} }},
                    {{ type: 'category', data: dates, gridIndex: 1, axisLine: {{ lineStyle: {{ color: '#334155' }} }}, axisLabel: {{ show: false }} }},
                    {{ type: 'category', data: dates, gridIndex: 2, axisLine: {{ lineStyle: {{ color: '#334155' }} }}, axisLabel: {{ color: '#94a3b8', fontSize: 14 }} }}
                ],
                yAxis: [
                    {{ type: 'value', gridIndex: 0, scale: true, splitLine: {{ lineStyle: {{ color: 'rgba(255,255,255,0.05)' }} }}, axisLabel: {{ color: '#94a3b8', fontSize: 14, formatter: '${{value}}' }} }},
                    {{ type: 'value', gridIndex: 1, scale: true, splitLine: {{ lineStyle: {{ color: 'rgba(255,255,255,0.05)' }} }}, axisLabel: {{ color: '#94a3b8', fontSize: 14 }} }},
                    {{ type: 'value', gridIndex: 2, min: 0, max: 100, splitLine: {{ lineStyle: {{ color: 'rgba(255,255,255,0.05)' }} }}, axisLabel: {{ color: '#94a3b8', fontSize: 14 }} }}
                ],
                dataZoom: [
                    {{ type: 'inside', xAxisIndex: [0, 1, 2], start: 40, end: 100 }},
                    {{ type: 'slider', xAxisIndex: [0, 1, 2], bottom: '4px', height: 18, borderColor: '#1e293b', backgroundColor: '#0f172a', fillerColor: 'rgba(56, 189, 248, 0.25)' }}
                ],
                series: [
                    {{ name: '{symbol} 股价', type: 'line', xAxisIndex: 0, yAxisIndex: 0, data: {close_json}, lineStyle: {{ width: 2.2, color: '#38bdf8' }}, itemStyle: {{ color: '#38bdf8' }} }},
                    {{ name: '20MA 中轨', type: 'line', xAxisIndex: 0, yAxisIndex: 0, data: {bb_mid_json}, lineStyle: {{ width: 1.2, color: '#94a3b8' }}, symbol: 'none' }},
                    {{ name: '布林上轨', type: 'line', xAxisIndex: 0, yAxisIndex: 0, data: {bb_up_json}, lineStyle: {{ width: 1.0, color: 'rgba(148, 163, 184, 0.5)', type: 'dotted' }}, symbol: 'none' }},
                    {{ name: '布林下轨', type: 'line', xAxisIndex: 0, yAxisIndex: 0, data: {bb_low_json}, lineStyle: {{ width: 1.0, color: 'rgba(148, 163, 184, 0.5)', type: 'dotted' }}, symbol: 'none' }},
                    {{ name: 'MACD', type: 'line', xAxisIndex: 1, yAxisIndex: 1, data: {macd_json}, lineStyle: {{ width: 1.5, color: '#38bdf8' }}, symbol: 'none' }},
                    {{ name: 'Signal', type: 'line', xAxisIndex: 1, yAxisIndex: 1, data: {sig_json}, lineStyle: {{ width: 1.5, color: '#f59e0b' }}, symbol: 'none' }},
                    {{
                        name: 'MACD Hist', type: 'bar', xAxisIndex: 1, yAxisIndex: 1,
                        data: histData.map(v => ({{ value: v, itemStyle: {{ color: v >= 0 ? '#10b981' : '#f43f5e' }} }}))
                    }},
                    {{
                        name: 'RSI', type: 'line', xAxisIndex: 2, yAxisIndex: 2, data: {rsi_json}, lineStyle: {{ width: 1.8, color: '#a855f7' }}, symbol: 'none',
                        markLine: {{
                            silent: true, symbol: 'none',
                            data: [
                                {{ yAxis: 70, lineStyle: {{ color: '#ef4444', type: 'dashed' }} }},
                                {{ yAxis: 30, lineStyle: {{ color: '#10b981', type: 'dashed' }} }}
                            ]
                        }}
                    }}
                ]
            }};
            chart.setOption(option);
            window.addEventListener('resize', () => chart.resize());
        </script>
    </body>
    </html>
    """
    components.html(html_code, height=height + 15, scrolling=False)
    return True


# ------------------------------------------------------------------
# 9. 财务三张表趋势组合图 (Revenue, Net Income, Margins, FCF)
# ------------------------------------------------------------------
def render_echarts_financial_trends(df_stmt: pd.DataFrame, symbol: str = "", period_type: str = "季度", height: int = 540):
    t = get_chart_theme_tokens()
    """
    使用 Apache ECharts 渲染机构级财务三张表趋势组合图 (柱+线+副轴)
    """
    if df_stmt is None or df_stmt.empty:
        st.warning("暂无财务报表历史趋势数据。")
        return False

    df = df_stmt.copy()
    periods = df['Period'].tolist() if 'Period' in df.columns else [f"P{i}" for i in range(len(df))]

    rev_vals = [round(float(v), 1) if pd.notna(v) else 0 for v in df.get('Revenue ($M)', [])]
    ni_vals = [round(float(v), 1) if pd.notna(v) else 0 for v in df.get('Net Income ($M)', [])]
    fcf_vals = [round(float(v), 1) if pd.notna(v) else 0 for v in df.get('Free Cash Flow ($M)', [])]
    gm_vals = [round(float(v), 1) if pd.notna(v) else None for v in df.get('Gross Margin (%)', [])]
    nm_vals = [round(float(v), 1) if pd.notna(v) else None for v in df.get('Net Margin (%)', [])]

    periods_json = json.dumps(periods)
    rev_json = json.dumps(rev_vals)
    ni_json = json.dumps(ni_vals)
    fcf_json = json.dumps(fcf_vals)
    gm_json = json.dumps(gm_vals)
    nm_json = json.dumps(nm_vals)

    html_code = f"""
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <script src="https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"></script>
        <style>
            * {{ box-sizing: border-box; }}
            body {{
                margin: 0;
                padding: 0;
                background-color: {t["body_bg"]};
                color: {t["text_color"]};
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
                overflow: hidden;
            }}
            .chart-card {{
                width: 100%;
                height: {height}px;
                background: {t["card_bg"]};
                border: 1px solid {t["border_color"]};
                border-radius: 12px;
                box-shadow: {t["box_shadow"]};
                position: relative;
                display: flex;
                flex-direction: column;
            }}
            .chart-header {{
                display: flex;
                justify-content: space-between;
                align-items: flex-start;
                padding: 12px 18px 4px 18px;
                gap: 12px;
                flex-shrink: 0;
            }}
            .chart-title-area {{
                flex: 1;
                min-width: 0;
            }}
            .chart-title {{
                font-size: 17px;
                font-weight: 700;
                color: {t["title_color"]};
                line-height: 1.35;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
            }}
            .chart-subtitle {{
                font-size: 13px;
                color: {t["subtitle_color"]};
                margin-top: 2px;
                line-height: 1.3;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
            }}
            .chart-body {{
                width: 100%;
                flex: 1;
                min-height: 0;
            }}
        </style>
    </head>
    <body>
        <div class="chart-card">
            <div class="chart-header">
                <div class="chart-title-area">
                    <div class="chart-title">{symbol} 核心财务报表趋势透视 ({period_type})</div>
                    <div class="chart-subtitle">营收 & 净利规模 ($M, 左轴) · 毛利率 & 净利率 (%, 右轴)</div>
                </div>
            </div>
            <div id="fin_chart" class="chart-body"></div>
        </div>
        <script>
            const chart = echarts.init(document.getElementById('fin_chart'), '{t["echarts_theme"]}');
            const option = {{
                backgroundColor: '{t["card_bg"]}',
                tooltip: {{
                    trigger: 'axis',
                    axisPointer: {{ type: 'shadow' }},
                    backgroundColor: 'rgba(15, 23, 42, 0.95)',
                    borderColor: '#334155', borderWidth: 1,
                    textStyle: {{ color: '#f8fafc', fontSize: 14 }}
                }},
                legend: {{
                    data: ['总营收 ($M)', '净利润 ($M)', '自由现金流 ($M)', '毛利率 (%)', '净利率 (%)'],
                    top: '6px',
                    left: 'center',
                    type: 'scroll',
                    textStyle: {{ color: '#cbd5e1', fontSize: 13 }},
                    itemGap: 14
                }},
                grid: {{ left: '4%', right: '4%', top: '46px', bottom: '12%', containLabel: true }},
                xAxis: {{
                    type: 'category',
                    data: {periods_json},
                    axisLine: {{ lineStyle: {{ color: '#334155' }} }},
                    axisLabel: {{ color: '#94a3b8', fontSize: 14 }}
                }},
                yAxis: [
                    {{
                        type: 'value',
                        name: '规模 ($M)',
                        nameTextStyle: {{ color: '#94a3b8', fontSize: 14, padding: [0, 0, 6, 0] }},
                        splitLine: {{ lineStyle: {{ color: 'rgba(255,255,255,0.05)' }} }},
                        axisLabel: {{ color: '#94a3b8', fontSize: 14, formatter: '${{value}}M' }}
                    }},
                    {{
                        type: 'value',
                        name: '利润率 (%)',
                        nameTextStyle: {{ color: '#94a3b8', fontSize: 14, padding: [0, 0, 6, 0] }},
                        splitLine: {{ show: false }},
                        axisLabel: {{ color: '#94a3b8', fontSize: 14, formatter: '{{value}}%' }}
                    }}
                ],
                series: [
                    {{
                        name: '总营收 ($M)', type: 'bar', yAxisIndex: 0, data: {rev_json},
                        itemStyle: {{ color: '#3b82f6', borderRadius: [4, 4, 0, 0] }}
                    }},
                    {{
                        name: '净利润 ($M)', type: 'bar', yAxisIndex: 0, data: {ni_json},
                        itemStyle: {{ color: '#10b981', borderRadius: [4, 4, 0, 0] }}
                    }},
                    {{
                        name: '自由现金流 ($M)', type: 'line', yAxisIndex: 0, data: {fcf_json},
                        lineStyle: {{ width: 2.2, color: '#06b6d4' }}, itemStyle: {{ color: '#06b6d4' }}
                    }},
                    {{
                        name: '毛利率 (%)', type: 'line', yAxisIndex: 1, data: {gm_json},
                        lineStyle: {{ width: 2.0, color: '#8b5cf6', type: 'dashed' }}, itemStyle: {{ color: '#8b5cf6' }}
                    }},
                    {{
                        name: '净利率 (%)', type: 'line', yAxisIndex: 1, data: {nm_json},
                        lineStyle: {{ width: 2.0, color: '#f59e0b' }}, itemStyle: {{ color: '#f59e0b' }}
                    }}
                ]
            }};
            chart.setOption(option);
            window.addEventListener('resize', () => chart.resize());
        </script>
    </body>
    </html>
    """
    components.html(html_code, height=height + 15, scrolling=False)
    return True


# ------------------------------------------------------------------
# 10. 标普 500 股权风险溢价 (ERP 动态版) 组件
# ------------------------------------------------------------------
def render_echarts_erp_chart(erp_dict: dict, timeframe: str = "3Y", height: int = 480):
    t = get_chart_theme_tokens()
    """
    使用 Apache ECharts 渲染 S&P 500 股权风险溢价 (ERP) 动态罗盘
    - 10Y 美债收益率 vs 标普盈利收益率 (EY)
    - ERP 利差柱 (零轴正负分色) 与 0% 倒挂预警线、2.5% 高性价比线
    """
    if not erp_dict or "df_history" not in erp_dict:
        st.warning("暂无可用 ERP 历史数据。")
        return False

    df = filter_by_timeframe(erp_dict["df_history"].copy(), 'date', timeframe)
    if df.empty:
        return False

    current_ey = erp_dict.get("current_ey", 4.65)
    df['Earnings_Yield'] = current_ey
    df['ERP'] = df['Earnings_Yield'] - df['10Y_Yield']

    dates = pd.to_datetime(df['date']).dt.strftime('%Y-%m-%d').tolist()
    y10_vals = [round(float(v), 2) for v in df['10Y_Yield']]
    ey_vals = [round(float(v), 2) for v in df['Earnings_Yield']]
    erp_vals = [round(float(v), 2) for v in df['ERP']]

    dates_json = json.dumps(dates)
    y10_json = json.dumps(y10_vals)
    ey_json = json.dumps(ey_vals)
    erp_json = json.dumps(erp_vals)

    html_code = f"""
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <script src="https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"></script>
        <style>
            * {{ box-sizing: border-box; }}
            body {{
                margin: 0;
                padding: 0;
                background-color: {t["body_bg"]};
                color: {t["text_color"]};
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
                overflow: hidden;
            }}
            .chart-card {{
                width: 100%;
                height: {height}px;
                background: {t["card_bg"]};
                border: 1px solid {t["border_color"]};
                border-radius: 12px;
                box-shadow: {t["box_shadow"]};
                position: relative;
                display: flex;
                flex-direction: column;
            }}
            .chart-header {{
                display: flex;
                justify-content: space-between;
                align-items: flex-start;
                padding: 12px 18px 4px 18px;
                gap: 12px;
                flex-shrink: 0;
            }}
            .chart-title-area {{
                flex: 1;
                min-width: 0;
            }}
            .chart-title {{
                font-size: 17px;
                font-weight: 700;
                color: {t["title_color"]};
                line-height: 1.35;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
            }}
            .chart-subtitle {{
                font-size: 13px;
                color: {t["subtitle_color"]};
                margin-top: 2px;
                line-height: 1.3;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
            }}
            .chart-body {{
                width: 100%;
                flex: 1;
                min-height: 0;
            }}
        </style>
    </head>
    <body>
        <div class="chart-card">
            <div class="chart-header">
                <div class="chart-title-area">
                    <div class="chart-title">S&P 500 股权风险溢价 (Equity Risk Premium, ERP)</div>
                    <div class="chart-subtitle">标普远期盈利收益率 (EY) vs 10Y美债收益率 · 零轴倒挂风险警戒</div>
                </div>
            </div>
            <div id="erp_chart" class="chart-body"></div>
        </div>
        <script>
            const chart = echarts.init(document.getElementById('erp_chart'), '{t["echarts_theme"]}');
            const erpData = {erp_json};

            const option = {{
                backgroundColor: '{t["card_bg"]}',
                tooltip: {{
                    trigger: 'axis',
                    backgroundColor: 'rgba(15, 23, 42, 0.95)',
                    borderColor: '#334155', borderWidth: 1,
                    textStyle: {{ color: '#f8fafc', fontSize: 14 }},
                    valueFormatter: (v) => v != null ? v.toFixed(2) + ' %' : '-'
                }},
                legend: {{
                    data: ['10Y 美债收益率', '标普盈利收益率 (EY)', 'ERP 风险溢价差'],
                    top: '6px',
                    left: 'center',
                    type: 'scroll',
                    textStyle: {{ color: '#cbd5e1', fontSize: 13 }},
                    itemGap: 16
                }},
                grid: {{ left: '4%', right: '4%', top: '46px', bottom: '16%', containLabel: true }},
                xAxis: {{
                    type: 'category', data: {dates_json},
                    axisLine: {{ lineStyle: {{ color: '#334155' }} }},
                    axisLabel: {{ color: '#94a3b8', fontSize: 14 }}
                }},
                yAxis: [
                    {{
                        type: 'value', name: '收益率 (%)',
                        nameTextStyle: {{ color: '#94a3b8', fontSize: 14, padding: [0, 0, 6, 0] }},
                        splitLine: {{ lineStyle: {{ color: 'rgba(255,255,255,0.05)' }} }},
                        axisLabel: {{ color: '#94a3b8', fontSize: 14, formatter: '{{value}}%' }}
                    }},
                    {{
                        type: 'value', name: 'ERP 溢价 (%)',
                        nameTextStyle: {{ color: '#94a3b8', fontSize: 14, padding: [0, 0, 6, 0] }},
                        splitLine: {{ show: false }},
                        axisLabel: {{ color: '#94a3b8', fontSize: 14, formatter: '{{value}}%' }}
                    }}
                ],
                dataZoom: [
                    {{ type: 'inside', start: 0, end: 100 }},
                    {{ type: 'slider', bottom: '10px', height: 20, borderColor: '#1e293b', backgroundColor: '#0f172a', fillerColor: 'rgba(56, 189, 248, 0.25)' }}
                ],
                series: [
                    {{
                        name: '10Y 美债收益率', type: 'line', yAxisIndex: 0, data: {y10_json},
                        lineStyle: {{ width: 2.2, color: '#ef4444' }}, itemStyle: {{ color: '#ef4444' }}
                    }},
                    {{
                        name: '标普盈利收益率 (EY)', type: 'line', yAxisIndex: 0, data: {ey_json},
                        lineStyle: {{ width: 2.2, color: '#10b981', type: 'dashed' }}, itemStyle: {{ color: '#10b981' }}
                    }},
                    {{
                        name: 'ERP 风险溢价差', type: 'bar', yAxisIndex: 1,
                        data: erpData.map(v => ({{
                            value: v,
                            itemStyle: {{ color: v >= 0 ? 'rgba(59, 130, 246, 0.6)' : 'rgba(249, 115, 22, 0.7)' }}
                        }})),
                        markLine: {{
                            silent: true, symbol: 'none',
                            data: [
                                {{ yAxis: 0, lineStyle: {{ color: '#e2e8f0', type: 'dashed' }}, label: {{ formatter: '0% 倒挂界限', color: '#e2e8f0' }} }},
                                {{ yAxis: 2.5, lineStyle: {{ color: '#10b981', type: 'dotted' }}, label: {{ formatter: '2.5% 高性价比', color: '#10b981' }} }}
                            ]
                        }}
                    }}
                ]
            }};
            chart.setOption(option);
            window.addEventListener('resize', () => chart.resize());
        </script>
    </body>
    </html>
    """
    components.html(html_code, height=height + 15, scrolling=False)
    return True


# ------------------------------------------------------------------
# 11. 高收益债信用利差 (HY OAS) 组件
# ------------------------------------------------------------------
def render_echarts_credit_spread(df_data: pd.DataFrame, timeframe: str = "ALL", height: int = 460):
    """
    使用 ECharts 渲染 US High Yield OAS 高收益债信用利差 (含 4.5% 风险警戒线)
    """
    date_col = 'date' if 'date' in df_data.columns else ('Date' if 'Date' in df_data.columns else df_data.columns[0])
    val_col = 'Value' if 'Value' in df_data.columns else ('High_Yield_Spread' if 'High_Yield_Spread' in df_data.columns else df_data.columns[1])
    series_configs = [
        {"col": val_col, "name": "高收益债利差 (OAS)", "color": "#f43f5e", "area": True, "width": 2.2},
    ]
    mark_lines = [
        {"yAxis": 4.5, "color": "#ef4444", "label": "4.5% 紧缩警戒线", "type": "dashed"},
    ]
    return render_echarts_macro_chart(
        df=df_data,
        date_col=date_col,
        series_configs=series_configs,
        title="US High Yield Option-Adjusted Spread (高收益债信用利差)",
        subtitle="企业融资违约风险溢价 · 4.5% 信用紧缩警戒线",
        yaxis_title="利差 (%)",
        height=height,
        zero_line=False,
        mark_lines=mark_lines,
        timeframe=timeframe,
        initial_zoom_pct=40
    )


# ------------------------------------------------------------------
# 12. 芝加哥联储金融条件指数 (NFCI) 组件
# ------------------------------------------------------------------
def render_echarts_nfci_chart(df_nfci: pd.DataFrame, timeframe: str = "ALL", height: int = 460):
    """
    使用 ECharts 渲染芝加哥联储全国金融条件指数 (NFCI) (零轴正负分色)
    """
    date_col = 'date' if 'date' in df_nfci.columns else ('Date' if 'Date' in df_nfci.columns else df_nfci.columns[0])
    val_col = 'NFCI' if 'NFCI' in df_nfci.columns else df_nfci.columns[1]
    series_configs = [
        {"col": val_col, "name": "芝加哥联储 NFCI", "color": "#38bdf8", "area": True, "width": 2.2},
    ]
    return render_echarts_macro_chart(
        df=df_nfci,
        date_col=date_col,
        series_configs=series_configs,
        title="Chicago Fed National Financial Conditions Index (NFCI)",
        subtitle="综合金融体系松紧度 · 零轴 (<0 宽松, >0 紧缩)",
        yaxis_title="指数点位",
        height=height,
        zero_line=True,
        timeframe=timeframe,
        initial_zoom_pct=40
    )


# ------------------------------------------------------------------
# 13. 萨姆法则衰退指标 (Sahm Rule) 组件
# ------------------------------------------------------------------
def render_echarts_sahm_rule(df_sahm: pd.DataFrame, timeframe: str = "ALL", height: int = 460):
    """
    使用 ECharts 渲染萨姆法则衰退指标 (Sahm Rule) (含 0.50% 硬衰退红线)
    """
    date_col = 'date' if 'date' in df_sahm.columns else ('Date' if 'Date' in df_sahm.columns else df_sahm.columns[0])
    val_col = 'Sahm_Rule' if 'Sahm_Rule' in df_sahm.columns else df_sahm.columns[1]
    series_configs = [
        {"col": val_col, "name": "萨姆法则衰退指标", "color": "#f59e0b", "area": True, "width": 2.2},
    ]
    mark_lines = [
        {"yAxis": 0.50, "color": "#ef4444", "label": "0.50% 衰退红线", "type": "dashed"},
    ]
    return render_echarts_macro_chart(
        df=df_sahm,
        date_col=date_col,
        series_configs=series_configs,
        title="Sahm Rule Recession Indicator (萨姆法则经济衰退指标)",
        subtitle="失业率3个月移动均值相对前12个月低点差值 · ≥0.50% 历史100%对应经济衰退",
        yaxis_title="点位",
        height=height,
        zero_line=False,
        mark_lines=mark_lines,
        timeframe=timeframe,
        initial_zoom_pct=40
    )


# ------------------------------------------------------------------
# 14. CNN 恐慌与贪婪指数 (Fear & Greed) 组件
# ------------------------------------------------------------------
def render_echarts_fear_greed(df_fgi: pd.DataFrame, timeframe: str = "ALL", height: int = 480):
    """
    使用 ECharts 渲染 CNN 恐慌与贪婪指数历史走势 (含 25 极度恐慌 / 75 极度贪婪区间)
    """
    date_col = 'date' if 'date' in df_fgi.columns else ('Date' if 'Date' in df_fgi.columns else df_fgi.columns[0])
    val_col = 'Score' if 'Score' in df_fgi.columns else df_fgi.columns[1]
    series_configs = [
        {"col": val_col, "name": "CNN 恐慌贪婪指数", "color": "#06b6d4", "area": True, "width": 2.2},
    ]
    mark_lines = [
        {"yAxis": 25, "color": "#10b981", "label": "25 极度恐慌 (价值区)", "type": "dashed"},
        {"yAxis": 75, "color": "#ef4444", "label": "75 极度贪婪 (警惕区)", "type": "dashed"},
    ]
    return render_echarts_macro_chart(
        df=df_fgi,
        date_col=date_col,
        series_configs=series_configs,
        title="CNN Fear & Greed Index (市场情绪恐慌与贪婪指数)",
        subtitle="0-25 极度恐慌 (逆向买点) · 75-100 极度贪婪 (风险回调预警)",
        yaxis_title="分值 (0-100)",
        height=height,
        zero_line=False,
        mark_lines=mark_lines,
        timeframe=timeframe,
        initial_zoom_pct=40
    )


# ------------------------------------------------------------------
# 15. 10Y TIPS 实际利率与 10Y 盈亏平衡通胀预期组件
# ------------------------------------------------------------------
def render_echarts_real_yield_breakeven(df_ry: pd.DataFrame, timeframe: str = "ALL", height: int = 460):
    """
    使用 ECharts 渲染 10Y TIPS 实际利率与 10Y 盈亏平衡通胀率双线对比
    """
    date_col = 'date' if 'date' in df_ry.columns else ('Date' if 'Date' in df_ry.columns else df_ry.columns[0])
    series_configs = []
    if '10Y_Real_Yield' in df_ry.columns:
        series_configs.append({"col": "10Y_Real_Yield", "name": "10Y TIPS 实际利率", "color": "#38bdf8", "area": False, "width": 2.2})
    if '10Y_Breakeven_Inflation' in df_ry.columns:
        series_configs.append({"col": "10Y_Breakeven_Inflation", "name": "10Y 盈亏平衡通胀预期", "color": "#f59e0b", "area": False, "width": 2.2})

    return render_echarts_macro_chart(
        df=df_ry,
        date_col=date_col,
        series_configs=series_configs,
        title="10Y TIPS 实际利率 & 10Y 盈亏平衡通胀预期 (%)",
        subtitle="全球无风险资产真实回报率分母 vs 通胀预期锚",
        yaxis_title="利率 (%)",
        height=height,
        zero_line=True,
        timeframe=timeframe,
        initial_zoom_pct=40
    )


# ------------------------------------------------------------------
# 16. SOFR - IORB 利率与利差双轴图表 (ECharts 自适应版本)
# ------------------------------------------------------------------
def render_echarts_sofr_iorb(df_sofr: pd.DataFrame, timeframe: str = "ALL", height: int = 480):
    """
    使用 ECharts 渲染 SOFR 隔夜融资利率 vs IORB 准备金利率 & 利差 (bps)
    """
    if df_sofr is None or df_sofr.empty:
        st.warning("暂无 SOFR / IORB 数据。")
        return False
    date_col = 'date' if 'date' in df_sofr.columns else df_sofr.columns[0]
    series_configs = []
    if 'SOFR' in df_sofr.columns:
        series_configs.append({"col": "SOFR", "name": "SOFR 隔夜利率 (%)", "color": "#38bdf8", "width": 2.2})
    if 'IORB' in df_sofr.columns:
        series_configs.append({"col": "IORB", "name": "IORB 准备金利率 (%)", "color": "#10b981", "width": 2.2})
    if 'Spread_bps' in df_sofr.columns:
        series_configs.append({
            "col": "Spread_bps",
            "name": "SOFR - IORB 利差 (bps)",
            "color": "#f43f5e",
            "line_type": "dashed",
            "width": 2.0,
            "y_axis_index": 1,
            "mark_lines": [
                {"yAxis": 0.0, "color": "#94a3b8", "label": "0 bps 基准线"},
                {"yAxis": 10.0, "color": "#ef4444", "label": "钱荒预警 (+10 bps)"}
            ]
        })
    return render_echarts_macro_chart(
        df=df_sofr,
        date_col=date_col,
        series_configs=series_configs,
        title="SOFR 隔夜抵押融资利率 vs IORB 准备金利率 & 利差",
        subtitle="资金面体温计 · >+10 bps 钱荒警报",
        yaxis_title="利率 (%)",
        y2axis_title="利差 (bps)",
        y_format="{value} %",
        y2_format="{value} bps",
        height=height,
        timeframe=timeframe,
        initial_zoom_pct=40
    )


# ------------------------------------------------------------------
# 17. 美联储总资产 (Fed Balance Sheet / WALCL)
# ------------------------------------------------------------------
def render_echarts_fed_balance_sheet(df_fed: pd.DataFrame, timeframe: str = "ALL", height: int = 480):
    """
    使用 ECharts 渲染美联储总资产 (WALCL) 规模走势
    """
    if df_fed is None or df_fed.empty:
        st.warning("暂无美联储资产负债表数据。")
        return False
    date_col = 'date' if 'date' in df_fed.columns else ('Date' if 'Date' in df_fed.columns else df_fed.columns[0])
    val_col = 'balance_sheet_tn' if 'balance_sheet_tn' in df_fed.columns else df_fed.columns[1]
    series_configs = [
        {"col": val_col, "name": "美联储总资产 (万亿美元)", "color": "#10b981", "area": True, "width": 2.5}
    ]
    return render_echarts_macro_chart(
        df=df_fed,
        date_col=date_col,
        series_configs=series_configs,
        title="Fed Balance Sheet (美联储总资产 WALCL)",
        subtitle="QE 扩表注水 / QT 缩表紧缩 · 美联储资产负债表与货币供应",
        yaxis_title="总资产 (万亿美元 / $T)",
        y_format="${value} T",
        height=height,
        timeframe=timeframe,
        initial_zoom_pct=40
    )


# ------------------------------------------------------------------
# 18. M2 广义货币供应量总量与同比增速
# ------------------------------------------------------------------
def render_echarts_m2_money_supply(df_m2: pd.DataFrame, timeframe: str = "ALL", height: int = 480):
    """
    使用 ECharts 渲染 M2 广义货币供应量总量与同比增速 (YoY)
    """
    if df_m2 is None or df_m2.empty:
        st.warning("暂无 M2 数据。")
        return False
    date_col = 'date' if 'date' in df_m2.columns else ('Date' if 'Date' in df_m2.columns else df_m2.columns[0])
    series_configs = []
    if 'M2' in df_m2.columns:
        series_configs.append({"col": "M2", "name": "M2 货币供应总量 ($B)", "color": "#10b981", "width": 2.2})
    if 'M2_YoY' in df_m2.columns:
        series_configs.append({
            "col": "M2_YoY",
            "name": "M2 同比增速 (%)",
            "color": "#fbbf24",
            "line_type": "dashed",
            "width": 2.0,
            "y_axis_index": 1,
            "mark_lines": [
                {"yAxis": 0.0, "color": "#94a3b8", "label": "0% 临界线"}
            ]
        })
    return render_echarts_macro_chart(
        df=df_m2,
        date_col=date_col,
        series_configs=series_configs,
        title="M2 广义货币供应量总量与同比增速 (YoY)",
        subtitle="实体经济购买力蓄水池 · 再通胀周期启动信号",
        yaxis_title="总量 ($B)",
        y2axis_title="同比增速 (%)",
        y_format="${value} B",
        y2_format="{value} %",
        height=height,
        timeframe=timeframe,
        initial_zoom_pct=40
    )


# ------------------------------------------------------------------
# 19. 纽约联储 ACM 10 年期期限溢价 (Term Premium)
# ------------------------------------------------------------------
def render_echarts_term_premium(df_tp: pd.DataFrame, timeframe: str = "5Y", height: int = 480):
    """
    使用 ECharts 渲染纽约联储 ACM 10 年期期限溢价 (Term Premium)
    """
    if df_tp is None or df_tp.empty:
        st.warning("暂无期限溢价数据。")
        return False
    date_col = 'date' if 'date' in df_tp.columns else df_tp.columns[0]
    t = get_chart_theme_tokens()
    neutral_line_color = '#94a3b8' if t['mode'] == 'light' else '#cbd5e1'
    series_configs = []
    if 'DGS10' in df_tp.columns:
        series_configs.append({"col": "DGS10", "name": "10Y 美债名义收益率 (%)", "color": neutral_line_color, "line_type": "dashed", "width": 1.8})
    if 'Risk_Neutral_Rate' in df_tp.columns:
        series_configs.append({"col": "Risk_Neutral_Rate", "name": "风险中性期望利率 (%)", "color": "#60a5fa", "width": 1.8})
    if 'Term_Premium' in df_tp.columns:
        series_configs.append({
            "col": "Term_Premium",
            "name": "ACM 10Y 期限溢价 (%)",
            "color": "#f43f5e",
            "area": True,
            "width": 2.5,
            "mark_lines": [
                {"yAxis": 0.0, "color": neutral_line_color, "label": "0.0% 基准线"},
                {"yAxis": 0.5, "color": "#fbbf24", "label": "温和偏紧 (+0.5%)"},
                {"yAxis": 1.0, "color": "#ef4444", "label": "供给冲击红线 (+1.0%)"}
            ]
        })
    return render_echarts_macro_chart(
        df=df_tp,
        date_col=date_col,
        series_configs=series_configs,
        title="纽约联储 ACM 10 年期期限溢价 (Term Premium)",
        subtitle="美债供给冲击与财政赤字溢价拆解 · ACM 期限溢价模型",
        yaxis_title="收益率 / 溢价率 (%)",
        y_format="{value} %",
        height=height,
        timeframe=timeframe,
        initial_zoom_pct=50
    )


# ------------------------------------------------------------------
# 20. 全美商业银行工商业贷款规模与增速 (BUSLOANS) - 双网格自适应图
# ------------------------------------------------------------------
def render_echarts_commercial_loans(df_loans: pd.DataFrame, timeframe: str = "5Y", height: int = 540):
    """
    全美商业银行工商业贷款规模与增速 (BUSLOANS) - 动态自适应双网格图表
    """
    if df_loans is None or df_loans.empty:
        st.warning("暂无商业银行贷款数据。")
        return False
    date_col = 'date' if 'date' in df_loans.columns else df_loans.columns[0]
    df_clean = df_loans.copy()
    df_clean[date_col] = pd.to_datetime(df_clean[date_col])
    df_clean = df_clean.sort_values(date_col).dropna(subset=[date_col]).copy()
    if timeframe and timeframe != "ALL":
        df_clean = filter_by_timeframe(df_clean, date_col, timeframe)
    if df_clean.empty:
        st.warning(f"【工商业贷款】在选定时间跨度 [{timeframe}] 内无记录。")
        return False

    t = get_chart_theme_tokens()
    dates = df_clean[date_col].dt.strftime('%Y-%m-%d').tolist()
    loans_vals = [round(float(v), 2) if (v is not None and not pd.isna(v)) else None for v in df_clean.get('Loans_Billion', [])]
    yoy_vals = [round(float(v), 2) if (v is not None and not pd.isna(v)) else None for v in df_clean.get('YoY_pct', [])]

    yoy_bars = []
    for v in yoy_vals:
        if v is None:
            yoy_bars.append(None)
        else:
            bar_color = "#10b981" if v >= 0 else "#ef4444"
            yoy_bars.append({"value": v, "itemStyle": {"color": bar_color}})

    dates_json = json.dumps(dates)
    loans_json = json.dumps(loans_vals)
    yoy_json = json.dumps(yoy_bars)
    default_start = 50 if len(dates) > 50 else 0

    html_code = f"""
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <script src="https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"></script>
        <style>
            * {{ box-sizing: border-box; }}
            body {{
                margin: 0;
                padding: 0;
                background-color: {t["body_bg"]};
                color: {t["text_color"]};
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
                overflow: hidden;
            }}
            .chart-card {{
                width: 100%;
                height: {height}px;
                background: {t["card_bg"]};
                border: 1px solid {t["border_color"]};
                border-radius: 12px;
                box-shadow: {t["box_shadow"]};
                position: relative;
                display: flex;
                flex-direction: column;
            }}
            .chart-header {{
                display: flex;
                justify-content: space-between;
                align-items: flex-start;
                padding: 12px 18px 4px 18px;
                gap: 12px;
                flex-shrink: 0;
            }}
            .chart-title-area {{
                flex: 1;
                min-width: 0;
            }}
            .chart-title {{
                font-size: 17px;
                font-weight: 700;
                color: {t["title_color"]};
                line-height: 1.35;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
            }}
            .chart-subtitle {{
                font-size: 13px;
                color: {t["subtitle_color"]};
                margin-top: 2px;
                line-height: 1.3;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
            }}
            .chart-body {{
                width: 100%;
                flex: 1;
                min-height: 0;
            }}
        </style>
    </head>
    <body>
        <div class="chart-card">
            <div class="chart-header">
                <div class="chart-title-area">
                    <div class="chart-title">商业银行工商业贷款总规模 (BUSLOANS) & 同比增速 YoY</div>
                    <div class="chart-subtitle">实体信贷扩张与紧缩晴雨表</div>
                </div>
            </div>
            <div id="ec_main" class="chart-body"></div>
        </div>

        <script>
            const chartDom = document.getElementById('ec_main');
            const myChart = echarts.init(chartDom, '{t["echarts_theme"]}');

            const option = {{
                backgroundColor: '{t["card_bg"]}',
                animationDuration: 400,
                tooltip: {{
                    trigger: 'axis',
                    backgroundColor: '{t["tooltip_bg"]}',
                    borderColor: '{t["tooltip_border"]}',
                    borderWidth: 1,
                    textStyle: {{ color: '{t["tooltip_text"]}', fontSize: 14 }},
                    axisPointer: {{
                        type: 'cross',
                        label: {{ backgroundColor: '{t["tooltip_border"]}' }},
                        link: [{{ xAxisIndex: 'all' }}],
                        lineStyle: {{ color: '{t["axis_line"]}', type: 'dashed' }}
                    }}
                }},
                axisPointer: {{
                    link: [{{ xAxisIndex: 'all' }}]
                }},
                legend: {{
                    data: ['贷款总额 ($B)', 'YoY 增速 (%)'],
                    top: '6px',
                    left: 'center',
                    type: 'scroll',
                    textStyle: {{ color: '{t["legend_text"]}', fontSize: 13 }},
                    itemGap: 16,
                }},
                grid: [
                    {{
                        left: '5%',
                        right: '5%',
                        top: '46px',
                        height: '42%',
                        containLabel: true,
                    }},
                    {{
                        left: '5%',
                        right: '5%',
                        top: '60%',
                        height: '26%',
                        containLabel: true,
                    }}
                ],
                xAxis: [
                    {{
                        type: 'category',
                        gridIndex: 0,
                        data: {dates_json},
                        boundaryGap: false,
                        axisLine: {{ lineStyle: {{ color: '{t["axis_line"]}' }} }},
                        axisLabel: {{ show: false }},
                        splitLine: {{ show: false }}
                    }},
                    {{
                        type: 'category',
                        gridIndex: 1,
                        data: {dates_json},
                        boundaryGap: true,
                        axisLine: {{ lineStyle: {{ color: '{t["axis_line"]}' }} }},
                        axisLabel: {{ color: '{t["axis_label"]}', fontSize: 13 }},
                        splitLine: {{ show: false }}
                    }}
                ],
                yAxis: [
                    {{
                        type: 'value',
                        gridIndex: 0,
                        name: '贷款总额 ($B)',
                        nameTextStyle: {{ color: '{t["axis_label"]}', fontSize: 13, padding: [0, 0, 4, 0] }},
                        scale: true,
                        axisLine: {{ show: false }},
                        splitLine: {{ lineStyle: {{ color: '{t["split_line"]}' }} }},
                        axisLabel: {{
                            color: '{t["axis_label"]}',
                            fontSize: 13,
                            formatter: '${{value}} B'
                        }}
                    }},
                    {{
                        type: 'value',
                        gridIndex: 1,
                        name: 'YoY 增速 (%)',
                        nameTextStyle: {{ color: '{t["axis_label"]}', fontSize: 13, padding: [0, 0, 4, 0] }},
                        scale: true,
                        axisLine: {{ show: false }},
                        splitLine: {{ lineStyle: {{ color: '{t["split_line"]}' }} }},
                        axisLabel: {{
                            color: '{t["axis_label"]}',
                            fontSize: 13,
                            formatter: '{{value}} %'
                        }}
                    }}
                ],
                dataZoom: [
                    {{
                        type: 'inside',
                        xAxisIndex: [0, 1],
                        start: {default_start},
                        end: 100,
                    }},
                    {{
                        type: 'slider',
                        xAxisIndex: [0, 1],
                        start: {default_start},
                        end: 100,
                        bottom: 8,
                        height: 24,
                        borderColor: '{t["datazoom_border"]}',
                        backgroundColor: '{t["datazoom_bg"]}',
                        fillerColor: '{t["datazoom_filler"]}',
                        handleStyle: {{ color: '{t["datazoom_handle"]}' }},
                        textStyle: {{ color: '{t["axis_label"]}', fontSize: 12 }},
                        dataBackground: {{
                            lineStyle: {{ color: '{t["datazoom_handle"]}' }},
                            areaStyle: {{ color: '{t["datazoom_filler"]}' }}
                        }}
                    }}
                ],
                series: [
                    {{
                        name: '贷款总额 ($B)',
                        type: 'line',
                        xAxisIndex: 0,
                        yAxisIndex: 0,
                        smooth: true,
                        showSymbol: false,
                        data: {loans_json},
                        lineStyle: {{ width: 2.2, color: '#3b82f6' }},
                        areaStyle: {{
                            color: {{
                                type: 'linear',
                                x: 0, y: 0, x2: 0, y2: 1,
                                colorStops: [
                                    {{ offset: 0, color: 'rgba(59, 130, 246, 0.35)' }},
                                    {{ offset: 1, color: 'rgba(59, 130, 246, 0.0)' }}
                                ]
                            }}
                        }}
                    }},
                    {{
                        name: 'YoY 增速 (%)',
                        type: 'bar',
                        xAxisIndex: 1,
                        yAxisIndex: 1,
                        data: {yoy_json},
                        markLine: {{
                            silent: true,
                            symbol: 'none',
                            data: [
                                {{ yAxis: 0, lineStyle: {{ color: '{t["axis_label"]}', type: 'solid', width: 1 }} }},
                                {{ yAxis: 5, lineStyle: {{ color: '#22c55e', type: 'dashed', width: 1.5 }}, label: {{ formatter: '扩张 (>5%)', color: '#22c55e', fontSize: 12, position: 'end' }} }},
                                {{ yAxis: -2, lineStyle: {{ color: '#ef4444', type: 'dashed', width: 1.5 }}, label: {{ formatter: '紧缩 (<-2%)', color: '#ef4444', fontSize: 12, position: 'end' }} }}
                            ]
                        }}
                    }}
                ]
            }};

            myChart.setOption(option);
            window.addEventListener('resize', () => myChart.resize());
        </script>
    </body>
    </html>
    """
    components.html(html_code, height=height + 15, scrolling=False)
    return True


# ------------------------------------------------------------------
# 21. 美国居民个人储蓄率 (Personal Saving Rate, PSAVERT)
# ------------------------------------------------------------------
def render_echarts_personal_saving_rate(df_save: pd.DataFrame, timeframe: str = "5Y", height: int = 480):
    """
    使用 ECharts 渲染美国居民个人储蓄率 (PSAVERT)
    """
    if df_save is None or df_save.empty:
        st.warning("暂无居民个人储蓄率数据。")
        return False
    date_col = 'date' if 'date' in df_save.columns else df_save.columns[0]
    series_configs = []
    if 'Saving_Rate' in df_save.columns:
        series_configs.append({
            "col": "Saving_Rate",
            "name": "个人储蓄率 (%)",
            "color": "#14b8a6",
            "area": True,
            "width": 2.2,
            "mark_lines": [
                {"yAxis": 3.5, "color": "#ef4444", "label": "超额储蓄耗尽警戒 (3.5%)"}
            ]
        })
    if 'Saving_MA12' in df_save.columns:
        series_configs.append({"col": "Saving_MA12", "name": "12个月均线 (12MA)", "color": "#f59e0b", "line_type": "dashed", "width": 1.8})

    mark_areas = [
        {"y0": 5.5, "y1": 8.5, "color": "rgba(34, 197, 94, 0.12)", "label": "健康常态区间 (5.5% - 8.5%)"}
    ]
    return render_echarts_macro_chart(
        df=df_save,
        date_col=date_col,
        series_configs=series_configs,
        title="美国居民个人储蓄率 (Personal Saving Rate / PSAVERT)",
        subtitle="消费终极蓄水池 · 跌破 3.5% 消费抗风险韧性脆弱",
        yaxis_title="储蓄率 (%)",
        y_format="{value} %",
        mark_areas=mark_areas,
        height=height,
        timeframe=timeframe,
        initial_zoom_pct=50
    )


# ------------------------------------------------------------------
# 22. 美国周度初请与续请失业金人数 (Jobless Claims)
# ------------------------------------------------------------------
def render_echarts_jobless_claims(df_claims: pd.DataFrame, timeframe: str = "ALL", height: int = 480):
    """
    使用 ECharts 渲染美国周度初请与续请失业金人数高频追踪
    """
    if df_claims is None or df_claims.empty:
        st.warning("暂无失业金申请数据。")
        return False
    date_col = 'date' if 'date' in df_claims.columns else df_claims.columns[0]
    series_configs = []
    if 'Initial_Claims' in df_claims.columns:
        series_configs.append({
            "col": "Initial_Claims",
            "name": "初请失业金 (周度领先)",
            "color": "#38bdf8",
            "width": 2.2,
            "mark_lines": [
                {"yAxis": 250000, "color": "#fbbf24", "label": "边际松动 25万", "position": "insideStartBottom"},
                {"yAxis": 300000, "color": "#ef4444", "label": "衰退预警 30万", "position": "insideStartTop"}
            ]
        })
    if 'Continued_Claims' in df_claims.columns:
        series_configs.append({
            "col": "Continued_Claims",
            "name": "续请失业金 (同期人数)",
            "color": "#fb923c",
            "line_type": "dashed",
            "width": 1.8,
            "y_axis_index": 1
        })
    return render_echarts_macro_chart(
        df=df_claims,
        date_col=date_col,
        series_configs=series_configs,
        title="美国周度初请与续请失业金人数高频追踪",
        subtitle="初请领先劳动力边际 · 续请衡量再就业冻结程度",
        yaxis_title="初请 (人)",
        y2axis_title="续请 (人)",
        y_format="{value}",
        y2_format="{value}",
        height=height,
        timeframe=timeframe,
        initial_zoom_pct=40
    )


# ------------------------------------------------------------------
# 23. 支出与成本构成优雅环形图 (Donut Chart)
# ------------------------------------------------------------------
def render_echarts_expense_breakdown(expense_data, rev_base: float = 0.0, symbol: str = "", height: int = 380):
    """
    使用 Apache ECharts 渲染支出与成本构成优雅环形图 (Donut Chart)
    """
    t = get_chart_theme_tokens()
    if not expense_data:
        st.info("暂无可拆解的细分支出项。")
        return False

    if isinstance(expense_data, dict):
        raw_items = list(expense_data.items())
    elif isinstance(expense_data, pd.DataFrame):
        col_name = "支出科目" if "支出科目" in expense_data.columns else expense_data.columns[0]
        col_val = "金额 ($)" if "金额 ($)" in expense_data.columns else expense_data.columns[1]
        raw_items = list(zip(expense_data[col_name], expense_data[col_val]))
    else:
        st.warning("支出数据格式不支持。")
        return False

    chart_items = []
    total_exp = 0.0
    for k, v in raw_items:
        try:
            val = float(v)
            if val > 0:
                short_k = k.split("(")[0].strip() if "(" in k else str(k)
                chart_items.append({"name": short_k, "full_name": str(k), "value": round(val, 2)})
                total_exp += val
        except (ValueError, TypeError):
            continue

    if not chart_items:
        st.info("支出项无有效正值。")
        return False

    chart_items.sort(key=lambda x: x["value"], reverse=True)
    items_json = json.dumps(chart_items, ensure_ascii=False)

    subtext_str = f"总支出 ${total_exp:,.0f}"
    if rev_base and rev_base > 0:
        subtext_str += f" · 占营收比重 {(total_exp / rev_base) * 100:.1f}%"

    html_code = f"""
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <script src="https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"></script>
        <style>
            * {{ box-sizing: border-box; }}
            body {{
                margin: 0;
                padding: 0;
                background-color: {t["body_bg"]};
                color: {t["text_color"]};
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
                overflow: hidden;
            }}
            .chart-card {{
                width: 100%;
                height: {height}px;
                background: {t["card_bg"]};
                border: 1px solid {t["border_color"]};
                border-radius: 12px;
                box-shadow: {t["box_shadow"]};
                position: relative;
                display: flex;
                flex-direction: column;
            }}
            .chart-header {{
                display: flex;
                justify-content: space-between;
                align-items: flex-start;
                padding: 12px 18px 4px 18px;
                gap: 12px;
                flex-shrink: 0;
            }}
            .chart-title-area {{
                flex: 1;
                min-width: 0;
            }}
            .chart-title {{
                font-size: 17px;
                font-weight: 700;
                color: {t["title_color"]};
                line-height: 1.35;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
            }}
            .chart-subtitle {{
                font-size: 13px;
                color: {t["subtitle_color"]};
                margin-top: 2px;
                line-height: 1.3;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
            }}
            .chart-body {{
                width: 100%;
                flex: 1;
                min-height: 0;
            }}
        </style>
    </head>
    <body>
        <div class="chart-card">
            <div class="chart-header">
                <div class="chart-title-area">
                    <div class="chart-title">{symbol} 支出与成本构成 (Expense Breakdown)</div>
                    <div class="chart-subtitle">{subtext_str}</div>
                </div>
            </div>
            <div id="donut_chart" class="chart-body"></div>
        </div>
        <script>
            function formatLargeNum(val) {{
                if (val === null || val === undefined || isNaN(val)) return 'N/A';
                const absVal = Math.abs(val);
                const sign = val < 0 ? '-' : '';
                if (absVal >= 1e12) return sign + '$' + (absVal / 1e12).toFixed(2) + ' T';
                if (absVal >= 1e9) return sign + '$' + (absVal / 1e9).toFixed(2) + ' B';
                if (absVal >= 1e6) return sign + '$' + (absVal / 1e6).toFixed(2) + ' M';
                if (absVal >= 1e3) return sign + '$' + (absVal / 1e3).toFixed(1) + ' K';
                return sign + '$' + absVal.toFixed(0);
            }}

            const chartData = {items_json};
            const totalExp = {total_exp};
            const revBase = {rev_base if rev_base else 0.0};

            const chart = echarts.init(document.getElementById('donut_chart'), '{t["echarts_theme"]}');
            const option = {{
                backgroundColor: '{t["card_bg"]}',
                tooltip: {{
                    trigger: 'item',
                    backgroundColor: '{t["tooltip_bg"]}',
                    borderColor: '{t["tooltip_border"]}',
                    borderWidth: 1,
                    textStyle: {{ color: '{t["tooltip_text"]}', fontSize: 14 }},
                    formatter: function(params) {{
                        const d = params.data;
                        const shareOfExp = totalExp > 0 ? ((d.value / totalExp) * 100).toFixed(1) : '0.0';
                        const shareOfRev = revBase > 0 ? ((d.value / revBase) * 100).toFixed(1) : '0.0';
                        return '<div style="font-weight:700; margin-bottom:4px; font-size:15px; color:{t["tooltip_text"]};">' + (d.full_name || d.name) + '</div>'
                            + '<div style="color:{t["subtitle_color"]}; font-size:14px;">金额: <b style="color:{t["title_color"]};">' + formatLargeNum(d.value) + '</b></div>'
                            + '<div style="color:{t["subtitle_color"]}; font-size:14px;">占总支出比例: <b style="color:#38bdf8;">' + shareOfExp + '%</b></div>'
                            + (revBase > 0 ? '<div style="color:{t["subtitle_color"]}; font-size:14px;">占营业总收入: <b style="color:#fbbf24;">' + shareOfRev + '%</b></div>' : '');
                    }}
                }},
                legend: {{
                    orient: 'vertical',
                    right: '15px',
                    top: 'middle',
                    textStyle: {{ color: '{t["legend_text"]}', fontSize: 13 }},
                    formatter: function(name) {{
                        const item = chartData.find(d => d.name === name);
                        if (!item) return name;
                        const pct = totalExp > 0 ? ((item.value / totalExp) * 100).toFixed(1) + '%' : '';
                        return name + ' ' + formatLargeNum(item.value) + ' (' + pct + ')';
                    }}
                }},
                color: ['#38bdf8', '#818cf8', '#c084fc', '#f472b6', '#fb923c', '#facc15', '#4ade80', '#2dd4bf'],
                series: [{{
                    name: '支出科目',
                    type: 'pie',
                    radius: ['42%', '68%'],
                    center: ['32%', '56%'],
                    avoidLabelOverlap: true,
                    itemStyle: {{
                        borderRadius: 8,
                        borderColor: '{t["card_bg"]}',
                        borderWidth: 2
                    }},
                    label: {{
                        show: true,
                        formatter: '{{b}}\\n{{d}}%',
                        fontSize: 13,
                        color: '{t["text_color"]}'
                    }},
                    labelLine: {{
                        smooth: 0.2,
                        length: 8,
                        length2: 10
                    }},
                    data: chartData
                }}]
            }};
            chart.setOption(option);
            window.addEventListener('resize', () => chart.resize());
        </script>
    </body>
    </html>
    """
    components.html(html_code, height=height + 25, scrolling=False)
    return True


# ------------------------------------------------------------------
# 24. 动态自适应利润流向瀑布图 (P&L Waterfall Chart)
# ------------------------------------------------------------------
def render_echarts_pl_waterfall(total_revenue: float, expense_dict: dict, net_income: float, symbol: str = "", height: int = 380):
    """
    使用 Apache ECharts 渲染营收至净利润流向瀑布图 (P&L Waterfall Chart)
    """
    t = get_chart_theme_tokens()
    if total_revenue <= 0:
        st.info("总营收数据暂不可用，无法生成瀑布图。")
        return False

    categories = ["营业总收入"]
    base_data = [0]
    val_data = [{
        "value": round(total_revenue, 2),
        "rawVal": round(total_revenue, 2),
        "type": "rev",
        "itemStyle": {"color": "#38bdf8", "borderRadius": [4, 4, 0, 0]}
    }]

    running_val = float(total_revenue)
    if expense_dict:
        for k, v in expense_dict.items():
            try:
                v_flt = float(v)
                if v_flt > 0:
                    short_k = k.split("(")[0].strip() if "(" in k else str(k)[:8]
                    categories.append(short_k)
                    next_val = running_val - v_flt
                    base_data.append(round(max(0, next_val), 2))
                    val_data.append({
                        "value": round(v_flt, 2),
                        "rawVal": round(-v_flt, 2),
                        "full_name": str(k),
                        "type": "exp",
                        "itemStyle": {"color": "#ef4444", "borderRadius": [4, 4, 0, 0]}
                    })
                    running_val = next_val
            except (ValueError, TypeError):
                continue

    categories.append("净利润")
    base_data.append(0)
    val_data.append({
        "value": round(abs(net_income), 2),
        "rawVal": round(net_income, 2),
        "full_name": "最终净利润 (Net Income)",
        "type": "ni",
        "itemStyle": {
            "color": "#10b981" if net_income >= 0 else "#ef4444",
            "borderRadius": [4, 4, 0, 0]
        }
    })

    categories_json = json.dumps(categories, ensure_ascii=False)
    base_data_json = json.dumps(base_data)
    val_data_json = json.dumps(val_data, ensure_ascii=False)

    net_margin_pct = (net_income / total_revenue) * 100.0 if total_revenue > 0 else 0.0
    subtext_str = f"总营收: ${total_revenue:,.0f} → 净利润: ${net_income:,.0f} (净利率: {net_margin_pct:+.1f}%)"

    html_code = f"""
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <script src="https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"></script>
        <style>
            * {{ box-sizing: border-box; }}
            body {{
                margin: 0;
                padding: 0;
                background-color: {t["body_bg"]};
                color: {t["text_color"]};
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
                overflow: hidden;
            }}
            .chart-card {{
                width: 100%;
                height: {height}px;
                background: {t["card_bg"]};
                border: 1px solid {t["border_color"]};
                border-radius: 12px;
                box-shadow: {t["box_shadow"]};
                position: relative;
                display: flex;
                flex-direction: column;
            }}
            .chart-header {{
                display: flex;
                justify-content: space-between;
                align-items: flex-start;
                padding: 12px 18px 4px 18px;
                gap: 12px;
                flex-shrink: 0;
            }}
            .chart-title-area {{
                flex: 1;
                min-width: 0;
            }}
            .chart-title {{
                font-size: 17px;
                font-weight: 700;
                color: {t["title_color"]};
                line-height: 1.35;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
            }}
            .chart-subtitle {{
                font-size: 13px;
                color: {t["subtitle_color"]};
                margin-top: 2px;
                line-height: 1.3;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
            }}
            .chart-body {{
                width: 100%;
                flex: 1;
                min-height: 0;
            }}
        </style>
    </head>
    <body>
        <div class="chart-card">
            <div class="chart-header">
                <div class="chart-title-area">
                    <div class="chart-title">{symbol} 营收至净利润流向瀑布图 (P&L Flow)</div>
                    <div class="chart-subtitle">{subtext_str}</div>
                </div>
            </div>
            <div id="wf_chart" class="chart-body"></div>
        </div>
        <script>
            function formatLargeNum(val) {{
                if (val === null || val === undefined || isNaN(val)) return 'N/A';
                const absVal = Math.abs(val);
                const sign = val < 0 ? '-' : '';
                if (absVal >= 1e12) return sign + '$' + (absVal / 1e12).toFixed(2) + ' T';
                if (absVal >= 1e9) return sign + '$' + (absVal / 1e9).toFixed(2) + ' B';
                if (absVal >= 1e6) return sign + '$' + (absVal / 1e6).toFixed(2) + ' M';
                if (absVal >= 1e3) return sign + '$' + (absVal / 1e3).toFixed(1) + ' K';
                return sign + '$' + absVal.toFixed(0);
            }}

            const revBase = {total_revenue};
            const categories = {categories_json};
            const baseData = {base_data_json};
            const valData = {val_data_json};

            const chart = echarts.init(document.getElementById('wf_chart'), '{t["echarts_theme"]}');
            const option = {{
                backgroundColor: '{t["card_bg"]}',
                tooltip: {{
                    trigger: 'axis',
                    axisPointer: {{ type: 'shadow' }},
                    backgroundColor: '{t["tooltip_bg"]}',
                    borderColor: '{t["tooltip_border"]}',
                    borderWidth: 1,
                    textStyle: {{ color: '{t["tooltip_text"]}', fontSize: 14 }},
                    formatter: function(params) {{
                        const item = params.find(p => p.seriesName === '流向金额');
                        if (!item) return '';
                        const d = item.data;
                        let desc = '';
                        if (d.type === 'rev') desc = '营收基准起点';
                        else if (d.type === 'exp') desc = '成本费用扣除';
                        else if (d.type === 'ni') desc = '最终留存净利润';
                        const pct = revBase > 0 ? ((Math.abs(d.rawVal) / revBase) * 100).toFixed(1) + '%' : '';
                        const titleName = d.full_name || item.name;
                        return '<div style="font-weight:700; font-size:15px; margin-bottom:4px; color:{t["tooltip_text"]};">' + titleName + ' (' + desc + ')</div>'
                            + '<div style="font-size:14px; color:{t["subtitle_color"]};">发生金额: <b style="color:' + item.color + ';">' + (d.rawVal < 0 ? '-' : '') + formatLargeNum(Math.abs(d.rawVal)) + '</b></div>'
                            + (revBase > 0 ? '<div style="font-size:14px; color:{t["subtitle_color"]};">占总营收比重: <b style="color:{t["title_color"]};">' + pct + '</b></div>' : '');
                    }}
                }},
                grid: {{
                    left: '60px', right: '35px', top: '35px', bottom: '45px'
                }},
                xAxis: {{
                    type: 'category',
                    data: categories,
                    axisLabel: {{ color: '{t["axis_label"]}', fontSize: 13, interval: 0 }},
                    axisLine: {{ lineStyle: {{ color: '{t["axis_line"]}' }} }}
                }},
                yAxis: {{
                    type: 'value',
                    scale: true,
                    axisLabel: {{
                        color: '{t["axis_label"]}', fontSize: 14,
                        formatter: function(val) {{ return formatLargeNum(val); }}
                    }},
                    splitLine: {{ lineStyle: {{ color: '{t["split_line"]}' }} }}
                }},
                series: [
                    {{
                        name: '基底占位',
                        type: 'bar',
                        stack: 'Total',
                        itemStyle: {{ borderColor: 'transparent', color: 'transparent' }},
                        emphasis: {{ itemStyle: {{ borderColor: 'transparent', color: 'transparent' }} }},
                        data: baseData
                    }},
                    {{
                        name: '流向金额',
                        type: 'bar',
                        stack: 'Total',
                        label: {{
                            show: true,
                            position: 'top',
                            fontSize: 13,
                            color: '{t["text_color"]}',
                            formatter: function(params) {{
                                const d = params.data;
                                return (d.rawVal < 0 ? '-' : '') + formatLargeNum(Math.abs(d.rawVal));
                            }}
                        }},
                        data: valData
                    }}
                ]
            }};
            chart.setOption(option);
            window.addEventListener('resize', () => chart.resize());
        </script>
    </body>
    </html>
    """
    components.html(html_code, height=height + 25, scrolling=False)
    return True


# ------------------------------------------------------------------
# 25. Chandelier 动态吊灯多头追踪止损与波动率挤压走势图
# ------------------------------------------------------------------
def render_echarts_chandelier_risk(df_metrics: pd.DataFrame, symbol: str = "", timeframe: str = "1Y", height: int = 620):
    """
    使用 Apache ECharts 渲染股价、20MA 与 Chandelier 动态吊灯多头追踪止损、20D 均线偏离度与布林带带宽
    """
    t = get_chart_theme_tokens()
    if df_metrics is None or df_metrics.empty:
        st.warning("暂无微观量价动量与止损数据。")
        return False

    df = df_metrics.copy()
    if 'Date' in df.columns:
        date_col = 'Date'
        df[date_col] = pd.to_datetime(df[date_col])
    else:
        df = df.reset_index()
        date_col = df.columns[0]
        df[date_col] = pd.to_datetime(df[date_col])

    df = filter_by_timeframe(df, date_col, timeframe)
    if df.empty:
        st.warning("所选时间窗口内暂无有效数据。")
        return False

    df = df.sort_values(date_col)
    dates = df[date_col].dt.strftime('%Y-%m-%d').tolist()

    close_vals = [round(float(v), 2) if pd.notna(v) else None for v in df['Close']]

    ma20 = df['Close'].rolling(20).mean()
    ma20_vals = [round(float(v), 2) if pd.notna(v) else None for v in ma20]

    ch_col = 'Chandelier_Exit' if 'Chandelier_Exit' in df.columns else None
    ch_vals = [round(float(v), 2) if (ch_col and pd.notna(v)) else None for v in df.get(ch_col, [None]*len(df))]

    bias_col = 'Bias20' if 'Bias20' in df.columns else None
    bias_vals = [round(float(v), 2) if (bias_col and pd.notna(v)) else None for v in df.get(bias_col, [None]*len(df))]

    bw_col = 'BandWidth' if 'BandWidth' in df.columns else None
    bw_vals = [round(float(v), 2) if (bw_col and pd.notna(v)) else None for v in df.get(bw_col, [None]*len(df))]

    # Format Bias bars with dynamic colors
    bias_series_data = []
    for b in bias_vals:
        if b is not None:
            c = "#10b981" if b >= 0 else "#ef4444"
            bias_series_data.append({"value": b, "itemStyle": {"color": c}})
        else:
            bias_series_data.append(None)

    dates_json = json.dumps(dates)
    close_json = json.dumps(close_vals)
    ma20_json = json.dumps(ma20_vals)
    ch_json = json.dumps(ch_vals)
    bias_json = json.dumps(bias_series_data)
    bw_json = json.dumps(bw_vals)

    html_code = f"""
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <script src="https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"></script>
        <style>
            * {{ box-sizing: border-box; }}
            body {{
                margin: 0;
                padding: 0;
                background-color: {t["body_bg"]};
                color: {t["text_color"]};
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
                overflow: hidden;
            }}
            .chart-card {{
                width: 100%;
                height: {height}px;
                background: {t["card_bg"]};
                border: 1px solid {t["border_color"]};
                border-radius: 12px;
                box-shadow: {t["box_shadow"]};
                position: relative;
                display: flex;
                flex-direction: column;
            }}
            .chart-header {{
                display: flex;
                justify-content: space-between;
                align-items: flex-start;
                padding: 12px 18px 4px 18px;
                gap: 12px;
                flex-shrink: 0;
            }}
            .chart-title-area {{
                flex: 1;
                min-width: 0;
            }}
            .chart-title {{
                font-size: 17px;
                font-weight: 700;
                color: {t["title_color"]};
                line-height: 1.35;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
            }}
            .chart-subtitle {{
                font-size: 13px;
                color: {t["subtitle_color"]};
                margin-top: 2px;
                line-height: 1.3;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
            }}
            .chart-body {{
                width: 100%;
                flex: 1;
                min-height: 0;
            }}
        </style>
    </head>
    <body>
        <div class="chart-card">
            <div class="chart-header">
                <div class="chart-title-area">
                    <div class="chart-title">{symbol} 股价、20MA 与 Chandelier 动态吊灯多头追踪止损位</div>
                    <div class="chart-subtitle">上栏: 价格与 ATR 动态吊灯止损位 ($) · 下栏: 20D 均线偏离度 (Bias %) 与布林带带宽 (BandWidth %)</div>
                </div>
            </div>
            <div id="chandelier_chart" class="chart-body"></div>
        </div>
        <script>
            const dates = {dates_json};
            const closeVals = {close_json};
            const ma20Vals = {ma20_json};
            const chVals = {ch_json};
            const biasVals = {bias_json};
            const bwVals = {bw_json};

            const chart = echarts.init(document.getElementById('chandelier_chart'), '{t["echarts_theme"]}');
            const option = {{
                backgroundColor: '{t["card_bg"]}',
                tooltip: {{
                    trigger: 'axis',
                    axisPointer: {{
                        type: 'cross',
                        crossStyle: {{ color: '{t["axis_label"]}' }},
                        lineStyle: {{ color: 'rgba(56, 189, 248, 0.4)', width: 1.5 }}
                    }},
                    backgroundColor: '{t["tooltip_bg"]}',
                    borderColor: '{t["tooltip_border"]}',
                    borderWidth: 1,
                    textStyle: {{ color: '{t["tooltip_text"]}', fontSize: 14 }},
                    formatter: function(params) {{
                        if (!params || !params.length) return '';
                        const date = params[0].name;
                        let html = '<div style="font-weight:700; margin-bottom:6px; font-size:15px; color:{t["tooltip_text"]};">' + date + '</div>';
                        let close = null, ma20 = null, chandelier = null, bias = null, bw = null;
                        params.forEach(p => {{
                            if (p.seriesName === '收盘价') close = p.value;
                            else if (p.seriesName === '20MA 均线') ma20 = p.value;
                            else if (p.seriesName === 'Chandelier 动态止损') chandelier = p.value;
                            else if (p.seriesName.includes('Bias') || p.seriesName.includes('偏离度')) bias = (typeof p.value === 'object' && p.value !== null) ? p.value.value : p.value;
                            else if (p.seriesName.includes('BandWidth') || p.seriesName.includes('带宽')) bw = p.value;
                        }});
                        if (close !== null && close !== undefined) {{
                            html += '<div style="font-size:14px; color:{t["subtitle_color"]};">收盘价: <b style="color:#38bdf8;">$' + Number(close).toFixed(2) + '</b></div>';
                        }}
                        if (ma20 !== null && ma20 !== undefined) {{
                            html += '<div style="font-size:14px; color:{t["subtitle_color"]};">20MA 均线: <b style="color:#f59e0b;">$' + Number(ma20).toFixed(2) + '</b></div>';
                        }}
                        if (chandelier !== null && chandelier !== undefined) {{
                            const buf = (close && close > 0) ? (((chandelier - close) / close) * 100).toFixed(1) : 'N/A';
                            html += '<div style="font-size:14px; color:{t["subtitle_color"]};">Chandelier 止损: <b style="color:#ef4444;">$' + Number(chandelier).toFixed(2) + '</b> <span style="font-size:12px; color:#ef4444;">(缓冲 ' + buf + '%)</span></div>';
                        }}
                        if (bias !== null && bias !== undefined) {{
                            const bColor = bias >= 0 ? '#10b981' : '#ef4444';
                            html += '<div style="font-size:14px; color:{t["subtitle_color"]};">20D 偏离度: <b style="color:' + bColor + ';">' + (bias >= 0 ? '+' : '') + Number(bias).toFixed(2) + '%</b></div>';
                        }}
                        if (bw !== null && bw !== undefined) {{
                            html += '<div style="font-size:14px; color:{t["subtitle_color"]};">布林带带宽: <b style="color:#c084fc;">' + Number(bw).toFixed(1) + '%</b></div>';
                        }}
                        return html;
                    }}
                }},
                legend: {{
                    data: ['收盘价', '20MA 均线', 'Chandelier 动态止损', '20D 偏离度 (%)', '布林带带宽 (%)'],
                    top: '6px',
                    left: 'center',
                    type: 'scroll',
                    textStyle: {{ color: '{t["legend_text"]}', fontSize: 13 }},
                    itemGap: 14
                }},
                axisPointer: {{
                    link: [{{ xAxisIndex: 'all' }}]
                }},
                grid: [
                    {{ left: '65px', right: '65px', top: '46px', height: '50%' }},
                    {{ left: '65px', right: '65px', top: '66%', height: '22%' }}
                ],
                xAxis: [
                    {{
                        type: 'category', gridIndex: 0, data: dates,
                        axisLabel: {{ show: false }},
                        axisLine: {{ lineStyle: {{ color: '{t["axis_line"]}' }} }},
                        splitLine: {{ show: false }}
                    }},
                    {{
                        type: 'category', gridIndex: 1, data: dates,
                        axisLabel: {{ color: '{t["axis_label"]}', fontSize: 13 }},
                        axisLine: {{ lineStyle: {{ color: '{t["axis_line"]}' }} }},
                        splitLine: {{ show: false }}
                    }}
                ],
                yAxis: [
                    {{
                        type: 'value', gridIndex: 0, scale: true,
                        name: '价格 ($)',
                        nameTextStyle: {{ color: '{t["axis_label"]}', fontSize: 14 }},
                        axisLabel: {{ color: '{t["axis_label"]}', fontSize: 13, formatter: '${{value}}' }},
                        splitLine: {{ lineStyle: {{ color: '{t["split_line"]}' }} }}
                    }},
                    {{
                        type: 'value', gridIndex: 1, scale: true,
                        name: '偏离度 (%)',
                        nameTextStyle: {{ color: '{t["axis_label"]}', fontSize: 14 }},
                        axisLabel: {{ color: '{t["axis_label"]}', fontSize: 13, formatter: '{{value}}%' }},
                        splitLine: {{ lineStyle: {{ color: '{t["split_line"]}' }} }}
                    }},
                    {{
                        type: 'value', gridIndex: 1, scale: true,
                        name: '带宽 (%)',
                        nameTextStyle: {{ color: '{t["axis_label"]}', fontSize: 14 }},
                        axisLabel: {{ color: '{t["axis_label"]}', fontSize: 13, formatter: '{{value}}%' }},
                        splitLine: {{ show: false }}
                    }}
                ],
                dataZoom: [
                    {{
                        type: 'inside', xAxisIndex: [0, 1],
                        start: 60, end: 100
                    }},
                    {{
                        type: 'slider', xAxisIndex: [0, 1],
                        bottom: '8px', height: 22,
                        backgroundColor: '{t["datazoom_bg"]}',
                        borderColor: '{t["datazoom_border"]}',
                        fillerColor: '{t["datazoom_filler"]}',
                        handleStyle: {{ color: '{t["datazoom_handle"]}' }},
                        textStyle: {{ color: '{t["axis_label"]}', fontSize: 12 }},
                        start: 60, end: 100
                    }}
                ],
                series: [
                    {{
                        name: '收盘价', type: 'line', xAxisIndex: 0, yAxisIndex: 0,
                        lineStyle: {{ color: '#38bdf8', width: 2 }},
                        itemStyle: {{ color: '#38bdf8' }},
                        showSymbol: false,
                        data: closeVals
                    }},
                    {{
                        name: '20MA 均线', type: 'line', xAxisIndex: 0, yAxisIndex: 0,
                        lineStyle: {{ color: '#f59e0b', width: 1.6, type: 'dashed' }},
                        itemStyle: {{ color: '#f59e0b' }},
                        showSymbol: false,
                        data: ma20Vals
                    }},
                    {{
                        name: 'Chandelier 动态止损', type: 'line', xAxisIndex: 0, yAxisIndex: 0,
                        lineStyle: {{ color: '#ef4444', width: 2.2, type: 'dotted' }},
                        itemStyle: {{ color: '#ef4444' }},
                        showSymbol: false,
                        data: chVals
                    }},
                    {{
                        name: '20D 偏离度 (%)', type: 'bar', xAxisIndex: 1, yAxisIndex: 1,
                        data: biasVals,
                        markLine: {{
                            silent: true,
                            symbol: 'none',
                            data: [
                                {{
                                    yAxis: 8.0,
                                    lineStyle: {{ color: '#ef4444', type: 'dashed', width: 1.5 }},
                                    label: {{ show: true, formatter: '+8% 过热', color: '#ef4444', fontSize: 12, position: 'end' }}
                                }},
                                {{
                                    yAxis: -8.0,
                                    lineStyle: {{ color: '#10b981', type: 'dashed', width: 1.5 }},
                                    label: {{ show: true, formatter: '-8% 反弹', color: '#10b981', fontSize: 12, position: 'end' }}
                                }}
                            ]
                        }}
                    }},
                    {{
                        name: '布林带带宽 (%)', type: 'line', xAxisIndex: 1, yAxisIndex: 2,
                        lineStyle: {{ color: '#c084fc', width: 2 }},
                        itemStyle: {{ color: '#c084fc' }},
                        showSymbol: false,
                        data: bwVals
                    }}
                ]
            }};
            chart.setOption(option);
            window.addEventListener('resize', () => chart.resize());
        </script>
    </body>
    </html>
    """
    components.html(html_code, height=height + 25, scrolling=False)
    return True


# ------------------------------------------------------------------
# 26. 标普 500 市场宽度分析折线图 (Market Breadth)
# ------------------------------------------------------------------
def render_echarts_market_breadth(df_breadth: pd.DataFrame = None, height: int = 480):
    """
    使用 Apache ECharts 渲染标普 500 市场宽度分析图 (% > 20MA / 50MA / 200MA)
    """
    t = get_chart_theme_tokens()
    if df_breadth is None or df_breadth.empty:
        try:
            from market_breadth_viz import load_market_breadth_data
            df_breadth = load_market_breadth_data()
        except Exception:
            pass

    if df_breadth is None or df_breadth.empty:
        st.warning("暂无标普 500 市场宽度数据。")
        return False

    df = df_breadth.copy()
    date_col = 'date' if 'date' in df.columns else df.columns[0]
    df[date_col] = pd.to_datetime(df[date_col])
    df = df.sort_values(date_col)

    dates = df[date_col].dt.strftime('%Y-%m-%d').tolist()
    v20 = [round(float(v), 2) if pd.notna(v) else None for v in df.get('pct_above_20ma', [])]
    v50 = [round(float(v), 2) if pd.notna(v) else None for v in df.get('pct_above_50ma', [])]
    v200 = [round(float(v), 2) if pd.notna(v) else None for v in df.get('pct_above_200ma', [])]

    dates_json = json.dumps(dates)
    v20_json = json.dumps(v20)
    v50_json = json.dumps(v50)
    v200_json = json.dumps(v200)

    html_code = f"""
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <script src="https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"></script>
        <style>
            * {{ box-sizing: border-box; }}
            body {{
                margin: 0;
                padding: 0;
                background-color: {t["body_bg"]};
                color: {t["text_color"]};
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
                overflow: hidden;
            }}
            .chart-card {{
                width: 100%;
                height: {height}px;
                background: {t["card_bg"]};
                border: 1px solid {t["border_color"]};
                border-radius: 12px;
                box-shadow: {t["box_shadow"]};
                position: relative;
                display: flex;
                flex-direction: column;
            }}
            .chart-header {{
                display: flex;
                justify-content: space-between;
                align-items: flex-start;
                padding: 12px 18px 4px 18px;
                gap: 12px;
                flex-shrink: 0;
            }}
            .chart-title-area {{
                flex: 1;
                min-width: 0;
            }}
            .chart-title {{
                font-size: 17px;
                font-weight: 700;
                color: {t["title_color"]};
                line-height: 1.35;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
            }}
            .chart-subtitle {{
                font-size: 13px;
                color: {t["subtitle_color"]};
                margin-top: 2px;
                line-height: 1.3;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
            }}
            .chart-body {{
                width: 100%;
                flex: 1;
                min-height: 0;
            }}
        </style>
    </head>
    <body>
        <div class="chart-card">
            <div class="chart-header">
                <div class="chart-title-area">
                    <div class="chart-title">S&P 500 市场宽度分析 (Market Breadth)</div>
                    <div class="chart-subtitle">成分股高于各均线比例 (%) · 80% 超买红线与 20% 超卖绿线区域透视</div>
                </div>
            </div>
            <div id="breadth_chart" class="chart-body"></div>
        </div>
        <script>
            const dates = {dates_json};
            const v20 = {v20_json};
            const v50 = {v50_json};
            const v200 = {v200_json};

            const chart = echarts.init(document.getElementById('breadth_chart'), '{t["echarts_theme"]}');
            const option = {{
                backgroundColor: '{t["card_bg"]}',
                tooltip: {{
                    trigger: 'axis',
                    axisPointer: {{
                        type: 'cross',
                        crossStyle: {{ color: '{t["axis_label"]}' }},
                        lineStyle: {{ color: 'rgba(56, 189, 248, 0.4)', width: 1.5 }}
                    }},
                    backgroundColor: '{t["tooltip_bg"]}',
                    borderColor: '{t["tooltip_border"]}',
                    borderWidth: 1,
                    textStyle: {{ color: '{t["tooltip_text"]}', fontSize: 14 }},
                    formatter: function(params) {{
                        if (!params || !params.length) return '';
                        let html = '<div style="font-weight:700; margin-bottom:6px; font-size:15px; color:{t["tooltip_text"]};">' + params[0].name + '</div>';
                        params.forEach(p => {{
                            if (p.value !== null && p.value !== undefined) {{
                                html += '<div style="font-size:14px; color:{t["subtitle_color"]};">' + p.seriesName + ': <b style="color:' + p.color + ';">' + Number(p.value).toFixed(1) + '%</b></div>';
                            }}
                        }});
                        return html;
                    }}
                }},
                legend: {{
                    data: ['% > 20MA (短期动能)', '% > 50MA (中期趋势)', '% > 200MA (长期牛熊)'],
                    top: '6px',
                    left: 'center',
                    type: 'scroll',
                    textStyle: {{ color: '{t["legend_text"]}', fontSize: 13 }},
                    itemGap: 16
                }},
                grid: {{
                    left: '60px', right: '35px', top: '44px', bottom: '65px'
                }},
                xAxis: {{
                    type: 'category',
                    data: dates,
                    axisLabel: {{ color: '{t["axis_label"]}', fontSize: 13 }},
                    axisLine: {{ lineStyle: {{ color: '{t["axis_line"]}' }} }}
                }},
                yAxis: {{
                    type: 'value',
                    min: 0, max: 100,
                    axisLabel: {{ color: '{t["axis_label"]}', fontSize: 13, formatter: '{{value}}%' }},
                    splitLine: {{ lineStyle: {{ color: '{t["split_line"]}' }} }}
                }},
                dataZoom: [
                    {{
                        type: 'inside',
                        start: Math.max(0, 100 - Math.min(100, (750 / Math.max(1, dates.length)) * 100)),
                        end: 100
                    }},
                    {{
                        type: 'slider',
                        bottom: '12px', height: 24,
                        backgroundColor: '{t["datazoom_bg"]}',
                        borderColor: '{t["datazoom_border"]}',
                        fillerColor: '{t["datazoom_filler"]}',
                        handleStyle: {{ color: '{t["datazoom_handle"]}' }},
                        textStyle: {{ color: '{t["axis_label"]}', fontSize: 12 }},
                        start: Math.max(0, 100 - Math.min(100, (750 / Math.max(1, dates.length)) * 100)),
                        end: 100
                    }}
                ],
                series: [
                    {{
                        name: '% > 20MA (短期动能)',
                        type: 'line',
                        data: v20,
                        lineStyle: {{ color: '#38bdf8', width: 2 }},
                        itemStyle: {{ color: '#38bdf8' }},
                        showSymbol: false,
                        markArea: {{
                            silent: true,
                            data: [
                                [
                                    {{ yAxis: 80, itemStyle: {{ color: 'rgba(239, 68, 68, 0.08)' }} }},
                                    {{ yAxis: 100 }}
                                ],
                                [
                                    {{ yAxis: 0, itemStyle: {{ color: 'rgba(16, 185, 129, 0.08)' }} }},
                                    {{ yAxis: 20 }}
                                ]
                            ]
                        }},
                        markLine: {{
                            silent: true,
                            symbol: 'none',
                            data: [
                                {{
                                    yAxis: 80,
                                    lineStyle: {{ color: 'rgba(239, 68, 68, 0.7)', type: 'dashed', width: 1.5 }},
                                    label: {{ show: true, formatter: '80% 超买', color: '#ef4444', fontSize: 13, position: 'insideStartTop' }}
                                }},
                                {{
                                    yAxis: 50,
                                    lineStyle: {{ color: 'rgba(148, 163, 184, 0.5)', type: 'dashed', width: 1.2 }},
                                    label: {{ show: true, formatter: '50% 多空分界', color: '#94a3b8', fontSize: 13, position: 'insideStartTop' }}
                                }},
                                {{
                                    yAxis: 20,
                                    lineStyle: {{ color: 'rgba(16, 185, 129, 0.7)', type: 'dashed', width: 1.5 }},
                                    label: {{ show: true, formatter: '20% 超卖', color: '#10b981', fontSize: 13, position: 'insideStartTop' }}
                                }}
                            ]
                        }}
                    }},
                    {{
                        name: '% > 50MA (中期趋势)',
                        type: 'line',
                        data: v50,
                        lineStyle: {{ color: '#fbbf24', width: 2.2 }},
                        itemStyle: {{ color: '#fbbf24' }},
                        showSymbol: false
                    }},
                    {{
                        name: '% > 200MA (长期牛熊)',
                        type: 'line',
                        data: v200,
                        lineStyle: {{ color: '#f43f5e', width: 2.5 }},
                        itemStyle: {{ color: '#f43f5e' }},
                        showSymbol: false
                    }}
                ]
            }};
            chart.setOption(option);
            window.addEventListener('resize', () => chart.resize());
        </script>
    </body>
    </html>
    """
    components.html(html_code, height=height + 25, scrolling=False)
    return True


# ------------------------------------------------------------------
# 27. 中金胜率-赔率四象限 2D 气泡图 (CICC Quadrant Bubble Chart)
# ------------------------------------------------------------------
def render_echarts_cicc_quadrant(
    df_quadrant: pd.DataFrame,
    selected_category: str = "🌟 全量 23 个板块全景",
    render_theme: str = "💎「璀璨光晕」霓虹琉璃 (推荐)",
    height: int = 760
):
    """
    使用 Apache ECharts 渲染中金胜率-赔率四象限资产配置气泡图
    """
    t = get_chart_theme_tokens()
    if df_quadrant is None or df_quadrant.empty:
        st.warning("暂无四象限配置数据。")
        return False

    df = df_quadrant.copy()
    if selected_category and "全量" not in selected_category and "全部" not in selected_category and "跨资产" not in selected_category:
        df = df[df['category'] == selected_category]

    if df.empty:
        st.info("所选分类下暂无资产标的。")
        return False

    sym_col = 'ticker' if 'ticker' in df.columns else 'symbol'
    name_col = 'name' if 'name' in df.columns else sym_col
    cat_col = 'category' if 'category' in df.columns else 'quadrant'

    # Curated category palette
    cat_colors = {
        "核心权益/宏观指数": "#38bdf8",
        "科技与先导成长": "#818cf8",
        "周期/防御与红利": "#34d399",
        "固收与信用债": "#fbbf24",
        "大宗商品与外汇": "#f43f5e",
        "全品类宏观大类资产": "#38bdf8",
        "美国核心行业与红利": "#a855f7",
        "成长/价值风格因子": "#06b6d4",
    }
    fallback_colors = ["#38bdf8", "#818cf8", "#34d399", "#fbbf24", "#f43f5e", "#a855f7", "#06b6d4", "#fb923c"]

    categories = sorted(list(df[cat_col].unique()))
    series_list = []

    for idx, cat in enumerate(categories):
        sub_df = df[df[cat_col] == cat]
        data_points = []
        for _, r in sub_df.iterrows():
            win = round(float(r['win_score']), 4) if pd.notna(r.get('win_score')) else 0.55
            odds = round(float(r['odds_score']), 4) if pd.notna(r.get('odds_score')) else 0.50
            comp = round(float(r.get('composite_score', 50.0)), 1)
            sym = str(r[sym_col])
            name = str(r.get(name_col, sym))
            val_tag = str(r.get('valuation_tag', ''))
            mom = round(float(r.get('mom_12_1', 0.0)), 1) if pd.notna(r.get('mom_12_1')) else None
            data_points.append({
                "value": [win, odds, comp, sym, name, val_tag, mom],
                "name": sym
            })

        c = cat_colors.get(cat, fallback_colors[idx % len(fallback_colors)])
        series_obj = {
            "name": cat,
            "type": "scatter",
            "data": data_points,
            "itemStyle": {
                "color": c,
                "shadowBlur": 10,
                "shadowColor": c + "66"
            },
            "label": {
                "show": True,
                "position": "inside",
                "formatter": "{b}",
                "fontSize": 12,
                "fontWeight": "bold",
                "color": "#ffffff"
            }
        }
        series_list.append(series_obj)

    series_json = json.dumps(series_list, ensure_ascii=False)
    cat_names_json = json.dumps(categories, ensure_ascii=False)

    html_code = f"""
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <script src="https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"></script>
        <style>
            * {{ box-sizing: border-box; }}
            body {{
                margin: 0;
                padding: 0;
                background-color: {t["body_bg"]};
                color: {t["text_color"]};
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
                overflow: hidden;
            }}
            .chart-card {{
                width: 100%;
                height: {height}px;
                background: {t["card_bg"]};
                border: 1px solid {t["border_color"]};
                border-radius: 12px;
                box-shadow: {t["box_shadow"]};
                position: relative;
                display: flex;
                flex-direction: column;
            }}
            .chart-header {{
                display: flex;
                justify-content: space-between;
                align-items: flex-start;
                padding: 12px 18px 4px 18px;
                gap: 12px;
                flex-shrink: 0;
            }}
            .chart-title-area {{
                flex: 1;
                min-width: 0;
            }}
            .chart-title {{
                font-size: 17px;
                font-weight: 700;
                color: {t["title_color"]};
                line-height: 1.35;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
            }}
            .chart-subtitle {{
                font-size: 13px;
                color: {t["subtitle_color"]};
                margin-top: 2px;
                line-height: 1.3;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
            }}
            .chart-body {{
                width: 100%;
                flex: 1;
                min-height: 0;
            }}
            .quad-watermark {{
                position: absolute; pointer-events: none; padding: 6px 12px;
                border-radius: 6px; font-weight: 700; z-index: 10;
                backdrop-filter: blur(4px); font-size: 13px;
            }}
        </style>
    </head>
    <body>
        <div class="chart-card">
            <div class="chart-header">
                <div class="chart-title-area">
                    <div class="chart-title">中金胜率 - 赔率四象限资产配置全景雷达 (CICC Quadrant Strategy)</div>
                    <div class="chart-subtitle">横轴: 宏观胜率 (0.35~0.85, 中枢 55%) · 纵轴: 估值赔率 (-0.05~1.10, 中枢 0.50) · 气泡大小与综合评分绑定</div>
                </div>
            </div>
            <div id="cicc_chart" class="chart-body"></div>
            <!-- Quadrant Watermarks -->
            <div class="quad-watermark" style="top: 85px; right: 55px; background: rgba(16, 185, 129, 0.12); color: #10b981; border: 1px solid rgba(16, 185, 129, 0.3);">
                【第一象限: 戴维斯双击】高胜率 + 高赔率 (核心超配)
            </div>
            <div class="quad-watermark" style="top: 85px; left: 85px; background: rgba(245, 158, 11, 0.12); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.3);">
                【第四象限: 价值洼地反转】低胜率 + 高赔率 (左侧分批定投)
            </div>
            <div class="quad-watermark" style="bottom: 75px; left: 85px; background: rgba(239, 68, 68, 0.12); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.3);">
                【第三象限: 戴维斯双杀】低胜率 + 低赔率 (坚决回避)
            </div>
            <div class="quad-watermark" style="bottom: 75px; right: 55px; background: rgba(168, 85, 247, 0.12); color: #c084fc; border: 1px solid rgba(168, 85, 247, 0.3);">
                【第二象限: 动量顺势】高胜率 + 低赔率 (顺势持有/紧设止损)
            </div>
        </div>
        <script>
            const seriesData = {series_json};
            const catNames = {cat_names_json};

            // Inject dynamic symbolSize function
            seriesData.forEach(s => {{
                s.symbolSize = function(val) {{
                    const score = val[2] || 50;
                    return Math.max(18, Math.min(52, score * 0.48));
                }};
            }});

            const chart = echarts.init(document.getElementById('cicc_chart'), '{t["echarts_theme"]}');
            const option = {{
                backgroundColor: '{t["card_bg"]}',
                tooltip: {{
                    trigger: 'item',
                    backgroundColor: '{t["tooltip_bg"]}',
                    borderColor: '{t["tooltip_border"]}',
                    borderWidth: 1,
                    textStyle: {{ color: '{t["tooltip_text"]}', fontSize: 14 }},
                    formatter: function(param) {{
                        const d = param.data.value;
                        if (!d) return '';
                        const winPct = (d[0] * 100).toFixed(1) + '%';
                        const oddsVal = Number(d[1]).toFixed(2);
                        const compScore = Number(d[2]).toFixed(1);
                        const ticker = d[3];
                        const name = d[4] || '';
                        const valTag = d[5] || '正常估值';
                        const mom = d[6] !== null && d[6] !== undefined ? ((d[6] >= 0 ? '+' : '') + d[6] + '%') : 'N/A';
                        return '<div style="font-weight:700; font-size:15px; margin-bottom:6px; color:{t["tooltip_text"]};">'
                            + ticker + (name ? ' (' + name + ')' : '') + ' <span style="font-size:12px; color:{t["subtitle_color"]}; font-weight:400;">[' + param.seriesName + ']</span></div>'
                            + '<div style="font-size:14px; color:{t["subtitle_color"]};">综合投资评分: <b style="color:#38bdf8;">' + compScore + ' 分</b></div>'
                            + '<div style="font-size:14px; color:{t["subtitle_color"]};">宏观胜率 (X轴): <b style="color:#10b981;">' + winPct + '</b></div>'
                            + '<div style="font-size:14px; color:{t["subtitle_color"]};">估值赔率 (Y轴): <b style="color:#fbbf24;">' + oddsVal + '</b></div>'
                            + '<div style="font-size:14px; color:{t["subtitle_color"]};">估值诊断状态: <b style="color:' + param.color + ';">' + valTag + '</b></div>'
                            + '<div style="font-size:14px; color:{t["subtitle_color"]};">12-1M 学术动量: <b style="color:#a855f7;">' + mom + '</b></div>';
                    }}
                }},
                legend: {{
                    data: catNames,
                    top: '6px',
                    left: 'center',
                    type: 'scroll',
                    textStyle: {{ color: '{t["legend_text"]}', fontSize: 13 }},
                    itemGap: 14
                }},
                grid: {{
                    left: '65px', right: '45px', top: '48px', bottom: '60px'
                }},
                xAxis: {{
                    type: 'value',
                    name: '宏观胜率 (Win Rate %)',
                    nameLocation: 'middle',
                    nameGap: 32,
                    nameTextStyle: {{ color: '{t["axis_label"]}', fontSize: 14, fontWeight: 600 }},
                    min: 0.35, max: 0.85,
                    axisLabel: {{
                        color: '{t["axis_label"]}', fontSize: 13,
                        formatter: function(val) {{ return (val * 100).toFixed(0) + '%'; }}
                    }},
                    axisLine: {{ lineStyle: {{ color: '{t["axis_line"]}' }} }},
                    splitLine: {{ lineStyle: {{ color: '{t["split_line"]}' }} }}
                }},
                yAxis: {{
                    type: 'value',
                    name: '估值赔率 (Odds Score)',
                    nameTextStyle: {{ color: '{t["axis_label"]}', fontSize: 14, fontWeight: 600 }},
                    min: -0.05, max: 1.12,
                    axisLabel: {{
                        color: '{t["axis_label"]}', fontSize: 13,
                        formatter: function(val) {{ return Number(val).toFixed(2); }}
                    }},
                    axisLine: {{ lineStyle: {{ color: '{t["axis_line"]}' }} }},
                    splitLine: {{ lineStyle: {{ color: '{t["split_line"]}' }} }}
                }},
                series: seriesData
            }};

            // Add background quadrant markArea & midline markLine to the first series
            if (option.series && option.series.length > 0) {{
                option.series[0].markArea = {{
                    silent: true,
                    data: [
                        // Q1: Top Right (Davis Double Play)
                        [
                            {{ coord: [0.55, 0.50], itemStyle: {{ color: 'rgba(16, 185, 129, 0.08)' }} }},
                            {{ coord: [0.85, 1.12] }}
                        ],
                        // Q2: Bottom Right (Momentum)
                        [
                            {{ coord: [0.55, -0.05], itemStyle: {{ color: 'rgba(168, 85, 247, 0.08)' }} }},
                            {{ coord: [0.85, 0.50] }}
                        ],
                        // Q3: Bottom Left (Davis Double Kill)
                        [
                            {{ coord: [0.35, -0.05], itemStyle: {{ color: 'rgba(239, 68, 68, 0.08)' }} }},
                            {{ coord: [0.55, 0.50] }}
                        ],
                        // Q4: Top Left (Deep Value Reversal)
                        [
                            {{ coord: [0.35, 0.50], itemStyle: {{ color: 'rgba(245, 158, 11, 0.08)' }} }},
                            {{ coord: [0.55, 1.12] }}
                        ]
                    ]
                }};
                option.series[0].markLine = {{
                    silent: true,
                    symbol: 'none',
                    lineStyle: {{ color: 'rgba(148, 163, 184, 0.6)', type: 'dashed', width: 1.6 }},
                    data: [
                        {{ xAxis: 0.55, label: {{ show: true, formatter: '胜率中枢 55%', color: '{t["subtitle_color"]}', fontSize: 12, position: 'end' }} }},
                        {{ yAxis: 0.50, label: {{ show: true, formatter: '赔率中枢 0.50', color: '{t["subtitle_color"]}', fontSize: 12, position: 'end' }} }}
                    ]
                }};
            }}

            chart.setOption(option);
            window.addEventListener('resize', () => chart.resize());
        </script>
    </body>
    </html>
    """
    components.html(html_code, height=height + 25, scrolling=False)
    return True


# ------------------------------------------------------------------
# 28. 黄文政相空间动力学相图 (Lagrangian Phase Portrait: q1 vs q1_dot)
# ------------------------------------------------------------------
def render_echarts_phase_portrait(df: pd.DataFrame, symbol: str = "NOW", height: int = 620):
    """
    使用 Apache ECharts 渲染二维拉格朗日相空间动力学相图
    横轴：状态位置 q1 (相对 200MA 偏离度 %)
    纵轴：状态速度 q1_dot (10日有限差分变化率 %/day)
    """
    t = get_chart_theme_tokens()
    if df is None or df.empty or 'q1' not in df.columns or 'q1_dot' not in df.columns:
        st.warning("暂无相空间动力学指标数据。")
        return False

    sub = df.dropna(subset=['q1', 'q1_dot']).copy()
    if sub.empty:
        st.warning("有效相空间数据不足。")
        return False

    date_col = 'date' if 'date' in sub.columns else sub.columns[0]
    sub['dt'] = pd.to_datetime(sub[date_col])
    sub = sub.sort_values('dt')

    q = sub['q1'].values
    qd = sub['q1_dot'].values
    dates = sub['dt'].dt.strftime('%Y-%m-%d').tolist()
    years = sub['dt'].dt.year.tolist()
    quads = sub.get('Quadrant', pd.Series([0]*len(sub))).tolist()

    q_lim = max(abs(float(np.nanmin(q))), abs(float(np.nanmax(q)))) * 1.10
    qd_lim = max(abs(float(np.nanmin(qd))), abs(float(np.nanmax(qd)))) * 1.10

    min_yr = int(min(years)) if years else 2013
    max_yr = int(max(years)) if years else 2026

    # Build scatter points
    scatter_data = []
    for q_val, qd_val, d_str, yr, q_num in zip(q, qd, dates, years, quads):
        if pd.notna(q_val) and pd.notna(qd_val):
            scatter_data.append([round(float(q_val), 2), round(float(qd_val), 3), d_str, int(q_num), yr])

    scatter_json = json.dumps(scatter_data, ensure_ascii=False)

    html_code = f"""
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <script src="https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"></script>
        <style>
            * {{ box-sizing: border-box; }}
            body {{
                margin: 0;
                padding: 0;
                background-color: {t["body_bg"]};
                color: {t["text_color"]};
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
                overflow: hidden;
            }}
            .chart-card {{
                width: 100%;
                height: {height}px;
                background: {t["card_bg"]};
                border: 1px solid {t["border_color"]};
                border-radius: 12px;
                box-shadow: {t["box_shadow"]};
                position: relative;
                display: flex;
                flex-direction: column;
            }}
            .chart-header {{
                display: flex;
                justify-content: space-between;
                align-items: flex-start;
                padding: 12px 18px 4px 18px;
                gap: 12px;
                flex-shrink: 0;
            }}
            .chart-title-area {{
                flex: 1;
                min-width: 0;
            }}
            .chart-title {{
                font-size: 17px;
                font-weight: 700;
                color: {t["title_color"]};
                line-height: 1.35;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
            }}
            .chart-subtitle {{
                font-size: 13px;
                color: {t["subtitle_color"]};
                margin-top: 2px;
                line-height: 1.3;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
            }}
            .chart-body {{
                width: 100%;
                flex: 1;
                min-height: 0;
            }}
            .phase-badge {{
                position: absolute; pointer-events: none; padding: 6px 12px;
                border-radius: 6px; font-weight: 700; z-index: 10;
                backdrop-filter: blur(4px); font-size: 13px;
            }}
        </style>
    </head>
    <body>
        <div class="chart-card">
            <div class="chart-header">
                <div class="chart-title-area">
                    <div class="chart-title">{symbol} 拉格朗日相空间动力学相图 (Phase Portrait: q1 vs q1_dot)</div>
                    <div class="chart-subtitle">横轴: 势能位置 q1 (相对200MA偏离度 %) · 纵轴: 动能速度 q1_dot (10日有限差分变化率 %/day) · 时间演化色阶</div>
                </div>
            </div>
            <div id="phase_chart" class="chart-body"></div>
            <!-- Quadrant Badges -->
            <div class="phase-badge" style="top: 85px; right: 45px; background: rgba(16, 185, 129, 0.12); color: #10b981; border: 1px solid rgba(16, 185, 129, 0.3);">
                【第一象限: 正反身性主升浪】q > 0, q_dot > 0 顺势持有
            </div>
            <div class="phase-badge" style="top: 85px; left: 75px; background: rgba(245, 158, 11, 0.12); color: #fbbf24; border: 1px solid rgba(245, 158, 11, 0.3);">
                【第二象限: 底部蓄势重构】q < 0, q_dot > 0 🌟 黄金坑右侧确认买点
            </div>
            <div class="phase-badge" style="bottom: 70px; left: 75px; background: rgba(239, 68, 68, 0.12); color: #f87171; border: 1px solid rgba(239, 68, 68, 0.3);">
                【第三象限: 负反身性死亡螺旋】q < 0, q_dot < 0 ⛔ 严禁左侧接飞刀
            </div>
            <div class="phase-badge" style="bottom: 70px; right: 45px; background: rgba(249, 115, 22, 0.12); color: #fb923c; border: 1px solid rgba(249, 115, 22, 0.3);">
                【第四象限: 动能衰竭与相变崩塌】q > 0, q_dot < 0 🚨 物理级反身性逃顶
            </div>
        </div>
        <script>
            const scatterData = {scatter_json};
            const qLim = {q_lim:.2f};
            const qdLim = {qd_lim:.2f};

            const chart = echarts.init(document.getElementById('phase_chart'), '{t["echarts_theme"]}');
            const option = {{
                backgroundColor: '{t["card_bg"]}',
                tooltip: {{
                    trigger: 'item',
                    backgroundColor: '{t["tooltip_bg"]}',
                    borderColor: '{t["tooltip_border"]}',
                    borderWidth: 1,
                    textStyle: {{ color: '{t["tooltip_text"]}', fontSize: 14 }},
                    formatter: function(param) {{
                        const d = param.data.value;
                        if (!d) return '';
                        const winPct = (d[0] * 100).toFixed(1) + '%';
                        const oddsVal = Number(d[1]).toFixed(2);
                        const compScore = Number(d[2]).toFixed(1);
                        const ticker = d[3];
                        const name = d[4] || '';
                        const valTag = d[5] || '正常估值';
                        const mom = d[6] !== null && d[6] !== undefined ? ((d[6] >= 0 ? '+' : '') + d[6] + '%') : 'N/A';
                        return '<div style="font-weight:700; font-size:15px; margin-bottom:6px; color:{t["tooltip_text"]};">'
                            + ticker + (name ? ' (' + name + ')' : '') + ' <span style="font-size:12px; color:{t["subtitle_color"]}; font-weight:400;">[' + param.seriesName + ']</span></div>'
                            + '<div style="font-size:14px; color:{t["subtitle_color"]};">综合投资评分: <b style="color:#38bdf8;">' + compScore + ' 分</b></div>'
                            + '<div style="font-size:14px; color:{t["subtitle_color"]};">宏观胜率 (X轴): <b style="color:#10b981;">' + winPct + '</b></div>'
                            + '<div style="font-size:14px; color:{t["subtitle_color"]};">估值赔率 (Y轴): <b style="color:#fbbf24;">' + oddsVal + '</b></div>'
                            + '<div style="font-size:14px; color:{t["subtitle_color"]};">估值诊断状态: <b style="color:' + param.color + ';">' + valTag + '</b></div>'
                            + '<div style="font-size:14px; color:{t["subtitle_color"]};">12-1M 学术动量: <b style="color:#a855f7;">' + mom + '</b></div>';
                    }}
                }},
                visualMap: {{
                    min: {min_yr},
                    max: {max_yr},
                    dimension: 4,
                    orient: 'horizontal',
                    left: 'center',
                    bottom: '12px',
                    text: ['最新年份', '起始年份'],
                    textStyle: {{ color: '{t["axis_label"]}', fontSize: 12 }},
                    inRange: {{
                        color: ['#38bdf8', '#818cf8', '#c084fc', '#f43f5e', '#fbbf24', '#34d399']
                    }},
                    calculable: true
                }},
                grid: {{
                    left: '70px', right: '45px', top: '35px', bottom: '65px'
                }},
                xAxis: {{
                    type: 'value',
                    name: '广义势能位置 q1 (相对 200MA 偏离度 %)',
                    nameLocation: 'middle',
                    nameGap: 30,
                    nameTextStyle: {{ color: '{t["axis_label"]}', fontSize: 14, fontWeight: 600 }},
                    min: -qLim, max: qLim,
                    axisLabel: {{ color: '{t["axis_label"]}', fontSize: 13, formatter: '{{value}}%' }},
                    axisLine: {{ lineStyle: {{ color: '{t["axis_line"]}' }} }},
                    splitLine: {{ lineStyle: {{ color: '{t["split_line"]}' }} }}
                }},
                yAxis: {{
                    type: 'value',
                    name: '广义动能速度 q1_dot (%/day)',
                    nameTextStyle: {{ color: '{t["axis_label"]}', fontSize: 14, fontWeight: 600 }},
                    min: -qdLim, max: qdLim,
                    axisLabel: {{ color: '{t["axis_label"]}', fontSize: 13, formatter: '{{value}}%' }},
                    axisLine: {{ lineStyle: {{ color: '{t["axis_line"]}' }} }},
                    splitLine: {{ lineStyle: {{ color: '{t["split_line"]}' }} }}
                }},
                series: [
                    {{
                        name: '相轨迹点',
                        type: 'scatter',
                        symbolSize: 6,
                        data: scatterData,
                        markArea: {{
                            silent: true,
                            data: [
                                [
                                    {{ coord: [0, 0], itemStyle: {{ color: 'rgba(16, 185, 129, 0.08)' }} }},
                                    {{ coord: [qLim, qdLim] }}
                                ],
                                [
                                    {{ coord: [-qLim, 0], itemStyle: {{ color: 'rgba(245, 158, 11, 0.08)' }} }},
                                    {{ coord: [0, qdLim] }}
                                ],
                                [
                                    {{ coord: [-qLim, -qdLim], itemStyle: {{ color: 'rgba(239, 68, 68, 0.08)' }} }},
                                    {{ coord: [0, 0] }}
                                ],
                                [
                                    {{ coord: [0, -qdLim], itemStyle: {{ color: 'rgba(249, 115, 22, 0.08)' }} }},
                                    {{ coord: [qLim, 0] }}
                                ]
                            ]
                        }},
                        markLine: {{
                            silent: true,
                            symbol: 'none',
                            lineStyle: {{ color: 'rgba(148, 163, 184, 0.6)', type: 'solid', width: 1.5 }},
                            data: [
                                {{ xAxis: 0 }},
                                {{ yAxis: 0 }}
                            ]
                        }},
                        markPoint: {{
                            data: [
                                {{
                                    name: '2021.11 逃顶相变',
                                    coord: [24.6, -0.76],
                                    value: '2021.11 逃顶',
                                    itemStyle: {{ color: '#ef4444' }},
                                    label: {{ show: true, fontSize: 12, fontWeight: 'bold', color: '#ffffff' }}
                                }},
                                {{
                                    name: '2022.10 黄金坑回补',
                                    coord: [-22.1, 0.42],
                                    value: '2022.10 回补',
                                    itemStyle: {{ color: '#10b981' }},
                                    label: {{ show: true, fontSize: 12, fontWeight: 'bold', color: '#ffffff' }}
                                }}
                            ]
                        }}
                    }}
                ]
            }};
            chart.setOption(option);
            window.addEventListener('resize', () => chart.resize());
        </script>
    </body>
    </html>
    """
    components.html(html_code, height=height + 25, scrolling=False)
    return True


# ------------------------------------------------------------------
# 29. Layer 4: 真实券商记账全周期资产净值对账曲线 (Strategy vs Benchmark)
# ------------------------------------------------------------------
def render_echarts_brokerage_nav(df: pd.DataFrame, ticker: str = "NOW", timeframe: str = "ALL", height: int = 480):
    """
    使用 Apache ECharts 渲染真实券商记账全周期资产净值走势对比 (Strategy vs Benchmark)
    """
    t = get_chart_theme_tokens()
    if df is None or df.empty:
        st.warning("暂无净值对账数据。")
        return False

    date_col = 'date' if 'date' in df.columns else df.columns[0]
    df_sorted = df.copy()
    df_sorted[date_col] = pd.to_datetime(df_sorted[date_col])
    df_sorted = df_sorted.sort_values(date_col)

    df_filtered = filter_by_timeframe(df_sorted, date_col, timeframe)
    if df_filtered.empty:
        df_filtered = df_sorted

    dates = df_filtered[date_col].dt.strftime('%Y-%m-%d').tolist()

    has_nav = 'strat_nav' in df_filtered.columns and 'bench_nav' in df_filtered.columns
    if has_nav:
        strat_vals = [round(float(v), 2) if pd.notna(v) else None for v in df_filtered['strat_nav']]
        bench_vals = [round(float(v), 2) if pd.notna(v) else None for v in df_filtered['bench_nav']]
    else:
        close_col = ticker if ticker in df_filtered.columns else ('close' if 'close' in df_filtered.columns else df_filtered.columns[1])
        strat_vals = [round(float(v), 2) if pd.notna(v) else None for v in df_filtered[close_col]]
        bench_vals = []

    dates_json = json.dumps(dates)
    strat_json = json.dumps(strat_vals)
    bench_json = json.dumps(bench_vals)

    subtext_str = '宏观反身性策略 (真实持股与现金池记账) vs 买入持有基准 (Buy & Hold 定投)' if has_nav else f'{ticker} 标的价格历史走势'
    nav_legend = ['宏观反身性策略 (真实券商记账)', '买入持有基准 (Buy & Hold)'] if has_nav else [f'{ticker} 价格']
    nav_legend_json = json.dumps(nav_legend)

    html_code = f"""
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <script src="https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"></script>
        <style>
            * {{ box-sizing: border-box; }}
            body {{
                margin: 0;
                padding: 0;
                background-color: {t["body_bg"]};
                color: {t["text_color"]};
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
                overflow: hidden;
            }}
            .chart-card {{
                width: 100%;
                height: {height}px;
                background: {t["card_bg"]};
                border: 1px solid {t["border_color"]};
                border-radius: 12px;
                box-shadow: {t["box_shadow"]};
                position: relative;
                display: flex;
                flex-direction: column;
            }}
            .chart-header {{
                display: flex;
                justify-content: space-between;
                align-items: flex-start;
                padding: 12px 18px 4px 18px;
                gap: 12px;
                flex-shrink: 0;
            }}
            .chart-title-area {{
                flex: 1;
                min-width: 0;
            }}
            .chart-title {{
                font-size: 17px;
                font-weight: 700;
                color: {t["title_color"]};
                line-height: 1.35;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
            }}
            .chart-subtitle {{
                font-size: 13px;
                color: {t["subtitle_color"]};
                margin-top: 2px;
                line-height: 1.3;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
            }}
            .chart-body {{
                width: 100%;
                flex: 1;
                min-height: 0;
            }}
        </style>
    </head>
    <body>
        <div class="chart-card">
            <div class="chart-header">
                <div class="chart-title-area">
                    <div class="chart-title">💰 真实券商记账全周期资产净值走势对比 ({ticker})</div>
                    <div class="chart-subtitle">{subtext_str}</div>
                </div>
            </div>
            <div id="nav_chart" class="chart-body"></div>
        </div>
        <script>
            function formatLargeNum(val) {{
                if (val === null || val === undefined || isNaN(val)) return 'N/A';
                const absVal = Math.abs(val);
                const sign = val < 0 ? '-' : '';
                if (absVal >= 1e12) return sign + '$' + (absVal / 1e12).toFixed(2) + ' T';
                if (absVal >= 1e9) return sign + '$' + (absVal / 1e9).toFixed(2) + ' B';
                if (absVal >= 1e6) return sign + '$' + (absVal / 1e6).toFixed(2) + ' M';
                if (absVal >= 1e3) return sign + '$' + (absVal / 1e3).toFixed(1) + ' K';
                return sign + '$' + absVal.toFixed(0);
            }}

            const dates = {dates_json};
            const stratVals = {strat_json};
            const benchVals = {bench_json};
            const hasNav = {str(has_nav).lower()};

            const chart = echarts.init(document.getElementById('nav_chart'), '{t["echarts_theme"]}');
            const option = {{
                backgroundColor: '{t["card_bg"]}',
                tooltip: {{
                    trigger: 'axis',
                    axisPointer: {{
                        type: 'cross',
                        crossStyle: {{ color: '{t["axis_label"]}' }},
                        lineStyle: {{ color: 'rgba(56, 189, 248, 0.4)', width: 1.5 }}
                    }},
                    backgroundColor: '{t["tooltip_bg"]}',
                    borderColor: '{t["tooltip_border"]}',
                    borderWidth: 1,
                    textStyle: {{ color: '{t["tooltip_text"]}', fontSize: 14 }},
                    formatter: function(params) {{
                        if (!params || !params.length) return '';
                        let html = '<div style="font-weight:700; margin-bottom:6px; font-size:15px; color:{t["tooltip_text"]};">' + params[0].name + '</div>';
                        let sVal = null, bVal = null;
                        params.forEach(p => {{
                            if (p.seriesName.includes('宏观反身性') || p.seriesName.includes('策略')) sVal = p.value;
                            else if (p.seriesName.includes('基准')) bVal = p.value;
                            else if (p.value !== null) {{
                                html += '<div style="font-size:14px; color:{t["subtitle_color"]};">' + p.seriesName + ': <b style="color:' + p.color + ';">' + formatLargeNum(p.value) + '</b></div>';
                            }}
                        }});
                        if (sVal !== null) {{
                            html += '<div style="font-size:14px; color:{t["subtitle_color"]};">策略真实净资产: <b style="color:#f43f5e;">$' + Number(sVal).toLocaleString('en-US', {{minimumFractionDigits: 0, maximumFractionDigits: 0}}) + '</b></div>';
                        }}
                        if (bVal !== null) {{
                            html += '<div style="font-size:14px; color:{t["subtitle_color"]};">基准买入持有: <b style="color:#94a3b8;">$' + Number(bVal).toLocaleString('en-US', {{minimumFractionDigits: 0, maximumFractionDigits: 0}}) + '</b></div>';
                        }}
                        if (sVal !== null && bVal !== null && bVal > 0) {{
                            const alpha = sVal - bVal;
                            const alphaPct = ((alpha / bVal) * 100).toFixed(1);
                            const alphaColor = alpha >= 0 ? '#10b981' : '#ef4444';
                            html += '<div style="font-size:14px; color:{t["subtitle_color"]};">超额财富 Alpha: <b style="color:' + alphaColor + ';">' + (alpha >= 0 ? '+' : '') + '$' + Number(alpha).toLocaleString('en-US', {{minimumFractionDigits: 0, maximumFractionDigits: 0}}) + ' (' + (alpha >= 0 ? '+' : '') + alphaPct + '%)</b></div>';
                        }}
                        return html;
                    }}
                }},
                legend: {{
                    data: {nav_legend_json},
                    top: '6px',
                    left: 'center',
                    type: 'scroll',
                    textStyle: {{ color: '{t["legend_text"]}', fontSize: 13 }},
                    itemGap: 16
                }},
                grid: {{
                    left: '65px', right: '45px', top: '44px', bottom: '65px'
                }},
                xAxis: {{
                    type: 'category',
                    data: dates,
                    axisLabel: {{ color: '{t["axis_label"]}', fontSize: 13 }},
                    axisLine: {{ lineStyle: {{ color: '{t["axis_line"]}' }} }}
                }},
                yAxis: {{
                    type: 'value',
                    scale: true,
                    name: hasNav ? '账户总资产 (USD)' : '价格 (USD)',
                    nameTextStyle: {{ color: '{t["axis_label"]}', fontSize: 14 }},
                    axisLabel: {{
                        color: '{t["axis_label"]}', fontSize: 13,
                        formatter: function(val) {{ return formatLargeNum(val); }}
                    }},
                    splitLine: {{ lineStyle: {{ color: '{t["split_line"]}' }} }}
                }},
                dataZoom: [
                    {{
                        type: 'inside',
                        start: Math.max(0, 100 - Math.min(100, (500 / Math.max(1, dates.length)) * 100)),
                        end: 100
                    }},
                    {{
                        type: 'slider',
                        bottom: '12px', height: 24,
                        backgroundColor: '{t["datazoom_bg"]}',
                        borderColor: '{t["datazoom_border"]}',
                        fillerColor: '{t["datazoom_filler"]}',
                        handleStyle: {{ color: '{t["datazoom_handle"]}' }},
                        textStyle: {{ color: '{t["axis_label"]}', fontSize: 12 }},
                        start: Math.max(0, 100 - Math.min(100, (500 / Math.max(1, dates.length)) * 100)),
                        end: 100
                    }}
                ],
                series: [
                    {{
                        name: hasNav ? '宏观反身性策略 (真实券商记账)' : '{ticker} 价格',
                        type: 'line',
                        data: stratVals,
                        lineStyle: {{ color: '#f43f5e', width: 2.5 }},
                        itemStyle: {{ color: '#f43f5e' }},
                        showSymbol: false,
                        areaStyle: {{
                            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                                {{ offset: 0, color: 'rgba(244, 63, 94, 0.25)' }},
                                {{ offset: 1, color: 'rgba(244, 63, 94, 0.0)' }}
                            ])
                        }}
                    }}
                ]
            }};

            if (hasNav && benchVals.length > 0) {{
                option.series.push({{
                    name: '买入持有基准 (Buy & Hold)',
                    type: 'line',
                    data: benchVals,
                    lineStyle: {{ color: '#94a3b8', width: 1.8, type: 'dashed' }},
                    itemStyle: {{ color: '#94a3b8' }},
                    showSymbol: false
                }});
            }}

            chart.setOption(option);
            window.addEventListener('resize', () => chart.resize());
        </script>
    </body>
    </html>
    """
    components.html(html_code, height=height + 25, scrolling=False)
    return True


# ------------------------------------------------------------------
# 30. Layer 3: 行业内部成分股 50MA 广度与顶背离深度剖析图
# ------------------------------------------------------------------
def render_echarts_industry_breadth(df: pd.DataFrame, ticker: str = "IGV", default_range: str = "1Y", height: int = 580):
    """
    使用 Apache ECharts 渲染行业内部成分股 50MA 广度与顶背离深度剖析图 (双 Y 轴自适应缩放)
    """
    t = get_chart_theme_tokens()
    if df is None or df.empty:
        st.warning("暂无行业内部广度数据。")
        return False

    date_col = 'date' if 'date' in df.columns else df.columns[0]
    df_sorted = df.copy()
    df_sorted[date_col] = pd.to_datetime(df_sorted[date_col])
    df_sorted = df_sorted.sort_values(date_col)

    df_filtered = filter_by_timeframe(df_sorted, date_col, default_range)
    if df_filtered.empty:
        df_filtered = df_sorted

    dates = df_filtered[date_col].dt.strftime('%Y-%m-%d').tolist()

    # Primary Breadth
    breadth_col = 'Breadth_50' if 'Breadth_50' in df_filtered.columns else None
    if breadth_col:
        breadth_vals = [round(float(v) * 100.0, 1) if pd.notna(v) else None for v in df_filtered[breadth_col]]
    else:
        breadth_vals = []

    # Price curve
    price_col = ticker if ticker in df_filtered.columns else ('close' if 'close' in df_filtered.columns else None)
    price_vals = [round(float(v), 2) if (price_col and pd.notna(v)) else None for v in df_filtered.get(price_col, [None]*len(df_filtered))]

    # Optional sub-breadths
    sub_series = []
    if ticker == 'XLE':
        if 'Breadth_Services' in df_filtered.columns:
            sub_series.append({
                "name": "油服设备广度 (Services %)",
                "data": [round(float(v)*100.0, 1) if pd.notna(v) else None for v in df_filtered['Breadth_Services']],
                "color": "#f97316",
                "type": "dashed"
            })
        if 'Breadth_EP' in df_filtered.columns:
            sub_series.append({
                "name": "上游勘探广度 (E&P %)",
                "data": [round(float(v)*100.0, 1) if pd.notna(v) else None for v in df_filtered['Breadth_EP']],
                "color": "#10b981",
                "type": "dashed"
            })
    elif ticker == 'KRE':
        if 'Breadth_Regional_Banks' in df_filtered.columns:
            sub_series.append({
                "name": "区域银行广度 (Regional %)",
                "data": [round(float(v)*100.0, 1) if pd.notna(v) else None for v in df_filtered['Breadth_Regional_Banks']],
                "color": "#f97316",
                "type": "dashed"
            })
        if 'Breadth_GSIBs' in df_filtered.columns:
            sub_series.append({
                "name": "大型投行广度 (G-SIBs %)",
                "data": [round(float(v)*100.0, 1) if pd.notna(v) else None for v in df_filtered['Breadth_GSIBs']],
                "color": "#38bdf8",
                "type": "dashed"
            })
    elif ticker == 'VNQ':
        if 'Breadth_Homebuilders' in df_filtered.columns:
            sub_series.append({
                "name": "住宅建筑商广度 (Builders %)",
                "data": [round(float(v)*100.0, 1) if pd.notna(v) else None for v in df_filtered['Breadth_Homebuilders']],
                "color": "#10b981",
                "type": "dashed"
            })
        if 'Breadth_Office_CRE' in df_filtered.columns:
            sub_series.append({
                "name": "商业写字楼广度 (Office/CRE %)",
                "data": [round(float(v)*100.0, 1) if pd.notna(v) else None for v in df_filtered['Breadth_Office_CRE']],
                "color": "#ef4444",
                "type": "dashed"
            })

    dates_json = json.dumps(dates)
    breadth_json = json.dumps(breadth_vals)
    price_json = json.dumps(price_vals)
    sub_series_json = json.dumps(sub_series, ensure_ascii=False)

    html_code = f"""
    <!DOCTYPE html>
    <html lang="zh-CN">
    <head>
        <meta charset="UTF-8">
        <script src="https://cdn.jsdelivr.net/npm/echarts@5.5.0/dist/echarts.min.js"></script>
        <style>
            * {{ box-sizing: border-box; }}
            body {{
                margin: 0;
                padding: 0;
                background-color: {t["body_bg"]};
                color: {t["text_color"]};
                font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
                overflow: hidden;
            }}
            .chart-card {{
                width: 100%;
                height: {height}px;
                background: {t["card_bg"]};
                border: 1px solid {t["border_color"]};
                border-radius: 12px;
                box-shadow: {t["box_shadow"]};
                position: relative;
                display: flex;
                flex-direction: column;
            }}
            .chart-header {{
                display: flex;
                justify-content: space-between;
                align-items: flex-start;
                padding: 12px 18px 4px 18px;
                gap: 12px;
                flex-shrink: 0;
            }}
            .chart-title-area {{
                flex: 1;
                min-width: 0;
            }}
            .chart-title {{
                font-size: 17px;
                font-weight: 700;
                color: {t["title_color"]};
                line-height: 1.35;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
            }}
            .chart-subtitle {{
                font-size: 13px;
                color: {t["subtitle_color"]};
                margin-top: 2px;
                line-height: 1.3;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
            }}
            .chart-body {{
                width: 100%;
                flex: 1;
                min-height: 0;
            }}
        </style>
    </head>
    <body>
        <div class="chart-card">
            <div class="chart-header">
                <div class="chart-title-area">
                    <div class="chart-title">📉 Layer 3: 内部成分股 50MA 广度与顶背离深度剖析 ({ticker})</div>
                    <div class="chart-subtitle">左轴: 站上 50MA 股票比例 (%) · 右轴: {ticker} 价格 ($) · 40% 坍塌线与顶背离预警</div>
                </div>
            </div>
            <div id="breadth_chart" class="chart-body"></div>
        </div>
        <script>
            const dates = {dates_json};
            const breadthVals = {breadth_json};
            const priceVals = {price_json};
            const subSeriesList = {sub_series_json};

            const chart = echarts.init(document.getElementById('breadth_chart'), '{t["echarts_theme"]}');
            const legendNames = ['综合站上 50MA 比例 (%)', '{ticker} 价格 ($)'];
            subSeriesList.forEach(s => legendNames.push(s.name));

            const seriesArr = [
                {{
                    name: '综合站上 50MA 比例 (%)',
                    type: 'line',
                    yAxisIndex: 0,
                    data: breadthVals,
                    lineStyle: {{ color: '#ec4899', width: 2.2 }},
                    itemStyle: {{ color: '#ec4899' }},
                    showSymbol: false,
                    markArea: {{
                        silent: true,
                        data: [
                            [
                                {{ yAxis: 0, itemStyle: {{ color: 'rgba(239, 68, 68, 0.08)' }} }},
                                {{ yAxis: 40 }}
                            ]
                        ]
                    }},
                    markLine: {{
                        silent: true,
                        symbol: 'none',
                        data: [
                            {{
                                yAxis: 50,
                                lineStyle: {{ color: 'rgba(236, 72, 153, 0.7)', type: 'dashed', width: 1.5 }},
                                label: {{ show: true, formatter: '50% 多空平衡线', color: '#ec4899', fontSize: 12, position: 'insideStartTop' }}
                            }},
                            {{
                                yAxis: 40,
                                lineStyle: {{ color: 'rgba(239, 68, 68, 0.7)', type: 'dashed', width: 1.5 }},
                                label: {{ show: true, formatter: '40% 广度坍塌线', color: '#ef4444', fontSize: 12, position: 'insideStartTop' }}
                            }}
                        ]
                    }}
                }},
                {{
                    name: '{ticker} 价格 ($)',
                    type: 'line',
                    yAxisIndex: 1,
                    data: priceVals,
                    lineStyle: {{ color: '#38bdf8', width: 2 }},
                    itemStyle: {{ color: '#38bdf8' }},
                    showSymbol: false
                }}
            ];

            subSeriesList.forEach(s => {{
                seriesArr.push({{
                    name: s.name,
                    type: 'line',
                    yAxisIndex: 0,
                    data: s.data,
                    lineStyle: {{ color: s.color, width: 1.6, type: s.type || 'dashed' }},
                    itemStyle: {{ color: s.color }},
                    showSymbol: false
                }});
            }});

            const option = {{
                backgroundColor: '{t["card_bg"]}',
                tooltip: {{
                    trigger: 'axis',
                    axisPointer: {{
                        type: 'cross',
                        crossStyle: {{ color: '{t["axis_label"]}' }},
                        lineStyle: {{ color: 'rgba(56, 189, 248, 0.4)', width: 1.5 }}
                    }},
                    backgroundColor: '{t["tooltip_bg"]}',
                    borderColor: '{t["tooltip_border"]}',
                    borderWidth: 1,
                    textStyle: {{ color: '{t["tooltip_text"]}', fontSize: 14 }},
                    formatter: function(params) {{
                        if (!params || !params.length) return '';
                        let html = '<div style="font-weight:700; margin-bottom:6px; font-size:15px; color:{t["tooltip_text"]};">' + params[0].name + '</div>';
                        params.forEach(p => {{
                            if (p.value !== null && p.value !== undefined) {{
                                const isPrice = p.seriesName.includes('价格');
                                const valStr = isPrice ? ('$' + Number(p.value).toFixed(2)) : (Number(p.value).toFixed(1) + '%');
                                html += '<div style="font-size:14px; color:{t["subtitle_color"]};">' + p.seriesName + ': <b style="color:' + p.color + ';">' + valStr + '</b></div>';
                            }}
                        }});
                        return html;
                    }}
                }},
                legend: {{
                    data: legendNames,
                    top: '6px',
                    left: 'center',
                    type: 'scroll',
                    textStyle: {{ color: '{t["legend_text"]}', fontSize: 13 }},
                    itemGap: 14
                }},
                grid: {{
                    left: '60px', right: '65px', top: '46px', bottom: '65px'
                }},
                xAxis: {{
                    type: 'category',
                    data: dates,
                    axisLabel: {{ color: '{t["axis_label"]}', fontSize: 13 }},
                    axisLine: {{ lineStyle: {{ color: '{t["axis_line"]}' }} }}
                }},
                yAxis: [
                    {{
                        type: 'value',
                        name: '站上 50MA 比例 (%)',
                        nameTextStyle: {{ color: '{t["axis_label"]}', fontSize: 14 }},
                        min: 0, max: 100,
                        axisLabel: {{ color: '{t["axis_label"]}', fontSize: 13, formatter: '{{value}}%' }},
                        splitLine: {{ lineStyle: {{ color: '{t["split_line"]}' }} }}
                    }},
                    {{
                        type: 'value',
                        scale: true,
                        name: '标的价格 ($)',
                        nameTextStyle: {{ color: '{t["axis_label"]}', fontSize: 14 }},
                        axisLabel: {{ color: '{t["axis_label"]}', fontSize: 13, formatter: '${{value}}' }},
                        splitLine: {{ show: false }}
                    }}
                ],
                dataZoom: [
                    {{
                        type: 'inside',
                        start: Math.max(0, 100 - Math.min(100, (400 / Math.max(1, dates.length)) * 100)),
                        end: 100
                    }},
                    {{
                        type: 'slider',
                        bottom: '12px', height: 24,
                        backgroundColor: '{t["datazoom_bg"]}',
                        borderColor: '{t["datazoom_border"]}',
                        fillerColor: '{t["datazoom_filler"]}',
                        handleStyle: {{ color: '{t["datazoom_handle"]}' }},
                        textStyle: {{ color: '{t["axis_label"]}', fontSize: 12 }},
                        start: Math.max(0, 100 - Math.min(100, (400 / Math.max(1, dates.length)) * 100)),
                        end: 100
                    }}
                ],
                series: seriesArr
            }};

            chart.setOption(option);
            window.addEventListener('resize', () => chart.resize());
        </script>
    </body>
    </html>
    """
    components.html(html_code, height=height + 25, scrolling=False)
    return True


