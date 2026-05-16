# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## [Unreleased]

### Added

- About tab in settings window showing app version, GitHub link, and a "Support me" donate link.
- "About" tray menu item that opens the About tab directly.

## [0.4.0] - 2026-05-13

### Changed

- Home Assistant MQTT discovery now registers the microphone as an `enum` sensor (`Muted` / `Unmuted`) instead of a `binary_sensor`. This is a better semantic fit and gives the entity a proper `mdi:microphone-plus` icon in the HA dashboard.
- State topic payloads changed from `muted`/`unmuted` to `Muted`/`Unmuted` to align with the enum sensor options. Update any HA automations that reference these values.

### Fixed

- The old `binary_sensor` discovery entity is automatically removed from Home Assistant on first connect.
- Menu bar icon now sets a stable identifier so Bartender, Ice, and similar apps correctly remember its position across restarts.

## [0.3.8] - 2026-05-08

### Fixed

- Keep pynput `Listener` alive on config reload to avoid TSM main-thread crash on macOS 15 Sequoia.

## [0.3.7] - 2026-05-08

### Fixed

- Dispatch hotkey restart to main thread on config reload.

## [0.3.6] - 2026-05-08

### Fixed

- Join hotkey listener thread on stop and surface reload errors.

## [0.3.5] - 2026-05-08

### Fixed

- Close settings window synchronously to avoid `evaluate_js` deadlock.

## [0.3.4] - 2026-05-08

### Fixed

- Close settings window via pure ObjC selector dispatch.

## [0.3.3] - 2026-05-08

### Fixed

- Dispatch `window.destroy()` via `NSOperationQueue` instead of `os._exit()`.

## [0.3.2] - 2026-05-08

### Fixed

- Force-exit settings subprocess after save instead of relying on `destroy()`.

## [0.3.1] - 2026-05-08

### Fixed

- Move autostart and window close off the JS callback thread.

## [0.3.0] - 2026-05-08

### Added

- File logging.

### Fixed

- Settings save hang.

## [0.2.0] - 2026-05-08

### Added

- Custom app icon.

### Fixed

- Skip MQTT entirely when `mqtt_host` is not configured.

## [0.1.1] - 2026-05-07

### Removed

- x86_64 (Intel) support dropped; arm64 only. Intel Macs can run via Rosetta 2.

## [0.1.0] - 2026-05-07

### Fixed

- Dynamic version injection in PyInstaller spec.
- Strip `v`-prefix from zip artifact names.

[Unreleased]: https://github.com/andrecedik/micdot/compare/v0.4.0...HEAD
[0.4.0]: https://github.com/andrecedik/micdot/compare/v0.3.8...v0.4.0
[0.3.8]: https://github.com/andrecedik/micdot/compare/v0.3.7...v0.3.8
[0.3.7]: https://github.com/andrecedik/micdot/compare/v0.3.6...v0.3.7
[0.3.6]: https://github.com/andrecedik/micdot/compare/v0.3.5...v0.3.6
[0.3.5]: https://github.com/andrecedik/micdot/compare/v0.3.4...v0.3.5
[0.3.4]: https://github.com/andrecedik/micdot/compare/v0.3.3...v0.3.4
[0.3.3]: https://github.com/andrecedik/micdot/compare/v0.3.2...v0.3.3
[0.3.2]: https://github.com/andrecedik/micdot/compare/v0.3.1...v0.3.2
[0.3.1]: https://github.com/andrecedik/micdot/compare/v0.3.0...v0.3.1
[0.3.0]: https://github.com/andrecedik/micdot/compare/v0.2.0...v0.3.0
[0.2.0]: https://github.com/andrecedik/micdot/compare/v0.1.1...v0.2.0
[0.1.1]: https://github.com/andrecedik/micdot/compare/v0.1.0...v0.1.1
[0.1.0]: https://github.com/andrecedik/micdot/releases/tag/v0.1.0
