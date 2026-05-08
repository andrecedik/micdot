import sys
import time
import pytest
from unittest.mock import MagicMock
from micdot.config import Config
from micdot.settings_window import Api


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
