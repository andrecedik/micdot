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
            log.debug("ConferencingSync.on_mute_change: %s observing=%s in_meeting=%s", p.name, id(p) in self._observing, p.is_in_meeting())
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
