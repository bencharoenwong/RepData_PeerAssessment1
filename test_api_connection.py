#!/usr/bin/env python3
"""
Simple test script to verify SEC API connection
"""

from sec_api import FullTextSearchApi, QueryApi
from datetime import datetime, timedelta

# API Key
API_KEY = "0cced11055b8c44b38e89fa66706ad19f99602f9d4d28d0a696ded9ebfc905d5"

def test_query_api():
    """Test basic Query API functionality"""
    print("Testing Query API...")
    try:
        query_api = QueryApi(api_key=API_KEY)

        # Simple query for recent Apple filings
        query = {
            "query": "ticker:AAPL AND formType:\"10-Q\"",
            "from": "0",
            "size": "2",
            "sort": [{"filedAt": {"order": "desc"}}]
        }

        results = query_api.get_filings(query)

        if 'filings' in results and len(results['filings']) > 0:
            print("✓ Query API working!")
            print(f"  Found {len(results['filings'])} Apple 10-Q filings")
            for filing in results['filings']:
                print(f"  - {filing['formType']} filed on {filing['filedAt']}")
            return True
        else:
            print("✗ Query API returned no results")
            return False

    except Exception as e:
        print(f"✗ Query API error: {e}")
        return False


def test_full_text_search():
    """Test Full-Text Search API functionality"""
    print("\nTesting Full-Text Search API...")
    try:
        full_text_api = FullTextSearchApi(api_key=API_KEY)

        # Search for Nvidia with geographic revenue mentions
        end_date = datetime.now()
        start_date = end_date - timedelta(days=365)

        query = {
            "query": 'ticker:NVDA AND "revenue"',
            "formTypes": ["10-Q", "10-K"],
            "startDate": start_date.strftime("%Y-%m-%d"),
            "endDate": end_date.strftime("%Y-%m-%d"),
            "page": "1"
        }

        results = full_text_api.get_filings(query)

        if 'filings' in results and len(results['filings']) > 0:
            print("✓ Full-Text Search API working!")
            print(f"  Found {len(results['filings'])} Nvidia filings mentioning 'revenue'")
            for filing in results['filings'][:2]:
                print(f"  - {filing['formType']} filed on {filing['filedAt']}")
            return True
        else:
            print("✗ Full-Text Search API returned no results")
            return False

    except Exception as e:
        print(f"✗ Full-Text Search API error: {e}")
        return False


def main():
    print("="*60)
    print("SEC API Connection Test")
    print("="*60)

    # Test both APIs
    query_ok = test_query_api()
    full_text_ok = test_full_text_search()

    print("\n" + "="*60)
    if query_ok and full_text_ok:
        print("✓ All tests passed! API is working correctly.")
        print("\nYou can now run: python sec_accounting_detector.py")
    else:
        print("✗ Some tests failed. Check your API key and connection.")
    print("="*60)


if __name__ == "__main__":
    main()
