"""Static tests for display switcher deployment files."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_updater_service_sets_pythonpath():
    service = (ROOT / "deploy" / "tope-updater.service").read_text(
        encoding="utf-8"
    )

    assert "Environment=PYTHONPATH=/opt/tope/updater/src" in service


def test_updater_service_sets_writable_display_switcher_lock():
    service = (ROOT / "deploy" / "tope-updater.service").read_text(
        encoding="utf-8"
    )

    assert (
        "Environment=TOPE_DISPLAY_SWITCHER_LOCK="
        "/opt/tope/updater/tmp/display-switcher.lock"
    ) in service


def test_updater_service_can_install_managed_system_units():
    service = (ROOT / "deploy" / "tope-updater.service").read_text(
        encoding="utf-8"
    )

    assert "/etc/systemd/system" in service
    assert "/usr/local/bin" in service


def test_updater_service_can_update_home_managed_services():
    service = (ROOT / "deploy" / "tope-updater.service").read_text(
        encoding="utf-8"
    )

    assert "/home/tope" not in service
    assert "ReadWritePaths=/opt/tope/updater/tmp" in service


def test_updater_gui_service_uses_printer_gui_python_runtime():
    service = (ROOT / "deploy" / "tope-updater-gui.service").read_text(
        encoding="utf-8"
    )

    assert "Description=TOPE OTA Updater GUI (EGLFS)" in service
    assert "Conflicts=printer-gui-eglfs.service" in service
    assert "Environment=PYTHONPATH=/opt/tope/updater/src" in service
    assert (
        "ConditionPathExists=/opt/tope/services/printer-gui/.venv/bin/python"
        in service
    )
    assert (
        "ExecStart=/opt/tope/services/printer-gui/.venv/bin/python "
        "-m updater.qt_gui.main"
    ) in service
    assert "/home/tope/printer-gui-qml" not in service


def test_install_script_installs_display_switcher_files():
    script = (ROOT / "deploy" / "install.sh").read_text(encoding="utf-8")

    assert "install -m 0755" in script
    assert "deploy/tope-display-switcher" in script
    assert "/usr/local/bin/tope-display-switcher" in script
    assert "tope-updater-gui.service" in script
    assert "updater-gui-eglfs-kms.json" in script
    assert "tope-console-quiet.service" in script
    assert "tope-console-hotkey.service" in script
    assert "tope-console-hotkey" in script
    assert "99-tope-console-quiet.conf" in script
    assert "99-tope-rescue-tty.conf" in script
    assert "getty@tty1.service getty@tty2.service getty@tty3.service" in script
    assert "getty@tty4.service getty@tty5.service getty@tty6.service" in script
    assert "enable --now getty@tty9.service" in script
    assert "enable --now tope-console-hotkey.service" in script


def test_setup_symlinks_keeps_services_pointing_at_current():
    script = (ROOT / "deploy" / "setup_symlinks.sh").read_text(encoding="utf-8")

    assert 'SERVICE_LINK_ROOT="$CURRENT_LINK/services"' in script
    assert 'ln -s "$SERVICE_LINK_ROOT/$service_name" "$symlink_path"' in script
    assert 'SERVICE_LINK_ROOT="$CURRENT_VERSION/services"' not in script


def test_updater_gui_kms_config_exists():
    config = (ROOT / "deploy" / "updater-gui-eglfs-kms.json").read_text(
        encoding="utf-8"
    )

    assert '"/dev/dri/card0"' in config
    assert '"hwcursor": false' in config


def test_display_switcher_quiets_physical_console():
    script = (ROOT / "deploy" / "tope-display-switcher").read_text(
        encoding="utf-8"
    )

    assert "tope-display-switcher show console" in script
    assert "quiet_console()" in script
    assert "restore_console()" in script
    assert "dmesg -n 1" in script
    assert "/proc/sys/kernel/printk" in script
    assert "setterm -cursor off" in script
    assert "setterm -cursor on" in script
    assert "enable --now \"$CONSOLE_GETTY_SERVICE\"" in script
    assert "/dev/tty6" in script
    assert "getty@tty9.service" in script


def test_console_quiet_service_disables_tty_noise():
    service = (ROOT / "deploy" / "tope-console-quiet.service").read_text(
        encoding="utf-8"
    )
    sysctl = (ROOT / "deploy" / "99-tope-console-quiet.conf").read_text(
        encoding="utf-8"
    )

    assert "Before=getty.target" in service
    assert "printer-gui-eglfs.service" in service
    assert "tope-updater-gui.service" in service
    assert "/dev/tty6" in service
    assert "/dev/tty9" not in service
    assert "kernel.printk = 1 1 1 1" in sysctl


def test_logind_config_only_allows_explicit_rescue_tty():
    config = (ROOT / "deploy" / "99-tope-rescue-tty.conf").read_text(
        encoding="utf-8"
    )

    assert "NAutoVTs=0" in config
    assert "ReserveVT=0" in config


def test_console_hotkey_triggers_rescue_console():
    service = (ROOT / "deploy" / "tope-console-hotkey.service").read_text(
        encoding="utf-8"
    )
    script = (ROOT / "deploy" / "tope-console-hotkey").read_text(
        encoding="utf-8"
    )

    assert "ExecStart=/usr/local/bin/tope-console-hotkey" in service
    assert "Restart=always" in service
    assert "KEY_F9" in script
    assert "KEY_F10" in script
    assert "KEY_LEFTCTRL" in script
    assert "KEY_LEFTALT" in script
    assert "tope-display-switcher" in script
    assert "show" in script
    assert "console" in script
    assert "printer" in script
    assert "toggle_rescue_console" in script
    assert "printer-gui-eglfs.service" in script
    assert "triggered_hotkeys" in script
    assert "value == 1" in script
