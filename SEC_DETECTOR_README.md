# SEC Accounting Changes Detector

Automated tool to detect accounting methodology changes in SEC filings using the sec-api.io service.

## Overview

This tool helps identify when companies change their accounting methodologies, such as:
- Geographic revenue recognition changes (like Nvidia's customer headquarters → billing location switch)
- Revenue recognition methodology updates
- Segment reporting reclassifications
- Financial statement restatements or recasts

## Files in This Repository

### Main Scripts

1. **`sec_detector_requests.py`** ⭐ **RECOMMENDED**
   - Uses pure `requests` library
   - Better SSL handling
   - More reliable in various environments
   - **Use this version if you're unsure which to use**

2. **`sec_accounting_detector.py`**
   - Uses the official `sec-api` Python SDK
   - Cleaner API but may have SSL issues in some environments

3. **`test_api_connection.py`**
   - Simple test script to verify API connectivity
   - Runs basic queries against Apple and Nvidia filings

### Supporting Files

- **`requirements.txt`** - Python dependencies
- **`SEC_DETECTOR_README.md`** - This file

## Setup

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

Or manually:
```bash
pip install sec-api requests
```

### 2. API Key

The API key is already configured in the scripts:
```
0cced11055b8c44b38e89fa66706ad19f99602f9d4d28d0a696ded9ebfc905d5
```

**Note:** This is a real API key. Keep it secure and don't share publicly.

## Usage

### Quick Start

Run the main detector:
```bash
python sec_detector_requests.py
```

You'll see a menu with 4 options:

```
1. Search for Nvidia's geographic revenue changes
2. Search all companies for accounting changes (6 months)
3. Search specific ticker for accounting changes
4. Run a simple test query
```

### Option 1: Nvidia Specific Search

Searches specifically for Nvidia's geographic revenue methodology change:

```bash
python sec_detector_requests.py
# Select option 1
```

**Output:**
- Finds all Nvidia 10-Q and 10-K filings mentioning geographic revenue changes
- Creates `nvidia_findings.json` with detailed results

### Option 2: Broad Search (All Companies)

Scans all companies for accounting changes in the last 6 months:

```bash
python sec_detector_requests.py
# Select option 2
```

**Search Patterns Used:**
- `"previously" AND ("revenue recognition" OR "geographic revenue")`
- `"changed our" AND ("accounting" OR "presentation")`
- `"customer headquarters" OR "billing location"`
- `"reclassified" AND "segment"`
- `"geographic revenue based"`

**Output:**
- `all_accounting_changes.json` with comprehensive findings
- Summary statistics by company

### Option 3: Company-Specific Search

Search a specific ticker symbol:

```bash
python sec_detector_requests.py
# Select option 3
# Enter ticker: AAPL
# Enter days: 180
```

**Output:**
- `{ticker}_findings.json` (e.g., `aapl_findings.json`)

### Option 4: Simple Test

Verifies API connection with a basic query:

```bash
python sec_detector_requests.py
# Select option 4
```

Returns 2 recent Apple 10-Q filings to confirm connectivity.

## Example Output

### Console Output
```
================================================================================
SEC ACCOUNTING CHANGES DETECTOR
Using sec-api.io to find methodology changes
================================================================================

Searching for: "previously" AND ("revenue recognition" OR "geographic revenue")
  Found 15 matches

Searching for: "changed our" AND ("accounting" OR "presentation")
  Found 8 matches

================================================================================
SUMMARY: Found 23 potential accounting changes
================================================================================

Unique companies: 18

Top companies with accounting changes:
  NVDA: 3 finding(s)
  MSFT: 2 finding(s)
  GOOGL: 2 finding(s)
  ...

First 5 detailed findings:

1. NVDA - NVIDIA CORP
   Form: 10-Q | Date: 2025-08-28
   URL: https://www.sec.gov/Archives/edgar/data/1045810/...
```

### JSON Report Structure

```json
{
  "generated_at": "2025-11-23T10:30:15.123456",
  "total_findings": 23,
  "findings": [
    {
      "pattern": "\"previously\" AND (\"revenue recognition\" OR \"geographic revenue\")",
      "ticker": "NVDA",
      "company": "NVIDIA CORP",
      "cik": "0001045810",
      "form": "10-Q",
      "date": "2025-08-28T16:05:24-04:00",
      "url": "https://www.sec.gov/Archives/edgar/data/1045810/...",
      "accession_no": "0001045810-25-000123"
    }
  ]
}
```

## Advanced Usage

### Programmatic Usage

```python
from sec_detector_requests import AccountingChangesDetector

# Initialize
API_KEY = "your_api_key"
detector = AccountingChangesDetector(API_KEY)

# Search for changes
findings = detector.search_methodology_changes(
    days_back=365,
    form_types=["10-Q", "10-K"],
    ticker="NVDA"  # Optional: specific ticker
)

# Generate report
detector.generate_report(findings, 'my_report.json')

# Extract sections from specific filing
content = detector.extract_section(
    filing_url="https://www.sec.gov/Archives/...",
    form_type="10-Q"
)
```

### Custom Search Patterns

Modify the search patterns in `search_methodology_changes()`:

```python
search_patterns = [
    '"ASC 606"',  # Revenue recognition standard
    '"segment" AND "reorganization"',
    '"non-GAAP" AND "changed"',
    # Add your own patterns
]
```

## Search Pattern Guide

The tool uses sec-api.io's full-text search with these operators:

| Operator | Example | Description |
|----------|---------|-------------|
| `"exact phrase"` | `"geographic revenue"` | Exact phrase match |
| `AND` | `"changed" AND "accounting"` | Both terms required |
| `OR` | `"restated" OR "recast"` | Either term required |
| `NOT` / `-` | `revenue NOT GAAP` | Exclude term |
| `*` | `account*` | Wildcard (accounting, accountant, etc.) |
| `ticker:` | `ticker:NVDA` | Filter by ticker |

## Understanding the Results

### What to Look For

**High Priority Findings:**
- Mentions of "previously" + accounting terms → indicates a change
- "Changed our methodology/presentation" → explicit change disclosure
- "Reclassified" or "restated" → retroactive adjustments
- Geographic terms with revenue → possible geographic methodology change

**Context Required:**
- Not all matches are material changes
- Review the actual filing to understand significance
- Check if change is prospective or retrospective

### Extracting Detailed Information

After finding a potential change, extract the relevant section:

```python
# For a 10-Q filing
content = detector.extract_section(finding['url'], '10-Q')

# Search within extracted content
if 'geographic revenue' in content.lower():
    # This filing discusses geographic revenue
    print("Found detailed discussion")
```

## Limitations & Considerations

### API Limits

- **Free Tier:** ~100-200 requests
- **Rate Limiting:** Built-in 0.2s delay between searches
- **Max Results:** 10,000 per query (use date ranges to segment)

### Search Quality

**Pros:**
- Searches actual filing text, not just XBRL tags
- Captures narrative disclosures in footnotes
- Real-time access to recent filings

**Cons:**
- False positives possible (e.g., "previously" in unrelated context)
- Requires manual review of findings
- May miss changes described with uncommon terminology

### Cost Management

```python
# For large-scale scanning, batch by date
date_ranges = [
    ("2025-01-01", "2025-03-31"),
    ("2025-04-01", "2025-06-30"),
    # etc.
]

for start, end in date_ranges:
    findings = detector.search_methodology_changes(
        days_back=None,  # Override with custom dates
        # Modify the method to accept start/end dates
    )
    time.sleep(1)  # Additional rate limiting
```

## Troubleshooting

### SSL/Connection Errors

If you see SSL handshake errors:
1. Use `sec_detector_requests.py` (includes SSL fallback)
2. The script automatically retries without SSL verification if needed

### No Results Found

Possible causes:
- API key invalid or expired
- Search pattern too specific
- Date range has no matching filings
- Network connectivity issues

**Debug Steps:**
```bash
# Test API connection
python sec_detector_requests.py
# Select option 4 (simple test)

# If test passes but searches fail, try broader patterns:
# Change: "previously" AND "geographic revenue"
# To: "geographic revenue" OR "segment"
```

### Rate Limiting

If you hit rate limits:
```python
# Increase delay between requests
time.sleep(1)  # Instead of 0.2

# Reduce number of search patterns
# Comment out less important patterns
```

## Example Use Cases

### 1. Monitor Portfolio Companies

```python
tickers = ['AAPL', 'GOOGL', 'MSFT', 'NVDA']

for ticker in tickers:
    print(f"\nScanning {ticker}...")
    findings = detector.search_methodology_changes(
        days_back=90,
        ticker=ticker
    )
    if findings:
        detector.generate_report(findings, f'{ticker}_changes.json')
```

### 2. Quarterly Earnings Review

```python
# After earnings season, scan for changes
findings = detector.search_methodology_changes(
    days_back=45,  # Last quarter
    form_types=["10-Q"]
)
```

### 3. Industry-Specific Monitoring

```python
# Tech companies with revenue recognition changes
search_query = {
    "query": '"ASC 606" AND ("changed" OR "adopted")',
    "formTypes": ["10-Q", "10-K"],
    "startDate": "2025-01-01",
    "endDate": "2025-11-23"
}

results = detector.full_text_search(search_query)
```

## Next Steps

1. **Run Initial Test:**
   ```bash
   python sec_detector_requests.py
   # Choose option 4
   ```

2. **Try Nvidia Search:**
   ```bash
   python sec_detector_requests.py
   # Choose option 1
   ```

3. **Review Results:**
   ```bash
   cat nvidia_findings.json | python -m json.tool
   ```

4. **Customize for Your Needs:**
   - Modify search patterns
   - Add specific tickers
   - Adjust date ranges

## Resources

- **SEC API Documentation:** https://sec-api.io/docs
- **Full-Text Search Guide:** https://sec-api.io/docs/full-text-search-api
- **Query API Reference:** https://sec-api.io/docs/query-api
- **Support:** support@sec-api.io

## License

This tool is for research and educational purposes. Ensure compliance with sec-api.io's terms of service.

---

**Questions or Issues?**

1. Check API connection: Run option 4
2. Review search patterns: Modify for your use case
3. Check API limits: Monitor usage at sec-api.io dashboard
4. Contact support: support@sec-api.io for API issues
