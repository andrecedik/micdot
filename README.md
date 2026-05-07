# MicDot

A macOS menu bar app that mutes and unmutes your microphone — via hotkey, tray click, or a physical button on your desk.

**Make it way cooler:** pair MicDot with an ESP32 and a WS2812B LED ring to get a glowing mute indicator that sits next to your monitor. Green when live, red when muted. No more guessing.

## Features

- One-click or hotkey (default `ctrl+shift+m`) mute toggle
- Menu bar icon reflects current mute state
- Optional ESP32 hardware: physical button + RGB LED ring over MQTT
- Settings window with live config reload (no restart needed)
- Launches at login via macOS LaunchAgent
- macOS 12+ · Python 3.11+

## Download & Install (no Python required)

Pre-built binaries are available on the [Releases page](https://github.com/andrecedik/micdot/releases).

1. Download `MicDot-<version>-arm64.app.zip` (Apple Silicon) or `MicDot-<version>-x86_64.app.zip` (Intel).
2. Unzip and move `MicDot.app` to `/Applications`.
3. **First launch:** right-click `MicDot.app` → **Open** → click **Open** in the dialog. This is a one-time step to bypass Gatekeeper for unsigned apps.
4. MicDot will appear in your menu bar.

> **Note:** If you move the app after enabling "Launch at Login", re-enable it in Settings so the LaunchAgent path updates.

## Software Setup

### Requirements

- macOS 12 or later
- Python 3.11+

### Install

```bash
git clone https://github.com/andrecedik/micdot.git
cd micdot
pip install -e .
```

### Configure

MicDot looks for its config at `~/.config/micdot/config.json`. On first run it creates a default one. You can edit it by hand or use the Settings window from the tray icon menu.

```json
{
  "mqtt_host": "",
  "mqtt_port": 1883,
  "mqtt_username": "",
  "mqtt_password": "",
  "color_muted":   { "r": 0,   "g": 255, "b": 0 },
  "color_unmuted": { "r": 255, "g": 0,   "b": 0 },
  "led_brightness": 128,
  "hotkey": "ctrl+shift+m",
  "autostart": false
}
```

Leave `mqtt_host` empty if you're not using the ESP32 hardware.

### Run

```bash
micdot
```

To start at login, enable **Launch at Login** in the Settings window.

## Hardware Setup (makes it way cooler)

Pair MicDot with an ESP32 and a WS2812B LED ring to get a physical mute indicator and a desk button that toggles your mic.

### What you need

- Any supported ESP32 board (DevKit V1, ESP32-S3, XIAO ESP32C3, C3 SuperMini)
- A WS2812B LED ring or strip
- A momentary pushbutton
- An MQTT broker on your network (e.g. Mosquitto)

### Flash the firmware

1. Install [ESPHome](https://esphome.io/guides/installing_esphome.html)

2. Copy `esphome/micdot.yaml` and create `esphome/secrets.yaml`:

```yaml
wifi_ssid: "your-wifi"
wifi_password: "your-password"
mqtt_host: "192.168.x.x"
mqtt_port: "1883"
mqtt_username: "your-user"
mqtt_password: "your-password"
```

3. Edit the substitutions at the top of `micdot.yaml` to match your board and wiring (LED pin, button pin).

4. Flash:

```bash
esphome run esphome/micdot.yaml
```

### Connect MicDot to your broker

Fill in the `mqtt_host`, `mqtt_port`, `mqtt_username`, and `mqtt_password` fields in Settings (or `~/.config/micdot/config.json`) to point at the same broker. MicDot will push state and receive button presses automatically.

## Development

### Setup

```bash
git clone https://github.com/andrecedik/micdot.git
cd micdot
pip install -e ".[dev]"
```

### Run tests

```bash
pytest
```

All tests run without hardware or an MQTT broker.

### Project layout

```
micdot/
  audio/              CoreAudio backend (mute/unmute via macOS APIs)
  config.py           JSON config loader/saver
  hotkey.py           Global hotkey listener (pynput)
  mqtt_client.py      MQTT publish/subscribe (paho)
  poller.py           Polls mic state, fires on change
  autostart.py        LaunchAgent install/uninstall
  settings_window.py  pywebview-based settings UI
  tray.py             pystray menu bar icon
  main.py             Entry point, wires everything together
esphome/
  micdot.yaml         ESPHome firmware config
tests/                Unit tests (pytest + pytest-mock)
```

### First-launch Gatekeeper note

MicDot is not signed with an Apple Developer certificate. On first launch, right-click the app and choose **Open** to bypass Gatekeeper.
