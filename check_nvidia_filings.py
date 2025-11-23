#!/usr/bin/env python3
"""
Quick diagnostic to check what Nvidia filings are available
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

    # Simple query for any Nvidia 10-Q or 10-K
    query = {
        "query": "ticker:NVDA AND (formType:\"10-Q\" OR formType:\"10-K\")",
        "from": "0",
        "size": "10",
        "sort": [{"filedAt": {"order": "desc"}}]
    }

    try:
        response = requests.post(url, headers=headers, json=query, timeout=30)

        if response.status_code == 200:
            results = response.json()

            if 'filings' in results and len(results['filings']) > 0:
                print(f"Found {len(results['filings'])} recent Nvidia filings:\n")

                for i, filing in enumerate(results['filings'], 1):
                    print(f"{i}. {filing['formType']} - Filed: {filing['filedAt']}")
                    print(f"   URL: {filing['filingUrl']}")
                    print()

                return results['filings']
            else:
                print("No filings found")
                return []
        else:
            print(f"Error: HTTP {response.status_code}")
            print(response.text)
            return []

    except Exception as e:
        print(f"Error: {e}")
        return []


def search_nvidia_with_revenue():
    """Search Nvidia filings mentioning 'revenue'"""
    print("\nSearching Nvidia filings for 'revenue' mentions...\n")

    url = "https://api.sec-api.io/full-text-search"
    headers = {
        'Authorization': API_KEY,
        'Content-Type': 'application/json'
    }

    query = {
        "query": 'ticker:NVDA AND "revenue"',
        "formTypes": ["10-Q", "10-K"],
        "startDate": "2024-01-01",
        "endDate": "2025-11-23",
        "page": "1"
    }

    try:
        response = requests.post(url, headers=headers, json=query, timeout=30)

        if response.status_code == 200:
            results = response.json()

            if 'filings' in results:
                print(f"Found {len(results['filings'])} filings mentioning 'revenue':\n")

                for i, filing in enumerate(results['filings'][:5], 1):
                    print(f"{i}. {filing['formType']} - {filing['filedAt']}")

                return results['filings']
            else:
                print("No results")
                return []
        else:
            print(f"Error: {response.status_code}")
            return []

    except Exception as e:
        print(f"Error: {e}")
        return []


if __name__ == "__main__":
    print("="*80)
    print("NVIDIA FILINGS DIAGNOSTIC")
    print("="*80 + "\n")

    # Check recent filings
    filings = check_recent_nvidia_filings()

    # Search for revenue mentions
    revenue_filings = search_nvidia_with_revenue()

    print("\n" + "="*80)
    print("Diagnostic complete!")
    print("="*80)
