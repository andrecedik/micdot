from __future__ import annotations
import logging
from micdot.conferencing.ax_utils import AXPlugin

log = logging.getLogger("micdot")

_MEET_URL_FRAGMENT = "meet.google.com"
_MUTE_SEARCH_KEYWORD = "mute"


class MeetPlugin(AXPlugin):
    bundle_id = "com.google.Chrome"
    name = "Google Meet"
    max_version = "136.99.99"

    def is_in_meeting(self) -> bool:
        app_el = self._get_app_element()
        if app_el is None:
            return False
        meet_window = self._find_meet_window(app_el)
        return meet_window is not None

    def _find_meet_window(self, app_element):
        """Return the Chrome window showing a Google Meet tab, or None."""
        err, windows = self._get_attr(app_element, "AXWindows")
        if err != 0 or not windows:
            return None
        for w in windows:
            err_t, title = self._get_attr(w, "AXTitle")
            if err_t == 0 and _MEET_URL_FRAGMENT in (title or "").lower():
                return w
        return None

    def _find_mute_element(self, app_element):
        meet_window = self._find_meet_window(app_element)
        if meet_window is None:
            return None
        # Chrome's tree is deep. Limit depth to avoid long traversal times.
        return self._walk(meet_window, "AXButton", _MUTE_SEARCH_KEYWORD, max_depth=20)
