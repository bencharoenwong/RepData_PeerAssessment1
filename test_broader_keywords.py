#!/usr/bin/env python3
"""
Quick test to validate broader keyword detection
Tests on 3 companies to show expanded terminology catching
"""

import sys
import os

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from multi_company_scanner import MultiCompanyScanner

def main():
    API_KEY = "0cced11055b8c44b38e89fa66706ad19f99602f9d4d28d0a696ded9ebfc905d5"

    scanner = MultiCompanyScanner(API_KEY)

    # Test on diverse companies to see what terminology they use
    test_companies = ['AAPL', 'MSFT', 'NVDA']

    print("="*80)
    print("TESTING BROADER KEYWORD DETECTION")
    print("="*80)
    print("\nExpanded keywords now include:")
    print("  - 'regional revenue', 'revenue by region'")
    print("  - 'international revenue', 'domestic revenue'")
    print("  - 'revenue attribution', 'revenue attributed to'")
    print("  - 'customer domicile', 'customer headquarters'")
    print("  - 'designated based on', 'determined by location'")
    print("  - And 20+ more variations...")
    print("\nTesting on 3 companies (2 filings each):\n")

    all_results = {}

    for ticker in test_companies:
        result = scanner.scan_company(ticker, num_filings=2)
        all_results[ticker] = result

    # Summary
    print("\n" + "="*80)
    print("KEYWORD MATCH SUMMARY")
    print("="*80)

    for ticker, result in all_results.items():
        print(f"\n{ticker}:")

        if result['status'] == 'no_filings':
            print("  No filings found")
            continue

        # Aggregate all keyword matches across filings
        all_keywords = {}
        for filing in result.get('findings', []):
            for category, terms in filing.get('keywords', {}).items():
                if category not in all_keywords:
                    all_keywords[category] = set()
                all_keywords[category].update(terms)

        if all_keywords:
            for category, terms in all_keywords.items():
                print(f"  {category}: {', '.join(sorted(terms))}")
        else:
            print("  No keywords found")

    # Check for geographic revenue specifically
    print("\n" + "="*80)
    print("GEOGRAPHIC REVENUE DETECTION")
    print("="*80)

    for ticker, result in all_results.items():
        has_geo_revenue = False

        for filing in result.get('findings', []):
            if 'geographic_revenue' in filing.get('keywords', {}):
                has_geo_revenue = True
                break

        status = "✓ FOUND" if has_geo_revenue else "✗ NOT FOUND"
        print(f"{ticker}: {status}")

    print("\n")


if __name__ == "__main__":
    main()
