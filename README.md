# downloadie

## What It Is
- High-speed parallel downloader for Google Takeout exports (terabyte-scale)
- Uses aria2c for multi-connection downloads, bypassing redirect and auth issues

## Status
- Active (periodic use) — runs when Takeout exports are available
- Also includes Immich pipeline setup for photo ingestion after download

## Quick Start
```bash
pip install -r requirements.txt  # if exists
# Ensure aria2c is installed: brew install aria2
python sequential_turbo.py       # fast parallel download mode
```

## Commands
- `sequential_turbo.py` — fastest mode, parallel aria2c downloads
- `sequential_downloader.py` — safer sequential download
- `batch_mode_control.py` — manage download batches
- `generate_direct_urls.py` — generate direct download URLs from Takeout manifest
- `setup_immich_pipeline.py` — configure Immich ingestion after download
- `immich_ingest.py` — ingest downloaded files into Immich photo library

## Env Vars
- Google account cookies (passed via aria2c config or browser session)

## Key Docs
- `PRD.md` — product direction
- `SPEC.md` — implementation approach
- `PLAN.md` — current work
