# Google Takeout High-Speed Downloader

This repository contains tools to systematically download large Google Takeout exports (terabytes of data) in parallel using `aria2c`, bypassing common redirect and authentication issues.

## Prerequisites

- `aria2c` installed (`brew install aria2`)
- Python 3
- A valid Google Takeout archive link

## How it works

Google Takeout serves files via `usercontent.google.com` links which are heavily protected. This tool works by:
1. Identifying the direct URL pattern for your specific export batch.
2. Cloning the security headers and cookies from a valid browser request.
3. Using `aria2c` to download multiple parts (ZIP files) simultaneously with resume support.

## Setup Instructions

1. **Get your direct download pattern**:
   - Go to your Google Takeout management page.
   - Open Developer Tools -> Network tab.
   - Click "Download" on one file and cancel it.
   - Right-click the request to `usercontent.google.com` -> Copy as cURL.
   - Save this to `curl_command.txt` in this directory.

2. **Generate Download Links**:
   - Run the provided Python scripts to extract headers and generate the full list of chunks (e.g., 001 to 114).
   ```bash
   python3 generate_direct_urls.py
   python3 convert_curl_to_aria2.py
   ```

3. **Start Downloading**:
   - Run the generated shell script:
   ```bash
   sh download_takeout_aria2.sh
   ```

## Optimization

The `download_takeout_aria2.sh` script is configured for high parallelism:
- `-j 16`: Downloads 16 files at once.
- `-x 16`: Uses 16 connections per file.
- `-c`: Supports resuming interrupted downloads.

## Security Warning

**Do not commit your `curl_command.txt` or `cookies.txt`!** They contain your Google session tokens. This repository includes a `.gitignore` to protect these files.
