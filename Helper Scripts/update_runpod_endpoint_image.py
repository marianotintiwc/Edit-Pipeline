import os
import json
from pathlib import Path
import requests

REPO = Path("/Users/marianotinti/Desktop/UGC EDITOR/Edit-Pipeline")
TARGET_IMAGE = "docker.io/marianotintiwc/edit-pipeline:v1.12"


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
    endpoint_id = os.getenv("RUNPOD_ENDPOINT_ID")

    if not api_key or not endpoint_id:
        raise SystemExit("RUNPOD_API_KEY or RUNPOD_ENDPOINT_ID not set in .env")

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
    update_body = {"imageName": TARGET_IMAGE}
    update_resp = requests.patch(update_url, headers=headers, json=update_body, timeout=30)
    print("Update HTTP", update_resp.status_code)
    update_resp.raise_for_status()

    updated = update_resp.json()
    print(json.dumps({"updatedTemplateId": updated.get("id"), "imageName": updated.get("imageName")}, indent=2))


if __name__ == "__main__":
    main()
