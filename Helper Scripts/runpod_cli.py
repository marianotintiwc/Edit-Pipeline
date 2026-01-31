#!/usr/bin/env python3
"""RunPod helper CLI.

Consolidates submit, status, poll, and endpoint image update into one tool.
"""

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Optional

import requests

REPO = Path("/Users/marianotinti/Desktop/UGC EDITOR/Edit-Pipeline")
DEFAULT_PAYLOAD = REPO / "assets" / "IGNOREASSETS" / "local_meli_first_row_payload.json"
DEFAULT_IMAGE = "docker.io/marianotintiwc/edit-pipeline:latest"


def load_env(env_path: Path) -> None:
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        if not line.strip() or line.strip().startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def require_env(*keys: str) -> None:
    missing = [k for k in keys if not os.getenv(k)]
    if missing:
        raise SystemExit(f"Missing required env vars: {', '.join(missing)}")


def get_endpoint_id(cli_value: Optional[str]) -> str:
    endpoint_id = cli_value or os.getenv("RUNPOD_ENDPOINT_ID")
    if not endpoint_id:
        raise SystemExit("RUNPOD_ENDPOINT_ID not set")
    return endpoint_id


def get_api_key() -> str:
    api_key = os.getenv("RUNPOD_API_KEY")
    if not api_key:
        raise SystemExit("RUNPOD_API_KEY not set")
    return api_key


def run_submit(payload_path: Path, endpoint_id: str, api_key: str) -> None:
    if not payload_path.exists():
        raise SystemExit(f"Payload not found: {payload_path}")

    payload = json.loads(payload_path.read_text())
    base = f"https://api.runpod.ai/v2/{endpoint_id}"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    resp = requests.post(f"{base}/run", headers=headers, json=payload, timeout=60)
    print("RUN HTTP", resp.status_code)
    print(resp.text)
    resp.raise_for_status()

    job_id = resp.json().get("id")
    if not job_id:
        raise SystemExit("No job id returned")

    print("JOB_ID", job_id)


def run_status(job_id: str, endpoint_id: str, api_key: str) -> None:
    base = f"https://api.runpod.ai/v2/{endpoint_id}"
    headers = {"Authorization": f"Bearer {api_key}"}
    resp = requests.get(f"{base}/status/{job_id}", headers=headers, timeout=30)
    print("STATUS HTTP", resp.status_code)
    print(resp.text)


def run_poll(job_id: str, endpoint_id: str, api_key: str, interval: float, max_polls: int) -> None:
    base = f"https://api.runpod.ai/v2/{endpoint_id}"
    headers = {"Authorization": f"Bearer {api_key}"}

    for i in range(1, max_polls + 1):
        time.sleep(interval)
        resp = requests.get(f"{base}/status/{job_id}", headers=headers, timeout=30)
        print(f"POLL {i} HTTP", resp.status_code)
        print(resp.text)
        if resp.status_code == 200:
            data = resp.json()
            if data.get("status") in {"COMPLETED", "FAILED", "CANCELLED"}:
                break


def run_update_image(endpoint_id: str, api_key: str, image_name: str) -> None:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    endpoint_url = f"https://rest.runpod.io/v1/endpoints/{endpoint_id}"
    endpoint_resp = requests.get(endpoint_url, headers=headers, timeout=30)
    print("Endpoint HTTP", endpoint_resp.status_code)
    endpoint_resp.raise_for_status()
    endpoint = endpoint_resp.json()

    template_id = endpoint.get("templateId") or (endpoint.get("template") or {}).get("id")
    if not template_id:
        raise SystemExit("Template ID not found for endpoint")

    current_image = (endpoint.get("template") or {}).get("imageName")
    print(json.dumps({"endpointId": endpoint_id, "templateId": template_id, "currentImage": current_image}, indent=2))

    update_url = f"https://rest.runpod.io/v1/templates/{template_id}"
    update_body = {"imageName": image_name}
    update_resp = requests.patch(update_url, headers=headers, json=update_body, timeout=30)
    print("Update HTTP", update_resp.status_code)
    update_resp.raise_for_status()

    updated = update_resp.json()
    print(json.dumps({"updatedTemplateId": updated.get("id"), "imageName": updated.get("imageName")}, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="RunPod helper CLI for submit/status/poll and image updates",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--env",
        default=str(REPO / ".env"),
        help="Path to .env file",
    )
    parser.add_argument(
        "--endpoint-id",
        default=None,
        help="Override RUNPOD_ENDPOINT_ID",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    submit_parser = subparsers.add_parser("submit", help="Submit a job from a payload JSON")
    submit_parser.add_argument("--payload", default=str(DEFAULT_PAYLOAD), help="Path to payload JSON")

    status_parser = subparsers.add_parser("status", help="Check job status")
    status_parser.add_argument("job_id", help="RunPod job id")

    poll_parser = subparsers.add_parser("poll", help="Poll job status")
    poll_parser.add_argument("job_id", help="RunPod job id")
    poll_parser.add_argument("--interval", type=float, default=10.0, help="Seconds between polls")
    poll_parser.add_argument("--max-polls", type=int, default=30, help="Maximum polls before exit")

    update_parser = subparsers.add_parser("update-image", help="Update endpoint template image")
    update_parser.add_argument("--image", default=DEFAULT_IMAGE, help="Docker image name")

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    load_env(Path(args.env))
    endpoint_id = get_endpoint_id(args.endpoint_id)
    api_key = get_api_key()

    if args.command == "submit":
        run_submit(Path(args.payload), endpoint_id, api_key)
        return 0
    if args.command == "status":
        run_status(args.job_id, endpoint_id, api_key)
        return 0
    if args.command == "poll":
        run_poll(args.job_id, endpoint_id, api_key, args.interval, args.max_polls)
        return 0
    if args.command == "update-image":
        run_update_image(endpoint_id, api_key, args.image)
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())
