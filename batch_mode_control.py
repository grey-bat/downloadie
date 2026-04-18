#!/usr/bin/env python3
import os
import sys
import time
import json
import subprocess
import urllib.request
import shutil
import fcntl
import re
import threading
from queue import Queue

# Configuration
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
DOWNLOADS_DIR_SSD = "/Users/greg/takeout_cache"
PHOTOS_DIR_HDD = "/Volumes/Backup/photos"
STATUS_FILE = os.path.join(PROJECT_DIR, "status.json")
ACTIVITY_FILE = os.path.join(PROJECT_DIR, "activity.json")
PROCESSED_FILE = os.path.join(PROJECT_DIR, "processed_batches.txt")
ARIA2_RPC_URL = "http://127.0.0.1:6865/jsonrpc"

class BatchController:
    def __init__(self):
        self.download_queue = Queue()
        self.extract_queue = Queue()
        self.processed = self._load_processed()
        
        # Tracking total data processed vs 5.8TB goal
        self.total_processed_bytes = len(self.processed) * 50 * 1024**3 
        
        self.enqueued_names = set() 
        self.stop_event = threading.Event()
        
        # Concurrent status tracking
        self.dl_status = {"name": "Idle", "phase": "IDLE", "pct": 0, "bytes": 0, "total": 0, "speed": 0, "eta": "--"}
        self.ex_status = {"name": "Idle", "phase": "IDLE", "pct": 0, "bytes": 0, "total": 0, "speed": 0, "eta": "--"}
        
        os.makedirs(DOWNLOADS_DIR_SSD, exist_ok=True)
        os.makedirs(PHOTOS_DIR_HDD, exist_ok=True)

    def _load_processed(self):
        if os.path.exists(PROCESSED_FILE):
            with open(PROCESSED_FILE, 'r') as f:
                return set(line.strip() for line in f if line.strip())
        return set()

    def _save_processed(self, name):
        self.processed.add(name)
        with open(PROCESSED_FILE, 'a') as f:
            f.write(f"{name}\n")

    def update_status(self, thread_type, phase, name="Idle", pct=0, current_b=0, total_b=0, speed=0, eta="--"):
        """Thread-safe status update for dashboard."""
        if thread_type == "DL":
            self.dl_status = {"name": name, "phase": phase, "pct": pct, "bytes": current_b, "total": total_b, "speed": speed, "eta": eta}
        else:
            self.ex_status = {"name": name, "phase": phase, "pct": pct, "bytes": current_b, "total": total_b, "speed": speed, "eta": eta}

        # Natural language mapping
        def get_display_phase(p):
            mapping = {
                "STABILIZING": "Downloading (External)",
                "DOWNLOADING": "Downloading to SSD",
                "EXTRACTING": "Unzipping to HDD",
                "VALIDATING": "Verifying Extraction",
                "ADOPTED": "Ready to Unzip",
                "IDLE": "Idle",
                "WAITING": "Waiting (Low Space)"
            }
            return mapping.get(p, p)

        status = {
            "time": time.strftime('%H:%M:%S'),
            "processed_count": len(self.processed),
            "total_gb_processed": round(self.total_processed_bytes / (1024**3), 1),
            "upcoming_queue": [item['name'] for item in list(self.download_queue.queue)[:5]],
            
            # Active Download
            "dl_name": self.dl_status["name"],
            "dl_phase": get_display_phase(self.dl_status["phase"]),
            "dl_pct": self.dl_status["pct"],
            "dl_bytes": self.dl_status["bytes"],
            "dl_total_bytes": self.dl_status["total"],
            "dl_speed": round(self.dl_status["speed"], 1),
            "dl_eta": self.dl_status["eta"],
            
            # Active Extraction
            "ex_name": self.ex_status["name"],
            "ex_phase": get_display_phase(self.ex_status["phase"]),
            "ex_pct": self.ex_status["pct"],
            "ex_bytes": self.ex_status["bytes"],
            "ex_total_bytes": self.ex_status["total"],
            "ex_speed": round(self.ex_status["speed"], 1),
            "ex_eta": self.ex_status["eta"]
        }
        
        # Atomic write using a temporary file
        temp_status = STATUS_FILE + ".tmp"
        try:
            with open(temp_status, 'w') as f:
                json.dump(status, f)
            os.rename(temp_status, STATUS_FILE)
        except Exception as e:
            print(f"Error updating status: {e}")

        # Log major events
        if phase in ["COMPLETE", "ADOPTED", "ERROR"]:
            log_entry = {"time": time.strftime('%H:%M:%S'), "type": "info" if "ERROR" not in phase else "error", "msg": f"{name}: {get_display_phase(phase)}"}
            logs = []
            if os.path.exists(ACTIVITY_FILE):
                try:
                    with open(ACTIVITY_FILE, 'r') as f: logs = json.load(f)
                except: pass
            logs.insert(0, log_entry)
            with open(ACTIVITY_FILE, 'w') as f: json.dump(logs[:50], f)

    def rpc_call(self, method, params=None):
        payload = {"jsonrpc": "2.0", "id": "batch", "method": method, "params": params or []}
        try:
            req = urllib.request.Request(ARIA2_RPC_URL, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=5) as res:
                return json.loads(res.read().decode())
        except Exception as e:
            # Added more logging for RPC failures
            if os.path.exists(ACTIVITY_FILE):
                try:
                    log_entry = {"time": time.strftime('%H:%M:%S'), "type": "error", "msg": f"RPC Connection Error: {str(e)}"}
                    with open(ACTIVITY_FILE, 'r+') as f:
                        logs = json.load(f)
                        logs.insert(0, log_entry)
                        f.seek(0)
                        json.dump(logs[:50], f)
                        f.truncate()
                except: pass
            return None

    def get_free_ssd_gb(self):
        stat = os.statvfs(DOWNLOADS_DIR_SSD)
        return (stat.f_bavail * stat.f_frsize) / (1024**3)

    def downloader_thread(self):
        while not self.stop_event.is_set():
            if self.download_queue.empty():
                self._reload_queue()
                if self.download_queue.empty():
                    self.update_status("DL", "IDLE")
                    time.sleep(30); continue
            
            item = self.download_queue.get()
            name, dest_path = item['name'], os.path.join(DOWNLOADS_DIR_SSD, f"{item['name']}.zip")
            
            print(f"[{time.strftime('%H:%M:%S')}] Processing download item: {name}")
            
            if os.path.exists(dest_path):
                print(f"[{time.strftime('%H:%M:%S')}] {name}.zip already exists on SSD. Moving to extraction.")
                # Update status to reflect we are skipping download because it exists
                self.update_status("DL", "ADOPTED", name, 100, os.path.getsize(dest_path), os.path.getsize(dest_path))
                self.extract_queue.put(item)
            else:
                if self.get_free_ssd_gb() < 60:
                    print(f"[{time.strftime('%H:%M:%S')}] Low SSD space ({self.get_free_ssd_gb():.1f}GB). Waiting...")
                    self.update_status("DL", "WAITING", name)
                    self.download_queue.put(item)
                    time.sleep(30); continue
                
                print(f"[{time.strftime('%H:%M:%S')}] Starting step1_download for {name}")
                if self.step1_download(item):
                    print(f"[{time.strftime('%H:%M:%S')}] Step 1 complete for {name}, adding to extraction queue.")
                    self.extract_queue.put(item)
                else:
                    print(f"[{time.strftime('%H:%M:%S')}] Step 1 FAILED for {name}. Delaying before retry.")
                    time.sleep(10) # Prevent tight loop on failure
            
            self.download_queue.task_done()

    def step1_download(self, item):
        name, url = item['name'], item['url']
        dest_path = os.path.join(DOWNLOADS_DIR_SSD, f"{name}.zip")
        
        if os.path.exists(dest_path):
            last_size = -1
            stable_count = 0
            start_time = time.time()
            last_time = start_time
            while stable_count < 3:
                curr_size = os.path.getsize(dest_path)
                now = time.time()
                speed = ((curr_size - last_size) / 1024**2) / (now - last_time) if last_size > 0 else 0
                eta = "--"
                if speed > 0:
                    rem_sec = ((117 * 1024**3) - curr_size) / (speed * 1024**2)
                    eta = f"{int(rem_sec//60)}m {int(rem_sec%60)}s"
                
                self.update_status("DL", "STABILIZING", name, int((curr_size/(117*1024**3))*100), curr_size, 117*1024**3, speed, eta)
                if curr_size == last_size and curr_size > 0: stable_count += 1
                else: stable_count = 0; last_size = curr_size
                last_time = now
                time.sleep(15)
            self.update_status("DL", "ADOPTED", name, 100, last_size, last_size)
            return True

        if not url.startswith("http"): return False
        
        params = [ [url], {"dir": DOWNLOADS_DIR_SSD, "out": f"{name}.zip", "split": "16", "max-connection-per-server": "16", "disk-cache": "128M", "file-allocation": "falloc"} ]
        res = self.rpc_call("aria2.addUri", params)
        if not res: return False
        
        gid = res['result']
        while True:
            res = self.rpc_call("aria2.tellStatus", [gid])
            if not res: break
            s = res['result']
            if s['status'] == 'complete': break
            if s['status'] == 'error': return False
            
            speed = int(s['downloadSpeed']) / 1024**2
            comp, tot = int(s['completedLength']), int(s['totalLength'])
            pct = int((comp/tot)*100) if tot > 0 else 0
            eta = f"{int(((tot-comp)/1024**2)/speed//60)}m {int(((tot-comp)/1024**2)/speed%60)}s" if speed > 0 and tot > 0 else "--"
            self.update_status("DL", "DOWNLOADING", name, pct, comp, tot, speed, eta)
            time.sleep(5)
        return True

    def extractor_thread(self):
        while not self.stop_event.is_set():
            if self.extract_queue.empty():
                self.update_status("EX", "IDLE")
                time.sleep(5); continue
                
            item = self.extract_queue.get()
            try:
                if self.step2_extract(item):
                    if self.step3_validate(item):
                        self.total_processed_bytes += os.path.getsize(os.path.join(DOWNLOADS_DIR_SSD, f"{item['name']}.zip"))
                        self.step4_cleanup(item)
                        self._save_processed(item['name'])
                        self.update_status("EX", "COMPLETE", item['name'])
                        
                        # Trigger Immich Ingestion
                        self.trigger_immich_ingest()
            except Exception as e:
                self.update_status("EX", "ERROR", item['name'], details=str(e))
            self.extract_queue.task_done()

    def step2_extract(self, item):
        name, zip_path = item['name'], os.path.join(DOWNLOADS_DIR_SSD, f"{item['name']}.zip")
        dest_dir = PHOTOS_DIR_HDD # Extracting directly to root for flattening
        
        zip_size = os.path.getsize(zip_path)
        z7_cmd = ["/opt/homebrew/bin/7z", "x", zip_path, f"-o{dest_dir}", "-y", "-mmt1", "-bso1", "-bsp2"]
        process = subprocess.Popen(z7_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=False)
        
        fd = process.stdout.fileno()
        fl = fcntl.fcntl(fd, fcntl.F_GETFL)
        fcntl.fcntl(fd, fcntl.F_SETFL, fl | os.O_NONBLOCK)

        percent_re = re.compile(rb"(\d{1,3})%")
        rolling, last_update, start_time = b"", 0, time.time()
        
        while True:
            try: chunk = process.stdout.read(4096)
            except BlockingIOError: chunk = b""
            
            if chunk:
                rolling = (rolling + chunk)[-4096:]
                matches = list(percent_re.finditer(rolling))
                if matches:
                    percent = int(matches[-1].group(1))
                    now = time.time()
                    if now - last_update > 5:
                        elapsed = now - start_time
                        proc_b = int(zip_size * (percent / 100.0))
                        speed = (proc_b / 1024**2) / elapsed if elapsed > 0 else 0
                        rem_mb = (zip_size - proc_b) / 1024**2
                        eta = f"{int(rem_mb/speed//60)}m {int(rem_mb/speed%60)}s" if speed > 0 else "--"
                        self.update_status("EX", "EXTRACTING", name, percent, proc_b, zip_size, speed, eta)
                        last_update = now
            if process.poll() is not None: break
            time.sleep(0.5)
        return process.returncode == 0

    def step3_validate(self, item):
        name = item['name']
        dest_dir = PHOTOS_DIR_HDD
        zip_path = os.path.join(DOWNLOADS_DIR_SSD, f"{name}.zip")
        self.update_status("EX", "VALIDATING", name)
        try:
            res = subprocess.run(["/opt/homebrew/bin/7z", "l", "-ba", "-slt", zip_path], capture_output=True, text=True)
            zip_files = [l.split("Path = ", 1)[1].strip() for l in res.stdout.splitlines() if l.startswith("Path = ") and l.split("Path = ", 1)[1].strip() != zip_path and not l.split("Path = ", 1)[1].strip().endswith(os.path.sep)]
            
            # Efficiently check existence in the root
            for f in zip_files:
                f_norm = f.replace("\\", os.path.sep).replace("/", os.path.sep)
                if not os.path.exists(os.path.join(dest_dir, f_norm)):
                    return False
            return True
        except: return False

    def step4_cleanup(self, item):
        p = os.path.join(DOWNLOADS_DIR_SSD, f"{item['name']}.zip")
        if os.path.exists(p): os.remove(p)

    def trigger_immich_ingest(self):
        """Triggers the Immich ingestion pipeline in the background."""
        api_key = os.environ.get("IMMICH_API_KEY")
        if not api_key:
            print(f"[{time.strftime('%H:%M:%S')}] Skipping Immich ingest: IMMICH_API_KEY not set")
            return

        ingest_script = os.path.join(PROJECT_DIR, "immich_ingest.py")
        cmd = [sys.executable, ingest_script, "--api-key", api_key, "--real"]
        try:
            subprocess.Popen(cmd, start_new_session=True)
            print(f"[{time.strftime('%H:%M:%S')}] Triggered Immich ingestion background task")
        except Exception as e:
            print(f"[{time.strftime('%H:%M:%S')}] Failed to trigger Immich ingestion: {e}")

    def _reload_queue(self):
        url_file = os.path.join(PROJECT_DIR, "batch_urls.txt")
        if os.path.exists(url_file):
            with open(url_file, 'r') as f:
                lines = [line.strip() for line in f if line.strip()]
                
                # Each URL might have a label on the next line
                i = 0
                while i < len(lines):
                    line = lines[i]
                    if line.startswith("https://"):
                        url = line
                        label = None
                        
                        # Check if next line is a label
                        if i + 1 < len(lines) and lines[i+1].startswith("#"):
                            label = lines[i+1].replace("#", "")
                            i += 2
                        else:
                            i += 1
                            
                        # If no label, use a generic batch name
                        if not label:
                            label = f"batch_{i}"
                            
                        # A single URL (like takeout_batch_2) might actually be multiple files
                        # but aria2 handles the multi-file download if the URL represents a set.
                        # However, for Google Takeout, if it's a single URL in the text file, 
                        # we should only enqueue it ONCE.
                        
                        if label not in self.processed and label not in self.enqueued_names:
                            self.enqueued_names.add(label)
                            self.download_queue.put({"url": url, "name": label})

    def run(self):
        d_t = threading.Thread(target=self.downloader_thread, name="Downloader")
        e_t = threading.Thread(target=self.extractor_thread, name="Extractor")
        d_t.start(); e_t.start()
        try:
            while True: time.sleep(1)
        except KeyboardInterrupt:
            self.stop_event.set(); d_t.join(); e_t.join()

if __name__ == "__main__":
    BatchController().run()
