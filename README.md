# Clawd Usage for Linux

A small desktop widget that shows how much of your Claude plan limit you've used, with Clawd walking around on top.

This is a Linux port of **[Enhed/clawd-usage-winwidget](https://github.com/Enhed/clawd-usage-winwidget)**, which is Windows-only (PowerShell + WPF). All credit for the idea, the design and the Clawd animations goes to that project. This version is rewritten in Python + Qt so it runs on most Linux distros (Debian, Ubuntu, Mint, Fedora, Arch, openSUSE…) and desktops (GNOME, KDE, XFCE, Cinnamon…).

![Clawd Usage](screenshot.png)

Unofficial fan project, not made by or affiliated with Anthropic.

## What it shows

- **Session %** for the current 5-hour window, with a bar and time until reset
- **Week %** (and Fable week when your plan has one)
- **Hearts** for Clawd's health: they drop as you use up the session
- Running Claude Code sessions, Claude service status, and stats for the last 24 h / 7 days
- A pixel sky behind Clawd that follows the time of day and your real local weather

**Added in this port:** under Details (▾) you can switch the big number to **Claude Code**, **Cowork** or **Chat**. Anthropic only reports one combined percentage, so these are *estimates* built from what was active on this PC when the percentage went up (marked with ≈).

## Install

You need [Claude Code](https://docs.claude.com/en/docs/claude-code) installed and logged in. The widget reads its data from `claude /usage`, which uses no tokens.

**1. Install PyQt6** (the Qt library for Python) with your distro's package manager:

| Distro | Command |
|---|---|
| Debian, Ubuntu, Mint, Pop!_OS | `sudo apt install python3-pyqt6` |
| Fedora | `sudo dnf install python3-pyqt6` |
| Arch, Manjaro, EndeavourOS | `sudo pacman -S python-pyqt6` |
| openSUSE | `sudo zypper install python3-PyQt6` |
| Anything else | `pip install --user PyQt6` |

Not sure? Skip this step: `install.sh` checks for PyQt6 and prints the right command for your distro.

**2. Download and install:**

```sh
git clone https://github.com/Ivan1Rev/clawd-usage-linux.git
cd clawd-usage-linux
sh install.sh
```

The installer asks whether to start Clawd Usage when you log in. To decide up front, run `sh install.sh --autostart` or `sh install.sh --no-autostart`. You can change your mind later by running it again with the other option.

Then open **Clawd Usage** from your app menu. Everything installs to your home folder; no root needed apart from PyQt6.

Needs a desktop session (not a headless server) and a distro recent enough to package PyQt6 (roughly 2021 or newer). Tested on Kubuntu with KDE Plasma 6 on Wayland; other setups are expected to work but haven't been tested - issues welcome.

To remove: `sh uninstall.sh` (add `--all` to delete settings too).

## Using it

- Drag the card to move it. Right-click for the menu (always on top, main number, sky & weather, animations, settings file).
- Click Clawd to make him do something.
- `–` hides it to the tray; `✕` quits.
- Settings live in `~/.config/clawd-usage/config.json`.

## Notes

- **GNOME:** the tray icon needs the *AppIndicator* extension. Ubuntu has it already; elsewhere install `gnome-shell-extension-appindicator` (Debian, Fedora, Arch) and enable it in the Extensions app.
- **Wayland:** apps can't place their own windows, so the widget can't remember its position or force itself on top. Drag it where you want it each time, or use your desktop's window rules.
- **Weather:** looks up your rough location from your IP (ipwho.is), then gets weather from Open-Meteo (met.no as a backup). To skip the IP lookup, set `weatherLat` and `weatherLon` in the settings file, or turn the sky off in the menu.

## License

MIT, same as the original. See [LICENSE](LICENSE).
