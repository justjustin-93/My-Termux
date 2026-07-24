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


def sync_repo(repo: Path, remote: str = "origin", auto_push: bool = False) -> dict:
    """Inspect and update a local git repo.

    Returns a dict with keys: dirty, ahead, behind, updated, branch, status, summary.
    If the repo is dirty or behind, it will attempt a pull/rebase and optionally a push.
    """
    repo = Path(repo).expanduser().resolve()
    if not (repo / ".git").exists():
        return {"dirty": False, "ahead": False, "behind": False, "updated": False,
                "branch": "", "status": "not a git repo", "summary": "not a git repo"}

    branch = current_branch(repo)
    rc, out, err = run(["git", "status", "--porcelain"], cwd=repo)
    dirty = bool((out or "").strip())

    rc, out, err = run(["git", "rev-parse", "@{upstream}"], cwd=repo)
    upstream_exists = rc == 0
    ahead = False
    behind = False
    if upstream_exists:
        rc, out, err = run(["git", "rev-list", "--left-right", "--count", "@{upstream}...HEAD"], cwd=repo)
        if rc == 0:
            left, right = 0, 0
            try:
                parts = out.split()
                if len(parts) >= 2:
                    left, right = int(parts[0]), int(parts[1])
                ahead = right > 0
                behind = left > 0
            except ValueError:
                ahead = False
                behind = False

    updated = False
    summary_lines = []
    if dirty:
        summary_lines.append("local changes present")
    if ahead:
        summary_lines.append("ahead of upstream")
    if behind:
        summary_lines.append("behind upstream")

    if behind and upstream_exists:
        rc, out, err = pull(repo)
        if rc == 0:
            updated = True
            summary_lines.append("pulled latest changes")
        else:
            summary_lines.append(f"pull failed: {err or out}")

    if dirty and not updated and auto_push:
        # leave dirty changes intact and report; no auto-commit/push by default
        summary_lines.append("local changes left intact")

    if auto_push and upstream_exists and not dirty and not behind and ahead:
        rc, out, err = push(repo, remote=remote, branch=branch)
        if rc == 0:
            updated = True
            summary_lines.append("pushed local commits")
        else:
            summary_lines.append(f"push failed: {err or out}")

    status = run(["git", "status", "--short", "--branch"], cwd=repo)[1]
    return {
        "dirty": dirty,
        "ahead": ahead,
        "behind": behind,
        "updated": updated,
        "branch": branch,
        "status": status,
        "summary": "; ".join(summary_lines) if summary_lines else "up to date",
    }
