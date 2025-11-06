# SEC Filing Timeliness Monitor - User Guide

## Overview

The `sec_filing_monitor.py` script provides a comprehensive system for monitoring SEC filing delays and creating an early-warning system for regulatory compliance issues.

## Features

1. **Filer Classification**: Automatically classifies companies as large accelerated, accelerated, or non-accelerated filers based on public float
2. **Statutory Due Date Calculation**: Computes filing deadlines according to SEC rules
3. **Filing Status Verification**: Queries SEC EDGAR to check if filings have been submitted
4. **Delay Detection**: Flags companies with late or missing filings
5. **Batch Processing**: Monitor multiple companies simultaneously

## Installation

```bash
pip install -r requirements.txt
```

## API Key Setup

Get a free API key from [sec-api.io](https://sec-api.io):

1. Sign up at https://sec-api.io
2. Copy your API key
3. Set it as an environment variable:

```bash
export SEC_API_KEY="your_api_key_here"
```

Or pass it directly when initializing the monitor:

```python
monitor = FilingMonitor(api_key="your_api_key_here")
```

## Quick Start

### Example 1: Check a Single Company

```python
from sec_filing_monitor import FilingMonitor
from datetime import datetime

monitor = FilingMonitor()  # Uses SEC_API_KEY environment variable

result = monitor.check_filing_status(
    ticker="AAPL",
    fiscal_period_end=datetime(2024, 9, 30),
    filing_type="10-K",
    public_float=3_000_000_000_000  # $3 trillion
)

print(result['status'])
# Output: "ON TIME: Filed on 2024-10-28" or "DELAYED: Filed 5 days late"
```

### Example 2: Monitor Multiple Companies

```python
companies = [
    {
        "ticker": "AAPL",
        "fiscal_period_end": datetime(2024, 9, 30),
        "filing_type": "10-K",
        "public_float": 3_000_000_000_000,
    },
    {
        "ticker": "MSFT",
        "fiscal_period_end": datetime(2024, 6, 30),
        "filing_type": "10-K",
        "public_float": 2_500_000_000_000,
    }
]

results_df = monitor.monitor_companies(companies)
print(results_df)
```

### Example 3: Find All Delayed Filings

```python
tickers = ["AAPL", "MSFT", "GOOGL", "TSLA", "AMZN"]

public_float_map = {
    "AAPL": 3_000_000_000_000,
    "MSFT": 2_500_000_000_000,
    "GOOGL": 1_800_000_000_000,
    "TSLA": 850_000_000_000,
    "AMZN": 1_600_000_000_000,
}

delayed_filings = monitor.find_delayed_filings(
    tickers=tickers,
    filing_type="10-K",
    public_float_map=public_float_map,
    fiscal_period_end=datetime(2024, 12, 31)
)

print(f"Found {len(delayed_filings)} delayed filings")
print(delayed_filings[['ticker', 'status', 'days_late']])
```

## Filer Classification Rules

According to SEC Rule 12b-2:

| Filer Status | Public Float Threshold | 10-K Deadline | 10-Q Deadline |
|-------------|------------------------|---------------|---------------|
| Large Accelerated | ≥ $700M | 60 days | 40 days |
| Accelerated | $75M - $700M | 75 days | 40 days |
| Non-Accelerated | < $75M | 90 days | 45 days |

## Output Fields

When checking filing status, the following information is returned:

- `ticker`: Company ticker symbol
- `filing_type`: Type of filing (10-K or 10-Q)
- `fiscal_period_end`: End date of the fiscal period
- `filer_status`: Classification (large_accelerated, accelerated, non_accelerated)
- `public_float`: Public float value in USD
- `statutory_due_date`: Calculated due date per SEC rules
- `actual_filing_date`: Actual date filed (if found in EDGAR)
- `is_delayed`: Boolean indicating if filing is late or missing
- `days_late`: Number of days past the due date (if delayed)
- `status`: Human-readable status message

## Advanced Usage

### Calculating Due Dates Without API

You can calculate statutory due dates without making API calls:

```python
from sec_filing_monitor import FilingMonitor
from datetime import datetime

due_date = FilingMonitor.calculate_statutory_due_date(
    fiscal_period_end=datetime(2024, 12, 31),
    filing_type="10-K",
    public_float=850_000_000_000
)

print(f"Due date: {due_date}")
# Output: Due date: 2025-03-01
```

### Classifying Filers

```python
filer_status = FilingMonitor.classify_filer(public_float=850_000_000_000)
print(filer_status)
# Output: large_accelerated
```

### Custom Search Window

By default, the monitor searches 180 days after the period end date. You can customize this:

```python
actual_filing_date = monitor.get_actual_filing_date(
    ticker="AAPL",
    filing_type="10-K",
    fiscal_period_end=datetime(2024, 9, 30),
    search_window_days=365  # Search up to 1 year after period end
)
```

## Integration Examples

### Daily Monitoring Script

Create a script that runs daily to check your portfolio:

```python
#!/usr/bin/env python3
from sec_filing_monitor import FilingMonitor
from datetime import datetime
import pandas as pd

# Load your watchlist
watchlist = pd.read_csv("portfolio.csv")  # columns: ticker, public_float

monitor = FilingMonitor()

# Check recent quarter-end (e.g., Dec 31)
companies = [
    {
        "ticker": row["ticker"],
        "fiscal_period_end": datetime(2024, 12, 31),
        "filing_type": "10-K",
        "public_float": row["public_float"]
    }
    for _, row in watchlist.iterrows()
]

results = monitor.monitor_companies(companies)

# Filter and alert on delayed filings
delayed = results[results["is_delayed"] == True]

if not delayed.empty:
    print(f"⚠️  ALERT: {len(delayed)} delayed filings detected!")
    print(delayed[['ticker', 'status', 'days_late']])

    # Send email alert, post to Slack, etc.
    # send_alert(delayed)
else:
    print("✓ All filings are on time")
```

### Export to CSV

```python
results_df = monitor.monitor_companies(companies)
results_df.to_csv("filing_status_report.csv", index=False)
```

## Troubleshooting

### API Key Errors

If you see "API key required" error:
1. Verify your API key is correct
2. Check that SEC_API_KEY environment variable is set
3. Ensure the key is active (not expired)

### No Filings Found

If the monitor can't find a filing:
1. Verify the ticker symbol is correct
2. Check that the fiscal_period_end date matches the company's actual period end
3. Confirm the filing has been submitted (check SEC EDGAR manually)
4. Try increasing the search_window_days parameter

### Rate Limits

The free tier of sec-api.io has rate limits. If you're monitoring many companies:
1. Add delays between API calls
2. Consider upgrading to a paid plan
3. Cache results to avoid repeated queries

## References

- SEC Rule 12b-2: https://www.sec.gov/rules-regulations
- SEC Filing Deadlines: https://www.sec.gov/fast-answers/answersformduehtm.html
- sec-api.io Documentation: https://sec-api.io/docs

## License

This script is provided as-is for educational and research purposes.
