#!/usr/bin/env python3
"""Submit MELI EDIT CLASSIC jobs from USER for Edit - MLC_Approved.csv."""
import csv
import copy
import json
import os
import re
import sys
from typing import Dict, Any
from urllib.parse import quote

import requests

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.dirname(BASE_DIR)
CSV_PATH = os.path.join(os.path.dirname(REPO_DIR), "USER for Edit - MLC_Approved.csv")
CASES_PATH = os.path.join(REPO_DIR, "presets", "meli_cases.json")
LOG_PATH = os.path.join(REPO_DIR, "users_mlc_meli_from_csv.log")


def load_env_from_dotenv() -> None:
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
        break


def log(message: str) -> None:
    text = str(message)
    print(text)
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as lf:
            lf.write(text + "\n")
    except OSError:
        pass


def parse_parent_from_scene_url(url: str) -> str:
    if not url:
        return "UNKNOWN"
    m = re.search(r"/([^/]+)/[^/]+_scene_1_lipsync\.mp4", url)
    if m:
        return m.group(1)
    m = re.search(r"/([^/]+)/[^/]+\.mp4", url)
    if m:
        return m.group(1)
    return "UNKNOWN"


def _normalize_url(url: str) -> str:
    """Convert s3:// URLs to https:// and properly encode special characters."""
    url = (url or "").strip()
    if url.startswith("s3://"):
        # Convert s3://bucket/key to https://s3.us-east-2.amazonaws.com/bucket/key
        without_scheme = url[len("s3://"):]
        if "/" in without_scheme:
            bucket, key = without_scheme.split("/", 1)
            # URL-encode the key (preserve slashes), keep original unicode encoding
            encoded_key = quote(key, safe="/")
            return f"https://s3.us-east-2.amazonaws.com/{bucket}/{encoded_key}"
    elif url.startswith("https://") or url.startswith("http://"):
        # URL-encode spaces in existing HTTP/HTTPS URLs if needed
        if " " in url:
            # Split scheme://host/path and encode only the path
            scheme_end = url.find("://") + 3
            rest = url[scheme_end:]
            if "/" in rest:
                host, path = rest.split("/", 1)
                # Keep original unicode encoding to match S3 keys
                encoded_path = quote(path, safe="/")
                return url[:scheme_end] + host + "/" + encoded_path
    return url


def build_payload(
    row: Dict[str, str],
    base_style: Dict[str, Any],
    default_introcard_url: str,
    output_folder: str,
) -> Dict[str, Any]:
    geo = (row.get("GEO") or "").strip()
    scene1 = (row.get("scene_1_lipsync") or "").strip()
    scene2 = (row.get("scene_2_lipsync") or "").strip()
    scene3 = (row.get("scene_3_lipsync") or "").strip()
    
    # For MLC CSV, columns are "BROLL S3" and "ENDCARD S3"
    broll_url = _normalize_url(row.get("BROLL S3") or row.get("BROLL S3 URL") or row.get("Broll") or "")
    endcard_url = _normalize_url(row.get("ENDCARD S3") or row.get("ENDCARD S3 URL") or row.get("Endcard") or "")

    if not (scene1 and scene2 and scene3):
        raise ValueError("missing one or more scene URLs")
    if not broll_url:
        raise ValueError("missing B-roll URL")
    if not endcard_url:
        raise ValueError("missing Endcard URL")

    parent = parse_parent_from_scene_url(scene1)

    style = copy.deepcopy(base_style)
    style.setdefault("endcard", {})
    style["endcard"]["url"] = endcard_url

    clips = []
    if default_introcard_url:
        clips.append({"type": "introcard", "url": default_introcard_url})
    clips.extend(
        [
            {"type": "scene", "url": scene1},
            {"type": "scene", "url": scene2},
            {"type": "broll", "url": broll_url},
            {"type": "scene", "url": scene3},
            {"type": "endcard", "url": endcard_url},
        ]
    )

    output_filename = f"{parent}_MELI_EDIT.mp4"

    return {
        "input": {
            "job_id": f"meli_user_{parent}",
            "geo": geo,
            "output_folder": output_folder,
            "output_filename": output_filename,
            "clips": clips,
            "music_url": "random",
            "subtitle_mode": "auto",
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
    endpoint_id = os.environ.get("RUNPOD_ENDPOINT_ID", "h55ft9cy7fyi1d")
    if not api_key:
        raise SystemExit("RUNPOD_API_KEY not set; please export it or add it to a .env file")

    with open(CASES_PATH, "r", encoding="utf-8") as f:
        cases = json.load(f)
    base_style = cases.get("base_style", {})
    default_introcard_url = (cases.get("introcard_url") or "").strip()

    base_url = f"https://api.runpod.ai/v2/{endpoint_id}/run"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    # MLC outputs go to a specific folder
    output_folder = "MP-Users/MLC_Outputs"

    try:
        if os.path.exists(LOG_PATH):
            os.remove(LOG_PATH)
    except OSError:
        pass

    log(f"Using endpoint {endpoint_id}")
    log(f"Reading from: {CSV_PATH}")
    log(f"Output folder: {output_folder}")
    log("")

    submitted = 0
    total = 0

    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        log(f"CSV columns: {reader.fieldnames}")
        log("")
        
        for row in reader:
            total += 1
            parent = parse_parent_from_scene_url((row.get("scene_1_lipsync") or "").strip())
            try:
                payload = build_payload(row, base_style, default_introcard_url, output_folder)
            except ValueError as e:
                log(f"Skipping {parent}: {e}")
                continue

            # Log the URLs being used
            broll_url = payload["input"]["clips"][3]["url"]  # broll is at index 3
            endcard_url = payload["input"]["clips"][5]["url"]  # endcard is at index 5
            log(f"Row {total}: {parent}")
            log(f"  Broll: {broll_url}")
            log(f"  Endcard: {endcard_url}")

            try:
                r = requests.post(base_url, headers=headers, json=payload, timeout=60)
                r.raise_for_status()
                data = r.json()
            except Exception as e:
                log(f"  ERROR submitting job: {e}")
                continue

            run_id = data.get("id")
            log(f"  -> submitted: {run_id}")
            submitted += 1

    log("")
    log(f"Submitted {submitted}/{total} jobs")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(1)
