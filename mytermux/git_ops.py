"""GitHub / git helpers — thin wrappers around the git CLI with PAT auth."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Optional, Tuple
from urllib.parse import urlparse, urlunparse

from . import db
from .config import load_config


def git_available() -> bool:
    return shutil.which("git") is not None


def run(cmd: list, cwd: Optional[Path] = None, timeout: int = 60) -> Tuple[int, str, str]:
    try:
        p = subprocess.run(
            cmd,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return p.returncode, p.stdout, p.stderr
    except FileNotFoundError:
        return 127, "", f"not found: {cmd[0]}"
    except subprocess.TimeoutExpired:
        return 124, "", "timeout"


def _inject_pat(url: str, token: str, username: str = "") -> str:
    """Insert PAT into an https github url. SSH urls untouched."""
    if not url.startswith("https://") or not token:
        return url
    parsed = urlparse(url)
    user = username or "x-access-token"
    netloc = f"{user}:{token}@{parsed.hostname}"
    if parsed.port:
        netloc += f":{parsed.port}"
    return urlunparse(parsed._replace(netloc=netloc))


def clone(url: str, dest: Path) -> Tuple[int, str, str]:
    if not git_available():
        return 127, "", "git not installed"
    cfg = load_config()
    token = cfg.get("github_token", "")
    username = cfg.get("github_username", "")
    auth_url = _inject_pat(url, token, username) if token else url
    dest = Path(dest).expanduser()
    dest.parent.mkdir(parents=True, exist_ok=True)
    rc, out, err = run(["git", "clone", auth_url, str(dest)], timeout=300)
    db.log("info" if rc == 0 else "error", "git", f"clone {url} -> {dest} rc={rc}")
    return rc, out, err


def status(repo: Path) -> str:
    rc, out, err = run(["git", "status", "--short", "--branch"], cwd=repo)
    return out if rc == 0 else err


def commit_all(repo: Path, message: str) -> Tuple[int, str, str]:
    rc, _, _ = run(["git", "add", "-A"], cwd=repo)
    if rc != 0:
        return rc, "", "git add failed"
    return run(["git", "commit", "-m", message], cwd=repo)


def push(repo: Path, remote: str = "origin", branch: str = "") -> Tuple[int, str, str]:
    cmd = ["git", "push", remote]
    if branch:
        cmd.append(branch)
    return run(cmd, cwd=repo, timeout=300)


def pull(repo: Path) -> Tuple[int, str, str]:
    return run(["git", "pull", "--rebase"], cwd=repo, timeout=300)


def current_branch(repo: Path) -> str:
    rc, out, _ = run(["git", "rev-parse", "--abbrev-ref", "HEAD"], cwd=repo)
    return out.strip() if rc == 0 else ""
