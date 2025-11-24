"""
Integration Test Suite
======================

End-to-end integration tests for SmartEstimates pipeline.
Tests complete workflows with realistic scenarios.

Run with: pytest test_integration.py -v --tb=short

Author: Quantitative Research
Date: 2025-11-24
"""

import pytest
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import tempfile
import os

from smartestimates_simulation import (
    SimulationConfig,
    DataSimulator,
    SmartEstimateBuilder,
    PerformanceEvaluator,
    run_simulation
)

from smartestimates_real_data import (
    IBESDataLoader,
    RealDataSmartEstimateEngine
)


class TestFullSimulationPipeline:
    """Test complete simulation from data generation to evaluation."""

    def test_end_to_end_simulation_runs(self):
        """Test that full simulation runs without errors."""
        config = SimulationConfig(
            n_companies=10,
            n_industries=2,
            n_analysts=10,
            n_periods=20
        )

        # Run complete simulation
        results_df, forecasts_df, analyst_skills = run_simulation(config)

        # Verify outputs
        assert len(results_df) > 0
        assert len(forecasts_df) > 0
        assert len(analyst_skills) == config.n_analysts

        # Check results have expected columns
        expected_cols = ['period', 'company', 'consensus', 'smart_estimate',
                        'n_analysts', 'true_eps']
        for col in expected_cols:
            assert col in results_df.columns

        # Check forecasts have expected columns
        forecast_cols = ['period', 'company', 'analyst_id', 'forecast_eps']
        for col in forecast_cols:
            assert col in forecasts_df.columns

    def test_smartestimate_performance_improvement(self):
        """Test that SmartEstimate generally improves over consensus."""
        config = SimulationConfig(
            n_companies=30,
            n_industries=3,
            n_analysts=20,
            n_periods=50
        )

        results_df, forecasts_df, analyst_skills = run_simulation(config)

        # Calculate performance metrics
        evaluator = PerformanceEvaluator()
        results_df = evaluator.calculate_metrics(results_df)
        summary = evaluator.summary_statistics(results_df)

        # SmartEstimate RMSE should be better than or equal to consensus
        consensus_rmse = summary.loc['Consensus', 'RMSE']
        smart_rmse = summary.loc['SmartEstimate', 'RMSE']

        assert smart_rmse <= consensus_rmse * 1.05  # Allow 5% tolerance

        # Information coefficient should be positive
        assert summary.loc['Consensus', 'Information_Coefficient'] > 0.5
        assert summary.loc['SmartEstimate', 'Information_Coefficient'] > 0.5

    def test_archetype_influence(self):
        """Test that analyst archetypes influence results as expected."""
        # Create config with strong skill differences
        config = SimulationConfig(
            n_companies=20,
            n_industries=2,
            n_analysts=30,
            n_periods=40,
            skill_industry_mean=0.7,
            skill_industry_std=0.3,
            skill_company_mean=0.7,
            skill_company_std=0.3,
            skill_correlation=0.1  # Low correlation for distinct archetypes
        )

        np.random.seed(42)
        results_df, forecasts_df, analyst_skills = run_simulation(config)

        # Compute forecast accuracy by archetype
        forecasts_df['error'] = (forecasts_df['forecast_eps'] - forecasts_df['true_eps']).abs()
        archetype_performance = forecasts_df.groupby('archetype')['error'].mean()

        # Generalists should be among the best
        if 'Generalist' in archetype_performance.index:
            generalist_rank = archetype_performance.rank().loc['Generalist']
            assert generalist_rank <= 2  # Should be top 2

        # Noise Traders should be worst
        if 'Noise Trader' in archetype_performance.index:
            noise_rank = archetype_performance.rank(ascending=False).loc['Noise Trader']
            assert noise_rank <= 2  # Should be bottom 2


class TestRealDataPipeline:
    """Test pipeline with simulated I/B/E/S-style data."""

    @pytest.fixture
    def ibes_style_data(self):
        """Generate I/B/E/S-style test data."""
        np.random.seed(42)

        data = []
        companies = ['AAPL', 'MSFT', 'GOOG', 'AMZN', 'META']
        analysts = [f'A{i:04d}' for i in range(20)]

        base_date = datetime(2023, 1, 1)

        for quarter in range(4):
            realization_date = base_date + timedelta(days=quarter * 90)

            for company in companies:
                true_eps = np.random.normal(1.0, 0.2)

                for analyst in np.random.choice(analysts, size=np.random.randint(8, 15)):
                    forecast_date = realization_date - timedelta(days=np.random.randint(15, 60))
                    forecast = true_eps + np.random.normal(0, 0.1)

                    data.append({
                        'TICKER': company,
                        'ESTIMATOR': analyst,
                        'ANNDATS': forecast_date.strftime('%Y-%m-%d'),
                        'FPEDATS': realization_date.strftime('%Y-%m-%d'),
                        'VALUE': forecast,
                        'ACTUAL': true_eps,
                        'GVKEY': 'TECH'
                    })

        return pd.DataFrame(data)

    def test_ibes_loader_with_simulated_data(self, ibes_style_data, tmp_path):
        """Test loading and preprocessing I/B/E/S-style data."""
        # Save to temporary CSV
        csv_path = tmp_path / "test_ibes.csv"
        ibes_style_data.to_csv(csv_path, index=False)

        # Load data
        loader = IBESDataLoader()
        raw_data = loader.load_ibes_detail_file(str(csv_path))

        assert len(raw_data) == len(ibes_style_data)
        assert 'company' in raw_data.columns
        assert 'analyst_id' in raw_data.columns

        # Preprocess
        clean_data = loader.preprocess_ibes_data(
            raw_data,
            min_analysts=3,
            max_horizon_days=365
        )

        assert len(clean_data) > 0
        assert 'period' in clean_data.columns

    def test_real_data_engine_with_simulated_data(self, ibes_style_data, tmp_path):
        """Test SmartEstimate construction on I/B/E/S-style data."""
        # Save to CSV
        csv_path = tmp_path / "test_ibes.csv"
        ibes_style_data.to_csv(csv_path, index=False)

        # Load and preprocess
        loader = IBESDataLoader()
        raw_data = loader.load_ibes_detail_file(str(csv_path))
        clean_data = loader.preprocess_ibes_data(raw_data, min_analysts=3)

        # Build SmartEstimates
        config = SimulationConfig(recency_halflife=30, min_history=2)
        engine = RealDataSmartEstimateEngine(config)

        results = engine.compute_smartestimates(clean_data, include_actuals=True)

        # Verify results
        assert len(results) > 0
        assert 'smart_estimate' in results.columns
        assert 'consensus' in results.columns

        # SmartEstimates should exist
        assert results['smart_estimate'].notna().sum() > 0


class TestErrorHandling:
    """Test error handling in various pipeline stages."""

    def test_empty_forecast_dataframe(self):
        """Test handling of empty input."""
        config = SimulationConfig()
        builder = SmartEstimateBuilder(config)

        empty_df = pd.DataFrame()
        result = builder.construct_smartestimate(empty_df, 0, 'AAPL')

        assert result is None

    def test_missing_columns_in_ibes_data(self, tmp_path):
        """Test error handling when required columns are missing."""
        # Create data missing required columns
        bad_data = pd.DataFrame({
            'TICKER': ['AAPL', 'MSFT'],
            'VALUE': [1.0, 1.1]
            # Missing: ESTIMATOR, ANNDATS, etc.
        })

        csv_path = tmp_path / "bad_data.csv"
        bad_data.to_csv(csv_path, index=False)

        loader = IBESDataLoader()

        with pytest.raises(ValueError, match="Missing required columns"):
            loader.load_ibes_detail_file(str(csv_path))

    def test_invalid_dates_in_data(self):
        """Test handling of invalid dates."""
        data = pd.DataFrame({
            'company': ['AAPL'] * 5,
            'analyst_id': ['A1'] * 5,
            'forecast_date': [datetime(2023, 1, 1)] * 5,
            'realization_date': [datetime(2022, 12, 31)] * 5,  # Before forecast!
            'forecast_eps': [1.0] * 5,
            'realized_eps': [1.05] * 5,
            'industry': ['TECH'] * 5
        })

        loader = IBESDataLoader()

        # Should filter out invalid dates during preprocessing
        clean = loader.preprocess_ibes_data(data, min_analysts=1, max_horizon_days=365)

        # Invalid dates should be removed (negative horizon)
        assert len(clean) == 0


class TestRealisticScenarios:
    """Test realistic market scenarios."""

    def test_market_downturn_scenario(self):
        """Test behavior during market downturn."""
        config = SimulationConfig(
            n_companies=20,
            n_industries=3,
            n_analysts=15,
            n_periods=50,
            industry_volatility=0.30,  # High volatility
            company_volatility=0.40
        )

        np.random.seed(42)
        simulator = DataSimulator(config)
        realized_df = simulator.generate_realized_values()

        # Simulate market crash in periods 20-30
        realized_df.loc[
            (realized_df['period'] >= 20) & (realized_df['period'] <= 30),
            'realized_eps'
        ] *= 0.5  # 50% drop

        # Generate forecasts (analysts don't predict the crash perfectly)
        forecasts_df = simulator.generate_forecasts(realized_df)

        # Build SmartEstimates
        builder = SmartEstimateBuilder(config)
        results = []

        periods = sorted(forecasts_df['period'].unique())
        for period in periods:
            if period > 0:
                builder.update_accuracy_history(forecasts_df, period - 1)

            companies = forecasts_df[forecasts_df['period'] == period]['company'].unique()
            for company in companies:
                result = builder.construct_smartestimate(forecasts_df, period, company)
                if result is not None:
                    results.append(result)

        results_df = pd.DataFrame(results)

        # Even in crisis, system should produce results
        assert len(results_df) > 0

        # Errors will be larger during crash period
        crash_errors = results_df[
            (results_df['period'] >= 20) & (results_df['period'] <= 30)
        ]['error_consensus'].abs().mean()

        normal_errors = results_df[
            results_df['period'] < 20
        ]['error_consensus'].abs().mean()

        assert crash_errors > normal_errors  # Larger errors during crisis

    def test_ipo_introduction(self):
        """Test introducing new company mid-stream (like IPO)."""
        config = SimulationConfig(
            n_companies=10,
            n_industries=2,
            n_analysts=10,
            n_periods=30
        )

        np.random.seed(42)
        simulator = DataSimulator(config)
        realized_df = simulator.generate_realized_values()
        forecasts_df = simulator.generate_forecasts(realized_df)

        # Add new "IPO" company starting at period 15
        ipo_company = 'IPO_NEW'
        ipo_start_period = 15

        ipo_data = []
        for period in range(ipo_start_period, config.n_periods):
            # Add to realized data
            industry = 'IND_0'
            realized_eps = np.random.normal(0.5, 0.1)

            # Add forecasts from some analysts
            for analyst in forecasts_df['analyst_id'].unique()[:5]:
                ipo_data.append({
                    'period': period,
                    'company': ipo_company,
                    'industry': industry,
                    'analyst_id': analyst,
                    'forecast_eps': realized_eps + np.random.normal(0, 0.05),
                    'forecast_industry_component': 0.5,
                    'forecast_company_component': realized_eps - 0.5,
                    'forecast_date': datetime(2023, 1, 1) + timedelta(days=period*7),
                    'realization_date': datetime(2023, 1, 1) + timedelta(days=period*7+30),
                    'true_eps': realized_eps,
                    'true_industry': 0.5,
                    'true_company': realized_eps - 0.5,
                    'skill_industry': 0.6,
                    'skill_company': 0.6,
                    'archetype': 'Generalist'
                })

        ipo_df = pd.DataFrame(ipo_data)
        forecasts_df = pd.concat([forecasts_df, ipo_df], ignore_index=True)

        # Build SmartEstimates
        builder = SmartEstimateBuilder(config)
        results = []

        periods = sorted(forecasts_df['period'].unique())
        for period in periods:
            if period > 0:
                builder.update_accuracy_history(forecasts_df, period - 1)

            companies = forecasts_df[forecasts_df['period'] == period]['company'].unique()
            for company in companies:
                result = builder.construct_smartestimate(forecasts_df, period, company)
                if result is not None:
                    results.append(result)

        results_df = pd.DataFrame(results)

        # Check that IPO company appears in results
        ipo_results = results_df[results_df['company'] == ipo_company]
        assert len(ipo_results) > 0
        assert ipo_results['period'].min() >= ipo_start_period


class TestDataQualityIssues:
    """Test handling of real-world data quality issues."""

    def test_duplicate_forecasts(self):
        """Test handling of duplicate analyst forecasts."""
        # Create data with duplicates
        data = []
        for i in range(10):
            data.append({
                'company': 'AAPL',
                'analyst_id': 'A1',
                'forecast_date': datetime(2023, 1, 1),
                'realization_date': datetime(2023, 3, 31),
                'forecast_eps': 1.0 if i < 5 else 1.1,  # Duplicate with revision
                'realized_eps': 1.05,
                'industry': 'TECH'
            })

        df = pd.DataFrame(data)

        loader = IBESDataLoader()
        clean = loader.preprocess_ibes_data(df, min_analysts=1)

        # Should keep only one forecast per analyst-company-period
        # (the most recent one)
        assert len(clean) == 1
        assert clean['forecast_eps'].iloc[0] == 1.1  # Latest revision

    def test_outlier_removal(self):
        """Test that extreme outliers are removed."""
        data = []
        base_eps = 1.0

        for i in range(20):
            if i == 10:
                forecast = 1000.0  # Extreme outlier
            else:
                forecast = base_eps + np.random.normal(0, 0.05)

            data.append({
                'company': 'AAPL',
                'analyst_id': f'A{i}',
                'forecast_date': datetime(2023, 1, 1),
                'realization_date': datetime(2023, 3, 31),
                'forecast_eps': forecast,
                'realized_eps': base_eps,
                'industry': 'TECH'
            })

        df = pd.DataFrame(data)

        loader = IBESDataLoader()
        clean = loader.preprocess_ibes_data(df, min_analysts=5, winsorize_pct=0.01)

        # Extreme outlier should be removed
        assert clean['forecast_eps'].max() < 100  # Much less than 1000


if __name__ == "__main__":
    pytest.main([__file__, '-v', '--tb=short'])
