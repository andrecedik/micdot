from micdot.audio.backend import StubAudioBackend
from micdot.poller import Poller


class FlakyBackend(StubAudioBackend):
    """Backend whose CoreAudio calls can be made to fail on demand."""

    def __init__(self, initial_mute: bool = False):
        super().__init__(initial_mute)
        self.fail = False

    def get_mute(self) -> bool:
        if self.fail:
            raise OSError("CoreAudio: property read failed")
        return super().get_mute()

    def set_mute(self, muted: bool) -> None:
        if self.fail:
            raise OSError("CoreAudio: property write failed")
        super().set_mute(muted)


def test_first_tick_publishes_initial_state():
    backend = StubAudioBackend(initial_mute=False)
    calls = []
    Poller(backend, on_change=calls.append).tick()
    assert calls == [False]


def test_second_tick_same_state_no_call():
    backend = StubAudioBackend(initial_mute=False)
    calls = []
    poller = Poller(backend, on_change=calls.append)
    poller.tick()
    poller.tick()
    assert calls == [False]


def test_tick_fires_on_state_change():
    backend = StubAudioBackend(initial_mute=False)
    calls = []
    poller = Poller(backend, on_change=calls.append)
    poller.tick()
    backend.set_mute(True)
    poller.tick()
    assert calls == [False, True]


def test_toggle_flips_mute_state():
    backend = StubAudioBackend(initial_mute=False)
    poller = Poller(backend, on_change=lambda _: None)
    poller.toggle()
    assert backend.get_mute() is True
    poller.toggle()
    assert backend.get_mute() is False


def test_tick_survives_backend_error():
    backend = FlakyBackend()
    backend.fail = True
    calls = []
    poller = Poller(backend, on_change=calls.append)
    poller.tick()  # must not raise
    assert calls == []


def test_tick_recovers_after_backend_error():
    backend = FlakyBackend(initial_mute=True)
    calls = []
    poller = Poller(backend, on_change=calls.append)
    backend.fail = True
    poller.tick()
    backend.fail = False
    poller.tick()
    assert calls == [True]


def test_tick_logs_error_only_once_per_episode(caplog):
    backend = FlakyBackend()
    backend.fail = True
    poller = Poller(backend, on_change=lambda _: None)
    with caplog.at_level("WARNING", logger="micdot"):
        poller.tick()
        poller.tick()
        poller.tick()
    warnings = [r for r in caplog.records if r.levelname == "WARNING"]
    assert len(warnings) == 1


def test_toggle_survives_backend_error(caplog):
    backend = FlakyBackend()
    backend.fail = True
    poller = Poller(backend, on_change=lambda _: None)
    with caplog.at_level("WARNING", logger="micdot"):
        poller.toggle()  # must not raise — runs inside pynput/MQTT callbacks
    assert any(r.levelname == "WARNING" for r in caplog.records)
