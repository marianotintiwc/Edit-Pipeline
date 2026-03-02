from __future__ import annotations

import argparse
from typing import Iterable

from . import assets_tools
from . import csv_tools
from . import runpod_tools
from . import s3_tools


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="UGC tooling CLI (csv, runpod, assets, s3)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparsers = parser.add_subparsers(dest="area", required=True)

    csv_tools.register_cli(subparsers)
    runpod_tools.register_cli(subparsers)
    assets_tools.register_cli(subparsers)
    s3_tools.register_cli(subparsers)

    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    if not hasattr(args, "func"):
        parser.print_help()
        return 1
    return int(args.func(args) or 0)

