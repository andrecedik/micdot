from __future__ import annotations
import plistlib
import subprocess
from pathlib import Path

PLIST_PATH = Path.home() / "Library" / "LaunchAgents" / "com.espmuter.agent.plist"


def enable_autostart(command: str) -> None:
    plist = {
        "Label": "com.espmuter.agent",
        "ProgramArguments": command.split(),
        "RunAtLoad": True,
        "KeepAlive": True,
    }
    PLIST_PATH.parent.mkdir(parents=True, exist_ok=True)
    PLIST_PATH.write_bytes(plistlib.dumps(plist))
    subprocess.run(["launchctl", "load", str(PLIST_PATH)], check=False)


def disable_autostart() -> None:
    if PLIST_PATH.exists():
        subprocess.run(["launchctl", "unload", str(PLIST_PATH)], check=False)
        PLIST_PATH.unlink()
