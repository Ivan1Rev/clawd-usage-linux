#!/bin/sh
# Installs Clawd Usage for the current user only (no sudo needed).
# Files go to ~/.local/share/clawd-usage, ~/.local/bin and ~/.local/share/applications.
set -e
cd "$(dirname "$0")"

if ! python3 -c 'import PyQt6.QtWidgets' 2>/dev/null; then
    echo "PyQt6 is missing. Install it first:"
    echo "    sudo apt install python3-pyqt6"
    exit 1
fi
command -v claude >/dev/null 2>&1 || echo "Note: 'claude' (Claude Code) is not on PATH - the widget needs it for usage data."

APP="$HOME/.local/share/clawd-usage"
mkdir -p "$APP" "$HOME/.local/bin" "$HOME/.local/share/applications"
cp clawd_usage.py mascot.py sky.py codestats.py split.py clawd-usage.png "$APP/"

cat > "$HOME/.local/bin/clawd-usage" <<'EOF'
#!/bin/sh
exec python3 "$HOME/.local/share/clawd-usage/clawd_usage.py" "$@"
EOF
chmod +x "$HOME/.local/bin/clawd-usage"

cat > "$HOME/.local/share/applications/clawd-usage.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Clawd Usage
GenericName=Claude usage meter
Comment=Floating widget and tray icon showing your Claude plan limits
Exec=$HOME/.local/bin/clawd-usage --show
Icon=$APP/clawd-usage.png
Terminal=false
Categories=Utility;Monitor;
StartupWMClass=clawd-usage
EOF

echo "Installed. Start it from your app menu (Clawd Usage) or run: clawd-usage"
