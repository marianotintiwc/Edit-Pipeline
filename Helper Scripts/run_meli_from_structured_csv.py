#!/usr/bin/env python3
"""Submit MELI Edit Classic jobs for all rows in s3_assets_structured.csv."""
import csv
import copy
import json
import os
import requests
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.dirname(BASE_DIR)
CSV_PATH = os.path.join(REPO_DIR, "assets", "IGNOREASSETS", "s3_assets_structured.csv")
CASES_PATH = os.path.join(REPO_DIR, "presets", "meli_cases.json")


def load_env():
    for path in (
        os.path.join(REPO_DIR, ".env"),
        os.path.join(os.path.dirname(REPO_DIR), ".env"),
        os.path.join(os.getcwd(), ".env"),
    ):
        if not os.path.exists(path):
            continue
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))
        break


def main():
    load_env()
    api_key = os.environ.get("RUNPOD_API_KEY")
    endpoint_id = os.environ.get("RUNPOD_ENDPOINT_ID", "h55ft9cy7fyi1d")
    if not api_key:
        raise SystemExit("RUNPOD_API_KEY not set")

    with open(CASES_PATH, "r", encoding="utf-8") as f:
        cases = json.load(f)
    base_style = cases.get("base_style", {})
    default_introcard_url = cases.get("introcard_url", "")

    base_url = f"https://api.runpod.ai/v2/{endpoint_id}/run"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    submitted = 0
    errors = []
    
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    
    total = len(rows)
    print(f"Found {total} rows to process")
    
    for i, row in enumerate(rows, 1):
        parent = row["Parent Folder"].strip()
        ptype = row["Type"].strip()
        geo = row["GEO"].strip()
        scene1 = row["Scene1_URL"].strip()
        scene2 = row["Scene2_URL"].strip()
        scene3 = row["Scene3_URL"].strip()
        introcard_url = (row.get("Introcard_S3_URL") or "").strip() or default_introcard_url
        broll_url = row["Broll_S3_URL"].strip()
        endcard_url = row["Endcard_S3_URL"].strip()

        style = copy.deepcopy(base_style)
        if endcard_url:
            style.setdefault("endcard", {})
            style["endcard"]["url"] = endcard_url

        clips = []
        if introcard_url:
            clips.append({"type": "introcard", "url": introcard_url})
        clips.extend(
            [
                {"type": "scene", "url": scene1},
                {"type": "scene", "url": scene2},
                {"type": "broll", "url": broll_url},
                {"type": "scene", "url": scene3},
            ]
        )
        if endcard_url:
            clips.append({"type": "endcard", "url": endcard_url})

        payload = {
            "input": {
                "job_id": f"meli_{parent}",
                "geo": geo,
                "output_folder": "MELI_Exports/2026-02",
                "output_filename": f"{parent}_MELI_EDIT.mp4",
                "clips": clips,
                "music_url": "random",
                "subtitle_mode": "auto",
                "edit_preset": "standard_vertical",
                "style_overrides": style,
            }
        }

        try:
            r = requests.post(base_url, headers=headers, json=payload, timeout=60)
            r.raise_for_status()
            data = r.json()
            run_id = data.get("id")
            print(f"[{i}/{total}] {parent} ({ptype}/{geo}): submitted {run_id}")
            submitted += 1
        except Exception as e:
            print(f"[{i}/{total}] {parent} ({ptype}/{geo}): ERROR - {e}")
            errors.append((parent, str(e)))
        
        # Small delay to avoid rate limiting
        if i % 10 == 0:
            time.sleep(0.5)

    print(f"\n=== Summary ===")
    print(f"Submitted: {submitted}/{total} jobs")
    if errors:
        print(f"Errors: {len(errors)}")
        for parent, err in errors:
            print(f"  - {parent}: {err}")


if __name__ == "__main__":
    main()
