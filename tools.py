#!/usr/bin/env python3
"""
=============================================================================
MELI/MLB Video Pipeline Tools
=============================================================================
Unified CLI for common pipeline operations.

Usage:
    python tools.py <command> [options]

Commands:
    mapping         Generate MLB edit mapping (scenes + B-roll + Endcard)
    assets          Generate MELI video asset map
    batch-runpod    Run batch processing on RunPod (cloud GPU)
    batch-local     Run batch processing locally
    status          Check batch progress from log files

Examples:
    python tools.py mapping
    python tools.py assets
    python tools.py batch-runpod --workers 3 --filter even
    python tools.py batch-runpod --workers 3 --filter odd
    python tools.py batch-runpod --workers 3 --filter all
    python tools.py batch-runpod --workers 3 --filter "2,4,6,8"
    python tools.py batch-local --folder "2_incentivos-MLB-male"
    python tools.py status
"""

import argparse
import csv
import json
import os
import re
import sys
import time
import threading
import queue
from datetime import datetime
from collections import defaultdict
from typing import Optional, Dict, List, Tuple
from pathlib import Path

# Load .env
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# ============================================================================
# SHARED CONFIGURATION
# ============================================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

class Config:
    """Shared configuration for all tools"""
    # API Settings
    api_key: str = os.environ.get("RUNPOD_API_KEY", "")
    endpoint_id: str = os.environ.get("RUNPOD_ENDPOINT_ID", "3zysuiunu9iacy")
    
    # File paths
    mlb_mapping_csv: str = "mlb_edit_mapping_s3.csv"
    s3_assets_report: str = "s3_assets_report_4.csv"
    broll_endcard_csv: str = "MELI USERS BROLLS AND ENDCARDS - Hoja 1.csv"
    meli_assets_report: str = "MELI USERS ASSETS REPORT.csv"
    
    # Output settings
    s3_output_folder: str = "MLB_Exports/2026-01"
    
    # Batch settings
    max_workers: int = 3
    poll_interval: int = 15
    
    # MELI Style (subtitle settings at TOP LEVEL, not nested!)
    style_overrides = {
        "font": "/app/assets/fonts/MELIPROXIMANOVAA-BOLD.OTF",
        "fontsize": 60,
        "stroke_color": "#333333",
        "stroke_width": 10,
        "highlight": {
            "color": "#333333",
            "stroke_color": "#333333",
            "stroke_width": 4
        },
        "endcard": {"enabled": True, "overlap_seconds": 0.5},
        "endcard_alpha_fill": {
            "enabled": True,
            "force_chroma_key": True,
            "chroma_key_color": "0x000000",
            "chroma_key_similarity": 0.15,
            "chroma_key_blend": 0.05,
            "edge_feather": 3,
            "blur_sigma": 60,
            "slow_factor": 1.5
        },
        "interpolation": {"enabled": True, "target_fps": 60},
        "postprocess": {"color_grading": {"enabled": False}},
        "transcription": {"model": "large"}
    }


# ============================================================================
# VALUE PROP NORMALIZATION
# ============================================================================

VALUE_PROP_MAP = {
    'tarjeta_de_debito': 'Tarjeta de Débito',
    'tarjeta_de_credito': 'Tarjeta de Crédito',
    'rendimientos': 'Rendimientos',
    'prestamo_personal': 'Préstamo Personal',
    'lucky_winner': 'Lucky Winner',
    'incentivos': 'Incentivos',
    'servicios': 'Servicios',
    'credits_cuotas_sin_tarjeta': 'Cuotas Sin Tarjeta',
    'cuotas_sin_tarjeta': 'Cuotas Sin Tarjeta',
    'pix': 'Pix',
    'pix_na_credito': 'Pix na Crédito',
    'cofrinhos': 'Cofrinhos',
    'qr': 'QR',
}

def normalize_value_prop(raw: str) -> str:
    return VALUE_PROP_MAP.get(raw.lower(), raw.replace('_', ' ').title())


def parse_folder_name(folder: str) -> Optional[dict]:
    """Parse folder like: 89_pix_na_credito-MLB-female"""
    clean = re.sub(r'_tap$', '', folder, flags=re.IGNORECASE)
    match = re.match(r'^(\d+)_([^-]+)-([A-Z]{3})-(\w+)$', clean)
    if match:
        return {
            'id': match.group(1),
            'raw': match.group(2),
            'geo': match.group(3),
            'gender': match.group(4)
        }
    return None


# ============================================================================
# TOOL 1: GENERATE MLB EDIT MAPPING
# ============================================================================

def cmd_mapping(args):
    """Generate MLB edit mapping from S3 assets report"""
    print("=" * 60)
    print("🗺️  GENERATE MLB EDIT MAPPING")
    print("=" * 60)
    
    assets_path = os.path.join(BASE_DIR, args.assets or Config.s3_assets_report)
    map_path = os.path.join(BASE_DIR, args.broll_map or Config.broll_endcard_csv)
    out_path = os.path.join(BASE_DIR, args.output or Config.mlb_mapping_csv)
    
    print(f"📂 Assets report: {assets_path}")
    print(f"📂 B-roll/Endcard map: {map_path}")
    print(f"📂 Output: {out_path}")
    print()
    
    # Load B-roll/Endcard mapping
    broll_endcard_map = {}
    with open(map_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            geo = (row.get('GEO') or '').strip()
            vp = (row.get('Propuesta de Valor') or '').strip()
            broll = (row.get('Link B-Roll') or '').strip()
            endcard = (row.get('Link Endcard') or '').strip()
            if not geo or not vp:
                continue
            if broll.upper() == 'N/A':
                broll = ''
            if endcard.upper() == 'N/A':
                endcard = ''
            broll_endcard_map[(geo, vp)] = {'broll': broll, 'endcard': endcard}
    
    print(f"✅ Loaded {len(broll_endcard_map)} B-roll/Endcard mappings")
    
    # Load S3 assets
    assets_by_folder = defaultdict(list)
    with open(assets_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            folder = (row.get('Parent Folder') or '').strip()
            finished = (row.get('Finished') or '').strip()
            filename = (row.get('Filename') or '').strip()
            url = (row.get('Public URL') or '').strip()
            if finished == 'YES':
                assets_by_folder[folder].append({'filename': filename, 'url': url})
    
    print(f"✅ Loaded assets for {len(assets_by_folder)} folders")
    
    # Filter for complete projects
    def has_all_scenes(assets):
        filenames = [a['filename'] for a in assets]
        return all(
            any(f'scene_{i}' in fn and 'lipsync' in fn for fn in filenames)
            for i in [1, 2, 3]
        )
    
    def get_scene_url(assets, scene_num):
        for a in assets:
            if f'scene_{scene_num}' in a['filename'] and 'lipsync' in a['filename']:
                return a['url']
        return ''
    
    # Build results
    results = []
    for folder, assets in sorted(assets_by_folder.items()):
        if 'MLB' not in folder:
            continue
        if not has_all_scenes(assets):
            continue
        
        meta = parse_folder_name(folder)
        if not meta:
            print(f"⚠️  Could not parse: {folder}")
            continue
        
        vp_norm = normalize_value_prop(meta['raw'])
        broll_endcard = broll_endcard_map.get((meta['geo'], vp_norm), {})
        
        results.append({
            'ParentFolder': folder,
            'Geo': meta['geo'],
            'ValueProp': vp_norm,
            'Gender': meta['gender'],
            'Scene1_URL': get_scene_url(assets, 1),
            'Scene2_URL': get_scene_url(assets, 2),
            'Scene3_URL': get_scene_url(assets, 3),
            'Broll_URL': broll_endcard.get('broll', ''),
            'Endcard_URL': broll_endcard.get('endcard', ''),
        })
    
    # Export
    fieldnames = ['ParentFolder', 'Geo', 'ValueProp', 'Gender',
                  'Scene1_URL', 'Scene2_URL', 'Scene3_URL',
                  'Broll_URL', 'Endcard_URL']
    
    with open(out_path, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)
    
    print(f"\n✅ Exported {len(results)} MLB folders to: {out_path}")
    
    # Summary
    vp_counts = defaultdict(int)
    for r in results:
        vp_counts[r['ValueProp']] += 1
    
    print("\n📊 Summary by Value Proposition:")
    for vp, count in sorted(vp_counts.items(), key=lambda x: -x[1]):
        print(f"   {vp}: {count}")
    
    return 0


# ============================================================================
# TOOL 2: GENERATE MELI VIDEO ASSET MAP
# ============================================================================

def cmd_assets(args):
    """Generate MELI video asset map"""
    print("=" * 60)
    print("📦 GENERATE MELI VIDEO ASSET MAP")
    print("=" * 60)
    
    try:
        from meli_assets_mapper import (
            get_assets_for_project,
            load_broll_endcard_mapping,
        )
    except ImportError:
        print("❌ Could not import meli_assets_mapper. Make sure it exists.")
        return 1
    
    report_csv = os.path.join(BASE_DIR, args.report or Config.meli_assets_report)
    mapping_csv = os.path.join(BASE_DIR, args.mapping or Config.broll_endcard_csv)
    output_csv = os.path.join(BASE_DIR, args.output or "meli_video_asset_map.csv")
    
    print(f"📂 Assets report: {report_csv}")
    print(f"📂 B-roll/Endcard map: {mapping_csv}")
    print(f"📂 Output: {output_csv}")
    print()
    
    mapping = load_broll_endcard_mapping(mapping_csv)
    cache_dir = os.path.join(BASE_DIR, "assets", "meli_cache")
    
    fieldnames = [
        "Parent Folder", "Filename", "Video URL", "Finished",
        "Project ID", "Value Prop Raw", "Value Prop Normalized",
        "GEO", "Gender", "Broll URL", "Endcard URL",
        "Broll Cached Path", "Endcard Cached Path", "Mapping Found",
    ]
    
    rows_written = 0
    
    def iter_video_rows():
        with open(report_csv, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                folder = (row.get("Parent Folder") or "").strip()
                filename = (row.get("Filename") or "").strip()
                file_type = (row.get("Type") or "").strip().lower()
                url = (row.get("Public URL") or "").strip()
                finished = (row.get("Finished") or "").strip()
                
                if not folder or not filename:
                    continue
                if "_tap" in folder.lower():
                    continue
                if file_type != "video":
                    continue
                
                yield {"folder": folder, "filename": filename, "url": url, "finished": finished}
    
    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        for row in iter_video_rows():
            folder = row["folder"]
            result = get_assets_for_project(folder, mapping, use_cache=True, base_cache_dir=cache_dir)
            
            metadata = assets = None
            cached_paths = {"broll": None, "endcard": None}
            
            if result:
                metadata, assets, cached_paths = result
            
            writer.writerow({
                "Parent Folder": folder,
                "Filename": row["filename"],
                "Video URL": row["url"],
                "Finished": row["finished"],
                "Project ID": getattr(metadata, "project_id", ""),
                "Value Prop Raw": getattr(metadata, "value_prop_raw", ""),
                "Value Prop Normalized": getattr(metadata, "value_prop_normalized", ""),
                "GEO": getattr(metadata, "geo", ""),
                "Gender": getattr(metadata, "gender", ""),
                "Broll URL": getattr(assets, "broll_url", ""),
                "Endcard URL": getattr(assets, "endcard_url", ""),
                "Broll Cached Path": cached_paths.get("broll") or "",
                "Endcard Cached Path": cached_paths.get("endcard") or "",
                "Mapping Found": "YES" if assets else "NO",
            })
            rows_written += 1
    
    print(f"\n✅ Wrote {rows_written} rows to {output_csv}")
    return 0


# ============================================================================
# TOOL 3: BATCH RUNPOD PROCESSING
# ============================================================================

# Shared state for batch processing
print_lock = threading.Lock()
stats_lock = threading.Lock()
stats = {'completed': 0, 'failed': 0, 'total': 0, 'start_time': None, 'results': []}
LOG_FILE = None
PROGRESS_FILE = None


def init_logging(prefix: str = "batch"):
    """Initialize log files"""
    global LOG_FILE, PROGRESS_FILE
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    LOG_FILE = os.path.join(BASE_DIR, f"{prefix}_log_{timestamp}.txt")
    PROGRESS_FILE = os.path.join(BASE_DIR, f"{prefix}_progress_{timestamp}.json")
    
    with open(LOG_FILE, 'w', encoding='utf-8') as f:
        f.write(f"=== Batch Started at {datetime.now().isoformat()} ===\n")
    
    print(f"📝 Logging to: {LOG_FILE}")
    print(f"📊 Progress file: {PROGRESS_FILE}")


def log(msg: str):
    """Thread-safe logging"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    full_msg = f"[{timestamp}] {msg}"
    
    with print_lock:
        print(full_msg)
        if LOG_FILE:
            try:
                with open(LOG_FILE, 'a', encoding='utf-8') as f:
                    f.write(full_msg + "\n")
            except:
                pass


def save_progress():
    """Save current progress to JSON"""
    if not PROGRESS_FILE:
        return
    try:
        with stats_lock:
            progress = {
                'timestamp': datetime.now().isoformat(),
                'completed': stats['completed'],
                'failed': stats['failed'],
                'total': stats['total'],
                'elapsed_seconds': time.time() - stats['start_time'] if stats['start_time'] else 0,
                'results': stats['results']
            }
        with open(PROGRESS_FILE, 'w', encoding='utf-8') as f:
            json.dump(progress, f, indent=2)
    except:
        pass


def convert_drive_to_direct_url(url: str) -> Optional[str]:
    """Convert Google Drive URL to direct download"""
    if not url:
        return None
    if url.startswith('https://s3.') or 'amazonaws.com' in url:
        return url
    match = re.search(r'/d/([a-zA-Z0-9_-]+)', url)
    if match:
        return f"https://drive.google.com/uc?export=download&id={match.group(1)}"
    return url if 'uc?export=download' in url else None


def load_mlb_projects(csv_path: str) -> list:
    """Load MLB projects from mapping CSV"""
    projects = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            folder = row.get('ParentFolder', '').strip()
            match = re.match(r'^(\d+)_', folder)
            projects.append({
                'folder': folder,
                'project_num': int(match.group(1)) if match else 0,
                'geo': row.get('Geo', 'MLB').strip(),
                'value_prop': row.get('ValueProp', '').strip(),
                'gender': row.get('Gender', '').strip(),
                'scene1_url': row.get('Scene1_URL', '').strip(),
                'scene2_url': row.get('Scene2_URL', '').strip(),
                'scene3_url': row.get('Scene3_URL', '').strip(),
                'broll_url': row.get('Broll_URL', '').strip(),
                'endcard_url': row.get('Endcard_URL', '').strip(),
            })
    return projects


def generate_job_payload(project: dict, config: Config) -> dict:
    """Generate RunPod job payload"""
    broll_direct = convert_drive_to_direct_url(project['broll_url'])
    endcard_direct = convert_drive_to_direct_url(project['endcard_url'])
    style = dict(config.style_overrides)
    style['endcard'] = {**style.get('endcard', {}), 'url': endcard_direct}
    
    # Build clips list - include endcard as a clip so it gets downloaded by handler
    clips = [
        {"type": "scene", "url": project['scene1_url']},
        {"type": "scene", "url": project['scene2_url']},
        {"type": "broll", "url": broll_direct},
        {"type": "scene", "url": project['scene3_url']},
    ]
    
    # Add endcard as a clip (handler will download it and include in clips.json)
    if endcard_direct:
        clips.append({"type": "endcard", "url": endcard_direct})
    
    return {
        "input": {
            "job_id": f"mlb_{project['folder']}",
            "geo": project['geo'],
            "output_folder": config.s3_output_folder,
            "output_filename": f"{project['folder']}_MELI_EDIT.mp4",
            "clips": clips,
            "music_url": "random",
            "subtitle_mode": "auto",
            "edit_preset": "standard_vertical",
            "style_overrides": style
        }
    }


class RunPodClient:
    def __init__(self, api_key: str, endpoint_id: str):
        self.base_url = f"https://api.runpod.ai/v2/{endpoint_id}"
        self.headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    
    def submit_job(self, payload: dict) -> dict:
        import requests
        r = requests.post(f"{self.base_url}/run", json=payload, headers=self.headers)
        r.raise_for_status()
        return r.json()
    
    def get_job_status(self, job_id: str) -> dict:
        import requests
        r = requests.get(f"{self.base_url}/status/{job_id}", headers=self.headers)
        r.raise_for_status()
        return r.json()


def worker_runpod(worker_id: int, job_queue: queue.Queue, client: RunPodClient, config: Config):
    """RunPod batch worker"""
    while True:
        try:
            project = job_queue.get(timeout=1)
        except queue.Empty:
            if job_queue.empty():
                log(f"🏁 Worker {worker_id} finished - no more jobs")
                return
            continue
        
        folder = project['folder']
        short_name = folder[:30] + "..." if len(folder) > 30 else folder
        
        log(f"🚀 Worker {worker_id} | Starting #{project['project_num']}: {short_name}")
        
        try:
            payload = generate_job_payload(project, config)
            start_time = time.time()
            
            result = client.submit_job(payload)
            runpod_id = result.get("id")
            log(f"✅ Worker {worker_id} | #{project['project_num']} submitted: {runpod_id}")
            
            last_status = ""
            while True:
                time.sleep(config.poll_interval)
                elapsed = time.time() - start_time
                
                try:
                    status = client.get_job_status(runpod_id)
                    job_status = status.get("status", "UNKNOWN")
                    
                    if job_status != last_status:
                        log(f"   Worker {worker_id} | #{project['project_num']} [{elapsed:.0f}s]: {job_status}")
                        last_status = job_status
                    
                    if job_status == "COMPLETED":
                        output = status.get("output", {})
                        elapsed_final = time.time() - start_time
                        
                        with stats_lock:
                            stats['completed'] += 1
                            stats['results'].append({
                                'folder': folder,
                                'project_num': project['project_num'],
                                'status': 'COMPLETED',
                                'elapsed': elapsed_final,
                                'output_url': output.get('output_url', 'N/A'),
                                'runpod_id': runpod_id
                            })
                            c, f, t = stats['completed'], stats['failed'], stats['total']
                        
                        log(f"✅ Worker {worker_id} | #{project['project_num']} COMPLETED in {elapsed_final:.1f}s")
                        log(f"   URL: {output.get('output_url', 'N/A')}")
                        log(f"📊 Progress: {c + f}/{t} done ({c} ✅, {f} ❌)")
                        save_progress()
                        break
                        
                    elif job_status == "FAILED":
                        error = status.get("error", "Unknown error")
                        elapsed_final = time.time() - start_time
                        
                        with stats_lock:
                            stats['failed'] += 1
                            stats['results'].append({
                                'folder': folder,
                                'project_num': project['project_num'],
                                'status': 'FAILED',
                                'elapsed': elapsed_final,
                                'error': error,
                                'runpod_id': runpod_id
                            })
                            c, f, t = stats['completed'], stats['failed'], stats['total']
                        
                        log(f"❌ Worker {worker_id} | #{project['project_num']} FAILED: {error}")
                        log(f"📊 Progress: {c + f}/{t} done ({c} ✅, {f} ❌)")
                        save_progress()
                        break
                        
                except Exception as e:
                    log(f"⚠️ Worker {worker_id} | #{project['project_num']} poll error: {e}")
                    
        except Exception as e:
            log(f"❌ Worker {worker_id} | #{project['project_num']} error: {e}")
            with stats_lock:
                stats['failed'] += 1
                stats['results'].append({
                    'folder': folder,
                    'project_num': project['project_num'],
                    'status': 'FAILED',
                    'error': str(e),
                    'elapsed': 0
                })
            save_progress()
        
        finally:
            job_queue.task_done()


def cmd_batch_runpod(args):
    """Run batch processing on RunPod"""
    global stats
    
    config = Config()
    config.max_workers = args.workers
    
    # Override CSV file if specified
    if args.csv:
        config.mlb_mapping_csv = args.csv
    
    # Override output folder if specified
    if args.output_folder:
        config.s3_output_folder = args.output_folder
    
    if not config.api_key:
        print("❌ RUNPOD_API_KEY not set. Set it in .env file or environment.")
        return 1
    
    init_logging("runpod_batch")
    
    print("=" * 70)
    print("🚀 BATCH PROCESS: RUNPOD SERVERLESS")
    print(f"   Workers: {config.max_workers} | Poll interval: {config.poll_interval}s")
    print(f"   Filter: {args.filter}")
    print(f"   CSV: {config.mlb_mapping_csv}")
    print(f"   Output folder: {config.s3_output_folder}")
    print("=" * 70)
    
    # Load projects
    projects = load_mlb_projects(os.path.join(BASE_DIR, config.mlb_mapping_csv))
    
    # Apply filter
    if args.filter == "even":
        filtered = [p for p in projects if p['project_num'] % 2 == 0]
    elif args.filter == "odd":
        filtered = [p for p in projects if p['project_num'] % 2 == 1]
    elif args.filter == "all":
        filtered = projects
    elif "," in args.filter:
        nums = [int(x.strip()) for x in args.filter.split(",")]
        filtered = [p for p in projects if p['project_num'] in nums]
    else:
        try:
            num = int(args.filter)
            filtered = [p for p in projects if p['project_num'] == num]
        except ValueError:
            filtered = [p for p in projects if args.filter.lower() in p['folder'].lower()]
    
    filtered.sort(key=lambda x: x['project_num'])
    
    if not filtered:
        print("❌ No projects match the filter")
        return 1
    
    print(f"\n📋 Found {len(filtered)} projects:")
    for p in filtered[:10]:
        print(f"   #{p['project_num']:3d}: {p['folder']}")
    if len(filtered) > 10:
        print(f"   ... and {len(filtered) - 10} more")
    
    if not args.yes:
        confirm = input(f"\n▶️  Process {len(filtered)} projects with {config.max_workers} workers? [y/N]: ")
        if confirm.lower() != 'y':
            print("Cancelled.")
            return 0
    
    # Reset stats
    stats = {'completed': 0, 'failed': 0, 'total': len(filtered), 'start_time': time.time(), 'results': []}
    
    # Create queue and client
    job_queue = queue.Queue()
    for p in filtered:
        job_queue.put(p)
    
    client = RunPodClient(config.api_key, config.endpoint_id)
    
    # Start workers
    threads = []
    for i in range(config.max_workers):
        t = threading.Thread(target=worker_runpod, args=(i + 1, job_queue, client, config))
        t.start()
        threads.append(t)
        time.sleep(0.5)
    
    # Wait for completion
    for t in threads:
        t.join()
    
    # Summary
    total_time = time.time() - stats['start_time']
    print("\n" + "=" * 70)
    print("BATCH COMPLETE")
    print("=" * 70)
    print(f"Total time: {total_time:.1f}s ({total_time/60:.1f} min)")
    print(f"Completed: {stats['completed']}/{stats['total']}")
    print(f"Failed: {stats['failed']}/{stats['total']}")
    
    # Save final results
    results_file = os.path.join(BASE_DIR, f"batch_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    with open(results_file, 'w') as f:
        json.dump({'total_time': total_time, **stats}, f, indent=2)
    print(f"\n💾 Results saved to: {results_file}")
    
    return 0 if stats['failed'] == 0 else 1


# ============================================================================
# TOOL 4: BATCH LOCAL PROCESSING
# ============================================================================

def cmd_batch_local(args):
    """Run batch processing locally"""
    print("=" * 70)
    print("🖥️  BATCH PROCESS: LOCAL")
    print("=" * 70)
    
    # Check if handler exists
    handler_path = os.path.join(BASE_DIR, "handler.py")
    if not os.path.exists(handler_path):
        print("❌ handler.py not found. Cannot run local processing.")
        return 1
    
    # Import the handler
    import sys
    sys.path.insert(0, BASE_DIR)
    
    try:
        from handler import handler
    except ImportError as e:
        print(f"❌ Could not import handler: {e}")
        return 1
    
    config = Config()
    projects = load_mlb_projects(os.path.join(BASE_DIR, config.mlb_mapping_csv))
    
    # Find the project
    if args.folder:
        matches = [p for p in projects if args.folder.lower() in p['folder'].lower()]
        if not matches:
            print(f"❌ No project found matching: {args.folder}")
            return 1
        project = matches[0]
    elif args.number:
        matches = [p for p in projects if p['project_num'] == args.number]
        if not matches:
            print(f"❌ No project found with number: {args.number}")
            return 1
        project = matches[0]
    else:
        print("❌ Specify --folder or --number")
        return 1
    
    print(f"📂 Processing: {project['folder']}")
    print(f"   Geo: {project['geo']}")
    print(f"   Value Prop: {project['value_prop']}")
    print()
    
    # Generate payload
    payload = generate_job_payload(project, config)
    
    # For local, adjust output to local path
    payload['input']['output_folder'] = os.path.join(BASE_DIR, "local_outputs")
    os.makedirs(payload['input']['output_folder'], exist_ok=True)
    
    print("🚀 Starting local processing...")
    start_time = time.time()
    
    try:
        result = handler(payload)
        elapsed = time.time() - start_time
        
        if result.get('status') == 'success':
            print(f"\n✅ COMPLETED in {elapsed:.1f}s")
            print(f"   Output: {result.get('output_url', 'N/A')}")
        else:
            print(f"\n❌ FAILED: {result.get('error', 'Unknown')}")
            return 1
            
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        return 1
    
    return 0


# ============================================================================
# TOOL 5: CHECK STATUS
# ============================================================================

def cmd_status(args):
    """Check batch progress from log files"""
    print("=" * 60)
    print("📊 BATCH STATUS CHECK")
    print("=" * 60)
    
    # Find latest progress file
    progress_files = sorted(Path(BASE_DIR).glob("*_progress_*.json"), key=lambda x: x.stat().st_mtime, reverse=True)
    log_files = sorted(Path(BASE_DIR).glob("*_log_*.txt"), key=lambda x: x.stat().st_mtime, reverse=True)
    
    if not progress_files:
        print("❌ No progress files found")
        return 1
    
    latest_progress = progress_files[0]
    print(f"📂 Latest progress file: {latest_progress.name}")
    
    with open(latest_progress, 'r') as f:
        progress = json.load(f)
    
    print(f"\n📊 Status at: {progress.get('timestamp', 'N/A')}")
    print(f"   Completed: {progress.get('completed', 0)}/{progress.get('total', 0)}")
    print(f"   Failed: {progress.get('failed', 0)}/{progress.get('total', 0)}")
    print(f"   Elapsed: {progress.get('elapsed_seconds', 0):.0f}s")
    
    if args.tail and log_files:
        latest_log = log_files[0]
        print(f"\n📝 Last {args.tail} lines from {latest_log.name}:")
        print("-" * 60)
        with open(latest_log, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            for line in lines[-args.tail:]:
                print(line.rstrip())
    
    return 0


# ============================================================================
# MAIN CLI
# ============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="MELI/MLB Video Pipeline Tools",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python tools.py mapping                          # Generate MLB edit mapping
    python tools.py assets                           # Generate MELI asset map
    python tools.py batch-runpod --filter even       # Process even-numbered projects
    python tools.py batch-runpod --filter odd        # Process odd-numbered projects  
    python tools.py batch-runpod --filter "2,4,6"    # Process specific projects
    python tools.py batch-runpod --filter all -y     # Process all (skip confirm)
    python tools.py batch-local --folder "2_incentivos-MLB-male"
    python tools.py status --tail 20                 # Check progress
        """
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # MAPPING command
    p_map = subparsers.add_parser("mapping", help="Generate MLB edit mapping")
    p_map.add_argument("--assets", help="S3 assets report CSV")
    p_map.add_argument("--broll-map", help="B-roll/Endcard mapping CSV")
    p_map.add_argument("--output", help="Output CSV path")
    
    # ASSETS command
    p_assets = subparsers.add_parser("assets", help="Generate MELI video asset map")
    p_assets.add_argument("--report", help="MELI assets report CSV")
    p_assets.add_argument("--mapping", help="B-roll/Endcard mapping CSV")
    p_assets.add_argument("--output", help="Output CSV path")
    
    # BATCH-RUNPOD command
    p_runpod = subparsers.add_parser("batch-runpod", help="Batch process on RunPod")
    p_runpod.add_argument("--workers", "-w", type=int, default=3, help="Number of workers (default: 3)")
    p_runpod.add_argument("--filter", "-f", default="all", help="Filter: even, odd, all, or comma-separated numbers")
    p_runpod.add_argument("--yes", "-y", action="store_true", help="Skip confirmation")
    p_runpod.add_argument("--csv", help="Custom mapping CSV file (default: mlb_edit_mapping_s3.csv)")
    p_runpod.add_argument("--output-folder", help="S3 output folder (default: MLB_Exports/2026-01)")
    
    # BATCH-LOCAL command
    p_local = subparsers.add_parser("batch-local", help="Process single project locally")
    p_local.add_argument("--folder", help="Folder name to process")
    p_local.add_argument("--number", "-n", type=int, help="Project number to process")
    
    # STATUS command
    p_status = subparsers.add_parser("status", help="Check batch progress")
    p_status.add_argument("--tail", "-t", type=int, default=10, help="Show last N log lines")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 0
    
    commands = {
        "mapping": cmd_mapping,
        "assets": cmd_assets,
        "batch-runpod": cmd_batch_runpod,
        "batch-local": cmd_batch_local,
        "status": cmd_status,
    }
    
    return commands[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
