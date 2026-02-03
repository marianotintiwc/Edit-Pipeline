#!/usr/bin/env python3
"""
Submit MLM jobs to RunPod from the updated CSV
"""

import csv
import requests
import os
import time
from dotenv import load_dotenv

load_dotenv()

# Configuration
RUNPOD_API_KEY = os.getenv("RUNPOD_API_KEY")
ENDPOINT_ID = "h55ft9cy7fyi1d"  # MELI Edit Classic
CSV_PATH = "/Users/marianotinti/Desktop/UGC EDITOR/Edit-Pipeline/Files for Edit - MLM_Approved.s3.csv"
OUTPUT_PREFIX = "MP-Users/MLM_Outputs"

def submit_job(row, row_num):
    """Submit a single job to RunPod"""
    
    # Extract video ID from scene_1 URL
    # Example: .../12_60_de_regalo-MLM-male/12_60_de_regalo-MLM-male_scene_1_lipsync.mp4
    scene1_url = row["scene_1_lipsync"]
    video_id = scene1_url.split("/")[-2]  # Get folder name like "12_60_de_regalo-MLM-male"
    
    payload = {
        "input": {
            "clips": [
                {"url": row["scene_1_lipsync"]},
                {"url": row["BROLL S3"]},
                {"url": row["scene_2_lipsync"]},
                {"url": row["BROLL S3"]},
                {"url": row["scene_3_lipsync"]},
                {"url": row["ENDCARD S3"]}
            ],
            "output_filename": f"{video_id}_final.mp4",
            "s3_output_prefix": OUTPUT_PREFIX
        }
    }
    
    headers = {
        "Authorization": f"Bearer {RUNPOD_API_KEY}",
        "Content-Type": "application/json"
    }
    
    url = f"https://api.runpod.ai/v2/{ENDPOINT_ID}/run"
    
    response = requests.post(url, json=payload, headers=headers)
    
    if response.status_code == 200:
        data = response.json()
        return data.get("id"), None
    else:
        return None, f"HTTP {response.status_code}: {response.text}"

def main():
    print("=" * 60)
    print("SUBMITTING MLM JOBS TO RUNPOD")
    print("=" * 60)
    print(f"Endpoint: {ENDPOINT_ID}")
    print(f"Output: s3://meli-ai.filmmaker/{OUTPUT_PREFIX}/")
    print()
    
    # Read CSV
    rows = []
    with open(CSV_PATH, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    
    print(f"Found {len(rows)} jobs to submit")
    print()
    
    # Submit jobs
    job_ids = []
    errors = []
    
    for i, row in enumerate(rows, 1):
        product = row["Product"]
        gender = row["Gender"]
        
        job_id, error = submit_job(row, i)
        
        if job_id:
            job_ids.append(job_id)
            print(f"[{i:2d}/{len(rows)}] ✓ {product}-{gender}: {job_id}")
        else:
            errors.append((i, product, error))
            print(f"[{i:2d}/{len(rows)}] ✗ {product}-{gender}: {error}")
        
        # Small delay to avoid rate limiting
        time.sleep(0.1)
    
    # Summary
    print()
    print("=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"✓ Submitted: {len(job_ids)}")
    print(f"✗ Failed: {len(errors)}")
    
    if job_ids:
        print()
        print("Job IDs saved to: mlm_job_ids.txt")
        with open("/Users/marianotinti/Desktop/UGC EDITOR/Edit-Pipeline/mlm_job_ids.txt", "w") as f:
            for jid in job_ids:
                f.write(jid + "\n")
    
    if errors:
        print()
        print("ERRORS:")
        for row_num, product, error in errors:
            print(f"  Row {row_num} ({product}): {error}")

if __name__ == "__main__":
    main()
