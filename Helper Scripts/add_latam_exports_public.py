#!/usr/bin/env python3
"""
Add public read access to s3://latam-ai.filmmaker/LATAM/ prefixes
without removing existing bucket policy statements.

Prefixes:
  - LATAM/Outputs/     (source clips for RunPod download)
  - LATAM/LATAM_Exports/  (edited outputs)

Requires: boto3, AWS credentials (.env, aws configure, or env vars)
"""
import argparse
import json
import os
import sys

try:
    import boto3
except ImportError:
    print("Install boto3: pip install boto3")
    sys.exit(1)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.dirname(BASE_DIR)

BUCKET = "latam-ai.filmmaker"

# Both prefixes need public read: Outputs for RunPod downloads, Exports for final videos
PUBLIC_PREFIXES = [
    ("LATAM/Outputs/", "PublicReadLATAMOutputs"),
    ("LATAM/LATAM_Exports/", "PublicReadLATAMExports"),
]


def load_env_from_dotenv() -> None:
    """Load .env into os.environ (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, etc.)."""
    candidates = [
        os.path.join(REPO_DIR, ".env"),
        os.path.join(os.path.dirname(REPO_DIR), ".env"),
        os.path.join(os.getcwd(), ".env"),
    ]
    for path in candidates:
        if not os.path.exists(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    key, value = line.split("=", 1)
                    key, value = key.strip(), value.strip().strip('"').strip("'")
                    if key and key not in os.environ:
                        os.environ[key] = value
        except OSError:
            pass
        break


def main():
    from botocore.exceptions import ClientError, NoCredentialsError

    load_env_from_dotenv()

    parser = argparse.ArgumentParser(description="Add public read to LATAM S3 prefixes")
    parser.add_argument("--outputs-only", action="store_true", help="Only add LATAM/Outputs/")
    parser.add_argument("--exports-only", action="store_true", help="Only add LATAM/LATAM_Exports/")
    args = parser.parse_args()

    if args.outputs_only:
        to_add = [(p, sid) for p, sid in PUBLIC_PREFIXES if "Outputs" in p]
    elif args.exports_only:
        to_add = [(p, sid) for p, sid in PUBLIC_PREFIXES if "Exports" in p]
    else:
        to_add = PUBLIC_PREFIXES

    s3 = boto3.client("s3")
    try:
        resp = s3.get_bucket_policy(Bucket=BUCKET)
        policy = json.loads(resp["Policy"])
    except (ClientError, NoCredentialsError) as e:
        if isinstance(e, NoCredentialsError):
            print("AWS credentials not found. Run: aws configure")
            print("Or set AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY")
            return 1
        if e.response["Error"]["Code"] == "NoSuchBucketPolicy":
            policy = {"Version": "2012-10-17", "Statement": []}
        else:
            raise

    statements = list(policy.get("Statement", []))
    existing_sids = {s.get("Sid") for s in statements if s.get("Sid")}
    added = []

    for prefix, sid in to_add:
        if sid in existing_sids:
            print(f"{sid} already in policy. Skipping {prefix}")
            continue
        statements.append({
            "Sid": sid,
            "Effect": "Allow",
            "Principal": "*",
            "Action": "s3:GetObject",
            "Resource": f"arn:aws:s3:::{BUCKET}/{prefix}*",
        })
        added.append(prefix)

    if not added:
        print("No new statements to add.")
        return 0

    policy["Statement"] = statements
    s3.put_bucket_policy(Bucket=BUCKET, Policy=json.dumps(policy, indent=2))
    for p in added:
        print(f"Added public read for s3://{BUCKET}/{p}*")
    print("Existing statements preserved.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
