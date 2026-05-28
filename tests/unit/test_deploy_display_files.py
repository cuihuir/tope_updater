"""Static tests for display switcher deployment files."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_updater_service_sets_pythonpath():
    service = (ROOT / "deploy" / "tope-updater.service").read_text(
        encoding="utf-8"
    )

    assert "Environment=PYTHONPATH=/opt/tope/updater/src" in service


def test_updater_gui_service_uses_printer_gui_python_runtime():
    service = (ROOT / "deploy" / "tope-updater-gui.service").read_text(
        encoding="utf-8"
    )

    assert "Description=TOPE OTA Updater GUI (EGLFS)" in service
    assert "Conflicts=printer-gui-eglfs.service" in service
    assert "Environment=PYTHONPATH=/opt/tope/updater/src" in service
    assert (
        "ExecStart=/opt/tope/services/printer-gui-qml/.venv/bin/python "
        "-m updater.qt_gui.main"
    ) in service


def test_install_script_installs_display_switcher_files():
    script = (ROOT / "deploy" / "install.sh").read_text(encoding="utf-8")

    assert "install -m 0755" in script
    assert "deploy/tope-display-switcher" in script
    assert "/usr/local/bin/tope-display-switcher" in script
    assert "tope-updater-gui.service" in script
    assert "updater-gui-eglfs-kms.json" in script


def test_updater_gui_kms_config_exists():
    config = (ROOT / "deploy" / "updater-gui-eglfs-kms.json").read_text(
        encoding="utf-8"
    )

    assert '"/dev/dri/card0"' in config
    assert '"hwcursor": false' in config
