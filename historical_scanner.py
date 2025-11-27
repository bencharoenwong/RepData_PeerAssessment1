#!/usr/bin/env python3
"""
Enhanced Historical Accounting Change Scanner
Supports:
- CIK-based scanning (works for delisted companies)
- Date range queries (get ALL filings over time)
- Systematic universe scanning
- Incremental saving for large batches
"""

import requests
import json
import time
from datetime import datetime

class HistoricalAccountingScanner:
    """Scanner with CIK support and date ranges for systematic historical extraction"""

    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://api.sec-api.io"

    def query_api(self, query_params):
        """Query SEC filings using Query API"""
        url = f"{self.base_url}/query"

        headers = {
            "Authorization": self.api_key
        }

        try:
            response = requests.post(url, json=query_params, headers=headers, timeout=30)

            if response.status_code == 200:
                data = response.json()
                return data.get('filings', [])
            else:
                print(f"  ✗ Query API error: {response.status_code}")
                return []

        except Exception as e:
            print(f"  ✗ Query API exception: {str(e)}")
            return []

    def extract_filing(self, filing_url, form_type):
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
        """Search text for accounting change keywords - BROADENED VERSION"""
        if not text:
            return {}

        text_lower = text.lower()

        keywords = {
            'geographic_revenue': [
                # Core terms
                'geographic revenue', 'revenue by geographic', 'geographic distribution of revenue',
                # Regional variations
                'regional revenue', 'revenue by region', 'regional distribution',
                'territorial revenue', 'revenue by territory',
                # International/domestic
                'international revenue', 'domestic revenue', 'revenue from external customers',
                # Location methodology terms
                'customer location', 'billing location', 'ship-to location', 'shipping location',
                'customer headquarters', 'customer domicile', 'invoicing location',
                'point of sale', 'destination', 'origin',
                # Attribution language
                'revenue attribution', 'revenue attributed to', 'attributed to individual countries',
                'revenue designated based on', 'revenue determined by',
                # Basis/methodology statements
                'based on the location', 'based upon the location', 'determined by location',
                'designated based on', 'classified based on'
            ],
            'methodology_change': [
                'changed our methodology', 'changed our presentation', 'changed our accounting',
                'changed the basis', 'modified our methodology', 'revised our methodology',
                'updated our methodology', 'revised our presentation', 'updated our presentation',
                'change in presentation', 'change in methodology', 'change in the basis'
            ],
            'previously': [
                'previously, revenue', 'previously, we', 'previously reported',
                'previously, geographic revenue', 'previously, revenue by geographic',
                'prior to', 'previously disclosed', 'previously presented'
            ],
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
                    if term not in findings[category]:  # Avoid duplicates
                        findings[category].append(term)

        return findings

    def get_all_filings_for_company(self, cik, start_date=None, end_date=None):
        """
        Get ALL filings for a company in date range (handles pagination)

        Args:
            cik: Central Index Key (e.g., "1045810" for Nvidia)
            start_date: "2015-01-01" (optional)
            end_date: "2025-12-31" (optional)

        Returns:
            List of all 10-Q and 10-K filings in range
        """

        # Build date filter
        date_filter = ""
        if start_date and end_date:
            date_filter = f" AND filedAt:[{start_date} TO {end_date}]"

        all_filings = []
        from_index = 0
        batch_size = 200

        print(f"  Fetching filings for CIK {cik}...")

        while True:
            query = {
                "query": f"cik:{cik} AND formType:(10-Q OR 10-K){date_filter}",
                "from": str(from_index),
                "size": str(batch_size),
                "sort": [{"filedAt": {"order": "desc"}}]
            }

            results = self.query_api(query)

            if not results or len(results) == 0:
                break

            all_filings.extend(results)
            print(f"    Retrieved {len(results)} filings (total: {len(all_filings)})")

            if len(results) < batch_size:
                # No more results
                break

            from_index += batch_size
            time.sleep(0.5)  # Rate limiting

        return all_filings

    def scan_company_by_cik(self, cik, start_date=None, end_date=None, company_name=None):
        """
        Scan using CIK (works for delisted companies)

        Args:
            cik: Central Index Key
            start_date: "2015-01-01" (optional, defaults to all filings)
            end_date: "2025-12-31" (optional, defaults to today)
            company_name: Optional display name for output

        Returns:
            Dictionary with scan results
        """

        print(f"\n{'='*80}")
        print(f"Scanning: {company_name or 'Unknown'} (CIK: {cik})")
        if start_date and end_date:
            print(f"Date range: {start_date} to {end_date}")
        print(f"{'='*80}")

        # Get all filings
        filings = self.get_all_filings_for_company(cik, start_date, end_date)

        if not filings:
            print(f"  ✗ No filings found for CIK {cik}")
            return {
                'cik': cik,
                'company_name': company_name,
                'status': 'no_filings',
                'filings_analyzed': 0,
                'findings': []
            }

        # Extract company name from first filing if not provided
        if not company_name:
            company_name = filings[0].get('companyName', 'Unknown')

        print(f"  Found {len(filings)} filings")
        print(f"  Extracting and analyzing...")

        # Process each filing
        results = []
        for i, filing in enumerate(filings):
            filing_date = filing.get('filedAt', 'Unknown')
            form_type = filing.get('formType', 'Unknown')
            filing_url = filing.get('linkToFilingDetails', '')

            # Extract filing content
            content = self.extract_filing(filing_url, form_type)

            if not content:
                print(f"    [{i+1}/{len(filings)}] {form_type} {filing_date}: Extraction failed")
                continue

            # Search for keywords
            findings = self.search_for_accounting_changes(content)

            if findings:
                print(f"    [{i+1}/{len(filings)}] {form_type} {filing_date}: ✓ Findings detected")
                results.append({
                    'filing_date': filing_date,
                    'form_type': form_type,
                    'url': filing_url,
                    'findings': findings,
                    'content_length': len(content)
                })
            else:
                print(f"    [{i+1}/{len(filings)}] {form_type} {filing_date}: No keywords found")

            # Rate limiting
            time.sleep(0.5)

        print(f"\n  Analysis complete: {len(results)} filings with findings out of {len(filings)} total")

        return {
            'cik': cik,
            'company_name': company_name,
            'status': 'success',
            'filings_analyzed': len(filings),
            'filings_with_findings': len(results),
            'findings': results
        }

    def scan_universe(self, cik_list, start_date, end_date, output_file):
        """
        Scan entire universe of companies systematically

        Args:
            cik_list: List of tuples [(cik, company_name), ...]
            start_date: "2015-01-01"
            end_date: "2025-12-31"
            output_file: "universe_scan_results.json"

        Returns:
            Dictionary of all results
        """

        print(f"\n{'='*80}")
        print(f"SYSTEMATIC UNIVERSE SCAN")
        print(f"{'='*80}")
        print(f"Companies: {len(cik_list)}")
        print(f"Date range: {start_date} to {end_date}")
        print(f"Output: {output_file}")
        print(f"{'='*80}\n")

        all_results = {}
        start_time = datetime.now()

        for i, (cik, name) in enumerate(cik_list):
            print(f"\n[{i+1}/{len(cik_list)}] Processing {name}...")

            try:
                results = self.scan_company_by_cik(cik, start_date, end_date, name)

                all_results[cik] = results

                # Save incrementally every 5 companies (in case of failures)
                if (i + 1) % 5 == 0:
                    with open(output_file, 'w') as f:
                        json.dump(all_results, f, indent=2)
                    print(f"\n  💾 Progress saved to {output_file}")

            except Exception as e:
                print(f"  ✗ Error processing {name}: {str(e)}")
                all_results[cik] = {
                    'cik': cik,
                    'company_name': name,
                    'status': 'error',
                    'error': str(e)
                }

            # Rate limiting between companies
            time.sleep(1)

        # Final save
        with open(output_file, 'w') as f:
            json.dump(all_results, f, indent=2)

        elapsed = datetime.now() - start_time
        print(f"\n{'='*80}")
        print(f"SCAN COMPLETE")
        print(f"{'='*80}")
        print(f"Total companies: {len(cik_list)}")
        print(f"Time elapsed: {elapsed}")
        print(f"Results saved: {output_file}")
        print(f"{'='*80}\n")

        # Summary statistics
        companies_with_findings = sum(1 for r in all_results.values()
                                      if r.get('filings_with_findings', 0) > 0)
        total_filings = sum(r.get('filings_analyzed', 0) for r in all_results.values())

        print(f"\nSUMMARY:")
        print(f"  Companies with geographic revenue keywords: {companies_with_findings}/{len(cik_list)} ({companies_with_findings/len(cik_list)*100:.1f}%)")
        print(f"  Total filings analyzed: {total_filings}")

        return all_results


def main():
    """Example usage"""

    # API key
    API_KEY = "0cced11055b8c44b38e89fa66706ad19f99602f9d4d28d0a696ded9ebfc905d5"

    # Initialize scanner
    scanner = HistoricalAccountingScanner(API_KEY)

    # Example 1: Scan single company over 5 years
    print("\n" + "="*80)
    print("EXAMPLE 1: Single Company Historical Scan")
    print("="*80)

    nvidia_results = scanner.scan_company_by_cik(
        cik="1045810",
        start_date="2020-01-01",
        end_date="2025-12-31",
        company_name="NVIDIA"
    )

    print(f"\nNVIDIA Results:")
    print(f"  Filings analyzed: {nvidia_results['filings_analyzed']}")
    print(f"  Filings with findings: {nvidia_results['filings_with_findings']}")

    # Example 2: Scan multiple companies
    print("\n" + "="*80)
    print("EXAMPLE 2: Multi-Company Universe Scan")
    print("="*80)

    companies = [
        ("1045810", "NVIDIA"),
        ("2488", "AMD"),
        ("804328", "QUALCOMM"),
    ]

    universe_results = scanner.scan_universe(
        cik_list=companies,
        start_date="2023-01-01",
        end_date="2025-12-31",
        output_file="historical_scan_results.json"
    )


if __name__ == "__main__":
    main()
