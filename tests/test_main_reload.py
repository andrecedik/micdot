import pytest
from unittest.mock import MagicMock
from micdot.config import Config
from micdot.main import _State, _reload_config


@pytest.fixture
def config_path(tmp_path):
    cfg = Config(mqtt_host="new-host", mqtt_port=1884, hotkey="ctrl+shift+x")
    cfg.save(tmp_path / "config.json")
    return tmp_path / "config.json"


def test_reload_stops_old_mqtt_and_starts_new(config_path, mocker):
    old_mqtt = MagicMock()
    mock_mqtt_cls = mocker.patch("micdot.main.MQTTClient")
    mocker.patch("micdot.main.HotkeyListener")
    state = _State(Config(), old_mqtt, MagicMock())
    on_toggle = MagicMock()

    _reload_config(state, config_path, on_toggle)

    old_mqtt.stop.assert_called_once()
    assert mock_mqtt_cls.call_args[0][0].mqtt_host == "new-host"
    mock_mqtt_cls.return_value.start.assert_called_once()
    assert mock_mqtt_cls.call_args[1]["on_button_press"] is on_toggle


def test_reload_stops_old_hotkey_and_starts_new(config_path, mocker):
    mocker.patch("micdot.main.MQTTClient")
    old_hotkey = MagicMock()
    mock_hotkey_cls = mocker.patch("micdot.main.HotkeyListener")
    state = _State(Config(), MagicMock(), old_hotkey)
    on_toggle = MagicMock()

    _reload_config(state, config_path, on_toggle)

    old_hotkey.stop.assert_called_once()
    assert mock_hotkey_cls.call_args[0][0] == "ctrl+shift+x"
    mock_hotkey_cls.return_value.start.assert_called_once()
    assert mock_hotkey_cls.call_args[1]["callback"] is on_toggle


def test_reload_updates_state_references(config_path, mocker):
    mock_mqtt_cls = mocker.patch("micdot.main.MQTTClient")
    mock_hotkey_cls = mocker.patch("micdot.main.HotkeyListener")
    state = _State(Config(), MagicMock(), MagicMock())

    _reload_config(state, config_path, MagicMock())

    assert state.mqtt is mock_mqtt_cls.return_value
    assert state.hotkey_listener is mock_hotkey_cls.return_value
    assert state.config.mqtt_host == "new-host"
