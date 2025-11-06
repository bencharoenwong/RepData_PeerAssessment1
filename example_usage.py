"""
SEC Filing Delay Monitor - Example Usage
=========================================

This script demonstrates various ways to use the SEC Filing Delay Monitor system.

Before running:
1. Install dependencies: pip install -r requirements.txt
2. Get an API key from https://sec-api.io
3. Set your API key as environment variable: export SEC_API_KEY="your_key_here"
   OR pass it directly in the code
"""

import os
from datetime import datetime
from sec_filing_monitor import (
    CompanyFilingInfo,
    check_filing_delay,
    analyze_company_filing,
    batch_analyze_filings,
    generate_delay_report,
    classify_filer,
    statutory_due_date
)

# Only import SEC API if available
try:
    from sec_api_integration import SECAPIClient, monitor_portfolio
    SEC_API_AVAILABLE = True
except ImportError:
    SEC_API_AVAILABLE = False
    print("Warning: sec-api package not installed. Some examples will be skipped.")


def example_1_basic_calculations():
    """
    Example 1: Basic statutory due date calculations without API
    """
    print("\n" + "="*80)
    print("EXAMPLE 1: Basic Statutory Due Date Calculations")
    print("="*80)

    # Calculate due dates for different filer types
    fiscal_end = datetime(2024, 12, 31)
    filing_type = "10-K"

    print(f"\nFiscal Year End: {fiscal_end.date()}")
    print(f"Filing Type: {filing_type}\n")

    for public_float in [3_000_000_000_000, 500_000_000, 50_000_000]:
        filer_status = classify_filer(public_float)
        due_date, _ = statutory_due_date(fiscal_end, filing_type, public_float)

        print(f"Public Float: ${public_float:,.0f}")
        print(f"  Filer Status: {filer_status.value.replace('_', ' ').title()}")
        print(f"  Due Date: {due_date.date()}")
        print()


def example_2_delay_checking():
    """
    Example 2: Check if specific filings are delayed
    """
    print("\n" + "="*80)
    print("EXAMPLE 2: Filing Delay Detection")
    print("="*80)

    # Scenario 1: Filed on time
    print("\n--- Scenario 1: Large Company Filed On Time ---")
    result = check_filing_delay(
        fiscal_period_end=datetime(2024, 9, 30),
        filing_type="10-K",
        public_float=3_000_000_000_000,  # Large accelerated filer
        actual_filing_date=datetime(2024, 11, 20)  # 51 days after (< 60 day deadline)
    )
    print(f"Status: {'DELAYED' if result.is_delayed else 'ON TIME'}")
    print(f"Details: {result.status_message}")

    # Scenario 2: Filed late
    print("\n--- Scenario 2: Company Filed Late ---")
    result = check_filing_delay(
        fiscal_period_end=datetime(2024, 12, 31),
        filing_type="10-K",
        public_float=100_000_000,  # Accelerated filer (75 days)
        actual_filing_date=datetime(2025, 4, 1)  # 91 days after (> 75 day deadline)
    )
    print(f"Status: {'DELAYED' if result.is_delayed else 'ON TIME'}")
    print(f"Details: {result.status_message}")
    print(f"Days Late: {result.days_delayed}")

    # Scenario 3: Not yet filed, checking if overdue
    print("\n--- Scenario 3: Filing Not Yet Submitted (Checking if Overdue) ---")
    result = check_filing_delay(
        fiscal_period_end=datetime(2024, 12, 31),
        filing_type="10-Q",
        public_float=50_000_000,  # Non-accelerated filer (45 days)
        actual_filing_date=None,
        reference_date=datetime(2025, 3, 1)  # 60 days after fiscal end
    )
    print(f"Status: {'OVERDUE' if result.is_delayed else 'NOT DUE YET'}")
    print(f"Details: {result.status_message}")


def example_3_batch_analysis():
    """
    Example 3: Analyze multiple companies at once
    """
    print("\n" + "="*80)
    print("EXAMPLE 3: Batch Analysis of Multiple Companies")
    print("="*80)

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
            ticker="MSFT",
            company_name="Microsoft Corporation",
            fiscal_period_end=datetime(2024, 6, 30),
            filing_type="10-K",
            public_float=2_500_000_000_000,
            actual_filing_date=datetime(2024, 8, 15)
        ),
        CompanyFilingInfo(
            ticker="TSLA",
            company_name="Tesla, Inc.",
            fiscal_period_end=datetime(2024, 12, 31),
            filing_type="10-K",
            public_float=800_000_000_000,
            actual_filing_date=datetime(2025, 3, 15)  # This one might be late
        ),
        CompanyFilingInfo(
            ticker="SMALLCO",
            company_name="Small Corp",
            fiscal_period_end=datetime(2024, 12, 31),
            filing_type="10-K",
            public_float=50_000_000,
            actual_filing_date=None  # Not filed yet
        ),
    ]

    # Analyze all companies
    results = batch_analyze_filings(companies)

    # Generate and print report
    print(generate_delay_report(results, show_all=True))


def example_4_quarterly_monitoring():
    """
    Example 4: Monitor quarterly (10-Q) filings
    """
    print("\n" + "="*80)
    print("EXAMPLE 4: Quarterly Filing (10-Q) Monitoring")
    print("="*80)

    quarters = [
        ("Q1", datetime(2024, 3, 31)),
        ("Q2", datetime(2024, 6, 30)),
        ("Q3", datetime(2024, 9, 30)),
    ]

    ticker = "EXAMPLE"
    public_float = 150_000_000  # Accelerated filer

    print(f"\nMonitoring {ticker} (Public Float: ${public_float:,.0f})")
    print(f"Filer Status: {classify_filer(public_float).value.replace('_', ' ').title()}\n")

    for quarter, fiscal_end in quarters:
        due_date, _ = statutory_due_date(fiscal_end, "10-Q", public_float)
        print(f"{quarter} {fiscal_end.year}:")
        print(f"  Fiscal Period End: {fiscal_end.date()}")
        print(f"  10-Q Due Date: {due_date.date()}")
        print()


def example_5_with_sec_api():
    """
    Example 5: Live monitoring using SEC API
    (Requires valid API key)
    """
    if not SEC_API_AVAILABLE:
        print("\n" + "="*80)
        print("EXAMPLE 5: Skipped (sec-api not installed)")
        print("="*80)
        return

    print("\n" + "="*80)
    print("EXAMPLE 5: Live Monitoring with SEC API")
    print("="*80)

    # Get API key from environment
    api_key = os.environ.get("SEC_API_KEY")

    if not api_key:
        print("\nSkipping: SEC_API_KEY environment variable not set")
        print("To run this example:")
        print("  export SEC_API_KEY='your_key_here'")
        return

    print("\nMonitoring real-time filing data from SEC EDGAR...\n")

    try:
        # Initialize client
        client = SECAPIClient(api_key)

        # Monitor a small portfolio
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
            },
        ]

        report = monitor_portfolio(api_key, portfolio, show_all=True)
        print(report)

    except Exception as e:
        print(f"Error: {e}")
        print("\nMake sure:")
        print("1. You have a valid API key from https://sec-api.io")
        print("2. sec-api is installed: pip install sec-api")


def example_6_custom_watchlist():
    """
    Example 6: Create a custom watchlist for specific companies
    """
    print("\n" + "="*80)
    print("EXAMPLE 6: Custom Investment Watchlist")
    print("="*80)

    # Define your investment universe
    watchlist = {
        "AAPL": {"name": "Apple Inc.", "float": 3_000_000_000_000},
        "GOOGL": {"name": "Alphabet Inc.", "float": 1_800_000_000_000},
        "AMZN": {"name": "Amazon.com Inc.", "float": 1_500_000_000_000},
        "NVDA": {"name": "NVIDIA Corporation", "float": 1_200_000_000_000},
        "META": {"name": "Meta Platforms Inc.", "float": 900_000_000_000},
    }

    # Upcoming fiscal year ends to monitor
    upcoming_period = datetime(2024, 12, 31)
    filing_type = "10-K"

    print(f"\nWatchlist for fiscal period ending: {upcoming_period.date()}")
    print(f"Filing type: {filing_type}\n")

    companies = []
    for ticker, info in watchlist.items():
        company = CompanyFilingInfo(
            ticker=ticker,
            company_name=info["name"],
            fiscal_period_end=upcoming_period,
            filing_type=filing_type,
            public_float=info["float"],
            actual_filing_date=None  # Monitoring for future filing
        )
        companies.append(company)

    results = batch_analyze_filings(companies)

    # Show when each company needs to file
    print("Expected Filing Deadlines:")
    print("-" * 80)
    for result in results:
        print(f"{result.company_info.ticker:6} ({result.filer_status.value.replace('_', ' ').title():20}) - "
              f"Due: {result.statutory_due_date.date()}")

    print("\n" + generate_delay_report(results, show_all=True))


def main():
    """Run all examples"""
    print("\n")
    print("="*80)
    print("SEC FILING DELAY MONITOR - COMPREHENSIVE EXAMPLES")
    print("="*80)

    # Run all examples
    example_1_basic_calculations()
    example_2_delay_checking()
    example_3_batch_analysis()
    example_4_quarterly_monitoring()
    example_5_with_sec_api()
    example_6_custom_watchlist()

    print("\n" + "="*80)
    print("All examples completed!")
    print("="*80)
    print("\nTo use this in production:")
    print("1. Get your API key from https://sec-api.io")
    print("2. Set SEC_API_KEY environment variable")
    print("3. Run daily/weekly to monitor your portfolio")
    print("4. Set up alerts for delayed filings")
    print()


if __name__ == "__main__":
    main()
