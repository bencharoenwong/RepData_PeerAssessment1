"""
End-to-End Test: Plug-and-Play with Real I/B/E/S Data
======================================================

This demonstrates the complete workflow with realistic I/B/E/S data:
1. Generate realistic asynchronous I/B/E/S data
2. Load with IBESDataLoader
3. Preprocess
4. Auto-decompose (NEW!)
5. Compute SmartEstimates with skill-based weighting
6. Evaluate performance

Author: Quantitative Research
Date: 2025-11-27
"""

import numpy as np
import pandas as pd
from smartestimates import (
    create_realistic_ibes_sample,
    IBESDataLoader,
    RealDataSmartEstimateEngine,
    PerformanceEvaluator,
    ForecastDecomposer
)


def test_plug_and_play_workflow():
    """
    Test the complete plug-and-play workflow with realistic I/B/E/S data.

    This is what the user will actually do:
    1. Load their I/B/E/S CSV file
    2. Preprocess it
    3. Call compute_smartestimates() -> DONE!

    The decomposition happens automatically under the hood.
    """
    print("=" * 90)
    print("PLUG-AND-PLAY TEST: Realistic I/B/E/S Data → SmartEstimates")
    print("=" * 90)

    # Step 1: Generate realistic I/B/E/S data (in real usage, user downloads from Wharton/Bloomberg)
    print("\n[Step 1] Generating realistic I/B/E/S data...")
    ibes_data = create_realistic_ibes_sample(save_to_csv=False)

    # Remove the decomposed components (simulate raw I/B/E/S data user would receive)
    raw_ibes_cols = ['TICKER', 'ESTIMATOR', 'ANNDATS', 'FPEDATS', 'VALUE', 'ACTUAL', 'GVKEY']
    raw_ibes_data = ibes_data[raw_ibes_cols].copy()

    print(f"✓ Generated {len(raw_ibes_data):,} forecast records")
    print(f"  Format: {list(raw_ibes_data.columns)}")
    print("\nSample data:")
    print(raw_ibes_data.head(3))

    # Step 2: Load and preprocess (user's first step)
    print("\n" + "=" * 90)
    print("[Step 2] Loading and preprocessing I/B/E/S data...")
    print("=" * 90)

    # Save to CSV first (simulating real workflow)
    raw_ibes_data.to_csv('/tmp/test_ibes.csv', index=False)

    loader = IBESDataLoader()
    loaded_data = loader.load_ibes_detail_file('/tmp/test_ibes.csv')

    clean_data = loader.preprocess_ibes_data(
        loaded_data,
        min_analysts=3,
        max_horizon_days=180,
        winsorize_pct=0.01
    )

    # Step 3: Compute SmartEstimates with AUTO-DECOMPOSITION (user's second step)
    print("\n" + "=" * 90)
    print("[Step 3] Computing SmartEstimates with automatic decomposition...")
    print("=" * 90)

    engine = RealDataSmartEstimateEngine()
    results = engine.compute_smartestimates(
        clean_data,
        include_actuals=True,
        auto_decompose=True  # This is the key! Automatic decomposition enables skill-based weighting
    )

    # Step 4: Analyze results
    print("\n" + "=" * 90)
    print("[Step 4] Performance Analysis")
    print("=" * 90)

    print(f"\n✓ Generated {len(results):,} SmartEstimates")
    print(f"  • Companies: {results['company'].nunique()}")
    print(f"  • Periods: {results['period'].nunique()}")

    # Performance metrics
    evaluator = PerformanceEvaluator()
    summary = evaluator.summary_statistics(results)

    print("\nPerformance Summary:")
    print(summary)

    # Check that SmartEstimate actually outperforms consensus
    rmse_consensus = np.sqrt(results['se_consensus'].mean())
    rmse_smart = np.sqrt(results['se_smart'].mean())
    improvement_pct = (rmse_consensus - rmse_smart) / rmse_consensus * 100

    print(f"\n{'='*90}")
    print("KEY RESULT: Does Decomposed Weighting Work?")
    print(f"{'='*90}")
    print(f"Consensus RMSE:      {rmse_consensus:.4f}")
    print(f"SmartEstimate RMSE:  {rmse_smart:.4f}")
    print(f"Improvement:         {improvement_pct:.2f}%")

    if improvement_pct > 0:
        print(f"\n✓ SUCCESS: SmartEstimate outperforms consensus by {improvement_pct:.2f}%")
        print("  → Decomposed weighting is working!")
    else:
        print(f"\n⚠ WARNING: SmartEstimate underperforms consensus by {-improvement_pct:.2f}%")
        print("  → Check decomposition quality")

    # Diebold-Mariano test
    dm_result = evaluator.diebold_mariano_test(results)
    print(f"\nDiebold-Mariano Test:")
    print(f"  Statistic: {dm_result['statistic']:.4f}")
    print(f"  P-value:   {dm_result['p_value']:.4f}")
    print(f"  Result:    {dm_result['message']}")

    return results


def verify_decomposition_applied(results_df: pd.DataFrame):
    """
    Verify that decomposition was actually used (not just equal weights).

    If decomposition wasn't applied, all analysts would get equal weights
    and SmartEstimate ≈ Consensus.
    """
    print("\n" + "=" * 90)
    print("VERIFICATION: Was Decomposition Actually Used?")
    print("=" * 90)

    # If decomposition wasn't used, SmartEstimate should be very close to Consensus
    diff = (results_df['smart_estimate'] - results_df['consensus']).abs()
    mean_diff = diff.mean()
    max_diff = diff.max()

    print(f"Mean |SmartEstimate - Consensus|: {mean_diff:.4f}")
    print(f"Max |SmartEstimate - Consensus|:  {max_diff:.4f}")

    if mean_diff < 0.001 and max_diff < 0.01:
        print("\n⚠ WARNING: SmartEstimate ≈ Consensus")
        print("  → Decomposition may not be working (all analysts have equal weights)")
        return False
    else:
        print("\n✓ CONFIRMED: SmartEstimate ≠ Consensus")
        print("  → Decomposed weighting is active (analysts have different weights)")
        return True


def demonstrate_manual_decomposition():
    """
    Demonstrate manual decomposition for advanced users who want control.
    """
    print("\n" + "=" * 90)
    print("ADVANCED: Manual Decomposition Control")
    print("=" * 90)

    # Generate test data
    test_data = pd.DataFrame({
        'period': [0] * 6,
        'company': ['A', 'A', 'A', 'B', 'B', 'B'],
        'industry': ['Tech'] * 6,
        'analyst_id': ['AN1', 'AN2', 'AN3', 'AN1', 'AN2', 'AN3'],
        'forecast_eps': [1.0, 1.2, 0.9, 1.1, 1.3, 1.0],
        'realized_eps': [1.05] * 3 + [1.15] * 3
    })

    print("\nBefore decomposition:")
    print(test_data)

    # Apply manual decomposition
    decomposed = ForecastDecomposer.add_decomposition(
        test_data,
        verbose=True
    )

    print("\nAfter decomposition:")
    print(decomposed[['company', 'analyst_id', 'forecast_eps',
                     'forecast_industry_component', 'forecast_company_component']])

    print("\nInterpretation:")
    print("- forecast_industry_component: Industry consensus (same for all analysts in same industry)")
    print("- forecast_company_component: Analyst's company-specific view (deviation from sector)")


if __name__ == "__main__":
    np.random.seed(42)

    # Main test
    print("\n\n")
    print("█" * 90)
    print("█" + " " * 88 + "█")
    print("█" + "  PLUG-AND-PLAY TEST: Feed Real I/B/E/S Data → Get SmartEstimates".center(88) + "█")
    print("█" + " " * 88 + "█")
    print("█" * 90)

    results = test_plug_and_play_workflow()
    verify_decomposition_applied(results)

    # Advanced demo
    demonstrate_manual_decomposition()

    print("\n\n" + "=" * 90)
    print("✓ PLUG-AND-PLAY TEST COMPLETE")
    print("=" * 90)
    print("\nNext steps:")
    print("1. Replace test data with your actual I/B/E/S download")
    print("2. Run: engine.compute_smartestimates(your_data, auto_decompose=True)")
    print("3. That's it! Decomposition happens automatically.")
