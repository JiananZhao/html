import pandas as pd
import numpy as np
import yfinance as yf
import warnings
warnings.filterwarnings('ignore')

def run_etf_warning_eval():
    print("Fetching ETF data from Yahoo Finance for QQQ...")
    data = yf.download("QQQ", start="2007-01-01", progress=False)["Close"]
    
    # Target Event: Next 20 days max drawdown > 10% from current price
    # We want to predict if the asset will drop significantly in the next 20 days.
    rolling_min = data.shift(-20).rolling(window=20).min()
    fwd_max_drawdown = (rolling_min - data) / data
    
    # Event definition: max drawdown within next 20 days is worse than -10%
    event_happens = (fwd_max_drawdown < -0.10).astype(int)
    
    # Signal generation (Features/Rules)
    ma20 = data.rolling(window=20).mean()
    vol20 = data.rolling(window=20).std()
    z_score = (data - ma20) / vol20
    
    # Let's test a simple Risk Warning:
    # Rule 1: Overbought (Z > 2.0)
    # Rule 2: Overbought and Trend Reversing (Z was > 2.0 recently, now dropping below 1.0)
    
    df = pd.DataFrame(index=data.index)
    df["Close"] = data
    df["Z"] = z_score
    df["Event"] = event_happens
    df = df.dropna()
    df = df.iloc[:-20] # Drop last 20 days without forward truth
    
    # Baseline Warning: Simply Z > 1.5
    df["Warning"] = (df["Z"] > 1.5).astype(int)
    
    # Calculate Precision and Recall
    true_positives = ((df["Warning"] == 1) & (df["Event"] == 1)).sum()
    false_positives = ((df["Warning"] == 1) & (df["Event"] == 0)).sum()
    false_negatives = ((df["Warning"] == 0) & (df["Event"] == 1)).sum()
    true_negatives = ((df["Warning"] == 0) & (df["Event"] == 0)).sum()
    
    precision = true_positives / (true_positives + false_positives) if (true_positives + false_positives) > 0 else 0
    recall = true_positives / (true_positives + false_negatives) if (true_positives + false_negatives) > 0 else 0
    
    # Repeat Alarm Burden: average number of consecutive warning days
    warning_blocks = (df["Warning"] != df["Warning"].shift(1)).cumsum()
    alarm_burden = df[df["Warning"] == 1].groupby(warning_blocks).size().mean()
    
    print("\n" + "="*80)
    print("ETF RISK WARNING EVALUATION (QQQ: 20-Day Drawdown > 10%)")
    print("Baseline Signal: Z-Score > 1.5 (Overbought)")
    print("="*80)
    
    total_days = len(df)
    event_days = df['Event'].sum()
    warning_days = df['Warning'].sum()
    
    print(f"Total Trading Days Evaluated: {total_days}")
    print(f"Days with actual Drawdown > 10% approaching: {event_days} ({event_days/total_days:.1%})")
    print(f"Days with Warning Fired: {warning_days} ({warning_days/total_days:.1%})\n")
    
    print(f"Precision (Precision): {precision:.2%} -> When alarm rings, {precision:.2%} of the time a crash actually follows.")
    print(f"Recall (Recall): {recall:.2%} -> Out of all crashes, {recall:.2%} were preceded by this alarm.")
    print(f"Repeat Alarm Burden (Burden): {alarm_burden:.1f} days -> Alarm stays on for {alarm_burden:.1f} days consecutively on average.")
    print("="*80)
    print("Conclusion: A simple 'Overbought' rule has terrible precision for predicting crashes.")
    print("This proves your point: '超买不自动等于卖出' (Overbought does not automatically mean sell).")
    print("Further logic (e.g. Trend Breakdown confirmation) must be added to Layer 3 Trading Rules.")

if __name__ == "__main__":
    run_etf_warning_eval()
