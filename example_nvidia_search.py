#!/usr/bin/env python3
"""
Example: Detecting Nvidia's Geographic Revenue Methodology Change

This script demonstrates how to search for Nvidia's specific accounting change
where they switched from customer headquarters to billing location for
geographic revenue reporting.
"""

import requests
import json
from datetime import datetime


def search_nvidia_geographic_change(api_key):
    """
    Search for Nvidia's geographic revenue methodology change

    Args:
        api_key: Your sec-api.io API key

    Returns:
        List of relevant filings
    """
    print("="*80)
    print("NVIDIA GEOGRAPHIC REVENUE METHODOLOGY CHANGE DETECTOR")
    print("="*80)

    # API endpoint for full-text search
    url = "https://api.sec-api.io/full-text-search"

    headers = {
        'Authorization': api_key,
        'Content-Type': 'application/json'
    }

    # Search parameters targeting Nvidia's specific change
    search_params = {
        "query": 'ticker:NVDA AND ("geographic revenue" OR "customer headquarters" OR "billing location")',
        "formTypes": ["10-Q", "10-K"],
        "startDate": "2024-01-01",
        "endDate": datetime.now().strftime("%Y-%m-%d"),
        "page": "1"
    }

    print("\nSearching Nvidia filings for geographic revenue mentions...")
    print(f"Date range: {search_params['startDate']} to {search_params['endDate']}")

    try:
        # Make API request
        response = requests.post(
            url,
            headers=headers,
            json=search_params,
            timeout=30
        )

        if response.status_code == 200:
            results = response.json()

            if 'filings' in results and len(results['filings']) > 0:
                print(f"\n✓ Found {len(results['filings'])} relevant filings!\n")

                findings = []
                for i, filing in enumerate(results['filings'], 1):
                    finding = {
                        'number': i,
                        'company': filing.get('companyNameLong', 'N/A'),
                        'ticker': filing.get('ticker', 'N/A'),
                        'form': filing.get('formType', 'N/A'),
                        'date': filing.get('filedAt', 'N/A'),
                        'url': filing.get('filingUrl', 'N/A'),
                        'accession': filing.get('accessionNo', 'N/A')
                    }
                    findings.append(finding)

                    # Print details
                    print(f"Finding #{i}:")
                    print(f"  Company: {finding['company']}")
                    print(f"  Form: {finding['form']}")
                    print(f"  Filed: {finding['date']}")
                    print(f"  URL: {finding['url']}")
                    print()

                # Save to JSON file
                output_file = 'nvidia_geographic_revenue_findings.json'
                with open(output_file, 'w') as f:
                    json.dump({
                        'search_date': datetime.now().isoformat(),
                        'total_findings': len(findings),
                        'search_query': search_params['query'],
                        'findings': findings
                    }, f, indent=2)

                print(f"✓ Results saved to {output_file}")

                return findings

            else:
                print("\n✗ No filings found matching the search criteria")
                return []

        else:
            print(f"\n✗ API Error: HTTP {response.status_code}")
            print(f"Response: {response.text}")
            return []

    except Exception as e:
        print(f"\n✗ Error: {e}")
        return []


def extract_relevant_section(api_key, filing_url, form_type):
    """
    Extract the financial statements section from a filing

    Args:
        api_key: Your sec-api.io API key
        filing_url: URL of the SEC filing
        form_type: Type of form (10-Q or 10-K)

    Returns:
        Extracted text content
    """
    print(f"\nExtracting financial statements section from {form_type}...")

    # Determine which section to extract
    if "10-K" in form_type:
        item = "8"  # Item 8: Financial Statements and Supplementary Data
    elif "10-Q" in form_type:
        item = "part1item1"  # Part I, Item 1: Financial Statements
    else:
        print("Unsupported form type")
        return None

    # Extractor API endpoint
    url = "https://api.sec-api.io/extractor"
    params = {
        "url": filing_url,
        "item": item,
        "type": "text",
        "token": api_key
    }

    try:
        response = requests.get(url, params=params, timeout=60)

        if response.status_code == 200:
            content = response.text

            # Search for relevant keywords in extracted content
            keywords = ['geographic revenue', 'customer headquarters', 'billing location', 'ship-to']

            print(f"\n✓ Successfully extracted {len(content)} characters")

            # Find mentions of keywords
            found_keywords = []
            for keyword in keywords:
                if keyword.lower() in content.lower():
                    found_keywords.append(keyword)

            if found_keywords:
                print(f"✓ Found mentions of: {', '.join(found_keywords)}")

                # Extract relevant paragraphs
                lines = content.split('\n')
                relevant_paragraphs = []

                for i, line in enumerate(lines):
                    if any(kw.lower() in line.lower() for kw in keywords):
                        # Get context (3 lines before and after)
                        start = max(0, i - 3)
                        end = min(len(lines), i + 4)
                        paragraph = '\n'.join(lines[start:end])
                        relevant_paragraphs.append(paragraph)

                return {
                    'full_content': content,
                    'keywords_found': found_keywords,
                    'relevant_paragraphs': relevant_paragraphs[:5]  # First 5 matches
                }
            else:
                print("✗ No keyword mentions found in extracted content")
                return {'full_content': content, 'keywords_found': []}

        else:
            print(f"✗ Extraction failed: HTTP {response.status_code}")
            return None

    except Exception as e:
        print(f"✗ Error during extraction: {e}")
        return None


def main():
    """Main execution"""

    # API Key
    API_KEY = "0cced11055b8c44b38e89fa66706ad19f99602f9d4d28d0a696ded9ebfc905d5"

    # Step 1: Search for relevant filings
    findings = search_nvidia_geographic_change(API_KEY)

    if not findings:
        print("\nNo findings to analyze. Exiting.")
        return

    # Step 2: Optionally extract and analyze the first finding
    print("\n" + "="*80)
    choice = input("Would you like to extract details from the first finding? (y/n): ").strip().lower()

    if choice == 'y' and len(findings) > 0:
        first_finding = findings[0]

        print(f"\nAnalyzing: {first_finding['form']} filed on {first_finding['date']}")

        extracted = extract_relevant_section(
            API_KEY,
            first_finding['url'],
            first_finding['form']
        )

        if extracted and extracted.get('relevant_paragraphs'):
            print("\n" + "="*80)
            print("RELEVANT EXCERPTS:")
            print("="*80)

            for i, paragraph in enumerate(extracted['relevant_paragraphs'], 1):
                print(f"\nExcerpt #{i}:")
                print("-" * 80)
                print(paragraph[:500])  # First 500 characters
                print("...")

            # Save excerpts to file
            with open('nvidia_excerpts.txt', 'w') as f:
                f.write("NVIDIA GEOGRAPHIC REVENUE EXCERPTS\n")
                f.write("="*80 + "\n\n")
                for i, paragraph in enumerate(extracted['relevant_paragraphs'], 1):
                    f.write(f"Excerpt #{i}:\n")
                    f.write("-"*80 + "\n")
                    f.write(paragraph + "\n\n")

            print(f"\n✓ Full excerpts saved to nvidia_excerpts.txt")

    print("\n" + "="*80)
    print("Analysis complete!")
    print("="*80)


if __name__ == "__main__":
    main()
