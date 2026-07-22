"""Project scanner — detects project kind, dependencies, git state."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, List

from . import db


DEP_FILES = {
    "python": ["requirements.txt", "pyproject.toml", "setup.py", "Pipfile"],
    "node": ["package.json"],
    "rust": ["Cargo.toml"],
    "go": ["go.mod"],
    "java": ["pom.xml", "build.gradle", "build.gradle.kts"],
    "ruby": ["Gemfile"],
    "php": ["composer.json"],
    "docker": ["Dockerfile", "docker-compose.yml", "compose.yaml"],
}


def detect_kind(path: Path) -> List[str]:
    kinds = []
    for kind, files in DEP_FILES.items():
        for f in files:
            if (path / f).exists():
                kinds.append(kind)
                break
    return kinds


def is_git_repo(path: Path) -> bool:
    return (path / ".git").exists()


def count_files(path: Path, exts: List[str] | None = None) -> int:
    n = 0
    for root, dirs, files in os.walk(path):
        # skip heavy/irrelevant dirs
        dirs[:] = [d for d in dirs if d not in {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build", ".next"}]
        for name in files:
            if exts is None or any(name.endswith(e) for e in exts):
                n += 1
    return n


def scan(path: Path) -> Dict:
    path = Path(path).expanduser().resolve()
    if not path.exists():
        return {"error": f"path not found: {path}"}
    kinds = detect_kind(path)
    info = {
        "path": str(path),
        "name": path.name,
        "kinds": kinds,
        "git": is_git_repo(path),
        "files": count_files(path),
        "code_files": count_files(path, [".py", ".js", ".ts", ".tsx", ".jsx", ".rs", ".go", ".java", ".rb", ".php", ".sh"]),
    }
    db.upsert_project(name=path.name, path=str(path), kind=",".join(kinds))
    db.log("info", "scanner", f"scanned {path} kinds={kinds}")
    return info
