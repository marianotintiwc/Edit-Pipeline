#!/usr/bin/env python3
"""
MELI Assets Mapper
==================
Maps value propositions (from folder names) to B-rolls and Endcards
from Google Drive links in the CSV.

Folder naming pattern: [ID]_[value_prop]-[GEO]-[gender]
Example: 46_rendimientos-MLA-female
"""

import csv
import os
import re
import requests
from typing import Dict, Optional, Tuple
from dataclasses import dataclass


# ─────────────────────────────────────────────────────────────────────────────
# VALUE PROPOSITION NORMALIZATION
# ─────────────────────────────────────────────────────────────────────────────

VALUE_PROP_MAPPING = {
    # Mapping from folder name format to CSV format
    "tarjeta_de_debito": "Tarjeta de Débito",
    "tarjeta_de_credito": "Tarjeta de Crédito",
    "rendimientos": "Rendimientos",
    "prestamo_personal": "Préstamo Personal",
    "lucky_winner": "Lucky Winner",
    "incentivos": "Incentivos",
    "servicios": "Servicios",
    "credits_cuotas_sin_tarjeta": "Cuotas Sin Tarjeta",
    "cuotas_sin_tarjeta": "Cuotas Sin Tarjeta",
    "pix": "Pix",
    "pix_na_credito": "Pix na Crédito",
    "cofrinhos": "Cofrinhos",
    "qr": "QR",
}


def normalize_value_prop(raw_value_prop: str) -> str:
    """
    Normalize value prop from folder name to CSV format.
    Example: tarjeta_de_debito -> Tarjeta de Débito
    """
    normalized = VALUE_PROP_MAPPING.get(raw_value_prop.lower())
    if normalized:
        return normalized
    
    # Fallback: replace underscores with spaces and capitalize each word
    return raw_value_prop.replace("_", " ").title()


# ─────────────────────────────────────────────────────────────────────────────
# FOLDER NAME PARSING
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class ProjectMetadata:
    """Parsed metadata from project folder name."""
    full_name: str
    project_id: str
    value_prop_raw: str
    value_prop_normalized: str
    geo: str
    gender: str


def parse_folder_name(folder_name: str) -> Optional[ProjectMetadata]:
    """
    Parse folder name like: 46_rendimientos-MLA-female
    Returns ProjectMetadata or None if parsing fails.
    """
    # Pattern: [ID]_[value_prop]-[GEO]-[gender]
    # Allow for _tap suffix or other variations
    pattern = r'^(\d+)_([^-]+)-([A-Z]{3})-(\w+)$'
    
    # Remove _tap suffix if present
    clean_name = re.sub(r'_tap$', '', folder_name, flags=re.IGNORECASE)
    
    match = re.match(pattern, clean_name)
    if not match:
        return None
    
    project_id, value_prop_raw, geo, gender = match.groups()
    
    return ProjectMetadata(
        full_name=folder_name,
        project_id=project_id,
        value_prop_raw=value_prop_raw,
        value_prop_normalized=normalize_value_prop(value_prop_raw),
        geo=geo,
        gender=gender
    )


# ─────────────────────────────────────────────────────────────────────────────
# B-ROLL/ENDCARD MAPPING
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class AssetLinks:
    """B-roll and Endcard links for a value proposition."""
    broll_url: Optional[str] = None
    endcard_url: Optional[str] = None


def load_broll_endcard_mapping(csv_path: str) -> Dict[Tuple[str, str], AssetLinks]:
    """
    Load B-roll and Endcard mapping from CSV.
    Returns dict keyed by (GEO, value_prop_normalized).
    
    Example: ("MLA", "Tarjeta de Débito") -> AssetLinks(...)
    """
    mapping = {}
    
    if not os.path.exists(csv_path):
        print(f"⚠️  Warning: CSV not found at {csv_path}")
        return mapping
    
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            geo = (row.get("GEO") or "").strip()
            value_prop = (row.get("Propuesta de Valor") or "").strip()
            broll_link = (row.get("Link B-Roll") or "").strip()
            endcard_link = (row.get("Link Endcard") or "").strip()
            
            if not geo or not value_prop:
                continue
            
            # Handle N/A values
            if broll_link.upper() == "N/A":
                broll_link = None
            if endcard_link.upper() == "N/A":
                endcard_link = None
            
            key = (geo, value_prop)
            mapping[key] = AssetLinks(
                broll_url=broll_link if broll_link else None,
                endcard_url=endcard_link if endcard_link else None
            )
    
    print(f"✅ Loaded {len(mapping)} B-roll/Endcard mappings from CSV")
    return mapping


def get_assets_for_project(
    folder_name: str,
    mapping: Dict[Tuple[str, str], AssetLinks],
    use_cache: bool = True,
    base_cache_dir: str = "assets/meli_cache"
) -> Optional[Tuple[ProjectMetadata, AssetLinks, Dict[str, Optional[str]]]]:
    """
    Get B-roll and Endcard links for a project folder.
    Also checks for cached versions.
    
    Returns:
        Tuple of (metadata, asset_links, cached_paths) or None if not found
        cached_paths is a dict with keys 'broll' and 'endcard'
    """
    metadata = parse_folder_name(folder_name)
    if not metadata:
        print(f"⚠️  Could not parse folder name: {folder_name}")
        return None
    
    key = (metadata.geo, metadata.value_prop_normalized)
    assets = mapping.get(key)
    
    if not assets:
        print(f"⚠️  No B-roll/Endcard found for {metadata.geo} - {metadata.value_prop_normalized}")
        return None
    
    # Check cache if enabled
    cached_paths = {
        'broll': None,
        'endcard': None
    }
    
    if use_cache:
        if assets.broll_url:
            cached_paths['broll'] = get_cached_asset(
                metadata.geo, 
                metadata.value_prop_normalized, 
                'broll', 
                base_cache_dir
            )
        
        if assets.endcard_url:
            cached_paths['endcard'] = get_cached_asset(
                metadata.geo, 
                metadata.value_prop_normalized, 
                'endcard', 
                base_cache_dir
            )
    
    return (metadata, assets, cached_paths)


# ─────────────────────────────────────────────────────────────────────────────
# CACHE MANAGEMENT
# ─────────────────────────────────────────────────────────────────────────────

def get_cache_path(geo: str, value_prop: str, asset_type: str, base_cache_dir: str = "assets/meli_cache") -> str:
    """
    Get the cache path for a B-roll or Endcard.
    
    Args:
        geo: GEO code (MLA, MLB, MLM, MLC)
        value_prop: Normalized value prop name
        asset_type: 'broll' or 'endcard'
        base_cache_dir: Base directory for cached assets
    
    Returns:
        Full path to cached file
    """
    # Sanitize value prop for filename (remove spaces, special chars)
    safe_value_prop = value_prop.lower().replace(" ", "_").replace("á", "a").replace("é", "e").replace("ó", "o")
    
    cache_dir = os.path.join(base_cache_dir, geo)
    os.makedirs(cache_dir, exist_ok=True)
    
    filename = f"{safe_value_prop}_{asset_type}.mp4"
    return os.path.join(cache_dir, filename)


def get_cached_asset(geo: str, value_prop: str, asset_type: str, base_cache_dir: str = "assets/meli_cache") -> Optional[str]:
    """
    Check if an asset is already cached locally.
    
    Returns:
        Path to cached file if it exists, None otherwise
    """
    cache_path = get_cache_path(geo, value_prop, asset_type, base_cache_dir)
    
    if os.path.exists(cache_path) and os.path.getsize(cache_path) > 0:
        print(f"      ✅ Found cached {asset_type}: {os.path.basename(cache_path)}")
        return cache_path
    
    return None


# ─────────────────────────────────────────────────────────────────────────────
# GOOGLE DRIVE DOWNLOADER
# ─────────────────────────────────────────────────────────────────────────────

def extract_drive_file_id(drive_url: str) -> Optional[str]:
    """
    Extract file ID from various Google Drive URL formats:
    - https://drive.google.com/file/d/FILE_ID/view
    - https://drive.google.com/open?id=FILE_ID
    - https://drive.google.com/uc?id=FILE_ID
    """
    patterns = [
        r'/d/([a-zA-Z0-9_-]+)',  # /file/d/FILE_ID/view
        r'id=([a-zA-Z0-9_-]+)',  # ?id=FILE_ID or &id=FILE_ID
    ]
    
    for pattern in patterns:
        match = re.search(pattern, drive_url)
        if match:
            return match.group(1)
    
    return None


def download_from_drive(drive_url: str, dest_path: str, timeout: int = 300) -> bool:
    """
    Download a file from Google Drive.
    Handles both direct download links and shareable links.
    Returns True if successful, False otherwise.
    """
    if not drive_url:
        print("❌ No drive URL provided")
        return False
    
    file_id = extract_drive_file_id(drive_url)
    if not file_id:
        print(f"❌ Could not extract file ID from: {drive_url}")
        return False
    
    print(f"      ⬇️  Downloading from Drive: {os.path.basename(dest_path)}")
    
    # Try using gdown first (more reliable for large files)
    try:
        import gdown
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        
        download_url = f"https://drive.google.com/uc?id={file_id}"
        gdown.download(download_url, dest_path, quiet=False)
        
        if os.path.exists(dest_path) and os.path.getsize(dest_path) > 0:
            file_size = os.path.getsize(dest_path)
            print(f"      ✅ Downloaded: {file_size / (1024*1024):.1f} MB")
            return True
        else:
            print(f"      ⚠️  gdown returned empty file, trying manual method...")
    except ImportError:
        print(f"      ⚠️  gdown not installed, using manual method...")
    except Exception as e:
        print(f"      ⚠️  gdown failed ({e}), trying manual method...")
    
    # Fallback to manual download
    try:
        download_url = f"https://drive.google.com/uc?export=download&id={file_id}"
        
        session = requests.Session()
        response = session.get(download_url, stream=True, timeout=timeout)
        
        # Handle virus scan warning for large files
        if "virus scan warning" in response.text.lower():
            for key, value in response.cookies.items():
                if key.startswith('download_warning'):
                    params = {'export': 'download', 'id': file_id, 'confirm': value}
                    response = session.get("https://drive.google.com/uc", params=params, stream=True, timeout=timeout)
                    break
        
        response.raise_for_status()
        
        # Write file
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        with open(dest_path, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        
        file_size = os.path.getsize(dest_path)
        if file_size > 0:
            print(f"      ✅ Downloaded: {file_size / (1024*1024):.1f} MB")
            return True
        else:
            print(f"      ❌ Downloaded file is empty")
            return False
        
    except Exception as e:
        print(f"      ❌ Download failed: {e}")
        if os.path.exists(dest_path):
            os.remove(dest_path)
        return False


# ─────────────────────────────────────────────────────────────────────────────
# TESTING
# ─────────────────────────────────────────────────────────────────────────────

def test_mapping():
    """Test the mapping logic with sample folder names."""
    
    print("=" * 80)
    print("TESTING MELI ASSETS MAPPER")
    print("=" * 80)
    
    # Test folder name parsing
    test_folders = [
        "46_rendimientos-MLA-female",
        "29_servicios-MLM-female",
        "64_tarjeta_de_debito-MLM-female",
        "17_lucky_winner-MLM-male",
        "43_prestamo_personal-MLA-female",
        "29_credits_cuotas_sin_tarjeta-MLA-female",
        "15_tap-MLB-male",  # Invalid (no value prop)
        "invalid_format",  # Invalid
    ]
    
    print("\n📋 FOLDER NAME PARSING TESTS:")
    print("-" * 80)
    for folder in test_folders:
        metadata = parse_folder_name(folder)
        if metadata:
            print(f"✅ {folder}")
            print(f"   ID: {metadata.project_id}")
            print(f"   Value Prop (raw): {metadata.value_prop_raw}")
            print(f"   Value Prop (normalized): {metadata.value_prop_normalized}")
            print(f"   GEO: {metadata.geo}")
            print(f"   Gender: {metadata.gender}")
        else:
            print(f"❌ {folder} - Could not parse")
        print()
    
    # Test CSV loading
    csv_path = "MELI USERS BROLLS AND ENDCARDS - Hoja 1.csv"
    if os.path.exists(csv_path):
        print("\n📊 LOADING B-ROLL/ENDCARD MAPPING:")
        print("-" * 80)
        mapping = load_broll_endcard_mapping(csv_path)
        
        print(f"\nTotal mappings: {len(mapping)}")
        print("\nSample mappings:")
        for i, (key, assets) in enumerate(list(mapping.items())[:5]):
            geo, value_prop = key
            print(f"{i+1}. {geo} - {value_prop}")
            print(f"   B-roll: {'✅' if assets.broll_url else '❌'}")
            print(f"   Endcard: {'✅' if assets.endcard_url else '❌'}")
        
        # Test project asset lookup
        print("\n🔍 PROJECT ASSET LOOKUP TESTS:")
        print("-" * 80)
        for folder in ["46_rendimientos-MLA-female", "29_servicios-MLM-female", "17_lucky_winner-MLM-male"]:
            assets = get_assets_for_project(folder, mapping)
            if assets:
                print(f"✅ {folder}")
                print(f"   B-roll: {'✅' if assets.broll_url else '❌ N/A'}")
                print(f"   Endcard: {'✅' if assets.endcard_url else '❌ N/A'}")
            else:
                print(f"❌ {folder} - No assets found")
            print()
    
    # Test Drive URL parsing
    print("\n🔗 GOOGLE DRIVE URL PARSING TESTS:")
    print("-" * 80)
    test_urls = [
        "https://drive.google.com/file/d/1JQ0tJr6I8y47lse5-nlVvK0FFisgHxC_/view?usp=drive_link",
        "https://drive.google.com/open?id=1E4AMG-67ScQuNjzsJmJrFuYxkwc99GeS",
        "https://drive.google.com/uc?export=download&id=12K4wxci7i37Cph9bwpIOTFqHZaYX3FLH",
    ]
    
    for url in test_urls:
        file_id = extract_drive_file_id(url)
        if file_id:
            print(f"✅ Extracted ID: {file_id}")
            print(f"   From: {url[:60]}...")
        else:
            print(f"❌ Could not extract ID from: {url}")
        print()
    
    print("=" * 80)
    print("TEST COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    test_mapping()
