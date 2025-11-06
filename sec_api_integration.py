"""
SEC API Integration Module
===========================

Integration layer for sec-api.io to retrieve actual filing data from SEC EDGAR.
This module provides functions to:
- Query filings by company (ticker or CIK)
- Retrieve public float from XBRL data
- Get actual filing dates
- Build comprehensive company filing profiles

Requires sec-api package: pip install sec-api
API Key required from: https://sec-api.io
"""

from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
import logging
from dataclasses import asdict

try:
    from sec_api import QueryApi, ExtractorApi
except ImportError:
    QueryApi = None
    ExtractorApi = None
    logging.warning(
        "sec-api package not installed. Install with: pip install sec-api"
    )

from sec_filing_monitor import (
    CompanyFilingInfo,
    FilingDelayResult,
    analyze_company_filing,
    batch_analyze_filings,
    generate_delay_report
)

logger = logging.getLogger(__name__)


class SECAPIClient:
    """
    Client for interacting with SEC EDGAR data via sec-api.io.

    Attributes:
        api_key: Your sec-api.io API key
        query_api: QueryApi instance for searching filings
        extractor_api: ExtractorApi instance for extracting XBRL data
    """

    def __init__(self, api_key: str):
        """
        Initialize SEC API client.

        Args:
            api_key: Your sec-api.io API key from https://sec-api.io

        Raises:
            ImportError: If sec-api package is not installed
        """
        if QueryApi is None:
            raise ImportError(
                "sec-api package is required. Install with: pip install sec-api"
            )

        self.api_key = api_key
        self.query_api = QueryApi(api_key=api_key)
        self.extractor_api = ExtractorApi(api_key=api_key)
        logger.info("SEC API Client initialized")

    def get_filings(
        self,
        ticker: Optional[str] = None,
        cik: Optional[str] = None,
        form_type: str = "10-K",
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        max_results: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Query SEC filings for a company.

        Args:
            ticker: Company ticker symbol (e.g., "AAPL")
            cik: Central Index Key (alternative to ticker)
            form_type: Filing type (e.g., "10-K", "10-Q")
            start_date: Start of date range to search
            end_date: End of date range to search
            max_results: Maximum number of results to return

        Returns:
            List of filing dictionaries with metadata

        Raises:
            ValueError: If neither ticker nor CIK is provided
        """
        if not ticker and not cik:
            raise ValueError("Must provide either ticker or CIK")

        # Build query
        query_parts = []

        if ticker:
            query_parts.append(f'ticker:{ticker}')
        elif cik:
            query_parts.append(f'cik:{cik}')

        query_parts.append(f'formType:"{form_type}"')

        # Add date range if provided
        if start_date or end_date:
            start_str = start_date.strftime("%Y-%m-%d") if start_date else "*"
            end_str = end_date.strftime("%Y-%m-%d") if end_date else "*"
            query_parts.append(f'filedAt:[{start_str} TO {end_str}]')

        query_string = " AND ".join(query_parts)

        logger.info(f"Querying SEC filings: {query_string}")

        # Execute query
        search_params = {
            "query": query_string,
            "from": "0",
            "size": str(min(max_results, 50)),  # API limit is 50 per request
            "sort": [{"filedAt": {"order": "desc"}}]
        }

        try:
            response = self.query_api.get_filings(search_params)
            filings = response.get("filings", [])
            logger.info(f"Found {len(filings)} filings")
            return filings
        except Exception as e:
            logger.error(f"Error querying SEC API: {e}")
            raise

    def get_latest_filing(
        self,
        ticker: str,
        form_type: str,
        period_end_date: Optional[datetime] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Get the most recent filing of a specific type for a company.

        Args:
            ticker: Company ticker symbol
            form_type: Filing type (e.g., "10-K", "10-Q")
            period_end_date: Optional fiscal period end to filter for

        Returns:
            Filing dictionary or None if not found
        """
        # Search with a reasonable date range
        end_date = datetime.now()
        start_date = period_end_date - timedelta(days=180) if period_end_date else end_date - timedelta(days=365)

        filings = self.get_filings(
            ticker=ticker,
            form_type=form_type,
            start_date=start_date,
            end_date=end_date,
            max_results=10
        )

        if not filings:
            logger.warning(f"No {form_type} filings found for {ticker}")
            return None

        # If period_end_date specified, try to match it
        if period_end_date:
            for filing in filings:
                period_of_report = filing.get("periodOfReport")
                if period_of_report:
                    filing_period = datetime.strptime(period_of_report, "%Y-%m-%d")
                    if filing_period.date() == period_end_date.date():
                        return filing

        # Return most recent filing
        return filings[0]

    def extract_public_float(self, filing_url: str) -> Optional[float]:
        """
        Extract public float from a filing's XBRL data.

        The public float is typically found in the 10-K filing's cover page
        under the tag 'EntityPublicFloat'.

        Args:
            filing_url: URL to the filing details page

        Returns:
            Public float value in USD, or None if not found

        Note:
            This requires the ExtractorApi which may need additional setup.
        """
        try:
            # Extract XBRL data
            xbrl_data = self.extractor_api.get_xbrl(filing_url)

            # Look for public float in various possible locations
            float_tags = [
                "EntityPublicFloat",
                "dei:EntityPublicFloat",
            ]

            for tag in float_tags:
                if tag in xbrl_data:
                    value = xbrl_data[tag]
                    if isinstance(value, dict):
                        return float(value.get("value", 0))
                    return float(value)

            logger.warning("Public float not found in XBRL data")
            return None

        except Exception as e:
            logger.error(f"Error extracting public float: {e}")
            return None

    def build_company_filing_info(
        self,
        ticker: str,
        fiscal_period_end: datetime,
        filing_type: str,
        public_float: Optional[float] = None
    ) -> CompanyFilingInfo:
        """
        Build a complete CompanyFilingInfo object by querying SEC API.

        Args:
            ticker: Company ticker symbol
            fiscal_period_end: End date of fiscal period
            filing_type: Type of filing (e.g., "10-K", "10-Q")
            public_float: Optional pre-fetched public float value

        Returns:
            CompanyFilingInfo object populated with SEC data
        """
        logger.info(f"Building filing info for {ticker} - {filing_type}")

        # Get the latest filing for this period
        filing = self.get_latest_filing(ticker, filing_type, fiscal_period_end)

        # Extract basic info
        company_name = None
        cik = None
        actual_filing_date = None

        if filing:
            company_name = filing.get("companyName")
            cik = filing.get("cik")

            # Parse filing date
            filed_at = filing.get("filedAt")
            if filed_at:
                # Format: "2024-10-28 00:00:00"
                actual_filing_date = datetime.strptime(
                    filed_at.split()[0], "%Y-%m-%d"
                )

            # Try to extract public float if not provided
            if public_float is None and filing_type == "10-K":
                filing_url = filing.get("linkToFilingDetails")
                if filing_url:
                    public_float = self.extract_public_float(filing_url)

        return CompanyFilingInfo(
            ticker=ticker,
            cik=cik,
            company_name=company_name,
            fiscal_period_end=fiscal_period_end,
            filing_type=filing_type,
            public_float=public_float,
            actual_filing_date=actual_filing_date
        )

    def monitor_tickers(
        self,
        tickers: List[str],
        fiscal_period_end: datetime,
        filing_type: str,
        public_floats: Optional[Dict[str, float]] = None
    ) -> List[FilingDelayResult]:
        """
        Monitor filing delays for a list of tickers.

        Args:
            tickers: List of company ticker symbols
            fiscal_period_end: Fiscal period end date to check
            filing_type: Type of filing (e.g., "10-K", "10-Q")
            public_floats: Optional dict mapping ticker to public float

        Returns:
            List of FilingDelayResult objects
        """
        public_floats = public_floats or {}
        companies = []

        for ticker in tickers:
            try:
                public_float = public_floats.get(ticker)
                company_info = self.build_company_filing_info(
                    ticker=ticker,
                    fiscal_period_end=fiscal_period_end,
                    filing_type=filing_type,
                    public_float=public_float
                )

                if company_info.public_float is None:
                    logger.warning(
                        f"Could not determine public float for {ticker}. "
                        "Manual input required."
                    )
                    continue

                companies.append(company_info)

            except Exception as e:
                logger.error(f"Error processing {ticker}: {e}")
                continue

        # Analyze all companies
        return batch_analyze_filings(companies)


def monitor_portfolio(
    api_key: str,
    portfolio: List[Dict[str, Any]],
    show_all: bool = False
) -> str:
    """
    Monitor filing delays for a portfolio of companies.

    Args:
        api_key: sec-api.io API key
        portfolio: List of dicts with keys: ticker, fiscal_period_end,
                   filing_type, public_float (optional)
        show_all: If True, show all filings; if False, only show delays

    Returns:
        Formatted report string

    Example:
        >>> portfolio = [
        ...     {
        ...         "ticker": "AAPL",
        ...         "fiscal_period_end": datetime(2024, 9, 30),
        ...         "filing_type": "10-K",
        ...         "public_float": 3_000_000_000_000
        ...     },
        ...     {
        ...         "ticker": "MSFT",
        ...         "fiscal_period_end": datetime(2024, 6, 30),
        ...         "filing_type": "10-K",
        ...         "public_float": 2_500_000_000_000
        ...     }
        ... ]
        >>> report = monitor_portfolio("YOUR_API_KEY", portfolio)
        >>> print(report)
    """
    client = SECAPIClient(api_key)
    companies = []

    for item in portfolio:
        try:
            company_info = client.build_company_filing_info(
                ticker=item["ticker"],
                fiscal_period_end=item["fiscal_period_end"],
                filing_type=item["filing_type"],
                public_float=item.get("public_float")
            )

            if company_info.public_float is None:
                logger.warning(
                    f"Skipping {item['ticker']}: public float could not be determined"
                )
                continue

            companies.append(company_info)

        except Exception as e:
            logger.error(f"Error processing {item['ticker']}: {e}")
            continue

    # Analyze and generate report
    results = batch_analyze_filings(companies)
    return generate_delay_report(results, show_all=show_all)


# Example usage
if __name__ == "__main__":
    print("SEC API Integration Module - Test Mode\n")
    print("This module requires a valid sec-api.io API key.")
    print("Set your API key as an environment variable or pass it directly.\n")

    # Example: Monitor specific tickers
    example_code = '''
    # Example 1: Monitor a single company
    from datetime import datetime

    api_key = "YOUR_API_KEY_HERE"
    client = SECAPIClient(api_key)

    results = client.monitor_tickers(
        tickers=["AAPL", "MSFT", "GOOGL"],
        fiscal_period_end=datetime(2024, 9, 30),
        filing_type="10-K",
        public_floats={
            "AAPL": 3_000_000_000_000,
            "MSFT": 2_500_000_000_000,
            "GOOGL": 1_800_000_000_000
        }
    )

    # Generate report
    from sec_filing_monitor import generate_delay_report
    print(generate_delay_report(results, show_all=True))

    # Example 2: Monitor a portfolio
    portfolio = [
        {
            "ticker": "AAPL",
            "fiscal_period_end": datetime(2024, 9, 30),
            "filing_type": "10-K",
            "public_float": 3_000_000_000_000
        },
        {
            "ticker": "TSLA",
            "fiscal_period_end": datetime(2024, 12, 31),
            "filing_type": "10-K",
            "public_float": 800_000_000_000
        }
    ]

    report = monitor_portfolio(api_key, portfolio, show_all=True)
    print(report)
    '''

    print("Example usage:")
    print(example_code)
