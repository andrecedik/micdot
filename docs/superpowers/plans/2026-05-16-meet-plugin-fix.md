# Google Meet Plugin Fix — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the three bugs in `MeetPlugin` so bidirectional mute sync works with Google Meet running in Chrome.

**Architecture:** All changes are confined to `micdot/conferencing/plugins/meet.py` and the `TestMeetPlugin` class in `tests/test_conferencing_plugins.py`. No changes to `AXPlugin`, other plugins, `ConferencingSync`, or `PLUGINS` — `MeetPlugin()` is already registered.

**Tech Stack:** Python, pytest, pytest-mock (`mocker` fixture), macOS Accessibility API (mocked in tests via `mocker.patch.object`)

---

### Task 1: Fix `is_in_meeting` — wrong window detection keyword

**Context:** `_find_meet_window` searches `AXTitle` for `"meet.google.com"` (a URL fragment), but Chrome sets `AXTitle` to the **page title** (e.g., `"André Cedik - Google Meet"`), not the URL. The fix: search for `"google meet"` instead.

**Files:**
- Modify: `tests/test_conferencing_plugins.py` — add two tests to `TestMeetPlugin`
- Modify: `micdot/conferencing/plugins/meet.py` — change the `_MEET_URL_FRAGMENT` constant

- [ ] **Step 1: Add two failing tests to `TestMeetPlugin`**

In `tests/test_conferencing_plugins.py`, add these two methods inside the existing `TestMeetPlugin` class (after the last existing test). `MagicMock` is already imported at the top of the file.

```python
def test_is_in_meeting_false_when_no_meet_window(self, mocker):
    from micdot.conferencing.plugins.meet import MeetPlugin
    plugin = MeetPlugin()
    fake_app_el = MagicMock()
    fake_window = MagicMock()
    mocker.patch.object(plugin, "_get_app_element", return_value=fake_app_el)

    def fake_get_attr(element, attr):
        if attr == "AXWindows":
            return (0, [fake_window])
        if attr == "AXTitle":
            return (0, "GitHub - Some Repo")
        return (-1, None)

    mocker.patch.object(plugin, "_get_attr", side_effect=fake_get_attr)
    assert plugin.is_in_meeting() is False

def test_is_in_meeting_true_when_window_title_contains_google_meet(self, mocker):
    from micdot.conferencing.plugins.meet import MeetPlugin
    plugin = MeetPlugin()
    fake_app_el = MagicMock()
    fake_window = MagicMock()
    mocker.patch.object(plugin, "_get_app_element", return_value=fake_app_el)

    def fake_get_attr(element, attr):
        if attr == "AXWindows":
            return (0, [fake_window])
        if attr == "AXTitle":
            return (0, "André Cedik - Google Meet")
        return (-1, None)

    mocker.patch.object(plugin, "_get_attr", side_effect=fake_get_attr)
    assert plugin.is_in_meeting() is True
```

- [ ] **Step 2: Run the two new tests to confirm the second one fails**

```bash
pytest tests/test_conferencing_plugins.py::TestMeetPlugin::test_is_in_meeting_false_when_no_meet_window tests/test_conferencing_plugins.py::TestMeetPlugin::test_is_in_meeting_true_when_window_title_contains_google_meet -v
```

Expected: first test PASSES (`"meet.google.com"` is not in `"GitHub - Some Repo"` either), second test FAILS (`"meet.google.com"` is not in `"André Cedik - Google Meet"`).

- [ ] **Step 3: Fix `_find_meet_window` in `meet.py`**

Replace the full content of `micdot/conferencing/plugins/meet.py` with:

```python
from __future__ import annotations
import logging
from micdot.conferencing.ax_utils import AXPlugin

log = logging.getLogger("micdot")

_MEET_TITLE_FRAGMENT = "google meet"
_MUTE_SEARCH_KEYWORD = "mute"


class MeetPlugin(AXPlugin):
    bundle_id = "com.google.Chrome"
    name = "Google Meet"
    max_version = "136.99.99"

    def is_in_meeting(self) -> bool:
        app_el = self._get_app_element()
        if app_el is None:
            return False
        return self._find_meet_window(app_el) is not None

    def _find_meet_window(self, app_element):
        """Return the Chrome window showing a Google Meet tab, or None."""
        err, windows = self._get_attr(app_element, "AXWindows")
        if err != 0 or not windows:
            return None
        for w in windows:
            err_t, title = self._get_attr(w, "AXTitle")
            if err_t == 0 and _MEET_TITLE_FRAGMENT in (title or "").lower():
                return w
        return None

    def _find_mute_element(self, app_element):
        meet_window = self._find_meet_window(app_element)
        if meet_window is None:
            return None
        return self._walk(meet_window, "AXButton", _MUTE_SEARCH_KEYWORD, max_depth=20)
```

Note: `max_version` and `_MUTE_SEARCH_KEYWORD = "mute"` are intentionally unchanged — those are fixed in later tasks.

- [ ] **Step 4: Run the two tests again to confirm both pass**

```bash
pytest tests/test_conferencing_plugins.py::TestMeetPlugin::test_is_in_meeting_false_when_no_meet_window tests/test_conferencing_plugins.py::TestMeetPlugin::test_is_in_meeting_true_when_window_title_contains_google_meet -v
```

Expected: both PASS.

- [ ] **Step 5: Commit**

```bash
git add micdot/conferencing/plugins/meet.py tests/test_conferencing_plugins.py
git commit -m "fix(meet): detect meeting by page title not URL fragment"
```

---

### Task 2: Fix `_find_mute_element` — wrong button search keyword

**Context:** `_find_mute_element` calls `_walk` with keyword `"mute"`, but Google Meet's microphone buttons are labelled `"Turn off microphone"` / `"Turn on microphone"`. Neither contains `"mute"`, so the button is never found. Fix: use `"microphone"` as the search keyword.

**Files:**
- Modify: `tests/test_conferencing_plugins.py` — add one test to `TestMeetPlugin`
- Modify: `micdot/conferencing/plugins/meet.py` — change `_MUTE_SEARCH_KEYWORD`

- [ ] **Step 1: Add a failing test to `TestMeetPlugin`**

In `tests/test_conferencing_plugins.py`, add to the `TestMeetPlugin` class:

```python
def test_find_mute_element_searches_microphone_keyword(self, mocker):
    from micdot.conferencing.plugins.meet import MeetPlugin
    plugin = MeetPlugin()
    fake_app_el = MagicMock()
    fake_window = MagicMock()
    fake_btn = MagicMock()
    mocker.patch.object(plugin, "_find_meet_window", return_value=fake_window)
    walk = mocker.patch.object(plugin, "_walk", return_value=fake_btn)
    result = plugin._find_mute_element(fake_app_el)
    walk.assert_called_once_with(fake_window, "AXButton", "microphone", max_depth=20)
    assert result is fake_btn
```

- [ ] **Step 2: Run the new test to confirm it fails**

```bash
pytest tests/test_conferencing_plugins.py::TestMeetPlugin::test_find_mute_element_searches_microphone_keyword -v
```

Expected: FAIL — `_walk` was called with `"mute"`, not `"microphone"`.

- [ ] **Step 3: Change `_MUTE_SEARCH_KEYWORD` in `meet.py`**

In `micdot/conferencing/plugins/meet.py`, change:

```python
_MUTE_SEARCH_KEYWORD = "mute"
```

to:

```python
_MUTE_SEARCH_KEYWORD = "microphone"
```

- [ ] **Step 4: Run the test again to confirm it passes**

```bash
pytest tests/test_conferencing_plugins.py::TestMeetPlugin::test_find_mute_element_searches_microphone_keyword -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add micdot/conferencing/plugins/meet.py tests/test_conferencing_plugins.py
git commit -m "fix(meet): search for 'microphone' keyword to find mute button"
```

---

### Task 3: Fix `get_mute` semantics and remove version cap

**Context:** `MeetPlugin` inherits `AXPlugin.get_mute`, which checks for `"unmute"` in the button title. Google Meet's button says `"Turn on microphone"` when you are muted — the word `"unmute"` never appears. Fix: override `get_mute` to check for `"turn on"` instead (`"Turn on microphone"` means muted; `"Turn off microphone"` means unmuted). Also remove `max_version = "136.99.99"`, which was a guard for the broken implementation.

`_read_title` is defined in `AXPlugin` (`micdot/conferencing/ax_utils.py:124`): calls `_get_attr(element, "AXTitle")` and returns the title string or `None`.

**Files:**
- Modify: `tests/test_conferencing_plugins.py` — add two tests to `TestMeetPlugin`
- Modify: `micdot/conferencing/plugins/meet.py` — add `get_mute` override, remove `max_version`

- [ ] **Step 1: Add two tests to `TestMeetPlugin`**

In `tests/test_conferencing_plugins.py`, add to the `TestMeetPlugin` class:

```python
def test_get_mute_true_when_button_says_turn_on_microphone(self, mocker):
    from micdot.conferencing.plugins.meet import MeetPlugin
    plugin = MeetPlugin()
    mocker.patch.object(plugin, "is_running", return_value=True)
    mocker.patch.object(plugin, "is_in_meeting", return_value=True)
    mocker.patch.object(plugin, "_get_app_element", return_value=MagicMock())
    mocker.patch.object(plugin, "_find_mute_element", return_value=MagicMock())
    mocker.patch.object(plugin, "_read_title", return_value="Turn on microphone")
    assert plugin.get_mute() is True

def test_get_mute_false_when_button_says_turn_off_microphone(self, mocker):
    from micdot.conferencing.plugins.meet import MeetPlugin
    plugin = MeetPlugin()
    mocker.patch.object(plugin, "is_running", return_value=True)
    mocker.patch.object(plugin, "is_in_meeting", return_value=True)
    mocker.patch.object(plugin, "_get_app_element", return_value=MagicMock())
    mocker.patch.object(plugin, "_find_mute_element", return_value=MagicMock())
    mocker.patch.object(plugin, "_read_title", return_value="Turn off microphone")
    assert plugin.get_mute() is False
```

- [ ] **Step 2: Run both tests to confirm the first fails**

```bash
pytest tests/test_conferencing_plugins.py::TestMeetPlugin::test_get_mute_true_when_button_says_turn_on_microphone tests/test_conferencing_plugins.py::TestMeetPlugin::test_get_mute_false_when_button_says_turn_off_microphone -v
```

Expected: first test FAILS (inherited `AXPlugin.get_mute` checks for `"unmute"` → returns `False` for `"Turn on microphone"`). Second test PASSES (neither implementation returns `True` for `"Turn off microphone"`).

- [ ] **Step 3: Rewrite `meet.py` with `get_mute` override and no `max_version`**

Replace the full content of `micdot/conferencing/plugins/meet.py` with:

```python
from __future__ import annotations
import logging
from micdot.conferencing.ax_utils import AXPlugin

log = logging.getLogger("micdot")

_MEET_TITLE_FRAGMENT = "google meet"
_MUTE_SEARCH_KEYWORD = "microphone"


class MeetPlugin(AXPlugin):
    bundle_id = "com.google.Chrome"
    name = "Google Meet"

    def is_in_meeting(self) -> bool:
        app_el = self._get_app_element()
        if app_el is None:
            return False
        return self._find_meet_window(app_el) is not None

    def _find_meet_window(self, app_element):
        """Return the Chrome window showing a Google Meet tab, or None."""
        err, windows = self._get_attr(app_element, "AXWindows")
        if err != 0 or not windows:
            return None
        for w in windows:
            err_t, title = self._get_attr(w, "AXTitle")
            if err_t == 0 and _MEET_TITLE_FRAGMENT in (title or "").lower():
                return w
        return None

    def _find_mute_element(self, app_element):
        meet_window = self._find_meet_window(app_element)
        if meet_window is None:
            return None
        return self._walk(meet_window, "AXButton", _MUTE_SEARCH_KEYWORD, max_depth=20)

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
        # "Turn on microphone" → currently muted (clicking unmutes)
        # "Turn off microphone" → currently unmuted (clicking mutes)
        return "turn on" in title.lower()
```

- [ ] **Step 4: Run both `get_mute` tests to confirm both pass**

```bash
pytest tests/test_conferencing_plugins.py::TestMeetPlugin::test_get_mute_true_when_button_says_turn_on_microphone tests/test_conferencing_plugins.py::TestMeetPlugin::test_get_mute_false_when_button_says_turn_off_microphone -v
```

Expected: both PASS.

- [ ] **Step 5: Run the full `TestMeetPlugin` class to confirm no regressions**

```bash
pytest tests/test_conferencing_plugins.py::TestMeetPlugin -v
```

Expected: all 8 tests PASS (`test_bundle_ids_include_chrome_and_safari`, `test_name`, `test_get_mute_returns_none_when_not_in_meeting`, plus the 5 new ones).

- [ ] **Step 6: Run the full test suite**

```bash
pytest -v
```

Expected: all tests PASS.

- [ ] **Step 7: Commit**

```bash
git add micdot/conferencing/plugins/meet.py tests/test_conferencing_plugins.py
git commit -m "fix(meet): override get_mute with correct button label semantics, remove version cap"
```
