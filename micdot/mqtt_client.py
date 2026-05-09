from __future__ import annotations
import json
import logging
from typing import Callable
import paho.mqtt.client as mqtt
from micdot.config import Config

log = logging.getLogger("micdot")


class MQTTClient:
    def __init__(self, config: Config, on_button_press: Callable[[], None]):
        self._config = config
        self._on_button_press = on_button_press
        self._client = mqtt.Client(client_id="micdot", clean_session=True)
        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message
        if config.mqtt_username:
            self._client.username_pw_set(config.mqtt_username, config.mqtt_password)

    @property
    def _configured(self) -> bool:
        return bool(self._config.mqtt_host)

    def start(self) -> None:
        if not self._configured:
            log.debug("MQTT not configured — skipping connection")
            return
        log.info("MQTT connecting to %s:%d", self._config.mqtt_host, self._config.mqtt_port)
        self._client.connect_async(
            self._config.mqtt_host, self._config.mqtt_port, keepalive=60
        )
        self._client.loop_start()

    def stop(self) -> None:
        if not self._configured:
            return
        log.info("MQTT disconnecting")
        self._client.loop_stop()
        self._client.disconnect()

    def publish_state(self, muted: bool) -> None:
        if not self._configured:
            return
        self._client.publish(
            "micdot/state", "Muted" if muted else "Unmuted", retain=True
        )
        color = self._config.color_muted if muted else self._config.color_unmuted
        self._client.publish(
            "micdot/led/set",
            json.dumps({"r": color["r"], "g": color["g"], "b": color["b"],
                        "brightness": self._config.led_brightness}),
            retain=True,
        )

    def _on_connect(self, client, userdata, flags, rc) -> None:
        if rc == 0:
            log.info("MQTT connected")
            client.subscribe("micdot/button")
            self._publish_autodiscovery()
        else:
            log.warning("MQTT connection failed (rc=%d)", rc)

    def _on_message(self, client, userdata, message) -> None:
        if message.topic == "micdot/button" and message.payload == b"pressed":
            self._on_button_press()

    def _publish_autodiscovery(self) -> None:
        self._client.publish(
            "homeassistant/binary_sensor/micdot/state/config", "", retain=True
        )
        self._client.publish(
            "homeassistant/sensor/micdot/state/config",
            json.dumps({
                "name": "Microphone",
                "device_class": "enum",
                "options": ["Muted", "Unmuted"],
                "state_topic": "micdot/state",
                "unique_id": "micdot_microphone_state",
                "device": {"identifiers": ["micdot"], "name": "MicDot"},
            }),
            retain=True,
        )
        self._client.publish(
            "homeassistant/device_automation/micdot/button/config",
            json.dumps({
                "automation_type": "trigger",
                "type": "button_short_press",
                "subtype": "button_1",
                "topic": "micdot/button",
                "payload": "pressed",
                "device": {"identifiers": ["micdot"], "name": "MicDot"},
            }),
            retain=True,
        )
