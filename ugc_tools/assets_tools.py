from __future__ import annotations

import argparse
import csv
import os
import re
from pathlib import Path
from typing import Iterable
from urllib.parse import quote

import boto3
import requests

from .env import load_env_default
from .paths import repo_root


DEFAULT_TMP_DIR = "assets/IGNOREASSETS/users_assets_upload_tmp"
DEFAULT_REPORT = "assets/IGNOREASSETS/users_assets_upload_report.csv"
DEFAULT_COLUMNS = "Broll,Endcard,BRoll"
DEFAULT_S3_BUCKET = "meli-ai.filmmaker"
DEFAULT_S3_PREFIX = "MP-Users/Assets"
DEFAULT_S3_REGION = "us-east-2"


def register_cli(subparsers: argparse._SubParsersAction) -> None:
    assets_parser = subparsers.add_parser("assets", help="Drive/S3 asset workflows")
    assets_sub = assets_parser.add_subparsers(dest="command", required=True)

    upload = assets_sub.add_parser("upload-drive", help="Download Drive assets and upload to S3")
    upload.add_argument("--csv", required=True, help="Input CSV with Drive URLs")
    upload.add_argument("--columns", default=DEFAULT_COLUMNS, help="Comma-separated columns to scan")
    upload.add_argument("--tmp-dir", default=DEFAULT_TMP_DIR, help="Temporary download dir")
    upload.add_argument("--report", default=DEFAULT_REPORT, help="Report CSV output")
    upload.add_argument("--bucket", default=DEFAULT_S3_BUCKET, help="S3 bucket name")
    upload.add_argument("--prefix", default=DEFAULT_S3_PREFIX, help="S3 key prefix")
    upload.add_argument("--region", default=DEFAULT_S3_REGION, help="S3 region")
    upload.add_argument("--skip-existing", action="store_true", help="Skip upload if object exists")
    upload.set_defaults(func=cmd_upload_drive)

    replace = assets_sub.add_parser("replace-urls", help="Replace Drive URLs with S3 URLs")
    replace.add_argument("--input", required=True, help="Input CSV")
    replace.add_argument("--output", required=True, help="Output CSV")
    replace.add_argument("--report", default=DEFAULT_REPORT, help="Upload report CSV")
    replace.add_argument("--columns", default=DEFAULT_COLUMNS, help="Comma-separated columns to replace")
    replace.set_defaults(func=cmd_replace_urls)


def cmd_upload_drive(args: argparse.Namespace) -> int:
    repo_dir = repo_root()
    load_env_default(repo_dir)

    input_csv = resolve_path(args.csv, repo_dir)
    tmp_dir = resolve_path(args.tmp_dir, repo_dir)
    report_path = resolve_path(args.report, repo_dir)

    if not input_csv.exists():
        raise SystemExit(f"CSV not found: {input_csv}")

    tmp_dir.mkdir(parents=True, exist_ok=True)
    for part_file in tmp_dir.glob("*.part"):
        part_file.unlink(missing_ok=True)

    columns = [c.strip() for c in args.columns.split(",") if c.strip()]
    items = list(iter_drive_items(input_csv, columns))
    print(f"Found {len(items)} unique Drive files")

    s3 = boto3.client(
        "s3",
        region_name=args.region,
        aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
    )

    report_rows: list[dict[str, str]] = []
    for idx, item in enumerate(items, 1):
        drive_id = item["drive_id"]
        kind = item["kind"]
        url = item["source_url"]
        print(f"[{idx}/{len(items)}] Downloading {kind} {drive_id}...")

        try:
            downloaded_path = download_drive_file(drive_id, tmp_dir)
        except Exception as e:
            report_rows.append(
                {
                    "kind": kind,
                    "drive_id": drive_id,
                    "source_url": url,
                    "filename": "",
                    "s3_key": "",
                    "s3_url": "",
                    "status": f"download_error: {e}",
                }
            )
            continue

        filename = downloaded_path.name
        s3_key = f"{args.prefix}/{filename}"
        s3_url = s3_http_url(args.bucket, args.region, s3_key)

        status = "uploaded"
        if args.skip_existing and s3_exists(s3, args.bucket, s3_key):
            status = "already_exists"
        else:
            try:
                s3_upload(s3, args.bucket, s3_key, downloaded_path)
            except Exception as e:
                status = f"upload_error: {e}"

        report_rows.append(
            {
                "kind": kind,
                "drive_id": drive_id,
                "source_url": url,
                "filename": filename,
                "s3_key": s3_key,
                "s3_url": s3_url,
                "status": status,
            }
        )

    report_path.parent.mkdir(parents=True, exist_ok=True)
    with report_path.open("w", newline="", encoding="utf-8") as f:
        fieldnames = ["kind", "drive_id", "source_url", "filename", "s3_key", "s3_url", "status"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(report_rows)

    uploaded = sum(1 for r in report_rows if r["status"] == "uploaded")
    exists = sum(1 for r in report_rows if r["status"] == "already_exists")
    errors = [r for r in report_rows if "error" in r["status"] or r["status"] == "download_failed"]
    print(f"Report saved: {report_path}")
    print(f"Uploaded: {uploaded}, Already existed: {exists}, Errors: {len(errors)}")
    return 0


def cmd_replace_urls(args: argparse.Namespace) -> int:
    repo_dir = repo_root()
    report_path = resolve_path(args.report, repo_dir)
    input_csv = resolve_path(args.input, repo_dir)
    output_csv = resolve_path(args.output, repo_dir)

    if not report_path.exists():
        raise SystemExit(f"Report not found: {report_path}")
    if not input_csv.exists():
        raise SystemExit(f"CSV not found: {input_csv}")

    columns = [c.strip() for c in args.columns.split(",") if c.strip()]
    lookup = load_upload_report(report_path)

    replaced = 0
    missing = 0

    with input_csv.open(newline="", encoding="utf-8") as f_in, output_csv.open(
        "w", newline="", encoding="utf-8"
    ) as f_out:
        reader = csv.DictReader(f_in)
        fieldnames = reader.fieldnames or []
        writer = csv.DictWriter(f_out, fieldnames=fieldnames)
        writer.writeheader()
        for row in reader:
            for col in columns:
                url = (row.get(col) or "").strip()
                drive_id = extract_drive_id(url)
                if drive_id and drive_id in lookup:
                    row[col] = lookup[drive_id]
                    replaced += 1
                elif drive_id:
                    missing += 1
            writer.writerow(row)

    print(f"Wrote: {output_csv}")
    print(f"Replaced: {replaced}, Missing: {missing}")
    return 0


def resolve_path(value: str, repo_dir: Path) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = repo_dir / path
    return path


def extract_drive_id(url: str) -> str | None:
    if not url or not url.startswith("http"):
        return None
    match = re.search(r"/d/([a-zA-Z0-9_-]+)", url)
    if match:
        return match.group(1)
    match = re.search(r"[?&]id=([a-zA-Z0-9_-]+)", url)
    if match:
        return match.group(1)
    return None


def iter_drive_items(csv_path: Path, columns: list[str]) -> Iterable[dict[str, str]]:
    seen: set[str] = set()
    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            for kind in columns:
                url = (row.get(kind) or "").strip()
                drive_id = extract_drive_id(url)
                if not drive_id or drive_id in seen:
                    continue
                seen.add(drive_id)
                yield {"kind": kind, "drive_id": drive_id, "source_url": url}


def download_drive_file(drive_id: str, dest_dir: Path) -> Path:
    try:
        import gdown

        current_dir = Path.cwd()
        try:
            os.chdir(dest_dir)
            downloaded = gdown.download(id=drive_id, output=None, quiet=False)
        finally:
            os.chdir(current_dir)

        if not downloaded:
            raise RuntimeError("Download failed: empty path")
        downloaded_path = Path(downloaded)
        if not downloaded_path.is_absolute():
            downloaded_path = dest_dir / downloaded_path
        if not downloaded_path.exists():
            raise RuntimeError("Download failed: file missing")
        return downloaded_path
    except Exception:
        return download_drive_file_fallback(drive_id, dest_dir)


def download_drive_file_fallback(drive_id: str, dest_dir: Path) -> Path:
    url = f"https://drive.google.com/uc?export=download&id={drive_id}"
    session = requests.Session()
    response = session.get(url, stream=True, allow_redirects=True, timeout=60)
    if "text/html" in response.headers.get("Content-Type", ""):
        for key, value in response.cookies.items():
            if key.startswith("download_warning"):
                url = f"https://drive.google.com/uc?export=download&confirm={value}&id={drive_id}"
                response = session.get(url, stream=True, allow_redirects=True, timeout=60)
                break
    response.raise_for_status()
    filename = extract_filename(response, drive_id)
    dest_path = dest_dir / filename
    with dest_path.open("wb") as f:
        for chunk in response.iter_content(chunk_size=1024 * 1024):
            if chunk:
                f.write(chunk)
    if dest_path.stat().st_size == 0:
        dest_path.unlink(missing_ok=True)
        raise RuntimeError("Download failed: empty file")
    return dest_path


def extract_filename(response: requests.Response, fallback_id: str) -> str:
    content_disp = response.headers.get("Content-Disposition", "")
    if content_disp:
        match = re.search(r"filename\*=UTF-8''([^;]+)", content_disp)
        if match:
            return requests.utils.unquote(match.group(1))
        match = re.search(r"filename=\"([^\"]+)\"", content_disp)
        if match:
            return match.group(1)
        match = re.search(r"filename=([^;]+)", content_disp)
        if match:
            return match.group(1).strip().strip('"')
    content_type = response.headers.get("Content-Type", "")
    if "mp4" in content_type:
        return f"{fallback_id}.mp4"
    return f"{fallback_id}.mov"


def s3_http_url(bucket: str, region: str, key: str) -> str:
    return f"https://s3.{region}.amazonaws.com/{bucket}/{quote(key, safe='/')}"


def s3_exists(s3, bucket: str, key: str) -> bool:
    try:
        s3.head_object(Bucket=bucket, Key=key)
        return True
    except Exception:
        return False


def s3_upload(s3, bucket: str, key: str, local_path: Path) -> None:
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


def load_upload_report(report_path: Path) -> dict[str, str]:
    lookup = {}
    with report_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            drive_id = (row.get("drive_id") or "").strip()
            s3_url = (row.get("s3_url") or "").strip()
            status = (row.get("status") or "").strip()
            if drive_id and s3_url and status in {"uploaded", "already_exists"}:
                lookup[drive_id] = s3_url
    return lookup


