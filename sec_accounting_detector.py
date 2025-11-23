#!/usr/bin/env python3
"""
SEC Accounting Changes Detector
Finds accounting methodology changes in recent SEC filings using sec-api.io
"""

from sec_api import FullTextSearchApi, QueryApi
import requests
import json
from datetime import datetime, timedelta
import time


class AccountingChangesDetector:
    def __init__(self, api_key):
        """
        Initialize the detector with SEC API key

        Args:
            api_key: Your sec-api.io API key
        """
        self.full_text_api = FullTextSearchApi(api_key=api_key)
        self.query_api = QueryApi(api_key=api_key)
        self.api_key = api_key

    def search_methodology_changes(self, days_back=180, form_types=None, ticker=None):
        """
        Search for accounting methodology changes in recent filings

        Args:
            days_back: Number of days to look back (default: 180)
            form_types: List of form types to search (default: ["10-Q", "10-K"])
            ticker: Optional specific ticker to search (e.g., "NVDA")

        Returns:
            List of filings with potential methodology changes
        """
        if form_types is None:
            form_types = ["10-Q", "10-K"]

        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)

        # Search queries for different types of changes
        search_patterns = [
            '"previously" AND ("revenue recognition" OR "geographic revenue")',
            '"changed our" AND ("accounting" OR "presentation" OR "methodology")',
            '"customer headquarters" OR "billing location"',
            '"reclassified" AND "segment"',
            '"recast" OR "restated"',
            '"geographic revenue based"'
        ]

        all_findings = []

        for pattern in search_patterns:
            print(f"\nSearching for: {pattern}")

            # Build query
            query = {
                "query": pattern,
                "formTypes": form_types,
                "startDate": start_date.strftime("%Y-%m-%d"),
                "endDate": end_date.strftime("%Y-%m-%d"),
                "page": "1"
            }

            # Add ticker filter if specified
            if ticker:
                query["query"] = f'{pattern} AND ticker:{ticker}'

            try:
                results = self.full_text_api.get_filings(query)

                if 'filings' in results:
                    for filing in results['filings']:
                        finding = {
                            'pattern': pattern,
                            'ticker': filing.get('ticker', 'N/A'),
                            'company': filing.get('companyNameLong', 'N/A'),
                            'cik': filing.get('cik', 'N/A'),
                            'form': filing.get('formType', 'N/A'),
                            'date': filing.get('filedAt', 'N/A'),
                            'url': filing.get('filingUrl', 'N/A'),
                            'accession_no': filing.get('accessionNo', 'N/A')
                        }

                        # Avoid duplicates
                        if not any(f['accession_no'] == finding['accession_no'] for f in all_findings):
                            all_findings.append(finding)

                    print(f"  Found {len(results['filings'])} matches")
                else:
                    print(f"  No results found")

                # Rate limiting
                time.sleep(0.2)

            except Exception as e:
                print(f"  Error: {e}")

        return all_findings

    def search_nvidia_specific(self):
        """
        Search specifically for Nvidia's geographic revenue changes

        Returns:
            List of relevant Nvidia filings
        """
        print("\n" + "="*80)
        print("NVIDIA GEOGRAPHIC REVENUE CHANGE DETECTION")
        print("="*80)

        # Nvidia's CIK
        nvidia_cik = "0001045810"

        query = {
            "query": '"geographic revenue" AND ("customer headquarters" OR "billing location")',
            "ciks": [nvidia_cik],
            "formTypes": ["10-Q", "10-K"],
            "startDate": "2024-01-01",
            "endDate": datetime.now().strftime("%Y-%m-%d")
        }

        try:
            results = self.full_text_api.get_filings(query)

            findings = []
            if 'filings' in results:
                for filing in results['filings']:
                    finding = {
                        'ticker': filing.get('ticker', 'N/A'),
                        'company': filing.get('companyNameLong', 'N/A'),
                        'form': filing.get('formType', 'N/A'),
                        'date': filing.get('filedAt', 'N/A'),
                        'url': filing.get('filingUrl', 'N/A'),
                        'description': 'Geographic revenue methodology change'
                    }
                    findings.append(finding)

                print(f"\nFound {len(findings)} Nvidia filings with geographic revenue mentions")

                for finding in findings:
                    print(f"\n  Form: {finding['form']}")
                    print(f"  Date: {finding['date']}")
                    print(f"  URL: {finding['url']}")
            else:
                print("\nNo Nvidia filings found")

            return findings

        except Exception as e:
            print(f"\nError searching Nvidia filings: {e}")
            return []

    def extract_section(self, filing_url, form_type):
        """
        Extract relevant section from a filing

        Args:
            filing_url: URL of the filing
            form_type: Type of form (10-K, 10-Q, 8-K)

        Returns:
            Extracted text content
        """
        # Determine which section to extract
        if "10-K" in form_type:
            item = "8"  # Financial Statements and Supplementary Data
        elif "10-Q" in form_type:
            item = "part1item1"  # Financial Statements
        else:
            return None

        url = "https://api.sec-api.io/extractor"
        params = {
            "url": filing_url,
            "item": item,
            "type": "text",
            "token": self.api_key
        }

        try:
            print(f"  Extracting {item} from filing...")
            response = requests.get(url, params=params, timeout=30)

            if response.status_code == 200:
                return response.text
            else:
                return f"Error: HTTP {response.status_code}"
        except Exception as e:
            return f"Error: {e}"

    def analyze_finding(self, finding):
        """
        Analyze a specific finding for accounting changes

        Args:
            finding: Dictionary containing filing information

        Returns:
            Dictionary with analysis results
        """
        print(f"\n{'='*80}")
        print(f"Analyzing {finding['ticker']} - {finding['form']} - {finding['date']}")
        print(f"{'='*80}")

        # Extract the relevant section
        content = self.extract_section(finding['url'], finding['form'])

        if not content or "Error" in content:
            return {'status': 'extraction_failed', 'error': content}

        # Keywords that indicate changes
        change_keywords = [
            'previously', 'changed our', 'methodology', 'reclassified',
            'restated', 'recast', 'customer headquarters', 'billing location',
            'geographic revenue', 'segment reporting', 'ship-to location'
        ]

        # Find relevant paragraphs
        relevant_sections = []
        lines = content.split('\n')

        for i, line in enumerate(lines):
            if any(keyword in line.lower() for keyword in change_keywords):
                # Get context (5 lines before and after)
                start = max(0, i - 5)
                end = min(len(lines), i + 6)
                context = '\n'.join(lines[start:end])

                relevant_sections.append({
                    'line_number': i,
                    'matched_line': line.strip(),
                    'context': context
                })

        return {
            'status': 'success',
            'finding': finding,
            'relevant_sections': relevant_sections,
            'total_matches': len(relevant_sections)
        }

    def generate_report(self, findings, output_file='accounting_changes_report.json'):
        """
        Generate a JSON report of all findings

        Args:
            findings: List of findings
            output_file: Path to output JSON file
        """
        report = {
            'generated_at': datetime.now().isoformat(),
            'total_findings': len(findings),
            'findings': findings
        }

        with open(output_file, 'w') as f:
            json.dump(report, f, indent=2)

        print(f"\nReport saved to {output_file}")

        # Print summary
        print(f"\n{'='*80}")
        print(f"SUMMARY: Found {len(findings)} potential accounting changes")
        print(f"{'='*80}")

        # Group by ticker
        by_ticker = {}
        for finding in findings:
            ticker = finding['ticker']
            if ticker not in by_ticker:
                by_ticker[ticker] = []
            by_ticker[ticker].append(finding)

        print(f"\nUnique companies: {len(by_ticker)}")

        # Show top companies by number of findings
        sorted_tickers = sorted(by_ticker.items(), key=lambda x: len(x[1]), reverse=True)

        print(f"\nTop companies with accounting changes:")
        for ticker, items in sorted_tickers[:10]:
            company_name = items[0]['company']
            print(f"  {ticker} ({company_name}): {len(items)} finding(s)")

        print(f"\nFirst 5 detailed findings:")
        for i, finding in enumerate(findings[:5], 1):
            print(f"\n{i}. {finding['ticker']} - {finding['company']}")
            print(f"   Form: {finding['form']} | Date: {finding['date']}")
            print(f"   Pattern: {finding['pattern']}")
            print(f"   URL: {finding['url']}")


def main():
    """Main execution function"""

    # API Key
    API_KEY = "0cced11055b8c44b38e89fa66706ad19f99602f9d4d28d0a696ded9ebfc905d5"

    print("="*80)
    print("SEC ACCOUNTING CHANGES DETECTOR")
    print("Using sec-api.io to find methodology changes in SEC filings")
    print("="*80)

    # Initialize detector
    detector = AccountingChangesDetector(API_KEY)

    # Menu
    print("\nWhat would you like to do?")
    print("1. Search for Nvidia's geographic revenue changes (specific)")
    print("2. Search all companies for accounting changes (last 6 months)")
    print("3. Search specific ticker for accounting changes")
    print("4. Analyze a specific finding in detail")

    choice = input("\nEnter choice (1-4): ").strip()

    if choice == "1":
        # Nvidia specific search
        findings = detector.search_nvidia_specific()

        if findings:
            detector.generate_report(findings, 'nvidia_findings.json')

            # Optionally analyze first finding
            if findings:
                analyze = input("\nAnalyze first finding in detail? (y/n): ").strip().lower()
                if analyze == 'y':
                    analysis = detector.analyze_finding(findings[0])

                    if analysis['status'] == 'success':
                        print(f"\nFound {analysis['total_matches']} relevant sections")
                        for i, section in enumerate(analysis['relevant_sections'][:3], 1):
                            print(f"\n--- Section {i} (line {section['line_number']}) ---")
                            print(section['context'][:800])

    elif choice == "2":
        # Broad search
        print("\nScanning SEC filings for accounting methodology changes (last 6 months)...")
        findings = detector.search_methodology_changes(days_back=180)

        if findings:
            detector.generate_report(findings, 'all_accounting_changes.json')

    elif choice == "3":
        # Ticker-specific search
        ticker = input("\nEnter ticker symbol (e.g., AAPL): ").strip().upper()
        days = input("Days to look back (default 180): ").strip()
        days = int(days) if days.isdigit() else 180

        print(f"\nSearching {ticker} for accounting changes...")
        findings = detector.search_methodology_changes(days_back=days, ticker=ticker)

        if findings:
            detector.generate_report(findings, f'{ticker.lower()}_findings.json')

    elif choice == "4":
        # Analyze specific finding
        print("\nPlease run a search first (options 1-3) to generate findings.")

    else:
        print("\nInvalid choice. Please run again and select 1-4.")

    print("\n" + "="*80)
    print("Detection complete!")
    print("="*80)


if __name__ == "__main__":
    main()
