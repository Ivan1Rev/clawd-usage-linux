#!/bin/sh
# Removes Clawd Usage. Your settings in ~/.config/clawd-usage are kept unless you pass --all.
pkill -f "^python3 .*clawd_usage.py" 2>/dev/null || true
rm -rf "$HOME/.local/share/clawd-usage"
rm -f "$HOME/.local/bin/clawd-usage" "$HOME/.local/share/applications/clawd-usage.desktop"
rm -f "${XDG_CONFIG_HOME:-$HOME/.config}/autostart/clawd-usage.desktop"
if [ "$1" = "--all" ]; then
    rm -rf "$HOME/.config/clawd-usage" "$HOME/.local/state/clawd-usage"
fi
echo "Clawd Usage removed."
