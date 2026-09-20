"""
Macro & Equity Research Terminal
Main Entrypoint for Streamlit Web Application
"""
import importlib
import streamlit as st

# ------------------------------------------------------------------
# 模块导入与热重载安全机制 (防止 Streamlit Cloud 内存模块缓存导致 ImportError)
# ------------------------------------------------------------------
try:
    import visualization
    importlib.reload(visualization)
except Exception:
    pass

try:
    import data_service
    importlib.reload(data_service)
except Exception:
    pass

try:
    import macro_tab
    importlib.reload(macro_tab)
except Exception:
    pass

try:
    import stock_tab
    importlib.reload(stock_tab)
except Exception:
    pass

try:
    import semi_tab
    importlib.reload(semi_tab)
except Exception:
    pass

try:
    import company_tab
    importlib.reload(company_tab)
except Exception:
    pass

try:
    import reflexivity_tab
    importlib.reload(reflexivity_tab)
except Exception:
    pass

try:
    import industry_bubble_tab
    importlib.reload(industry_bubble_tab)
except Exception:
    pass

from data_service import get_current_time_str_eastern
from macro_tab import render_macro_tab
from stock_tab import render_stock_tab
from semi_tab import render_semi_tab
from company_tab import render_company_deep_dive_tab
from reflexivity_tab import render_reflexivity_tab
from industry_bubble_tab import render_industry_bubble_tab

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

tab_macro, tab_stock, tab_semi, tab_company, tab_reflexivity, tab_bubble = st.tabs([
    "🌐 宏观流动性与经济全景指标",
    "📈 个股全景追踪 & 估值与技术面",
    "⚡ 芯片半导体全产业链追踪",
    "🏢 财报深度拆解与公司基本面剖析 (Tab 4)",
    "🦅 索罗斯反身性大类配置 (Tab 5)",
    "📡 行业微观内生泡沫雷达 (Tab 6 · 聚焦 Layer 2 & 3)"
])

# ==================================================================
# TAB 1: 宏观全景与市场流动性
# ==================================================================
with tab_macro:
    render_macro_tab()

# ==================================================================
# TAB 2: 个股全景追踪 & 估值与技术面
# ==================================================================
with tab_stock:
    render_stock_tab()

# ==================================================================
# TAB 3: 半导体产业链追踪与相对表现矩阵
# ==================================================================
with tab_semi:
    render_semi_tab()

# ==================================================================
# TAB 4: 个股深度与基本面剖析 (Company Profile & Financials)
# ==================================================================
with tab_company:
    try:
        render_company_deep_dive_tab()
    except Exception as e:
        st.error(f"个股深度分析模块加载失败: {e}")

# ==================================================================
# TAB 5: 索罗斯反身性大类配置 (Soros Reflexivity Macro Allocation)
# ==================================================================
with tab_reflexivity:
    try:
        render_reflexivity_tab()
    except Exception as e:
        st.error(f"反身性大类配置模块加载失败: {e}")

# ==================================================================
# TAB 6: 行业微观内生泡沫雷达 (Industry Micro-Bubble Radar · Layer 2 & 3)
# ==================================================================
with tab_bubble:
    try:
        render_industry_bubble_tab()
    except Exception as e:
        st.error(f"行业微观内生泡沫雷达模块加载失败: {e}")
