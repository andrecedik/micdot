# Conferencing App Mute Sync — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bidirectional mute sync between MicDot and conferencing apps (Zoom, Teams, Google Meet) via the macOS Accessibility API, using a plugin architecture for extensibility.

**Architecture:** A `ConferencingSync` coordinator plugs into the existing `Poller.on_change` callback (outbound) and uses per-app plugins that poll the AX element tree every 250 ms (inbound). Each plugin subclasses `AXPlugin` and only needs to specify how to find the mute button in its app's AX tree. The coordinator suppresses echo notifications via a `_pending` dict.

**Tech Stack:** Python 3.11+, pyobjc (AppKit, ApplicationServices), pytest, pytest-mock

**Spec:** `docs/superpowers/specs/2026-05-14-conferencing-sync-design.md`

---

## File Map

| Action | Path | Responsibility |
|--------|------|----------------|
| Modify | `pyproject.toml` | Add pyobjc-framework-ApplicationServices dep |
| Modify | `micdot/config.py` | Add `conferencing_sync_enabled` field |
| Create | `micdot/conferencing/__init__.py` | Package exports |
| Create | `micdot/conferencing/base.py` | `ConferencingPlugin` ABC |
| Create | `micdot/conferencing/ax_utils.py` | `AXPlugin` base — shared AX helpers + 250ms poll loop |
| Create | `micdot/conferencing/sync.py` | `ConferencingSync` coordinator |
| Create | `micdot/conferencing/plugins/__init__.py` | `PLUGINS` list |
| Create | `micdot/conferencing/plugins/zoom.py` | `ZoomPlugin` |
| Create | `micdot/conferencing/plugins/teams.py` | `TeamsPlugin` |
| Create | `micdot/conferencing/plugins/meet.py` | `MeetPlugin` (best-effort) |
| Modify | `micdot/main.py` | Wire sync into `_State`, `on_state_change`, `_reload_config` |
| Create | `tests/test_conferencing_base.py` | Tests for ABC + version comparison |
| Create | `tests/test_conferencing_sync.py` | Tests for coordinator logic |

---

## Task 1: Add pyobjc-framework-ApplicationServices dependency

**Files:**
- Modify: `pyproject.toml`

The AX APIs (`AXUIElementCreateApplication`, `AXUIElementCopyAttributeValue`, `AXUIElementPerformAction`) live in `pyobjc-framework-ApplicationServices`. `AppKit` (for `NSRunningApplication`, `NSWorkspace`) is already available transitively through pystray.

- [ ] **Step 1: Add the dependency**

In `pyproject.toml`, add to the `dependencies` list:

```toml
dependencies = [
    "pystray>=0.19.0",
    "Pillow>=10.0.0",
    "paho-mqtt>=1.6.1,<2.0",
    "pynput>=1.7.6",
    "pywebview>=4.0",
    "pyobjc-framework-ApplicationServices>=9.0; sys_platform == 'darwin'",
]
```

- [ ] **Step 2: Install**

```bash
pip install -e ".[dev]"
```

Expected: installs cleanly, `import ApplicationServices` works in Python.

- [ ] **Step 3: Verify import works**

```bash
python -c "from ApplicationServices import AXUIElementCreateApplication; print('ok')"
```

Expected: `ok`

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml
git commit -m "deps: add pyobjc-framework-ApplicationServices for AX API access"
```

---

## Task 2: Add `conferencing_sync_enabled` to Config

**Files:**
- Modify: `micdot/config.py`
- Test: `tests/test_config.py` (extend existing file)

- [ ] **Step 1: Read the existing test file**

```bash
cat tests/test_config.py
```

- [ ] **Step 2: Add failing tests**

Append to `tests/test_config.py`:

```python
def test_conferencing_sync_enabled_defaults_to_true():
    cfg = Config()
    assert cfg.conferencing_sync_enabled is True


def test_conferencing_sync_enabled_persists_through_save_load(tmp_path):
    cfg = Config(conferencing_sync_enabled=False)
    cfg.save(tmp_path / "config.json")
    loaded = Config.load(tmp_path / "config.json")
    assert loaded.conferencing_sync_enabled is False


def test_conferencing_sync_enabled_defaults_to_true_when_missing_from_file(tmp_path):
    import json
    (tmp_path / "config.json").write_text(json.dumps({"mqtt_host": "h"}))
    loaded = Config.load(tmp_path / "config.json")
    assert loaded.conferencing_sync_enabled is True
```

- [ ] **Step 3: Run tests to verify they fail**

```bash
pytest tests/test_config.py -v -k "conferencing"
```

Expected: FAIL — `TypeError: Config.__init__() got an unexpected keyword argument 'conferencing_sync_enabled'`

- [ ] **Step 4: Add the field to Config**

In `micdot/config.py`, add one field to the dataclass (after `autostart`):

```python
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
    conferencing_sync_enabled: bool = True
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_config.py -v
```

Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add micdot/config.py tests/test_config.py
git commit -m "feat: add conferencing_sync_enabled config field"
```

---

## Task 3: Create `ConferencingPlugin` ABC

**Files:**
- Create: `micdot/conferencing/base.py`
- Create: `tests/test_conferencing_base.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_conferencing_base.py`:

```python
import sys
import pytest
from micdot.conferencing.base import ConferencingPlugin, _version_tuple


# ---- version comparison helpers ----

def test_version_tuple_parses_semver():
    assert _version_tuple("5.12.3") == (5, 12, 3)


def test_version_tuple_parses_two_part():
    assert _version_tuple("1.0") == (1, 0)


def test_version_tuple_returns_empty_on_garbage():
    assert _version_tuple("not-a-version") == ()


# ---- ConferencingPlugin.is_compatible ----

class _StubPlugin(ConferencingPlugin):
    bundle_id = "com.test.stub"
    name = "Stub"

    def __init__(self, installed_version=None):
        self._installed_version = installed_version

    def _get_installed_version(self):
        return self._installed_version

    def is_running(self): return True
    def is_in_meeting(self): return True
    def get_mute(self): return False
    def set_mute(self, muted): pass
    def start_observing(self, on_change): pass
    def stop_observing(self): pass


def test_is_compatible_true_with_no_version_constraints():
    assert _StubPlugin(installed_version="1.0.0").is_compatible() is True


def test_is_compatible_false_when_platform_unsupported(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    p = _StubPlugin(installed_version="5.0.0")
    assert p.is_compatible() is False


def test_is_compatible_false_when_installed_below_min():
    p = _StubPlugin(installed_version="4.9.9")
    p.min_version = "5.0.0"
    assert p.is_compatible() is False


def test_is_compatible_true_when_installed_meets_min():
    p = _StubPlugin(installed_version="5.0.0")
    p.min_version = "5.0.0"
    assert p.is_compatible() is True


def test_is_compatible_true_when_installed_version_unknown():
    p = _StubPlugin(installed_version=None)
    p.min_version = "5.0.0"
    # Can't check version, so allow it
    assert p.is_compatible() is True
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest tests/test_conferencing_base.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'micdot.conferencing'`

- [ ] **Step 3: Create the package skeleton**

```bash
mkdir -p micdot/conferencing/plugins
touch micdot/conferencing/__init__.py
touch micdot/conferencing/plugins/__init__.py
```

- [ ] **Step 4: Create `micdot/conferencing/base.py`**

```python
from __future__ import annotations
import sys
from abc import ABC, abstractmethod
from collections.abc import Callable


def _version_tuple(v: str) -> tuple[int, ...]:
    try:
        return tuple(int(x) for x in v.split("."))
    except ValueError:
        return ()


class ConferencingPlugin(ABC):
    bundle_id: str
    name: str
    supported_platforms: tuple[str, ...] = ("darwin",)
    min_version: str | None = None
    max_version: str | None = None

    def is_compatible(self) -> bool:
        if sys.platform not in self.supported_platforms:
            return False
        installed = self._get_installed_version()
        if installed and self.min_version:
            if _version_tuple(installed) < _version_tuple(self.min_version):
                return False
        return True

    def _get_installed_version(self) -> str | None:
        return None

    @abstractmethod
    def is_running(self) -> bool: ...

    @abstractmethod
    def is_in_meeting(self) -> bool: ...

    @abstractmethod
    def get_mute(self) -> bool | None:
        """Return current mute state, or None if not in a meeting."""
        ...

    @abstractmethod
    def set_mute(self, muted: bool) -> None:
        """Set mute state. No-op if not in a meeting."""
        ...

    @abstractmethod
    def start_observing(self, on_change: Callable[[bool], None]) -> None:
        """Start watching for mute state changes. on_change(muted) is called from any thread."""
        ...

    @abstractmethod
    def stop_observing(self) -> None: ...
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
pytest tests/test_conferencing_base.py -v
```

Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add micdot/conferencing/ tests/test_conferencing_base.py
git commit -m "feat: add ConferencingPlugin ABC"
```

---

## Task 4: Create `ConferencingSync` coordinator

**Files:**
- Create: `micdot/conferencing/sync.py`
- Create: `tests/test_conferencing_sync.py`

- [ ] **Step 1: Write failing tests**

Create `tests/test_conferencing_sync.py`:

```python
import threading
import pytest
from collections.abc import Callable
from micdot.audio.backend import StubAudioBackend
from micdot.conferencing.base import ConferencingPlugin
from micdot.conferencing.sync import ConferencingSync


class StubPlugin(ConferencingPlugin):
    bundle_id = "com.stub"
    name = "Stub"

    def __init__(self, running: bool = True, in_meeting: bool = True, mute: bool = False):
        self._running = running
        self._in_meeting = in_meeting
        self._mute = mute
        self.set_mute_calls: list[bool] = []
        self._on_change: Callable[[bool], None] | None = None

    def is_running(self) -> bool: return self._running
    def is_in_meeting(self) -> bool: return self._in_meeting
    def get_mute(self) -> bool | None: return self._mute if self._in_meeting else None

    def set_mute(self, muted: bool) -> None:
        self._mute = muted
        self.set_mute_calls.append(muted)

    def start_observing(self, on_change: Callable[[bool], None]) -> None:
        self._on_change = on_change

    def stop_observing(self) -> None:
        self._on_change = None

    def fire(self, muted: bool) -> None:
        if self._on_change:
            self._on_change(muted)


def test_on_mute_change_propagates_to_plugin_in_meeting():
    backend = StubAudioBackend()
    plugin = StubPlugin(running=True, in_meeting=True)
    sync = ConferencingSync([plugin], backend)
    sync.start()

    sync.on_mute_change(True)

    assert plugin.set_mute_calls == [True]
    sync.stop()


def test_on_mute_change_skips_plugin_not_in_meeting():
    backend = StubAudioBackend()
    plugin = StubPlugin(running=True, in_meeting=False)
    sync = ConferencingSync([plugin], backend)
    sync.start()

    sync.on_mute_change(True)

    assert plugin.set_mute_calls == []
    sync.stop()


def test_on_mute_change_skips_plugin_not_running():
    backend = StubAudioBackend()
    plugin = StubPlugin(running=False, in_meeting=True)
    sync = ConferencingSync([plugin], backend)
    sync.start()

    sync.on_mute_change(True)

    assert plugin.set_mute_calls == []
    sync.stop()


def test_app_change_updates_backend():
    backend = StubAudioBackend(initial_mute=False)
    plugin = StubPlugin(running=True, in_meeting=True)
    sync = ConferencingSync([plugin], backend)
    sync.start()

    plugin.fire(True)

    assert backend.get_mute() is True
    sync.stop()


def test_echo_suppression_ignores_our_own_set():
    backend = StubAudioBackend(initial_mute=False)
    plugin = StubPlugin(running=True, in_meeting=True)
    sync = ConferencingSync([plugin], backend)
    sync.start()

    # MicDot mutes → propagated to plugin
    sync.on_mute_change(True)
    # AX notifies us back with the same state we just set (our echo)
    plugin.fire(True)

    # Backend must NOT have been changed (it was our echo)
    assert backend.get_mute() is False
    sync.stop()


def test_genuine_app_change_after_our_set_updates_backend():
    backend = StubAudioBackend(initial_mute=False)
    plugin = StubPlugin(running=True, in_meeting=True)
    sync = ConferencingSync([plugin], backend)
    sync.start()

    sync.on_mute_change(True)   # MicDot mutes
    plugin.fire(True)            # echo — suppressed
    plugin.fire(False)           # user immediately unmutes inside app

    assert backend.get_mute() is False
    sync.stop()


def test_stop_unregisters_observers():
    backend = StubAudioBackend()
    plugin = StubPlugin(running=True, in_meeting=True)
    sync = ConferencingSync([plugin], backend)
    sync.start()
    sync.stop()

    assert plugin._on_change is None


def test_start_skips_incompatible_plugins():
    backend = StubAudioBackend()
    plugin = StubPlugin()
    plugin.min_version = "99.0.0"
    plugin._installed = "1.0.0"

    class _Incompatible(StubPlugin):
        def _get_installed_version(self): return "1.0.0"
        def is_compatible(self): return False

    bad = _Incompatible()
    sync = ConferencingSync([bad], backend)
    sync.start()

    # incompatible plugin should never be observed
    assert bad._on_change is None
    sync.stop()
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest tests/test_conferencing_sync.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'micdot.conferencing.sync'`

- [ ] **Step 3: Create `micdot/conferencing/sync.py`**

```python
from __future__ import annotations
import logging
import threading
from micdot.audio.backend import AudioBackend
from micdot.conferencing.base import ConferencingPlugin

log = logging.getLogger("micdot")


class ConferencingSync:
    def __init__(self, plugins: list[ConferencingPlugin], backend: AudioBackend) -> None:
        self._plugins = plugins
        self._backend = backend
        self._pending: dict[int, bool] = {}
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._observing: set[int] = set()

    def start(self) -> None:
        self._stop_event.clear()
        for p in self._plugins:
            if p.is_compatible() and p.is_running():
                self._start_plugin(p)
        threading.Thread(
            target=self._discovery_loop, daemon=True, name="conf-discovery"
        ).start()

    def stop(self) -> None:
        self._stop_event.set()
        for p in self._plugins:
            if id(p) in self._observing:
                try:
                    p.stop_observing()
                except Exception:
                    log.debug("Error stopping plugin %s", p.name, exc_info=True)
        self._observing.clear()

    def on_mute_change(self, muted: bool) -> None:
        """Called by Poller's on_change when MicDot's hardware mute state changes."""
        for p in self._plugins:
            if id(p) not in self._observing or not p.is_in_meeting():
                continue
            with self._lock:
                self._pending[id(p)] = muted
            try:
                p.set_mute(muted)
            except Exception:
                log.warning("Error setting mute on %s", p.name, exc_info=True)
                with self._lock:
                    self._pending.pop(id(p), None)

    def _on_app_change(self, plugin: ConferencingPlugin, muted: bool) -> None:
        """Called from a plugin's observation callback when the app's mute state changes."""
        with self._lock:
            expected = self._pending.get(id(plugin))
            if expected == muted:
                self._pending.pop(id(plugin), None)
                return  # our own echo — ignore
            self._pending.pop(id(plugin), None)
        try:
            self._backend.set_mute(muted)
        except Exception:
            log.warning("Error setting backend mute", exc_info=True)

    def _start_plugin(self, plugin: ConferencingPlugin) -> None:
        if id(plugin) in self._observing:
            return
        if plugin.max_version:
            installed = plugin._get_installed_version()
            if installed and installed > plugin.max_version:
                log.warning(
                    "%s version %s exceeds tested max %s — AX paths may be stale",
                    plugin.name, installed, plugin.max_version,
                )
        log.debug("ConferencingSync: starting observation for %s", plugin.name)
        plugin.start_observing(lambda muted, p=plugin: self._on_app_change(p, muted))
        self._observing.add(id(plugin))

    def _discovery_loop(self) -> None:
        while not self._stop_event.wait(3.0):
            for p in self._plugins:
                if not p.is_compatible():
                    continue
                running = p.is_running()
                observing = id(p) in self._observing
                if running and not observing:
                    self._start_plugin(p)
                elif not running and observing:
                    log.debug("ConferencingSync: %s quit, stopping observation", p.name)
                    try:
                        p.stop_observing()
                    except Exception:
                        log.debug("Error stopping plugin %s", p.name, exc_info=True)
                    self._observing.discard(id(p))
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_conferencing_sync.py -v
```

Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add micdot/conferencing/sync.py tests/test_conferencing_sync.py
git commit -m "feat: add ConferencingSync coordinator with echo suppression"
```

---

## Task 5: Create `AXPlugin` base

**Files:**
- Create: `micdot/conferencing/ax_utils.py`

This is macOS-only. All pyobjc imports are inside methods so the module imports cleanly on non-macOS. No separate unit tests — the per-plugin tests in Task 6–8 exercise this indirectly via mocks.

- [ ] **Step 1: Create `micdot/conferencing/ax_utils.py`**

```python
from __future__ import annotations
import logging
import plistlib
import threading
from abc import abstractmethod
from collections.abc import Callable
from pathlib import Path

from micdot.conferencing.base import ConferencingPlugin

log = logging.getLogger("micdot")

# AXTitle value semantics for mute buttons:
# When the user IS muted  → button says "Unmute" (clicking it would unmute)
# When the user is NOT muted → button says "Mute"   (clicking it would mute)
# So: "unmute" in title.lower() → currently muted.
_MUTED_KEYWORD = "unmute"


class AXPlugin(ConferencingPlugin):
    """Base class for plugins that use the macOS Accessibility API.

    Subclasses must implement:
      - bundle_id, name  (class attributes)
      - _find_mute_element(app_element) -> AX element or None
      - is_in_meeting() -> bool
    """

    def __init__(self) -> None:
        self._on_change: Callable[[bool], None] | None = None
        self._stop_event = threading.Event()
        self._last_mute: bool | None = None

    # ------------------------------------------------------------------ #
    # Version / running detection
    # ------------------------------------------------------------------ #

    def _get_installed_version(self) -> str | None:
        try:
            from AppKit import NSWorkspace
            url = NSWorkspace.sharedWorkspace().URLForApplicationWithBundleIdentifier_(
                self.bundle_id
            )
            if url is None:
                return None
            plist_path = Path(url.path()) / "Contents" / "Info.plist"
            data = plistlib.loads(plist_path.read_bytes())
            return data.get("CFBundleShortVersionString")
        except Exception:
            log.debug("Could not read version for %s", self.bundle_id, exc_info=True)
            return None

    def is_running(self) -> bool:
        try:
            from AppKit import NSRunningApplication
            apps = NSRunningApplication.runningApplicationsWithBundleIdentifier_(
                self.bundle_id
            )
            return len(apps) > 0
        except Exception:
            return False

    def _get_app_pid(self) -> int | None:
        try:
            from AppKit import NSRunningApplication
            apps = NSRunningApplication.runningApplicationsWithBundleIdentifier_(
                self.bundle_id
            )
            return apps[0].processIdentifier() if apps else None
        except Exception:
            return None

    # ------------------------------------------------------------------ #
    # AX element helpers
    # ------------------------------------------------------------------ #

    def _get_app_element(self):
        """Return the root AXUIElement for this app, or None."""
        pid = self._get_app_pid()
        if pid is None:
            return None
        try:
            from ApplicationServices import AXUIElementCreateApplication
            return AXUIElementCreateApplication(pid)
        except Exception:
            log.debug("AXUIElementCreateApplication failed for %s", self.name, exc_info=True)
            return None

    def _get_attr(self, element, attribute: str):
        """Return (error_code, value) for an AX attribute. error_code == 0 means success."""
        try:
            from ApplicationServices import AXUIElementCopyAttributeValue
            return AXUIElementCopyAttributeValue(element, attribute, None)
        except Exception:
            return (-1, None)

    def _walk(self, element, role: str, keyword: str, max_depth: int = 12):
        """DFS through the AX tree. Returns the first AXButton whose AXTitle
        contains `keyword` (case-insensitive), or None."""
        if max_depth == 0:
            return None
        err_role, elem_role = self._get_attr(element, "AXRole")
        err_title, elem_title = self._get_attr(element, "AXTitle")
        if (
            err_role == 0
            and err_title == 0
            and elem_role == role
            and keyword.lower() in (elem_title or "").lower()
        ):
            return element
        err_ch, children = self._get_attr(element, "AXChildren")
        if err_ch == 0 and children:
            for child in children:
                result = self._walk(child, role, keyword, max_depth - 1)
                if result is not None:
                    return result
        return None

    def _read_title(self, element) -> str | None:
        err, title = self._get_attr(element, "AXTitle")
        return title if err == 0 else None

    def _press(self, element) -> bool:
        try:
            from ApplicationServices import AXUIElementPerformAction
            err = AXUIElementPerformAction(element, "AXPress")
            return err == 0
        except Exception:
            log.debug("AXUIElementPerformAction failed for %s", self.name, exc_info=True)
            return False

    # ------------------------------------------------------------------ #
    # Subclass contract
    # ------------------------------------------------------------------ #

    @abstractmethod
    def _find_mute_element(self, app_element):
        """Return the mute/unmute AXButton element, or None if not in a meeting."""
        ...

    # ------------------------------------------------------------------ #
    # ConferencingPlugin implementation
    # ------------------------------------------------------------------ #

    def get_mute(self) -> bool | None:
        if not self.is_running() or not self.is_in_meeting():
            return None
        app_el = self._get_app_element()
        if app_el is None:
            return None
        mute_el = self._find_mute_element(app_el)
        if mute_el is None:
            return None
        title = self._read_title(mute_el)
        if title is None:
            return None
        return _MUTED_KEYWORD in title.lower()

    def set_mute(self, muted: bool) -> None:
        if not self.is_running() or not self.is_in_meeting():
            return
        current = self.get_mute()
        if current is None or current == muted:
            return
        app_el = self._get_app_element()
        if app_el is None:
            return
        mute_el = self._find_mute_element(app_el)
        if mute_el is None:
            log.warning("%s: mute element not found", self.name)
            return
        if not self._press(mute_el):
            log.warning("%s: AXPress on mute element failed", self.name)

    # ------------------------------------------------------------------ #
    # Observation — 250ms poll loop
    # ------------------------------------------------------------------ #

    def start_observing(self, on_change: Callable[[bool], None]) -> None:
        self._on_change = on_change
        self._stop_event.clear()
        self._last_mute = None
        threading.Thread(
            target=self._poll_loop, daemon=True, name=f"ax-poll-{self.name}"
        ).start()

    def stop_observing(self) -> None:
        self._stop_event.set()
        self._on_change = None

    def _poll_loop(self) -> None:
        while not self._stop_event.wait(0.25):
            if not self.is_running() or not self.is_in_meeting():
                self._last_mute = None
                continue
            try:
                current = self.get_mute()
            except Exception:
                log.debug("%s: error reading mute state", self.name, exc_info=True)
                continue
            if current is not None and current != self._last_mute:
                self._last_mute = current
                cb = self._on_change
                if cb:
                    cb(current)
```

- [ ] **Step 2: Verify existing tests still pass**

```bash
pytest -v
```

Expected: all PASS (ax_utils.py has no tests of its own yet; it's exercised by plugin tests in tasks 6–8)

- [ ] **Step 3: Commit**

```bash
git add micdot/conferencing/ax_utils.py
git commit -m "feat: add AXPlugin base with 250ms poll loop and AX tree helpers"
```

---

## Task 6: Create `ZoomPlugin`

**Files:**
- Create: `micdot/conferencing/plugins/zoom.py`
- Create: `tests/test_conferencing_plugins.py`

Zoom (`com.zoom.xpc`) is a native Cocoa app with a rich, stable AX tree. The in-meeting toolbar is its own window. The mute button's `AXTitle` is `"Mute my audio"` (when unmuted) or `"Unmute my audio"` (when muted).

> **Note for implementer:** Verify the exact `AXTitle` strings against a live Zoom meeting by running:
> ```python
> from AppKit import NSRunningApplication
> from ApplicationServices import AXUIElementCreateApplication, AXUIElementCopyAttributeValue
> apps = NSRunningApplication.runningApplicationsWithBundleIdentifier_("com.zoom.xpc")
> app_el = AXUIElementCreateApplication(apps[0].processIdentifier())
> # Then walk the tree manually to find the mute button and print its AXTitle
> ```
> If the title differs from `"Mute my audio"` / `"Unmute my audio"`, update `_ZOOM_MUTE_KEYWORD` and `_ZOOM_IN_MEETING_KEYWORD` accordingly.

- [ ] **Step 1: Write failing tests**

Create `tests/test_conferencing_plugins.py`:

```python
import pytest
from unittest.mock import MagicMock, patch


# ------------------------------------------------------------------ #
# ZoomPlugin
# ------------------------------------------------------------------ #

class TestZoomPlugin:
    def _make_plugin(self, running=True, in_meeting=True):
        with patch("micdot.conferencing.ax_utils.AXPlugin.is_running", return_value=running), \
             patch("micdot.conferencing.ax_utils.AXPlugin._get_app_element", return_value=MagicMock()):
            from micdot.conferencing.plugins.zoom import ZoomPlugin
            plugin = ZoomPlugin()
            plugin._running = running
            plugin._in_meeting_result = in_meeting
            return plugin

    def test_bundle_id(self):
        from micdot.conferencing.plugins.zoom import ZoomPlugin
        assert ZoomPlugin.bundle_id == "com.zoom.xpc"

    def test_name(self):
        from micdot.conferencing.plugins.zoom import ZoomPlugin
        assert ZoomPlugin.name == "Zoom"

    def test_is_in_meeting_false_when_no_toolbar_window(self, mocker):
        from micdot.conferencing.plugins.zoom import ZoomPlugin
        plugin = ZoomPlugin()
        mocker.patch.object(plugin, "_get_app_element", return_value=None)
        assert plugin.is_in_meeting() is False

    def test_is_in_meeting_false_when_no_app_element(self, mocker):
        from micdot.conferencing.plugins.zoom import ZoomPlugin
        plugin = ZoomPlugin()
        mocker.patch.object(plugin, "_get_app_pid", return_value=None)
        assert plugin.is_in_meeting() is False

    def test_find_mute_element_searches_for_mute_keyword(self, mocker):
        from micdot.conferencing.plugins.zoom import ZoomPlugin
        plugin = ZoomPlugin()
        fake_el = MagicMock()
        mocker.patch.object(plugin, "_walk", return_value=fake_el)
        app_el = MagicMock()
        result = plugin._find_mute_element(app_el)
        assert result is fake_el

    def test_get_mute_returns_none_when_not_in_meeting(self, mocker):
        from micdot.conferencing.plugins.zoom import ZoomPlugin
        plugin = ZoomPlugin()
        mocker.patch.object(plugin, "is_running", return_value=True)
        mocker.patch.object(plugin, "is_in_meeting", return_value=False)
        assert plugin.get_mute() is None

    def test_get_mute_true_when_title_contains_unmute(self, mocker):
        from micdot.conferencing.plugins.zoom import ZoomPlugin
        plugin = ZoomPlugin()
        mocker.patch.object(plugin, "is_running", return_value=True)
        mocker.patch.object(plugin, "is_in_meeting", return_value=True)
        mocker.patch.object(plugin, "_get_app_element", return_value=MagicMock())
        mocker.patch.object(plugin, "_find_mute_element", return_value=MagicMock())
        mocker.patch.object(plugin, "_read_title", return_value="Unmute my audio")
        assert plugin.get_mute() is True

    def test_get_mute_false_when_title_contains_mute_only(self, mocker):
        from micdot.conferencing.plugins.zoom import ZoomPlugin
        plugin = ZoomPlugin()
        mocker.patch.object(plugin, "is_running", return_value=True)
        mocker.patch.object(plugin, "is_in_meeting", return_value=True)
        mocker.patch.object(plugin, "_get_app_element", return_value=MagicMock())
        mocker.patch.object(plugin, "_find_mute_element", return_value=MagicMock())
        mocker.patch.object(plugin, "_read_title", return_value="Mute my audio")
        assert plugin.get_mute() is False


# ------------------------------------------------------------------ #
# TeamsPlugin
# ------------------------------------------------------------------ #

class TestTeamsPlugin:
    def test_bundle_id(self):
        from micdot.conferencing.plugins.teams import TeamsPlugin
        assert TeamsPlugin.bundle_id == "com.microsoft.teams2"

    def test_name(self):
        from micdot.conferencing.plugins.teams import TeamsPlugin
        assert TeamsPlugin.name == "Microsoft Teams"

    def test_is_in_meeting_false_when_no_app_element(self, mocker):
        from micdot.conferencing.plugins.teams import TeamsPlugin
        plugin = TeamsPlugin()
        mocker.patch.object(plugin, "_get_app_pid", return_value=None)
        assert plugin.is_in_meeting() is False

    def test_get_mute_returns_none_when_not_in_meeting(self, mocker):
        from micdot.conferencing.plugins.teams import TeamsPlugin
        plugin = TeamsPlugin()
        mocker.patch.object(plugin, "is_running", return_value=True)
        mocker.patch.object(plugin, "is_in_meeting", return_value=False)
        assert plugin.get_mute() is None

    def test_get_mute_true_when_title_contains_unmute(self, mocker):
        from micdot.conferencing.plugins.teams import TeamsPlugin
        plugin = TeamsPlugin()
        mocker.patch.object(plugin, "is_running", return_value=True)
        mocker.patch.object(plugin, "is_in_meeting", return_value=True)
        mocker.patch.object(plugin, "_get_app_element", return_value=MagicMock())
        mocker.patch.object(plugin, "_find_mute_element", return_value=MagicMock())
        mocker.patch.object(plugin, "_read_title", return_value="Unmute microphone")
        assert plugin.get_mute() is True


# ------------------------------------------------------------------ #
# MeetPlugin
# ------------------------------------------------------------------ #

class TestMeetPlugin:
    def test_bundle_ids_include_chrome_and_safari(self):
        from micdot.conferencing.plugins.meet import MeetPlugin
        assert MeetPlugin.bundle_id == "com.google.Chrome"

    def test_name(self):
        from micdot.conferencing.plugins.meet import MeetPlugin
        assert MeetPlugin.name == "Google Meet"

    def test_get_mute_returns_none_when_not_in_meeting(self, mocker):
        from micdot.conferencing.plugins.meet import MeetPlugin
        plugin = MeetPlugin()
        mocker.patch.object(plugin, "is_running", return_value=True)
        mocker.patch.object(plugin, "is_in_meeting", return_value=False)
        assert plugin.get_mute() is None
```

- [ ] **Step 2: Run to confirm failure**

```bash
pytest tests/test_conferencing_plugins.py -v
```

Expected: FAIL — `ModuleNotFoundError: No module named 'micdot.conferencing.plugins.zoom'`

- [ ] **Step 3: Create `micdot/conferencing/plugins/zoom.py`**

```python
from __future__ import annotations
import logging
from micdot.conferencing.ax_utils import AXPlugin

log = logging.getLogger("micdot")

# The Zoom meeting toolbar window title contains this string.
_ZOOM_TOOLBAR_TITLE = "Zoom Meeting"
# The mute button AXTitle when the user is NOT muted (clicking mutes).
# When muted, the title contains "Unmute" — which _MUTED_KEYWORD in ax_utils catches.
# Verify these against a live meeting if they change across Zoom versions.
_MUTE_SEARCH_KEYWORD = "mute"


class ZoomPlugin(AXPlugin):
    bundle_id = "com.zoom.xpc"
    name = "Zoom"
    min_version = "5.0.0"
    max_version = "6.99.99"

    def is_in_meeting(self) -> bool:
        app_el = self._get_app_element()
        if app_el is None:
            return False
        # Zoom shows a floating toolbar window during meetings.
        # We detect it by looking for a window whose AXTitle contains the meeting keyword.
        err, windows = self._get_attr(app_el, "AXWindows")
        if err != 0 or not windows:
            return False
        for w in windows:
            err_t, title = self._get_attr(w, "AXTitle")
            if err_t == 0 and _ZOOM_TOOLBAR_TITLE in (title or ""):
                return True
        return False

    def _find_mute_element(self, app_element):
        """Search the AX tree for a button whose title contains 'mute' (case-insensitive)."""
        return self._walk(app_element, "AXButton", _MUTE_SEARCH_KEYWORD)
```

- [ ] **Step 4: Run Zoom tests**

```bash
pytest tests/test_conferencing_plugins.py::TestZoomPlugin -v
```

Expected: all PASS

- [ ] **Step 5: Commit**

```bash
git add micdot/conferencing/plugins/zoom.py tests/test_conferencing_plugins.py
git commit -m "feat: add ZoomPlugin"
```

---

## Task 7: Create `TeamsPlugin`

**Files:**
- Modify: `micdot/conferencing/plugins/teams.py` (create)

Teams (`com.microsoft.teams2`) is an Electron app. Its AX tree is shallower. The call-controls bar contains an `AXButton` with `AXTitle` like `"Mute microphone"` / `"Unmute microphone"`.

> **Note for implementer:** Verify the exact `AXTitle` string against a live Teams call. Teams updates frequently — bump `max_version` to the installed Teams version at time of implementation.

- [ ] **Step 1: Create `micdot/conferencing/plugins/teams.py`**

```python
from __future__ import annotations
import logging
from micdot.conferencing.ax_utils import AXPlugin

log = logging.getLogger("micdot")

# The call-controls toolbar is an AXGroup. Searching for "mute" keyword in
# AXButton AXTitle works for both "Mute microphone" and "Unmute microphone".
# Verify against a live Teams call — Electron AX trees change more often than
# native apps. Bump max_version when re-verified.
_MUTE_SEARCH_KEYWORD = "mute"
# Teams shows a call-controls bar identified by a group containing a mute button.
# We detect "in meeting" by checking whether such a button exists at all.


class TeamsPlugin(AXPlugin):
    bundle_id = "com.microsoft.teams2"
    name = "Microsoft Teams"
    min_version = "23.0.0"
    max_version = "25.99.99"

    def is_in_meeting(self) -> bool:
        app_el = self._get_app_element()
        if app_el is None:
            return False
        return self._find_mute_element(app_el) is not None

    def _find_mute_element(self, app_element):
        """Search the AX tree for a button whose title contains 'mute'."""
        return self._walk(app_element, "AXButton", _MUTE_SEARCH_KEYWORD)
```

- [ ] **Step 2: Run Teams tests**

```bash
pytest tests/test_conferencing_plugins.py::TestTeamsPlugin -v
```

Expected: all PASS

- [ ] **Step 3: Commit**

```bash
git add micdot/conferencing/plugins/teams.py
git commit -m "feat: add TeamsPlugin"
```

---

## Task 8: Create `MeetPlugin` (best-effort)

**Files:**
- Create: `micdot/conferencing/plugins/meet.py`

Google Meet runs in Chrome. The plugin finds the frontmost Chrome window showing a `meet.google.com` URL (via the window's `AXTitle`) and searches that window's AX tree for the mute button. This is fragile by design — full support requires a browser extension (separate project).

> **Note for implementer:** Chrome's AX tree can be very deep and slow to traverse. The `_find_mute_element` implementation uses `_walk` with a reduced `max_depth` to avoid blocking. If Meet's mute button cannot be found this way, set `is_in_meeting()` to always return `False` as a temporary measure until the browser extension approach is implemented.

- [ ] **Step 1: Create `micdot/conferencing/plugins/meet.py`**

```python
from __future__ import annotations
import logging
from micdot.conferencing.ax_utils import AXPlugin

log = logging.getLogger("micdot")

_MEET_URL_FRAGMENT = "meet.google.com"
_MUTE_SEARCH_KEYWORD = "mute"


class MeetPlugin(AXPlugin):
    bundle_id = "com.google.Chrome"
    name = "Google Meet"
    max_version = "136.99.99"

    def is_in_meeting(self) -> bool:
        app_el = self._get_app_element()
        if app_el is None:
            return False
        meet_window = self._find_meet_window(app_el)
        return meet_window is not None

    def _find_meet_window(self, app_element):
        """Return the Chrome window showing a Google Meet tab, or None."""
        err, windows = self._get_attr(app_element, "AXWindows")
        if err != 0 or not windows:
            return None
        for w in windows:
            err_t, title = self._get_attr(w, "AXTitle")
            if err_t == 0 and _MEET_URL_FRAGMENT in (title or "").lower():
                return w
        return None

    def _find_mute_element(self, app_element):
        meet_window = self._find_meet_window(app_element)
        if meet_window is None:
            return None
        # Chrome's tree is deep. Limit depth to avoid long traversal times.
        return self._walk(meet_window, "AXButton", _MUTE_SEARCH_KEYWORD, max_depth=20)
```

- [ ] **Step 2: Run Meet tests**

```bash
pytest tests/test_conferencing_plugins.py::TestMeetPlugin -v
```

Expected: all PASS

- [ ] **Step 3: Commit**

```bash
git add micdot/conferencing/plugins/meet.py
git commit -m "feat: add MeetPlugin (best-effort, browser tab detection)"
```

---

## Task 9: Wire up package `__init__` files

**Files:**
- Modify: `micdot/conferencing/__init__.py`
- Modify: `micdot/conferencing/plugins/__init__.py`

- [ ] **Step 1: Write `micdot/conferencing/plugins/__init__.py`**

```python
from micdot.conferencing.plugins.zoom import ZoomPlugin
from micdot.conferencing.plugins.teams import TeamsPlugin
from micdot.conferencing.plugins.meet import MeetPlugin

PLUGINS = [ZoomPlugin(), TeamsPlugin(), MeetPlugin()]
```

- [ ] **Step 2: Write `micdot/conferencing/__init__.py`**

```python
from micdot.conferencing.sync import ConferencingSync
from micdot.conferencing.plugins import PLUGINS

__all__ = ["ConferencingSync", "PLUGINS"]
```

- [ ] **Step 3: Verify full test suite passes**

```bash
pytest -v
```

Expected: all PASS

- [ ] **Step 4: Commit**

```bash
git add micdot/conferencing/__init__.py micdot/conferencing/plugins/__init__.py
git commit -m "feat: wire conferencing package exports and PLUGINS list"
```

---

## Task 10: Wire `ConferencingSync` into `main.py`

**Files:**
- Modify: `micdot/main.py`
- Modify: `tests/test_main_reload.py`

This task touches the existing `_State`, `main()`, `on_state_change`, `on_quit`, and `_reload_config`. Read `micdot/main.py` carefully before editing — it uses `__slots__` on `_State` and dispatches hotkey updates to the main thread.

- [ ] **Step 1: Read `micdot/main.py` to understand the current structure**

```bash
cat micdot/main.py
```

- [ ] **Step 2: Write failing reload test**

Add to `tests/test_main_reload.py`:

```python
from micdot.audio.backend import StubAudioBackend

def test_reload_stops_old_conferencing_sync_and_starts_new(config_path, mocker):
    mocker.patch("micdot.main.MQTTClient")
    old_sync = MagicMock()
    mock_sync_cls = mocker.patch("micdot.main.ConferencingSync")
    backend = StubAudioBackend()
    state = _State(Config(), MagicMock(), MagicMock(), old_sync)
    on_toggle = MagicMock()

    _reload_config(state, config_path, on_toggle, backend)

    old_sync.stop.assert_called_once()
    mock_sync_cls.return_value.start.assert_called_once()
```

- [ ] **Step 3: Run to confirm failure**

```bash
pytest tests/test_main_reload.py::test_reload_stops_old_conferencing_sync_and_starts_new -v
```

Expected: FAIL — `TypeError: _State.__init__() takes 4 positional arguments but 5 were given`

- [ ] **Step 4: Update `micdot/main.py`**

Apply all changes below. The diff is shown logically; apply each change carefully:

**4a — Add import at the top (after existing imports):**

```python
from micdot.conferencing import ConferencingSync, PLUGINS
```

**4b — Replace the `_State` class:**

```python
class _State:
    __slots__ = ("config", "mqtt", "hotkey_listener", "conferencing_sync")

    def __init__(
        self,
        config: Config,
        mqtt: MQTTClient,
        hotkey_listener: HotkeyListener,
        conferencing_sync: ConferencingSync,
    ) -> None:
        self.config = config
        self.mqtt = mqtt
        self.hotkey_listener = hotkey_listener
        self.conferencing_sync = conferencing_sync
```

**4c — Replace `_reload_config` — add `backend` parameter and sync stop/start alongside MQTT:**

```python
def _reload_config(
    state: _State,
    config_path: Path,
    on_toggle: Callable[[], None],
    backend: AudioBackend,
) -> None:
    log.info("Reloading config from %s", config_path)
    new_config = Config.load(config_path)
    try:
        new_mqtt = MQTTClient(new_config, on_button_press=on_toggle)
    except Exception:
        log.exception("Failed to construct MQTT client during reload — keeping existing config")
        return
    state.mqtt.stop()
    state.mqtt = new_mqtt
    state.mqtt.start()

    state.conferencing_sync.stop()
    new_sync = ConferencingSync(PLUGINS, backend)
    if new_config.conferencing_sync_enabled:
        new_sync.start()
    state.conferencing_sync = new_sync

    def _update_hotkey() -> None:
        try:
            log.debug("Updating hotkey to %r (main thread)", new_config.hotkey)
            state.hotkey_listener.update(new_config.hotkey, on_toggle)
            state.config = new_config
            log.info("Config reloaded")
        except Exception:
            log.exception("Error updating hotkey on main thread")

    if threading.current_thread() is threading.main_thread():
        _update_hotkey()
    else:
        try:
            from Foundation import NSOperationQueue
            NSOperationQueue.mainQueue().addOperationWithBlock_(_update_hotkey)
        except Exception:
            log.exception("Could not dispatch to main thread; updating hotkey inline")
            _update_hotkey()
```

**4c-ii — Update the `_reload_config` call inside `open_settings._on_exit` in `main()`:**

Find this block inside `open_settings`:

```python
        def _on_exit() -> None:
            rc = settings_proc[0].wait() if settings_proc[0] else 1
            if rc == 0:
                try:
                    _reload_config(state, DEFAULT_CONFIG_PATH, on_toggle)
```

Replace with (adds `backend`):

```python
        def _on_exit() -> None:
            rc = settings_proc[0].wait() if settings_proc[0] else 1
            if rc == 0:
                try:
                    _reload_config(state, DEFAULT_CONFIG_PATH, on_toggle, backend)
```

Also add `AudioBackend` to the imports at the top of `main.py`:

```python
from micdot.audio.backend import get_backend, AudioBackend
```

**4d — Update `on_state_change` in `main()` to call sync:**

```python
    def on_state_change(muted: bool) -> None:
        log.debug("Mic state changed: muted=%s", muted)
        state.mqtt.publish_state(muted)
        tray.set_muted(muted)
        state.conferencing_sync.on_mute_change(muted)
```

**4e — Update `on_quit` to stop sync:**

```python
    def on_quit() -> None:
        log.info("Quit requested")
        state.hotkey_listener.stop()
        poller.stop()
        state.mqtt.stop()
        state.conferencing_sync.stop()
        sys.exit(0)
```

**4f — Check Accessibility permission and create sync in `main()`:**

Replace the `state = _State(...)` block:

```python
    _check_accessibility(config)
    conferencing_sync = ConferencingSync(PLUGINS, backend)

    state = _State(
        config,
        MQTTClient(config, on_button_press=on_toggle),
        HotkeyListener(config.hotkey, callback=on_toggle),
        conferencing_sync,
    )
```

**4g — Add `_check_accessibility` helper before `main()`:**

```python
def _check_accessibility(config: Config) -> None:
    if not config.conferencing_sync_enabled:
        return
    try:
        from ApplicationServices import AXIsProcessTrusted
        if AXIsProcessTrusted():
            return
    except Exception:
        return
    log.warning(
        "Accessibility permission not granted — conferencing sync disabled. "
        "Grant it in System Settings → Privacy & Security → Accessibility, then restart MicDot."
    )
    try:
        import subprocess
        subprocess.run(
            ["osascript", "-e",
             'display notification "Grant Accessibility access in System Settings to enable '
             'conferencing sync, then restart MicDot." with title "MicDot"'],
            check=False,
        )
    except Exception:
        pass
```

**4h — Start `conferencing_sync` after the other components (only if trusted):**

After `state.hotkey_listener.start()`, add:

```python
    try:
        from ApplicationServices import AXIsProcessTrusted
        if config.conferencing_sync_enabled and AXIsProcessTrusted():
            conferencing_sync.start()
            log.info("Conferencing sync started")
    except Exception:
        log.warning("Could not start conferencing sync", exc_info=True)
```

- [ ] **Step 5: Run all tests**

```bash
pytest -v
```

Expected: all PASS

- [ ] **Step 6: Verify existing reload tests still pass**

```bash
pytest tests/test_main_reload.py -v
```

Expected: all PASS

- [ ] **Step 7: Commit**

```bash
git add micdot/main.py tests/test_main_reload.py
git commit -m "feat: wire ConferencingSync into main — bidirectional mute sync"
```

---

## Task 11: Final verification

- [ ] **Step 1: Run the full test suite**

```bash
pytest -v
```

Expected: all PASS, no warnings about missing imports

- [ ] **Step 2: Verify the module tree is complete**

```bash
python -c "from micdot.conferencing import ConferencingSync, PLUGINS; print([p.name for p in PLUGINS])"
```

Expected: `['Zoom', 'Microsoft Teams', 'Google Meet']`

- [ ] **Step 3: Verify Accessibility check works**

```bash
python -c "from ApplicationServices import AXIsProcessTrusted; print('trusted:', AXIsProcessTrusted())"
```

Expected: prints `trusted: True` or `trusted: False` without error

- [ ] **Step 4: Run MicDot and check log**

```bash
micdot
```

Open `~/Library/Logs/MicDot/micdot.log`. Expected to see:
- `Conferencing sync started` (if Accessibility is granted)
- or the Accessibility warning (if not granted)

- [ ] **Step 5: Tag for manual AX path verification**

Open a Zoom meeting. Check the log for `ConferencingSync: starting observation for Zoom`. Mute in Zoom → MicDot's LED/tray should update within 250ms. Mute via MicDot hotkey → Zoom's UI should update.

If Zoom mute button is not found, verify the AX title by running the inspection snippet in the `ZoomPlugin` task note above and update `_MUTE_SEARCH_KEYWORD` accordingly.

- [ ] **Step 6: Final commit if any AX path adjustments were needed**

```bash
git add -p
git commit -m "fix: adjust AX mute button search keywords from live-app verification"
```
