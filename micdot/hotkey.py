from __future__ import annotations
from typing import Callable
from pynput import keyboard

_MODIFIERS = {"ctrl", "shift", "alt", "cmd"}


def to_pynput_format(hotkey: str) -> str:
    return "+".join(
        f"<{p.lower()}>" if len(p) != 1 else p.lower()
        for p in hotkey.split("+")
    )


class HotkeyListener:
    """Long-lived pynput Listener whose active HotKey is swappable at runtime.

    The Listener thread is started once (start()) and kept alive for the
    process lifetime. Only the HotKey matching object is replaced via update(),
    avoiding a restart of the background thread.

    This is required on macOS 15+ (Sequoia): Listener._run() calls
    keycode_context() → TISCopyCurrentKeyboardInputSource(), which asserts
    dispatch_assert_queue(main_queue). Restarting the Listener after NSApp is
    running triggers that assertion and crashes the process. Keeping the
    original thread avoids it entirely.
    """

    def __init__(self, hotkey: str, callback: Callable[[], None]):
        self._hotkey_str = to_pynput_format(hotkey)
        self._callback = callback
        self._hotkey: keyboard.HotKey | None = None
        self._listener: keyboard.Listener | None = None

    def _on_press(self, key) -> None:
        # canonical() strips modifier effects from the key (shift+m arrives as
        # 'M' on macOS) and folds cmd_l/cmd_r into cmd — without it, HotKey
        # never matches combos that include shift.
        if self._hotkey is not None and self._listener is not None:
            self._hotkey.press(self._listener.canonical(key))

    def _on_release(self, key) -> None:
        if self._hotkey is not None and self._listener is not None:
            self._hotkey.release(self._listener.canonical(key))

    def start(self) -> None:
        self._hotkey = keyboard.HotKey(
            keyboard.HotKey.parse(self._hotkey_str),
            self._callback,
        )
        self._listener = keyboard.Listener(
            on_press=self._on_press,
            on_release=self._on_release,
        )
        self._listener.start()

    def update(self, hotkey: str, callback: Callable[[], None]) -> None:
        """Swap the active hotkey without restarting the listener thread.

        On macOS 15+, call from the main thread — KeyCode construction may
        invoke TISCopyCurrentKeyboardInputSource, which requires the main queue.
        """
        self._hotkey_str = to_pynput_format(hotkey)
        self._callback = callback
        self._hotkey = keyboard.HotKey(
            keyboard.HotKey.parse(self._hotkey_str),
            callback,
        )

    def stop(self) -> None:
        if self._listener:
            self._listener.stop()
            self._listener.join(timeout=2.0)
