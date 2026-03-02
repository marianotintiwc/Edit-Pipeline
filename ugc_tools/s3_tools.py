from __future__ import annotations

import argparse
import csv
import json
import os
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

import boto3

from .env import load_env_default
from .paths import repo_root


DEFAULT_BUCKET = "meli-ai.filmmaker"
DEFAULT_PREFIX = "MP-Users/Assets"
DEFAULT_REGION = "us-east-2"


def register_cli(subparsers: argparse._SubParsersAction) -> None:
    s3_parser = subparsers.add_parser("s3", help="S3 utilities")
    s3_sub = s3_parser.add_subparsers(dest="command", required=True)

    rename = s3_sub.add_parser("rename", help="Rename S3 objects from a plan or map")
    rename.add_argument("--map", default=None, help="JSON map of old_name -> new_name")
    rename.add_argument("--plan", default=None, help="Rename plan JSON output/input")
    rename.add_argument("--apply", action="store_true", help="Apply rename plan")
    rename.add_argument("--bucket", default=DEFAULT_BUCKET, help="S3 bucket")
    rename.add_argument("--prefix", default=DEFAULT_PREFIX, help="S3 prefix")
    rename.add_argument("--region", default=DEFAULT_REGION, help="AWS region")
    rename.add_argument("--update-csv", default=None, help="CSV to update URLs")
    rename.add_argument("--csv-column", default="ENDCARD S3", help="CSV column to update")
    rename.add_argument("--csv-output", default=None, help="CSV output path")
    rename.set_defaults(func=cmd_rename)

    upload = s3_sub.add_parser("upload-folder", help="Upload local folder to S3")
    upload.add_argument("--folder", required=True, help="Local folder path")
    upload.add_argument("--bucket", default=DEFAULT_BUCKET, help="S3 bucket")
    upload.add_argument("--prefix", default=DEFAULT_PREFIX, help="S3 prefix")
    upload.add_argument("--region", default=DEFAULT_REGION, help="AWS region")
    upload.add_argument("--extensions", default=".mov,.mp4", help="File extensions to upload")
    upload.add_argument("--recursive", action="store_true", help="Recurse into subfolders")
    upload.add_argument("--overwrite", action="store_true", help="Overwrite existing objects")
    upload.add_argument("--dry-run", action="store_true", help="Print actions only")
    upload.set_defaults(func=cmd_upload_folder)


def cmd_rename(args: argparse.Namespace) -> int:
    repo_dir = repo_root()
    load_env_default(repo_dir)

    plan_path = resolve_plan_path(args.plan, repo_dir)
    if args.map:
        mapping = load_rename_map(resolve_path(args.map, repo_dir))
        plan = build_rename_plan(mapping, args.bucket, args.prefix)
        write_plan(plan_path, plan)
        print(f"Wrote plan: {plan_path}")
    else:
        plan = read_plan(plan_path)

    if args.apply:
        s3 = boto3.client(
            "s3",
            region_name=args.region,
            aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
        )
        apply_plan(s3, plan)
        print("Rename plan applied.")

    if args.update_csv:
        csv_path = resolve_path(args.update_csv, repo_dir)
        csv_output = resolve_csv_output(args.csv_output, csv_path)
        update_csv_urls(csv_path, csv_output, plan, args.bucket, args.region, args.prefix, args.csv_column)
        print(f"Updated CSV: {csv_output}")

    return 0


def cmd_upload_folder(args: argparse.Namespace) -> int:
    repo_dir = repo_root()
    load_env_default(repo_dir)

    folder = resolve_path(args.folder, repo_dir)
    if not folder.exists():
        raise SystemExit(f"Folder not found: {folder}")

    extensions = {ext.strip().lower() for ext in args.extensions.split(",") if ext.strip()}
    files = list(iter_files(folder, args.recursive, extensions))
    print(f"Found {len(files)} files to upload")

    if args.dry_run:
        for path in files:
            print(f"DRY-RUN: {path}")
        return 0

    s3 = boto3.client(
        "s3",
        region_name=args.region,
        aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
    )

    for path in files:
        key = f"{args.prefix}/{path.name}"
        if not args.overwrite and s3_exists(s3, args.bucket, key):
            print(f"Skip existing: {path.name}")
            continue
        upload_file(s3, args.bucket, key, path)
        print(f"Uploaded: {path.name}")

    return 0


def resolve_path(value: str, repo_dir: Path) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = repo_dir / path
    return path


def resolve_plan_path(value: str | None, repo_dir: Path) -> Path:
    if value:
        return resolve_path(value, repo_dir)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return repo_dir / f"s3_rename_plan_{timestamp}.json"


def resolve_csv_output(value: str | None, csv_path: Path) -> Path:
    if value:
        return Path(value) if Path(value).is_absolute() else csv_path.parent / value
    return csv_path.with_suffix(".updated.csv")


def load_rename_map(path: Path) -> dict[str, str]:
    if not path.exists():
        raise SystemExit(f"Map not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        return {str(k): str(v) for k, v in data.items()}
    raise SystemExit("Rename map must be a JSON object of old_name -> new_name")


def build_rename_plan(mapping: dict[str, str], bucket: str, prefix: str) -> dict:
    items = []
    for old_name, new_name in mapping.items():
        items.append(
            {
                "old_key": f"{prefix}/{old_name}",
                "new_key": f"{prefix}/{new_name}",
            }
        )
    return {"bucket": bucket, "prefix": prefix, "items": items}


def write_plan(path: Path, plan: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(plan, indent=2), encoding="utf-8")


def read_plan(path: Path) -> dict:
    if not path.exists():
        raise SystemExit(f"Plan not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def apply_plan(s3, plan: dict) -> None:
    bucket = plan.get("bucket")
    for item in plan.get("items", []):
        old_key = item["old_key"]
        new_key = item["new_key"]
        try:
            s3.copy_object(
                Bucket=bucket,
                CopySource={"Bucket": bucket, "Key": old_key},
                Key=new_key,
            )
            s3.delete_object(Bucket=bucket, Key=old_key)
        except Exception as e:
            print(f"Rename failed: {old_key} -> {new_key} ({e})")


def update_csv_urls(
    csv_path: Path,
    output_path: Path,
    plan: dict,
    bucket: str,
    region: str,
    prefix: str,
    column: str,
) -> None:
    items = plan.get("items", [])
    mapping = {item["old_key"].split("/", 1)[1]: item["new_key"].split("/", 1)[1] for item in items}

    with csv_path.open("r", encoding="utf-8", newline="") as f_in:
        reader = csv.DictReader(f_in)
        fieldnames = reader.fieldnames or []
        rows = list(reader)

    updated = 0
    for row in rows:
        url = row.get(column, "")
        for old_name, new_name in mapping.items():
            if old_name in url or quote(old_name) in url:
                new_url = s3_http_url(bucket, region, f"{prefix}/{new_name}")
                row[column] = new_url
                updated += 1
                break

    with output_path.open("w", encoding="utf-8", newline="") as f_out:
        writer = csv.DictWriter(f_out, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"Updated {updated} rows in CSV")


def iter_files(folder: Path, recursive: bool, extensions: set[str]):
    if recursive:
        for path in folder.rglob("*"):
            if path.is_file() and path.suffix.lower() in extensions:
                yield path
    else:
        for path in folder.iterdir():
            if path.is_file() and path.suffix.lower() in extensions:
                yield path


def s3_exists(s3, bucket: str, key: str) -> bool:
    try:
        s3.head_object(Bucket=bucket, Key=key)
        return True
    except Exception:
        return False


def upload_file(s3, bucket: str, key: str, local_path: Path) -> None:
    if local_path.suffix.lower() == ".mov":
        content_type = "video/quicktime"
    elif local_path.suffix.lower() == ".mp4":
        content_type = "video/mp4"
    else:
        content_type = "application/octet-stream"
    s3.upload_file(
        str(local_path),
        bucket,
        key,
        ExtraArgs={"ContentType": content_type},
    )


def s3_http_url(bucket: str, region: str, key: str) -> str:
    return f"https://s3.{region}.amazonaws.com/{bucket}/{quote(key, safe='/')}"


