import pandas as pd
import numpy as np
import yfinance as yf
from datetime import datetime

def run_macro_prototype():
    print("Fetching data from Yahoo Finance...")
    tickers = ["SPY", "TLT", "GLD", "LQD", "SHV"]
    # We use yf.download
    data = yf.download(tickers, start="2007-01-01", progress=False)["Close"]
    
    # 63-day forward returns
    fwd_63d = data.shift(-63) / data - 1
    
    # Excess returns vs SHV (Cash proxy)
    excess_ret = pd.DataFrame(index=data.index)
    for ticker in ["SPY", "TLT", "GLD", "LQD"]:
        excess_ret[ticker] = fwd_63d[ticker] - fwd_63d["SHV"]
        
    # Moving average for trend baseline
    ma200 = data.rolling(window=200).mean()
    
    print("\n" + "="*80)
    print("MACRO ASSET 63-DAY PROTOTYPE (VS CASH)")
    print("p: Pr(X > 0), G: E[X | X > 0], L: -E[X | X <= 0], b: G/L, E: pG - (1-p)L")
    print("="*80)
    
    results = []
    
    for ticker in ["SPY", "TLT", "GLD", "LQD"]:
        # Drop rows where we don't have forward returns (last 63 days)
        valid_idx = excess_ret[ticker].dropna().index
        
        # 1. Unconditional Baseline
        X = excess_ret.loc[valid_idx, ticker]
        
        p = (X > 0).mean()
        G = X[X > 0].mean() if p > 0 else 0
        L = -X[X <= 0].mean() if p < 1 else 0
        b = G / L if L != 0 else np.nan
        E = p * G - (1 - p) * L
        
        results.append({
            "Asset": ticker,
            "State": "All (Unconditional)",
            "Samples": len(X),
            "WinRate(p)": f"{p:.2%}",
            "WinAvg(G)": f"{G:.2%}",
            "LossAvg(L)": f"{L:.2%}",
            "Odds(b)": f"{b:.2f}",
            "ExpExcess(E)": f"{E:.2%}"
        })
        
        # 2. Trend Baseline (Price > MA200)
        trend_up_idx = valid_idx.intersection(data[data[ticker] > ma200[ticker]].index)
        X_up = excess_ret.loc[trend_up_idx, ticker]
        
        if len(X_up) > 0:
            p_up = (X_up > 0).mean()
            G_up = X_up[X_up > 0].mean() if p_up > 0 else 0
            L_up = -X_up[X_up <= 0].mean() if p_up < 1 else 0
            b_up = G_up / L_up if L_up != 0 else np.nan
            E_up = p_up * G_up - (1 - p_up) * L_up
            
            results.append({
                "Asset": ticker,
                "State": "Trend UP (>200MA)",
                "Samples": len(X_up),
                "WinRate(p)": f"{p_up:.2%}",
                "WinAvg(G)": f"{G_up:.2%}",
                "LossAvg(L)": f"{L_up:.2%}",
                "Odds(b)": f"{b_up:.2f}",
                "ExpExcess(E)": f"{E_up:.2%}"
            })
            
        # 3. Trend DOWN (Price <= MA200)
        trend_dn_idx = valid_idx.intersection(data[data[ticker] <= ma200[ticker]].index)
        X_dn = excess_ret.loc[trend_dn_idx, ticker]
        
        if len(X_dn) > 0:
            p_dn = (X_dn > 0).mean()
            G_dn = X_dn[X_dn > 0].mean() if p_dn > 0 else 0
            L_dn = -X_dn[X_dn <= 0].mean() if p_dn < 1 else 0
            b_dn = G_dn / L_dn if L_dn != 0 else np.nan
            E_dn = p_dn * G_dn - (1 - p_dn) * L_dn
            
            results.append({
                "Asset": ticker,
                "State": "Trend DOWN (<=200MA)",
                "Samples": len(X_dn),
                "WinRate(p)": f"{p_dn:.2%}",
                "WinAvg(G)": f"{G_dn:.2%}",
                "LossAvg(L)": f"{L_dn:.2%}",
                "Odds(b)": f"{b_dn:.2f}",
                "ExpExcess(E)": f"{E_dn:.2%}"
            })
            
    df_results = pd.DataFrame(results)
    print(df_results.to_string(index=False))
    print("="*80)
    print("NOTE: WinRate(p) is Pr(Asset runs better than Cash).")
    
if __name__ == "__main__":
    run_macro_prototype()
