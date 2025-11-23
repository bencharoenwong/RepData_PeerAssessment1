#!/usr/bin/env python3
"""
Multi-Company Accounting Changes Scanner

Scans a list of companies for potential accounting methodology changes
in their recent SEC filings.
"""

import requests
import json
from datetime import datetime, timedelta
import time

API_KEY = "0cced11055b8c44b38e89fa66706ad19f99602f9d4d28d0a696ded9ebfc905d5"

class MultiCompanyScanner:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://api.sec-api.io"
        self.headers = {
            'Authorization': api_key,
            'Content-Type': 'application/json'
        }

    def get_recent_filings(self, ticker, form_types=['10-Q', '10-K'], limit=3):
        """Get recent filings for a company"""
        form_query = ' OR '.join([f'formType:"{ft}"' for ft in form_types])
        query_string = f'ticker:{ticker} AND ({form_query})'

        query = {
            "query": query_string,
            "from": "0",
            "size": str(limit),
            "sort": [{"filedAt": {"order": "desc"}}]
        }

        try:
            response = requests.post(
                self.base_url,
                headers=self.headers,
                json=query,
                timeout=30
            )

            if response.status_code == 200:
                results = response.json()
                if 'filings' in results:
                    return results['filings']
            return []
        except Exception as e:
            print(f"  ✗ Error getting filings for {ticker}: {e}")
            return []

    def extract_filing_section(self, filing_url, form_type):
        """Extract relevant section from a filing using Extractor API"""
        # Determine which section to extract
        if "10-K" in form_type:
            item = "8"  # Item 8: Financial Statements
        elif "10-Q" in form_type:
            item = "part1item1"  # Part I, Item 1: Financial Statements
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
            response = requests.get(url, params=params, timeout=60)

            if response.status_code == 200:
                return response.text
            else:
                return None
        except Exception as e:
            return None

    def search_for_accounting_changes(self, text):
        """Search text for accounting change keywords"""
        if not text:
            return {}

        text_lower = text.lower()

        keywords = {
            'geographic_revenue': ['geographic revenue', 'customer location', 'billing location', 'ship-to location'],
            'methodology_change': ['changed our methodology', 'changed our presentation', 'changed our accounting'],
            'previously': ['previously, revenue', 'previously, we', 'previously reported'],
            'reclassification': ['reclassified', 'reclassification'],
            'restatement': ['restated', 'restatement', 'recast'],
            'segment_change': ['segment reorganization', 'reportable segments', 'segment reporting']
        }

        findings = {}

        for category, terms in keywords.items():
            for term in terms:
                if term in text_lower:
                    if category not in findings:
                        findings[category] = []
                    findings[category].append(term)

        return findings

    def scan_company(self, ticker, num_filings=3):
        """Scan a company's recent filings"""
        print(f"\n{'='*80}")
        print(f"Scanning: {ticker}")
        print(f"{'='*80}")

        # Get recent filings
        filings = self.get_recent_filings(ticker, limit=num_filings)

        if not filings:
            print(f"  ✗ No filings found for {ticker}")
            return {
                'ticker': ticker,
                'status': 'no_filings',
                'filings_analyzed': 0,
                'findings': []
            }

        print(f"  Found {len(filings)} recent filings")

        results = []

        for i, filing in enumerate(filings, 1):
            form_type = filing.get('formType', 'N/A')
            filed_date = filing.get('filedAt', 'N/A')
            filing_url = filing.get('linkToFilingDetails', filing.get('linkToHtml', 'N/A'))

            print(f"\n  [{i}/{len(filings)}] {form_type} - {filed_date[:10]}")
            print(f"      Extracting section...")

            # Extract section
            content = self.extract_filing_section(filing_url, form_type)

            if content:
                print(f"      ✓ Extracted {len(content):,} characters")

                # Search for keywords
                findings = self.search_for_accounting_changes(content)

                if findings:
                    print(f"      ✓ Found {len(findings)} keyword categories!")
                    for category, terms in findings.items():
                        print(f"        - {category}: {', '.join(set(terms))}")

                    results.append({
                        'form': form_type,
                        'date': filed_date,
                        'url': filing_url,
                        'findings': findings,
                        'has_findings': True
                    })
                else:
                    print(f"      - No keywords found")
                    results.append({
                        'form': form_type,
                        'date': filed_date,
                        'url': filing_url,
                        'findings': {},
                        'has_findings': False
                    })
            else:
                print(f"      ✗ Extraction failed")
                results.append({
                    'form': form_type,
                    'date': filed_date,
                    'url': filing_url,
                    'findings': {},
                    'has_findings': False,
                    'extraction_failed': True
                })

            # Rate limiting
            time.sleep(1)

        return {
            'ticker': ticker,
            'status': 'success',
            'filings_analyzed': len(filings),
            'findings': results
        }

    def scan_multiple_companies(self, tickers, num_filings_per_company=3):
        """Scan multiple companies"""
        print("\n" + "="*80)
        print("MULTI-COMPANY ACCOUNTING CHANGES SCANNER")
        print("="*80)
        print(f"\nCompanies to scan: {', '.join(tickers)}")
        print(f"Filings per company: {num_filings_per_company}")

        all_results = []

        for i, ticker in enumerate(tickers, 1):
            print(f"\n[{i}/{len(tickers)}]")
            result = self.scan_company(ticker, num_filings=num_filings_per_company)
            all_results.append(result)

            # Longer delay between companies
            if i < len(tickers):
                time.sleep(2)

        return all_results

    def generate_report(self, results, output_file='multi_company_scan_results.json'):
        """Generate comprehensive report"""

        # Summary statistics
        total_companies = len(results)
        companies_with_findings = len([r for r in results if any(f.get('has_findings', False) for f in r.get('findings', []))])
        total_filings = sum(r.get('filings_analyzed', 0) for r in results)
        filings_with_findings = sum(
            len([f for f in r.get('findings', []) if f.get('has_findings', False)])
            for r in results
        )

        report = {
            'generated_at': datetime.now().isoformat(),
            'summary': {
                'total_companies_scanned': total_companies,
                'companies_with_findings': companies_with_findings,
                'total_filings_analyzed': total_filings,
                'filings_with_findings': filings_with_findings
            },
            'results': results
        }

        # Save JSON report
        with open(output_file, 'w') as f:
            json.dump(report, f, indent=2)

        print(f"\n{'='*80}")
        print("SCAN COMPLETE - SUMMARY")
        print(f"{'='*80}")
        print(f"\nTotal companies scanned: {total_companies}")
        print(f"Companies with potential changes: {companies_with_findings}")
        print(f"Total filings analyzed: {total_filings}")
        print(f"Filings with keyword matches: {filings_with_findings}")

        # Detailed findings
        print(f"\n{'='*80}")
        print("COMPANIES WITH POTENTIAL ACCOUNTING CHANGES")
        print(f"{'='*80}")

        for result in results:
            ticker = result['ticker']
            filings_with_matches = [f for f in result.get('findings', []) if f.get('has_findings', False)]

            if filings_with_matches:
                print(f"\n{ticker}:")
                for filing in filings_with_matches:
                    print(f"  {filing['form']} - {filing['date'][:10]}")
                    for category, terms in filing['findings'].items():
                        print(f"    • {category}: {', '.join(set(terms))}")
                    print(f"    URL: {filing['url']}")

        print(f"\n✓ Detailed report saved to: {output_file}")

        # Create human-readable summary
        summary_file = output_file.replace('.json', '_summary.txt')
        with open(summary_file, 'w') as f:
            f.write("MULTI-COMPANY ACCOUNTING CHANGES SCAN\n")
            f.write("="*80 + "\n\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            f.write(f"Companies scanned: {total_companies}\n")
            f.write(f"Companies with findings: {companies_with_findings}\n")
            f.write(f"Total filings analyzed: {total_filings}\n")
            f.write(f"Filings with findings: {filings_with_findings}\n\n")

            f.write("="*80 + "\n")
            f.write("DETAILED FINDINGS\n")
            f.write("="*80 + "\n\n")

            for result in results:
                ticker = result['ticker']
                f.write(f"\n{ticker}\n")
                f.write("-"*80 + "\n")

                filings_with_matches = [f for f in result.get('findings', []) if f.get('has_findings', False)]

                if filings_with_matches:
                    for filing in filings_with_matches:
                        f.write(f"\n{filing['form']} filed {filing['date'][:10]}\n")
                        f.write(f"URL: {filing['url']}\n")
                        f.write(f"\nKeyword matches:\n")
                        for category, terms in filing['findings'].items():
                            f.write(f"  - {category}: {', '.join(set(terms))}\n")
                        f.write("\n")
                else:
                    f.write("No accounting change keywords found in recent filings.\n\n")

        print(f"✓ Summary report saved to: {summary_file}")


def main():
    """Main execution"""

    scanner = MultiCompanyScanner(API_KEY)

    # Sample companies to scan
    sample_companies = [
        'NVDA',  # Nvidia (known geographic revenue change)
        'AAPL',  # Apple
        'MSFT',  # Microsoft
        'GOOGL', # Google
        'AMZN',  # Amazon
        'META',  # Meta
        'TSLA',  # Tesla
        'NFLX',  # Netflix
    ]

    print("\nDefault sample companies:")
    for i, ticker in enumerate(sample_companies, 1):
        print(f"  {i}. {ticker}")

    print("\nOptions:")
    print("1. Scan default sample companies (above)")
    print("2. Enter custom list of tickers")
    print("3. Quick test (just NVDA and AAPL)")

    choice = input("\nEnter choice (1-3): ").strip()

    if choice == "2":
        custom = input("\nEnter tickers separated by commas (e.g., NVDA,AAPL,MSFT): ").strip()
        tickers = [t.strip().upper() for t in custom.split(',') if t.strip()]
    elif choice == "3":
        tickers = ['NVDA', 'AAPL']
    else:
        tickers = sample_companies

    num_filings = input(f"\nNumber of recent filings to check per company (default 3): ").strip()
    num_filings = int(num_filings) if num_filings.isdigit() else 3

    # Run scan
    results = scanner.scan_multiple_companies(tickers, num_filings_per_company=num_filings)

    # Generate report
    scanner.generate_report(results)

    print("\n" + "="*80)
    print("SCAN COMPLETE!")
    print("="*80)


if __name__ == "__main__":
    main()
