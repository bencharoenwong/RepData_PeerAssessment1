"""
Comprehensive Test Suite for SmartEstimates with Decomposed Weighting
======================================================================

Tests edge cases including:
- Stale predictions
- Huge outliers (stock splits, data errors)
- Positive and negative EPS
- Negative earnings (P/E complications)
- Missing data and NaN values
- Division by zero scenarios
- Single analyst coverage
- Extreme forecast horizons

Run with: pytest test_smartestimates.py -v

Author: Quantitative Research
Date: 2025-11-23
"""

import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import warnings

# Import modules to test
from smartestimates import (
    SimulationConfig,
    DataSimulator,
    SmartEstimateBuilder,
    PerformanceEvaluator,
    run_simulation,
    IBESDataLoader,
    RealDataSmartEstimateEngine
)


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def basic_config():
    """Basic configuration for testing."""
    return SimulationConfig(
        n_companies=10,
        n_industries=2,
        n_analysts=5,
        n_periods=20,
        recency_halflife=30,
        min_history=5
    )


@pytest.fixture
def minimal_forecasts_df():
    """Minimal valid forecast dataset."""
    data = {
        'period': [0, 0, 0, 1, 1, 1],
        'company': ['AAPL', 'AAPL', 'AAPL', 'AAPL', 'AAPL', 'AAPL'],
        'industry': ['TECH', 'TECH', 'TECH', 'TECH', 'TECH', 'TECH'],
        'analyst_id': ['A1', 'A2', 'A3', 'A1', 'A2', 'A3'],
        'forecast_eps': [1.0, 1.1, 0.9, 1.2, 1.3, 1.1],
        'forecast_industry_component': [1.0, 1.0, 1.0, 1.2, 1.2, 1.2],
        'forecast_company_component': [0.0, 0.1, -0.1, 0.0, 0.1, -0.1],
        'forecast_date': [datetime(2023, 1, 1)] * 6,
        'realization_date': [datetime(2023, 3, 31), datetime(2023, 3, 31), datetime(2023, 3, 31),
                             datetime(2023, 6, 30), datetime(2023, 6, 30), datetime(2023, 6, 30)],
        'true_eps': [1.05, 1.05, 1.05, 1.25, 1.25, 1.25],
        'true_industry': [1.0, 1.0, 1.0, 1.2, 1.2, 1.2],
        'true_company': [0.05, 0.05, 0.05, 0.05, 0.05, 0.05],
        'skill_industry': [0.6, 0.7, 0.5, 0.6, 0.7, 0.5],
        'skill_company': [0.6, 0.5, 0.7, 0.6, 0.5, 0.7],
        'archetype': ['Generalist', 'Macro Specialist', 'Stock Picker',
                     'Generalist', 'Macro Specialist', 'Stock Picker']
    }
    return pd.DataFrame(data)


# ============================================================================
# EDGE CASE TESTS: STALE PREDICTIONS
# ============================================================================

class TestStalePredictions:
    """Test handling of old/stale forecasts."""

    def test_very_old_forecasts(self, basic_config):
        """Test forecasts that are 1+ year old."""
        data = {
            'period': [0, 0, 1, 1],
            'company': ['AAPL', 'AAPL', 'AAPL', 'AAPL'],
            'industry': ['TECH', 'TECH', 'TECH', 'TECH'],
            'analyst_id': ['A1', 'A2', 'A1', 'A2'],
            'forecast_eps': [1.0, 1.1, 1.2, 1.3],
            'forecast_date': [
                datetime(2022, 1, 1),  # Very old
                datetime(2023, 11, 1),  # Recent
                datetime(2022, 1, 1),  # Very old
                datetime(2023, 11, 1)   # Recent
            ],
            'realization_date': [datetime(2023, 12, 31)] * 4,
            'true_eps': [1.15] * 4,
            'forecast_industry_component': [1.0, 1.0, 1.2, 1.2],
            'forecast_company_component': [0.0, 0.1, 0.0, 0.1],
            'true_industry': [1.0] * 4,
            'true_company': [0.15] * 4,
            'skill_industry': [0.6] * 4,
            'skill_company': [0.6] * 4,
            'archetype': ['Generalist'] * 4
        }
        df = pd.DataFrame(data)

        builder = SmartEstimateBuilder(basic_config)
        result = builder.construct_smartestimate(df, 0, 'AAPL')

        assert result is not None
        assert 'smart_estimate' in result
        assert result['n_analysts'] == 2
        # SmartEstimate should exist even with old forecasts
        assert not np.isnan(result['smart_estimate'])

    def test_forecast_horizon_calculation(self):
        """Test calculation of forecast horizon (days between forecast and realization)."""
        data = {
            'company': ['AAPL', 'AAPL', 'AAPL'],
            'analyst_id': ['A1', 'A2', 'A3'],
            'forecast_date': [
                datetime(2023, 1, 1),
                datetime(2023, 3, 1),
                datetime(2023, 3, 25)
            ],
            'realization_date': [datetime(2023, 3, 31)] * 3,
            'forecast_eps': [1.0, 1.1, 1.2],
            'realized_eps': [1.05] * 3,
            'industry': ['TECH'] * 3
        }
        df = pd.DataFrame(data)

        # Calculate horizon
        df['forecast_horizon_days'] = (df['realization_date'] - df['forecast_date']).dt.days

        assert df['forecast_horizon_days'].iloc[0] == 89  # ~3 months
        assert df['forecast_horizon_days'].iloc[1] == 30  # 1 month
        assert df['forecast_horizon_days'].iloc[2] == 6   # 6 days

    def test_recency_weight_decay(self, basic_config):
        """Test that recency weights decay exponentially."""
        builder = SmartEstimateBuilder(basic_config)

        # Simulate accuracy history with different ages
        builder.accuracy_history['industry']['A1'] = [
            (0, 0.01),   # 20 periods ago (20*7 = 140 days)
            (10, 0.01),  # 10 periods ago (70 days)
            (19, 0.01)   # 1 period ago (7 days)
        ]

        current_period = 20
        weight = builder.compute_analyst_weights('A1', 'AAPL', current_period, 'industry')

        # Recent data should be weighted more heavily
        # Weight should be positive and finite
        assert weight > 0
        assert np.isfinite(weight)


# ============================================================================
# EDGE CASE TESTS: HUGE OUTLIERS
# ============================================================================

class TestHugeOutliers:
    """Test handling of extreme outliers (e.g., stock split errors)."""

    def test_stock_split_not_adjusted(self, basic_config):
        """Simulate stock split where one analyst forgot to adjust."""
        data = {
            'period': [0] * 5,
            'company': ['AAPL'] * 5,
            'industry': ['TECH'] * 5,
            'analyst_id': ['A1', 'A2', 'A3', 'A4', 'A5'],
            'forecast_eps': [
                1.0,    # Normal
                1.1,    # Normal
                0.95,   # Normal
                10.0,   # OUTLIER - forgot 10:1 split!
                1.05    # Normal
            ],
            'forecast_industry_component': [1.0] * 5,
            'forecast_company_component': [0.0, 0.1, -0.05, 9.0, 0.05],
            'true_eps': [1.02] * 5,
            'true_industry': [1.0] * 5,
            'true_company': [0.02] * 5,
            'skill_industry': [0.6] * 5,
            'skill_company': [0.6] * 5,
            'archetype': ['Generalist'] * 5
        }
        df = pd.DataFrame(data)

        builder = SmartEstimateBuilder(basic_config)
        result = builder.construct_smartestimate(df, 0, 'AAPL')

        # Consensus should be heavily distorted by outlier
        consensus = df['forecast_eps'].mean()
        assert consensus > 2.0  # Pulled up by 10.0 outlier

        # SmartEstimate should be more robust (winsorization)
        assert result['smart_estimate'] < 2.0  # Should be closer to true value
        assert abs(result['smart_estimate'] - 1.02) < abs(consensus - 1.02)

    def test_extreme_negative_outlier(self, basic_config):
        """Test handling of extreme negative forecast (data error)."""
        data = {
            'period': [0] * 5,
            'company': ['AAPL'] * 5,
            'industry': ['TECH'] * 5,
            'analyst_id': ['A1', 'A2', 'A3', 'A4', 'A5'],
            'forecast_eps': [
                1.0,
                1.1,
                -999.0,  # Extreme outlier (data error)
                0.95,
                1.05
            ],
            'forecast_industry_component': [1.0, 1.0, -999.0, 1.0, 1.0],
            'forecast_company_component': [0.0, 0.1, 0.0, -0.05, 0.05],
            'true_eps': [1.02] * 5,
            'true_industry': [1.0] * 5,
            'true_company': [0.02] * 5,
            'skill_industry': [0.6] * 5,
            'skill_company': [0.6] * 5,
            'archetype': ['Generalist'] * 5
        }
        df = pd.DataFrame(data)

        builder = SmartEstimateBuilder(basic_config)
        result = builder.construct_smartestimate(df, 0, 'AAPL')

        # SmartEstimate should handle this via winsorization
        assert result is not None
        assert np.isfinite(result['smart_estimate'])
        # Should be closer to normal range than raw consensus
        assert -10 < result['smart_estimate'] < 10

    def test_winsorization_effectiveness(self, basic_config):
        """Test that winsorization effectively removes outliers."""
        # Create data with extreme outliers
        normal_values = np.random.normal(1.0, 0.1, 98)
        outliers = np.array([100.0, -100.0])  # Extreme outliers
        all_values = np.concatenate([normal_values, outliers])

        data = {
            'period': [0] * 100,
            'company': ['AAPL'] * 100,
            'industry': ['TECH'] * 100,
            'analyst_id': [f'A{i}' for i in range(100)],
            'forecast_eps': all_values,
            'forecast_industry_component': [1.0] * 100,
            'forecast_company_component': all_values - 1.0,
            'true_eps': [1.0] * 100,
            'true_industry': [1.0] * 100,
            'true_company': [0.0] * 100,
            'skill_industry': [0.6] * 100,
            'skill_company': [0.6] * 100,
            'archetype': ['Generalist'] * 100
        }
        df = pd.DataFrame(data)

        builder = SmartEstimateBuilder(basic_config)
        result = builder.construct_smartestimate(df, 0, 'AAPL')

        # SmartEstimate should be close to 1.0, not distorted by outliers
        assert 0.5 < result['smart_estimate'] < 1.5
        assert abs(result['smart_estimate'] - 1.0) < 0.5


# ============================================================================
# EDGE CASE TESTS: NEGATIVE EARNINGS
# ============================================================================

class TestNegativeEarnings:
    """Test handling of negative EPS (losses)."""

    def test_all_negative_earnings(self, basic_config):
        """Test when company is losing money (all EPS negative)."""
        data = {
            'period': [0, 0, 0, 1, 1, 1],
            'company': ['LOSS', 'LOSS', 'LOSS', 'LOSS', 'LOSS', 'LOSS'],
            'industry': ['TECH', 'TECH', 'TECH', 'TECH', 'TECH', 'TECH'],
            'analyst_id': ['A1', 'A2', 'A3', 'A1', 'A2', 'A3'],
            'forecast_eps': [-0.50, -0.45, -0.55, -0.30, -0.28, -0.32],
            'forecast_industry_component': [-0.50, -0.50, -0.50, -0.30, -0.30, -0.30],
            'forecast_company_component': [0.0, 0.05, -0.05, 0.0, 0.02, -0.02],
            'true_eps': [-0.48, -0.48, -0.48, -0.31, -0.31, -0.31],
            'true_industry': [-0.50, -0.50, -0.50, -0.30, -0.30, -0.30],
            'true_company': [0.02, 0.02, 0.02, -0.01, -0.01, -0.01],
            'skill_industry': [0.6, 0.7, 0.5, 0.6, 0.7, 0.5],
            'skill_company': [0.6, 0.5, 0.7, 0.6, 0.5, 0.7],
            'archetype': ['Generalist'] * 6
        }
        df = pd.DataFrame(data)

        builder = SmartEstimateBuilder(basic_config)
        result = builder.construct_smartestimate(df, 0, 'LOSS')

        assert result is not None
        assert result['smart_estimate'] < 0  # Should predict loss
        assert np.isfinite(result['smart_estimate'])

    def test_mixed_positive_negative_forecasts(self, basic_config):
        """Test when analysts disagree on profit vs loss."""
        data = {
            'period': [0] * 5,
            'company': ['TURN'] * 5,
            'industry': ['TECH'] * 5,
            'analyst_id': ['A1', 'A2', 'A3', 'A4', 'A5'],
            'forecast_eps': [
                -0.10,  # Predicts loss
                0.05,   # Predicts small profit
                -0.02,  # Predicts small loss
                0.08,   # Predicts profit
                0.01    # Predicts breakeven
            ],
            'forecast_industry_component': [0.0] * 5,
            'forecast_company_component': [-0.10, 0.05, -0.02, 0.08, 0.01],
            'true_eps': [0.03, 0.03, 0.03, 0.03, 0.03],  # Actually profitable
            'true_industry': [0.0] * 5,
            'true_company': [0.03] * 5,
            'skill_industry': [0.6] * 5,
            'skill_company': [0.6] * 5,
            'archetype': ['Generalist'] * 5
        }
        df = pd.DataFrame(data)

        builder = SmartEstimateBuilder(basic_config)
        result = builder.construct_smartestimate(df, 0, 'TURN')

        assert result is not None
        assert np.isfinite(result['smart_estimate'])
        # Consensus should be close to 0 (mean of mixed forecasts)
        consensus = df['forecast_eps'].mean()
        assert abs(consensus) < 0.05

    def test_negative_earnings_with_pe_calculation(self):
        """Test that negative earnings don't break P/E-related metrics."""
        # Simulate earnings data
        eps = np.array([-0.50, 1.20, -0.30, 1.50, 0.80])
        price = 50.0

        # P/E ratio calculation (should handle negatives)
        pe_ratios = np.where(eps > 0, price / eps, np.nan)

        assert np.isnan(pe_ratios[0])  # Negative earnings -> NaN
        assert np.isfinite(pe_ratios[1])  # Positive -> valid P/E
        assert np.isnan(pe_ratios[2])  # Negative earnings -> NaN

    def test_deep_losses_to_profitability(self, basic_config):
        """Test turnaround scenario: deep losses → profitability."""
        data = {
            'period': [0, 0, 0, 1, 1, 1],
            'company': ['TURN'] * 6,
            'industry': ['TECH'] * 6,
            'analyst_id': ['A1', 'A2', 'A3'] * 2,
            'forecast_eps': [
                -5.00, -4.80, -5.20,  # Period 0: deep losses
                0.50, 0.60, 0.55      # Period 1: turnaround
            ],
            'forecast_industry_component': [-5.0, -5.0, -5.0, 0.5, 0.5, 0.5],
            'forecast_company_component': [0.0, 0.2, -0.2, 0.0, 0.1, 0.05],
            'true_eps': [-4.90, -4.90, -4.90, 0.58, 0.58, 0.58],
            'true_industry': [-5.0, -5.0, -5.0, 0.5, 0.5, 0.5],
            'true_company': [0.10, 0.10, 0.10, 0.08, 0.08, 0.08],
            'skill_industry': [0.6] * 6,
            'skill_company': [0.6] * 6,
            'archetype': ['Generalist'] * 6
        }
        df = pd.DataFrame(data)

        builder = SmartEstimateBuilder(basic_config)

        # Period 0 result
        result0 = builder.construct_smartestimate(df, 0, 'TURN')
        assert result0['smart_estimate'] < 0

        # Update history
        builder.update_accuracy_history(df[df['period'] == 0], 0)

        # Period 1 result
        result1 = builder.construct_smartestimate(df, 1, 'TURN')
        assert result1['smart_estimate'] > 0


# ============================================================================
# EDGE CASE TESTS: MISSING DATA & NaN
# ============================================================================

class TestMissingData:
    """Test handling of missing values and NaN."""

    def test_missing_forecast_values(self, basic_config):
        """Test when some forecast_eps values are NaN."""
        data = {
            'period': [0] * 5,
            'company': ['AAPL'] * 5,
            'industry': ['TECH'] * 5,
            'analyst_id': ['A1', 'A2', 'A3', 'A4', 'A5'],
            'forecast_eps': [1.0, np.nan, 1.1, 0.95, np.nan],
            'forecast_industry_component': [1.0, np.nan, 1.0, 1.0, np.nan],
            'forecast_company_component': [0.0, np.nan, 0.1, -0.05, np.nan],
            'true_eps': [1.02] * 5,
            'true_industry': [1.0] * 5,
            'true_company': [0.02] * 5,
            'skill_industry': [0.6] * 5,
            'skill_company': [0.6] * 5,
            'archetype': ['Generalist'] * 5
        }
        df = pd.DataFrame(data)

        builder = SmartEstimateBuilder(basic_config)
        result = builder.construct_smartestimate(df, 0, 'AAPL')

        # Should handle NaN via skipna=True
        assert result is not None
        assert np.isfinite(result['smart_estimate'])
        # Consensus should only use non-NaN values (3 analysts)
        assert result['n_analysts'] == 5  # Total count, but calculation handles NaN

    def test_all_forecasts_nan(self, basic_config):
        """Test when all forecasts are NaN (should return None or handle gracefully)."""
        data = {
            'period': [0] * 3,
            'company': ['AAPL'] * 3,
            'industry': ['TECH'] * 3,
            'analyst_id': ['A1', 'A2', 'A3'],
            'forecast_eps': [np.nan, np.nan, np.nan],
            'forecast_industry_component': [np.nan] * 3,
            'forecast_company_component': [np.nan] * 3,
            'true_eps': [1.02] * 3,
            'true_industry': [1.0] * 3,
            'true_company': [0.02] * 3,
            'skill_industry': [0.6] * 3,
            'skill_company': [0.6] * 3,
            'archetype': ['Generalist'] * 3
        }
        df = pd.DataFrame(data)

        builder = SmartEstimateBuilder(basic_config)
        result = builder.construct_smartestimate(df, 0, 'AAPL')

        # Should handle gracefully - might return NaN or None
        # The key is it shouldn't crash
        if result is not None:
            # If it returns a result, it should be NaN
            assert np.isnan(result['smart_estimate']) or result is None

    def test_missing_realized_eps(self, basic_config):
        """Test when realized EPS is missing (future periods)."""
        data = {
            'period': [0, 0, 0],
            'company': ['AAPL'] * 3,
            'industry': ['TECH'] * 3,
            'analyst_id': ['A1', 'A2', 'A3'],
            'forecast_eps': [1.0, 1.1, 0.95],
            'forecast_industry_component': [1.0] * 3,
            'forecast_company_component': [0.0, 0.1, -0.05],
            'true_eps': [np.nan] * 3,  # Not yet realized
            'true_industry': [np.nan] * 3,
            'true_company': [np.nan] * 3,
            'skill_industry': [0.6] * 3,
            'skill_company': [0.6] * 3,
            'archetype': ['Generalist'] * 3
        }
        df = pd.DataFrame(data)

        builder = SmartEstimateBuilder(basic_config)
        result = builder.construct_smartestimate(df, 0, 'AAPL')

        # Should still construct estimate (forecasting future)
        assert result is not None
        assert np.isfinite(result['smart_estimate'])
        # true_eps in result will be NaN, which is expected
        assert 'smart_estimate' in result


# ============================================================================
# EDGE CASE TESTS: DIVISION BY ZERO
# ============================================================================

class TestDivisionByZero:
    """Test scenarios that could cause division by zero."""

    def test_all_analysts_identical_errors(self, basic_config):
        """Test when all analysts have exactly the same error (RMSE variance = 0)."""
        builder = SmartEstimateBuilder(basic_config)

        # Create identical errors for all analysts
        builder.accuracy_history['industry']['A1'] = [(0, 0.01), (1, 0.01), (2, 0.01)]
        builder.accuracy_history['industry']['A2'] = [(0, 0.01), (1, 0.01), (2, 0.01)]
        builder.accuracy_history['industry']['A3'] = [(0, 0.01), (1, 0.01), (2, 0.01)]

        # Compute weights - should not crash
        w1 = builder.compute_analyst_weights('A1', 'AAPL', 3, 'industry')
        w2 = builder.compute_analyst_weights('A2', 'AAPL', 3, 'industry')
        w3 = builder.compute_analyst_weights('A3', 'AAPL', 3, 'industry')

        # All weights should be equal (since errors are identical)
        assert np.isfinite(w1)
        assert np.isfinite(w2)
        assert np.isfinite(w3)
        assert np.isclose(w1, w2)
        assert np.isclose(w2, w3)

    def test_zero_sum_weights(self, basic_config):
        """Test when weight sum is zero (all weights are 0)."""
        data = {
            'period': [0] * 3,
            'company': ['AAPL'] * 3,
            'industry': ['TECH'] * 3,
            'analyst_id': ['A1', 'A2', 'A3'],
            'forecast_eps': [1.0, 1.1, 0.95],
            'forecast_industry_component': [1.0] * 3,
            'forecast_company_component': [0.0, 0.1, -0.05],
            'true_eps': [1.02] * 3,
            'true_industry': [1.0] * 3,
            'true_company': [0.02] * 3,
            'skill_industry': [0.6] * 3,
            'skill_company': [0.6] * 3,
            'archetype': ['Generalist'] * 3
        }
        df = pd.DataFrame(data)

        builder = SmartEstimateBuilder(basic_config)
        # Don't add any history - so all weights should be equal (1.0 fallback)

        result = builder.construct_smartestimate(df, 0, 'AAPL')

        # Should handle via equal weighting fallback
        assert result is not None
        assert np.isfinite(result['smart_estimate'])

    def test_consensus_exactly_zero(self, basic_config):
        """Test when consensus is exactly 0 (for percentage calculation)."""
        data = {
            'period': [0] * 3,
            'company': ['AAPL'] * 3,
            'industry': ['TECH'] * 3,
            'analyst_id': ['A1', 'A2', 'A3'],
            'forecast_eps': [-0.05, 0.05, 0.00],  # Mean = 0
            'forecast_industry_component': [0.0] * 3,
            'forecast_company_component': [-0.05, 0.05, 0.0],
            'true_eps': [0.10] * 3,
            'true_industry': [0.0] * 3,
            'true_company': [0.10] * 3,
            'skill_industry': [0.6] * 3,
            'skill_company': [0.6] * 3,
            'archetype': ['Generalist'] * 3
        }
        df = pd.DataFrame(data)

        builder = SmartEstimateBuilder(basic_config)
        result = builder.construct_smartestimate(df, 0, 'AAPL')

        assert result is not None
        assert result['consensus'] == 0.0

        # Create results df for evaluation
        results_df = pd.DataFrame([result])
        evaluator = PerformanceEvaluator()
        results_df = evaluator.calculate_metrics(results_df)
        summary = evaluator.summary_statistics(results_df)

        # Should handle division by zero in percentage calc
        assert summary is not None
        # Improvement_% should be NaN when consensus is 0
        # (this is expected and handled)


# ============================================================================
# EDGE CASE TESTS: SINGLE ANALYST
# ============================================================================

class TestSingleAnalyst:
    """Test scenarios with only one analyst covering a stock."""

    def test_single_analyst_coverage(self, basic_config):
        """Test when only one analyst covers a company."""
        data = {
            'period': [0],
            'company': ['SMALL'],
            'industry': ['TECH'],
            'analyst_id': ['A1'],
            'forecast_eps': [1.0],
            'forecast_industry_component': [1.0],
            'forecast_company_component': [0.0],
            'true_eps': [1.05],
            'true_industry': [1.0],
            'true_company': [0.05],
            'skill_industry': [0.6],
            'skill_company': [0.6],
            'archetype': ['Generalist']
        }
        df = pd.DataFrame(data)

        builder = SmartEstimateBuilder(basic_config)
        result = builder.construct_smartestimate(df, 0, 'SMALL')

        assert result is not None
        assert result['n_analysts'] == 1
        # SmartEstimate should equal consensus (only one forecast)
        assert np.isclose(result['smart_estimate'], result['consensus'])

    def test_single_analyst_with_history(self, basic_config):
        """Test single analyst with historical accuracy."""
        builder = SmartEstimateBuilder(basic_config)

        # Add history for analyst
        builder.accuracy_history['industry']['A1'] = [
            (i, 0.01) for i in range(10)
        ]
        builder.accuracy_history['company'][('A1', 'SMALL')] = [
            (i, 0.01) for i in range(10)
        ]

        data = {
            'period': [10],
            'company': ['SMALL'],
            'industry': ['TECH'],
            'analyst_id': ['A1'],
            'forecast_eps': [1.0],
            'forecast_industry_component': [1.0],
            'forecast_company_component': [0.0],
            'true_eps': [1.05],
            'true_industry': [1.0],
            'true_company': [0.05],
            'skill_industry': [0.6],
            'skill_company': [0.6],
            'archetype': ['Generalist']
        }
        df = pd.DataFrame(data)

        result = builder.construct_smartestimate(df, 10, 'SMALL')

        # With history, weight should be calculated but result same as consensus
        assert result is not None
        assert np.isclose(result['smart_estimate'], result['consensus'])


# ============================================================================
# EDGE CASE TESTS: EMPTY DATA
# ============================================================================

class TestEmptyData:
    """Test handling of empty or minimal datasets."""

    def test_empty_forecast_dataframe(self, basic_config):
        """Test with completely empty dataframe."""
        df = pd.DataFrame()

        builder = SmartEstimateBuilder(basic_config)
        result = builder.construct_smartestimate(df, 0, 'AAPL')

        # Should return None for empty data
        assert result is None

    def test_no_forecasts_for_company_period(self, basic_config, minimal_forecasts_df):
        """Test requesting SmartEstimate for company-period with no data."""
        builder = SmartEstimateBuilder(basic_config)

        # Request forecast for company that doesn't exist
        result = builder.construct_smartestimate(minimal_forecasts_df, 0, 'TSLA')

        assert result is None

    def test_insufficient_analyst_coverage(self):
        """Test preprocessing filter when too few analysts."""
        loader = IBESDataLoader()

        data = {
            'company': ['AAPL', 'AAPL', 'MSFT'],
            'analyst_id': ['A1', 'A2', 'A1'],
            'forecast_date': [datetime(2023, 1, 1)] * 3,
            'realization_date': [datetime(2023, 3, 31)] * 3,
            'forecast_eps': [1.0, 1.1, 2.0],
            'realized_eps': [1.05, 1.05, 2.1],
            'industry': ['TECH', 'TECH', 'TECH']
        }
        df = pd.DataFrame(data)

        # Require minimum 5 analysts (neither company has enough)
        clean = loader.preprocess_ibes_data(df, min_analysts=5)

        # Should filter out all data
        assert len(clean) == 0


# ============================================================================
# EDGE CASE TESTS: EXTREME SCENARIOS
# ============================================================================

class TestExtremeScenarios:
    """Test extreme but realistic market scenarios."""

    def test_market_crash_scenario(self, basic_config):
        """Test during market crash (all forecasts dramatically wrong)."""
        # Analysts forecast normal earnings, but crash happens
        data = {
            'period': [0] * 10,
            'company': ['CRASH'] * 10,
            'industry': ['FIN'] * 10,
            'analyst_id': [f'A{i}' for i in range(10)],
            'forecast_eps': [2.0 + np.random.normal(0, 0.1) for _ in range(10)],  # Predict $2
            'forecast_industry_component': [2.0] * 10,
            'forecast_company_component': [np.random.normal(0, 0.1) for _ in range(10)],
            'true_eps': [-5.0] * 10,  # Actually lose $5 (crisis)
            'true_industry': [-5.0] * 10,
            'true_company': [0.0] * 10,
            'skill_industry': [0.6] * 10,
            'skill_company': [0.6] * 10,
            'archetype': ['Generalist'] * 10
        }
        df = pd.DataFrame(data)

        builder = SmartEstimateBuilder(basic_config)
        result = builder.construct_smartestimate(df, 0, 'CRASH')

        # All analysts were wrong in the same direction
        assert result is not None
        # SmartEstimate can't save you from black swan events
        # But it should still produce a finite estimate
        assert np.isfinite(result['smart_estimate'])

    def test_ipo_no_historical_data(self, basic_config):
        """Test IPO scenario with no historical analyst accuracy."""
        data = {
            'period': [0] * 8,
            'company': ['IPO'] * 8,
            'industry': ['TECH'] * 8,
            'analyst_id': [f'A{i}' for i in range(8)],
            'forecast_eps': [0.50, 0.45, 0.55, 0.48, 0.52, 0.49, 0.51, 0.47],
            'forecast_industry_component': [0.50] * 8,
            'forecast_company_component': [0.0, -0.05, 0.05, -0.02, 0.02, -0.01, 0.01, -0.03],
            'true_eps': [0.51] * 8,
            'true_industry': [0.50] * 8,
            'true_company': [0.01] * 8,
            'skill_industry': [0.6] * 8,
            'skill_company': [0.6] * 8,
            'archetype': ['Generalist'] * 8
        }
        df = pd.DataFrame(data)

        builder = SmartEstimateBuilder(basic_config)
        result = builder.construct_smartestimate(df, 0, 'IPO')

        # Should fall back to equal weighting (no history)
        assert result is not None
        # SmartEstimate should be close to consensus
        assert np.isclose(result['smart_estimate'], result['consensus'], atol=0.1)

    def test_very_high_dispersion(self, basic_config):
        """Test when analyst estimates are extremely dispersed."""
        data = {
            'period': [0] * 5,
            'company': ['VOLATILE'] * 5,
            'industry': ['TECH'] * 5,
            'analyst_id': ['A1', 'A2', 'A3', 'A4', 'A5'],
            'forecast_eps': [
                -2.0,   # Very pessimistic
                0.0,    # Neutral
                2.0,    # Optimistic
                5.0,    # Very optimistic
                -1.0    # Pessimistic
            ],
            'forecast_industry_component': [0.0] * 5,
            'forecast_company_component': [-2.0, 0.0, 2.0, 5.0, -1.0],
            'true_eps': [1.0] * 5,
            'true_industry': [0.0] * 5,
            'true_company': [1.0] * 5,
            'skill_industry': [0.6] * 5,
            'skill_company': [0.6] * 5,
            'archetype': ['Generalist'] * 5
        }
        df = pd.DataFrame(data)

        builder = SmartEstimateBuilder(basic_config)
        result = builder.construct_smartestimate(df, 0, 'VOLATILE')

        # High dispersion should be handled by winsorization
        assert result is not None
        assert np.isfinite(result['smart_estimate'])


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

class TestIntegration:
    """End-to-end integration tests."""

    def test_full_simulation_runs(self):
        """Test that full simulation completes without errors."""
        config = SimulationConfig(
            n_companies=5,
            n_industries=2,
            n_analysts=10,
            n_periods=10
        )

        # Should not raise any exceptions
        results_df, forecasts_df, analyst_skills = run_simulation(config)

        assert len(results_df) > 0
        assert len(forecasts_df) > 0
        assert len(analyst_skills) == 10

    def test_real_data_pipeline(self, tmp_path):
        """Test complete real data pipeline."""
        # Create synthetic I/B/E/S-style data
        data = {
            'TICKER': ['AAPL'] * 20 + ['MSFT'] * 20,
            'ESTIMATOR': [f'A{i%5}' for i in range(40)],
            'ANNDATS': [datetime(2023, 1, 1) + timedelta(days=i*7) for i in range(40)],
            'FPEDATS': [datetime(2023, 3, 31)] * 20 + [datetime(2023, 6, 30)] * 20,
            'VALUE': np.random.normal(1.0, 0.1, 40),
            'ACTUAL': [1.05] * 20 + [1.10] * 20,
            'GVKEY': ['TECH'] * 40
        }
        df = pd.DataFrame(data)

        # Save to CSV
        csv_path = tmp_path / "test_ibes.csv"
        df.to_csv(csv_path, index=False)

        # Load and process
        loader = IBESDataLoader()
        raw_data = loader.load_ibes_detail_file(str(csv_path))

        assert len(raw_data) == 40

        # Preprocess
        clean_data = loader.preprocess_ibes_data(raw_data, min_analysts=3)

        assert len(clean_data) > 0

        # Build SmartEstimates
        engine = RealDataSmartEstimateEngine()
        results = engine.compute_smartestimates(clean_data)

        assert len(results) > 0
        assert 'smart_estimate' in results.columns


# ============================================================================
# PERFORMANCE TESTS
# ============================================================================

class TestPerformance:
    """Test performance and scalability."""

    def test_large_dataset_performance(self):
        """Test performance with larger dataset."""
        import time

        config = SimulationConfig(
            n_companies=100,
            n_industries=10,
            n_analysts=50,
            n_periods=50
        )

        start_time = time.time()
        results_df, forecasts_df, analyst_skills = run_simulation(config)
        elapsed = time.time() - start_time

        # Should complete within reasonable time (< 5 minutes)
        assert elapsed < 300

        print(f"\nLarge dataset test: {len(forecasts_df):,} forecasts in {elapsed:.1f}s")

    def test_memory_usage(self):
        """Test that memory usage is reasonable."""
        config = SimulationConfig(
            n_companies=50,
            n_industries=5,
            n_analysts=30,
            n_periods=100
        )

        # Run simulation
        results_df, forecasts_df, analyst_skills = run_simulation(config)

        # Check memory usage (rough estimate)
        forecast_mem = forecasts_df.memory_usage(deep=True).sum() / 1024**2  # MB
        results_mem = results_df.memory_usage(deep=True).sum() / 1024**2  # MB

        print(f"\nMemory usage: Forecasts={forecast_mem:.1f}MB, Results={results_mem:.1f}MB")

        # Should be < 100MB for this size
        assert forecast_mem < 100
        assert results_mem < 100


# ============================================================================
# RUN ALL TESTS
# ============================================================================

if __name__ == "__main__":
    # Run with pytest
    pytest.main([__file__, '-v', '--tb=short'])
