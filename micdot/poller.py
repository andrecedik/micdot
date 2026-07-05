from __future__ import annotations
import logging
import threading
from typing import Callable, Optional
from micdot.audio.backend import AudioBackend

log = logging.getLogger("micdot")


class Poller:
    def __init__(self, backend: AudioBackend, on_change: Callable[[bool], None]):
        self._backend = backend
        self._on_change = on_change
        self._last_state: Optional[bool] = None
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._error_logged = False

    def tick(self) -> None:
        changed = False
        value: Optional[bool] = None
        with self._lock:
            try:
                current = self._backend.get_mute()
            except OSError as exc:
                # The device may lack a HAL mute control or have just been
                # unplugged. Log once per episode — tick runs every 200 ms.
                if not self._error_logged:
                    log.warning("Could not read mic mute state: %s", exc)
                    self._error_logged = True
                return
            self._error_logged = False
            if current != self._last_state:
                self._last_state = current
                changed = True
                value = current
        if changed:
            self._on_change(value)

    def toggle(self) -> None:
        with self._lock:
            try:
                self._backend.set_mute(not self._backend.get_mute())
            except OSError as exc:
                # Runs inside pynput/MQTT/tray callbacks — an uncaught error
                # here would kill the hotkey listener thread.
                log.warning("Could not toggle mic mute: %s", exc)

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
