# Browser Settings Window Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the tkinter settings window with a pywebview WKWebView window backed by embedded HTML, and add live config reload in the main app when the user saves.

**Architecture:** `settings_window.py` is rewritten to spin up a pywebview window (via subprocess, as today) that serves an embedded HTML form. On Save, JS calls a Python `Api.save()` method via pywebview's JS bridge; the process exits 0. `main.py` watches the subprocess exit code on a daemon thread and, on 0, calls `_reload_config()` which hot-swaps the MQTT client and hotkey listener.

**Tech Stack:** `pywebview>=4.0` (WKWebView on macOS), stdlib `threading`, `json`, `dataclasses.asdict`

---

## File Map

| File | Action |
|------|--------|
| `pyproject.toml` | Add `pywebview>=4.0` to `dependencies` |
| `micdot/settings_window.py` | Full rewrite: `Api` class + `_HTML` constant + `run()` via pywebview |
| `micdot/main.py` | Add `import threading`; add `_State` class + `_reload_config()`; refactor `main()` |
| `tests/test_settings_window.py` | New: tests for `Api.save()` |
| `tests/test_main_reload.py` | New: tests for `_reload_config()` |

---

## Task 1: Add pywebview dependency

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Add pywebview to dependencies**

Edit `pyproject.toml` — change the `dependencies` list from:
```toml
dependencies = [
    "pystray>=0.19.0",
    "Pillow>=10.0.0",
    "paho-mqtt>=1.6.1,<2.0",
    "pynput>=1.7.6",
]
```
to:
```toml
dependencies = [
    "pystray>=0.19.0",
    "Pillow>=10.0.0",
    "paho-mqtt>=1.6.1,<2.0",
    "pynput>=1.7.6",
    "pywebview>=4.0",
]
```

- [ ] **Step 2: Install**

```bash
pip install -e ".[dev]"
```

- [ ] **Step 3: Verify import**

```bash
python -c "import webview; print(webview.__version__)"
```

Expected: a version string starting with `4.` (e.g. `4.4.1`)

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "feat: add pywebview dependency"
```

---

## Task 2: Implement and test `Api` class

The `Api` class is a plain Python object (no webview needed to instantiate it). Tests call `api.save(data)` directly — no browser, no subprocess.

**Files:**
- Create: `tests/test_settings_window.py`
- Modify: `micdot/settings_window.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_settings_window.py`:

```python
import pytest
from micdot.config import Config
from micdot.settings_window import Api


@pytest.fixture
def api(tmp_path):
    return Api(tmp_path / "config.json")


_DATA = {
    "mqtt_host": "broker.local",
    "mqtt_port": 1883,
    "mqtt_username": "user",
    "mqtt_password": "s3cr3t",
    "hotkey": "ctrl+shift+m",
    "led_brightness": 128,
    "color_muted": {"r": 0, "g": 255, "b": 0},
    "color_unmuted": {"r": 255, "g": 0, "b": 0},
    "autostart": False,
}


def test_save_writes_config_to_file(api, tmp_path, mocker):
    mocker.patch("micdot.settings_window.enable_autostart")
    mocker.patch("micdot.settings_window.disable_autostart")
    api.save(_DATA)
    loaded = Config.load(tmp_path / "config.json")
    assert loaded.mqtt_host == "broker.local"
    assert loaded.mqtt_port == 1883
    assert loaded.mqtt_username == "user"
    assert loaded.color_muted == {"r": 0, "g": 255, "b": 0}


def test_save_sets_saved_flag(api, mocker):
    mocker.patch("micdot.settings_window.enable_autostart")
    mocker.patch("micdot.settings_window.disable_autostart")
    assert not api.saved
    api.save(_DATA)
    assert api.saved


def test_save_enables_autostart_when_true(api, mocker):
    enable = mocker.patch("micdot.settings_window.enable_autostart")
    mocker.patch("micdot.settings_window.disable_autostart")
    api.save({**_DATA, "autostart": True})
    enable.assert_called_once()


def test_save_disables_autostart_when_false(api, mocker):
    mocker.patch("micdot.settings_window.enable_autostart")
    disable = mocker.patch("micdot.settings_window.disable_autostart")
    api.save({**_DATA, "autostart": False})
    disable.assert_called_once()
```

- [ ] **Step 2: Run — confirm failure**

```bash
pytest tests/test_settings_window.py -v
```

Expected: `ImportError` or `4 failed` — `Api` does not exist yet.

- [ ] **Step 3: Add `Api` class to `settings_window.py`**

Replace the entire contents of `micdot/settings_window.py` with:

```python
"""Run as: python -m micdot.settings_window [config_path]"""
from __future__ import annotations
import json
import shutil
import sys
from dataclasses import asdict
from pathlib import Path

from micdot.autostart import enable_autostart, disable_autostart
from micdot.config import Config, DEFAULT_CONFIG_PATH


class Api:
    def __init__(self, config_path: Path) -> None:
        self._config_path = config_path
        self._saved = False
        self._window = None

    @property
    def saved(self) -> bool:
        return self._saved

    def set_window(self, window) -> None:
        self._window = window

    def save(self, data: dict) -> None:
        new = Config(
            mqtt_host=str(data["mqtt_host"]),
            mqtt_port=int(data["mqtt_port"]),
            mqtt_username=str(data["mqtt_username"]),
            mqtt_password=str(data["mqtt_password"]),
            hotkey=str(data["hotkey"]),
            led_brightness=int(data["led_brightness"]),
            color_muted={
                "r": int(data["color_muted"]["r"]),
                "g": int(data["color_muted"]["g"]),
                "b": int(data["color_muted"]["b"]),
            },
            color_unmuted={
                "r": int(data["color_unmuted"]["r"]),
                "g": int(data["color_unmuted"]["g"]),
                "b": int(data["color_unmuted"]["b"]),
            },
            autostart=bool(data["autostart"]),
        )
        new.save(self._config_path)
        if new.autostart:
            python = shutil.which("python3") or sys.executable
            enable_autostart(f"{python} -m micdot.main")
        else:
            disable_autostart()
        self._saved = True
        if self._window is not None:
            self._window.destroy()


_HTML = ""  # filled in Task 3


def run(config_path: Path) -> None:
    raise NotImplementedError("pywebview run() added in Task 3")


if __name__ == "__main__":
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_CONFIG_PATH
    run(path)
```

- [ ] **Step 4: Run — confirm passing**

```bash
pytest tests/test_settings_window.py -v
```

Expected:
```
PASSED tests/test_settings_window.py::test_save_writes_config_to_file
PASSED tests/test_settings_window.py::test_save_sets_saved_flag
PASSED tests/test_settings_window.py::test_save_enables_autostart_when_true
PASSED tests/test_settings_window.py::test_save_disables_autostart_when_false
4 passed
```

- [ ] **Step 5: Run full suite — confirm no regressions**

```bash
pytest -v
```

Expected: all previously passing tests still pass.

- [ ] **Step 6: Commit**

```bash
git add micdot/settings_window.py tests/test_settings_window.py
git commit -m "feat: add Api class to settings_window with tests"
```

---

## Task 3: Complete `settings_window.py` — HTML + pywebview `run()`

**Files:**
- Modify: `micdot/settings_window.py`

- [ ] **Step 1: Replace `_HTML` and `run()` in `settings_window.py`**

Replace the entire file with the final implementation:

```python
"""Run as: python -m micdot.settings_window [config_path]"""
from __future__ import annotations
import json
import shutil
import sys
from dataclasses import asdict
from pathlib import Path

from micdot.autostart import enable_autostart, disable_autostart
from micdot.config import Config, DEFAULT_CONFIG_PATH


_HTML = """\
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,sans-serif;font-size:13px;
  background:#f0f0f0;padding:20px;color:#222}
h1{font-size:15px;font-weight:600;margin-bottom:16px;color:#111}
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
</style>
</head>
<body>
<h1>MicDot Settings</h1>
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
<script>
var c=CONFIG_PLACEHOLDER;
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
  document.getElementById('btn').disabled=true;
  window.pywebview.api.save({
    mqtt_host:document.getElementById('mqtt_host').value,
    mqtt_port:parseInt(document.getElementById('mqtt_port').value),
    mqtt_username:document.getElementById('mqtt_username').value,
    mqtt_password:document.getElementById('mqtt_password').value,
    hotkey:document.getElementById('hotkey').value,
    led_brightness:parseInt(document.getElementById('led_brightness').value),
    color_muted:hexToRgb(mh.value),
    color_unmuted:hexToRgb(uh.value),
    autostart:document.getElementById('autostart').checked
  });
});
</script>
</body>
</html>"""


class Api:
    def __init__(self, config_path: Path) -> None:
        self._config_path = config_path
        self._saved = False
        self._window = None

    @property
    def saved(self) -> bool:
        return self._saved

    def set_window(self, window) -> None:
        self._window = window

    def save(self, data: dict) -> None:
        new = Config(
            mqtt_host=str(data["mqtt_host"]),
            mqtt_port=int(data["mqtt_port"]),
            mqtt_username=str(data["mqtt_username"]),
            mqtt_password=str(data["mqtt_password"]),
            hotkey=str(data["hotkey"]),
            led_brightness=int(data["led_brightness"]),
            color_muted={
                "r": int(data["color_muted"]["r"]),
                "g": int(data["color_muted"]["g"]),
                "b": int(data["color_muted"]["b"]),
            },
            color_unmuted={
                "r": int(data["color_unmuted"]["r"]),
                "g": int(data["color_unmuted"]["g"]),
                "b": int(data["color_unmuted"]["b"]),
            },
            autostart=bool(data["autostart"]),
        )
        new.save(self._config_path)
        if new.autostart:
            python = shutil.which("python3") or sys.executable
            enable_autostart(f"{python} -m micdot.main")
        else:
            disable_autostart()
        self._saved = True
        if self._window is not None:
            self._window.destroy()


def run(config_path: Path) -> None:
    import webview  # deferred so tests never need pywebview mocked
    config = Config.load(config_path)
    api = Api(config_path)
    html = _HTML.replace("CONFIG_PLACEHOLDER", json.dumps(asdict(config)))
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


if __name__ == "__main__":
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_CONFIG_PATH
    run(path)
```

- [ ] **Step 2: Run tests — confirm all still pass**

```bash
pytest -v
```

Expected: same 4 `test_settings_window` tests pass; all other tests pass.

- [ ] **Step 3: Smoke-test the window manually**

```bash
python -m micdot.settings_window
```

Expected: a 440×580 native macOS window opens titled "MicDot Settings" with two grouped sections. Change a field, click Save — window closes, `~/.config/micdot/config.json` is updated.

- [ ] **Step 4: Commit**

```bash
git add micdot/settings_window.py
git commit -m "feat: replace tkinter settings window with pywebview"
```

---

## Task 4: Add `_State` + `_reload_config` to `main.py` and test

**Files:**
- Create: `tests/test_main_reload.py`
- Modify: `micdot/main.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_main_reload.py`:

```python
import pytest
from unittest.mock import MagicMock
from micdot.config import Config
from micdot.main import _State, _reload_config


@pytest.fixture
def config_path(tmp_path):
    cfg = Config(mqtt_host="new-host", mqtt_port=1884, hotkey="ctrl+shift+x")
    cfg.save(tmp_path / "config.json")
    return tmp_path / "config.json"


def test_reload_stops_old_mqtt_and_starts_new(config_path, mocker):
    old_mqtt = MagicMock()
    mock_mqtt_cls = mocker.patch("micdot.main.MQTTClient")
    mocker.patch("micdot.main.HotkeyListener")
    state = _State(Config(), old_mqtt, MagicMock())
    on_toggle = MagicMock()

    _reload_config(state, config_path, on_toggle)

    old_mqtt.stop.assert_called_once()
    assert mock_mqtt_cls.call_args[0][0].mqtt_host == "new-host"
    mock_mqtt_cls.return_value.start.assert_called_once()


def test_reload_stops_old_hotkey_and_starts_new(config_path, mocker):
    mocker.patch("micdot.main.MQTTClient")
    old_hotkey = MagicMock()
    mock_hotkey_cls = mocker.patch("micdot.main.HotkeyListener")
    state = _State(Config(), MagicMock(), old_hotkey)

    _reload_config(state, config_path, MagicMock())

    old_hotkey.stop.assert_called_once()
    assert mock_hotkey_cls.call_args[0][0] == "ctrl+shift+x"
    mock_hotkey_cls.return_value.start.assert_called_once()


def test_reload_updates_state_references(config_path, mocker):
    mock_mqtt_cls = mocker.patch("micdot.main.MQTTClient")
    mock_hotkey_cls = mocker.patch("micdot.main.HotkeyListener")
    state = _State(Config(), MagicMock(), MagicMock())

    _reload_config(state, config_path, MagicMock())

    assert state.mqtt is mock_mqtt_cls.return_value
    assert state.hotkey_listener is mock_hotkey_cls.return_value
    assert state.config.mqtt_host == "new-host"
```

- [ ] **Step 2: Run — confirm failure**

```bash
pytest tests/test_main_reload.py -v
```

Expected: `ImportError` — `_State` and `_reload_config` do not exist yet.

- [ ] **Step 3: Rewrite `main.py`**

Replace the entire contents of `micdot/main.py` with:

```python
from __future__ import annotations
import subprocess
import sys
import threading
from pathlib import Path
from typing import Callable

from micdot.audio.backend import get_backend
from micdot.config import Config, DEFAULT_CONFIG_PATH
from micdot.hotkey import HotkeyListener
from micdot.mqtt_client import MQTTClient
from micdot.poller import Poller
from micdot.tray import TrayIcon


class _State:
    __slots__ = ("config", "mqtt", "hotkey_listener")

    def __init__(
        self,
        config: Config,
        mqtt: MQTTClient,
        hotkey_listener: HotkeyListener,
    ) -> None:
        self.config = config
        self.mqtt = mqtt
        self.hotkey_listener = hotkey_listener


def _reload_config(
    state: _State,
    config_path: Path,
    on_toggle: Callable[[], None],
) -> None:
    state.config = Config.load(config_path)
    state.mqtt.stop()
    state.mqtt = MQTTClient(state.config, on_button_press=on_toggle)
    state.mqtt.start()
    state.hotkey_listener.stop()
    state.hotkey_listener = HotkeyListener(state.config.hotkey, callback=on_toggle)
    state.hotkey_listener.start()


def main() -> None:
    config = Config.load(DEFAULT_CONFIG_PATH)
    backend = get_backend()

    def on_toggle() -> None:
        poller.toggle()

    def on_state_change(muted: bool) -> None:
        state.mqtt.publish_state(muted)
        tray.set_muted(muted)

    def on_quit() -> None:
        state.hotkey_listener.stop()
        poller.stop()
        state.mqtt.stop()
        sys.exit(0)

    def open_settings() -> None:
        proc = subprocess.Popen(
            [sys.executable, "-m", "micdot.settings_window", str(DEFAULT_CONFIG_PATH)]
        )
        threading.Thread(
            target=lambda: proc.wait() == 0 and _reload_config(
                state, DEFAULT_CONFIG_PATH, on_toggle
            ),
            daemon=True,
        ).start()

    state = _State(
        config,
        MQTTClient(config, on_button_press=on_toggle),
        HotkeyListener(config.hotkey, callback=on_toggle),
    )
    poller = Poller(backend, on_change=on_state_change)
    tray = TrayIcon(
        on_toggle=on_toggle,
        on_settings=open_settings,
        on_quit=on_quit,
    )

    state.mqtt.start()
    poller.start()
    state.hotkey_listener.start()
    tray.run()


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run reload tests — confirm passing**

```bash
pytest tests/test_main_reload.py -v
```

Expected:
```
PASSED tests/test_main_reload.py::test_reload_stops_old_mqtt_and_starts_new
PASSED tests/test_main_reload.py::test_reload_stops_old_hotkey_and_starts_new
PASSED tests/test_main_reload.py::test_reload_updates_state_references
3 passed
```

- [ ] **Step 5: Run full suite — confirm no regressions**

```bash
pytest -v
```

Expected: all tests pass (35 existing + 4 settings + 3 reload = 42 total).

- [ ] **Step 6: Commit**

```bash
git add micdot/main.py tests/test_main_reload.py
git commit -m "feat: add live config reload on settings save"
```
