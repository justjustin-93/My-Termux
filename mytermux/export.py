"""Export and import sessions/config/projects to Android-visible shared storage."""
from __future__ import annotations

import json
import os
import shutil
import sqlite3
import tarfile
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


def _ensure_unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    idx = 1
    while True:
        candidate = path.with_name(f"{path.name}-{idx}")
        if not candidate.exists():
            return candidate
        idx += 1


def _restore_tar_archive(archive_path: Path, dest_dir: Path) -> Path:
    with tarfile.open(archive_path, "r:gz") as tf:
        members = [m for m in tf.getmembers() if m.name not in ("", ".")]
        if not members:
            raise RuntimeError("archive is empty")
        root_parts = []
        for member in members:
            parts = Path(member.name).parts
            if not parts:
                continue
            if parts[0] in (".", ""):
                continue
            root_parts.append(parts[0])
        root_name = root_parts[0] if len(set(root_parts)) == 1 and root_parts else archive_path.stem.replace(".tar", "")
        target = _ensure_unique_path(dest_dir / root_name)
        target.mkdir(parents=True, exist_ok=True)
        for member in members:
            member_path = Path(member.name)
            if member_path.is_absolute() or ".." in member_path.parts:
                raise RuntimeError(f"unsafe archive path: {member.name}")
            rel_parts = member_path.parts
            if rel_parts and rel_parts[0] == root_name:
                rel_parts = rel_parts[1:]
            rel_path = Path(*rel_parts)
            if not rel_path.parts:
                continue
            current = (target / rel_path).resolve()
            if os.path.commonpath([str(target.resolve()), str(current)]) != str(target.resolve()):
                raise RuntimeError(f"unsafe archive path: {member.name}")
            if member.isdir():
                current.mkdir(parents=True, exist_ok=True)
                continue
            if member.isreg():
                current.parent.mkdir(parents=True, exist_ok=True)
                with tf.extractfile(member) as src, current.open("wb") as dst:
                    if src is None:
                        continue
                    shutil.copyfileobj(src, dst)
        return target


def import_export(what: str, source: str | os.PathLike[str]) -> str:
    what = (what or "session").lower()
    src = Path(source).expanduser()
    if not src.exists():
        raise FileNotFoundError(f"import path missing: {src}")

    if what == "config":
        dest = paths.CONFIG_FILE
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dest)
        return str(dest)

    if what == "project":
        from .config import load_config, save_config
        target = _restore_tar_archive(src, paths.PROJECTS_DIR)
        cfg = load_config()
        cfg["current_project"] = str(target)
        save_config(cfg)
        return str(target)

    # default: session
    with src.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    session = payload.get("session") or {}
    messages = payload.get("messages") or []
    if not session:
        raise RuntimeError("import file is missing session data")

    try:
        with db.connect() as conn:
            conn.execute(
                "INSERT INTO sessions(id, started_at, ended_at, project, summary) VALUES (?,?,?,?,?)",
                (
                    session.get("id"),
                    session.get("started_at", db.now_iso()),
                    session.get("ended_at"),
                    session.get("project", ""),
                    session.get("summary", ""),
                ),
            )
            session_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
            for message in messages:
                conn.execute(
                    "INSERT INTO messages(session_id, role, content, model, created_at) VALUES (?,?,?,?,?)",
                    (
                        session_id,
                        message.get("role", ""),
                        message.get("content", ""),
                        message.get("model", ""),
                        message.get("created_at", db.now_iso()),
                    ),
                )
    except sqlite3.IntegrityError:
        with db.connect() as conn:
            conn.execute(
                "INSERT INTO sessions(started_at, ended_at, project, summary) VALUES (?,?,?,?)",
                (
                    session.get("started_at", db.now_iso()),
                    session.get("ended_at"),
                    session.get("project", ""),
                    session.get("summary", ""),
                ),
            )
            session_id = int(conn.execute("SELECT last_insert_rowid()").fetchone()[0])
            for message in messages:
                conn.execute(
                    "INSERT INTO messages(session_id, role, content, model, created_at) VALUES (?,?,?,?,?)",
                    (
                        session_id,
                        message.get("role", ""),
                        message.get("content", ""),
                        message.get("model", ""),
                        message.get("created_at", db.now_iso()),
                    ),
                )
    return str(src)
