# SEC Filing Delay Monitor

A comprehensive Python toolkit for monitoring SEC filing timeliness and detecting potential delays based on statutory requirements.

## Overview

This system helps investors, analysts, and compliance professionals:

- **Compute statutory due dates** for 10-K and 10-Q filings based on filer classification
- **Monitor filing timeliness** across investment portfolios
- **Detect filing delays** before they become material issues
- **Automate compliance checks** with live SEC EDGAR data

## Key Features

### 1. Filer Classification
Automatically classifies companies based on public float per **SEC Rule 12b-2**:
- **Large Accelerated Filer**: Public float ≥ $700M
- **Accelerated Filer**: Public float $75M - $700M
- **Non-Accelerated Filer**: Public float < $75M

### 2. Statutory Due Date Calculation
Computes exact due dates based on filer status:

| Filing Type | Large Accelerated | Accelerated | Non-Accelerated |
|-------------|-------------------|-------------|-----------------|
| **10-K**    | 60 days          | 75 days     | 90 days         |
| **10-Q**    | 40 days          | 40 days     | 45 days         |

### 3. Delay Detection
- Checks if filings were submitted after statutory deadline
- Monitors for missing filings past due date
- Calculates exact number of days delayed

### 4. SEC API Integration
- Live data from SEC EDGAR via [sec-api.io](https://sec-api.io)
- Automatic retrieval of filing dates
- XBRL extraction for public float values
- Full-text search capabilities

## Installation

### Basic Installation
```bash
pip install sec-api
```

### Full Installation (with optional dependencies)
```bash
pip install -r requirements.txt
```

## Quick Start

### 1. Basic Usage (No API Required)

```python
from datetime import datetime
from sec_filing_monitor import check_filing_delay

# Check if a company's filing is delayed
result = check_filing_delay(
    fiscal_period_end=datetime(2024, 12, 31),
    filing_type="10-K",
    public_float=850_000_000,  # $850M - Large Accelerated Filer
    actual_filing_date=datetime(2025, 3, 15)
)

print(f"Status: {'DELAYED' if result.is_delayed else 'ON TIME'}")
print(f"Due Date: {result.statutory_due_date.date()}")
print(f"Details: {result.status_message}")
```

### 2. Batch Monitoring

```python
from sec_filing_monitor import CompanyFilingInfo, batch_analyze_filings, generate_delay_report

companies = [
    CompanyFilingInfo(
        ticker="AAPL",
        company_name="Apple Inc.",
        fiscal_period_end=datetime(2024, 9, 30),
        filing_type="10-K",
        public_float=3_000_000_000_000,
        actual_filing_date=datetime(2024, 10, 31)
    ),
    CompanyFilingInfo(
        ticker="TSLA",
        company_name="Tesla, Inc.",
        fiscal_period_end=datetime(2024, 12, 31),
        filing_type="10-K",
        public_float=800_000_000_000,
        actual_filing_date=None  # Not yet filed
    ),
]

results = batch_analyze_filings(companies)
print(generate_delay_report(results, show_all=True))
```

### 3. Live Monitoring with SEC API

```python
import os
from datetime import datetime
from sec_api_integration import monitor_portfolio

# Set your API key
api_key = os.environ.get("SEC_API_KEY")  # Get from https://sec-api.io

portfolio = [
    {
        "ticker": "AAPL",
        "fiscal_period_end": datetime(2024, 9, 30),
        "filing_type": "10-K",
        "public_float": 3_000_000_000_000
    },
    {
        "ticker": "MSFT",
        "fiscal_period_end": datetime(2024, 6, 30),
        "filing_type": "10-K",
        "public_float": 2_500_000_000_000
    }
]

report = monitor_portfolio(api_key, portfolio, show_all=True)
print(report)
```

## API Key Setup

### Get Your API Key
1. Sign up at [https://sec-api.io](https://sec-api.io)
2. Get your API key from the dashboard
3. Set as environment variable:

```bash
export SEC_API_KEY="your_api_key_here"
```

Or in Python:
```python
import os
os.environ["SEC_API_KEY"] = "your_api_key_here"
```

## Module Reference

### `sec_filing_monitor.py`
Core logic for filer classification, due date calculation, and delay detection.

**Key Functions:**
- `classify_filer(public_float)` - Classify filer status
- `statutory_due_date(fiscal_period_end, filing_type, public_float)` - Compute due date
- `check_filing_delay(...)` - Check for delays
- `batch_analyze_filings(companies)` - Analyze multiple companies
- `generate_delay_report(results)` - Generate formatted report

**Key Classes:**
- `FilerStatus` - Enum for filer classifications
- `FilingType` - Enum for filing types (10-K, 10-Q)
- `CompanyFilingInfo` - Data structure for company info
- `FilingDelayResult` - Result of delay analysis

### `sec_api_integration.py`
Integration layer for live SEC EDGAR data via sec-api.io.

**Key Class: `SECAPIClient`**

**Methods:**
- `get_filings(ticker, form_type, start_date, end_date)` - Query filings
- `get_latest_filing(ticker, form_type, period_end_date)` - Get most recent filing
- `extract_public_float(filing_url)` - Extract public float from XBRL
- `build_company_filing_info(ticker, fiscal_period_end, filing_type)` - Build complete company profile
- `monitor_tickers(tickers, fiscal_period_end, filing_type)` - Monitor multiple tickers

**Functions:**
- `monitor_portfolio(api_key, portfolio, show_all)` - Monitor portfolio of companies

### `example_usage.py`
Comprehensive examples demonstrating all features.

**Examples:**
1. Basic statutory due date calculations
2. Filing delay detection
3. Batch analysis of multiple companies
4. Quarterly (10-Q) monitoring
5. Live monitoring with SEC API
6. Custom investment watchlist

## Example Output

```
================================================================================
SEC FILING DELAY REPORT
================================================================================
Total companies analyzed: 5
Delayed filings: 2
On-time filings: 3
================================================================================

🔴 DELAYED - TSLA (Tesla, Inc.)
  Filing Type: 10-K
  Filer Status: Large Accelerated
  Fiscal Period End: 2024-12-31
  Statutory Due Date: 2025-03-01
  Actual Filing Date: 2025-03-15
  Days Delayed: 14
  Status: Filing submitted 14 day(s) after statutory deadline

🔴 DELAYED - SMALLCO (Small Corp)
  Filing Type: 10-K
  Filer Status: Non Accelerated
  Fiscal Period End: 2024-12-31
  Statutory Due Date: 2025-03-31
  Days Delayed: 15
  Status: Filing OVERDUE by 15 day(s). Due: 2025-03-31

================================================================================
```

## Use Cases

### 1. Investment Due Diligence
Monitor portfolio companies for compliance red flags before they become material.

### 2. Risk Management
Set up automated alerts for delayed filings indicating potential operational issues.

### 3. Compliance Monitoring
Track filing obligations across large universes of companies.

### 4. Research & Analysis
Study patterns in filing behavior across sectors, market caps, or time periods.

### 5. Trading Signals
Detect filing delays that may precede price movements or material events.

## Advanced Usage

### Automated Daily Monitoring

```python
import schedule
import time
from datetime import datetime
from sec_api_integration import SECAPIClient

def daily_monitor():
    """Run daily monitoring check"""
    api_key = os.environ.get("SEC_API_KEY")
    client = SECAPIClient(api_key)

    # Your watchlist
    tickers = ["AAPL", "MSFT", "GOOGL", "AMZN", "TSLA"]

    # Check for Q4 2024 10-K filings
    results = client.monitor_tickers(
        tickers=tickers,
        fiscal_period_end=datetime(2024, 12, 31),
        filing_type="10-K"
    )

    # Filter for delays only
    delayed = [r for r in results if r.is_delayed]

    if delayed:
        # Send alert (email, Slack, etc.)
        send_alert(f"ALERT: {len(delayed)} delayed filings detected!")

# Schedule daily at 9 AM
schedule.every().day.at("09:00").do(daily_monitor)

while True:
    schedule.run_pending()
    time.sleep(60)
```

### Export to CSV

```python
import pandas as pd
from sec_filing_monitor import batch_analyze_filings

results = batch_analyze_filings(companies)

# Convert to DataFrame
df = pd.DataFrame([
    {
        "ticker": r.company_info.ticker,
        "company_name": r.company_info.company_name,
        "filer_status": r.filer_status.value,
        "fiscal_period_end": r.company_info.fiscal_period_end,
        "due_date": r.statutory_due_date,
        "filing_date": r.company_info.actual_filing_date,
        "is_delayed": r.is_delayed,
        "days_delayed": r.days_delayed
    }
    for r in results
])

# Export
df.to_csv("filing_delays.csv", index=False)
```

### Integration with Database

```python
from sqlalchemy import create_engine
import pandas as pd

# Store results in database
engine = create_engine("postgresql://user:pass@localhost/filings")

df.to_sql("filing_delays", engine, if_exists="append", index=False)
```

## Testing

Run the test suite:
```bash
pytest tests/
```

Run with coverage:
```bash
pytest --cov=sec_filing_monitor tests/
```

## Statutory References

This tool implements SEC regulations per:

- **SEC Rule 12b-2**: Definitions of accelerated filer and large accelerated filer
- **SEC Form 10-K**: Annual report filing requirements
- **SEC Form 10-Q**: Quarterly report filing requirements
- **17 CFR § 240.13a-1 and § 240.15d-1**: Filing deadlines

## Limitations

1. **Public Float Availability**: Public float is typically reported in 10-K filings and may not be available for all companies
2. **Smaller Reporting Companies**: Additional considerations apply for SRCs that are not fully implemented
3. **Foreign Private Issuers**: Use different forms (20-F, 6-K) with different deadlines
4. **Extension Requests**: NT 10-K/10-Q extension filings are not automatically tracked
5. **API Rate Limits**: sec-api.io has rate limits depending on your subscription tier

## Roadmap

- [ ] Support for 8-K current report monitoring
- [ ] NT 10-K/10-Q extension tracking
- [ ] Foreign private issuer support (20-F, 6-K)
- [ ] Historical filing pattern analysis
- [ ] Machine learning for delay prediction
- [ ] Real-time streaming alerts
- [ ] Web dashboard interface
- [ ] Multi-year trend analysis

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Submit a pull request

## License

MIT License - See LICENSE file for details

## Support

- **Documentation**: See inline docstrings and examples
- **Issues**: Report bugs or request features via GitHub Issues
- **API Docs**: https://sec-api.io/docs

## Disclaimer

This tool is for informational purposes only. Users should:

- Verify critical information independently
- Consult SEC EDGAR directly for official records
- Seek professional advice for compliance decisions
- Not rely solely on automated systems for material decisions

Filing deadlines may vary based on specific circumstances not captured by this tool.

## Acknowledgments

- SEC EDGAR system for public access to filings
- [sec-api.io](https://sec-api.io) for API infrastructure
- SEC staff for maintaining comprehensive filing requirements

---

**Version**: 1.0.0
**Last Updated**: 2025
**Author**: Filing Compliance Monitoring System
