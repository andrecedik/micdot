"""Run as: python -m micdot.settings_window [config_path]"""
from __future__ import annotations
import json
import shutil
import sys
from dataclasses import asdict
from pathlib import Path

from micdot.autostart import enable_autostart, disable_autostart
from micdot.config import Config, DEFAULT_CONFIG_PATH


class Api:
    def __init__(self, config_path: Path) -> None:
        self._config_path = config_path
        self._saved = False
        self._window = None

    @property
    def saved(self) -> bool:
        return self._saved

    def set_window(self, window) -> None:
        self._window = window

    def save(self, data: dict) -> None:
        new = Config(
            mqtt_host=str(data["mqtt_host"]),
            mqtt_port=int(data["mqtt_port"]),
            mqtt_username=str(data["mqtt_username"]),
            mqtt_password=str(data["mqtt_password"]),
            hotkey=str(data["hotkey"]),
            led_brightness=int(data["led_brightness"]),
            color_muted={
                "r": int(data["color_muted"]["r"]),
                "g": int(data["color_muted"]["g"]),
                "b": int(data["color_muted"]["b"]),
            },
            color_unmuted={
                "r": int(data["color_unmuted"]["r"]),
                "g": int(data["color_unmuted"]["g"]),
                "b": int(data["color_unmuted"]["b"]),
            },
            autostart=bool(data["autostart"]),
        )
        new.save(self._config_path)
        if new.autostart:
            python = shutil.which("python3") or sys.executable
            enable_autostart(f"{python} -m micdot.main")
        else:
            disable_autostart()
        self._saved = True
        if self._window is not None:
            self._window.destroy()


_HTML = ""  # filled in Task 3


def run(config_path: Path) -> None:
    raise NotImplementedError("pywebview run() added in Task 3")


if __name__ == "__main__":
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_CONFIG_PATH
    run(path)
