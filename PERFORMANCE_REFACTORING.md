# Performance Refactoring: O(n²) → O(n)

## 🔴 THE PROBLEM: Why It's O(n²)

### Current Code Structure

```python
# Line 613-623: OUTER LOOPS (run_simulation)
for period in range(config.n_periods):                           # Loop 1: 100 periods
    companies = forecasts_df[forecasts_df['period'] == period]['company'].unique()
    for company in companies:                                     # Loop 2: 50 companies
        result = builder.construct_smartestimate(forecasts_df, period, company)

# Line 291-294: INNER FILTERING (construct_smartestimate) - CALLED 5,000 TIMES
period_forecasts = forecasts_df[
    (forecasts_df['period'] == period) &                          # Scans ALL rows
    (forecasts_df['company'] == company)                          # For EACH company-period
].copy()

# Line 305-308: ANOTHER FILTER - CALLED 5,000 TIMES
industry_forecasts = forecasts_df[
    (forecasts_df['period'] == period) &                          # Scans ALL rows AGAIN
    (forecasts_df['industry'] == industry)                        # For EACH company-period
]['forecast_eps']
```

### Complexity Analysis

**With simulation data:**
- N = 105,252 forecasts (total rows)
- P = 100 periods
- C = 50 companies
- Total iterations: P × C = 5,000

**Each iteration scans the entire DataFrame (N rows):**
- Line 291-294: Scans N rows to filter by (period, company)
- Line 305-308: Scans N rows to filter by (period, industry)
- **Total scans: 5,000 × 2 × 105,252 = 1 BILLION row comparisons**

**With real I/B/E/S data:**
- N = 10,000,000 forecasts
- P = 100 periods
- C = 50,000 companies
- Total iterations: P × C = 5,000,000
- **Total scans: 5,000,000 × 2 × 10,000,000 = 100 TRILLION row comparisons** ⚠️

### Runtime Estimates

| Dataset Size | Current O(n²) | Optimized O(n) |
|-------------|---------------|----------------|
| Simulation (105K rows) | 40 seconds | ~2 seconds |
| Small I/B/E/S (1M rows) | 1 hour | ~30 seconds |
| Medium I/B/E/S (10M rows) | **10+ hours** | ~5 minutes |
| Large I/B/E/S (50M rows) | **50+ hours** | ~20 minutes |

---

## 🟢 THE SOLUTION: Pre-Group and Reuse

### Key Insight

Instead of filtering the entire DataFrame 10,000 times, **group it once** and reuse the groups.

```python
# ❌ BAD: Filter entire DataFrame repeatedly
for period in periods:
    for company in companies:
        subset = df[(df['period'] == period) & (df['company'] == company)]  # O(N) scan

# ✅ GOOD: Group once, iterate over groups
grouped = df.groupby(['period', 'company'])  # O(N) - one pass
for (period, company), group in grouped:     # O(P×C) - iterate groups
    # group is already filtered! No scanning needed
```

### Complexity Improvement

**Current approach:**
- Outer loops: O(P × C)
- Inner filtering per iteration: O(N)
- **Total: O(P × C × N) ≈ O(N²)** when P×C ~ N

**Optimized approach:**
- Group once: O(N)
- Iterate groups: O(P × C)
- Process each group: O(analysts per group) ≈ O(1) average
- **Total: O(N) + O(P × C) = O(N)**

---

## 📊 Visual Comparison

### Current O(n²) Approach

```
forecasts_df (105,252 rows)
     ↓
[Period 0 loop]
     ↓
  [Company AAPL] → Filter entire 105K rows → Extract ~20 rows
  [Company MSFT] → Filter entire 105K rows → Extract ~20 rows
  [Company GOOG] → Filter entire 105K rows → Extract ~20 rows
  ... (50 companies × 105K scans = 5.25 million row comparisons)
     ↓
[Period 1 loop]
  [Company AAPL] → Filter entire 105K rows → Extract ~20 rows
  ... (repeat 5.25 million scans)
     ↓
... (100 periods)

TOTAL: 100 × 50 × 105K = 525 MILLION row scans
```

### Optimized O(n) Approach

```
forecasts_df (105,252 rows)
     ↓
  [GROUP BY period, company] → ONE pass through data (105K rows)
     ↓
grouped_data (5,000 groups, each ~20 rows)
     ↓
[Iterate over 5,000 pre-grouped chunks]
  (Period 0, AAPL) → Already extracted (20 rows)
  (Period 0, MSFT) → Already extracted (20 rows)
  (Period 0, GOOG) → Already extracted (20 rows)
  ...
  (Period 99, AAPL) → Already extracted (20 rows)

TOTAL: 105K rows scanned ONCE + 5,000 group iterations
```

---

## 💻 OPTIMIZED IMPLEMENTATION

See `smartestimates_simulation_optimized.py` for the complete refactored version.

### Key Changes

#### 1. Pre-compute Industry Means (One Pass)

**Before (O(n²)):**
```python
# Lines 305-308 - Called 5,000 times, each scans 105K rows
industry_forecasts = forecasts_df[
    (forecasts_df['period'] == period) &
    (forecasts_df['industry'] == industry)
]['forecast_eps'].mean()
```

**After (O(n)):**
```python
# Computed ONCE before loop
industry_means = forecasts_df.groupby(['period', 'industry'])['forecast_eps'].mean()

# Then lookup (O(1))
industry_mean = industry_means.loc[(period, industry)]
```

#### 2. Group by (Period, Company) Once

**Before (O(n²)):**
```python
for period in range(config.n_periods):
    companies = forecasts_df[forecasts_df['period'] == period]['company'].unique()  # Scan N rows
    for company in companies:
        period_forecasts = forecasts_df[                                             # Scan N rows AGAIN
            (forecasts_df['period'] == period) &
            (forecasts_df['company'] == company)
        ]
```

**After (O(n)):**
```python
# Group once
grouped = forecasts_df.groupby(['period', 'company'])

# Iterate pre-grouped data
for (period, company), period_forecasts in grouped:
    # period_forecasts is already filtered!
```

#### 3. Vectorized Weight Calculation

**Before (O(m) per group, iterrows):**
```python
weights_industry = []
for _, row in period_forecasts.iterrows():  # iterrows is slow
    w = self.compute_analyst_weights(row['analyst_id'], company, period, 'industry')
    weights_industry.append(w)
```

**After (O(m) per group, vectorized):**
```python
# Pre-compute all weights as DataFrame, merge once
analyst_weights_df = self._get_weights_batch(period_forecasts, period, company)
period_forecasts = period_forecasts.merge(analyst_weights_df, on='analyst_id')

# Now weights are columns, can use vectorized operations
weights_industry = period_forecasts['weight_industry'].values
```

---

## 🚀 IMPLEMENTATION STRATEGY

### Phase 1: Drop-in Replacement (Minimal Changes)

Create `construct_smartestimate_optimized()` that:
1. Pre-computes industry means at the beginning
2. Uses `.groupby()` instead of filtering
3. Maintains same API and outputs

**Effort:** 1-2 days
**Speedup:** 10-50x

### Phase 2: Full Vectorization

Refactor entire pipeline to:
1. Process all periods/companies in parallel
2. Batch weight lookups
3. Use NumPy operations where possible

**Effort:** 1 week
**Speedup:** 100-500x

### Phase 3: Distributed Processing (If Needed)

For truly massive datasets (100M+ rows):
1. Use Dask or Spark for distributed groupby
2. Partition by period for parallel processing
3. Database backend for accuracy history

**Effort:** 2-3 weeks
**Speedup:** 1000x+ (scales horizontally)

---

## 📋 REFACTORING CHECKLIST

- [ ] Pre-compute industry means before main loop
- [ ] Replace nested loops with `.groupby(['period', 'company'])`
- [ ] Cache accuracy weights in memory (or database)
- [ ] Vectorize weight calculations where possible
- [ ] Remove `.iterrows()` (replace with `.apply()` or vectorized ops)
- [ ] Use `.loc` instead of boolean indexing for lookups
- [ ] Add progress bar for long-running operations
- [ ] Benchmark on real I/B/E/S data sample (1M rows)
- [ ] Update tests to cover both implementations
- [ ] Document performance characteristics

---

## 🧪 TESTING THE OPTIMIZATION

```python
import time

# Test current implementation
start = time.time()
results_old = run_simulation(config)
time_old = time.time() - start

# Test optimized implementation
start = time.time()
results_new = run_simulation_optimized(config)
time_new = time.time() - start

# Verify results match
assert np.allclose(results_old['smart_estimate'], results_new['smart_estimate'])

# Report speedup
print(f"Old: {time_old:.1f}s")
print(f"New: {time_new:.1f}s")
print(f"Speedup: {time_old/time_new:.1f}x")
```

---

## 📖 REFERENCES

- [Pandas Performance Guide](https://pandas.pydata.org/pandas-docs/stable/user_guide/enhancingperf.html)
- [Optimizing Pandas Groupby](https://realpython.com/pandas-groupby/)
- [Avoiding .iterrows()](https://stackoverflow.com/questions/16476924/how-to-iterate-over-rows-in-a-dataframe-in-pandas)
- [NumPy Broadcasting](https://numpy.org/doc/stable/user/basics.broadcasting.html)

---

**Next:** See `smartestimates_simulation_optimized.py` for working implementation.
