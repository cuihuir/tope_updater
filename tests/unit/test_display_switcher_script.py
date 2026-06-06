"""Unit tests for the tope-display-switcher script."""

import os
import subprocess
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[2] / "deploy" / "tope-display-switcher"


def _write_fake_systemctl(tmp_path: Path, body: str) -> None:
    fake = tmp_path / "systemctl"
    fake.write_text(body, encoding="utf-8")
    fake.chmod(0o755)


def _run_switcher(tmp_path: Path, *args: str) -> subprocess.CompletedProcess:
    env = {
        **os.environ,
        "PATH": f"{tmp_path}:{os.environ['PATH']}",
        "TOPE_DISPLAY_SWITCHER_LOCK": str(tmp_path / "display.lock"),
        "TOPE_DISPLAY_SWITCHER_TIMEOUT": "1",
        "TOPE_DISPLAY_SWITCHER_INTERVAL": "0.01",
        "TOPE_DISPLAY_SWITCHER_QUIET_CONSOLE": "0",
    }
    return subprocess.run(
        [str(SCRIPT), *args],
        text=True,
        capture_output=True,
        env=env,
        check=False,
    )


def test_show_updater_stops_printer_and_starts_updater(tmp_path):
    calls = tmp_path / "calls"
    _write_fake_systemctl(
        tmp_path,
        f"""#!/usr/bin/env bash
echo "$*" >> "{calls}"
if [ "$1" = "is-active" ]; then
  if [ "$2" = "printer-gui-eglfs.service" ]; then echo inactive; exit 3; fi
  if [ "$2" = "tope-updater-gui.service" ]; then echo active; exit 0; fi
fi
exit 0
""",
    )

    result = _run_switcher(tmp_path, "show", "updater")

    assert result.returncode == 0, result.stderr
    assert calls.read_text(encoding="utf-8").splitlines() == [
        "disable --now getty@tty1.service",
        "reset-failed getty@tty1.service",
        "enable --now getty@tty9.service",
        "stop printer-gui-eglfs.service",
        "is-active printer-gui-eglfs.service",
        "reset-failed printer-gui-eglfs.service",
        "start tope-updater-gui.service",
        "is-active tope-updater-gui.service",
    ]


def test_show_printer_stops_updater_and_starts_printer(tmp_path):
    calls = tmp_path / "calls"
    _write_fake_systemctl(
        tmp_path,
        f"""#!/usr/bin/env bash
echo "$*" >> "{calls}"
if [ "$1" = "is-active" ]; then
  if [ "$2" = "tope-updater-gui.service" ]; then echo failed; exit 3; fi
  if [ "$2" = "printer-gui-eglfs.service" ]; then echo active; exit 0; fi
fi
exit 0
""",
    )

    result = _run_switcher(tmp_path, "show", "printer")

    assert result.returncode == 0, result.stderr
    assert "reset-failed tope-updater-gui.service" in calls.read_text(
        encoding="utf-8"
    )
    assert "disable --now getty@tty1.service" in calls.read_text(encoding="utf-8")

def test_show_console_stops_guis_and_starts_tty_login(tmp_path):
    calls = tmp_path / "calls"
    _write_fake_systemctl(
        tmp_path,
        f"""#!/usr/bin/env bash
echo "$*" >> "{calls}"
if [ "$1" = "is-active" ]; then
  if [ "$2" = "tope-updater-gui.service" ]; then echo inactive; exit 3; fi
  if [ "$2" = "printer-gui-eglfs.service" ]; then echo inactive; exit 3; fi
  if [ "$2" = "getty@tty9.service" ]; then echo active; exit 0; fi
fi
exit 0
""",
    )

    result = _run_switcher(tmp_path, "show", "console")

    assert result.returncode == 0, result.stderr
    assert calls.read_text(encoding="utf-8").splitlines() == [
        "stop tope-updater-gui.service",
        "is-active tope-updater-gui.service",
        "reset-failed tope-updater-gui.service",
        "stop printer-gui-eglfs.service",
        "is-active printer-gui-eglfs.service",
        "reset-failed printer-gui-eglfs.service",
        "enable --now getty@tty9.service",
        "is-active getty@tty9.service",
    ]


def test_status_fails_when_both_guis_are_active(tmp_path):
    _write_fake_systemctl(
        tmp_path,
        """#!/usr/bin/env bash
if [ "$1" = "is-active" ]; then echo active; exit 0; fi
exit 0
""",
    )

    result = _run_switcher(tmp_path, "status")

    assert result.returncode != 0
    assert "both display services are active" in result.stderr

def test_quiet_console_default_includes_rescue_tty():
    source = SCRIPT.read_text(encoding="utf-8")

    assert (
        'CONSOLE_TTYS="${TOPE_DISPLAY_SWITCHER_CONSOLE_TTYS:-'
        '/dev/tty1 /dev/tty3 /dev/tty4 /dev/tty5 /dev/tty6 /dev/tty9}"'
    ) in source
    assert 'RESCUE_TTYS="${TOPE_DISPLAY_SWITCHER_RESCUE_TTYS:-/dev/tty9}"' in source

def test_gui_transitions_restore_rescue_tty_after_target_is_active():
    source = SCRIPT.read_text(encoding="utf-8")

    assert "restore_rescue_console()" in source
    assert "wait_active \"$UPDATER_GUI_SERVICE\"\n  quiet_console\n  restore_rescue_console" in source
    assert "wait_active \"$PRINTER_GUI_SERVICE\"\n  quiet_console\n  restore_rescue_console" in source
