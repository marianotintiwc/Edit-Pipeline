#!/usr/bin/env python3
"""
=============================================================================
MELI Edit Runner - Simple Interface for RunPod Processing
=============================================================================
Run MELI EDIT CLASSIC with pre-configured cases.

Usage:
    # List available cases
    python run_meli_edit.py --list
    
    # Run a single job
    python run_meli_edit.py --case MLB_PIX --scenes s1.mp4 s2.mp4 s3.mp4
    
    # Run from a jobs JSON file
    python run_meli_edit.py --jobs jobs.json
    
    # Run with custom output name
    python run_meli_edit.py --case MLB_PIX --scenes s1.mp4 s2.mp4 s3.mp4 --output my_video.mp4

Example jobs.json:
    {
      "jobs": [
        {
          "case": "MLB_PIX",
          "scenes": ["https://s3.../scene1.mp4", "https://s3.../scene2.mp4", "https://s3.../scene3.mp4"],
          "output_name": "project_001"
        },
        {
          "case": "MLB_COFRINHOS", 
          "scenes": ["https://s3.../scene1.mp4", "https://s3.../scene2.mp4", "https://s3.../scene3.mp4"],
          "output_name": "project_002"
        }
      ]
    }
"""

import argparse
import json
import os
import sys
import time
import threading
import queue
from datetime import datetime
from typing import Optional, List, Dict

# Load .env
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

import requests

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CASES_FILE = os.path.join(BASE_DIR, "presets", "meli_cases.json")


def load_cases() -> dict:
    """Load the MELI cases configuration"""
    with open(CASES_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)


def list_cases():
    """Print all available cases"""
    config = load_cases()
    
    print("=" * 70)
    print("📋 AVAILABLE MELI EDIT CASES")
    print("=" * 70)
    
    # Group by GEO
    by_geo = {}
    for case_id, case_data in config['cases'].items():
        geo = case_data['geo']
        if geo not in by_geo:
            by_geo[geo] = []
        by_geo[geo].append((case_id, case_data))
    
    for geo in sorted(by_geo.keys()):
        print(f"\n🌎 {geo} ({by_geo[geo][0][1]['language']})")
        print("-" * 40)
        for case_id, case_data in sorted(by_geo[geo]):
            has_endcard = "✓" if case_data.get('endcard_url') else "✗"
            print(f"   {case_id:<30} Endcard: {has_endcard}")
    
    print("\n" + "=" * 70)
    print("Usage: python run_meli_edit.py --case <CASE_ID> --scenes s1.mp4 s2.mp4 s3.mp4")


def build_payload(case_id: str, scene_urls: List[str], output_name: Optional[str] = None, output_folder: Optional[str] = None) -> dict:
    """Build RunPod payload from case ID and scene URLs"""
    config = load_cases()
    
    if case_id not in config['cases']:
        raise ValueError(f"Unknown case: {case_id}. Use --list to see available cases.")
    
    case = config['cases'][case_id]
    base_style = config['base_style'].copy()
    
    # Set endcard URL
    if case.get('endcard_url'):
        base_style['endcard'] = {
            **base_style.get('endcard', {}),
            'url': case['endcard_url']
        }
    
    # Build clips array: scene1, scene2, broll, scene3, endcard
    clips = [
        {"type": "scene", "url": scene_urls[0]},
        {"type": "scene", "url": scene_urls[1]},
        {"type": "broll", "url": case['broll_url']},
        {"type": "scene", "url": scene_urls[2]},
    ]

    # Add endcard as a clip so the handler includes it in clips.json
    if case.get("endcard_url"):
        clips.append({"type": "endcard", "url": case["endcard_url"]})
    
    # Output name
    if not output_name:
        output_name = f"{case_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    return {
        "input": {
            "job_id": f"meli_{output_name}",
            "geo": case['geo'],
            "output_folder": output_folder or "MELI_Exports/2026-01",
            "output_filename": f"{output_name}_MELI_EDIT.mp4",
            "clips": clips,
            "music_url": "random",
            "subtitle_mode": "auto",
            "edit_preset": "standard_vertical",
            "style_overrides": base_style
        }
    }


class RunPodClient:
    def __init__(self, api_key: str, endpoint_id: str):
        self.base_url = f"https://api.runpod.ai/v2/{endpoint_id}"
        self.headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    
    def submit_job(self, payload: dict) -> dict:
        r = requests.post(f"{self.base_url}/run", json=payload, headers=self.headers)
        r.raise_for_status()
        return r.json()
    
    def get_job_status(self, job_id: str) -> dict:
        r = requests.get(f"{self.base_url}/status/{job_id}", headers=self.headers)
        r.raise_for_status()
        return r.json()


def run_single_job(case_id: str, scene_urls: List[str], output_name: Optional[str] = None, 
                   output_folder: Optional[str] = None, wait: bool = True) -> dict:
    """Run a single MELI edit job"""
    api_key = os.environ.get("RUNPOD_API_KEY")
    endpoint_id = os.environ.get("RUNPOD_ENDPOINT_ID", "3zysuiunu9iacy")
    
    if not api_key:
        raise ValueError("RUNPOD_API_KEY not set")
    
    payload = build_payload(case_id, scene_urls, output_name, output_folder)
    client = RunPodClient(api_key, endpoint_id)
    
    print(f"🚀 Submitting job: {case_id}")
    print(f"   Scenes: {len(scene_urls)}")
    print(f"   Output: {payload['input']['output_filename']}")
    
    result = client.submit_job(payload)
    job_id = result.get("id")
    print(f"✅ Job submitted: {job_id}")
    
    if not wait:
        return {"job_id": job_id, "status": "SUBMITTED"}
    
    # Poll until complete
    print("⏳ Waiting for completion...")
    start_time = time.time()
    poll_interval = 15
    
    while True:
        time.sleep(poll_interval)
        elapsed = time.time() - start_time
        
        status = client.get_job_status(job_id)
        job_status = status.get("status", "UNKNOWN")
        
        print(f"   [{elapsed:.0f}s] {job_status}")
        
        if job_status == "COMPLETED":
            output = status.get("output", {})
            print(f"\n✅ COMPLETED in {elapsed:.1f}s")
            print(f"   Output: {output.get('output_url', 'N/A')}")
            return {"job_id": job_id, "status": "COMPLETED", "output": output, "elapsed": elapsed}
            
        elif job_status == "FAILED":
            error = status.get("error", "Unknown")
            print(f"\n❌ FAILED: {error}")
            return {"job_id": job_id, "status": "FAILED", "error": error, "elapsed": elapsed}


def run_jobs_from_file(jobs_file: str, workers: int = 3):
    """Run multiple jobs from a JSON file"""
    with open(jobs_file, 'r', encoding='utf-8') as f:
        jobs_config = json.load(f)
    
    jobs = jobs_config.get('jobs', [])
    output_folder = jobs_config.get('output_folder', "MELI_Exports/2026-01")
    
    print("=" * 70)
    print(f"🚀 BATCH MELI EDIT: {len(jobs)} jobs with {workers} workers")
    print("=" * 70)
    
    api_key = os.environ.get("RUNPOD_API_KEY")
    endpoint_id = os.environ.get("RUNPOD_ENDPOINT_ID", "3zysuiunu9iacy")
    
    if not api_key:
        print("❌ RUNPOD_API_KEY not set")
        return
    
    client = RunPodClient(api_key, endpoint_id)
    
    # Stats
    stats = {'completed': 0, 'failed': 0, 'total': len(jobs), 'results': []}
    stats_lock = threading.Lock()
    print_lock = threading.Lock()
    
    def log(msg):
        with print_lock:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")
    
    def worker(worker_id: int, job_queue: queue.Queue):
        while True:
            try:
                job = job_queue.get(timeout=1)
            except queue.Empty:
                if job_queue.empty():
                    return
                continue
            
            try:
                payload = build_payload(
                    job['case'],
                    job['scenes'],
                    job.get('output_name'),
                    output_folder
                )
                
                log(f"🚀 Worker {worker_id} | Starting: {job['case']}")
                
                result = client.submit_job(payload)
                runpod_id = result.get("id")
                log(f"✅ Worker {worker_id} | Submitted: {runpod_id}")
                
                start_time = time.time()
                while True:
                    time.sleep(15)
                    status = client.get_job_status(runpod_id)
                    job_status = status.get("status")
                    
                    if job_status == "COMPLETED":
                        elapsed = time.time() - start_time
                        output = status.get("output", {})
                        with stats_lock:
                            stats['completed'] += 1
                            stats['results'].append({
                                'case': job['case'],
                                'status': 'COMPLETED',
                                'output_url': output.get('output_url'),
                                'elapsed': elapsed
                            })
                        log(f"✅ Worker {worker_id} | {job['case']} COMPLETED in {elapsed:.0f}s")
                        break
                        
                    elif job_status == "FAILED":
                        with stats_lock:
                            stats['failed'] += 1
                            stats['results'].append({
                                'case': job['case'],
                                'status': 'FAILED',
                                'error': status.get('error')
                            })
                        log(f"❌ Worker {worker_id} | {job['case']} FAILED")
                        break
                        
            except Exception as e:
                with stats_lock:
                    stats['failed'] += 1
                log(f"❌ Worker {worker_id} | Error: {e}")
            
            finally:
                job_queue.task_done()
    
    # Create queue
    job_queue = queue.Queue()
    for job in jobs:
        job_queue.put(job)
    
    # Start workers
    threads = []
    for i in range(workers):
        t = threading.Thread(target=worker, args=(i + 1, job_queue))
        t.start()
        threads.append(t)
    
    # Wait
    for t in threads:
        t.join()
    
    # Summary
    print("\n" + "=" * 70)
    print("BATCH COMPLETE")
    print(f"Completed: {stats['completed']}/{stats['total']}")
    print(f"Failed: {stats['failed']}/{stats['total']}")


def main():
    parser = argparse.ArgumentParser(
        description="MELI Edit Runner - Simple interface for RunPod processing",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python run_meli_edit.py --list
    python run_meli_edit.py --case MLB_PIX --scenes s1.mp4 s2.mp4 s3.mp4
    python run_meli_edit.py --jobs my_jobs.json --workers 3
        """
    )
    
    parser.add_argument("--list", "-l", action="store_true", help="List all available cases")
    parser.add_argument("--case", "-c", help="Case ID (e.g., MLB_PIX, MLA_INCENTIVOS)")
    parser.add_argument("--scenes", "-s", nargs=3, metavar="URL", help="Three scene URLs: scene1 scene2 scene3")
    parser.add_argument("--output", "-o", help="Custom output filename (without .mp4)")
    parser.add_argument("--output-folder", help="S3 output folder")
    parser.add_argument("--jobs", "-j", help="JSON file with multiple jobs")
    parser.add_argument("--workers", "-w", type=int, default=3, help="Number of workers for batch jobs")
    parser.add_argument("--no-wait", action="store_true", help="Submit and don't wait for completion")
    parser.add_argument("--payload-only", action="store_true", help="Print payload JSON and exit (don't submit)")
    
    args = parser.parse_args()
    
    if args.list:
        list_cases()
        return 0
    
    if args.jobs:
        run_jobs_from_file(args.jobs, args.workers)
        return 0
    
    if args.case and args.scenes:
        if args.payload_only:
            payload = build_payload(args.case, args.scenes, args.output, args.output_folder)
            print(json.dumps(payload, indent=2))
            return 0
        
        run_single_job(
            args.case,
            args.scenes,
            args.output,
            args.output_folder,
            wait=not args.no_wait
        )
        return 0
    
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
