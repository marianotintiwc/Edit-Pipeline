#!/usr/bin/env python3
"""
Download MLB assets (B-rolls and Endcards) from Google Drive and upload to S3,
then create a proper CSV with S3 URLs.
"""
import csv
import os
import re
from pathlib import Path
from urllib.parse import quote

import boto3
import requests

BASE_DIR = Path(__file__).resolve().parent
REPO_DIR = BASE_DIR.parent
INPUT_CSV = REPO_DIR / "Files for Edit - MLB_Approved.csv"
OUTPUT_CSV = REPO_DIR / "Files for Edit - MLB_Approved.s3.csv"
TMP_DIR = REPO_DIR / "assets/IGNOREASSETS/users_assets_upload_tmp"

S3_BUCKET = "meli-ai.filmmaker"
S3_PREFIX = "MP-Users/Assets"
S3_REGION = "us-east-2"


def load_env_from_dotenv() -> None:
    candidates = [
        REPO_DIR / ".env",
        REPO_DIR.parent / ".env",
    ]
    for path in candidates:
        if not path.exists():
            continue
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
        break


def extract_drive_file_id(url: str) -> str | None:
    if not url or "drive.google.com" not in url:
        return None
    m = re.search(r"/file/d/([^/]+)", url)
    if m:
        return m.group(1)
    m = re.search(r"[?&]id=([^&]+)", url)
    if m:
        return m.group(1)
    return None


def _download_response(file_id: str) -> requests.Response:
    url = f"https://drive.google.com/uc?export=download&id={file_id}"
    session = requests.Session()
    response = session.get(url, stream=True, allow_redirects=True)
    if "text/html" in response.headers.get("Content-Type", ""):
        for key, value in response.cookies.items():
            if key.startswith("download_warning"):
                url = f"https://drive.google.com/uc?export=download&confirm={value}&id={file_id}"
                response = session.get(url, stream=True, allow_redirects=True)
                break
        else:
            url = f"https://drive.google.com/uc?export=download&confirm=t&id={file_id}"
            response = session.get(url, stream=True, allow_redirects=True)
    return response


def extract_filename(response: requests.Response, fallback_id: str) -> str:
    content_disp = response.headers.get("Content-Disposition", "")
    if content_disp:
        match = re.search(r"filename\*=UTF-8''([^;]+)", content_disp)
        if match:
            return requests.utils.unquote(match.group(1))
        match = re.search(r"filename=\"([^\"]+)\"", content_disp)
        if match:
            return match.group(1)
        match = re.search(r"filename=([^;]+)", content_disp)
        if match:
            return match.group(1).strip().strip('"')
    content_type = response.headers.get("Content-Type", "")
    if "mp4" in content_type:
        return f"{fallback_id}.mp4"
    return f"{fallback_id}.mov"


def download_drive_file(file_id: str, dest_dir: Path) -> Path:
    response = _download_response(file_id)
    if response.status_code != 200:
        raise RuntimeError(f"Download failed: status {response.status_code}")
    content_type = response.headers.get("Content-Type", "")
    if "text/html" in content_type:
        raise RuntimeError("Download failed: got HTML (not public?)")
    filename = extract_filename(response, file_id)
    dest_path = dest_dir / filename
    with dest_path.open("wb") as f:
        for chunk in response.iter_content(chunk_size=1024 * 1024):
            if chunk:
                f.write(chunk)
    if dest_path.stat().st_size == 0:
        dest_path.unlink(missing_ok=True)
        raise RuntimeError("Download failed: empty file")
    return dest_path


def s3_http_url(key: str) -> str:
    encoded_key = quote(key, safe="/")
    return f"https://s3.{S3_REGION}.amazonaws.com/{S3_BUCKET}/{encoded_key}"


def upload_to_s3(local_path: Path, s3_client) -> str:
    key = f"{S3_PREFIX}/{local_path.name}"
    try:
        s3_client.head_object(Bucket=S3_BUCKET, Key=key)
        return s3_http_url(key)
    except Exception:
        pass
    if local_path.suffix.lower() == ".mov":
        content_type = "video/quicktime"
    elif local_path.suffix.lower() == ".mp4":
        content_type = "video/mp4"
    else:
        content_type = "application/octet-stream"
    s3_client.upload_file(
        str(local_path),
        S3_BUCKET,
        key,
        ExtraArgs={"ContentType": content_type},
    )
    return s3_http_url(key)


def pick_first(row: dict, keys: list[str]) -> str:
    for key in keys:
        value = (row.get(key) or "").strip()
        if value:
            return value
    return ""


def resolve_s3_from_value(value: str, drive_map: dict[str, str]) -> str:
    value = (value or "").strip()
    if not value:
        return ""
    if value.startswith("s3://") or value.startswith("https://s3"):
        return value
    drive_id = extract_drive_file_id(value)
    if drive_id and drive_id in drive_map:
        return drive_map[drive_id]
    filename = os.path.basename(value)
    key = f"{S3_PREFIX}/{filename}"
    return s3_http_url(key)


def main() -> None:
    if not INPUT_CSV.exists():
        raise SystemExit(f"Input CSV not found: {INPUT_CSV}")

    TMP_DIR.mkdir(parents=True, exist_ok=True)

    load_env_from_dotenv()

    s3_client = boto3.client(
        "s3",
        region_name=S3_REGION,
        aws_access_key_id=os.environ.get("AWS_ACCESS_KEY_ID"),
        aws_secret_access_key=os.environ.get("AWS_SECRET_ACCESS_KEY"),
    )

    with INPUT_CSV.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print(f"Read {len(rows)} rows from {INPUT_CSV}")

    drive_map: dict[str, str] = {}
    unique_drive_ids = []
    for row in rows:
        for col in ("Broll", "BRoll", "Endcard"):
            url = (row.get(col) or "").strip()
            drive_id = extract_drive_file_id(url)
            if drive_id and drive_id not in drive_map:
                drive_map[drive_id] = ""
                unique_drive_ids.append(drive_id)

    print(f"Found {len(unique_drive_ids)} unique Google Drive files")

    for idx, drive_id in enumerate(unique_drive_ids, 1):
        print(f"[{idx}/{len(unique_drive_ids)}] Downloading {drive_id}...")
        try:
            local_path = download_drive_file(drive_id, TMP_DIR)
            print(f"  ✓ Downloaded to {local_path}")
            s3_url = upload_to_s3(local_path, s3_client)
            drive_map[drive_id] = s3_url
            print(f"  ✓ Uploaded: {s3_url}")
        except Exception as e:
            print(f"  ✗ Failed: {e}")

    output_rows = []
    for row in rows:
        product = pick_first(row, ["Product", "product"])
        geo = pick_first(row, ["GEO", "Geo", "geo"])
        gender = pick_first(row, ["Gender", "gender"])
        scene1 = pick_first(row, ["scene_1_lipsync", "Scene_1", "scene_1"])
        scene2 = pick_first(row, ["scene_2_lipsync", "Scene_2", "scene_2"])
        scene3 = pick_first(row, ["scene_3_lipsync", "Scene_3", "scene_3"])
        broll = pick_first(row, ["Broll", "BRoll"])
        endcard = pick_first(row, ["Endcard"])

        broll_s3 = resolve_s3_from_value(broll, drive_map)
        endcard_s3 = resolve_s3_from_value(endcard, drive_map)

        output_rows.append({
            "Product": product,
            "GEO": geo,
            "Gender": gender,
            "scene_1_lipsync": scene1,
            "scene_2_lipsync": scene2,
            "scene_3_lipsync": scene3,
            "Broll": broll,
            "Endcard": endcard,
            "BROLL S3": broll_s3,
            "ENDCARD S3": endcard_s3,
        })

    output_rows.sort(key=lambda r: (r["Product"].lower(), r["Gender"].lower(), r["scene_1_lipsync"]))

    fieldnames = [
        "Product",
        "GEO",
        "Gender",
        "scene_1_lipsync",
        "scene_2_lipsync",
        "scene_3_lipsync",
        "Broll",
        "Endcard",
        "BROLL S3",
        "ENDCARD S3",
    ]

    with OUTPUT_CSV.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(output_rows)

    print(f"\n✓ Output CSV written: {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
