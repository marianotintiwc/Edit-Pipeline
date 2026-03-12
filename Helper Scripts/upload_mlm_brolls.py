#!/usr/bin/env python3
"""Wrapper for ugc_tools s3 upload-folder."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> int:
    repo_dir = Path(__file__).resolve().parent.parent
    local_dir = repo_dir / "assets/IGNOREASSETS/users_assets_upload_tmp/MLM"

    extra = sys.argv[1:]
    if not extra:
        extra = [
            "--folder",
            str(local_dir),
            "--bucket",
            "meli-ai.filmmaker",
            "--prefix",
            "MP-Users/Assets",
            "--region",
            "us-east-2",
        ]

    cmd = [sys.executable, "-m", "ugc_tools", "s3", "upload-folder"] + extra
    return subprocess.call(cmd)


if __name__ == "__main__":
    raise SystemExit(main())
