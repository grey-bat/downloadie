#!/bin/bash
# Usage: ./download_takeout_aria2.sh [DOWNLOAD_DIR]

DOWNLOAD_DIR=${1:-"/Volumes/Backup/downloads"}

aria2c \
  -i /Users/greg/.gemini/antigravity/scratch/urls_direct.txt \
  -d "$DOWNLOAD_DIR" \
  -j 1 \
  -s 16 \
  -x 16 \
  --connect-timeout=60 \
  --timeout=60 \
  -c \
  --file-allocation=none \
  --enable-mmap=false \
  --disk-cache=128M \
  --enable-rpc=true \
  --rpc-listen-all=false \
  --rpc-listen-port=6865 \
  --rpc-allow-origin-all=true \
  --retry-wait=10 \
  --max-tries=0 \
  --log=aria2.log \
  --log-level=info \
  --load-cookies=/Users/greg/.gemini/antigravity/scratch/cookies.txt \
  --user-agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36" \
  --on-download-complete=/Users/greg/.gemini/antigravity/scratch/on_complete.py
