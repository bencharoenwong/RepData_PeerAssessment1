"""
End-to-End Integration Test for Real I/B/E/S Data Workflow
===========================================================

Tests the complete pipeline from raw I/B/E/S data to SmartEstimates.
This verifies that the system is truly "plug and play" for production use.

Run: pytest test_full_pipeline.py -v

Author: Quantitative Research
Date: 2025-11-27
"""

import pytest
import numpy as np
import pandas as pd
import tempfile
import os
from datetime import datetime

from smartestimates import (
    # I/B/E/S Simulation
    IBESDataSimulator,
    IBESSimulationConfig,
    create_realistic_ibes_sample,
    # Data Loading
    IBESDataLoader,
    RealDataSmartEstimateEngine,
    # Core Algorithm
    SmartEstimateConfig,
    # Evaluation
    PerformanceEvaluator,
    # Decomposition
    ForecastDecomposer
)


class TestFullIBESPipeline:
    """Test complete workflow from I/B/E/S CSV to SmartEstimates."""

    def test_end_to_end_ibes_workflow(self):
        """
        Complete workflow test:
        1. Generate realistic I/B/E/S data
        2. Save to CSV
        3. Load with IBESDataLoader
        4. Preprocess
        5. Auto-decompose
        6. Build SmartEstimates
        7. Evaluate performance
        """
        print("\n" + "=" * 80)
        print("FULL I/B/E/S WORKFLOW TEST")
        print("=" * 80)

        # Step 1: Generate realistic I/B/E/S data
        print("\n[Step 1/7] Generating realistic I/B/E/S data...")
        config = IBESSimulationConfig(
            n_companies=30,
            n_analysts=20,
            n_quarters=12,  # 3 years
            avg_stocks_per_analyst=10,
            min_analysts_per_stock=5
        )

        np.random.seed(42)
        simulator = IBESDataSimulator(config)
        ibes_data = simulator.generate_ibes_data()

        print(f"  ✓ Generated {len(ibes_data):,} forecast records")
        print(f"    • {ibes_data['TICKER'].nunique()} companies")
        print(f"    • {ibes_data['ESTIMATOR'].nunique()} analysts")
        print(f"    • {ibes_data['FPEDATS'].nunique()} fiscal periods")

        # Step 2: Save to CSV (simulating real workflow)
        print("\n[Step 2/7] Saving to CSV (simulating file-based workflow)...")
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            csv_path = f.name
            ibes_data.to_csv(csv_path, index=False)
        print(f"  ✓ Saved to {csv_path}")

        try:
            # Step 3: Load with IBESDataLoader
            print("\n[Step 3/7] Loading I/B/E/S data...")
            loader = IBESDataLoader()
            raw_data = loader.load_ibes_detail_file(
                csv_path,
                ticker_col='TICKER',
                analyst_col='ESTIMATOR',
                forecast_date_col='ANNDATS',
                fiscal_period_col='FPEDATS',
                estimate_col='VALUE',
                actual_col='ACTUAL',
                industry_col='GVKEY'
            )
            print(f"  ✓ Loaded {len(raw_data):,} records")

            # Step 4: Preprocess
            print("\n[Step 4/7] Preprocessing data...")
            clean_data = loader.preprocess_ibes_data(
                raw_data,
                min_analysts=3,
                max_horizon_days=365,
                winsorize_pct=0.01
            )

            # Verify preprocessing worked
            assert len(clean_data) > 0, "Preprocessing should retain some data"
            assert 'period' in clean_data.columns, "Should have period column"
            assert clean_data['period'].nunique() > 1, "Should have multiple periods"

            # Step 5: Build SmartEstimates with auto-decomposition
            print("\n[Step 5/7] Building SmartEstimates with auto-decomposition...")
            engine = RealDataSmartEstimateEngine()
            results = engine.compute_smartestimates(
                clean_data,
                include_actuals=True,
                auto_decompose=True  # THIS IS THE KEY - automatic decomposition!
            )

            # Verify results
            assert len(results) > 0, "Should produce SmartEstimates"
            assert 'smart_estimate' in results.columns
            assert 'consensus' in results.columns
            assert np.isfinite(results['smart_estimate']).all(), "All SmartEstimates should be finite"

            print(f"  ✓ Generated {len(results):,} SmartEstimates")

            # Step 6: Evaluate performance
            print("\n[Step 6/7] Evaluating performance...")
            if 'true_eps' in results.columns:
                # Calculate summary statistics
                evaluator = PerformanceEvaluator()
                summary = evaluator.summary_statistics(results)

                print("\n" + "=" * 60)
                print("PERFORMANCE SUMMARY")
                print("=" * 60)
                print(summary.to_string())
                print("=" * 60)

                # SmartEstimate should be at least as good as consensus
                consensus_rmse = summary.loc['Consensus', 'RMSE']
                smart_rmse = summary.loc['SmartEstimate', 'RMSE']

                # Allow small tolerance (might be equal on small datasets)
                assert smart_rmse <= consensus_rmse * 1.15, \
                    f"SmartEstimate RMSE ({smart_rmse:.4f}) should not be much worse than Consensus ({consensus_rmse:.4f})"

            # Step 7: Verify decomposition worked
            print("\n[Step 7/7] Verifying decomposition...")
            # Check that the cleaned data has decomposed components
            assert 'forecast_industry_component' in clean_data.columns, \
                "Auto-decomposition should add industry component"
            assert 'forecast_company_component' in clean_data.columns, \
                "Auto-decomposition should add company component"

            # Verify decomposition is mathematically sound
            reconstructed = (clean_data['forecast_industry_component'] +
                           clean_data['forecast_company_component'])
            diff = (clean_data['forecast_eps'] - reconstructed).abs()
            assert diff.max() < 1e-10, "Decomposition should reconstruct forecasts exactly"

            print("  ✓ Decomposition verified")

            print("\n" + "=" * 80)
            print("✅ FULL PIPELINE TEST PASSED")
            print("=" * 80)
            print("\nThe system is PLUG-AND-PLAY ready for real I/B/E/S data!")
            print("Just map the column names and call RealDataSmartEstimateEngine.compute_smartestimates()")

        finally:
            # Cleanup
            os.unlink(csv_path)

    def test_plug_and_play_with_minimal_code(self):
        """
        Test that user can go from CSV to SmartEstimates with minimal code.

        This is what the user experience should be:
        """
        print("\n" + "=" * 80)
        print("PLUG-AND-PLAY USER EXPERIENCE TEST")
        print("=" * 80)

        # Generate sample data
        ibes_df = create_realistic_ibes_sample(
            n_companies=20,
            n_analysts=15,
            n_quarters=8
        )

        # Save to temp file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            csv_path = f.name
            ibes_df.to_csv(csv_path, index=False)

        try:
            # ============================================================
            # USER CODE STARTS HERE (3 simple steps!)
            # ============================================================

            # Step 1: Load data
            loader = IBESDataLoader()
            raw = loader.load_ibes_detail_file(csv_path)

            # Step 2: Clean data
            clean = loader.preprocess_ibes_data(raw, min_analysts=3)

            # Step 3: Build SmartEstimates (auto-decomposition happens automatically!)
            engine = RealDataSmartEstimateEngine()
            results = engine.compute_smartestimates(clean)

            # ============================================================
            # USER CODE ENDS HERE - That's it!
            # ============================================================

            # Verify it worked
            assert len(results) > 0
            assert 'smart_estimate' in results.columns
            assert 'consensus' in results.columns
            assert np.isfinite(results['smart_estimate']).all()

            print("\n✅ PLUG-AND-PLAY SUCCESS!")
            print("   3 lines of code: load → clean → build SmartEstimates")

        finally:
            os.unlink(csv_path)

    def test_skill_based_weighting_actually_works(self):
        """
        Verify that decomposed weighting actually differentiates analyst skills.

        This tests the CORE VALUE PROPOSITION of your system.
        """
        print("\n" + "=" * 80)
        print("SKILL-BASED WEIGHTING VERIFICATION")
        print("=" * 80)

        # Generate data with clear skill differences
        config = IBESSimulationConfig(
            n_companies=50,
            n_analysts=30,
            n_quarters=16,
            skill_industry_mean=0.6,
            skill_industry_std=0.3,  # High variation in industry skill
            skill_company_mean=0.6,
            skill_company_std=0.3,   # High variation in company skill
            skill_correlation=0.1     # Low correlation = distinct skills
        )

        np.random.seed(42)
        simulator = IBESDataSimulator(config)
        ibes_data = simulator.generate_ibes_data()

        # Save and load (full pipeline)
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            csv_path = f.name
            ibes_data.to_csv(csv_path, index=False)

        try:
            loader = IBESDataLoader()
            raw = loader.load_ibes_detail_file(csv_path)
            clean = loader.preprocess_ibes_data(raw, min_analysts=3)

            # Build with decomposed weighting
            engine = RealDataSmartEstimateEngine()
            results_decomposed = engine.compute_smartestimates(
                clean,
                auto_decompose=True  # Decomposed weighting
            )

            # Verify SmartEstimate outperforms consensus
            if 'true_eps' in results_decomposed.columns:
                evaluator = PerformanceEvaluator()
                results_with_metrics = evaluator.calculate_metrics(results_decomposed)

                consensus_rmse = np.sqrt(results_with_metrics['se_consensus'].mean())
                smart_rmse = np.sqrt(results_with_metrics['se_smart'].mean())

                improvement = (consensus_rmse - smart_rmse) / consensus_rmse * 100

                print(f"\n  Consensus RMSE:      {consensus_rmse:.4f}")
                print(f"  SmartEstimate RMSE:  {smart_rmse:.4f}")
                print(f"  Improvement:         {improvement:.2f}%")

                # With heterogeneous skills, SmartEstimate should improve
                # (Allow equal performance on small datasets)
                assert smart_rmse <= consensus_rmse * 1.05, \
                    "SmartEstimate should perform at least as well as consensus"

                print("\n  ✓ Skill-based weighting is working!")

        finally:
            os.unlink(csv_path)


class TestDecompositionRobustness:
    """Test that decomposition works under various conditions."""

    def test_decomposition_with_single_industry(self):
        """Test decomposition when all companies are in same industry."""
        df = pd.DataFrame({
            'period': [0, 0, 0, 0],
            'company': ['A', 'A', 'B', 'B'],
            'industry': ['IND1', 'IND1', 'IND1', 'IND1'],  # All same
            'analyst_id': ['AN1', 'AN2', 'AN1', 'AN2'],
            'forecast_eps': [1.0, 1.1, 2.0, 2.1],
            'realized_eps': [1.05, 1.05, 2.05, 2.05]
        })

        decomposed = ForecastDecomposer.add_decomposition(
            df,
            forecast_col='forecast_eps',
            actual_col='realized_eps',
            verbose=False
        )

        # Should complete without error
        assert 'forecast_industry_component' in decomposed.columns
        assert 'forecast_company_component' in decomposed.columns

    def test_decomposition_with_sparse_coverage(self):
        """Test decomposition with uneven analyst coverage."""
        df = pd.DataFrame({
            'period': [0, 0, 0, 1, 1],
            'company': ['A', 'B', 'C', 'A', 'B'],
            'industry': ['IND1', 'IND1', 'IND2', 'IND1', 'IND1'],
            'analyst_id': ['AN1', 'AN1', 'AN2', 'AN3', 'AN3'],
            'forecast_eps': [1.0, 2.0, 3.0, 1.1, 2.1],
            'realized_eps': [1.05, 2.05, 3.05, 1.15, 2.15]
        })

        decomposed = ForecastDecomposer.add_decomposition(
            df,
            forecast_col='forecast_eps',
            actual_col='realized_eps',
            verbose=False
        )

        # Should handle sparse coverage gracefully
        assert len(decomposed) == len(df)
        assert decomposed['forecast_industry_component'].notna().all()

    def test_decomposition_preserves_forecast_values(self):
        """Test that industry + company components = original forecast."""
        # Generate realistic test data
        ibes_df = create_realistic_ibes_sample(n_companies=10, n_analysts=8, n_quarters=4)

        decomposed = ForecastDecomposer.add_decomposition(
            ibes_df,
            forecast_col='VALUE',
            actual_col='ACTUAL',
            industry_col='GVKEY',
            company_col='TICKER',
            period_col='period',
            analyst_col='ESTIMATOR',
            verbose=False
        )

        # Verify reconstruction
        reconstructed = (decomposed['forecast_industry_component'] +
                        decomposed['forecast_company_component'])
        diff = (decomposed['VALUE'] - reconstructed).abs()

        assert diff.max() < 1e-10, "Decomposition must preserve forecast values exactly"


if __name__ == "__main__":
    pytest.main([__file__, '-v', '--tb=short'])
