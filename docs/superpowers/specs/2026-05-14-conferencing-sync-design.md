# Conferencing App Mute Sync — Design Spec

**Date:** 2026-05-14
**Branch:** feature/0.5.0
**Status:** Approved

## Problem

MicDot mutes the system microphone at the CoreAudio HAL level (`kAudioDevicePropertyMute`). This silences the audio that conferencing apps receive, but the apps maintain their own independent mute state and UI indicator. When MicDot mutes, Teams/Zoom/Meet still show the mic as live. When the user mutes inside Teams, MicDot's tray icon and LED ring do not reflect it.

The goal is bidirectional mute sync between MicDot and conferencing apps, implemented with a plugin architecture so new apps can be added without touching the core system.

## Why Apps Have Their Own Mute

Conferencing apps mute at the **network/encoding layer** — they stop sending RTP audio packets rather than touching the OS mic state. This is cross-platform, reliable across hardware that may not honour `kAudioDevicePropertyMute`, and allows per-app mute states to be independent (muted in Teams, live in Discord simultaneously). Their own source selection exists because they open their own CoreAudio capture pipeline with specific sample rates, channel counts, and processing chains (AEC, noise cancellation). They don't passively inherit the OS default device.

## Approach

Use the macOS **Accessibility API (AXUIElement + AXObserver)**:

- **Outbound (MicDot → app):** `AXUIElementPerformAction(element, kAXPressAction)` on the app's mute button. State-setting, not a toggle — no risk of double-toggle if states diverge.
- **Inbound (app → MicDot):** `AXObserver` registered on the mute button element fires a callback the moment the button value changes in the app. Real-time, no polling.

Requires the **Accessibility permission** (System Settings → Privacy & Security → Accessibility). Checked at startup; sync is skipped gracefully if not granted.

## Architecture

`ConferencingSync` is a new component that plugs into the existing MicDot event flow without restructuring anything.

```
Poller.on_change ──► ConferencingSync.on_mute_change ──► plugin.set_mute()
                                                               │
AXObserver callback ◄──── Teams/Zoom UI change                │
       │                                                       ▼
       └──► ConferencingSync._on_app_change ──► AudioBackend.set_mute()
                                                      │
                                               Poller detects within 200ms
                                               → tray icon + LED update
```

### Feedback Loop Prevention

When `ConferencingSync` sets an app's mute state via AX, the app's own state change fires an AX notification back. To suppress this echo, the coordinator maintains:

```python
_pending: dict[int, bool]  # plugin id → mute state we just set
```

When an inbound AX notification arrives, `_pending` is checked. If the notified state matches what was just set, it is an echo — ignored. If it differs, it is a genuine user action — propagated to MicDot. The lock is released before calling `plugin.set_mute()` to avoid deadlock if the AX call blocks.

### Lifecycle

`ConferencingSync` is included in the `_State` dataclass alongside `MQTTClient` and `HotkeyListener`. On config reload, the old instance is stopped (observers unregistered) and a new instance is created — same pattern as the rest of `_State`.

## Plugin Interface

```python
# micdot/conferencing/base.py

class ConferencingPlugin(ABC):
    bundle_id: str                          # e.g. "com.microsoft.teams2"
    name: str                               # e.g. "Microsoft Teams"
    supported_platforms: tuple[str, ...] = ("darwin",)
    min_version: str | None = None          # oldest known-good app version
    max_version: str | None = None          # newest tested version (warns if exceeded)

    def is_compatible(self) -> bool:
        """False if platform or app version rules out this plugin."""
        if sys.platform not in self.supported_platforms:
            return False
        installed = self._get_installed_version()
        if installed and self.min_version and installed < self.min_version:
            return False
        return True

    def _get_installed_version(self) -> str | None:
        """Reads version from the app bundle's Info.plist. Implemented by AXPlugin."""
        ...

    @abstractmethod
    def is_running(self) -> bool: ...

    @abstractmethod
    def is_in_meeting(self) -> bool: ...

    @abstractmethod
    def get_mute(self) -> bool | None:
        """None means not in a meeting."""
        ...

    @abstractmethod
    def set_mute(self, muted: bool) -> None:
        """No-op if not in a meeting."""
        ...

    @abstractmethod
    def start_observing(self, on_change: Callable[[bool], None]) -> None:
        """Register for mute state changes. Calls on_change(muted) from any thread."""
        ...

    @abstractmethod
    def stop_observing(self) -> None: ...
```

`max_version` does not block the plugin — it logs a warning so stale AX paths are visible when an app ships a UI update.

Version strings are compared component-by-component on semver segments (`"5.12.0" < "6.0.0"`). No external dependency required.

## AXPlugin Base

`micdot/conferencing/ax_utils.py` provides `AXPlugin(ConferencingPlugin, ABC)` — a non-abstract intermediate base with shared helpers:

- Find the app's root `AXUIElement` by bundle ID
- Walk an element tree by role and description
- Perform a press action on an element
- Register and tear down an `AXObserver` with a given notification name
- Read `_get_installed_version()` from the app bundle's `Info.plist`

Per-app plugins subclass `AXPlugin` and implement only:

- Class attributes (`bundle_id`, `name`, `min_version`, `max_version`)
- `_find_mute_element(app_element: AXUIElement) -> AXUIElement | None`
- `is_in_meeting() -> bool`

Everything else (observer lifecycle, press, version check) is inherited.

## Sync Coordinator

```python
# micdot/conferencing/sync.py

class ConferencingSync:
    def __init__(
        self,
        plugins: list[ConferencingPlugin],
        backend: AudioBackend,
    ) -> None: ...

    def start(self) -> None:
        # Filters to compatible + running plugins, starts observing on each.
        ...

    def stop(self) -> None:
        # Stops all observers.
        ...

    def on_mute_change(self, muted: bool) -> None:
        # Called by Poller's on_change.
        # Propagates to every plugin where is_running() and is_in_meeting().
        ...

    def _on_app_change(self, plugin: ConferencingPlugin, muted: bool) -> None:
        # Called by a plugin's AXObserver callback (any thread).
        # Checks _pending to distinguish echo from genuine user action.
        # Calls backend.set_mute() if genuine.
        ...
```

## Per-App Plugins

### Zoom (`com.zoom.xpc`)

Native Cocoa app with a rich, stable AX tree.

- Mute button: `AXButton` in the meeting toolbar, identified by description `"Mute"` / `"Unmute"`.
- `is_in_meeting()`: checks for the meeting toolbar window in the app's window list.

### Microsoft Teams (`com.microsoft.teams2`)

Electron app. AX tree is shallower than a native app.

- Mute button: `AXButton` in the call-controls area, searched by description since the element path is not fixed across updates.
- `is_in_meeting()`: checks for a call-controls group element in the AX tree.
- AX paths are more likely to break on Teams updates than on Zoom — `max_version` is set to the latest tested version at time of writing.

### Google Meet (`com.google.Chrome` / Safari)

Best-effort support. Meet runs in a browser tab, not a native app.

- `MeetPlugin` searches the frontmost browser window's AX tree for a button whose description matches the Meet mute button label.
- Fragile by nature — documented as such. `max_version` is set to the Chrome version at time of writing.
- Full support deferred to a dedicated browser extension (separate project).

## File Layout

```
micdot/
  conferencing/
    __init__.py          # exports ConferencingSync, PLUGINS
    base.py              # ConferencingPlugin ABC
    ax_utils.py          # AXPlugin base + shared AX helpers
    sync.py              # ConferencingSync coordinator
    plugins/
      __init__.py        # PLUGINS = [ZoomPlugin(), TeamsPlugin(), MeetPlugin()]
      zoom.py            # ZoomPlugin
      teams.py           # TeamsPlugin
      meet.py            # MeetPlugin
```

## Changes to Existing Files

### `micdot/config.py`

One new field with a default of `True`:

```python
@dataclass
class Config:
    ...
    conferencing_sync_enabled: bool = True
```

### `micdot/main.py`

`_State` gains a `conferencing_sync` slot:

```python
@dataclass
class _State:
    config: Config
    mqtt: MQTTClient
    hotkey_listener: HotkeyListener
    conferencing_sync: ConferencingSync
```

The `Poller`'s `on_change` callback gets one additional line:

```python
def _on_mute_change(muted: bool) -> None:
    _update_tray(muted)
    _update_led(muted)
    _state.conferencing_sync.on_mute_change(muted)
```

`_reload_config` stops the old `ConferencingSync` and creates a new one, same as it does for `MQTTClient`.

## Permissions

On startup, `AXIsProcessTrusted()` is checked when `conferencing_sync_enabled = True`. If the Accessibility permission has not been granted:

- A tray notification prompts the user to grant it in System Settings → Privacy & Security → Accessibility.
- `ConferencingSync` is not started — sync is silently skipped rather than crashing.
- On next launch after the permission is granted, sync starts normally.

## Testing

All tests run without hardware, real apps, or the Accessibility permission. The `ConferencingPlugin` ABC is easily stubbed:

- **Unit tests for `ConferencingSync`:** Use a `StubPlugin` that records calls to `set_mute()` and can fire `on_change` callbacks manually. Test outbound propagation, inbound propagation, and echo suppression via `_pending`.
- **Unit tests for `AXPlugin` helpers:** Mock the pyobjc AX calls. Test version comparison logic independently.
- **Per-plugin tests:** Stub the AX tree responses. Test `is_in_meeting()` and `_find_mute_element()` against representative element trees captured from each app.

No integration tests against live apps — AX paths are validated manually when adding or updating a plugin.
