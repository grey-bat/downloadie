# PLAN

## Current Goal
- Document aria2c setup and Google cookie configuration

## Now
- [ ] Add `requirements.txt` if missing
- [ ] Document how to extract Google cookies for aria2c auth
- [ ] Add `.gitignore` for download artifacts (`*.aria2`, `*.log`, `activity.json`)

## Next
- [ ] Auto-trigger Immich ingest when download completes
- [ ] Progress monitoring dashboard

## Later
- [ ] Support other providers (iCloud, Dropbox)

## Blockers
- Requires valid Google session cookie — expires; must re-authenticate per export

## Notes / Execution Decisions
- `immich_ingest.py` requires Immich running in Docker (`immich-docker/` archived in Archive/misc/)
- Use `sequential_turbo.py` unless hitting rate limits; then fall back to `sequential_downloader.py`
