"""Static contract tests for the Qt updater GUI files."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_qt_gui_entrypoint_uses_progress_model():
    source = (ROOT / "src" / "updater" / "qt_gui" / "main.py").read_text(
        encoding="utf-8"
    )

    assert "class ProgressModel" in source
    assert "TOPE_UPDATER_PROGRESS_URL" in source
    assert "progressModel" in source
    assert "UpdaterWindow.qml" in source


def test_qml_window_is_fullscreen_and_display_only():
    source = (
        ROOT / "src" / "updater" / "qt_gui" / "qml" / "UpdaterWindow.qml"
    ).read_text(encoding="utf-8")

    assert "visibility: Window.FullScreen" in source
    assert "progressModel.progress" in source
    assert "progressModel.message" in source
    assert "Update Failed" in source
    assert "Update Complete" in source

def test_qml_window_rotates_to_landscape_panel():
    source = (
        ROOT / "src" / "updater" / "qt_gui" / "qml" / "UpdaterWindow.qml"
    ).read_text(encoding="utf-8")

    assert "width: root.height" in source
    assert "height: root.width" in source
    assert "rotation: 90" in source

def test_qml_terminal_state_has_countdown_and_ok_exit():
    source = (
        ROOT / "src" / "updater" / "qt_gui" / "qml" / "UpdaterWindow.qml"
    ).read_text(encoding="utf-8")

    assert "progressModel.terminal" in source
    assert "progressModel.countdownSeconds" in source
    assert "tickTerminalCountdown" in source
    assert "confirmExit" in source
    assert "OK" in source
