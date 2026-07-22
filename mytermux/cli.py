"""Single dispatcher entrypoint for all my-* commands.

Invoked as `python -m mytermux <command> [args...]` OR through the thin
shell wrappers installed in $PREFIX/bin.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import chat as chat_mod
from . import db, export as export_mod, git_ops, heal as heal_mod, menu, paths, scanner, ui
from .config import load_config, save_config


def _bootstrap() -> None:
    """Ensure folders + db exist. Runs before every command."""
    paths.ensure_dirs()
    db.init_db()
    load_config()  # creates default if missing


def cmd_dashboard(args) -> int:
    _bootstrap()
    ui.dashboard(show_banner=True)
    return 0


def cmd_start(args) -> int:
    """Full startup: heal (if needed) then dashboard."""
    _bootstrap()
    # quick auto-heal on start (safe operations only)
    report = heal_mod.heal()
    fails = [c for c in report["after"] if not c["ok"] and "optional" not in c["name"]]
    if fails:
        print(f"[my-termux] startup notice: {len(fails)} issue(s) remain — run `my-fix`.")
    ui.dashboard(show_banner=True)
    return 0


def cmd_chat(args) -> int:
    _bootstrap()
    return chat_mod.run(resume=False)


def cmd_menu(args) -> int:
    _bootstrap()
    return menu.run()


def cmd_status(args) -> int:
    _bootstrap()
    ui.dashboard(show_banner=False)
    return 0


def cmd_scan(args) -> int:
    _bootstrap()
    path = args.path or "."
    info = scanner.scan(Path(path))
    for k, v in info.items():
        print(f"  {k}: {v}")
    # remember as current project
    if "path" in info:
        cfg = load_config()
        cfg["current_project"] = info["path"]
        save_config(cfg)
        print(f"[my-termux] current_project set to {info['path']}")
    return 0


def cmd_sync(args) -> int:
    _bootstrap()
    path = Path(args.path or ".").expanduser().resolve()
    if not (path / ".git").exists():
        print(f"[my-termux] {path} is not a git repo.")
        return 1
    print(f"-- branch: {git_ops.current_branch(path)}")
    print(git_ops.status(path))
    if args.pull:
        rc, out, err = git_ops.pull(path)
        print(out or err)
    if args.commit:
        rc, out, err = git_ops.commit_all(path, args.commit)
        print(out or err)
    if args.push:
        rc, out, err = git_ops.push(path)
        print(out or err)
    return 0


def cmd_fix(args) -> int:
    _bootstrap()
    report = heal_mod.heal()
    print("== self-heal report ==")
    for r in report["repairs"]:
        print(f"  {r['action']}: {'ok' if r['ok'] else 'fail'}")
    print("-- remaining checks --")
    for c in report["after"]:
        mark = "✓" if c["ok"] else ("~" if "optional" in c["name"] else "✗")
        print(f"  {mark} {c['name']:<32} {c['detail']}")
    if "log_path" in report:
        print(f"log: {report['log_path']}")
    return 0


def cmd_export(args) -> int:
    _bootstrap()
    what = args.what or "session"
    try:
        path = export_mod.export(what)
        print(f"[my-termux] exported {what}: {path}")
        return 0
    except RuntimeError as e:
        print(f"[error] {e}")
        return 1


def cmd_resume(args) -> int:
    _bootstrap()
    return chat_mod.run(resume=True)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="my-termux", description="my-termux AI workspace")
    sub = p.add_subparsers(dest="cmd")

    sub.add_parser("dashboard").set_defaults(func=cmd_dashboard)
    sub.add_parser("start").set_defaults(func=cmd_start)
    sub.add_parser("chat").set_defaults(func=cmd_chat)
    sub.add_parser("menu").set_defaults(func=cmd_menu)
    sub.add_parser("status").set_defaults(func=cmd_status)
    sub.add_parser("resume").set_defaults(func=cmd_resume)
    sub.add_parser("fix").set_defaults(func=cmd_fix)

    scan_p = sub.add_parser("scan")
    scan_p.add_argument("path", nargs="?", default=".")
    scan_p.set_defaults(func=cmd_scan)

    sync_p = sub.add_parser("sync")
    sync_p.add_argument("path", nargs="?", default=".")
    sync_p.add_argument("--pull", action="store_true")
    sync_p.add_argument("--commit", help="commit message to make with -a")
    sync_p.add_argument("--push", action="store_true")
    sync_p.set_defaults(func=cmd_sync)

    exp_p = sub.add_parser("export")
    exp_p.add_argument("what", nargs="?", default="session",
                       choices=["session", "config", "project"])
    exp_p.set_defaults(func=cmd_export)

    return p


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        return cmd_dashboard(argparse.Namespace())
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return 0
    return int(args.func(args) or 0)


if __name__ == "__main__":
    raise SystemExit(main())
