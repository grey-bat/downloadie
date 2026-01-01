import subprocess
import os
import time
import webbrowser
import signal
import sys
import threading
import json
import urllib.request
import queue
import shutil
import http.server
import socketserver

PROJECT_DIR = "/Users/greg/.gemini/antigravity/scratch"
OUTPUT_DIR = "/Volumes/Backup/downloads"  # Where ZIPs download
SSD_CACHE_DIR = "/Users/greg/takeout_cache"  # Landing zone on SSD
EXTRACT_DIR = "/Volumes/Backup/photos"  # Where files extract to
STATUS_FILE = os.path.join(PROJECT_DIR, "status.json")
# Important: ensure absolute path to project dir
os.chdir(PROJECT_DIR)

# Defaults
DEFAULT_CONCURRENCY = "1"
DEFAULT_CONNECTIONS = "16"

class Extractor:
    def __init__(self, target_dir=EXTRACT_DIR):
        self.target_dir = target_dir
        self.processed_file = os.path.join(PROJECT_DIR, "processed_zips.txt")
        self.processed_zips = self._load_processed()
        self.lock = threading.RLock()
        self.queue = queue.Queue()
        self.queued_zips = set()
        self.is_extracting = False
        self.last_options = {}
        
        # Start worker threads
        threading.Thread(target=self._worker, daemon=True).start()
        threading.Thread(target=self._monitor_settings, daemon=True).start()
        
        # Ensure target dir exists
        if not os.path.exists(self.target_dir):
            os.makedirs(self.target_dir)
            try:
                subprocess.run(["mdutil", "-i", "off", self.target_dir], capture_output=True)
                with open(os.path.join(self.target_dir, ".metadata_never_index"), 'w') as f:
                    f.write("")
            except:
                pass
        
        self.log_activity(f"System initialized. Monitoring {OUTPUT_DIR} for ZIPs.")

    def _load_processed(self):
        if os.path.exists(self.processed_file):
            with open(self.processed_file, 'r') as f:
                return set(line.strip() for line in f if line.strip())
        return set()

    def _save_processed(self, zip_path):
        with self.lock:
            self.processed_zips.add(zip_path)
            with open(self.processed_file, 'a') as f:
                f.write(zip_path + "\n")


    def log_activity(self, msg, type="info"):
        print(f"[{time.strftime('%H:%M:%S')}] Log: {msg}", flush=True)
        log_file = os.path.join(PROJECT_DIR, "activity.json")
        try:
            with self.lock:
                logs = []
                if os.path.exists(log_file) and os.path.getsize(log_file) > 0:
                    try:
                        with open(log_file, 'r') as f:
                            logs = json.load(f)
                    except:
                        logs = []
                logs.insert(0, {"time": time.strftime("%H:%M:%S"), "msg": f"[PID {os.getpid()}] {msg}", "type": type})
                with open(log_file, 'w') as f:
                    json.dump(logs[:50], f)
        except Exception as e:
            print(f"Log error: {e}", flush=True)
        
    def process_completed(self):
        """Check both local disk and aria2 RPC for completed ZIPs."""
        print(f"[{time.strftime('%H:%M:%S')}] Scanning for completed ZIPs in {OUTPUT_DIR}...", flush=True)
        try:
            # 1. From local disk (robust and fast)
            download_dir = OUTPUT_DIR
            if os.path.exists(download_dir):
                files = os.listdir(download_dir)
                print(f"  Disk: Found {len(files)} items", flush=True)
                for f in files:
                    # ONLY pick up .zip files that are NOT .part
                    if f.endswith(".zip") and not f.startswith("_"):
                        full_path = os.path.join(download_dir, f)
                        aria_file = full_path + ".aria2"
                        # Also check for .part.aria2 just in case
                        part_aria_file = full_path + ".part.aria2"
                        if not os.path.exists(aria_file) and not os.path.exists(part_aria_file) and os.path.isfile(full_path):
                            print(f"  Disk: Found completed ZIP {f}", flush=True)
                            self._queue_if_new(full_path)
                        else:
                            # It's okay if it doesn't exist yet or is in progress
                            pass
            else:
                print(f"  Disk: Directory NOT FOUND: {download_dir}", flush=True)

            # 2. From aria2 RPC (backup for exact status)
            try:
                rpc_payload = {
                    "jsonrpc": "2.0",
                    "id": "ext",
                    "method": "aria2.tellStopped",
                    "params": [0, 1000]
                }
                req = urllib.request.Request(
                    "http://localhost:6865/jsonrpc",
                    data=json.dumps(rpc_payload).encode(),
                    headers={"Content-Type": "application/json"}
                )
                with urllib.request.urlopen(req, timeout=2) as res:
                    data = json.loads(res.read().decode())
                    stopped_items = data.get('result', [])
                    for item in stopped_items:
                        if item['status'] == 'complete':
                            zip_path = item['files'][0]['path']
                            print(f"  RPC: Found completed GID {item['gid']}", flush=True)
                            self._queue_if_new(zip_path)
            except:
                pass
        except Exception as e:
            self.log_activity(f"Scanning error: {e}", "error")
            print(f"  Error during scan: {e}", flush=True)

    def _queue_if_new(self, zip_path):
        if not zip_path.endswith('.zip'):
            return
            
        with self.lock:
            if zip_path in self.processed_zips:
                return
            if zip_path in self.queued_zips:
                return
                
            if os.path.exists(zip_path):
                print(f"!!! QUEUEING: {zip_path}", flush=True)
                self.queued_zips.add(zip_path)
                self.log_activity(f"Queued for extraction: {os.path.basename(zip_path)}")
                self.queue.put(zip_path)
            else:
                print(f"!!! NOT FOUND: {zip_path}", flush=True)

    def _update_status(self, active=None, current=0, total=0, system_status=None, details=None, extraction_eta=None):
        try:
            # Load existing to preserve fields if needed
            current_status = {}
            if os.path.exists(STATUS_FILE):
                with open(STATUS_FILE, 'r') as f:
                    current_status = json.load(f)
            
            # Simple logic: If extracting, show EXTRACTING. Otherwise use provided status or default.
            if self.is_extracting:
                final_system_status = "EXTRACTING"
                # Keep active zip and details from file if not provided
                if not active:
                    active = current_status.get("active_zip")
            else:
                final_system_status = system_status

            status = {
                "active_zip": active or current_status.get("active_zip"),
                "queue_size": self.queue.qsize(),
                "current_file": current,
                "total_files": total,
                "extraction_eta": extraction_eta or "",
                "system_status": final_system_status or ("EXTRACTING" if active else "IDLE"),
                "status_details": details or "",
                "time": time.strftime('%H:%M:%S')
            }
            print(f"DEBUG: Writing status={status['system_status']} (final={final_system_status}, active={active})", flush=True)
            with open(STATUS_FILE, 'w') as f:
                json.dump(status, f)
        except Exception as e:
            print(f"Status error: {e}", flush=True)

    def _worker(self):
        """Sequential worker to prevent disk thrashing."""
        self.log_activity("Sequential extraction worker started (one ZIP at a time).", "info")
        self._update_status()
        while True:
            # 0. Extraction worker loop (Throttle removed to allow processing during high-speed downloads)

            zip_path = self.queue.get()
            base = os.path.basename(zip_path)
            try:
                # 1. Get total uncompressed size (in KB) for progress
                self.log_activity(f"Checking {base} contents...")
                self.is_extracting = True
                
                total_size_kb = 1
                # Sum up file sizes from unzip -l summary line
                count_cmd = ["unzip", "-l", zip_path]
                count_result = subprocess.run(count_cmd, capture_output=True)
                lines = count_result.stdout.decode('utf-8', errors='replace').splitlines()
                total_bytes = 0
                # Look for the last line with dashes, the total is usually the line after it
                for i in range(len(lines)-1, 0, -1):
                    if "---------" in lines[i]:
                        parts = lines[i+1].split()
                        if parts and parts[0].isdigit():
                            total_bytes = int(parts[0])
                            break
                if total_bytes > 0:
                    total_size_kb = total_bytes // 1024

                
                # 2. Extract to temp dir (Use timestamp to avoid any locks/conflicts)
                ts = int(time.time())
                tmp_extract = os.path.join(self.target_dir, f"_tmp_{base}_{ts}")
                os.makedirs(tmp_extract, exist_ok=True)
                
                self.log_activity(f"Extracting {base} to {os.path.basename(tmp_extract)}...")
                # Run at normal priority for maximum speed (user requested)
                extract_cmd = ["bsdtar", "-xf", zip_path, "-C", tmp_extract]
                
                # Start extraction process
                process = subprocess.Popen(extract_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
                
                # --- Watchdog Loop ---
                last_size = -1
                last_move_time = time.time()
                stuck_timeout = 300 # 5 minutes of no growth = stuck
                
                start_time = time.time()
                while process.poll() is None:
                    # Check current size of tmp folder using du -sk 
                    current_size = 0
                    try:
                        du_result = subprocess.run(["du", "-sk", tmp_extract], capture_output=True, timeout=5)
                        if du_result.returncode == 0:
                            current_size = int(du_result.stdout.decode('utf-8', errors='replace').split()[0])
                    except:
                        pass

                    
                    if current_size > last_size:
                        last_size = current_size
                        last_move_time = time.time()
                    elif time.time() - last_move_time > stuck_timeout:
                        self.log_activity(f"Extraction STALLED (no growth for {stuck_timeout}s). Killing and retrying...", "error")
                        process.kill()
                        break
                    
                    # Calculate ETA
                    elapsed = time.time() - start_time
                    eta_str = ""
                    if elapsed > 15 and current_size > 0:
                         speed = current_size / elapsed # KB/s
                         if speed > 0:
                             remaining = total_size_kb - current_size
                             if remaining > 0:
                                 sec = remaining / speed
                                 eta_str = f"{int(sec//60)}m {int(sec%60)}s"
                    
                    self._update_status(active=base, current=current_size, total=total_size_kb, extraction_eta=eta_str)
                    time.sleep(15)
                
                if process.returncode != 0 and process.returncode is not None:
                    stderr_data = process.stderr.read().decode('utf-8', errors='replace')
                    self.log_activity(f"Extraction error: {stderr_data.strip()[:200]}", "error")
                    # Catastrophic failure - don't mark as processed
                    if "Directory not empty" not in stderr_data:
                        raise Exception(f"bsdtar failed with code {process.returncode}")
                
                # 3. Flatten files
                self.log_activity(f"Flattening {base}...")
                processed = 0
                
                # Build a set of existing files for O(1) lookups
                self.log_activity("Building file index...")
                existing_files = set()
                try:
                    for entry in os.scandir(self.target_dir):
                        if entry.is_file():
                            existing_files.add(entry.name)
                except:
                    pass

                for root, dirs, files in os.walk(tmp_extract):
                    for f in files:
                        if f.startswith(".") or f.lower() == "thumbs.db":
                            continue
                            
                        src = os.path.join(root, f)
                        dst_name = f
                        
                        if dst_name in existing_files:
                            name, ext = os.path.splitext(f)
                            i = 1
                            while f"{name}_{i}{ext}" in existing_files:
                                i += 1
                            dst_name = f"{name}_{i}{ext}"
                        
                        try:
                            dst = os.path.join(self.target_dir, dst_name)
                            os.rename(src, dst)
                            existing_files.add(dst_name)
                            processed += 1
                            if processed % 100 == 0:
                                self._update_status(active=base, current=processed, total=total_size_kb)
                        except Exception as move_err:
                            print(f"Move error: {move_err}")
                
                # Cleanup
                try:
                    shutil.rmtree(tmp_extract, ignore_errors=True)
                except:
                    pass
                
                self._save_processed(zip_path)
                self.log_activity(f"Extraction complete: {base} ({processed} files)", "success")

            except Exception as e:
                self.log_activity(f"Error processing {base}: {e}", "error")
            finally:
                self.is_extracting = False
                self._update_status(active=None)
                self.queue.task_done()

    def _monitor_settings(self):
        """Poll aria2c for global options and log changes to the message box."""
        while True:
            try:
                rpc_payload = {
                    "jsonrpc": "2.0",
                    "id": "mon",
                    "method": "aria2.getGlobalOption",
                    "params": []
                }
                req = urllib.request.Request(
                    "http://localhost:6865/jsonrpc",
                    data=json.dumps(rpc_payload).encode(),
                    headers={"Content-Type": "application/json"}
                )
                with urllib.request.urlopen(req, timeout=5) as res:
                    data = json.loads(res.read().decode())
                    options = data.get('result', {})
                    
                    if not self.last_options:
                        self.last_options = options
                    else:
                        relevant_keys = ['max-concurrent-downloads', 'split', 'max-connection-per-server']
                        for key in relevant_keys:
                            if options.get(key) != self.last_options.get(key):
                                msg = f"Settings updated: {key} = {options.get(key)}"
                                self.log_activity(msg, "info")
                        self.last_options = options
            except:
                pass
            time.sleep(5)

def _background_cleanup():
    print(f"[{time.strftime('%H:%M:%S')}] Background cleanup thread started...")
    now = time.time()
    
    # Clean EXTRACT_DIR
    if os.path.exists(EXTRACT_DIR):
        for f in os.listdir(EXTRACT_DIR):
            if f.startswith("_tmp_") or f.startswith("_delete_me_") or ".trash" in f:
                path = os.path.join(EXTRACT_DIR, f)
                try:
                    if now - os.path.getmtime(path) > 3600:
                        shutil.rmtree(path, ignore_errors=True)
                except:
                    pass
                    
    # Clean SSD_CACHE_DIR (Stale files only)
    if os.path.exists(SSD_CACHE_DIR):
        for f in os.listdir(SSD_CACHE_DIR):
            path = os.path.join(SSD_CACHE_DIR, f)
            try:
                # If it's a finished .zip that didn't move, or stale .aria2
                if now - os.path.getmtime(path) > 86400: # 24 hours
                    if os.path.isfile(path):
                        os.remove(path)
            except:
                pass
    print(f"[{time.strftime('%H:%M:%S')}] Background cleanup complete.")

def start_aria2():
    MAIN_PORT = "6865"
    print(f"[{time.strftime('%H:%M:%S')}] Starting aria2c with SSD cache: {SSD_CACHE_DIR}")
    
    # 1. Kill processes
    for proc in ["aria2c", "bsdtar", "unzip", "ditto"]:
        os.system(f"/usr/bin/pkill -9 {proc} 2>/dev/null")
    
    os.system("pkill -9 -f 'rpc-listen-port=6859' 2>/dev/null")
    os.system("pkill -9 -f 'rpc-listen-port=6861' 2>/dev/null")
    os.system("pkill -9 -f 'rpc-listen-port=6865' 2>/dev/null")
    
    # 2. Ensure SSD cache exists and is writable
    os.makedirs(SSD_CACHE_DIR, exist_ok=True)
    
    # 3. Start cleanup in background
    threading.Thread(target=_background_cleanup, daemon=True).start()

    print(f"[{time.strftime('%H:%M:%S')}] Launching aria2c...")
    # SAFE FALLBACK: If SSD has < 60GB, use HDD directly
    download_dir = OUTPUT_DIR
    try:
        st = os.statvfs(SSD_CACHE_DIR)
        free_ssd = st.f_bavail * st.f_frsize
        
        # Calculate size of files already in cache
        cached_size = 0
        for f in os.listdir(SSD_CACHE_DIR):
            cached_size += os.path.getsize(os.path.join(SSD_CACHE_DIR, f))
            
        effective_free = free_ssd + cached_size
        
        if effective_free > 65 * 1024 * 1024 * 1024: # 65GB requirement
            download_dir = SSD_CACHE_DIR
            print(f"  SSD has {effective_free//1024**3}GB effective free. Using SSD cache.")
        else:
            print(f"  SSD has only {effective_free//1024**3}GB effective free. Falling back to HDD for safety.")
    except:
        pass

    cmd = ["sh", os.path.join(PROJECT_DIR, "download_takeout_aria2.sh"), download_dir]
    return subprocess.Popen(cmd, cwd=PROJECT_DIR, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def open_dashboard():
    print("Opening Dashboard...")
    # Use the local server URL instead of file://
    url = "http://localhost:6860/dashboard.html"
    webbrowser.open(url)

if __name__ == "__main__":
    # Start HTTP server in a separate thread
    class Handler(http.server.SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=PROJECT_DIR, **kwargs)

    server_address = ('', 6860)
    httpd = http.server.HTTPServer(server_address, Handler)
    server_thread = threading.Thread(target=httpd.serve_forever)
    server_thread.daemon = True # Allow main program to exit even if server is running
    server_thread.start()
    print(f"HTTP server started on port 6860, serving {PROJECT_DIR}")

    # Singleton check with name verification
    lock_file = os.path.join(PROJECT_DIR, ".app.lock")
    if os.path.exists(lock_file):
        try:
            with open(lock_file, 'r') as f:
                content = f.read().strip()
                if content:
                    old_pid = int(content)
                    # Check if process exists AND is actually this app
                    ps_check = subprocess.run(["ps", "-p", str(old_pid), "-o", "command="], capture_output=True, text=True)
                    if ps_check.returncode == 0 and "start_app.py" in ps_check.stdout:
                        print(f"Error: Another instance of Takeout Turbo is already running (PID {old_pid}).")
                        print("Force-killing the old instance...")
                        os.kill(old_pid, signal.SIGKILL)
                        time.sleep(1)
                    else:
                        # Stale lock or PID reused by something else
                        os.remove(lock_file)
        except (ProcessLookupError, ValueError, FileNotFoundError):
            if os.path.exists(lock_file):
                os.remove(lock_file)
            
    with open(lock_file, 'w') as f:
        f.write(str(os.getpid()))

    process = None
    extractor = Extractor()
    
    print("\nTakeout Turbo is running!")
    print(f"Photos will be flattened to: {OUTPUT_DIR}")
    print("Press Ctrl+C to stop.")

    retry_count = 0
    while True:
        try:
            # Passive watchdog: only restart if process is GONE
            if process is None or process.poll() is not None:
                if process is not None:
                    exit_code = process.poll()
                    retry_count += 1
                    wait_time = min(30, retry_count * 5)
                    print(f"[{time.strftime('%H:%M:%S')}] aria2c process exited with code {exit_code}. Restarting in {wait_time}s...")
                    time.sleep(wait_time)
                
                process = start_aria2()
                if process and process.poll() is None:
                    retry_count = 0
                
                # Immediate initial scan after starting aria2
                time.sleep(2)
                extractor.process_completed()
            
            # Use small timeout for health check to avoid hanging loop
            try:
                # We don't need to check completed ZIPs every 5s if disk is slow
                # but we'll try anyway.
                extractor.process_completed()
            except Exception as e:
                # Don't let RPC timeout kill the whole app
                if "timeout" in str(e).lower():
                    print(f"[{time.strftime('%H:%M:%S')}] Warning: RPC health check timed out (Slow I/O)")
                else:
                    print(f"[{time.strftime('%H:%M:%S')}] Watchdog check error: {e}")
            
            time.sleep(10) # Less frequent polling for backend tasks
            
        except KeyboardInterrupt:
            print("\nShutting down...")
            if os.path.exists(lock_file):
                os.remove(lock_file)
            if process:
                process.send_signal(signal.SIGINT)
                try:
                    process.wait(timeout=5)
                except:
                    os.system("pkill -9 aria2c")
            sys.exit(0)
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(5)
