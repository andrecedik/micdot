from __future__ import annotations
import threading
from typing import Callable, Optional
from espmuter.audio.backend import AudioBackend


class Poller:
    def __init__(self, backend: AudioBackend, on_change: Callable[[bool], None]):
        self._backend = backend
        self._on_change = on_change
        self._last_state: Optional[bool] = None
        self._lock = threading.Lock()
        self._stop = threading.Event()

    def tick(self) -> None:
        changed = False
        value: Optional[bool] = None
        with self._lock:
            current = self._backend.get_mute()
            if current != self._last_state:
                self._last_state = current
                changed = True
                value = current
        if changed:
            self._on_change(value)

    def toggle(self) -> None:
        with self._lock:
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
