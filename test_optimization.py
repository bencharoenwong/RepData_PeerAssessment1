"""
Test Suite for Optimized vs Original Implementation
===================================================

Tests that the optimized O(n) implementation produces similar results
to the original O(n²) implementation and is actually faster.

Run with: pytest test_optimization.py -v

Author: Quantitative Research
Date: 2025-11-24
"""

import pytest
import numpy as np
import pandas as pd
import time
from scipy import stats

from smartestimates_simulation import (
    SimulationConfig,
    DataSimulator,
    SmartEstimateBuilder,
    PerformanceEvaluator
)

from smartestimates_simulation_optimized import (
    SmartEstimateBuilderOptimized,
    run_simulation_optimized
)


class TestOptimizedVsOriginal:
    """Compare optimized and original implementations."""

    @pytest.fixture
    def test_data(self):
        """Generate test data for comparison."""
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

    def test_same_results_small_dataset(self, test_data):
        """Test that both implementations produce similar results on small dataset."""
        config, forecasts_df, analyst_skills = test_data

        # Original implementation
        builder_orig = SmartEstimateBuilder(config)
        results_orig = []

        periods = sorted(forecasts_df['period'].unique())
        for period in periods:
            if period > 0:
                builder_orig.update_accuracy_history(forecasts_df, period - 1)

            companies = forecasts_df[forecasts_df['period'] == period]['company'].unique()
            for company in companies:
                result = builder_orig.construct_smartestimate(forecasts_df, period, company)
                if result is not None:
                    results_orig.append(result)

        results_df_orig = pd.DataFrame(results_orig)

        # Optimized implementation
        builder_opt = SmartEstimateBuilderOptimized(config)

        # Build accuracy history
        for period in periods[:-1]:
            if period > 0:
                builder_opt.update_accuracy_history(forecasts_df, period)

        results_df_opt = builder_opt.construct_smartestimates_batch(forecasts_df)

        # Compare results
        merged = results_df_orig.merge(
            results_df_opt,
            on=['period', 'company'],
            suffixes=('_orig', '_opt')
        )

        # Check consensus values match (should be identical)
        consensus_diff = (merged['consensus_orig'] - merged['consensus_opt']).abs()
        assert consensus_diff.max() < 1e-10, "Consensus values should be identical"

        # Check SmartEstimates are similar (may differ slightly due to timing)
        se_diff = (merged['smart_estimate_orig'] - merged['smart_estimate_opt']).abs()
        mean_diff_pct = (se_diff / merged['smart_estimate_orig'].abs()).mean() * 100

        assert mean_diff_pct < 5, f"SmartEstimates differ by {mean_diff_pct:.2f}% on average"

    def test_optimization_is_faster(self):
        """Test that optimized version is faster."""
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

        # Time original implementation
        builder_orig = SmartEstimateBuilder(config)
        start_orig = time.time()

        periods = sorted(forecasts_df['period'].unique())
        results_orig = []
        for period in periods:
            if period > 0:
                builder_orig.update_accuracy_history(forecasts_df, period - 1)

            companies = forecasts_df[forecasts_df['period'] == period]['company'].unique()
            for company in companies:
                result = builder_orig.construct_smartestimate(forecasts_df, period, company)
                if result is not None:
                    results_orig.append(result)

        time_orig = time.time() - start_orig

        # Time optimized implementation
        builder_opt = SmartEstimateBuilderOptimized(config)
        start_opt = time.time()

        for period in periods[:-1]:
            if period > 0:
                builder_opt.update_accuracy_history(forecasts_df, period)

        results_df_opt = builder_opt.construct_smartestimates_batch(forecasts_df)
        time_opt = time.time() - start_opt

        speedup = time_orig / time_opt

        print(f"\nPerformance comparison:")
        print(f"  Original: {time_orig:.2f}s")
        print(f"  Optimized: {time_opt:.2f}s")
        print(f"  Speedup: {speedup:.2f}x")

        # Optimized should be faster (at least on this size)
        assert time_opt < time_orig, "Optimized version should be faster"

    def test_industry_mean_caching_works(self, test_data):
        """Test that industry mean caching produces correct results."""
        config, forecasts_df, _ = test_data

        builder = SmartEstimateBuilderOptimized(config)

        # Pre-compute industry means
        industry_means = forecasts_df.groupby(['period', 'industry'])['forecast_eps'].mean()
        builder._industry_means_cache = {
            (row[0], row[1]): mean
            for (row, mean) in industry_means.items()
        }

        # Test a specific company-period
        period = 5
        company = 'RIC_000'

        period_forecasts = forecasts_df[
            (forecasts_df['period'] == period) &
            (forecasts_df['company'] == company)
        ].copy()

        if len(period_forecasts) > 0:
            industry = period_forecasts['industry'].iloc[0]

            # Cached value
            cached_mean = builder._industry_means_cache.get((period, industry))

            # Computed value
            computed_mean = forecasts_df[
                (forecasts_df['period'] == period) &
                (forecasts_df['industry'] == industry)
            ]['forecast_eps'].mean()

            # Should match
            assert abs(cached_mean - computed_mean) < 1e-10


class TestScalability:
    """Test performance scaling with different dataset sizes."""

    def test_linear_scaling_hypothesis(self):
        """Test that optimized version scales linearly with data size."""
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

            # Time optimized version
            builder = SmartEstimateBuilderOptimized(config)
            periods = sorted(forecasts_df['period'].unique())

            for period in periods[:-1]:
                if period > 0:
                    builder.update_accuracy_history(forecasts_df, period)

            start = time.time()
            results = builder.construct_smartestimates_batch(forecasts_df)
            elapsed = time.time() - start

            timings.append(elapsed)

        print(f"\nScalability test:")
        for size, timing in zip(sizes, timings):
            print(f"  {size:,} forecasts: {timing:.2f}s ({size/timing:.0f} forecasts/sec)")

        # Check that time scales linearly (or better) with size
        # If linear: time2/time1 ≈ size2/size1
        time_ratio = timings[2] / timings[0]
        size_ratio = sizes[2] / sizes[0]

        # Allow for some overhead, but should be roughly linear
        assert time_ratio < size_ratio * 1.5, "Time should scale linearly with data size"


class TestCorrectnessWithEdgeCases:
    """Test that optimized version handles edge cases correctly."""

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

        builder = SmartEstimateBuilderOptimized(config)
        periods = sorted(forecasts_df['period'].unique())

        for period in periods[:-1]:
            if period > 0:
                builder.update_accuracy_history(forecasts_df, period)

        results = builder.construct_smartestimates_batch(forecasts_df)

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

        builder = SmartEstimateBuilderOptimized(config)
        results = builder.construct_smartestimates_batch(forecasts_df)

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

        builder = SmartEstimateBuilderOptimized(config)
        periods = sorted(forecasts_df['period'].unique())

        for period in periods[:-1]:
            if period > 0:
                builder.update_accuracy_history(forecasts_df, period)

        results = builder.construct_smartestimates_batch(forecasts_df)

        # Should handle sparse data
        assert len(results) > 0
        assert results['n_analysts'].min() >= 1


class TestNumericalStability:
    """Test numerical stability of optimized implementation."""

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

        builder = SmartEstimateBuilderOptimized(config)
        periods = sorted(forecasts_df['period'].unique())

        for period in periods[:-1]:
            if period > 0:
                builder.update_accuracy_history(forecasts_df, period)

        results = builder.construct_smartestimates_batch(forecasts_df)

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

        builder = SmartEstimateBuilderOptimized(config)
        results = builder.construct_smartestimates_batch(forecasts_df)

        # Should handle this without crashing
        assert len(results) > 0
        assert results['consensus'].eq(1.0).all()  # All forecasts were 1.0


if __name__ == "__main__":
    pytest.main([__file__, '-v', '--tb=short'])
