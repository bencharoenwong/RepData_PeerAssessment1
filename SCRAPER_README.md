# NOAA NMME FTP Scraper

A Python script to scrape all files from the NOAA NMME (North American Multi-Model Ensemble) FTP site and maintain the folder structure locally.

## Features

- **Recursive scraping**: Automatically discovers and traverses all subdirectories
- **Maintains folder structure**: Preserves the same directory hierarchy locally
- **Resume capability**: Skips already downloaded files (run again to resume interrupted downloads)
- **Progress tracking**: Shows download progress for large files
- **Error handling**: Logs failed downloads and continues with others
- **Polite scraping**: Includes small delays between requests to be respectful to the server

## Installation

1. Install the required dependencies:

```bash
pip install -r requirements.txt
```

Or install manually:

```bash
pip install requests beautifulsoup4 lxml
```

## Usage

### Basic usage (saves to `nmme_data/` folder):

```bash
python scrape_noaa_nmme.py
```

### Specify custom output directory:

```bash
python scrape_noaa_nmme.py my_custom_folder
```

### Make script executable and run:

```bash
chmod +x scrape_noaa_nmme.py
./scrape_noaa_nmme.py
```

## What It Does

The script will:
1. Connect to https://ftp.cpc.ncep.noaa.gov/NMME/realtime_anom/ENSMEAN/
2. Recursively scan all subdirectories
3. Download ALL files while maintaining the folder structure
4. Display progress and statistics
5. Generate a summary report when complete

## Output

Files will be saved in the following structure:

```
nmme_data/
├── subfolder1/
│   ├── file1.nc
│   ├── file2.nc
│   └── ...
├── subfolder2/
│   └── ...
└── ...
```

## Notes

- The script may take a long time to run depending on the total size of files
- You can interrupt the script with Ctrl+C and resume later (already downloaded files are skipped)
- Download progress is shown for files larger than 1MB
- A summary report is displayed at the end showing total files downloaded and any failures

## Troubleshooting

**Connection errors**: The script will retry failed downloads. If you have persistent connection issues, check your internet connection or firewall settings.

**Disk space**: Make sure you have sufficient disk space for all the files. The script doesn't check available space beforehand.

**Permissions**: Ensure you have write permissions in the directory where you're running the script.
