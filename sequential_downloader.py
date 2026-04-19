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
        with open(temp_status, "w") as f:
            json.dump(status, f)
        os.rename(temp_status, STATUS_FILE)
    except Exception as e:
        print(f"Error updating status: {e}")

def run():
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
                except: pass
        process.wait()
        
        if process.returncode != 0:
            status["phase"] = "ERROR: Download failed"
            update_board(status)
            return

        # Check if it is a real file
        if os.path.getsize(dest_path) < 100 * 1024 * 1024:
            status["phase"] = "ERROR: Auth Expired (Small file)"
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
                except: pass
        ex_proc.wait()
        
        if ex_proc.returncode != 0:
            status["phase"] = "ERROR: Extraction failed"
            update_board(status)
            return

        # Cleanup
        os.remove(dest_path)
        status["phase"] = "CLEANED"
        update_board(status)

    status["phase"] = "COMPLETE"
    status["progress"] = "100%"
    update_board(status)

if __name__ == "__main__":
    run()
