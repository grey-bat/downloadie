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

## Env Vars & Authentication
Since Google Takeout links are bound to your user session, `aria2c` requires valid cookies to download the files successfully. To configure this:
1. Copy `.env.example` to `.env`.
2. Open Google Takeout in your browser, open Developer Tools (Network Tab), and begin a download.
3. Inspect the download request.
4. Copy the entire `Cookie` request header and paste it as `TAKEOUT_COOKIES` in `.env`.
5. Note the `rapt` parameter from the download URL and set `TAKEOUT_RAPT`.
6. Set the `TAKEOUT_JOB_ID` and `TAKEOUT_USER_ID` based on the URL parameters (`j` and `user`).

## Key Docs
- `PRD.md` — product direction
- `SPEC.md` — implementation approach
- `PLAN.md` — current work
