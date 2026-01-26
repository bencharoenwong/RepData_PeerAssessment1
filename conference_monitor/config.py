"""
Configuration for conference monitoring pipeline.
"""

# Your paper keywords for relevance scoring
PAPER_KEYWORDS = {
    "high_relevance": [
        "financial advice", "consumer finance", "fintech regulation",
        "algorithmic fairness", "credit scoring", "consumer protection",
        "vulnerable investors", "AI discrimination", "robo-advisor",
        "financial services", "suitability", "fiduciary", "CFPB",
        "household finance", "retail investors", "financial literacy"
    ],
    "medium_relevance": [
        "AI accountability", "algorithmic bias", "machine learning fairness",
        "AI regulation", "AI governance", "LLM evaluation", "AI ethics",
        "consumer harm", "disparate impact", "demographic bias"
    ],
    "low_relevance": [
        "artificial intelligence", "technology law", "platform regulation",
        "data governance", "privacy", "algorithmic transparency"
    ]
}

# Google Sheets configuration
GOOGLE_SHEETS_CONFIG = {
    "spreadsheet_id": "YOUR_SPREADSHEET_ID_HERE",  # From the URL
    "sheet_name": "Conference Contacts",
    "credentials_file": "credentials.json",  # Service account JSON
}

# Conference sources to monitor (add URLs here)
CONFERENCE_WATCHLIST = [
    {
        "name": "Wharton Accountable AI Lab",
        "url": "https://ai-analytics.wharton.upenn.edu/wharton-accountable-ai-lab/",
        "check_frequency": "monthly"
    },
    # Add more conferences here
]

# CSV output columns
CSV_COLUMNS = [
    "Conference",
    "Date Added",
    "Name",
    "Affiliation",
    "Email",
    "Research Focus",
    "Relevant to Paper?",
    "Relevance Score",
    "Priority Tier",
    "Key Relevance Notes"
]
