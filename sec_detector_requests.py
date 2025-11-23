#!/usr/bin/env python3
"""
SEC Accounting Changes Detector (using requests library directly)
Alternative implementation for environments with SSL issues
"""

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
        self.api_key = api_key
        self.base_url = "https://api.sec-api.io"
        self.headers = {
            'Authorization': api_key,
            'Content-Type': 'application/json'
        }

    def query_api(self, query_params):
        """
        Query the SEC API using Query API endpoint

        Args:
            query_params: Dictionary with query parameters

        Returns:
            JSON response from API
        """
        try:
            response = requests.post(
                self.base_url,
                headers=self.headers,
                json=query_params,
                timeout=30,
                verify=True
            )

            if response.status_code == 200:
                return response.json()
            else:
                return {'error': f'HTTP {response.status_code}: {response.text}'}

        except requests.exceptions.SSLError as e:
            print(f"SSL Error: {e}")
            print("Trying without SSL verification...")
            try:
                response = requests.post(
                    self.base_url,
                    headers=self.headers,
                    json=query_params,
                    timeout=30,
                    verify=False
                )
                return response.json()
            except Exception as e2:
                return {'error': f'SSL retry failed: {e2}'}

        except Exception as e:
            return {'error': str(e)}

    def full_text_search(self, search_params):
        """
        Perform full-text search across SEC filings

        Args:
            search_params: Dictionary with search parameters

        Returns:
            JSON response from API
        """
        url = f"{self.base_url}/full-text-search"

        try:
            response = requests.post(
                url,
                headers=self.headers,
                json=search_params,
                timeout=30,
                verify=True
            )

            if response.status_code == 200:
                return response.json()
            else:
                return {'error': f'HTTP {response.status_code}: {response.text}'}

        except requests.exceptions.SSLError as e:
            print(f"SSL Error: {e}")
            print("Trying without SSL verification...")
            try:
                response = requests.post(
                    url,
                    headers=self.headers,
                    json=search_params,
                    timeout=30,
                    verify=False
                )
                return response.json()
            except Exception as e2:
                return {'error': f'SSL retry failed: {e2}'}

        except Exception as e:
            return {'error': str(e)}

    def search_methodology_changes(self, days_back=180, form_types=None, ticker=None):
        """
        Search for accounting methodology changes in recent filings

        Args:
            days_back: Number of days to look back
            form_types: List of form types to search
            ticker: Optional specific ticker

        Returns:
            List of filings with potential methodology changes
        """
        if form_types is None:
            form_types = ["10-Q", "10-K"]

        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)

        # Search patterns
        search_patterns = [
            '"previously" AND ("revenue recognition" OR "geographic revenue")',
            '"changed our" AND ("accounting" OR "presentation")',
            '"customer headquarters" OR "billing location"',
            '"reclassified" AND "segment"',
            '"geographic revenue based"'
        ]

        all_findings = []

        for pattern in search_patterns:
            print(f"\nSearching for: {pattern}")

            # Build query
            search_query = pattern
            if ticker:
                search_query = f'{pattern} AND ticker:{ticker}'

            params = {
                "query": search_query,
                "formTypes": form_types,
                "startDate": start_date.strftime("%Y-%m-%d"),
                "endDate": end_date.strftime("%Y-%m-%d"),
                "page": "1"
            }

            results = self.full_text_search(params)

            if 'error' in results:
                print(f"  Error: {results['error']}")
                continue

            if 'filings' in results and len(results['filings']) > 0:
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

            time.sleep(0.2)

        return all_findings

    def search_nvidia_specific(self):
        """
        Search specifically for Nvidia's geographic revenue changes
        """
        print("\n" + "="*80)
        print("NVIDIA GEOGRAPHIC REVENUE CHANGE DETECTION")
        print("="*80)

        params = {
            "query": 'ticker:NVDA AND ("geographic revenue" OR "customer headquarters" OR "billing location")',
            "formTypes": ["10-Q", "10-K"],
            "startDate": "2024-01-01",
            "endDate": datetime.now().strftime("%Y-%m-%d"),
            "page": "1"
        }

        results = self.full_text_search(params)

        if 'error' in results:
            print(f"\nError: {results['error']}")
            return []

        findings = []
        if 'filings' in results and len(results['filings']) > 0:
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

            print(f"\nFound {len(findings)} Nvidia filings")

            for finding in findings:
                print(f"\n  Form: {finding['form']}")
                print(f"  Date: {finding['date']}")
                print(f"  URL: {finding['url']}")
        else:
            print("\nNo Nvidia filings found")

        return findings

    def extract_section(self, filing_url, form_type):
        """
        Extract specific section from a filing
        """
        if "10-K" in form_type:
            item = "8"
        elif "10-Q" in form_type:
            item = "part1item1"
        else:
            return None

        url = f"{self.base_url}/extractor"
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

    def generate_report(self, findings, output_file='accounting_changes_report.json'):
        """
        Generate JSON report of findings
        """
        report = {
            'generated_at': datetime.now().isoformat(),
            'total_findings': len(findings),
            'findings': findings
        }

        with open(output_file, 'w') as f:
            json.dump(report, f, indent=2)

        print(f"\n✓ Report saved to {output_file}")

        # Summary
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

        sorted_tickers = sorted(by_ticker.items(), key=lambda x: len(x[1]), reverse=True)

        print(f"\nTop companies with accounting changes:")
        for ticker, items in sorted_tickers[:10]:
            company_name = items[0]['company']
            print(f"  {ticker}: {len(items)} finding(s)")

        print(f"\nFirst 5 detailed findings:")
        for i, finding in enumerate(findings[:5], 1):
            print(f"\n{i}. {finding['ticker']} - {finding['company']}")
            print(f"   Form: {finding['form']} | Date: {finding['date']}")
            print(f"   URL: {finding['url']}")


def main():
    """Main execution"""
    API_KEY = "0cced11055b8c44b38e89fa66706ad19f99602f9d4d28d0a696ded9ebfc905d5"

    print("="*80)
    print("SEC ACCOUNTING CHANGES DETECTOR")
    print("Using sec-api.io to find methodology changes")
    print("="*80)

    detector = AccountingChangesDetector(API_KEY)

    # Menu
    print("\nSelect an option:")
    print("1. Search for Nvidia's geographic revenue changes")
    print("2. Search all companies for accounting changes (6 months)")
    print("3. Search specific ticker for accounting changes")
    print("4. Run a simple test query")

    choice = input("\nEnter choice (1-4): ").strip()

    if choice == "1":
        findings = detector.search_nvidia_specific()
        if findings:
            detector.generate_report(findings, 'nvidia_findings.json')

    elif choice == "2":
        print("\nScanning filings for accounting changes (last 6 months)...")
        findings = detector.search_methodology_changes(days_back=180)
        if findings:
            detector.generate_report(findings, 'all_accounting_changes.json')

    elif choice == "3":
        ticker = input("\nEnter ticker (e.g., AAPL): ").strip().upper()
        days = input("Days to look back (default 180): ").strip()
        days = int(days) if days.isdigit() else 180

        print(f"\nSearching {ticker}...")
        findings = detector.search_methodology_changes(days_back=days, ticker=ticker)
        if findings:
            detector.generate_report(findings, f'{ticker.lower()}_findings.json')

    elif choice == "4":
        # Simple test
        print("\nTesting API connection with simple query...")
        params = {
            "query": "ticker:AAPL AND formType:\"10-Q\"",
            "from": "0",
            "size": "2",
            "sort": [{"filedAt": {"order": "desc"}}]
        }
        results = detector.query_api(params)

        if 'error' in results:
            print(f"Error: {results['error']}")
        elif 'filings' in results:
            print(f"✓ Success! Found {len(results['filings'])} Apple 10-Q filings")
            for filing in results['filings']:
                print(f"  - {filing['formType']} on {filing['filedAt']}")
        else:
            print("Unexpected response format")

    else:
        print("\nInvalid choice")

    print("\n" + "="*80)
    print("Complete!")
    print("="*80)


if __name__ == "__main__":
    main()
