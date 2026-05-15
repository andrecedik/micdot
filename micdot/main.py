from __future__ import annotations
import subprocess
import sys
import threading
from pathlib import Path
from typing import Callable

from micdot.audio.backend import get_backend, AudioBackend
from micdot.config import Config, DEFAULT_CONFIG_PATH
from micdot.hotkey import HotkeyListener
from micdot.log import setup as setup_logging
from micdot.mqtt_client import MQTTClient
from micdot.poller import Poller
from micdot.tray import TrayIcon
from micdot.conferencing import ConferencingSync, PLUGINS

log = setup_logging()


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
    if new_config.conferencing_sync_enabled and _ax_is_trusted():
        new_sync.start()
    state.conferencing_sync = new_sync

    # HotKey construction calls TISCopyCurrentKeyboardInputSource which asserts
    # dispatch_assert_queue(main_queue) on macOS 15+. Dispatch to main thread.
    # The Listener thread is NOT restarted — only the HotKey matching object is
    # swapped — so Listener._run()/keycode_context() never runs again after NSApp.
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


def _ax_is_trusted() -> bool:
    try:
        from ApplicationServices import AXIsProcessTrusted
        return bool(AXIsProcessTrusted())
    except Exception:
        return False


def _check_accessibility(config: Config) -> None:
    if not config.conferencing_sync_enabled:
        return
    if _ax_is_trusted():
        return
    log.warning(
        "Accessibility permission not granted — conferencing sync disabled. "
        "Grant it in System Settings → Privacy & Security → Accessibility, then restart MicDot."
    )
    try:
        subprocess.run(
            ["osascript", "-e",
             'display notification "Grant Accessibility access in System Settings to enable '
             'conferencing sync, then restart MicDot." with title "MicDot"'],
            check=False,
        )
    except Exception:
        pass


def _settings_cmd(config_path: Path) -> list[str]:
    if getattr(sys, "frozen", False):
        return [sys.executable, "--settings", str(config_path)]
    return [sys.executable, "-m", "micdot.settings_window", str(config_path)]


def main() -> None:
    if getattr(sys, "frozen", False) and "--settings" in sys.argv:
        idx = sys.argv.index("--settings")
        path = Path(sys.argv[idx + 1]) if idx + 1 < len(sys.argv) else DEFAULT_CONFIG_PATH
        from micdot.settings_window import run as run_settings
        run_settings(path)
        return

    log.info("MicDot starting")
    config = Config.load(DEFAULT_CONFIG_PATH)
    log.info("Config loaded (mqtt_host=%r, hotkey=%r)", config.mqtt_host, config.hotkey)
    backend = get_backend()
    log.info("Audio backend: %s", type(backend).__name__)

    def on_toggle() -> None:
        poller.toggle()

    def on_state_change(muted: bool) -> None:
        log.debug("Mic state changed: muted=%s", muted)
        state.mqtt.publish_state(muted)
        tray.set_muted(muted)
        state.conferencing_sync.on_mute_change(muted)

    def on_quit() -> None:
        log.info("Quit requested")
        state.hotkey_listener.stop()
        poller.stop()
        state.mqtt.stop()
        state.conferencing_sync.stop()
        sys.exit(0)

    settings_proc: list[subprocess.Popen | None] = [None]

    def open_settings() -> None:
        if settings_proc[0] is not None and settings_proc[0].poll() is None:
            return
        log.info("Opening settings window")
        settings_proc[0] = subprocess.Popen(_settings_cmd(DEFAULT_CONFIG_PATH))

        def _on_exit() -> None:
            rc = settings_proc[0].wait() if settings_proc[0] else 1
            if rc == 0:
                try:
                    _reload_config(state, DEFAULT_CONFIG_PATH, on_toggle, backend)
                except Exception:
                    log.exception("Uncaught error during config reload")

        threading.Thread(target=_on_exit, daemon=True).start()

    _check_accessibility(config)
    conferencing_sync = ConferencingSync(PLUGINS, backend)
    state = _State(
        config,
        MQTTClient(config, on_button_press=on_toggle),
        HotkeyListener(config.hotkey, callback=on_toggle),
        conferencing_sync,
    )
    poller = Poller(backend, on_change=on_state_change)
    tray = TrayIcon(
        on_toggle=on_toggle,
        on_settings=open_settings,
        on_quit=on_quit,
    )

    state.mqtt.start()
    poller.start()
    state.hotkey_listener.start()
    if config.conferencing_sync_enabled and _ax_is_trusted():
        conferencing_sync.start()
        log.info("Conferencing sync started")
    log.info("MicDot running")
    tray.run()


if __name__ == "__main__":
    main()
