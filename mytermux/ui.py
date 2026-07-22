"""Terminal UI — dashboard, menus, banners. Uses `rich` if available, else plain."""
from __future__ import annotations

from typing import Dict, List, Optional

from . import db, paths, planner
from .config import load_config


def _rich():
    try:
        from rich.console import Console
        from rich.panel import Panel
        from rich.table import Table
        from rich.text import Text
        from rich.align import Align
        return Console, Panel, Table, Text, Align
    except Exception:
        return None


BANNER = r"""
                       __                                      
   ____ ___  __  __   / /____  _________ ___  __  ___  __      
  / __ `__ \/ / / /  / __/ _ \/ ___/ __ `__ \/ / / / |/_/      
 / / / / / / /_/ /  / /_/  __/ /  / / / / / / /_/ />  <        
/_/ /_/ /_/\__, /   \__/\___/_/  /_/ /_/ /_/\__,_/_/|_|        
          /____/   your phone. your agent. your workspace.     
"""


def read_banner() -> str:
    try:
        if paths.BANNER_FILE.exists():
            return paths.BANNER_FILE.read_text(encoding="utf-8")
    except Exception:
        pass
    return BANNER


def _status_rows(cfg: dict, state: dict) -> List[tuple]:
    return [
        ("OpenRouter API", "ok" if state["api_configured"] else "missing",
         cfg.get("openrouter_title", "my-termux")),
        ("GitHub token", "ok" if state["github_configured"] else "missing",
         cfg.get("github_username", "") or "-"),
        ("Current project", "ok" if state["current_project"] else "-",
         state["current_project"] or "(none)"),
        ("Last session", "ok" if state["last_session_id"] else "-",
         f"#{state['last_session_id']}" if state["last_session_id"] else "(none)"),
        ("Pending tasks", "ok" if state["pending_tasks"] else "-",
         str(len(state["pending_tasks"]))),
        ("Notifications", "on" if state["notifications_on"] else "off", ""),
    ]


def dashboard(show_banner: bool = True) -> None:
    cfg = load_config()
    state = planner.current_state()
    actions = planner.next_actions()

    r = _rich()
    if r is None:
        # plain-text fallback
        if show_banner:
            print(read_banner())
        print("=" * 60)
        print("  my-termux — status")
        print("=" * 60)
        for name, status, extra in _status_rows(cfg, state):
            print(f"  {name:<20} {status:<10} {extra}")
        print("-" * 60)
        print("  Next actions:")
        for i, a in enumerate(actions, 1):
            print(f"   {i}. [{a['cmd']}] {a['action']}")
            print(f"      why: {a['why']}")
        print("=" * 60)
        print("  Try: my-chat  |  my-menu  |  my-resume  |  my-fix\n")
        return

    Console, Panel, Table, Text, Align = r
    con = Console()
    if show_banner:
        con.print(Text(read_banner(), style="bold cyan"))

    tbl = Table(show_header=False, expand=True, box=None, padding=(0, 1))
    tbl.add_column(style="bold")
    tbl.add_column()
    tbl.add_column(style="dim")
    for name, status, extra in _status_rows(cfg, state):
        color = "green" if status in ("ok", "on") else ("yellow" if status == "-" else "red")
        tbl.add_row(name, f"[{color}]{status}[/{color}]", extra)
    con.print(Panel(tbl, title="[bold cyan]status[/bold cyan]",
                    border_style="cyan", padding=(1, 2)))

    act = Table(show_header=True, header_style="bold magenta", box=None, expand=True)
    act.add_column("#", width=3)
    act.add_column("run", style="bold green")
    act.add_column("what")
    act.add_column("why", style="dim")
    for i, a in enumerate(actions, 1):
        act.add_row(str(i), a["cmd"], a["action"], a["why"])
    con.print(Panel(act, title="[bold magenta]proactive next steps[/bold magenta]",
                    border_style="magenta", padding=(1, 2)))

    con.print(
        "[dim]commands:[/dim] "
        "[bold]my-chat[/bold]  [bold]my-menu[/bold]  [bold]my-resume[/bold]  "
        "[bold]my-scan[/bold]  [bold]my-sync[/bold]  [bold]my-fix[/bold]  "
        "[bold]my-export[/bold]  [bold]my-status[/bold]\n"
    )


MENU_ITEMS = [
    ("Chat with agent", "chat"),
    ("Resume last session", "resume"),
    ("Scan a project", "scan"),
    ("GitHub sync (status)", "sync"),
    ("Run self-heal", "fix"),
    ("Export data", "export"),
    ("Settings", "settings"),
    ("Show status", "status"),
    ("Exit", "exit"),
]


def print_menu() -> None:
    r = _rich()
    if r is None:
        print("\n== my-termux menu ==")
        for i, (label, _) in enumerate(MENU_ITEMS, 1):
            print(f"  {i}. {label}")
        return
    Console, Panel, Table, Text, Align = r
    con = Console()
    tbl = Table(show_header=False, box=None, padding=(0, 2))
    tbl.add_column("#", style="bold cyan", width=3)
    tbl.add_column("action")
    for i, (label, _) in enumerate(MENU_ITEMS, 1):
        tbl.add_row(str(i), label)
    con.print(Panel(tbl, title="[bold cyan]my-termux menu[/bold cyan]",
                    border_style="cyan", padding=(1, 2)))


def prompt(msg: str, default: str = "") -> str:
    tail = f" [{default}]" if default else ""
    try:
        val = input(f"{msg}{tail}: ").strip()
    except EOFError:
        return default
    return val or default


def confirm(msg: str, default: bool = False) -> bool:
    d = "Y/n" if default else "y/N"
    v = prompt(f"{msg} ({d})").lower()
    if not v:
        return default
    return v in ("y", "yes")
