from micdot.audio.backend import StubAudioBackend
from micdot.poller import Poller


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
