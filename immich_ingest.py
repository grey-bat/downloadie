#!/usr/bin/env python3
import os
import sys
import subprocess
import argparse
import json
import time
from typing import List

# Default configuration
DEFAULT_IMMICH_URL = "http://localhost:2283/api"
DEFAULT_PHOTOS_ROOT = "/Volumes/Backup/photos"

def log(msg: str, level: str = "INFO"):
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [{level}] {msg}")

class ImmichIngestor:
    def __init__(self, api_url: str, api_key: str, photos_root: str, dry_run: bool = True):
        self.api_url = api_url.rstrip('/')
        self.api_key = api_key
        self.photos_root = photos_root
        self.dry_run = dry_run
        self.immich_go_bin = "immich-go"

    def verify_connectivity(self) -> bool:
        log(f"Verifying connectivity to {self.api_url}...")
        try:
            subprocess.run([self.immich_go_bin, "-h"], capture_output=True, check=True)
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            log("immich-go not found in PATH.", "ERROR")
            return False

    def find_takeout_folders(self) -> List[str]:
        takeout_folders = []
        log(f"Scanning {self.photos_root}...")
        if not os.path.exists(self.photos_root):
            return []

        for root, dirs, _ in os.walk(self.photos_root):
            if "Google Photos" in root:
                for d in dirs:
                    if d.startswith("Photos from ") or d in ["Trash", "Archive"]:
                        takeout_folders.append(os.path.join(root, d))
        return sorted(takeout_folders)

    def ingest_folder(self, folder_path: str, delete_after: bool = False):
        log(f"Processing: {folder_path}")
        cmd = [
            self.immich_go_bin,
            "-server", self.api_url,
            "-key", self.api_key,
            "upload",
            "-skip-verify",
            folder_path
        ]

        if self.dry_run:
            log(f"[DRY-RUN] Would run: {' '.join(cmd)}")
            return True

        try:
            subprocess.run(cmd, check=True)
            log(f"Successfully ingested: {folder_path}", "SUCCESS")
            if delete_after:
                import shutil
                shutil.rmtree(folder_path)
                log(f"Deleted: {folder_path}")
            return True
        except subprocess.CalledProcessError as e:
            log(f"Failed to ingest {folder_path}: {e}", "ERROR")
            return False

def main():
    parser = argparse.ArgumentParser(description="Immich Takeout Ingestion")
    parser.add_argument("--api-key", required=True)
    parser.add_argument("--api-url", default=DEFAULT_IMMICH_URL)
    parser.add_argument("--root", default=DEFAULT_PHOTOS_ROOT)
    parser.add_argument("--batch", help="Specific batch folder name")
    parser.add_argument("--real", action="store_true")
    parser.add_argument("--delete", action="store_true")

    args = parser.parse_args()
    ingestor = ImmichIngestor(args.api_url, args.api_key, args.root, not args.real)

    if not ingestor.verify_connectivity():
        sys.exit(1)

    if args.batch:
        batch_path = os.path.join(args.root, args.batch)
        folders = []
        for root, dirs, _ in os.walk(batch_path):
            if "Google Photos" in root:
                for d in dirs:
                    if d.startswith("Photos from "):
                        folders.append(os.path.join(root, d))
    else:
        folders = ingestor.find_takeout_folders()

    for folder in folders:
        ingestor.ingest_folder(folder, args.delete)

if __name__ == "__main__":
    main()
