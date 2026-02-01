#!/usr/bin/env python3
"""
Submit MELI EDIT CLASSIC-style jobs to RunPod for all rows
in assets/IGNOREASSETS/unified_parent_asset_mapping.csv.

- Uses introcard per row if Introcard_S3_URL is set
  otherwise falls back to presets/meli_cases.json introcard_url.
- Uses per-row B-roll and Endcard S3 URLs from the CSV.
- Applies MELI base_style from presets/meli_cases.json.
"""

import csv
import copy
import json
import os
import sys
from typing import Dict, Any

import requests


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.dirname(BASE_DIR)
CSV_PATH = os.path.join(REPO_DIR, "assets", "IGNOREASSETS", "unified_parent_asset_mapping.csv")
CASES_PATH = os.path.join(REPO_DIR, "presets", "meli_cases.json")
LOG_PATH = os.path.join(REPO_DIR, "meli_from_csv.log")


def load_env_from_dotenv() -> None:
    """Best-effort load of RUNPOD_* vars from nearby .env files."""
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
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    if key and key not in os.environ:
                        os.environ[key] = value
        except OSError:
            pass
        # Stop at first .env we successfully read
        break


def log(message: str) -> None:
    """Log to stdout and to a local file for inspection."""
    text = str(message)
    print(text)
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as lf:
            lf.write(text + "\n")
    except OSError:
        pass


def build_payload(
    row: Dict[str, str],
    base_style: Dict[str, Any],
    default_introcard_url: str,
    output_folder: str,
) -> Dict[str, Any]:
    parent = row["Parent Folder"].strip()
    geo = row["GEO"].strip()
    scene1 = (row.get("Scene1_URL") or "").strip()
    scene2 = (row.get("Scene2_URL") or "").strip()
    scene3 = (row.get("Scene3_URL") or "").strip()
    broll_url = (row.get("Broll_S3_URL") or "").strip()
    endcard_url = (row.get("Endcard_S3_URL") or "").strip()
    introcard_url = (row.get("Introcard_S3_URL") or "").strip() or default_introcard_url

    if not (scene1 and scene2 and scene3):
        raise ValueError(f"{parent}: missing one or more scene URLs")
    if not broll_url:
        raise ValueError(f"{parent}: missing B-roll S3 URL")

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

    output_filename = f"{parent}_MELI_EDIT.mp4"

    return {
        "input": {
            "job_id": f"meli_{parent}",
            "geo": geo,
            "output_folder": output_folder,
            "output_filename": output_filename,
            "clips": clips,
            "music_url": "random",
            "subtitle_mode": "auto",
            # MELI classic uses standard_vertical preset with MELI style_overrides
            "edit_preset": "standard_vertical",
            "style_overrides": style,
        }
    }


def main() -> None:
    if not os.path.exists(CSV_PATH):
        raise SystemExit(f"CSV not found: {CSV_PATH}")
    if not os.path.exists(CASES_PATH):
        raise SystemExit(f"Cases config not found: {CASES_PATH}")

    load_env_from_dotenv()

    api_key = os.environ.get("RUNPOD_API_KEY")
    endpoint_id = os.environ.get("RUNPOD_ENDPOINT_ID", "3zysuiunu9iacy")
    if not api_key:
        raise SystemExit("RUNPOD_API_KEY not set; please export it or add it to a .env file")

    with open(CASES_PATH, "r", encoding="utf-8") as f:
        cases = json.load(f)
    base_style = cases.get("base_style", {})
    default_introcard_url = (cases.get("introcard_url") or "").strip()

    base_url = f"https://api.runpod.ai/v2/{endpoint_id}/run"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    output_folder = "MELI_Exports/2026-01"
    # Start fresh log
    try:
        if os.path.exists(LOG_PATH):
            os.remove(LOG_PATH)
    except OSError:
        pass

    log(f"Using endpoint {endpoint_id}")

    submitted = 0

    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            parent = row.get("Parent Folder", "").strip() or "UNKNOWN"
            try:
                payload = build_payload(row, base_style, default_introcard_url, output_folder)
            except ValueError as e:
                log(f"Skipping {parent}: {e}")
                continue

            try:
                r = requests.post(base_url, headers=headers, json=payload, timeout=60)
                r.raise_for_status()
                data = r.json()
            except Exception as e:
                log(f"{parent}: ERROR submitting job: {e}")
                continue

            run_id = data.get("id")
            log(f"{parent}: submitted {run_id}")
            submitted += 1

    log(f"Submitted {submitted} jobs")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(1)
