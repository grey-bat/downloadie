#!/bin/bash
# Check for cookies.txt
if [ ! -f "cookies.txt" ]; then
  echo "Error: cookies.txt not found!"
  echo "Please export your Google cookies to a Netscape formatted 'cookies.txt' file."
  echo "You can use a browser extension like 'Get cookies.txt LOCALLY' or copy the curl command from Developer Tools and extract cookies."
  echo "Save it in this directory: $(pwd)/cookies.txt"
  exit 1
fi

echo "Starting download..."
# aria2c options:
# -i urls.txt: Input file
# -d ...: Output directory
# --load-cookies: Cookies
# -j5: 5 parallel downloads
# -x8: 8 connections per download
# -c: Continue/Resume
# --file-allocation=none: Faster startup for large files
# --retry-wait=10: Wait 10s between retries
# --max-tries=0: Infinite retries
aria2c -i urls.txt \
       -d /Volumes/Backup/photos \
       --load-cookies=cookies.txt \
       -j 5 \
       -x 8 \
       -c \
       --file-allocation=none \
       --retry-wait=10 \
       --max-tries=0 \\
       --user-agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36" \\
       --summary-interval=60
