#!/usr/bin/env python3
"""
MLM CSV Job Submission Script
Reads the MLM CSV, maps B-rolls and Endcards to S3 URLs, and submits MELI Edit Classic jobs.
"""
import csv
import os
import sys
import re
import requests
import unicodedata
from urllib.parse import urlparse, quote
import json
from datetime import datetime

# ================== CONFIG ==================
# Load from environment or .env file
def load_env():
    import os
    env_files = [
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"),
        os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), ".env"),
    ]
    for env_path in env_files:
        if os.path.exists(env_path):
            with open(env_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and '=' in line and not line.startswith('#'):
                        key, value = line.split('=', 1)
                        key = key.strip()
                        value = value.strip().strip('"').strip("'")
                        if key and key not in os.environ:
                            os.environ[key] = value
            break

load_env()

RUNPOD_API_KEY = os.environ.get("RUNPOD_API_KEY", "")
RUNPOD_ENDPOINT_ID = "h55ft9cy7fyi1d"  # MELI Edit Classic
S3_BUCKET = "meli-ai.filmmaker"
S3_REGION = "us-east-2"
S3_PREFIX = "MP-Users/Assets"
OUTPUT_PREFIX = "MP-Users/MLM_Outputs"

CSV_PATH = "/Users/marianotinti/Desktop/UGC EDITOR/Edit-Pipeline/Files for Edit - MLM_Approved.csv"

# B-roll mapping: product -> S3 filename
BROLL_MAPPING = {
    "60_de_regalo": "60-PESOS-REGALO-MLM.mov",
    "cuenta_pro": "GANANCIAS-DIARIAS-MLM.mov",
    "paga_tus_servicios": "INGRESO-APP-MLM.mov",
    "participa_por_50_000": "INGRESO-APP-MLM.mov",
    "participa_por_50_00o": "INGRESO-APP-MLM.mov",  # Note typo in CSV
    "prestamo_personal": "INGRESO-APP-MLM.mov",
    "tarjeta_de_credito": "TARJETA-DE-CREDITO-MLM.mp4",
    "tarjeta_debit_mastercard": "TARJETA-DEBIT-MASTERCARD-MLM.mov",
}

# Endcard mapping: Google Drive file ID -> S3 filename (from earlier upload)
# These are the EXACT filenames from S3 listing
ENDCARD_MAPPING = {
    "1XxdP69DTnoppVCaGAblbNzFJqjGI3PXr": "MLM- 60_de_regalo Endcard.mov",
    "1hOA-P2lZTNvGOP0Rdm0oul-Iec5yB78M": "MLM- cuenta_pro Endcard.mov",
    "1ONyYAdqCETU9tWkPdWBFFm4rVmI2vHuP": "MLM- participa_por_50_000 Endcard.mov",
    "19nCqgQA8heH9potisKIv8CtdCBRtrra3": "MLM- prestamo_personal Endcard.mov",
    "1tAWdTfSeRcs9SZUrxDHqTc7dehJlx3VN": "MLM- tarjeta_de_credito Endcard.mov",
    "1nTA4Lr5hcZj3ToQk75YKx1uNxbYJ88vj": "MLM- tarjeta_debit_mastercard Endcard.mov",
}


def extract_drive_file_id(url):
    """Extract Google Drive file ID from URL."""
    if not url or url.strip() == "":
        return None
    # Pattern for /d/{id}/ format
    match = re.search(r'/d/([a-zA-Z0-9_-]+)', url)
    if match:
        return match.group(1)
    # Pattern for id={id} format
    match = re.search(r'id=([a-zA-Z0-9_-]+)', url)
    if match:
        return match.group(1)
    return None


def _normalize_url(url: str) -> str:
    """NFD-decompose the path, then URL-encode non-ASCII."""
    if not url:
        return url
    parsed = urlparse(url)
    nfd_path = unicodedata.normalize("NFD", parsed.path)
    safe_path = quote(nfd_path, safe="/-_.~")
    return f"{parsed.scheme}://{parsed.netloc}{safe_path}"


def get_s3_url(filename: str) -> str:
    """Build S3 URL for a filename."""
    return f"https://s3.{S3_REGION}.amazonaws.com/{S3_BUCKET}/{S3_PREFIX}/{filename}"


def build_payload(row: dict, broll_s3: str, endcard_s3: str) -> dict:
    """Build MELI Edit Classic payload from CSV row."""
    product = row["Product"]
    geo = row["GEO"]
    gender = row["Gender"]
    
    # Extract unique ID from scene_1_lipsync URL
    scene1_url = row["scene_1_lipsync"]
    # Pattern: /MP-Users/MLM_NEW/123_product-GEO-gender/...
    match = re.search(r'/(\d+)_[^/]+/', scene1_url)
    unique_id = match.group(1) if match else "unknown"
    
    output_name = f"{unique_id}_{product}-{geo}-{gender}_edited"
    
    return {
        "input": {
            "clips": [
                {"url": _normalize_url(row["scene_1_lipsync"]), "type": "lipsync"},
                {"url": _normalize_url(row["scene_2_lipsync"]), "type": "lipsync"},
                {"url": _normalize_url(row["scene_3_lipsync"]), "type": "lipsync"},
                {"url": _normalize_url(broll_s3), "type": "broll"},
                {"url": _normalize_url(endcard_s3), "type": "endcard"},
            ],
            "output_name": output_name,
            "s3_output_prefix": OUTPUT_PREFIX,
            "style": "meli_edit_classic",
        }
    }


def submit_job(payload: dict) -> dict:
    """Submit job to RunPod endpoint."""
    url = f"https://api.runpod.ai/v2/{RUNPOD_ENDPOINT_ID}/run"
    headers = {
        "Authorization": f"Bearer {RUNPOD_API_KEY}",
        "Content-Type": "application/json",
    }
    response = requests.post(url, headers=headers, json=payload, timeout=30)
    response.raise_for_status()
    return response.json()


def main():
    print("=" * 60)
    print("MLM CSV Job Submission")
    print(f"Endpoint: {RUNPOD_ENDPOINT_ID}")
    print(f"Output prefix: {OUTPUT_PREFIX}")
    print("=" * 60)
    
    # Read CSV
    with open(CSV_PATH, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    
    print(f"\nFound {len(rows)} rows in CSV")
    
    # Process each row
    successful = 0
    failed = 0
    job_ids = []
    
    for i, row in enumerate(rows, 1):
        product = row["Product"]
        geo = row["GEO"]
        gender = row["Gender"]
        
        print(f"\n[{i}/{len(rows)}] {product}-{geo}-{gender}")
        
        # Get B-roll S3 URL
        broll_filename = BROLL_MAPPING.get(product)
        if not broll_filename:
            print(f"  ✗ No B-roll mapping for product: {product}")
            failed += 1
            continue
        broll_s3 = get_s3_url(broll_filename)
        
        # Get Endcard S3 URL
        endcard_drive_url = row.get("Endcard", "")
        endcard_file_id = extract_drive_file_id(endcard_drive_url)
        endcard_filename = ENDCARD_MAPPING.get(endcard_file_id)
        if not endcard_filename:
            print(f"  ✗ No Endcard mapping for Drive ID: {endcard_file_id}")
            failed += 1
            continue
        endcard_s3 = get_s3_url(endcard_filename)
        
        print(f"  B-roll: {broll_filename}")
        print(f"  Endcard: {endcard_filename}")
        
        # Build and submit
        try:
            payload = build_payload(row, broll_s3, endcard_s3)
            result = submit_job(payload)
            job_id = result.get("id", "unknown")
            job_ids.append(job_id)
            print(f"  ✓ Submitted: {job_id}")
            successful += 1
        except Exception as e:
            print(f"  ✗ Failed: {e}")
            failed += 1
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total rows: {len(rows)}")
    print(f"Successful: {successful}")
    print(f"Failed: {failed}")
    
    if job_ids:
        print(f"\nJob IDs saved to mlm_job_ids_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
        with open(f"/Users/marianotinti/Desktop/UGC EDITOR/Edit-Pipeline/Helper Scripts/mlm_job_ids_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt", 'w') as f:
            f.write('\n'.join(job_ids))


if __name__ == "__main__":
    main()
