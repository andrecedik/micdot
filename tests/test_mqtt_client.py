import json
import pytest
from unittest.mock import MagicMock
from espmuter.config import Config
from espmuter.mqtt_client import MQTTClient


@pytest.fixture
def mock_paho(mocker):
    return mocker.patch("espmuter.mqtt_client.mqtt.Client")


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
    assert calls["espmuter/state"][0][1] == "muted"
    assert calls["espmuter/state"][1]["retain"] is True


def test_publish_unmuted_sends_correct_state(mock_paho, config):
    client = MQTTClient(config, MagicMock())
    client.publish_state(muted=False)
    calls = {c[0][0]: c for c in mock_paho.return_value.publish.call_args_list}
    assert calls["espmuter/state"][0][1] == "unmuted"


def test_publish_muted_sends_retained_green_led(mock_paho, config):
    client = MQTTClient(config, MagicMock())
    client.publish_state(muted=True)
    calls = {c[0][0]: c for c in mock_paho.return_value.publish.call_args_list}
    payload = json.loads(calls["espmuter/led/set"][0][1])
    assert payload == {"r": 0, "g": 255, "b": 0, "brightness": 128}
    assert calls["espmuter/led/set"][1]["retain"] is True


def test_publish_unmuted_sends_retained_red_led(mock_paho, config):
    client = MQTTClient(config, MagicMock())
    client.publish_state(muted=False)
    calls = {c[0][0]: c for c in mock_paho.return_value.publish.call_args_list}
    payload = json.loads(calls["espmuter/led/set"][0][1])
    assert payload == {"r": 255, "g": 0, "b": 0, "brightness": 128}


def test_button_message_calls_callback(mock_paho, config):
    on_button = MagicMock()
    client = MQTTClient(config, on_button)
    msg = MagicMock()
    msg.topic = "espmuter/button"
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
