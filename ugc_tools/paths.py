from __future__ import annotations

from pathlib import Path


def repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def helper_scripts_dir() -> Path:
    return repo_root() / "Helper Scripts"

