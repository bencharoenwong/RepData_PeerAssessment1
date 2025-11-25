"""
SmartEstimates Data Loading Module
===================================

Tools for loading and preprocessing real I/B/E/S or Refinitiv analyst forecast data.

Supports:
- I/B/E/S detail history files
- Refinitiv Eikon/Datastream exports
- Custom CSV formats

Author: Quantitative Research
Date: 2025-11-25
"""

import pandas as pd
import numpy as np
from typing import Optional


class IBESDataLoader:
    """Load and preprocess I/B/E/S analyst forecast data."""

    @staticmethod
    def load_ibes_detail_file(filepath: str,
                               ticker_col: str = 'TICKER',
                               analyst_col: str = 'ESTIMATOR',
                               forecast_date_col: str = 'ANNDATS',
                               fiscal_period_col: str = 'FPEDATS',
                               estimate_col: str = 'VALUE',
                               actual_col: str = 'ACTUAL',
                               industry_col: str = 'GVKEY') -> pd.DataFrame:
        """
        Load I/B/E/S detail history file.

        Expected columns:
        - TICKER: Company ticker (str)
        - ESTIMATOR: Analyst identifier (str or int)
        - ANNDATS: Forecast announcement date (datetime or string YYYY-MM-DD)
        - FPEDATS: Fiscal period end date (datetime or string YYYY-MM-DD)
        - VALUE: EPS estimate (float, in reporting currency)
        - ACTUAL: Realized EPS (float, may be NaN if not yet reported)
        - GVKEY: Industry/sector classification (str or int)

        Parameters:
            filepath: Path to CSV, Excel, or Parquet file
            *_col: Column name mappings for flexibility

        Returns:
            Preprocessed DataFrame with standardized column names
        """
        # Detect file type and load
        if filepath.endswith('.csv'):
            df = pd.read_csv(filepath, low_memory=False)
        elif filepath.endswith(('.xlsx', '.xls')):
            df = pd.read_excel(filepath)
        elif filepath.endswith('.parquet'):
            df = pd.read_parquet(filepath)
        else:
            raise ValueError(f"Unsupported file type: {filepath}. Use .csv, .xlsx, or .parquet")

        # Standardize column names
        column_mapping = {
            ticker_col: 'company',
            analyst_col: 'analyst_id',
            forecast_date_col: 'forecast_date',
            fiscal_period_col: 'realization_date',
            estimate_col: 'forecast_eps',
            industry_col: 'industry',
            actual_col: 'realized_eps'
        }

        # Check required columns exist
        missing_cols = [col for col in column_mapping.keys() if col not in df.columns]
        if missing_cols:
            raise ValueError(f"Missing required columns: {missing_cols}")

        df = df.rename(columns=column_mapping)

        # Convert dates
        for date_col in ['forecast_date', 'realization_date']:
            if not pd.api.types.is_datetime64_any_dtype(df[date_col]):
                df[date_col] = pd.to_datetime(df[date_col], errors='coerce')

        # Convert analyst_id to string
        df['analyst_id'] = df['analyst_id'].astype(str)

        # Convert industry to string
        df['industry'] = df['industry'].astype(str)

        # Keep only essential columns
        essential_cols = ['company', 'analyst_id', 'forecast_date', 'realization_date',
                         'forecast_eps', 'realized_eps', 'industry']
        df = df[essential_cols]

        print(f"[IBESDataLoader] Loaded {len(df):,} raw forecast records from {filepath}")

        return df

    @staticmethod
    def preprocess_ibes_data(df: pd.DataFrame,
                             min_analysts: int = 3,
                             max_horizon_days: int = 365,
                             winsorize_pct: float = 0.01) -> pd.DataFrame:
        """
        Clean and preprocess I/B/E/S data for SmartEstimate construction.

        Handles:
        1. Duplicate forecasts (keep most recent)
        2. Missing values
        3. Extreme outliers (likely data errors)
        4. Stale forecasts (too far from realization date)
        5. Insufficient analyst coverage

        Parameters:
            df: Raw I/B/E/S data from load_ibes_detail_file()
            min_analysts: Minimum number of analysts required per company-period
            max_horizon_days: Maximum days between forecast and realization
            winsorize_pct: Percentile for winsorizing extreme values (0.01 = 1%/99%)

        Returns:
            Cleaned DataFrame ready for SmartEstimate construction
        """
        print("\n" + "=" * 80)
        print("PREPROCESSING I/B/E/S DATA")
        print("=" * 80)

        initial_count = len(df)
        print(f"\n[1/7] Initial records: {initial_count:,}")

        # 1. Remove records with missing essential values
        df = df.dropna(subset=['forecast_eps', 'forecast_date', 'realization_date', 'company', 'analyst_id'])
        print(f"[2/7] After removing missing values: {len(df):,} ({len(df)/initial_count*100:.1f}% retained)")

        # 2. Remove duplicate forecasts (same analyst, company, realization date)
        #    Keep the most recent forecast
        df = df.sort_values('forecast_date')
        df = df.drop_duplicates(subset=['company', 'analyst_id', 'realization_date'], keep='last')
        print(f"[3/7] After removing duplicates: {len(df):,} ({len(df)/initial_count*100:.1f}% retained)")

        # 3. Calculate forecast horizon
        df['forecast_horizon_days'] = (df['realization_date'] - df['forecast_date']).dt.days

        # Remove forecasts with negative or excessive horizons
        df = df[(df['forecast_horizon_days'] >= 0) & (df['forecast_horizon_days'] <= max_horizon_days)]
        print(f"[4/7] After filtering horizon (0-{max_horizon_days} days): {len(df):,} ({len(df)/initial_count*100:.1f}% retained)")

        # 4. Winsorize extreme forecast values (likely data errors)
        lower_bound = df['forecast_eps'].quantile(winsorize_pct)
        upper_bound = df['forecast_eps'].quantile(1 - winsorize_pct)

        n_outliers = ((df['forecast_eps'] < lower_bound) | (df['forecast_eps'] > upper_bound)).sum()
        df = df[(df['forecast_eps'] >= lower_bound) & (df['forecast_eps'] <= upper_bound)]
        print(f"[5/7] After removing outliers ({winsorize_pct*100:.1f}%/{100-winsorize_pct*100:.1f}%): {len(df):,} (removed {n_outliers:,})")

        # 5. Filter to company-periods with sufficient analyst coverage
        coverage = df.groupby(['company', 'realization_date']).size()
        sufficient_coverage = coverage[coverage >= min_analysts].index
        df = df.set_index(['company', 'realization_date'])
        df = df.loc[df.index.isin(sufficient_coverage)]
        df = df.reset_index()
        print(f"[6/7] After filtering min {min_analysts} analysts: {len(df):,} ({len(df)/initial_count*100:.1f}% retained)")

        # 6. Create period identifier (fiscal quarters)
        df['period'] = df.groupby('realization_date').ngroup()

        print(f"[7/7] Final dataset: {len(df):,} forecasts")
        print(f"  • {df['company'].nunique()} companies")
        print(f"  • {df['analyst_id'].nunique()} analysts")
        print(f"  • {df['period'].nunique()} periods")
        print(f"  • {df['industry'].nunique()} industries")

        return df


class RealDataSmartEstimateEngine:
    """
    Constructs SmartEstimates from real I/B/E/S data using decomposed weighting.
    """

    def __init__(self, config=None):
        """
        Initialize engine with configuration.

        Parameters:
            config: SmartEstimateConfig instance (uses defaults if None)
        """
        from .core import SmartEstimateBuilder, SmartEstimateConfig

        if config is None:
            config = SmartEstimateConfig()

        self.config = config
        self.builder = SmartEstimateBuilder(config)

    def compute_smartestimates(self, forecasts_df: pd.DataFrame,
                               include_actuals: bool = True) -> pd.DataFrame:
        """
        Compute SmartEstimates for all company-periods in the dataset.

        Parameters:
            forecasts_df: Preprocessed I/B/E/S data from preprocess_ibes_data()
            include_actuals: If True, join realized EPS for evaluation

        Returns:
            DataFrame with SmartEstimates, consensus, and metadata
        """
        print("\n" + "=" * 80)
        print("CONSTRUCTING SMARTESTIMATES")
        print("=" * 80)

        # Use sequential processing for temporal consistency
        results_df = self.builder.construct_smartestimates_sequential(forecasts_df, verbose=True)

        # Add realized EPS if available and not already present
        if include_actuals and 'realized_eps' in forecasts_df.columns:
            # Check if true_eps was already added by the builder
            if 'true_eps' not in results_df.columns:
                # Get realized values (should be same for all forecasts in a company-period)
                realized = forecasts_df.groupby(['period', 'company'])['realized_eps'].first().reset_index()
                realized = realized.rename(columns={'realized_eps': 'true_eps'})
                results_df = results_df.merge(realized, on=['period', 'company'], how='left')

        # If we have actuals, compute errors
        if include_actuals and 'true_eps' in results_df.columns:
            results_df = self._compute_errors(results_df)

        return results_df

    def _compute_errors(self, results_df: pd.DataFrame) -> pd.DataFrame:
        """Compute forecast errors for evaluation."""
        from .evaluation import PerformanceEvaluator

        results_df = results_df.copy()

        # Remove rows without actuals
        results_df = results_df.dropna(subset=['true_eps'])

        # Compute errors (already using 'true_eps' column name)
        evaluator = PerformanceEvaluator()
        results_df = evaluator.calculate_metrics(results_df)

        return results_df
