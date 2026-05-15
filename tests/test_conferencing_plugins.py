import pytest
from unittest.mock import MagicMock, patch


# ------------------------------------------------------------------ #
# ZoomPlugin
# ------------------------------------------------------------------ #

class TestZoomPlugin:
    def _make_plugin(self, running=True, in_meeting=True):
        with patch("micdot.conferencing.ax_utils.AXPlugin.is_running", return_value=running), \
             patch("micdot.conferencing.ax_utils.AXPlugin._get_app_element", return_value=MagicMock()):
            from micdot.conferencing.plugins.zoom import ZoomPlugin
            plugin = ZoomPlugin()
            plugin._running = running
            plugin._in_meeting_result = in_meeting
            return plugin

    def test_bundle_id(self):
        from micdot.conferencing.plugins.zoom import ZoomPlugin
        assert ZoomPlugin.bundle_id == "com.zoom.xpc"

    def test_name(self):
        from micdot.conferencing.plugins.zoom import ZoomPlugin
        assert ZoomPlugin.name == "Zoom"

    def test_is_in_meeting_false_when_no_toolbar_window(self, mocker):
        from micdot.conferencing.plugins.zoom import ZoomPlugin
        plugin = ZoomPlugin()
        mocker.patch.object(plugin, "_get_app_element", return_value=None)
        assert plugin.is_in_meeting() is False

    def test_is_in_meeting_false_when_no_app_element(self, mocker):
        from micdot.conferencing.plugins.zoom import ZoomPlugin
        plugin = ZoomPlugin()
        mocker.patch.object(plugin, "_get_app_pid", return_value=None)
        assert plugin.is_in_meeting() is False

    def test_find_mute_element_searches_for_mute_keyword(self, mocker):
        from micdot.conferencing.plugins.zoom import ZoomPlugin
        plugin = ZoomPlugin()
        fake_el = MagicMock()
        mocker.patch.object(plugin, "_walk", return_value=fake_el)
        app_el = MagicMock()
        result = plugin._find_mute_element(app_el)
        assert result is fake_el

    def test_get_mute_returns_none_when_not_in_meeting(self, mocker):
        from micdot.conferencing.plugins.zoom import ZoomPlugin
        plugin = ZoomPlugin()
        mocker.patch.object(plugin, "is_running", return_value=True)
        mocker.patch.object(plugin, "is_in_meeting", return_value=False)
        assert plugin.get_mute() is None

    def test_get_mute_true_when_title_contains_unmute(self, mocker):
        from micdot.conferencing.plugins.zoom import ZoomPlugin
        plugin = ZoomPlugin()
        mocker.patch.object(plugin, "is_running", return_value=True)
        mocker.patch.object(plugin, "is_in_meeting", return_value=True)
        mocker.patch.object(plugin, "_get_app_element", return_value=MagicMock())
        mocker.patch.object(plugin, "_find_mute_element", return_value=MagicMock())
        mocker.patch.object(plugin, "_read_title", return_value="Unmute my audio")
        assert plugin.get_mute() is True

    def test_get_mute_false_when_title_contains_mute_only(self, mocker):
        from micdot.conferencing.plugins.zoom import ZoomPlugin
        plugin = ZoomPlugin()
        mocker.patch.object(plugin, "is_running", return_value=True)
        mocker.patch.object(plugin, "is_in_meeting", return_value=True)
        mocker.patch.object(plugin, "_get_app_element", return_value=MagicMock())
        mocker.patch.object(plugin, "_find_mute_element", return_value=MagicMock())
        mocker.patch.object(plugin, "_read_title", return_value="Mute my audio")
        assert plugin.get_mute() is False


# ------------------------------------------------------------------ #
# TeamsPlugin
# ------------------------------------------------------------------ #

class TestTeamsPlugin:
    def test_bundle_id(self):
        from micdot.conferencing.plugins.teams import TeamsPlugin
        assert TeamsPlugin.bundle_id == "com.microsoft.teams2"

    def test_name(self):
        from micdot.conferencing.plugins.teams import TeamsPlugin
        assert TeamsPlugin.name == "Microsoft Teams"

    def test_is_in_meeting_false_when_no_app_element(self, mocker):
        from micdot.conferencing.plugins.teams import TeamsPlugin
        plugin = TeamsPlugin()
        mocker.patch.object(plugin, "_get_app_pid", return_value=None)
        assert plugin.is_in_meeting() is False

    def test_get_mute_returns_none_when_not_in_meeting(self, mocker):
        from micdot.conferencing.plugins.teams import TeamsPlugin
        plugin = TeamsPlugin()
        mocker.patch.object(plugin, "is_running", return_value=True)
        mocker.patch.object(plugin, "is_in_meeting", return_value=False)
        assert plugin.get_mute() is None

    def test_get_mute_true_when_title_contains_unmute(self, mocker):
        from micdot.conferencing.plugins.teams import TeamsPlugin
        plugin = TeamsPlugin()
        mocker.patch.object(plugin, "is_running", return_value=True)
        mocker.patch.object(plugin, "is_in_meeting", return_value=True)
        mocker.patch.object(plugin, "_get_app_element", return_value=MagicMock())
        mocker.patch.object(plugin, "_find_mute_element", return_value=MagicMock())
        mocker.patch.object(plugin, "_read_title", return_value="Unmute microphone")
        assert plugin.get_mute() is True


# ------------------------------------------------------------------ #
# MeetPlugin
# ------------------------------------------------------------------ #

class TestMeetPlugin:
    def test_bundle_ids_include_chrome_and_safari(self):
        from micdot.conferencing.plugins.meet import MeetPlugin
        assert MeetPlugin.bundle_id == "com.google.Chrome"

    def test_name(self):
        from micdot.conferencing.plugins.meet import MeetPlugin
        assert MeetPlugin.name == "Google Meet"

    def test_get_mute_returns_none_when_not_in_meeting(self, mocker):
        from micdot.conferencing.plugins.meet import MeetPlugin
        plugin = MeetPlugin()
        mocker.patch.object(plugin, "is_running", return_value=True)
        mocker.patch.object(plugin, "is_in_meeting", return_value=False)
        assert plugin.get_mute() is None
