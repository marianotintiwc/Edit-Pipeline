from __future__ import annotations

import os
from pathlib import Path


def _load_dotenv_file(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def load_env_from_candidates(candidates: list[Path]) -> None:
    for path in candidates:
        if path.exists():
            _load_dotenv_file(path)
            return


def load_env_default(repo_dir: Path) -> None:
    candidates = [
        repo_dir / ".env",
        repo_dir.parent / ".env",
        Path.cwd() / ".env",
    ]

    try:
        from dotenv import load_dotenv

        for path in candidates:
            if path.exists():
                load_dotenv(path, override=False)
                return
    except Exception:
        pass

    load_env_from_candidates(candidates)

