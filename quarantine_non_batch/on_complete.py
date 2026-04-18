#!/usr/bin/env python3
import sys
import os
import shutil
import time
import json
import urllib.request
import subprocess

# Configuration
HDD_DEST = "/Volumes/Backup/downloads"
RPC_URL = "http://localhost:6865/jsonrpc"

def rpc_call(method, params=None):
    payload = {
        "jsonrpc": "2.0",
        "id": "hook",
        "method": method,
        "params": params or []
    }
    try:
        req = urllib.request.Request(
            RPC_URL,
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"}
        )
        with urllib.request.urlopen(req, timeout=5) as res:
            return json.loads(res.read().decode())
    except Exception as e:
        log(f"RPC {method} failed: {e}")
        return None

def log(msg, type="info"):
    with open("/Users/greg/.gemini/antigravity/scratch/on_complete.log", "a") as f:
        f.write(f"[{time.strftime('%H:%M:%S')}] {msg}\n")

def update_status(system_status, details=""):
    status_file = "/Users/greg/.gemini/antigravity/scratch/status.json"
    try:
        # Read current status as base
        current = {}
        if os.path.exists(status_file):
            with open(status_file, 'r') as f:
                current = json.load(f)
        
        current["system_status"] = system_status
        current["status_details"] = details
        current["time"] = time.strftime('%H:%M:%S')
        
        with open(status_file, 'w') as f:
            json.dump(current, f)
    except:
        pass

if len(sys.argv) < 4:
    log(f"Not enough arguments: {sys.argv}")
    sys.exit(1)

gid = sys.argv[1]
num_files = sys.argv[2]
file_path = sys.argv[3]

log(f"Download complete: GID={gid}, Files={num_files}, Path={file_path}")

LOCK_FILE = "/Users/greg/.gemini/antigravity/scratch/.migration.lock"
with open(LOCK_FILE, 'w') as f:
    f.write(str(os.getpid()))

def cleanup():
    if os.path.exists(LOCK_FILE):
        try:
            os.remove(LOCK_FILE)
        except: pass
import atexit
atexit.register(cleanup)

if not os.path.exists(file_path):
    log(f"Error: File doesn't exist at {file_path}")
    sys.exit(1)

# Only move if it's in the cache
if "/takeout_cache/" in file_path:
    basename = os.path.basename(file_path)
    dest_name = basename.replace(".zip.part", ".zip")
    dst = os.path.join(HDD_DEST, dest_name)
    
    try:
        total_size = os.path.getsize(file_path)
        total_gb = total_size / (1024**3)
        
        # Pause EXTRACTION (not downloads) during move to prevent disk thrashing
        log("Pausing extraction during move...")
        update_status("I/O PAUSE", f"Moving {basename} to HDD")
        
        # Pause any active bsdtar
        paused_pids = []
        try:
            pids = subprocess.check_output(["pgrep", "bsdtar"]).decode().split()
            for pid in pids:
                log(f"Pausing bsdtar PID {pid}")
                os.kill(int(pid), 17)  # SIGSTOP
                paused_pids.append(int(pid))
        except:
            pass

        
        log(f"Moving {file_path} to {dst}")
        
        # Start move in a separate process/thread so we can poll progress
        def do_move():
            shutil.move(file_path, dst)
            
        import threading
        move_thread = threading.Thread(target=do_move)
        
        start_time = time.time()
        move_thread.start()
        
        while move_thread.is_alive():
            curr_size = 0
            if os.path.exists(dst):
                curr_size = os.path.getsize(dst)
            curr_gb = curr_size / (1024**3)
            
            # Calculate ETA
            elapsed = time.time() - start_time
            eta_str = ""
            if elapsed > 5 and curr_size > 0:
                speed_bps = curr_size / elapsed
                remaining_bytes = total_size - curr_size
                if speed_bps > 0:
                    eta_sec = remaining_bytes / speed_bps
                    eta_str = f" (ETA: {int(eta_sec//60)}m {int(eta_sec%60)}s)"
            
            update_status("MIGRATING", f"Moving {basename}: {curr_gb:.1f} / {total_gb:.1f} GB{eta_str}")
            time.sleep(2)
            
        move_thread.join()
        log(f"Move successful: {dst}")
        
        # Resume extraction
        update_status("RESUMING", "Resuming extraction")
        for pid in paused_pids:
            log(f"Resuming bsdtar PID {pid}")
            os.kill(pid, 19)  # SIGCONT
        
        # Verify SSD is clear
        log("Verifying SSD cache is clear...")
        cache_dir = os.path.dirname(file_path)
        time.sleep(2)
        
        remaining = [f for f in os.listdir(cache_dir) if not f.endswith(".aria2")]
        if not remaining:
            log("SSD cleared. Movement successful.")
            update_status("IDLE", f"Moved {basename} successfully")

        else:
            log(f"SSD still occupied by {remaining}. Keeping paused for safety.", "warning")
            update_status("PAUSED", "SSD Cache occupied")
    except Exception as e:
        log(f"Move failed: {e}")
        update_status("ERROR", f"Move failed: {str(e)[:50]}")
        # Resume extraction on failure
        try:
            for pid in paused_pids:
                os.kill(pid, 19)  # SIGCONT
        except:
            pass
        sys.exit(1)
else:
    log(f"File not in cache, skipping move: {file_path}")
