# ESPMuter Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python macOS menu bar app and ESPHome firmware config that together control microphone mute state via a hardware button and LED ring, bridged over MQTT.

**Architecture:** The Python app polls the system microphone mute state every 200ms via CoreAudio (ctypes, no extra dependencies), publishes state changes to MQTT, and listens for button-press events from the ESP32. The ESP32 runs ESPHome over WiFi — USB-C is power only. Home Assistant receives visibility via MQTT autodiscovery without being in the critical toggle loop.

**Tech Stack:** Python 3.11+, pystray, Pillow, paho-mqtt 1.x, pynput, tkinter (stdlib), ctypes/CoreAudio (macOS audio, no pip install needed), ESPHome with NeoPixelBus for WS2812B.

---

## File Map

| File | Responsibility |
|---|---|
| `pyproject.toml` | Project metadata, dependencies, entry point |
| `espmuter/__init__.py` | Package marker |
| `espmuter/config.py` | Config dataclass, JSON load/save, defaults |
| `espmuter/audio/__init__.py` | Package marker |
| `espmuter/audio/backend.py` | Abstract `AudioBackend` + `StubAudioBackend` for tests |
| `espmuter/audio/macos.py` | macOS CoreAudio mic mute via ctypes (no pyobjc dep) |
| `espmuter/poller.py` | 200ms polling loop, fires callback on state change, toggle |
| `espmuter/mqtt_client.py` | MQTT connection, pub/sub, HA autodiscovery payloads |
| `espmuter/hotkey.py` | Global keyboard shortcut via pynput, hotkey format conversion |
| `espmuter/autostart.py` | macOS launchd plist write/remove |
| `espmuter/tray.py` | pystray menu bar icon, left-click toggle, right-click menu |
| `espmuter/settings_window.py` | tkinter settings UI — runs as subprocess to avoid macOS thread conflicts |
| `espmuter/main.py` | Entry point, wires all components, starts threads |
| `tests/__init__.py` | Package marker |
| `tests/test_config.py` | Config dataclass and persistence tests |
| `tests/test_audio_backend.py` | AudioBackend interface and StubAudioBackend tests |
| `tests/test_poller.py` | Polling loop and toggle logic tests |
| `tests/test_mqtt_client.py` | MQTT publish and message handling tests |
| `tests/test_hotkey.py` | Hotkey format conversion and listener tests |
| `tests/test_autostart.py` | launchd plist generation tests |
| `esphome/secrets.yaml.example` | ESPHome secrets template (committed, secrets.yaml is not) |
| `esphome/espmuter.yaml` | ESPHome firmware config with multi-board substitutions |
| `.gitignore` | Excludes esphome/secrets.yaml and Python artifacts |

---

### Task 1: Project Scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `espmuter/__init__.py`
- Create: `espmuter/audio/__init__.py`
- Create: `tests/__init__.py`
- Create: `.gitignore`

- [ ] **Step 1: Create directory structure**

```bash
mkdir -p espmuter/audio tests esphome
```

- [ ] **Step 2: Create `pyproject.toml`**

```toml
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.backends.legacy:build"

[project]
name = "espmuter"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "pystray>=0.19.0",
    "Pillow>=10.0.0",
    "paho-mqtt>=1.6.1,<2.0",
    "pynput>=1.7.6",
]

[project.scripts]
espmuter = "espmuter.main:main"

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-mock>=3.12.0",
]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 3: Create empty package markers**

Create `espmuter/__init__.py` — empty file.

Create `espmuter/audio/__init__.py` — empty file.

Create `tests/__init__.py` — empty file.

- [ ] **Step 4: Create `.gitignore`**

```
esphome/secrets.yaml
__pycache__/
*.pyc
.pytest_cache/
*.egg-info/
dist/
build/
```

- [ ] **Step 5: Install dependencies**

```bash
pip install -e ".[dev]"
```

Expected: installs pystray, Pillow, paho-mqtt, pynput, pytest, pytest-mock.

- [ ] **Step 6: Verify pytest runs with no tests**

```bash
pytest
```

Expected: `no tests ran` — exit code 0.

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml espmuter/ tests/ .gitignore
git commit -m "chore: project scaffolding"
```

---

### Task 2: Config Module

**Files:**
- Create: `espmuter/config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_config.py`:

```python
import json
import pytest
from pathlib import Path
from espmuter.config import Config


def test_config_defaults():
    c = Config()
    assert c.mqtt_host == ""
    assert c.mqtt_port == 1883
    assert c.mqtt_username == ""
    assert c.mqtt_password == ""
    assert c.color_muted == {"r": 0, "g": 255, "b": 0}
    assert c.color_unmuted == {"r": 255, "g": 0, "b": 0}
    assert c.led_brightness == 128
    assert c.hotkey == "ctrl+shift+m"
    assert c.autostart is False


def test_config_save_and_load(tmp_path):
    path = tmp_path / "config.json"
    Config(mqtt_host="192.168.1.50", mqtt_port=1884).save(path)
    loaded = Config.load(path)
    assert loaded.mqtt_host == "192.168.1.50"
    assert loaded.mqtt_port == 1884


def test_config_load_missing_file_returns_defaults(tmp_path):
    config = Config.load(tmp_path / "nonexistent.json")
    assert config.mqtt_host == ""
    assert config.mqtt_port == 1883


def test_config_load_partial_file_fills_defaults(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"mqtt_host": "10.0.0.1"}))
    config = Config.load(path)
    assert config.mqtt_host == "10.0.0.1"
    assert config.mqtt_port == 1883


def test_config_save_creates_parent_dirs(tmp_path):
    path = tmp_path / "nested" / "dir" / "config.json"
    Config().save(path)
    assert path.exists()
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest tests/test_config.py -v
```

Expected: `ModuleNotFoundError: No module named 'espmuter.config'`

- [ ] **Step 3: Implement `config.py`**

Create `espmuter/config.py`:

```python
from __future__ import annotations
import json
from dataclasses import dataclass, field, asdict
from pathlib import Path

DEFAULT_CONFIG_PATH = Path.home() / ".config" / "espmuter" / "config.json"


@dataclass
class Config:
    mqtt_host: str = ""
    mqtt_port: int = 1883
    mqtt_username: str = ""
    mqtt_password: str = ""
    color_muted: dict = field(default_factory=lambda: {"r": 0, "g": 255, "b": 0})
    color_unmuted: dict = field(default_factory=lambda: {"r": 255, "g": 0, "b": 0})
    led_brightness: int = 128
    hotkey: str = "ctrl+shift+m"
    autostart: bool = False

    def save(self, path: Path = DEFAULT_CONFIG_PATH) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2))

    @classmethod
    def load(cls, path: Path = DEFAULT_CONFIG_PATH) -> "Config":
        if not path.exists():
            return cls()
        data = json.loads(path.read_text())
        defaults = asdict(cls())
        defaults.update(data)
        return cls(**{k: defaults[k] for k in asdict(cls()).keys()})
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
pytest tests/test_config.py -v
```

Expected: `5 passed`

- [ ] **Step 5: Commit**

```bash
git add espmuter/config.py tests/test_config.py
git commit -m "feat: config dataclass with JSON persistence"
```

---

### Task 3: AudioBackend Interface

**Files:**
- Create: `espmuter/audio/backend.py`
- Create: `tests/test_audio_backend.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_audio_backend.py`:

```python
from espmuter.audio.backend import AudioBackend, StubAudioBackend


def test_stub_default_mute_is_false():
    assert StubAudioBackend().get_mute() is False


def test_stub_initial_mute_true():
    assert StubAudioBackend(initial_mute=True).get_mute() is True


def test_stub_set_mute():
    backend = StubAudioBackend()
    backend.set_mute(True)
    assert backend.get_mute() is True
    backend.set_mute(False)
    assert backend.get_mute() is False


def test_stub_is_audio_backend():
    assert isinstance(StubAudioBackend(), AudioBackend)
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest tests/test_audio_backend.py -v
```

Expected: `ModuleNotFoundError: No module named 'espmuter.audio.backend'`

- [ ] **Step 3: Implement `audio/backend.py`**

Create `espmuter/audio/backend.py`:

```python
from __future__ import annotations
import sys
from abc import ABC, abstractmethod


class AudioBackend(ABC):
    @abstractmethod
    def get_mute(self) -> bool: ...

    @abstractmethod
    def set_mute(self, muted: bool) -> None: ...


class StubAudioBackend(AudioBackend):
    def __init__(self, initial_mute: bool = False):
        self._muted = initial_mute

    def get_mute(self) -> bool:
        return self._muted

    def set_mute(self, muted: bool) -> None:
        self._muted = muted


def get_backend() -> AudioBackend:
    match sys.platform:
        case "darwin":
            from espmuter.audio.macos import MacOSAudioBackend
            return MacOSAudioBackend()
        case _:
            raise NotImplementedError(f"No AudioBackend for platform: {sys.platform}")
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
pytest tests/test_audio_backend.py -v
```

Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add espmuter/audio/backend.py tests/test_audio_backend.py
git commit -m "feat: AudioBackend abstract interface and StubAudioBackend"
```

---

### Task 4: macOS AudioBackend

**Files:**
- Create: `espmuter/audio/macos.py`

No unit tests — requires real CoreAudio hardware. Verified manually.

- [ ] **Step 1: Implement `audio/macos.py`**

Create `espmuter/audio/macos.py`:

```python
from __future__ import annotations
import ctypes
from espmuter.audio.backend import AudioBackend

_ca = ctypes.cdll.LoadLibrary(
    "/System/Library/Frameworks/CoreAudio.framework/CoreAudio"
)

_kAudioObjectSystemObject = 1
_kAudioHardwarePropertyDefaultInputDevice = 0x64496E20  # 'dIn '
_kAudioDevicePropertyMute = 0x6D757465              # 'mute'
_kAudioObjectPropertyScopeGlobal = 0x676C6F62       # 'glob'
_kAudioObjectPropertyScopeInput = 0x696E7074        # 'inpt'
_kAudioObjectPropertyElementMain = 0


class _AudioObjectPropertyAddress(ctypes.Structure):
    _fields_ = [
        ("mSelector", ctypes.c_uint32),
        ("mScope", ctypes.c_uint32),
        ("mElement", ctypes.c_uint32),
    ]


def _get_default_input_device() -> int:
    prop = _AudioObjectPropertyAddress(
        _kAudioHardwarePropertyDefaultInputDevice,
        _kAudioObjectPropertyScopeGlobal,
        _kAudioObjectPropertyElementMain,
    )
    device_id = ctypes.c_uint32(0)
    size = ctypes.c_uint32(ctypes.sizeof(device_id))
    _ca.AudioObjectGetPropertyData(
        _kAudioObjectSystemObject, ctypes.byref(prop),
        0, None, ctypes.byref(size), ctypes.byref(device_id),
    )
    return device_id.value


class MacOSAudioBackend(AudioBackend):
    def get_mute(self) -> bool:
        device_id = _get_default_input_device()
        prop = _AudioObjectPropertyAddress(
            _kAudioDevicePropertyMute,
            _kAudioObjectPropertyScopeInput,
            _kAudioObjectPropertyElementMain,
        )
        mute = ctypes.c_uint32(0)
        size = ctypes.c_uint32(ctypes.sizeof(mute))
        _ca.AudioObjectGetPropertyData(
            device_id, ctypes.byref(prop),
            0, None, ctypes.byref(size), ctypes.byref(mute),
        )
        return bool(mute.value)

    def set_mute(self, muted: bool) -> None:
        device_id = _get_default_input_device()
        prop = _AudioObjectPropertyAddress(
            _kAudioDevicePropertyMute,
            _kAudioObjectPropertyScopeInput,
            _kAudioObjectPropertyElementMain,
        )
        mute = ctypes.c_uint32(int(muted))
        size = ctypes.c_uint32(ctypes.sizeof(mute))
        _ca.AudioObjectSetPropertyData(
            device_id, ctypes.byref(prop),
            0, None, size, ctypes.byref(mute),
        )
```

- [ ] **Step 2: Manual verification**

Open a Python REPL (must be on macOS with a microphone):

```python
from espmuter.audio.macos import MacOSAudioBackend
b = MacOSAudioBackend()
print(b.get_mute())    # True or False — check against System Settings → Sound → Input
b.set_mute(True)
print(b.get_mute())    # True
b.set_mute(False)
print(b.get_mute())    # False
```

Check that mic mute state changes are visible in System Settings → Sound → Input while running `set_mute`.

- [ ] **Step 3: Commit**

```bash
git add espmuter/audio/macos.py
git commit -m "feat: macOS CoreAudio backend for mic mute via ctypes"
```

---

### Task 5: Poller

**Files:**
- Create: `espmuter/poller.py`
- Create: `tests/test_poller.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_poller.py`:

```python
from espmuter.audio.backend import StubAudioBackend
from espmuter.poller import Poller


def test_first_tick_publishes_initial_state():
    backend = StubAudioBackend(initial_mute=False)
    calls = []
    Poller(backend, on_change=calls.append).tick()
    assert calls == [False]


def test_second_tick_same_state_no_call():
    backend = StubAudioBackend(initial_mute=False)
    calls = []
    poller = Poller(backend, on_change=calls.append)
    poller.tick()
    poller.tick()
    assert calls == [False]


def test_tick_fires_on_state_change():
    backend = StubAudioBackend(initial_mute=False)
    calls = []
    poller = Poller(backend, on_change=calls.append)
    poller.tick()
    backend.set_mute(True)
    poller.tick()
    assert calls == [False, True]


def test_toggle_flips_mute_state():
    backend = StubAudioBackend(initial_mute=False)
    poller = Poller(backend, on_change=lambda _: None)
    poller.toggle()
    assert backend.get_mute() is True
    poller.toggle()
    assert backend.get_mute() is False
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest tests/test_poller.py -v
```

Expected: `ModuleNotFoundError: No module named 'espmuter.poller'`

- [ ] **Step 3: Implement `poller.py`**

Create `espmuter/poller.py`:

```python
from __future__ import annotations
import threading
from typing import Callable, Optional
from espmuter.audio.backend import AudioBackend


class Poller:
    def __init__(self, backend: AudioBackend, on_change: Callable[[bool], None]):
        self._backend = backend
        self._on_change = on_change
        self._last_state: Optional[bool] = None
        self._stop = threading.Event()

    def tick(self) -> None:
        current = self._backend.get_mute()
        if current != self._last_state:
            self._last_state = current
            self._on_change(current)

    def toggle(self) -> None:
        self._backend.set_mute(not self._backend.get_mute())

    def start(self, interval: float = 0.2) -> threading.Thread:
        self._stop.clear()

        def loop() -> None:
            self.tick()
            while not self._stop.wait(interval):
                self.tick()

        thread = threading.Thread(target=loop, daemon=True, name="poller")
        thread.start()
        return thread

    def stop(self) -> None:
        self._stop.set()
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
pytest tests/test_poller.py -v
```

Expected: `4 passed`

- [ ] **Step 5: Commit**

```bash
git add espmuter/poller.py tests/test_poller.py
git commit -m "feat: polling loop with state-change callback and toggle"
```

---

### Task 6: MQTT Client

**Files:**
- Create: `espmuter/mqtt_client.py`
- Create: `tests/test_mqtt_client.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_mqtt_client.py`:

```python
import json
import pytest
from unittest.mock import MagicMock
from espmuter.config import Config
from espmuter.mqtt_client import MQTTClient


@pytest.fixture
def mock_paho(mocker):
    return mocker.patch("espmuter.mqtt_client.mqtt.Client")


@pytest.fixture
def config():
    return Config(
        mqtt_host="localhost",
        mqtt_port=1883,
        mqtt_username="user",
        mqtt_password="pass",
        color_muted={"r": 0, "g": 255, "b": 0},
        color_unmuted={"r": 255, "g": 0, "b": 0},
        led_brightness=128,
    )


def test_publish_muted_sends_retained_state(mock_paho, config):
    client = MQTTClient(config, MagicMock())
    client.publish_state(muted=True)
    calls = {c[0][0]: c for c in mock_paho.return_value.publish.call_args_list}
    assert calls["espmuter/state"][0][1] == "muted"
    assert calls["espmuter/state"][1]["retain"] is True


def test_publish_unmuted_sends_correct_state(mock_paho, config):
    client = MQTTClient(config, MagicMock())
    client.publish_state(muted=False)
    calls = {c[0][0]: c for c in mock_paho.return_value.publish.call_args_list}
    assert calls["espmuter/state"][0][1] == "unmuted"


def test_publish_muted_sends_retained_green_led(mock_paho, config):
    client = MQTTClient(config, MagicMock())
    client.publish_state(muted=True)
    calls = {c[0][0]: c for c in mock_paho.return_value.publish.call_args_list}
    payload = json.loads(calls["espmuter/led/set"][0][1])
    assert payload == {"r": 0, "g": 255, "b": 0, "brightness": 128}
    assert calls["espmuter/led/set"][1]["retain"] is True


def test_publish_unmuted_sends_retained_red_led(mock_paho, config):
    client = MQTTClient(config, MagicMock())
    client.publish_state(muted=False)
    calls = {c[0][0]: c for c in mock_paho.return_value.publish.call_args_list}
    payload = json.loads(calls["espmuter/led/set"][0][1])
    assert payload == {"r": 255, "g": 0, "b": 0, "brightness": 128}


def test_button_message_calls_callback(mock_paho, config):
    on_button = MagicMock()
    client = MQTTClient(config, on_button)
    msg = MagicMock()
    msg.topic = "espmuter/button"
    msg.payload = b"pressed"
    client._on_message(None, None, msg)
    on_button.assert_called_once()


def test_unrelated_topic_ignored(mock_paho, config):
    on_button = MagicMock()
    client = MQTTClient(config, on_button)
    msg = MagicMock()
    msg.topic = "other/topic"
    msg.payload = b"pressed"
    client._on_message(None, None, msg)
    on_button.assert_not_called()
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest tests/test_mqtt_client.py -v
```

Expected: `ModuleNotFoundError: No module named 'espmuter.mqtt_client'`

- [ ] **Step 3: Implement `mqtt_client.py`**

Create `espmuter/mqtt_client.py`:

```python
from __future__ import annotations
import json
from typing import Callable
import paho.mqtt.client as mqtt
from espmuter.config import Config


class MQTTClient:
    def __init__(self, config: Config, on_button_press: Callable[[], None]):
        self._config = config
        self._on_button_press = on_button_press
        self._client = mqtt.Client(client_id="espmuter", clean_session=True)
        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message
        if config.mqtt_username:
            self._client.username_pw_set(config.mqtt_username, config.mqtt_password)

    def start(self) -> None:
        self._client.connect_async(
            self._config.mqtt_host, self._config.mqtt_port, keepalive=60
        )
        self._client.loop_start()

    def stop(self) -> None:
        self._client.loop_stop()
        self._client.disconnect()

    def publish_state(self, muted: bool) -> None:
        self._client.publish(
            "espmuter/state", "muted" if muted else "unmuted", retain=True
        )
        color = self._config.color_muted if muted else self._config.color_unmuted
        self._client.publish(
            "espmuter/led/set",
            json.dumps({"r": color["r"], "g": color["g"], "b": color["b"],
                        "brightness": self._config.led_brightness}),
            retain=True,
        )

    def _on_connect(self, client, userdata, flags, rc) -> None:
        if rc == 0:
            client.subscribe("espmuter/button")
            self._publish_autodiscovery()

    def _on_message(self, client, userdata, message) -> None:
        if message.topic == "espmuter/button" and message.payload == b"pressed":
            self._on_button_press()

    def _publish_autodiscovery(self) -> None:
        self._client.publish(
            "homeassistant/binary_sensor/espmuter/state/config",
            json.dumps({
                "name": "Microphone",
                "device_class": "sound",
                "state_topic": "espmuter/state",
                "payload_on": "muted",
                "payload_off": "unmuted",
                "unique_id": "espmuter_microphone_state",
                "device": {"identifiers": ["espmuter"], "name": "ESPMuter"},
            }),
            retain=True,
        )
        self._client.publish(
            "homeassistant/device_automation/espmuter/button/config",
            json.dumps({
                "automation_type": "trigger",
                "type": "action",
                "subtype": "button_1_press",
                "topic": "espmuter/button",
                "payload": "pressed",
                "device": {"identifiers": ["espmuter"], "name": "ESPMuter"},
            }),
            retain=True,
        )
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
pytest tests/test_mqtt_client.py -v
```

Expected: `6 passed`

- [ ] **Step 5: Commit**

```bash
git add espmuter/mqtt_client.py tests/test_mqtt_client.py
git commit -m "feat: MQTT client with state publishing and HA autodiscovery"
```

---

### Task 7: Hotkey Listener

**Files:**
- Create: `espmuter/hotkey.py`
- Create: `tests/test_hotkey.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_hotkey.py`:

```python
from espmuter.hotkey import to_pynput_format, HotkeyListener


def test_modifiers_wrapped_in_angle_brackets():
    assert to_pynput_format("ctrl+shift+m") == "<ctrl>+<shift>+m"


def test_single_modifier():
    assert to_pynput_format("ctrl+m") == "<ctrl>+m"


def test_multiple_modifiers():
    assert to_pynput_format("alt+shift+f4") == "<alt>+<shift>+f4"


def test_plain_key_unchanged():
    assert to_pynput_format("f12") == "f12"


def test_listener_registers_correct_hotkey(mocker):
    mock_cls = mocker.patch("espmuter.hotkey.keyboard.GlobalHotKeys")
    callback = mocker.Mock()
    listener = HotkeyListener("ctrl+shift+m", callback)
    listener.start()
    mock_cls.assert_called_once_with({"<ctrl>+<shift>+m": callback})
    mock_cls.return_value.start.assert_called_once()


def test_listener_stop_delegates(mocker):
    mock_cls = mocker.patch("espmuter.hotkey.keyboard.GlobalHotKeys")
    listener = HotkeyListener("ctrl+m", mocker.Mock())
    listener.start()
    listener.stop()
    mock_cls.return_value.stop.assert_called_once()
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest tests/test_hotkey.py -v
```

Expected: `ModuleNotFoundError: No module named 'espmuter.hotkey'`

- [ ] **Step 3: Implement `hotkey.py`**

Create `espmuter/hotkey.py`:

```python
from __future__ import annotations
from typing import Callable
from pynput import keyboard

_MODIFIERS = {"ctrl", "shift", "alt", "cmd", "super"}


def to_pynput_format(hotkey: str) -> str:
    return "+".join(
        f"<{p.lower()}>" if p.lower() in _MODIFIERS else p.lower()
        for p in hotkey.split("+")
    )


class HotkeyListener:
    def __init__(self, hotkey: str, callback: Callable[[], None]):
        self._hotkey = to_pynput_format(hotkey)
        self._callback = callback
        self._listener: keyboard.GlobalHotKeys | None = None

    def start(self) -> None:
        self._listener = keyboard.GlobalHotKeys({self._hotkey: self._callback})
        self._listener.start()

    def stop(self) -> None:
        if self._listener:
            self._listener.stop()
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
pytest tests/test_hotkey.py -v
```

Expected: `6 passed`

- [ ] **Step 5: Commit**

```bash
git add espmuter/hotkey.py tests/test_hotkey.py
git commit -m "feat: global hotkey listener with pynput format conversion"
```

---

### Task 8: Autostart

**Files:**
- Create: `espmuter/autostart.py`
- Create: `tests/test_autostart.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_autostart.py`:

```python
import plistlib
import pytest
from espmuter.autostart import enable_autostart, disable_autostart


def test_enable_creates_plist_file(tmp_path, mocker):
    plist_path = tmp_path / "com.espmuter.agent.plist"
    mocker.patch("espmuter.autostart.PLIST_PATH", plist_path)
    mocker.patch("espmuter.autostart.subprocess.run")
    enable_autostart("/usr/bin/python3 /path/to/main.py")
    assert plist_path.exists()


def test_plist_label(tmp_path, mocker):
    plist_path = tmp_path / "com.espmuter.agent.plist"
    mocker.patch("espmuter.autostart.PLIST_PATH", plist_path)
    mocker.patch("espmuter.autostart.subprocess.run")
    enable_autostart("/usr/bin/python3 /path/to/main.py")
    data = plistlib.loads(plist_path.read_bytes())
    assert data["Label"] == "com.espmuter.agent"


def test_plist_run_at_load(tmp_path, mocker):
    plist_path = tmp_path / "com.espmuter.agent.plist"
    mocker.patch("espmuter.autostart.PLIST_PATH", plist_path)
    mocker.patch("espmuter.autostart.subprocess.run")
    enable_autostart("/usr/bin/python3 /path/to/main.py")
    data = plistlib.loads(plist_path.read_bytes())
    assert data["RunAtLoad"] is True


def test_plist_program_arguments(tmp_path, mocker):
    plist_path = tmp_path / "com.espmuter.agent.plist"
    mocker.patch("espmuter.autostart.PLIST_PATH", plist_path)
    mocker.patch("espmuter.autostart.subprocess.run")
    enable_autostart("/usr/bin/python3 /path/to/main.py")
    data = plistlib.loads(plist_path.read_bytes())
    assert data["ProgramArguments"] == ["/usr/bin/python3", "/path/to/main.py"]


def test_disable_removes_plist(tmp_path, mocker):
    plist_path = tmp_path / "com.espmuter.agent.plist"
    plist_path.write_bytes(b"content")
    mocker.patch("espmuter.autostart.PLIST_PATH", plist_path)
    mocker.patch("espmuter.autostart.subprocess.run")
    disable_autostart()
    assert not plist_path.exists()


def test_disable_noop_when_plist_missing(tmp_path, mocker):
    plist_path = tmp_path / "com.espmuter.agent.plist"
    mocker.patch("espmuter.autostart.PLIST_PATH", plist_path)
    mocker.patch("espmuter.autostart.subprocess.run")
    disable_autostart()  # must not raise
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
pytest tests/test_autostart.py -v
```

Expected: `ModuleNotFoundError: No module named 'espmuter.autostart'`

- [ ] **Step 3: Implement `autostart.py`**

Create `espmuter/autostart.py`:

```python
from __future__ import annotations
import plistlib
import subprocess
from pathlib import Path

PLIST_PATH = Path.home() / "Library" / "LaunchAgents" / "com.espmuter.agent.plist"


def enable_autostart(command: str) -> None:
    plist = {
        "Label": "com.espmuter.agent",
        "ProgramArguments": command.split(),
        "RunAtLoad": True,
        "KeepAlive": True,
    }
    PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    PLIST_PATH.write_bytes(plistlib.dumps(plist))
    subprocess.run(["launchctl", "load", str(PLIST_PATH)], check=False)


def disable_autostart() -> None:
    if PLIST_PATH.exists():
        subprocess.run(["launchctl", "unload", str(PLIST_PATH)], check=False)
        PLIST_PATH.unlink()
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
pytest tests/test_autostart.py -v
```

Expected: `6 passed`

- [ ] **Step 5: Confirm full test suite still green**

```bash
pytest -v
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add espmuter/autostart.py tests/test_autostart.py
git commit -m "feat: macOS launchd autostart enable/disable"
```

---

### Task 9: Tray Icon

**Files:**
- Create: `espmuter/tray.py`

No unit tests — pystray requires a display server. Verified manually.

- [ ] **Step 1: Implement `tray.py`**

Create `espmuter/tray.py`:

```python
from __future__ import annotations
import sys
from typing import Callable
import pystray
from PIL import Image, ImageDraw


def _make_icon(color: tuple[int, int, int]) -> Image.Image:
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([4, 4, 60, 60], fill=(*color, 255))
    return img


def _hide_dock_icon() -> None:
    try:
        import AppKit
        AppKit.NSApp.setActivationPolicy_(
            AppKit.NSApplicationActivationPolicyAccessory
        )
    except Exception:
        pass


class TrayIcon:
    def __init__(
        self,
        on_toggle: Callable[[], None],
        on_settings: Callable[[], None],
        on_quit: Callable[[], None],
    ):
        self._on_toggle = on_toggle
        self._on_settings = on_settings
        self._on_quit = on_quit
        self._icon = pystray.Icon(
            "espmuter",
            _make_icon((128, 128, 128)),
            menu=pystray.Menu(
                pystray.MenuItem("Toggle Mute", self._toggle, default=True),
                pystray.MenuItem("Settings", self._settings),
                pystray.MenuItem("Quit", self._quit),
            ),
        )

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

    def _quit(self, icon, item) -> None:
        self.stop()
        self._on_quit()
```

- [ ] **Step 2: Manual verification**

Create a temporary test script `_test_tray.py` in the project root:

```python
import threading
from espmuter.tray import TrayIcon

tray = TrayIcon(
    on_toggle=lambda: print("toggle"),
    on_settings=lambda: print("settings"),
    on_quit=lambda: __import__("os")._exit(0),
)
threading.Timer(3, lambda: tray.set_muted(True)).start()
threading.Timer(6, lambda: tray.set_muted(False)).start()
tray.run()
```

```bash
python _test_tray.py
```

Verify:
- Menu bar icon appears as a grey circle
- After 3 seconds it turns green
- After 6 seconds it turns red
- Left-click prints "toggle"
- Right-click shows: Toggle Mute, Settings, Quit
- No dock icon appears

Delete `_test_tray.py` after verification.

- [ ] **Step 3: Commit**

```bash
git add espmuter/tray.py
git commit -m "feat: pystray menu bar icon with mute state indicator"
```

---

### Task 10: Settings Window

**Files:**
- Create: `espmuter/settings_window.py`

Runs as a subprocess (`python -m espmuter.settings_window <config_path>`) to avoid macOS main-thread conflicts between pystray and tkinter. No unit tests — verified manually.

- [ ] **Step 1: Implement `settings_window.py`**

Create `espmuter/settings_window.py`:

```python
"""Run as: python -m espmuter.settings_window [config_path]"""
from __future__ import annotations
import shutil
import sys
import tkinter as tk
from tkinter import ttk
from pathlib import Path
from espmuter.config import Config, DEFAULT_CONFIG_PATH


def _hex(color: dict) -> str:
    return "#{r:02x}{g:02x}{b:02x}".format(**color)


def _from_hex(h: str) -> dict:
    h = h.lstrip("#")
    return {"r": int(h[0:2], 16), "g": int(h[2:4], 16), "b": int(h[4:6], 16)}


def run(config_path: Path) -> None:
    config = Config.load(config_path)
    root = tk.Tk()
    root.title("ESPMuter Settings")
    root.resizable(False, False)

    f = ttk.Frame(root, padding=16)
    f.grid(sticky="nsew")

    def add_row(label: str, var: tk.Variable, r: int, **kw) -> None:
        ttk.Label(f, text=label).grid(row=r, column=0, sticky="w", pady=4)
        ttk.Entry(f, textvariable=var, **kw).grid(row=r, column=1, sticky="ew", padx=(8, 0))

    mqtt_host = tk.StringVar(value=config.mqtt_host)
    mqtt_port = tk.IntVar(value=config.mqtt_port)
    mqtt_user = tk.StringVar(value=config.mqtt_username)
    mqtt_pass = tk.StringVar(value=config.mqtt_password)
    hotkey = tk.StringVar(value=config.hotkey)
    brightness = tk.IntVar(value=config.led_brightness)
    color_muted = tk.StringVar(value=_hex(config.color_muted))
    color_unmuted = tk.StringVar(value=_hex(config.color_unmuted))
    autostart = tk.BooleanVar(value=config.autostart)

    add_row("MQTT Host", mqtt_host, 0)
    add_row("MQTT Port", mqtt_port, 1, width=8)
    add_row("MQTT Username", mqtt_user, 2)
    add_row("MQTT Password", mqtt_pass, 3, show="*")
    add_row("Hotkey", hotkey, 4)
    add_row("LED Brightness (0-255)", brightness, 5, width=8)
    add_row("Color Muted (hex)", color_muted, 6)
    add_row("Color Unmuted (hex)", color_unmuted, 7)

    ttk.Label(f, text="Autostart on login").grid(row=8, column=0, sticky="w", pady=4)
    ttk.Checkbutton(f, variable=autostart).grid(row=8, column=1, sticky="w", padx=(8, 0))

    def save() -> None:
        from espmuter.autostart import enable_autostart, disable_autostart
        new = Config(
            mqtt_host=mqtt_host.get(),
            mqtt_port=mqtt_port.get(),
            mqtt_username=mqtt_user.get(),
            mqtt_password=mqtt_pass.get(),
            hotkey=hotkey.get(),
            led_brightness=brightness.get(),
            color_muted=_from_hex(color_muted.get()),
            color_unmuted=_from_hex(color_unmuted.get()),
            autostart=autostart.get(),
        )
        new.save(config_path)
        if new.autostart:
            python = shutil.which("python3") or sys.executable
            enable_autostart(f"{python} -m espmuter.main")
        else:
            disable_autostart()
        root.destroy()

    ttk.Button(f, text="Save", command=save).grid(
        row=9, column=0, columnspan=2, pady=(16, 0)
    )
    f.columnconfigure(1, weight=1)
    root.mainloop()


if __name__ == "__main__":
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_CONFIG_PATH
    run(path)
```

- [ ] **Step 2: Manual verification**

```bash
python -m espmuter.settings_window
```

Verify:
- Window opens with all fields pre-populated from `~/.config/espmuter/config.json` (or defaults on first run)
- Password field obscures characters
- Changing MQTT Host and clicking Save writes the change to `~/.config/espmuter/config.json`
- Toggling Autostart and saving creates/removes `~/Library/LaunchAgents/com.espmuter.agent.plist`

- [ ] **Step 3: Commit**

```bash
git add espmuter/settings_window.py
git commit -m "feat: tkinter settings window as subprocess"
```

---

### Task 11: Main Wiring

**Files:**
- Create: `espmuter/main.py`

- [ ] **Step 1: Implement `main.py`**

Create `espmuter/main.py`:

```python
from __future__ import annotations
import subprocess
import sys
from pathlib import Path

from espmuter.audio.backend import get_backend
from espmuter.config import Config, DEFAULT_CONFIG_PATH
from espmuter.hotkey import HotkeyListener
from espmuter.mqtt_client import MQTTClient
from espmuter.poller import Poller
from espmuter.tray import TrayIcon


def main() -> None:
    config = Config.load(DEFAULT_CONFIG_PATH)
    backend = get_backend()

    # All callbacks use late-binding closures — poller/mqtt/tray are all
    # assigned before any callback can fire (mqtt.start() comes later).
    def on_toggle() -> None:
        poller.toggle()

    def on_state_change(muted: bool) -> None:
        mqtt.publish_state(muted)
        tray.set_muted(muted)

    def on_quit() -> None:
        hotkey_listener.stop()
        poller.stop()
        mqtt.stop()
        sys.exit(0)

    poller = Poller(backend, on_change=on_state_change)
    mqtt = MQTTClient(config, on_button_press=on_toggle)
    tray = TrayIcon(
        on_toggle=on_toggle,
        on_settings=lambda: subprocess.Popen(
            [sys.executable, "-m", "espmuter.settings_window", str(DEFAULT_CONFIG_PATH)]
        ),
        on_quit=on_quit,
    )
    hotkey_listener = HotkeyListener(config.hotkey, callback=on_toggle)

    mqtt.start()
    poller.start()
    hotkey_listener.start()
    tray.run()  # blocks main thread until quit


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Run full test suite**

```bash
pytest -v
```

Expected: all tests pass.

- [ ] **Step 3: Manual end-to-end verification**

Prerequisites: Mosquitto running and reachable; settings configured with correct MQTT host.

```bash
# Configure MQTT (first run)
python -m espmuter.settings_window

# In a second terminal — watch MQTT traffic
mosquitto_sub -h <NAS_IP> -u <user> -P <pass> -t 'espmuter/#' -v

# Run the app
python -m espmuter.main
```

Verify in order:
1. Menu bar icon appears (grey → red or green within 200ms)
2. `espmuter/state` and `espmuter/led/set` messages appear on MQTT subscriber
3. Left-click icon → mic toggles, icon colour changes, new MQTT messages appear
4. Hotkey (`ctrl+shift+m`) → same effect as left-click
5. Right-click → Settings opens a separate window; Quit exits cleanly

Note: settings changes take effect after restarting the app.

- [ ] **Step 4: Commit**

```bash
git add espmuter/main.py
git commit -m "feat: main entry point wiring all components"
```

---

### Task 12: ESPHome Configuration

**Files:**
- Create: `esphome/secrets.yaml.example`
- Create: `esphome/espmuter.yaml`

No Python tests — ESPHome validates config at compile time via `esphome compile`.

- [ ] **Step 1: Create `esphome/secrets.yaml.example`**

```yaml
mqtt_host: "192.168.1.x"
mqtt_port: "1883"
mqtt_username: "espmuter"
mqtt_password: "yourpassword"
wifi_ssid: "YourNetwork"
wifi_password: "YourWifiPassword"
```

- [ ] **Step 2: Create `esphome/espmuter.yaml`**

```yaml
# Board substitutions — change these three lines to switch boards.
#
#   Board                 board_name                    led_pin   button_pin
#   ESP32 DevKit V1       esp32dev                      GPIO5     GPIO14
#   ESP32-S3 DevKit       esp32-s3-devkitc-1            GPIO5     GPIO4
#   XIAO ESP32C3          seeed_xiao_esp32c3            GPIO2     GPIO3
#   ESP32-C3 SuperMini    esp32-c3-devkitm-1            GPIO8     GPIO9
substitutions:
  board_name: esp32dev
  led_pin: GPIO5
  button_pin: GPIO14

esphome:
  name: espmuter

esp32:
  board: ${board_name}
  framework:
    type: arduino

wifi:
  ssid: !secret wifi_ssid
  password: !secret wifi_password
  ap:
    ssid: "ESPMuter Fallback"
    password: "espmuter123"

captive_portal:

logger:

ota:
  platform: esphome

mqtt:
  broker: !secret mqtt_host
  port: !secret mqtt_port
  username: !secret mqtt_username
  password: !secret mqtt_password
  on_message:
    - topic: espmuter/led/set
      then:
        - lambda: |-
            StaticJsonDocument<128> doc;
            deserializeJson(doc, x.c_str());
            auto call = id(led_ring).make_call();
            call.set_state(true);
            call.set_rgb(
              doc["r"].as<int>() / 255.0f,
              doc["g"].as<int>() / 255.0f,
              doc["b"].as<int>() / 255.0f
            );
            call.set_brightness(doc["brightness"].as<int>() / 255.0f);
            call.perform();

light:
  - platform: neopixelbus
    type: GRB
    variant: WS2812X
    pin: ${led_pin}
    num_leds: 12
    name: "ESPMuter Ring"
    id: led_ring
    default_transition_length: 100ms

binary_sensor:
  - platform: gpio
    pin:
      number: ${button_pin}
      mode: INPUT_PULLUP
      inverted: true
    name: "ESPMuter Button"
    filters:
      - delayed_on: 20ms
    on_press:
      - mqtt.publish:
          topic: espmuter/button
          payload: "pressed"
```

- [ ] **Step 3: Validate ESPHome config compiles**

```bash
cd esphome
cp secrets.yaml.example secrets.yaml
# Edit secrets.yaml with real values
esphome compile espmuter.yaml
```

Expected: `INFO Successfully compiled program.`

- [ ] **Step 4: Flash and verify hardware**

Connect your ESP32 via USB, then:

```bash
esphome run espmuter.yaml
```

With both the Python app and ESP32 running, verify:

1. LED ring lights up with the correct color for the current mic mute state (green = muted, red = unmuted) within ~300ms of app start
2. Press hardware button → mic toggles and LED changes color
3. Toggle via tray left-click → LED updates within ~300ms
4. In HA → Developer Tools → MQTT: subscribe to `espmuter/#` — confirm `espmuter/state` sensor and button automation appear under Devices automatically

- [ ] **Step 5: Commit**

```bash
git add esphome/espmuter.yaml esphome/secrets.yaml.example
git commit -m "feat: ESPHome firmware config with multi-board support"
```
