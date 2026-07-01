from __future__ import annotations
import sys
from typing import Callable
import pystray
from PIL import Image, ImageDraw


def _make_icon(color: tuple[int, int, int]) -> Image.Image:
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([4, 4, 60, 60], fill=(*color, 255))
    return img


def _hide_dock_icon() -> None:
    try:
        import AppKit
        AppKit.NSApp.setActivationPolicy_(
            AppKit.NSApplicationActivationPolicyAccessory
        )
    except Exception:
        pass


class TrayIcon:
    def __init__(
        self,
        on_toggle: Callable[[], None],
        on_settings: Callable[[], None],
        on_about: Callable[[], None],
        on_quit: Callable[[], None],
    ):
        self._on_toggle = on_toggle
        self._on_settings = on_settings
        self._on_about = on_about
        self._on_quit = on_quit
        self._icon = pystray.Icon(
            "micdot",
            _make_icon((128, 128, 128)),
            menu=pystray.Menu(
                pystray.MenuItem("Toggle Mute", self._toggle, default=True),
                pystray.MenuItem("Settings", self._settings),
                pystray.MenuItem("About", self._about),
                pystray.Menu.SEPARATOR,
                pystray.MenuItem("Quit", self._quit),
            ),
        )
        if sys.platform == "darwin":
            status_item = getattr(self._icon, "_status_item", None)
            if status_item is not None:
                status_item.setAutosaveName_("MicDot")

    def set_muted(self, muted: bool) -> None:
        self._icon.icon = _make_icon((0, 200, 0) if muted else (200, 0, 0))

    def run(self) -> None:
        if sys.platform == "darwin":
            _hide_dock_icon()
        self._icon.run()

    def stop(self) -> None:
        self._icon.stop()

    def _toggle(self, icon, item) -> None:
        self._on_toggle()

    def _settings(self, icon, item) -> None:
        self._on_settings()

    def _about(self, icon, item) -> None:
        self._on_about()

    def _quit(self, icon, item) -> None:
        self.stop()
        self._on_quit()
