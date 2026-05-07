# README Design — MicDot

**Date:** 2026-05-07  
**Status:** Approved  

## Goal

Write a `README.md` for the public GitHub repo at `https://github.com/andrecedik/micdot`. The README serves both the author (personal reference) and technical users who find the repo cold. No screenshots yet — placeholder noted for later.

## Audience

Technical users who know Python and pip. Not hand-holdy, but welcoming. Hardware section sells the ESP32 experience as a compelling upgrade, not a requirement.

## Structure (Option A — Feature-first)

### 1. Header + Intro

- Project name and one-sentence description
- "Make it way cooler" callout for the ESP32 hardware
- Feature bullet list covering: hotkey toggle, tray icon, optional ESP32 (button + LED over MQTT), settings window with live reload, LaunchAgent autostart, platform/Python requirements

### 2. Software Setup

- Requirements: macOS 12+, Python 3.11+
- Install: `git clone` → `pip install -e .`
- Configure: document `~/.config/micdot/config.json` with full default JSON, note that `mqtt_host` can be left empty for software-only use
- Run: `micdot` command, mention Settings window for enabling Launch at Login

### 3. Hardware Setup

- What you need: any supported ESP32 board (list four variants), WS2812B LED ring or strip, momentary pushbutton, MQTT broker
- Flash: install ESPHome, create `secrets.yaml` (template provided), edit board substitutions in `micdot.yaml`, run `esphome run`
- Connect: fill in MQTT fields in Settings to point at the same broker

### 4. Development

- Setup: `pip install -e ".[dev]"`
- Run tests: `pytest` — note all 43 tests run without hardware or broker
- Project layout: tree of `micdot/` submodules with one-line descriptions, `esphome/`, `tests/`
- Gatekeeper note: app is unsigned — right-click → Open on first launch

## Decisions

- No screenshots in initial version; structure leaves natural space to add them above the Features list later
- Generic hardware references (no specific vendor links) — keeps README evergreen
- ESPHome flashing steps are complete end-to-end (install ESPHome, secrets, substitutions, flash command)
- Gatekeeper note lives in Development rather than a top-level warning — it only matters when running a built `.app`, which doesn't exist yet
