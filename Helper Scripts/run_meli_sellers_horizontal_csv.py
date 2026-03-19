#!/usr/bin/env python3
"""MP-Sellers 16:9 CSV → RunPod. meli_cases base_style + flat subtitles + horizontal preset.

Production config snapshot: config/mp_sellers_horizontal_hd15_production.json
Canonical full batch CSV: Videos para Editar - SPLA.csv (74 jobs).
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from typing import Any, Dict, List, Tuple

import requests
from concurrent.futures import ThreadPoolExecutor, as_completed

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.dirname(BASE_DIR)
sys.path.insert(0, REPO_DIR)

from geo_mapping import normalize_geo  # noqa: E402
from ugc_tools.meli_subtitle_style import apply_meli_flat_subtitle_style  # noqa: E402

MELI_CASES_PATH = os.path.join(REPO_DIR, "presets", "meli_cases.json")
DEFAULT_OUTPUT_BUCKET = "meli-ai.filmmaker"
DEFAULT_OUTPUT_FOLDER = "MP-Sellers/Outputs-Horizontal-HD15-Master"
DEFAULT_ENDPOINT = "h55ft9cy7fyi1d"
LOG_PATH = os.path.join(REPO_DIR, "meli_sellers_horizontal_csv.log")
ASPECT_RATIO = "16:9"
# Base ~52px equivalent, then −15% for smaller subs (52 * 0.85 ≈ 44).
DEFAULT_HORIZONTAL_SUBTITLE_FONTSIZE = 44

HORIZONTAL_STYLE_DELTA: Dict[str, Any] = {
    "resolution": [1920, 1080],
    "margin_bottom": 378,
    # True horizontal center + full frame width for line fit; lower third via margin_bottom above (not UAC bottom).
    "position": "center_bottom",
    "subtitle_horizontal_ignore_safe_zone": True,
    "shadow": {"enabled": False},
    "uac_16x9_margins": {
        "ref_width": 1920,
        "ref_height": 1080,
        "top": 40,
        "bottom": 378,
        "left": 105,
        "right": 516,
    },
    "postprocess": {
        "output": {"profile": "master", "crf": 18, "preset": "slow"},
    },
}


def deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    result = dict(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_meli_base_style() -> Dict[str, Any]:
    with open(MELI_CASES_PATH, "r", encoding="utf-8") as f:
        cfg = json.load(f)
    raw = cfg.get("base_style")
    if not isinstance(raw, dict):
        raise RuntimeError("meli_cases.json missing base_style")
    return json.loads(json.dumps(raw))


def build_horizontal_style_overrides() -> Dict[str, Any]:
    style = deep_merge(load_meli_base_style(), HORIZONTAL_STYLE_DELTA)
    fs = int(os.environ.get("MELI_HORIZONTAL_SUBTITLE_FONTSIZE", str(DEFAULT_HORIZONTAL_SUBTITLE_FONTSIZE)))
    apply_meli_flat_subtitle_style(style, fontsize=fs, position="center_bottom", shadow_enabled=False)
    return style


def load_env_from_dotenv() -> None:
    for path in (
        os.path.join(REPO_DIR, ".env"),
        os.path.join(os.path.dirname(REPO_DIR), ".env"),
        os.path.join(os.getcwd(), ".env"),
    ):
        if not os.path.exists(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, _, v = line.partition("=")
                    k, v = k.strip(), v.strip().strip('"').strip("'")
                    if k and k not in os.environ:
                        os.environ[k] = v
        except OSError:
            pass
        break


def log(msg: str) -> None:
    print(msg)
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as lf:
            lf.write(msg + "\n")
    except OSError:
        pass


def _normalize_url(url: str) -> str:
    from urllib.parse import quote

    url = (url or "").strip()
    if url.startswith("s3://"):
        rest = url[len("s3://") :]
        if "/" in rest:
            bucket, key = rest.split("/", 1)
            url = f"https://s3.us-east-2.amazonaws.com/{bucket}/{quote(key, safe='/')}"
    return url


def _sanitize_folder_name(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", (name or "").strip()) or "unknown"


def geo_from_folder(folder: str) -> str:
    m = re.search(r"-([A-Z]{2,4})-(male|female)$", (folder or "").strip(), re.IGNORECASE)
    if not m:
        raise ValueError(f"cannot parse geo from FOLDER NAME: {folder!r}")
    raw = m.group(1).upper()
    return normalize_geo(raw) or raw


def build_payload(
    row: Dict[str, str],
    output_bucket: str,
    output_folder: str,
    style_template: Dict[str, Any],
    clip_order: str = "linear",
) -> Dict[str, Any]:
    folder = (row.get("FOLDER NAME") or row.get("FOLDER_NAME") or "").strip()
    if not folder:
        raise ValueError("empty FOLDER NAME")
    intro = _normalize_url((row.get("introcard") or "").strip())
    s1 = _normalize_url((row.get("Scene_1") or "").strip())
    s2 = _normalize_url((row.get("Scene_2") or "").strip())
    s3 = _normalize_url((row.get("Scene_3") or "").strip())
    broll = _normalize_url((row.get("Broll1") or row.get("Broll") or "").strip())
    end = _normalize_url((row.get("Endcard") or "").strip())
    for label, u in [
        ("introcard", intro),
        ("Scene_1", s1),
        ("Scene_2", s2),
        ("Scene_3", s3),
        ("Broll1", broll),
        ("Endcard", end),
    ]:
        if not u:
            raise ValueError(f"missing {label}")
    geo = geo_from_folder(folder)
    safe = _sanitize_folder_name(folder)
    style_overrides = json.loads(json.dumps(style_template))
    overlap = float((style_overrides.get("endcard") or {}).get("overlap_seconds") or 0.5)
    if clip_order == "meli-classic":
        clips: List[Dict[str, Any]] = [
            {"type": "introcard", "url": intro},
            {"type": "scene", "url": s1},
            {"type": "scene", "url": s2},
            {"type": "broll", "url": broll},
            {"type": "scene", "url": s3},
            {"type": "endcard", "url": end, "overlap_seconds": overlap},
        ]
    else:
        clips = [
            {"type": "introcard", "url": intro},
            {"type": "scene", "url": s1},
            {"type": "scene", "url": s2},
            {"type": "scene", "url": s3},
            {"type": "broll", "url": broll},
            {"type": "endcard", "url": end, "overlap_seconds": overlap},
        ]
    return {
        "input": {
            "job_id": f"sellers_h15_{safe}",
            "geo": geo,
            "aspect_ratio": ASPECT_RATIO,
            "output_folder": output_folder.strip().strip("/"),
            "output_bucket": output_bucket.strip(),
            "output_filename": f"{safe}_16x9_MELI_EDIT.mp4",
            "clips": clips,
            "music_url": "random",
            "subtitle_mode": "auto",
            "edit_preset": "horizontal",
            "style_overrides": style_overrides,
        }
    }


def resolve_csv_path(csv_arg: str) -> str:
    if os.path.isabs(csv_arg) and os.path.exists(csv_arg):
        return csv_arg
    for base in (os.getcwd(), REPO_DIR):
        c = os.path.normpath(os.path.join(base, csv_arg))
        if os.path.exists(c):
            return os.path.abspath(c)
    return os.path.abspath(os.path.join(os.getcwd(), csv_arg))


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--csv", required=True)
    p.add_argument("--output-bucket", default=os.environ.get("MELI_OUTPUT_BUCKET", DEFAULT_OUTPUT_BUCKET))
    p.add_argument("--output-folder", default=os.environ.get("MELI_OUTPUT_FOLDER", DEFAULT_OUTPUT_FOLDER))
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--results-json", default="")
    p.add_argument(
        "--clip-order",
        choices=("linear", "meli-classic"),
        default=os.environ.get("MELI_HORIZONTAL_CLIP_ORDER", "linear"),
    )
    args = p.parse_args()
    csv_path = resolve_csv_path(args.csv)
    if not os.path.exists(csv_path):
        raise SystemExit(f"CSV not found: {csv_path}")
    load_env_from_dotenv()
    api_key = os.environ.get("RUNPOD_API_KEY")
    endpoint_id = os.environ.get("RUNPOD_ENDPOINT_ID", DEFAULT_ENDPOINT)
    try:
        if os.path.exists(LOG_PATH):
            os.remove(LOG_PATH)
    except OSError:
        pass
    style_template = build_horizontal_style_overrides()
    log(f"Horizontal MELI — fontsize={style_template.get('fontsize')} clip_order={args.clip_order}")
    log(f"CSV: {csv_path}")
    jobs: List[Tuple[str, Dict[str, Any]]] = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            folder = (row.get("FOLDER NAME") or row.get("FOLDER_NAME") or "").strip()
            if not folder:
                continue
            if args.limit and len(jobs) >= args.limit:
                break
            try:
                jobs.append(
                    (
                        folder,
                        build_payload(row, args.output_bucket, args.output_folder, style_template, args.clip_order),
                    )
                )
            except ValueError as e:
                log(f"Skip {folder!r}: {e}")
    log(f"Prepared {len(jobs)} job(s)")
    out_path = args.results_json or os.path.join(REPO_DIR, "meli_sellers_horizontal_results.json")
    if args.dry_run:
        with open(out_path, "w", encoding="utf-8") as fp:
            json.dump(
                {
                    "csv": csv_path,
                    "clip_order": args.clip_order,
                    "subtitle_fontsize": style_template.get("fontsize"),
                    "jobs": [{"folder": a, "output_filename": b["input"]["output_filename"]} for a, b in jobs],
                },
                fp,
                indent=2,
            )
        log(f"Wrote {out_path}")
        return
    if not api_key:
        raise SystemExit("RUNPOD_API_KEY not set")
    base_url = f"https://api.runpod.ai/v2/{endpoint_id}/run"
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    log(f"Endpoint: {endpoint_id}")
    results: List[Dict[str, Any]] = []
    workers = int(os.environ.get("RUNPOD_WORKERS", "8"))

    def submit(folder: str, payload: Dict[str, Any]) -> Tuple[str, str, str]:
        r = requests.post(base_url, headers=headers, json=payload, timeout=90)
        r.raise_for_status()
        return folder, r.json().get("id", ""), payload["input"]["output_filename"]

    ok = 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        fmap = {ex.submit(submit, fo, pl): fo for fo, pl in jobs}
        for fut in as_completed(fmap):
            fo = fmap[fut]
            try:
                f, jid, name = fut.result()
                log(f"{f}: {jid} -> {name}")
                results.append({"folder": f, "runpod_id": jid, "output_filename": name, "ok": True})
                ok += 1
            except Exception as e:
                log(f"{fo}: ERROR {e}")
                results.append({"folder": fo, "ok": False, "error": str(e)})
    log(f"Submitted {ok}/{len(jobs)}")
    with open(out_path, "w", encoding="utf-8") as fp:
        json.dump(
            {
                "csv": csv_path,
                "output": f"s3://{args.output_bucket}/{args.output_folder.strip().strip('/')}/",
                "endpoint": endpoint_id,
                "clip_order": args.clip_order,
                "subtitle_fontsize": style_template.get("fontsize"),
                "edit_preset": "horizontal",
                "jobs": results,
            },
            fp,
            indent=2,
        )
    log(f"Wrote {out_path}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(1)
