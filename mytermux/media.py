"""Local media vault for my-termux.

Keeps images/audio/video/docs organised under ~/my-termux/media/ and mirrors
them to Android-visible ~/storage/shared/MyTermux/media/ when available.
Also integrates with Termux camera/mic when installed.
"""
from __future__ import annotations

import hashlib
import mimetypes
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from . import db, paths


# ---- kind detection ---------------------------------------------------------

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".heic", ".heif", ".svg"}
VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".3gp", ".m4v"}
AUDIO_EXTS = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac", ".opus", ".amr"}
DOC_EXTS = {".pdf", ".txt", ".md", ".doc", ".docx", ".xls", ".xlsx", ".ppt",
            ".pptx", ".json", ".csv", ".yaml", ".yml", ".html", ".epub"}

KIND_DIRS = {
    "image": "images",
    "video": "video",
    "audio": "audio",
    "doc": "docs",
    "other": "other",
}


def detect_kind(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in IMAGE_EXTS:
        return "image"
    if ext in VIDEO_EXTS:
        return "video"
    if ext in AUDIO_EXTS:
        return "audio"
    if ext in DOC_EXTS:
        return "doc"
    # mimetype fallback
    mt, _ = mimetypes.guess_type(str(path))
    if mt:
        if mt.startswith("image/"):
            return "image"
        if mt.startswith("video/"):
            return "video"
        if mt.startswith("audio/"):
            return "audio"
        if mt.startswith("text/") or "pdf" in mt or "officedocument" in mt:
            return "doc"
    return "other"


# ---- paths ------------------------------------------------------------------

MEDIA_DIR = paths.HOME / "media"


def ensure_media_dirs() -> None:
    for sub in KIND_DIRS.values():
        (MEDIA_DIR / sub).mkdir(parents=True, exist_ok=True)
    # shared mirror
    shared_root = paths.SHARED_EXPORTS.parent / "media"
    try:
        shared_root.mkdir(parents=True, exist_ok=True)
        for sub in KIND_DIRS.values():
            (shared_root / sub).mkdir(parents=True, exist_ok=True)
    except Exception:
        pass


def shared_mirror_path(kind: str, filename: str) -> Optional[Path]:
    root = paths.SHARED_EXPORTS.parent / "media"
    if not root.parent.exists():
        return None
    p = root / KIND_DIRS.get(kind, "other") / filename
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
    except Exception:
        return None
    return p


# ---- db --------------------------------------------------------------------

MEDIA_SCHEMA = """
CREATE TABLE IF NOT EXISTS media (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT NOT NULL,
    kind TEXT NOT NULL,
    original_name TEXT,
    size_bytes INTEGER,
    sha256 TEXT,
    session_id INTEGER,
    project TEXT,
    tags TEXT,
    cloud_provider TEXT,
    cloud_public_id TEXT,
    cloud_url TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _ensure_schema() -> None:
    with db.connect() as conn:
        conn.executescript(MEDIA_SCHEMA)


def _sha256(path: Path, limit: int = 8 * 1024 * 1024) -> str:
    """Hash first `limit` bytes — good enough for de-dup on phones."""
    h = hashlib.sha256()
    try:
        with path.open("rb") as f:
            h.update(f.read(limit))
    except Exception:
        return ""
    return h.hexdigest()


# ---- public API ------------------------------------------------------------

def add(source: Path, kind: str = "", tags: str = "",
        session_id: Optional[int] = None, project: str = "",
        move: bool = False) -> Dict:
    """Import a file into the vault. Returns the media row as a dict."""
    _ensure_schema()
    ensure_media_dirs()

    src = Path(source).expanduser().resolve()
    if not src.exists() or not src.is_file():
        raise FileNotFoundError(f"not a file: {src}")

    k = kind or detect_kind(src)
    subdir = KIND_DIRS.get(k, "other")

    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    safe_name = f"{stamp}-{src.name}"
    dest = MEDIA_DIR / subdir / safe_name
    dest.parent.mkdir(parents=True, exist_ok=True)
    if move:
        shutil.move(str(src), str(dest))
    else:
        shutil.copy2(str(src), str(dest))

    # mirror to shared storage (best-effort)
    mirror = shared_mirror_path(k, safe_name)
    if mirror is not None:
        try:
            shutil.copy2(str(dest), str(mirror))
        except Exception:
            pass

    size = dest.stat().st_size
    digest = _sha256(dest)

    with db.connect() as conn:
        cur = conn.execute(
            """INSERT INTO media(path, kind, original_name, size_bytes, sha256,
                                 session_id, project, tags, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (str(dest), k, src.name, size, digest,
             session_id, project, tags, _now(), _now()),
        )
        mid = int(cur.lastrowid)

    db.log("info", "media", f"added #{mid} {k} {dest}")
    return get(mid)


def get(media_id: int) -> Dict:
    _ensure_schema()
    with db.connect() as conn:
        row = conn.execute("SELECT * FROM media WHERE id=?", (media_id,)).fetchone()
    if not row:
        raise KeyError(f"media #{media_id} not found")
    return dict(row)


def list_media(kind: str = "", session_id: Optional[int] = None,
               project: str = "", limit: int = 50) -> List[Dict]:
    _ensure_schema()
    q = "SELECT * FROM media WHERE 1=1"
    args: list = []
    if kind:
        q += " AND kind=?"; args.append(kind)
    if session_id is not None:
        q += " AND session_id=?"; args.append(session_id)
    if project:
        q += " AND project=?"; args.append(project)
    q += " ORDER BY id DESC LIMIT ?"
    args.append(limit)
    with db.connect() as conn:
        rows = conn.execute(q, args).fetchall()
    return [dict(r) for r in rows]


def remove(media_id: int, keep_file: bool = False) -> Dict:
    """Delete media record. Removes the local file unless keep_file=True.
    Does NOT touch cloud copies (use `cloud.destroy_asset` for that)."""
    row = get(media_id)
    p = Path(row["path"])
    if not keep_file and p.exists():
        try:
            p.unlink()
        except Exception:
            pass
    with db.connect() as conn:
        conn.execute("DELETE FROM media WHERE id=?", (media_id,))
    db.log("info", "media", f"removed #{media_id}")
    return row


def attach(media_id: int, session_id: Optional[int] = None, project: str = "",
           tags: str = "") -> Dict:
    """Link a media asset to a session / project / tag set."""
    row = get(media_id)
    with db.connect() as conn:
        conn.execute(
            """UPDATE media
                  SET session_id=COALESCE(?, session_id),
                      project=COALESCE(NULLIF(?, ''), project),
                      tags=COALESCE(NULLIF(?, ''), tags),
                      updated_at=?
                WHERE id=?""",
            (session_id, project, tags, _now(), media_id),
        )
    return get(media_id)


def set_cloud(media_id: int, provider: str, public_id: str, url: str) -> None:
    with db.connect() as conn:
        conn.execute(
            """UPDATE media
                  SET cloud_provider=?, cloud_public_id=?, cloud_url=?, updated_at=?
                WHERE id=?""",
            (provider, public_id, url, _now(), media_id),
        )


def clear_cloud(media_id: int) -> None:
    with db.connect() as conn:
        conn.execute(
            "UPDATE media SET cloud_provider=NULL, cloud_public_id=NULL, cloud_url=NULL, updated_at=? WHERE id=?",
            (_now(), media_id),
        )


def open_with_android(media_id: int) -> bool:
    """Open a media file with the phone's default app via `termux-open`."""
    row = get(media_id)
    if shutil.which("termux-open") is None:
        print(f"[media] termux-open not installed. File is at: {row['path']}")
        return False
    try:
        subprocess.run(["termux-open", row["path"]], check=False, timeout=5)
        return True
    except Exception:
        return False


# ---- capture (camera / mic) ------------------------------------------------

def capture_photo(camera_id: str = "0") -> Dict:
    """Take a photo via termux-camera-photo and import into the vault."""
    if shutil.which("termux-camera-photo") is None:
        raise RuntimeError("termux-camera-photo not installed. Run: pkg install termux-api")
    ensure_media_dirs()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    tmp = MEDIA_DIR / "images" / f"cam-{stamp}.jpg"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["termux-camera-photo", "-c", camera_id, str(tmp)],
                   check=False, timeout=30)
    if not tmp.exists() or tmp.stat().st_size == 0:
        raise RuntimeError("photo capture failed or was cancelled")
    return add(tmp, kind="image", move=True, tags="camera")


def record_audio(seconds: int = 10) -> Dict:
    """Record audio via termux-microphone-record and import into the vault."""
    if shutil.which("termux-microphone-record") is None:
        raise RuntimeError("termux-microphone-record not installed. Run: pkg install termux-api")
    ensure_media_dirs()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    tmp = MEDIA_DIR / "audio" / f"rec-{stamp}.m4a"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    # start
    subprocess.run(["termux-microphone-record", "-f", str(tmp), "-l", str(seconds)],
                   check=False, timeout=seconds + 10)
    if not tmp.exists() or tmp.stat().st_size == 0:
        raise RuntimeError("audio record failed or was cancelled")
    return add(tmp, kind="audio", move=True, tags="mic")
