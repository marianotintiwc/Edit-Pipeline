#!/usr/bin/env python3
"""
Test TAP project in Docker container.
Run after docker build is complete.
"""

import subprocess
import json
import os
import sys
from pathlib import Path

def main():
    # Load test request
    script_dir = Path(__file__).parent
    request_file = script_dir / "test_tap_request.json"
    
    with open(request_file) as f:
        test_request = json.load(f)
    
    print("=" * 60)
    print("TAP Docker Test")
    print("=" * 60)
    print(f"\n📋 Test Request:")
    print(json.dumps(test_request, indent=2))
    
    # Load .env file
    env_file = script_dir / ".env"
    env_vars = {}
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    env_vars[key.strip()] = value.strip()
    
    aws_key = env_vars.get('AWS_ACCESS_KEY_ID', '')
    aws_secret = env_vars.get('AWS_SECRET_ACCESS_KEY', '')
    aws_region = env_vars.get('AWS_DEFAULT_REGION', 'us-east-2')
    s3_bucket = env_vars.get('S3_BUCKET', 'meli-ai.filmmaker')
    
    if not aws_key or not aws_secret:
        print("❌ AWS credentials not found in .env file!")
        sys.exit(1)
    
    print(f"\n🔑 AWS Region: {aws_region}")
    print(f"📦 S3 Bucket: {s3_bucket}")
    
    # Save request to temp file for mounting
    temp_request = script_dir / "temp_docker_request.json"
    with open(temp_request, 'w') as f:
        json.dump(test_request, f)
    
    # Build docker run command
    # Note: Using --gpus all requires NVIDIA Container Toolkit
    cmd = [
        "docker", "run",
        "--rm",
        "-it",
        "--gpus", "all",
        "-e", f"AWS_ACCESS_KEY_ID={aws_key}",
        "-e", f"AWS_SECRET_ACCESS_KEY={aws_secret}",
        "-e", f"AWS_REGION={aws_region}",
        "-e", f"S3_BUCKET={s3_bucket}",
        "-v", f"{temp_request}:/app/test_request.json:ro",
        "ugc-pipeline:latest",
        "python", "-c", """
import json
import sys
sys.path.insert(0, '/app')

# Load test request
with open('/app/test_request.json') as f:
    request = json.load(f)

print("\\n🚀 Starting pipeline test...")
print("=" * 50)

# Run the handler's process function
from handler import process_job

# Simulate RunPod job
class MockJob:
    def __init__(self, input_data):
        self.input = input_data
        self.id = "test-job-001"

mock_job = MockJob(request['input'])

try:
    result = process_job(mock_job)
    print("\\n✅ SUCCESS!")
    print(json.dumps(result, indent=2))
except Exception as e:
    print(f"\\n❌ ERROR: {e}")
    import traceback
    traceback.print_exc()
"""
    ]
    
    print(f"\n🐳 Running Docker container...")
    print(f"   Command: docker run --gpus all ugc-pipeline:latest ...")
    print("\n" + "=" * 60)
    
    # Run docker
    result = subprocess.run(cmd, cwd=str(script_dir))
    
    # Cleanup
    if temp_request.exists():
        temp_request.unlink()
    
    return result.returncode

if __name__ == "__main__":
    sys.exit(main())
