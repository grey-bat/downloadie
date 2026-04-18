import os
import zipfile

DOWNLOADS_DIR = "/Volumes/Backup/downloads"
results = {}

print(f"Auditing files in {DOWNLOADS_DIR}...")
files = sorted([f for f in os.listdir(DOWNLOADS_DIR) if f.endswith(".zip")])

for f in files:
    path = os.path.join(DOWNLOADS_DIR, f)
    # Get size in GB
    size_gb = os.path.getsize(path) / (1024**3)
    print(f"Auditing {f} ({size_gb:.1f} GB)...")
    try:
        # zipfile.testzip() is faster than unzip -t for initial structural check
        with zipfile.ZipFile(path, 'r') as z:
            bad = z.testzip()
            if bad:
                results[f] = f"CORRUPT (First bad file: {bad})"
            else:
                results[f] = "OK (Structural)"
    except Exception as e:
        results[f] = f"ERROR: {str(e)}"

print("\n" + "="*50)
print("AUDIT SUMMARY:")
print("="*50)
for f, res in results.items():
    print(f"{f:30} | {res}")
print("="*50)
