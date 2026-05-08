from micdot.hotkey import to_pynput_format, HotkeyListener


def test_modifiers_wrapped_in_angle_brackets():
    assert to_pynput_format("ctrl+shift+m") == "<ctrl>+<shift>+m"


def test_single_modifier():
    assert to_pynput_format("ctrl+m") == "<ctrl>+m"


def test_multiple_modifiers():
    assert to_pynput_format("alt+shift+f4") == "<alt>+<shift>+f4"


def test_plain_key_unchanged():
    assert to_pynput_format("f12") == "f12"


def test_listener_start_creates_hotkey_and_listener(mocker):
    mock_hotkey_cls = mocker.patch("micdot.hotkey.keyboard.HotKey")
    mock_parse = mocker.patch("micdot.hotkey.keyboard.HotKey.parse")
    mock_listener_cls = mocker.patch("micdot.hotkey.keyboard.Listener")
    callback = mocker.Mock()

    listener = HotkeyListener("ctrl+shift+m", callback)
    listener.start()

    mock_parse.assert_called_once_with("<ctrl>+<shift>+m")
    mock_hotkey_cls.assert_called_once_with(mock_parse.return_value, callback)
    mock_listener_cls.assert_called_once()
    mock_listener_cls.return_value.start.assert_called_once()


def test_listener_stop_delegates(mocker):
    mocker.patch("micdot.hotkey.keyboard.HotKey")
    mocker.patch("micdot.hotkey.keyboard.HotKey.parse")
    mock_listener_cls = mocker.patch("micdot.hotkey.keyboard.Listener")

    listener = HotkeyListener("ctrl+m", mocker.Mock())
    listener.start()
    listener.stop()

    mock_listener_cls.return_value.stop.assert_called_once()
    mock_listener_cls.return_value.join.assert_called_once()


def test_listener_stop_before_start_is_noop(mocker):
    mocker.patch("micdot.hotkey.keyboard.HotKey")
    mocker.patch("micdot.hotkey.keyboard.HotKey.parse")
    mocker.patch("micdot.hotkey.keyboard.Listener")
    listener = HotkeyListener("ctrl+m", mocker.Mock())
    listener.stop()  # must not raise


def test_listener_update_replaces_hotkey(mocker):
    mock_hotkey_cls = mocker.patch("micdot.hotkey.keyboard.HotKey")
    mock_parse = mocker.patch("micdot.hotkey.keyboard.HotKey.parse")
    mocker.patch("micdot.hotkey.keyboard.Listener")
    callback = mocker.Mock()
    new_callback = mocker.Mock()

    listener = HotkeyListener("ctrl+shift+m", callback)
    listener.start()
    listener.update("ctrl+shift+x", new_callback)

    mock_parse.assert_called_with("<ctrl>+<shift>+x")
    assert listener._hotkey is mock_hotkey_cls.return_value
