import os
import sys
import time
from pathlib import Path
import requests

REPO = Path("/Users/marianotinti/Desktop/UGC EDITOR/Edit-Pipeline")


def load_env(env_path: Path) -> None:
    if not env_path.exists():
        return
    for line in env_path.read_text().splitlines():
        if not line.strip() or line.strip().startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("Usage: runpod_poll.py <job_id> [interval_seconds] [max_polls]")

    job_id = sys.argv[1]
    interval = float(sys.argv[2]) if len(sys.argv) > 2 else 10.0
    max_polls = int(sys.argv[3]) if len(sys.argv) > 3 else 30

    load_env(REPO / ".env")

    api_key = os.getenv("RUNPOD_API_KEY")
    endpoint_id = os.getenv("RUNPOD_ENDPOINT_ID", "3zysuiunu9iacy")

    if not api_key:
        raise SystemExit("RUNPOD_API_KEY not set in .env")

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


if __name__ == "__main__":
    main()
