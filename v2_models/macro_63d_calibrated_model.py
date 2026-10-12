import pandas as pd
import numpy as np
import yfinance as yf
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, roc_auc_score
import warnings
warnings.filterwarnings('ignore')

def run_calibrated_macro_model():
    print("Fetching data from Yahoo Finance for SPY and SHV...")
    data = yf.download(["SPY", "SHV"], start="2007-01-01", progress=False)["Close"]
    
    spy = data["SPY"]
    shv = data["SHV"]
    
    # Target: 63-day forward excess return > 0
    fwd_ret_spy = spy.shift(-63) / spy - 1
    fwd_ret_shv = shv.shift(-63) / shv - 1
    excess_fwd = fwd_ret_spy - fwd_ret_shv
    target = (excess_fwd > 0).astype(int)
    
    # Features
    df = pd.DataFrame(index=data.index)
    df["target"] = target
    
    # 1. Trend distance (Price / 200MA - 1)
    ma200 = spy.rolling(window=200).mean()
    df["trend_dist"] = spy / ma200 - 1
    
    # 2. Volatility (63-day std of daily returns)
    daily_ret = spy.pct_change()
    df["vol_63d"] = daily_ret.rolling(window=63).std()
    
    # 3. Momentum (63-day return)
    df["mom_63d"] = spy / spy.shift(63) - 1
    
    df = df.dropna()
    # Drop the last 63 days where target is invalid (future data)
    df = df.iloc[:-63]
    
    # Walk-forward cross validation
    # Start with 5 years of training data (approx 1250 trading days)
    min_train_size = 1250
    step_size = 63 # Re-train every quarter
    
    preds = []
    actuals = []
    
    print("\nRunning walk-forward validation (Train: Expanding, Test: 63 days)...")
    for i in range(min_train_size, len(df) - step_size, step_size):
        train = df.iloc[:i]
        test = df.iloc[i:i+step_size]
        
        X_train = train[["trend_dist", "vol_63d", "mom_63d"]]
        y_train = train["target"]
        X_test = test[["trend_dist", "vol_63d", "mom_63d"]]
        y_test = test["target"]
        
        # Logistic Regression with L2 penalty
        clf = LogisticRegression(penalty='l2', C=1.0)
        clf.fit(X_train, y_train)
        
        prob = clf.predict_proba(X_test)[:, 1]
        preds.extend(prob)
        actuals.extend(y_test.values)
        
    preds = np.array(preds)
    actuals = np.array(actuals)
    
    # Evaluation Metrics
    brier = brier_score_loss(actuals, preds)
    auc = roc_auc_score(actuals, preds)
    base_rate = actuals.mean()
    
    print("="*80)
    print("MACRO ASSET PROBABILITY CALIBRATION (SPY vs CASH)")
    print("="*80)
    print(f"Total Out-of-Sample Predictions: {len(preds)}")
    print(f"Unconditional Base Rate (Actual Win Rate): {base_rate:.2%}")
    print(f"ROC AUC Score: {auc:.3f} (1.0 is perfect, 0.5 is random)")
    print(f"Brier Score: {brier:.4f} (Lower is better, 0.0 is perfect)")
    print("\nCalibration Table (Predicted Probability Bins vs Actual Win Rate):")
    
    # Calibration Curve (Binning)
    bins = [0.0, 0.4, 0.6, 0.7, 0.8, 1.0]
    bin_labels = ["<40%", "40%-60%", "60%-70%", "70%-80%", ">80%"]
    
    calib_results = []
    for i in range(len(bins)-1):
        mask = (preds >= bins[i]) & (preds < bins[i+1])
        count = mask.sum()
        if count > 0:
            actual_rate = actuals[mask].mean()
            mean_pred = preds[mask].mean()
            calib_results.append({
                "Pred Bin": bin_labels[i],
                "Count": count,
                "Avg Pred Prob": f"{mean_pred:.1%}",
                "Actual Win Rate": f"{actual_rate:.1%}",
                "Error (Actual - Pred)": f"{(actual_rate - mean_pred):+.1%}"
            })
            
    df_calib = pd.DataFrame(calib_results)
    print(df_calib.to_string(index=False))
    print("="*80)
    print("Conclusion: A well-calibrated model will have 'Actual Win Rate' closely matching 'Avg Pred Prob'.")
    print("If it doesn't match, the model's confidence is severely flawed, proving that raw feature scores")
    print("cannot be safely interpreted as probabilities without explicit probability modeling.")

if __name__ == "__main__":
    run_calibrated_macro_model()
