import json
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
        assert ZoomPlugin.bundle_id == "us.zoom.xos"

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
        fake_app_el = MagicMock()
        mocker.patch.object(plugin, "_all_zoom_elements", return_value=iter([fake_app_el]))
        mocker.patch.object(plugin, "_walk_desc", return_value=fake_el)
        result = plugin._find_mute_element(None)
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
        mocker.patch.object(plugin, "_find_mute_element", return_value=MagicMock())
        mocker.patch.object(plugin, "_get_attr", return_value=(0, "Unmute my audio"))
        assert plugin.get_mute() is True

    def test_get_mute_false_when_title_contains_mute_only(self, mocker):
        from micdot.conferencing.plugins.zoom import ZoomPlugin
        plugin = ZoomPlugin()
        mocker.patch.object(plugin, "is_running", return_value=True)
        mocker.patch.object(plugin, "is_in_meeting", return_value=True)
        mocker.patch.object(plugin, "_find_mute_element", return_value=MagicMock())
        mocker.patch.object(plugin, "_get_attr", return_value=(0, "Mute my audio"))
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

    def test_get_mute_returns_none_initially(self):
        from micdot.conferencing.plugins.teams import TeamsPlugin
        assert TeamsPlugin().get_mute() is None

    def test_is_in_meeting_false_initially(self):
        from micdot.conferencing.plugins.teams import TeamsPlugin
        assert TeamsPlugin().is_in_meeting() is False

    def test_on_message_updates_state_when_in_meeting(self, mocker):
        from micdot.conferencing.plugins.teams import TeamsPlugin
        plugin = TeamsPlugin()
        cb = mocker.Mock()
        plugin._on_change = cb
        msg = json.dumps({"meetingUpdate": {"meetingState": {"isInMeeting": True, "isMuted": True}}})
        plugin._on_message(None, msg)
        assert plugin.is_in_meeting() is True
        assert plugin.get_mute() is True
        cb.assert_called_once_with(True)

    def test_on_message_clears_state_when_not_in_meeting(self, mocker):
        from micdot.conferencing.plugins.teams import TeamsPlugin
        plugin = TeamsPlugin()
        plugin._in_meeting = True
        plugin._muted = True
        msg = json.dumps({"meetingUpdate": {"meetingState": {"isInMeeting": False, "isMuted": False}}})
        plugin._on_message(None, msg)
        assert plugin.is_in_meeting() is False
        assert plugin.get_mute() is None

    def test_on_message_saves_token_refresh(self, mocker):
        from micdot.conferencing.plugins.teams import TeamsPlugin
        plugin = TeamsPlugin()
        save = mocker.patch.object(plugin, "_save_token")
        plugin._on_message(None, json.dumps({"tokenRefresh": "tok123"}))
        save.assert_called_once_with("tok123")

    def test_set_mute_sends_toggle_when_state_differs(self, mocker):
        from micdot.conferencing.plugins.teams import TeamsPlugin
        plugin = TeamsPlugin()
        plugin._in_meeting = True
        plugin._muted = False
        send = mocker.patch.object(plugin, "_send")
        plugin.set_mute(True)
        send.assert_called_once_with({"action": "toggle-mute"})

    def test_set_mute_noop_when_state_already_matches(self, mocker):
        from micdot.conferencing.plugins.teams import TeamsPlugin
        plugin = TeamsPlugin()
        plugin._in_meeting = True
        plugin._muted = True
        send = mocker.patch.object(plugin, "_send")
        plugin.set_mute(True)
        send.assert_not_called()

    def test_set_mute_noop_when_not_in_meeting(self, mocker):
        from micdot.conferencing.plugins.teams import TeamsPlugin
        plugin = TeamsPlugin()
        send = mocker.patch.object(plugin, "_send")
        plugin.set_mute(True)
        send.assert_not_called()


# ------------------------------------------------------------------ #
# MeetPlugin
# ------------------------------------------------------------------ #

class TestMeetPlugin:
    def test_bundle_id_is_chrome(self):
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

    def test_is_in_meeting_false_when_no_meet_window(self, mocker):
        from micdot.conferencing.plugins.meet import MeetPlugin
        plugin = MeetPlugin()
        fake_app_el = MagicMock()
        fake_window = MagicMock()
        mocker.patch.object(plugin, "_get_app_element", return_value=fake_app_el)

        def fake_get_attr(element, attr):
            if attr == "AXWindows":
                return (0, [fake_window])
            if attr == "AXTitle":
                return (0, "GitHub - Some Repo")
            return (-1, None)

        mocker.patch.object(plugin, "_get_attr", side_effect=fake_get_attr)
        assert plugin.is_in_meeting() is False

    def test_is_in_meeting_true_when_window_title_contains_google_meet(self, mocker):
        from micdot.conferencing.plugins.meet import MeetPlugin
        plugin = MeetPlugin()
        fake_app_el = MagicMock()
        fake_window = MagicMock()
        mocker.patch.object(plugin, "_get_app_element", return_value=fake_app_el)

        def fake_get_attr(element, attr):
            if attr == "AXWindows":
                return (0, [fake_window])
            if attr == "AXTitle":
                return (0, "André Cedik - Google Meet")
            return (-1, None)

        mocker.patch.object(plugin, "_get_attr", side_effect=fake_get_attr)
        assert plugin.is_in_meeting() is True

    def test_find_mute_element_searches_microphone_keyword(self, mocker):
        from micdot.conferencing.plugins.meet import MeetPlugin
        plugin = MeetPlugin()
        fake_app_el = MagicMock()
        fake_window = MagicMock()
        fake_btn = MagicMock()
        mocker.patch.object(plugin, "_find_meet_window", return_value=fake_window)
        walk = mocker.patch.object(plugin, "_walk", return_value=fake_btn)
        result = plugin._find_mute_element(fake_app_el)
        walk.assert_called_once_with(fake_window, "AXButton", "microphone", max_depth=20)
        assert result is fake_btn

    def test_get_mute_true_when_button_says_turn_on_microphone(self, mocker):
        from micdot.conferencing.plugins.meet import MeetPlugin
        plugin = MeetPlugin()
        mocker.patch.object(plugin, "is_running", return_value=True)
        mocker.patch.object(plugin, "is_in_meeting", return_value=True)
        mocker.patch.object(plugin, "_get_app_element", return_value=MagicMock())
        mocker.patch.object(plugin, "_find_mute_element", return_value=MagicMock())
        mocker.patch.object(plugin, "_read_title", return_value="Turn on microphone")
        assert plugin.get_mute() is True

    def test_get_mute_false_when_button_says_turn_off_microphone(self, mocker):
        from micdot.conferencing.plugins.meet import MeetPlugin
        plugin = MeetPlugin()
        mocker.patch.object(plugin, "is_running", return_value=True)
        mocker.patch.object(plugin, "is_in_meeting", return_value=True)
        mocker.patch.object(plugin, "_get_app_element", return_value=MagicMock())
        mocker.patch.object(plugin, "_find_mute_element", return_value=MagicMock())
        mocker.patch.object(plugin, "_read_title", return_value="Turn off microphone")
        assert plugin.get_mute() is False
