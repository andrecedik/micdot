# About Page and Tray Item Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add an About tab to the settings window (showing version, GitHub link, and a donate link) and a matching "About" tray menu item that opens it directly.

**Architecture:** The existing single-subprocess model is unchanged — one `settings_proc[0]` slot manages both Settings and About tabs. A new `--tab {settings,about}` CLI flag on the settings subprocess selects the initial tab. `_build_html(config, initial_tab, version)` centralises all HTML substitution and is the primary test surface for the UI.

**Tech Stack:** Python 3.11+, pywebview (settings window), pystray (tray icon), pyobjc Foundation (frozen-mode version), stdlib webbrowser + json.

---

## File Map

| File | Change |
|---|---|
| `micdot/__init__.py` | Add `__version__ = "0.5.0"` |
| `pyproject.toml` | Bump `version` to `"0.5.0"` |
| `micdot/version.py` | **New.** `get_version()` — NSBundle in frozen mode, `__version__` otherwise |
| `micdot/settings_window.py` | `_build_html` helper, About tab in `_HTML`, `Api.open_url`, updated `run()` and `__main__` |
| `micdot/main.py` | `_settings_cmd` gets `tab` arg; frozen re-entry parses `--tab`; `_open_settings_window(tab)` replaces `open_settings` closure; `open_about` added |
| `micdot/tray.py` | `on_about` parameter, `_about` method, updated menu |
| `CHANGELOG.md` | Entry under `[Unreleased]` |
| `tests/test_version.py` | **New.** Tests for `get_version()` |
| `tests/test_settings_window.py` | New cases for `_build_html` and `Api.open_url` |
| `tests/test_main_frozen.py` | Update existing `_settings_cmd` and dispatch cases; add `--tab` cases |

---

### Task 1: Version constant and pyproject bump

**Files:**
- Modify: `micdot/__init__.py`
- Modify: `pyproject.toml`

- [ ] **Step 1: Add `__version__` to `micdot/__init__.py`**

The file is currently empty. Replace its contents with:

```python
__version__ = "0.5.0"
```

- [ ] **Step 2: Bump version in `pyproject.toml`**

Change line 7:
```toml
version = "0.5.0"
```

- [ ] **Step 3: Verify the constant is importable**

```bash
python -c "from micdot import __version__; print(__version__)"
```

Expected output:
```
0.5.0
```

- [ ] **Step 4: Commit**

```bash
git add micdot/__init__.py pyproject.toml
git commit -m "chore: set version to 0.5.0"
```

---

### Task 2: `micdot/version.py` — version resolver (TDD)

**Files:**
- Create: `tests/test_version.py`
- Create: `micdot/version.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_version.py`:

```python
import sys
from unittest.mock import MagicMock


def test_get_version_returns_package_version_when_not_frozen():
    from micdot import __version__
    from micdot.version import get_version
    assert get_version() == __version__


def test_get_version_reads_nsbundle_when_frozen(mocker):
    mock_foundation = MagicMock()
    mock_foundation.NSBundle.mainBundle.return_value.infoDictionary.return_value = {
        "CFBundleShortVersionString": "9.9.9"
    }
    mocker.patch.object(sys, "frozen", True, create=True)
    mocker.patch.dict("sys.modules", {"Foundation": mock_foundation})

    from micdot.version import get_version
    assert get_version() == "9.9.9"


def test_get_version_falls_back_when_nsbundle_raises(mocker):
    from micdot import __version__
    mock_foundation = MagicMock()
    mock_foundation.NSBundle.mainBundle.side_effect = Exception("no bundle")
    mocker.patch.object(sys, "frozen", True, create=True)
    mocker.patch.dict("sys.modules", {"Foundation": mock_foundation})

    from micdot.version import get_version
    assert get_version() == __version__
```

- [ ] **Step 2: Run to confirm they fail**

```bash
pytest tests/test_version.py -v
```

Expected: `ERROR` — `ModuleNotFoundError: No module named 'micdot.version'`

- [ ] **Step 3: Create `micdot/version.py`**

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

- [ ] **Step 4: Run to confirm they pass**

```bash
pytest tests/test_version.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add micdot/version.py tests/test_version.py
git commit -m "feat: add version resolver with NSBundle support for frozen app"
```

---

### Task 3: `_build_html`, About tab, updated `run()` and `__main__` (TDD)

**Files:**
- Modify: `tests/test_settings_window.py` (extend)
- Modify: `micdot/settings_window.py` (major rewrite of `_HTML`, new `_build_html`, updated `run()` and `__main__`)

- [ ] **Step 1: Add failing tests for `_build_html` to `tests/test_settings_window.py`**

First, update the existing import line near the top of the file:

```python
# before
from micdot.settings_window import Api

# after
from micdot.settings_window import Api, _build_html
```

Then append these cases at the bottom of the file:

```python
def test_build_html_substitutes_all_placeholders(tmp_path):
    config = Config.load(tmp_path / "config.json")
    html = _build_html(config, "settings", "0.5.0")
    assert "CONFIG_PLACEHOLDER" not in html
    assert "INITIAL_TAB_PLACEHOLDER" not in html
    assert "VERSION_PLACEHOLDER" not in html


def test_build_html_sets_initial_tab_settings(tmp_path):
    config = Config.load(tmp_path / "config.json")
    html = _build_html(config, "settings", "0.5.0")
    assert '"settings"' in html


def test_build_html_sets_initial_tab_about(tmp_path):
    config = Config.load(tmp_path / "config.json")
    html = _build_html(config, "about", "0.5.0")
    assert '"about"' in html


def test_build_html_injects_version(tmp_path):
    config = Config.load(tmp_path / "config.json")
    html = _build_html(config, "settings", "1.2.3")
    assert "1.2.3" in html


def test_build_html_includes_github_link(tmp_path):
    config = Config.load(tmp_path / "config.json")
    html = _build_html(config, "settings", "0.5.0")
    assert "https://github.com/andrecedik/micdot" in html


def test_build_html_includes_support_link(tmp_path):
    config = Config.load(tmp_path / "config.json")
    html = _build_html(config, "settings", "0.5.0")
    assert "https://donatr.ee/andrecedik" in html
```

Also add `Config` to the existing import line at the top of `test_settings_window.py` — it is already imported there, so no change needed.

- [ ] **Step 2: Run to confirm they fail**

```bash
pytest tests/test_settings_window.py -v -k "build_html"
```

Expected: `ImportError` — `cannot import name '_build_html'`

- [ ] **Step 3: Rewrite `_HTML` and add `_build_html` in `micdot/settings_window.py`**

Add `import webbrowser` and `from micdot.version import get_version` to the imports block at the top of the file (alongside the existing imports):

```python
import webbrowser
from micdot.version import get_version
```

Replace the entire `_HTML` string (lines 17–125) with:

```python
_HTML = """\
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,sans-serif;font-size:13px;
  background:#f0f0f0;padding:20px;color:#222}
h1{font-size:15px;font-weight:600;margin-bottom:12px;color:#111}
.lbl{font-size:10px;font-weight:600;text-transform:uppercase;letter-spacing:.8px;
  color:#888;margin-bottom:6px}
.group{background:#fff;border-radius:8px;border:1px solid #e5e5e5;
  overflow:hidden;margin-bottom:16px}
.row{display:flex;align-items:center;padding:8px 12px;
  border-bottom:1px solid #e5e5e5}
.row:last-child{border-bottom:none}
.row>label{width:110px;color:#555;flex-shrink:0}
.row input[type=text],.row input[type=password],.row input[type=number]{
  flex:1;border:none;outline:none;font-size:13px;font-family:inherit;background:transparent}
.crow{display:flex;align-items:center;gap:8px;flex:1}
input[type=color]{width:22px;height:22px;border:1px solid #ccc;border-radius:4px;
  padding:0;cursor:pointer;flex-shrink:0}
.hex{font-family:monospace;border:1px solid #ddd;border-radius:4px;
  padding:3px 6px;font-size:12px;flex:1;outline:none}
.autorow{display:flex;align-items:center;justify-content:space-between;
  padding:8px 0;margin-bottom:16px}
button{width:100%;padding:8px;border-radius:6px;background:#007aff;color:#fff;
  border:none;font-size:13px;font-weight:500;cursor:pointer}
button:disabled{opacity:.6;cursor:default}
nav.tabs{display:flex;gap:2px;background:#e0e0e0;border-radius:8px;padding:2px;margin-bottom:16px}
.tab-btn{flex:1;padding:5px;border:none;background:transparent;font-size:12px;font-weight:500;
  color:#555;border-radius:6px;cursor:pointer}
.tab-btn.active{background:#fff;color:#111;box-shadow:0 1px 3px rgba(0,0,0,.12)}
.pane.hidden{display:none}
.link-row{display:flex;align-items:center;padding:10px 12px;border-bottom:1px solid #e5e5e5;
  text-decoration:none;color:#007aff;font-size:13px;cursor:pointer}
.link-row:last-child{border-bottom:none}
.about-app{padding:16px 12px 4px;font-size:15px;font-weight:600;color:#111}
.about-ver{padding:2px 12px 14px;font-size:12px;color:#888}
</style>
</head>
<body>
<h1>MicDot</h1>
<nav class="tabs">
  <button class="tab-btn" data-tab="settings">Settings</button>
  <button class="tab-btn" data-tab="about">About</button>
</nav>
<section class="pane" id="pane-settings">
<div class="lbl">MQTT</div>
<div class="group">
  <div class="row"><label>Host</label>
    <input type="text" id="mqtt_host"></div>
  <div class="row"><label>Port</label>
    <input type="number" id="mqtt_port" min="1" max="65535" style="width:70px;flex:none"></div>
  <div class="row"><label>Username</label>
    <input type="text" id="mqtt_username" autocomplete="off"></div>
  <div class="row"><label>Password</label>
    <input type="password" id="mqtt_password" autocomplete="off"></div>
</div>
<div class="lbl">HARDWARE &amp; BEHAVIOUR</div>
<div class="group">
  <div class="row"><label>Hotkey</label>
    <input type="text" id="hotkey"></div>
  <div class="row"><label>Brightness</label>
    <input type="number" id="led_brightness" min="0" max="255" style="width:70px;flex:none"></div>
  <div class="row"><label>Muted color</label>
    <div class="crow">
      <input type="color" id="mp">
      <input type="text" class="hex" id="mh" maxlength="7">
    </div></div>
  <div class="row"><label>Unmuted color</label>
    <div class="crow">
      <input type="color" id="up">
      <input type="text" class="hex" id="uh" maxlength="7">
    </div></div>
</div>
<div class="autorow">
  <span>Autostart on login</span>
  <input type="checkbox" id="autostart">
</div>
<button id="btn">Save</button>
</section>
<section class="pane" id="pane-about">
<div class="group">
  <div class="about-app">MicDot</div>
  <div class="about-ver" id="about-version"></div>
</div>
<div class="lbl">LINKS</div>
<div class="group">
  <a class="link-row" href="#" data-url="https://github.com/andrecedik/micdot">GitHub Repository ↗</a>
  <a class="link-row" href="#" data-url="https://donatr.ee/andrecedik">Support me ↗</a>
</div>
</section>
<script>
var c=CONFIG_PLACEHOLDER;
var initialTab=INITIAL_TAB_PLACEHOLDER;
var appVersion=VERSION_PLACEHOLDER;
document.getElementById('about-version').textContent='Version '+appVersion;
var panes=document.querySelectorAll('.pane');
var tabBtns=document.querySelectorAll('.tab-btn');
function showTab(name){
  panes.forEach(function(p){p.classList.toggle('hidden',p.id!=='pane-'+name)});
  tabBtns.forEach(function(b){b.classList.toggle('active',b.dataset.tab===name)});
}
tabBtns.forEach(function(b){b.addEventListener('click',function(){showTab(b.dataset.tab)})});
showTab(initialTab);
document.querySelectorAll('[data-url]').forEach(function(el){
  el.addEventListener('click',function(e){
    e.preventDefault();
    window.pywebview.api.open_url(el.dataset.url);
  });
});
document.getElementById('mqtt_host').value=c.mqtt_host;
document.getElementById('mqtt_port').value=c.mqtt_port;
document.getElementById('mqtt_username').value=c.mqtt_username;
document.getElementById('mqtt_password').value=c.mqtt_password;
document.getElementById('hotkey').value=c.hotkey;
document.getElementById('led_brightness').value=c.led_brightness;
document.getElementById('autostart').checked=c.autostart;
function toHex(o){return'#'+[o.r,o.g,o.b].map(function(v){return('0'+v.toString(16)).slice(-2)}).join('')}
function hexToRgb(h){h=h.replace('#','');return{r:parseInt(h.slice(0,2),16),g:parseInt(h.slice(2,4),16),b:parseInt(h.slice(4,6),16)}}
var mp=document.getElementById('mp'),mh=document.getElementById('mh');
var up=document.getElementById('up'),uh=document.getElementById('uh');
mp.value=mh.value=toHex(c.color_muted);
up.value=uh.value=toHex(c.color_unmuted);
mp.addEventListener('input',function(){mh.value=mp.value});
mh.addEventListener('input',function(){if(/^#[0-9a-fA-F]{6}$/.test(mh.value))mp.value=mh.value});
up.addEventListener('input',function(){uh.value=up.value});
uh.addEventListener('input',function(){if(/^#[0-9a-fA-F]{6}$/.test(uh.value))up.value=uh.value});
document.getElementById('btn').addEventListener('click',function(){
  var portVal=parseInt(document.getElementById('mqtt_port').value);
  var brightVal=parseInt(document.getElementById('led_brightness').value);
  if(isNaN(portVal)||portVal<1||portVal>65535){alert('Port must be 1–65535');return;}
  if(isNaN(brightVal)||brightVal<0||brightVal>255){alert('Brightness must be 0–255');return;}
  var mhv=/^#[0-9a-fA-F]{6}$/.test(mh.value)?mh.value:toHex(c.color_muted);
  var uhv=/^#[0-9a-fA-F]{6}$/.test(uh.value)?uh.value:toHex(c.color_unmuted);
  document.getElementById('btn').disabled=true;
  window.pywebview.api.save({
    mqtt_host:document.getElementById('mqtt_host').value,
    mqtt_port:portVal,
    mqtt_username:document.getElementById('mqtt_username').value,
    mqtt_password:document.getElementById('mqtt_password').value,
    hotkey:document.getElementById('hotkey').value,
    led_brightness:brightVal,
    color_muted:hexToRgb(mhv),
    color_unmuted:hexToRgb(uhv),
    autostart:document.getElementById('autostart').checked
  }).catch(function(){document.getElementById('btn').disabled=false;});
});
</script>
</body>
</html>"""
```

Add `_build_html` immediately after the `_HTML` string (before the `class Api:` line):

```python
def _build_html(config: Config, initial_tab: str, version: str) -> str:
    html = _HTML.replace("CONFIG_PLACEHOLDER", json.dumps(asdict(config)))
    html = html.replace("INITIAL_TAB_PLACEHOLDER", json.dumps(initial_tab))
    html = html.replace("VERSION_PLACEHOLDER", json.dumps(version))
    return html
```

- [ ] **Step 4: Update `run()` and `__main__` in `micdot/settings_window.py`**

Replace the existing `run()` function:

```python
def run(config_path: Path, initial_tab: str = "settings") -> None:
    import webview  # deferred so tests never need pywebview mocked
    if initial_tab not in {"settings", "about"}:
        initial_tab = "settings"
    config = Config.load(config_path)
    api = Api(config_path)
    html = _build_html(config, initial_tab, get_version())
    window = webview.create_window(
        "MicDot Settings",
        html=html,
        js_api=api,
        width=440,
        height=580,
        resizable=False,
    )
    api.set_window(window)
    webview.start()
    sys.exit(0 if api.saved else 1)
```

Replace the `__main__` block:

```python
if __name__ == "__main__":
    argv = sys.argv[1:]
    tab = "settings"
    if "--tab" in argv:
        i = argv.index("--tab")
        if i + 1 < len(argv):
            tab = argv[i + 1]
            del argv[i:i + 2]
    path = Path(argv[0]) if argv else DEFAULT_CONFIG_PATH
    run(path, initial_tab=tab)
```

- [ ] **Step 5: Run the new tests to confirm they pass, and the full suite to check for regressions**

```bash
pytest tests/test_settings_window.py -v
```

Expected: all existing tests pass, 6 new `build_html` tests pass.

- [ ] **Step 6: Commit**

```bash
git add micdot/settings_window.py tests/test_settings_window.py
git commit -m "feat: add About tab to settings window with _build_html helper"
```

---

### Task 4: `Api.open_url` (TDD)

**Files:**
- Modify: `tests/test_settings_window.py` (extend)
- Modify: `micdot/settings_window.py` (extend `Api`)

- [ ] **Step 1: Add failing tests for `Api.open_url`**

Append to `tests/test_settings_window.py`:

```python
def test_open_url_calls_webbrowser_for_https(api, mocker):
    mock_open = mocker.patch("micdot.settings_window.webbrowser.open")
    api.open_url("https://github.com/andrecedik/micdot")
    mock_open.assert_called_once_with("https://github.com/andrecedik/micdot")


def test_open_url_calls_webbrowser_for_http(api, mocker):
    mock_open = mocker.patch("micdot.settings_window.webbrowser.open")
    api.open_url("http://example.com")
    mock_open.assert_called_once_with("http://example.com")


def test_open_url_rejects_file_scheme(api, mocker):
    mock_open = mocker.patch("micdot.settings_window.webbrowser.open")
    api.open_url("file:///etc/passwd")
    mock_open.assert_not_called()


def test_open_url_rejects_javascript_scheme(api, mocker):
    mock_open = mocker.patch("micdot.settings_window.webbrowser.open")
    api.open_url("javascript:alert(1)")
    mock_open.assert_not_called()


def test_open_url_rejects_empty_string(api, mocker):
    mock_open = mocker.patch("micdot.settings_window.webbrowser.open")
    api.open_url("")
    mock_open.assert_not_called()


def test_open_url_rejects_non_string(api, mocker):
    mock_open = mocker.patch("micdot.settings_window.webbrowser.open")
    api.open_url(None)
    mock_open.assert_not_called()
```

- [ ] **Step 2: Run to confirm they fail**

```bash
pytest tests/test_settings_window.py -v -k "open_url"
```

Expected: `AttributeError` — `'Api' object has no attribute 'open_url'`

- [ ] **Step 3: Add `open_url` to the `Api` class in `micdot/settings_window.py`**

Add this method to `Api` after `_handle_autostart`:

```python
def open_url(self, url: str) -> None:
    if not isinstance(url, str) or not url.startswith(("http://", "https://")):
        log.warning("Refusing to open non-http(s) URL: %r", url)
        return
    log.info("Opening external URL %s", url)
    webbrowser.open(url)
```

- [ ] **Step 4: Run to confirm they pass**

```bash
pytest tests/test_settings_window.py -v -k "open_url"
```

Expected: 6 passed.

- [ ] **Step 5: Run the full suite**

```bash
pytest tests/test_settings_window.py -v
```

Expected: all tests pass (no regressions).

- [ ] **Step 6: Commit**

```bash
git add micdot/settings_window.py tests/test_settings_window.py
git commit -m "feat: add Api.open_url with http(s) allowlist for external links"
```

---

### Task 5: `main.py` subprocess plumbing (TDD)

**Files:**
- Modify: `tests/test_main_frozen.py` (update existing + add new)
- Modify: `micdot/main.py`

- [ ] **Step 1: Update existing tests and add new ones in `tests/test_main_frozen.py`**

The two existing `_settings_cmd` tests and the two frozen-dispatch tests will fail once `main.py` is updated (they don't account for `--tab` in the command or `initial_tab` in the `run_settings` call). Update them now so the test file reflects the desired end state, then implement.

Replace the full contents of `tests/test_main_frozen.py` with:

```python
import sys
import pytest
from pathlib import Path
from unittest.mock import patch


def test_settings_cmd_returns_module_mode_when_not_frozen():
    from micdot.main import _settings_cmd
    cmd = _settings_cmd(Path("/cfg/config.json"))
    assert cmd == [
        sys.executable, "-m", "micdot.settings_window",
        "/cfg/config.json", "--tab", "settings",
    ]


def test_settings_cmd_returns_flag_mode_when_frozen():
    from micdot.main import _settings_cmd
    with patch.object(sys, "frozen", True, create=True), \
         patch.object(sys, "executable", "/App/MicDot.app/Contents/MacOS/MicDot"):
        cmd = _settings_cmd(Path("/cfg/config.json"))
    assert cmd == [
        "/App/MicDot.app/Contents/MacOS/MicDot", "--settings",
        "/cfg/config.json", "--tab", "settings",
    ]


def test_settings_cmd_passes_tab_about():
    from micdot.main import _settings_cmd
    cmd = _settings_cmd(Path("/cfg/config.json"), tab="about")
    assert "--tab" in cmd
    assert cmd[cmd.index("--tab") + 1] == "about"


def test_main_dispatches_to_settings_when_frozen_with_flag(tmp_path, mocker):
    cfg_path = tmp_path / "config.json"
    mocker.patch.object(sys, "frozen", True, create=True)
    mocker.patch.object(sys, "argv", ["micdot", "--settings", str(cfg_path)])
    mock_run = mocker.patch("micdot.settings_window.run")

    from micdot.main import main
    main()

    mock_run.assert_called_once_with(cfg_path, initial_tab="settings")


def test_main_dispatches_to_about_when_tab_flag_set(tmp_path, mocker):
    cfg_path = tmp_path / "config.json"
    mocker.patch.object(sys, "frozen", True, create=True)
    mocker.patch.object(sys, "argv", ["micdot", "--settings", str(cfg_path), "--tab", "about"])
    mock_run = mocker.patch("micdot.settings_window.run")

    from micdot.main import main
    main()

    mock_run.assert_called_once_with(cfg_path, initial_tab="about")


def test_main_uses_default_config_path_when_no_path_arg(mocker):
    from micdot.config import DEFAULT_CONFIG_PATH
    mocker.patch.object(sys, "frozen", True, create=True)
    mocker.patch.object(sys, "argv", ["micdot", "--settings"])
    mock_run = mocker.patch("micdot.settings_window.run")

    from micdot.main import main
    main()

    mock_run.assert_called_once_with(DEFAULT_CONFIG_PATH, initial_tab="settings")
```

- [ ] **Step 2: Run to confirm the updated tests fail**

```bash
pytest tests/test_main_frozen.py -v
```

Expected: multiple failures — `_settings_cmd` missing `--tab`, `run_settings` called without `initial_tab`.

- [ ] **Step 3: Update `_settings_cmd` in `micdot/main.py`**

Replace the existing `_settings_cmd` function:

```python
def _settings_cmd(config_path: Path, tab: str = "settings") -> list[str]:
    if getattr(sys, "frozen", False):
        return [sys.executable, "--settings", str(config_path), "--tab", tab]
    return [sys.executable, "-m", "micdot.settings_window", str(config_path), "--tab", tab]
```

- [ ] **Step 4: Update the frozen re-entry block in `main()` in `micdot/main.py`**

Replace the frozen re-entry block (the `if getattr(sys, "frozen", False) and "--settings"` block at the top of `main()`):

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

- [ ] **Step 5: Refactor `open_settings` into `_open_settings_window` and add `open_about`**

Inside the `main()` function, replace the `open_settings` closure with:

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

- [ ] **Step 6: Run the full frozen test suite**

```bash
pytest tests/test_main_frozen.py -v
```

Expected: 6 passed.

- [ ] **Step 7: Run the full test suite to check for regressions**

```bash
pytest -v
```

Expected: all tests pass.

- [ ] **Step 8: Commit**

```bash
git add micdot/main.py tests/test_main_frozen.py
git commit -m "feat: add --tab flag to settings subprocess and open_about callback"
```

---

### Task 6: `tray.py` — About menu item, and wire `open_about` in `main.py`

**Files:**
- Modify: `micdot/tray.py`
- Modify: `micdot/main.py` (one-line change to `TrayIcon(...)` call)

No new automated tests — the tray is callback plumbing verified by smoke test.

- [ ] **Step 1: Add `on_about` to `TrayIcon.__init__`, update menu, add `_about` method**

In `micdot/tray.py`, replace the `TrayIcon` class with:

```python
class TrayIcon:
    def __init__(
        self,
        on_toggle: Callable[[], None],
        on_settings: Callable[[], None],
        on_about: Callable[[], None],
        on_quit: Callable[[], None],
    ):
        self._on_toggle = on_toggle
        self._on_settings = on_settings
        self._on_about = on_about
        self._on_quit = on_quit
        self._icon = pystray.Icon(
            "micdot",
            _make_icon((128, 128, 128)),
            menu=pystray.Menu(
                pystray.MenuItem("Toggle Mute", self._toggle, default=True),
                pystray.MenuItem("Settings", self._settings),
                pystray.MenuItem("About", self._about),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Quit", self._quit),
            ),
        )
        if sys.platform == "darwin":
            status_item = getattr(self._icon, "_status_item", None)
            if status_item is not None:
                status_item.setAutosaveName_("MicDot")

    def set_muted(self, muted: bool) -> None:
        self._icon.icon = _make_icon((0, 200, 0) if muted else (200, 0, 0))

    def run(self) -> None:
        if sys.platform == "darwin":
            _hide_dock_icon()
        self._icon.run()

    def stop(self) -> None:
        self._icon.stop()

    def _toggle(self, icon, item) -> None:
        self._on_toggle()

    def _settings(self, icon, item) -> None:
        self._on_settings()

    def _about(self, icon, item) -> None:
        self._on_about()

    def _quit(self, icon, item) -> None:
        self.stop()
        self._on_quit()
```

- [ ] **Step 2: Pass `on_about=open_about` in `micdot/main.py`**

In `main()`, find the `TrayIcon(...)` call and add the `on_about` argument:

```python
tray = TrayIcon(
    on_toggle=on_toggle,
    on_settings=open_settings,
    on_about=open_about,
    on_quit=on_quit,
)
```

- [ ] **Step 3: Run the full test suite**

```bash
pytest -v
```

Expected: all tests pass.

- [ ] **Step 4: Commit**

```bash
git add micdot/tray.py micdot/main.py
git commit -m "feat: add About tray menu item and wire open_about callback"
```

---

### Task 7: CHANGELOG

**Files:**
- Modify: `CHANGELOG.md`

- [ ] **Step 1: Add entry under `[Unreleased]`**

The `[Unreleased]` section is currently empty (line 7–8). Add:

```markdown
## [Unreleased]

### Added

- About tab in settings window showing app version, GitHub link, and a "Support me" donate link.
- "About" tray menu item that opens the About tab directly.
```

- [ ] **Step 2: Run the full suite one final time**

```bash
pytest -v
```

Expected: all tests pass.

- [ ] **Step 3: Commit**

```bash
git add CHANGELOG.md
git commit -m "docs: add About page and tray item to CHANGELOG"
```

---

## Smoke Test Checklist

After all tasks are committed, verify manually:

**Source-mode:**
```bash
pip install -e ".[dev]"
micdot
```
- [ ] Tray menu shows: `Toggle Mute`, `Settings`, `About`, separator, `Quit`
- [ ] `Settings` → window opens on Settings tab; Save still works; config reloads on close
- [ ] `About` (window closed) → window opens on About tab; version shows `0.5.0`
- [ ] GitHub and Support me links open in the system browser
- [ ] Tab bar switches between panes; Save button absent on About, present on Settings
- [ ] Clicking the other tray item while the window is open is a no-op

**Frozen-app:**
```bash
MICDOT_VERSION="0.5.0" pyinstaller MicDot.spec --noconfirm
open dist/MicDot.app
```
- [ ] About tab shows `0.5.0` sourced from `CFBundleShortVersionString`
- [ ] Both tray entries open the correct tab; both links open the system browser
- [ ] Save still works (no regression to the `performSelectorOnMainThread` close path)
