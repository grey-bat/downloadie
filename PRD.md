# PRD

## Product
- Automated Google Takeout downloader that handles multi-GB/TB exports reliably
- Post-download: feeds photos into Immich self-hosted photo library

## User
- Primary user: Greg (solo operator)
- Pain point: Google Takeout exports timeout or fail when downloaded via browser for large archives
- Context: migrating photos and data away from Google; Immich is the destination

## MVP Goal
- Download a full Google Takeout export in the background without manual intervention or timeouts

## Core Flow
1. Generate Takeout export on Google
2. `generate_direct_urls.py` extracts download URLs from Takeout manifest
3. `sequential_turbo.py` downloads all parts in parallel via aria2c
4. `setup_immich_pipeline.py` configures ingestion path
5. `immich_ingest.py` moves/links downloaded files into Immich library

## Must Have
- Parallel download via aria2c (multi-connection per file)
- Resume on failure (aria2c checkpoint files)
- Google auth cookie passthrough

## Nice to Have
- Progress dashboard
- Auto-trigger Immich ingest after download completes

## Not Now
- Other cloud provider exports

## Product Decisions
- decision: aria2c (not requests/wget)
  - why: multi-connection support dramatically speeds up large downloads

## Success
- Full Takeout archive downloaded without manual intervention; photos visible in Immich
