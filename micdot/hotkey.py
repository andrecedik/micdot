from __future__ import annotations
from typing import Callable
from pynput import keyboard

_MODIFIERS = {"ctrl", "shift", "alt", "cmd"}


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
            self._listener.join(timeout=2.0)
