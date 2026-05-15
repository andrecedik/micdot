from __future__ import annotations
import sys
from micdot import __version__


def get_version() -> str:
    if getattr(sys, "frozen", False):
        try:
            from Foundation import NSBundle
            info = NSBundle.mainBundle().infoDictionary() or {}
            v = info.get("CFBundleShortVersionString")
            if v:
                return str(v)
        except Exception:
            pass
    return __version__
