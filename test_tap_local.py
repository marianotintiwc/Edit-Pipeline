#!/usr/bin/env python3
"""
Test TAP editing locally before Docker deployment.

TAP Edit Structure:
  Scene 1 → Scene 2 → B-Roll (transparent + blur) → Scene 3 → Endcard (0.5s overlap)

This script tests one TAP project to validate the pipeline.
"""

import os
import sys
import json
import tempfile
import requests
from pathlib import Path

# Add parent dir to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# TAP-specific assets from the CSV
TAP_ASSETS = {
    "broll": "https://s3.us-east-2.amazonaws.com/meli-ai.filmmaker/MP-Sellers/Assets/MP_SELLERS_AI_VIDEO_GENERICO_TAP_ESP_9X16.mov",
    "endcard_a": "https://s3.us-east-2.amazonaws.com/meli-ai.filmmaker/MP-Sellers/Assets/MLB+-+Ative+com+TAP+do+Mercado+Pago.mov",
    "endcard_b": "https://s3.us-east-2.amazonaws.com/meli-ai.filmmaker/MP-Sellers/Assets/MLB+-+Use+com+TAP+do+Mercado+Pago+(1).mov",
    "endcard_c": "https://s3.us-east-2.amazonaws.com/meli-ai.filmmaker/MP-Sellers/Assets/MLB+-+Use+com+TAP+do+Mercado+Pago.mov",
}

def download_file(url: str, dest_path: str) -> bool:
    """Download a file from URL."""
    print(f"  Downloading: {url[:80]}...")
    try:
        response = requests.get(url, stream=True, timeout=60)
        response.raise_for_status()
        with open(dest_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        size_mb = os.path.getsize(dest_path) / (1024 * 1024)
        print(f"  ✅ Downloaded: {os.path.basename(dest_path)} ({size_mb:.1f} MB)")
        return True
    except Exception as e:
        print(f"  ❌ Failed: {e}")
        return False


def build_tap_request(project_folder: str, s3_base_url: str, endcard_variant: str = "A"):
    """
    Build a RunPod-style request for a TAP project.
    
    Args:
        project_folder: Folder name like "69_tap-MLB-male"
        s3_base_url: Base URL for the scene videos
        endcard_variant: Which endcard to use (A, B, or C)
    
    Returns:
        dict: Request payload for the pipeline
    """
    # Extract geo from folder name
    if "-MLB-" in project_folder:
        geo = "MLB"
    elif "-MLA-" in project_folder:
        geo = "MLA"
    elif "-MLM-" in project_folder:
        geo = "MLM"
    elif "-MLC-" in project_folder:
        geo = "MLC"
    else:
        geo = "MLB"  # Default for TAP (all are MLB)
    
    # Build scene URLs
    base = f"{s3_base_url}/{project_folder}"
    
    # TAP structure: scene_1, scene_2, broll, scene_3, endcard
    clips = [
        {"type": "scene", "url": f"{base}/{project_folder}_scene_1_lipsync.mp4"},
        {"type": "scene", "url": f"{base}/{project_folder}_scene_2_lipsync.mp4"},
        {"type": "broll", "url": TAP_ASSETS["broll"]},
        {"type": "scene", "url": f"{base}/{project_folder}_scene_3_lipsync.mp4"},
    ]
    
    # Select endcard
    endcard_key = f"endcard_{endcard_variant.lower()}"
    endcard_url = TAP_ASSETS.get(endcard_key, TAP_ASSETS["endcard_a"])
    
    return {
        "input": {
            "geo": geo,
            "clips": clips,
            "music_url": "random",
            "subtitle_mode": "auto",
            "edit_preset": "standard_vertical",
            "style_overrides": {
                "endcard": {
                    "enabled": True,
                    "overlap_seconds": 0.5,  # TAP uses 0.5s overlap
                    "url": endcard_url,  # Direct URL for endcard
                },
                "transcription": {
                    "model": "large"
                }
            }
        }
    }


def test_single_tap_project():
    """Test a single TAP project locally."""
    print("=" * 60)
    print("TAP Project Local Test")
    print("=" * 60)
    
    # Use first TAP project for testing
    test_project = "69_tap-MLB-male"
    s3_base = "https://s3.us-east-2.amazonaws.com/meli-ai.filmmaker/MP-Sellers/Outputs"
    
    print(f"\n📁 Test Project: {test_project}")
    print(f"📍 S3 Base: {s3_base}")
    
    # Build request
    request = build_tap_request(test_project, s3_base, endcard_variant="A")
    
    print("\n📋 Request Payload:")
    print(json.dumps(request, indent=2))
    
    # Verify URLs are accessible
    print("\n🔍 Verifying URLs...")
    for clip in request["input"]["clips"]:
        url = clip["url"]
        try:
            resp = requests.head(url, timeout=10)
            status = "✅" if resp.status_code == 200 else f"⚠️ {resp.status_code}"
            print(f"  {status} {clip['type']}: {url.split('/')[-1]}")
        except Exception as e:
            print(f"  ❌ {clip['type']}: {e}")
    
    # Verify endcard
    endcard_url = request["input"]["style_overrides"]["endcard"]["url"]
    try:
        resp = requests.head(endcard_url, timeout=10)
        status = "✅" if resp.status_code == 200 else f"⚠️ {resp.status_code}"
        print(f"  {status} endcard: {endcard_url.split('/')[-1]}")
    except Exception as e:
        print(f"  ❌ endcard: {e}")
    
    # Verify B-Roll
    broll_url = TAP_ASSETS["broll"]
    try:
        resp = requests.head(broll_url, timeout=10)
        status = "✅" if resp.status_code == 200 else f"⚠️ {resp.status_code}"
        print(f"  {status} broll: {broll_url.split('/')[-1]}")
    except Exception as e:
        print(f"  ❌ broll: {e}")
    
    return request


def generate_batch_requests(output_file: str = "tap_batch_requests.json"):
    """Generate batch requests for all TAP projects."""
    import csv
    
    csv_path = os.path.join(os.path.dirname(__file__), "s3_assets_report.csv")
    
    # Read all TAP folders from CSV
    tap_folders = set()
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            folder = row['Parent Folder']
            if '_tap' in folder:
                # Check if it has 3 lipsync videos
                tap_folders.add(folder)
    
    # Count scenes per folder
    folder_scenes = {}
    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            folder = row['Parent Folder']
            filename = row['Filename']
            if folder in tap_folders and '_lipsync.mp4' in filename:
                folder_scenes[folder] = folder_scenes.get(folder, 0) + 1
    
    # Filter to only folders with 3 scenes
    complete_folders = [f for f, count in folder_scenes.items() if count == 3]
    complete_folders.sort(key=lambda x: int(x.split('_')[0]))
    
    print(f"\n📊 Found {len(complete_folders)} complete TAP projects (3 scenes each)")
    
    # Generate requests
    s3_base = "https://s3.us-east-2.amazonaws.com/meli-ai.filmmaker/MP-Sellers/Outputs"
    
    batch = []
    for folder in complete_folders:
        request = build_tap_request(folder, s3_base, endcard_variant="A")
        request["project_name"] = folder  # Add for tracking
        batch.append(request)
    
    # Save to file
    output_path = os.path.join(os.path.dirname(__file__), output_file)
    with open(output_path, 'w') as f:
        json.dump(batch, f, indent=2)
    
    print(f"✅ Saved {len(batch)} requests to: {output_file}")
    return batch


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Test TAP project editing")
    parser.add_argument("--generate-batch", action="store_true", 
                        help="Generate batch requests JSON for all TAP projects")
    parser.add_argument("--test", action="store_true",
                        help="Test a single TAP project (verify URLs)")
    
    args = parser.parse_args()
    
    if args.generate_batch:
        generate_batch_requests()
    elif args.test:
        test_single_tap_project()
    else:
        # Default: run test
        test_single_tap_project()
        print("\n" + "=" * 60)
        print("To generate batch requests: python test_tap_local.py --generate-batch")
        print("=" * 60)
