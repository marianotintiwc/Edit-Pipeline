#!/usr/bin/env python3
"""
Submit MELI EDIT jobs from LATAM_edit_outputs_urls.csv.

LATAM alpha detection config:
  - broll: has_alpha=True (argb, qtrle) → force_chroma_key=False, use_blur_background=True
  - endcard: has_alpha=False (yuv420p, h264) → force_chroma_key=True, use_blur_background=False

Outputs: s3://latam-ai.filmmaker/LATAM/LATAM_Exports/
Geo: MLC (endpoint accepts MLC, MLA, MLB only; CL maps to MLC)
"""
import argparse
import csv
import json
import os
import re
import sys
from typing import Dict, Any

import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.dirname(BASE_DIR)
sys.path.insert(0, REPO_DIR)
from geo_mapping import normalize_geo
DEFAULT_CSV = "LATAM_edit_outputs_urls.csv"
CASES_PATH = os.path.join(REPO_DIR, "presets", "meli_cases.json")
LOG_PATH = os.path.join(REPO_DIR, "latam_meli_from_csv.log")

# Output path: s3://latam-ai.filmmaker/LATAM/LATAM_Exports/
OUTPUT_FOLDER = "LATAM/LATAM_Exports"
OUTPUT_BUCKET = "latam-ai.filmmaker"

# LATAM alpha config (proven working)
LATAM_BROLL_ALPHA = {
    "enabled": True,
    "force_chroma_key": False,
    "use_blur_background": True,
    "invert_alpha": False,
    "auto_invert_alpha": False,
}
LATAM_ENDCARD_ALPHA = {
    "enabled": True,
    "force_chroma_key": True,
    "use_blur_background": False,
    "invert_alpha": False,
    "auto_invert_alpha": False,
    "chroma_key_color": "0x000000",
    "chroma_key_similarity": 0.04,
    "chroma_key_blend": 0.0,
    "edge_feather": 0,
}
ENDCARD_OVERLAP = 0.75


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


def _normalize_url(url: str) -> str:
    from urllib.parse import quote, unquote

    url = (url or "").strip()
    if url.startswith("s3://"):
        without_scheme = url[len("s3://") :]
        if "/" in without_scheme:
            bucket, key = without_scheme.split("/", 1)
            encoded_key = quote(key, safe="/")
            url = f"https://s3.us-east-2.amazonaws.com/{bucket}/{encoded_key}"
    if url.startswith("https://") or url.startswith("http://"):
        # S3 objects use -MLC- (MercadoLibre Chile); CSV may use -CL-
        if "latam-ai.filmmaker" in url and "-CL-" in url:
            url = url.replace("-CL-", "-MLC-")
        return url
    return url


def _sanitize_aspect(s: str) -> str:
    """Convert 9:16 -> 9x16, 16:9 -> 16x9 for filenames."""
    s = (s or "").strip().replace(":", "x")
    return re.sub(r"[^0-9x]", "", s) or "9x16"


def build_payload(row: Dict[str, str]) -> Dict[str, Any]:
    video_name = (row.get("video_name") or "").strip()
    aspect_ratio = (row.get("aspect_ratio") or "9:16").strip()
    scene1 = _normalize_url((row.get("scene_1") or "").strip())
    scene2 = _normalize_url((row.get("scene_2") or "").strip())
    scene3 = _normalize_url((row.get("scene_3") or "").strip())
    broll_url = _normalize_url((row.get("broll") or "").strip())
    endcard_url = _normalize_url((row.get("endcard") or "").strip())

    if not (scene1 and scene2 and scene3):
        raise ValueError("missing one or more scene URLs")
    if not broll_url:
        raise ValueError("missing broll URL")
    if not endcard_url:
        raise ValueError("missing endcard URL")
    if not video_name:
        raise ValueError("missing video_name")

    # Normalize geo: CL->MLC, AR->MLA, BR->MLB, etc.
    geo = normalize_geo(row.get("geo") or "CL") or "MLC"

    clips = [
        {"type": "scene", "url": scene1},
        {"type": "scene", "url": scene2},
        {"type": "broll", "url": broll_url},
        {"type": "scene", "url": scene3},
        {"type": "endcard", "url": endcard_url, "overlap_seconds": ENDCARD_OVERLAP},
    ]

    safe_aspect = _sanitize_aspect(aspect_ratio)
    safe_name = re.sub(r"[^A-Za-z0-9._-]+", "", video_name.replace(" ", "_"))
    output_filename = f"{safe_name}_{safe_aspect}.mp4"

    # 16:9 -> resolution [1920, 1080]; 9:16 -> [1080, 1920]
    is_16x9 = aspect_ratio.strip().replace(":", "x").lower() in ("16x9", "16:9")
    resolution = [1920, 1080] if is_16x9 else [1080, 1920]

    style_overrides = {
        "broll_alpha_fill": dict(LATAM_BROLL_ALPHA),
        "endcard_alpha_fill": dict(LATAM_ENDCARD_ALPHA),
        "color": "white",
        "stroke_color": "black",
        "stroke_width": 8,
        "highlight": {"enabled": True, "bg_color": "#1b0088"},
        "endcard": {"enabled": True, "overlap_seconds": ENDCARD_OVERLAP, "audio_fade_seconds": 0.1},
        "resolution": resolution,
    }
    # Safe zones: TikTok (9:16) and UAC 16:9 - margin_bottom keeps subtitles in safe area
    if is_16x9:
        style_overrides["margin_bottom"] = 504  # UAC 16:9 @ 1920x1080
        style_overrides["uac_16x9_margins"] = {
            "ref_width": 1920,
            "ref_height": 1080,
            "top": 40,
            "bottom": 504,
            "left": 105,
            "right": 516,
        }
    else:
        style_overrides["margin_bottom"] = 704  # TikTok 9:16 @ 1080x1920 (352*2)
        style_overrides["tiktok_safe_margins"] = {
            "ref_width": 540,
            "ref_height": 960,
            "top": 126,
            "bottom": 352,
            "left": 60,
            "right": 120,
            "zone_height": 780,
        }

    return {
        "input": {
            "job_id": f"latam_{safe_name}_{safe_aspect}",
            "geo": geo,
            "aspect_ratio": aspect_ratio,
            "output_folder": OUTPUT_FOLDER,
            "output_bucket": OUTPUT_BUCKET,
            "output_filename": output_filename,
            "clips": clips,
            "music_url": "random",
            "subtitle_mode": "auto",
            "edit_preset": "standard_vertical",
            "style_overrides": style_overrides,
        }
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Submit LATAM edit jobs from CSV")
    parser.add_argument(
        "--csv",
        default=os.path.join(REPO_DIR, DEFAULT_CSV),
        help=f"Path to CSV (default: {DEFAULT_CSV})",
    )
    parser.add_argument("--limit", type=int, default=0, help="Max jobs to submit (0=all)")
    parser.add_argument("--aspect", default="", help="Filter by aspect_ratio (e.g. 16:9 or 9:16)")
    args = parser.parse_args()
    csv_path = args.csv
    if not os.path.isabs(csv_path):
        for base in [os.getcwd(), REPO_DIR]:
            candidate = os.path.normpath(os.path.join(base, csv_path))
            if os.path.exists(candidate):
                csv_path = os.path.abspath(candidate)
                break
        else:
            csv_path = os.path.abspath(os.path.join(os.getcwd(), csv_path))
    else:
        csv_path = args.csv
    if not os.path.exists(csv_path):
        raise SystemExit(f"CSV not found: {csv_path}")

    load_env_from_dotenv()

    api_key = os.environ.get("RUNPOD_API_KEY")
    endpoint_id = os.environ.get("RUNPOD_ENDPOINT_ID", "h55ft9cy7fyi1d")
    if not api_key:
        raise SystemExit("RUNPOD_API_KEY not set; export it or add to .env")

    base_url = f"https://api.runpod.ai/v2/{endpoint_id}/run"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    try:
        if os.path.exists(LOG_PATH):
            os.remove(LOG_PATH)
    except OSError:
        pass

    log("LATAM Edit - Text: white+black outline, highlight: #1b0088, safe zones, endcard 0.75s")
    log(f"Using endpoint {endpoint_id}")
    log(f"CSV: {csv_path}")
    log(f"Output folder: {OUTPUT_FOLDER}")
    log(
        "Alpha config: broll force_chroma_key=False, use_blur_background=True; "
        "endcard force_chroma_key=True, use_blur_background=False"
    )

    jobs = []
    aspect_filter = (args.aspect or "").strip()
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if aspect_filter and (row.get("aspect_ratio") or "").strip() != aspect_filter:
                continue
            if args.limit and len(jobs) >= args.limit:
                break
            try:
                payload = build_payload(row)
            except ValueError as e:
                name = (row.get("video_name") or "?").strip()
                log(f"Skipping {name}: {e}")
                continue
            label = f"{row.get('video_name', '?')} ({row.get('aspect_ratio', '?')})"
            jobs.append((label, payload))

    submit_workers = int(os.environ.get("RUNPOD_WORKERS", "10"))

    def _submit(label: str, payload: Dict[str, Any]) -> str:
        r = requests.post(base_url, headers=headers, json=payload, timeout=60)
        r.raise_for_status()
        return r.json().get("id", "")

    submitted = 0
    with ThreadPoolExecutor(max_workers=submit_workers) as executor:
        future_map = {
            executor.submit(_submit, label, payload): label for label, payload in jobs
        }
        for future in as_completed(future_map):
            label = future_map[future]
            try:
                run_id = future.result()
                log(f"{label}: submitted {run_id}")
                submitted += 1
            except Exception as e:
                log(f"{label}: ERROR submitting job: {e}")

    log(f"Submitted {submitted}/{len(jobs)} jobs")
    log(f"Outputs will be saved to s3://{OUTPUT_BUCKET}/{OUTPUT_FOLDER}/")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(1)
