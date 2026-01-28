#!/usr/bin/env python3
"""
Generate a CSV that maps MELI user videos to their B-roll and Endcard assets.

Output columns include the source video file plus the mapped asset links.
"""

import argparse
import csv
import os
from typing import Dict, Tuple

from meli_assets_mapper import (
    AssetLinks,
    ProjectMetadata,
    get_assets_for_project,
    load_broll_endcard_mapping,
)


def iter_video_rows(report_csv: str):
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

            yield {
                "folder": folder,
                "filename": filename,
                "url": url,
                "finished": finished,
            }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create a CSV mapping MELI videos to B-roll and endcard assets"
    )
    parser.add_argument(
        "--report",
        default="MELI USERS ASSETS REPORT.csv",
        help="Input assets report CSV",
    )
    parser.add_argument(
        "--mapping",
        default="MELI USERS BROLLS AND ENDCARDS - Hoja 1.csv",
        help="Input B-roll/Endcard mapping CSV",
    )
    parser.add_argument(
        "--output",
        default="meli_video_asset_map.csv",
        help="Output CSV path",
    )
    args = parser.parse_args()

    base_dir = os.path.dirname(os.path.abspath(__file__))
    report_csv = os.path.join(base_dir, args.report)
    mapping_csv = os.path.join(base_dir, args.mapping)
    output_csv = os.path.join(base_dir, args.output)

    mapping = load_broll_endcard_mapping(mapping_csv)
    cache_dir = os.path.join(base_dir, "assets", "meli_cache")

    fieldnames = [
        "Parent Folder",
        "Filename",
        "Video URL",
        "Finished",
        "Project ID",
        "Value Prop Raw",
        "Value Prop Normalized",
        "GEO",
        "Gender",
        "Broll URL",
        "Endcard URL",
        "Broll Cached Path",
        "Endcard Cached Path",
        "Mapping Found",
    ]

    rows_written = 0

    with open(output_csv, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for row in iter_video_rows(report_csv):
            folder = row["folder"]

            result = get_assets_for_project(
                folder,
                mapping,
                use_cache=True,
                base_cache_dir=cache_dir,
            )

            metadata: ProjectMetadata = None
            assets: AssetLinks = None
            cached_paths: Dict[str, str] = {"broll": None, "endcard": None}

            if result:
                metadata, assets, cached_paths = result

            writer.writerow(
                {
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
                }
            )
            rows_written += 1

    print(f"✅ Wrote {rows_written} rows to {output_csv}")


if __name__ == "__main__":
    main()
