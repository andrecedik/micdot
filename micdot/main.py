from __future__ import annotations
import subprocess
import sys
import threading
from pathlib import Path
from typing import Callable

from micdot.audio.backend import get_backend
from micdot.config import Config, DEFAULT_CONFIG_PATH
from micdot.hotkey import HotkeyListener
from micdot.mqtt_client import MQTTClient
from micdot.poller import Poller
from micdot.tray import TrayIcon


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
    state.config = Config.load(config_path)
    state.mqtt.stop()
    state.mqtt = MQTTClient(state.config, on_button_press=on_toggle)
    state.mqtt.start()
    state.hotkey_listener.stop()
    state.hotkey_listener = HotkeyListener(state.config.hotkey, callback=on_toggle)
    state.hotkey_listener.start()


def main() -> None:
    config = Config.load(DEFAULT_CONFIG_PATH)
    backend = get_backend()

    def on_toggle() -> None:
        poller.toggle()

    def on_state_change(muted: bool) -> None:
        state.mqtt.publish_state(muted)
        tray.set_muted(muted)

    def on_quit() -> None:
        state.hotkey_listener.stop()
        poller.stop()
        state.mqtt.stop()
        sys.exit(0)

    def open_settings() -> None:
        proc = subprocess.Popen(
            [sys.executable, "-m", "micdot.settings_window", str(DEFAULT_CONFIG_PATH)]
        )
        threading.Thread(
            target=lambda: proc.wait() == 0 and _reload_config(
                state, DEFAULT_CONFIG_PATH, on_toggle
            ),
            daemon=True,
        ).start()

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
    tray.run()


if __name__ == "__main__":
    main()
