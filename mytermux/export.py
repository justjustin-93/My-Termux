"""Export sessions/config/projects to Android-visible shared storage."""
from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

from . import db, paths


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def _dest(name: str) -> Path:
    paths.try_ensure_shared_exports()
    if paths.SHARED_EXPORTS.exists():
        base = paths.SHARED_EXPORTS
    else:
        base = paths.HOME / "exports"
        base.mkdir(parents=True, exist_ok=True)
    return base / name


def export(what: str = "session") -> str:
    what = (what or "session").lower()
    if what == "config":
        target = _dest(f"config-{_stamp()}.yaml")
        if paths.CONFIG_FILE.exists():
            shutil.copy2(paths.CONFIG_FILE, target)
        return str(target)

    if what == "project":
        # export the current project folder (if set) as a tar.gz
        from .config import load_config
        cur = load_config().get("current_project", "")
        if not cur:
            raise RuntimeError("No current_project set. Use `/project X` in chat or Settings.")
        src = Path(cur).expanduser()
        if not src.exists():
            raise RuntimeError(f"project path missing: {src}")
        out = _dest(f"{src.name}-{_stamp()}.tar.gz")
        # use shutil.make_archive
        base = out.with_suffix("").with_suffix("")
        archive = shutil.make_archive(str(base), "gztar", root_dir=str(src.parent), base_dir=src.name)
        return archive

    # default: session
    row = db.get_last_session()
    if not row:
        raise RuntimeError("no session to export")
    msgs = db.get_session_messages(int(row["id"]))
    payload = {
        "session": dict(row),
        "messages": [dict(m) for m in msgs],
        "exported_at": _stamp(),
    }
    out = _dest(f"session-{row['id']}-{_stamp()}.json")
    out.write_text(json.dumps(payload, indent=2, default=str), encoding="utf-8")
    return str(out)
