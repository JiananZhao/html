import io
import os
import re
import sys
import datetime
import importlib
import numpy as np
import pandas as pd
import streamlit as st
from zoneinfo import ZoneInfo

from data_processing import load_and_transform_data
from market_breadth_viz import render_market_breadth_ui

# ------------------------------------------------------------------
# 模块导入与热重载安全机制 (防止 Streamlit Cloud 内存模块缓存导致 ImportError)
# ------------------------------------------------------------------
try:
    import market_breadth_viz
    importlib.reload(market_breadth_viz)
    from market_breadth_viz import render_market_breadth_ui
except Exception:
    pass

try:
    import company_tab
    importlib.reload(company_tab)
    from company_tab import render_company_deep_dive_tab
except Exception:
    pass

from visualization import (
    create_treasury_chart,
    create_unemployment_chart,
    create_sp500_market_cap_chart,
    create_soxx_market_cap_chart,
    create_soxx_relative_strength_chart,
    create_sp500_sector_correlation_heatmap,
    create_soxx_individual_relative_strength_chart,
    create_semi_ratio_vs_soxx_chart,
    create_soxx_scatter_valuation_chart,
    create_stock_price_chart,
    create_relative_performance_chart,
    create_financial_trends_chart,
    create_pe_ps_band_chart,
    create_technical_momentum_chart,
    create_yield_spreads_chart,
    create_jobless_claims_chart,
    create_dxy_chart,
    create_inflation_wages_chart,
    create_sahm_rule_chart,
    create_real_yield_chart,
    create_liquidity_gauge_chart,
    create_m2_supply_chart,
    create_high_yield_spread_chart,
    create_sloos_credit_chart,
    create_net_liquidity_chart
)
