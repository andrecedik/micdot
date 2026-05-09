import json
import pytest
from unittest.mock import MagicMock
from micdot.config import Config
from micdot.mqtt_client import MQTTClient


@pytest.fixture
def mock_paho(mocker):
    return mocker.patch("micdot.mqtt_client.mqtt.Client")


@pytest.fixture
def config():
    return Config(
        mqtt_host="localhost",
        mqtt_port=1883,
        mqtt_username="user",
        mqtt_password="pass",
        color_muted={"r": 0, "g": 255, "b": 0},
        color_unmuted={"r": 255, "g": 0, "b": 0},
        led_brightness=128,
    )


def test_publish_muted_sends_retained_state(mock_paho, config):
    client = MQTTClient(config, MagicMock())
    client.publish_state(muted=True)
    calls = {c[0][0]: c for c in mock_paho.return_value.publish.call_args_list}
    assert calls["micdot/state"][0][1] == "Muted"
    assert calls["micdot/state"][1]["retain"] is True


def test_publish_unmuted_sends_correct_state(mock_paho, config):
    client = MQTTClient(config, MagicMock())
    client.publish_state(muted=False)
    calls = {c[0][0]: c for c in mock_paho.return_value.publish.call_args_list}
    assert calls["micdot/state"][0][1] == "Unmuted"


def test_publish_muted_sends_retained_green_led(mock_paho, config):
    client = MQTTClient(config, MagicMock())
    client.publish_state(muted=True)
    calls = {c[0][0]: c for c in mock_paho.return_value.publish.call_args_list}
    payload = json.loads(calls["micdot/led/set"][0][1])
    assert payload == {"r": 0, "g": 255, "b": 0, "brightness": 128}
    assert calls["micdot/led/set"][1]["retain"] is True


def test_publish_unmuted_sends_retained_red_led(mock_paho, config):
    client = MQTTClient(config, MagicMock())
    client.publish_state(muted=False)
    calls = {c[0][0]: c for c in mock_paho.return_value.publish.call_args_list}
    payload = json.loads(calls["micdot/led/set"][0][1])
    assert payload == {"r": 255, "g": 0, "b": 0, "brightness": 128}


def test_button_message_calls_callback(mock_paho, config):
    on_button = MagicMock()
    client = MQTTClient(config, on_button)
    msg = MagicMock()
    msg.topic = "micdot/button"
    msg.payload = b"pressed"
    client._on_message(None, None, msg)
    on_button.assert_called_once()


def test_unrelated_topic_ignored(mock_paho, config):
    on_button = MagicMock()
    client = MQTTClient(config, on_button)
    msg = MagicMock()
    msg.topic = "other/topic"
    msg.payload = b"pressed"
    client._on_message(None, None, msg)
    on_button.assert_not_called()


def test_publish_muted_sends_uppercase_state(mock_paho, config):
    client = MQTTClient(config, MagicMock())
    client.publish_state(muted=True)
    calls = {c[0][0]: c for c in mock_paho.return_value.publish.call_args_list}
    assert calls["micdot/state"][0][1] == "Muted"


def test_publish_unmuted_sends_uppercase_state(mock_paho, config):
    client = MQTTClient(config, MagicMock())
    client.publish_state(muted=False)
    calls = {c[0][0]: c for c in mock_paho.return_value.publish.call_args_list}
    assert calls["micdot/state"][0][1] == "Unmuted"


def test_autodiscovery_publishes_sensor_topic(mock_paho, config):
    client = MQTTClient(config, MagicMock())
    client._publish_autodiscovery()
    topics = [c[0][0] for c in mock_paho.return_value.publish.call_args_list]
    assert "homeassistant/sensor/micdot/state/config" in topics


def test_autodiscovery_sensor_config_is_enum_with_options(mock_paho, config):
    client = MQTTClient(config, MagicMock())
    client._publish_autodiscovery()
    calls = {c[0][0]: c for c in mock_paho.return_value.publish.call_args_list}
    payload = json.loads(calls["homeassistant/sensor/micdot/state/config"][0][1])
    assert payload["device_class"] == "enum"
    assert payload["options"] == ["Muted", "Unmuted"]
    assert payload["state_topic"] == "micdot/state"
    assert "payload_on" not in payload
    assert "payload_off" not in payload


def test_autodiscovery_clears_old_binary_sensor(mock_paho, config):
    client = MQTTClient(config, MagicMock())
    client._publish_autodiscovery()
    calls = {c[0][0]: c for c in mock_paho.return_value.publish.call_args_list}
    assert "homeassistant/binary_sensor/micdot/state/config" in calls
    assert calls["homeassistant/binary_sensor/micdot/state/config"][0][1] == ""
    assert calls["homeassistant/binary_sensor/micdot/state/config"][1]["retain"] is True
