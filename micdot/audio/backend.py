from __future__ import annotations
import sys
from abc import ABC, abstractmethod


class AudioBackend(ABC):
    @abstractmethod
    def get_mute(self) -> bool: ...

    @abstractmethod
    def set_mute(self, muted: bool) -> None: ...


class StubAudioBackend(AudioBackend):
    def __init__(self, initial_mute: bool = False):
        self._muted = initial_mute

    def get_mute(self) -> bool:
        return self._muted

    def set_mute(self, muted: bool) -> None:
        self._muted = muted


def get_backend() -> AudioBackend:
    match sys.platform:
        case "darwin":
            from micdot.audio.macos import MacOSAudioBackend
            return MacOSAudioBackend()
        case _:
            raise NotImplementedError(f"No AudioBackend for platform: {sys.platform}")
