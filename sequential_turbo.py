import os
import sys
import json
import subprocess
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

        # Using sys.stdout.write and \r for an in-place updating terminal progress bar if we're in a TTY
        # but for logs it's better to just print normally or use \r
        sys.stdout.write(f"\r\033[K{out_msg}")
        sys.stdout.flush()

        # Update JSON payload to support the complex dashboard
        # Map our simple status to the expected format of dashboard.html
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

        with open(STATUS_FILE + ".tmp", "w") as f:
            json.dump(dashboard_payload, f)
        os.rename(STATUS_FILE + ".tmp", STATUS_FILE)
    except Exception as e:
        pass

def run():
    print("\nStarting Takeout Turbo Download Pipeline...")
    status = {"batch": BATCH_NAME, "part": 0, "total_parts": 3, "phase": "IDLE", "speed": "0 MB/s", "progress": "0%", "file": ""}
    update_board(status)
    
    for i in range(3):
        file_name = f"takeout_{BATCH_NAME}_part{i+1}.zip"
        url = f"https://takeout.google.com/takeout/download?j={JOB_ID}&i={i}&user={USER_ID}&rapt={RAPT}"
        dest_path = os.path.join(SSD_CACHE, file_name)
        
        status.update({"part": i+1, "file": file_name, "phase": "DOWNLOADING", "progress": "0%", "speed": "0 MB/s"})
        update_board(status)
        
        cmd = [
            "aria2c", url, "--header", f"Cookie: {COOKIES}",
            "--header", f"User-Agent: {UA}",
            "--header", f"Referer: {REFERER}",
            "-d", SSD_CACHE, "-o", file_name,
            "-s", "16", "-x", "16", "-k", "1M",
            "--file-allocation=falloc", "--allow-overwrite=true", "--summary-interval=1"
        ]
        
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for line in proc.stdout:
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
        proc.wait()
        
        if proc.returncode != 0:
            status["phase"] = f"ERROR: Download failed (aria2c exit code {proc.returncode})"
            if proc.returncode == 22:
                status["phase"] = "ERROR: Auth Expired (HTTP 401/403)"
            update_board(status)
            return

        if not os.path.exists(dest_path):
            status["phase"] = "ERROR: Download failed, file missing"
            update_board(status)
            return

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

        status.update({"phase": "EXTRACTING", "progress": "0%", "speed": "--"})
        update_board(status)
        
        out_dir = os.path.join(HDD_BASE, BATCH_NAME)
        os.makedirs(out_dir, exist_ok=True)
        
        ex_proc = subprocess.Popen(["/opt/homebrew/bin/7z", "x", dest_path, f"-o{out_dir}", "-y"], 
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for line in ex_proc.stdout:
            if "%" in line:
                try:
                    p = [x for x in line.split() if "%" in x][-1]
                    status["progress"] = p
                    update_board(status)
                except Exception as e:
                    pass
        ex_proc.wait()
        
        if ex_proc.returncode == 0:
            os.remove(dest_path)
            status["phase"] = "CLEANED"
            update_board(status)
        else:
            status["phase"] = "ERROR: Extraction failed"
            update_board(status)
            return

    status.update({"phase": "INGESTING", "progress": "Triggering Immich"})
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
            status.update({"phase": "COMPLETE_AND_INGESTED"})
        except Exception as e:
            print(f"Immich ingest failed: {e}")
            status.update({"phase": "COMPLETE_BUT_INGEST_FAILED"})
    else:
        status.update({"phase": "COMPLETE", "progress": "100%"})

    update_board(status)

if __name__ == "__main__":
    run()
