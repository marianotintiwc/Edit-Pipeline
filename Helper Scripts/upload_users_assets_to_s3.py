#!/usr/bin/env python3
"""Upload Google Drive b-roll and endcards from the users CSV to S3."""

from __future__ import annotations

import csv
import os
import re
import subprocess
from pathlib import Path
from typing import Iterable

import gdown

CSV_PATH = Path(
    "/Users/marianotinti/Desktop/UGC EDITOR/Edit-Pipeline/USERS FILES FOR EDIT, MLA APPROVED.csv"
)
TMP_DIR = Path(
    "/Users/marianotinti/Desktop/UGC EDITOR/Edit-Pipeline/assets/IGNOREASSETS/users_assets_upload_tmp"
)
REPORT_PATH = Path(
    "/Users/marianotinti/Desktop/UGC EDITOR/Edit-Pipeline/assets/IGNOREASSETS/users_assets_upload_report.csv"
)
S3_BUCKET = "s3://meli-ai.filmmaker/MP-Users/Assets"
S3_HTTP_BASE = "https://s3.us-east-2.amazonaws.com/meli-ai.filmmaker/MP-Users/Assets"


def extract_drive_id(url: str) -> str | None:
    if not url or not url.startswith("http"):
        return None
    m = re.search(r"/d/([a-zA-Z0-9_-]+)", url)
    if m:
        return m.group(1)
    m = re.search(r"[?&]id=([a-zA-Z0-9_-]+)", url)
    if m:
        return m.group(1)
    return None


def s3_exists(key: str) -> bool:
    result = subprocess.run(
        ["aws", "s3", "ls", f"{S3_BUCKET}/{key}"],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0 and bool(result.stdout.strip())


def s3_upload(local_path: Path, key: str) -> None:
    subprocess.run([
        "aws",
        "s3",
        "cp",
        str(local_path),
        f"{S3_BUCKET}/{key}",
    ], check=True)


def iter_drive_items() -> Iterable[dict[str, str]]:
    seen: set[str] = set()
    with CSV_PATH.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            for kind in ("Broll", "Endcard"):
                url = (row.get(kind) or "").strip()
                drive_id = extract_drive_id(url)
                if not drive_id:
                    continue
                if drive_id in seen:
                    continue
                seen.add(drive_id)
                yield {"kind": kind, "drive_id": drive_id, "source_url": url}


def main() -> None:
    TMP_DIR.mkdir(parents=True, exist_ok=True)

    # Clean up any leftover partial downloads
    for part_file in TMP_DIR.glob("*.part"):
        part_file.unlink(missing_ok=True)

    items = list(iter_drive_items())
    print(f"Found {len(items)} unique Google Drive files")

    report_rows: list[dict[str, str]] = []

    for idx, item in enumerate(items, 1):
        drive_id = item["drive_id"]
        kind = item["kind"]
        url = item["source_url"]
        print(f"[{idx}/{len(items)}] Downloading {kind} {drive_id}...")

        try:
            # gdown preserves the original filename when output is None
            # so we temporarily change into TMP_DIR
            current_dir = Path.cwd()
            try:
                os.chdir(TMP_DIR)
                downloaded_path = gdown.download(id=drive_id, output=None, quiet=False)
            finally:
                os.chdir(current_dir)
        except Exception as e:
            report_rows.append({
                "kind": kind,
                "drive_id": drive_id,
                "source_url": url,
                "filename": "",
                "s3_key": "",
                "s3_url": "",
                "status": f"download_error: {e}",
            })
            continue

        if not downloaded_path:
            report_rows.append({
                "kind": kind,
                "drive_id": drive_id,
                "source_url": url,
                "filename": "",
                "s3_key": "",
                "s3_url": "",
                "status": "download_failed",
            })
            continue

        downloaded_path = Path(downloaded_path)
        if not downloaded_path.is_absolute():
            candidate = TMP_DIR / downloaded_path
            if candidate.exists():
                downloaded_path = candidate
        if not downloaded_path.exists():
            report_rows.append({
                "kind": kind,
                "drive_id": drive_id,
                "source_url": url,
                "filename": "",
                "s3_key": "",
                "s3_url": "",
                "status": "download_path_missing",
            })
            continue
        filename = downloaded_path.name
        s3_key = filename
        s3_url = f"{S3_HTTP_BASE}/{filename}"

        if s3_exists(s3_key):
            status = "already_exists"
        else:
            try:
                s3_upload(downloaded_path, s3_key)
                status = "uploaded"
            except Exception as e:
                status = f"upload_error: {e}"

        report_rows.append({
            "kind": kind,
            "drive_id": drive_id,
            "source_url": url,
            "filename": filename,
            "s3_key": s3_key,
            "s3_url": s3_url,
            "status": status,
        })

    with REPORT_PATH.open("w", newline="", encoding="utf-8") as f:
        fieldnames = ["kind", "drive_id", "source_url", "filename", "s3_key", "s3_url", "status"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(report_rows)

    uploaded = sum(1 for r in report_rows if r["status"] == "uploaded")
    exists = sum(1 for r in report_rows if r["status"] == "already_exists")
    errors = [r for r in report_rows if "error" in r["status"] or r["status"] == "download_failed"]

    print(f"Report saved: {REPORT_PATH}")
    print(f"Uploaded: {uploaded}, Already existed: {exists}, Errors: {len(errors)}")


if __name__ == "__main__":
    main()
