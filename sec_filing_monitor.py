"""
SEC Filing Delay Monitor
========================

A comprehensive tool to monitor SEC filing timeliness and detect potential delays
based on statutory due dates derived from filer status classification.

This module computes statutory due dates for 10-K and 10-Q filings based on:
- Fiscal period end date
- Public float (determines filer status per SEC Rule 12b-2)
- Filing type

It then checks whether filings have been submitted on time and flags delays.

Author: Filing Compliance Monitoring System
Date: 2025
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, List, Tuple
from dataclasses import dataclass
from enum import Enum
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class FilerStatus(Enum):
    """SEC Filer classification based on public float (Rule 12b-2)"""
    LARGE_ACCELERATED = "large_accelerated"
    ACCELERATED = "accelerated"
    NON_ACCELERATED = "non_accelerated"


class FilingType(Enum):
    """Supported SEC filing types"""
    FORM_10K = "10-K"
    FORM_10Q = "10-Q"


# Statutory deadline mapping: {filing_type: {filer_status: days}}
STATUTORY_DEADLINES = {
    FilingType.FORM_10K: {
        FilerStatus.LARGE_ACCELERATED: 60,
        FilerStatus.ACCELERATED: 75,
        FilerStatus.NON_ACCELERATED: 90
    },
    FilingType.FORM_10Q: {
        FilerStatus.LARGE_ACCELERATED: 40,
        FilerStatus.ACCELERATED: 40,
        FilerStatus.NON_ACCELERATED: 45
    }
}


@dataclass
class CompanyFilingInfo:
    """Data structure for company filing information"""
    ticker: str
    cik: Optional[str] = None
    company_name: Optional[str] = None
    fiscal_period_end: Optional[datetime] = None
    filing_type: Optional[str] = None
    public_float: Optional[float] = None
    actual_filing_date: Optional[datetime] = None

    def __str__(self):
        return f"{self.ticker} ({self.company_name or 'Unknown'})"


@dataclass
class FilingDelayResult:
    """Result of delay analysis"""
    company_info: CompanyFilingInfo
    filer_status: FilerStatus
    statutory_due_date: datetime
    is_delayed: bool
    days_delayed: Optional[int] = None
    status_message: str = ""

    def __str__(self):
        status = "DELAYED" if self.is_delayed else "ON TIME"
        delay_info = f" ({self.days_delayed} days late)" if self.days_delayed else ""
        return f"{self.company_info.ticker}: {status}{delay_info}"


def classify_filer(public_float: float) -> FilerStatus:
    """
    Classify filer status based on public float per SEC Rule 12b-2.

    SEC Rule 12b-2 definitions:
    - Large Accelerated Filer: Public float >= $700 million
    - Accelerated Filer: Public float >= $75 million and < $700 million
    - Non-Accelerated Filer: Public float < $75 million

    Args:
        public_float: Company's public float in USD

    Returns:
        FilerStatus enum value

    Examples:
        >>> classify_filer(850_000_000)
        <FilerStatus.LARGE_ACCELERATED: 'large_accelerated'>
        >>> classify_filer(100_000_000)
        <FilerStatus.ACCELERATED: 'accelerated'>
        >>> classify_filer(50_000_000)
        <FilerStatus.NON_ACCELERATED: 'non_accelerated'>
    """
    if public_float >= 700_000_000:
        return FilerStatus.LARGE_ACCELERATED
    elif public_float >= 75_000_000:
        return FilerStatus.ACCELERATED
    else:
        return FilerStatus.NON_ACCELERATED


def statutory_due_date(
    fiscal_period_end: datetime,
    filing_type: str,
    public_float: float
) -> Tuple[datetime, FilerStatus]:
    """
    Compute the statutory due date for SEC filings based on filer type and filing form.

    Statutory deadlines after fiscal period end:

    10-K Filings:
        - Large Accelerated Filer: 60 days
        - Accelerated Filer: 75 days
        - Non-Accelerated Filer: 90 days

    10-Q Filings:
        - Large Accelerated Filer: 40 days
        - Accelerated Filer: 40 days
        - Non-Accelerated Filer: 45 days

    Args:
        fiscal_period_end: End date of the fiscal period
        filing_type: Type of filing (e.g., "10-K", "10-Q")
        public_float: Company's public float in USD

    Returns:
        Tuple of (due_date, filer_status)

    Raises:
        ValueError: If filing type is not supported

    Examples:
        >>> statutory_due_date(datetime(2024, 12, 31), "10-K", 850_000_000)
        (datetime(2025, 3, 1, 0, 0), <FilerStatus.LARGE_ACCELERATED: 'large_accelerated'>)
        >>> statutory_due_date(datetime(2024, 9, 30), "10-Q", 100_000_000)
        (datetime(2024, 11, 9, 0, 0), <FilerStatus.ACCELERATED: 'accelerated'>)
    """
    # Classify the filer
    filer_status = classify_filer(public_float)

    # Map string to enum
    try:
        filing_type_enum = FilingType(filing_type)
    except ValueError:
        raise ValueError(
            f"Unsupported filing type: {filing_type}. "
            f"Supported types: {[ft.value for ft in FilingType]}"
        )

    # Get the appropriate deadline
    days_to_add = STATUTORY_DEADLINES[filing_type_enum][filer_status]

    # Calculate due date
    due_date = fiscal_period_end + timedelta(days=days_to_add)

    logger.debug(
        f"Computed due date for {filing_type} (filer: {filer_status.value}): "
        f"{due_date.date()} ({days_to_add} days after {fiscal_period_end.date()})"
    )

    return due_date, filer_status


def check_filing_delay(
    fiscal_period_end: datetime,
    filing_type: str,
    public_float: float,
    actual_filing_date: Optional[datetime] = None,
    reference_date: Optional[datetime] = None
) -> FilingDelayResult:
    """
    Determine if a filing is delayed based on statutory requirements.

    Logic:
    1. If actual_filing_date is provided: Compare it to statutory due date
    2. If no actual_filing_date: Compare reference_date (or today) to due date
       to check if filing is overdue

    Args:
        fiscal_period_end: End date of the fiscal period
        filing_type: Type of filing (e.g., "10-K", "10-Q")
        public_float: Company's public float in USD
        actual_filing_date: Actual date the filing was submitted (if known)
        reference_date: Date to use for comparison (defaults to today)

    Returns:
        FilingDelayResult object containing delay analysis

    Examples:
        >>> # Case 1: Filing was submitted late
        >>> result = check_filing_delay(
        ...     fiscal_period_end=datetime(2024, 12, 31),
        ...     filing_type="10-K",
        ...     public_float=850_000_000,
        ...     actual_filing_date=datetime(2025, 3, 15)
        ... )
        >>> result.is_delayed
        True
        >>> result.days_delayed
        14

        >>> # Case 2: Filing not yet submitted, checking if overdue
        >>> result = check_filing_delay(
        ...     fiscal_period_end=datetime(2024, 12, 31),
        ...     filing_type="10-K",
        ...     public_float=100_000_000,
        ...     actual_filing_date=None,
        ...     reference_date=datetime(2025, 4, 1)
        ... )
        >>> result.is_delayed
        True
    """
    # Compute statutory due date
    due_date, filer_status = statutory_due_date(
        fiscal_period_end, filing_type, public_float
    )

    # Create company info placeholder
    company_info = CompanyFilingInfo(
        ticker="",
        fiscal_period_end=fiscal_period_end,
        filing_type=filing_type,
        public_float=public_float,
        actual_filing_date=actual_filing_date
    )

    # Determine delay status
    if actual_filing_date is not None:
        # Filing has been submitted - check if it was late
        is_delayed = actual_filing_date > due_date
        days_delayed = (actual_filing_date - due_date).days if is_delayed else 0

        if is_delayed:
            status_message = (
                f"Filing submitted {days_delayed} day(s) after statutory deadline. "
                f"Due: {due_date.date()}, Filed: {actual_filing_date.date()}"
            )
        else:
            days_early = (due_date - actual_filing_date).days
            status_message = (
                f"Filing submitted on time, {days_early} day(s) before deadline. "
                f"Due: {due_date.date()}, Filed: {actual_filing_date.date()}"
            )
    else:
        # Filing not yet submitted - check if it's overdue
        check_date = reference_date or datetime.now()
        is_delayed = check_date > due_date
        days_delayed = (check_date - due_date).days if is_delayed else None

        if is_delayed:
            status_message = (
                f"Filing OVERDUE by {days_delayed} day(s). "
                f"Due: {due_date.date()}, Current date: {check_date.date()}"
            )
        else:
            days_remaining = (due_date - check_date).days
            status_message = (
                f"Filing not yet submitted. "
                f"Due in {days_remaining} day(s) on {due_date.date()}"
            )

    return FilingDelayResult(
        company_info=company_info,
        filer_status=filer_status,
        statutory_due_date=due_date,
        is_delayed=is_delayed,
        days_delayed=days_delayed if is_delayed else None,
        status_message=status_message
    )


def analyze_company_filing(company_info: CompanyFilingInfo) -> FilingDelayResult:
    """
    Convenience function to analyze a company's filing delay status.

    Args:
        company_info: CompanyFilingInfo object with all required data

    Returns:
        FilingDelayResult object

    Raises:
        ValueError: If required fields are missing
    """
    # Validate required fields
    if company_info.fiscal_period_end is None:
        raise ValueError(f"fiscal_period_end is required for {company_info.ticker}")
    if company_info.filing_type is None:
        raise ValueError(f"filing_type is required for {company_info.ticker}")
    if company_info.public_float is None:
        raise ValueError(f"public_float is required for {company_info.ticker}")

    # Perform delay check
    result = check_filing_delay(
        fiscal_period_end=company_info.fiscal_period_end,
        filing_type=company_info.filing_type,
        public_float=company_info.public_float,
        actual_filing_date=company_info.actual_filing_date
    )

    # Update company info in result
    result.company_info = company_info

    return result


def batch_analyze_filings(
    companies: List[CompanyFilingInfo]
) -> List[FilingDelayResult]:
    """
    Analyze filing delays for multiple companies.

    Args:
        companies: List of CompanyFilingInfo objects

    Returns:
        List of FilingDelayResult objects
    """
    results = []

    for company in companies:
        try:
            result = analyze_company_filing(company)
            results.append(result)
            logger.info(f"Analyzed {company.ticker}: {result.status_message}")
        except Exception as e:
            logger.error(f"Error analyzing {company.ticker}: {e}")
            continue

    return results


def generate_delay_report(
    results: List[FilingDelayResult],
    show_all: bool = False
) -> str:
    """
    Generate a formatted report of filing delay analysis.

    Args:
        results: List of FilingDelayResult objects
        show_all: If False, only show delayed filings

    Returns:
        Formatted string report
    """
    if show_all:
        filtered_results = results
        header = "SEC FILING STATUS REPORT"
    else:
        filtered_results = [r for r in results if r.is_delayed]
        header = "SEC FILING DELAY REPORT"

    if not filtered_results:
        return "No delayed filings detected." if not show_all else "No filings to report."

    report_lines = [
        "=" * 80,
        header,
        "=" * 80,
        f"Total companies analyzed: {len(results)}",
        f"Delayed filings: {sum(1 for r in results if r.is_delayed)}",
        f"On-time filings: {sum(1 for r in results if not r.is_delayed)}",
        "=" * 80,
        ""
    ]

    for result in filtered_results:
        company = result.company_info
        status = "🔴 DELAYED" if result.is_delayed else "🟢 ON TIME"

        report_lines.extend([
            f"{status} - {company.ticker} ({company.company_name or 'N/A'})",
            f"  Filing Type: {company.filing_type}",
            f"  Filer Status: {result.filer_status.value.replace('_', ' ').title()}",
            f"  Fiscal Period End: {company.fiscal_period_end.date()}",
            f"  Statutory Due Date: {result.statutory_due_date.date()}",
        ])

        if company.actual_filing_date:
            report_lines.append(f"  Actual Filing Date: {company.actual_filing_date.date()}")

        if result.days_delayed:
            report_lines.append(f"  Days Delayed: {result.days_delayed}")

        report_lines.extend([
            f"  Status: {result.status_message}",
            ""
        ])

    report_lines.append("=" * 80)

    return "\n".join(report_lines)


# Example standalone usage
if __name__ == "__main__":
    print("SEC Filing Delay Monitor - Standalone Test\n")

    # Example 1: Large accelerated filer with 10-K (60 days)
    print("Example 1: Large Accelerated Filer (Apple-like company)")
    result1 = check_filing_delay(
        fiscal_period_end=datetime(2024, 9, 30),
        filing_type="10-K",
        public_float=3_000_000_000_000,  # $3 trillion
        actual_filing_date=datetime(2024, 10, 28)
    )
    print(f"Due Date: {result1.statutory_due_date.date()}")
    print(f"Status: {result1.status_message}\n")

    # Example 2: Accelerated filer with 10-Q
    print("Example 2: Accelerated Filer with 10-Q")
    result2 = check_filing_delay(
        fiscal_period_end=datetime(2024, 12, 31),
        filing_type="10-Q",
        public_float=100_000_000,  # $100 million
        actual_filing_date=None,  # Not yet filed
        reference_date=datetime(2025, 3, 1)
    )
    print(f"Due Date: {result2.statutory_due_date.date()}")
    print(f"Status: {result2.status_message}\n")

    # Example 3: Batch analysis
    print("Example 3: Batch Analysis")
    companies = [
        CompanyFilingInfo(
            ticker="AAPL",
            company_name="Apple Inc.",
            fiscal_period_end=datetime(2024, 9, 30),
            filing_type="10-K",
            public_float=3_000_000_000_000,
            actual_filing_date=datetime(2024, 10, 28)
        ),
        CompanyFilingInfo(
            ticker="XYZ",
            company_name="XYZ Corp",
            fiscal_period_end=datetime(2024, 12, 31),
            filing_type="10-K",
            public_float=100_000_000,
            actual_filing_date=None
        ),
    ]

    results = batch_analyze_filings(companies)
    print(generate_delay_report(results, show_all=True))
