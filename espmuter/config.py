from __future__ import annotations
import json
from dataclasses import dataclass, field, asdict
from pathlib import Path

DEFAULT_CONFIG_PATH = Path.home() / ".config" / "espmuter" / "config.json"


@dataclass
class Config:
    mqtt_host: str = ""
    mqtt_port: int = 1883
    mqtt_username: str = ""
    mqtt_password: str = ""
    color_muted: dict = field(default_factory=lambda: {"r": 0, "g": 255, "b": 0})
    color_unmuted: dict = field(default_factory=lambda: {"r": 255, "g": 0, "b": 0})
    led_brightness: int = 128
    hotkey: str = "ctrl+shift+m"
    autostart: bool = False

    def save(self, path: Path = DEFAULT_CONFIG_PATH) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path = DEFAULT_CONFIG_PATH) -> "Config":
        if not path.exists():
            return cls()
        data = json.loads(path.read_text(encoding="utf-8"))
        defaults = asdict(cls())
        defaults.update(data)
        return cls(**{k: defaults[k] for k in defaults})
