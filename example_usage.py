#!/usr/bin/env python3
"""
Example Usage: SEC Filing Monitor
==================================

Demonstrates practical use cases for the filing monitor.
Replace YOUR_API_KEY with your actual sec-api.io API key.
"""

from sec_filing_monitor import FilingMonitor
from datetime import datetime
import os


def example_1_single_company():
    """Check if a specific company filed on time."""
    print("=" * 70)
    print("Example 1: Check Single Company")
    print("=" * 70)

    api_key = os.getenv("SEC_API_KEY", "YOUR_API_KEY")
    monitor = FilingMonitor(api_key=api_key)

    # Check Apple's 10-K for fiscal year ending Sept 30, 2024
    result = monitor.check_filing_status(
        ticker="AAPL",
        fiscal_period_end=datetime(2024, 9, 30),
        filing_type="10-K",
        public_float=3_000_000_000_000  # Apple is a large accelerated filer
    )

    print(f"\nCompany: {result['ticker']}")
    print(f"Status: {result['status']}")
    print(f"Filer Category: {result['filer_status']}")
    print(f"Due Date: {result['statutory_due_date']}")
    if result['actual_filing_date']:
        print(f"Filed On: {result['actual_filing_date']}")
    print(f"Delayed: {'Yes' if result['is_delayed'] else 'No'}")


def example_2_portfolio_monitoring():
    """Monitor multiple companies in your portfolio."""
    print("\n" + "=" * 70)
    print("Example 2: Portfolio-Wide Monitoring")
    print("=" * 70)

    api_key = os.getenv("SEC_API_KEY", "YOUR_API_KEY")
    monitor = FilingMonitor(api_key=api_key)

    # Define your portfolio
    portfolio = [
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
        },
        {
            "ticker": "GOOGL",
            "fiscal_period_end": datetime(2024, 12, 31),
            "filing_type": "10-K",
            "public_float": 1_800_000_000_000,
        },
        {
            "ticker": "TSLA",
            "fiscal_period_end": datetime(2024, 12, 31),
            "filing_type": "10-K",
            "public_float": 850_000_000_000,
        },
    ]

    print(f"\nMonitoring {len(portfolio)} companies...")

    results = monitor.monitor_companies(portfolio)

    # Display summary
    print("\n" + "-" * 70)
    print(f"{'Ticker':<8} {'Type':<6} {'Due Date':<12} {'Status':<30}")
    print("-" * 70)

    for _, row in results.iterrows():
        status_short = row['status'][:30]
        print(f"{row['ticker']:<8} {row['filing_type']:<6} {row['statutory_due_date']!s:<12} {status_short:<30}")

    # Count delayed filings
    delayed_count = results['is_delayed'].sum()
    print("-" * 70)
    print(f"Summary: {delayed_count} delayed or missing filings")


def example_3_quarterly_check():
    """Check all Q1 10-Q filings for a list of companies."""
    print("\n" + "=" * 70)
    print("Example 3: Quarterly Filing Check (10-Q)")
    print("=" * 70)

    api_key = os.getenv("SEC_API_KEY", "YOUR_API_KEY")
    monitor = FilingMonitor(api_key=api_key)

    # Companies with Q1 ending March 31
    companies = [
        {
            "ticker": "AAPL",
            "fiscal_period_end": datetime(2024, 3, 31),
            "filing_type": "10-Q",
            "public_float": 3_000_000_000_000,
        },
        {
            "ticker": "MSFT",
            "fiscal_period_end": datetime(2024, 3, 31),
            "filing_type": "10-Q",
            "public_float": 2_500_000_000_000,
        },
    ]

    results = monitor.monitor_companies(companies)

    print("\n10-Q Filing Status for Q1 2024:")
    for _, row in results.iterrows():
        delay_info = f" ({row['days_late']} days late)" if row['is_delayed'] else ""
        print(f"  {row['ticker']}: {row['status']}{delay_info}")


def example_4_calculate_deadlines():
    """Calculate filing deadlines without making API calls."""
    print("\n" + "=" * 70)
    print("Example 4: Calculate Deadlines (No API Required)")
    print("=" * 70)

    scenarios = [
        {
            "name": "Large Cap Tech Company",
            "public_float": 2_000_000_000_000,
            "filing_type": "10-K",
            "period_end": datetime(2024, 12, 31)
        },
        {
            "name": "Mid-Tier Biotech",
            "public_float": 200_000_000_000,
            "filing_type": "10-K",
            "period_end": datetime(2024, 12, 31)
        },
        {
            "name": "Small Cap Startup",
            "public_float": 30_000_000_000,
            "filing_type": "10-K",
            "period_end": datetime(2024, 12, 31)
        },
    ]

    for scenario in scenarios:
        filer_status = FilingMonitor.classify_filer(scenario["public_float"])
        due_date = FilingMonitor.calculate_statutory_due_date(
            scenario["period_end"],
            scenario["filing_type"],
            scenario["public_float"]
        )

        print(f"\n{scenario['name']}:")
        print(f"  Public Float: ${scenario['public_float']:,.0f}")
        print(f"  Filer Status: {filer_status}")
        print(f"  Period End: {scenario['period_end'].date()}")
        print(f"  {scenario['filing_type']} Due: {due_date.date()}")


def example_5_alert_system():
    """Create an early warning alert system."""
    print("\n" + "=" * 70)
    print("Example 5: Early Warning Alert System")
    print("=" * 70)

    api_key = os.getenv("SEC_API_KEY", "YOUR_API_KEY")

    # Skip if no API key
    if api_key == "YOUR_API_KEY":
        print("\nSkipping: Requires valid API key")
        print("Set SEC_API_KEY environment variable to run this example")
        return

    monitor = FilingMonitor(api_key=api_key)

    # List of tickers to monitor
    tickers = ["AAPL", "MSFT", "GOOGL", "TSLA", "AMZN"]

    # Public float data (in practice, fetch this from your database or API)
    public_float_map = {
        "AAPL": 3_000_000_000_000,
        "MSFT": 2_500_000_000_000,
        "GOOGL": 1_800_000_000_000,
        "TSLA": 850_000_000_000,
        "AMZN": 1_600_000_000_000,
    }

    # Check for delayed 10-K filings for fiscal year ending Dec 31, 2023
    print(f"\nScanning {len(tickers)} companies for delayed 10-K filings...")

    delayed = monitor.find_delayed_filings(
        tickers=tickers,
        filing_type="10-K",
        public_float_map=public_float_map,
        fiscal_period_end=datetime(2023, 12, 31)
    )

    if len(delayed) > 0:
        print(f"\n⚠️  ALERT: Found {len(delayed)} delayed filing(s)!\n")
        for _, row in delayed.iterrows():
            print(f"  • {row['ticker']}: {row['status']}")

        # In a real system, you would:
        # - Send email alerts
        # - Post to Slack/Teams
        # - Update a dashboard
        # - Log to monitoring system
    else:
        print("\n✓ All monitored companies filed on time")


def main():
    """Run all examples."""
    print("\n")
    print("╔" + "═" * 68 + "╗")
    print("║" + " " * 15 + "SEC Filing Monitor - Example Usage" + " " * 19 + "║")
    print("╚" + "═" * 68 + "╝")

    # Example 1: Single company check
    # Uncomment to run with valid API key:
    # example_1_single_company()

    # Example 2: Portfolio monitoring
    # Uncomment to run with valid API key:
    # example_2_portfolio_monitoring()

    # Example 3: Quarterly check
    # Uncomment to run with valid API key:
    # example_3_quarterly_check()

    # Example 4: Calculate deadlines (no API required)
    example_4_calculate_deadlines()

    # Example 5: Alert system
    # Uncomment to run with valid API key:
    # example_5_alert_system()

    print("\n" + "=" * 70)
    print("Note: To run examples requiring API access:")
    print("  1. Get free API key from https://sec-api.io")
    print("  2. Set environment variable: export SEC_API_KEY='your_key'")
    print("  3. Uncomment the example function calls above")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
