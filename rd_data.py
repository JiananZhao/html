"""
Macro & Equity Research Terminal
Main Entrypoint for Streamlit Web Application
"""
import streamlit as st
from data_service import get_current_time_str_eastern
from macro_tab import render_macro_tab
from stock_tab import render_stock_tab
from semi_tab import render_semi_tab
from company_tab import render_company_deep_dive_tab
from reflexivity_tab import render_reflexivity_tab
from industry_bubble_tab import render_industry_bubble_tab
from huang_dynamics_tab import render_huang_dynamics_tab
from charts.theme import get_theme_css

# ------------------------------------------------------------------
# Streamlit 主页面设置与整体布局渲染
# ------------------------------------------------------------------
st.set_page_config(
    page_title="Macro & Equity Research Terminal",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("Macro Liquidity & Equity Research Terminal")
st.markdown("### 宏观流动性监控、半导体产业追踪与个股量化估值投研平台")

st.sidebar.markdown(f"**数据更新基准 (美东时间 EDT):** `{get_current_time_str_eastern()}`")
st.sidebar.markdown("---")

# ------------------------------------------------------------------
# 页面主导航：按需惰性渲染 (Lazy-Loading Conditional Execution)
# 彻底根治 Streamlit st.tabs 强制全量重跑全部 6 个 Tab (45+ 图表) 导致的 14 秒卡顿
# ------------------------------------------------------------------
TAB_OPTIONS = [
    "🌐 宏观流动性与经济全景指标",
    "📈 个股全景追踪 & 估值与技术面",
    "⚡ 芯片半导体全产业链追踪",
    "🏢 财报深度拆解与公司基本面剖析 (Tab 4)",
    "🦅 索罗斯反身性大类配置 (Tab 5)",
    "📡 行业微观内生泡沫雷达 (Tab 6 · 聚焦 Layer 2 & 3)",
    "🌌 黄文政动力学相空间引擎 (Tab 7 · 形式同源与李氏实证)"
]

# ------------------------------------------------------------------
# 界面显示模式切换 (Theme Switcher: Dark Mode vs Bright/Daytime Mode)
# ------------------------------------------------------------------
if "theme_mode" not in st.session_state:
    st.session_state["theme_mode"] = "dark"

st.sidebar.markdown("### 🌓 界面显示模式 (Theme)")
selected_theme_label = st.sidebar.radio(
    "主题选择",
    options=["🌙 深色极客夜间 (Dark Mode)", "☀️ 清爽典雅日间 (Bright Mode)"],
    index=0 if st.session_state["theme_mode"] == "dark" else 1,
    key="ui_theme_mode_radio",
    label_visibility="collapsed"
)
st.session_state["theme_mode"] = "dark" if "深色" in selected_theme_label else "light"
theme_mode = st.session_state["theme_mode"]

# ------------------------------------------------------------------
# 全局图表渲染引擎切换 (Global Chart Engine: ECharts vs Plotly)
# ------------------------------------------------------------------
if "global_chart_engine" not in st.session_state:
    st.session_state["global_chart_engine"] = "echarts"

st.sidebar.markdown("### 🎨 全局图表渲染引擎")
selected_engine_label = st.sidebar.radio(
    "渲染引擎选择",
    options=["⚡ 现代自适应引擎 (ECharts · 推荐)", "📊 传统 Plotly 统计引擎"],
    index=0 if st.session_state["global_chart_engine"] == "echarts" else 1,
    key="ui_global_chart_engine_radio",
    label_visibility="collapsed"
)
st.session_state["global_chart_engine"] = "echarts" if "现代" in selected_engine_label else "plotly"


# 注入当前模式的高品质全站设计系统 CSS (Dark Mode vs Bright Mode)
st.markdown(get_theme_css(theme_mode), unsafe_allow_html=True)

if "main_selected_tab" not in st.session_state:
    st.session_state["main_selected_tab"] = TAB_OPTIONS[0]

selected_tab = st.segmented_control(
    "系统主导航模块",
    options=TAB_OPTIONS,
    default=st.session_state["main_selected_tab"],
    key="main_tab_nav",
    label_visibility="collapsed"
)

if not selected_tab:
    selected_tab = st.session_state.get("main_selected_tab", TAB_OPTIONS[0])
else:
    st.session_state["main_selected_tab"] = selected_tab

import time
t_start = time.time()

# ==================================================================
# 按需惰性渲染：仅运行当前选中的 Tab
# ==================================================================
if selected_tab == TAB_OPTIONS[0]:
    render_macro_tab()
elif selected_tab == TAB_OPTIONS[1]:
    render_stock_tab()
elif selected_tab == TAB_OPTIONS[2]:
    render_semi_tab()
elif selected_tab == TAB_OPTIONS[3]:
    try:
        render_company_deep_dive_tab()
    except Exception as e:
        st.error(f"个股深度分析模块加载失败: {e}")
elif selected_tab == TAB_OPTIONS[4]:
    try:
        render_reflexivity_tab()
    except Exception as e:
        st.error(f"反身性大类配置模块加载失败: {e}")
elif selected_tab == TAB_OPTIONS[5]:
    try:
        render_industry_bubble_tab()
    except Exception as e:
        st.error(f"行业微观内生泡沫雷达模块加载失败: {e}")
elif selected_tab == TAB_OPTIONS[6]:
    try:
        render_huang_dynamics_tab()
    except Exception as e:
        st.error(f"黄文政动力学相空间引擎加载失败: {e}")

print(f"[PERF] Active tab [{selected_tab}] finished in: {time.time() - t_start:.3f}s", flush=True)

