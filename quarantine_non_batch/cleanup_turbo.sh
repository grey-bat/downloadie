#!/bin/bash
# Emergency Cleanup for Takeout Turbo
# Run this if you ever see "Port already in use" errors

PORT=6806

echo "--- Takeout Turbo Emergency Cleanup ---"

# 1. Identify and Kill processes on the RPC port
echo "Checking port $PORT..."
PIDS=$(lsof -ti:$PORT)

if [ -z "$PIDS" ]; then
    echo "No processes found on port $PORT."
else
    for PID in $PIDS; do
        PROC_NAME=$(ps -p $PID -o comm=)
        echo "Killing PID $PID ($PROC_NAME) holding port $PORT..."
        kill -9 $PID 2>/dev/null
    done
fi

# 2. Kill any stray aria2c or python processes related to the app
echo "Cleaning up any other stray processes..."
pkill -9 -f "start_app.py"
pkill -9 "aria2c"

echo "Port $PORT and related processes cleared."
echo "You can now run 'python3 start_app.py' again."
echo "---------------------------------------"
