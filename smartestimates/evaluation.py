"""
SmartEstimates Performance Evaluation Module
=============================================

Tools for evaluating SmartEstimate performance vs consensus forecasts.

Provides metrics including:
- RMSE (Root Mean Squared Error)
- MAE (Mean Absolute Error)
- Bias
- Information Coefficient

Author: Quantitative Research
Date: 2025-11-25
"""

import numpy as np
import pandas as pd


class PerformanceEvaluator:
    """Evaluate SmartEstimate vs Consensus performance."""

    @staticmethod
    def calculate_metrics(results_df: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate performance metrics for consensus vs SmartEstimate.

        Args:
            results_df: DataFrame with consensus, smart_estimate, and true_eps columns

        Returns:
            DataFrame with additional error metric columns
        """
        results_df = results_df.copy()

        # Forecast errors
        results_df['error_consensus'] = results_df['consensus'] - results_df['true_eps']
        results_df['error_smart'] = results_df['smart_estimate'] - results_df['true_eps']

        # Squared errors
        results_df['se_consensus'] = results_df['error_consensus'] ** 2
        results_df['se_smart'] = results_df['error_smart'] ** 2

        # Absolute errors
        results_df['ae_consensus'] = np.abs(results_df['error_consensus'])
        results_df['ae_smart'] = np.abs(results_df['error_smart'])

        return results_df

    @staticmethod
    def summary_statistics(results_df: pd.DataFrame) -> pd.DataFrame:
        """
        Generate summary statistics comparing methods.

        Args:
            results_df: DataFrame with error metrics (output of calculate_metrics)

        Returns:
            Summary DataFrame with RMSE, MAE, Bias, and IC for both methods
        """
        metrics = {
            'RMSE': [
                np.sqrt(results_df['se_consensus'].mean()),
                np.sqrt(results_df['se_smart'].mean())
            ],
            'MAE': [
                results_df['ae_consensus'].mean(),
                results_df['ae_smart'].mean()
            ],
            'Bias': [
                results_df['error_consensus'].mean(),
                results_df['error_smart'].mean()
            ],
            'Information_Coefficient': [
                results_df[['consensus', 'true_eps']].corr().iloc[0, 1] if len(results_df) >= 2 else np.nan,
                results_df[['smart_estimate', 'true_eps']].corr().iloc[0, 1] if len(results_df) >= 2 else np.nan
            ]
        }

        summary = pd.DataFrame(metrics, index=['Consensus', 'SmartEstimate'])

        # Calculate improvement
        improvement = {}
        for metric in metrics.keys():
            if metric == 'Information_Coefficient':
                improvement[metric] = summary.loc['SmartEstimate', metric] - summary.loc['Consensus', metric]
            else:
                consensus_val = summary.loc['Consensus', metric]
                if consensus_val == 0:
                    improvement[metric] = np.nan
                else:
                    improvement[metric] = (consensus_val - summary.loc['SmartEstimate', metric]) / consensus_val * 100

        summary.loc['Improvement_%'] = improvement

        return summary

    @staticmethod
    def diebold_mariano_test(results_df: pd.DataFrame) -> dict:
        """
        Perform Diebold-Mariano test for forecast accuracy difference.

        Tests null hypothesis that Consensus and SmartEstimate have equal accuracy.

        Args:
            results_df: DataFrame with error metrics

        Returns:
            Dictionary with test statistic and p-value
        """
        # Compute loss differential
        diff = results_df['se_consensus'] - results_df['se_smart']

        # Check for zero variance
        std_diff = diff.std()
        if std_diff == 0 or len(diff) == 0:
            return {
                'statistic': np.nan,
                'p_value': np.nan,
                'message': 'Cannot compute (zero variance or no data)'
            }

        # Compute test statistic
        dm_stat = diff.mean() / (std_diff / np.sqrt(len(diff)))

        # Compute p-value (two-tailed)
        from scipy import stats
        p_value = 2 * (1 - stats.norm.cdf(abs(dm_stat)))

        return {
            'statistic': dm_stat,
            'p_value': p_value,
            'message': 'SmartEstimate is significantly better' if p_value < 0.05 and dm_stat > 0 else 'No significant difference'
        }
