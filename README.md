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
- **Real agent brain** (not just a chatbot): visible `<think>` reasoning, self-directed
  tool use — `shell`, `read_file`, `write_file`, `list_dir`, `scan_project`, `git`,
  `media_list`, `add_task`, `add_goal`, `notify`, `web_search`, `finish`. Multi-hop
  loop up to `MYTERMUX_AGENT_MAX_HOPS` (default 6). Dangerous shell / protected file
  writes ask you to confirm.
- **Local SQLite memory** for sessions, goals, tasks, logs, repairs and projects.
- **Proactive planner** — suggests 2–4 concrete next actions after each activity.
- **Self-heal** — startup diagnostics + safe auto-repair, with backups.
- **GitHub over PAT** — clone, status, pull, commit, push right from the CLI.
- **Project scanner** that detects Python / Node / Rust / Go / Java / etc.
- **Android-visible exports** to `/sdcard/MyTermux/exports/` (sessions, config, whole projects).
- **Termux notifications** via `termux-notification` (stub for future WhatsApp/SMS hooks).

## Install (Termux, phone only)

### Quick install from a GitHub repo

```bash
pkg update && pkg install -y git
git clone https://github.com/<you>/<repo>.git ~/my-termux-src
cd ~/my-termux-src && bash install.sh
```

### Or copy the source to your phone manually
Zip the source, put it somewhere on your phone (Drive / USB / email), then:
```bash
cd ~
unzip /storage/shared/Download/my-termux.zip -d my-termux-src
cd my-termux-src && bash install.sh
```

### Finding the correct photo path
Camera photos live at `~/storage/shared/DCIM/Camera/` **after** you've granted
storage permission (the installer does this via `termux-setup-storage`). To find
a real filename, list the folder first — don't type `<some-photo>.jpg` literally:

```bash
ls ~/storage/shared/DCIM/Camera/
my-media add ~/storage/shared/DCIM/Camera/IMG_<TAB>     # Tab auto-completes
```

### What the installer does

### What the installer does

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
| `my-media …`        | Local media vault: `add`, `list`, `info`, `open`, `rm`, `attach`, `capture`, `record` |
| `my-cloud …`        | Optional Cloudinary sync: `setup`, `status`, `sync`, `up`, `pull`, `rm`, `list` |

Inside chat, slash-commands work too: `/help /new /resume /project X /goal X /task X /suggest /q`.

## File & media storage

### Local vault (always on, offline, free)

```bash
my-media add ~/Downloads/photo.jpg              # copy into ~/my-termux/media/images/
my-media add ~/song.mp3 --tags "music,relax"    # tag on import
my-media list --kind image                      # filter by kind
my-media open 3                                 # open with phone's default app
my-media capture                                # snap a photo (needs termux-api)
my-media record 15                              # record 15s of audio
my-media attach 3 --session 12 --project foo    # link media to a chat/project
my-media rm 3 --keep-file                       # unregister but keep the file
```

Files land under `~/my-termux/media/{images,video,audio,docs,other}/` and are
mirrored to `~/storage/shared/MyTermux/media/…` so they show up in your Android
Gallery / Files app automatically (after `termux-setup-storage` — the installer
does that for you).

### Optional Cloudinary cloud sync (free tier, 25 GB)

Cloud sync is **entirely optional**. Everything above works fully offline
without it. When you're ready:

1. Sign up free at [cloudinary.com](https://cloudinary.com/console).
2. From your Dashboard copy `cloud_name`, `api_key`, `api_secret`.
3. Run:
   ```bash
   my-cloud setup           # paste the three values once
   my-cloud sync            # upload every un-synced local media asset
   my-cloud list            # see what's in the cloud
   my-cloud pull 12         # restore a specific asset back to the phone
   my-cloud rm 12 --also-local   # delete from cloud (optionally locally too)
   ```

Behind the scenes:

- images → `resource_type=image`
- videos → `resource_type=video`
- audio  → `resource_type=video` (Cloudinary treats audio as video)
- docs / other → `resource_type=raw`
- Every asset lives under `my-termux/<kind>/<basename>` in your Cloudinary account,
  so it's easy to find and delete from the Cloudinary dashboard too.

If creds are missing, `my-cloud` prints a helpful error and the vault keeps
working locally — no network, no crash.



```
~/my-termux/
├── app/                # installed source (do not edit — reinstall to update)
├── projects/           # any working projects you create locally
├── sessions/           # future: per-session exports
├── logs/               # repair logs (repair-YYYYMMDD-hhmmss.json)
├── config/config.yaml  # your API keys and preferences
├── backups/            # rolling config backups
├── media/              # local media vault
│   ├── images/
│   ├── video/
│   ├── audio/
│   ├── docs/
│   └── other/
└── mytermux.db         # SQLite: sessions, messages, goals, tasks, logs, repairs, projects, media

~/storage/shared/MyTermux/
├── exports/            # session/config/project exports (Android-visible)
└── media/              # mirror of the local media vault (Android-visible)
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
cloudinary_cloud_name: ""                # optional, for `my-cloud`
cloudinary_api_key: ""
cloudinary_api_secret: ""
media_auto_sync: false
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
elegram) can be added without touching
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
