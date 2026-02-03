#!/usr/bin/env python3
"""Submit MELI EDIT CLASSIC jobs for MLA + MLC + MLM CSVs into a single output folder."""
import csv
import copy
import json
import os
import re
import sys
import time
from typing import Dict, Any, Iterable, List, Optional
from urllib.parse import quote

import requests

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.dirname(BASE_DIR)
WORKSPACE_DIR = os.path.dirname(REPO_DIR)

CSV_SOURCES = [
    {
        "label": "MLA",
        "path": os.path.join(REPO_DIR, "USERS FILES FOR EDIT, MLA APPROVED.csv"),
    },
    {
        "label": "MLC",
        "path": os.path.join(WORKSPACE_DIR, "USER for Edit - MLC_Approved.csv"),
    },
    {
        "label": "MLM",
        "path": os.path.join(REPO_DIR, "Files for Edit - MLM_Approved.s3.csv"),
    },
]

CASES_PATH = os.path.join(REPO_DIR, "presets", "meli_cases.json")
LOG_PATH = os.path.join(REPO_DIR, "users_meli_reedit_feb_2026.log")

OUTPUT_FOLDER = "MP-Users/Outputs 02-2026"


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
    url = (url or "").strip()
    if url.startswith("s3://"):
        without_scheme = url[len("s3://"):]
        if "/" in without_scheme:
            bucket, key = without_scheme.split("/", 1)
            encoded_key = quote(key, safe="/")
            return f"https://s3.us-east-2.amazonaws.com/{bucket}/{encoded_key}"
    elif url.startswith("https://") or url.startswith("http://"):
        if " " in url:
            scheme_end = url.find("://") + 3
            rest = url[scheme_end:]
            if "/" in rest:
                host, path = rest.split("/", 1)
                encoded_path = quote(path, safe="/")
                return url[:scheme_end] + host + "/" + encoded_path
    return url


def _pick_first(row: Dict[str, str], keys: Iterable[str]) -> str:
    for key in keys:
        value = (row.get(key) or "").strip()
        if value:
            return value
    return ""


def build_payload(
    row: Dict[str, str],
    base_style: Dict[str, Any],
    default_introcard_url: str,
) -> Dict[str, Any]:
    geo = (row.get("GEO") or "").strip()
    scene1 = (row.get("scene_1_lipsync") or "").strip()
    scene2 = (row.get("scene_2_lipsync") or "").strip()
    scene3 = (row.get("scene_3_lipsync") or "").strip()

    broll_url = _normalize_url(
        _pick_first(row, ["BROLL S3", "BROLL S3 URL", "Broll", "BRoll"])
    )
    endcard_url = _normalize_url(
        _pick_first(row, ["ENDCARD S3", "ENDCARD S3 URL", "Endcard"])
    )

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

    clips: List[Dict[str, str]] = []
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
            "job_id": f"meli_user_{geo}_{parent}",
            "geo": geo,
            "output_folder": OUTPUT_FOLDER,
            "output_filename": output_filename,
            "clips": clips,
            "music_url": "random",
            "subtitle_mode": "auto",
            "edit_preset": "standard_vertical",
            "style_overrides": style,
        }
    }


def iter_csv_rows(csv_path: str) -> Iterable[Dict[str, str]]:
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            yield row


def main() -> None:
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

    try:
        if os.path.exists(LOG_PATH):
            os.remove(LOG_PATH)
    except OSError:
        pass

    log(f"Using endpoint {endpoint_id}")
    log(f"Output folder: {OUTPUT_FOLDER}")
    log("")

    submitted = 0
    total = 0

    for source in CSV_SOURCES:
        label = source["label"]
        path = source["path"]
        if not os.path.exists(path):
            log(f"Skipping {label}: CSV not found: {path}")
            continue

        log(f"Processing {label}: {path}")

        for row in iter_csv_rows(path):
            total += 1
            parent = parse_parent_from_scene_url((row.get("scene_1_lipsync") or "").strip())
            try:
                payload = build_payload(row, base_style, default_introcard_url)
            except ValueError as e:
                log(f"Skipping {label} {parent}: {e}")
                continue

            broll_url = payload["input"]["clips"][3]["url"]
            endcard_url = payload["input"]["clips"][5]["url"]
            log(f"{label} {parent}")
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

            if submitted % 10 == 0:
                time.sleep(0.5)

        log("")

    log(f"Submitted {submitted}/{total} jobs")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(1)
