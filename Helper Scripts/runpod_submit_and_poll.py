import os
import json
import time
from pathlib import Path

import requests

REPO = Path("/Users/marianotinti/Desktop/UGC EDITOR/Edit-Pipeline")
PAYLOAD_PATH = REPO / "assets" / "IGNOREASSETS" / "local_meli_first_row_payload.json"


def load_env(env_path: Path) -> None:
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        if not line.strip() or line.strip().startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def main() -> None:
    load_env(REPO / ".env")

    api_key = os.getenv("RUNPOD_API_KEY")
    endpoint_id = os.getenv("RUNPOD_ENDPOINT_ID", "3zysuiunu9iacy")

    if not api_key:
        raise SystemExit("RUNPOD_API_KEY not set in .env")

    if not PAYLOAD_PATH.exists():
        raise SystemExit(f"Payload not found: {PAYLOAD_PATH}")

    payload = json.loads(PAYLOAD_PATH.read_text())

    base = f"https://api.runpod.ai/v2/{endpoint_id}"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    run_resp = requests.post(f"{base}/run", headers=headers, json=payload, timeout=60)
    print("RUN HTTP", run_resp.status_code)
    print(run_resp.text)
    run_resp.raise_for_status()

    job_id = run_resp.json().get("id")
    if not job_id:
        raise SystemExit("No job id returned")

    print("JOB_ID", job_id)

    for i in range(1, 31):
        time.sleep(10)
        status_resp = requests.get(f"{base}/status/{job_id}", headers=headers, timeout=30)
        print(f"POLL {i} HTTP", status_resp.status_code)
        print(status_resp.text)
        if status_resp.status_code != 200:
            continue
        data = status_resp.json()
        if data.get("status") in {"COMPLETED", "FAILED", "CANCELLED"}:
            break


if __name__ == "__main__":
    main()
