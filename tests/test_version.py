import sys
from unittest.mock import MagicMock


def test_get_version_returns_package_version_when_not_frozen():
    from micdot import __version__
    from micdot.version import get_version
    assert get_version() == __version__


def test_get_version_reads_nsbundle_when_frozen(mocker):
    mock_foundation = MagicMock()
    mock_foundation.NSBundle.mainBundle.return_value.infoDictionary.return_value = {
        "CFBundleShortVersionString": "9.9.9"
    }
    mocker.patch.object(sys, "frozen", True, create=True)
    mocker.patch.dict("sys.modules", {"Foundation": mock_foundation})

    from micdot.version import get_version
    assert get_version() == "9.9.9"


def test_get_version_falls_back_when_nsbundle_raises(mocker):
    from micdot import __version__
    mock_foundation = MagicMock()
    mock_foundation.NSBundle.mainBundle.side_effect = Exception("no bundle")
    mocker.patch.object(sys, "frozen", True, create=True)
    mocker.patch.dict("sys.modules", {"Foundation": mock_foundation})

    from micdot.version import get_version
    assert get_version() == __version__
