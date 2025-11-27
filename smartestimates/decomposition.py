"""
Forecast Decomposition for Real I/B/E/S Data
=============================================

Automatically decomposes raw analyst forecasts into:
- Industry component (sector-level consensus)
- Company-specific component (deviation from sector)

This enables decomposed weighting even when the raw data doesn't
include pre-computed components.

Author: Quantitative Research
Date: 2025-11-27
"""

import numpy as np
import pandas as pd
from typing import Dict, Tuple
import warnings


class ForecastDecomposer:
    """
    Decomposes analyst forecasts into industry and company components.

    Theory:
    -------
    Forecast_ij = Industry_Mean_j + Company_Deviation_ij

    Where:
    - Forecast_ij: Analyst i's forecast for company j
    - Industry_Mean_j: Cross-sectional mean of all forecasts for companies in j's industry
    - Company_Deviation_ij: Analyst i's company-specific view (deviation from sector)

    This decomposition allows separate weighting of:
    1. Industry forecasting skill (macro/sector calls)
    2. Company forecasting skill (stock-picking ability)
    """

    @staticmethod
    def decompose_forecasts(forecasts_df: pd.DataFrame,
                           forecast_col: str = 'forecast_eps',
                           industry_col: str = 'industry',
                           company_col: str = 'company',
                           period_col: str = 'period',
                           analyst_col: str = 'analyst_id') -> pd.DataFrame:
        """
        Decompose forecasts into industry and company components.

        Args:
            forecasts_df: DataFrame with analyst forecasts
            forecast_col: Column name for EPS forecast
            industry_col: Column name for industry identifier
            company_col: Column name for company identifier
            period_col: Column name for time period
            analyst_col: Column name for analyst identifier

        Returns:
            DataFrame with added columns:
            - forecast_industry_component: Industry-level forecast
            - forecast_company_component: Company-specific deviation
        """
        df = forecasts_df.copy()

        # Compute industry mean for each (period, industry)
        # This represents the "industry consensus" across all forecasts
        industry_means = df.groupby([period_col, industry_col])[forecast_col].transform('mean')

        df['forecast_industry_component'] = industry_means
        df['forecast_company_component'] = df[forecast_col] - industry_means

        return df

    @staticmethod
    def decompose_actuals(forecasts_df: pd.DataFrame,
                         actual_col: str = 'realized_eps',
                         industry_col: str = 'industry',
                         company_col: str = 'company',
                         period_col: str = 'period') -> pd.DataFrame:
        """
        Decompose realized earnings into industry and company components.

        This is needed for accuracy tracking - we need to know the "true"
        industry component to measure analyst industry forecasting skill.

        Args:
            forecasts_df: DataFrame with realized earnings
            actual_col: Column name for actual EPS
            industry_col: Column name for industry identifier
            company_col: Column name for company identifier
            period_col: Column name for time period

        Returns:
            DataFrame with added columns:
            - true_industry: Industry-level realized earnings
            - true_company: Company-specific realized earnings
        """
        df = forecasts_df.copy()

        # Check if we have actuals
        if actual_col not in df.columns:
            warnings.warn(f"Column '{actual_col}' not found. Cannot decompose actuals.")
            df['true_industry'] = np.nan
            df['true_company'] = np.nan
            return df

        # Only decompose where we have actuals
        mask = df[actual_col].notna()

        if mask.sum() == 0:
            warnings.warn("No non-null actuals found. Cannot decompose.")
            df['true_industry'] = np.nan
            df['true_company'] = np.nan
            return df

        # For each (period, industry), compute mean realized EPS
        # This represents the "industry shock" for that period
        industry_actual_means = df[mask].groupby([period_col, industry_col])[actual_col].mean()

        # Map back to full dataframe
        df['true_industry'] = df.apply(
            lambda row: industry_actual_means.get((row[period_col], row[industry_col]), np.nan)
            if pd.notna(row.get(actual_col, np.nan)) else np.nan,
            axis=1
        )

        # Company-specific component
        df['true_company'] = df[actual_col] - df['true_industry']

        return df

    @staticmethod
    def add_decomposition(forecasts_df: pd.DataFrame,
                         forecast_col: str = 'forecast_eps',
                         actual_col: str = 'realized_eps',
                         industry_col: str = 'industry',
                         company_col: str = 'company',
                         period_col: str = 'period',
                         analyst_col: str = 'analyst_id',
                         verbose: bool = True) -> pd.DataFrame:
        """
        Add all decomposed components to DataFrame.

        This is the main entry point - call this on raw I/B/E/S data
        to add the 4 components needed for decomposed weighting.

        Args:
            forecasts_df: Raw I/B/E/S data
            forecast_col: Column with EPS forecasts
            actual_col: Column with realized EPS
            industry_col: Column with industry ID
            company_col: Column with company ID
            period_col: Column with time period
            analyst_col: Column with analyst ID
            verbose: Print decomposition summary

        Returns:
            DataFrame with added columns:
            - forecast_industry_component
            - forecast_company_component
            - true_industry (if actuals available)
            - true_company (if actuals available)
        """
        df = forecasts_df.copy()

        if verbose:
            print("\n" + "=" * 80)
            print("DECOMPOSING FORECASTS FOR SKILL-BASED WEIGHTING")
            print("=" * 80)
            print(f"\nInput: {len(df):,} forecast records")

        # Decompose forecasts
        df = ForecastDecomposer.decompose_forecasts(
            df,
            forecast_col=forecast_col,
            industry_col=industry_col,
            company_col=company_col,
            period_col=period_col,
            analyst_col=analyst_col
        )

        if verbose:
            print(f"✓ Decomposed forecasts into industry + company components")
            print(f"  • Industry component std: {df['forecast_industry_component'].std():.4f}")
            print(f"  • Company component std: {df['forecast_company_component'].std():.4f}")

        # Decompose actuals if available
        if actual_col in df.columns and df[actual_col].notna().sum() > 0:
            df = ForecastDecomposer.decompose_actuals(
                df,
                actual_col=actual_col,
                industry_col=industry_col,
                company_col=company_col,
                period_col=period_col
            )

            n_actuals = df['true_industry'].notna().sum()
            if verbose:
                print(f"✓ Decomposed {n_actuals:,} actual realizations")
                if n_actuals > 0:
                    print(f"  • True industry std: {df[df['true_industry'].notna()]['true_industry'].std():.4f}")
                    print(f"  • True company std: {df[df['true_company'].notna()]['true_company'].std():.4f}")
        else:
            if verbose:
                print(f"⚠ No actuals available - accuracy tracking will be limited")
            df['true_industry'] = np.nan
            df['true_company'] = np.nan

        if verbose:
            print("=" * 80)

        return df


def validate_decomposition(df: pd.DataFrame,
                           forecast_col: str = 'forecast_eps',
                           tolerance: float = 1e-6) -> Tuple[bool, Dict]:
    """
    Validate that decomposition was performed correctly.

    Checks:
    1. Forecast = Industry Component + Company Component (within tolerance)
    2. All components are finite
    3. Industry component has lower variance than company component (typically)

    Args:
        df: DataFrame with decomposed forecasts
        forecast_col: Name of original forecast column
        tolerance: Numerical tolerance for reconstruction check

    Returns:
        (is_valid, diagnostics_dict)
    """
    diagnostics = {}

    # Check 1: Reconstruction
    required_cols = [forecast_col, 'forecast_industry_component', 'forecast_company_component']
    missing_cols = [col for col in required_cols if col not in df.columns]

    if missing_cols:
        return False, {'error': f"Missing columns: {missing_cols}"}

    reconstructed = df['forecast_industry_component'] + df['forecast_company_component']
    reconstruction_error = (df[forecast_col] - reconstructed).abs()
    max_error = reconstruction_error.max()

    diagnostics['max_reconstruction_error'] = max_error
    diagnostics['reconstruction_ok'] = max_error < tolerance

    # Check 2: Finite values
    diagnostics['all_finite'] = (
        np.isfinite(df['forecast_industry_component']).all() and
        np.isfinite(df['forecast_company_component']).all()
    )

    # Check 3: Variance decomposition
    diagnostics['industry_std'] = df['forecast_industry_component'].std()
    diagnostics['company_std'] = df['forecast_company_component'].std()
    diagnostics['original_std'] = df[forecast_col].std()

    is_valid = diagnostics['reconstruction_ok'] and diagnostics['all_finite']

    return is_valid, diagnostics


if __name__ == "__main__":
    # Demo: Decompose synthetic I/B/E/S data
    print("Testing decomposition on synthetic data...")

    # Create simple test case
    test_data = pd.DataFrame({
        'period': [0, 0, 0, 0, 1, 1, 1, 1],
        'company': ['A', 'A', 'B', 'B', 'A', 'A', 'B', 'B'],
        'industry': ['Tech', 'Tech', 'Tech', 'Tech', 'Tech', 'Tech', 'Tech', 'Tech'],
        'analyst_id': ['AN1', 'AN2', 'AN1', 'AN2', 'AN1', 'AN2', 'AN1', 'AN2'],
        'forecast_eps': [1.0, 1.2, 0.9, 1.1, 1.5, 1.3, 1.4, 1.6],
        'realized_eps': [1.1, 1.1, 0.95, 0.95, 1.4, 1.4, 1.5, 1.5]
    })

    # Apply decomposition
    decomposed = ForecastDecomposer.add_decomposition(test_data, verbose=True)

    # Validate
    is_valid, diagnostics = validate_decomposition(decomposed)

    print(f"\nValidation: {'✓ PASSED' if is_valid else '✗ FAILED'}")
    print(f"Diagnostics: {diagnostics}")

    print("\nSample decomposed data:")
    print(decomposed[['period', 'company', 'analyst_id', 'forecast_eps',
                     'forecast_industry_component', 'forecast_company_component']].head())
