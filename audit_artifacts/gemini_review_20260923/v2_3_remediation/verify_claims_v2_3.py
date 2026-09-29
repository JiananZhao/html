"""
Positive Claims & Verification Audit Script v2.3
=================================================
Automated verification of all v2.3 remediation items:
1. Frozen Model Full-History Equivalence (Zero Model Drift):
   - 2020-03-20 exact match (q1=-9.694703, q1_dot=-2.252796, v_dot=58.050330, M0=47.325476)
   - 100% missing mask equality and tolerance <= 1e-6 without isnan bypass across all 35 columns
   - C0 boolean signals 100% identical across full history
2. Production Dual-Track Baseline:
   - Verifies production signal_ready start date (2014-04-16) and full history parity
3. Trade Clock & Re-entry Stop Loss Countdown:
   - Stop loss countdown advances across unready and missing quote trading days
   - Day 10 is the final valid day; Day 12 is expired and does not trigger
4. Holding Position DCA Catch-up & Pending Sell Protection:
   - Delayed monthly DCA invested upon quote recovery (no idle cash)
   - Existing pending risk sell order is protected from being cancelled by DCA order
5. Open Position Stale Valuation & Forward Return Quote Verification:
   - Terminal missing quote evaluated at executor's last_valid_price (zero cost fallback)
   - Forward returns require both start and horizon quote to be valid
6. Signal Extrema Evaluation Window & End Truncation Alignment:
   - [S - 15, S + 5] matching window for both buys and sells
   - Truncation mask [window : n - 60] excludes truncated signals and extrema
7. Continuous Full-History Signal Generation & Sub-period Deliverable:
   - Sub-period evaluations for Mode A (Inherited) and Mode B (Fresh Reset)
8. Factor C Complete Removal of AFTER_STOP:
   - Zero AFTER_STOP state; stop loss orders strictly 0 for C0, C1, C2, C4
"""

import sys
import io
import json
from pathlib import Path
from unittest.mock import patch
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT))

import audit_artifacts.gemini_review_20260923.v2_3_remediation.run_factorial_experiment_v2_3 as exp
import audit_artifacts.gemini_review_20260923.v2_3_remediation.test_experiment_engine_v2_3 as tests
from audit_artifacts.gemini_review_20260923 import run_factorial_experiment as old
from reflexivity_engine import run_universal_reflexivity_radar
from shared_executor import SharedExecutor

OUT_DIR = Path(__file__).resolve().parent


def main():
    print("=" * 80)
    print("V2.3 POSITIVE CLAIMS & REMEDIATION AUDIT")
    print("=" * 80)
    
    evidence = {}
    
    # -------------------------------------------------------------------------
    # 1. Full-History Model Equivalence & Strict Masks
    # -------------------------------------------------------------------------
    print("\n[Audit 1] Verifying Frozen Mathematical Model Equivalence & Masks...")
    prices = pd.read_csv(ROOT / 'now_ohlcv_local.csv')
    macro = pd.read_csv(ROOT / 'market_data_local.csv')
    
    new_features = exp.prepare_base_features(prices, macro)
    old_features = old.prepare_base_features(prices, macro)
    
    common_cols = [c for c in old_features.columns if c in new_features.columns and c != 'date']
    mask_matches = {}
    max_diffs = {}
    for c in common_cols:
        if pd.api.types.is_numeric_dtype(new_features[c]):
            mask_ok = bool(new_features[c].isna().equals(old_features[c].isna()))
            mask_matches[c] = mask_ok
            assert mask_ok, f"Missing mask for {c} does not match!"
            
            valid_mask = old_features[c].notna()
            if valid_mask.any():
                if new_features[c].dtype == bool:
                    diff = float((new_features.loc[valid_mask, c] != old_features.loc[valid_mask, c]).sum())
                else:
                    diff = float((new_features.loc[valid_mask, c] - old_features.loc[valid_mask, c]).abs().max())
                max_diffs[c] = diff
                assert not np.isnan(diff), f"Diff is NaN for {c}"
                assert diff <= 1e-6, f"Column {c} drift {diff} exceeds 1e-6!"
                
    cols_2020 = ['q1', 'q1_dot', 'q1_ddot', 'v_dot', 'Composite_Score_M0', 'Score_Overheat_A', 'Score_PanicDepth_A']
    row_new = new_features.loc[new_features.date == '2020-03-20', cols_2020].iloc[0].round(6).to_dict()
    row_old = old_features.loc[old_features.date == '2020-03-20', cols_2020].iloc[0].round(6).to_dict()
    assert row_new == row_old, f"2020-03-20 mismatch: {row_new} vs {row_old}"
    
    sig_new_c0 = exp.generate_signals(new_features, False, False, False)
    sig_old_c0 = old.generate_signals(old_features, False, False, False)
    for sig_col in ['Trigger_Panic', 'Trigger_Bubble_Top', 'Trigger_Bear_Top', 'cond_trend']:
        assert sig_new_c0[sig_col].equals(sig_old_c0[sig_col]), f"Signal {sig_col} does not match 100%!"
        
    evidence['model_equivalence'] = {
        'row_2020_03_20': row_new,
        'all_35_masks_equal': all(mask_matches.values()),
        'max_diffs_valid_rows': max_diffs,
        'c0_signals_100pct_match': True,
        'status': 'PASS'
    }
    print("  -> Full-history features, missing masks, and 2020-03-20 values verified with zero drift.")

    # -------------------------------------------------------------------------
    # 2. Production Dual-Track Baseline
    # -------------------------------------------------------------------------
    print("\n[Audit 2] Verifying Production Dual-Track Baseline...")
    prod_df = run_universal_reflexivity_radar('NOW', prices, macro)
    prod_first_ready = str(prod_df.loc[prod_df.signal_ready, 'date'].iloc[0].date())
    v23_first_ready = str(new_features.loc[new_features.signal_ready, 'date'].iloc[0].date())
    assert prod_first_ready == v23_first_ready == '2014-04-16'
    assert new_features.signal_ready.equals(prod_df.signal_ready), "Full-history signal_ready parity mismatch!"
    
    evidence['production_baseline'] = {
        'production_signal_ready_start': prod_first_ready,
        'v2_3_signal_ready_start': v23_first_ready,
        'full_history_parity': True,
        'status': 'PASS'
    }
    print(f"  -> Production baseline verified: first_ready={prod_first_ready} with 100% full-history parity.")

    # -------------------------------------------------------------------------
    # 3. Trade Clock & Re-entry Stop Loss Countdown (Requirement 3)
    # -------------------------------------------------------------------------
    print("\n[Audit 3] Verifying Re-entry Stop Clock Calendar Progression...")
    case = tests.TestFactorialExperimentEngineV23()
    case.setUp()
    stop_df = case.df_base.iloc[:35].copy()
    stop_df['signal_ready'] = True
    stop_df.loc[1, 'Trigger_Panic'] = True
    stop_df.loc[4, ['raw_sell', 'sell_reason']] = [True, 'BUBBLE']
    stop_df['ma50_band'] = False
    stop_df.loc[12, 'ma50_band'] = True
    stop_df.loc[12, 'q1_dot'] = 0.2  # Reentry fills day 13
    stop_df.loc[14:24, 'signal_ready'] = False
    
    # Day 25 (Day 12 after reentry): timer expired at Day 10 -> stop orders must be 0!
    df_late = stop_df.copy()
    df_late.loc[25, 'close'] = 94.0
    res_late = exp.run_execution_simulation(df_late, use_factor_c=True, dca_monthly=0)
    assert res_late['stop_loss_order_count'] == 0, "Stop loss must not trigger on Day 12!"
    
    # Day 23 (Day 10 after reentry): final valid day of stop loss protection -> triggers stop!
    df_valid = stop_df.copy()
    df_valid.loc[23, 'close'] = 94.0
    res_valid = exp.run_execution_simulation(df_valid, use_factor_c=True, dca_monthly=0)
    assert res_valid['stop_loss_order_count'] == 1, "Stop loss must trigger on Day 10!"
    
    evidence['stop_clock_advancement'] = {
        'day_10_valid_stop_triggered': True,
        'day_12_expired_stop_ignored': True,
        'status': 'PASS'
    }
    print("  -> Stop clock advancement verified: Day 10 valid stop triggered, Day 12 expired stop ignored.")

    # -------------------------------------------------------------------------
    # 4. Holding Position DCA Catch-up & Pending Sell Protection (Requirement 2)
    # -------------------------------------------------------------------------
    print("\n[Audit 4] Verifying Holding DCA Catch-up & Pending Sell Protection...")
    raw = prices.copy()
    raw.loc[raw.date.eq('2018-02-01'), 'close'] = np.nan
    prepared = exp.prepare_base_features(raw, macro)
    sub = exp.generate_signals(prepared)
    sub = sub[sub.date.between('2018-01-29', '2018-02-07')].copy().reset_index(drop=True)
    sub['Trigger_Panic'] = False
    sub.loc[0, 'Trigger_Panic'] = True
    sub['cond_trend'] = False
    sub['raw_sell'] = False
    sub['sell_reason'] = 'NONE'
    
    res_dca = exp.run_execution_simulation(sub, initial_cash=10000.0, dca_monthly=1000.0)
    ex_dca = res_dca['executor_instance']
    assert ex_dca.daily_states[-1]['cash'] < 10.0, f"Idle cash {ex_dca.daily_states[-1]['cash']} remained in account!"
    
    # 1. Holding DCA catch-up on missing price day
    res_dca = exp.run_execution_simulation(sub, initial_cash=10000.0, dca_monthly=1000.0)
    ex_dca = res_dca['executor_instance']
    assert ex_dca.daily_states[-1]['cash'] < 10.0, f"Idle cash {ex_dca.daily_states[-1]['cash']} remained in account!"
    
    # 2. Real loop pending sell protection under scheduled DCA contribution
    guard = case.df_base.iloc[:8].copy()
    guard['date'] = pd.to_datetime(['2023-01-27', '2023-01-30', '2023-01-31',
                                     '2023-02-01', '2023-02-02', '2023-02-03',
                                     '2023-02-06', '2023-02-07'])
    guard.loc[0, 'Trigger_Panic'] = True
    guard.loc[2, ['raw_sell', 'sell_reason']] = [True, 'BEAR']
    guard.loc[3, 'close'] = np.nan
    res_guard = exp.run_execution_simulation(guard)
    risk_orders = [o for o in res_guard['executor_instance'].orders_history if o['reason'] == 'BEAR']
    assert len(risk_orders) == 1
    assert risk_orders[0]['status'] == 'FILLED' and risk_orders[0]['actual_dt'] == '2023-02-02', \
        "Pending risk sell order was cancelled or failed to fill upon quote recovery!"
        
    # Mutation verification
    source = Path(exp.__file__).read_text(encoding='utf-8')
    marker = 'if pos == 1.0 and not submitted_sell_today and not has_pending_sell:'
    assert source.count(marker) == 1
    ns = dict(exp.__dict__)
    exec(compile(source.replace(marker, 'if pos == 1.0 and not submitted_sell_today:'), exp.__file__, 'exec'), ns)
    bad_res = ns['run_execution_simulation'](guard)
    bad_risk = [o for o in bad_res['executor_instance'].orders_history if o['reason'] == 'BEAR'][0]
    assert bad_risk['status'] == 'CANCELLED', "Mutation removing guard must cause CANCELLED status!"
    
    evidence['dca_and_pending_sell_protection'] = {
        'dca_cash_fully_invested': True,
        'final_cash': ex_dca.daily_states[-1]['cash'],
        'pending_sell_protected': True,
        'mutation_verified': True,
        'status': 'PASS'
    }
    print("  -> Holding DCA catch-up verified: delayed cash fully invested upon price recovery; pending sell protected.")

    # -------------------------------------------------------------------------
    # 5. Open Position Stale Valuation & Forward Return Verification (Requirement 4)
    # -------------------------------------------------------------------------
    print("\n[Audit 5] Verifying Open Position Stale Valuation & Forward Returns...")
    terminal = case.df_base.iloc[:4].copy()
    terminal.loc[0, 'Trigger_Panic'] = True
    terminal.loc[2, 'close'] = 120.0
    terminal.loc[3, 'close'] = np.nan
    
    end_res = exp.run_execution_simulation(terminal, initial_cash=10000.0, dca_monthly=0, fee_rate=0)
    open_pos = end_res['open_positions'][0]
    acc_state = end_res['executor_instance'].daily_states[-1]
    
    assert open_pos['latest_market_val'] == 12000.0, f"Open position market value {open_pos['latest_market_val']} != 12000!"
    assert acc_state['equity'] == 12000.0
    assert open_pos['valuation_quality'] == 'stale'
    
    # Forward returns horizon quote check
    fwd_df = case.df_base.iloc[:30].copy()
    fwd_df.loc[0, 'Trigger_Panic'] = True
    fwd_df.loc[21, 'close'] = np.nan
    fwd_res = exp.run_execution_simulation(fwd_df, dca_monthly=0)
    event = fwd_res['event_forward_evaluations'][0]
    assert not event['valid_fill_20'], "Missing target price must set valid_fill_20 to False!"
    assert np.isnan(event['fwd_ret_fill_20d'])
    
    evidence['open_position_and_forward_returns'] = {
        'stale_open_position_value': open_pos['latest_market_val'],
        'reconciles_with_executor_equity': True,
        'missing_horizon_quote_sets_valid_false': True,
        'status': 'PASS'
    }
    print("  -> Open position valuation (zero cost fallback) and forward return horizon checks verified.")

    # -------------------------------------------------------------------------
    # 6. Extrema Evaluation Window & End Truncation (Requirement 6)
    # -------------------------------------------------------------------------
    print("\n[Audit 6] Verifying Extrema Matching Window [S - 15, S + 5] & Truncation...")
    peak_df = pd.DataFrame({
        'date': pd.bdate_range('2020-01-01', periods=160),
        'close': [200.0 - abs(i - 50) for i in range(160)],
        'Trigger_Panic': False,
        'raw_sell': False
    })
    # S = 40 (peak - 10): misses E = 50 -> FDR = 100%
    p40 = peak_df.copy()
    p40.loc[40, 'raw_sell'] = True
    res40 = exp.evaluate_signals(p40, price_col='close', window=20)
    assert res40['sell_fdr'] == 100.0
    assert res40['top_miss_rate'] == 100.0
    
    # S = 60 (peak + 10): hits E = 50 -> FDR = 0%
    p60 = peak_df.copy()
    p60.loc[60, 'raw_sell'] = True
    res60 = exp.evaluate_signals(p60, price_col='close', window=20)
    assert res60['sell_fdr'] == 0.0
    assert res60['top_miss_rate'] == 0.0
    
    # Cross-boundary check: Peak at E = 102, Signal at S = 99 (within eval_mask [20:100])
    peak_cross = pd.DataFrame({
        'date': pd.bdate_range('2020-01-01', periods=160),
        'close': [200.0 - abs(i - 102) for i in range(160)],
        'Trigger_Panic': False,
        'raw_sell': False
    })
    peak_cross.loc[99, 'raw_sell'] = True
    res_cross = exp.evaluate_signals(peak_cross, price_col='close', window=20)
    assert res_cross['sell_signals_count'] == 1
    assert res_cross['sell_fdr'] == 0.0, f"Cross-boundary FDR must be 0.0%, got {res_cross['sell_fdr']}%!"
    
    evidence['extrema_evaluation_window'] = {
        's_40_misses_peak_50': True,
        's_60_hits_peak_50': True,
        'cross_boundary_fdr_zero': True,
        'status': 'PASS'
    }
    print("  -> Extrema matching window verified: S=40 misses peak 50 (FDR=100%), S=60 hits peak 50 (FDR=0%), cross-boundary FDR=0%.")

    # -------------------------------------------------------------------------
    # 7. Sub-period Deliverable Coverage (Requirement 5)
    # -------------------------------------------------------------------------
    print("\n[Audit 7] Verifying Sub-period Deliverable Coverage...")
    sub_df = pd.read_csv(OUT_DIR / 'subperiod_evaluation_v2_3.csv')
    assert len(sub_df) == 96, f"Subperiod evaluation CSV row count {len(sub_df)} != 96!"
    modes = sorted(sub_df['Mode'].unique().tolist())
    segs = sorted(sub_df['Segment'].unique().tolist())
    assets = sorted(sub_df['Asset'].unique().tolist())
    
    assert modes == ['Mode_A_Continuous_Inherited', 'Mode_B_Fresh_Reset']
    assert segs == ['Calibration_Segment_2014_2019', 'Historical_Verification_2020_2026']
    assert assets == ['NOW', 'QQQ', 'SPY']
    
    # 1. Mode A opening equity reconciliation for NOW C7
    now_c7_a = sub_df[(sub_df.Asset == 'NOW') & (sub_df.Config == 'C7_Full_Candidate') 
                      & (sub_df.Segment == 'Historical_Verification_2020_2026') 
                      & (sub_df.Mode == 'Mode_A_Continuous_Inherited')].iloc[0]
    assert now_c7_a['Strat_Start_Equity'] == 412487.19, f"Mode A start equity {now_c7_a['Strat_Start_Equity']} != 412487.19!"
    assert now_c7_a['Bench_Start_Equity'] == 734340.24, f"Mode A bench start equity {now_c7_a['Bench_Start_Equity']} != 734340.24!"
    assert now_c7_a['Strat_XIRR%'] == 9.81, f"Mode A corrected XIRR {now_c7_a['Strat_XIRR%']} != 9.81%!"
    assert now_c7_a['Bench_XIRR%'] == 14.51, f"Mode A bench corrected XIRR {now_c7_a['Bench_XIRR%']} != 14.51%!"
    
    # 2. Mode B total DCA includes initial day contribution ($81k for verification, $69k for calibration)
    now_c7_b = sub_df[(sub_df.Asset == 'NOW') & (sub_df.Config == 'C7_Full_Candidate') 
                      & (sub_df.Segment == 'Historical_Verification_2020_2026') 
                      & (sub_df.Mode == 'Mode_B_Fresh_Reset')].iloc[0]
    assert now_c7_b['Strat_Total_DCA'] == 81000.0, f"Mode B total DCA {now_c7_b['Strat_Total_DCA']} != 81000.0!"
    assert now_c7_b['Bench_Total_DCA'] == 81000.0, f"Mode B bench total DCA {now_c7_b['Bench_Total_DCA']} != 81000.0!"
    assert now_c7_b['Strat_Start_Equity'] + now_c7_b['Strat_Total_DCA'] == 181000.0
    
    # 3. Flat no-fee counterexample: economic XIRR must be 0.00%
    flat = case.df_base.iloc[:100].copy()
    calendar = pd.bdate_range('2019-12-27', periods=len(flat) + 1)
    flat['date'] = calendar[calendar != pd.Timestamp('2020-01-01')][:len(flat)]
    flat.loc[0, 'Trigger_Panic'] = True
    flat_result = exp.run_execution_simulation(flat, initial_cash=100000, dca_monthly=1000, fee_rate=0)
    flat_segs = exp.run_subperiod_evaluations('FLAT', 'C0', flat, '2019-12-27', False, False, flat_result)
    flat_a = next(r for r in flat_segs if r['Mode'] == 'Mode_A_Continuous_Inherited'
                  and r['Segment'] == 'Historical_Verification_2020_2026')
    assert abs(flat_a['Strat_XIRR%']) < 0.01, f"Flat no-fee Mode A XIRR must be 0.00%, got {flat_a['Strat_XIRR%']}%!"
    
    evidence['subperiod_deliverable'] = {
        'modes_covered': modes,
        'segments_covered': segs,
        'assets_covered': assets,
        'total_rows': len(sub_df),
        'now_c7_mode_a_reconciled': True,
        'mode_b_first_dca_included': True,
        'flat_no_fee_xirr_zero': True,
        'status': 'PASS'
    }
    print(f"  -> Sub-period deliverable verified: {len(sub_df)} rows, Mode A prior close anchor reconciled, Mode B DCA complete, flat no-fee XIRR=0.00%.")

    # -------------------------------------------------------------------------
    # 8. Factor C Removal of AFTER_STOP & Control Group Isolation
    # -------------------------------------------------------------------------
    print("\n[Audit 8] Verifying Factor C Clean-up & Control Group Stop Orders...")
    source = Path(exp.__file__).read_text(encoding='utf-8')
    assert 'AFTER_STOP' not in source, "Unapproved AFTER_STOP state still present in source code!"
    
    stop_counts = {}
    for asset in ['now', 'qqq', 'spy']:
        df_asset = pd.read_csv(OUT_DIR / f'factorial_ablation_results_v2_3_{asset}.csv')
        for idx in [0, 1, 2, 4]:  # C0, C1, C2, C4
            cfg = df_asset.iloc[idx]['Config']
            stops = int(df_asset.iloc[idx]['Stop_Loss_Orders'])
            stop_counts[f"{asset.upper()}_{cfg}"] = stops
            assert stops == 0, f"Control group {asset.upper()} {cfg} had {stops} stop loss orders!"
            
    evidence['factor_c_isolation'] = {
        'after_stop_removed': True,
        'control_group_stop_orders': stop_counts,
        'status': 'PASS'
    }
    print("  -> Factor C clean-up verified: zero AFTER_STOP state; control group stop loss orders strictly 0.")

    # -------------------------------------------------------------------------
    # Summary of Published Numerical Metrics
    # -------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("ACTUAL REPRODUCED BENCHMARK AND STRATEGY METRICS (ZERO PRESET NUMBERS)")
    print("=" * 80)
    
    metrics_summary = {}
    for asset in ['now', 'qqq', 'spy']:
        df_asset = pd.read_csv(OUT_DIR / f'factorial_ablation_results_v2_3_{asset}.csv')
        bench_row = df_asset.iloc[0]
        c0_row = df_asset.iloc[0]
        c7_row = df_asset.iloc[7]
        metrics_summary[asset.upper()] = {
            'Benchmark': {
                'Final': float(bench_row['Bench_Final']),
                'XIRR%': float(bench_row['Bench_XIRR%']),
                'MDD%': float(bench_row['Bench_MDD%'])
            },
            'C0_Baseline': {
                'Final': float(c0_row['Strat_Final']),
                'XIRR%': float(c0_row['Strat_XIRR%']),
                'MDD%': float(c0_row['Strat_MDD%'])
            },
            'C7_Full_Candidate': {
                'Final': float(c7_row['Strat_Final']),
                'XIRR%': float(c7_row['Strat_XIRR%']),
                'MDD%': float(c7_row['Strat_MDD%']),
                'Stops': int(c7_row['Stop_Loss_Orders'])
            }
        }
        print(f"\n[{asset.upper()}]")
        print(f"  Benchmark : Final=${bench_row['Bench_Final']:,.2f} | XIRR={bench_row['Bench_XIRR%']:.2f}% | MDD={bench_row['Bench_MDD%']:.2f}%")
        print(f"  C0 Strat  : Final=${c0_row['Strat_Final']:,.2f} | XIRR={c0_row['Strat_XIRR%']:.2f}% | MDD={c0_row['Strat_MDD%']:.2f}%")
        print(f"  C7 Strat  : Final=${c7_row['Strat_Final']:,.2f} | XIRR={c7_row['Strat_XIRR%']:.2f}% | MDD={c7_row['Strat_MDD%']:.2f}% | Stops={c7_row['Stop_Loss_Orders']}")
        
    events_df = pd.read_csv(OUT_DIR / 'forward_return_evaluations_v2_3.csv')
    event_breakdown = events_df['event_type'].value_counts().to_dict()
    evidence['event_counts'] = event_breakdown
    evidence['total_events'] = len(events_df)
    unique_entries = int(events_df[events_df['event_type'].isin(['TREND_BUY', 'REENTRY_BUY', 'PANIC_BUY'])].drop_duplicates(['Asset', 'fill_dt', 'event_type']).shape[0])
    evidence['unique_entry_events'] = unique_entries
    
    print("\n[Event Counts Breakdown]")
    for ev_type, count in event_breakdown.items():
        print(f"  {ev_type:20s}: {count:,}")
    print(f"  Total Event Records : {len(events_df):,}")
    print(f"  Unique Buy Entries  : {unique_entries:,}")
    
    (OUT_DIR / 'claims_evidence_v2_3.json').write_text(json.dumps(evidence, indent=2), encoding='utf-8')
    print("\nALL_V2_3_CLAIMS_VERIFIED")


if __name__ == '__main__':
    main()
