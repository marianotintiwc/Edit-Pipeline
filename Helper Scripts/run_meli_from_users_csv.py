#!/usr/bin/env python3
"""Submit MELI EDIT CLASSIC jobs from USERS FILES FOR EDIT, MLA APPROVED.s3.csv."""
import csv
import copy
import json
import os
import re
import sys
from typing import Dict, Any

import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urlparse, unquote

import boto3
from botocore.exceptions import ClientError

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.dirname(BASE_DIR)
sys.path.insert(0, REPO_DIR)
from geo_mapping import normalize_geo
DEFAULT_CSV_PATH = os.path.join(REPO_DIR, "Files for Edit - MARIAN ESTOS SON PARA EDITAR.presigned.csv")
CASES_PATH = os.path.join(REPO_DIR, "presets", "meli_cases.json")
LOG_PATH = os.path.join(REPO_DIR, "users_meli_from_csv.log")


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
    m = re.search(r"/([^/]+)/[^/]+_scene_1(?:_lipsync)?\.mp4", url)
    if m:
        return m.group(1)
    m = re.search(r"/([^/]+)/[^/]+\.mp4", url)
    if m:
        return m.group(1)
    return "UNKNOWN"


def _get_index(headers: list, name: str) -> int:
    try:
        return headers.index(name)
    except ValueError:
        return -1


def _get_index_any(headers: list, names: list) -> int:
    for name in names:
        idx = _get_index(headers, name)
        if idx >= 0:
            return idx
    return -1


def _build_row_dict(headers: list, values: list) -> Dict[str, str]:
    row: Dict[str, str] = {}
    for i, header in enumerate(headers):
        if header:
            row[header] = values[i] if i < len(values) else ""

    if "GEO" not in row:
        geo_idx = _get_index_any(headers, ["GEO", "geo", "Geo"])
        if geo_idx >= 0 and len(values) > geo_idx:
            row["GEO"] = values[geo_idx]

    if "GEO" not in row:
        name_idx = _get_index(headers, "Nombre_Limpio")
        if name_idx >= 0 and len(values) > name_idx + 1:
            row["GEO"] = values[name_idx + 1]

    if "scene_1_lipsync" not in row:
        scene_1_idx = _get_index_any(headers, ["Scene_1", "scene_1", "scene 1", "SCENE 1", "SCENE_1", "scene_1_lipsync", "scene_1_lipsync_url"])
        if scene_1_idx >= 0 and len(values) > scene_1_idx:
            row["scene_1_lipsync"] = values[scene_1_idx]
    if "scene_2_lipsync" not in row:
        scene_2_idx = _get_index_any(headers, ["Scene_2", "scene_2", "scene 2", "SCENE 2", "SCENE_2", "scene_2_lipsync", "scene_2_lipsync_url"])
        if scene_2_idx >= 0 and len(values) > scene_2_idx:
            row["scene_2_lipsync"] = values[scene_2_idx]
    if "scene_3_lipsync" not in row:
        scene_3_idx = _get_index_any(headers, ["Scene_3", "scene_3", "scene 3", "SCENE 3", "SCENE_3", "scene_3_lipsync", "scene_3_lipsync_url"])
        if scene_3_idx >= 0 and len(values) > scene_3_idx:
            row["scene_3_lipsync"] = values[scene_3_idx]

    if "BROLL S3 URL" not in row:
        broll_idx = _get_index_any(
            headers,
            ["BROLL S3 URL", "BROLL", "broll", "Broll", "Broll1", "broll1", "broll_url", "Broll_S3_URL"],
        )
        if broll_idx >= 0 and len(values) > broll_idx:
            row["BROLL S3 URL"] = values[broll_idx]
    if "ENDCARD S3 URL" not in row:
        endcard_idx = _get_index_any(headers, ["ENDCARD S3 URL", "ENDCARD", "endcard", "Endcard", "endcard_url", "Endcard_S3_URL"])
        if endcard_idx >= 0 and len(values) > endcard_idx:
            row["ENDCARD S3 URL"] = values[endcard_idx]

    return row


def _normalize_url(url: str) -> str:
    from urllib.parse import quote
    url = (url or "").strip()
    if url.startswith("s3://"):
        # Convert s3://bucket/key to https://s3.us-east-2.amazonaws.com/bucket/key
        without_scheme = url[len("s3://"):]
        if "/" in without_scheme:
            bucket, key = without_scheme.split("/", 1)
            encoded_key = quote(key, safe="/")
            return f"https://s3.us-east-2.amazonaws.com/{bucket}/{encoded_key}"

    if url.startswith("https://") or url.startswith("http://"):
        parsed = urlparse(url)
        host = parsed.netloc
        path = unquote(parsed.path.lstrip("/"))

        # Convert virtual-hosted style to path-style for us-east-2
        if host.endswith(".s3.amazonaws.com"):
            bucket = host.split(".s3.amazonaws.com", 1)[0]
            encoded_path = quote(path, safe="/")
            return f"https://s3.us-east-2.amazonaws.com/{bucket}/{encoded_path}"

        # Ensure path-style URLs have encoded path
        if host == "s3.us-east-2.amazonaws.com":
            encoded_path = quote(path, safe="/")
            return f"https://{host}/{encoded_path}"

        # URL-encode spaces in any other HTTP/HTTPS URLs (ignore query params)
        if " " in path:
            encoded_path = quote(path, safe="/")
            return f"{parsed.scheme}://{host}{encoded_path}"

    return url


def _parse_s3_location(url: str) -> tuple[str, str] | None:
    raw = (url or "").strip()
    if not raw:
        return None

    if raw.startswith("s3://"):
        without_scheme = raw[len("s3://"):]
        if "/" not in without_scheme:
            return None
        bucket, key = without_scheme.split("/", 1)
        return bucket, unquote(key)

    parsed = urlparse(raw)
    host = parsed.netloc
    path = unquote(parsed.path.lstrip("/"))
    if not host or not path:
        return None

    # Path style: https://s3.<region>.amazonaws.com/<bucket>/<key>
    if host.startswith("s3.") and host.endswith(".amazonaws.com"):
        if "/" not in path:
            return None
        bucket, key = path.split("/", 1)
        return bucket, key

    # Virtual hosted style: https://<bucket>.s3.amazonaws.com/<key>
    if ".s3.amazonaws.com" in host:
        bucket = host.split(".s3.amazonaws.com", 1)[0]
        return bucket, path

    return None


def _to_presigned_url(url: str, s3_client: Any, expires_seconds: int) -> str:
    normalized = _normalize_url(url)
    parsed = urlparse(normalized)
    if parsed.query and "X-Amz-Signature=" in parsed.query:
        return normalized

    location = _parse_s3_location(normalized)
    if not location:
        return normalized

    bucket, key = location
    # Some CSV URLs use '+' where S3 object keys actually contain spaces.
    # Resolve that mismatch before signing so RunPod can download assets.
    if "+" in key:
        try:
            s3_client.head_object(Bucket=bucket, Key=key)
        except ClientError as e:
            code = (e.response or {}).get("Error", {}).get("Code", "")
            if code in {"404", "NoSuchKey", "NotFound"}:
                spaced_key = key.replace("+", " ")
                try:
                    s3_client.head_object(Bucket=bucket, Key=spaced_key)
                    key = spaced_key
                except ClientError:
                    pass
    return s3_client.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=expires_seconds,
    )


def _sanitize_filename_part(value: str) -> str:
    if not value:
        return ""
    text = value.strip().replace(" ", "_")
    text = re.sub(r"[^A-Za-z0-9._-]+", "", text)
    return text


def _infer_geo_from_row(row: Dict[str, str]) -> str:
    """
    Infer MercadoLibre GEO from row fields when explicit GEO column is missing.
    Supports values like MLB/MLA and country hints like BR.
    """
    candidates = [
        row.get("GEO"),
        row.get("geo"),
        row.get("video_name"),
        row.get("Video_Name"),
        row.get("scene_1_lipsync"),
    ]
    for raw in candidates:
        text = (raw or "").strip()
        if not text:
            continue
        upper = text.upper()
        if "-MLB" in upper or "_MLB" in upper or "MLB" == upper:
            return "MLB"
        if "-MLA" in upper or "_MLA" in upper or "MLA" == upper:
            return "MLA"
        if "-MLC" in upper or "_MLC" in upper or "MLC" == upper:
            return "MLC"
        if "-MLM" in upper or "_MLM" in upper or "MLM" == upper:
            return "MLM"
        if "-BR" in upper or "_BR" in upper or " BR " in f" {upper} " or upper == "BR":
            return "MLB"
    return ""


def build_payload(
    row: Dict[str, str],
    base_style: Dict[str, Any],
    default_introcard_url: str,
    output_folder: str,
    output_bucket: str | None = None,
    s3_client: Any | None = None,
    presign_expires_seconds: int = 43200,
) -> Dict[str, Any]:
    geo = normalize_geo((row.get("GEO") or row.get("geo") or "").strip())
    if not geo:
        geo = normalize_geo(_infer_geo_from_row(row))
    scene1 = _normalize_url((row.get("scene_1_lipsync") or "").strip())
    scene2 = _normalize_url((row.get("scene_2_lipsync") or "").strip())
    scene3 = _normalize_url((row.get("scene_3_lipsync") or "").strip())
    broll_url = _normalize_url(
        row.get("BROLL S3 URL")
        or row.get("Broll")
        or row.get("Broll1")
        or row.get("broll1")
        or ""
    )
    endcard_url = _normalize_url(row.get("ENDCARD S3 URL") or row.get("Endcard") or "")
    introcard_url = _normalize_url(
        row.get("introcard")
        or row.get("Introcard")
        or row.get("INTROCARD")
        or default_introcard_url
        or ""
    )

    if s3_client is not None:
        scene1 = _to_presigned_url(scene1, s3_client, presign_expires_seconds)
        scene2 = _to_presigned_url(scene2, s3_client, presign_expires_seconds)
        scene3 = _to_presigned_url(scene3, s3_client, presign_expires_seconds)
        broll_url = _to_presigned_url(broll_url, s3_client, presign_expires_seconds)
        endcard_url = _to_presigned_url(endcard_url, s3_client, presign_expires_seconds)
        introcard_url = _to_presigned_url(introcard_url, s3_client, presign_expires_seconds)

    if not (scene1 and scene2 and scene3):
        raise ValueError("missing one or more scene URLs")
    if not broll_url:
        raise ValueError("missing B-roll URL")
    if not endcard_url:
        raise ValueError("missing Endcard URL")

    parent = parse_parent_from_scene_url(scene1)
    record_id = (row.get("#") or row.get("record_id") or row.get("Record_ID") or "").strip()
    prod = (row.get("Prod") or row.get("product") or row.get("Product") or "").strip()
    safe_geo = _sanitize_filename_part(geo)
    safe_record = _sanitize_filename_part(record_id)
    safe_prod = _sanitize_filename_part(prod)

    style = copy.deepcopy(base_style)
    style.setdefault("endcard", {})
    style["endcard"]["url"] = endcard_url
    # Requested subtitle style: no black stroke; text uses stroke color as fill.
    if style.get("stroke_color"):
        style["color"] = style.get("stroke_color")
    style["stroke_width"] = 0
    if isinstance(style.get("highlight"), dict):
        style["highlight"]["stroke_width"] = 0
        if style["highlight"].get("stroke_color"):
            style["highlight"]["text_color"] = style["highlight"]["stroke_color"]
        elif style.get("stroke_color"):
            style["highlight"]["text_color"] = style.get("stroke_color")
    style["broll_alpha_fill"] = {
        "enabled": True,
        "invert_alpha": False,
        "auto_invert_alpha": False,
    }

    clips = []
    if introcard_url:
        clips.append({"type": "introcard", "url": introcard_url})
    # Clip order must match preset: introcard, scene1, scene2, scene3, broll, endcard.
    # Do NOT send start_time/end_time or duration for endcard — pipeline uses file duration.
    clips.extend(
        [
            {"type": "scene", "url": scene1},
            {"type": "scene", "url": scene2},
            {"type": "scene", "url": scene3},
            {"type": "broll", "url": broll_url},
            {"type": "endcard", "url": endcard_url},
        ]
    )

    file_name_raw = (
        row.get("FILE NAME")
        or row.get("FILE_NAME")
        or row.get("filename")
        or row.get("file_name")
        or row.get("video_name")
        or row.get("Video_Name")
        or ""
    ).strip()
    safe_file_name = _sanitize_filename_part(file_name_raw)

    if safe_file_name:
        if safe_file_name.lower().endswith(".mp4"):
            output_filename = safe_file_name
        else:
            output_filename = f"{safe_file_name}_MELI_EDIT.mp4"
    elif safe_geo and safe_record and safe_prod:
        output_filename = f"{safe_geo}-{safe_record}-{safe_prod}.mp4"
    else:
        output_filename = f"{parent}_MELI_EDIT.mp4"

    payload = {
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
    if output_bucket:
        payload["input"]["output_bucket"] = output_bucket
    return payload


def main() -> None:
    csv_path = os.environ.get("USERS_CSV_PATH", "").strip() or DEFAULT_CSV_PATH
    if not os.path.exists(csv_path) and csv_path == DEFAULT_CSV_PATH:
        fallback = os.path.join(REPO_DIR, "Files for Edit - MARIAN ESTOS SON PARA EDITAR.csv")
        if os.path.exists(fallback):
            csv_path = fallback
    if not os.path.exists(csv_path):
        raise SystemExit(f"CSV not found: {csv_path}")
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
    request_headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    output_folder = os.environ.get("OUTPUT_FOLDER", "outputs").strip() or "outputs"
    output_bucket = os.environ.get("OUTPUT_BUCKET", "").strip() or None
    presign_s3_urls = os.environ.get("PRESIGN_S3_URLS", "1").strip().lower() not in {"0", "false", "no"}
    presign_expires_seconds = int(os.environ.get("PRESIGN_EXPIRES_SECONDS", "43200"))
    s3_client = None
    if presign_s3_urls:
        s3_region = os.environ.get("AWS_DEFAULT_REGION", "us-east-2")
        s3_client = boto3.client("s3", region_name=s3_region)

    try:
        if os.path.exists(LOG_PATH):
            os.remove(LOG_PATH)
    except OSError:
        pass

    log(f"Using endpoint {endpoint_id}")

    submitted = 0
    total = 0

    jobs = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        csv_headers = next(reader, [])
        for values in reader:
            total += 1
            row = _build_row_dict(csv_headers, values)
            parent = parse_parent_from_scene_url((row.get("scene_1_lipsync") or "").strip())
            try:
                payload = build_payload(
                    row,
                    base_style,
                    default_introcard_url,
                    output_folder,
                    output_bucket=output_bucket,
                    s3_client=s3_client,
                    presign_expires_seconds=presign_expires_seconds,
                )
            except ValueError as e:
                log(f"Skipping {parent}: {e}")
                continue
            jobs.append((parent, payload))

    submit_workers = int(os.environ.get("RUNPOD_WORKERS", "30"))

    def _submit_job(parent_name: str, payload: Dict[str, Any]) -> str:
        r = requests.post(base_url, headers=request_headers, json=payload, timeout=60)
        r.raise_for_status()
        return r.json().get("id", "")

    with ThreadPoolExecutor(max_workers=submit_workers) as executor:
        future_map = {
            executor.submit(_submit_job, parent, payload): parent
            for parent, payload in jobs
        }
        for future in as_completed(future_map):
            parent = future_map[future]
            try:
                run_id = future.result()
                log(f"{parent}: submitted {run_id}")
                submitted += 1
            except Exception as e:
                log(f"{parent}: ERROR submitting job: {e}")

    log(f"Submitted {submitted}/{total} jobs")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        sys.exit(1)
