"""
Quantitative Valuation & Financial Models
"""
import numpy as np

def calculate_reverse_dcf(
    current_price: float,
    ttm_fcf_per_share: float,
    wacc: float = 0.09,
    terminal_growth: float = 0.03,
    forecast_years: int = 10
) -> float:
    """
    反向自由现金流折现模型 (Reverse DCF):
    通过二分法根据当前股价倒算市场隐含的未来 10 年自由现金流年化复合增长率 (CAGR %)
    """
    if ttm_fcf_per_share <= 0 or current_price <= 0:
        return np.nan
    low_g, high_g = -0.50, 1.00
    for _ in range(100):
        mid_g = (low_g + high_g) / 2.0
        pv = 0.0
        cf = ttm_fcf_per_share
        for t in range(1, forecast_years + 1):
            cf *= (1 + mid_g)
            pv += cf / ((1 + wacc) ** t)
        terminal_val = (cf * (1 + terminal_growth)) / (wacc - terminal_growth)
        pv += terminal_val / ((1 + wacc) ** forecast_years)
        if abs(pv - current_price) < 0.01:
            return mid_g * 100.0
        if pv > current_price:
            high_g = mid_g
        else:
            low_g = mid_g
    return mid_g * 100.0
