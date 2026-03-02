#!/usr/bin/env python3
"""Submit MELI EDIT CLASSIC jobs from Files for Edit - MLB_Approved.s3.csv."""
import csv
import copy
import json
import os
import re
import sys
import time
from datetime import datetime
from typing import Dict, Any
from urllib.parse import urlparse

import boto3
import requests

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.dirname(BASE_DIR)
sys.path.insert(0, REPO_DIR)
from geo_mapping import normalize_geo
CSV_PATH = os.path.join(REPO_DIR, "Files for Edit - MLB_Approved.s3.csv")
CASES_PATH = os.path.join(REPO_DIR, "presets", "meli_cases.json")
LOG_PATH = os.path.join(REPO_DIR, "mlb_meli_from_csv.log")
DEFAULT_PRESIGN_EXPIRES = 6 * 60 * 60
_S3_CLIENT = None


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
    from urllib.parse import quote, unquote
    import unicodedata

    url = (url or "").strip()
    if url.startswith("https://meli-ai.filmmaker.s3.us-east-2.amazonaws.com/"):
        url = url.replace(
            "https://meli-ai.filmmaker.s3.us-east-2.amazonaws.com/",
            "https://s3.us-east-2.amazonaws.com/meli-ai.filmmaker/",
            1,
        )
    elif url.startswith("https://meli-ai.filmmaker.s3.amazonaws.com/"):
        url = url.replace(
            "https://meli-ai.filmmaker.s3.amazonaws.com/",
            "https://s3.us-east-2.amazonaws.com/meli-ai.filmmaker/",
            1,
        )
    if url.startswith("s3://"):
        without_scheme = url[len("s3://"):]
        if "/" in without_scheme:
            bucket, key = without_scheme.split("/", 1)
            decoded_key = unquote(key)
            if "MP-Users/Assets/" in decoded_key and "+" in decoded_key:
                decoded_key = decoded_key.replace("+", " ")
            normalized_key = unicodedata.normalize("NFD", decoded_key)
            encoded_key = quote(normalized_key, safe="/")
            return f"https://s3.us-east-2.amazonaws.com/{bucket}/{encoded_key}"
    elif url.startswith("https://") or url.startswith("http://"):
        scheme_end = url.find("://") + 3
        rest = url[scheme_end:]
        if "/" in rest:
            host, path = rest.split("/", 1)
            decoded_path = unquote(path)
            if "MP-Users/Assets/" in decoded_path and "+" in decoded_path:
                decoded_path = decoded_path.replace("+", " ")
            normalized_path = unicodedata.normalize("NFD", decoded_path)
            encoded_path = quote(normalized_path, safe="/")
            return url[:scheme_end] + host + "/" + encoded_path
    return url


def _get_s3_client(region: str | None = None):
    global _S3_CLIENT
    if _S3_CLIENT is None:
        if region:
            _S3_CLIENT = boto3.client("s3", region_name=region)
        else:
            _S3_CLIENT = boto3.client("s3")
    return _S3_CLIENT


def _extract_s3_bucket_key(url: str):
    from urllib.parse import unquote
    import unicodedata

    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return None
    host = parsed.netloc
    path = parsed.path or ""
    if "X-Amz-Signature" in parsed.query:
        return None

    def _clean_key(raw_key: str) -> str:
        decoded = unquote(raw_key)
        if "MP-Users/Assets/" in decoded and "+" in decoded:
            decoded = decoded.replace("+", " ")
        return unicodedata.normalize("NFD", decoded)

    if host.endswith(".s3.us-east-2.amazonaws.com"):
        bucket = host.split(".s3.us-east-2.amazonaws.com")[0]
        key = _clean_key(path.lstrip("/"))
        return bucket, key, "us-east-2"

    if host.endswith(".s3.amazonaws.com"):
        bucket = host.split(".s3.amazonaws.com")[0]
        key = _clean_key(path.lstrip("/"))
        return bucket, key, None

    if host in {"s3.us-east-2.amazonaws.com", "s3.amazonaws.com"}:
        parts = path.lstrip("/").split("/", 1)
        if len(parts) == 2:
            bucket, key = parts[0], _clean_key(parts[1])
            return bucket, key, "us-east-2" if host == "s3.us-east-2.amazonaws.com" else None
    return None


def _presign_if_s3(url: str, expires: int = DEFAULT_PRESIGN_EXPIRES) -> str:
    if not url:
        return url
    info = _extract_s3_bucket_key(url)
    if not info:
        return url
    bucket, key, region = info
    client = _get_s3_client(region)
    return client.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=expires,
    )


def _pick_first(row: Dict[str, str], keys: list[str]) -> str:
    for key in keys:
        value = (row.get(key) or "").strip()
        if value:
            return value
    return ""


def build_payload(
    row: Dict[str, str],
    base_style: Dict[str, Any],
    default_introcard_url: str,
    output_folder: str,
) -> Dict[str, Any]:
    geo = normalize_geo((row.get("GEO") or "").strip())
    scene1 = _presign_if_s3(_normalize_url((row.get("scene_1_lipsync") or "").strip()))
    scene2 = _presign_if_s3(_normalize_url((row.get("scene_2_lipsync") or "").strip()))
    scene3 = _presign_if_s3(_normalize_url((row.get("scene_3_lipsync") or "").strip()))
    broll_url = _presign_if_s3(_normalize_url(
        _pick_first(row, ["BROLL S3", "BROLL S3 URL", "Broll", "BRoll"])
    ))
    endcard_url = _presign_if_s3(_normalize_url(
        _pick_first(row, ["ENDCARD S3", "ENDCARD S3 URL", "Endcard"])
    ))

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

    # Use default b-roll configuration (no special handling for pix_no_credito)
    broll_clip: Dict[str, Any] = {"type": "broll", "url": broll_url}

    clips.extend(
        [
            {"type": "scene", "url": scene1},
            {"type": "scene", "url": scene2},
            broll_clip,
            {"type": "scene", "url": scene3},
            {"type": "endcard", "url": endcard_url},
        ]
    )

    output_filename = f"{parent}_MELI_EDIT.mp4"

    return {
        "input": {
            "job_id": f"meli_user_{geo}_{parent}",
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

    output_folder = "MP-Users/Outputs 02-2026"

    log_path = os.path.join(
        REPO_DIR,
        f"mlb_meli_from_csv_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log",
    )
    global LOG_PATH
    LOG_PATH = log_path

    log(f"Using endpoint {endpoint_id}")

    submitted = 0
    total = 0
    job_map: dict[str, str] = {}

    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            total += 1
            parent = parse_parent_from_scene_url((row.get("scene_1_lipsync") or "").strip())
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
            name = f"{parent}"
            job_map[name] = run_id
            log(f"{parent}: submitted {run_id}")
            submitted += 1

    log(f"Submitted {submitted}/{total} jobs")

    if job_map:
        log("Monitoring job status...")
        deadline = time.time() + 60 * 60
        pending = dict(job_map)
        while pending and time.time() < deadline:
            done = []
            for name, job_id in pending.items():
                try:
                    status_resp = requests.get(
                        f"https://api.runpod.ai/v2/{endpoint_id}/status/{job_id}",
                        headers={"Authorization": f"Bearer {api_key}"},
                        timeout=30,
                    )
                    status_resp.raise_for_status()
                    status = status_resp.json().get("status", "UNKNOWN")
                except Exception as exc:
                    status = f"ERROR: {exc}"
                log(f"STATUS {name}: {status}")
                if status in {"COMPLETED", "FAILED", "CANCELLED", "TIMED_OUT"}:
                    done.append(name)
            for name in done:
                pending.pop(name, None)
            if pending:
                time.sleep(20)
        if pending:
            log("WARNING: Some jobs still pending after timeout:")
            for name, job_id in pending.items():
                log(f"  {name} -> {job_id}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(1)
