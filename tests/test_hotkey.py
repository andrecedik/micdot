from micdot.hotkey import to_pynput_format, HotkeyListener


def test_modifiers_wrapped_in_angle_brackets():
    assert to_pynput_format("ctrl+shift+m") == "<ctrl>+<shift>+m"


def test_single_modifier():
    assert to_pynput_format("ctrl+m") == "<ctrl>+m"


def test_multiple_modifiers():
    assert to_pynput_format("alt+shift+f4") == "<alt>+<shift>+f4"


def test_plain_key_unchanged():
    assert to_pynput_format("f12") == "f12"


def test_listener_registers_correct_hotkey(mocker):
    mock_cls = mocker.patch("micdot.hotkey.keyboard.GlobalHotKeys")
    callback = mocker.Mock()
    listener = HotkeyListener("ctrl+shift+m", callback)
    listener.start()
    mock_cls.assert_called_once_with({"<ctrl>+<shift>+m": callback})
    mock_cls.return_value.start.assert_called_once()


def test_listener_stop_delegates(mocker):
    mock_cls = mocker.patch("micdot.hotkey.keyboard.GlobalHotKeys")
    listener = HotkeyListener("ctrl+m", mocker.Mock())
    listener.start()
    listener.stop()
    mock_cls.return_value.stop.assert_called_once()


def test_listener_stop_before_start_is_noop(mocker):
    mocker.patch("micdot.hotkey.keyboard.GlobalHotKeys")
    listener = HotkeyListener("ctrl+m", mocker.Mock())
    listener.stop()  # must not raise
