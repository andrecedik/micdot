from __future__ import annotations
import logging
import subprocess
import time
from micdot.conferencing.ax_utils import AXPlugin

log = logging.getLogger("micdot")

_ZOOM_TOOLBAR_TITLE = "Zoom Meeting"
# AXDescription on the mute button:
#   unmuted → "Mute" (or "Mute audio")   → clicking it mutes
#   muted   → "Unmute" (or "Unmute audio") → clicking it unmutes
_MUTE_BTN_KEYWORD = "mute"   # present in both "Mute" and "Unmute"
_MUTED_KEYWORD = "unmute"    # only present when currently muted

# PID cache TTL — re-enumerate Zoom child processes every N seconds.
_PID_CACHE_TTL = 5.0


class ZoomPlugin(AXPlugin):
    bundle_id = "us.zoom.xos"
    name = "Zoom"
    min_version = "5.0.0"

    def __init__(self) -> None:
        super().__init__()
        self._cached_pids: list[int] = []
        self._pids_at: float = 0.0
        self._dump_done: bool = False

    # ------------------------------------------------------------------ #
    # Meeting detection
    # ------------------------------------------------------------------ #

    def is_in_meeting(self) -> bool:
        app_el = self._get_app_element()
        if app_el is None:
            return False
        err, windows = self._get_attr(app_el, "AXWindows")
        if err != 0 or not windows:
            return False
        for w in windows:
            err_t, title = self._get_attr(w, "AXTitle")
            if err_t == 0 and _ZOOM_TOOLBAR_TITLE in (title or ""):
                return True
        return False

    # ------------------------------------------------------------------ #
    # Multi-process AX element enumeration
    # ------------------------------------------------------------------ #

    def _get_zoom_pids(self) -> list[int]:
        """PIDs of all zoom.us.app processes (main + CptHost + caphost…), cached."""
        now = time.monotonic()
        if now - self._pids_at < _PID_CACHE_TTL:
            return self._cached_pids
        try:
            out = subprocess.run(
                ["pgrep", "-f", "zoom.us.app"],
                capture_output=True, text=True, timeout=0.5,
            ).stdout
            self._cached_pids = [int(p) for p in out.split() if p.strip().isdigit()]
        except Exception:
            log.debug("ZoomPlugin: pgrep failed", exc_info=True)
            self._cached_pids = []
        self._pids_at = now
        return self._cached_pids

    def _all_zoom_elements(self):
        """Yield an AX app element for every Zoom process."""
        from ApplicationServices import AXUIElementCreateApplication
        for pid in self._get_zoom_pids():
            try:
                yield AXUIElementCreateApplication(pid)
            except Exception:
                pass

    # ------------------------------------------------------------------ #
    # AX tree search by AXDescription (Zoom 7.x has title=None on buttons)
    # ------------------------------------------------------------------ #

    def _walk_desc(self, element, role: str, keyword: str, max_depth: int = 12):
        """DFS: return first element of `role` whose AXDescription contains `keyword`."""
        if max_depth == 0:
            return None
        err_r, elem_role = self._get_attr(element, "AXRole")
        err_d, elem_desc = self._get_attr(element, "AXDescription")
        if (
            err_r == 0 and err_d == 0
            and elem_role == role
            and keyword.lower() in (elem_desc or "").lower()
        ):
            return element
        err_ch, children = self._get_attr(element, "AXChildren")
        if err_ch == 0 and children:
            for child in children:
                result = self._walk_desc(child, role, keyword, max_depth - 1)
                if result is not None:
                    return result
        return None

    def _find_mute_element(self, app_element):
        # app_element (main process) is tried first; then CptHost / caphost.
        for el in self._all_zoom_elements():
            btn = self._walk_desc(el, "AXButton", _MUTE_BTN_KEYWORD)
            if btn is not None:
                return btn
        return None

    # ------------------------------------------------------------------ #
    # Mute state
    # ------------------------------------------------------------------ #

    def get_mute(self) -> bool | None:
        if not self.is_running() or not self.is_in_meeting():
            return None
        btn = self._find_mute_element(None)
        if btn is None:
            if not self._dump_done:
                log.debug("ZoomPlugin: mute button not found — dumping all Zoom buttons")
                for el in self._all_zoom_elements():
                    self._dump_walk(el, 12)
                self._dump_done = True
            return None
        self._dump_done = False  # reset so a future loss is re-logged
        err_d, desc = self._get_attr(btn, "AXDescription")
        if err_d != 0 or not desc:
            return None
        return _MUTED_KEYWORD in desc.lower()

    def set_mute(self, muted: bool) -> None:
        if not self.is_running() or not self.is_in_meeting():
            return
        current = self.get_mute()
        if current is None or current == muted:
            return
        btn = self._find_mute_element(None)
        if btn is None:
            log.warning("ZoomPlugin: mute button not found, cannot set mute")
            return
        if not self._press(btn):
            log.warning("ZoomPlugin: AXPress on mute button failed")

    # ------------------------------------------------------------------ #
    # Diagnostics
    # ------------------------------------------------------------------ #

    def _dump_walk(self, element, depth: int) -> None:
        if depth == 0:
            return
        err_r, role = self._get_attr(element, "AXRole")
        if err_r == 0 and role == "AXButton":
            _, title = self._get_attr(element, "AXTitle")
            _, desc = self._get_attr(element, "AXDescription")
            _, help_ = self._get_attr(element, "AXHelp")
            _, val = self._get_attr(element, "AXValue")
            log.debug(
                "ZoomPlugin button: title=%r desc=%r help=%r value=%r",
                title, desc, help_, val,
            )
        err_ch, children = self._get_attr(element, "AXChildren")
        if err_ch == 0 and children:
            for child in children:
                self._dump_walk(child, depth - 1)
