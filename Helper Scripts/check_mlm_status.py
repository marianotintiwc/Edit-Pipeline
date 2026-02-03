#!/usr/bin/env python3
"""Check status of MLM jobs on RunPod."""
import os
import glob
import requests

# Load env
env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
with open(env_path, 'r') as f:
    for line in f:
        line = line.strip()
        if line and '=' in line and not line.startswith('#'):
            key, value = line.split('=', 1)
            os.environ[key.strip()] = value.strip().strip('"')

API_KEY = os.environ.get('RUNPOD_API_KEY')
ENDPOINT_ID = 'h55ft9cy7fyi1d'

# Read job IDs
job_files = sorted(glob.glob(os.path.join(os.path.dirname(__file__), 'mlm_job_ids_*.txt')))
if not job_files:
    print('No job ID files found')
    exit()

with open(job_files[-1], 'r') as f:
    job_ids = [line.strip() for line in f if line.strip()]

print(f'Checking {len(job_ids)} MLM jobs...\n')

headers = {'Authorization': f'Bearer {API_KEY}'}
statuses = {}
failed_jobs = []

for job_id in job_ids:
    url = f'https://api.runpod.ai/v2/{ENDPOINT_ID}/status/{job_id}'
    try:
        r = requests.get(url, headers=headers, timeout=10)
        data = r.json()
        status = data.get('status', 'UNKNOWN')
        statuses[status] = statuses.get(status, 0) + 1
        if status == 'FAILED':
            failed_jobs.append((job_id, data.get('error', 'Unknown error')))
    except Exception as e:
        statuses['ERROR'] = statuses.get('ERROR', 0) + 1

print('=' * 40)
print('MLM JOBS STATUS')
print('=' * 40)
for status, count in sorted(statuses.items(), key=lambda x: -x[1]):
    if count > 0:
        pct = count / len(job_ids) * 100
        bar = '█' * int(pct / 5)
        print(f'{status:12} {count:3} ({pct:5.1f}%) {bar}')
print('=' * 40)
print(f'Total: {len(job_ids)} jobs')

if failed_jobs:
    print('\nFailed jobs:')
    for job_id, error in failed_jobs[:5]:
        print(f'  {job_id}: {error}')
