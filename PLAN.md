# PLAN

## Current Goal
- Document aria2c setup and Google cookie configuration; address code review findings

## Code Review Findings (per CODE.md)

### 🔴 Bugs / Correctness

- [ ] **`sequential_downloader.py` lines 16-20 — hardcoded secrets committed to repo**
  - `JOB_ID`, `USER_ID`, `RAPT`, `COOKIES`, `UA` are all hardcoded as module-level constants and committed to git — `COOKIES` contains active Google session tokens including `NID`, `AEC`, `__Secure-ENID`
  - Fix: move all auth tokens to `.env` / environment variables; add cookie string to `.gitignore` patterns; rotate any committed cookies immediately

- [ ] **`sequential_downloader.py` line 70 — bare `except: pass`**
  - Swallows all exceptions silently during progress parsing — acceptable for display parsing but masks unexpected errors; at minimum use `except Exception`

- [ ] **`sequential_downloader.py` line 79 — size check `< 100 * 1024 * 1024` is heuristic**
  - A 99 MB legitimate partial download would be misclassified as auth-expired; no way to distinguish truncated vs auth failure without parsing HTTP status code
  - Fix: check aria2c exit code and parse response headers instead of file size

### 🟡 Code Quality (CODE.md violations)

- [ ] **Multiple versioned scripts: `turbo_downloader.py`, `turbo_final.py`, `turbo_sequential.py`, `sequential_turbo.py`, `simple_turbo.py`, `takeout_turbo.py`, `takeout_turbo_v1.py`**
  - 7 iteration variants at repo root; CODE.md forbids copy-paste evolution
  - Fix: keep canonical `sequential_downloader.py`; archive rest to `archive/`

- [ ] **`sequential_downloader.py` lines 8-18 — all config at module level with hardcoded absolute paths**
  - `SSD_CACHE`, `HDD_BASE`, `STATUS_FILE` are hardcoded to `/Users/greg/...` — not portable
  - Fix: read from env vars or CLI args

### 🟢 Usability / Ops

- [ ] Add `requirements.txt`
- [ ] Document how to extract Google cookies for aria2c auth
- [ ] Add `.gitignore` for download artifacts (`*.aria2`, `*.log`, `*.zip`)

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
