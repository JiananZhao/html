import unittest
import pandas as pd
import numpy as np
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from expanding_ols import expanding_polyfit_residual

class TestCausality(unittest.TestCase):
    def test_expanding_ols_causality(self):
        """
        Verify that adding future data points does not alter the historical residuals
        calculated using expanding_polyfit_residual.
        """
        # Create a synthetic price series
        np.random.seed(42)
        prices = pd.Series(np.exp(np.cumsum(np.random.normal(0.001, 0.01, 500))))
        
        # Calculate residuals for the first 300 days
        prefix_prices = prices.iloc[:300].copy()
        prefix_res = expanding_polyfit_residual(prefix_prices, min_periods=252)
        
        # Calculate residuals for the full 500 days
        full_res = expanding_polyfit_residual(prices, min_periods=252)
        
        # The residuals for the first 300 days must be exactly identical
        # between the prefix run and the full run.
        prefix_residuals = prefix_res['Valuation_Residual'].dropna()
        full_residuals_matched = full_res['Valuation_Residual'].iloc[:300].dropna()
        
        # Ensure we have data
        self.assertGreater(len(prefix_residuals), 0, "No valid residuals computed for prefix")
        self.assertEqual(len(prefix_residuals), len(full_residuals_matched))
        
        # Check strict equality (up to floating point precision)
        pd.testing.assert_series_equal(
            prefix_residuals, 
            full_residuals_matched,
            check_names=False,
            check_exact=False,
            rtol=1e-5
        )

if __name__ == '__main__':
    unittest.main()
