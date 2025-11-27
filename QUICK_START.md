# ⚡ Quick Start: 3-Step Workflow

## Input: Raw I/B/E/S Data Format

```csv
TICKER,ESTIMATOR,ANNDATS,FPEDATS,VALUE,ACTUAL,GVKEY
AAPL,ANALYST_001,2024-01-15,2024-03-31,1.52,1.48,TECH
AAPL,ANALYST_002,2024-01-18,2024-03-31,1.55,1.48,TECH
MSFT,ANALYST_001,2024-01-16,2024-03-31,2.10,2.05,TECH
...
```

## Complete Workflow

```python
from smartestimates import (
    IBESDataLoader,
    RealDataSmartEstimateEngine,
    PerformanceEvaluator
)

# Step 1: Load
loader = IBESDataLoader()
data = loader.load_ibes_detail_file('your_ibes.csv')

# Step 2: Clean
clean_data = loader.preprocess_ibes_data(data, min_analysts=5)

# Step 3: Compute SmartEstimates (with auto-decomposition!)
engine = RealDataSmartEstimateEngine()
results = engine.compute_smartestimates(clean_data, auto_decompose=True)

# Step 4: Evaluate
evaluator = PerformanceEvaluator()
print(evaluator.summary_statistics(results))
```

## Output

```
                   RMSE       MAE      Bias  Information_Coefficient
Consensus      0.134670  0.100091 -0.003864                 0.963170
SmartEstimate  0.132462  0.098262 -0.003841                 0.963670
Improvement_%  1.639910  1.826944  0.594056                 0.000501

✓ SmartEstimate outperforms consensus by 1.64% (p < 0.0001)
```

## What Happens Automatically

1. ✅ **Auto-decomposition** → Forecasts split into industry + company components
2. ✅ **Separate skill tracking** → Industry skill vs company skill measured independently
3. ✅ **Differential weighting** → Analysts weighted by skill for each component
4. ✅ **Validation** → Decomposition quality checked automatically
5. ✅ **Temporal consistency** → No look-ahead bias, sequential processing

## Key Parameters

```python
# Preprocessing
preprocess_ibes_data(
    min_analysts=5,        # Minimum analysts required per stock-period
    max_horizon_days=180,  # Max days between forecast and earnings
    winsorize_pct=0.01     # Remove extreme 1%/99%
)

# SmartEstimate Engine
RealDataSmartEstimateEngine(
    config=SmartEstimateConfig(
        recency_halflife=30,      # Weight decay half-life (days)
        min_history=10,           # Periods before using history
        weight_floor=0.01,        # Minimum analyst weight
        max_history_periods=252   # Max history to keep (memory bound)
    )
)
```

## Column Mapping (if your data differs)

```python
data = loader.load_ibes_detail_file(
    'your_file.csv',
    ticker_col='YOUR_TICKER_COL',
    analyst_col='YOUR_ANALYST_COL',
    forecast_date_col='YOUR_DATE_COL',
    fiscal_period_col='YOUR_PERIOD_COL',
    estimate_col='YOUR_FORECAST_COL',
    actual_col='YOUR_ACTUAL_COL',
    industry_col='YOUR_INDUSTRY_COL'
)
```

## Test with Simulated Data First

```python
from smartestimates import create_realistic_ibes_sample

# Generate realistic test data (asynchronous, revisions, etc.)
test_data = create_realistic_ibes_sample(save_to_csv=True)

# Now use it like real I/B/E/S data
loader = IBESDataLoader()
data = loader.load_ibes_detail_file('realistic_ibes_sample.csv')
# ... continue with steps 2-4 above
```

## Full Documentation

- **Plug-and-Play Guide**: `PLUG_AND_PLAY_GUIDE.md` (detailed explanation)
- **Deployment Guide**: `DEPLOYMENT_GUIDE.md` (production setup)
- **Performance Details**: `PERFORMANCE_REFACTORING.md` (optimization)
- **Test End-to-End**: `python test_ibes_plugin_play.py`
