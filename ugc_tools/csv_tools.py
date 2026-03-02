from __future__ import annotations

import argparse
import csv
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Iterable

from .paths import repo_root


DEFAULT_INPUT_CSV = "s3_assets_report sellers RERUN.csv"
DEFAULT_OUTPUT_CSV = "folders_over_1000_edit_config.csv"
DEFAULT_FILLED_OUTPUT = "folders_over_1000_edit_config_filled.csv"
DEFAULT_ASSET_MAP = repo_root() / "config" / "ugc_assets_map.json"


def register_cli(subparsers: argparse._SubParsersAction) -> None:
    csv_parser = subparsers.add_parser("csv", help="CSV structuring and validation")
    csv_sub = csv_parser.add_subparsers(dest="command", required=True)

    complete = csv_sub.add_parser("complete-folders", help="Generate edit config CSV")
    complete.add_argument("--input", default=DEFAULT_INPUT_CSV, help="Input CSV path")
    complete.add_argument("--output", default=DEFAULT_OUTPUT_CSV, help="Output CSV path")
    complete.add_argument("--min-id", type=int, default=1000, help="Minimum folder id (exclusive)")
    complete.add_argument(
        "--lipsync-suffix",
        default="_lipsync.mp4",
        help="Filename suffix for lipsync clips",
    )
    complete.add_argument(
        "--allow-unfinished",
        action="store_true",
        help="Allow folders without Finished=Yes for all lipsync files",
    )
    complete.set_defaults(func=cmd_complete_folders)

    autofill = csv_sub.add_parser("autofill-assets", help="Autofill assets in CSV")
    autofill.add_argument("--input", default=DEFAULT_OUTPUT_CSV, help="Input CSV path")
    autofill.add_argument("--output", default=DEFAULT_FILLED_OUTPUT, help="Output CSV path")
    autofill.add_argument("--asset-map", default=str(DEFAULT_ASSET_MAP), help="JSON asset map")
    autofill.add_argument("--market-field", default="Market", help="Market column name")
    autofill.add_argument("--template-field", default="Template", help="Template column name")
    autofill.add_argument("--endcard-field", default="Endcard_URL", help="Endcard column name")
    autofill.add_argument("--broll-field", default="Broll_1_URL", help="Broll column name")
    autofill.set_defaults(func=cmd_autofill_assets)


def cmd_complete_folders(args: argparse.Namespace) -> int:
    repo_dir = repo_root()
    input_csv = _resolve_path(args.input, repo_dir)
    output_csv = _resolve_path(args.output, repo_dir)

    if not input_csv.exists():
        raise SystemExit(f"Input CSV not found: {input_csv}")

    complete_folders = analyze_csv(
        input_csv,
        lipsync_suffix=args.lipsync_suffix,
        min_id=args.min_id,
        require_finished=not bool(args.allow_unfinished),
    )
    write_edit_config_csv(output_csv, complete_folders)

    print(f"Created {output_csv} with {len(complete_folders)} rows")
    return 0


def cmd_autofill_assets(args: argparse.Namespace) -> int:
    repo_dir = repo_root()
    input_csv = _resolve_path(args.input, repo_dir)
    output_csv = _resolve_path(args.output, repo_dir)
    asset_map_path = _resolve_path(args.asset_map, repo_dir)

    if not input_csv.exists():
        raise SystemExit(f"Input CSV not found: {input_csv}")

    asset_map = load_asset_map(asset_map_path)
    rows, fieldnames = load_csv_rows(input_csv)

    endcard_field = args.endcard_field
    broll_field = args.broll_field

    if endcard_field not in fieldnames:
        fieldnames.append(endcard_field)
    if broll_field not in fieldnames:
        fieldnames.append(broll_field)

    missing = []
    for row in rows:
        market = _pick_first(row, [args.market_field, "GEO", "Geo", "geo"])
        template = _pick_first(row, [args.template_field, "Template", "template"])
        asset_type = template_to_asset_type(template)
        endcard, broll = get_assets_for_market(asset_map, asset_type, market)
        if not endcard or not broll:
            missing.append((market, template, asset_type))
        row[endcard_field] = endcard or row.get(endcard_field, "")
        row[broll_field] = broll or row.get(broll_field, "")

    write_csv_rows(output_csv, fieldnames, rows)

    if missing:
        unique_missing = sorted({(m, t, a) for (m, t, a) in missing})
        print("Missing assets for:")
        for market, template, asset_type in unique_missing:
            print(f"  {market} / {template} ({asset_type})")
    else:
        print("All assets filled from map.")

    print(f"Wrote: {output_csv}")
    return 0


def analyze_csv(
    csv_path: Path,
    lipsync_suffix: str,
    min_id: int,
    require_finished: bool,
) -> list[dict]:
    folders_data = defaultdict(lambda: {"lipsync_count": 0, "finished_lipsync_count": 0})

    with csv_path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            folder = (row.get("Parent Folder") or row.get("Parent_Folder") or "").strip()
            filename = (row.get("Filename") or "").strip()
            finished = (row.get("Finished") or row.get("finished") or "").strip().lower()

            if not folder:
                continue
            if lipsync_suffix in filename:
                folders_data[folder]["lipsync_count"] += 1
                if finished in {"yes", "y", "true", "1"}:
                    folders_data[folder]["finished_lipsync_count"] += 1

    complete_folders = []
    for folder, data in folders_data.items():
        folder_id = extract_id(folder)
        if folder_id is None or folder_id <= min_id:
            continue
        is_complete = data["lipsync_count"] == 3
        if require_finished:
            is_complete = is_complete and data["finished_lipsync_count"] == 3
        if is_complete:
            folder_id, template, market, gender = extract_info(folder)
            complete_folders.append(
                {
                    "id": folder_id,
                    "folder_name": folder,
                    "template": template,
                    "market": market,
                    "gender": gender,
                }
            )

    complete_folders.sort(key=lambda x: x["id"] or 0)
    return complete_folders


def extract_id(folder_name: str) -> int | None:
    match = re.match(r"^(\d+)", folder_name)
    if match:
        return int(match.group(1))
    return None


def extract_info(folder_name: str) -> tuple[int | None, str, str, str]:
    parts = folder_name.split("-")
    folder_id = extract_id(folder_name)

    template = ""
    if parts:
        first = parts[0]
        if "_" in first:
            template = first.split("_", 1)[1]
    market = parts[1] if len(parts) > 1 else ""
    gender = parts[2] if len(parts) > 2 else ""

    return folder_id, template, market, gender


def write_edit_config_csv(output_file: Path, complete_folders: Iterable[dict]) -> None:
    fieldnames = [
        "ID",
        "Folder_Name",
        "Template",
        "Market",
        "Gender",
        "Endcard_URL",
        "Broll_1_URL",
        "Broll_2_URL",
        "Broll_3_URL",
        "Notes",
    ]

    with output_file.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for folder in complete_folders:
            writer.writerow(
                {
                    "ID": folder.get("id") or "",
                    "Folder_Name": folder.get("folder_name") or "",
                    "Template": folder.get("template") or "",
                    "Market": folder.get("market") or "",
                    "Gender": folder.get("gender") or "",
                    "Endcard_URL": "",
                    "Broll_1_URL": "",
                    "Broll_2_URL": "",
                    "Broll_3_URL": "",
                    "Notes": "",
                }
            )


def load_asset_map(path: Path) -> dict:
    if path.exists():
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)

    return {
        "SMART": {
            "MLA": {
                "endcard": "https://s3.us-east-2.amazonaws.com/meli-ai.filmmaker/MP-Sellers/Assets/MLA-%20Consegu%C3%AD%20tu%20Point%20Smart.mov",
                "broll": "https://s3.us-east-2.amazonaws.com/meli-ai.filmmaker/MP-Sellers/Assets/MP_SELLERS_AI_VIDEO_GENERICO_PROYECTO_TECH_MLA_9X16.mov",
            },
            "MLB": {
                "endcard": "https://s3.us-east-2.amazonaws.com/meli-ai.filmmaker/MP-Sellers/Assets/MLB-%20Compre%20sua%20maquininha.mov",
                "broll": "https://s3.us-east-2.amazonaws.com/meli-ai.filmmaker/MP-Sellers/Assets/MP_SELLERS_AI_VIDEO_GENERICO_PROYECTO_TECH_MLB_9X16.mov",
            },
            "MLM": {
                "endcard": "https://s3.us-east-2.amazonaws.com/meli-ai.filmmaker/MP-Sellers/Assets/MLM-%20Consigue%20tu%20Terminal.mov",
                "broll": "https://s3.us-east-2.amazonaws.com/meli-ai.filmmaker/MP-Sellers/Assets/MP_SELLERS_AI_VIDEO_GENERICO_PROYECTO_TECH_MLM_9X16.mov",
            },
            "MLC": {
                "endcard": "https://s3.us-east-2.amazonaws.com/meli-ai.filmmaker/MP-Sellers/Assets/MLC-%20Compra%20tu%20Point%20Smart.mov",
                "broll": "https://s3.us-east-2.amazonaws.com/meli-ai.filmmaker/MP-Sellers/Assets/MP_SELLERS_AI_VIDEO_GENERICO_PROYECTO_TECH_MLC_9X16.mov",
            },
        },
        "TAP": {
            "MLB": {
                "endcard": "https://s3.us-east-2.amazonaws.com/meli-ai.filmmaker/MP-Sellers/Assets/MLB%20-%20Venda%20com%20Tap%20do%20Mercado%20Pago.mov",
                "broll": "https://s3.us-east-2.amazonaws.com/meli-ai.filmmaker/MP-Sellers/Assets/MP_SELLERS_AI_VIDEO_GENERICO_TAP_MLB_9X16.mov",
            }
        },
    }


def template_to_asset_type(template: str) -> str:
    if "tap" in (template or "").lower():
        return "TAP"
    return "SMART"


def get_assets_for_market(asset_map: dict, asset_type: str, market: str) -> tuple[str, str]:
    asset_type = (asset_type or "").upper()
    market = (market or "").upper()
    assets = asset_map.get(asset_type, {}).get(market, {})
    return assets.get("endcard", ""), assets.get("broll", "")


def load_csv_rows(path: Path) -> tuple[list[dict], list[str]]:
    with path.open("r", encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])
    return rows, fieldnames


def write_csv_rows(path: Path, fieldnames: list[str], rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _resolve_path(value: str, repo_dir: Path) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = repo_dir / path
    return path


def _pick_first(row: dict, keys: list[str]) -> str:
    for key in keys:
        value = (row.get(key) or "").strip()
        if value:
            return value
    return ""


