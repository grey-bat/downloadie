import subprocess
import os
import time
import webbrowser
import signal
import sys
import threading
import json
import urllib.request

PROJECT_DIR = "/Users/greg/.gemini/antigravity/scratch"
OUTPUT_DIR = "/Volumes/Backup/photo"

class Extractor:
    def __init__(self, target_dir=OUTPUT_DIR):
        self.target_dir = target_dir
        self.processed_zips = set()
        self.lock = threading.Lock()
        
        # Ensure target dir exists
        if not os.path.exists(self.target_dir):
            os.makedirs(self.target_dir)
            try:
                subprocess.run(["mdutil", "-i", "off", self.target_dir], capture_output=True)
                with open(os.path.join(self.target_dir, ".metadata_never_index"), 'w') as f:
                    f.write("")
            except:
                pass
        self.log_activity("System initialized. Ready for extraction.")

    def log_activity(self, msg, type="info"):
        log_file = os.path.join(PROJECT_DIR, "activity.json")
        try:
            logs = []
            if os.path.exists(log_file):
                with open(log_file, 'r') as f:
                    logs = json.load(f)
            logs.insert(0, {"time": time.strftime("%H:%M:%S"), "msg": msg, "type": type})
            with open(log_file, 'w') as f:
                json.dump(logs[:50], f)
        except:
            pass
        
    def process_completed(self):
        try:
            rpc_payload = {
                "jsonrpc": "2.0",
                "id": "extractor",
                "method": "aria2.tellStopped",
                "params": [0, 1000]
            }
            req = urllib.request.Request(
                "http://localhost:6806/jsonrpc",
                data=json.dumps(rpc_payload).encode(),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req, timeout=2) as res:
                data = json.loads(res.read().decode())
                for item in data.get('result', []):
                    if item['status'] == 'complete':
                        zip_path = item['files'][0]['path']
                        if zip_path.endswith('.zip'):
                            with self.lock:
                                if zip_path not in self.processed_zips and os.path.exists(zip_path):
                                    self.processed_zips.add(zip_path)
                                    threading.Thread(target=self.extract, args=(zip_path,), daemon=True).start()
        except Exception:
            pass

    def extract(self, zip_path):
        base = os.path.basename(zip_path)
        self.log_activity(f"Starting extraction: {base}")
        # -j = junk paths (flatten), -n = don't overwrite
        cmd = ["unzip", "-j", "-n", "-q", zip_path, "-d", self.target_dir]
        try:
            subprocess.run(cmd, check=True)
            self.log_activity(f"Successfully extracted {base}. Deleting ZIP...", "success")
            os.remove(zip_path)
        except Exception as e:
            self.log_activity(f"Failed to extract {base}: {e}", "error")

def start_aria2():
    print("Checking port 6806...")
    
    # 1. Broadly kill any existing aria2c processes first
    os.system("/usr/bin/pkill -9 aria2c 2>/dev/null")
    
    # 2. Targeted cleanup of port 6806
    try:
        # Try both 'lsof' and a direct kill just in case
        lsof_path = "/usr/sbin/lsof"
        if not os.path.exists(lsof_path):
            lsof_path = "lsof" # Fallback to PATH
            
        pid_output = subprocess.check_output([lsof_path, "-ti:6806"], stderr=subprocess.DEVNULL).decode().strip()
        if pid_output:
            pids = pid_output.split('\n')
            for pid in pids:
                print(f"Force-clearing PID {pid} from port 6806...")
                os.system(f"kill -9 {pid} 2>/dev/null")
            time.sleep(2)
    except Exception as e:
        # If lsof fails, we already tried pkill, so we keep going
        print(f"Port check info: {e}")
        pass

    # 3. Last resort - check if it's still blocked
    print("Starting aria2c...")
    cmd = ["sh", os.path.join(PROJECT_DIR, "download_takeout_aria2.sh")]
    return subprocess.Popen(cmd, cwd=PROJECT_DIR)

def open_dashboard():
    print("Opening Dashboard...")
    dashboard_path = os.path.join(PROJECT_DIR, "dashboard.html")
    file_url = "file://" + os.path.abspath(dashboard_path)
    webbrowser.open(file_url)

if __name__ == "__main__":
    # Singleton check
    lock_file = os.path.join(PROJECT_DIR, ".app.lock")
    if os.path.exists(lock_file):
        try:
            with open(lock_file, 'r') as f:
                old_pid = int(f.read().strip())
                os.kill(old_pid, 0) # Check if process exists
                print(f"Error: Another instance of Takeout Turbo is already running (PID {old_pid}).")
                print("Please close that instance first or delete .app.lock if it's a stale file.")
                sys.exit(1)
        except (ProcessLookupError, ValueError):
            os.remove(lock_file)
            
    with open(lock_file, 'w') as f:
        f.write(str(os.getpid()))

    process = None
    extractor = Extractor()
    open_dashboard()
    
    print("\nTakeout Turbo is running!")
    print(f"Photos will be flattened to: {OUTPUT_DIR}")
    print("Press Ctrl+C to stop.")

    retry_count = 0
    while True:
        try:
            if process is None or process.poll() is not None:
                if process is not None:
                    retry_count += 1
                    wait_time = min(30, retry_count * 5)
                    print(f"[{time.strftime('%H:%M:%S')}] aria2c failed to stay active. Retry #{retry_count} in {wait_time}s...")
                    time.sleep(wait_time)
                
                process = start_aria2()
                if process and process.poll() is None:
                    retry_count = 0 # Reset on success
            
            # Check for completed zips to extract
            extractor.process_completed()
            
            time.sleep(5)
            
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
