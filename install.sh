#!/bin/sh
# Installs Clawd Usage for the current user only (no sudo needed).
# Files go to ~/.local/share/clawd-usage, ~/.local/bin and ~/.local/share/applications.
set -e
cd "$(dirname "$0")"

if ! command -v python3 >/dev/null 2>&1; then
    echo "python3 is missing. Install Python 3 with your package manager, then run this again."
    exit 1
fi

if ! python3 -c 'import PyQt6.QtWidgets' 2>/dev/null; then
    # Work out the distro family from /etc/os-release (ID, plus ID_LIKE for derivatives).
    ids=""
    if [ -r /etc/os-release ]; then
        ids=$(. /etc/os-release; echo "$ID $ID_LIKE")
    fi
    case " $ids " in
        *" debian "*|*" ubuntu "*)          cmd="sudo apt install python3-pyqt6" ;;
        *" fedora "*|*" rhel "*|*" centos "*) cmd="sudo dnf install python3-pyqt6" ;;
        *" arch "*)                          cmd="sudo pacman -S python-pyqt6" ;;
        *" opensuse"*|*" suse "*)            cmd="sudo zypper install python3-PyQt6" ;;
        *" alpine "*)                        cmd="sudo apk add py3-pyqt6" ;;
        *" gentoo "*)                        cmd="sudo emerge dev-python/pyqt6" ;;
        *" void "*)                          cmd="sudo xbps-install python3-pyqt6" ;;
        *)                                   cmd="" ;;
    esac
    echo "PyQt6 is missing. Install it first:"
    if [ -n "$cmd" ]; then
        echo "    $cmd"
        echo "or, on any distro, without root:"
    fi
    echo "    pip install --user PyQt6"
    echo "Then run this again."
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
