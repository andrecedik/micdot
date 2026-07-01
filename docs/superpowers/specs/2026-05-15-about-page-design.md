# Design: About tab in settings window + tray "About" item

## Context

When testing builds there is no way to tell which version of MicDot is running. This spec adds an About tab to the existing settings window that surfaces the running version, a link to the GitHub repository, and a "Support me" donation link. A new tray menu item opens the window directly on the About tab.

## Architecture

The existing subprocess model is unchanged: one `settings_proc[0]` slot, one dedup guard, one pywebview window. Clicking "About" while the window is already open is a no-op (matches existing Settings behavior).

Key additions:

- **Tab bar** — a `<nav class="tabs">` segment control at the top of `_HTML` with "Settings" and "About" buttons. JS toggles `.hidden` on the two content panes and `.active` on the buttons.
- **`--tab {settings,about}` CLI flag** — passed to the settings subprocess. `run()` gains an `initial_tab` parameter that selects which pane is visible on load.
- **`_build_html(config, initial_tab, version)`** — module-level helper that performs all placeholder substitutions. Makes HTML generation testable without importing pywebview.
- **`Api.open_url(url)`** — validates `http(s)://` then calls `webbrowser.open`. Guards the bridge against non-http inputs.
- **`micdot/version.py`** — `get_version() -> str`: reads `CFBundleShortVersionString` from NSBundle in frozen mode; falls back to `micdot.__version__` in source runs. Exception-safe.
- **`_open_settings_window(tab)`** in `main.py` — shared helper from which `open_settings()` and `open_about()` are derived as thin wrappers.

## Files to Modify

### `micdot/__init__.py`

Add:

```python
__version__ = "0.5.0"
```

### `pyproject.toml`

Bump `version = "0.1.0"` → `"0.5.0"`.

### `micdot/version.py` (new)

```python
from __future__ import annotations
import sys
from micdot import __version__


def get_version() -> str:
    if getattr(sys, "frozen", False):
        try:
            from Foundation import NSBundle
            info = NSBundle.mainBundle().infoDictionary() or {}
            v = info.get("CFBundleShortVersionString")
            if v:
                return str(v)
        except Exception:
            pass
    return __version__
```

### `micdot/settings_window.py`

- Add `<nav class="tabs">` with two segment buttons (`data-tab="settings"`, `data-tab="about"`) styled to match the existing `#007aff` accent.
- Wrap existing form in `<section data-pane="settings">`. Save button stays inside — automatically absent on the About tab.
- Add `<section data-pane="about">` with: app name, `MicDot <VERSION_PLACEHOLDER>`, link rows for GitHub and Support me. Links: `<a href="#" data-url="…">` calling `window.pywebview.api.open_url(this.dataset.url)`.
- Three placeholders: `CONFIG_PLACEHOLDER` (existing), `INITIAL_TAB_PLACEHOLDER`, `VERSION_PLACEHOLDER`.
- New `_build_html(config, initial_tab, version)` does all substitution using `json.dumps` for every injected value (`CONFIG_PLACEHOLDER`, `INITIAL_TAB_PLACEHOLDER`, `VERSION_PLACEHOLDER`) to guarantee correct string escaping.
- `run(config_path, initial_tab="settings")` validates `initial_tab in {"settings","about"}`, calls `get_version()` and `_build_html`.
- `Api.open_url(url)` — validates `isinstance(url, str) and url.startswith(("http://","https://"))`; silently returns otherwise, then calls `webbrowser.open`. Module-level `import webbrowser` added alongside the other stdlib imports.
- `__main__` block parses `--tab <value>` from `sys.argv`.

### `micdot/main.py`

- `_settings_cmd(config_path, tab="settings")` appends `["--tab", tab]`.
- Frozen re-entry block parses `--tab` from `sys.argv`.
- `_open_settings_window(tab)` replaces inline `open_settings` closure; dedup guard preserved.
- `open_settings()` and `open_about()` are one-line wrappers calling `_open_settings_window`.
- `TrayIcon(…, on_about=open_about)` passed in.

### `micdot/tray.py`

- `TrayIcon.__init__` gains `on_about: Callable[[], None]`.
- Menu order: `Toggle Mute`, `Settings`, `About`, separator, `Quit`.
- New `_about(self, icon, item)` method calls `self._on_about()`.

## URLs

- GitHub: `https://github.com/andrecedik/micdot`
- Support me: `https://donatr.ee/andrecedik`

## Testing

### `tests/test_version.py` (new)

- `get_version()` returns `__version__` when `sys.frozen` is not set.
- `get_version()` returns the NSBundle value when `sys.frozen` is set and NSBundle is mocked.

### `tests/test_settings_window.py` — new cases

- `_build_html(config, "about", "0.5.0")` produces HTML with `"about"` as the active tab identifier.
- `Api.open_url` calls `webbrowser.open` for `https://` and `http://` URLs.
- `Api.open_url` does not call `webbrowser.open` for `file://`, `javascript:`, empty string, and non-string inputs.

### `tests/test_main_frozen.py` — extended cases

- `_settings_cmd(path)` includes `["--tab", "settings"]`.
- `_settings_cmd(path, tab="about")` includes `["--tab", "about"]`.
- Frozen re-entry block with `["--settings", str(path), "--tab", "about"]` in `sys.argv` calls `run_settings(path, initial_tab="about")`.

## CHANGELOG entry

Under `[Unreleased]`:

```
### Added
- About tab in settings window showing app version, GitHub link, and a "Support me" donate link.
- "About" tray menu item that opens the About tab directly.
```

## Verification

### Source-mode smoke test

```bash
pip install -e ".[dev]"
micdot
```

- Tray menu shows: `Toggle Mute`, `Settings`, `About`, separator, `Quit`.
- `Settings` → window opens on Settings tab; Save works; config reloads.
- `About` (window closed) → window opens on About tab; version reads `0.5.0`; GitHub and Support me links open in the system browser.
- Tab bar switches between panes in both directions; Save button is absent on About, present on Settings.
- Clicking the other tray item while the window is open is a no-op.

### Frozen-app smoke test

```bash
MICDOT_VERSION="0.5.0" pyinstaller MicDot.spec --noconfirm
open dist/MicDot.app
```

- About tab shows `0.5.0` sourced from `CFBundleShortVersionString`, not `__version__`.
- Both tray entries open the correct tab; both links open the system browser.
- Save still works (no regression to the `performSelectorOnMainThread` close path).

## Out of scope

- Focus-existing-window when the user clicks the other tray item while the window is open (would need IPC to the subprocess).
- App icon on the About page.
- Dynamic version reading from `pyproject.toml` (PEP 621).
