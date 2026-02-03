#!/usr/bin/env python3
"""
Download MLM assets (B-rolls and Endcards) from Google Drive and upload to S3,
then create a proper CSV with S3 URLs.
"""
import csv
import os
import re
import tempfile
from urllib.parse import quote

import boto3
import requests

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.dirname(BASE_DIR)
INPUT_CSV = os.path.join(REPO_DIR, "Files for Edit - MLM_Approved.csv")
OUTPUT_CSV = os.path.join(REPO_DIR, "Files for Edit - MLM_Approved.s3.csv")

S3_BUCKET = "meli-ai.filmmaker"
S3_PREFIX = "MP-Users/Assets"
S3_REGION = "us-east-2"


def load_env_from_dotenv() -> None:
    candidates = [
        os.path.join(REPO_DIR, ".env"),
        os.path.join(os.path.dirname(REPO_DIR), ".env"),
    ]
    for path in candidates:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    if key and key not in os.environ:
                        os.environ[key] = value
            break


def extract_drive_file_id(url: str) -> str | None:
    """Extract Google Drive file ID from various URL formats."""
    if not url or "drive.google.com" not in url:
        return None
    # Format: https://drive.google.com/file/d/FILE_ID/view...
    m = re.search(r"/file/d/([^/]+)", url)
    if m:
        return m.group(1)
    # Format: https://drive.google.com/open?id=FILE_ID
    m = re.search(r"[?&]id=([^&]+)", url)
    if m:
        return m.group(1)
    return None


def download_from_google_drive(file_id: str, dest_path: str) -> bool:
    """Download a file from Google Drive using direct download URL."""
    url = f"https://drive.google.com/uc?export=download&id={file_id}"
    
    session = requests.Session()
    
    print(f"  Downloading from Google Drive: {file_id}")
    response = session.get(url, stream=True, allow_redirects=True)
    
    # Check if we got a confirmation page (for large files)
    if "text/html" in response.headers.get("Content-Type", ""):
        for key, value in response.cookies.items():
            if key.startswith("download_warning"):
                url = f"https://drive.google.com/uc?export=download&confirm={value}&id={file_id}"
                response = session.get(url, stream=True, allow_redirects=True)
                break
        else:
            url = f"https://drive.google.com/uc?export=download&confirm=t&id={file_id}"
            response = session.get(url, stream=True, allow_redirects=True)
    
    if response.status_code != 200:
        print(f"  ERROR: Failed to download, status {response.status_code}")
        return False
    
    content_type = response.headers.get("Content-Type", "")
    if "text/html" in content_type:
        print(f"  ERROR: Got HTML instead of video - file may not be publicly shared")
        return False
    
    with open(dest_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)
    
    file_size = os.path.getsize(dest_path)
    print(f"  Downloaded: {file_size / 1024 / 1024:.1f} MB")
    return file_size > 0


def upload_to_s3(local_path: str, s3_key: str, s3_client) -> str:
    """Upload a file to S3 and return the HTTPS URL."""
    print(f"  Uploading to S3: {s3_key}")
    
    if local_path.endswith(".mov"):
        content_type = "video/quicktime"
    elif local_path.endswith(".mp4"):
        content_type = "video/mp4"
    else:
        content_type = "application/octet-stream"
    
    s3_client.upload_file(
        local_path,
        S3_BUCKET,
        s3_key,
        ExtraArgs={"ContentType": content_type}
    )
    
    encoded_key = quote(s3_key, safe="/")
    return f"https://s3.{S3_REGION}.amazonaws.com/{S3_BUCKET}/{encoded_key}"


def check_s3_exists(s3_key: str, s3_client) -> str | None:
    """Check if a key exists in S3, return HTTPS URL if it does."""
    try:
        s3_client.head_object(Bucket=S3_BUCKET, Key=s3_key)
        encoded_key = quote(s3_key, safe="/")
        return f"https://s3.{S3_REGION}.amazonaws.com/{S3_BUCKET}/{encoded_key}"
    except:
        return None


def main():
    load_env_from_dotenv()
    
    s3_client = boto3.client(
        "s3",
        region_name=S3_REGION,
        aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
    )
    
    with open(INPUT_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    
    print(f"Read {len(rows)} rows from {INPUT_CSV}")
    
    # Collect unique assets by Google Drive ID
    # Map: drive_id -> (asset_type, product_hint, s3_url)
    unique_assets = {}
    
    for row in rows:
        product = row.get("Product", "").strip()
        broll_url = (row.get("BRoll") or row.get("Broll") or "").strip()
        endcard_url = (row.get("Endcard") or "").strip()
        
        broll_id = extract_drive_file_id(broll_url)
        endcard_id = extract_drive_file_id(endcard_url)
        
        if broll_id and broll_id not in unique_assets:
            unique_assets[broll_id] = ("broll", product, None)
        
        if endcard_id and endcard_id not in unique_assets:
            unique_assets[endcard_id] = ("endcard", product, None)
    
    print(f"\nUnique assets to process: {len(unique_assets)}")
    
    # Process each unique asset
    with tempfile.TemporaryDirectory() as tmp_dir:
        for drive_id, (asset_type, product_hint, _) in list(unique_assets.items()):
            ext = ".mov"  # Default extension
            if asset_type == "broll":
                s3_name = f"MLM- {product_hint} Broll{ext}"
            else:
                s3_name = f"MLM- {product_hint} Endcard{ext}"
            
            s3_key = f"{S3_PREFIX}/{s3_name}"
            
            print(f"\n{asset_type.upper()}: {drive_id} ({product_hint})")
            
            # Check if already in S3
            existing_url = check_s3_exists(s3_key, s3_client)
            if existing_url:
                unique_assets[drive_id] = (asset_type, product_hint, existing_url)
                print(f"  ✓ Already in S3: {s3_name}")
                continue
            
            # Download from Google Drive
            local_path = os.path.join(tmp_dir, f"{drive_id}{ext}")
            if download_from_google_drive(drive_id, local_path):
                s3_url = upload_to_s3(local_path, s3_key, s3_client)
                unique_assets[drive_id] = (asset_type, product_hint, s3_url)
                print(f"  ✓ Uploaded: {s3_name}")
            else:
                print(f"  ✗ Failed to download")
    
    # Generate output CSV
    print("\n--- Generating Output CSV ---")
    
    output_rows = []
    for row in rows:
        broll_url = (row.get("BRoll") or row.get("Broll") or "").strip()
        endcard_url = (row.get("Endcard") or "").strip()
        
        broll_id = extract_drive_file_id(broll_url)
        endcard_id = extract_drive_file_id(endcard_url)
        
        broll_s3 = unique_assets.get(broll_id, (None, None, None))[2] or ""
        endcard_s3 = unique_assets.get(endcard_id, (None, None, None))[2] or ""
        
        output_row = {
            "Product": row.get("Product", ""),
            "GEO": row.get("GEO", ""),
            "Gender": row.get("Gender", ""),
            "scene_1_lipsync": row.get("scene_1_lipsync", ""),
            "scene_2_lipsync": row.get("scene_2_lipsync", ""),
            "scene_3_lipsync": row.get("scene_3_lipsync", ""),
            "Broll": broll_url,
            "Endcard": endcard_url,
            "BROLL S3": broll_s3,
            "ENDCARD S3": endcard_s3,
        }
        output_rows.append(output_row)
    
    fieldnames = ["Product", "GEO", "Gender", "scene_1_lipsync", "scene_2_lipsync", "scene_3_lipsync", "Broll", "Endcard", "BROLL S3", "ENDCARD S3"]
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(output_rows)
    
    print(f"\n✓ Output CSV written: {OUTPUT_CSV}")
    print(f"  Total rows: {len(output_rows)}")
    
    # Summary
    print("\n--- Summary ---")
    missing = [(k, v) for k, v in unique_assets.items() if not v[2]]
    if missing:
        print(f"⚠ Missing assets ({len(missing)}):")
        for drive_id, (asset_type, product, _) in missing:
            print(f"  - {asset_type}: {drive_id} ({product})")
    else:
        print("✓ All assets available in S3!")


if __name__ == "__main__":
    main()
