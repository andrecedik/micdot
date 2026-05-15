from __future__ import annotations
import logging
from micdot.conferencing.ax_utils import AXPlugin

log = logging.getLogger("micdot")

# The call-controls toolbar is an AXGroup. Searching for "mute" keyword in
# AXButton AXTitle works for both "Mute microphone" and "Unmute microphone".
# Verify against a live Teams call — Electron AX trees change more often than
# native apps. Bump max_version when re-verified.
_MUTE_SEARCH_KEYWORD = "mute"
# Teams shows a call-controls bar identified by a group containing a mute button.
# We detect "in meeting" by checking whether such a button exists at all.


class TeamsPlugin(AXPlugin):
    bundle_id = "com.microsoft.teams2"
    name = "Microsoft Teams"
    min_version = "23.0.0"
    max_version = "25.99.99"

    def is_in_meeting(self) -> bool:
        app_el = self._get_app_element()
        if app_el is None:
            return False
        return self._find_mute_element(app_el) is not None

    def _find_mute_element(self, app_element):
        """Search the AX tree for a button whose title contains 'mute'."""
        return self._walk(app_element, "AXButton", _MUTE_SEARCH_KEYWORD)
