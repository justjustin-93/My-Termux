"""Session + long-term memory helpers built on the sqlite layer."""
from __future__ import annotations

from typing import List, Optional

from . import db


SYSTEM_PROMPT = (
    "You are my-termux, a proactive on-device AI agent living in Termux on the user's phone. "
    "Be concise, terminal-friendly, and always end helpful answers with 2-4 concrete "
    "next-step suggestions the user can take. Prefer safe, reversible actions and "
    "flag destructive shell commands clearly."
)


class Conversation:
    """A lightweight session-aware conversation buffer backed by SQLite."""

    def __init__(self, session_id: Optional[int] = None, project: str = "", max_turns: int = 30):
        self.project = project
        self.max_turns = max_turns
        self.session_id = session_id if session_id is not None else db.start_session(project)

    def load_history(self) -> List[dict]:
        rows = db.get_session_messages(self.session_id)
        return [{"role": r["role"], "content": r["content"]} for r in rows]

    def build_messages(self, user_text: str) -> List[dict]:
        history = self.load_history()
        # keep last N turns
        trimmed = history[-self.max_turns * 2:]
        return [{"role": "system", "content": SYSTEM_PROMPT}, *trimmed,
                {"role": "user", "content": user_text}]

    def record_user(self, text: str) -> None:
        db.add_message(self.session_id, "user", text)

    def record_assistant(self, text: str, model: str = "") -> None:
        db.add_message(self.session_id, "assistant", text, model=model)

    def close(self, summary: str = "") -> None:
        db.end_session(self.session_id, summary)


def resume_last() -> Optional[Conversation]:
    row = db.get_last_session()
    if not row:
        return None
    return Conversation(session_id=int(row["id"]), project=row["project"] or "")
