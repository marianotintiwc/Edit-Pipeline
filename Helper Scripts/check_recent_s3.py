#!/usr/bin/env python3
"""Check for recent MLM outputs in S3."""
import os
import boto3
from datetime import datetime, timezone

# Load env
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
with open(env_path, 'r') as f:
    for line in f:
        line = line.strip()
        if line and '=' in line and not line.startswith('#'):
            key, value = line.split('=', 1)
            os.environ[key.strip()] = value.strip().strip('"')

s3 = boto3.client('s3', region_name='us-east-2')

# List recent outputs
paginator = s3.get_paginator('list_objects_v2')
recent_mlm = []
all_mlm = []

print("Scanning S3 for MLM outputs...\n")

for page in paginator.paginate(Bucket='meli-ai.filmmaker'):
    for obj in page.get('Contents', []):
        key = obj['Key']
        if not key.endswith('.mp4'):
            continue
            
        last_modified = obj['LastModified']
        age_hours = (datetime.now(timezone.utc) - last_modified).total_seconds() / 3600
        
        # Check for our MLM outputs by the naming pattern we used
        if '_edited' in key or 'MLM' in key:
            all_mlm.append((key, obj['Size'], age_hours, last_modified))
            if age_hours < 4:  # Last 4 hours
                recent_mlm.append((key, obj['Size'], age_hours))

print(f"Total MLM-related videos: {len(all_mlm)}")
print(f"Recent (last 4h): {len(recent_mlm)}")

if recent_mlm:
    print("\n=== RECENT MLM OUTPUTS ===")
    for key, size, age in sorted(recent_mlm, key=lambda x: x[2])[:30]:
        mb = size / 1024 / 1024
        name = key.split('/')[-1]
        print(f"  {age:5.2f}h ago  {mb:6.1f} MB  {name}")
    if len(recent_mlm) > 30:
        print(f"  ... and {len(recent_mlm) - 30} more")
else:
    print("\nNo recent MLM outputs found in S3.")
    print("\nMost recent MLM files:")
    for key, size, age, dt in sorted(all_mlm, key=lambda x: x[2])[:10]:
        mb = size / 1024 / 1024
        name = key.split('/')[-1]
        print(f"  {age:5.1f}h ago  {mb:6.1f} MB  {name}")
