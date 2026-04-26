import json
import os
import subprocess
import sys
import time

from dotenv import load_dotenv

load_dotenv()

SSD_CACHE = os.getenv("SSD_CACHE", os.path.expanduser("~/takeout_cache"))
HDD_BASE = os.getenv("HDD_BASE", "/Volumes/Backup/photos")
STATUS_FILE = os.getenv("STATUS_FILE", os.path.join(os.path.dirname(__file__), "status.json"))

# Auth — set these in .env (NEVER hardcode session tokens)
JOB_ID = os.getenv("TAKEOUT_JOB_ID", "")
USER_ID = os.getenv("TAKEOUT_USER_ID", "")
BATCH_NAME = os.getenv("TAKEOUT_BATCH_NAME", "batch1")
RAPT = os.getenv("TAKEOUT_RAPT", "")
UA = os.getenv("TAKEOUT_UA", "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36")
REFERER = os.getenv("TAKEOUT_REFERER", f"https://takeout.google.com/manage/archive/{JOB_ID}?download=true&rapt={RAPT}&quotaExceeded=true")
COOKIES = os.getenv("TAKEOUT_COOKIES", "")

def update_board(status):
    temp_status = STATUS_FILE + ".tmp"
    try:
        # Also log to console nicely
        phase = status.get("phase", "")
        progress = status.get("progress", "")
        speed = status.get("speed", "")
        part = status.get("part", "")

        # Format a nice output string for the console
        out_msg = f"[{phase}] Part {part}/3 - Progress: {progress}"
        if speed and speed != "--":
            out_msg += f" - Speed: {speed}"

        sys.stdout.write(f"\r\033[K{out_msg}")
        sys.stdout.flush()

        # Update JSON payload to support the complex dashboard
        dashboard_payload = {
            "time": time.strftime("%H:%M:%S"),
            "processed_count": part,
            "dl_speed": float(speed.replace("MB/s", "").replace("KB/s", "").strip() or 0) if "MB/s" in speed or "KB/s" in speed else 0,
            "dl_name": status.get("file", ""),
            "dl_phase": status.get("phase", ""),
            "dl_pct": int(progress.replace("%", "")) if "%" in progress else 0,
            "ex_name": status.get("file", ""),
            "ex_phase": status.get("phase", "") if status.get("phase") in ["EXTRACTING", "CLEANED", "INGESTING"] else "IDLE",
            "ex_pct": int(progress.replace("%", "")) if "%" in progress and status.get("phase") == "EXTRACTING" else 0
        }

        with open(temp_status, "w") as f:
            json.dump(dashboard_payload, f)
        os.rename(temp_status, STATUS_FILE)
    except Exception as e:
        print(f"\nError updating status: {e}")

def run():
    print("\nStarting Takeout Sequential Download Pipeline...")
    status = {"batch": BATCH_NAME, "part": 0, "total_parts": 3, "phase": "IDLE", "speed": "0 MB/s", "progress": "0%", "file": ""}
    update_board(status)
    
    # We specifically need part 2 and 3 (index 1 and 2), but user asked for batchTwo.
    # Google index is 0-based. i=0, i=1, i=2.
    for i in range(3):
        file_name = f"takeout_{BATCH_NAME}_part{i+1}.zip"
        url = f"https://takeout.google.com/takeout/download?j={JOB_ID}&i={i}&user={USER_ID}&rapt={RAPT}"
        dest_path = os.path.join(SSD_CACHE, file_name)
        
        status["part"] = i + 1
        status["file"] = file_name
        status["phase"] = "DOWNLOADING"
        status["progress"] = "0%"
        status["speed"] = "0 MB/s"
        update_board(status)
        
        cmd = [
            "aria2c", url, "--header", f"Cookie: {COOKIES}",
            "--header", f"User-Agent: {UA}",
            "--header", f"Referer: {REFERER}",
            "-d", SSD_CACHE, "-o", file_name,
            "-s", "16", "-x", "16", "-k", "1M",
            "--file-allocation=falloc", "--allow-overwrite=true", "--summary-interval=1"
        ]
        
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for line in process.stdout:
            # Parse aria2c output
            if "(" in line and "%)" in line and "DL:" in line:
                try:
                    parts = line.split()
                    for p in parts:
                        if "(" in p and "%)" in p:
                            status["progress"] = p.strip("[]()")
                        if "DL:" in p:
                            status["speed"] = p.replace("DL:", "")
                    update_board(status)
                except Exception as e:
                    pass
        process.wait()
        
        if process.returncode != 0:
            status["phase"] = f"ERROR: Download failed (aria2c exit code {process.returncode})"
            # aria2c returns 22 for HTTP error 401/403 which means auth failed.
            if process.returncode == 22:
                status["phase"] = "ERROR: Auth Expired (HTTP 401/403)"
            update_board(status)
            return

        # Explicitly check for ZIP magic bytes to verify successful download
        try:
            with open(dest_path, 'rb') as f:
                if f.read(4) != b'PK\x03\x04':
                    status["phase"] = "ERROR: Invalid ZIP (Auth likely expired or file corrupted)"
                    update_board(status)
                    return
        except Exception as e:
            status["phase"] = f"ERROR: Failed to read file: {e}"
            update_board(status)
            return

        # Extract
        status["phase"] = "EXTRACTING"
        status["progress"] = "0%"
        status["speed"] = "--"
        update_board(status)
        
        dest_dir = os.path.join(HDD_BASE, BATCH_NAME)
        os.makedirs(dest_dir, exist_ok=True)
        
        extract_cmd = ["/opt/homebrew/bin/7z", "x", dest_path, f"-o{dest_dir}", "-y"]
        ex_proc = subprocess.Popen(extract_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for line in ex_proc.stdout:
            if "%" in line:
                try:
                    parts = line.split()
                    for p in parts:
                        if "%" in p: status["progress"] = p
                    update_board(status)
                except Exception as e:
                    pass
        ex_proc.wait()
        
        if ex_proc.returncode != 0:
            status["phase"] = "ERROR: Extraction failed"
            update_board(status)
            return

        # Cleanup
        os.remove(dest_path)
        status["phase"] = "CLEANED"
        update_board(status)

    status["phase"] = "INGESTING"
    status["progress"] = "Triggering Immich"
    update_board(status)

    immich_api_key = os.getenv("IMMICH_API_KEY", "")
    if immich_api_key:
        print(f"Triggering immich_ingest.py for {BATCH_NAME}...")
        ingest_cmd = [
            sys.executable, "immich_ingest.py",
            "--api-key", immich_api_key,
            "--root", HDD_BASE,
            "--batch", BATCH_NAME,
            "--real"
        ]
        try:
            subprocess.run(ingest_cmd, check=True)
            status["phase"] = "COMPLETE_AND_INGESTED"
        except Exception as e:
            print(f"Immich ingest failed: {e}")
            status["phase"] = "COMPLETE_BUT_INGEST_FAILED"
    else:
        status["phase"] = "COMPLETE"
        status["progress"] = "100%"

    update_board(status)

if __name__ == "__main__":
    run()
