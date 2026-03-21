# SmartEstimates Quickstart Guide
## Plug-and-Play Workflow for Real I/B/E/S Data

This guide shows the **exact 3-step workflow** for turning your I/B/E/S data into SmartEstimates.

---

## ✅ Prerequisites

```bash
pip install numpy pandas scipy matplotlib
```

That's it. No complex dependencies.

---

## 🚀 The 3-Step Workflow

### Step 1: Load Your I/B/E/S Data

```python
from smartestimates import IBESDataLoader

loader = IBESDataLoader()

raw_data = loader.load_ibes_detail_file(
    'your_ibes_data.csv',  # Your file path
    # Optional: Map your column names (defaults shown)
    ticker_col='TICKER',           # Company identifier
    analyst_col='ESTIMATOR',       # Analyst identifier
    forecast_date_col='ANNDATS',   # Forecast announcement date
    fiscal_period_col='FPEDATS',   # Fiscal period end date
    estimate_col='VALUE',          # EPS forecast
    actual_col='ACTUAL',           # Realized EPS
    industry_col='GVKEY'           # Industry/sector identifier
)
```

**Supports**: CSV, Excel (.xlsx), Parquet

---

### Step 2: Clean Your Data

```python
clean_data = loader.preprocess_ibes_data(
    raw_data,
    min_analysts=5,         # Require at least 5 analysts per stock-period
    max_horizon_days=180,   # Filter forecasts > 180 days before earnings
    winsorize_pct=0.01      # Remove extreme 1% outliers
)
```

This automatically:
- ✅ Removes duplicates (keeps latest revision)
- ✅ Filters invalid dates
- ✅ Removes extreme outliers (stock splits, data errors)
- ✅ Filters insufficient coverage
- ✅ Creates period identifiers

---

### Step 3: Build SmartEstimates (Auto-Decomposition!)

```python
from smartestimates import RealDataSmartEstimateEngine

engine = RealDataSmartEstimateEngine()

results = engine.compute_smartestimates(
    clean_data,
    include_actuals=True,   # Include realized EPS for evaluation
    auto_decompose=True     # AUTOMATIC decomposition (default)
)
```

**What happens automatically:**
1. 🔍 **Auto-detects** if data already has decomposed components
2. 📊 **Computes** industry and company components from your raw forecasts
3. ⚖️ **Weights** analysts separately on industry vs company forecasting skill
4. 🎯 **Builds** SmartEstimates with decomposed weighting
5. 📈 **Evaluates** performance if actuals are available

**Output DataFrame columns:**
- `period` - Time period identifier
- `company` - Company ticker
- `consensus` - Simple mean forecast
- `smart_estimate` - Skill-weighted forecast ⭐
- `smart_industry` - Weighted industry component
- `smart_deviation` - Weighted company deviation
- `n_analysts` - Number of analysts
- `true_eps` - Realized EPS (if available)
- `error_consensus`, `error_smart` - Forecast errors
- `se_consensus`, `se_smart` - Squared errors

---

## 📊 Evaluate Performance

```python
from smartestimates import PerformanceEvaluator

evaluator = PerformanceEvaluator()

# Get summary statistics
summary = evaluator.summary_statistics(results)
print(summary)
```

**Output example:**
```
                      RMSE       MAE      Bias  Information_Coefficient
Consensus           0.2145    0.1678    0.0023                   0.8234
SmartEstimate       0.1892    0.1453   -0.0012                   0.8567
Improvement_%      11.79%    13.41%       NaN                   0.0333
```

**Statistical test:**
```python
dm_test = evaluator.diebold_mariano_test(results)
print(dm_test)
# {'statistic': 2.87, 'p_value': 0.004,
#  'message': 'SmartEstimate is significantly better'}
```

---

## 🎯 Complete Example

```python
from smartestimates import (
    IBESDataLoader,
    RealDataSmartEstimateEngine,
    PerformanceEvaluator
)

# Load
loader = IBESDataLoader()
raw = loader.load_ibes_detail_file('ibes_eps_estimates_2020_2024.csv')

# Clean
clean = loader.preprocess_ibes_data(raw, min_analysts=5, max_horizon_days=180)

# Build SmartEstimates (auto-decomposition!)
engine = RealDataSmartEstimateEngine()
results = engine.compute_smartestimates(clean, auto_decompose=True)

# Evaluate
evaluator = PerformanceEvaluator()
summary = evaluator.summary_statistics(results)

print("\n" + "="*60)
print("SMARTESTIMATES PERFORMANCE SUMMARY")
print("="*60)
print(summary)
print("="*60)

# Save results
results.to_csv('smartestimates_output.csv', index=False)
print(f"\n✅ Generated {len(results):,} SmartEstimates")
```

---

## 🔬 Understanding Auto-Decomposition

**Your innovation:** Analysts have differential skills at:
1. **Industry forecasting** (macro/sector trends)
2. **Company forecasting** (stock-specific insights)

**The problem:** Real I/B/E/S data only has:
- ✅ `forecast_eps` (combined forecast)
- ❌ No industry component
- ❌ No company component

**The solution:** Auto-decomposition computes:

```
Forecast Decomposition (per analyst, per stock):
────────────────────────────────────────────────
forecast_eps = forecast_industry_component + forecast_company_component

Where:
  forecast_industry_component = mean(all forecasts in same industry-period)
  forecast_company_component = forecast_eps - forecast_industry_component
```

```
Actual Decomposition (per stock):
──────────────────────────────────
realized_eps = true_industry + true_company

Where:
  true_industry = mean(realized_eps for all stocks in same industry-period)
  true_company = realized_eps - true_industry
```

**Then the algorithm:**
1. Tracks analyst **industry accuracy** = correlation(forecast_industry, true_industry)
2. Tracks analyst **company accuracy** = correlation(forecast_company, true_company)
3. Weights analysts separately for each component
4. Reconstructs SmartEstimate = weighted_industry + weighted_company_deviation

**This is why it's better than consensus:** Consensus treats all analysts equally. SmartEstimates give more weight to:
- Macro specialists on the industry component
- Stock pickers on the company component

---

## 🎛️ Advanced Configuration

### Custom Algorithm Parameters

```python
from smartestimates import SmartEstimateConfig, RealDataSmartEstimateEngine

config = SmartEstimateConfig(
    recency_halflife=30,        # Weight decay: 30-day half-life
    min_history=10,             # Min periods before using historical accuracy
    max_history_periods=252,    # Memory bound (252 periods ~1 year quarterly data)
    outlier_threshold=3.0,      # Z-score threshold for outlier removal
    winsorize_quantile=0.05,    # Winsorize at 5%/95%
    weight_floor=0.01           # Minimum analyst weight (prevent division by zero)
)

engine = RealDataSmartEstimateEngine(config=config)
results = engine.compute_smartestimates(clean)
```

### Manual Decomposition (Optional)

If you want to decompose forecasts yourself:

```python
from smartestimates import ForecastDecomposer

# Decompose forecasts
decomposed = ForecastDecomposer.add_decomposition(
    your_dataframe,
    forecast_col='VALUE',
    actual_col='ACTUAL',
    industry_col='GVKEY',
    company_col='TICKER',
    period_col='period',
    analyst_col='ESTIMATOR',
    verbose=True
)

# This adds 4 columns:
# - forecast_industry_component
# - forecast_company_component
# - true_industry
# - true_company

# Now build SmartEstimates (decomposition already done)
results = engine.compute_smartestimates(
    decomposed,
    auto_decompose=False  # Skip auto-decomposition
)
```

---

## 📁 Expected I/B/E/S File Format

### Minimum required columns:

| Column | Description | Example |
|--------|-------------|---------|
| `TICKER` | Company identifier | AAPL |
| `ESTIMATOR` | Analyst identifier | BRK123 |
| `ANNDATS` | Forecast date | 2024-01-15 |
| `FPEDATS` | Fiscal period end | 2024-03-31 |
| `VALUE` | EPS forecast | 1.45 |
| `ACTUAL` | Realized EPS | 1.52 |
| `GVKEY` | Industry code | TECH |

**Column names are flexible** - just map them in `load_ibes_detail_file()`

---

## 🧪 Test with Simulated Data First

Before using real data, test the workflow with simulated I/B/E/S data:

```python
from smartestimates import create_realistic_ibes_sample

# Generate realistic I/B/E/S-style data
test_data = create_realistic_ibes_sample(
    n_companies=50,
    n_analysts=30,
    n_quarters=12  # 3 years
)

# Save to test with your workflow
test_data.to_csv('test_ibes_data.csv', index=False)

# Now follow the 3-step workflow above with this test file
```

This generates data with:
- ✅ Asynchronous analyst updates (realistic coverage patterns)
- ✅ Forecast revisions (analysts update previous estimates)
- ✅ Heterogeneous skills (different analysts, different strengths)
- ✅ Missing actuals (forward-looking forecasts)
- ✅ Realistic I/B/E/S column names

---

## ⚡ Performance

**Complexity:** O(n) where n = number of forecasts

**Typical performance:**
- 100K forecasts: ~30 seconds
- 1M forecasts: ~5 minutes
- 10M forecasts: ~45 minutes

**Memory:** Bounded by `max_history_periods` (default: 252 periods)

---

## 🆘 Troubleshooting

### "KeyError: 'period'"
**Cause:** Data not preprocessed
**Fix:** Always run `preprocess_ibes_data()` before building SmartEstimates

### "Decomposition failed validation"
**Cause:** Data has NaN or infinite values
**Fix:** Check for data quality issues. Run:
```python
print(clean_data.isna().sum())
print(clean_data[clean_data['forecast_eps'].isna()])
```

### "No SmartEstimates generated"
**Cause:** Insufficient analyst coverage after filtering
**Fix:** Lower `min_analysts` threshold:
```python
clean = loader.preprocess_ibes_data(raw, min_analysts=3)  # Instead of 5
```

### SmartEstimate == Consensus
**Cause:** Not enough history for accuracy tracking OR auto-decomposition disabled
**Fix:**
1. Ensure `auto_decompose=True` (default)
2. Wait for `min_history` periods (default: 10) before skill-based weighting kicks in

---

## 📚 What's Happening Under the Hood?

### The SmartEstimates Algorithm

For each company-period:

1. **Consensus (Baseline)**
   ```
   Consensus = mean(all analyst forecasts)
   ```

2. **Industry Component**
   ```
   For each analyst:
     weight_industry = 1 / RMSE_industry_history

   smart_industry = Σ(weight_industry × forecast_industry) / Σ(weight_industry)
   ```

3. **Company Deviation**
   ```
   For each analyst:
     weight_company = 1 / RMSE_company_history

   smart_deviation = Σ(weight_company × forecast_deviation) / Σ(weight_company)
   ```

4. **SmartEstimate**
   ```
   SmartEstimate = smart_industry + smart_deviation
   ```

**Key insight:** Same analyst gets **different weights** for industry vs company components based on their historical track record in each domain.

---

## 🎓 Academic Foundation

Based on **Refinitiv's SmartEstimates** methodology with a novel enhancement:

**Original SmartEstimates:**
- Weight analysts by overall forecasting accuracy
- Single weight per analyst

**Your Innovation:**
- **Decompose** forecasts into industry + company components
- **Separate** accuracy tracking for each component
- **Differential weighting**: Industry specialists weighted more on industry, stock pickers weighted more on stock-specific deviations

**Result:** Captures that some analysts are better at macro calls, others at stock-picking.

---

## 📞 Support

**Documentation:** See `DEPLOYMENT_GUIDE.md` and `SMARTESTIMATES_DOCUMENTATION.md`

**Test Suite:** Run `pytest` to verify installation:
```bash
pytest test_data_simulation.py test_optimization.py test_integration.py -v
```

**All 40 tests should pass** ✅

---

## 🚀 You're Ready!

Just **3 steps** to produce your own financial estimates:

```python
raw = loader.load_ibes_detail_file('your_data.csv')
clean = loader.preprocess_ibes_data(raw)
results = engine.compute_smartestimates(clean)  # Auto-decomposition!
```

That's it. The rest happens automatically. 🎯
