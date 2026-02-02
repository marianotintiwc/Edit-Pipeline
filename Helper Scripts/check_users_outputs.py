#!/usr/bin/env python3
"""Check missing outputs in S3 for user jobs."""
import csv
import re
import subprocess
from pathlib import Path

CSV_PATH = Path("USERS FILES FOR EDIT, MLA APPROVED.s3.csv")
OUTPUT_PREFIX = "s3://meli-ai.filmmaker/MP-Users/Outputs 02-2026/"


def list_existing() -> set[str]:
    result = subprocess.run(
        ["aws", "s3", "ls", OUTPUT_PREFIX],
        capture_output=True,
        text=True,
        check=True,
    )
    existing = set()
    for line in result.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 4:
            key = parts[3]
            if key.endswith("_MELI_EDIT.mp4"):
                existing.add(key)
    return existing


def expected_outputs() -> list[str]:
    expected = []
    with CSV_PATH.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            scene1 = (row.get("scene_1_lipsync") or "").strip()
            m = re.search(r"/([^/]+)/[^/]+_scene_1_lipsync\.mp4", scene1)
            parent = m.group(1) if m else "UNKNOWN"
            expected.append(f"{parent}_MELI_EDIT.mp4")
    return expected


def main() -> None:
    existing = list_existing()
    expected = expected_outputs()
    missing = [name for name in expected if name not in existing]

    print(f"Expected: {len(expected)}")
    print(f"Existing: {len(existing)}")
    print(f"Missing: {len(missing)}")
    print("\nMissing outputs:")
    for name in missing:
        print(name)


if __name__ == "__main__":
    main()
