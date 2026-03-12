#!/usr/bin/env python3
"""Wrapper for ugc_tools assets upload-drive."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> int:
    repo_dir = Path(__file__).resolve().parent.parent
    csv_path = repo_dir / "USERS FILES FOR EDIT, MLA APPROVED.csv"
    tmp_dir = repo_dir / "assets/IGNOREASSETS/users_assets_upload_tmp"
    report_path = repo_dir / "assets/IGNOREASSETS/users_assets_upload_report.csv"

    extra = sys.argv[1:]
    if not extra:
        extra = [
            "--csv",
            str(csv_path),
            "--tmp-dir",
            str(tmp_dir),
            "--report",
            str(report_path),
            "--columns",
            "Broll,Endcard",
            "--skip-existing",
        ]

    cmd = [sys.executable, "-m", "ugc_tools", "assets", "upload-drive"] + extra
    return subprocess.call(cmd)


if __name__ == "__main__":
    raise SystemExit(main())
