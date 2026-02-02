#!/usr/bin/env python3
"""Check RunPod job status for the 14 missing user outputs."""

import os
from pathlib import Path
import requests

REPO = Path("/Users/marianotinti/Desktop/UGC EDITOR/Edit-Pipeline")

# Job IDs from the last resubmit (with NFD-encoded URLs)
JOB_IDS = {
    "82_15_000_de_descuento-MLA-female": "9838a8a9-5cd1-4160-bdb8-66e103d51e62-u2",
    "1_tarjeta_prepaga-MLA-female": "73799b13-4a73-405c-9985-d57d3f6fd735-u2",
    "1_tarjeta_prepaga_de_mercado_pago-MLA-male": "25dfcf6f-fb4b-4cbf-8045-ac86fc866d27-u2",
    "29_tarjeta_prepaga-MLA-male": "c77c1484-c83b-4d77-b866-dec6d2d34fd4-u2",
    "2_tarjeta_prepaga-MLA-male": "d409debe-2133-4164-915b-f59f960c5ad4-u2",
    "41_tarjeta_prepaga-MLA-female": "c2e1fd45-44a0-4a95-99a5-b4ea22372cef-u2",
    "42_tarjeta_prepaga-MLA-male": "69924664-d64b-4981-8b85-abe6c217b4c8-u1",
    "43_tarjeta_prepaga-MLA-female": "59b844fb-7e34-4679-b959-a68eaa9ee155-u1",
    "46_tarjeta_prepaga-MLA-male": "fc0593d3-78c0-467a-8873-094ba545b267-u2",
    "48_tarjeta_prepaga-MLA-female": "2b4702bd-86e7-4c5f-b9fe-931ac369a6ea-u2",
    "50_tarjeta_prepaga-MLA-male": "987ef9ce-d89c-4089-8c9c-2d9439bec3ec-u2",
    "51_tarjeta_prepaga-MLA-female": "f1ce0af3-2e96-4516-95d7-e2823519dbb7-u1",
    "53_tarjeta_prepaga-MLA-male": "45d2a844-f20a-415b-a1ac-ec967eaeb705-u2",
    "57_tarjeta_prepaga-MLA-female": "10e0e811-beaf-4f3e-a65d-cbd036286b50-u1",
}


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
    endpoint_id = "h55ft9cy7fyi1d"

    if not api_key:
        raise SystemExit("RUNPOD_API_KEY not set in .env")

    base = f"https://api.runpod.ai/v2/{endpoint_id}"
    headers = {"Authorization": f"Bearer {api_key}"}

    print(f"Checking {len(JOB_IDS)} jobs on endpoint {endpoint_id}\n")

    for name, job_id in JOB_IDS.items():
        resp = requests.get(f"{base}/status/{job_id}", headers=headers, timeout=30)
        if resp.status_code == 200:
            data = resp.json()
            status = data.get("status", "UNKNOWN")
            error = ""
            if status == "FAILED":
                out = data.get("output", {})
                if isinstance(out, dict):
                    error = out.get("error", "")
                elif isinstance(out, str):
                    error = out
                # Also check for error in root
                if not error:
                    error = data.get("error", "")
            print(f"{name}: {status}" + (f" | {error[:200]}" if error else ""))
        else:
            print(f"{name}: HTTP {resp.status_code} | {resp.text[:100]}")


if __name__ == "__main__":
    main()
