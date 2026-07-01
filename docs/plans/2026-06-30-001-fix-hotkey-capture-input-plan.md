---
title: "fix: Key-capture input for hotkey field in settings UI"
type: fix
date: 2026-06-30
---

# fix: Key-capture input for hotkey field in settings UI

## Summary

The hotkey field in the settings UI is a plain text input. Users can type arbitrary strings; nothing enforces that the value is a valid pynput hotkey. When a malformed string reaches `keyboard.HotKey.parse()` in `HotkeyListener`, it raises at runtime and the hotkey stops working. The field should intercept `keydown` events and format the pressed combination as `ctrl+shift+m`, and `Api.save()` should validate the string before persisting it.

## Requirements

**Input capture**

- R1. The hotkey field captures `keydown` events when focused and displays the pressed combination as `<modifiers>+<key>` (e.g. `ctrl+shift+m`).
- R2. At least one modifier key (`ctrl`, `shift`, `alt`, `cmd`) is required; bare key presses are ignored.
- R3. The captured string is accepted by `to_pynput_format()` and subsequently by `keyboard.HotKey.parse()`.
- R4. The field is readonly; free-text typing does not alter its value.

**Validation**

- R5. `Api.save()` validates the hotkey string before constructing `Config`. An invalid string causes the save to fail and the window to remain open.

## Key Technical Decisions

- KTD1: **`readonly` field + `keydown` listener.** The input is set `readonly` so no character insertion occurs. A `keydown` listener fires before the browser inserts text, reads modifier booleans and `event.key`, and sets the field value programmatically. `event.preventDefault()` suppresses default behavior for the captured event.

- KTD2: **`event.metaKey` maps to `cmd`.** On macOS the Command key exposes as `event.metaKey`. The stored name must be `cmd` to match `_MODIFIERS` in `hotkey.py`.

- KTD3: **Key name normalisation in JS.** `event.key` is lowercased for single characters. Known named keys map to pynput equivalents: `" "` → `space`, `"Enter"` → `enter`, `"Tab"` → `tab`, `"Backspace"` → `backspace`, `"F1"`–`"F12"` → `f1`–`f12`. Modifier key names (`"Control"`, `"Shift"`, `"Alt"`, `"Meta"`) trigger an early return — they are not treated as the target key.

- KTD4: **Server-side validation via try/except.** `Api.save()` imports `to_pynput_format` from `micdot.hotkey` and attempts `keyboard.HotKey.parse(to_pynput_format(hotkey))` inside a `try/except`. On failure it raises `ValueError` with a descriptive message. pywebview serialises this as a rejected Promise, which the existing JS `.catch()` handler catches to re-enable the Save button.

## Scope Boundaries

Deferred to follow-up work:
- Ability to clear / disable the hotkey (requires `HotkeyListener` to handle a no-op mode).
- Human-readable glyph display (e.g. `⌘⇧M`) — needs a separate rendering layer.
- Key conflict detection.

---

## Implementation Units

### U1. Key-capture JS and readonly hotkey input

**Goal:** Replace the free-text hotkey field with a capture-mode input that intercepts key presses and formats them correctly.

**Requirements:** R1, R2, R3, R4

**Dependencies:** none

**Files:**
- `micdot/settings_window.py`

**Approach:**
- Add `readonly` and `placeholder="click, then press hotkey…"` to `<input type="text" id="hotkey">`.
- Optionally add a CSS `cursor: default` or `cursor: pointer` hint to signal the field is capture-mode.
- After the existing event listeners (lines 145–148), attach a `keydown` listener on the hotkey field:
  - Call `event.preventDefault()`.
  - If `event.key` is a modifier name (`Control`, `Shift`, `Alt`, `Meta`), return early.
  - Collect active modifiers in order: `ctrl` (ctrlKey), `shift` (shiftKey), `alt` (altKey), `cmd` (metaKey).
  - Map `event.key` to a pynput-compatible name (KTD3).
  - If the resulting key name is empty or unknown, return early without updating the field.
  - Join parts with `+` and assign to `hotkeyInput.value`.

**Patterns to follow:** Existing listeners at `settings_window.py:145–148` use the same inline-JS event-listener style.

**Test scenarios:**
- Simulating `keydown` with Ctrl+Shift+M → field value becomes `ctrl+shift+m`.
- Simulating `keydown` with Meta+Space → field value becomes `cmd+space`.
- Simulating `keydown` with a bare letter (no modifiers) → field value unchanged.
- Simulating `keydown` with only a modifier key (`Shift`) → field value unchanged.
- Simulating `keydown` with Ctrl+F1 → field value becomes `ctrl+f1`.
- Verify `readonly` attribute is present on the rendered input.

*Note: these are client-side JS scenarios; the test file covers Python-side behaviour. Manual verification in the running app is the primary check for the JS capture logic. Consider adding a `_build_html` content assertion that the `readonly` attribute and `keydown` listener are present in the emitted HTML.*

**Verification:** Start the app, open Settings, click the hotkey field, press Ctrl+Shift+M, confirm the field shows `ctrl+shift+m`. Press Save and verify `~/.config/micdot/config.json` contains the correct value.

---

### U2. Server-side hotkey validation in `Api.save()`

**Goal:** Prevent malformed hotkey strings from reaching `keyboard.HotKey.parse()` at runtime by validating in `Api.save()` before writing config.

**Requirements:** R5

**Dependencies:** U1 (logic dependency; can be implemented in the same commit)

**Files:**
- `micdot/settings_window.py`
- `tests/test_settings_window.py`

**Approach:**
- Import `to_pynput_format` from `micdot.hotkey` and `keyboard` from `pynput` at the top of `settings_window.py`.
- At the start of `Api.save()`, before constructing `Config`, attempt:
  ```python
  keyboard.HotKey.parse(to_pynput_format(str(data["hotkey"])))
  ```
  inside `try/except (ValueError, Exception)`. On failure, log the error and `raise ValueError(f"Invalid hotkey: {data['hotkey']!r}")`.
- The existing JS `.catch()` at line 167 already handles a rejected Promise by re-enabling the Save button — no JS changes needed for this unit.

**Patterns to follow:** The existing `open_url` validation in `Api.open_url()` shows the log-and-return-early pattern for bad input; this unit uses the same structure but raises instead of returning to propagate the error to the JS caller.

**Test scenarios:**
- `Api.save()` with `hotkey="ctrl+shift+m"` → succeeds, config saved, `api.saved` is True.
- `Api.save()` with `hotkey="cmd+space"` → succeeds.
- `Api.save()` with `hotkey="ctrl+f1"` → succeeds.
- `Api.save()` with `hotkey="not!!!valid"` → raises `ValueError`, `api.saved` remains False.
- `Api.save()` with `hotkey=""` (empty string) → raises `ValueError`.
- `Api.save()` with `hotkey="m"` (no modifier) → raises `ValueError` (pynput rejects bare keys in `HotKey.parse`).

**Verification:** `pytest tests/test_settings_window.py` passes, including new invalid-hotkey test cases.
