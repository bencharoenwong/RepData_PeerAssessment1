# SEC API Quick Reference

## 🚀 Quick Start

```bash
# 1. Test the working script
python check_nvidia_filings_v2.py

# 2. Install dependencies (if needed)
pip install -r requirements.txt
```

## 🔑 Your API Key

```
0cced11055b8c44b38e89fa66706ad19f99602f9d4d28d0a696ded9ebfc905d5
```

## 📝 Quick Example - Get Company Filings

```python
import requests

API_KEY = "0cced11055b8c44b38e89fa66706ad19f99602f9d4d28d0a696ded9ebfc905d5"
url = "https://api.sec-api.io"
headers = {'Authorization': API_KEY, 'Content-Type': 'application/json'}

# Query for recent filings
query = {
    "query": "ticker:NVDA AND (formType:\"10-Q\" OR formType:\"10-K\")",
    "from": "0",
    "size": "5",
    "sort": [{"filedAt": {"order": "desc"}}]
}

response = requests.post(url, headers=headers, json=query)
filings = response.json()['filings']

for filing in filings:
    print(f"{filing['formType']} - {filing['filedAt']}")
    print(f"URL: {filing['linkToFilingDetails']}\n")
```

## 🔍 Accounting Change Keywords

Search filings for these terms:

### Geographic Revenue Changes
- `geographic revenue`
- `customer headquarters`
- `billing location`
- `ship-to location`

### General Changes
- `previously, revenue`
- `changed our methodology`
- `changed our presentation`
- `reclassified`
- `restated`

## 📂 Key Files

| File | Command | Purpose |
|------|---------|---------|
| `check_nvidia_filings_v2.py` | `python check_nvidia_filings_v2.py` | List recent filings ✅ |
| `SEC_DETECTOR_README.md` | `cat SEC_DETECTOR_README.md` | Full documentation |
| `FINAL_SUMMARY.md` | `cat FINAL_SUMMARY.md` | Complete summary |
| `nvidia_raw_response.json` | `cat nvidia_raw_response.json` | Sample data |

## 📊 Query API Cheat Sheet

### Basic Query
```python
{"query": "ticker:AAPL AND formType:\"10-K\""}
```

### Date Range
```python
{
    "query": "ticker:NVDA",
    "from": "0",
    "size": "10",
    "sort": [{"filedAt": {"order": "desc"}}]
}
```

### Multiple Tickers
```python
{"query": "(ticker:AAPL OR ticker:MSFT) AND formType:\"10-Q\""}
```

## 🛠️ Common Tasks

### Task 1: Get Latest 10-Q
```python
query = {
    "query": "ticker:NVDA AND formType:\"10-Q\"",
    "from": "0",
    "size": "1",
    "sort": [{"filedAt": {"order": "desc"}}]
}
```

### Task 2: Get All 2025 Filings
```python
query = {
    "query": "ticker:NVDA AND filedAt:[2025-01-01 TO 2025-12-31]",
    "from": "0",
    "size": "50"
}
```

### Task 3: Check Multiple Companies
```python
tickers = ['NVDA', 'AAPL', 'MSFT', 'GOOGL']

for ticker in tickers:
    query["query"] = f'ticker:{ticker} AND formType:"10-Q"'
    response = requests.post(url, headers=headers, json=query)
    # Process results...
```

## ⚠️ Current Limitations

✅ **Working:**
- Query API (filing metadata)
- Filing URLs
- Basic ticker/date searches

⚠️ **Limited:**
- Full-text search (returns 0 results)
- Direct SEC downloads (403 errors)

💡 **Solution:** Contact support@sec-api.io for full-text search access

## 📧 Support

- **API Issues:** support@sec-api.io
- **Documentation:** https://sec-api.io/docs
- **Pricing:** https://sec-api.io/pricing

## 🎯 Next Steps

1. ✅ Run `python check_nvidia_filings_v2.py`
2. 📖 Read `FINAL_SUMMARY.md`
3. 📧 Contact sec-api.io about full-text search
4. 🔨 Build custom queries for your needs
