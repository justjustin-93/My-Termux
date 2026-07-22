# my-termux

A **Termux-only, phone-first AI agent workspace** that turns your Android phone
into a personalised terminal environment. It launches into a branded dashboard,
remembers your sessions and projects, uses **free OpenRouter models**, talks to
GitHub, thinks ahead about your next steps, and repairs itself when it breaks —
all stored locally on your phone, all free.

```
   ┌────────────────────────────────────────────────────────────┐
   │   my-termux  ~/projects/foo $                              │
   │   ✓ OpenRouter API   ✓ GitHub    ~ current project         │
   │   ✓ last session #12 (2 unfinished tasks)                  │
   │                                                            │
   │   next steps:                                              │
   │     1. my-resume   → continue what you were doing          │
   │     2. my-scan .   → refresh project state                 │
   │     3. my-chat     → ask the agent anything                │
   └────────────────────────────────────────────────────────────┘
```

## Features

- **Branded launch** — custom banner, `my-termux` prompt, status dashboard on every open.
- **Named commands** instead of a bare terminal:
  `my-termux`, `start-my-termux`, `my-chat`, `my-menu`, `my-status`, `my-scan`,
  `my-sync`, `my-fix`, `my-export`, `my-resume`.
- **Free OpenRouter routing** with automatic fallback across free models
  (`deepseek/deepseek-chat-v3.1:free` → `google/gemini-2.0-flash-exp:free` →
  `meta-llama/llama-3.3-70b-instruct:free` → `openrouter/auto`).
- **Local SQLite memory** for sessions, goals, tasks, logs, repairs and projects.
- **Proactive planner** — suggests 2–4 concrete next actions after each activity.
- **Self-heal** — startup diagnostics + safe auto-repair, with backups.
- **GitHub over PAT** — clone, status, pull, commit, push right from the CLI.
- **Project scanner** that detects Python / Node / Rust / Go / Java / etc.
- **Android-visible exports** to `/sdcard/MyTermux/exports/` (sessions, config, whole projects).
- **Termux notifications** via `termux-notification` (stub for future WhatsApp/SMS hooks).

## Install (Termux, phone only)

```bash
pkg update && pkg install -y git
git clone https://github.com/your-user/my-termux ~/my-termux-src   # or copy the folder in
cd ~/my-termux-src
bash install.sh
```

The installer:

1. Installs `python`, `git`, `termux-api`.
2. Copies source to `~/my-termux/app/`.
3. Creates `~/my-termux/{projects,sessions,logs,config,backups}`.
4. Runs `termux-setup-storage` and links `/sdcard/MyTermux/exports/`.
5. `pip install httpx rich pyyaml`.
6. Installs global commands into `$PREFIX/bin/` (works from any folder).
7. Adds a compact block to `~/.bashrc` — custom prompt + auto-dashboard.
8. Runs a **first-run wizard** to save your OpenRouter key and optional GitHub PAT
   into `~/my-termux/config/config.yaml`.

Skip auto-dashboard temporarily with `MYTERMUX_NO_AUTOSTART=1 bash`.
Uninstall with `bash uninstall.sh` (asks before deleting data).

## Commands

| Command             | What it does                                                          |
| ------------------- | --------------------------------------------------------------------- |
| `my-termux`         | Show dashboard (banner + status + proactive next actions)             |
| `start-my-termux`   | Auto-heal on boot, then dashboard                                     |
| `my-chat`           | Enter interactive chat (streaming, free models)                       |
| `my-menu`           | Numeric guided menu (settings, scan, sync, fix, export…)              |
| `my-status`         | Same status card as the dashboard, no banner                          |
| `my-scan [PATH]`    | Scan a project, detect kind + git, register it, set current           |
| `my-sync [PATH]`    | `git status`; optional `--pull`, `--commit "msg"`, `--push`           |
| `my-fix`            | Run diagnostics + safe self-repair; writes JSON log in `~/my-termux/logs/` |
| `my-export [WHAT]`  | Export `session` / `config` / `project` to `/sdcard/MyTermux/exports/` |
| `my-resume`         | Resume the last chat session (with full history)                      |

Inside chat, slash-commands work too: `/help /new /resume /project X /goal X /task X /suggest /q`.

## Data layout on the phone

```
~/my-termux/
├── app/                # installed source (do not edit — reinstall to update)
├── projects/           # any working projects you create locally
├── sessions/           # future: per-session exports
├── logs/               # repair logs (repair-YYYYMMDD-hhmmss.json)
├── config/config.yaml  # your API keys and preferences
├── backups/            # rolling config backups
└── mytermux.db         # SQLite: sessions, messages, goals, tasks, logs, repairs, projects

~/storage/shared/MyTermux/exports/   # Android-visible exports (post storage permission)
```

## Config file (`~/my-termux/config/config.yaml`)

```yaml
openrouter_api_key: sk-or-v1-...        # required for chat
openrouter_title: my-termux
model_order:
  - deepseek/deepseek-chat-v3.1:free
  - google/gemini-2.0-flash-exp:free
  - meta-llama/llama-3.3-70b-instruct:free
  - openrouter/auto
github_token: ghp_...                    # optional, for git push over HTTPS
github_username: your-user
current_project: /data/data/com.termux/files/home/projects/foo
auto_dashboard: true
notifications: true
theme: dark
```

## Phone-number / messaging integration (v1 notes)

Per your own recommendation, **v1 ships with local Termux notifications only**
(`termux-notification`). A `notify` stub is exposed in `mytermux/notify.py` so
future integrations (WhatsApp, SMS, Telegram) can be added without touching
the rest of the codebase — just add another sender behind the same `notify()`
call.

## OpenRouter free models — recommendation

Currently the best free default is `deepseek/deepseek-chat-v3.1:free` for
reasoning/coding, with the fast `google/gemini-2.0-flash-exp:free` and
multilingual `meta-llama/llama-3.3-70b-instruct:free` as fallbacks, and finally
the `openrouter/auto` router. This ordered list lives in your config; edit it
freely — the client falls back automatically on transient errors and honours
`Retry-After` on 429s.

## License

MIT — do whatever you want, but don't ship your API key to anyone.
