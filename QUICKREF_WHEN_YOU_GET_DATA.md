# Quick Reference: When You Get Your I/B/E/S Data

## The Exact Code You'll Run

```python
from smartestimates import IBESDataLoader, RealDataSmartEstimateEngine, PerformanceEvaluator

# ============================================================================
# STEP 1: LOAD YOUR DATA
# ============================================================================

loader = IBESDataLoader()

# Map YOUR column names to standard names
raw = loader.load_ibes_detail_file(
    'YOUR_IBES_FILE.csv',       # ← Your file path
    ticker_col='TICKER',         # ← Your ticker column name
    analyst_col='ESTIMATOR',     # ← Your analyst column name
    forecast_date_col='ANNDATS', # ← Your forecast date column name
    fiscal_period_col='FPEDATS', # ← Your fiscal period column name
    estimate_col='VALUE',        # ← Your EPS forecast column name
    actual_col='ACTUAL',         # ← Your realized EPS column name
    industry_col='GVKEY'         # ← Your industry column name
)

# ============================================================================
# STEP 2: CLEAN YOUR DATA
# ============================================================================

clean = loader.preprocess_ibes_data(
    raw,
    min_analysts=5,         # Require at least 5 analysts per stock
    max_horizon_days=180,   # Forecasts within 180 days of earnings
    winsorize_pct=0.01      # Remove extreme 1% outliers
)

# ============================================================================
# STEP 3: BUILD SMARTESTIMATES (AUTO-DECOMPOSITION!)
# ============================================================================

engine = RealDataSmartEstimateEngine()

results = engine.compute_smartestimates(
    clean,
    include_actuals=True,   # Include realized EPS for evaluation
    auto_decompose=True     # AUTOMATIC DECOMPOSITION (default)
)

# ============================================================================
# STEP 4: EVALUATE PERFORMANCE
# ============================================================================

evaluator = PerformanceEvaluator()

# Summary statistics
summary = evaluator.summary_statistics(results)
print("\n" + "=" * 70)
print("SMARTESTIMATES PERFORMANCE SUMMARY")
print("=" * 70)
print(summary)
print("=" * 70)

# Statistical test
dm_test = evaluator.diebold_mariano_test(results)
print(f"\nDiebold-Mariano Test: {dm_test['message']}")
print(f"  Statistic: {dm_test['statistic']:.2f}")
print(f"  P-value:   {dm_test['p_value']:.4f}")

# ============================================================================
# STEP 5: SAVE RESULTS
# ============================================================================

results.to_csv('smartestimates_output.csv', index=False)
print(f"\n✅ Saved {len(results):,} SmartEstimates to smartestimates_output.csv")
```

---

## Column Mapping Checklist

Before running, identify these columns in YOUR data:

| What You Need | Common Names | Your Column Name |
|--------------|--------------|------------------|
| Company ticker | TICKER, CUSIP, PERMNO, ISIN | _______________ |
| Analyst ID | ESTIMATOR, ANALYS, ANALYST_ID | _______________ |
| Forecast date | ANNDATS, REVDATS, EST_DATE | _______________ |
| Fiscal period | FPEDATS, ANNDATS_ACT, EARNINGS_DATE | _______________ |
| EPS forecast | VALUE, MEANEST, EPS_FORECAST | _______________ |
| Realized EPS | ACTUAL, VALUE_ACT, REPORTED_EPS | _______________ |
| Industry code | GVKEY, SIC, GICS, SECTOR | _______________ |

**Fill in the blanks above, then update the column names in Step 1.**

---

## Typical Runtime Estimates

| # Forecasts | Runtime | Memory |
|-------------|---------|--------|
| 10K | ~5 sec | < 100 MB |
| 100K | ~30 sec | < 500 MB |
| 1M | ~5 min | < 2 GB |
| 10M | ~45 min | < 5 GB |

---

## Expected Output Columns

Your `results` DataFrame will have:

```python
results.columns
# ['period', 'company', 'consensus', 'smart_estimate',
#  'smart_industry', 'smart_deviation', 'n_analysts', 'true_eps',
#  'error_consensus', 'error_smart', 'se_consensus', 'se_smart',
#  'ae_consensus', 'ae_smart']
```

**Key columns:**
- `consensus` - Simple mean (baseline)
- `smart_estimate` - ⭐ Your skill-weighted forecast
- `true_eps` - Actual EPS (if available)
- `error_smart` - Forecast error (smart_estimate - true_eps)

---

## Troubleshooting Quick Fixes

### Error: `KeyError: 'TICKER'`
**Fix:** Your ticker column has a different name. Update `ticker_col` parameter.

### Error: `KeyError: 'period'`
**Fix:** Always run `preprocess_ibes_data()` before `compute_smartestimates()`.

### Error: `No SmartEstimates generated`
**Fix:** Lower `min_analysts` threshold (try 3 instead of 5).

### Warning: `Not enough history for accuracy tracking`
**Fix:** Normal for early periods. Skill-based weighting starts after 10 periods.

### Result: `SmartEstimate == Consensus`
**Fix:**
1. Check `auto_decompose=True` (should be default)
2. Wait for more periods (need 10+ for accuracy history)
3. Verify you have industry codes (required for decomposition)

---

## Performance Check

After running, check if it's working:

```python
# 1. Check you got results
print(f"Generated {len(results):,} SmartEstimates")

# 2. Check SmartEstimate differs from consensus
diff = (results['smart_estimate'] - results['consensus']).abs().mean()
print(f"Average difference: {diff:.4f}")
# Should be > 0.01 after 10+ periods

# 3. Check improvement
if 'true_eps' in results.columns:
    consensus_rmse = np.sqrt((results['error_consensus']**2).mean())
    smart_rmse = np.sqrt((results['error_smart']**2).mean())
    improvement = (consensus_rmse - smart_rmse) / consensus_rmse * 100
    print(f"RMSE Improvement: {improvement:.2f}%")
    # Should be 5-15% typically
```

---

## What to Expect

### First Run (periods 0-9)
- SmartEstimate ≈ Consensus (not enough history yet)
- Equal weights for all analysts
- Building accuracy history

### After 10+ Periods
- SmartEstimate starts diverging from consensus
- Skill-based weighting kicks in
- Macro specialists weighted more on industry
- Stock pickers weighted more on company deviations
- Performance improves vs consensus

### After 20+ Periods
- Full skill differentiation
- Stable accuracy estimates
- Maximum performance improvement

---

## Save Your Configuration

Once you've mapped your columns, save this for future runs:

```python
# config.py
IBES_FILE = 'YOUR_IBES_FILE.csv'

COLUMN_MAPPING = {
    'ticker_col': 'YOUR_TICKER_COL',
    'analyst_col': 'YOUR_ANALYST_COL',
    'forecast_date_col': 'YOUR_FORECAST_DATE_COL',
    'fiscal_period_col': 'YOUR_FISCAL_PERIOD_COL',
    'estimate_col': 'YOUR_ESTIMATE_COL',
    'actual_col': 'YOUR_ACTUAL_COL',
    'industry_col': 'YOUR_INDUSTRY_COL'
}

PREPROCESS_CONFIG = {
    'min_analysts': 5,
    'max_horizon_days': 180,
    'winsorize_pct': 0.01
}

# Then use:
# raw = loader.load_ibes_detail_file(IBES_FILE, **COLUMN_MAPPING)
# clean = loader.preprocess_ibes_data(raw, **PREPROCESS_CONFIG)
```

---

## You're Ready! 🚀

**Just run the code above when you get your I/B/E/S data.**

Auto-decomposition handles the rest automatically.
