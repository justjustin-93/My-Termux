"""Safe shell + file tools for the agent."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Optional, Tuple

from . import db

# commands considered dangerous — the CLI must confirm before running these
DANGEROUS_TOKENS = {"rm ", "rm\t", "mkfs", "dd if=", ":(){", "shutdown", "reboot",
                    "chmod 777 /", "chown -R /", "mv / ", "> /dev/sda"}


def is_dangerous(cmd: str) -> bool:
    c = cmd.strip()
    if not c:
        return False
    for tok in DANGEROUS_TOKENS:
        if tok in c:
            return True
    if c.startswith("rm ") and "-rf" in c and (" /" in c or " ~" == c[-2:] or " ~/" in c):
        return True
    return False


def run_shell(cmd: str, cwd: Optional[Path] = None, timeout: int = 60) -> Tuple[int, str, str]:
    try:
        p = subprocess.run(
            cmd,
            shell=True,
            cwd=str(cwd) if cwd else None,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        db.log("info", "shell", f"cmd={cmd!r} rc={p.returncode}")
        return p.returncode, p.stdout, p.stderr
    except subprocess.TimeoutExpired:
        db.log("warn", "shell", f"timeout cmd={cmd!r}")
        return 124, "", "timeout"
    except Exception as e:
        db.log("error", "shell", f"cmd={cmd!r} err={e}")
        return 1, "", str(e)


def read_file(path: Path, max_bytes: int = 200_000) -> str:
    p = Path(path).expanduser()
    if not p.exists() or not p.is_file():
        return ""
    data = p.read_bytes()[:max_bytes]
    try:
        return data.decode("utf-8", errors="replace")
    except Exception:
        return ""


def write_file(path: Path, content: str, backup: bool = True) -> bool:
    p = Path(path).expanduser()
    p.parent.mkdir(parents=True, exist_ok=True)
    if backup and p.exists():
        bak = p.with_suffix(p.suffix + ".bak")
        try:
            shutil.copy2(p, bak)
        except Exception:
            pass
    p.write_text(content, encoding="utf-8")
    return True
