#!/usr/bin/env python3
"""
Local Batch Processor for TAP Videos
===================================
Runs TAP edits locally using ugc_pipeline.py with the sequence:
scene1 -> scene2 -> broll -> scene3 -> random endcard

Requirements:
- Dependencies from requirements.txt installed
- FFmpeg available
- GPU (optional but recommended)

Usage:
    python run_local_tap_batch.py --dry-run
    python run_local_tap_batch.py --start 0 --count 10
    python run_local_tap_batch.py --all
"""

import argparse
import csv
import json
import os
import random
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from typing import Dict, List, Optional

# ─────────────────────────────────────────────────────────────────────────────
# CONFIGURATION
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class LocalTapConfig:
    csv_path: str = "s3_assets_report.csv"
    tap_assets_csv: str = "TAP BROLL AND ENDCARDS - Hoja 1.csv"
    style_path: str = "config/style.json"
    output_dir: str = "TAP EXPORTS"
    temp_dir: str = "batch_temp/tap"

    # Music options (relative to script location)
    music_files: List[str] = None

    # Processing settings
    timeout_seconds: int = 1200  # 20 min per video

    def __post_init__(self):
        if self.music_files is None:
            self.music_files = [
                "assets/audio/music.mp3",
                "assets/audio/ROYALTY FREE Business Technology Music  Presentation Background Music Royalty Free by MUSIC4VIDEO - Music for Video Library.mp3",
                "assets/audio/ROYALTY FREE Corporate Background Music _ Upbeat Background Music Royalty Free by MUSIC4VIDEO - Music for Video Library.mp3",
                "assets/audio/ROYALTY FREE Event Presentation Music _ Chill Hop Instrumental Music Royalty Free by MUSIC4VIDEO - Music for Video Library.mp3",
                "assets/audio/ROYALTY FREE Presentation Background Music _ Tutorial Music Background Royalty Free by MUSIC4VIDEO - Music for Video Library.mp3",
            ]


@dataclass
class TapProject:
    name: str
    geo: str

    scene_1_url: Optional[str] = None
    scene_2_url: Optional[str] = None
    scene_3_url: Optional[str] = None

    scene_1_finished: bool = False
    scene_2_finished: bool = False
    scene_3_finished: bool = False

    @property
    def is_complete(self) -> bool:
        return self.scene_1_finished and self.scene_2_finished and self.scene_3_finished

    @property
    def project_number(self) -> int:
        try:
            return int(self.name.split("_tap")[0])
        except Exception:
            return 0


# ─────────────────────────────────────────────────────────────────────────────
# CSV PARSING
# ─────────────────────────────────────────────────────────────────────────────


def parse_tap_assets(tap_assets_csv: str) -> Dict[str, str]:
    assets = {}
    with open(tap_assets_csv, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            t = (row.get("TYPE") or "").strip().upper()
            link = (row.get("LINK") or "").strip()
            if t and link:
                assets[t] = link
    return assets


def parse_tap_projects(csv_path: str) -> Dict[str, TapProject]:
    projects: Dict[str, TapProject] = {}

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            folder = (row.get("Parent Folder") or "").strip()
            filename = (row.get("Filename") or "").strip()
            file_type = (row.get("Type") or "").strip().lower()
            url = (row.get("Public URL") or "").strip()
            finished = (row.get("Finished") or "").strip().lower() in ("yes", "true", "1")

            if "_tap" not in folder.lower():
                continue

            if file_type != "video" or "_lipsync.mp4" not in filename.lower():
                continue

            geo = "MLB"
            for g in ["MLB", "MLA", "MLM", "MLC"]:
                if f"-{g}" in folder.upper():
                    geo = g
                    break

            if folder not in projects:
                projects[folder] = TapProject(name=folder, geo=geo)

            project = projects[folder]
            fname_lower = filename.lower()
            if "scene_1_lipsync" in fname_lower:
                project.scene_1_url = url
                project.scene_1_finished = finished
            elif "scene_2_lipsync" in fname_lower:
                project.scene_2_url = url
                project.scene_2_finished = finished
            elif "scene_3_lipsync" in fname_lower:
                project.scene_3_url = url
                project.scene_3_finished = finished

    return projects


def get_complete_projects(projects: Dict[str, TapProject]) -> List[TapProject]:
    complete = [p for p in projects.values() if p.is_complete]
    return sorted(complete, key=lambda p: p.project_number)


# ─────────────────────────────────────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────────────────────────────────────


def select_random_music(config: LocalTapConfig, base_dir: str) -> str:
    available = []
    for m in config.music_files:
        full_path = os.path.join(base_dir, m)
        if os.path.exists(full_path):
            available.append(m)
    if not available:
        raise FileNotFoundError("No music files found in assets/audio")
    return random.choice(available)


def download_file(url: str, dest_path: str, timeout: int = 180) -> None:
    import requests

    print(f"      ⬇️  Downloading: {os.path.basename(dest_path)}")
    response = requests.get(url, stream=True, timeout=timeout)
    response.raise_for_status()
    with open(dest_path, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            f.write(chunk)


def generate_clips_json(scene_1: str, scene_2: str, broll: str, scene_3: str, output_path: str) -> None:
    clips_config = {
        "clips": [
            {"path": scene_1, "type": "scene", "start": None, "end": None},
            {"path": scene_2, "type": "scene", "start": None, "end": None},
            {"path": broll, "type": "broll", "start": None, "end": None},
            {"path": scene_3, "type": "scene", "start": None, "end": None},
        ]
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(clips_config, f, indent=2)


def build_style_override(style_path: str, endcard_url: str, temp_dir: str) -> str:
    with open(style_path, "r", encoding="utf-8") as f:
        style = json.load(f)

    endcard = style.get("endcard", {})
    endcard["enabled"] = True
    endcard["overlap_seconds"] = 0.5
    endcard["url"] = endcard_url
    style["endcard"] = endcard

    # Ensure 60fps interpolation enabled
    postprocess = style.get("postprocess", {})
    frame_interp = postprocess.get("frame_interpolation", {})
    frame_interp["enabled"] = True
    frame_interp["target_fps"] = 60
    postprocess["frame_interpolation"] = frame_interp
    style["postprocess"] = postprocess

    os.makedirs(temp_dir, exist_ok=True)
    override_path = os.path.join(temp_dir, "style_override.json")
    with open(override_path, "w", encoding="utf-8") as f:
        json.dump(style, f, indent=2)

    return override_path


# ─────────────────────────────────────────────────────────────────────────────
# JOB EXECUTION
# ─────────────────────────────────────────────────────────────────────────────


def run_local_job(project: TapProject, config: LocalTapConfig, assets: Dict[str, str], base_dir: str, idx: int) -> bool:
    start = time.time()

    temp_root = os.path.join(base_dir, config.temp_dir)
    os.makedirs(temp_root, exist_ok=True)
    temp_project_dir = os.path.join(temp_root, f"tap_{idx:04d}_{project.name}")
    os.makedirs(temp_project_dir, exist_ok=True)

    print(f"\n▶️  [{idx:04d}] {project.name} ({project.geo})")
    print(f"    📁 Temp: {temp_project_dir}")

    # Download scenes
    scene_1_path = os.path.join(temp_project_dir, "scene_1_lipsync.mp4")
    scene_2_path = os.path.join(temp_project_dir, "scene_2_lipsync.mp4")
    scene_3_path = os.path.join(temp_project_dir, "scene_3_lipsync.mp4")

    download_file(project.scene_1_url, scene_1_path)
    download_file(project.scene_2_url, scene_2_path)
    download_file(project.scene_3_url, scene_3_path)

    # Download broll
    broll_url = assets.get("BROLL")
    if not broll_url:
        raise RuntimeError("BROLL URL not found in TAP assets CSV")
    broll_path = os.path.join(temp_project_dir, "tap_broll.mov")
    download_file(broll_url, broll_path)

    # Random endcard
    endcard_candidates = [
        assets.get("ENDCARD-A"),
        assets.get("ENDCARD-B"),
        assets.get("ENDCARD-C"),
    ]
    endcard_candidates = [u for u in endcard_candidates if u]
    if not endcard_candidates:
        raise RuntimeError("No endcard URLs found in TAP assets CSV")
    endcard_url = random.choice(endcard_candidates)

    # Clips config
    clips_json_path = os.path.join(temp_project_dir, "clips.json")
    generate_clips_json(scene_1_path, scene_2_path, broll_path, scene_3_path, clips_json_path)

    # Style override
    style_override_path = build_style_override(os.path.join(base_dir, config.style_path), endcard_url, temp_project_dir)

    # Music
    music_rel = select_random_music(config, base_dir)
    music_path = os.path.join(base_dir, music_rel)

    # Output dir
    geo_output_dir = os.path.join(base_dir, config.output_dir, project.geo)
    os.makedirs(geo_output_dir, exist_ok=True)
    output_path = os.path.join(geo_output_dir, f"{project.name}_tap_edit.mp4")

    # Run pipeline
    pipeline_script = os.path.join(base_dir, "ugc_pipeline.py")
    cmd = [
        sys.executable,
        pipeline_script,
        "--clips_config", clips_json_path,
        "--music", music_path,
        "--style", style_override_path,
        "--output", output_path,
    ]

    env = {
        **os.environ,
        "CUDA_VISIBLE_DEVICES": "0",
        "PYTHONIOENCODING": "utf-8",
        "PYTHONUTF8": "1",
    }

    print(f"    🎵 Music: {os.path.basename(music_rel)}")
    print(f"    🧾 Endcard: {endcard_url.split('/')[-1]}")
    print(f"    🐍 Running local pipeline...")

    result = subprocess.run(
        cmd,
        cwd=base_dir,
        env=env,
        timeout=config.timeout_seconds
    )

    if result.returncode != 0:
        print(f"    ❌ Failed (exit code {result.returncode})")
        return False

    duration = time.time() - start
    print(f"    ✅ Done in {duration:.1f}s → {output_path}")
    return True


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="Run TAP batch locally")
    parser.add_argument("--dry-run", action="store_true", help="List jobs only")
    parser.add_argument("--start", type=int, default=0, help="Start index")
    parser.add_argument("--count", type=int, default=None, help="How many to run")
    parser.add_argument("--all", action="store_true", help="Run all")

    args = parser.parse_args()

    base_dir = os.path.dirname(os.path.abspath(__file__))
    config = LocalTapConfig()

    assets = parse_tap_assets(os.path.join(base_dir, config.tap_assets_csv))
    projects = parse_tap_projects(os.path.join(base_dir, config.csv_path))
    complete = get_complete_projects(projects)

    print("=" * 60)
    print("TAP Local Batch")
    print("=" * 60)
    print(f"Total TAP projects found: {len(projects)}")
    print(f"Complete (3 finished lipsync): {len(complete)}")

    if args.dry_run:
        for i, p in enumerate(complete):
            print(f"[{i:03d}] {p.name} (geo={p.geo})")
        return

    if not args.all and args.count is None:
        print("No --all or --count provided. Use --dry-run to preview.")
        return

    start = args.start
    count = args.count if args.count is not None else len(complete) - start
    end = min(start + count, len(complete))
    batch = complete[start:end]

    print(f"\nRunning jobs {start}..{end - 1} ({len(batch)} total)")

    success = 0
    for i, project in enumerate(batch, start=start):
        try:
            ok = run_local_job(project, config, assets, base_dir, i)
            success += 1 if ok else 0
        except Exception as e:
            print(f"    ❌ Error: {e}")

    print("=" * 60)
    print(f"Done. Success: {success}/{len(batch)}")


if __name__ == "__main__":
    main()
