"""
Test Suite for SmartEstimates Performance
==========================================

Tests that the SmartEstimates implementation is efficient and produces
correct results with proper temporal consistency.

Run with: pytest test_optimization.py -v

Author: Quantitative Research
Date: 2025-11-25
"""

import pytest
import numpy as np
import pandas as pd
import time
from scipy import stats

from smartestimates import (
    SimulationConfig,
    DataSimulator,
    SmartEstimateBuilder,
    PerformanceEvaluator
)


class TestPerformance:
    """Test SmartEstimates performance and correctness."""

    @pytest.fixture
    def test_data(self):
        """Generate test data for performance testing."""
        np.random.seed(42)
        config = SimulationConfig(
            n_companies=10,
            n_industries=2,
            n_analysts=10,
            n_periods=20
        )

        simulator = DataSimulator(config)
        realized_df = simulator.generate_realized_values()
        forecasts_df = simulator.generate_forecasts(realized_df)

        return config, forecasts_df, simulator.analyst_skills

    def test_sequential_processing_works(self, test_data):
        """Test that sequential processing produces valid results."""
        config, forecasts_df, _ = test_data

        builder = SmartEstimateBuilder(config)
        results_df = builder.construct_smartestimates_sequential(forecasts_df, verbose=False)

        # Verify we got results
        assert len(results_df) > 0

        # Verify essential columns exist
        expected_cols = ['period', 'company', 'consensus', 'smart_estimate', 'n_analysts', 'true_eps']
        for col in expected_cols:
            assert col in results_df.columns

        # Verify no NaN in key columns
        assert results_df['consensus'].notna().all()
        assert results_df['smart_estimate'].notna().all()

        # Verify SmartEstimate is finite
        assert np.isfinite(results_df['smart_estimate']).all()

    def test_smartestimate_improves_over_consensus(self, test_data):
        """Test that SmartEstimate generally outperforms consensus."""
        config, forecasts_df, _ = test_data

        builder = SmartEstimateBuilder(config)
        results_df = builder.construct_smartestimates_sequential(forecasts_df, verbose=False)

        # Calculate errors
        evaluator = PerformanceEvaluator()
        results_df = evaluator.calculate_metrics(results_df)

        # SmartEstimate RMSE should be <= consensus (with small tolerance)
        consensus_rmse = np.sqrt(results_df['se_consensus'].mean())
        smart_rmse = np.sqrt(results_df['se_smart'].mean())

        # Allow 10% tolerance (SmartEstimate might be slightly worse on tiny datasets)
        assert smart_rmse <= consensus_rmse * 1.1

    def test_performance_is_reasonable(self):
        """Test that processing performance is reasonable for medium dataset."""
        config = SimulationConfig(
            n_companies=20,
            n_industries=3,
            n_analysts=15,
            n_periods=30
        )

        np.random.seed(42)
        simulator = DataSimulator(config)
        realized_df = simulator.generate_realized_values()
        forecasts_df = simulator.generate_forecasts(realized_df)

        # Time the sequential processing
        builder = SmartEstimateBuilder(config)
        start = time.time()
        results_df = builder.construct_smartestimates_sequential(forecasts_df, verbose=False)
        elapsed = time.time() - start

        forecasts_per_sec = len(forecasts_df) / elapsed

        print(f"\nPerformance: {len(forecasts_df):,} forecasts in {elapsed:.2f}s ({forecasts_per_sec:.0f} forecasts/sec)")

        # Should process at least 500 forecasts per second (very conservative)
        assert forecasts_per_sec > 500, f"Too slow: {forecasts_per_sec:.0f} forecasts/sec"

        # Verify we got results
        assert len(results_df) > 0


class TestScalability:
    """Test performance scaling with different dataset sizes."""

    def test_linear_scaling_hypothesis(self):
        """Test that processing time scales reasonably with data size."""
        config_base = SimulationConfig(
            n_companies=10,
            n_industries=2,
            n_analysts=10,
            n_periods=10
        )

        timings = []
        sizes = []

        for multiplier in [1, 2, 4]:
            config = SimulationConfig(
                n_companies=config_base.n_companies * multiplier,
                n_industries=config_base.n_industries,
                n_analysts=config_base.n_analysts * multiplier,
                n_periods=config_base.n_periods * multiplier
            )

            np.random.seed(42)
            simulator = DataSimulator(config)
            realized_df = simulator.generate_realized_values()
            forecasts_df = simulator.generate_forecasts(realized_df)

            sizes.append(len(forecasts_df))

            # Time sequential processing
            builder = SmartEstimateBuilder(config)
            start = time.time()
            results = builder.construct_smartestimates_sequential(forecasts_df, verbose=False)
            elapsed = time.time() - start

            timings.append(elapsed)

        print(f"\nScalability test:")
        for size, timing in zip(sizes, timings):
            print(f"  {size:,} forecasts: {timing:.2f}s ({size/timing:.0f} forecasts/sec)")

        # Check that time scales reasonably with size
        # Allow for some overhead, but should be roughly linear (or better)
        time_ratio = timings[2] / timings[0]
        size_ratio = sizes[2] / sizes[0]

        # Time should not scale quadratically (would be size_ratio^2)
        # Allow up to 2x linear scaling due to overhead
        assert time_ratio < size_ratio * 2.0, f"Scaling too slow: time ratio {time_ratio:.1f}x vs size ratio {size_ratio:.1f}x"


class TestCorrectnessWithEdgeCases:
    """Test that implementation handles edge cases correctly."""

    def test_single_company(self):
        """Test with single company."""
        config = SimulationConfig(
            n_companies=1,
            n_industries=1,
            n_analysts=5,
            n_periods=10
        )

        np.random.seed(42)
        simulator = DataSimulator(config)
        realized_df = simulator.generate_realized_values()
        forecasts_df = simulator.generate_forecasts(realized_df)

        builder = SmartEstimateBuilder(config)
        results = builder.construct_smartestimates_sequential(forecasts_df, verbose=False)

        assert len(results) > 0
        assert results['company'].nunique() == 1

    def test_single_period(self):
        """Test with single period."""
        config = SimulationConfig(
            n_companies=10,
            n_industries=2,
            n_analysts=10,
            n_periods=1
        )

        np.random.seed(42)
        simulator = DataSimulator(config)
        realized_df = simulator.generate_realized_values()
        forecasts_df = simulator.generate_forecasts(realized_df)

        builder = SmartEstimateBuilder(config)
        results = builder.construct_smartestimates_sequential(forecasts_df, verbose=False)

        assert len(results) > 0
        assert results['period'].nunique() == 1

    def test_sparse_coverage(self):
        """Test with sparse analyst coverage."""
        config = SimulationConfig(
            n_companies=50,
            n_industries=5,
            n_analysts=10,  # Few analysts for many companies
            n_periods=20,
            update_probability=0.5  # Sparse updates
        )

        np.random.seed(42)
        simulator = DataSimulator(config)
        realized_df = simulator.generate_realized_values()
        forecasts_df = simulator.generate_forecasts(realized_df)

        builder = SmartEstimateBuilder(config)
        results = builder.construct_smartestimates_sequential(forecasts_df, verbose=False)

        # Should handle sparse data
        assert len(results) > 0
        assert results['n_analysts'].min() >= 1


class TestNumericalStability:
    """Test numerical stability of implementation."""

    def test_extreme_values(self):
        """Test with extreme forecast values."""
        config = SimulationConfig(
            n_companies=5,
            n_industries=1,
            n_analysts=5,
            n_periods=10,
            industry_volatility=1.0,  # High volatility
            company_volatility=2.0
        )

        np.random.seed(42)
        simulator = DataSimulator(config)
        realized_df = simulator.generate_realized_values()
        forecasts_df = simulator.generate_forecasts(realized_df)

        builder = SmartEstimateBuilder(config)
        results = builder.construct_smartestimates_sequential(forecasts_df, verbose=False)

        # All results should be finite
        assert results['smart_estimate'].notna().all()
        assert np.isfinite(results['smart_estimate']).all()

    def test_zero_variance_case(self):
        """Test case where all forecasts are identical."""
        # Create artificial data where all forecasts are same
        data = []
        for period in range(5):
            for company in ['A', 'B']:
                for analyst in range(3):
                    data.append({
                        'period': period,
                        'company': company,
                        'industry': 'IND1',
                        'analyst_id': f'AN{analyst}',
                        'forecast_eps': 1.0,  # All same
                        'forecast_industry_component': 1.0,
                        'forecast_company_component': 0.0,
                        'true_eps': 1.0,
                        'true_industry': 1.0,
                        'true_company': 0.0,
                        'skill_industry': 0.5,
                        'skill_company': 0.5,
                        'archetype': 'Generalist'
                    })

        forecasts_df = pd.DataFrame(data)
        config = SimulationConfig()

        builder = SmartEstimateBuilder(config)
        results = builder.construct_smartestimates_sequential(forecasts_df, verbose=False)

        # Should handle this without crashing
        assert len(results) > 0
        # When all forecasts are 1.0, consensus should be 1.0
        assert results['consensus'].eq(1.0).all()


if __name__ == "__main__":
    pytest.main([__file__, '-v', '--tb=short'])
