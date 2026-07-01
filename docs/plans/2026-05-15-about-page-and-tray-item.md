# Plan: About page in settings window + tray "About" item

## Context

While testing builds the user found there was no way to tell which version of MicDot was currently running. To fix this we add an "About" view that surfaces:

- The running app version
- A link to the GitHub repository
- A "Support me" link to `https://donatr.ee/andrecedik`

The About view lives inside the existing settings window as a second tab (alongside "Settings"). The tray menu gets a new "About" item that opens the settings window with the About tab pre-selected. Tab buttons provide navigation in both directions, which satisfies the user's "backlink to settings" request implicitly.

## Approach

Two-tab layout inside the existing pywebview settings window (chosen: top tab bar). External links go through a small `Api.open_url` Python bridge that calls `webbrowser.open` (no existing pattern in the codebase to reuse, but `webbrowser` is stdlib). The settings subprocess gains an optional `--tab {settings,about}` flag that selects the initial tab. A new `__version__` constant in `micdot/__init__.py` becomes the canonical version for source runs; the frozen `.app` keeps using `CFBundleShortVersionString` (already populated from the `MICDOT_VERSION` env var in CI).

## Files to modify

### 1. `micdot/__init__.py` — add version constant

Currently empty. Add:

```python
__version__ = "0.5.0"
```

Matches the current branch `feature/0.5.0` and the next release in `CHANGELOG.md` (currently `[Unreleased]`, last tagged `0.4.0`).

### 2. `pyproject.toml` — bump version (line 7)

Change `version = "0.1.0"` → `version = "0.5.0"`. This keeps `pyproject.toml` and `micdot/__init__.py` in lockstep. `MicDot.spec` is untouched — CI still overrides via `MICDOT_VERSION`.

### 3. `micdot/version.py` (new file) — version resolver

Single small helper used by the settings window to find the right version string regardless of run mode:

```python
"""Resolve the running MicDot version for display."""
from __future__ import annotations
import sys
from micdot import __version__


def get_version() -> str:
    if getattr(sys, "frozen", False):
        try:
            from Foundation import NSBundle  # provided by pyobjc on darwin
            info = NSBundle.mainBundle().infoDictionary() or {}
            v = info.get("CFBundleShortVersionString")
            if v:
                return str(v)
        except Exception:
            pass
    return __version__
```

The `NSBundle` path returns the version baked into `Info.plist` at build time (`MICDOT_VERSION` env var in CI → `MicDot.spec` line 62). Source runs fall back to `__version__`.

### 4. `micdot/settings_window.py` — add About tab, link bridge, initial-tab routing

- Rework `_HTML` (lines 17–125):
  - Add a `<nav class="tabs">` row with two buttons (`data-tab="settings"`, `data-tab="about"`) styled as a segmented control (matches the existing macOS-style accent color `#007aff`).
  - Wrap existing settings markup (MQTT group, hardware group, autostart row, Save button) in `<section data-pane="settings">`.
  - Add `<section data-pane="about">` with: app name, `MicDot <version>`, two link rows ("GitHub", "Support me"). Render as `<a href="#" data-url="…">` so the click goes through the JS bridge.
  - JS: tab switching toggles a `.hidden` class on the two sections and an `.active` class on the buttons. Link clicks call `window.pywebview.api.open_url(this.dataset.url)`. Initial active tab is read from a `INITIAL_TAB_PLACEHOLDER` string substituted in `run()`.
  - The Save button stays inside the Settings section, so it's automatically hidden on the About tab. No layout reshuffling needed.
  - Inject the version via a new `VERSION_PLACEHOLDER` string.

- Extend `Api` class (lines 128–202) with `open_url`:

  ```python
  import webbrowser
  # ...
  def open_url(self, url: str) -> None:
      if not isinstance(url, str) or not url.startswith(("http://", "https://")):
          log.warning("Refusing to open non-http(s) URL: %r", url)
          return
      log.info("Opening external URL %s", url)
      webbrowser.open(url)
  ```

  Allow-listing `http(s)` keeps the bridge from being weaponised by any future templated content. Method does NOT close the window (unlike `save()`), so the existing pywebview deadlock concern doesn't apply.

- Update `run(config_path)` signature (line 205) to `run(config_path, initial_tab: str = "settings")`:
  - Validate `initial_tab in {"settings", "about"}`; default to `"settings"` otherwise.
  - Replace `INITIAL_TAB_PLACEHOLDER` and `VERSION_PLACEHOLDER` alongside the existing `CONFIG_PLACEHOLDER` substitution at line 209. Use `json.dumps` for both to keep the string-escaping safe.
  - Import `get_version` from `micdot.version`.

- Update `__main__` block (lines 223–225) to parse an optional `--tab` flag:

  ```python
  if __name__ == "__main__":
      argv = sys.argv[1:]
      tab = "settings"
      if "--tab" in argv:
          i = argv.index("--tab")
          if i + 1 < len(argv):
              tab = argv[i + 1]
              del argv[i:i+2]
      path = Path(argv[0]) if argv else DEFAULT_CONFIG_PATH
      run(path, initial_tab=tab)
  ```

### 5. `micdot/main.py` — frozen-mode parsing + open_about handler

- Extend `_settings_cmd` (lines 116–119) to accept an optional `tab` argument:

  ```python
  def _settings_cmd(config_path: Path, tab: str = "settings") -> list[str]:
      if getattr(sys, "frozen", False):
          return [sys.executable, "--settings", str(config_path), "--tab", tab]
      return [sys.executable, "-m", "micdot.settings_window", str(config_path), "--tab", tab]
  ```

- Extend the frozen-app re-entry block (lines 122–128) to parse `--tab`:

  ```python
  if getattr(sys, "frozen", False) and "--settings" in sys.argv:
      idx = sys.argv.index("--settings")
      path = Path(sys.argv[idx + 1]) if idx + 1 < len(sys.argv) else DEFAULT_CONFIG_PATH
      tab = "settings"
      if "--tab" in sys.argv:
          tidx = sys.argv.index("--tab")
          if tidx + 1 < len(sys.argv):
              tab = sys.argv[tidx + 1]
      from micdot.settings_window import run as run_settings
      run_settings(path, initial_tab=tab)
      return
  ```

- Replace the single `open_settings` closure (lines 155–169) with a parametrised helper, exposing two callables:

  ```python
  def _open_settings_window(tab: str) -> None:
      if settings_proc[0] is not None and settings_proc[0].poll() is None:
          return
      log.info("Opening settings window (tab=%s)", tab)
      settings_proc[0] = subprocess.Popen(_settings_cmd(DEFAULT_CONFIG_PATH, tab))

      def _on_exit() -> None:
          rc = settings_proc[0].wait() if settings_proc[0] else 1
          if rc == 0:
              try:
                  _reload_config(state, DEFAULT_CONFIG_PATH, on_toggle, backend)
              except Exception:
                  log.exception("Uncaught error during config reload")

      threading.Thread(target=_on_exit, daemon=True).start()

  def open_settings() -> None:
      _open_settings_window("settings")

  def open_about() -> None:
      _open_settings_window("about")
  ```

  The existing dedup guard (`settings_proc[0].poll() is None`) is preserved — clicking "About" while the window is already open is a no-op, matching today's "Settings" behavior. (A nicer focus-existing behavior would require IPC; out of scope.)

- Pass `on_about=open_about` into `TrayIcon(...)` (lines 180–184).

### 6. `micdot/tray.py` — new About menu item

- Add `on_about: Callable[[], None]` parameter to `TrayIcon.__init__` (lines 26–34).
- Insert the new item in the menu tuple (line 38–43), with a separator before Quit for macOS polish:

  ```python
  menu=pystray.Menu(
      pystray.MenuItem("Toggle Mute", self._toggle, default=True),
      pystray.MenuItem("Settings", self._settings),
      pystray.MenuItem("About", self._about),
      pystray.Menu.SEPARATOR,
      pystray.MenuItem("Quit", self._quit),
  ),
  ```

- Add `_about(self, icon, item)` method that calls `self._on_about()`.

### 7. Tests

- `tests/test_main_frozen.py` — extend the two `_settings_cmd` cases to assert the new `--tab` arg, and add coverage for frozen-mode parsing of `--tab about`.
- `tests/test_settings_window.py` — add tests for:
  - `Api.open_url` calling `webbrowser.open` for `https://` URLs
  - `Api.open_url` refusing `file://`, `javascript:`, empty, and non-string inputs (no `webbrowser.open` call)
  - `run(..., initial_tab="about")` substituting the placeholder in the rendered HTML (assert the string appears in `_HTML` after substitution — `webview` import is deferred, so we can patch it before calling `run`, or factor the HTML build into a helper and test that)
- New `tests/test_version.py` — `get_version()` returns `__version__` when not frozen; returns the NSBundle value when frozen and NSBundle is mocked.

The factoring suggestion: split the HTML-building step into `def _build_html(config, initial_tab, version)` at module scope so tests can call it without needing pywebview. Keeps `run()` thin.

### 8. `CHANGELOG.md`

Add an entry under `[Unreleased]`:

```
### Added
- About page in settings window showing app version, GitHub link, and a "Support me" donate link.
- "About" tray menu item that opens the About page directly.
```

## URLs (canonical strings)

- GitHub: `https://github.com/andrecedik/micdot` (from README/CHANGELOG link refs)
- Support me: `https://donatr.ee/andrecedik` (from user)

## Verification

1. **Unit tests:** `pytest` — full suite. New tests above plus existing 80-odd should pass without hardware/MQTT.
2. **Source-mode smoke test:**
   ```bash
   pip install -e ".[dev]"
   micdot
   ```
   - Right-click tray icon → menu shows `Toggle Mute`, `Settings`, `About`, separator, `Quit`.
   - Click `Settings` → window opens on Settings tab; Save still works; config reloads on save.
   - Click `About` (while window closed) → window opens on About tab; version reads `0.5.0`; clicking "GitHub" opens browser to the repo; clicking "Support me" opens browser to donatr.ee.
   - Switch from About → Settings tab in-window; form values are preserved; Save reappears.
   - With settings window already open, clicking the other tray item is a no-op (current dedup behavior).
3. **Frozen-app smoke test:**
   ```bash
   MICDOT_VERSION="0.5.0" pyinstaller MicDot.spec --noconfirm
   open dist/MicDot.app
   ```
   - About tab shows `0.5.0` (sourced from `CFBundleShortVersionString`, not `__version__`).
   - Both tray entries open the correct tab; both links open the system browser.
   - Save still works (no regression to the existing `performSelectorOnMainThread` close path).

## Out of scope

- Focus-existing-window behavior when the user clicks About while Settings is already open (would need IPC to the subprocess).
- Dynamic version reading from `pyproject.toml` (PEP 621 dynamic versioning) — kept simple with paired `__version__` + `pyproject.toml` bump.
- Adding the app icon to the About page — possible follow-up; would require copying `resources/MicDot.icns` (or a PNG) into the bundle's `datas=` and resolving via `sys._MEIPASS` at runtime.
