# Google Meet Plugin — Design Spec

**Date:** 2026-05-16
**Status:** Approved

## Problem

`MeetPlugin` exists but is non-functional due to three bugs in the AX-based implementation:

1. **Wrong window detection keyword** — `is_in_meeting` searches `AXTitle` for `"meet.google.com"` (a URL fragment), but Chrome's `AXTitle` reflects the page title (e.g., `"André Cedik - Google Meet"`), not the URL.

2. **Wrong mute button keyword** — `_find_mute_element` searches for `"mute"`, but Google Meet's mic buttons are labelled `"Turn off microphone"` and `"Turn on microphone"`. Neither contains `"mute"`, so the button is never found.

3. **Wrong mute state semantics** — inherits `AXPlugin.get_mute` which looks for `"unmute"` in the button title. Meet's button says `"Turn on microphone"` when you are muted (clicking it would unmute you). The correct sentinel is `"turn on"`.

## Scope

- **Browser:** Chrome only (`com.google.Chrome`)
- **Detection:** any Chrome window (not restricted to frontmost)
- **Approach:** AX-based, Approach A — fix only `MeetPlugin`, no changes to `AXPlugin` or other plugins

## Design

### `MeetPlugin` — full implementation

`MeetPlugin` extends `AXPlugin` and overrides four members. All other behaviour (`start_observing`, `stop_observing`, `set_mute`, `is_running`, `_get_app_element`, `_press`, etc.) is inherited unchanged.

```python
class MeetPlugin(AXPlugin):
    bundle_id = "com.google.Chrome"
    name = "Google Meet"

    def is_in_meeting(self) -> bool:
        app_el = self._get_app_element()
        if app_el is None:
            return False
        return self._find_meet_window(app_el) is not None

    def _find_meet_window(self, app_element):
        """Return the first Chrome window whose AXTitle contains 'google meet', or None."""
        err, windows = self._get_attr(app_element, "AXWindows")
        if err != 0 or not windows:
            return None
        for w in windows:
            err_t, title = self._get_attr(w, "AXTitle")
            if err_t == 0 and "google meet" in (title or "").lower():
                return w
        return None

    def _find_mute_element(self, app_element):
        meet_window = self._find_meet_window(app_element)
        if meet_window is None:
            return None
        return self._walk(meet_window, "AXButton", "microphone", max_depth=20)

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
        # "Turn on microphone" → user is muted (button would unmute)
        # "Turn off microphone" → user is unmuted (button would mute)
        return "turn on" in title.lower()
```

### `set_mute` (inherited, no changes)

`AXPlugin.set_mute` calls `self.get_mute()` (the overridden version), compares with the requested state, and calls `_press` on the mute element. No changes needed.

### Observation (inherited, no changes)

`AXPlugin.start_observing` runs a 250 ms poll loop calling `get_mute()`. Since `get_mute` is overridden, observation works correctly for Meet without any additional changes.

## Tests

New tests added to `TestMeetPlugin` in `tests/test_conferencing_plugins.py`:

| Test | Assertion |
|---|---|
| `test_is_in_meeting_false_when_no_meet_window` | No window title contains `"google meet"` → `False` |
| `test_is_in_meeting_true_when_window_title_contains_google_meet` | Window title `"André Cedik - Google Meet"` → `True` |
| `test_find_mute_element_searches_microphone_keyword` | `_walk` is called with keyword `"microphone"` |
| `test_get_mute_true_when_button_says_turn_on_microphone` | Button title `"Turn on microphone"` → `True` |
| `test_get_mute_false_when_button_says_turn_off_microphone` | Button title `"Turn off microphone"` → `False` |
| `test_get_mute_none_when_not_in_meeting` | Already exists — keep |

## What is not changing

- `AXPlugin` base class — no modifications
- `ZoomPlugin`, `TeamsPlugin` — untouched
- `ConferencingSync`, `PLUGINS` list — no changes needed (`MeetPlugin()` is already registered)
- No new dependencies
