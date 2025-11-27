# Systematic Historical Extraction Guide

## Overview

This guide shows how to systematically extract SEC filings over time, including delisted companies, to cast the widest possible net for detecting geographic revenue methodology changes.

---

## Key Concepts

### 1. CIK vs Ticker

**Ticker (NVDA, AAPL, etc.)**:
- Can change when companies rebrand
- Disappears when companies delist
- Not suitable for historical/delisted company research

**CIK (Central Index Key)**:
- Permanent identifier assigned by SEC
- Never changes, even after delisting
- **Use CIK for systematic historical research**

**Example:**
- **Twitter** → Ticker changed from TWTR → delisted → merged into X
- **CIK: 1418091** → Works for all historical filings regardless of ticker changes

### 2. Date Range Queries

The Query API supports date range filtering:

```python
query = {
    "query": "cik:1045810 AND formType:(10-Q OR 10-K) AND filedAt:[2020-01-01 TO 2025-12-31]",
    "from": "0",
    "size": "100",  # Can go up to 200
    "sort": [{"filedAt": {"order": "desc"}}]
}
```

**Benefits:**
- Get ALL filings in a time window (not just 2 most recent)
- Can go back years to detect historical methodology changes
- Can paginate through results using "from" parameter

### 3. Pagination for Large Result Sets

If a company has >200 filings in your date range:

```python
# First batch
query["from"] = "0"
query["size"] = "200"
batch1 = get_filings(query)

# Second batch
query["from"] = "200"
query["size"] = "200"
batch2 = get_filings(query)

# Continue until no more results
```

---

## Systematic Extraction Strategies

### Strategy 1: All Filings for Specific Companies Over Time

**Use case**: You have a list of 100 companies, want to check ALL their filings from 2015-2025

```python
def extract_all_filings_for_company(cik, start_date, end_date):
    """
    Get all 10-Q and 10-K filings for a company in date range

    Args:
        cik: Central Index Key (e.g., "1045810" for Nvidia)
        start_date: "2015-01-01"
        end_date: "2025-12-31"

    Returns:
        List of all filings in range
    """

    all_filings = []
    from_index = 0
    batch_size = 200

    while True:
        query = {
            "query": f"cik:{cik} AND formType:(10-Q OR 10-K) AND filedAt:[{start_date} TO {end_date}]",
            "from": str(from_index),
            "size": str(batch_size),
            "sort": [{"filedAt": {"order": "desc"}}]
        }

        results = query_api(query)

        if not results or len(results) == 0:
            break

        all_filings.extend(results)

        if len(results) < batch_size:
            # No more results
            break

        from_index += batch_size

    return all_filings
```

**Example output**: Nvidia might have 40+ filings from 2015-2025 (4 per year × 10 years)

### Strategy 2: Including Delisted Companies

**Problem**: Delisted companies don't have active tickers
**Solution**: Use CIK codes

**How to get CIK codes:**

1. **Manual lookup**: https://www.sec.gov/cgi-bin/browse-edgar?company=&CIK=&type=&dateb=&owner=exclude&count=40&search_text=
2. **Ticker to CIK mapping files**: SEC provides company list
3. **Historical databases**: Capital IQ, Compustat have ticker→CIK mappings

**Example delisted companies:**

| Company | Ticker (historical) | CIK | Delisted Date |
|---------|---------------------|-----|---------------|
| Toys R Us | - | 0001005414 | 2018 |
| Sears | SHLDQ | 0001310067 | 2018 |
| RadioShack | - | 0001015922 | 2015 |
| Borders Books | - | 0001013488 | 2011 |

**Scanner modification for delisted companies:**

```python
# Instead of this:
scanner.scan_company("NVDA")  # Won't work for delisted

# Use this:
scanner.scan_company_by_cik("1045810", company_name="NVIDIA")  # Works always
```

### Strategy 3: Systematic Universe Scan

**Use case**: Scan entire Russell 3000 or S&P 500 over 10 years

**Approach:**

```python
# 1. Get list of CIKs for your universe
sp500_ciks = [
    "1045810",  # NVDA
    "320193",   # AAPL
    "789019",   # MSFT
    # ... 497 more
]

# 2. Define time window
start = "2015-01-01"
end = "2025-12-31"

# 3. Systematic scan
results = {}
for cik in sp500_ciks:
    filings = extract_all_filings_for_company(cik, start, end)

    for filing in filings:
        # Extract and analyze each filing
        content = extract_filing_section(filing['url'])
        findings = search_for_accounting_changes(content)

        if findings.get('geographic_revenue'):
            results[cik] = findings
```

**Estimated scale:**
- 500 companies × 40 filings each = 20,000 filings
- At 2 seconds per filing = ~11 hours total
- API rate limits: Likely need to batch this over days

---

## Enhanced Scanner with Historical Support

### New Features Needed

```python
class HistoricalAccountingScanner:
    """Enhanced scanner with CIK support and date ranges"""

    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://api.sec-api.io"

    def scan_company_by_cik(self, cik, start_date=None, end_date=None, company_name=None):
        """
        Scan using CIK (works for delisted companies)

        Args:
            cik: Central Index Key
            start_date: "2015-01-01" (optional, defaults to all time)
            end_date: "2025-12-31" (optional, defaults to today)
            company_name: Optional display name
        """

        # Build query
        date_filter = ""
        if start_date and end_date:
            date_filter = f" AND filedAt:[{start_date} TO {end_date}]"

        query = {
            "query": f"cik:{cik} AND formType:(10-Q OR 10-K){date_filter}",
            "from": "0",
            "size": "200",
            "sort": [{"filedAt": {"order": "desc"}}]
        }

        # Get all filings
        filings = self.query_api(query)

        # Process each filing
        results = []
        for filing in filings:
            content = self.extract_filing(filing['linkToFilingDetails'], filing['formType'])
            findings = self.search_for_accounting_changes(content)

            if findings:
                results.append({
                    'cik': cik,
                    'company_name': company_name or filing.get('companyName', 'Unknown'),
                    'filing_date': filing['filedAt'],
                    'form_type': filing['formType'],
                    'url': filing['linkToFilingDetails'],
                    'findings': findings
                })

        return results

    def scan_universe(self, cik_list, start_date, end_date, output_file):
        """
        Scan entire universe of companies

        Args:
            cik_list: List of tuples [(cik, company_name), ...]
            start_date: "2015-01-01"
            end_date: "2025-12-31"
            output_file: "universe_scan_results.json"
        """

        all_results = {}

        for i, (cik, name) in enumerate(cik_list):
            print(f"[{i+1}/{len(cik_list)}] Scanning {name} (CIK: {cik})...")

            results = self.scan_company_by_cik(cik, start_date, end_date, name)

            if results:
                all_results[cik] = {
                    'company_name': name,
                    'filings_analyzed': len(results),
                    'findings': results
                }

            # Rate limiting: pause between companies
            time.sleep(1)

            # Save incrementally (in case of API failures)
            if i % 10 == 0:
                with open(output_file, 'w') as f:
                    json.dump(all_results, f, indent=2)

        return all_results
```

---

## Practical Workflows

### Workflow 1: Deep Dive on Specific Industry Over Time

**Goal**: Check if ANY semiconductor companies changed geographic revenue methodology 2015-2025

```python
semiconductor_companies = [
    ("1045810", "NVIDIA"),
    ("2488", "AMD"),
    ("804328", "QUALCOMM"),
    ("1061302", "BROADCOM"),
    ("200406", "INTEL"),
    ("1524472", "MICRON"),
    ("1141391", "TEXAS INSTRUMENTS"),
    # ... more
]

scanner = HistoricalAccountingScanner(api_key)
results = scanner.scan_universe(
    cik_list=semiconductor_companies,
    start_date="2015-01-01",
    end_date="2025-12-31",
    output_file="semiconductor_historical_scan.json"
)

# Analyze results
for cik, data in results.items():
    if data['findings']:
        print(f"\n{data['company_name']}:")
        print(f"  Total filings with findings: {len(data['findings'])}")

        # Check for temporal changes (methodology mentioned in some quarters but not others)
        for finding in data['findings']:
            if 'methodology_change' in finding['findings']:
                print(f"  ⚠️  METHODOLOGY CHANGE DETECTED: {finding['filing_date']}")
                print(f"     URL: {finding['url']}")
```

### Workflow 2: Screening Delisted Companies

**Goal**: Check if delisted retailers had geographic revenue methodology issues before bankruptcy

```python
delisted_retailers = [
    ("1005414", "Toys R Us"),
    ("1310067", "Sears"),
    ("1013488", "Borders Books"),
    ("814453", "Circuit City"),
]

# Scan final 2 years before delisting
for cik, name in delisted_retailers:
    print(f"\nChecking {name} final filings...")

    # Get last filings before delisting
    results = scanner.scan_company_by_cik(
        cik=cik,
        start_date="2016-01-01",  # Adjust per company
        end_date="2018-12-31",
        company_name=name
    )

    # Look for methodology changes during distress period
```

### Workflow 3: Longitudinal Panel Study

**Goal**: Build dataset of ALL S&P 500 companies, ALL filings, 2015-2025

```python
# Load S&P 500 CIKs (from external source)
sp500 = load_sp500_ciks()  # Returns [(cik, name), ...]

# Scan entire universe
scanner.scan_universe(
    cik_list=sp500,
    start_date="2015-01-01",
    end_date="2025-12-31",
    output_file="sp500_10year_panel.json"
)

# Result: Complete dataset of every geographic revenue disclosure
# Can then analyze:
# - Prevalence over time (has it increased?)
# - Industry patterns (which industries discuss it more?)
# - Methodology changes (who switched, when, why?)
```

---

## Casting the Widest Net

### Comprehensive Detection Strategy

**Phase 1: Broad Screening**
1. ✅ Use expanded keyword list (25+ variations)
2. ✅ Search 10-Q AND 10-K filings
3. ✅ Use date ranges to get ALL historical filings
4. ✅ Use CIK codes to include delisted companies

**Phase 2: Multiple Section Extraction**
1. Extract financial statements (item 8 / part1item1)
2. Extract MD&A (item 7 / part1item2)
3. Extract accounting policies sections specifically

**Phase 3: Temporal Comparison**
1. For each company, compare filings across quarters
2. Flag when methodology language CHANGES between periods
3. This catches implicit changes even without "previously" language

**Phase 4: Cross-Reference**
1. When methodology keywords found, extract full context
2. Look for footnotes (1), (2) markers
3. Compare to prior quarter's language

---

## API Rate Limits and Optimization

### SEC-API Rate Limits

**Free tier**: Unknown (test incrementally)
**Paid tier**: Likely 100-1000 requests/min

### Optimization Strategies

1. **Batch Processing**:
   - Process 10 companies at a time
   - Save results incrementally
   - Can resume if interrupted

2. **Caching**:
   - Save extracted filing text to local files
   - Don't re-download same filing multiple times
   - Particularly important for large historical scans

3. **Parallel Processing**:
   - Run multiple workers in parallel (if API allows)
   - Each worker processes different companies

4. **Smart Filtering**:
   - First pass: Quick keyword check on ALL filings
   - Second pass: Deep extraction only on flagged filings

---

## Next Steps

### Immediate (Today)

1. ✅ Broaden keyword detection (DONE)
2. ⏳ Test broader keywords on sample companies
3. ⏳ Implement CIK-based scanning

### Short-term (This Week)

1. Create enhanced scanner with CIK support
2. Build S&P 500 CIK mapping file
3. Test historical scan on 5-10 companies over 10 years
4. Validate results against known cases

### Long-term (Research Project)

1. Scan entire S&P 500 or Russell 3000 historically
2. Build panel dataset of all geographic revenue disclosures
3. Analyze temporal trends and industry patterns
4. Identify all methodology changes systematically

---

## Example: Complete Historical Scan

```python
# 1. Load company universe
companies = [
    ("1045810", "NVIDIA"),
    ("320193", "APPLE"),
    ("789019", "MICROSOFT"),
    # ... more
]

# 2. Initialize scanner with broader keywords
scanner = HistoricalAccountingScanner(api_key)

# 3. Scan 10-year history
results = scanner.scan_universe(
    cik_list=companies,
    start_date="2015-01-01",
    end_date="2025-12-31",
    output_file="10year_scan_results.json"
)

# 4. Analyze prevalence
total_companies = len(companies)
companies_with_geo_revenue = len([c for c in results if results[c]['findings']])
prevalence = companies_with_geo_revenue / total_companies * 100

print(f"Prevalence: {prevalence:.1f}% of companies discuss geographic revenue methodology")

# 5. Identify methodology changes
changes = []
for cik, data in results.items():
    for finding in data['findings']:
        if 'methodology_change' in finding['findings'] or 'previously' in finding['findings']:
            changes.append({
                'company': data['company_name'],
                'date': finding['filing_date'],
                'url': finding['url']
            })

print(f"\nMethodology changes detected: {len(changes)}")
for change in changes:
    print(f"  - {change['company']}: {change['date']}")
```

---

## Summary

**To cast the widest systematic net:**

1. ✅ **Use CIK codes** (not tickers) → Includes delisted companies
2. ✅ **Use date ranges** → Get ALL filings over time, not just recent 2
3. ✅ **Use broader keywords** → Catch terminology variations (DONE)
4. ⏳ **Implement pagination** → Handle companies with >200 filings
5. ⏳ **Add temporal comparison** → Detect changes even without explicit language
6. ⏳ **Build systematic workflows** → Process hundreds of companies efficiently

**Result**: Complete historical dataset of geographic revenue methodology disclosures and changes across your entire universe of interest.
