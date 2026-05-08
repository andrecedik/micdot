from __future__ import annotations
import subprocess
import sys
import threading
from pathlib import Path
from typing import Callable

from micdot.audio.backend import get_backend
from micdot.config import Config, DEFAULT_CONFIG_PATH
from micdot.hotkey import HotkeyListener
from micdot.log import setup as setup_logging
from micdot.mqtt_client import MQTTClient
from micdot.poller import Poller
from micdot.tray import TrayIcon

log = setup_logging()


class _State:
    __slots__ = ("config", "mqtt", "hotkey_listener")

    def __init__(
        self,
        config: Config,
        mqtt: MQTTClient,
        hotkey_listener: HotkeyListener,
    ) -> None:
        self.config = config
        self.mqtt = mqtt
        self.hotkey_listener = hotkey_listener


def _reload_config(
    state: _State,
    config_path: Path,
    on_toggle: Callable[[], None],
) -> None:
    log.info("Reloading config from %s", config_path)
    new_config = Config.load(config_path)
    try:
        new_mqtt = MQTTClient(new_config, on_button_press=on_toggle)
        new_hotkey = HotkeyListener(new_config.hotkey, callback=on_toggle)
    except Exception:
        log.exception("Failed to construct components during reload — keeping existing config")
        return
    state.mqtt.stop()
    state.mqtt = new_mqtt
    state.mqtt.start()
    state.hotkey_listener.stop()
    state.hotkey_listener = new_hotkey
    state.hotkey_listener.start()
    state.config = new_config
    log.info("Config reloaded")


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

    def on_quit() -> None:
        log.info("Quit requested")
        state.hotkey_listener.stop()
        poller.stop()
        state.mqtt.stop()
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
                _reload_config(state, DEFAULT_CONFIG_PATH, on_toggle)

        threading.Thread(target=_on_exit, daemon=True).start()

    state = _State(
        config,
        MQTTClient(config, on_button_press=on_toggle),
        HotkeyListener(config.hotkey, callback=on_toggle),
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
    log.info("MicDot running")
    tray.run()


if __name__ == "__main__":
    main()
