from __future__ import annotations
import subprocess
import sys
from pathlib import Path

from espmuter.audio.backend import get_backend
from espmuter.config import Config, DEFAULT_CONFIG_PATH
from espmuter.hotkey import HotkeyListener
from espmuter.mqtt_client import MQTTClient
from espmuter.poller import Poller
from espmuter.tray import TrayIcon


def main() -> None:
    config = Config.load(DEFAULT_CONFIG_PATH)
    backend = get_backend()

    def on_toggle() -> None:
        poller.toggle()

    def on_state_change(muted: bool) -> None:
        mqtt.publish_state(muted)
        tray.set_muted(muted)

    def on_quit() -> None:
        hotkey_listener.stop()
        poller.stop()
        mqtt.stop()
        sys.exit(0)

    poller = Poller(backend, on_change=on_state_change)
    mqtt = MQTTClient(config, on_button_press=on_toggle)
    tray = TrayIcon(
        on_toggle=on_toggle,
        on_settings=lambda: subprocess.Popen(
            [sys.executable, "-m", "espmuter.settings_window", str(DEFAULT_CONFIG_PATH)]
        ),
        on_quit=on_quit,
    )
    hotkey_listener = HotkeyListener(config.hotkey, callback=on_toggle)

    mqtt.start()
    poller.start()
    hotkey_listener.start()
    tray.run()  # blocks main thread until quit


if __name__ == "__main__":
    main()
