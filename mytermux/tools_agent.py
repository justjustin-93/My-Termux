"""Agent tool registry for my-termux.

Each tool has:
  - name           : short id used in <tool name="…"> blocks
  - description    : shown to the model in the system prompt
  - args_schema    : dict of arg_name -> description
  - safety         : "safe" | "confirm" | "danger"
  - fn(args) -> str: returns an observation string given a dict of args

Tool executors are pure Python — no network unless the tool explicitly uses one.
Observations are truncated to keep the model's context small.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Callable, Dict, List

from . import db, scanner, tools, git_ops, notify, media


MAX_OBSERVATION_CHARS = 4000


def _clip(s: str, n: int = MAX_OBSERVATION_CHARS) -> str:
    if len(s) <= n:
        return s
    return s[:n] + f"\n… [truncated {len(s) - n} chars]"


# ---------------- individual tools -----------------------------------------

def _tool_shell(args: Dict) -> str:
    cmd = args.get("cmd", "").strip()
    if not cmd:
        return "error: missing 'cmd'"
    cwd = args.get("cwd")
    rc, out, err = tools.run_shell(cmd, cwd=Path(cwd).expanduser() if cwd else None,
                                    timeout=int(args.get("timeout", 30)))
    return _clip(f"exit_code: {rc}\nstdout:\n{out}\nstderr:\n{err}")


def _tool_read_file(args: Dict) -> str:
    p = Path(args.get("path", "")).expanduser()
    max_bytes = int(args.get("max_bytes", 8000))
    if not p.exists():
        return f"error: not found: {p}"
    if p.is_dir():
        return f"error: '{p}' is a directory. Use list_dir."
    content = tools.read_file(p, max_bytes=max_bytes)
    return _clip(f"path: {p}\nbytes_read: {len(content)}\n---\n{content}")


def _tool_write_file(args: Dict) -> str:
    p = Path(args.get("path", "")).expanduser()
    content = args.get("content", "")
    if not p.parent.exists():
        return f"error: parent dir missing: {p.parent}"
    tools.write_file(p, content, backup=True)
    return f"wrote {len(content)} bytes to {p} (backup: {p}.bak if existed)"


def _tool_list_dir(args: Dict) -> str:
    p = Path(args.get("path", ".")).expanduser()
    if not p.exists():
        return f"error: not found: {p}"
    if not p.is_dir():
        return f"error: '{p}' is not a directory"
    entries = []
    for child in sorted(p.iterdir())[:200]:
        kind = "d" if child.is_dir() else "f"
        size = child.stat().st_size if child.is_file() else 0
        entries.append(f"  {kind} {size:>10} {child.name}")
    return _clip(f"path: {p}\nentries: {len(entries)}\n" + "\n".join(entries))


def _tool_scan_project(args: Dict) -> str:
    p = Path(args.get("path", ".")).expanduser()
    info = scanner.scan(p)
    return json.dumps(info, indent=2, default=str)


def _tool_git(args: Dict) -> str:
    action = args.get("action", "status")
    repo = Path(args.get("path", ".")).expanduser().resolve()
    if not (repo / ".git").exists():
        return f"error: not a git repo: {repo}"
    if action == "status":
        return _clip(f"branch: {git_ops.current_branch(repo)}\n{git_ops.status(repo)}")
    if action == "log":
        rc, out, err = git_ops.run(["git", "log", "--oneline", "-20"], cwd=repo)
        return _clip(out or err)
    if action == "diff":
        rc, out, err = git_ops.run(["git", "diff", "--stat"], cwd=repo)
        return _clip(out or err)
    if action == "branch":
        rc, out, err = git_ops.run(["git", "branch", "-vv"], cwd=repo)
        return _clip(out or err)
    return f"error: unknown git action '{action}'. Allowed: status, log, diff, branch."


def _tool_media_list(args: Dict) -> str:
    kind = args.get("kind", "")
    rows = media.list_media(kind=kind, limit=20)
    if not rows:
        return "media vault is empty"
    lines = [f"#{r['id']} {r['kind']:<6} {r.get('original_name') or Path(r['path']).name}"
             + (" [cloud]" if r.get('cloud_public_id') else "")
             for r in rows]
    return "\n".join(lines)


def _tool_add_task(args: Dict) -> str:
    title = args.get("title", "").strip()
    if not title:
        return "error: missing 'title'"
    tid = db.add_task(title, project=args.get("project", ""),
                      priority=int(args.get("priority", 3)))
    return f"task #{tid} added: {title}"


def _tool_add_goal(args: Dict) -> str:
    title = args.get("title", "").strip()
    if not title:
        return "error: missing 'title'"
    gid = db.add_goal(title, project=args.get("project", ""))
    return f"goal #{gid} added: {title}"


def _tool_notify(args: Dict) -> str:
    ok = notify.notify(args.get("title", "my-termux"),
                       args.get("content", ""),
                       priority=args.get("priority", "default"))
    return "notification sent" if ok else "notification skipped (no termux-api or disabled)"


def _tool_web_search(args: Dict) -> str:
    """DuckDuckGo Instant Answer API — free, no key."""
    q = args.get("query", "").strip()
    if not q:
        return "error: missing 'query'"
    try:
        import httpx
    except ImportError:
        return "error: httpx not installed"
    try:
        with httpx.Client(timeout=15.0, follow_redirects=True) as c:
            r = c.get("https://api.duckduckgo.com/",
                      params={"q": q, "format": "json", "no_html": 1, "skip_disambig": 1})
            r.raise_for_status()
            data = r.json()
    except Exception as e:
        return f"error: web_search failed: {e}"
    lines = []
    if data.get("AbstractText"):
        lines.append(f"summary: {data['AbstractText']}")
        if data.get("AbstractURL"):
            lines.append(f"source: {data['AbstractURL']}")
    for t in (data.get("RelatedTopics") or [])[:5]:
        if isinstance(t, dict) and t.get("Text"):
            lines.append(f"- {t['Text']}")
            if t.get("FirstURL"):
                lines.append(f"  {t['FirstURL']}")
    if not lines:
        return f"no direct answer for: {q}. Try more specific keywords."
    return _clip("\n".join(lines))


def _tool_finish(args: Dict) -> str:
    return "__FINISH__"


# ---------------- registry --------------------------------------------------

class Tool:
    def __init__(self, name: str, desc: str, schema: Dict[str, str],
                 fn: Callable[[Dict], str], safety: str = "safe"):
        self.name = name
        self.desc = desc
        self.schema = schema
        self.fn = fn
        self.safety = safety  # "safe" | "confirm" | "danger"


REGISTRY: Dict[str, Tool] = {
    "shell": Tool("shell",
                  "Run a shell command in Termux. Use for ls, cat, grep, python -c, etc. "
                  "Do NOT use for destructive ops (rm -rf, mkfs).",
                  {"cmd": "command string", "cwd": "optional working dir",
                   "timeout": "seconds (default 30)"},
                  _tool_shell, safety="confirm"),
    "read_file": Tool("read_file",
                      "Read a file's contents (first max_bytes bytes).",
                      {"path": "file path", "max_bytes": "int, default 8000"},
                      _tool_read_file, safety="safe"),
    "write_file": Tool("write_file",
                       "Write content to a file. Creates a .bak of the previous version.",
                       {"path": "file path", "content": "full new content as string"},
                       _tool_write_file, safety="confirm"),
    "list_dir": Tool("list_dir",
                     "List entries in a directory (up to 200).",
                     {"path": "directory path"},
                     _tool_list_dir, safety="safe"),
    "scan_project": Tool("scan_project",
                         "Detect project kind (python/node/rust/…), git presence, file counts.",
                         {"path": "project root"},
                         _tool_scan_project, safety="safe"),
    "git": Tool("git",
                "Read-only git ops on a local repo. Actions: status, log, diff, branch. "
                "Push/commit are intentionally NOT available — user runs those with `my-sync`.",
                {"action": "status|log|diff|branch", "path": "repo path"},
                _tool_git, safety="safe"),
    "media_list": Tool("media_list",
                       "List entries in the local media vault.",
                       {"kind": "optional: image|video|audio|doc|other"},
                       _tool_media_list, safety="safe"),
    "add_task": Tool("add_task",
                     "Add a pending task to the user's task list.",
                     {"title": "short task title", "project": "optional",
                      "priority": "1-5 (1 = highest)"},
                     _tool_add_task, safety="safe"),
    "add_goal": Tool("add_goal",
                     "Add a higher-level goal.",
                     {"title": "goal title", "project": "optional"},
                     _tool_add_goal, safety="safe"),
    "notify": Tool("notify",
                   "Send a Termux notification to the user's phone.",
                   {"title": "notification title", "content": "body",
                    "priority": "low|default|high"},
                   _tool_notify, safety="safe"),
    "web_search": Tool("web_search",
                       "Search the web via DuckDuckGo Instant Answer (free, no key). "
                       "Best for definitions, docs, quick facts. Returns summaries + links.",
                       {"query": "search text"},
                       _tool_web_search, safety="safe"),
    "finish": Tool("finish",
                   "Signal you are done and don't need another turn. Use when you have "
                   "given your final answer + next-step suggestions.",
                   {},
                   _tool_finish, safety="safe"),
}


def describe_tools() -> str:
    """Render the tool descriptions as a compact string for the system prompt."""
    lines = []
    for t in REGISTRY.values():
        schema = ", ".join(f"{k}={v}" for k, v in t.schema.items()) or "(no args)"
        lines.append(f"- {t.name}({schema}): {t.desc}")
    return "\n".join(lines)


def run_tool(name: str, args: Dict) -> str:
    t = REGISTRY.get(name)
    if t is None:
        return f"error: unknown tool '{name}'. Available: {', '.join(REGISTRY)}"
    try:
        return t.fn(args or {})
    except Exception as e:
        return f"error: tool '{name}' raised: {type(e).__name__}: {e}"


def is_dangerous(name: str, args: Dict) -> bool:
    """Return True if this tool call needs user confirmation."""
    t = REGISTRY.get(name)
    if t is None:
        return False
    if t.safety == "danger":
        return True
    if t.safety == "confirm":
        if name == "shell":
            return tools.is_dangerous(args.get("cmd", ""))
        if name == "write_file":
            # writing to protected paths always confirms
            p = str(Path(args.get("path", "")).expanduser())
            protected_prefixes = ("/data/data/com.termux/files/usr/",)
            return p.startswith(protected_prefixes) or p.endswith(".bashrc") or p.endswith("/config.yaml")
    return False
