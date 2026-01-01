#!/bin/bash
if [ -z "$1" ]; then
    echo "Usage: ./check_integrity.sh <zip_file>"
    exit 1
fi
echo "Verifying $1 (This may take several minutes for 50GB files...)"
unzip -t "$1" | tail -n 2
