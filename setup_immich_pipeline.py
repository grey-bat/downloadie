#!/usr/bin/env python3
"""
Immich Takeout Ingestion Pipeline - One-Click Setup and Execution

This script automates:
1. Setting up Immich Docker Compose on external HDD.
2. Configuring Immich Storage Template via API.
3. Running ingestion of Google Photos Takeout folders.
"""

import os
import sys
import subprocess
import argparse
import json
import time
import urllib.request
from pathlib import Path

# Configuration
DEFAULT_IMMICH_URL = "http://localhost:2283/api"
DEFAULT_PHOTOS_ROOT = "/Volumes/Backup/photos"
DEFAULT_IMMICH_LIBRARY = "/Volumes/Backup/immich_library"

DOCKER_COMPOSE_TEMPLATE = """
version: "3.8"
services:
  immich-server:
    image: ghcr.io/immich-app/immich-server:${IMMICH_VERSION:-release}
    container_name: immich_server
    volumes:
      - ${UPLOAD_LOCATION}:/usr/src/app/upload
      - /etc/localtime:/etc/localtime:ro
    env_file:
      - .env
    ports:
      - "2283:3001"
    depends_on:
      - redis
      - database
    restart: always

  immich-microservices:
    image: ghcr.io/immich-app/immich-server:${IMMICH_VERSION:-release}
    container_name: immich_microservices
    volumes:
      - ${UPLOAD_LOCATION}:/usr/src/app/upload
      - /etc/localtime:/etc/localtime:ro
    env_file:
      - .env
    depends_on:
      - redis
      - database
    restart: always

  redis:
    container_name: immich_redis
    image: redis:6.2-alpine
    restart: always

  database:
    container_name: immich_postgres
    image: tensorchord/pgvecto-rs:pg14-v0.2.0
    environment:
      POSTGRES_PASSWORD: postgres
      POSTGRES_USER: postgres
      POSTGRES_DB: immich
    command: ["postgres", "-c", "shared_preload_libraries=vectors.so", "-c", "search_path=\\"$user\\", public, vectors", "-c", "logging_collector=on", "-c", "max_wal_size=2GB", "-c", "shared_buffers=512MB", "-c", "wal_compression=on"]
    volumes:
      - ./postgres:/var/lib/postgresql/data
    restart: always
"""

def log(msg: str, level: str = "INFO"):
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] [{level}] {msg}")

def api_request(url, method='GET', data=None, headers=None):
    if headers is None:
        headers = {}
    
    req = urllib.request.Request(url, method=method, headers=headers)
    if data:
        req.data = json.dumps(data).encode('utf-8')
        req.add_header('Content-Type', 'application/json')
    
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            return response.getcode(), json.loads(response.read().decode('utf-8'))
    except Exception as e:
        return None, str(e)

class ImmichPipeline:
    def __init__(self, api_url=DEFAULT_IMMICH_URL, photos_root=DEFAULT_PHOTOS_ROOT, library_path=DEFAULT_IMMICH_LIBRARY):
        self.api_url = api_url.rstrip('/')
        self.photos_root = photos_root
        self.library_path = library_path
        self.docker_dir = Path.home() / "immich-docker"
        self.api_key = os.environ.get("IMMICH_API_KEY")

    def setup_docker(self):
        log("Setting up Immich Docker environment...")
        self.docker_dir.mkdir(exist_ok=True)
        
        with open(self.docker_dir / "docker-compose.yml", 'w') as f:
            f.write(DOCKER_COMPOSE_TEMPLATE.strip())
            
        with open(self.docker_dir / ".env", 'w') as f:
            f.writelines([
                f"UPLOAD_LOCATION={self.library_path}\n",
                "IMMICH_VERSION=release\n",
                "DB_PASSWORD=postgres\n",
                "DB_USERNAME=postgres\n",
                "DB_DATABASE_NAME=immich\n",
                "DB_HOSTNAME=database\n",
                "REDIS_HOSTNAME=redis\n"
            ])
        
        os.makedirs(self.library_path, exist_ok=True)
        log(f"Setup complete. Library mapped to {self.library_path}")

    def start_services(self):
        log("Starting Immich services...")
        try:
            subprocess.run(["docker-compose", "up", "-d"], cwd=self.docker_dir, check=True)
            log("Services started. Waiting for readiness...")
            
            for i in range(30):
                code, res = api_request(f"{self.api_url}/server-info/ping")
                if code == 200:
                    log("Immich is UP.")
                    return True
                time.sleep(10)
            return False
        except Exception as e:
            log(f"Error starting services: {e}", "ERROR")
            return False

    def configure_template(self):
        if not self.api_key:
            log("IMMICH_API_KEY not found. Skipping auto-template config.", "WARNING")
            return
            
        log("Configuring storage template...")
        headers = {"x-api-key": self.api_key}
        payload = {"enabled": True, "template": "{{y}}/{{y}}-{{MM}}-{{dd}}_{{seq}}"}
        
        code, res = api_request(f"{self.api_url}/system-config/storage-template", method='PUT', data=payload, headers=headers)
        if code == 200:
            log("Storage template updated successfully.")
        else:
            log(f"Failed to update template: {res}", "ERROR")

    def run_ingestion(self, real=False, delete=False):
        if not self.api_key:
            log("Cannot run ingestion without IMMICH_API_KEY.", "ERROR")
            return
            
        log(f"Running ingestion (Real={real}, Delete={delete})...")
        ingest_script = Path(__file__).parent / "immich_ingest.py"
        cmd = [sys.executable, str(ingest_script), "--api-key", self.api_key, "--root", self.photos_root]
        
        if real: cmd.append("--real")
        if delete: cmd.append("--delete")
        
        subprocess.run(cmd)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--real", action="store_true", help="Perform real ingestion")
    parser.add_argument("--delete", action="store_true", help="Delete source files on success")
    args = parser.parse_args()

    pipeline = ImmichPipeline()
    pipeline.setup_docker()
    
    if pipeline.start_services():
        pipeline.configure_template()
        pipeline.run_ingestion(real=args.real, delete=args.delete)
        log("Pipeline execution finished.")
    else:
        log("Could not start Immich. Please check docker logs.", "ERROR")

if __name__ == "__main__":
    main()
