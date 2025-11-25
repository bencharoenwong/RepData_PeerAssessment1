"""
SmartEstimates Data Simulation Module
======================================

Generates realistic analyst forecast data with factor structure for testing.

This module creates simulated analyst forecasts with:
- Decomposed EPS structure (industry + company-specific components)
- Heterogeneous analyst skills (industry vs company forecasting)
- Forecast staleness and coverage patterns
- Realistic statistical properties

Author: Quantitative Research
Date: 2025-11-25
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Dict


@dataclass
class SimulationConfig:
    """Configuration parameters for simulation."""

    # Simulation size
    n_companies: int = 50
    n_industries: int = 5
    n_analysts: int = 30
    n_periods: int = 100

    # Analyst skill parameters
    skill_industry_mean: float = 0.6
    skill_industry_std: float = 0.25
    skill_company_mean: float = 0.6
    skill_company_std: float = 0.25
    skill_correlation: float = 0.3  # Correlation between skills

    # Data generation parameters
    industry_volatility: float = 0.15
    company_volatility: float = 0.25
    forecast_noise_base: float = 0.10

    # Forecast staleness parameters
    update_probability: float = 0.7  # Probability analyst updates each period
    staleness_decay: float = 0.95  # Accuracy decay for stale forecasts

    # SmartEstimate parameters (for compatibility with core module)
    recency_halflife: int = 30
    min_history: int = 10
    max_history_periods: int = 252
    outlier_threshold: float = 3.0
    winsorize_quantile: float = 0.05
    weight_floor: float = 0.01


class DataSimulator:
    """Generates realistic analyst forecast data with factor structure."""

    def __init__(self, config: SimulationConfig):
        self.config = config
        self._initialize_structure()

    def _initialize_structure(self):
        """Set up company-industry mapping and analyst skills."""
        # Assign companies to industries
        self.company_to_industry = {
            f"RIC_{i:03d}": f"IND_{i % self.config.n_industries}"
            for i in range(self.config.n_companies)
        }

        # Generate analyst skills
        self.analyst_skills = self._generate_analyst_skills()

    def _generate_analyst_skills(self) -> pd.DataFrame:
        """Generate heterogeneous analyst skills for industry vs company forecasting."""
        # Construct correlated bivariate normal
        cov_matrix = [
            [self.config.skill_industry_std**2,
             self.config.skill_correlation * self.config.skill_industry_std * self.config.skill_company_std],
            [self.config.skill_correlation * self.config.skill_industry_std * self.config.skill_company_std,
             self.config.skill_company_std**2]
        ]

        skills = np.random.multivariate_normal(
            mean=[self.config.skill_industry_mean, self.config.skill_company_mean],
            cov=cov_matrix,
            size=self.config.n_analysts
        )

        # Clip to [0, 1] range (skill = Information Coefficient)
        skills = np.clip(skills, 0.05, 0.95)

        df = pd.DataFrame(skills, columns=['skill_industry', 'skill_company'])
        df['analyst_id'] = [f"ANALYST_{i:03d}" for i in range(self.config.n_analysts)]

        # Classify analyst archetypes
        df['archetype'] = df.apply(self._classify_archetype, axis=1)

        return df.set_index('analyst_id')

    @staticmethod
    def _classify_archetype(row) -> str:
        """Classify analyst into archetype based on skills."""
        ind_skill = row['skill_industry']
        comp_skill = row['skill_company']

        if ind_skill > 0.7 and comp_skill < 0.5:
            return 'Macro Specialist'
        elif ind_skill < 0.5 and comp_skill > 0.7:
            return 'Stock Picker'
        elif ind_skill > 0.6 and comp_skill > 0.6:
            return 'Generalist'
        else:
            return 'Noise Trader'

    def generate_realized_values(self) -> pd.DataFrame:
        """Generate true realized EPS for each company-period."""
        data = []

        for period in range(self.config.n_periods):
            # Generate industry-level shocks
            industry_shocks = {
                f"IND_{i}": np.random.normal(0, self.config.industry_volatility)
                for i in range(self.config.n_industries)
            }

            # Generate company-level realizations
            for company, industry in self.company_to_industry.items():
                industry_component = industry_shocks[industry]
                company_specific = np.random.normal(0, self.config.company_volatility)

                realized_eps = industry_component + company_specific

                data.append({
                    'period': period,
                    'company': company,
                    'industry': industry,
                    'industry_component': industry_component,
                    'company_specific': company_specific,
                    'realized_eps': realized_eps,
                    'forecast_date': datetime(2020, 1, 1) + timedelta(days=period*7),
                    'realization_date': datetime(2020, 1, 1) + timedelta(days=period*7 + 30)
                })

        return pd.DataFrame(data)

    def generate_forecasts(self, realized_df: pd.DataFrame) -> pd.DataFrame:
        """Generate analyst forecasts with heterogeneous skills and staleness."""
        forecasts = []

        # Track last update period for each analyst-company
        last_update = {}

        for _, row in realized_df.iterrows():
            period = row['period']
            company = row['company']
            industry = row['industry']
            true_industry = row['industry_component']
            true_company = row['company_specific']

            for analyst_id, skill_row in self.analyst_skills.iterrows():
                # Decide if analyst updates forecast this period
                if np.random.random() > self.config.update_probability:
                    continue  # Skip - no update

                last_update[(analyst_id, company)] = period

                # Generate forecast with skill-based accuracy
                skill_ind = skill_row['skill_industry']
                skill_comp = skill_row['skill_company']

                # Forecast industry component (information coefficient approach)
                noise_ind = np.random.normal(0, self.config.forecast_noise_base)
                forecast_industry = skill_ind * true_industry + (1 - skill_ind) * noise_ind

                # Forecast company-specific component
                noise_comp = np.random.normal(0, self.config.forecast_noise_base)
                forecast_company_specific = skill_comp * true_company + (1 - skill_comp) * noise_comp

                # Combined forecast
                forecast_eps = forecast_industry + forecast_company_specific

                # Add some additional noise
                forecast_eps += np.random.normal(0, 0.02)

                forecasts.append({
                    'period': period,
                    'company': company,
                    'industry': industry,
                    'analyst_id': analyst_id,
                    'forecast_eps': forecast_eps,
                    'forecast_industry_component': forecast_industry,
                    'forecast_company_component': forecast_company_specific,
                    'forecast_date': row['forecast_date'],
                    'realization_date': row['realization_date'],
                    'true_eps': row['realized_eps'],
                    'true_industry': true_industry,
                    'true_company': true_company,
                    'skill_industry': skill_ind,
                    'skill_company': skill_comp,
                    'archetype': skill_row['archetype']
                })

        return pd.DataFrame(forecasts)


def run_simulation(config: SimulationConfig):
    """
    Run complete simulation pipeline.

    Args:
        config: Simulation configuration

    Returns:
        Tuple of (results_df, forecasts_df, analyst_skills)
    """
    from .core import SmartEstimateBuilder

    # Generate data
    simulator = DataSimulator(config)
    realized_df = simulator.generate_realized_values()
    forecasts_df = simulator.generate_forecasts(realized_df)

    # Build SmartEstimates
    builder = SmartEstimateBuilder(config)
    results_df = builder.construct_smartestimates_sequential(forecasts_df, verbose=True)

    return results_df, forecasts_df, simulator.analyst_skills
