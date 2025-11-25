#!/usr/bin/env python3
"""
Large-scale test: 25 companies across diverse industries
Testing if geographic revenue methodology changes are common or rare
"""

# Test companies by industry
companies = {
    'Technology': ['AAPL', 'MSFT', 'GOOGL', 'META', 'ORCL'],
    'Semiconductors': ['NVDA', 'AMD', 'QCOM'],
    'Consumer': ['PG', 'KO', 'PEP', 'NKE', 'SBUX'],
    'Healthcare': ['JNJ', 'UNH', 'PFE', 'ABBV'],
    'Financial': ['JPM', 'BAC', 'WFC', 'GS'],
    'Industrial': ['CAT', 'BA', 'HON', 'GE'],
    'Retail': ['WMT', 'HD', 'COST'],
    'Energy': ['XOM', 'CVX']
}

# Flatten to list
all_companies = []
for industry, tickers in companies.items():
    all_companies.extend(tickers)

print(f"Total companies to scan: {len(all_companies)}")
print(f"Industries: {len(companies)}")
print("\nCompanies by industry:")
for industry, tickers in companies.items():
    print(f"  {industry}: {', '.join(tickers)}")

print(f"\nFlat list: {','.join(all_companies)}")
