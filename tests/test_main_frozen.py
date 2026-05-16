import sys
import pytest
from pathlib import Path
from unittest.mock import patch


def test_settings_cmd_returns_module_mode_when_not_frozen():
    from micdot.main import _settings_cmd
    cmd = _settings_cmd(Path("/cfg/config.json"))
    assert cmd == [
        sys.executable, "-m", "micdot.settings_window",
        "/cfg/config.json", "--tab", "settings",
    ]


def test_settings_cmd_returns_flag_mode_when_frozen():
    from micdot.main import _settings_cmd
    with patch.object(sys, "frozen", True, create=True), \
         patch.object(sys, "executable", "/App/MicDot.app/Contents/MacOS/MicDot"):
        cmd = _settings_cmd(Path("/cfg/config.json"))
    assert cmd == [
        "/App/MicDot.app/Contents/MacOS/MicDot", "--settings",
        "/cfg/config.json", "--tab", "settings",
    ]


def test_settings_cmd_passes_tab_about():
    from micdot.main import _settings_cmd
    cmd = _settings_cmd(Path("/cfg/config.json"), tab="about")
    assert "--tab" in cmd
    assert cmd[cmd.index("--tab") + 1] == "about"


def test_main_dispatches_to_settings_when_frozen_with_flag(tmp_path, mocker):
    cfg_path = tmp_path / "config.json"
    mocker.patch.object(sys, "frozen", True, create=True)
    mocker.patch.object(sys, "argv", ["micdot", "--settings", str(cfg_path)])
    mock_run = mocker.patch("micdot.settings_window.run")

    from micdot.main import main
    main()

    mock_run.assert_called_once_with(cfg_path, initial_tab="settings")


def test_main_dispatches_to_about_when_tab_flag_set(tmp_path, mocker):
    cfg_path = tmp_path / "config.json"
    mocker.patch.object(sys, "frozen", True, create=True)
    mocker.patch.object(sys, "argv", ["micdot", "--settings", str(cfg_path), "--tab", "about"])
    mock_run = mocker.patch("micdot.settings_window.run")

    from micdot.main import main
    main()

    mock_run.assert_called_once_with(cfg_path, initial_tab="about")


def test_main_uses_default_config_path_when_no_path_arg(mocker):
    from micdot.config import DEFAULT_CONFIG_PATH
    mocker.patch.object(sys, "frozen", True, create=True)
    mocker.patch.object(sys, "argv", ["micdot", "--settings"])
    mock_run = mocker.patch("micdot.settings_window.run")

    from micdot.main import main
    main()

    mock_run.assert_called_once_with(DEFAULT_CONFIG_PATH, initial_tab="settings")
