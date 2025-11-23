#!/usr/bin/env python3
"""
Improved diagnostic to check Nvidia filings
"""

import requests
import json
from datetime import datetime

API_KEY = "0cced11055b8c44b38e89fa66706ad19f99602f9d4d28d0a696ded9ebfc905d5"

def check_recent_nvidia_filings():
    """Check recent Nvidia filings"""
    print("Checking recent Nvidia filings...\n")

    url = "https://api.sec-api.io"
    headers = {
        'Authorization': API_KEY,
        'Content-Type': 'application/json'
    }

    query = {
        "query": "ticker:NVDA AND (formType:\"10-Q\" OR formType:\"10-K\")",
        "from": "0",
        "size": "5",
        "sort": [{"filedAt": {"order": "desc"}}]
    }

    try:
        response = requests.post(url, headers=headers, json=query, timeout=30)

        if response.status_code == 200:
            results = response.json()

            # Save raw response for debugging
            with open('nvidia_raw_response.json', 'w') as f:
                json.dump(results, f, indent=2)

            print("✓ Raw response saved to nvidia_raw_response.json\n")

            if 'filings' in results and len(results['filings']) > 0:
                print(f"Found {len(results['filings'])} recent filings:\n")

                for i, filing in enumerate(results['filings'], 1):
                    print(f"{i}. Form: {filing.get('formType', 'N/A')}")
                    print(f"   Date: {filing.get('filedAt', 'N/A')}")
                    print(f"   Company: {filing.get('companyName', filing.get('companyNameLong', 'N/A'))}")

                    # Check what URL field is available
                    url_field = None
                    if 'linkToFilingDetails' in filing:
                        url_field = filing['linkToFilingDetails']
                    elif 'filingUrl' in filing:
                        url_field = filing['filingUrl']
                    elif 'linkToTxt' in filing:
                        url_field = filing['linkToTxt']
                    elif 'linkToHtml' in filing:
                        url_field = filing['linkToHtml']

                    if url_field:
                        print(f"   URL: {url_field}")

                    # Show all available keys for first filing
                    if i == 1:
                        print(f"   Available fields: {list(filing.keys())}")

                    print()

                return results['filings']
            else:
                print("No filings found")
                print(f"Response: {results}")
                return []
        else:
            print(f"Error: HTTP {response.status_code}")
            print(response.text)
            return []

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return []


def test_full_text_search_simple():
    """Test full-text search with simple query"""
    print("\nTesting full-text search with broad query...\n")

    url = "https://api.sec-api.io/full-text-search"
    headers = {
        'Authorization': API_KEY,
        'Content-Type': 'application/json'
    }

    # Very simple query
    query = {
        "query": 'ticker:NVDA',
        "formTypes": ["10-Q"],
        "startDate": "2025-01-01",
        "endDate": "2025-11-23",
        "page": "1"
    }

    try:
        response = requests.post(url, headers=headers, json=query, timeout=30)

        print(f"Status Code: {response.status_code}")

        if response.status_code == 200:
            results = response.json()

            # Save raw response
            with open('nvidia_fulltext_response.json', 'w') as f:
                json.dump(results, f, indent=2)

            print("✓ Response saved to nvidia_fulltext_response.json")

            # Check structure
            print(f"\nResponse keys: {list(results.keys())}")

            if 'filings' in results:
                print(f"Number of filings: {len(results['filings'])}")

                if len(results['filings']) > 0:
                    first_filing = results['filings'][0]
                    print(f"First filing keys: {list(first_filing.keys())}")
                    print(f"First filing: {json.dumps(first_filing, indent=2)[:500]}")
            else:
                print(f"Full response: {json.dumps(results, indent=2)[:1000]}")

            return results
        else:
            print(f"Error: {response.status_code}")
            print(f"Response: {response.text[:500]}")
            return None

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return None


if __name__ == "__main__":
    print("="*80)
    print("NVIDIA FILINGS DIAGNOSTIC v2")
    print("="*80 + "\n")

    # Test regular query API
    filings = check_recent_nvidia_filings()

    # Test full-text search
    full_text_results = test_full_text_search_simple()

    print("\n" + "="*80)
    print("Check the JSON files for detailed responses")
    print("="*80)
