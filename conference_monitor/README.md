# Conference Committee Monitor

Automated pipeline to extract program committee members from academic conferences, research their backgrounds, score relevance to your paper, and export to Google Sheets.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Set your Anthropic API key
export ANTHROPIC_API_KEY="your-key-here"

# Run on a conference URL
python monitor.py --url "https://conference-url/committee" --name "Conference Name"
```

## Output

Creates/appends to `all_conference_contacts.csv` with columns:
- Conference, Date Added, Name, Affiliation, Email
- Research Focus, Relevant to Paper?, Relevance Score, Priority Tier, Key Relevance Notes

## Google Sheets Integration

### Step 1: Create a Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (e.g., "Conference Monitor")
3. Enable the **Google Sheets API**:
   - Go to APIs & Services → Library
   - Search for "Google Sheets API"
   - Click Enable

### Step 2: Create Service Account Credentials

1. Go to APIs & Services → Credentials
2. Click "Create Credentials" → "Service Account"
3. Name it (e.g., "conference-monitor")
4. Click "Create and Continue" → "Done"
5. Click on the service account you created
6. Go to "Keys" tab → "Add Key" → "Create new key" → JSON
7. Save the downloaded file as `credentials.json` in this folder

### Step 3: Share Your Spreadsheet

1. Create a Google Sheet for your contacts
2. Copy the spreadsheet ID from the URL:
   ```
   https://docs.google.com/spreadsheets/d/SPREADSHEET_ID_HERE/edit
   ```
3. Share the spreadsheet with your service account email:
   - Find the email in `credentials.json` (looks like `name@project.iam.gserviceaccount.com`)
   - Click "Share" in Google Sheets
   - Add the service account email with "Editor" access

### Step 4: Update Configuration

Edit `config.py`:
```python
GOOGLE_SHEETS_CONFIG = {
    "spreadsheet_id": "YOUR_SPREADSHEET_ID_HERE",
    "sheet_name": "Conference Contacts",  # Tab name
    "credentials_file": "credentials.json",
}
```

### Step 5: Run with Sheets Integration

```bash
python monitor.py --url "https://..." --name "Conference" --sheets
```

## Customizing Relevance Scoring

Edit `config.py` to adjust keywords for your research:

```python
PAPER_KEYWORDS = {
    "high_relevance": [
        "financial advice", "consumer finance", ...
    ],
    "medium_relevance": [...],
    "low_relevance": [...]
}
```

## Automation Options

### Option 1: Cron Job (Linux/Mac)
```bash
# Run weekly on Sundays at 9am
0 9 * * 0 cd /path/to/conference_monitor && python monitor.py --watchlist --sheets
```

### Option 2: GitHub Actions

Create `.github/workflows/conference-monitor.yml`:
```yaml
name: Monitor Conferences
on:
  schedule:
    - cron: '0 9 * * 0'  # Weekly on Sunday
  workflow_dispatch:  # Manual trigger

jobs:
  monitor:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - name: Install dependencies
        run: pip install -r conference_monitor/requirements.txt
      - name: Run monitor
        env:
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
        run: python conference_monitor/monitor.py --watchlist --sheets
```

### Option 3: Google Apps Script (In-Sheet Automation)

For a self-contained solution that runs inside Google Sheets, see `apps_script.js`.

## Example Usage

```bash
# Single conference
python monitor.py \
  --url "https://ai-analytics.wharton.upenn.edu/wharton-accountable-ai-lab/accountable-ai-research-conference/" \
  --name "Wharton Accountable AI Conference" \
  --sheets

# Process watchlist (add URLs to config.py first)
python monitor.py --watchlist --sheets
```

## Files

- `monitor.py` - Main pipeline script
- `config.py` - Configuration (keywords, Google Sheets settings)
- `requirements.txt` - Python dependencies
- `credentials.json` - Google service account credentials (you create this)
- `all_conference_contacts.csv` - Output file (auto-generated)
