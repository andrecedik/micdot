import sys
import pytest
from micdot.audio.backend import AudioBackend, StubAudioBackend


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


# --- MacOSAudioBackend status handling (CoreAudio calls mocked) ---

@pytest.fixture
def mac(mocker):
    if sys.platform != "darwin":
        pytest.skip("CoreAudio only loads on macOS")
    from micdot.audio import macos
    ca = mocker.patch.object(macos, "_ca")
    return macos.MacOSAudioBackend(), ca


def test_get_mute_raises_when_property_read_fails(mac):
    backend, ca = mac
    # first call resolves the default device, second reads the mute property
    ca.AudioObjectGetPropertyData.side_effect = [0, 0x77686F3F]  # 'who?'
    with pytest.raises(OSError):
        backend.get_mute()


def test_get_mute_returns_bool_on_success(mac):
    backend, ca = mac
    ca.AudioObjectGetPropertyData.side_effect = [0, 0]
    assert backend.get_mute() is False


def test_set_mute_raises_when_property_write_fails(mac):
    backend, ca = mac
    ca.AudioObjectGetPropertyData.return_value = 0
    ca.AudioObjectSetPropertyData.return_value = 0x77686F3F  # 'who?'
    with pytest.raises(OSError):
        backend.set_mute(True)


def test_set_mute_succeeds_when_status_ok(mac):
    backend, ca = mac
    ca.AudioObjectGetPropertyData.return_value = 0
    ca.AudioObjectSetPropertyData.return_value = 0
    backend.set_mute(True)  # must not raise
