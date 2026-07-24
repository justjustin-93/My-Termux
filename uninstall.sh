#!/data/data/com.termux/files/usr/bin/env bash
# my-termux uninstaller — safely removes commands, .bashrc block, and (optionally) data.

set -e
PREFIX="${PREFIX:-/data/data/com.termux/files/usr}"
BIN_DIR="$PREFIX/bin"
APP_HOME="$HOME/my-termux"
BASHRC="$HOME/.bashrc"

echo "[Termux] removing global commands..."
for c in termux start chat menu status scan sync fix export import resume media cloud; do
    if [ -L "$BIN_DIR/$c" ] || [ -f "$BIN_DIR/$c" ]; then
        rm -f "$BIN_DIR/$c" && echo "  - $c"
    fi
done

echo "[my-termux] removing auto-launch block from ~/.bashrc..."
if [ -f "$BASHRC" ]; then
    python - <<'PY'
import re, os
p = os.path.expanduser("~/.bashrc")
try:
    txt = open(p, "r", encoding="utf-8").read()
except FileNotFoundError:
    raise SystemExit(0)
new = re.sub(r"\n?# >>> my-termux auto-launch >>>.*?# <<< my-termux auto-launch <<<\n?",
             "\n", txt, flags=re.DOTALL)
open(p, "w", encoding="utf-8").write(new)
print("  - bashrc cleaned")
PY
fi

read -r -p "Delete ALL data in $APP_HOME? [y/N] " ans
case "$ans" in
    y|Y|yes|YES)
        rm -rf "$APP_HOME"
        echo "  - $APP_HOME removed"
        ;;
    *)
        echo "  - keeping $APP_HOME (config, sessions, logs preserved)"
        ;;
esac

echo "[my-termux] uninstalled. Open a new shell for changes to take effect."
