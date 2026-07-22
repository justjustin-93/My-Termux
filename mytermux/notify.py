"""Termux notification bridge. Silent no-op if termux-api is not installed."""
from __future__ import annotations

import shutil
import subprocess

from .config import load_config


def available() -> bool:
    return shutil.which("termux-notification") is not None


def notify(title: str, content: str, priority: str = "default") -> bool:
    """Send a Termux notification. Returns True on success."""
    if not load_config().get("notifications", True):
        return False
    if not available():
        return False
    try:
        subprocess.run(
            [
                "termux-notification",
                "--title", title,
                "--content", content,
                "--priority", priority,
                "--id", "mytermux",
            ],
            check=False,
            timeout=5,
        )
        return True
    except Exception:
        return False
