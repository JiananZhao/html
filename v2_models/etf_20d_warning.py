import pandas as pd
import numpy as np
import yfinance as yf

def run_etf_warning_prototype():
    print("Fetching ETF data from Yahoo Finance...")
    tickers = ["QQQ", "SMH", "XLE"]
    data = yf.download(tickers, start="2007-01-01", progress=False)["Close"]
    
    # 20-day forward returns
    fwd_20d = data.shift(-20) / data - 1
    
    # Rolling 20-day mean and std
    ma20 = data.rolling(window=20).mean()
    vol20 = data.rolling(window=20).std()
    
    # Z-score of price to 20MA
    z_score = (data - ma20) / vol20
    
    print("\n" + "="*80)
    print("ETF 20-DAY OVERBOUGHT/OVERSOLD WARNING BASELINE")
    print("State definition based on Z-Score of Price vs 20MA (Vol standardized)")
    print("Target: Probability of > 5% drawdown in next 20 days: Pr(FwdRet < -5%)")
    print("="*80)
    
    results = []
    
    for ticker in tickers:
        valid_idx = fwd_20d[ticker].dropna().index
        
        # Merge series for filtering
        df_asset = pd.DataFrame({
            "Price": data[ticker],
            "Z": z_score[ticker],
            "Fwd20": fwd_20d[ticker]
        }).loc[valid_idx].dropna()
        
        states = [
            ("All (Unconditional)", df_asset),
            ("Overbought (Z > 2.0)", df_asset[df_asset["Z"] > 2.0]),
            ("Oversold (Z < -2.0)", df_asset[df_asset["Z"] < -2.0]),
            ("Normal (-2.0 <= Z <= 2.0)", df_asset[(df_asset["Z"] >= -2.0) & (df_asset["Z"] <= 2.0)])
        ]
        
        for state_name, df_sub in states:
            count = len(df_sub)
            if count == 0:
                continue
            
            p_drawdown = (df_sub["Fwd20"] < -0.05).mean()
            p_rally = (df_sub["Fwd20"] > 0.05).mean()
            mean_fwd = df_sub["Fwd20"].mean()
            
            results.append({
                "Asset": ticker,
                "State": state_name,
                "Samples": count,
                "Pr(< -5%) [Risk]": f"{p_drawdown:.2%}",
                "Pr(> +5%) [Rally]": f"{p_rally:.2%}",
                "Mean Fwd Ret": f"{mean_fwd:.2%}",
            })
            
    df_results = pd.DataFrame(results)
    print(df_results.to_string(index=False))
    print("="*80)

if __name__ == "__main__":
    run_etf_warning_prototype()
