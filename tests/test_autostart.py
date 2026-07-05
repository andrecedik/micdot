import plistlib
import pytest
from micdot.autostart import enable_autostart, disable_autostart


@pytest.fixture
def plist_path(tmp_path, mocker):
    path = tmp_path / "com.micdot.agent.plist"
    mocker.patch("micdot.autostart.PLIST_PATH", path)
    mocker.patch("micdot.autostart.subprocess.run")
    return path


def test_enable_creates_plist_file(plist_path):
    enable_autostart("/usr/bin/python3 /path/to/main.py")
    assert plist_path.exists()


def test_plist_label(plist_path):
    enable_autostart("/usr/bin/python3 /path/to/main.py")
    data = plistlib.loads(plist_path.read_bytes())
    assert data["Label"] == "com.micdot.agent"


def test_plist_run_at_load(plist_path):
    enable_autostart("/usr/bin/python3 /path/to/main.py")
    data = plistlib.loads(plist_path.read_bytes())
    assert data["RunAtLoad"] is True


def test_plist_keep_alive_allows_clean_quit(plist_path):
    # KeepAlive must not be a bare True: launchd would relaunch MicDot
    # immediately after the user quits from the tray. SuccessfulExit=False
    # restarts only after a crash (non-zero exit).
    enable_autostart("/usr/bin/python3 /path/to/main.py")
    data = plistlib.loads(plist_path.read_bytes())
    assert data["KeepAlive"] == {"SuccessfulExit": False}


def test_plist_program_arguments(plist_path):
    enable_autostart("/usr/bin/python3 /path/to/main.py")
    data = plistlib.loads(plist_path.read_bytes())
    assert data["ProgramArguments"] == ["/usr/bin/python3", "/path/to/main.py"]


def test_enable_calls_launchctl_load(plist_path, mocker):
    import micdot.autostart as mod
    enable_autostart("/usr/bin/python3 /path/to/main.py")
    mod.subprocess.run.assert_called_once_with(
        ["launchctl", "load", str(plist_path)], check=False
    )


def test_disable_removes_plist(plist_path):
    plist_path.write_bytes(b"content")
    disable_autostart()
    assert not plist_path.exists()


def test_disable_calls_launchctl_unload(plist_path, mocker):
    import micdot.autostart as mod
    plist_path.write_bytes(b"content")
    disable_autostart()
    mod.subprocess.run.assert_called_once_with(
        ["launchctl", "unload", str(plist_path)], check=False
    )


def test_disable_noop_when_plist_missing(plist_path, mocker):
    import micdot.autostart as mod
    disable_autostart()  # must not raise
    mod.subprocess.run.assert_not_called()
