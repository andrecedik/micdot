from espmuter.audio.backend import AudioBackend, StubAudioBackend


def test_stub_default_mute_is_false():
    assert StubAudioBackend().get_mute() is False


def test_stub_initial_mute_true():
    assert StubAudioBackend(initial_mute=True).get_mute() is True


def test_stub_set_mute():
    backend = StubAudioBackend()
    backend.set_mute(True)
    assert backend.get_mute() is True
    backend.set_mute(False)
    assert backend.get_mute() is False


def test_stub_is_audio_backend():
    assert isinstance(StubAudioBackend(), AudioBackend)
