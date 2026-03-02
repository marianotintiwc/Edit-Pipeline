from __future__ import annotations

import argparse
import csv
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Iterable

import requests

from .env import load_env_default
from .paths import repo_root


DEFAULT_LOG_GLOB = "*from_csv*.log"
DEFAULT_TIMEOUT_SECONDS = 60 * 60
DEFAULT_POLL_INTERVAL = 60.0


def register_cli(subparsers: argparse._SubParsersAction) -> None:
    rp_parser = subparsers.add_parser("runpod", help="RunPod utilities")
    rp_sub = rp_parser.add_subparsers(dest="command", required=True)

    monitor = rp_sub.add_parser("monitor", help="Monitor jobs from a log")
    monitor.add_argument("--log", default=None, help="Log file with submitted job ids")
    monitor.add_argument("--glob", default=DEFAULT_LOG_GLOB, help="Glob for latest log")
    monitor.add_argument("--interval", type=float, default=DEFAULT_POLL_INTERVAL, help="Seconds between polls")
    monitor.add_argument("--max-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS, help="Max monitoring time")
    monitor.add_argument("--output", default="status_report.json", help="JSON status output")
    monitor.add_argument("--monitor-log", default=None, help="Append summary lines to this file")
    monitor.add_argument("--endpoint-id", default=None, help="Override RUNPOD_ENDPOINT_ID")
    monitor.add_argument("--once", action="store_true", help="Check once and exit")
    monitor.set_defaults(func=cmd_monitor)

    retry = rp_sub.add_parser("retry-from-log", help="Build retry CSV from log")
    retry.add_argument("--log", default=None, help="Log file with submitted job ids")
    retry.add_argument("--glob", default=DEFAULT_LOG_GLOB, help="Glob for latest log")
    retry.add_argument("--csv", default=None, help="Source CSV to filter")
    retry.add_argument("--output", default=None, help="Retry CSV output path")
    retry.add_argument(
        "--scene-columns",
        default="scene 1,scene_1_lipsync,scene_1_lipsync_url,Scene_1,scene_1",
        help="Comma-separated scene1 columns for parent detection",
    )
    retry.add_argument("--endpoint-id", default=None, help="Override RUNPOD_ENDPOINT_ID")
    retry.add_argument("--resubmit", action="store_true", help="Run a resubmit script")
    retry.add_argument(
        "--resubmit-script",
        default="Helper Scripts/run_meli_from_users_csv.py",
        help="Script to resubmit with USERS_CSV_PATH",
    )
    retry.set_defaults(func=cmd_retry_from_log)


def cmd_monitor(args: argparse.Namespace) -> int:
    repo_dir = repo_root()
    load_env_default(repo_dir)

    api_key = os.environ.get("RUNPOD_API_KEY")
    endpoint_id = args.endpoint_id or os.environ.get("RUNPOD_ENDPOINT_ID")
    if not api_key or not endpoint_id:
        raise SystemExit("RUNPOD_API_KEY and RUNPOD_ENDPOINT_ID are required")

    log_path = resolve_log_path(args.log, args.glob, repo_dir)
    job_map = parse_jobs(log_path)
    if not job_map:
        raise SystemExit("No submitted jobs found in log.")

    output_path = resolve_path(args.output, repo_dir)
    monitor_log = resolve_path(args.monitor_log, repo_dir) if args.monitor_log else None

    pending = dict(job_map)
    deadline = time.time() + max(args.max_seconds, 0)

    while pending:
        statuses = {}
        for name, job_id in pending.items():
            statuses[job_id] = fetch_status(endpoint_id, api_key, job_id)

        summary = summarize_statuses(statuses)
        write_status_report(output_path, summary, statuses, job_map)

        line = " ".join(f"{k}={v}" for k, v in sorted(summary.items()))
        log_line(line, monitor_log)

        finished_ids = {jid for jid, status in statuses.items() if status in {"COMPLETED", "FAILED", "CANCELLED", "TIMED_OUT"}}
        pending = {name: jid for name, jid in pending.items() if jid not in finished_ids}

        if args.once:
            break
        if args.max_seconds > 0 and time.time() > deadline:
            break
        time.sleep(args.interval)

    return 0


def cmd_retry_from_log(args: argparse.Namespace) -> int:
    repo_dir = repo_root()
    load_env_default(repo_dir)

    api_key = os.environ.get("RUNPOD_API_KEY")
    endpoint_id = args.endpoint_id or os.environ.get("RUNPOD_ENDPOINT_ID")
    if not api_key or not endpoint_id:
        raise SystemExit("RUNPOD_API_KEY and RUNPOD_ENDPOINT_ID are required")

    log_path = resolve_log_path(args.log, args.glob, repo_dir)
    job_map = parse_jobs(log_path)
    if not job_map:
        raise SystemExit("No submitted jobs found in log.")

    failed_parents = fetch_failed_parents(job_map, endpoint_id, api_key)
    if not failed_parents:
        print("No failed jobs found.")
        return 0

    source_csv = resolve_source_csv(args.csv, repo_dir)
    output_csv = resolve_retry_output(args.output, repo_dir)
    scene_columns = [c.strip() for c in args.scene_columns.split(",") if c.strip()]

    build_retry_csv(source_csv, output_csv, failed_parents, scene_columns)
    print(f"Retry CSV: {output_csv}")

    if args.resubmit:
        resubmit_script = resolve_path(args.resubmit_script, repo_dir)
        if not resubmit_script.exists():
            raise SystemExit(f"Resubmit script not found: {resubmit_script}")
        env = os.environ.copy()
        env["USERS_CSV_PATH"] = str(output_csv)
        subprocess.run([sys.executable, str(resubmit_script)], check=False, env=env)

    return 0


def resolve_log_path(log_path: str | None, glob_pattern: str, repo_dir: Path) -> Path:
    if log_path:
        path = resolve_path(log_path, repo_dir)
        if not path.exists():
            raise SystemExit(f"Log not found: {path}")
        return path

    logs = sorted(repo_dir.glob(glob_pattern), key=lambda p: p.stat().st_mtime, reverse=True)
    if not logs:
        raise SystemExit(f"No log files found for glob: {glob_pattern}")
    return logs[0]


def resolve_path(value: str, repo_dir: Path) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = repo_dir / path
    return path


def parse_jobs(log_path: Path) -> dict[str, str]:
    job_map = {}
    pattern = re.compile(r"(.+?):\s+submitted\s+(\S+)")
    for line in log_path.read_text(encoding="utf-8").splitlines():
        match = pattern.search(line)
        if match:
            job_map[match.group(1).strip()] = match.group(2).strip()
            continue
        alt = re.search(r"submitted\s+(\S+)", line)
        if alt:
            job_map[alt.group(1).strip()] = alt.group(1).strip()
    return job_map


def fetch_status(endpoint_id: str, api_key: str, job_id: str) -> str:
    url = f"https://api.runpod.ai/v2/{endpoint_id}/status/{job_id}"
    headers = {"Authorization": f"Bearer {api_key}"}
    resp = requests.get(url, headers=headers, timeout=30)
    if resp.status_code != 200:
        return f"HTTP_{resp.status_code}"
    data = resp.json()
    return data.get("status", "UNKNOWN")


def summarize_statuses(statuses: dict[str, str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for status in statuses.values():
        counts[status] = counts.get(status, 0) + 1
    return counts


def write_status_report(output_path: Path, summary: dict, statuses: dict, job_map: dict) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "summary": summary,
        "statuses": statuses,
        "jobs": job_map,
    }
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def log_line(message: str, log_path: Path | None) -> None:
    stamp = time.strftime("%H:%M:%S")
    line = f"[{stamp}] {message}"
    print(line)
    if log_path:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")


def fetch_failed_parents(job_map: dict[str, str], endpoint_id: str, api_key: str) -> list[str]:
    headers = {"Authorization": f"Bearer {api_key}"}
    session = requests.Session()
    failed: list[str] = []
    for parent, job_id in job_map.items():
        try:
            resp = session.get(
                f"https://api.runpod.ai/v2/{endpoint_id}/status/{job_id}",
                headers=headers,
                timeout=(4, 10),
            )
            data = resp.json() if resp.status_code == 200 else {}
        except Exception:
            continue
        if data.get("status") == "FAILED":
            failed.append(parent)
    return failed


def resolve_source_csv(value: str | None, repo_dir: Path) -> Path:
    if value:
        path = resolve_path(value, repo_dir)
        if not path.exists():
            raise SystemExit(f"CSV not found: {path}")
        return path

    candidates = [
        repo_dir / "Files for Edit almost there - Algunos de MLM.csv",
        repo_dir / "USERS FILES FOR EDIT, MLA APPROVED.csv",
    ]
    for path in candidates:
        if path.exists():
            return path
    raise SystemExit("CSV not found; please pass --csv")


def resolve_retry_output(value: str | None, repo_dir: Path) -> Path:
    if value:
        return resolve_path(value, repo_dir)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return repo_dir / f"retry_failed_{timestamp}.csv"


def build_retry_csv(
    csv_path: Path,
    output_csv: Path,
    failed_parents: Iterable[str],
    scene_columns: list[str],
) -> None:
    failed_set = {p.strip() for p in failed_parents}
    with csv_path.open("r", encoding="utf-8", newline="") as f_in:
        reader = csv.reader(f_in)
        headers = next(reader, [])
        rows = []
        for values in reader:
            row = dict(zip(headers, values))
            scene1 = _pick_first(row, scene_columns)
            parent = parse_parent_from_scene_url(scene1)
            if parent in failed_set:
                rows.append(values)

    with output_csv.open("w", encoding="utf-8", newline="") as f_out:
        writer = csv.writer(f_out)
        writer.writerow(headers)
        writer.writerows(rows)


def parse_parent_from_scene_url(url: str) -> str:
    if not url:
        return ""
    match = re.search(r"/([^/]+)/[^/]+_scene_1(?:_lipsync)?\.mp4", url)
    if match:
        return match.group(1)
    return ""


def _pick_first(row: dict, keys: list[str]) -> str:
    for key in keys:
        value = (row.get(key) or "").strip()
        if value:
            return value
    return ""


