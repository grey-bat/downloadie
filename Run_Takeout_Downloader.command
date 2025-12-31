#!/bin/bash

# Configuration
PROJECT_DIR="/Users/greg/.gemini/antigravity/scratch"

echo "===================================================="
echo "    Google Takeout Turbo Dashboard Launcher"
echo "===================================================="

# Check if aria2c is installed
if ! command -v aria2c &> /dev/null
then
    echo "Error: aria2c not found. Please run 'brew install aria2'"
    exit 1
fi

# Switch to project dir and launch the dashboard app
cd "$PROJECT_DIR"
python3 start_app.py

echo "Done."
sleep 5
