import json
import pytest
from pathlib import Path
from micdot.config import Config


def test_config_defaults():
    c = Config()
    assert c.mqtt_host == ""
    assert c.mqtt_port == 1883
    assert c.mqtt_username == ""
    assert c.mqtt_password == ""
    assert c.color_muted == {"r": 0, "g": 255, "b": 0}
    assert c.color_unmuted == {"r": 255, "g": 0, "b": 0}
    assert c.led_brightness == 128
    assert c.hotkey == "ctrl+shift+m"
    assert c.autostart is False


def test_config_save_and_load(tmp_path):
    path = tmp_path / "config.json"
    Config(mqtt_host="192.168.1.50", mqtt_port=1884).save(path)
    loaded = Config.load(path)
    assert loaded.mqtt_host == "192.168.1.50"
    assert loaded.mqtt_port == 1884


def test_config_load_missing_file_returns_defaults(tmp_path):
    config = Config.load(tmp_path / "nonexistent.json")
    assert config.mqtt_host == ""
    assert config.mqtt_port == 1883


def test_config_load_partial_file_fills_defaults(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"mqtt_host": "10.0.0.1"}))
    config = Config.load(path)
    assert config.mqtt_host == "10.0.0.1"
    assert config.mqtt_port == 1883


def test_config_save_creates_parent_dirs(tmp_path):
    path = tmp_path / "nested" / "dir" / "config.json"
    Config().save(path)
    assert path.exists()


def test_conferencing_sync_enabled_defaults_to_true():
    cfg = Config()
    assert cfg.conferencing_sync_enabled is True


def test_conferencing_sync_enabled_persists_through_save_load(tmp_path):
    cfg = Config(conferencing_sync_enabled=False)
    cfg.save(tmp_path / "config.json")
    loaded = Config.load(tmp_path / "config.json")
    assert loaded.conferencing_sync_enabled is False


def test_conferencing_sync_enabled_defaults_to_true_when_missing_from_file(tmp_path):
    import json
    (tmp_path / "config.json").write_text(json.dumps({"mqtt_host": "h"}))
    loaded = Config.load(tmp_path / "config.json")
    assert loaded.conferencing_sync_enabled is True
