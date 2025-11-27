"""
Realistic I/B/E/S Data Simulator
=================================

Simulates I/B/E/S-style analyst forecast data with realistic features:
- Asynchronous analyst updates (not all analysts update every period)
- Staggered forecast dates (analysts update at different times)
- Heterogeneous coverage (analysts don't cover all stocks)
- Forecast revisions (analysts update their previous estimates)
- Missing actuals (forward-looking forecasts)

This simulates what you'll actually see in real I/B/E/S data.

Author: Quantitative Research
Date: 2025-11-27
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass


@dataclass
class IBESSimulationConfig:
    """Configuration for realistic I/B/E/S simulation."""

    # Universe
    n_companies: int = 100
    n_analysts: int = 50
    n_quarters: int = 20  # 5 years of quarterly data

    # Coverage realism
    avg_stocks_per_analyst: int = 15  # Analysts typically cover 10-20 stocks
    min_analysts_per_stock: int = 5   # Minimum coverage requirement

    # Temporal realism
    base_date: datetime = datetime(2020, 1, 1)
    days_before_earnings: int = 30  # Forecast window before earnings announcement

    # Update frequency (realistic: analysts don't update every day)
    analyst_update_prob_per_week: float = 0.3  # 30% chance analyst updates in a given week
    revision_prob: float = 0.7  # 70% of updates are revisions, 30% are new initiations

    # Skill distribution (similar to your original simulation)
    skill_industry_mean: float = 0.6
    skill_industry_std: float = 0.25
    skill_company_mean: float = 0.6
    skill_company_std: float = 0.25
    skill_correlation: float = 0.3

    # Economic parameters
    industry_volatility: float = 0.15
    company_volatility: float = 0.25
    forecast_noise: float = 0.10


class IBESDataSimulator:
    """
    Simulates realistic I/B/E/S analyst forecast data.

    Output format matches real I/B/E/S detail files:
    - TICKER: Company identifier
    - ESTIMATOR: Analyst identifier
    - ANNDATS: Forecast announcement date
    - FPEDATS: Fiscal period end date (earnings announcement date)
    - VALUE: EPS forecast
    - ACTUAL: Realized EPS (NaN for future periods)
    - GVKEY: Industry identifier
    """

    def __init__(self, config: IBESSimulationConfig):
        self.config = config
        self._initialize_universe()
        self._initialize_analyst_skills()

    def _initialize_universe(self):
        """Set up company-industry mapping and coverage matrix."""
        # Create companies with industry assignments
        n_industries = max(5, self.config.n_companies // 20)  # ~20 companies per industry

        self.companies = [f"TICKER_{i:04d}" for i in range(self.config.n_companies)]
        self.industries = [f"IND_{i % n_industries:02d}" for i in range(self.config.n_companies)]
        self.company_to_industry = dict(zip(self.companies, self.industries))

        # Create analyst coverage matrix (who covers what)
        self.coverage = self._generate_coverage_matrix()

    def _generate_coverage_matrix(self) -> pd.DataFrame:
        """
        Generate realistic analyst coverage matrix.

        Realistic features:
        - Analysts tend to specialize in certain industries
        - Some stocks (large cap) have more coverage
        - Coverage is sparse and heterogeneous
        """
        coverage_data = []

        for analyst_idx in range(self.config.n_analysts):
            analyst_id = f"ANALYST_{analyst_idx:04d}"

            # Analyst specializes in 1-3 industries
            n_specialist_industries = np.random.choice([1, 2, 3], p=[0.5, 0.3, 0.2])
            specialist_industries = np.random.choice(
                list(set(self.industries)),
                size=n_specialist_industries,
                replace=False
            )

            # Select stocks from specialist industries
            eligible_stocks = [
                ticker for ticker, ind in self.company_to_industry.items()
                if ind in specialist_industries
            ]

            # Cover ~15 stocks on average, but with variation
            n_stocks = min(
                len(eligible_stocks),
                max(5, int(np.random.normal(self.config.avg_stocks_per_analyst, 5)))
            )

            covered_stocks = np.random.choice(eligible_stocks, size=n_stocks, replace=False)

            for ticker in covered_stocks:
                coverage_data.append({
                    'analyst_id': analyst_id,
                    'company': ticker,
                    'industry': self.company_to_industry[ticker]
                })

        coverage_df = pd.DataFrame(coverage_data)

        # Ensure all stocks have minimum coverage
        stocks_with_coverage = coverage_df.groupby('company').size()
        for ticker in self.companies:
            if ticker not in stocks_with_coverage or stocks_with_coverage[ticker] < self.config.min_analysts_per_stock:
                # Add random analysts to meet minimum
                n_needed = self.config.min_analysts_per_stock - stocks_with_coverage.get(ticker, 0)
                random_analysts = np.random.choice(
                    [f"ANALYST_{i:04d}" for i in range(self.config.n_analysts)],
                    size=n_needed,
                    replace=False
                )
                for analyst_id in random_analysts:
                    if not ((coverage_df['analyst_id'] == analyst_id) & (coverage_df['company'] == ticker)).any():
                        coverage_df = pd.concat([coverage_df, pd.DataFrame([{
                            'analyst_id': analyst_id,
                            'company': ticker,
                            'industry': self.company_to_industry[ticker]
                        }])], ignore_index=True)

        return coverage_df

    def _initialize_analyst_skills(self):
        """Generate heterogeneous analyst skills (industry vs company forecasting)."""
        # Correlated bivariate normal for industry and company skills
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

        skills = np.clip(skills, 0.05, 0.95)

        self.analyst_skills = pd.DataFrame({
            'analyst_id': [f"ANALYST_{i:04d}" for i in range(self.config.n_analysts)],
            'skill_industry': skills[:, 0],
            'skill_company': skills[:, 1]
        }).set_index('analyst_id')

    def generate_ibes_data(self) -> pd.DataFrame:
        """
        Generate realistic I/B/E/S detail data.

        Returns:
            DataFrame matching I/B/E/S format with columns:
            - TICKER: Company ticker
            - ESTIMATOR: Analyst ID
            - ANNDATS: Forecast announcement date
            - FPEDATS: Fiscal period end date
            - VALUE: EPS forecast
            - ACTUAL: Realized EPS (NaN for future periods)
            - GVKEY: Industry ID
        """
        # First generate realized earnings
        realized_df = self._generate_realized_earnings()

        # Then generate forecasts with asynchronous timing
        forecasts_df = self._generate_asynchronous_forecasts(realized_df)

        # Format as I/B/E/S-style data
        ibes_df = self._format_as_ibes(forecasts_df, realized_df)

        return ibes_df

    def _generate_realized_earnings(self) -> pd.DataFrame:
        """
        Generate true realized EPS with factor structure.

        Structure: EPS = Industry Component + Company-Specific Component
        """
        data = []

        for quarter in range(self.config.n_quarters):
            # Earnings announcement date (end of quarter + 30 days)
            announcement_date = self.config.base_date + timedelta(days=quarter * 90 + 30)

            # Generate industry shocks
            unique_industries = list(set(self.industries))
            industry_shocks = {
                ind: np.random.normal(0, self.config.industry_volatility)
                for ind in unique_industries
            }

            for company in self.companies:
                industry = self.company_to_industry[company]
                industry_component = industry_shocks[industry]
                company_specific = np.random.normal(0, self.config.company_volatility)

                realized_eps = industry_component + company_specific

                data.append({
                    'quarter': quarter,
                    'company': company,
                    'industry': industry,
                    'announcement_date': announcement_date,
                    'industry_component': industry_component,
                    'company_specific': company_specific,
                    'realized_eps': realized_eps
                })

        return pd.DataFrame(data)

    def _generate_asynchronous_forecasts(self, realized_df: pd.DataFrame) -> List[Dict]:
        """
        Generate analyst forecasts with realistic asynchronous updates.

        Key realistic features:
        - Analysts update at different times (not synchronized)
        - Updates happen throughout the forecast window (not all on same day)
        - Analysts revise their forecasts (multiple updates per quarter)
        - Not all analysts update every quarter
        """
        forecasts = []

        # Track last forecast for each (analyst, company, quarter) for revisions
        last_forecast = {}

        for _, realized_row in realized_df.iterrows():
            quarter = realized_row['quarter']
            company = realized_row['company']
            industry = realized_row['industry']
            announcement_date = realized_row['announcement_date']

            # Get analysts who cover this company
            covering_analysts = self.coverage[self.coverage['company'] == company]['analyst_id'].values

            if len(covering_analysts) == 0:
                continue

            # Forecast window: 90 days before earnings announcement
            forecast_window_start = announcement_date - timedelta(days=90)

            # Simulate weekly update opportunities (13 weeks before announcement)
            for week in range(13):
                week_date = forecast_window_start + timedelta(days=week * 7)

                # Skip if week is after announcement date
                if week_date >= announcement_date:
                    continue

                for analyst_id in covering_analysts:
                    # Does analyst update this week?
                    if np.random.random() > self.config.analyst_update_prob_per_week:
                        continue

                    # Exact forecast date: random day within the week
                    forecast_date = week_date + timedelta(days=np.random.randint(0, 7))

                    # Generate forecast using decomposed skill
                    forecast = self._generate_single_forecast(
                        analyst_id=analyst_id,
                        company=company,
                        industry=industry,
                        true_industry=realized_row['industry_component'],
                        true_company=realized_row['company_specific'],
                        forecast_date=forecast_date,
                        announcement_date=announcement_date
                    )

                    forecast['quarter'] = quarter
                    forecasts.append(forecast)

                    # Track for potential revision
                    last_forecast[(analyst_id, company, quarter)] = forecast

        return forecasts

    def _generate_single_forecast(self, analyst_id: str, company: str, industry: str,
                                  true_industry: float, true_company: float,
                                  forecast_date: datetime, announcement_date: datetime) -> Dict:
        """Generate a single forecast with skill-based accuracy."""
        skills = self.analyst_skills.loc[analyst_id]
        skill_ind = skills['skill_industry']
        skill_comp = skills['skill_company']

        # Forecast industry component (Information Coefficient approach)
        noise_ind = np.random.normal(0, self.config.forecast_noise)
        forecast_industry = skill_ind * true_industry + (1 - skill_ind) * noise_ind

        # Forecast company-specific component
        noise_comp = np.random.normal(0, self.config.forecast_noise)
        forecast_company = skill_comp * true_company + (1 - skill_comp) * noise_comp

        # Combined forecast
        forecast_eps = forecast_industry + forecast_company

        # Add some additional noise
        forecast_eps += np.random.normal(0, 0.02)

        return {
            'company': company,
            'industry': industry,
            'analyst_id': analyst_id,
            'forecast_date': forecast_date,
            'announcement_date': announcement_date,
            'forecast_eps': forecast_eps,
            'forecast_industry_component': forecast_industry,
            'forecast_company_component': forecast_company,
            'true_industry': true_industry,
            'true_company': true_company,
            'skill_industry': skill_ind,
            'skill_company': skill_comp
        }

    def _format_as_ibes(self, forecasts_df: List[Dict], realized_df: pd.DataFrame) -> pd.DataFrame:
        """
        Format data to match I/B/E/S detail file structure.

        I/B/E/S Columns:
        - TICKER: Company identifier
        - ESTIMATOR: Analyst identifier
        - ANNDATS: Forecast announcement date
        - FPEDATS: Fiscal period end date (earnings date)
        - VALUE: EPS estimate
        - ACTUAL: Realized EPS
        - GVKEY: Industry identifier
        """
        forecasts_df = pd.DataFrame(forecasts_df)

        # Merge with realized earnings
        realized_lookup = realized_df.set_index(['quarter', 'company'])['realized_eps'].to_dict()

        forecasts_df['realized_eps'] = forecasts_df.apply(
            lambda row: realized_lookup.get((row['quarter'], row['company']), np.nan),
            axis=1
        )

        # Rename to I/B/E/S standard column names
        ibes_format = forecasts_df.rename(columns={
            'company': 'TICKER',
            'analyst_id': 'ESTIMATOR',
            'forecast_date': 'ANNDATS',
            'announcement_date': 'FPEDATS',
            'forecast_eps': 'VALUE',
            'realized_eps': 'ACTUAL',
            'industry': 'GVKEY'
        })

        # Keep only standard I/B/E/S columns + decomposed components (for validation)
        standard_cols = ['TICKER', 'ESTIMATOR', 'ANNDATS', 'FPEDATS', 'VALUE', 'ACTUAL', 'GVKEY']
        decomposed_cols = ['forecast_industry_component', 'forecast_company_component',
                          'true_industry', 'true_company', 'skill_industry', 'skill_company', 'quarter']

        return ibes_format[standard_cols + decomposed_cols]


def create_realistic_ibes_sample(save_to_csv: bool = True) -> pd.DataFrame:
    """
    Create a realistic I/B/E/S sample dataset for testing.

    This simulates what you'll actually see in real I/B/E/S data:
    - Asynchronous analyst updates
    - Heterogeneous coverage
    - Realistic temporal patterns

    Args:
        save_to_csv: If True, save to 'realistic_ibes_sample.csv'

    Returns:
        DataFrame in I/B/E/S format
    """
    config = IBESSimulationConfig(
        n_companies=50,
        n_analysts=30,
        n_quarters=12,  # 3 years
        avg_stocks_per_analyst=15,
        analyst_update_prob_per_week=0.25
    )

    np.random.seed(42)
    simulator = IBESDataSimulator(config)
    ibes_data = simulator.generate_ibes_data()

    if save_to_csv:
        ibes_data.to_csv('realistic_ibes_sample.csv', index=False)
        print(f"✓ Saved {len(ibes_data):,} forecasts to realistic_ibes_sample.csv")
        print(f"  • {ibes_data['TICKER'].nunique()} companies")
        print(f"  • {ibes_data['ESTIMATOR'].nunique()} analysts")
        print(f"  • {ibes_data['quarter'].nunique()} quarters")
        print(f"  • Avg forecasts per company-quarter: {len(ibes_data) / (ibes_data['TICKER'].nunique() * ibes_data['quarter'].nunique()):.1f}")

    return ibes_data


if __name__ == "__main__":
    # Demo: Create realistic I/B/E/S data
    ibes_data = create_realistic_ibes_sample(save_to_csv=True)

    # Show sample
    print("\nSample I/B/E/S records:")
    print(ibes_data[['TICKER', 'ESTIMATOR', 'ANNDATS', 'FPEDATS', 'VALUE', 'ACTUAL', 'GVKEY']].head(10))
