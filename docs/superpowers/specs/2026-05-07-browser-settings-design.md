# Browser-based Settings Window — Design Spec

**Date:** 2026-05-07  
**Replaces:** `micdot/settings_window.py` (tkinter implementation)

## Problem

tkinter is not available in pyenv-managed Python builds and will not be available in the PyInstaller bundle. The settings window must be replaced with something that works in both dev (`pip install -e .`) and the distributed `.app`.

## Decision

Use **pywebview** to open a native macOS WKWebView window containing a plain HTML form. The window has no browser chrome — it looks and behaves like a macOS app window.

## Architecture

### Process model

Unchanged from today: `main.py` spawns `settings_window.py` as a subprocess via `subprocess.Popen`. The subprocess owns the pywebview window; the main process is unaffected while settings is open.

### Settings subprocess (`settings_window.py`)

```
run(config_path)
├── Load Config from disk
├── Define Api class — save(data) method exposed to JS
│   ├── Validate and construct new Config
│   ├── Write config.json
│   ├── Handle autostart (enable_autostart / disable_autostart)
│   └── window.destroy()
├── Build HTML string (current config values injected as JSON into <script>)
├── webview.create_window('MicDot Settings', html=html, js_api=Api(),
│                         width=440, height=580, resizable=False)
└── webview.start()
    └── sys.exit(0 if saved else 1)
```

The HTML is an **embedded string** inside the Python file — no HTTP server, no temp files, trivially bundleable with PyInstaller.

### JS ↔ Python bridge

pywebview exposes the `Api` instance at `window.pywebview.api`. On Save, JS collects all form values into a dict and calls:

```js
window.pywebview.api.save(data)
```

Python validates the data, writes `config.json`, and destroys the window. The process exits with code `0` if saved, `1` if dismissed without saving.

### Live reload IPC

The parent process (`main.py`) starts a **daemon thread** that blocks on `proc.wait()`. When the settings subprocess exits with code `0`, the thread calls `_reload_config()` — no sockets, no signals, no polling files.

```python
def open_settings():
    proc = subprocess.Popen([sys.executable, "-m", "micdot.settings_window",
                              str(DEFAULT_CONFIG_PATH)])
    threading.Thread(
        target=lambda: proc.wait() == 0 and _reload_config(),
        daemon=True,
    ).start()

def _reload_config():
    nonlocal config, mqtt, hotkey_listener
    config = Config.load(DEFAULT_CONFIG_PATH)
    mqtt.stop()
    mqtt = MQTTClient(config, on_button_press=on_toggle)
    mqtt.start()
    hotkey_listener.stop()
    hotkey_listener = HotkeyListener(config.hotkey, callback=on_toggle)
    hotkey_listener.start()
```

Both helpers are defined inside `main()` and close over `mqtt` and `hotkey_listener` via `nonlocal`.

**What reloads:** MQTT (reconnects to new broker/credentials) and hotkey (rebinds).  
**What does not reload:** Poller and TrayIcon — neither reads config directly.  
LED colors and brightness take effect when the MQTT connection next publishes state; no extra handling needed.

## HTML Form

### Layout

Grouped/sectioned, macOS system-prefs style. Two inset list sections separated by a section label:

```
MicDot Settings
─────────────────────────────
MQTT
┌─────────────────────────────┐
│ Host      [_______________] │
│ Port      [_______________] │
│ Username  [_______________] │
│ Password  [•••••••••••••••] │
└─────────────────────────────┘

HARDWARE & BEHAVIOUR
┌─────────────────────────────┐
│ Hotkey        [___________] │
│ Brightness    [___________] │
│ Muted color   [■] [#00ff00] │
│ Unmuted color [■] [#ff0000] │
└─────────────────────────────┘

Autostart on login        [ ● ]

              [ Save ]
```

### Color fields

Each color row has an `<input type="color">` swatch and a synced `<input type="text">` hex field. Changing either updates the other in real time via JS `input` event listeners:

```js
colorPicker.addEventListener('input', () => hexField.value = colorPicker.value);
hexField.addEventListener('input', () => {
  if (/^#[0-9a-fA-F]{6}$/.test(hexField.value))
    colorPicker.value = hexField.value;
});
```

### Styling

- Font: `-apple-system, BlinkMacSystemFont, sans-serif`, 13px
- Background: `#f0f0f0` page, `white` card, inset list rows separated by 1px `#e5e5e5` borders
- Save button: `#007aff` (macOS blue), full-width, disabled after first click to prevent double-submit
- Window: 440 × 580 px, not resizable

## Files Changed

| File | Change |
|------|--------|
| `micdot/settings_window.py` | Full rewrite — tkinter removed, pywebview + embedded HTML |
| `micdot/main.py` | Add `import threading`; replace inline `on_settings` lambda with `open_settings()`; add `_reload_config()` |
| `pyproject.toml` | Add `pywebview>=4.0` to `dependencies` |

## New Dependency

`pywebview>=4.0` — thin wrapper around macOS WKWebView. Ships with PyInstaller hooks. No other new dependencies.

## Testing

No existing tests cover `settings_window.py`. A new `tests/test_settings_window.py` will test:

- `Config` round-trip via the `Api.save()` method directly (no webview needed — instantiate `Api`, call `save()`, assert config file written correctly)
- Autostart is enabled/disabled based on the `autostart` flag in the submitted data

`main.py` reload logic will be tested in a new `tests/test_main_reload.py`:

- When `_reload_config()` is called, the old MQTT client is stopped and a new one is started with the new config
- The old hotkey listener is stopped and a new one is started with the new hotkey
