"""
SmartEstimates Core Module - Production Version
================================================

Core SmartEstimate builder with proper temporal sequencing and O(n) performance.

This module provides the fundamental SmartEstimate construction algorithm
with industry-company decomposed weighting.

Author: Quantitative Research
Date: 2025-11-25
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import Dict, List, Optional
from collections import defaultdict, deque


@dataclass
class SmartEstimateConfig:
    """Configuration for SmartEstimate algorithm."""

    # Accuracy tracking
    recency_halflife: int = 30          # Days for exponential decay
    min_history: int = 10               # Minimum periods before using historical accuracy
    max_history_periods: int = 252      # Maximum history to keep (memory management)

    # Outlier handling
    outlier_threshold: float = 3.0      # Z-score threshold for outlier removal
    winsorize_quantile: float = 0.05    # Winsorize at 5%/95%

    # Numerical stability
    weight_floor: float = 0.01          # Regularization for RMSE to weight conversion

    def __post_init__(self):
        """Validate configuration parameters."""
        if self.recency_halflife <= 0:
            raise ValueError("recency_halflife must be positive")
        if self.min_history < 1:
            raise ValueError("min_history must be at least 1")
        if not 0 < self.winsorize_quantile < 0.5:
            raise ValueError("winsorize_quantile must be between 0 and 0.5")


class SmartEstimateBuilder:
    """
    Production-grade SmartEstimate builder with temporal consistency.

    Key features:
    - Processes periods sequentially to maintain temporal consistency
    - Uses optimized groupby operations within each period
    - Bounded memory usage for accuracy history
    - Comprehensive error handling
    """

    def __init__(self, config: SmartEstimateConfig):
        self.config = config

        # Use deque with maxlen for bounded memory
        self.accuracy_history = {
            'industry': defaultdict(lambda: deque(maxlen=config.max_history_periods)),
            'company': defaultdict(lambda: deque(maxlen=config.max_history_periods))
        }

        # Cache for pre-computed values
        self._industry_means_cache = {}

    def update_accuracy_history(self, forecasts_df: pd.DataFrame, period: int):
        """
        Update historical accuracy tracking for a specific period.

        Args:
            forecasts_df: DataFrame with forecasts and actuals
            period: Period to update history for
        """
        period_data = forecasts_df[forecasts_df['period'] == period]

        # Check if we have decomposed components (simulation data vs real data)
        has_components = ('forecast_industry_component' in period_data.columns and
                         'forecast_company_component' in period_data.columns and
                         'true_industry' in period_data.columns and
                         'true_company' in period_data.columns)

        if not has_components:
            # For real I/B/E/S data without decomposition, skip accuracy tracking
            # or use overall forecast error as proxy
            # TODO: Implement decomposition for real data
            return

        for _, row in period_data.iterrows():
            analyst_id = row['analyst_id']
            company = row['company']

            # Industry component error
            industry_error = (row['forecast_industry_component'] - row['true_industry']) ** 2
            self.accuracy_history['industry'][analyst_id].append((period, industry_error))

            # Company component error
            company_error = (row['forecast_company_component'] - row['true_company']) ** 2
            self.accuracy_history['company'][(analyst_id, company)].append((period, company_error))

    def compute_analyst_weights(self, analyst_id: str, company: str,
                               current_period: int, component: str) -> float:
        """
        Compute weight for analyst based on historical accuracy and recency.

        Args:
            analyst_id: Analyst identifier
            company: Company identifier
            current_period: Current period
            component: 'industry' or 'company'

        Returns:
            Weight for this analyst (higher = more accurate historically)
        """
        if component == 'industry':
            history = list(self.accuracy_history['industry'][analyst_id])
        else:
            history = list(self.accuracy_history['company'][(analyst_id, company)])

        if len(history) < self.config.min_history:
            return 1.0  # Equal weight if insufficient history

        # Compute recency-weighted RMSE
        weighted_errors = []
        weights = []

        for period, error in history:
            days_ago = (current_period - period) * 7
            recency_weight = 0.5 ** (days_ago / self.config.recency_halflife)
            weighted_errors.append(error * recency_weight)
            weights.append(recency_weight)

        sum_weights = np.sum(weights)
        if sum_weights == 0 or len(weighted_errors) == 0:
            return 1.0

        rmse = np.sqrt(np.sum(weighted_errors) / sum_weights)
        weight = 1.0 / (rmse + self.config.weight_floor)

        return weight

    def construct_smartestimates_sequential(self, forecasts_df: pd.DataFrame,
                                           verbose: bool = True) -> pd.DataFrame:
        """
        Construct SmartEstimates with proper temporal sequencing.

        Processes periods in order while using optimized groupby operations
        within each period. This maintains temporal consistency (no look-ahead bias)
        while achieving O(n) performance.

        Args:
            forecasts_df: DataFrame with all forecasts
            verbose: Whether to print progress

        Returns:
            DataFrame with SmartEstimates for all company-periods
        """
        if verbose:
            print("\n[OPTIMIZED] Constructing SmartEstimates with temporal consistency...")

        # Pre-compute industry means for ALL periods (this is OK - just data)
        if verbose:
            print("  [1/3] Pre-computing industry means...")
        industry_means = forecasts_df.groupby(['period', 'industry'])['forecast_eps'].mean()
        self._industry_means_cache = industry_means.to_dict()

        # Get sorted periods
        periods = sorted(forecasts_df['period'].unique())

        if verbose:
            print(f"  [2/3] Processing {len(periods)} periods sequentially...")

        results = []

        for i, period in enumerate(periods):
            # Update accuracy history with PREVIOUS period only (temporal consistency)
            if period > 0 and periods.index(period) > 0:
                prev_period = periods[periods.index(period) - 1]
                self.update_accuracy_history(forecasts_df, prev_period)

            # Get data for this period
            period_df = forecasts_df[forecasts_df['period'] == period]

            # Use optimized groupby WITHIN this period
            for company, group_df in period_df.groupby('company'):
                result = self._construct_smartestimate_from_group(
                    group_df, period, company
                )
                if result is not None:
                    results.append(result)

            # Progress reporting
            if verbose and (i + 1) % max(1, len(periods) // 10) == 0:
                pct = (i + 1) / len(periods) * 100
                print(f"    Progress: {i+1}/{len(periods)} periods ({pct:.0f}%)")

        if verbose:
            print(f"  [3/3] Completed {len(results)} SmartEstimates")

        return pd.DataFrame(results)

    def construct_smartestimate(self, forecasts_df: pd.DataFrame, period: int,
                                company: str) -> Optional[Dict]:
        """
        Construct SmartEstimate for a single company-period (backwards compatibility).

        This method is provided for backwards compatibility with existing tests.
        For production use, prefer construct_smartestimates_sequential().

        Args:
            forecasts_df: DataFrame with all forecasts
            period: Period to process
            company: Company to process

        Returns:
            Dictionary with SmartEstimate result or None if no data
        """
        # Handle empty DataFrame
        if len(forecasts_df) == 0 or 'period' not in forecasts_df.columns:
            return None

        # Filter to this company-period
        period_forecasts = forecasts_df[
            (forecasts_df['period'] == period) &
            (forecasts_df['company'] == company)
        ].copy()

        if len(period_forecasts) == 0:
            return None

        # Compute industry mean manually (not from cache)
        industry = period_forecasts['industry'].iloc[0]
        industry_forecasts = forecasts_df[
            (forecasts_df['period'] == period) &
            (forecasts_df['industry'] == industry)
        ]['forecast_eps']

        industry_mean = industry_forecasts.mean() if len(industry_forecasts) > 0 else period_forecasts['forecast_eps'].mean()

        # Store in cache for the helper method
        self._industry_means_cache[(period, industry)] = industry_mean

        return self._construct_smartestimate_from_group(period_forecasts, period, company)

    def _construct_smartestimate_from_group(self, period_forecasts: pd.DataFrame,
                                           period: int, company: str) -> Optional[Dict]:
        """Construct SmartEstimate from pre-filtered group."""
        if len(period_forecasts) == 0:
            return None

        # Compute consensus
        consensus = period_forecasts['forecast_eps'].mean(skipna=True)

        # Get industry mean from cache
        industry = period_forecasts['industry'].iloc[0]
        industry_mean = self._industry_means_cache.get((period, industry), consensus)

        # Compute deviations
        period_forecasts = period_forecasts.copy()
        period_forecasts['industry_component'] = industry_mean
        period_forecasts['company_deviation'] = period_forecasts['forecast_eps'] - industry_mean

        # Winsorize deviations
        deviations = period_forecasts['company_deviation']
        if len(deviations) > 2:
            lower = deviations.quantile(self.config.winsorize_quantile)
            upper = deviations.quantile(1 - self.config.winsorize_quantile)
            period_forecasts['company_deviation_winsorized'] = deviations.clip(lower, upper)
        else:
            period_forecasts['company_deviation_winsorized'] = deviations

        # Compute weights
        analysts = period_forecasts['analyst_id'].values

        weights_industry = np.array([
            self.compute_analyst_weights(aid, company, period, 'industry')
            for aid in analysts
        ])

        weights_company = np.array([
            self.compute_analyst_weights(aid, company, period, 'company')
            for aid in analysts
        ])

        # Normalize weights
        sum_ind = weights_industry.sum()
        sum_comp = weights_company.sum()

        if sum_ind == 0:
            weights_industry = np.ones_like(weights_industry) / len(weights_industry)
        else:
            weights_industry = weights_industry / sum_ind

        if sum_comp == 0:
            weights_company = np.ones_like(weights_company) / len(weights_company)
        else:
            weights_company = weights_company / sum_comp

        # Construct SmartEstimate
        smart_industry = np.sum(weights_industry * period_forecasts['industry_component'].values)
        smart_deviation = np.sum(weights_company * period_forecasts['company_deviation_winsorized'].values)
        smart_estimate = smart_industry + smart_deviation

        result = {
            'period': period,
            'company': company,
            'consensus': consensus,
            'smart_estimate': smart_estimate,
            'smart_industry': smart_industry,
            'smart_deviation': smart_deviation,
            'n_analysts': len(period_forecasts)
        }

        # Add realized EPS if available (could be 'true_eps' or 'realized_eps')
        if 'true_eps' in period_forecasts.columns:
            result['true_eps'] = period_forecasts['true_eps'].iloc[0]
        elif 'realized_eps' in period_forecasts.columns:
            result['true_eps'] = period_forecasts['realized_eps'].iloc[0]

        return result
