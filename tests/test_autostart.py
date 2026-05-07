import plistlib
import pytest
from espmuter.autostart import enable_autostart, disable_autostart


def test_enable_creates_plist_file(tmp_path, mocker):
    plist_path = tmp_path / "com.espmuter.agent.plist"
    mocker.patch("espmuter.autostart.PLIST_PATH", plist_path)
    mocker.patch("espmuter.autostart.subprocess.run")
    enable_autostart("/usr/bin/python3 /path/to/main.py")
    assert plist_path.exists()


def test_plist_label(tmp_path, mocker):
    plist_path = tmp_path / "com.espmuter.agent.plist"
    mocker.patch("espmuter.autostart.PLIST_PATH", plist_path)
    mocker.patch("espmuter.autostart.subprocess.run")
    enable_autostart("/usr/bin/python3 /path/to/main.py")
    data = plistlib.loads(plist_path.read_bytes())
    assert data["Label"] == "com.espmuter.agent"


def test_plist_run_at_load(tmp_path, mocker):
    plist_path = tmp_path / "com.espmuter.agent.plist"
    mocker.patch("espmuter.autostart.PLIST_PATH", plist_path)
    mocker.patch("espmuter.autostart.subprocess.run")
    enable_autostart("/usr/bin/python3 /path/to/main.py")
    data = plistlib.loads(plist_path.read_bytes())
    assert data["RunAtLoad"] is True


def test_plist_program_arguments(tmp_path, mocker):
    plist_path = tmp_path / "com.espmuter.agent.plist"
    mocker.patch("espmuter.autostart.PLIST_PATH", plist_path)
    mocker.patch("espmuter.autostart.subprocess.run")
    enable_autostart("/usr/bin/python3 /path/to/main.py")
    data = plistlib.loads(plist_path.read_bytes())
    assert data["ProgramArguments"] == ["/usr/bin/python3", "/path/to/main.py"]


def test_disable_removes_plist(tmp_path, mocker):
    plist_path = tmp_path / "com.espmuter.agent.plist"
    plist_path.write_bytes(b"content")
    mocker.patch("espmuter.autostart.PLIST_PATH", plist_path)
    mocker.patch("espmuter.autostart.subprocess.run")
    disable_autostart()
    assert not plist_path.exists()


def test_disable_noop_when_plist_missing(tmp_path, mocker):
    plist_path = tmp_path / "com.espmuter.agent.plist"
    mocker.patch("espmuter.autostart.PLIST_PATH", plist_path)
    mocker.patch("espmuter.autostart.subprocess.run")
    disable_autostart()  # must not raise
