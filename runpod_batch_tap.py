#!/usr/bin/env python3
"""
RunPod Batch Processor for TAP Videos
======================================
Generates and submits batch jobs to RunPod serverless endpoint.

Usage:
    python runpod_batch_tap.py --dry-run              # Preview jobs
    python runpod_batch_tap.py --generate-only        # Generate JSON files only
    python runpod_batch_tap.py --start 0 --count 10   # Submit jobs 0-9
    python runpod_batch_tap.py --all                  # Submit all jobs
"""

import argparse
import csv
import json
import os
import time
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional
import requests

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class RunPodConfig:
    """RunPod configuration."""
    # RunPod API
    api_key: str = os.environ.get("RUNPOD_API_KEY", "")
    endpoint_id: str = os.environ.get("RUNPOD_ENDPOINT_ID", "")
    
    # Paths
    csv_path: str = "s3_assets_report.csv"
    output_dir: str = "tap_batch_jobs"
    
    # S3 Output Configuration
    s3_output_folder: str = "TAP_Exports/2026-01"  # New folder for TAP outputs
    
    # TAP B-roll URL (the generic TAP video)
    broll_url: str = "https://s3.us-east-2.amazonaws.com/meli-ai.filmmaker/MP-Sellers/Assets/MP_SELLERS_AI_VIDEO_GENERICO_TAP_ESP_9X16.mov"
    
    # Endcard URLs by GEO
    endcard_urls: Dict[str, str] = None
    
    # Processing
    concurrent_jobs: int = 5
    poll_interval: int = 30  # seconds
    
    def __post_init__(self):
        if self.endcard_urls is None:
            self.endcard_urls = {
                "MLB": "https://s3.us-east-2.amazonaws.com/meli-ai.filmmaker/MP-Sellers/Assets/MLB+-+Ative+com+TAP+do+Mercado+Pago.mov",
                "MLA": "https://s3.us-east-2.amazonaws.com/meli-ai.filmmaker/MP-Sellers/Assets/MLA+-+Activa+TAP+de+Mercado+Pago.mov",
                "MLM": "https://s3.us-east-2.amazonaws.com/meli-ai.filmmaker/MP-Sellers/Assets/MLM+-+Activa+tu+Terminal+Punto+de+Venta.mov",
                "MLC": "https://s3.us-east-2.amazonaws.com/meli-ai.filmmaker/MP-Sellers/Assets/MLC+-+Activa+tu+Lector+de+Tarjeta.mov",
            }


@dataclass
class TapProject:
    """A TAP video project."""
    name: str
    geo: str
    gender: str
    
    scene_1_url: Optional[str] = None
    scene_2_url: Optional[str] = None
    scene_3_url: Optional[str] = None
    
    scene_1_finished: bool = False
    scene_2_finished: bool = False
    scene_3_finished: bool = False
    
    @property
    def is_complete(self) -> bool:
        return self.scene_1_finished and self.scene_2_finished and self.scene_3_finished
    
    @property
    def project_number(self) -> int:
        """Extract project number from name like '69_tap-MLB-male'."""
        try:
            return int(self.name.split("_tap")[0])
        except:
            return 0


# ─────────────────────────────────────────────────────────────────────────────
# CSV PARSING
# ─────────────────────────────────────────────────────────────────────────────

def parse_tap_projects(csv_path: str) -> Dict[str, TapProject]:
    """Parse CSV and extract TAP projects."""
    projects: Dict[str, TapProject] = {}
    
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            folder = row.get('Parent Folder', '').strip()
            filename = row.get('Filename', '').strip()
            url = row.get('Public URL', '').strip()
            finished = row.get('Finished', '').strip().lower() in ('yes', 'true', '1')
            
            # Only TAP projects
            if '_tap' not in folder.lower():
                continue
            
            # Only lipsync videos
            if '_lipsync.mp4' not in filename.lower():
                continue
            
            # Extract GEO and gender
            geo = "MLB"
            for g in ["MLB", "MLA", "MLM", "MLC"]:
                if f"-{g}" in folder.upper():
                    geo = g
                    break
            
            gender = "male"
            if "-female" in folder.lower():
                gender = "female"
            
            # Create or get project
            if folder not in projects:
                projects[folder] = TapProject(name=folder, geo=geo, gender=gender)
            
            project = projects[folder]
            
            # Assign scenes
            fname_lower = filename.lower()
            if 'scene_1_lipsync' in fname_lower:
                project.scene_1_url = url
                project.scene_1_finished = finished
            elif 'scene_2_lipsync' in fname_lower:
                project.scene_2_url = url
                project.scene_2_finished = finished
            elif 'scene_3_lipsync' in fname_lower:
                project.scene_3_url = url
                project.scene_3_finished = finished
    
    return projects


def get_complete_projects(projects: Dict[str, TapProject]) -> List[TapProject]:
    """Get projects with all 3 scenes finished, sorted by number."""
    complete = [p for p in projects.values() if p.is_complete]
    return sorted(complete, key=lambda p: p.project_number)


# ─────────────────────────────────────────────────────────────────────────────
# JOB GENERATION
# ─────────────────────────────────────────────────────────────────────────────

def generate_job_payload(project: TapProject, config: RunPodConfig) -> dict:
    """Generate RunPod job payload for a TAP project."""
    
    endcard_url = config.endcard_urls.get(project.geo, config.endcard_urls["MLB"])
    
    # Extract clean project name from folder (e.g., "36_tap-MLB-FEMALE" -> "36_SMART-MLB-FEMALE")
    # Replace "tap" with "SMART" for cleaner output names
    output_name = project.name.replace("_tap-", "_SMART-").replace("-male", "-MALE").replace("-female", "-FEMALE")
    
    return {
        "input": {
            "job_id": f"tap_{project.name}",
            "geo": project.geo,
            "output_folder": config.s3_output_folder,  # Custom S3 output folder
            "output_filename": f"{output_name}.mp4",   # Named after parent folder
            "clips": [
                {
                    "type": "scene",
                    "url": project.scene_1_url
                },
                {
                    "type": "scene",
                    "url": project.scene_2_url
                },
                {
                    "type": "broll",
                    "url": config.broll_url
                },
                {
                    "type": "scene",
                    "url": project.scene_3_url
                }
            ],
            "music_url": "random",
            "subtitle_mode": "auto",
            "edit_preset": "standard_vertical",
            "style_overrides": {
                "endcard": {
                    "enabled": True,
                    "overlap_seconds": 0.5,
                    "url": endcard_url
                },
                "transcription": {
                    "model": "large"
                }
            }
        }
    }


def generate_all_jobs(projects: List[TapProject], config: RunPodConfig) -> List[dict]:
    """Generate job payloads for all projects."""
    return [generate_job_payload(p, config) for p in projects]


# ─────────────────────────────────────────────────────────────────────────────
# RUNPOD API
# ─────────────────────────────────────────────────────────────────────────────

class RunPodClient:
    """Client for RunPod serverless API."""
    
    def __init__(self, api_key: str, endpoint_id: str):
        self.api_key = api_key
        self.endpoint_id = endpoint_id
        self.base_url = f"https://api.runpod.ai/v2/{endpoint_id}"
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
    
    def submit_job(self, payload: dict) -> dict:
        """Submit a job and return the response."""
        url = f"{self.base_url}/run"
        response = requests.post(url, json=payload, headers=self.headers)
        response.raise_for_status()
        return response.json()
    
    def get_job_status(self, job_id: str) -> dict:
        """Get status of a submitted job."""
        url = f"{self.base_url}/status/{job_id}"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json()
    
    def cancel_job(self, job_id: str) -> dict:
        """Cancel a running job."""
        url = f"{self.base_url}/cancel/{job_id}"
        response = requests.post(url, headers=self.headers)
        response.raise_for_status()
        return response.json()


# ─────────────────────────────────────────────────────────────────────────────
# BATCH PROCESSING
# ─────────────────────────────────────────────────────────────────────────────

def run_batch(
    jobs: List[dict],
    config: RunPodConfig,
    start: int = 0,
    count: int = None,
    dry_run: bool = False
) -> dict:
    """
    Submit and monitor batch jobs.
    
    Returns summary of results.
    """
    # Slice jobs
    if count:
        jobs = jobs[start:start + count]
    else:
        jobs = jobs[start:]
    
    print(f"\n{'='*60}")
    print(f"TAP Batch Processing - {len(jobs)} jobs")
    print(f"{'='*60}\n")
    
    if dry_run:
        print("DRY RUN - No jobs will be submitted\n")
        for i, job in enumerate(jobs):
            project_name = job["input"]["job_id"]
            geo = job["input"]["geo"]
            print(f"  [{i+1:3d}] {project_name} ({geo})")
        return {"dry_run": True, "job_count": len(jobs)}
    
    # Check API credentials
    if not config.api_key or not config.endpoint_id:
        print("ERROR: RUNPOD_API_KEY and RUNPOD_ENDPOINT_ID must be set!")
        print("\nSet environment variables:")
        print("  $env:RUNPOD_API_KEY = 'your-api-key'")
        print("  $env:RUNPOD_ENDPOINT_ID = 'your-endpoint-id'")
        return {"error": "Missing credentials"}
    
    client = RunPodClient(config.api_key, config.endpoint_id)
    
    # Submit jobs
    submitted = []
    failed_submit = []
    
    print("Submitting jobs...\n")
    
    for i, job in enumerate(jobs):
        project_name = job["input"]["job_id"]
        try:
            result = client.submit_job(job)
            runpod_id = result.get("id")
            submitted.append({
                "project": project_name,
                "runpod_id": runpod_id,
                "status": "SUBMITTED"
            })
            print(f"  [{i+1:3d}/{len(jobs)}] ✓ {project_name} -> {runpod_id}")
            
            # Rate limiting
            if (i + 1) % config.concurrent_jobs == 0:
                time.sleep(1)
                
        except Exception as e:
            failed_submit.append({"project": project_name, "error": str(e)})
            print(f"  [{i+1:3d}/{len(jobs)}] ✗ {project_name} - {e}")
    
    print(f"\n{'─'*60}")
    print(f"Submitted: {len(submitted)} | Failed: {len(failed_submit)}")
    print(f"{'─'*60}\n")
    
    # Monitor jobs
    if submitted:
        print("Monitoring jobs... (Ctrl+C to stop monitoring)\n")
        
        completed = []
        failed = []
        
        try:
            while submitted:
                for job_info in submitted[:]:
                    try:
                        status = client.get_job_status(job_info["runpod_id"])
                        job_status = status.get("status", "UNKNOWN")
                        
                        if job_status == "COMPLETED":
                            output = status.get("output", {})
                            output_url = output.get("output_url", "N/A")
                            completed.append({
                                **job_info,
                                "output_url": output_url,
                                "status": "COMPLETED"
                            })
                            submitted.remove(job_info)
                            print(f"  ✓ {job_info['project']} - COMPLETED")
                            print(f"    {output_url}")
                            
                        elif job_status == "FAILED":
                            error = status.get("error", "Unknown error")
                            failed.append({
                                **job_info,
                                "error": error,
                                "status": "FAILED"
                            })
                            submitted.remove(job_info)
                            print(f"  ✗ {job_info['project']} - FAILED: {error}")
                            
                    except Exception as e:
                        print(f"  ? {job_info['project']} - Status check error: {e}")
                
                if submitted:
                    in_progress = len(submitted)
                    print(f"\n  [{datetime.now().strftime('%H:%M:%S')}] "
                          f"In progress: {in_progress} | "
                          f"Completed: {len(completed)} | "
                          f"Failed: {len(failed)}")
                    time.sleep(config.poll_interval)
                    
        except KeyboardInterrupt:
            print("\n\nMonitoring stopped by user.")
    
    # Save results
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    results = {
        "timestamp": timestamp,
        "total_jobs": len(jobs),
        "completed": completed,
        "failed": failed + failed_submit,
        "in_progress": submitted
    }
    
    os.makedirs(config.output_dir, exist_ok=True)
    results_path = os.path.join(config.output_dir, f"batch_results_{timestamp}.json")
    with open(results_path, 'w') as f:
        json.dump(results, f, indent=2)
    print(f"\nResults saved to: {results_path}")
    
    return results


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="RunPod Batch Processor for TAP Videos")
    parser.add_argument("--dry-run", action="store_true", help="Preview jobs without submitting")
    parser.add_argument("--generate-only", action="store_true", help="Generate JSON files only")
    parser.add_argument("--start", type=int, default=0, help="Start index (default: 0)")
    parser.add_argument("--count", type=int, help="Number of jobs to process")
    parser.add_argument("--all", action="store_true", help="Process all jobs")
    parser.add_argument("--list", action="store_true", help="List available projects")
    args = parser.parse_args()
    
    config = RunPodConfig()
    
    # Parse projects
    print("Parsing S3 assets report...")
    projects = parse_tap_projects(config.csv_path)
    complete = get_complete_projects(projects)
    
    print(f"Found {len(complete)} complete TAP projects\n")
    
    if args.list:
        for i, p in enumerate(complete):
            status = "✓" if p.is_complete else "✗"
            print(f"  [{i:3d}] {status} {p.name} ({p.geo})")
        return
    
    # Generate jobs
    jobs = generate_all_jobs(complete, config)
    
    if args.generate_only:
        os.makedirs(config.output_dir, exist_ok=True)
        
        # Save individual job files
        for job in jobs:
            project_name = job["input"]["job_id"]
            path = os.path.join(config.output_dir, f"{project_name}.json")
            with open(path, 'w') as f:
                json.dump(job, f, indent=2)
        
        # Save combined file
        combined_path = os.path.join(config.output_dir, "all_tap_jobs.json")
        with open(combined_path, 'w') as f:
            json.dump(jobs, f, indent=2)
        
        print(f"Generated {len(jobs)} job files in {config.output_dir}/")
        print(f"Combined file: {combined_path}")
        return
    
    # Run batch
    count = None if args.all else args.count
    run_batch(jobs, config, start=args.start, count=count, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
