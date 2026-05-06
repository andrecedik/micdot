from __future__ import annotations
import json
from typing import Callable
import paho.mqtt.client as mqtt
from espmuter.config import Config


class MQTTClient:
    def __init__(self, config: Config, on_button_press: Callable[[], None]):
        self._config = config
        self._on_button_press = on_button_press
        self._client = mqtt.Client(client_id="espmuter", clean_session=True)
        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message
        if config.mqtt_username:
            self._client.username_pw_set(config.mqtt_username, config.mqtt_password)

    def start(self) -> None:
        self._client.connect_async(
            self._config.mqtt_host, self._config.mqtt_port, keepalive=60
        )
        self._client.loop_start()

    def stop(self) -> None:
        self._client.loop_stop()
        self._client.disconnect()

    def publish_state(self, muted: bool) -> None:
        self._client.publish(
            "espmuter/state", "muted" if muted else "unmuted", retain=True
        )
        color = self._config.color_muted if muted else self._config.color_unmuted
        self._client.publish(
            "espmuter/led/set",
            json.dumps({"r": color["r"], "g": color["g"], "b": color["b"],
                        "brightness": self._config.led_brightness}),
            retain=True,
        )

    def _on_connect(self, client, userdata, flags, rc) -> None:
        if rc == 0:
            client.subscribe("espmuter/button")
            self._publish_autodiscovery()

    def _on_message(self, client, userdata, message) -> None:
        if message.topic == "espmuter/button" and message.payload == b"pressed":
            self._on_button_press()

    def _publish_autodiscovery(self) -> None:
        self._client.publish(
            "homeassistant/binary_sensor/espmuter/state/config",
            json.dumps({
                "name": "Microphone",
                "device_class": "sound",
                "state_topic": "espmuter/state",
                "payload_on": "muted",
                "payload_off": "unmuted",
                "unique_id": "espmuter_microphone_state",
                "device": {"identifiers": ["espmuter"], "name": "ESPMuter"},
            }),
            retain=True,
        )
        self._client.publish(
            "homeassistant/device_automation/espmuter/button/config",
            json.dumps({
                "automation_type": "trigger",
                "type": "action",
                "subtype": "button_1_press",
                "topic": "espmuter/button",
                "payload": "pressed",
                "device": {"identifiers": ["espmuter"], "name": "ESPMuter"},
            }),
            retain=True,
        )
