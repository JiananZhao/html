"""
FactSet S&P 500 NTM EPS and Forward P/E Automated Weekly Updater
Fetches official FactSet Earnings Insight weekly PDF reports, extracts valuation metrics,
and updates sp500_ntm_eps.csv automatically.
"""

import os
import io
import re
import sys
import datetime
import requests
import pandas as pd
from pypdf import PdfReader

# Ensure standard UTF-8 stream handling
if sys.stdout.encoding != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(BASE_DIR, "sp500_ntm_eps.csv")
FACTSET_PDF_TEMPLATE = (
    "https://advantage.factset.com/hubfs/Website/Resources%20Section/Research%20Desk/"
    "Earnings%20Insight/EarningsInsight_{mmddyy}.pdf"
)

def get_recent_fridays(count: int = 4):
    """返回最近 count 个周五的日期列表 (降序)"""
    today = datetime.date.today()
    fridays = []
    # 查找最近的周五 (若今天是周五且在发布窗口之后，则包含今天)
    offset = (today.weekday() - 4) % 7
    latest_friday = today - datetime.timedelta(days=offset)
    
    for i in range(count):
        f = latest_friday - datetime.timedelta(weeks=i)
        fridays.append(f)
    return fridays

def fetch_factset_metrics_for_date(target_date: datetime.date):
    """
    根据目标周五日期下载对应 FactSet Earnings Insight PDF 并提取估值指标。
    返回: dict(date, forward_pe, spx_price, ntm_eps, source) 或 None
    """
    mmddyy = target_date.strftime("%m%d%y")
    iso_date = target_date.strftime("%Y-%m-%d")
    url = FACTSET_PDF_TEMPLATE.format(mmddyy=mmddyy)
    
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
    }
    
    try:
        print(f"[FETCH] Checking FactSet report: {url} ...")
        resp = requests.get(url, headers=headers, timeout=20)
        if resp.status_code != 200:
            print(f"[INFO] Report not available (HTTP {resp.status_code}).")
            return None
            
        reader = PdfReader(io.BytesIO(resp.content))
        print(f"[OK] Downloaded PDF ({len(reader.pages)} pages). Parsing valuation section...")
        
        forward_pe = None
        spx_price = None
        
        # 扫描前 20 页以提取前瞻市盈率与点位
        for p_idx, page in enumerate(reader.pages[:20]):
            text = page.extract_text() or ""
            
            # 1. 匹配 Forward 12-Month P/E
            if not forward_pe:
                m_pe = re.search(
                    r"forward\s*12\s*[-– ]\s*month\s*P/E\s*ratio\s*[\w\s\(\)]*?is\s*(\d+\.\d+)",
                    text,
                    re.IGNORECASE
                )
                if m_pe:
                    forward_pe = float(m_pe.group(1))
                    print(f"  [Page {p_idx+1}] Extracted Forward P/E: {forward_pe}x")
            
            # 2. 匹配标普500基准收盘价
            if not spx_price:
                m_px = re.search(r"closing\s*price\s*of\s*([\d,]+\.\d+)", text, re.IGNORECASE)
                if m_px:
                    spx_price = float(m_px.group(1).replace(",", ""))
                    print(f"  [Page {p_idx+1}] Extracted SPX Benchmark Price: {spx_price}")
                    
            if forward_pe and spx_price:
                break
                
        if forward_pe:
            # 若 PDF 未能正则匹配到点位，优雅从 Yahoo Finance 补充当天真实收盘点位
            if not spx_price:
                try:
                    import yfinance as yf
                    spx = yf.Ticker("^GSPC")
                    hist = spx.history(start=iso_date, end=(target_date + datetime.timedelta(days=4)).strftime("%Y-%m-%d"))
                    if not hist.empty:
                        spx_price = round(float(hist["Close"].iloc[0]), 2)
                        print(f"  Fallback SPX price from yfinance: {spx_price}")
                except Exception as e:
                    print(f"  Fallback yfinance error: {e}")
                    
            if spx_price:
                ntm_eps = round(spx_price / forward_pe, 2)
                return {
                    "date": iso_date,
                    "forward_pe": forward_pe,
                    "spx_price": spx_price,
                    "ntm_eps": ntm_eps,
                    "source": "FactSet Earnings Insight"
                }
                
        print(f"[WARN] Incomplete valuation metrics (pe: {forward_pe}, price: {spx_price})")
        return None
        
    except Exception as e:
        print(f"[ERROR] FactSet fetch/parse exception: {e}")
        return None

def update_sp500_ntm_eps():
    """主更新调度逻辑"""
    print("=" * 70)
    print("FACTSET S&P 500 NTM EPS & FORWARD P/E AUTOMATED UPDATER")
    print("=" * 70)
    
    # 1. 加载现有 CSV
    if os.path.exists(CSV_PATH):
        df_existing = pd.read_csv(CSV_PATH)
    else:
        df_existing = pd.DataFrame(columns=["date", "forward_pe", "spx_price", "ntm_eps", "source"])
        
    existing_dates = set(df_existing["date"].astype(str).tolist())
    latest_dt = df_existing['date'].iloc[-1] if not df_existing.empty else 'None'
    print(f"[INFO] Current records in CSV: {len(df_existing)}, latest date: {latest_dt}")
    
    # 2. 检查最近 4 周的周五数据
    candidate_fridays = get_recent_fridays(count=4)
    new_rows = []
    
    for friday in candidate_fridays:
        iso_str = friday.strftime("%Y-%m-%d")
        if iso_str in existing_dates:
            print(f"[SKIP] Friday {iso_str} already exists in CSV.")
            continue
            
        print(f"[SEARCH] Fetching Friday {iso_str} from FactSet...")
        metrics = fetch_factset_metrics_for_date(friday)
        if metrics:
            print(f"[SUCCESS] Appending: Date={metrics['date']}, P/E={metrics['forward_pe']}x, Price={metrics['spx_price']}, NTM EPS=${metrics['ntm_eps']}")
            new_rows.append(metrics)
        else:
            print(f"[INFO] Friday {iso_str} no valid metrics found.")
            
    # 3. 追加并落盘
    if new_rows:
        df_new = pd.DataFrame(new_rows)
        df_combined = pd.concat([df_existing, df_new], ignore_index=True)
        df_combined.drop_duplicates(subset=["date"], keep="last", inplace=True)
        df_combined.sort_values("date", inplace=True)
        df_combined.reset_index(drop=True, inplace=True)
        df_combined.to_csv(CSV_PATH, index=False)
        print(f"[DONE] Appended {len(new_rows)} records to {CSV_PATH}")
    else:
        print("[DONE] CSV is already up-to-date. No new rows added.")
        
    print("=" * 70)

if __name__ == "__main__":
    update_sp500_ntm_eps()
