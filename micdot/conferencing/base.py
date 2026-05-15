from __future__ import annotations
import sys
from abc import ABC, abstractmethod
from collections.abc import Callable


def _version_tuple(v: str) -> tuple[int, ...]:
    try:
        return tuple(int(x) for x in v.split("."))
    except ValueError:
        return ()


class ConferencingPlugin(ABC):
    bundle_id: str
    name: str
    supported_platforms: tuple[str, ...] = ("darwin",)
    min_version: str | None = None
    max_version: str | None = None

    def is_compatible(self) -> bool:
        if sys.platform not in self.supported_platforms:
            return False
        installed = self._get_installed_version()
        if installed and self.min_version:
            if _version_tuple(installed) < _version_tuple(self.min_version):
                return False
        return True

    def _get_installed_version(self) -> str | None:
        return None

    @abstractmethod
    def is_running(self) -> bool: ...

    @abstractmethod
    def is_in_meeting(self) -> bool: ...

    @abstractmethod
    def get_mute(self) -> bool | None:
        """Return current mute state, or None if not in a meeting."""
        ...

    @abstractmethod
    def set_mute(self, muted: bool) -> None:
        """Set mute state. No-op if not in a meeting."""
        ...

    @abstractmethod
    def start_observing(self, on_change: Callable[[bool], None]) -> None:
        """Start watching for mute state changes. on_change(muted) is called from any thread."""
        ...

    @abstractmethod
    def stop_observing(self) -> None: ...
