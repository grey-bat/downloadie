import os
import time
import re

LOG_FILE = "/Users/greg/.gemini/antigravity/scratch/aria2.log"

def notify(title, text):
    # macOS native notification
    cmd = f'display notification "{text}" with title "{title}"'
    os.system(f"osascript -e '{cmd}'")

def check_log():
    if not os.path.exists(LOG_FILE):
        return

    with open(LOG_FILE, 'r') as f:
        # Check last 50 lines
        lines = f.readlines()[-50:]
        content = "".join(lines)
        
        if "Redirecting to https://accounts.google.com" in content:
            return "AUTH_EXPIRED"
        if "403 Forbidden" in content:
            return "FORBIDDEN"
        if "Download complete" in content and "identifier" in content:
            return "AUTH_EXPIRED" # It's downloading HTML login pages
    return None

if __name__ == "__main__":
    print("Monitoring Takeout log for failures...")
    last_alert = 0
    while True:
        status = check_log()
        if status and (time.time() - last_alert > 300): # Alert max once every 5 mins
            if status == "AUTH_EXPIRED":
                notify("Google Takeout Alert", "Session expired or blocked. Please refresh cookies in curl_command.txt.")
                # Kill aria2 to prevent downloading 114 HTML files
                os.system("pkill aria2c")
            last_alert = time.time()
        time.sleep(10)
