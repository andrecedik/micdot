from __future__ import annotations
import ctypes
from espmuter.audio.backend import AudioBackend

_ca = ctypes.cdll.LoadLibrary(
    "/System/Library/Frameworks/CoreAudio.framework/CoreAudio"
)

_kAudioObjectSystemObject = 1
_kAudioHardwarePropertyDefaultInputDevice = 0x64496E20  # 'dIn '
_kAudioDevicePropertyMute = 0x6D757465              # 'mute'
_kAudioObjectPropertyScopeGlobal = 0x676C6F62       # 'glob'
_kAudioObjectPropertyScopeInput = 0x696E7074        # 'inpt'
_kAudioObjectPropertyElementMain = 0


class _AudioObjectPropertyAddress(ctypes.Structure):
    _fields_ = [
        ("mSelector", ctypes.c_uint32),
        ("mScope", ctypes.c_uint32),
        ("mElement", ctypes.c_uint32),
    ]


_ca.AudioObjectGetPropertyData.restype = ctypes.c_int32
_ca.AudioObjectGetPropertyData.argtypes = [
    ctypes.c_uint32,                                  # inObjectID
    ctypes.POINTER(_AudioObjectPropertyAddress),      # inAddress
    ctypes.c_uint32,                                  # inQualifierDataSize
    ctypes.c_void_p,                                  # inQualifierData
    ctypes.POINTER(ctypes.c_uint32),                  # ioDataSize
    ctypes.c_void_p,                                  # outData
]

_ca.AudioObjectSetPropertyData.restype = ctypes.c_int32
_ca.AudioObjectSetPropertyData.argtypes = [
    ctypes.c_uint32,                                  # inObjectID
    ctypes.POINTER(_AudioObjectPropertyAddress),      # inAddress
    ctypes.c_uint32,                                  # inQualifierDataSize
    ctypes.c_void_p,                                  # inQualifierData
    ctypes.c_uint32,                                  # inDataSize
    ctypes.c_void_p,                                  # inData
]


def _get_default_input_device() -> int:
    prop = _AudioObjectPropertyAddress(
        _kAudioHardwarePropertyDefaultInputDevice,
        _kAudioObjectPropertyScopeGlobal,
        _kAudioObjectPropertyElementMain,
    )
    device_id = ctypes.c_uint32(0)
    size = ctypes.c_uint32(ctypes.sizeof(device_id))
    status = _ca.AudioObjectGetPropertyData(
        _kAudioObjectSystemObject, ctypes.byref(prop),
        0, None, ctypes.byref(size), ctypes.byref(device_id),
    )
    if status != 0:
        raise OSError(f"CoreAudio: AudioObjectGetPropertyData returned {status}")
    return device_id.value


class MacOSAudioBackend(AudioBackend):
    def get_mute(self) -> bool:
        device_id = _get_default_input_device()
        prop = _AudioObjectPropertyAddress(
            _kAudioDevicePropertyMute,
            _kAudioObjectPropertyScopeInput,
            _kAudioObjectPropertyElementMain,
        )
        mute = ctypes.c_uint32(0)
        size = ctypes.c_uint32(ctypes.sizeof(mute))
        _ca.AudioObjectGetPropertyData(
            device_id, ctypes.byref(prop),
            0, None, ctypes.byref(size), ctypes.byref(mute),
        )
        return bool(mute.value)

    def set_mute(self, muted: bool) -> None:
        device_id = _get_default_input_device()
        prop = _AudioObjectPropertyAddress(
            _kAudioDevicePropertyMute,
            _kAudioObjectPropertyScopeInput,
            _kAudioObjectPropertyElementMain,
        )
        mute = ctypes.c_uint32(int(muted))
        size = ctypes.c_uint32(ctypes.sizeof(mute))
        _ca.AudioObjectSetPropertyData(
            device_id, ctypes.byref(prop),
            0, None, size, ctypes.byref(mute),
        )
