#!/usr/bin/env python3
"""
Upload MLB B-rolls and Endcards from Google Drive to S3
========================================================
Downloads unique B-rolls/Endcards from Google Drive and uploads to S3,
then updates mlb_edit_mapping.csv with S3 URLs.
"""

import csv
import os
import re
import boto3
from pathlib import Path
import gdown
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

# S3 Configuration
S3_BUCKET = "meli-ai.filmmaker"
S3_PREFIX = "MLB_Assets/brolls_endcards"
AWS_REGION = "us-east-2"

# Local temp directory
TEMP_DIR = Path("batch_temp/broll_upload")


def extract_drive_id(url: str) -> str:
    """Extract Google Drive file ID from URL."""
    if not url:
        return None
    match = re.search(r'/d/([a-zA-Z0-9_-]+)', url)
    return match.group(1) if match else None


def download_from_drive(file_id: str, output_path: Path) -> bool:
    """Download file from Google Drive using gdown."""
    if output_path.exists():
        print(f"  ⏭️  Already exists: {output_path.name}")
        return True
    
    try:
        url = f"https://drive.google.com/uc?id={file_id}"
        print(f"  ⬇️  Downloading {file_id}...")
        gdown.download(url, str(output_path), quiet=False)
        
        # Verify it's a valid video file
        if output_path.exists() and output_path.stat().st_size > 1000000:  # > 1MB
            print(f"  ✅ Downloaded: {output_path.name} ({output_path.stat().st_size / 1024 / 1024:.1f} MB)")
            return True
        else:
            print(f"  ❌ Download failed or file too small")
            if output_path.exists():
                output_path.unlink()
            return False
    except Exception as e:
        print(f"  ❌ Error: {e}")
        return False


def upload_to_s3(local_path: Path, s3_key: str) -> str:
    """Upload file to S3 and return the URL."""
    s3 = boto3.client(
        's3',
        region_name=AWS_REGION,
        aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
        aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY')
    )
    
    try:
        print(f"  ☁️  Uploading to s3://{S3_BUCKET}/{s3_key}...")
        s3.upload_file(
            str(local_path),
            S3_BUCKET,
            s3_key,
            ExtraArgs={'ContentType': 'video/mp4'}
        )
        s3_url = f"https://s3.{AWS_REGION}.amazonaws.com/{S3_BUCKET}/{s3_key}"
        print(f"  ✅ Uploaded: {s3_url}")
        return s3_url
    except Exception as e:
        print(f"  ❌ Upload error: {e}")
        return None


def main():
    # Create temp directory
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    
    # Load mapping
    mapping_path = "mlb_edit_mapping.csv"
    with open(mapping_path, 'r', encoding='utf-8') as f:
        rows = list(csv.DictReader(f))
    
    print(f"✅ Loaded {len(rows)} MLB projects\n")
    
    # Collect unique B-roll and Endcard URLs
    unique_brolls = {}
    unique_endcards = {}
    
    for row in rows:
        broll_url = row.get('Broll_URL', '').strip()
        endcard_url = row.get('Endcard_URL', '').strip()
        value_prop = row.get('ValueProp', '').strip()
        
        broll_id = extract_drive_id(broll_url)
        endcard_id = extract_drive_id(endcard_url)
        
        if broll_id and broll_id not in unique_brolls:
            unique_brolls[broll_id] = {'value_prop': value_prop, 'original_url': broll_url}
        
        if endcard_id and endcard_id not in unique_endcards:
            unique_endcards[endcard_id] = {'value_prop': value_prop, 'original_url': endcard_url}
    
    print(f"📁 Unique B-rolls: {len(unique_brolls)}")
    print(f"📁 Unique Endcards: {len(unique_endcards)}\n")
    
    # Download and upload B-rolls
    print("=" * 60)
    print("PROCESSING B-ROLLS")
    print("=" * 60)
    
    broll_s3_map = {}  # drive_id -> s3_url
    for drive_id, info in unique_brolls.items():
        print(f"\n🎬 B-roll: {info['value_prop']} ({drive_id})")
        
        local_path = TEMP_DIR / f"broll_{drive_id}.mp4"
        
        if download_from_drive(drive_id, local_path):
            s3_key = f"{S3_PREFIX}/broll_{drive_id}.mp4"
            s3_url = upload_to_s3(local_path, s3_key)
            if s3_url:
                broll_s3_map[drive_id] = s3_url
    
    # Download and upload Endcards
    print("\n" + "=" * 60)
    print("PROCESSING ENDCARDS")
    print("=" * 60)
    
    endcard_s3_map = {}  # drive_id -> s3_url
    for drive_id, info in unique_endcards.items():
        print(f"\n🎬 Endcard: {info['value_prop']} ({drive_id})")
        
        local_path = TEMP_DIR / f"endcard_{drive_id}.mp4"
        
        if download_from_drive(drive_id, local_path):
            s3_key = f"{S3_PREFIX}/endcard_{drive_id}.mp4"
            s3_url = upload_to_s3(local_path, s3_key)
            if s3_url:
                endcard_s3_map[drive_id] = s3_url
    
    # Update mapping CSV
    print("\n" + "=" * 60)
    print("UPDATING MAPPING CSV")
    print("=" * 60)
    
    updated_rows = []
    for row in rows:
        broll_id = extract_drive_id(row.get('Broll_URL', ''))
        endcard_id = extract_drive_id(row.get('Endcard_URL', ''))
        
        if broll_id and broll_id in broll_s3_map:
            row['Broll_URL'] = broll_s3_map[broll_id]
        
        if endcard_id and endcard_id in endcard_s3_map:
            row['Endcard_URL'] = endcard_s3_map[endcard_id]
        
        updated_rows.append(row)
    
    # Write updated CSV
    output_path = "mlb_edit_mapping_s3.csv"
    fieldnames = list(rows[0].keys())
    with open(output_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(updated_rows)
    
    print(f"\n✅ Updated mapping saved to: {output_path}")
    print(f"   B-rolls migrated: {len(broll_s3_map)}/{len(unique_brolls)}")
    print(f"   Endcards migrated: {len(endcard_s3_map)}/{len(unique_endcards)}")
    
    # Summary
    print("\n" + "=" * 60)
    print("S3 URL MAPPING")
    print("=" * 60)
    print("\nB-rolls:")
    for drive_id, s3_url in broll_s3_map.items():
        print(f"  {drive_id} → {s3_url}")
    print("\nEndcards:")
    for drive_id, s3_url in endcard_s3_map.items():
        print(f"  {drive_id} → {s3_url}")


if __name__ == "__main__":
    main()
