#!/usr/bin/env python3
import os
import sys
import time
import json
import subprocess
import urllib.request
import shutil
import zipfile
import http.server
import socketserver
import threading
import fcntl

# Configuration
PROJECT_DIR = "/Users/greg/.gemini/antigravity/scratch"
DOWNLOADS_DIR = "/Volumes/Backup/downloads"
SSD_CACHE_DIR = "/Users/greg/takeout_cache"
PHOTOS_DIR = "/Volumes/Backup/photos"
STATUS_FILE = os.path.join(PROJECT_DIR, "status.json")
URLS_FILE = os.path.join(PROJECT_DIR, "urls_direct.txt")
PROCESSED_FILE = os.path.join(PROJECT_DIR, "processed_zips_safe.txt") # Use a separate record for safe mode
ARIA2_RPC_URL = "http://localhost:6865/jsonrpc"

class SafeModeController:
    def __init__(self):
        self.urls = self._load_urls()
        self.processed = self._load_processed()
        self.current_zip = None
        self.current_gid = None
        self.failed_zips = {} # name -> count

    def _load_urls(self):
        urls_with_names = []
        
        # 1. Add known on-disk files that might not be in the URL list
        # takeout1.zip is already there and we want to start with it
        for f in sorted(os.listdir(DOWNLOADS_DIR)):
            if f.endswith(".zip") and not f.startswith("test"):
                urls_with_names.append({"url": None, "name": f.replace(".zip", "")})

        # 2. Add from urls_direct.txt
        if os.path.exists(URLS_FILE):
            with open(URLS_FILE, 'r') as f:
                lines = f.readlines()
                for i in range(0, len(lines)):
                    line = lines[i].strip()
                    if line.startswith("https://"):
                        url = line
                        out_name = None
                        if i + 1 < len(lines) and "out=" in lines[i+1]:
                            out_line = lines[i+1].strip()
                            out_name = out_line.split("out=")[-1].replace(".part", "")
                        
                        if out_name:
                            # Avoid duplicates from step 1
                            if not any(u['name'] == out_name for u in urls_with_names):
                                urls_with_names.append({"url": url, "name": out_name})
        
        print(f"Loaded {len(urls_with_names)} unique ZIP entries.")
        return urls_with_names

    def _load_processed(self):
        if os.path.exists(PROCESSED_FILE):
            with open(PROCESSED_FILE, 'r') as f:
                return set(line.strip() for line in f if line.strip())
        return set()

    def _save_processed(self, zip_name):
        self.processed.add(zip_name)
        with open(PROCESSED_FILE, 'a') as f:
            f.write(f"{zip_name}\n")

    def update_status(self, phase, details="", progress=0, total=0, eta=""):
        status = {
            "system_status": phase, # Dashboard expects exact strings like EXTRACTING, MIGRATING
            "status_details": details,
            "active_zip": self.current_zip or "Idle",
            "current_file": progress,
            "total_files": total,
            "extraction_eta": eta,
            "processed_count": len(self.processed),
            "queue_size": len([u for u in self.urls if u['name'] not in self.processed]),
            "time": time.strftime('%H:%M:%S')
        }
        with open(STATUS_FILE, 'w') as f:
            json.dump(status, f)
            
        # Write to activity.json for the dashboard event log
        if details:
            log_entry = {"time": time.strftime('%H:%M:%S'), "type": "info", "msg": f"{phase}: {details}"}
            if "ERROR" in phase: log_entry["type"] = "error"
            if "COMPLETE" in phase: log_entry["type"] = "success"
            
            activity_file = os.path.join(PROJECT_DIR, "activity.json")
            logs = []
            if os.path.exists(activity_file):
                try:
                    with open(activity_file, 'r') as f:
                        logs = json.load(f)
                except: pass
            
            logs.insert(0, log_entry)
            with open(activity_file, 'w') as f:
                json.dump(logs[:50], f)

        # Only print main phase changes, not every poll
        if details and not details.startswith("Unpacking"):
            print(f"[{time.strftime('%H:%M:%S')}] {phase}: {details}")

    def rpc_call(self, method, params=None):
        payload = {"jsonrpc": "2.0", "id": "safe", "method": method, "params": params or []}
        try:
            req = urllib.request.Request(ARIA2_RPC_URL, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=5) as res:
                return json.loads(res.read().decode())
        except Exception as e:
            return None

    def download_zip(self, url_entry):
        url = url_entry['url']
        basename = url_entry['name']
        self.current_zip = basename
        self.update_status("DOWNLOADING", f"Starting download for {basename}")
        
        # Add to aria2 with optimize-concurrent-downloads and large disk cache
        params = [ [url], {
            "dir": DOWNLOADS_DIR, 
            "out": f"{basename}.zip.part",
            "disk-cache": "128M",
            "file-allocation": "falloc" 
        } ]
        res = self.rpc_call("aria2.addUri", params)
        if not res: return False
        self.current_gid = res['result']
        
        while True:
            res = self.rpc_call("aria2.tellStatus", [self.current_gid])
            if not res: break
            status = res['result']
            if status['status'] == 'complete':
                break
            if status['status'] == 'error':
                print(f"Download error: {status.get('errorMessage')}")
                return False
            
            dl_speed = int(status['downloadSpeed']) / 1024 / 1024
            completed = int(status['completedLength']) / 1024**3
            total = int(status['totalLength']) / 1024**3
            
            eta = ""
            if dl_speed > 0:
                rem = (int(status['totalLength']) - int(status['completedLength'])) / (1024**2)
                eta_sec = rem / dl_speed
                eta = f"{int(eta_sec//60)}m {int(eta_sec%60)}s"
                
            self.update_status("DOWNLOADING", f"{completed:.1f}/{total:.1f} GB @ {dl_speed:.1f} MB/s", int(status['completedLength']), int(status['totalLength']), eta)
            time.sleep(10)
            
        # Rename to final .zip
        src = os.path.join(DOWNLOADS_DIR, f"{basename}.zip.part")
        dst = os.path.join(DOWNLOADS_DIR, f"{basename}.zip")
        if os.path.exists(src):
            os.rename(src, dst)
        return True

    def check_zip_integrity(self, zip_path):
        # We handle real integrity during 7z extraction (Step 3) 
        # Here we just do a 'pre-flight' check to ensure file is accessible
        if os.path.exists(zip_path) and os.path.getsize(zip_path) > 0:
            return True
        return False

    def _get_photo_date(self, photo_path):
        json_path = f"{photo_path}.json"
        
        # Check for truncated JSON filename (Google Takeout quirk)
        if not os.path.exists(json_path):
            base, ext = os.path.splitext(photo_path)
            # Sometimes it's photo.json instead of photo.jpg.json
            alt_json = f"{base}.json"
            if os.path.exists(alt_json):
                json_path = alt_json
            else:
                # Try finding any .json that starts with the same 47 chars (Takeout truncation)
                dir_name = os.path.dirname(photo_path)
                short_name = os.path.basename(photo_path)[:47]
                for f in os.listdir(dir_name):
                    if f.startswith(short_name) and f.endswith(".json"):
                        json_path = os.path.join(dir_name, f)
                        break

        if os.path.exists(json_path):
            try:
                with open(json_path, 'r') as f:
                    data = json.load(f)
                    # Prefer photoTakenTime
                    ts = data.get("photoTakenTime", {}).get("timestamp")
                    if not ts:
                        ts = data.get("creationTime", {}).get("timestamp")
                    
                    if ts:
                        return time.strftime('%Y-%m-%d', time.gmtime(int(ts)))
            except:
                pass
        
        # Fallback to file creation time
        try:
            mtime = os.path.getmtime(photo_path)
            return time.strftime('%Y-%m-%d', time.gmtime(mtime))
        except:
            return "Unknown"

    def extract_and_flatten(self, zip_path):
        basename = os.path.basename(zip_path)
        tmp_dir = os.path.join(PHOTOS_DIR, f"_safe_tmp_{basename}")
        os.makedirs(tmp_dir, exist_ok=True)
        
        # Pre-calculate total size for progress (7z l is fast)
        self.update_status("EXTRACTING", "Calculating total size...")
        total_kb = os.path.getsize(zip_path) // 1024 # Fallback
        try:
            res = subprocess.run(["/opt/homebrew/bin/7z", "l", zip_path], capture_output=True, text=True)
            # Find the summary line at the bottom
            for line in reversed(res.stdout.splitlines()):
                if "files," in line or "3132 files" in line.replace("  "," "): # Match summary patterns
                    parts = line.split()
                    for p in reversed(parts):
                        if p.isdigit() and int(p) > 1000000:
                            total_kb = int(p) // 1024
                            break
                    if total_kb > 0: break
                if "-------------------" in line: # Alternate parsing for the dash separator
                    continue
        except Exception as e:
            print(f"Size parsing failed: {e}")

        # 7z: -mmt16 for M-series Mac multi-threading
        self.update_status("EXTRACTING", "Unpacking with 7z...", 0, total_kb)
        # Re-path 7z for reliability
        z7_exe = "/opt/homebrew/bin/7z"
        if not os.path.exists(z7_exe): z7_exe = "7z"
        
        z7_cmd = [z7_exe, "x", zip_path, f"-o{tmp_dir}", "-y", "-mmt16", "-bso0", "-bsp1"] # bsp1 for progress (though we use du)
        
        # Capture stderr to a dedicated file
        err_log = os.path.join(PROJECT_DIR, "7z_error.log")
        with open(err_log, "a") as err_f:
            err_f.write(f"\n--- {time.strftime('%Y-%m-%d %H:%M:%S')} Starting {basename} ---\n")
            process = subprocess.Popen(z7_cmd, stdout=subprocess.PIPE, stderr=err_f, text=True)
            
            start_time = time.time()
            
            while process.poll() is None:
                # Monitor folder growth
                current_kb = 0
                try:
                    du_res = subprocess.run(["du", "-sk", tmp_dir], capture_output=True, text=True)
                    current_kb = int(du_res.stdout.split()[0])
                except: pass
                
                elapsed = time.time() - start_time
                percent = min(99, int((current_kb / total_kb) * 100)) if total_kb > 0 else 0
                
                eta_str = "Calculating..."
                if elapsed > 30 and current_kb > 1024:
                    overall_speed = current_kb / elapsed # KB/s
                    rem_kb = total_kb - current_kb
                    if rem_kb > 0 and overall_speed > 10:
                        sec = rem_kb / overall_speed
                        eta_str = f"{int(sec//60)}m {int(sec%60)}s"
                
                self.update_status("EXTRACTING", f"Unpacking: {percent}% ({current_kb//1024}/{total_kb//1024} MB)", current_kb, total_kb, eta_str)
                time.sleep(10)
        
        if process.returncode != 0:
            msg = f"7z failed with code {process.returncode} for {basename}"
            print(f"[{time.strftime('%H:%M:%S')}] ERROR: {msg}")
            self.update_status("ERROR", msg)
            return False
            
        # Smart Organization
        self.update_status("ORGANIZING", "Sorting photos by date...")
        files_to_move = []
        for root, _, files in os.walk(tmp_dir):
            for f in files:
                if f.startswith(".") or f.lower().endswith(".json"): continue
                files_to_move.append(os.path.join(root, f))
        
        total = len(files_to_move)
        processed = 0
        start_move = time.time()
        for src in files_to_move:
            date_str = self._get_photo_date(src) # YYYY-MM-DD
            year = date_str[:4]
            dest_year_dir = os.path.join(PHOTOS_DIR, year)
            os.makedirs(dest_year_dir, exist_ok=True)
            ext = os.path.splitext(src)[1].lower()
            
            # Serial numbering: YYYY-MM-DD_0001.ext
            serial = 1
            while True:
                new_name = f"{date_str}_{serial:04d}{ext}"
                dst = os.path.join(dest_year_dir, new_name)
                if not os.path.exists(dst): break
                serial += 1
            
            try:
                shutil.move(src, dst)
            except Exception as e:
                print(f"Failed to move {src}: {e}")
            
            processed += 1
            if processed % 50 == 0:
                elapsed_move = time.time() - start_move
                move_speed = processed / elapsed_move if elapsed_move > 0 else 0
                rem_files = total - processed
                move_eta = ""
                if move_speed > 0:
                    sec = rem_files / move_speed
                    move_eta = f"{int(sec//60)}m {int(sec%60)}s"
                
                self.update_status("FLATTENING", f"Filing: {processed}/{total}", processed, total, move_eta)
            
        shutil.rmtree(tmp_dir)
        return True

    def _start_http_server(self):
        handler = http.server.SimpleHTTPRequestHandler
        socketserver.TCPServer.allow_reuse_address = True
        try:
            with socketserver.TCPServer(("", 6860), handler) as httpd:
                print(f"[{time.strftime('%H:%M:%S')}] Dashboard available at http://localhost:6860/dashboard.html")
                httpd.serve_forever()
        except Exception as e:
            print(f"HTTP Server failed: {e}")

    def run(self, start_with=None):
        # Start Dashboard Server
        threading.Thread(target=self._start_http_server, daemon=True).start()
        
        # Ensure aria2 is NOT running to ensure zero background I/O contention
        subprocess.run(["pkill", "-9", "aria2c"], stdout=subprocess.PIPE, stderr=subprocess.PIPE) 
        
        print(f"[{time.strftime('%H:%M:%S')}] MANUAL SEQUENTIAL BURST MODE ACTIVE")
        print(f"[{time.strftime('%H:%M:%S')}] Target: Extracting existing {len(os.listdir(DOWNLOADS_DIR))} files on HDD.")
        
        while True:
            # Look for the next ZIP that is finished and not processed
            next_zip = None
            # Explicitly check for takeout1 first if not processed
            if "takeout1" not in self.processed and os.path.exists(os.path.join(DOWNLOADS_DIR, "takeout1.zip")):
                next_zip = os.path.join(DOWNLOADS_DIR, "takeout1.zip")
                self.current_zip = "takeout1"
            else:
                for entry in self.urls:
                    basename = entry['name']
                    if basename in self.processed: continue
                    
                    zip_path = os.path.join(DOWNLOADS_DIR, f"{basename}.zip")
                    if os.path.exists(zip_path):
                        next_zip = zip_path
                        self.current_zip = basename
                        break
            
            if next_zip:
                basename = self.current_zip
                if self.failed_zips.get(basename, 0) >= 3:
                   print(f"[{time.strftime('%H:%M:%S')}] SKIPPING {basename} (too many failures)")
                   self.update_status("SKIPPED", f"Corrupted file skipped: {basename}")
                   time.sleep(60)
                   continue

                print(f"[{time.strftime('%H:%M:%S')}] STARTING EXTRACTION: {os.path.basename(next_zip)}")
                if self.extract_and_flatten(next_zip):
                    self._save_processed(self.current_zip)
                    try:
                        os.remove(next_zip)
                        print(f"[{time.strftime('%H:%M:%S')}] DELETED source {next_zip}")
                    except: pass
                else:
                    self.failed_zips[basename] = self.failed_zips.get(basename, 0) + 1
                    print(f"[{time.strftime('%H:%M:%S')}] Failed to process {next_zip} (Attempt {self.failed_zips[basename]}/3)")
                    self.update_status("ERROR", f"Failed on {next_zip}")
                    time.sleep(30)
            else:
                self.update_status("IDLE", "All existing ZIPs on HDD processed. Waiting for manual trigger...")
                time.sleep(60)

if __name__ == "__main__":
    # Instance locking
    lock_file = "/tmp/safe_mode_control.lock"
    f = open(lock_file, 'w')
    try:
        fcntl.lockf(f, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except IOError:
        print("[!] Another instance of safe_mode_control is already running. Exiting.")
        sys.exit(1)

    controller = SafeModeController()
    controller.run()
