#!/usr/bin/env python3
"""Upload MLM B-roll files from local folder to S3."""
import boto3
import os
from urllib.parse import quote

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.dirname(BASE_DIR)

def load_env():
    for path in [os.path.join(REPO_DIR, ".env"), os.path.join(os.path.dirname(REPO_DIR), ".env")]:
        if os.path.exists(path):
            with open(path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        if k.strip() not in os.environ:
                            os.environ[k.strip()] = v.strip().strip('"').strip("'")
            break

load_env()

s3 = boto3.client('s3', region_name='us-east-2',
    aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
    aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY'))

bucket = 'meli-ai.filmmaker'
prefix = 'MP-Users/Assets'
local_dir = os.path.join(REPO_DIR, 'assets/IGNOREASSETS/users_assets_upload_tmp/MLM')

files = [f for f in os.listdir(local_dir) if f.endswith(('.mov', '.mp4'))]
print(f'Found {len(files)} files to upload')

for f in files:
    local_path = os.path.join(local_dir, f)
    s3_key = f'{prefix}/{f}'
    
    try:
        s3.head_object(Bucket=bucket, Key=s3_key)
        print(f'✓ Already in S3: {f}')
        continue
    except:
        pass
    
    content_type = 'video/quicktime' if f.endswith('.mov') else 'video/mp4'
    size_mb = os.path.getsize(local_path) / 1024 / 1024
    print(f'Uploading {f} ({size_mb:.1f} MB)...')
    s3.upload_file(local_path, bucket, s3_key, ExtraArgs={'ContentType': content_type})
    print(f'✓ Uploaded: {f}')

print('Done!')
