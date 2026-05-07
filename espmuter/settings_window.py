"""Run as: python -m espmuter.settings_window [config_path]"""
from __future__ import annotations
import shutil
import sys
import tkinter as tk
from tkinter import ttk
from pathlib import Path
from espmuter.config import Config, DEFAULT_CONFIG_PATH


def _hex(color: dict) -> str:
    return "#{r:02x}{g:02x}{b:02x}".format(**color)


def _from_hex(h: str) -> dict:
    h = h.lstrip("#")
    return {"r": int(h[0:2], 16), "g": int(h[2:4], 16), "b": int(h[4:6], 16)}


def run(config_path: Path) -> None:
    config = Config.load(config_path)
    root = tk.Tk()
    root.title("ESPMuter Settings")
    root.resizable(False, False)

    f = ttk.Frame(root, padding=16)
    f.grid(sticky="nsew")

    def add_row(label: str, var: tk.Variable, r: int, **kw) -> None:
        ttk.Label(f, text=label).grid(row=r, column=0, sticky="w", pady=4)
        ttk.Entry(f, textvariable=var, **kw).grid(row=r, column=1, sticky="ew", padx=(8, 0))

    mqtt_host = tk.StringVar(value=config.mqtt_host)
    mqtt_port = tk.IntVar(value=config.mqtt_port)
    mqtt_user = tk.StringVar(value=config.mqtt_username)
    mqtt_pass = tk.StringVar(value=config.mqtt_password)
    hotkey = tk.StringVar(value=config.hotkey)
    brightness = tk.IntVar(value=config.led_brightness)
    color_muted = tk.StringVar(value=_hex(config.color_muted))
    color_unmuted = tk.StringVar(value=_hex(config.color_unmuted))
    autostart = tk.BooleanVar(value=config.autostart)

    add_row("MQTT Host", mqtt_host, 0)
    add_row("MQTT Port", mqtt_port, 1, width=8)
    add_row("MQTT Username", mqtt_user, 2)
    add_row("MQTT Password", mqtt_pass, 3, show="*")
    add_row("Hotkey", hotkey, 4)
    add_row("LED Brightness (0-255)", brightness, 5, width=8)
    add_row("Color Muted (hex)", color_muted, 6)
    add_row("Color Unmuted (hex)", color_unmuted, 7)

    ttk.Label(f, text="Autostart on login").grid(row=8, column=0, sticky="w", pady=4)
    ttk.Checkbutton(f, variable=autostart).grid(row=8, column=1, sticky="w", padx=(8, 0))

    def save() -> None:
        from espmuter.autostart import enable_autostart, disable_autostart
        new = Config(
            mqtt_host=mqtt_host.get(),
            mqtt_port=mqtt_port.get(),
            mqtt_username=mqtt_user.get(),
            mqtt_password=mqtt_pass.get(),
            hotkey=hotkey.get(),
            led_brightness=brightness.get(),
            color_muted=_from_hex(color_muted.get()),
            color_unmuted=_from_hex(color_unmuted.get()),
            autostart=autostart.get(),
        )
        new.save(config_path)
        if new.autostart:
            python = shutil.which("python3") or sys.executable
            enable_autostart(f"{python} -m espmuter.main")
        else:
            disable_autostart()
        root.destroy()

    ttk.Button(f, text="Save", command=save).grid(
        row=9, column=0, columnspan=2, pady=(16, 0)
    )
    f.columnconfigure(1, weight=1)
    root.mainloop()


if __name__ == "__main__":
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_CONFIG_PATH
    run(path)
