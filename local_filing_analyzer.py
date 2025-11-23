#!/usr/bin/env python3
"""
Local Filing Analyzer - Working Alternative

This script uses the Query API (which works!) to get filing URLs,
then downloads and parses them locally to find accounting changes.

This bypasses the full-text search API limitations.
"""

import requests
import json
import re
from datetime import datetime
from bs4 import BeautifulSoup


class LocalFilingAnalyzer:
    def __init__(self, api_key):
        """Initialize with SEC API key"""
        self.api_key = api_key
        self.base_url = "https://api.sec-api.io"
        self.headers = {
            'Authorization': api_key,
            'Content-Type': 'application/json'
        }

    def get_company_filings(self, ticker, form_types=None, limit=10):
        """
        Get recent filings for a company using Query API

        Args:
            ticker: Company ticker symbol (e.g., 'NVDA')
            form_types: List of form types (default: ['10-Q', '10-K'])
            limit: Number of filings to retrieve

        Returns:
            List of filing dictionaries
        """
        if form_types is None:
            form_types = ['10-Q', '10-K']

        # Build query
        form_query = ' OR '.join([f'formType:"{ft}"' for ft in form_types])
        query_string = f'ticker:{ticker} AND ({form_query})'

        query = {
            "query": query_string,
            "from": "0",
            "size": str(limit),
            "sort": [{"filedAt": {"order": "desc"}}]
        }

        print(f"Retrieving {ticker} filings...")

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
                    filings = []
                    for filing in results['filings']:
                        filings.append({
                            'ticker': filing.get('ticker', 'N/A'),
                            'company': filing.get('companyName', filing.get('companyNameLong', 'N/A')),
                            'form': filing.get('formType', 'N/A'),
                            'date': filing.get('filedAt', 'N/A'),
                            'url': filing.get('linkToHtml', filing.get('linkToFilingDetails', 'N/A')),
                            'accession': filing.get('accessionNo', 'N/A')
                        })

                    print(f"✓ Found {len(filings)} filings\n")
                    return filings
                else:
                    print("✗ No filings found")
                    return []
            else:
                print(f"✗ API Error: HTTP {response.status_code}")
                return []

        except Exception as e:
            print(f"✗ Error: {e}")
            return []

    def download_filing(self, url):
        """
        Download filing content from SEC

        Args:
            url: SEC filing URL

        Returns:
            Filing text content
        """
        try:
            print(f"  Downloading: {url[:80]}...")

            # SEC requires proper User-Agent header
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5'
            }

            response = requests.get(url, headers=headers, timeout=30)

            if response.status_code == 200:
                # Parse HTML to extract text
                soup = BeautifulSoup(response.text, 'html.parser')

                # Remove script and style elements
                for script in soup(["script", "style"]):
                    script.decompose()

                # Get text
                text = soup.get_text()

                # Clean up text
                lines = (line.strip() for line in text.splitlines())
                chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
                text = '\n'.join(chunk for chunk in chunks if chunk)

                print(f"  ✓ Downloaded {len(text)} characters")
                return text
            else:
                print(f"  ✗ Download failed: HTTP {response.status_code}")
                return None

        except Exception as e:
            print(f"  ✗ Error downloading: {e}")
            return None

    def search_for_keywords(self, text, keywords):
        """
        Search text for keywords and extract context

        Args:
            text: Text to search
            keywords: List of keywords/phrases

        Returns:
            Dictionary of matches with context
        """
        text_lower = text.lower()
        matches = {}

        for keyword in keywords:
            keyword_lower = keyword.lower()

            if keyword_lower in text_lower:
                # Find all occurrences with context
                contexts = []

                # Use regex to find keyword with surrounding context
                pattern = f'.{{0,300}}{re.escape(keyword_lower)}.{{0,300}}'
                found = re.findall(pattern, text_lower, re.DOTALL)

                # Limit to first 5 matches
                contexts = found[:5]

                matches[keyword] = {
                    'count': text_lower.count(keyword_lower),
                    'contexts': contexts
                }

        return matches

    def analyze_filing_for_changes(self, filing, keywords):
        """
        Download and analyze a single filing for accounting changes

        Args:
            filing: Filing dictionary from get_company_filings()
            keywords: List of keywords to search for

        Returns:
            Dictionary with analysis results
        """
        print(f"\n{'='*80}")
        print(f"Analyzing: {filing['form']} filed {filing['date']}")
        print(f"{'='*80}")

        # Download filing
        content = self.download_filing(filing['url'])

        if not content:
            return {'status': 'download_failed', 'filing': filing}

        # Search for keywords
        matches = self.search_for_keywords(content, keywords)

        if matches:
            print(f"\n✓ Found {len(matches)} keyword matches:")
            for keyword, data in matches.items():
                print(f"  - '{keyword}': {data['count']} occurrence(s)")

            return {
                'status': 'success',
                'filing': filing,
                'matches': matches,
                'total_keywords_found': len(matches)
            }
        else:
            print(f"\n✗ No keywords found")
            return {
                'status': 'no_matches',
                'filing': filing,
                'matches': {}
            }

    def scan_company_for_changes(self, ticker, keywords=None, num_filings=5):
        """
        Scan recent company filings for accounting methodology changes

        Args:
            ticker: Company ticker symbol
            keywords: List of keywords (default: accounting change keywords)
            num_filings: Number of recent filings to scan

        Returns:
            List of analysis results
        """
        if keywords is None:
            keywords = [
                'geographic revenue',
                'customer headquarters',
                'billing location',
                'changed our methodology',
                'changed our presentation',
                'previously, revenue',
                'reclassified',
                'restated',
                'segment reorganization'
            ]

        print("="*80)
        print(f"ACCOUNTING CHANGES SCANNER - {ticker}")
        print("="*80)
        print(f"\nKeywords: {', '.join(keywords)}\n")

        # Get filings
        filings = self.get_company_filings(ticker, limit=num_filings)

        if not filings:
            return []

        # Analyze each filing
        results = []
        for i, filing in enumerate(filings, 1):
            print(f"\n[{i}/{len(filings)}]")
            analysis = self.analyze_filing_for_changes(filing, keywords)
            results.append(analysis)

        # Summary
        print("\n" + "="*80)
        print("SCAN SUMMARY")
        print("="*80)

        filings_with_matches = [r for r in results if r['status'] == 'success']

        print(f"\nTotal filings scanned: {len(results)}")
        print(f"Filings with matches: {len(filings_with_matches)}")

        if filings_with_matches:
            print(f"\nFilings with potential accounting changes:")
            for result in filings_with_matches:
                filing = result['filing']
                print(f"\n  {filing['form']} - {filing['date']}")
                print(f"  Keywords found: {list(result['matches'].keys())}")
                print(f"  URL: {filing['url']}")

        return results

    def generate_report(self, results, output_file='local_analysis_report.json'):
        """
        Generate JSON report of analysis results

        Args:
            results: List of analysis results
            output_file: Output file path
        """
        report = {
            'generated_at': datetime.now().isoformat(),
            'total_filings_analyzed': len(results),
            'filings_with_matches': len([r for r in results if r['status'] == 'success']),
            'results': results
        }

        with open(output_file, 'w') as f:
            json.dump(report, f, indent=2)

        print(f"\n✓ Detailed report saved to {output_file}")

        # Also create human-readable text report
        text_file = output_file.replace('.json', '.txt')
        with open(text_file, 'w') as f:
            f.write("ACCOUNTING CHANGES ANALYSIS REPORT\n")
            f.write("="*80 + "\n\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"Total filings analyzed: {len(results)}\n\n")

            for result in results:
                if result['status'] == 'success':
                    filing = result['filing']
                    f.write(f"\n{'-'*80}\n")
                    f.write(f"Filing: {filing['form']} - {filing['company']}\n")
                    f.write(f"Date: {filing['date']}\n")
                    f.write(f"URL: {filing['url']}\n\n")

                    for keyword, data in result['matches'].items():
                        f.write(f"\nKeyword: '{keyword}' ({data['count']} occurrences)\n")
                        f.write(f"Sample contexts:\n")

                        for i, context in enumerate(data['contexts'][:2], 1):
                            f.write(f"\n  Context {i}:\n")
                            f.write(f"  {context[:400]}...\n")

        print(f"✓ Human-readable report saved to {text_file}")


def main():
    """Main execution"""

    API_KEY = "0cced11055b8c44b38e89fa66706ad19f99602f9d4d28d0a696ded9ebfc905d5"

    analyzer = LocalFilingAnalyzer(API_KEY)

    print("="*80)
    print("LOCAL FILING ANALYZER")
    print("Uses Query API + Local Parsing (NO full-text search needed!)")
    print("="*80 + "\n")

    # Menu
    print("Options:")
    print("1. Scan Nvidia for geographic revenue changes")
    print("2. Scan any company for accounting changes")
    print("3. Quick test - Download and analyze single filing")

    choice = input("\nEnter choice (1-3): ").strip()

    if choice == "1":
        # Nvidia specific
        keywords = [
            'geographic revenue',
            'customer headquarters',
            'billing location',
            'ship-to location',
            'changed our revenue'
        ]

        results = analyzer.scan_company_for_changes('NVDA', keywords=keywords, num_filings=3)
        analyzer.generate_report(results, 'nvidia_local_analysis.json')

    elif choice == "2":
        # Custom company
        ticker = input("\nEnter ticker (e.g., AAPL): ").strip().upper()
        num = input("Number of recent filings to scan (default 5): ").strip()
        num_filings = int(num) if num.isdigit() else 5

        results = analyzer.scan_company_for_changes(ticker, num_filings=num_filings)
        analyzer.generate_report(results, f'{ticker.lower()}_local_analysis.json')

    elif choice == "3":
        # Quick test
        print("\nQuick test: Downloading latest Nvidia 10-Q...")

        filings = analyzer.get_company_filings('NVDA', form_types=['10-Q'], limit=1)

        if filings:
            keywords = ['revenue', 'geographic']
            result = analyzer.analyze_filing_for_changes(filings[0], keywords)

            if result['status'] == 'success':
                print("\n" + "="*80)
                print("SAMPLE CONTEXT:")
                print("="*80)

                for keyword, data in result['matches'].items():
                    print(f"\nKeyword: '{keyword}'")
                    if data['contexts']:
                        print(f"Sample: {data['contexts'][0][:300]}...")

    else:
        print("\nInvalid choice")

    print("\n" + "="*80)
    print("Analysis complete!")
    print("="*80)


if __name__ == "__main__":
    # Install beautifulsoup4 if needed
    try:
        from bs4 import BeautifulSoup
    except ImportError:
        print("Installing beautifulsoup4...")
        import subprocess
        subprocess.check_call(['pip', 'install', 'beautifulsoup4', '--quiet'])
        from bs4 import BeautifulSoup

    main()
