#!/bin/bash
# GID=$1
# FILE_COUNT=$2
# FIRST_PATH=$3
# We rename the .zip.part to .zip
if [[ "$3" == *".zip.part" ]]; then
    NEW_NAME="${3%.part}"
    mv "$3" "$NEW_NAME"
    echo "Renamed $3 to $NEW_NAME" >> rename_hook.log
fi
