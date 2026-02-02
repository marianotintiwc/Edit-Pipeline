#!/usr/bin/env python3
"""Replace Google Drive Broll/Endcard URLs with S3 URLs using the upload report."""
import csv
import re
from pathlib import Path

REPORT = Path("assets/IGNOREASSETS/users_assets_upload_report.csv")
CSV_IN = Path("USERS FILES FOR EDIT, MLA APPROVED.csv")
CSV_OUT = Path("USERS FILES FOR EDIT, MLA APPROVED.s3.csv")


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


lookup = {}
with REPORT.open(newline="", encoding="utf-8") as f:
    reader = csv.DictReader(f)
    for row in reader:
        drive_id = row["drive_id"].strip()
        s3_url = row["s3_url"].strip()
        status = row["status"].strip()
        if drive_id and s3_url and status in {"uploaded", "already_exists"}:
            lookup[drive_id] = s3_url

replaced = 0
missing = 0

with CSV_IN.open(newline="", encoding="utf-8") as f_in, CSV_OUT.open("w", newline="", encoding="utf-8") as f_out:
    reader = csv.DictReader(f_in)
    fieldnames = reader.fieldnames
    writer = csv.DictWriter(f_out, fieldnames=fieldnames)
    writer.writeheader()
    for row in reader:
        for col in ("Broll", "Endcard"):
            url = (row.get(col) or "").strip()
            drive_id = extract_drive_id(url)
            if drive_id and drive_id in lookup:
                row[col] = lookup[drive_id]
                replaced += 1
            elif drive_id:
                missing += 1
        writer.writerow(row)

print(f"Wrote: {CSV_OUT}")
print(f"Replaced: {replaced}, Missing: {missing}")
