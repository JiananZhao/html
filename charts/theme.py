import pandas as pd
import plotly.graph_objects as go

# ------------------------------------------------------------------
# 通用调色板与常量
# ------------------------------------------------------------------
COLOR_PALETTE = {
    "primary_blue": "#2563eb",
    "danger_red": "#dc2626",
    "success_green": "#16a34a",
    "warning_amber": "#d97706",
    "purple": "#9333ea",
    "cyan": "#0891b2",
    "gray_text": "#64748b",
    "gray_line": "#94a3b8",
}

# ------------------------------------------------------------------
# 辅助函数：根据选定时间范围切片 DataFrame
# ------------------------------------------------------------------
def filter_by_timeframe(df: pd.DataFrame, date_col: str, timeframe: str = "ALL") -> pd.DataFrame:
    """
    按指定时间范围（1M, 3M, 6M, 1Y, 2Y, 3Y, 5Y, 10Y, ALL）对 DataFrame 进行时间切片
    """
    if df is None or df.empty or not timeframe or timeframe == "ALL":
        return df
    df_sorted = df.sort_values(date_col)
    last_date = df_sorted[date_col].max()
    tf_map = {
        "1M": pd.DateOffset(months=1),
        "3M": pd.DateOffset(months=3),
        "6M": pd.DateOffset(months=6),
        "1Y": pd.DateOffset(years=1),
        "2Y": pd.DateOffset(years=2),
        "3Y": pd.DateOffset(years=3),
        "5Y": pd.DateOffset(years=5),
        "10Y": pd.DateOffset(years=10),
    }
    if timeframe in tf_map:
        start_date = last_date - tf_map[timeframe]
        return df_sorted[df_sorted[date_col] >= start_date].copy()
    return df


# ------------------------------------------------------------------
# 统一图表布局应用函数 (减少重复的 update_layout 调用)
# ------------------------------------------------------------------
def apply_chart_theme(
    fig: go.Figure,
    title: str = None,
    height: int = 450,
    template: str = None,
    hovermode: str = "x unified",
    uirevision: str = None,
    yaxis_title: str = None,
    showlegend: bool = True,
    theme_mode: str = None,
    **kwargs
) -> go.Figure:
    """
    统一设置 Plotly 图表的标准样式、高度、hover 交互与 uirevision 状态保持
    自动同步全局 session_state["theme_mode"] (深色/浅色)，亦支持显式传入 theme_mode
    """
    if theme_mode is not None:
        current_theme = theme_mode
    else:
        try:
            import streamlit as st
            current_theme = st.session_state.get("theme_mode", "dark")
        except Exception:
            current_theme = "dark"

    # 强制与系统当前主题保持 100% 纯正一致 (无论历史代码是否传入了 plotly_white)
    if current_theme == "dark":
        active_template = "plotly_dark"
        font_color = "#f8fafc"
        paper_bg = "#0b0f19"
        plot_bg = "#0e131f"
        grid_color = "rgba(255, 255, 255, 0.08)"
    else:
        active_template = "plotly_white"
        font_color = "#0f172a"
        paper_bg = "#ffffff"
        plot_bg = "#ffffff"
        grid_color = "rgba(0, 0, 0, 0.08)"

    layout_params = {
        "height": height,
        "template": active_template,
        "hovermode": hovermode,
        "showlegend": showlegend,
        "font": dict(size=14, family="sans-serif", color=font_color),
        "paper_bgcolor": paper_bg,
        "plot_bgcolor": plot_bg,
    }
    if title is not None:
        layout_params["title"] = dict(text=title, font=dict(size=17, color=font_color))
    if uirevision is not None:
        layout_params["uirevision"] = uirevision
    if yaxis_title is not None:
        layout_params["yaxis_title"] = yaxis_title

    layout_params.update(kwargs)
    # 再次强制锁定背景与模板，杜绝 kwargs 中残留的旧配置
    layout_params["template"] = active_template
    layout_params["paper_bgcolor"] = paper_bg
    layout_params["plot_bgcolor"] = plot_bg
    layout_params["font"] = dict(size=14, family="sans-serif", color=font_color)

    fig.update_layout(**layout_params)
    fig.update_xaxes(
        gridcolor=grid_color,
        zerolinecolor=grid_color,
        tickfont=dict(color=font_color, size=14),
        title_font=dict(color=font_color, size=14)
    )
    fig.update_yaxes(
        gridcolor=grid_color,
        zerolinecolor=grid_color,
        tickfont=dict(color=font_color, size=14),
        title_font=dict(color=font_color, size=14)
    )
    if showlegend:
        fig.update_layout(
            legend=dict(
                font=dict(color=font_color, size=14),
                bgcolor="rgba(19, 27, 42, 0.92)" if current_theme == "dark" else "rgba(255, 255, 255, 0.95)",
                bordercolor="#334155" if current_theme == "dark" else "#cbd5e1",
                borderwidth=1
            )
        )

    # 自动对图表中存在的 rangeselector / rangeslider 统一注入深浅色样式与 >= 14pt 字体
    if hasattr(fig.layout, "xaxis") and fig.layout.xaxis:
        rs = getattr(fig.layout.xaxis, "rangeselector", None)
        if rs and getattr(rs, "buttons", None):
            rs_bg = "#1e293b" if current_theme == "dark" else "#f1f5f9"
            rs_active = "#2563eb" if current_theme == "dark" else "#3b82f6"
            rs_border = "#334155" if current_theme == "dark" else "#cbd5e1"
            fig.update_xaxes(
                rangeselector=dict(
                    bgcolor=rs_bg,
                    activecolor=rs_active,
                    bordercolor=rs_border,
                    borderwidth=1,
                    font=dict(color=font_color, size=14, family="sans-serif")
                )
            )
        rsl = getattr(fig.layout.xaxis, "rangeslider", None)
        if rsl and getattr(rsl, "visible", False):
            rsl_bg = "#131b2a" if current_theme == "dark" else "#f1f5f9"
            fig.update_xaxes(rangeslider=dict(bgcolor=rsl_bg))

    return fig


# ------------------------------------------------------------------
# 全站动态主题样式生成器 (Dark Mode vs Bright/Daytime Mode)
# ------------------------------------------------------------------
def get_theme_css(mode: str = "dark") -> str:
    """
    生成全站动态主题样式 (Dark Mode vs Bright/Daytime Mode)
    遵循 Rule 11 规范: 大字体 >= 14px，高对比度，零视觉割裂
    """
    if mode == "dark":
        return """
<style>
/* =================================================================
   🌙 深色极客夜间模式 (Dark Institutional Terminal Theme)
   ================================================================= */

/* 1. 整体页面画布、主视口与侧边栏 */
.stApp,
[data-testid="stAppViewContainer"],
[data-testid="stHeader"],
[data-testid="stMainBlockContainer"],
.main {
    background-color: #0b0f19 !important;
    color: #f8fafc !important;
}

[data-testid="stSidebar"],
[data-testid="stSidebarContent"],
section[data-testid="stSidebar"] {
    background-color: #070a12 !important;
    border-right: 1px solid #1e293b !important;
}

/* 2. 排版与文本颜色：彻底根除黑字，全量提亮为高对比度白与浅银灰 */
h1, h2, h3, h4, h5, h6,
[data-testid="stHeadingWithActionElements"] {
    color: #ffffff !important;
}

p, span, label, li,
[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] span,
[data-testid="stMarkdownContainer"] li,
[data-testid="stWidgetLabel"] p,
[data-testid="stWidgetLabel"] span {
    color: #cbd5e1 !important;
}

strong, b {
    color: #ffffff !important;
}

a {
    color: #38bdf8 !important;
}

hr {
    border-color: #1e293b !important;
}

[data-testid="stCaptionContainer"] p, small {
    color: #94a3b8 !important;
}

/* 2.1 行内代码与状态小胶囊 (Inline Code & Badges) - 彻底根除白底黑字小方块 */
code, pre, kbd, samp,
.stMarkdown code,
.stMarkdown pre,
[data-testid="stMarkdownContainer"] code,
[data-testid="stMarkdownContainer"] pre,
[data-testid="stMarkdownContainer"] p code,
[data-testid="stMarkdownContainer"] span code,
p code, span code, div code {
    background: #151d2e !important;
    background-color: #151d2e !important;
    color: #38bdf8 !important;
    border: 1px solid #27354f !important;
    border-radius: 5px !important;
    padding: 3px 8px !important;
    font-size: 13px !important;
    font-weight: 600 !important;
}

/* 3. 主导航条 (st.segmented_control / stButtonGroup) 强力暗色覆盖 - 彻底根除未选中选项白底问题 */
div[data-testid="stButtonGroup"],
div[data-testid="stButtonGroup"] > div,
div.stButtonGroup,
div[data-testid="stSegmentedControl"],
[data-baseweb="segmented-control"],
[data-baseweb="button-group"] {
    display: flex !important;
    flex-wrap: wrap !important;
    gap: 8px !important;
    padding: 6px 0 16px 0 !important;
    background: transparent !important;
    background-color: transparent !important;
    border: none !important;
}

div[data-testid="stButtonGroup"] button,
div.stButtonGroup button,
div[data-testid="stButtonGroup"] div button,
div[data-testid="stButtonGroup"] [role="radiogroup"] button,
button[data-testid*="segmented_control"],
button[data-testid="stBaseButton-segmented_control"],
button[data-testid="stBaseButton-segmented_controlActive"],
div[data-testid="stSegmentedControl"] button,
div[data-testid="stSegmentedControl"] [data-testid*="Button"],
div[data-testid="stSegmentedControl"] [data-baseweb="button-group"] button,
div[data-testid="stSegmentedControl"] [role="radiogroup"] button,
div[data-testid="stSegmentedControl"] [role="radio"],
[data-baseweb="button-group"] button {
    font-size: 15px !important;
    font-weight: 600 !important;
    padding: 10px 18px !important;
    border-radius: 8px !important;
    color: #cbd5e1 !important;
    background: #131b2a !important;
    background-color: #131b2a !important;
    border: 1px solid #223048 !important;
    transition: all 0.2s ease !important;
}

div[data-testid="stButtonGroup"] button *,
div.stButtonGroup button *,
button[data-testid="stBaseButton-segmented_control"] *,
div[data-testid="stSegmentedControl"] button div,
div[data-testid="stSegmentedControl"] button p,
div[data-testid="stSegmentedControl"] button span,
div[data-testid="stSegmentedControl"] [role="radio"] * {
    background-color: transparent !important;
    background: transparent !important;
    color: #cbd5e1 !important;
}

/* 未选中的 segmented control 选项 - 强制深色底、浅灰字、深色边框 */
div[data-testid="stButtonGroup"] button:not([data-testid*="Active"]):not([aria-checked="true"]):not([aria-selected="true"]):not([data-state="active"]),
div.stButtonGroup button:not([data-testid*="Active"]):not([aria-checked="true"]):not([aria-selected="true"]):not([data-state="active"]),
button[data-testid="stBaseButton-segmented_control"],
div[data-testid="stSegmentedControl"] button:not([aria-selected="true"]):not([aria-checked="true"]) {
    background: #131b2a !important;
    background-color: #131b2a !important;
    color: #cbd5e1 !important;
    border: 1px solid #223048 !important;
}

/* 激活选中的 segmented control 选项 - 强制深蓝/暗红色高光背景、亮白字 */
div[data-testid="stButtonGroup"] button[data-testid*="Active"],
div[data-testid="stButtonGroup"] button[aria-checked="true"],
div[data-testid="stButtonGroup"] button[aria-selected="true"],
div[data-testid="stButtonGroup"] button[data-state="active"],
div.stButtonGroup button[data-testid*="Active"],
button[data-testid="stBaseButton-segmented_controlActive"],
div[data-testid="stSegmentedControl"] button[aria-selected="true"],
div[data-testid="stSegmentedControl"] button[aria-checked="true"],
div[data-testid="stSegmentedControl"] button[aria-pressed="true"],
div[data-testid="stSegmentedControl"] button[data-state="active"],
div[data-testid="stSegmentedControl"] [role="radio"][aria-checked="true"] {
    color: #ffffff !important;
    background: #1e3a8a !important;
    background-color: #1e3a8a !important;
    border-color: #3b82f6 !important;
    box-shadow: 0 4px 14px rgba(37, 99, 235, 0.45) !important;
}

div[data-testid="stButtonGroup"] button[data-testid*="Active"] *,
div[data-testid="stButtonGroup"] button[aria-checked="true"] *,
div[data-testid="stButtonGroup"] button[aria-selected="true"] *,
div[data-testid="stButtonGroup"] button[data-state="active"] *,
div.stButtonGroup button[data-testid*="Active"] *,
button[data-testid="stBaseButton-segmented_controlActive"] *,
div[data-testid="stSegmentedControl"] button[aria-selected="true"] *,
div[data-testid="stSegmentedControl"] button[aria-checked="true"] * {
    color: #ffffff !important;
    font-weight: 700 !important;
    background-color: transparent !important;
}

/* Hover 状态 */
div[data-testid="stButtonGroup"] button:hover,
div.stButtonGroup button:hover,
button[data-testid="stBaseButton-segmented_control"]:hover,
div[data-testid="stSegmentedControl"] button:hover,
div[data-testid="stSegmentedControl"] [role="radio"]:hover {
    color: #ffffff !important;
    background: #1e293b !important;
    background-color: #1e293b !important;
    border-color: #38bdf8 !important;
}
div[data-testid="stButtonGroup"] button:hover *,
div.stButtonGroup button:hover *,
button[data-testid="stBaseButton-segmented_control"]:hover *,
div[data-testid="stSegmentedControl"] button:hover * {
    color: #ffffff !important;
    background-color: transparent !important;
}

/* 4. 子标签页 (stTabs) 强力暗色覆盖 - 根治未选中 Tab 白底问题 */
div[data-testid="stTabs"] [data-baseweb="tab-list"] {
    background: transparent !important;
    background-color: transparent !important;
    border-bottom: 1px solid #1e293b !important;
    gap: 8px !important;
}

div[data-testid="stTabs"] button[data-baseweb="tab"],
div[data-testid="stTabs"] [role="tab"] {
    color: #94a3b8 !important;
    font-size: 15px !important;
    font-weight: 600 !important;
    background: #131b2a !important;
    background-color: #131b2a !important;
    border: 1px solid #223048 !important;
    border-bottom: none !important;
    border-radius: 8px 8px 0 0 !important;
    padding: 8px 18px !important;
    transition: all 0.2s ease !important;
}

div[data-testid="stTabs"] button[data-baseweb="tab"] *,
div[data-testid="stTabs"] [role="tab"] * {
    background-color: transparent !important;
    color: #94a3b8 !important;
}

/* 未选中子标签页 */
div[data-testid="stTabs"] button[data-baseweb="tab"]:not([aria-selected="true"]) {
    background: #131b2a !important;
    background-color: #131b2a !important;
    color: #94a3b8 !important;
}

/* 选中的子标签页 */
div[data-testid="stTabs"] button[data-baseweb="tab"][aria-selected="true"],
div[data-testid="stTabs"] [role="tab"][aria-selected="true"] {
    color: #ffffff !important;
    background: #1e293b !important;
    background-color: #1e293b !important;
    border: 1px solid #38bdf8 !important;
    border-bottom: 2px solid #38bdf8 !important;
}

div[data-testid="stTabs"] button[data-baseweb="tab"][aria-selected="true"] * {
    color: #ffffff !important;
    font-weight: 700 !important;
    background-color: transparent !important;
}

div[data-testid="stTabs"] button[data-baseweb="tab"]:hover,
div[data-testid="stTabs"] [role="tab"]:hover {
    color: #f8fafc !important;
    background: #1a2234 !important;
    background-color: #1a2234 !important;
    border-color: #38bdf8 !important;
}

div[data-testid="stTabs"] [data-baseweb="tab-highlight"] {
    background-color: #38bdf8 !important;
}

/* 5. KPI 指标卡片 (stMetric) - 目前、最新交易日等卡片深色极客质感 */
div[data-testid="stMetric"] {
    background: #131b2a !important;
    border: 1px solid #223048 !important;
    border-radius: 12px !important;
    padding: 14px 18px !important;
    box-shadow: 0 4px 16px rgba(0,0,0,0.35) !important;
}
div[data-testid="stMetric"] [data-testid="stMetricLabel"],
div[data-testid="stMetric"] [data-testid="stMetricLabel"] p {
    font-size: 14px !important;
    color: #94a3b8 !important;
    font-weight: 600 !important;
}
div[data-testid="stMetric"] [data-testid="stMetricLabel"] svg {
    color: #94a3b8 !important;
}
div[data-testid="stMetric"] [data-testid="stMetricValue"],
div[data-testid="stMetric"] [data-testid="stMetricValue"] div {
    font-size: 26px !important;
    font-weight: 700 !important;
    color: #ffffff !important;
    letter-spacing: -0.5px !important;
}
div[data-testid="stMetric"] div[data-testid="stMetricDelta"] {
    font-size: 13px !important;
    font-weight: 600 !important;
    padding: 3px 10px !important;
    border-radius: 6px !important;
    display: inline-flex !important;
    align-items: center !important;
    width: fit-content !important;
    margin-top: 4px !important;
}
div[data-testid="stMetric"] div[data-testid="stMetricDelta"]:has(svg[data-testid="stMetricDeltaIcon-Up"]),
div[data-testid="stMetric"] div[data-testid="stMetricDelta"]:has([color*="green"]),
div[data-testid="stMetric"] div[data-testid="stMetricDelta"][data-direction="normal"] {
    background: rgba(16, 185, 129, 0.2) !important;
    color: #34d399 !important;
    border: 1px solid rgba(16, 185, 129, 0.4) !important;
}
div[data-testid="stMetric"] div[data-testid="stMetricDelta"]:has(svg[data-testid="stMetricDeltaIcon-Up"]) svg {
    fill: #34d399 !important;
}
div[data-testid="stMetric"] div[data-testid="stMetricDelta"]:has(svg[data-testid="stMetricDeltaIcon-Up"]) * {
    color: #34d399 !important;
}
div[data-testid="stMetric"] div[data-testid="stMetricDelta"]:has(svg[data-testid="stMetricDeltaIcon-Down"]),
div[data-testid="stMetric"] div[data-testid="stMetricDelta"]:has([color*="red"]),
div[data-testid="stMetric"] div[data-testid="stMetricDelta"][data-direction="inverse"] {
    background: rgba(244, 63, 94, 0.2) !important;
    color: #fb7185 !important;
    border: 1px solid rgba(244, 63, 94, 0.4) !important;
}
div[data-testid="stMetric"] div[data-testid="stMetricDelta"]:has(svg[data-testid="stMetricDeltaIcon-Down"]) svg {
    fill: #fb7185 !important;
}
div[data-testid="stMetric"] div[data-testid="stMetricDelta"]:has(svg[data-testid="stMetricDeltaIcon-Down"]) * {
    color: #fb7185 !important;
}

/* 6. 单选按钮胶囊容器 (stRadio) */
div[data-testid="stRadio"] > div[role="radiogroup"] {
    background: #131b2a !important;
    padding: 6px 14px !important;
    border-radius: 10px !important;
    border: 1px solid #223048 !important;
    gap: 16px !important;
}
div[data-testid="stRadio"] > div[role="radiogroup"] label,
div[data-testid="stRadio"] > div[role="radiogroup"] label p,
div[data-testid="stRadio"] > div[role="radiogroup"] label span,
div[data-testid="stRadio"] > div[role="radiogroup"] [data-testid="stMarkdownContainer"] p {
    color: #f1f5f9 !important;
    font-size: 14px !important;
    font-weight: 500 !important;
}
div[data-testid="stRadio"] > div[role="radiogroup"] label:hover p,
div[data-testid="stRadio"] > div[role="radiogroup"] label:hover span {
    color: #38bdf8 !important;
}
div[data-testid="stRadio"] > label p,
div[data-testid="stRadio"] > label span {
    color: #94a3b8 !important;
    font-size: 14px !important;
    font-weight: 600 !important;
}

/* 7. 折叠面板 (stExpander) 强力暗色覆盖 - 彻底根除白底横幅 */
[data-testid="stExpander"],
div[data-testid="stExpander"],
details[data-testid="stExpander"],
div.stExpander,
details.stExpander,
.stExpander {
    background: #131b2a !important;
    background-color: #131b2a !important;
    border: 1px solid #223048 !important;
    border-radius: 10px !important;
    overflow: hidden !important;
}

[data-testid="stExpander"] details,
div[data-testid="stExpander"] details,
details.stExpander {
    background: #131b2a !important;
    background-color: #131b2a !important;
    border: none !important;
    border-radius: 10px !important;
    overflow: hidden !important;
}

[data-testid="stExpander"] summary,
div[data-testid="stExpander"] summary,
details[data-testid="stExpander"] summary,
summary {
    background: #131b2a !important;
    background-color: #131b2a !important;
    color: #f8fafc !important;
    border-radius: 8px !important;
}

[data-testid="stExpander"] summary:hover,
div[data-testid="stExpander"] summary:hover,
details[data-testid="stExpander"] summary:hover {
    background: #1e293b !important;
    background-color: #1e293b !important;
}

[data-testid="stExpander"] summary *,
div[data-testid="stExpander"] summary *,
details[data-testid="stExpander"] summary *,
summary * {
    color: #f8fafc !important;
    background-color: transparent !important;
}

[data-testid="stExpander"] [data-testid="stExpanderDetails"],
[data-testid="stExpanderDetails"] {
    background: #0b0f19 !important;
    background-color: #0b0f19 !important;
    color: #cbd5e1 !important;
    border-top: 1px solid #223048 !important;
}

/* 8. 下拉框与文本输入框 (Selectbox, TextInput, Form) */
div[data-testid="stForm"] {
    background: #0e131f !important;
    border: 1px solid #223048 !important;
    border-radius: 10px !important;
    padding: 14px !important;
}
div[data-baseweb="select"] > div,
input[type="text"],
[data-baseweb="input"] input {
    background-color: #131b2a !important;
    border-color: #26354a !important;
    color: #f8fafc !important;
}
div[data-baseweb="select"] span {
    color: #f8fafc !important;
}
[data-baseweb="popover"],
[data-baseweb="menu"],
ul[data-baseweb="menu"] {
    background-color: #131b2a !important;
    color: #f8fafc !important;
    border: 1px solid #26354a !important;
}
li[data-baseweb="menu-item"] {
    color: #cbd5e1 !important;
}
li[data-baseweb="menu-item"]:hover {
    background-color: #1e293b !important;
    color: #ffffff !important;
}

/* 9. 全站各类按钮 (stButton, stFormSubmitButton, BaseButton) */
div[data-testid="stButton"] button,
div[data-testid="stFormSubmitButton"] button,
div.stButton button,
div.stFormSubmitButton button,
button[data-testid*="stBaseButton"],
button[data-testid*="FormSubmit"],
button[kind*="FormSubmit"],
button[kind="secondary"],
button[kind="primary"] {
    background: #1e3a8a !important;
    background-color: #1e3a8a !important;
    color: #ffffff !important;
    border: 1px solid #3b82f6 !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    font-size: 15px !important;
    transition: all 0.2s ease !important;
}

div[data-testid="stButton"] button:hover,
div[data-testid="stFormSubmitButton"] button:hover,
div.stButton button:hover,
div.stFormSubmitButton button:hover,
button[data-testid*="stBaseButton"]:hover,
button[data-testid*="FormSubmit"]:hover {
    background: #2563eb !important;
    background-color: #2563eb !important;
    border-color: #60a5fa !important;
    color: #ffffff !important;
    box-shadow: 0 4px 14px rgba(37, 99, 235, 0.45) !important;
}

div[data-testid="stButton"] button *,
div[data-testid="stFormSubmitButton"] button *,
button[data-testid*="stBaseButton"] *,
button[data-testid*="FormSubmit"] * {
    color: #ffffff !important;
    background-color: transparent !important;
}

/* 10. 提示与警告框 (stAlert, stInfo, stWarning) */
[data-testid="stAlert"] {
    background: #131b2a !important;
    border: 1px solid #223048 !important;
    border-radius: 8px !important;
}
[data-testid="stAlert"] p {
    color: #e2e8f0 !important;
}

/* 11. 自定义业务卡片与横幅 */
.company-desc-box {
    background-color: #131b2a !important;
    color: #e2e8f0 !important;
    border: 1px solid #223048 !important;
    border-left: 4px solid #3b82f6 !important;
}
div[style*="background-color: rgba(240,242,246"] {
    background-color: rgba(19, 27, 42, 0.85) !important;
    color: #f1f5f9 !important;
    border: 1px solid #223048 !important;
}

/* 12. 数据表格 (stDataFrame & Glide Data Grid) 容器与边框规范 */
div[data-testid="stDataFrame"] {
    border: 1px solid #223048 !important;
    border-radius: 8px !important;
    overflow: hidden !important;
}

/* 13. 原生表格 (stTable) */
div[data-testid="stTable"] table {
    background-color: #0e131f !important;
    color: #f8fafc !important;
    border-collapse: collapse !important;
    border: 1px solid #223048 !important;
    border-radius: 8px !important;
    width: 100% !important;
}
div[data-testid="stTable"] th {
    background-color: #131b2a !important;
    color: #ffffff !important;
    border: 1px solid #223048 !important;
    padding: 10px 14px !important;
    font-size: 14px !important;
    font-weight: 600 !important;
}
div[data-testid="stTable"] td {
    background-color: #0e131f !important;
    color: #cbd5e1 !important;
    border: 1px solid #1e293b !important;
    padding: 8px 14px !important;
    font-size: 14px !important;
}

/* 14. 极客终端专业数据表格样式 (.macro-terminal-table) */
.macro-terminal-table-container {
    width: 100%;
    overflow-x: auto;
    border: 1px solid #223048;
    border-radius: 8px;
    background-color: #0e131f;
    margin: 10px 0;
    box-shadow: 0 4px 16px rgba(0,0,0,0.3);
}
.macro-terminal-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 14px;
    color: #cbd5e1;
    text-align: left;
}
.macro-terminal-table th {
    background-color: #131b2a;
    color: #f8fafc;
    font-weight: 600;
    padding: 12px 16px;
    border-bottom: 2px solid #223048;
    white-space: nowrap;
}
.macro-terminal-table td {
    padding: 10px 16px;
    border-bottom: 1px solid #1e293b;
    white-space: nowrap;
}
.macro-terminal-table tr:hover {
    background-color: rgba(37, 99, 235, 0.12);
}
.macro-terminal-table tr:last-child td {
    border-bottom: none;
}

/* 15. Plotly Rangeselector SVG 样式强化 (彻底根除白底方块) */
.rangeselector rect {
    fill: #1e293b !important;
    stroke: #334155 !important;
}
.rangeselector text {
    fill: #f8fafc !important;
    font-size: 14px !important;
}
.rangeselector .button.active rect {
    fill: #2563eb !important;
    stroke: #3b82f6 !important;
}
.rangeslider-bg {
    fill: #131b2a !important;
}
</style>
"""
    else:
        return """
<style>
/* =================================================================
   ☀️ 清爽典雅日间模式 (Bright / Daytime Professional Theme)
   ================================================================= */

/* 1. 整体页面画布、主视口与侧边栏 */
.stApp,
[data-testid="stAppViewContainer"],
[data-testid="stHeader"],
[data-testid="stMainBlockContainer"],
.main {
    background-color: #f8fafc !important;
    color: #0f172a !important;
}

[data-testid="stSidebar"],
[data-testid="stSidebarContent"],
section[data-testid="stSidebar"] {
    background-color: #ffffff !important;
    border-right: 1px solid #e2e8f0 !important;
}

/* 2. 排版与文本颜色：深炭黑主标题与优雅板岩灰分级层级 */
h1, h2, h3, h4, h5, h6,
[data-testid="stHeadingWithActionElements"] {
    color: #0f172a !important;
}

p, span, label, li,
[data-testid="stMarkdownContainer"] p,
[data-testid="stMarkdownContainer"] span,
[data-testid="stMarkdownContainer"] li,
[data-testid="stWidgetLabel"] p,
[data-testid="stWidgetLabel"] span {
    color: #334155 !important;
}

strong, b {
    color: #0f172a !important;
}

a {
    color: #2563eb !important;
}

hr {
    border-color: #e2e8f0 !important;
}

[data-testid="stCaptionContainer"] p, small {
    color: #64748b !important;
}

/* 2.1 行内代码与状态小胶囊 (Inline Code & Badges) */
code, pre, kbd,
[data-testid="stMarkdownContainer"] code,
[data-testid="stMarkdownContainer"] pre {
    background: #f1f5f9 !important;
    background-color: #f1f5f9 !important;
    color: #0284c7 !important;
    border: 1px solid #cbd5e1 !important;
    border-radius: 5px !important;
    padding: 3px 8px !important;
    font-size: 13px !important;
    font-weight: 600 !important;
}

/* 3. 主导航条 (st.segmented_control / stButtonGroup) 典雅浅色覆盖 */
div[data-testid="stButtonGroup"],
div.stButtonGroup,
div[data-testid="stSegmentedControl"],
[data-baseweb="segmented-control"] {
    display: flex !important;
    flex-wrap: wrap !important;
    gap: 8px !important;
    padding: 6px 0 16px 0 !important;
    background: transparent !important;
    background-color: transparent !important;
    border: none !important;
}

div[data-testid="stButtonGroup"] button,
div.stButtonGroup button,
button[data-testid="stBaseButton-segmented_control"],
button[data-testid="stBaseButton-segmented_controlActive"],
div[data-testid="stSegmentedControl"] button,
div[data-testid="stSegmentedControl"] [data-testid*="Button"],
div[data-testid="stSegmentedControl"] [data-baseweb="button-group"] button,
div[data-testid="stSegmentedControl"] [role="radiogroup"] button,
div[data-testid="stSegmentedControl"] [role="radio"] {
    font-size: 15px !important;
    font-weight: 600 !important;
    padding: 10px 18px !important;
    border-radius: 8px !important;
    color: #334155 !important;
    background: #f8fafc !important;
    background-color: #f8fafc !important;
    border: 1px solid #cbd5e1 !important;
    box-shadow: 0 1px 3px rgba(0,0,0,0.04) !important;
    transition: all 0.2s ease !important;
}

div[data-testid="stButtonGroup"] button:not([data-testid*="Active"]):not([aria-checked="true"]):not([aria-selected="true"]):not([data-state="active"]),
div.stButtonGroup button:not([data-testid*="Active"]):not([aria-checked="true"]):not([aria-selected="true"]):not([data-state="active"]),
button[data-testid="stBaseButton-segmented_control"],
div[data-testid="stSegmentedControl"] button:not([aria-selected="true"]):not([aria-checked="true"]) {
    background: #f8fafc !important;
    background-color: #f8fafc !important;
    color: #334155 !important;
    border: 1px solid #cbd5e1 !important;
}

div[data-testid="stButtonGroup"] button[data-testid*="Active"],
div[data-testid="stButtonGroup"] button[aria-checked="true"],
div[data-testid="stButtonGroup"] button[aria-selected="true"],
div[data-testid="stButtonGroup"] button[data-state="active"],
div.stButtonGroup button[data-testid*="Active"],
button[data-testid="stBaseButton-segmented_controlActive"],
div[data-testid="stSegmentedControl"] button[aria-selected="true"],
div[data-testid="stSegmentedControl"] button[aria-checked="true"],
div[data-testid="stSegmentedControl"] button[aria-pressed="true"],
div[data-testid="stSegmentedControl"] button[data-state="active"],
div[data-testid="stSegmentedControl"] [role="radio"][aria-checked="true"] {
    color: #ffffff !important;
    background: #2563eb !important;
    background-color: #2563eb !important;
    border-color: #1d4ed8 !important;
    box-shadow: 0 4px 12px rgba(37, 99, 235, 0.25) !important;
}

div[data-testid="stSegmentedControl"] button[aria-selected="true"] *,
div[data-testid="stSegmentedControl"] button[aria-checked="true"] * {
    color: #ffffff !important;
    font-weight: 700 !important;
}

div[data-testid="stSegmentedControl"] button:hover,
div[data-testid="stSegmentedControl"] [role="radio"]:hover {
    color: #0f172a !important;
    background: #e2e8f0 !important;
    border-color: #3b82f6 !important;
}

/* 4. 子标签页 (stTabs) 典雅浅色覆盖 */
div[data-testid="stTabs"] [data-baseweb="tab-list"] {
    background: transparent !important;
    background-color: transparent !important;
    border-bottom: 2px solid #e2e8f0 !important;
    gap: 8px !important;
}

div[data-testid="stTabs"] button[data-baseweb="tab"],
div[data-testid="stTabs"] [role="tab"] {
    color: #64748b !important;
    font-size: 15px !important;
    font-weight: 600 !important;
    background: #f8fafc !important;
    background-color: #f8fafc !important;
    border: 1px solid #e2e8f0 !important;
    border-bottom: none !important;
    border-radius: 8px 8px 0 0 !important;
    padding: 8px 18px !important;
    transition: all 0.2s ease !important;
}

div[data-testid="stTabs"] button[data-baseweb="tab"]:not([aria-selected="true"]) {
    background: #f8fafc !important;
    color: #64748b !important;
}

div[data-testid="stTabs"] button[data-baseweb="tab"][aria-selected="true"],
div[data-testid="stTabs"] [role="tab"][aria-selected="true"] {
    color: #2563eb !important;
    background: #ffffff !important;
    background-color: #ffffff !important;
    border: 1px solid #2563eb !important;
    border-bottom: 2px solid #2563eb !important;
}

div[data-testid="stTabs"] button[data-baseweb="tab"][aria-selected="true"] * {
    color: #2563eb !important;
    font-weight: 700 !important;
}

div[data-testid="stTabs"] button[data-baseweb="tab"]:hover,
div[data-testid="stTabs"] [role="tab"]:hover {
    color: #0f172a !important;
    background: #e2e8f0 !important;
}

div[data-testid="stTabs"] [data-baseweb="tab-highlight"] {
    background-color: #2563eb !important;
}

/* 5. KPI 指标卡片 (stMetric) - 目前、最新交易日等卡片纯白清爽质感 (告别违和黑底) */
div[data-testid="stMetric"] {
    background: #ffffff !important;
    border: 1px solid #e2e8f0 !important;
    border-radius: 12px !important;
    padding: 14px 18px !important;
    box-shadow: 0 2px 10px rgba(0,0,0,0.05) !important;
}
div[data-testid="stMetric"] [data-testid="stMetricLabel"],
div[data-testid="stMetric"] [data-testid="stMetricLabel"] p {
    font-size: 14px !important;
    color: #64748b !important;
    font-weight: 600 !important;
}
div[data-testid="stMetric"] [data-testid="stMetricLabel"] svg {
    color: #64748b !important;
}
div[data-testid="stMetric"] [data-testid="stMetricValue"],
div[data-testid="stMetric"] [data-testid="stMetricValue"] div {
    font-size: 26px !important;
    font-weight: 700 !important;
    color: #0f172a !important;
    letter-spacing: -0.5px !important;
}
div[data-testid="stMetric"] div[data-testid="stMetricDelta"] {
    font-size: 13px !important;
    font-weight: 600 !important;
    padding: 3px 10px !important;
    border-radius: 6px !important;
    display: inline-flex !important;
    align-items: center !important;
    width: fit-content !important;
    margin-top: 4px !important;
}
div[data-testid="stMetric"] div[data-testid="stMetricDelta"]:has(svg[data-testid="stMetricDeltaIcon-Up"]),
div[data-testid="stMetric"] div[data-testid="stMetricDelta"]:has([color*="green"]),
div[data-testid="stMetric"] div[data-testid="stMetricDelta"][data-direction="normal"] {
    background: rgba(16, 185, 129, 0.12) !important;
    color: #059669 !important;
    border: 1px solid rgba(16, 185, 129, 0.3) !important;
}
div[data-testid="stMetric"] div[data-testid="stMetricDelta"]:has(svg[data-testid="stMetricDeltaIcon-Up"]) svg {
    fill: #059669 !important;
}
div[data-testid="stMetric"] div[data-testid="stMetricDelta"]:has(svg[data-testid="stMetricDeltaIcon-Up"]) * {
    color: #059669 !important;
}
div[data-testid="stMetric"] div[data-testid="stMetricDelta"]:has(svg[data-testid="stMetricDeltaIcon-Down"]),
div[data-testid="stMetric"] div[data-testid="stMetricDelta"]:has([color*="red"]),
div[data-testid="stMetric"] div[data-testid="stMetricDelta"][data-direction="inverse"] {
    background: rgba(239, 68, 68, 0.12) !important;
    color: #dc2626 !important;
    border: 1px solid rgba(239, 68, 68, 0.3) !important;
}
div[data-testid="stMetric"] div[data-testid="stMetricDelta"]:has(svg[data-testid="stMetricDeltaIcon-Down"]) svg {
    fill: #dc2626 !important;
}
div[data-testid="stMetric"] div[data-testid="stMetricDelta"]:has(svg[data-testid="stMetricDeltaIcon-Down"]) * {
    color: #dc2626 !important;
}

/* 6. 单选按钮胶囊容器 (stRadio) */
div[data-testid="stRadio"] > div[role="radiogroup"] {
    background: #ffffff !important;
    padding: 6px 14px !important;
    border-radius: 10px !important;
    border: 1px solid #cbd5e1 !important;
    box-shadow: 0 1px 4px rgba(0,0,0,0.04) !important;
    gap: 16px !important;
}
div[data-testid="stRadio"] > div[role="radiogroup"] label,
div[data-testid="stRadio"] > div[role="radiogroup"] label p,
div[data-testid="stRadio"] > div[role="radiogroup"] label span,
div[data-testid="stRadio"] > div[role="radiogroup"] [data-testid="stMarkdownContainer"] p {
    color: #1e293b !important;
    font-size: 14px !important;
    font-weight: 500 !important;
}
div[data-testid="stRadio"] > div[role="radiogroup"] label:hover p,
div[data-testid="stRadio"] > div[role="radiogroup"] label:hover span {
    color: #2563eb !important;
}
div[data-testid="stRadio"] > label p,
div[data-testid="stRadio"] > label span {
    color: #475569 !important;
    font-size: 14px !important;
    font-weight: 600 !important;
}

/* 7. 折叠面板 (stExpander) 典雅浅色覆盖 */
[data-testid="stExpander"],
div[data-testid="stExpander"],
details[data-testid="stExpander"],
div.stExpander,
details.stExpander,
.stExpander {
    background: #ffffff !important;
    background-color: #ffffff !important;
    border: 1px solid #e2e8f0 !important;
    border-radius: 10px !important;
    box-shadow: 0 1px 4px rgba(0,0,0,0.03) !important;
    overflow: hidden !important;
}

[data-testid="stExpander"] details,
div[data-testid="stExpander"] details,
details.stExpander {
    background: #ffffff !important;
    background-color: #ffffff !important;
    border: none !important;
    border-radius: 10px !important;
    overflow: hidden !important;
}

[data-testid="stExpander"] summary,
div[data-testid="stExpander"] summary,
details[data-testid="stExpander"] summary,
summary {
    background: #ffffff !important;
    background-color: #ffffff !important;
    color: #0f172a !important;
    border-radius: 8px !important;
}

[data-testid="stExpander"] summary:hover,
div[data-testid="stExpander"] summary:hover,
details[data-testid="stExpander"] summary:hover {
    background: #f1f5f9 !important;
    background-color: #f1f5f9 !important;
}

[data-testid="stExpander"] summary *,
div[data-testid="stExpander"] summary *,
details[data-testid="stExpander"] summary *,
summary * {
    color: #0f172a !important;
    background-color: transparent !important;
}

[data-testid="stExpander"] [data-testid="stExpanderDetails"],
[data-testid="stExpanderDetails"] {
    background: #ffffff !important;
    background-color: #ffffff !important;
    color: #334155 !important;
    border-top: 1px solid #e2e8f0 !important;
}

/* 8. 下拉框与文本输入框 (Selectbox, TextInput, Form) */
div[data-testid="stForm"] {
    background: #ffffff !important;
    border: 1px solid #e2e8f0 !important;
    border-radius: 10px !important;
    padding: 14px !important;
    box-shadow: 0 1px 4px rgba(0,0,0,0.03) !important;
}
div[data-baseweb="select"] > div,
input[type="text"],
[data-baseweb="input"] input {
    background-color: #ffffff !important;
    border-color: #cbd5e1 !important;
    color: #0f172a !important;
}
div[data-baseweb="select"] span {
    color: #0f172a !important;
}
[data-baseweb="popover"],
[data-baseweb="menu"],
ul[data-baseweb="menu"] {
    background-color: #ffffff !important;
    color: #0f172a !important;
    border: 1px solid #cbd5e1 !important;
}
li[data-baseweb="menu-item"] {
    color: #334155 !important;
}
li[data-baseweb="menu-item"]:hover {
    background-color: #f1f5f9 !important;
    color: #0f172a !important;
}

/* 9. 全站各类按钮 (stButton, stFormSubmitButton, BaseButton) */
div[data-testid="stButton"] button,
div[data-testid="stFormSubmitButton"] button,
div.stButton button,
div.stFormSubmitButton button,
button[data-testid*="stBaseButton"],
button[data-testid*="FormSubmit"],
button[kind*="FormSubmit"],
button[kind="secondary"],
button[kind="primary"] {
    background: #f1f5f9 !important;
    color: #0f172a !important;
    border: 1px solid #cbd5e1 !important;
    border-radius: 8px !important;
    font-weight: 600 !important;
    font-size: 15px !important;
    transition: all 0.2s ease !important;
}
div[data-testid="stButton"] button:hover,
div[data-testid="stFormSubmitButton"] button:hover,
div.stButton button:hover,
div.stFormSubmitButton button:hover,
button[data-testid*="stBaseButton"]:hover,
button[data-testid*="FormSubmit"]:hover {
    background: #2563eb !important;
    border-color: #1d4ed8 !important;
    color: #ffffff !important;
    box-shadow: 0 4px 12px rgba(37, 99, 235, 0.25) !important;
}

div[data-testid="stButton"] button *,
div[data-testid="stFormSubmitButton"] button *,
button[data-testid*="stBaseButton"] *,
button[data-testid*="FormSubmit"] * {
    color: inherit !important;
    background-color: transparent !important;
}

/* 10. 提示与警告框 (stAlert, stInfo, stWarning) */
[data-testid="stAlert"] {
    background: #ffffff !important;
    border: 1px solid #e2e8f0 !important;
    border-radius: 8px !important;
}
[data-testid="stAlert"] p {
    color: #1e293b !important;
}

/* 11. 自定义业务卡片与横幅 */
.company-desc-box {
    background-color: #f8fafc !important;
    color: #1e293b !important;
    border: 1px solid #e2e8f0 !important;
    border-left: 4px solid #3b82f6 !important;
}
div[style*="background-color: rgba(240,242,246"] {
    background-color: #ffffff !important;
    color: #0f172a !important;
    border: 1px solid #e2e8f0 !important;
    box-shadow: 0 1px 4px rgba(0,0,0,0.03) !important;
}

/* 12. 数据表格 (stDataFrame & Glide Data Grid) 容器与边框规范 */
div[data-testid="stDataFrame"] {
    border: 1px solid #e2e8f0 !important;
    border-radius: 8px !important;
    overflow: hidden !important;
}

/* 13. 原生表格 (stTable) */
div[data-testid="stTable"] table {
    background-color: #ffffff !important;
    color: #0f172a !important;
    border-collapse: collapse !important;
    border: 1px solid #e2e8f0 !important;
    border-radius: 8px !important;
    width: 100% !important;
}
div[data-testid="stTable"] th {
    background-color: #f8fafc !important;
    color: #0f172a !important;
    border: 1px solid #e2e8f0 !important;
    padding: 10px 14px !important;
    font-size: 14px !important;
    font-weight: 600 !important;
}
div[data-testid="stTable"] td {
    background-color: #ffffff !important;
    color: #334155 !important;
    border: 1px solid #f1f5f9 !important;
    padding: 8px 14px !important;
    font-size: 14px !important;
}

/* 14. 极客终端专业数据表格样式 (.macro-terminal-table) */
.macro-terminal-table-container {
    width: 100%;
    overflow-x: auto;
    border: 1px solid #e2e8f0;
    border-radius: 8px;
    background-color: #ffffff;
    margin: 10px 0;
    box-shadow: 0 2px 8px rgba(0,0,0,0.04);
}
.macro-terminal-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 14px;
    color: #334155;
    text-align: left;
}
.macro-terminal-table th {
    background-color: #f8fafc;
    color: #0f172a;
    font-weight: 600;
    padding: 12px 16px;
    border-bottom: 2px solid #e2e8f0;
    white-space: nowrap;
}
.macro-terminal-table td {
    padding: 10px 16px;
    border-bottom: 1px solid #f1f5f9;
    white-space: nowrap;
}
.macro-terminal-table tr:hover {
    background-color: rgba(37, 99, 235, 0.05);
}
.macro-terminal-table tr:last-child td {
    border-bottom: none;
}

/* 15. Plotly Rangeselector SVG 样式强化 */
.rangeselector rect {
    fill: #f1f5f9 !important;
    stroke: #cbd5e1 !important;
}
.rangeselector text {
    fill: #0f172a !important;
    font-size: 14px !important;
}
.rangeselector .button.active rect {
    fill: #3b82f6 !important;
    stroke: #2563eb !important;
}
.rangeslider-bg {
    fill: #f1f5f9 !important;
}
</style>
"""


# ------------------------------------------------------------------
# 自适应高品质 HTML 数据表格生成器 (彻底根除 Glide Data Grid 白底与错位)
# ------------------------------------------------------------------
def render_styled_table(df: pd.DataFrame, theme_mode: str = None) -> str:
    """
    生成高对比度、零瑕疵的自适应 HTML 数据表格
    支持 Dark Mode (深色极客) 与 Bright Mode (典雅日间)
    100% 免疫 Glide Data Grid canvas 缓存与白底问题
    """
    if df is None or df.empty:
        return ""

    if theme_mode is None:
        try:
            import streamlit as st
            theme_mode = st.session_state.get("theme_mode", "dark")
        except Exception:
            theme_mode = "dark"

    is_dark = (theme_mode == "dark")
    bg_container = "#0e131f" if is_dark else "#ffffff"
    border_color = "#223048" if is_dark else "#e2e8f0"
    th_bg = "#131b2a" if is_dark else "#f8fafc"
    th_color = "#f8fafc" if is_dark else "#0f172a"
    td_color = "#cbd5e1" if is_dark else "#334155"
    row_alt_bg = "#111827" if is_dark else "#f8fafc"

    headers = "".join([
        f"<th style='padding: 12px 16px; background: {th_bg}; color: {th_color}; "
        f"border-bottom: 2px solid {border_color}; font-size: 14px; font-weight: 600; "
        f"text-align: left; white-space: nowrap;'>{col}</th>"
        for col in df.columns
    ])

    rows = []
    for i, (_, row) in enumerate(df.iterrows()):
        bg = bg_container if i % 2 == 0 else row_alt_bg
        tds = "".join([
            f"<td style='padding: 10px 16px; color: {td_color}; "
            f"border-bottom: 1px solid {border_color}; font-size: 14px; white-space: nowrap;'>{val}</td>"
            for val in row
        ])
        rows.append(f"<tr style='background: {bg}; transition: background 0.2s;'>{tds}</tr>")

    rows_str = "".join(rows)
    return (
        f'<div class="macro-terminal-table-container" style="width: 100%; overflow-x: auto; '
        f'border: 1px solid {border_color}; border-radius: 8px; margin: 10px 0; background: {bg_container};">'
        f'<table class="macro-terminal-table" style="width: 100%; border-collapse: collapse; '
        f'font-family: -apple-system, BlinkMacSystemFont, \'Segoe UI\', Roboto, sans-serif;">'
        f'<thead><tr>{headers}</tr></thead>'
        f'<tbody>{rows_str}</tbody>'
        f'</table>'
        f'</div>'
    )


