import sys
import time
import pytest
from unittest.mock import MagicMock
from micdot.config import Config
from micdot.settings_window import Api, _build_html


@pytest.fixture
def api(tmp_path):
    return Api(tmp_path / "config.json")


_DATA = {
    "mqtt_host": "broker.local",
    "mqtt_port": 1883,
    "mqtt_username": "user",
    "mqtt_password": "s3cr3t",
    "hotkey": "ctrl+shift+m",
    "led_brightness": 128,
    "color_muted": {"r": 0, "g": 255, "b": 0},
    "color_unmuted": {"r": 255, "g": 0, "b": 0},
    "autostart": False,
}


def test_save_writes_config_to_file(api, tmp_path, mocker):
    mocker.patch("micdot.settings_window.enable_autostart")
    mocker.patch("micdot.settings_window.disable_autostart")
    api.save(_DATA)
    loaded = Config.load(tmp_path / "config.json")
    assert loaded.mqtt_host == "broker.local"
    assert loaded.mqtt_port == 1883
    assert loaded.mqtt_username == "user"
    assert loaded.color_muted == {"r": 0, "g": 255, "b": 0}


def test_save_sets_saved_flag(api, mocker):
    mocker.patch("micdot.settings_window.enable_autostart")
    mocker.patch("micdot.settings_window.disable_autostart")
    assert not api.saved
    api.save(_DATA)
    assert api.saved


def test_save_enables_autostart_when_true(api, mocker):
    enable = mocker.patch("micdot.settings_window.enable_autostart")
    mocker.patch("micdot.settings_window.disable_autostart")
    api.save({**_DATA, "autostart": True})
    time.sleep(0.05)
    enable.assert_called_once()


def test_save_disables_autostart_when_false(api, mocker):
    mocker.patch("micdot.settings_window.enable_autostart")
    disable = mocker.patch("micdot.settings_window.disable_autostart")
    api.save({**_DATA, "autostart": False})
    time.sleep(0.05)
    disable.assert_called_once()


def test_save_destroys_window(api, mocker):
    mocker.patch("micdot.settings_window.enable_autostart")
    mocker.patch("micdot.settings_window.disable_autostart")
    window = MagicMock()
    api.set_window(window)
    api.save(_DATA)
    window.native.performSelectorOnMainThread_withObject_waitUntilDone_.assert_called_once_with(
        b"close", None, True
    )


def test_save_enables_autostart_with_executable_when_frozen(api, mocker):
    mocker.patch.object(sys, "frozen", True, create=True)
    fake_exe = "/Applications/MicDot.app/Contents/MacOS/MicDot"
    mocker.patch.object(sys, "executable", fake_exe)
    enable = mocker.patch("micdot.settings_window.enable_autostart")
    mocker.patch("micdot.settings_window.disable_autostart")

    api.save({**_DATA, "autostart": True})
    time.sleep(0.05)

    enable.assert_called_once_with(fake_exe)


def test_save_enables_autostart_with_python_command_when_not_frozen(api, mocker):
    mocker.patch.object(sys, "frozen", False, create=True)
    mocker.patch("micdot.settings_window.shutil.which", return_value="/usr/bin/python3")
    enable = mocker.patch("micdot.settings_window.enable_autostart")
    mocker.patch("micdot.settings_window.disable_autostart")

    api.save({**_DATA, "autostart": True})
    time.sleep(0.05)

    args = enable.call_args[0][0]
    assert "-m" in args and "micdot.main" in args


def test_build_html_substitutes_all_placeholders(tmp_path):
    config = Config.load(tmp_path / "config.json")
    html = _build_html(config, "settings", "0.5.0")
    assert "__MICDOT_CONFIG__" not in html
    assert "__MICDOT_TAB__" not in html
    assert "__MICDOT_VER__" not in html


def test_build_html_sets_initial_tab_settings(tmp_path):
    config = Config.load(tmp_path / "config.json")
    html = _build_html(config, "settings", "0.5.0")
    assert '"settings"' in html


def test_build_html_sets_initial_tab_about(tmp_path):
    config = Config.load(tmp_path / "config.json")
    html = _build_html(config, "about", "0.5.0")
    assert '"about"' in html


def test_build_html_injects_version(tmp_path):
    config = Config.load(tmp_path / "config.json")
    html = _build_html(config, "settings", "1.2.3")
    assert "1.2.3" in html


def test_build_html_includes_github_link(tmp_path):
    config = Config.load(tmp_path / "config.json")
    html = _build_html(config, "settings", "0.5.0")
    assert "https://github.com/andrecedik/micdot" in html


def test_build_html_includes_support_link(tmp_path):
    config = Config.load(tmp_path / "config.json")
    html = _build_html(config, "settings", "0.5.0")
    assert "https://donatr.ee/andrecedik" in html


def test_open_url_calls_webbrowser_for_https(api, mocker):
    mock_open = mocker.patch("micdot.settings_window.webbrowser.open")
    api.open_url("https://github.com/andrecedik/micdot")
    mock_open.assert_called_once_with("https://github.com/andrecedik/micdot")


def test_open_url_calls_webbrowser_for_http(api, mocker):
    mock_open = mocker.patch("micdot.settings_window.webbrowser.open")
    api.open_url("http://example.com")
    mock_open.assert_called_once_with("http://example.com")


def test_open_url_rejects_file_scheme(api, mocker):
    mock_open = mocker.patch("micdot.settings_window.webbrowser.open")
    api.open_url("file:///etc/passwd")
    mock_open.assert_not_called()


def test_open_url_rejects_javascript_scheme(api, mocker):
    mock_open = mocker.patch("micdot.settings_window.webbrowser.open")
    api.open_url("javascript:alert(1)")
    mock_open.assert_not_called()


def test_open_url_rejects_empty_string(api, mocker):
    mock_open = mocker.patch("micdot.settings_window.webbrowser.open")
    api.open_url("")
    mock_open.assert_not_called()


def test_open_url_rejects_non_string(api, mocker):
    mock_open = mocker.patch("micdot.settings_window.webbrowser.open")
    api.open_url(None)
    mock_open.assert_not_called()


# --- hotkey validation ---

def test_save_accepts_valid_hotkey_ctrl_shift_m(api, mocker):
    mocker.patch("micdot.settings_window.enable_autostart")
    mocker.patch("micdot.settings_window.disable_autostart")
    api.save({**_DATA, "hotkey": "ctrl+shift+m"})
    assert api.saved


def test_save_accepts_valid_hotkey_cmd_space(api, mocker):
    mocker.patch("micdot.settings_window.enable_autostart")
    mocker.patch("micdot.settings_window.disable_autostart")
    api.save({**_DATA, "hotkey": "cmd+space"})
    assert api.saved


def test_save_accepts_valid_hotkey_ctrl_f1(api, mocker):
    mocker.patch("micdot.settings_window.enable_autostart")
    mocker.patch("micdot.settings_window.disable_autostart")
    api.save({**_DATA, "hotkey": "ctrl+f1"})
    assert api.saved


def test_save_rejects_invalid_hotkey_string(api, mocker):
    mocker.patch("micdot.settings_window.enable_autostart")
    mocker.patch("micdot.settings_window.disable_autostart")
    with pytest.raises(ValueError, match="Invalid hotkey"):
        api.save({**_DATA, "hotkey": "ctrl+not!!!valid"})
    assert not api.saved


def test_save_rejects_empty_hotkey(api, mocker):
    mocker.patch("micdot.settings_window.enable_autostart")
    mocker.patch("micdot.settings_window.disable_autostart")
    with pytest.raises(ValueError):
        api.save({**_DATA, "hotkey": ""})
    assert not api.saved


def test_save_rejects_bare_key_without_modifier(api, mocker):
    mocker.patch("micdot.settings_window.enable_autostart")
    mocker.patch("micdot.settings_window.disable_autostart")
    with pytest.raises(ValueError, match="modifier"):
        api.save({**_DATA, "hotkey": "m"})
    assert not api.saved


def test_build_html_hotkey_input_is_readonly(tmp_path):
    config = Config.load(tmp_path / "config.json")
    html = _build_html(config, "settings", "0.5.0")
    assert 'id="hotkey"' in html
    assert "readonly" in html


def test_build_html_hotkey_input_has_keydown_listener(tmp_path):
    config = Config.load(tmp_path / "config.json")
    html = _build_html(config, "settings", "0.5.0")
    assert "keydown" in html
    assert "hotkeyInput" in html


def test_build_html_hotkey_has_listening_css(tmp_path):
    config = Config.load(tmp_path / "config.json")
    html = _build_html(config, "settings", "0.5.0")
    assert "#hotkey.listening" in html
    assert "#ff3b30" in html


def test_build_html_hotkey_focus_saves_and_clears_value(tmp_path):
    config = Config.load(tmp_path / "config.json")
    html = _build_html(config, "settings", "0.5.0")
    assert "savedHotkey" in html
    assert "classList.add('listening')" in html


def test_build_html_hotkey_blur_restores_value(tmp_path):
    config = Config.load(tmp_path / "config.json")
    html = _build_html(config, "settings", "0.5.0")
    assert "classList.remove('listening')" in html
