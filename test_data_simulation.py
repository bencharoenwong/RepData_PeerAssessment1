"""
Test Suite for Data Simulation Quality
======================================

Tests that the data simulator generates realistic analyst forecast data
with proper statistical properties.

Run with: pytest test_data_simulation.py -v

Author: Quantitative Research
Date: 2025-11-24
"""

import pytest
import numpy as np
import pandas as pd
from datetime import datetime
from scipy import stats

from smartestimates_simulation import (
    SimulationConfig,
    DataSimulator
)


class TestDataSimulatorQuality:
    """Test that simulated data has realistic properties."""

    @pytest.fixture
    def simulator(self):
        """Create simulator with known seed for reproducibility."""
        np.random.seed(42)
        config = SimulationConfig(
            n_companies=50,
            n_industries=5,
            n_analysts=30,
            n_periods=100
        )
        return DataSimulator(config)

    def test_company_industry_mapping_consistency(self, simulator):
        """Test that each company is consistently assigned to one industry."""
        mapping = simulator.company_to_industry

        # Each company should have exactly one industry
        assert len(mapping) == simulator.config.n_companies

        # All companies should exist
        for i in range(simulator.config.n_companies):
            company = f"RIC_{i:03d}"
            assert company in mapping

        # Industry distribution should be balanced
        industry_counts = pd.Series(list(mapping.values())).value_counts()
        # Each industry should have at least a few companies
        assert industry_counts.min() >= 5

    def test_analyst_skill_distribution(self, simulator):
        """Test that analyst skills follow expected distribution."""
        skills = simulator.analyst_skills

        # Should have correct number of analysts
        assert len(skills) == simulator.config.n_analysts

        # Skills should be in [0, 1] range
        assert skills['skill_industry'].min() >= 0
        assert skills['skill_industry'].max() <= 1
        assert skills['skill_company'].min() >= 0
        assert skills['skill_company'].max() <= 1

        # Skills should be roughly centered around mean
        assert 0.4 < skills['skill_industry'].mean() < 0.8
        assert 0.4 < skills['skill_company'].mean() < 0.8

        # Should have positive correlation (as configured)
        corr = skills[['skill_industry', 'skill_company']].corr().iloc[0, 1]
        assert 0.1 < corr < 0.5  # Configured as 0.3

    def test_analyst_archetypes_exist(self, simulator):
        """Test that all analyst archetypes are present."""
        skills = simulator.analyst_skills
        archetypes = skills['archetype'].unique()

        # Should have at least 3 of the 4 archetypes
        assert len(archetypes) >= 3

        # Valid archetypes
        valid_archetypes = ['Macro Specialist', 'Stock Picker', 'Generalist', 'Noise Trader']
        for archetype in archetypes:
            assert archetype in valid_archetypes

    def test_realized_values_factor_structure(self, simulator):
        """Test that realized EPS has proper factor structure."""
        realized_df = simulator.generate_realized_values()

        # Should have correct number of observations
        expected_obs = simulator.config.n_companies * simulator.config.n_periods
        assert len(realized_df) == expected_obs

        # Test industry component variance
        industry_var = realized_df.groupby('period')['industry_component'].std().mean()
        assert 0.05 < industry_var < 0.30  # Reasonable industry volatility

        # Test company-specific variance
        company_var = realized_df.groupby('period')['company_specific'].std().mean()
        assert 0.10 < company_var < 0.40  # Higher than industry

        # Industry component should be same for all companies in industry-period
        for period in range(5):  # Test a few periods
            for industry in realized_df['industry'].unique()[:3]:  # Test a few industries
                industry_period = realized_df[
                    (realized_df['period'] == period) &
                    (realized_df['industry'] == industry)
                ]
                if len(industry_period) > 1:
                    # All should have same industry component
                    assert industry_period['industry_component'].nunique() == 1

    def test_forecast_generation_coverage(self, simulator):
        """Test that forecasts have good analyst coverage."""
        realized_df = simulator.generate_realized_values()
        forecasts_df = simulator.generate_forecasts(realized_df)

        # Should have many forecasts
        assert len(forecasts_df) > 50000  # Reasonable number

        # Coverage per company-period
        coverage = forecasts_df.groupby(['period', 'company']).size()

        # Average coverage should be reasonable
        assert 10 < coverage.mean() < 30

        # Should not be completely uniform (some staleness)
        assert coverage.std() > 1

    def test_forecast_skill_based_accuracy(self, simulator):
        """Test that high-skill analysts produce more accurate forecasts."""
        realized_df = simulator.generate_realized_values()
        forecasts_df = simulator.generate_forecasts(realized_df)

        # Compute forecast errors
        forecasts_df['error'] = (forecasts_df['forecast_eps'] - forecasts_df['true_eps']).abs()

        # Group by skill level
        forecasts_df['skill_avg'] = (forecasts_df['skill_industry'] + forecasts_df['skill_company']) / 2
        forecasts_df['skill_group'] = pd.cut(forecasts_df['skill_avg'], bins=3, labels=['Low', 'Med', 'High'])

        # High skill analysts should have lower errors
        error_by_skill = forecasts_df.groupby('skill_group')['error'].mean()

        assert error_by_skill['Low'] > error_by_skill['Med']
        assert error_by_skill['Med'] > error_by_skill['High']

    def test_forecast_decomposition_consistency(self, simulator):
        """Test that forecast decomposition sums correctly."""
        realized_df = simulator.generate_realized_values()
        forecasts_df = simulator.generate_forecasts(realized_df)

        # Forecast should equal industry + company components
        reconstructed = (forecasts_df['forecast_industry_component'] +
                        forecasts_df['forecast_company_component'])

        # Should be very close (within numerical precision)
        diff = (forecasts_df['forecast_eps'] - reconstructed).abs()
        assert diff.max() < 0.10  # Tolerance for numerical errors + noise added in generation

    def test_dates_progression(self, simulator):
        """Test that dates progress correctly."""
        realized_df = simulator.generate_realized_values()

        # Forecast dates should progress
        dates = realized_df.groupby('period')['forecast_date'].first()
        assert dates.is_monotonic_increasing

        # Realization date should be after forecast date
        date_diff = (realized_df['realization_date'] - realized_df['forecast_date']).dt.days
        assert date_diff.min() > 0  # Always positive
        assert date_diff.mean() > 20  # Reasonable horizon

    def test_no_missing_values_in_core_data(self, simulator):
        """Test that core columns have no missing values."""
        realized_df = simulator.generate_realized_values()
        forecasts_df = simulator.generate_forecasts(realized_df)

        # Realized data should be complete
        core_cols_realized = ['period', 'company', 'industry', 'realized_eps']
        for col in core_cols_realized:
            assert realized_df[col].notna().all()

        # Forecast data should be complete
        core_cols_forecasts = ['period', 'company', 'analyst_id', 'forecast_eps']
        for col in core_cols_forecasts:
            assert forecasts_df[col].notna().all()


class TestDataSimulatorEdgeCases:
    """Test data simulator handles edge case configurations."""

    def test_minimal_configuration(self):
        """Test with minimal configuration."""
        config = SimulationConfig(
            n_companies=2,
            n_industries=1,
            n_analysts=3,
            n_periods=5
        )
        simulator = DataSimulator(config)

        realized_df = simulator.generate_realized_values()
        forecasts_df = simulator.generate_forecasts(realized_df)

        assert len(realized_df) == 10  # 2 companies × 5 periods
        assert len(forecasts_df) > 0  # At least some forecasts

    def test_single_industry(self):
        """Test with all companies in one industry."""
        config = SimulationConfig(
            n_companies=10,
            n_industries=1,
            n_analysts=5,
            n_periods=10
        )
        simulator = DataSimulator(config)

        # All companies should be in same industry
        industries = list(simulator.company_to_industry.values())
        assert len(set(industries)) == 1

    def test_many_industries(self):
        """Test with many industries (sparse coverage)."""
        config = SimulationConfig(
            n_companies=20,
            n_industries=20,  # One company per industry
            n_analysts=10,
            n_periods=10
        )
        simulator = DataSimulator(config)

        realized_df = simulator.generate_realized_values()
        forecasts_df = simulator.generate_forecasts(realized_df)

        # Should still work
        assert len(realized_df) > 0
        assert len(forecasts_df) > 0

    def test_high_staleness(self):
        """Test with high staleness (low update probability)."""
        config = SimulationConfig(
            n_companies=10,
            n_industries=2,
            n_analysts=10,
            n_periods=20,
            update_probability=0.3  # Only 30% update each period
        )
        simulator = DataSimulator(config)

        realized_df = simulator.generate_realized_values()
        forecasts_df = simulator.generate_forecasts(realized_df)

        # Should have fewer forecasts due to staleness
        avg_coverage = len(forecasts_df) / (config.n_companies * config.n_periods)
        assert avg_coverage < config.n_analysts * 0.5  # Much less than full coverage


class TestStatisticalProperties:
    """Test that simulated data has correct statistical properties."""

    def test_eps_normality(self):
        """Test that EPS changes are approximately normal."""
        config = SimulationConfig(n_companies=100, n_periods=50)
        simulator = DataSimulator(config)
        realized_df = simulator.generate_realized_values()

        # Test normality of realized EPS
        _, p_value = stats.normaltest(realized_df['realized_eps'])
        # p > 0.01 suggests data is consistent with normal distribution
        assert p_value > 0.01

    def test_forecast_error_distribution(self):
        """Test that forecast errors have expected properties."""
        np.random.seed(42)
        config = SimulationConfig(n_companies=50, n_analysts=30, n_periods=50)
        simulator = DataSimulator(config)

        realized_df = simulator.generate_realized_values()
        forecasts_df = simulator.generate_forecasts(realized_df)

        # Compute errors
        errors = forecasts_df['forecast_eps'] - forecasts_df['true_eps']

        # Errors should be roughly centered at zero
        assert abs(errors.mean()) < 0.05

        # Errors should have reasonable variance
        assert 0.05 < errors.std() < 0.30

    def test_cross_sectional_variation(self):
        """Test that cross-sectional variation is reasonable."""
        config = SimulationConfig(n_companies=50, n_periods=20)
        simulator = DataSimulator(config)
        realized_df = simulator.generate_realized_values()

        # Within each period, there should be variation across companies
        for period in range(5):  # Test a few periods
            period_data = realized_df[realized_df['period'] == period]

            # Should have variation
            assert period_data['realized_eps'].std() > 0.1

            # Should have reasonable range
            eps_range = period_data['realized_eps'].max() - period_data['realized_eps'].min()
            assert eps_range > 0.3

    def test_time_series_properties(self):
        """Test that time series have reasonable properties."""
        config = SimulationConfig(n_companies=10, n_periods=100)
        simulator = DataSimulator(config)
        realized_df = simulator.generate_realized_values()

        # Pick one company
        company_data = realized_df[realized_df['company'] == 'RIC_000'].sort_values('period')

        # EPS should not have strong autocorrelation (our model is iid)
        eps_series = company_data['realized_eps'].values
        autocorr = np.corrcoef(eps_series[:-1], eps_series[1:])[0, 1]
        assert abs(autocorr) < 0.3  # Low autocorrelation


class TestReproducibility:
    """Test that results are reproducible with same seed."""

    def test_same_seed_same_results(self):
        """Test that same seed produces identical results."""
        config = SimulationConfig(n_companies=10, n_analysts=5, n_periods=10)

        # Run 1
        np.random.seed(123)
        sim1 = DataSimulator(config)
        realized1 = sim1.generate_realized_values()
        forecasts1 = sim1.generate_forecasts(realized1)

        # Run 2 with same seed
        np.random.seed(123)
        sim2 = DataSimulator(config)
        realized2 = sim2.generate_realized_values()
        forecasts2 = sim2.generate_forecasts(realized2)

        # Results should be identical
        assert realized1['realized_eps'].equals(realized2['realized_eps'])
        assert forecasts1['forecast_eps'].equals(forecasts2['forecast_eps'])

    def test_different_seed_different_results(self):
        """Test that different seeds produce different results."""
        config = SimulationConfig(n_companies=10, n_analysts=5, n_periods=10)

        # Run 1
        np.random.seed(123)
        sim1 = DataSimulator(config)
        realized1 = sim1.generate_realized_values()

        # Run 2 with different seed
        np.random.seed(456)
        sim2 = DataSimulator(config)
        realized2 = sim2.generate_realized_values()

        # Results should be different
        assert not realized1['realized_eps'].equals(realized2['realized_eps'])


if __name__ == "__main__":
    pytest.main([__file__, '-v', '--tb=short'])
