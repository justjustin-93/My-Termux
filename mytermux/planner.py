"""Brain / proactive planner — figures out what the user should do next.

Uses local signals only (no LLM calls) so it's fast, offline-friendly and cheap.
The LLM chat layer can layer on additional suggestions on top of this.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List

from . import db, paths
from .config import load_config


def current_state() -> Dict:
    cfg = load_config()
    last = db.get_last_session()
    pending = db.list_pending_tasks(limit=5)
    projects = db.list_projects()
    current_project = cfg.get("current_project", "")
    return {
        "api_configured": bool(cfg.get("openrouter_api_key")),
        "github_configured": bool(cfg.get("github_token")),
        "current_project": current_project,
        "last_session_id": last["id"] if last else None,
        "last_session_project": (last["project"] if last else "") or "",
        "pending_tasks": [dict(r) for r in pending],
        "projects_count": len(projects),
        "notifications_on": bool(cfg.get("notifications", True)),
    }


def next_actions() -> List[Dict]:
    """Return a ranked list of proactive next actions."""
    st = current_state()
    actions: List[Dict] = []

    if not st["api_configured"]:
        actions.append({
            "cmd": "my-menu",
            "why": "OpenRouter API key not set — chat won't work yet.",
            "action": "Open Settings and paste your OpenRouter key.",
            "priority": 1,
        })
    if not st["github_configured"]:
        actions.append({
            "cmd": "my-menu",
            "why": "GitHub token not configured.",
            "action": "Add a Personal Access Token to enable clone/pull/push.",
            "priority": 3,
        })

    if st["last_session_id"]:
        actions.append({
            "cmd": "my-resume",
            "why": f"You had an open session (#{st['last_session_id']}"
                   + (f" on {st['last_session_project']}" if st['last_session_project'] else "")
                   + ").",
            "action": "Resume your last chat and keep going.",
            "priority": 2,
        })

    if st["current_project"]:
        p = Path(st["current_project"]).expanduser()
        if p.exists():
            actions.append({
                "cmd": f"my-scan {p}",
                "why": f"Current project: {p.name}",
                "action": "Re-scan to refresh dependency and git status.",
                "priority": 2,
            })
            actions.append({
                "cmd": f"my-chat",
                "why": f"Keep momentum on {p.name}.",
                "action": "Ask the agent to inspect files, tests, or TODOs in the current project.",
                "priority": 2,
            })

    if st["pending_tasks"]:
        top = st["pending_tasks"][0]
        actions.append({
            "cmd": "my-menu",
            "why": f"{len(st['pending_tasks'])} pending task(s).",
            "action": f"Work on: {top['title']}",
            "priority": 2,
        })

    if not st["projects_count"]:
        actions.append({
            "cmd": "my-scan ~",
            "why": "No projects registered yet.",
            "action": "Scan a folder to register your first project.",
            "priority": 4,
        })

    if st["projects_count"]:
        actions.append({
            "cmd": "my-scan .",
            "why": "You already have registered projects.",
            "action": "Scan the current directory or switch to another project to broaden the workspace.",
            "priority": 4,
        })

    actions.append({
        "cmd": "my-fix",
        "why": "Keep your environment healthy.",
        "action": "Run diagnostics + auto-repair.",
        "priority": 5,
    })
    actions.append({
        "cmd": "my-media capture",
        "why": "You are on a phone with Termux media tools.",
        "action": "Capture a photo or record audio if the task involves media or evidence.",
        "priority": 5,
    })
    actions.append({
        "cmd": "my-chat",
        "why": "Jump straight in.",
        "action": "Ask the agent anything, or ask it to propose a next step from the current context.",
        "priority": 5,
    })

    actions.sort(key=lambda a: a["priority"])
    return actions[:6]
