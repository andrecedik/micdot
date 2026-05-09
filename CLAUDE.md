# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

MicDot is a macOS menu bar app that mutes/unmutes the system microphone via hotkey, tray click, or a physical ESP32 button. It optionally drives a WS2812B LED ring over MQTT to show mic state.

## Commands

```bash
# Install for development
pip install -e ".[dev]"

# Run the app
micdot

# Run tests (all run without hardware or MQTT broker)
pytest

# Run a single test file
pytest tests/test_config.py

# Build distributable .app (requires PyInstaller)
pip install -e ".[build]"
MICDOT_VERSION="1.0.0" pyinstaller MicDot.spec --noconfirm
# Output: dist/MicDot.app
```

Releases are built automatically via GitHub Actions on `v*` tags. Only arm64 (Apple Silicon) is published; Intel Macs run it via Rosetta 2.

## Architecture

### Process model

`main.py` is the single entry point. It wires together five components that all run concurrently:

- **`Poller`** — daemon thread that polls `AudioBackend.get_mute()` every 200 ms; fires `on_change` when state flips
- **`HotkeyListener`** — wraps pynput; one long-lived `Listener` thread with a swappable `HotKey` object
- **`MQTTClient`** — paho MQTT with `loop_start()` (background thread); skips entirely when `mqtt_host` is empty
- **`TrayIcon`** — pystray runs on the main thread via `tray.run()` (blocking); all UI updates must respect this
- **`SettingsWindow`** — launched as a **separate subprocess** (`subprocess.Popen`) to avoid pywebview conflicting with pystray's NSApp on the same main thread

`_State` holds the mutable trio (config, mqtt, hotkey_listener) that gets swapped on config reload.

### Config reload flow

When the settings subprocess exits with code 0, `_reload_config` is called from a background thread. It:
1. Loads new config from disk
2. Stops old MQTT client and starts a new one
3. Dispatches hotkey update to the **main thread** via `NSOperationQueue.mainQueue()` — required on macOS 15+ because `TISCopyCurrentKeyboardInputSource` asserts it's on the main queue

### macOS-specific constraints

- **HotkeyListener**: The pynput `Listener` thread must **never be restarted** after NSApp starts (macOS 15+ Sequoia). Only the `HotKey` matching object is swapped via `update()`.
- **Settings window close**: Must close synchronously via `performSelectorOnMainThread_withObject_waitUntilDone_(b"close", None, True)` before `save()` returns — otherwise pywebview's `evaluate_js` deadlocks waiting for a WKWebView callback that never fires because the window was destroyed.
- **Dock icon**: Hidden via `NSApp.setActivationPolicy_(NSApplicationActivationPolicyAccessory)` so MicDot appears only in the menu bar.

### Audio backend

`micdot/audio/backend.py` defines the `AudioBackend` ABC. `get_backend()` dispatches to `MacOSAudioBackend` (CoreAudio via ctypes) on darwin, and raises on other platforms. `StubAudioBackend` is used in tests.

### MQTT topics

| Topic | Direction | Payload |
|---|---|---|
| `micdot/state` | publish | `"muted"` / `"unmuted"` (retained) |
| `micdot/led/set` | publish | `{"r":…,"g":…,"b":…,"brightness":…}` (retained) |
| `micdot/button` | subscribe | `"pressed"` → triggers toggle |

Home Assistant MQTT discovery payloads are published on connect.

### Frozen app (`sys.frozen`)

When running as a PyInstaller bundle, `--settings <path>` is passed as a CLI argument to open the settings window in the same executable instead of spawning a new Python process.

### Config

Stored at `~/.config/micdot/config.json`. `Config` is a dataclass; `Config.load()` merges persisted values over defaults so new fields are always available.

### Autostart

`autostart.py` writes/removes a LaunchAgent plist at `~/Library/LaunchAgents/com.micdot.agent.plist` and calls `launchctl load/unload`. When running from source, it uses `python3 -m micdot.main`; when frozen, it uses `sys.executable`.
