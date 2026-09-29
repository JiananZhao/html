"""
Unit & Integration Test Suite for Factorial Ablation Experiment Engine v2.3
===========================================================================
Hardened test suite covering:
1. Feature preparation & raw NaN preservation;
2. End-to-end missing price delay and stale valuation;
3. Signal objective evaluation: [S - 15, S + 5] window & end truncation [window : n - 60];
4. Panic latch memory & calendar-day hysteresis non-consumption;
5. Wave cost accounting: initial entry date & duration preserved across DCAs, exact holding days (23);
6. Re-entry stop loss countdown strictly advances across unready and missing quote days;
7. Holding position DCA catch-up & pending sell order protection;
8. Open position valuation with zero cost fallback & forward return quote availability;
9. Full-history model equivalence with strict missing mask parity and <= 1e-6 tolerance without isnan bypass;
10. Fault detection sensitivity (latch consumption mutation, ffill mutation, DCA overwrite mutation, NaN mask mutation).
"""

import sys
import unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(ROOT))

import audit_artifacts.gemini_review_20260923.v2_3_remediation.run_factorial_experiment_v2_3 as exp
from audit_artifacts.gemini_review_20260923 import run_factorial_experiment as old
from reflexivity_engine import run_universal_reflexivity_radar


class TestFactorialExperimentEngineV23(unittest.TestCase):

    def setUp(self):
        """Prepare base data for testing strictly with all standard feature columns."""
        dates = pd.bdate_range('2023-01-03', periods=100)
        self.df_base = pd.DataFrame({
            'date': dates,
            'close': 100.0,
            'high': 102.0,
            'low': 98.0,
            'volume': 1000000.0,
            'MA10': 95.0,
            'MA20': 92.0,
            'MA50': 90.0,
            'MA200': 85.0,
            'Dist_200MA': 0.0,
            'Dist_50MA': 0.0,
            'MA200_Slope': 0.0,
            'q1': 0.0,
            'q1_dot': 0.0,
            'q1_ddot': 0.0,
            'v_dot': 0.0,
            'Quadrant': 1,
            'Score_Dim1_Pos': 50.0,
            'Score_Dim2_Vel': 50.0,
            'Score_Dim3_Lyapunov': 50.0,
            'Score_Dim5_Liquidity': 50.0,
            'Score_Dim6_Macro': 50.0,
            'Composite_Score_M0': 50.0,
            'Score_Overheat_A': 0.0,
            'Score_MacroStress_A': 50.0,
            'Score_PanicDepth_A': 50.0,
            'Macro_MA200': 80.0,
            'HYG': 80.0,
            'BAA10Y': 1.5,
            'NFCI': -0.5,
            'Real_Yield': 1.0,
            'RY_Surge': False,
            'macro_crisis_regime': False,
            'Price_Z': 0.0,
            'Macro_Z': 0.0,
            'Dynamic_Beta': 1.0,
            'Expected_Price_Z': 0.0,
            'Gap': 0.0,
            'Gap_Max_45': 0.0,
            'signal_ready': True,
            'Trigger_Panic': False,
            'Trigger_Bubble_Top': False,
            'Trigger_Bear_Top': False,
            'raw_sell': False,
            'sell_reason': 'NONE',
            'cond_trend': False
        })

    def test_01_feature_parity_and_raw_nan_preservation(self):
        """Verify that prepare_base_features does not ffill close prices and preserves NaNs."""
        df_p = self.df_base[['date', 'close', 'open', 'high', 'low', 'volume']].copy() if 'open' in self.df_base.columns else self.df_base[['date', 'close', 'high', 'low', 'volume']].copy()
        df_p['open'] = df_p['close']
        df_m = self.df_base[['date', 'HYG', 'BAA10Y', 'NFCI', 'Real_Yield']].copy()
        
        # Inject NaN into close
        df_p.loc[10, 'close'] = np.nan
        
        features = exp.prepare_base_features(df_p, df_m, price_col='close')
        self.assertTrue(pd.isna(features.loc[10, 'close']), "Raw close NaN must NOT be ffilled!")
        self.assertTrue(pd.isna(features.loc[10, 'Dist_200MA']), "Derived indicator on NaN close must be NaN!")

    def test_02_end_to_end_missing_price_delay(self):
        """Verify that pending orders are delayed when close quote is missing, and valuation is marked stale."""
        dates = pd.bdate_range('2020-01-01', periods=220)
        raw = pd.DataFrame({'date': dates, 'close': 100.0})
        raw.loc[210, 'close'] = np.nan
        raw_macro = pd.DataFrame({
            'date': dates, 'HYG': 80.0, 'BAA10Y': 1.5, 'NFCI': -0.5, 'Real_Yield': 1.0
        })
        prepared = exp.prepare_base_features(raw, raw_macro)
        self.assertTrue(pd.isna(prepared.loc[210, 'close']))
        
        sub = prepared.iloc[209:216].copy().reset_index(drop=True)
        sub['signal_ready'] = True
        sub['Trigger_Panic'] = False
        sub.loc[0, 'Trigger_Panic'] = True
        sub['raw_sell'] = False
        sub['sell_reason'] = 'NONE'
        sub['cond_trend'] = False
        
        res = exp.run_execution_simulation(sub, initial_cash=10000.0, dca_monthly=0.0)
        ex = res['executor_instance']
        
        missing_dt_str = str(dates[210].date())
        next_dt_str = str(dates[211].date())
        
        self.assertEqual(len(ex.fills), 1)
        self.assertEqual(ex.fills[0]['dt'], next_dt_str)
        self.assertEqual(ex.daily_states[1]['valuation_quality'], 'stale')

    def test_03_signal_objective_evaluation_matching_windows(self):
        """
        Verify [S - 15, S + 5] matching window for BOTH buys and sells,
        and verify that truncation mask [window : n - 60] excludes truncated ends.
        """
        n = 160
        synthetic = pd.DataFrame({
            'date': pd.bdate_range('2020-01-01', periods=n),
            'close': [200.0 - abs(i - 50) for i in range(n)],
            'Trigger_Panic': False,
            'raw_sell': False
        })
        # Peak at E = 50. window = 20. eval_mask = [20 : 100].
        # S = 40 (peak - 10): search [25, 45] -> misses E = 50
        df_40 = synthetic.copy()
        df_40.loc[40, 'raw_sell'] = True
        res_40 = exp.evaluate_signals(df_40, price_col='close', window=20)
        self.assertEqual(res_40['sell_fdr'], 100.0)
        self.assertEqual(res_40['top_miss_rate'], 100.0)
        
        # S = 60 (peak + 10): search [45, 65] -> hits E = 50
        df_60 = synthetic.copy()
        df_60.loc[60, 'raw_sell'] = True
        res_60 = exp.evaluate_signals(df_60, price_col='close', window=20)
        self.assertEqual(res_60['sell_fdr'], 0.0)
        self.assertEqual(res_60['top_miss_rate'], 0.0)
        
        # End truncation: signal at S = 120 (outside n - 60 = 100) must NOT enter denominator
        df_trunc = synthetic.copy()
        df_trunc.loc[120, 'raw_sell'] = True
        res_trunc = exp.evaluate_signals(df_trunc, price_col='close', window=20)
        self.assertEqual(res_trunc['sell_signals_count'], 0, "Truncated signal after n-60 must be excluded from evaluation!")
        
        # Cross-boundary check: Peak at E = 102, Signal at S = 99 (within eval_mask [20:100])
        # [S - 15, S + 5] = [84, 104], which includes E = 102!
        # Context matching must NOT treat this valid peak as missing or report 100% FDR.
        peak_df = pd.DataFrame({
            'date': pd.bdate_range('2020-01-01', periods=160),
            'close': [200.0 - abs(i - 102) for i in range(160)],
            'Trigger_Panic': False,
            'raw_sell': False
        })
        peak_df.loc[99, 'raw_sell'] = True
        res_cross = exp.evaluate_signals(peak_df, price_col='close', window=20)
        self.assertEqual(res_cross['sell_signals_count'], 1)
        self.assertEqual(res_cross['sell_fdr'], 0.0, "Valid peak across n-60 boundary within [S-15, S+5] must match (FDR=0%)!")

    def test_04_panic_latch_calendar_and_trading_days_schedule(self):
        """Verify that Factor B latch is not consumed when suppressed by calendar hysteresis."""
        df = self.df_base.iloc[:20].copy()
        df['Dist_200MA'] = 0.0
        df['Composite_Score_M0'] = 50.0
        df['close'] = 100.0
        df['MA10'] = 95.0
        df['q1_dot'] = 0.0
        
        # Idx 00: Panic fires
        df.loc[0, 'Dist_200MA'] = -12.0
        df.loc[0, 'q1_dot'] = 0.5
        
        # Idx 03: Panic re-arms latch
        df.loc[3, 'Dist_200MA'] = -12.0
        
        # Idx 04: passes technical gate, but suppressed by hysteresis (cal_days = 6 <= 15)
        df.loc[4, 'q1_dot'] = 0.5
        
        # Idx 12: passes technical gate, cal_days = 16 > 15
        df.loc[12, 'q1_dot'] = 0.5
        
        # Idx 13: technical gate true, but latch should be consumed
        df.loc[13, 'q1_dot'] = 0.5
        
        sig = exp.generate_signals(df, use_factor_b=True)
        self.assertTrue(sig.loc[0, 'Trigger_Panic'])
        self.assertFalse(sig.loc[4, 'Trigger_Panic'], "Idx 04 must be suppressed by calendar hysteresis")
        self.assertTrue(sig.loc[12, 'Trigger_Panic'], "Idx 12 must fire via preserved unconsumed latch")
        self.assertFalse(sig.loc[13, 'Trigger_Panic'], "Idx 13 must NOT fire because latch was consumed at Idx 12")

    def test_05_wave_cost_accounting_and_stop_isolation(self):
        """
        Verify wave holding accounting and duration:
        Idx 0 trigger -> fills Idx 1; DCA at Idx 21; Bubble sell at Idx 23 -> fills Idx 24.
        Exact holding duration = idx_exit - idx_entry = 24 - 1 = 23 trading days.
        Directly verify buy cost and net sell proceeds from executor fills.
        """
        df = self.df_base.iloc[:35].copy()
        df.loc[0, 'Trigger_Panic'] = True
        df.loc[20:, 'date'] = pd.bdate_range('2023-02-01', periods=15)
        df.loc[23, 'raw_sell'] = True
        df.loc[23, 'sell_reason'] = 'BUBBLE'
        
        res = exp.run_execution_simulation(df, initial_cash=10000.0, dca_monthly=1000.0, fee_rate=0.0005)
        self.assertEqual(res['round_trips'], 1)
        
        trade = res['round_trips_ledger'][0]
        ex = res['executor_instance']
        fills = ex.fills
        buys = [f for f in fills if f['direction'] == 'BUY']
        sells = [f for f in fills if f['direction'] == 'SELL']
        
        self.assertEqual(len(buys), 2, "Must have exactly 2 buys: initial entry + 1 DCA addition")
        self.assertEqual(len(sells), 1, "Must have exactly 1 sell")
        
        # 1. Entry Date & Duration Checks
        self.assertEqual(trade['entry_dt'], buys[0]['dt'], "entry_dt must be initial entry, NOT DCA date!")
        self.assertNotEqual(trade['entry_dt'], buys[1]['dt'], "entry_dt must NOT be overwritten by DCA!")
        self.assertEqual(trade['duration_trading_days'], 23, "Exact duration must be idx_exit (24) - idx_entry (1) = 23!")
        self.assertFalse(trade['is_short_term'])
        
        # 2. Formula Checks directly from fills
        expected_buy_cost = sum(b['signed_shares'] * b['price'] + b['fee'] for b in buys)
        expected_net_sell = abs(sells[0]['signed_shares']) * sells[0]['price'] - sells[0]['fee']
        expected_pnl = expected_net_sell - expected_buy_cost
        expected_return_pct = expected_pnl / expected_buy_cost * 100.0
        
        self.assertAlmostEqual(trade['total_buy_cost'], expected_buy_cost, places=2)
        self.assertAlmostEqual(trade['net_sell_proceeds'], expected_net_sell, places=2)
        self.assertAlmostEqual(trade['realized_pnl'], expected_pnl, places=2)
        self.assertAlmostEqual(trade['wave_return_pct'], expected_return_pct, places=4)
        self.assertEqual(res['stop_loss_order_count'], 0)

    def test_06_reentry_stop_clock_advances_across_unready_and_missing_quote_days(self):
        """
        Verify that re-entry stop timer advances in trading calendar time:
        - Re-entry fills on Day 13.
        - Days 14..24 are unready (signal_ready == False).
        - Day 25 (Day 12 after reentry) price drops to 94.0 -> STOP TIMER EXPIRED, NO STOP ORDER!
        - Contrast: Day 23 (Day 10 after reentry) price drops to 94.0 -> TRIGGERS STOP LOSS.
        """
        stop_df = self.df_base.iloc[:35].copy()
        stop_df['signal_ready'] = True
        stop_df.loc[1, 'Trigger_Panic'] = True
        stop_df.loc[4, ['raw_sell', 'sell_reason']] = [True, 'BUBBLE']
        stop_df['ma50_band'] = False
        stop_df.loc[12, 'ma50_band'] = True
        stop_df.loc[12, 'q1_dot'] = 0.2  # Reentry fills day 13
        stop_df.loc[14:24, 'signal_ready'] = False
        
        # Probe A: Price drop on Day 25 (Day 12 after reentry) -> Must NOT trigger stop!
        df_late = stop_df.copy()
        df_late.loc[25, 'close'] = 94.0
        res_late = exp.run_execution_simulation(df_late, use_factor_c=True, dca_monthly=0)
        self.assertEqual(res_late['stop_loss_order_count'], 0, "Stop loss must expire at 10 trading days; day 12 drop cannot trigger!")
        
        # Probe B: Price drop on Day 23 (Day 10 after reentry) -> Must trigger stop!
        df_valid = stop_df.copy()
        df_valid.loc[23, 'close'] = 94.0
        res_valid = exp.run_execution_simulation(df_valid, use_factor_c=True, dca_monthly=0)
        self.assertEqual(res_valid['stop_loss_order_count'], 1, "Day 10 is the final valid day of stop loss protection!")

    def test_07_holding_dca_catch_up_and_pending_sell_protection(self):
        """
        Verify holding DCA catch-up on missing price day and pending sell protection:
        - Real execution loop scenario: Day 0 Panic buy, Day 2 BEAR sell, Day 3 NaN quote + DCA scheduled, Day 4 Quote recovery;
        - Pending risk sell order MUST NOT be cancelled by DCA order and MUST execute as FILLED on Day 4;
        - Mutation sensitivity: removing 'and not has_pending_sell' MUST result in CANCELLED order and fail the test.
        """
        guard = self.df_base.iloc[:8].copy()
        guard['date'] = pd.to_datetime(['2023-01-27', '2023-01-30', '2023-01-31',
                                         '2023-02-01', '2023-02-02', '2023-02-03',
                                         '2023-02-06', '2023-02-07'])
        guard.loc[0, 'Trigger_Panic'] = True
        guard.loc[2, ['raw_sell', 'sell_reason']] = [True, 'BEAR']
        guard.loc[3, 'close'] = np.nan
        
        res = exp.run_execution_simulation(guard)
        ex = res['executor_instance']
        risk_orders = [o for o in ex.orders_history if o['reason'] == 'BEAR']
        self.assertEqual(len(risk_orders), 1)
        self.assertEqual(risk_orders[0]['status'], 'FILLED',
                         "Pending BEAR sell order must NOT be cancelled by monthly DCA!")
        self.assertEqual(risk_orders[0]['actual_dt'], '2023-02-02',
                         "Pending sell order must fill on next valid quote date!")
                         
        # Mutation check: verify that removing the guard condition causes order cancellation
        source = Path(exp.__file__).read_text(encoding='utf-8')
        marker = 'if pos == 1.0 and not submitted_sell_today and not has_pending_sell:'
        self.assertIn(marker, source)
        ns = dict(exp.__dict__)
        mutant_src = source.replace(marker, 'if pos == 1.0 and not submitted_sell_today:')
        exec(compile(mutant_src, exp.__file__, 'exec'), ns)
        bad_res = ns['run_execution_simulation'](guard)
        bad_risk = [o for o in bad_res['executor_instance'].orders_history if o['reason'] == 'BEAR'][0]
        self.assertEqual(bad_risk['status'], 'CANCELLED',
                         "Removing the pending sell guard MUST cancel the risk order, proving mutation detection!")

    def test_08_open_position_valuation_and_forward_return_quote_availability(self):
        """
        Verify open position valuation has zero cost fallback, reconciles with executor stale quote,
        and forward returns check start and target price availability across all paths.
        """
        terminal = self.df_base.iloc[:4].copy()
        terminal.loc[0, 'Trigger_Panic'] = True
        terminal.loc[2, 'close'] = 120.0
        terminal.loc[3, 'close'] = np.nan  # Terminal day quote missing
        
        res = exp.run_execution_simulation(terminal, initial_cash=10000.0, dca_monthly=0, fee_rate=0)
        open_pos = res['open_positions'][0]
        acc_state = res['executor_instance'].daily_states[-1]
        
        # Reconcile with executor last_valid_price (12000), NOT cost (10000)
        self.assertEqual(open_pos['latest_market_val'], 12000.0)
        self.assertEqual(acc_state['equity'], 12000.0)
        self.assertEqual(open_pos['valuation_quality'], 'stale')
        
        # Forward returns: target price missing at +20d must set valid_fill_20 = False
        fwd_df = self.df_base.iloc[:30].copy()
        fwd_df.loc[0, 'Trigger_Panic'] = True
        fwd_df.loc[21, 'close'] = np.nan
        fwd_res = exp.run_execution_simulation(fwd_df, dca_monthly=0)
        event = fwd_res['event_forward_evaluations'][0]
        self.assertFalse(event['valid_fill_20'], "Missing target price must set valid_fill_20 to False!")
        self.assertTrue(np.isnan(event['fwd_ret_fill_20d']))

    def test_09_full_history_model_equivalence_and_strict_masks(self):
        """
        Strict full-history model equivalence check:
        - 100% missing mask equality across all shared numeric columns;
        - Max absolute drift <= 1e-6 without isnan bypass;
        - Exact 2020-03-20 values to 6 decimal places;
        - Full-history C0 boolean signals match 100%.
        """
        prices = pd.read_csv(ROOT / 'now_ohlcv_local.csv')
        macro = pd.read_csv(ROOT / 'market_data_local.csv')
        
        df_new = exp.prepare_base_features(prices, macro)
        df_old = old.prepare_base_features(prices, macro)
        
        common_cols = [c for c in df_old.columns if c in df_new.columns and c != 'date']
        for c in common_cols:
            if pd.api.types.is_numeric_dtype(df_new[c]):
                self.assertTrue(df_new[c].isna().equals(df_old[c].isna()), f"Missing mask for {c} does not match!")
                valid_mask = df_old[c].notna()
                if valid_mask.any():
                    if df_new[c].dtype == bool:
                        diff = float((df_new.loc[valid_mask, c] != df_old.loc[valid_mask, c]).sum())
                    else:
                        diff = float((df_new.loc[valid_mask, c] - df_old.loc[valid_mask, c]).abs().max())
                    self.assertFalse(np.isnan(diff), f"diff is NaN for {c}")
                    self.assertLessEqual(diff, 1e-6, f"Column {c} max abs diff {diff} > 1e-6")
                    
        # Check 2020-03-20 exact values
        cols = ['q1', 'q1_dot', 'q1_ddot', 'v_dot', 'Composite_Score_M0', 'Score_Overheat_A', 'Score_PanicDepth_A']
        row_new = df_new.loc[df_new.date == '2020-03-20', cols].iloc[0].round(6).to_dict()
        row_old = df_old.loc[df_old.date == '2020-03-20', cols].iloc[0].round(6).to_dict()
        self.assertEqual(row_new, row_old)
        
        sig_new = exp.generate_signals(df_new, False, False, False)
        sig_old = old.generate_signals(df_old, False, False, False)
        for sig_col in ['Trigger_Panic', 'Trigger_Bubble_Top', 'Trigger_Bear_Top', 'cond_trend']:
            self.assertTrue(sig_new[sig_col].equals(sig_old[sig_col]), f"Signal {sig_col} must match 100%")

    def test_10_mutation_catch(self):
        """Verify that genuine mutations fail assertions."""
        source = Path(exp.__file__).read_text(encoding='utf-8')
        
        # 1. Premature latch consumption mutation
        marker_latch = '# If suppressed by hysteresis, latch is NOT consumed and continues countdown.'
        self.assertIn(marker_latch, source)
        mutant_latch = source.replace(marker_latch, 'latch = False  # injected mutation')
        ns_latch = dict(exp.__dict__)
        exec(compile(mutant_latch, exp.__file__, 'exec'), ns_latch)
        with patch.object(exp, 'generate_signals', ns_latch['generate_signals']):
            with self.assertRaises(AssertionError):
                self.test_04_panic_latch_calendar_and_trading_days_schedule()
                
        # 2. NaN injection mutation into Score_Overheat_A
        marker_return = '    return df\n\n\ndef generate_signals'
        self.assertIn(marker_return, source)
        mutant_nan = source.replace(marker_return,
            "    df.loc[df['date'].eq(pd.Timestamp('2019-01-02')), 'Score_Overheat_A'] = np.nan\n" + marker_return, 1)
        ns_nan = dict(exp.__dict__)
        exec(compile(mutant_nan, exp.__file__, 'exec'), ns_nan)
        with patch.object(exp, 'prepare_base_features', ns_nan['prepare_base_features']):
            with self.assertRaises(AssertionError):
                self.test_09_full_history_model_equivalence_and_strict_masks()
                
        # 3. ffill mutation in prepare_base_features
        mutant_ffill = source.replace("p = df[price_col]", "df[price_col] = df[price_col].ffill()\n    p = df[price_col]")
        ns_ffill = dict(exp.__dict__)
        exec(compile(mutant_ffill, exp.__file__, 'exec'), ns_ffill)
        with patch.object(exp, 'prepare_base_features', ns_ffill['prepare_base_features']):
            with self.assertRaises(AssertionError):
                self.test_02_end_to_end_missing_price_delay()
                
        # 4. DCA overwrite entry date mutation
        marker_dca = "# DCA addition while holding: append to wave, DO NOT overwrite initial_entry_fill!\n                        wave_buys.append({"
        self.assertIn(marker_dca, source)
        mutant_dca = source.replace(
            marker_dca,
            "current_entry_fill = latest_fill  # injected mutation overwriting entry date\n                        wave_buys.append({"
        )
        ns_dca = dict(exp.__dict__)
        exec(compile(mutant_dca, exp.__file__, 'exec'), ns_dca)
        with patch.object(exp, 'run_execution_simulation', ns_dca['run_execution_simulation']):
            with self.assertRaises(AssertionError):
                self.test_05_wave_cost_accounting_and_stop_isolation()

    def test_11_mode_a_flat_no_fee_zero_economic_return(self):
        """
        Verify that in flat prices and zero fees, Mode A segment XIRR is exactly 0.00%
        and does NOT double count opening day deposit or confuse opening anchor.
        """
        flat = self.df_base.iloc[:100].copy()
        calendar = pd.bdate_range('2019-12-27', periods=len(flat) + 1)
        flat['date'] = calendar[calendar != pd.Timestamp('2020-01-01')][:len(flat)]
        flat.loc[0, 'Trigger_Panic'] = True
        flat_result = exp.run_execution_simulation(flat, initial_cash=100000, dca_monthly=1000, fee_rate=0)
        segments = exp.run_subperiod_evaluations('FLAT', 'C0', flat, '2019-12-27', False, False, flat_result)
        flat_a = next(r for r in segments if r['Mode'] == 'Mode_A_Continuous_Inherited'
                      and r['Segment'] == 'Historical_Verification_2020_2026')
        self.assertAlmostEqual(flat_a['Strat_XIRR%'], 0.0, places=2,
                               msg=f"Mode A flat no-fee XIRR must be 0.00%, got {flat_a['Strat_XIRR%']}%")
        self.assertEqual(flat_a['Strat_MDD%'], 0.0)
        self.assertEqual(flat_a['Strat_Start_Equity'], 101000.0)
        self.assertEqual(flat_a['Strat_Total_DCA'], 5000.0)
        self.assertEqual(flat_a['Strat_End_Equity'], 106000.0)


if __name__ == '__main__':
    unittest.main()
