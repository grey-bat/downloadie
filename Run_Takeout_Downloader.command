#!/bin/bash

# Configuration
PROJECT_DIR="/Users/greg/.gemini/antigravity/scratch"

echo "===================================================="
echo "    Google Takeout Turbo Downloader (Desktop)"
echo "===================================================="

# Check if aria2c is installed
if ! command -v aria2c &> /dev/null
then
    echo "Error: aria2c not found. Please run 'brew install aria2'"
    exit 1
fi

# Run the monitoring script in background
echo "-> Starting failure monitor (Alerts will pop up if cookies expire)..."
python3 "$PROJECT_DIR/monitor_takeout.py" &
MONITOR_PID=$!

# Run the downloader
echo "-> Starting high-speed transfer..."
cd "$PROJECT_DIR"
sh ./download_takeout_aria2.sh

# Cleanup
kill $MONITOR_PID
echo "Done."
sleep 5
