from __future__ import annotations
import logging
import plistlib
import threading
from abc import abstractmethod
from collections.abc import Callable
from pathlib import Path

from micdot.conferencing.base import ConferencingPlugin

log = logging.getLogger("micdot")

# AXTitle value semantics for mute buttons:
# When the user IS muted  → button says "Unmute" (clicking it would unmute)
# When the user is NOT muted → button says "Mute"   (clicking it would mute)
# So: "unmute" in title.lower() → currently muted.
_MUTED_KEYWORD = "unmute"


class AXPlugin(ConferencingPlugin):
    """Base class for plugins that use the macOS Accessibility API.

    Subclasses must implement:
      - bundle_id, name  (class attributes)
      - _find_mute_element(app_element) -> AX element or None
      - is_in_meeting() -> bool
    """

    def __init__(self) -> None:
        self._on_change: Callable[[bool], None] | None = None
        self._stop_event = threading.Event()
        self._last_mute: bool | None = None

    # ------------------------------------------------------------------ #
    # Version / running detection
    # ------------------------------------------------------------------ #

    def _get_installed_version(self) -> str | None:
        try:
            from AppKit import NSWorkspace
            url = NSWorkspace.sharedWorkspace().URLForApplicationWithBundleIdentifier_(
                self.bundle_id
            )
            if url is None:
                return None
            plist_path = Path(url.path()) / "Contents" / "Info.plist"
            data = plistlib.loads(plist_path.read_bytes())
            return data.get("CFBundleShortVersionString")
        except Exception:
            log.debug("Could not read version for %s", self.bundle_id, exc_info=True)
            return None

    def is_running(self) -> bool:
        try:
            from AppKit import NSRunningApplication
            apps = NSRunningApplication.runningApplicationsWithBundleIdentifier_(
                self.bundle_id
            )
            return len(apps) > 0
        except Exception:
            return False

    def _get_app_pid(self) -> int | None:
        try:
            from AppKit import NSRunningApplication
            apps = NSRunningApplication.runningApplicationsWithBundleIdentifier_(
                self.bundle_id
            )
            return apps[0].processIdentifier() if apps else None
        except Exception:
            return None

    # ------------------------------------------------------------------ #
    # AX element helpers
    # ------------------------------------------------------------------ #

    def _get_app_element(self):
        """Return the root AXUIElement for this app, or None."""
        pid = self._get_app_pid()
        if pid is None:
            return None
        try:
            from ApplicationServices import AXUIElementCreateApplication
            return AXUIElementCreateApplication(pid)
        except Exception:
            log.debug("AXUIElementCreateApplication failed for %s", self.name, exc_info=True)
            return None

    def _get_attr(self, element, attribute: str):
        """Return (error_code, value) for an AX attribute. error_code == 0 means success."""
        try:
            from ApplicationServices import AXUIElementCopyAttributeValue
            return AXUIElementCopyAttributeValue(element, attribute, None)
        except Exception:
            return (-1, None)

    def _walk(self, element, role: str, keyword: str, max_depth: int = 12):
        """DFS through the AX tree. Returns the first AXButton whose AXTitle
        contains `keyword` (case-insensitive), or None."""
        if max_depth == 0:
            return None
        err_role, elem_role = self._get_attr(element, "AXRole")
        err_title, elem_title = self._get_attr(element, "AXTitle")
        if (
            err_role == 0
            and err_title == 0
            and elem_role == role
            and keyword.lower() in (elem_title or "").lower()
        ):
            return element
        err_ch, children = self._get_attr(element, "AXChildren")
        if err_ch == 0 and children:
            for child in children:
                result = self._walk(child, role, keyword, max_depth - 1)
                if result is not None:
                    return result
        return None

    def _read_title(self, element) -> str | None:
        err, title = self._get_attr(element, "AXTitle")
        return title if err == 0 else None

    def _press(self, element) -> bool:
        try:
            from ApplicationServices import AXUIElementPerformAction
            err = AXUIElementPerformAction(element, "AXPress")
            return err == 0
        except Exception:
            log.debug("AXUIElementPerformAction failed for %s", self.name, exc_info=True)
            return False

    # ------------------------------------------------------------------ #
    # Subclass contract
    # ------------------------------------------------------------------ #

    @abstractmethod
    def _find_mute_element(self, app_element):
        """Return the mute/unmute AXButton element, or None if not in a meeting."""
        ...

    # ------------------------------------------------------------------ #
    # ConferencingPlugin implementation
    # ------------------------------------------------------------------ #

    def get_mute(self) -> bool | None:
        if not self.is_running() or not self.is_in_meeting():
            return None
        app_el = self._get_app_element()
        if app_el is None:
            return None
        mute_el = self._find_mute_element(app_el)
        if mute_el is None:
            return None
        title = self._read_title(mute_el)
        if title is None:
            return None
        return _MUTED_KEYWORD in title.lower()

    def set_mute(self, muted: bool) -> None:
        if not self.is_running() or not self.is_in_meeting():
            return
        current = self.get_mute()
        if current is None or current == muted:
            return
        app_el = self._get_app_element()
        if app_el is None:
            return
        mute_el = self._find_mute_element(app_el)
        if mute_el is None:
            log.warning("%s: mute element not found", self.name)
            return
        if not self._press(mute_el):
            log.warning("%s: AXPress on mute element failed", self.name)

    # ------------------------------------------------------------------ #
    # Observation — 250ms poll loop
    # ------------------------------------------------------------------ #

    def start_observing(self, on_change: Callable[[bool], None]) -> None:
        self._on_change = on_change
        self._stop_event.clear()
        self._last_mute = None
        threading.Thread(
            target=self._poll_loop, daemon=True, name=f"ax-poll-{self.name}"
        ).start()

    def stop_observing(self) -> None:
        self._stop_event.set()
        self._on_change = None

    def _poll_loop(self) -> None:
        while not self._stop_event.wait(0.25):
            if not self.is_running() or not self.is_in_meeting():
                self._last_mute = None
                continue
            try:
                current = self.get_mute()
            except Exception:
                log.debug("%s: error reading mute state", self.name, exc_info=True)
                continue
            if current is not None and current != self._last_mute:
                self._last_mute = current
                cb = self._on_change
                if cb:
                    cb(current)
