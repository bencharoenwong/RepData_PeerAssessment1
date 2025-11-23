"""
SmartEstimates Simulation with Industry-Company Decomposition
==============================================================

A sophisticated simulation framework for testing decomposed analyst forecast weighting,
where analysts may have differential skill at industry-level vs company-specific forecasting.

Author: Quantitative Research
Date: 2025-11-23
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import Dict, List, Tuple
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import seaborn as sns
from scipy import stats

# Set random seed for reproducibility
np.random.seed(42)

# ============================================================================
# CONFIGURATION
# ============================================================================

@dataclass
class SimulationConfig:
    """Configuration parameters for the simulation."""
    n_companies: int = 50
    n_industries: int = 5
    n_analysts: int = 30
    n_periods: int = 100

    # Analyst skill parameters
    skill_industry_mean: float = 0.6
    skill_industry_std: float = 0.25
    skill_company_mean: float = 0.6
    skill_company_std: float = 0.25
    skill_correlation: float = 0.3  # Correlation between industry and company skills

    # Data generation parameters
    industry_volatility: float = 0.15
    company_volatility: float = 0.25
    forecast_noise_base: float = 0.10

    # Forecast staleness parameters
    update_probability: float = 0.7  # Probability analyst updates each period
    staleness_decay: float = 0.95  # Accuracy decay per period for stale forecasts

    # SmartEstimate parameters
    recency_halflife: int = 30  # days
    min_history: int = 10  # Minimum periods before using historical accuracy
    outlier_threshold: float = 3.0  # Z-score threshold for outlier removal
    winsorize_quantile: float = 0.05  # Winsorize at 5%/95%


# ============================================================================
# DATA GENERATION
# ============================================================================

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

        # Generate analyst skills (correlated bivariate normal)
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

            # Get cross-sectional industry mean (what analysts would observe from peers)
            industry_peer_mean = realized_df[
                (realized_df['period'] == period) &
                (realized_df['industry'] == industry)
            ]['realized_eps'].mean()

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


# ============================================================================
# SMARTESTIMATE CONSTRUCTION
# ============================================================================

class SmartEstimateBuilder:
    """Constructs SmartEstimates with decomposed industry/company weighting."""

    def __init__(self, config: SimulationConfig):
        self.config = config
        self.accuracy_history = {
            'industry': {},  # analyst_id -> list of (period, squared_error)
            'company': {}    # (analyst_id, company) -> list of (period, squared_error)
        }

    def update_accuracy_history(self, forecasts_df: pd.DataFrame, period: int):
        """Update historical accuracy tracking for analysts."""
        period_data = forecasts_df[forecasts_df['period'] == period].copy()

        for _, row in period_data.iterrows():
            analyst_id = row['analyst_id']
            company = row['company']

            # Industry component error
            industry_error = (row['forecast_industry_component'] - row['true_industry']) ** 2
            if analyst_id not in self.accuracy_history['industry']:
                self.accuracy_history['industry'][analyst_id] = []
            self.accuracy_history['industry'][analyst_id].append((period, industry_error))

            # Company component error
            company_error = (row['forecast_company_component'] - row['true_company']) ** 2
            key = (analyst_id, company)
            if key not in self.accuracy_history['company']:
                self.accuracy_history['company'][key] = []
            self.accuracy_history['company'][key].append((period, company_error))

    def compute_analyst_weights(self, analyst_id: str, company: str, current_period: int,
                                component: str) -> float:
        """Compute weight for analyst based on historical accuracy and recency."""
        if component == 'industry':
            history = self.accuracy_history['industry'].get(analyst_id, [])
        else:
            history = self.accuracy_history['company'].get((analyst_id, company), [])

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

        rmse = np.sqrt(np.sum(weighted_errors) / np.sum(weights))

        # Convert RMSE to weight (inverse, with floor)
        weight = 1.0 / (rmse + 0.01)  # Add small constant to prevent division by zero

        return weight

    def construct_smartestimate(self, forecasts_df: pd.DataFrame, period: int,
                                company: str) -> Dict:
        """Construct SmartEstimate for a given company-period using decomposed weighting."""
        period_forecasts = forecasts_df[
            (forecasts_df['period'] == period) &
            (forecasts_df['company'] == company)
        ].copy()

        if len(period_forecasts) == 0:
            return None

        # Compute consensus (simple mean)
        consensus = period_forecasts['forecast_eps'].mean()

        # Decompose each forecast into industry and company components
        # Industry component = cross-sectional industry mean
        industry = period_forecasts['industry'].iloc[0]
        industry_mean = forecasts_df[
            (forecasts_df['period'] == period) &
            (forecasts_df['industry'] == industry)
        ]['forecast_eps'].mean()

        period_forecasts['industry_component'] = industry_mean
        period_forecasts['company_deviation'] = period_forecasts['forecast_eps'] - industry_mean

        # Outlier removal (winsorize extreme deviations)
        deviations = period_forecasts['company_deviation']
        lower = deviations.quantile(self.config.winsorize_quantile)
        upper = deviations.quantile(1 - self.config.winsorize_quantile)
        period_forecasts['company_deviation_winsorized'] = deviations.clip(lower, upper)

        # Compute weights for each analyst
        weights_industry = []
        weights_company = []

        for _, row in period_forecasts.iterrows():
            w_ind = self.compute_analyst_weights(row['analyst_id'], company, period, 'industry')
            w_comp = self.compute_analyst_weights(row['analyst_id'], company, period, 'company')
            weights_industry.append(w_ind)
            weights_company.append(w_comp)

        weights_industry = np.array(weights_industry)
        weights_company = np.array(weights_company)

        # Normalize weights
        weights_industry = weights_industry / weights_industry.sum()
        weights_company = weights_company / weights_company.sum()

        # Construct SmartEstimate
        smart_industry = np.sum(weights_industry * period_forecasts['industry_component'])
        smart_deviation = np.sum(weights_company * period_forecasts['company_deviation_winsorized'])
        smart_estimate = smart_industry + smart_deviation

        return {
            'period': period,
            'company': company,
            'consensus': consensus,
            'smart_estimate': smart_estimate,
            'smart_industry': smart_industry,
            'smart_deviation': smart_deviation,
            'n_analysts': len(period_forecasts),
            'true_eps': period_forecasts['true_eps'].iloc[0]
        }


# ============================================================================
# EVALUATION
# ============================================================================

class PerformanceEvaluator:
    """Evaluate SmartEstimate vs Consensus performance."""

    @staticmethod
    def calculate_metrics(results_df: pd.DataFrame) -> pd.DataFrame:
        """Calculate performance metrics for consensus vs SmartEstimate."""
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
        """Generate summary statistics comparing methods."""
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
                results_df[['consensus', 'true_eps']].corr().iloc[0, 1],
                results_df[['smart_estimate', 'true_eps']].corr().iloc[0, 1]
            ]
        }

        summary = pd.DataFrame(metrics, index=['Consensus', 'SmartEstimate'])

        # Calculate improvement
        improvement = {}
        for metric in metrics.keys():
            if metric == 'Information_Coefficient':
                improvement[metric] = summary.loc['SmartEstimate', metric] - summary.loc['Consensus', metric]
            else:
                improvement[metric] = (summary.loc['Consensus', metric] - summary.loc['SmartEstimate', metric]) / summary.loc['Consensus', metric] * 100

        summary.loc['Improvement_%'] = improvement

        return summary


# ============================================================================
# VISUALIZATION
# ============================================================================

def create_visualizations(analyst_skills: pd.DataFrame, results_df: pd.DataFrame,
                         forecasts_df: pd.DataFrame, config: SimulationConfig):
    """Generate comprehensive visualizations."""

    fig = plt.figure(figsize=(18, 12))

    # 1. Analyst skill distribution
    ax1 = plt.subplot(3, 3, 1)
    scatter = ax1.scatter(analyst_skills['skill_industry'],
                         analyst_skills['skill_company'],
                         c=analyst_skills['archetype'].astype('category').cat.codes,
                         s=100, alpha=0.6, cmap='viridis')
    ax1.set_xlabel('Industry Forecasting Skill')
    ax1.set_ylabel('Company Forecasting Skill')
    ax1.set_title('Analyst Skill Distribution')
    ax1.grid(True, alpha=0.3)
    ax1.axhline(0.5, color='gray', linestyle='--', alpha=0.5)
    ax1.axvline(0.5, color='gray', linestyle='--', alpha=0.5)

    # Add legend for archetypes
    from matplotlib.patches import Patch
    archetype_map = {archetype: i for i, archetype in enumerate(analyst_skills['archetype'].unique())}
    legend_elements = [Patch(facecolor=plt.cm.viridis(i/len(archetype_map)),
                             label=archetype)
                      for archetype, i in archetype_map.items()]
    ax1.legend(handles=legend_elements, loc='upper left', fontsize=8)

    # 2. Forecast error distribution
    ax2 = plt.subplot(3, 3, 2)
    ax2.hist(results_df['error_consensus'], bins=50, alpha=0.5, label='Consensus', density=True)
    ax2.hist(results_df['error_smart'], bins=50, alpha=0.5, label='SmartEstimate', density=True)
    ax2.set_xlabel('Forecast Error')
    ax2.set_ylabel('Density')
    ax2.set_title('Forecast Error Distribution')
    ax2.legend()
    ax2.grid(True, alpha=0.3)

    # 3. RMSE over time
    ax3 = plt.subplot(3, 3, 3)
    results_df['period_group'] = results_df['period'] // 10
    rmse_over_time = results_df.groupby('period_group').agg({
        'se_consensus': lambda x: np.sqrt(x.mean()),
        'se_smart': lambda x: np.sqrt(x.mean())
    })
    ax3.plot(rmse_over_time.index * 10, rmse_over_time['se_consensus'],
             label='Consensus', marker='o')
    ax3.plot(rmse_over_time.index * 10, rmse_over_time['se_smart'],
             label='SmartEstimate', marker='s')
    ax3.set_xlabel('Period')
    ax3.set_ylabel('RMSE')
    ax3.set_title('RMSE Over Time')
    ax3.legend()
    ax3.grid(True, alpha=0.3)

    # 4. Scatter: Consensus vs True
    ax4 = plt.subplot(3, 3, 4)
    sample = results_df.sample(min(500, len(results_df)))
    ax4.scatter(sample['true_eps'], sample['consensus'], alpha=0.3, s=20)
    ax4.plot([-2, 2], [-2, 2], 'r--', alpha=0.5)
    ax4.set_xlabel('True EPS')
    ax4.set_ylabel('Consensus Forecast')
    ax4.set_title('Consensus vs Realized')
    ax4.grid(True, alpha=0.3)

    # 5. Scatter: SmartEstimate vs True
    ax5 = plt.subplot(3, 3, 5)
    ax5.scatter(sample['true_eps'], sample['smart_estimate'], alpha=0.3, s=20)
    ax5.plot([-2, 2], [-2, 2], 'r--', alpha=0.5)
    ax5.set_xlabel('True EPS')
    ax5.set_ylabel('SmartEstimate Forecast')
    ax5.set_title('SmartEstimate vs Realized')
    ax5.grid(True, alpha=0.3)

    # 6. Error reduction by company
    ax6 = plt.subplot(3, 3, 6)
    company_performance = results_df.groupby('company').agg({
        'se_consensus': 'mean',
        'se_smart': 'mean'
    })
    company_performance['improvement'] = (
        (company_performance['se_consensus'] - company_performance['se_smart']) /
        company_performance['se_consensus'] * 100
    )
    ax6.hist(company_performance['improvement'], bins=30, edgecolor='black')
    ax6.set_xlabel('RMSE Improvement (%)')
    ax6.set_ylabel('Number of Companies')
    ax6.set_title('Cross-Sectional Performance Distribution')
    ax6.axvline(0, color='red', linestyle='--', alpha=0.5)
    ax6.grid(True, alpha=0.3)

    # 7. Forecast accuracy by analyst archetype
    ax7 = plt.subplot(3, 3, 7)
    archetype_performance = forecasts_df.copy()
    archetype_performance['squared_error'] = (
        archetype_performance['forecast_eps'] - archetype_performance['true_eps']
    ) ** 2
    archetype_rmse = archetype_performance.groupby('archetype')['squared_error'].apply(
        lambda x: np.sqrt(x.mean())
    ).sort_values()
    archetype_rmse.plot(kind='barh', ax=ax7)
    ax7.set_xlabel('RMSE')
    ax7.set_title('Performance by Analyst Archetype')
    ax7.grid(True, alpha=0.3)

    # 8. Number of analysts over time
    ax8 = plt.subplot(3, 3, 8)
    analysts_per_period = forecasts_df.groupby('period').size()
    ax8.plot(analysts_per_period.index, analysts_per_period.values)
    ax8.set_xlabel('Period')
    ax8.set_ylabel('Number of Forecasts')
    ax8.set_title('Forecast Coverage Over Time')
    ax8.grid(True, alpha=0.3)

    # 9. Improvement distribution
    ax9 = plt.subplot(3, 3, 9)
    results_df['improvement'] = results_df['ae_consensus'] - results_df['ae_smart']
    ax9.hist(results_df['improvement'], bins=50, edgecolor='black')
    ax9.set_xlabel('Absolute Error Reduction')
    ax9.set_ylabel('Frequency')
    ax9.set_title('Period-by-Period Improvement')
    ax9.axvline(0, color='red', linestyle='--', alpha=0.5)
    ax9.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig('/home/user/RepData_PeerAssessment1/smartestimates_analysis.png', dpi=300, bbox_inches='tight')
    print("\n📊 Visualization saved to: smartestimates_analysis.png")

    return fig


# ============================================================================
# MAIN EXECUTION
# ============================================================================

def run_simulation(config: SimulationConfig = None) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Run complete SmartEstimate simulation."""

    if config is None:
        config = SimulationConfig()

    print("=" * 80)
    print("SMARTESTIMATES SIMULATION WITH DECOMPOSED WEIGHTING")
    print("=" * 80)

    # Initialize
    print("\n[1/5] Initializing data generator...")
    simulator = DataSimulator(config)

    print(f"  • {config.n_companies} companies across {config.n_industries} industries")
    print(f"  • {config.n_analysts} analysts with heterogeneous skills")
    print(f"  • {config.n_periods} forecast periods")

    # Generate realized values
    print("\n[2/5] Generating realized EPS data...")
    realized_df = simulator.generate_realized_values()
    print(f"  • Generated {len(realized_df)} company-period realizations")

    # Generate forecasts
    print("\n[3/5] Generating analyst forecasts...")
    forecasts_df = simulator.generate_forecasts(realized_df)
    print(f"  • Generated {len(forecasts_df)} analyst forecasts")
    print(f"  • Average {len(forecasts_df) / len(realized_df):.1f} analysts per company-period")

    # Analyst archetype distribution
    print("\n  Analyst Archetypes:")
    for archetype, count in simulator.analyst_skills['archetype'].value_counts().items():
        print(f"    - {archetype}: {count} analysts")

    # Build SmartEstimates
    print("\n[4/5] Constructing SmartEstimates with decomposed weighting...")
    builder = SmartEstimateBuilder(config)

    results = []
    for period in range(config.n_periods):
        # Update accuracy history with previous period
        if period > 0:
            builder.update_accuracy_history(forecasts_df, period - 1)

        # Construct SmartEstimates for all companies
        companies = forecasts_df[forecasts_df['period'] == period]['company'].unique()
        for company in companies:
            result = builder.construct_smartestimate(forecasts_df, period, company)
            if result is not None:
                results.append(result)

    results_df = pd.DataFrame(results)
    print(f"  • Constructed {len(results_df)} SmartEstimates")

    # Evaluate
    print("\n[5/5] Evaluating performance...")
    evaluator = PerformanceEvaluator()
    results_df = evaluator.calculate_metrics(results_df)
    summary = evaluator.summary_statistics(results_df)

    print("\n" + "=" * 80)
    print("PERFORMANCE SUMMARY")
    print("=" * 80)
    print(summary.to_string())

    # Statistical significance test
    print("\n" + "=" * 80)
    print("STATISTICAL TESTS")
    print("=" * 80)

    # Paired t-test for squared errors
    t_stat, p_value = stats.ttest_rel(results_df['se_consensus'], results_df['se_smart'])
    print(f"\nPaired t-test (Squared Errors):")
    print(f"  • t-statistic: {t_stat:.4f}")
    print(f"  • p-value: {p_value:.6f}")
    print(f"  • Significant at 5%: {'Yes' if p_value < 0.05 else 'No'}")

    # Diebold-Mariano test approximation
    diff = results_df['se_consensus'] - results_df['se_smart']
    dm_stat = diff.mean() / (diff.std() / np.sqrt(len(diff)))
    dm_pvalue = 2 * (1 - stats.norm.cdf(abs(dm_stat)))
    print(f"\nDiebold-Mariano Test:")
    print(f"  • DM statistic: {dm_stat:.4f}")
    print(f"  • p-value: {dm_pvalue:.6f}")

    # Generate visualizations
    print("\n[6/6] Generating visualizations...")
    create_visualizations(simulator.analyst_skills, results_df, forecasts_df, config)

    return results_df, forecasts_df, simulator.analyst_skills


if __name__ == "__main__":
    # Run simulation
    results_df, forecasts_df, analyst_skills = run_simulation()

    # Save results
    print("\n" + "=" * 80)
    print("SAVING RESULTS")
    print("=" * 80)

    results_df.to_csv('/home/user/RepData_PeerAssessment1/smartestimates_results.csv', index=False)
    forecasts_df.to_csv('/home/user/RepData_PeerAssessment1/analyst_forecasts.csv', index=False)
    analyst_skills.to_csv('/home/user/RepData_PeerAssessment1/analyst_skills.csv')

    print("\n✅ Results saved:")
    print("  • smartestimates_results.csv")
    print("  • analyst_forecasts.csv")
    print("  • analyst_skills.csv")
    print("  • smartestimates_analysis.png")

    print("\n" + "=" * 80)
    print("SIMULATION COMPLETE")
    print("=" * 80)
