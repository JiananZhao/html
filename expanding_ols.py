import numpy as np
import pandas as pd

def expanding_polyfit_residual(y_series: pd.Series, min_periods: int = 252) -> pd.DataFrame:
    """
    计算无前视的扩展窗口 OLS 对数残差。
    使用增量统计量公式 O(N) 避免每天重复拟合全部历史 O(N^2)。
    
    y_series: 通常是价格序列 (非对数)
    min_periods: 最小有效观测数量
    
    返回 DataFrame:
    - Log_Trend: 截至当日的趋势拟合值
    - Valuation_Residual: 100 * (log_p - Log_Trend)
    """
    n = len(y_series)
    log_p = np.full(n, np.nan)
    
    # 获取有效观测的索引
    valid_mask = (y_series > 0) & (~y_series.isna())
    valid_mask_np = valid_mask.values
    valid_indices = np.where(valid_mask_np)[0]
    
    log_p[valid_mask_np] = np.log(y_series.values[valid_mask_np])
    
    # 结果数组
    log_trend = np.full(n, np.nan)
    residuals = np.full(n, np.nan)
    
    # 增量统计变量
    sum_x = 0.0
    sum_y = 0.0
    sum_x2 = 0.0
    sum_xy = 0.0
    count = 0
    
    for i in range(n):
        if not valid_mask.iloc[i]:
            # 当前观测无效，保持 NaN
            continue
            
        x = i  # 使用全局时间索引作为自变量
        y = log_p[i]
        
        sum_x += x
        sum_y += y
        sum_x2 += x * x
        sum_xy += x * y
        count += 1
        
        if count >= min_periods:
            # 计算截距 a 和斜率 b
            # b = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x * sum_x)
            denominator = count * sum_x2 - sum_x * sum_x
            if denominator != 0:
                slope = (count * sum_xy - sum_x * sum_y) / denominator
                intercept = (sum_y - slope * sum_x) / count
                
                # 计算当天的趋势和残差（只能访问 <= i 的信息）
                trend_i = slope * x + intercept
                log_trend[i] = trend_i
                residuals[i] = (y - trend_i) * 100.0
            
    return pd.DataFrame({
        'Log_Trend': log_trend,
        'Valuation_Residual': residuals
    }, index=y_series.index)

def test_prefix_ols_validation(y_series: pd.Series, i: int) -> tuple:
    """
    保留独立的逐日前缀 OLS 实现作为验证基准。
    计算并返回在第 i 天结束时，截断数据的 OLS 结果。
    """
    subset = y_series.iloc[:i+1]
    valid_mask = (subset > 0) & (~subset.isna())
    
    valid_mask_np = valid_mask.values
    if valid_mask_np.sum() < 2:
        return np.nan, np.nan, np.nan, np.nan
        
    x = np.where(valid_mask_np)[0]
    y = np.log(subset.values[valid_mask_np])
    
    slope, intercept = np.polyfit(x, y, 1)
    
    if valid_mask.iloc[-1]:
        trend = slope * i + intercept
        residual = (y[-1] - trend) * 100.0
        return slope, intercept, trend, residual
    else:
        return slope, intercept, np.nan, np.nan
