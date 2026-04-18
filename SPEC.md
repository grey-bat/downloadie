# SPEC

## Build Goal
- Python CLI wrappers around aria2c for reliable Takeout download + Immich ingestion

## Stack
- language: Python 3.11+
- downloader: aria2c (external binary, via subprocess)
- photo library: Immich (self-hosted, Docker)
- hosting: local / run manually

## Main Parts
- `sequential_turbo.py` — parallel aria2c orchestrator (primary tool)
- `sequential_downloader.py` — sequential fallback
- `batch_mode_control.py` — batch management
- `generate_direct_urls.py` — URL extraction from Takeout manifest
- `setup_immich_pipeline.py` — Immich configuration helper
- `immich_ingest.py` — file ingestion into Immich

## Constraints
- aria2c must be installed: `brew install aria2`
- Google session cookies must be valid during download
- Downloaded files are large — store outside repo

## Verify
- `sequential_turbo.py` downloads a small test export without errors
- aria2c checkpoint files allow resume after interruption
