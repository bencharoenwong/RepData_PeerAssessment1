#!/usr/bin/env python3
"""
SEC Filing Timeliness Monitor
==============================

A regulatory filing delay early-warning system that:
1. Computes statutory due dates based on filer status (inferred from public float)
2. Checks whether expected filings (10-K, 10-Q) have been posted on time
3. Flags companies with delayed or missing filings

Requirements:
    pip install sec-api pandas

Usage:
    Set your SEC_API_KEY environment variable or pass it directly to the monitor.

    Example:
        monitor = FilingMonitor(api_key="your_api_key_here")
        results = monitor.check_company("AAPL", datetime(2024, 9, 30), "10-K", 3_000_000_000_000)
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple
import pandas as pd
from sec_api import QueryApi


class FilingMonitor:
    """Monitor SEC filing timeliness and flag delayed filings."""

    # Statutory filing deadlines (in calendar days after period end)
    DEADLINES = {
        "10-K": {
            "large_accelerated": 60,
            "accelerated": 75,
            "non_accelerated": 90
        },
        "10-Q": {
            "large_accelerated": 40,
            "accelerated": 40,
            "non_accelerated": 45
        }
    }

    # Public float thresholds for filer classification (per SEC Rule 12b-2)
    FLOAT_THRESHOLDS = {
        "large_accelerated": 700_000_000,
        "accelerated": 75_000_000
    }

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the Filing Monitor.

        Args:
            api_key: SEC API key from sec-api.io. If None, will attempt to read from
                    environment variable SEC_API_KEY.
        """
        if api_key is None:
            import os
            api_key = os.getenv("SEC_API_KEY")
            if api_key is None:
                raise ValueError(
                    "API key required. Either pass api_key parameter or set SEC_API_KEY "
                    "environment variable. Get your free key at https://sec-api.io"
                )

        self.query_api = QueryApi(api_key=api_key)

    @staticmethod
    def classify_filer(public_float: float) -> str:
        """
        Classify filer status based on public float.

        Args:
            public_float: Public float value in USD

        Returns:
            Filer classification: "large_accelerated", "accelerated", or "non_accelerated"
        """
        if public_float >= FilingMonitor.FLOAT_THRESHOLDS["large_accelerated"]:
            return "large_accelerated"
        elif public_float >= FilingMonitor.FLOAT_THRESHOLDS["accelerated"]:
            return "accelerated"
        else:
            return "non_accelerated"

    @staticmethod
    def calculate_statutory_due_date(
        fiscal_period_end: datetime,
        filing_type: str,
        public_float: float
    ) -> datetime:
        """
        Calculate the statutory due date for a SEC filing.

        Args:
            fiscal_period_end: End date of the fiscal period
            filing_type: Type of filing ("10-K" or "10-Q")
            public_float: Public float value in USD

        Returns:
            Statutory due date

        Raises:
            ValueError: If filing_type is not supported
        """
        if filing_type not in FilingMonitor.DEADLINES:
            raise ValueError(
                f"Unsupported filing type: {filing_type}. "
                f"Supported types: {list(FilingMonitor.DEADLINES.keys())}"
            )

        filer_status = FilingMonitor.classify_filer(public_float)
        days_to_add = FilingMonitor.DEADLINES[filing_type][filer_status]

        return fiscal_period_end + timedelta(days=days_to_add)

    def get_actual_filing_date(
        self,
        ticker: str,
        filing_type: str,
        fiscal_period_end: datetime,
        search_window_days: int = 180
    ) -> Optional[datetime]:
        """
        Query SEC EDGAR to find the actual filing date for a specific filing.

        Args:
            ticker: Company ticker symbol
            filing_type: Type of filing ("10-K" or "10-Q")
            fiscal_period_end: End date of the fiscal period
            search_window_days: How many days after period end to search (default: 180)

        Returns:
            Filing date if found, None otherwise
        """
        # Define search date range
        start_date = fiscal_period_end.strftime("%Y-%m-%d")
        end_date = (fiscal_period_end + timedelta(days=search_window_days)).strftime("%Y-%m-%d")

        # Construct query
        # Note: periodOfReport should match the fiscal_period_end
        period_str = fiscal_period_end.strftime("%Y-%m-%d")

        query = (
            f'ticker:{ticker} AND '
            f'formType:"{filing_type}" AND '
            f'periodOfReport:"{period_str}"'
        )

        search_params = {
            "query": query,
            "from": "0",
            "size": "10",
            "sort": [{"filedAt": {"order": "asc"}}]
        }

        try:
            response = self.query_api.get_filings(search_params)

            if response.get("filings") and len(response["filings"]) > 0:
                # Get the first filing (earliest filed)
                filing = response["filings"][0]
                filed_at = filing.get("filedAt")

                if filed_at:
                    # Parse the filing date (format: "2024-10-28 00:00:00")
                    return datetime.strptime(filed_at.split()[0], "%Y-%m-%d")

            return None

        except Exception as e:
            print(f"Error querying SEC API: {e}")
            return None

    def check_filing_status(
        self,
        ticker: str,
        fiscal_period_end: datetime,
        filing_type: str,
        public_float: float,
        actual_filing_date: Optional[datetime] = None
    ) -> Dict:
        """
        Check if a filing is delayed or missing.

        Args:
            ticker: Company ticker symbol
            fiscal_period_end: End date of the fiscal period
            filing_type: Type of filing ("10-K" or "10-Q")
            public_float: Public float value in USD
            actual_filing_date: Optional actual filing date. If None, will query SEC API.

        Returns:
            Dictionary with status information:
                - ticker
                - filing_type
                - fiscal_period_end
                - filer_status
                - statutory_due_date
                - actual_filing_date (if found)
                - is_delayed (boolean)
                - days_late (if delayed)
                - status_message
        """
        filer_status = self.classify_filer(public_float)
        due_date = self.calculate_statutory_due_date(
            fiscal_period_end, filing_type, public_float
        )

        # If actual filing date not provided, query SEC API
        if actual_filing_date is None:
            actual_filing_date = self.get_actual_filing_date(
                ticker, filing_type, fiscal_period_end
            )

        today = datetime.now()
        is_delayed = False
        days_late = None
        status_message = ""

        if actual_filing_date:
            # Filing exists - check if it was late
            if actual_filing_date > due_date:
                is_delayed = True
                days_late = (actual_filing_date - due_date).days
                status_message = f"DELAYED: Filed {days_late} days late on {actual_filing_date.date()}"
            else:
                status_message = f"ON TIME: Filed on {actual_filing_date.date()}"
        else:
            # Filing not found - check if it's past due
            if today > due_date:
                is_delayed = True
                days_late = (today - due_date).days
                status_message = f"MISSING: {days_late} days past due (due: {due_date.date()})"
            else:
                days_until_due = (due_date - today).days
                status_message = f"PENDING: Due in {days_until_due} days ({due_date.date()})"

        return {
            "ticker": ticker,
            "filing_type": filing_type,
            "fiscal_period_end": fiscal_period_end.date(),
            "filer_status": filer_status,
            "public_float": public_float,
            "statutory_due_date": due_date.date(),
            "actual_filing_date": actual_filing_date.date() if actual_filing_date else None,
            "is_delayed": is_delayed,
            "days_late": days_late,
            "status": status_message
        }

    def monitor_companies(
        self,
        companies: List[Dict]
    ) -> pd.DataFrame:
        """
        Monitor multiple companies for filing delays.

        Args:
            companies: List of dictionaries, each containing:
                - ticker (str)
                - fiscal_period_end (datetime)
                - filing_type (str)
                - public_float (float)
                - actual_filing_date (datetime, optional)

        Returns:
            DataFrame with monitoring results
        """
        results = []

        for company in companies:
            result = self.check_filing_status(
                ticker=company["ticker"],
                fiscal_period_end=company["fiscal_period_end"],
                filing_type=company["filing_type"],
                public_float=company["public_float"],
                actual_filing_date=company.get("actual_filing_date")
            )
            results.append(result)

        return pd.DataFrame(results)

    def find_delayed_filings(
        self,
        tickers: List[str],
        filing_type: str,
        public_float_map: Dict[str, float],
        fiscal_period_end: datetime
    ) -> pd.DataFrame:
        """
        Scan multiple companies and identify delayed filings.

        Args:
            tickers: List of ticker symbols to check
            filing_type: Type of filing ("10-K" or "10-Q")
            public_float_map: Dictionary mapping ticker to public float
            fiscal_period_end: Fiscal period end date

        Returns:
            DataFrame with only delayed or missing filings
        """
        companies = [
            {
                "ticker": ticker,
                "fiscal_period_end": fiscal_period_end,
                "filing_type": filing_type,
                "public_float": public_float_map.get(ticker, 0)
            }
            for ticker in tickers
        ]

        all_results = self.monitor_companies(companies)
        delayed = all_results[all_results["is_delayed"] == True]

        return delayed


def main():
    """Example usage of the Filing Monitor."""

    # Example 1: Check a single company
    print("=" * 80)
    print("Example 1: Check Apple's 10-K for fiscal year ending Sept 30, 2024")
    print("=" * 80)

    # Note: Replace with your actual API key
    api_key = "YOUR_API_KEY_HERE"  # or set SEC_API_KEY environment variable

    try:
        monitor = FilingMonitor(api_key=api_key)

        result = monitor.check_filing_status(
            ticker="AAPL",
            fiscal_period_end=datetime(2024, 9, 30),
            filing_type="10-K",
            public_float=3_000_000_000_000  # $3 trillion
        )

        print(f"\nTicker: {result['ticker']}")
        print(f"Filing Type: {result['filing_type']}")
        print(f"Fiscal Period End: {result['fiscal_period_end']}")
        print(f"Filer Status: {result['filer_status']}")
        print(f"Statutory Due Date: {result['statutory_due_date']}")
        print(f"Actual Filing Date: {result['actual_filing_date']}")
        print(f"Status: {result['status']}")

    except ValueError as e:
        print(f"\nError: {e}")
        print("\nTo run this example:")
        print("1. Get a free API key from https://sec-api.io")
        print("2. Either set SEC_API_KEY environment variable or modify api_key in the script")

    # Example 2: Monitor multiple companies
    print("\n" + "=" * 80)
    print("Example 2: Monitor multiple companies")
    print("=" * 80)

    companies_to_monitor = [
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
            "ticker": "TSLA",
            "fiscal_period_end": datetime(2024, 12, 31),
            "filing_type": "10-K",
            "public_float": 850_000_000_000,
        }
    ]

    print("\nCompanies to monitor:")
    for c in companies_to_monitor:
        print(f"  - {c['ticker']}: {c['filing_type']} for period ending {c['fiscal_period_end'].date()}")

    print("\nNote: Uncomment the code below to run the actual monitoring")
    print("(requires valid API key)")

    # Uncomment to run:
    # try:
    #     monitor = FilingMonitor(api_key=api_key)
    #     results_df = monitor.monitor_companies(companies_to_monitor)
    #     print("\n" + results_df.to_string())
    # except Exception as e:
    #     print(f"Error: {e}")

    # Example 3: Calculate due dates without API
    print("\n" + "=" * 80)
    print("Example 3: Calculate statutory due dates (no API required)")
    print("=" * 80)

    test_cases = [
        ("Large Accelerated Filer", 850_000_000_000, "10-K", datetime(2024, 12, 31)),
        ("Accelerated Filer", 100_000_000_000, "10-K", datetime(2024, 12, 31)),
        ("Non-Accelerated Filer", 50_000_000_000, "10-K", datetime(2024, 12, 31)),
        ("Large Accelerated Filer", 850_000_000_000, "10-Q", datetime(2024, 9, 30)),
    ]

    for name, public_float, filing_type, period_end in test_cases:
        filer_status = FilingMonitor.classify_filer(public_float)
        due_date = FilingMonitor.calculate_statutory_due_date(
            period_end, filing_type, public_float
        )
        days = FilingMonitor.DEADLINES[filing_type][filer_status]

        print(f"\n{name}:")
        print(f"  Public Float: ${public_float:,.0f}")
        print(f"  Filing: {filing_type} for period ending {period_end.date()}")
        print(f"  Filer Status: {filer_status}")
        print(f"  Deadline: {days} days after period end")
        print(f"  Due Date: {due_date.date()}")


if __name__ == "__main__":
    main()
