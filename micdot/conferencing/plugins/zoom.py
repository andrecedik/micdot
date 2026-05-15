from __future__ import annotations
import logging
from micdot.conferencing.ax_utils import AXPlugin

log = logging.getLogger("micdot")

# The Zoom meeting toolbar window title contains this string.
_ZOOM_TOOLBAR_TITLE = "Zoom Meeting"
# The mute button AXTitle when the user is NOT muted (clicking mutes).
# When muted, the title contains "Unmute" — which _MUTED_KEYWORD in ax_utils catches.
# Verify these against a live meeting if they change across Zoom versions.
_MUTE_SEARCH_KEYWORD = "mute"


class ZoomPlugin(AXPlugin):
    bundle_id = "com.zoom.xpc"
    name = "Zoom"
    min_version = "5.0.0"
    max_version = "6.99.99"

    def is_in_meeting(self) -> bool:
        app_el = self._get_app_element()
        if app_el is None:
            return False
        # Zoom shows a floating toolbar window during meetings.
        # We detect it by looking for a window whose AXTitle contains the meeting keyword.
        err, windows = self._get_attr(app_el, "AXWindows")
        if err != 0 or not windows:
            return False
        for w in windows:
            err_t, title = self._get_attr(w, "AXTitle")
            if err_t == 0 and _ZOOM_TOOLBAR_TITLE in (title or ""):
                return True
        return False

    def _find_mute_element(self, app_element):
        """Search the AX tree for a button whose title contains 'mute' (case-insensitive)."""
        return self._walk(app_element, "AXButton", _MUTE_SEARCH_KEYWORD)
