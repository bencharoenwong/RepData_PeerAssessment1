#!/usr/bin/env python3
"""
NOAA NMME FTP Scraper
Scrapes all files from https://ftp.cpc.ncep.noaa.gov/NMME/realtime_anom/ENSMEAN/
and maintains the folder structure locally.
"""

import os
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import time
from pathlib import Path
import sys


class NOAANMMEScraper:
    def __init__(self, base_url, output_dir="nmme_data"):
        """
        Initialize the scraper.

        Args:
            base_url: The base URL to scrape
            output_dir: Local directory to save files (default: nmme_data)
        """
        # Ensure base_url has a trailing slash for proper urljoin behavior
        self.base_url = base_url if base_url.endswith('/') else base_url + '/'
        self.output_dir = output_dir
        self.downloaded_files = 0
        self.failed_downloads = []
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

    def is_within_scope(self, url):
        """
        Check if a URL is within the base URL scope.

        Args:
            url: The URL to check

        Returns:
            True if URL is within scope, False otherwise
        """
        # Normalize URLs for comparison
        url_normalized = url.rstrip('/')
        base_normalized = self.base_url.rstrip('/')

        # URL must start with base_url to be in scope
        return url_normalized.startswith(base_normalized)

    def get_directory_listing(self, url):
        """
        Fetch and parse directory listing from FTP URL.

        Args:
            url: The URL to fetch

        Returns:
            List of tuples (name, url, is_directory)
        """
        try:
            response = self.session.get(url, timeout=30)
            response.raise_for_status()

            soup = BeautifulSoup(response.text, 'html.parser')
            items = []

            # Parse the directory listing
            for link in soup.find_all('a'):
                href = link.get('href')
                # Skip parent directory links, query params, and absolute paths to parent
                if not href or href == '../' or href.startswith('?') or href.startswith('/'):
                    continue

                # Build full URL
                full_url = urljoin(url, href)

                # IMPORTANT: Only include URLs within our base URL scope
                # This prevents escaping to parent directories or root
                if not self.is_within_scope(full_url):
                    continue

                # Check if it's a directory (ends with /)
                is_directory = href.endswith('/')
                name = href.rstrip('/')

                items.append((name, full_url, is_directory))

            return items

        except Exception as e:
            print(f"Error fetching directory listing from {url}: {e}")
            return []

    def download_file(self, url, local_path):
        """
        Download a file from URL to local path.

        Args:
            url: The URL to download from
            local_path: Local file path to save to
        """
        try:
            # Create parent directory if it doesn't exist
            os.makedirs(os.path.dirname(local_path), exist_ok=True)

            # Download file with streaming to handle large files
            response = self.session.get(url, stream=True, timeout=60)
            response.raise_for_status()

            # Get file size if available
            total_size = int(response.headers.get('content-length', 0))

            with open(local_path, 'wb') as f:
                if total_size > 0:
                    downloaded = 0
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                            downloaded += len(chunk)
                            # Print progress for large files (> 1MB)
                            if total_size > 1024 * 1024:
                                progress = (downloaded / total_size) * 100
                                print(f"\r  Progress: {progress:.1f}%", end='', flush=True)
                    if total_size > 1024 * 1024:
                        print()  # New line after progress
                else:
                    # No content-length header, just write all
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)

            self.downloaded_files += 1
            file_size = os.path.getsize(local_path)
            print(f"✓ Downloaded: {local_path} ({self.format_size(file_size)})")

        except Exception as e:
            print(f"✗ Failed to download {url}: {e}")
            self.failed_downloads.append((url, str(e)))

    def format_size(self, size):
        """Format file size in human-readable format."""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0:
                return f"{size:.2f} {unit}"
            size /= 1024.0
        return f"{size:.2f} PB"

    def get_relative_path(self, url):
        """
        Get the relative path from the base URL.

        Args:
            url: The full URL

        Returns:
            Relative path string
        """
        # Remove base_url from the url to get relative path
        if url.startswith(self.base_url):
            rel_path = url[len(self.base_url):].lstrip('/')
        else:
            # Fallback: use URL path
            parsed = urlparse(url)
            rel_path = parsed.path.lstrip('/')

        return rel_path

    def scrape_recursive(self, url, depth=0):
        """
        Recursively scrape directories and download files.

        Args:
            url: The URL to scrape
            depth: Current recursion depth (for logging)
        """
        indent = "  " * depth
        print(f"{indent}Scanning: {url}")

        items = self.get_directory_listing(url)

        if not items:
            print(f"{indent}  (empty or failed to read)")
            return

        # Process all items
        for name, item_url, is_directory in items:
            if is_directory:
                # Recursively process subdirectory
                print(f"{indent}  📁 {name}/")
                self.scrape_recursive(item_url, depth + 1)
            else:
                # Download file
                rel_path = self.get_relative_path(item_url)
                local_path = os.path.join(self.output_dir, rel_path)

                # Check if file already exists
                if os.path.exists(local_path):
                    print(f"{indent}  ⊙ Skipping (already exists): {name}")
                    continue

                print(f"{indent}  📄 Downloading: {name}")
                self.download_file(item_url, local_path)

                # Small delay to be nice to the server
                time.sleep(0.1)

    def run(self):
        """
        Run the scraper.
        """
        print("=" * 80)
        print("NOAA NMME FTP Scraper")
        print("=" * 80)
        print(f"Base URL: {self.base_url}")
        print(f"Output directory: {self.output_dir}")
        print("=" * 80)
        print()

        start_time = time.time()

        # Create output directory
        os.makedirs(self.output_dir, exist_ok=True)

        # Start scraping
        self.scrape_recursive(self.base_url)

        # Print summary
        elapsed_time = time.time() - start_time
        print()
        print("=" * 80)
        print("SCRAPING COMPLETE")
        print("=" * 80)
        print(f"Total files downloaded: {self.downloaded_files}")
        print(f"Failed downloads: {len(self.failed_downloads)}")
        print(f"Time elapsed: {elapsed_time:.2f} seconds")

        if self.failed_downloads:
            print("\nFailed downloads:")
            for url, error in self.failed_downloads:
                print(f"  - {url}: {error}")

        print(f"\nFiles saved to: {os.path.abspath(self.output_dir)}")
        print("=" * 80)


def main():
    """Main entry point."""
    # Default URL
    base_url = "https://ftp.cpc.ncep.noaa.gov/NMME/realtime_anom/ENSMEAN/"

    # Allow custom output directory from command line
    output_dir = sys.argv[1] if len(sys.argv) > 1 else "nmme_data"

    # Create and run scraper
    scraper = NOAANMMEScraper(base_url, output_dir)

    try:
        scraper.run()
    except KeyboardInterrupt:
        print("\n\nScraping interrupted by user.")
        print(f"Downloaded {scraper.downloaded_files} files before interruption.")
        sys.exit(1)


if __name__ == "__main__":
    main()
