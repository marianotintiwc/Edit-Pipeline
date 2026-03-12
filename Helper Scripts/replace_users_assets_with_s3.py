#!/usr/bin/env python3
"""Wrapper for ugc_tools assets replace-urls."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> int:
    repo_dir = Path(__file__).resolve().parent.parent
    report_path = repo_dir / "assets/IGNOREASSETS/users_assets_upload_report.csv"
    csv_in = repo_dir / "USERS FILES FOR EDIT, MLA APPROVED.csv"
    csv_out = repo_dir / "USERS FILES FOR EDIT, MLA APPROVED.s3.csv"

    extra = sys.argv[1:]
    if not extra:
        extra = [
            "--report",
            str(report_path),
            "--input",
            str(csv_in),
            "--output",
            str(csv_out),
            "--columns",
            "Broll,Endcard",
        ]

    cmd = [sys.executable, "-m", "ugc_tools", "assets", "replace-urls"] + extra
    return subprocess.call(cmd)


if __name__ == "__main__":
    raise SystemExit(main())
