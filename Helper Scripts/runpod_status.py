import os
import sys
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
        raise SystemExit("Usage: runpod_status.py <job_id>")

    job_id = sys.argv[1]
    load_env(REPO / ".env")

    api_key = os.getenv("RUNPOD_API_KEY")
    endpoint_id = os.getenv("RUNPOD_ENDPOINT_ID", "3zysuiunu9iacy")

    if not api_key:
        raise SystemExit("RUNPOD_API_KEY not set in .env")

    base = f"https://api.runpod.ai/v2/{endpoint_id}"
    headers = {"Authorization": f"Bearer {api_key}"}
    resp = requests.get(f"{base}/status/{job_id}", headers=headers, timeout=30)
    print("STATUS HTTP", resp.status_code)
    print(resp.text)


if __name__ == "__main__":
    main()
