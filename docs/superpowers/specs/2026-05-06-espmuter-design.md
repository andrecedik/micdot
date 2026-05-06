# ESPMuter — Design Spec

**Date:** 2026-05-06  
**Status:** Approved

---

## Overview

ESPMuter is a microphone mute controller with two components:

1. **Python desktop app** — runs in the macOS menu bar, monitors and controls the system default microphone mute state, communicates over MQTT.
2. **ESP32 hardware button** — a desk puck with a large arcade button and a 12-LED WS2812B NeoPixel ring, running ESPHome, connected via WiFi.

The two components communicate through an existing Mosquitto MQTT broker (running as a Docker container on a NAS). Home Assistant receives visibility into the system via MQTT autodiscovery — no manual HA configuration required.

---

## System Architecture

```
┌─────────────────────────────────┐
│       Python App (espmuter)     │
│  - Polls mic state (200ms)      │
│  - Menu bar icon                │
│  - Global hotkey                │
│  - Configures LED color         │
└────────────┬────────────────────┘
             │ MQTT (Mosquitto on NAS)
    ┌────────┴────────┐
    │                 │
    ▼                 ▼
┌─────────┐    ┌────────────────┐
│   HA    │    │  ESP32/ESPHome │
│ entities│    │  - Button      │
│ via     │    │  - 12x WS2812B │
│ autodis-│    │    NeoPixel    │
│ covery  │    │    ring        │
└─────────┘    └────────────────┘
```

---

## MQTT Topic Schema

| Topic | Publisher | Subscribers | Payload |
|---|---|---|---|
| `espmuter/state` | Python app | HA (autodiscovery) | `muted` / `unmuted` — retained |
| `espmuter/led/set` | Python app | ESP32 | `{"r":0,"g":255,"b":0,"brightness":128}` — retained |
| `espmuter/button` | ESP32 | Python app | `pressed` |

The Python app owns all color logic. It maps mute state to the user-configured RGB values and publishes directly to `espmuter/led/set`. ESPHome applies the color without any decision-making. HA receives `espmuter/state` for automation use and is never in the critical mute-toggle path.

---

## Python App

### Structure

```
espmuter/
├── main.py              # Entry point — wires all components, starts threads
├── config.py            # Config dataclass + JSON load/save
├── audio/
│   ├── backend.py       # Abstract AudioBackend interface
│   └── macos.py         # macOS implementation via pyobjc + CoreAudio
├── mqtt_client.py       # MQTT connection, pub/sub, reconnect logic
├── tray.py              # Menu bar icon + click handling (pystray)
├── hotkey.py            # Global keyboard shortcut listener (pynput)
└── settings_window.py   # Settings UI (tkinter)
```

### Threading Model

| Thread | Role |
|---|---|
| Main thread | `pystray` tray event loop |
| Polling thread | Reads mic state every 200ms via `AudioBackend`, publishes changes |
| MQTT thread | `paho-mqtt` network loop, handles reconnects transparently |
| Hotkey thread | `pynput` global listener, triggers toggle on shortcut keypress |

All threads share a single `AppState` dataclass protected by a `threading.Lock`. No mutable state exists outside of it.

### AudioBackend Interface

```python
class AudioBackend(ABC):
    def get_mute(self) -> bool: ...
    def set_mute(self, muted: bool) -> None: ...

def get_backend() -> AudioBackend:
    match sys.platform:
        case "darwin": return MacOSAudioBackend()
        case "win32":  return WindowsAudioBackend()   # future
        case _:        return LinuxAudioBackend()     # future
```

macOS implementation uses `pyobjc-framework-CoreAudio` to read and write the default input device's mute property directly (no subprocess spawning).

### Tray Behaviour

- **Left click** — toggles mute (via `pystray` left-click callback)
- **Right click** — menu: Toggle Mute, Settings, Quit
- **Icon** — reflects current state (solid circle: green = muted, red = unmuted)

### Hotkey

Configured as a string in settings (e.g. `ctrl+shift+m`). Implemented via `pynput` global listener. Triggers the same toggle action as a left click.

### Autostart

On macOS, autostart is implemented by writing/removing a `launchd` plist to `~/Library/LaunchAgents/com.espmuter.agent.plist` when the setting is toggled.

### Dependencies

| Library | Purpose |
|---|---|
| `pystray` | Cross-platform system tray icon (left-click toggle, right-click menu) |
| `Pillow` | Required by `pystray` for icon rendering |
| `pyobjc-framework-CoreAudio` | Mic mute read/write on macOS |
| `paho-mqtt` | MQTT client |
| `pynput` | Global hotkey listener |
| `tkinter` | Settings window (stdlib) |

### Configuration

Stored at `~/.config/espmuter/config.json`. Created with defaults on first run.

```json
{
  "mqtt_host": "192.168.1.x",
  "mqtt_port": 1883,
  "mqtt_username": "",
  "mqtt_password": "",
  "color_muted":   {"r": 0,   "g": 255, "b": 0},
  "color_unmuted": {"r": 255, "g": 0,   "b": 0},
  "led_brightness": 128,
  "hotkey": "ctrl+shift+m",
  "autostart": false
}
```

---

## ESPHome Hardware

### Recommended Hardware (Puck Form Factor)

- **Button:** 60mm momentary arcade push button (non-illuminated — LEDs provided by the ring)
- **LEDs:** 12-LED WS2812B NeoPixel ring (Adafruit #1643 or compatible)
- **Wiring notes:**
  - 300–500Ω resistor in series on the LED data line
  - 100–470µF capacitor across the LED ring power rails
  - WS2812B operates at 5V; all listed ESP32 boards output 3.3V on GPIO — the series resistor mitigates most signal integrity issues; a level shifter (e.g. 74AHCT125) is optional but recommended for reliability

### Supported Boards & Pinouts

| Board | LED Data Pin | Button Pin | Notes |
|---|---|---|---|
| ESP32 DevKit V1 | GPIO5 | GPIO14 | Most common; 5V rail available for LED power |
| ESP32-S3 DevKit | GPIO5 | GPIO4 | Native USB-C; more GPIO headroom |
| XIAO ESP32C3 | GPIO2 (D1) | GPIO3 (D2) | Smallest — fits easily inside puck enclosure |
| ESP32-C3 SuperMini | GPIO8 | GPIO9 | Cheapest small option |

### ESPHome Configuration

Board selection is handled via `substitutions` — switching boards requires changing three lines only.

**`secrets.yaml`:**
```yaml
mqtt_host: "192.168.1.x"
mqtt_port: "1883"
mqtt_username: "espmuter"
mqtt_password: "yourpassword"
wifi_ssid: "YourNetwork"
wifi_password: "YourWifiPassword"
```

**`espmuter.yaml` (ESP32 DevKit V1 shown):**
```yaml
substitutions:
  board_name: esp32dev
  led_pin: GPIO5
  button_pin: GPIO14

esphome:
  name: espmuter

esp32:
  board: ${board_name}

wifi:
  ssid: !secret wifi_ssid
  password: !secret wifi_password

mqtt:
  broker: !secret mqtt_host
  port: !secret mqtt_port
  username: !secret mqtt_username
  password: !secret mqtt_password
  on_message:
    - topic: espmuter/led/set
      then:
        - lambda: |-
            auto val = parse_json(x);
            auto call = id(led_ring).make_call();
            call.set_state(true);
            call.set_rgb(val["r"].as<int>() / 255.0,
                         val["g"].as<int>() / 255.0,
                         val["b"].as<int>() / 255.0);
            call.set_brightness(val["brightness"].as<int>() / 255.0);
            call.perform();

light:
  - platform: neopixelbus
    type: GRB
    variant: WS2812X
    pin: ${led_pin}
    num_leds: 12
    name: "ESPMuter Ring"
    id: led_ring

binary_sensor:
  - platform: gpio
    pin:
      number: ${button_pin}
      mode: INPUT_PULLUP
      inverted: true
    name: "ESPMuter Button"
    filters:
      - delayed_on: 20ms
    on_press:
      - mqtt.publish:
          topic: espmuter/button
          payload: "pressed"
```

**Board substitution reference:**

| Board | `board_name` | `led_pin` | `button_pin` |
|---|---|---|---|
| ESP32 DevKit V1 | `esp32dev` | `GPIO5` | `GPIO14` |
| ESP32-S3 DevKit | `esp32-s3-devkitc-1` | `GPIO5` | `GPIO4` |
| XIAO ESP32C3 | `seeed_xiao_esp32c3` | `GPIO2` | `GPIO3` |
| ESP32-C3 SuperMini | `esp32-c3-devkitm-1` | `GPIO8` | `GPIO9` |

---

## Home Assistant Integration

The Python app publishes MQTT autodiscovery payloads on startup with `retain: true`. No manual HA configuration is required.

### Entities Created Automatically

**Mute state binary sensor:**
```
Discovery topic:  homeassistant/binary_sensor/espmuter/state/config
State topic:      espmuter/state
Payload on:       muted
Payload off:      unmuted
```

**Button device automation:**
```
Discovery topic:  homeassistant/device_automation/espmuter/button/config
State topic:      espmuter/button
Payload:          pressed
```

On clean uninstall, the app publishes empty retained messages to both discovery topics to remove the entities from HA.

### Critical Path Clarification

HA is **not** in the mute toggle loop. The flow is:

```
Button press → espmuter/button → Python app → toggles mic → publishes espmuter/state + espmuter/led/set → ESP32 LED updates
```

HA receives `espmuter/state` passively and can trigger additional automations (e.g. do-not-disturb lights, notifications) but is never a dependency for the core function.

---

## Out of Scope

- Windows and Linux audio backends (architecture supports them; implementation deferred)
- Custom enclosure / 3D print files for the puck
- OTA firmware update workflow for ESPHome (handled by ESPHome's built-in OTA)
- Multi-device support (one puck, one computer)
