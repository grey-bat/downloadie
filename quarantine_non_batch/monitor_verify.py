import os
import zipfile
import json

PROJECT_DIR = "/Users/greg/.gemini/antigravity/scratch"
DOWNLOADS_DIR = "/Volumes/Backup/downloads"
PHOTOS_DIR = "/Volumes/Backup/photos"
PROCESSED_FILE = os.path.join(PROJECT_DIR, "processed_zips.txt")

def get_processed():
    if not os.path.exists(PROCESSED_FILE): return []
    with open(PROCESSED_FILE, 'r') as f:
        return [line.strip() for line in f if line.strip()]

def verify():
    processed = get_processed()
    extracted_files = set(os.listdir(PHOTOS_DIR))
    
    print(f"{'ZIP File':<20} | {'Expected':<10} | {'Found':<10} | {'Status'}")
    print("-" * 60)
    
    total_expected = 0
    total_found = 0
    
    to_requeue = []

    for zip_path in processed:
        if not os.path.exists(zip_path):
            print(f"{os.path.basename(zip_path):<20} | {'ERROR':<10} | {'-':<10} | FILE NOT FOUND")
            continue
            
        try:
            with zipfile.ZipFile(zip_path, 'r') as z:
                # Get list of all files in zip (excluding directories)
                zip_files = [info.filename for info in z.infolist() if not info.is_dir()]
                expected_count = len(zip_files)
                
                # Check how many of these exist in PHOTOS_DIR (ignoring path, just filename)
                found_count = 0
                for f_path in zip_files:
                    f_name = os.path.basename(f_path)
                    if f_name in extracted_files:
                        found_count += 1
                
                status = "✅ OK" if found_count >= expected_count else "❌ INCOMPLETE"
                if found_count < expected_count:
                    to_requeue.append(zip_path)
                    
                print(f"{os.path.basename(zip_path):<20} | {expected_count:<10} | {found_count:<10} | {status}")
                total_expected += expected_count
                total_found += found_count
        except Exception as e:
            print(f"{os.path.basename(zip_path):<20} | {'ERROR':<10} | {'-':<10} | {e}")

    print("-" * 60)
    print(f"{'TOTAL':<20} | {total_expected:<10} | {total_found:<10} |")
    
    if to_requeue:
        print("\nRecommended for re-extraction (remove from processed_zips.txt):")
        for p in to_requeue:
            print(f"  {p}")

if __name__ == "__main__":
    verify()
