# -*- coding: utf-8 -*-
"""
core_engine/stock_data_service.py
=================================
高可用个股数据获取与冷却重试状态机服务

核心原则 (严格遵守 AGENTS.md 与用户六大规范):
1. 细粒度拆分：公司资料 (Profile)、行情 (History)、财报 (Statements)、新闻 (News) 分别获取、分别缓存、分别记录状态；
2. 失败不长效缓存：底层获取失败时抛出受控异常 StockDataFetchError，防止 Streamlit 将空数据或错误字典写入长期缓存；
3. 独立重试冷却状态机：401 阶梯冷却、429 指数退避，冷却期内直接拦截上游调用，冷却过期自动恢复探测；
4. 真实性与本地优先：支持从本地各行业主数据集 (smh_constituents_local.csv 等) 提取真实历史收盘价，
   明确标注历史快照日期，严禁伪造 OHLC 或冒充实时行情；
5. 区分真实 0 与缺失 N/A，杜绝布尔隐式转换陷阱。
"""

import os
import time
import threading
from typing import Dict, Any, Tuple, Optional
import pandas as pd
import numpy as np
import streamlit as st

# =====================================================================
# 1. 受控异常与状态枚举
# =====================================================================
class StockDataFetchError(Exception):
    """业务受控数据获取异常，用于触发 Streamlit 缓存跳过与上游冷却记录"""
    def __init__(self, message: str, status_code: Optional[int] = None, is_transient: bool = True, is_not_found: bool = False):
        super().__init__(message)
        self.status_code = status_code
        self.is_transient = is_transient
        self.is_not_found = is_not_found

# =====================================================================
# 2. 独立冷却重试状态机 (In-Memory Thread-Safe Cooldown Manager)
# =====================================================================
class StockCooldownManager:
    """
    针对 (symbol, domain) 颗粒度的受控冷却管理器。
    - 401 Unauthorized: 阶梯冷却 300 秒 (5分钟)，避免频繁触发被彻底封禁；
    - 429 Too Many Requests: 尊重 retry_after 或应用指数退避 (60s -> 120s -> 240s, 最大 600s)；
    - 普通网络超时/空响应: 30 秒短冷却；
    - 成功后自动清除冷却记录。
    """
    def __init__(self):
        self._lock = threading.Lock()
        self._failures: Dict[Tuple[str, str], Dict[str, Any]] = {}

    def is_in_cooldown(self, symbol: str, domain: str) -> Tuple[bool, float, str]:
        """
        检查指定标的和数据域是否正处于冷却期。
        返回: (是否冷却中, 剩余冷却秒数, 冷却原因)
        """
        key = (symbol.upper().strip(), domain.lower().strip())
        now = time.time()
        with self._lock:
            record = self._failures.get(key)
            if not record:
                return False, 0.0, ""
            
            elapsed = now - record["last_failure_time"]
            cooldown = record["cooldown_seconds"]
            if elapsed < cooldown:
                remaining = cooldown - elapsed
                return True, remaining, record.get("reason", "上游接口保护中")
            else:
                # 冷却已过期，允许下一次探测
                return False, 0.0, ""

    def record_failure(self, symbol: str, domain: str, error_type: str, 
                       status_code: Optional[int] = None, retry_after: Optional[float] = None) -> float:
        """记录失败并计算下一次冷却时间"""
        key = (symbol.upper().strip(), domain.lower().strip())
        now = time.time()
        with self._lock:
            prev = self._failures.get(key, {"failure_count": 0})
            count = prev.get("failure_count", 0) + 1
            
            if status_code == 401:
                cooldown_seconds = 300.0  # 401 封锁 5 分钟冷却
                reason = "HTTP 401 Unauthorized (接口鉴权或IP访问受限)"
            elif status_code == 429:
                if retry_after and retry_after > 0:
                    cooldown_seconds = float(retry_after)
                else:
                    cooldown_seconds = min(600.0, 60.0 * (2 ** min(count - 1, 4)))
                reason = f"HTTP 429 Too Many Requests (限流退避: {int(cooldown_seconds)}s)"
            else:
                cooldown_seconds = min(120.0, 30.0 * min(count, 4))
                reason = f"{error_type} (冷却 {int(cooldown_seconds)}s)"

            self._failures[key] = {
                "last_failure_time": now,
                "cooldown_seconds": cooldown_seconds,
                "status_code": status_code,
                "reason": reason,
                "failure_count": count
            }
            return cooldown_seconds

    def record_success(self, symbol: str, domain: str):
        """成功后立即清除冷却记录"""
        key = (symbol.upper().strip(), domain.lower().strip())
        with self._lock:
            if key in self._failures:
                del self._failures[key]

    def reset(self):
        """重置所有冷却记录 (用于单元测试或手动刷新)"""
        with self._lock:
            self._failures.clear()

# 全局单例管理器
cooldown_manager = StockCooldownManager()

# =====================================================================
# 3. 本地主数据集离线历史行情提取器 (Local-First Price Fallback)
# =====================================================================
def get_local_stock_price_fallback(symbol: str) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    优先检查本地已清洗的标准主数据集 (smh_constituents_local.csv 等)。
    若命中对应资产，提取真实历史收盘价序列。
    
    必须绝对遵守：
    1. 仅有收盘价就仅展示收盘价，绝对不伪造 OHLC；
    2. 标明数据来源文件和最后日期 (截至 2026-09-11)；
    3. 严禁冠以“实时行情”或“当前最新价”标签欺骗用户。
    """
    sym = symbol.strip().upper()
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    # 候选本地数据集映射 (行业成分股离线库)
    local_files = [
        ("smh_constituents_local.csv", "半导体产业链离线主数据集 (SMH)"),
        ("igv_constituents_local.csv", "软件科技离线主数据集 (IGV)"),
        ("financial_constituents_local.csv", "金融银行离线主数据集 (Financials)"),
        ("energy_constituents_local.csv", "传统能源离线主数据集 (Energy)"),
        ("real_estate_constituents_local.csv", "房地产信托离线主数据集 (Real Estate)"),
    ]
    
    for fname, label in local_files:
        fpath = os.path.join(base_dir, fname)
        if not os.path.exists(fpath):
            continue
        try:
            # 仅预览首行确认是否有该列
            cols_preview = pd.read_csv(fpath, nrows=0).columns.tolist()
            # 兼容 BRK.B / BRK_B 等符号差异
            matching_col = None
            if sym in cols_preview:
                matching_col = sym
            elif sym.replace(".", "_") in cols_preview:
                matching_col = sym.replace(".", "_")
            elif sym.replace("-", "_") in cols_preview:
                matching_col = sym.replace("-", "_")
                
            if matching_col:
                df = pd.read_csv(fpath, usecols=['date', matching_col])
                df.dropna(subset=[matching_col], inplace=True)
                if not df.empty:
                    df['date'] = pd.to_datetime(df['date']).dt.tz_localize(None).astype('datetime64[ns]')
                    df.rename(columns={'date': 'Date', matching_col: 'Close'}, inplace=True)
                    df.sort_values('Date', inplace=True)
                    df.reset_index(drop=True, inplace=True)
                    
                    last_dt = df['Date'].iloc[-1].strftime('%Y-%m-%d')
                    meta = {
                        "is_local_fallback": True,
                        "source_file": fname,
                        "source_label": label,
                        "last_date": last_dt,
                        "is_close_only": True,
                        "record_count": len(df),
                        "price_type": f"本地离线历史收盘价序列 (截至 {last_dt}，非实时)"
                    }
                    return df, meta
        except Exception as e:
            # 本地读取异常不崩溃，继续尝试下一文件
            pass
            
    return pd.DataFrame(), {}

# =====================================================================
# 4. 底层原始数据获取 (在失败时抛出异常，杜绝污染 Streamlit 缓存)
# =====================================================================
def _raw_fetch_stock_profile(symbol: str) -> Dict[str, Any]:
    """从 yfinance 提取标的基础画像 info，失败时抛出 StockDataFetchError"""
    try:
        import yfinance as yf
    except ImportError:
        raise StockDataFetchError("系统未安装 yfinance 库", is_transient=False)
        
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info
    except Exception as e:
        err_msg = str(e)
        status_code = 401 if "401" in err_msg else (429 if "429" in err_msg else None)
        raise StockDataFetchError(f"请求公司资料异常: {err_msg}", status_code=status_code)

    if not info or not isinstance(info, dict):
        raise StockDataFetchError("上游未返回公司基础资料 (返回空响应)")
    
    # 检查基本有效性：只要存在任意常见身份字段或价格字段即可，避免过于严苛
    has_identity = any(k in info for k in ["shortName", "longName", "symbol", "quoteType", "currency", "regularMarketPrice", "currentPrice"])
    if not has_identity:
        raise StockDataFetchError("上游返回了响应但缺少身份字段", is_transient=True)
        
    return info

def _raw_fetch_stock_history(symbol: str, period: str = "5y") -> pd.DataFrame:
    """从 yfinance 提取股票历史行情 OHLCV，失败时抛出 StockDataFetchError"""
    try:
        import yfinance as yf
    except ImportError:
        raise StockDataFetchError("系统未安装 yfinance 库", is_transient=False)
        
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(period=period, interval="1d")
    except Exception as e:
        err_msg = str(e)
        status_code = 401 if "401" in err_msg else (429 if "429" in err_msg else None)
        raise StockDataFetchError(f"请求历史行情异常: {err_msg}", status_code=status_code)
        
    if df is None or df.empty:
        raise StockDataFetchError("上游未返回有效历史行情数据 (空行情序列)")
        
    return df

def _raw_fetch_stock_statements(symbol: str) -> Dict[str, Any]:
    """从 yfinance 独立提取三大财务报表 (季度与年度)，失败时抛出 StockDataFetchError"""
    try:
        import yfinance as yf
    except ImportError:
        raise StockDataFetchError("系统未安装 yfinance 库", is_transient=False)
        
    try:
        ticker = yf.Ticker(symbol)
        # 分别独立安全读取，某一属性读取失败不应导致全局崩溃
        q_inc = getattr(ticker, 'quarterly_income_stmt', None)
        if q_inc is None or getattr(q_inc, 'empty', True):
            q_inc = getattr(ticker, 'quarterly_financials', None)
            
        a_inc = getattr(ticker, 'income_stmt', None)
        if a_inc is None or getattr(a_inc, 'empty', True):
            a_inc = getattr(ticker, 'financials', None)
            
        q_bs = getattr(ticker, 'quarterly_balance_sheet', None)
        a_bs = getattr(ticker, 'balance_sheet', None)
        
        q_cf = getattr(ticker, 'quarterly_cashflow', None)
        if q_cf is None or getattr(q_cf, 'empty', True):
            q_cf = getattr(ticker, 'quarterly_cash_flow', None)
            
        a_cf = getattr(ticker, 'cashflow', None)
        if a_cf is None or getattr(a_cf, 'empty', True):
            a_cf = getattr(ticker, 'cash_flow', None)
    except Exception as e:
        err_msg = str(e)
        status_code = 401 if "401" in err_msg else (429 if "429" in err_msg else None)
        raise StockDataFetchError(f"请求财务报表异常: {err_msg}", status_code=status_code)
        
    # 只要季度或年度中至少有一张表存在非空数据，即视为成功抓取
    valid_tables = [t for t in [q_inc, a_inc, q_bs, a_bs, q_cf, a_cf] if t is not None and not getattr(t, 'empty', True)]
    if not valid_tables:
        raise StockDataFetchError("上游未返回任何财务三张表数据")
        
    return {
        "q_inc": q_inc if q_inc is not None and not getattr(q_inc, 'empty', True) else pd.DataFrame(),
        "a_inc": a_inc if a_inc is not None and not getattr(a_inc, 'empty', True) else pd.DataFrame(),
        "q_bs": q_bs if q_bs is not None and not getattr(q_bs, 'empty', True) else pd.DataFrame(),
        "a_bs": a_bs if a_bs is not None and not getattr(a_bs, 'empty', True) else pd.DataFrame(),
        "q_cf": q_cf if q_cf is not None and not getattr(q_cf, 'empty', True) else pd.DataFrame(),
        "a_cf": a_cf if a_cf is not None and not getattr(a_cf, 'empty', True) else pd.DataFrame(),
    }

def _raw_fetch_stock_news(symbol: str) -> list:
    """从 yfinance 提取标的新闻，失败时抛出 StockDataFetchError"""
    try:
        import yfinance as yf
    except ImportError:
        raise StockDataFetchError("系统未安装 yfinance 库", is_transient=False)
        
    try:
        ticker = yf.Ticker(symbol)
        news = getattr(ticker, 'news', None)
    except Exception as e:
        err_msg = str(e)
        status_code = 401 if "401" in err_msg else (429 if "429" in err_msg else None)
        raise StockDataFetchError(f"请求新闻动态异常: {err_msg}", status_code=status_code)
        
    if not news or not isinstance(news, list):
        raise StockDataFetchError("上游未返回新闻数据 (空列表)")
        
    return news

# =====================================================================
# 5. Streamlit 缓存包装层 (仅在成功时持久化，失败抛异常不写入缓存)
# =====================================================================
@st.cache_data(ttl=21600, show_spinner=False)  # 成功缓存 6 小时
def _cached_fetch_profile(symbol: str) -> Dict[str, Any]:
    return _raw_fetch_stock_profile(symbol)

@st.cache_data(ttl=14400, show_spinner=False)  # 成功缓存 4 小时
def _cached_fetch_history(symbol: str, period: str) -> pd.DataFrame:
    return _raw_fetch_stock_history(symbol, period=period)

@st.cache_data(ttl=43200, show_spinner=False)  # 成功缓存 12 小时
def _cached_fetch_statements(symbol: str) -> Dict[str, Any]:
    return _raw_fetch_stock_statements(symbol)

@st.cache_data(ttl=3600, show_spinner=False)   # 成功缓存 1 小时
def _cached_fetch_news(symbol: str) -> list:
    return _raw_fetch_stock_news(symbol)

# =====================================================================
# 6. 面向业务端的解耦安全消费接口 (带冷却状态拦截与诊断信息)
# =====================================================================
def get_stock_profile(symbol: str) -> Dict[str, Any]:
    """
    获取公司基础画像 (Profile/Info)
    返回: {"status": "SUCCESS" | "IN_COOLDOWN" | "FAILED", "data": dict, "message": str, "technical_details": str}
    """
    sym = symbol.strip().upper()
    in_cd, remain, reason = cooldown_manager.is_in_cooldown(sym, "profile")
    if in_cd:
        return {
            "status": "IN_COOLDOWN",
            "data": {},
            "message": f"公司资料接口处于保护冷却中（剩余约 {int(remain)} 秒）",
            "technical_details": reason,
            "remaining_seconds": remain
        }
        
    try:
        data = _cached_fetch_profile(sym)
        cooldown_manager.record_success(sym, "profile")
        return {
            "status": "SUCCESS",
            "data": data,
            "message": "获取成功",
            "technical_details": "Cache Hit or Live Fetch Success"
        }
    except StockDataFetchError as e:
        cd = cooldown_manager.record_failure(sym, "profile", error_type=str(e), status_code=e.status_code)
        return {
            "status": "FAILED",
            "data": {},
            "message": "公司资料暂不可用（上游数据源无响应或格式受限）",
            "technical_details": f"StockDataFetchError: {e} (已启用 {int(cd)}s 冷却保护)",
            "status_code": e.status_code
        }
    except Exception as e:
        cd = cooldown_manager.record_failure(sym, "profile", error_type=str(e))
        return {
            "status": "FAILED",
            "data": {},
            "message": "公司资料解析异常",
            "technical_details": f"Unhandled Exception: {e} (已启用 {int(cd)}s 冷却保护)"
        }

def get_stock_price_data(symbol: str, period: str = "5y") -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """
    获取行情数据 (支持上游在线 + 本地历史收盘价离线兜底)
    返回: (DataFrame, MetaDict)
    """
    sym = symbol.strip().upper()
    in_cd, remain, reason = cooldown_manager.is_in_cooldown(sym, "history")
    
    # 若在线行情不处于冷却，优先尝试在线获取
    if not in_cd:
        try:
            df = _cached_fetch_history(sym, period)
            cooldown_manager.record_success(sym, "history")
            meta = {
                "is_local_fallback": False,
                "is_close_only": False,
                "source_label": "Yahoo Finance 在线行情 (实时/延迟)",
                "status": "SUCCESS",
                "message": "在线行情获取成功"
            }
            return df, meta
        except StockDataFetchError as e:
            cd = cooldown_manager.record_failure(sym, "history", error_type=str(e), status_code=e.status_code)
        except Exception as e:
            cd = cooldown_manager.record_failure(sym, "history", error_type=str(e))

    # 在线获取失败或处于冷却，自动安全降级至本地离线主数据集
    df_local, local_meta = get_local_stock_price_fallback(sym)
    if not df_local.empty:
        local_meta["status"] = "SUCCESS_LOCAL_FALLBACK"
        local_meta["message"] = f"已安全切换至本地离线历史数据 ({local_meta.get('source_label')})"
        return df_local, local_meta
        
    # 本地也无该标的行情
    fail_meta = {
        "is_local_fallback": False,
        "is_close_only": False,
        "status": "FAILED",
        "message": f"在线行情受限且本地离线库无标的 `{sym}` 的历史序列"
    }
    return pd.DataFrame(), fail_meta

def get_stock_statements(symbol: str) -> Tuple[Dict[str, pd.DataFrame], Dict[str, Any]]:
    """
    获取三大财务报表明细
    返回: (statements_dict, meta_dict)
    """
    sym = symbol.strip().upper()
    in_cd, remain, reason = cooldown_manager.is_in_cooldown(sym, "statements")
    if in_cd:
        return {}, {
            "status": "IN_COOLDOWN",
            "message": f"财报数据接口处于保护冷却中（剩余约 {int(remain)} 秒）",
            "technical_details": reason,
            "remaining_seconds": remain
        }
        
    try:
        data = _cached_fetch_statements(sym)
        cooldown_manager.record_success(sym, "statements")
        return data, {
            "status": "SUCCESS",
            "message": "财务报表获取成功",
            "technical_details": "Statements Fetched Successfully"
        }
    except StockDataFetchError as e:
        cd = cooldown_manager.record_failure(sym, "statements", error_type=str(e), status_code=e.status_code)
        return {}, {
            "status": "FAILED",
            "message": "财务报表暂不可用（上游数据源无响应或未披露）",
            "technical_details": f"{e} (已启用 {int(cd)}s 冷却保护)"
        }
    except Exception as e:
        cd = cooldown_manager.record_failure(sym, "statements", error_type=str(e))
        return {}, {
            "status": "FAILED",
            "message": "财务报表解析异常",
            "technical_details": f"Unhandled Exception: {e}"
        }

def get_stock_news(symbol: str) -> Tuple[list, Dict[str, Any]]:
    """
    获取个股新闻与动态
    返回: (news_list, meta_dict)
    """
    sym = symbol.strip().upper()
    in_cd, remain, reason = cooldown_manager.is_in_cooldown(sym, "news")
    if in_cd:
        return [], {
            "status": "IN_COOLDOWN",
            "message": f"新闻数据接口处于保护冷却中（剩余约 {int(remain)} 秒）",
            "technical_details": reason
        }
        
    try:
        news = _cached_fetch_news(sym)
        cooldown_manager.record_success(sym, "news")
        return news, {"status": "SUCCESS", "message": "新闻获取成功"}
    except Exception as e:
        cd = cooldown_manager.record_failure(sym, "news", error_type=str(e))
        return [], {
            "status": "FAILED",
            "message": "新闻动态暂不可用",
            "technical_details": str(e)
        }
