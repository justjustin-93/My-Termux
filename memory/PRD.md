# my-termux — Product Requirements Doc

## Original problem statement
A Termux-only AI agent workspace for the user's phone that:
- stays free (OpenRouter free-model routing only)
- stores everything locally under `~/my-termux/`
- supports GitHub, internet research, proactive next-step reasoning, self-heal
- launches into a custom-branded environment (custom prompt + dashboard) via named commands (`my-termux`, `my-chat`, ...)
- has optional Termux notifications now, and a stub for future WhatsApp/SMS

## User choices (from ask_human)
- Deliverable: `install.sh` + source tree, installed globally on the phone.
- OpenRouter: enter key during first-run wizard; use best free model with fallback.
- Auto-launch dashboard on Termux open: **Yes** (via `.bashrc`).
- GitHub auth via Personal Access Token: **Yes**.
- v1 messaging: local Termux notifications only, stub for future integrations: **Yes**.

## Architecture
- Language: Python 3 + Bash. No web server. Pure CLI running under Termux.
- Python package `mytermux/` with modules:
  `paths.py, config.py, db.py (SQLite), openrouter.py (httpx streaming w/ fallback),
   memory.py, planner.py, notify.py, scanner.py, git_ops.py, tools.py, heal.py,
   ui.py (rich), chat.py, menu.py, export.py, cli.py, __main__.py, assets/banner.txt`
- Single dispatch script `bin/mytermux-dispatch` — every `my-*` alias is a symlink to it
  and the script routes to a subcommand based on `$0`.
- `install.sh` — Termux-guarded, idempotent installer: `pkg install`, source copy,
  data folders, storage permission, `pip install httpx rich pyyaml`, symlinks in
  `$PREFIX/bin`, `.bashrc` block with custom PS1 + auto-`start-my-termux`, first-run wizard.
- `uninstall.sh` — removes symlinks + `.bashrc` block, asks before deleting data.
- Storage layout: `~/my-termux/{app,projects,sessions,logs,config,backups}` +
  Android-visible `~/storage/shared/MyTermux/exports/`.
- Persistence: SQLite (`~/my-termux/mytermux.db`) for sessions, messages, goals,
  tasks, logs, repairs, projects. YAML for config, JSON for exports/repair logs.

## What's been implemented (2026-01)
- Full Python package with dashboard, chat, menu, scan, sync, fix, export, resume.
- Rich terminal UI with status card + proactive next-actions card.
- OpenRouter streaming client with ordered free-model fallback:
  `deepseek/deepseek-chat-v3.1:free → google/gemini-2.0-flash-exp:free →
   meta-llama/llama-3.3-70b-instruct:free → openrouter/auto`
  Honours `Retry-After`, does not fallback mid-stream, records logs.
- SQLite schema + full CRUD helpers for all entities.
- Project scanner (Python/Node/Rust/Go/Java/Ruby/PHP/Docker + git detection).
- Git helpers with PAT injection for HTTPS clones/push.
- Self-heal: checks dirs/config/db/pip/binaries and auto-repairs safely; writes JSON log.
- Termux notifications (silent no-op off-Termux), stub for future WhatsApp/SMS.
- Idempotent installer & uninstaller.
- **28 pytest tests, all passing.** Full CLI smoke-tested (dashboard, fix, scan, export).

## Prioritized backlog
- P1: Ship v1 as-is to phone; verify on real Termux.
- P2: Add `my-import` (inverse of export) and cross-project session linking.
- P2: LLM-backed planner suggestions layered on top of local rules.
- P2: Termux widget/shortcut integration (`termux-create-launcher`).
- P3: WhatsApp integration hook (WA Business API or third-party).
- P3: SMS bridge via `termux-sms-send`.
- P3: Optional encrypted-at-rest config (age/gpg).
- P3: Web-search tool for the agent (SerpAPI or duckduckgo-search).

## Files of note
- `/app/install.sh`, `/app/uninstall.sh`
- `/app/bin/mytermux-dispatch`
- `/app/mytermux/**/*.py`
- `/app/tests/test_mytermux.py` (28 tests)
- `/app/README.md`
