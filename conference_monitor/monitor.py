#!/usr/bin/env python3
"""
Conference Committee Monitor & Research Pipeline

Usage:
    python monitor.py --url "https://conference-url.com/committee" --name "Conference Name"
    python monitor.py --watchlist  # Process all conferences in watchlist

Requires:
    pip install anthropic google-api-python-client google-auth requests beautifulsoup4
"""

import argparse
import csv
import json
import os
import re
import time
from datetime import datetime
from typing import Optional

import requests
from bs4 import BeautifulSoup

# Optional imports - graceful degradation if not installed
try:
    import anthropic
    ANTHROPIC_AVAILABLE = True
except ImportError:
    ANTHROPIC_AVAILABLE = False
    print("Warning: anthropic package not installed. Using basic extraction only.")

try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    GOOGLE_AVAILABLE = True
except ImportError:
    GOOGLE_AVAILABLE = False
    print("Warning: Google API packages not installed. CSV output only.")

from config import PAPER_KEYWORDS, GOOGLE_SHEETS_CONFIG, CSV_COLUMNS


class ConferenceMonitor:
    def __init__(self, anthropic_api_key: Optional[str] = None):
        self.anthropic_api_key = anthropic_api_key or os.getenv("ANTHROPIC_API_KEY")
        if ANTHROPIC_AVAILABLE and self.anthropic_api_key:
            self.client = anthropic.Anthropic(api_key=self.anthropic_api_key)
        else:
            self.client = None

    def fetch_page(self, url: str) -> str:
        """Fetch webpage content."""
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; AcademicResearchBot/1.0)"
        }
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        return response.text

    def extract_committee_basic(self, html: str) -> list[dict]:
        """Basic extraction using BeautifulSoup (fallback)."""
        soup = BeautifulSoup(html, 'html.parser')
        text = soup.get_text(separator='\n')

        # Look for common patterns
        members = []
        lines = text.split('\n')

        for line in lines:
            line = line.strip()
            # Pattern: "Name - Institution" or "Name, Institution"
            if ' - ' in line or ', ' in line:
                parts = re.split(r' [-–] |, ', line, maxsplit=1)
                if len(parts) == 2 and len(parts[0]) > 3 and len(parts[0]) < 50:
                    members.append({
                        "name": parts[0].strip(),
                        "affiliation": parts[1].strip()
                    })

        return members

    def extract_committee_llm(self, html: str, url: str) -> list[dict]:
        """Use Claude to extract committee members."""
        if not self.client:
            return self.extract_committee_basic(html)

        soup = BeautifulSoup(html, 'html.parser')
        text = soup.get_text(separator='\n')[:15000]  # Limit context

        prompt = f"""Extract all program committee, scientific committee, or organizing committee members from this webpage.

URL: {url}

Page content:
{text}

Return a JSON array with objects containing:
- "name": full name
- "affiliation": institution/organization

Only include actual committee members, not speakers or attendees.
Return ONLY the JSON array, no other text."""

        message = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4000,
            messages=[{"role": "user", "content": prompt}]
        )

        try:
            result = message.content[0].text
            # Extract JSON from response
            json_match = re.search(r'\[.*\]', result, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except (json.JSONDecodeError, IndexError):
            pass

        return self.extract_committee_basic(html)

    def research_member(self, name: str, affiliation: str) -> dict:
        """Research a committee member using web search."""
        if not self.client:
            return {
                "email": "",
                "research_focus": "",
                "relevance_notes": ""
            }

        prompt = f"""Research this academic committee member and provide:
1. Their email address (search faculty pages)
2. Their main research areas (2-3 key topics)
3. Key relevance notes for a paper on "AI financial advice evaluation, consumer protection, LLM bias in financial services"

Person: {name}
Affiliation: {affiliation}

Return JSON:
{{
    "email": "their@email.edu",
    "research_focus": "topic1, topic2, topic3",
    "relevance_notes": "Brief note on why relevant or not to AI financial advice research"
}}

If you cannot find information, use empty strings. Return ONLY JSON."""

        try:
            message = self.client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1000,
                messages=[{"role": "user", "content": prompt}]
            )
            result = message.content[0].text
            json_match = re.search(r'\{.*\}', result, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
        except Exception as e:
            print(f"  Warning: Could not research {name}: {e}")

        return {"email": "", "research_focus": "", "relevance_notes": ""}

    def score_relevance(self, research_focus: str, relevance_notes: str) -> tuple[int, str, str]:
        """Score relevance based on keywords."""
        text = f"{research_focus} {relevance_notes}".lower()

        high_matches = sum(1 for kw in PAPER_KEYWORDS["high_relevance"] if kw.lower() in text)
        med_matches = sum(1 for kw in PAPER_KEYWORDS["medium_relevance"] if kw.lower() in text)
        low_matches = sum(1 for kw in PAPER_KEYWORDS["low_relevance"] if kw.lower() in text)

        score = min(10, high_matches * 3 + med_matches * 2 + low_matches)

        if score >= 9:
            return score, "Tier 1", "Yes - Highly Relevant"
        elif score >= 7:
            return score, "Tier 2", "Yes - Relevant"
        elif score >= 5:
            return score, "Tier 3", "Somewhat Relevant"
        else:
            return max(1, score), "Tier 4", "Less Relevant"

    def process_conference(self, url: str, conference_name: str) -> list[dict]:
        """Process a conference URL and return committee data."""
        print(f"\nProcessing: {conference_name}")
        print(f"URL: {url}")

        # Fetch and extract
        html = self.fetch_page(url)
        members = self.extract_committee_llm(html, url)
        print(f"Found {len(members)} committee members")

        results = []
        for i, member in enumerate(members):
            name = member.get("name", "")
            affiliation = member.get("affiliation", "")
            print(f"  [{i+1}/{len(members)}] Researching: {name}")

            # Research member
            research = self.research_member(name, affiliation)

            # Score relevance
            score, tier, relevance = self.score_relevance(
                research.get("research_focus", ""),
                research.get("relevance_notes", "")
            )

            results.append({
                "Conference": conference_name,
                "Date Added": datetime.now().strftime("%Y-%m-%d"),
                "Name": name,
                "Affiliation": affiliation,
                "Email": research.get("email", ""),
                "Research Focus": research.get("research_focus", ""),
                "Relevant to Paper?": relevance,
                "Relevance Score": score,
                "Priority Tier": tier,
                "Key Relevance Notes": research.get("relevance_notes", "")
            })

            # Rate limiting
            time.sleep(1)

        return results

    def save_to_csv(self, results: list[dict], output_file: str):
        """Save results to CSV file."""
        file_exists = os.path.exists(output_file)

        with open(output_file, 'a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
            if not file_exists:
                writer.writeheader()
            writer.writerows(results)

        print(f"Saved {len(results)} records to {output_file}")

    def append_to_sheets(self, results: list[dict]):
        """Append results to Google Sheets."""
        if not GOOGLE_AVAILABLE:
            print("Google Sheets API not available")
            return

        creds_file = GOOGLE_SHEETS_CONFIG["credentials_file"]
        if not os.path.exists(creds_file):
            print(f"Credentials file not found: {creds_file}")
            return

        creds = service_account.Credentials.from_service_account_file(
            creds_file,
            scopes=['https://www.googleapis.com/auth/spreadsheets']
        )

        service = build('sheets', 'v4', credentials=creds)
        sheet = service.spreadsheets()

        # Convert to rows
        rows = [[r.get(col, "") for col in CSV_COLUMNS] for r in results]

        body = {'values': rows}

        sheet.values().append(
            spreadsheetId=GOOGLE_SHEETS_CONFIG["spreadsheet_id"],
            range=f"{GOOGLE_SHEETS_CONFIG['sheet_name']}!A:J",
            valueInputOption='RAW',
            insertDataOption='INSERT_ROWS',
            body=body
        ).execute()

        print(f"Appended {len(results)} records to Google Sheets")


def main():
    parser = argparse.ArgumentParser(description="Monitor conference committees")
    parser.add_argument("--url", help="Conference committee page URL")
    parser.add_argument("--name", help="Conference name")
    parser.add_argument("--output", default="all_conference_contacts.csv", help="Output CSV file")
    parser.add_argument("--sheets", action="store_true", help="Also append to Google Sheets")
    args = parser.parse_args()

    if not args.url:
        print("Usage: python monitor.py --url 'https://...' --name 'Conference Name'")
        return

    monitor = ConferenceMonitor()
    results = monitor.process_conference(args.url, args.name or "Unknown Conference")

    # Sort by relevance score
    results.sort(key=lambda x: x["Relevance Score"], reverse=True)

    # Save to CSV
    monitor.save_to_csv(results, args.output)

    # Optionally append to Google Sheets
    if args.sheets:
        monitor.append_to_sheets(results)

    # Print summary
    print("\n" + "="*60)
    print("SUMMARY")
    print("="*60)
    tier_counts = {}
    for r in results:
        tier = r["Priority Tier"]
        tier_counts[tier] = tier_counts.get(tier, 0) + 1

    for tier in ["Tier 1", "Tier 2", "Tier 3", "Tier 4"]:
        if tier in tier_counts:
            print(f"  {tier}: {tier_counts[tier]} members")


if __name__ == "__main__":
    main()
