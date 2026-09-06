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
    template: str = "plotly_white",
    hovermode: str = "x unified",
    uirevision: str = None,
    yaxis_title: str = None,
    showlegend: bool = True,
    **kwargs
) -> go.Figure:
    """
    统一设置 Plotly 图表的标准样式、高度、hover 交互与 uirevision 状态保持
    """
    layout_params = {
        "height": height,
        "template": template,
        "hovermode": hovermode,
        "showlegend": showlegend,
    }
    if title is not None:
        layout_params["title"] = title
    if uirevision is not None:
        layout_params["uirevision"] = uirevision
    if yaxis_title is not None:
        layout_params["yaxis_title"] = yaxis_title

    layout_params.update(kwargs)
    fig.update_layout(**layout_params)
    return fig
