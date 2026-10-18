# Clawd Usage for Linux

A small desktop widget that shows how much of your Claude plan limit you've used, with Clawd walking around on top.

This is a Linux port of **[Enhed/clawd-usage-winwidget](https://github.com/Enhed/clawd-usage-winwidget)**, which is Windows-only (PowerShell + WPF). All credit for the idea, the design and the Clawd animations goes to that project. This version is rewritten in Python + Qt so it runs on Debian-based Linux (Debian, Ubuntu, Mint, Pop!_OS…) on GNOME or KDE.

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

```sh
sudo apt install python3-pyqt6
git clone https://github.com/Ivan1Rev/clawd-usage-linux.git
cd clawd-usage-linux
sh install.sh
```

Then open **Clawd Usage** from your app menu. Everything installs to your home folder; no root needed apart from PyQt6.

To remove: `sh uninstall.sh` (add `--all` to delete settings too).

## Using it

- Drag the card to move it. Right-click for the menu (always on top, main number, sky & weather, animations, settings file).
- Click Clawd to make him do something.
- `–` hides it to the tray; `✕` quits.
- Settings live in `~/.config/clawd-usage/config.json`.

## Notes

- **GNOME:** the tray icon needs the *AppIndicator* extension (Ubuntu has it already; on Debian install `gnome-shell-extension-appindicator`).
- **Wayland:** apps can't place their own windows, so the widget can't remember its position or force itself on top. Drag it where you want it each time, or use your desktop's window rules.
- **Weather:** looks up your rough location from your IP (ipwho.is), then gets weather from Open-Meteo (met.no as a backup). To skip the IP lookup, set `weatherLat` and `weatherLon` in the settings file, or turn the sky off in the menu.

## License

MIT, same as the original. See [LICENSE](LICENSE).
