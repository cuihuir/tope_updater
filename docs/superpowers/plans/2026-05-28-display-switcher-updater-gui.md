# Display Switcher Updater GUI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the production SDL overlay path with a systemd-managed display switcher and an independent Qt EGLFS updater progress GUI.

**Architecture:** `tope-updater` calls a small `DisplaySwitchService`, which shells out to `/usr/local/bin/tope-display-switcher`. The switcher owns systemd display transitions between `printer-gui-eglfs.service` and `tope-updater-gui.service`. The updater GUI is a display-only PySide6/QML app that polls `/api/v1.0/progress`.

**Tech Stack:** Python 3.11, FastAPI, pytest, systemd, shell script, PySide6/QML via the existing `printer-gui` runtime on device.

---

## File Map

- Modify: `src/updater/services/process.py`  
  Make stop verification accept `inactive` and `failed`, and reset failed services after a successful stop.

- Modify: `tests/unit/test_process.py`  
  Add stop-service tests for failed-as-stopped and reset-failed behavior.

- Create: `deploy/tope-display-switcher`  
  Shell command used on device to switch display owner.

- Create: `tests/unit/test_display_switcher_script.py`  
  Test the switcher script using a fake `systemctl` in `PATH`.

- Create: `src/updater/services/display.py`  
  Async wrapper around `tope-display-switcher`.

- Create: `tests/unit/test_display.py`  
  Unit tests for display switch wrapper timeout/failure behavior.

- Modify: `src/updater/api/routes.py`  
  Remove production use of `GUILauncher`; call `DisplaySwitchService` in `_update_workflow()`.

- Modify: `tests/unit/test_routes.py`  
  Update route and workflow tests for display switching.

- Create: `src/updater/qt_gui/__init__.py`  
  Qt GUI package marker.

- Create: `src/updater/qt_gui/progress_client.py`  
  Poll and normalize updater progress responses.

- Create: `src/updater/qt_gui/main.py`  
  PySide6 entrypoint and QML context binding.

- Create: `src/updater/qt_gui/qml/UpdaterWindow.qml`  
  Fullscreen install progress UI.

- Create: `tests/unit/test_qt_progress_client.py`  
  Unit tests for progress response normalization.

- Create: `deploy/tope-updater-gui.service`  
  systemd service for the updater GUI.

- Create: `deploy/updater-gui-eglfs-kms.json`  
  EGLFS KMS config matching the printer GUI style.

- Modify: `deploy/install.sh`  
  Install switcher, updater GUI service, KMS config, and reload systemd.

- Modify: `deploy/tope-updater.service`  
  Add `Environment=PYTHONPATH=/opt/tope/updater/src`.

- Modify: `README.md` or `docs/SHIPMENT_OTA_NOTES.md`  
  Link the new switcher deployment and test commands.

---

### Task 1: ProcessManager Stop Semantics

**Files:**
- Modify: `src/updater/services/process.py`
- Modify: `tests/unit/test_process.py`

- [ ] **Step 1: Add failing tests for failed-as-stopped**

Append tests to `tests/unit/test_process.py`:

```python
    @pytest.mark.asyncio
    async def test_stop_service_accepts_failed_as_stopped(self, process_manager):
        """A stopped service may be reported by systemd as failed."""
        mock_stop = AsyncMock()
        mock_stop.communicate = AsyncMock(return_value=(b"", b""))
        mock_stop.returncode = 0

        mock_reset = AsyncMock()
        mock_reset.communicate = AsyncMock(return_value=(b"", b""))
        mock_reset.returncode = 0

        created = [mock_stop, mock_reset]

        async def fake_exec(*args, **kwargs):
            return created.pop(0)

        with patch("asyncio.create_subprocess_exec", side_effect=fake_exec) as exec_mock:
            with patch.object(
                process_manager,
                "wait_for_service_stopped",
                new_callable=AsyncMock,
            ) as wait_mock:
                wait_mock.return_value = ServiceStatus.FAILED

                await process_manager.stop_service("printer-gui-eglfs.service")

        wait_mock.assert_called_once_with(
            "printer-gui-eglfs.service",
            timeout=ProcessManager.STOP_TIMEOUT,
        )
        assert exec_mock.call_args_list[1].args == (
            "systemctl",
            "reset-failed",
            "printer-gui-eglfs.service",
        )

    @pytest.mark.asyncio
    async def test_wait_for_service_stopped_accepts_inactive(self, process_manager):
        with patch.object(
            process_manager,
            "get_service_status",
            return_value=ServiceStatus.INACTIVE,
        ):
            result = await process_manager.wait_for_service_stopped(
                "test.service",
                timeout=1.0,
                check_interval=0.01,
            )

        assert result == ServiceStatus.INACTIVE

    @pytest.mark.asyncio
    async def test_wait_for_service_stopped_accepts_failed(self, process_manager):
        with patch.object(
            process_manager,
            "get_service_status",
            return_value=ServiceStatus.FAILED,
        ):
            result = await process_manager.wait_for_service_stopped(
                "test.service",
                timeout=1.0,
                check_interval=0.01,
            )

        assert result == ServiceStatus.FAILED
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
uv run pytest tests/unit/test_process.py -q
```

Expected: tests fail because `wait_for_service_stopped()` does not exist and `stop_service()` still waits only for `inactive`.

- [ ] **Step 3: Implement stopped-state helper and reset-failed**

Update `src/updater/services/process.py`:

```python
    async def stop_service(
        self,
        service_name: str,
        timeout: float = STOP_TIMEOUT,
    ) -> None:
        """Stop a systemd service with verification."""
        self.logger.info(f"Stopping service: {service_name}")

        process = await asyncio.create_subprocess_exec(
            "systemctl",
            "stop",
            service_name,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            error_msg = stderr.decode().strip()
            self.logger.error(
                f"systemctl stop failed for {service_name}: "
                f"exit code {process.returncode}, error: {error_msg}"
            )
            raise RuntimeError(
                f"SERVICE_STOP_FAILED: systemctl stop {service_name} "
                f"failed with exit code {process.returncode}: {error_msg}"
            )

        try:
            stopped_status = await self.wait_for_service_stopped(
                service_name,
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            self.logger.error(
                f"Service {service_name} did not stop within {timeout}s"
            )
            raise TimeoutError(
                f"SERVICE_STOP_TIMEOUT: {service_name} did not stop "
                f"within {timeout}s (may be stuck)"
            )

        if stopped_status == ServiceStatus.FAILED:
            await self.reset_failed(service_name)

        self.logger.info(
            f"Service {service_name} stopped successfully "
            f"({stopped_status.value})"
        )

    async def wait_for_service_stopped(
        self,
        service_name: str,
        timeout: float,
        check_interval: float = STATUS_CHECK_INTERVAL,
    ) -> ServiceStatus:
        """Wait until systemd reports the service is no longer running."""
        start_time = asyncio.get_event_loop().time()

        while True:
            current_status = await self.get_service_status(service_name)

            if current_status in {ServiceStatus.INACTIVE, ServiceStatus.FAILED}:
                return current_status

            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed >= timeout:
                raise asyncio.TimeoutError(
                    f"Service {service_name} did not stop within {timeout}s "
                    f"(current: {current_status.value})"
                )

            await asyncio.sleep(check_interval)

    async def reset_failed(self, service_name: str) -> None:
        """Clear systemd failed state after a service has stopped."""
        process = await asyncio.create_subprocess_exec(
            "systemctl",
            "reset-failed",
            service_name,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        if process.returncode != 0:
            self.logger.warning(
                f"systemctl reset-failed failed for {service_name}: "
                f"{stderr.decode().strip()}"
            )
```

- [ ] **Step 4: Run tests**

Run:

```bash
uv run pytest tests/unit/test_process.py -q
```

Expected: all `test_process.py` tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/updater/services/process.py tests/unit/test_process.py
git commit --author="cuihuir <cuihuir@163.com>" -m "fix: accept failed service state after stop"
```

---

### Task 2: Display Switcher Script

**Files:**
- Create: `deploy/tope-display-switcher`
- Create: `tests/unit/test_display_switcher_script.py`

- [ ] **Step 1: Write script tests with fake systemctl**

Create `tests/unit/test_display_switcher_script.py`:

```python
import os
import subprocess
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[2] / "deploy" / "tope-display-switcher"


def _write_fake_systemctl(tmp_path: Path, body: str) -> Path:
    fake = tmp_path / "systemctl"
    fake.write_text(body, encoding="utf-8")
    fake.chmod(0o755)
    return fake


def _run_switcher(tmp_path: Path, *args: str) -> subprocess.CompletedProcess:
    env = {
        **os.environ,
        "PATH": f"{tmp_path}:{os.environ['PATH']}",
        "TOPE_DISPLAY_SWITCHER_LOCK": str(tmp_path / "display.lock"),
        "TOPE_DISPLAY_SWITCHER_TIMEOUT": "1",
        "TOPE_DISPLAY_SWITCHER_INTERVAL": "0.01",
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
    assert "reset-failed tope-updater-gui.service" in calls.read_text(encoding="utf-8")


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
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
uv run pytest tests/unit/test_display_switcher_script.py -q
```

Expected: fails because `deploy/tope-display-switcher` does not exist.

- [ ] **Step 3: Implement the switcher script**

Create `deploy/tope-display-switcher`:

```bash
#!/usr/bin/env bash
set -euo pipefail

PRINTER_GUI_SERVICE="${PRINTER_GUI_SERVICE:-printer-gui-eglfs.service}"
UPDATER_GUI_SERVICE="${UPDATER_GUI_SERVICE:-tope-updater-gui.service}"
LOCK_PATH="${TOPE_DISPLAY_SWITCHER_LOCK:-/run/tope-display-switcher.lock}"
TIMEOUT="${TOPE_DISPLAY_SWITCHER_TIMEOUT:-10}"
INTERVAL="${TOPE_DISPLAY_SWITCHER_INTERVAL:-0.2}"

log() {
  echo "[tope-display-switcher] $*"
}

err() {
  echo "[tope-display-switcher] ERROR: $*" >&2
}

usage() {
  cat >&2 <<EOF
Usage:
  tope-display-switcher show updater
  tope-display-switcher show printer
  tope-display-switcher blank
  tope-display-switcher status
EOF
}

is_active() {
  systemctl is-active "$1" >/dev/null 2>&1
}

active_state() {
  systemctl is-active "$1" 2>/dev/null || true
}

wait_stopped() {
  local service="$1"
  local elapsed="0"
  local state

  while true; do
    state="$(active_state "$service")"
    if [ "$state" = "inactive" ] || [ "$state" = "failed" ] || [ "$state" = "unknown" ]; then
      return 0
    fi

    if awk "BEGIN { exit !($elapsed >= $TIMEOUT) }"; then
      err "$service did not stop within ${TIMEOUT}s (state=$state)"
      return 1
    fi

    sleep "$INTERVAL"
    elapsed="$(awk "BEGIN { print $elapsed + $INTERVAL }")"
  done
}

wait_active() {
  local service="$1"
  local elapsed="0"

  while true; do
    if is_active "$service"; then
      return 0
    fi

    if awk "BEGIN { exit !($elapsed >= $TIMEOUT) }"; then
      err "$service did not become active within ${TIMEOUT}s"
      return 1
    fi

    sleep "$INTERVAL"
    elapsed="$(awk "BEGIN { print $elapsed + $INTERVAL }")"
  done
}

stop_and_reset() {
  local service="$1"
  log "stopping $service"
  systemctl stop "$service"
  wait_stopped "$service"
  systemctl reset-failed "$service" || true
}

show_updater() {
  stop_and_reset "$PRINTER_GUI_SERVICE"
  log "starting $UPDATER_GUI_SERVICE"
  systemctl start "$UPDATER_GUI_SERVICE"
  wait_active "$UPDATER_GUI_SERVICE"
}

show_printer() {
  stop_and_reset "$UPDATER_GUI_SERVICE"
  log "starting $PRINTER_GUI_SERVICE"
  systemctl start "$PRINTER_GUI_SERVICE"
  wait_active "$PRINTER_GUI_SERVICE"
}

blank() {
  stop_and_reset "$UPDATER_GUI_SERVICE"
  stop_and_reset "$PRINTER_GUI_SERVICE"
}

status() {
  local printer updater
  printer="$(active_state "$PRINTER_GUI_SERVICE")"
  updater="$(active_state "$UPDATER_GUI_SERVICE")"
  log "$PRINTER_GUI_SERVICE=$printer"
  log "$UPDATER_GUI_SERVICE=$updater"

  if [ "$printer" = "active" ] && [ "$updater" = "active" ]; then
    err "both display services are active"
    return 1
  fi
}

main() {
  if [ "$#" -lt 1 ]; then
    usage
    return 2
  fi

  mkdir -p "$(dirname "$LOCK_PATH")"
  exec 9>"$LOCK_PATH"
  flock -n 9 || {
    err "another display transition is running"
    return 1
  }

  case "${1:-}" in
    show)
      case "${2:-}" in
        updater) show_updater ;;
        printer) show_printer ;;
        *) usage; return 2 ;;
      esac
      ;;
    blank)
      blank
      ;;
    status)
      status
      ;;
    *)
      usage
      return 2
      ;;
  esac
}

main "$@"
```

- [ ] **Step 4: Make script executable and run tests**

Run:

```bash
chmod +x deploy/tope-display-switcher
uv run pytest tests/unit/test_display_switcher_script.py -q
```

Expected: script tests pass.

- [ ] **Step 5: Commit**

```bash
git add deploy/tope-display-switcher tests/unit/test_display_switcher_script.py
git commit --author="cuihuir <cuihuir@163.com>" -m "feat: add display switcher script"
```

---

### Task 3: DisplaySwitchService Wrapper

**Files:**
- Create: `src/updater/services/display.py`
- Create: `tests/unit/test_display.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/test_display.py`:

```python
import asyncio
from unittest.mock import AsyncMock, patch

import pytest

from updater.services.display import DisplaySwitchService


@pytest.mark.unit
class TestDisplaySwitchService:
    @pytest.mark.asyncio
    async def test_show_updater_returns_true_on_success(self):
        service = DisplaySwitchService(command="/usr/local/bin/tope-display-switcher")

        process = AsyncMock()
        process.communicate = AsyncMock(return_value=(b"ok\n", b""))
        process.returncode = 0

        with patch("asyncio.create_subprocess_exec", return_value=process) as create:
            result = await service.show_updater()

        assert result is True
        create.assert_called_once_with(
            "/usr/local/bin/tope-display-switcher",
            "show",
            "updater",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

    @pytest.mark.asyncio
    async def test_show_printer_returns_false_on_nonzero(self):
        service = DisplaySwitchService()

        process = AsyncMock()
        process.communicate = AsyncMock(return_value=(b"", b"failed\n"))
        process.returncode = 1

        with patch("asyncio.create_subprocess_exec", return_value=process):
            result = await service.show_printer()

        assert result is False

    @pytest.mark.asyncio
    async def test_show_updater_returns_false_on_timeout(self):
        service = DisplaySwitchService(timeout=0.01)

        process = AsyncMock()
        process.communicate = AsyncMock(side_effect=asyncio.TimeoutError)
        process.kill = AsyncMock()

        with patch("asyncio.create_subprocess_exec", return_value=process):
            result = await service.show_updater()

        assert result is False
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
uv run pytest tests/unit/test_display.py -q
```

Expected: import fails because `updater.services.display` does not exist.

- [ ] **Step 3: Implement wrapper**

Create `src/updater/services/display.py`:

```python
"""Display ownership switching through the systemd display switcher."""

import asyncio
import logging


class DisplaySwitchService:
    """Thin async wrapper around tope-display-switcher."""

    def __init__(
        self,
        command: str = "/usr/local/bin/tope-display-switcher",
        timeout: float = 15.0,
    ):
        self.command = command
        self.timeout = timeout
        self.logger = logging.getLogger("updater.display")

    async def show_updater(self) -> bool:
        return await self._run("show", "updater")

    async def show_printer(self) -> bool:
        return await self._run("show", "printer")

    async def blank(self) -> bool:
        return await self._run("blank")

    async def _run(self, *args: str) -> bool:
        try:
            process = await asyncio.create_subprocess_exec(
                self.command,
                *args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=self.timeout,
            )
        except asyncio.TimeoutError:
            self.logger.error("Display switch timed out: %s", " ".join(args))
            try:
                process.kill()
            except Exception:
                pass
            return False
        except Exception as exc:
            self.logger.warning("Display switch failed to start: %s", exc)
            return False

        if stdout:
            self.logger.info(stdout.decode(errors="replace").strip())
        if stderr:
            self.logger.warning(stderr.decode(errors="replace").strip())

        return process.returncode == 0
```

- [ ] **Step 4: Run tests**

Run:

```bash
uv run pytest tests/unit/test_display.py -q
```

Expected: all display wrapper tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/updater/services/display.py tests/unit/test_display.py
git commit --author="cuihuir <cuihuir@163.com>" -m "feat: add display switch service"
```

---

### Task 4: Integrate Display Switching Into Update Workflow

**Files:**
- Modify: `src/updater/api/routes.py`
- Modify: `tests/unit/test_routes.py`

- [ ] **Step 1: Update route tests away from GUILauncher**

In `tests/unit/test_routes.py`, change `TestPostUpdate.test_to_install_state_starts_update` and `test_gui_start_failure_still_proceeds` so they no longer patch `GUILauncher`. The `/update` route should only validate and schedule background work.

Add workflow tests:

```python
    @pytest.mark.asyncio
    async def test_update_workflow_switches_to_updater_before_deploy(self):
        from updater.api.routes import _update_workflow

        with patch("updater.api.routes.StateManager") as MockSM:
            with patch("updater.api.routes.ReportService"):
                with patch("updater.api.routes.DeployService") as MockDS:
                    with patch("updater.api.routes.DisplaySwitchService") as MockDisplay:
                        with patch("updater.api.routes.Path") as MockPath:
                            with patch("updater.api.routes.asyncio.sleep", new_callable=AsyncMock):
                                with patch("updater.api.routes.verify_md5_or_raise"):
                                    mock_sm = MagicMock()
                                    persistent = MagicMock()
                                    persistent.package_name = "pkg.zip"
                                    persistent.package_md5 = "d41d8cd98f00b204e9800998ecf8427e"
                                    mock_sm.get_persistent_state.return_value = persistent
                                    MockSM.return_value = mock_sm

                                    package_path = MagicMock()
                                    package_path.exists.return_value = True
                                    MockPath.return_value.__truediv__ = MagicMock(return_value=package_path)

                                    mock_deploy = MagicMock()
                                    mock_deploy.deploy_package = AsyncMock(return_value=None)
                                    MockDS.return_value = mock_deploy

                                    mock_display = MagicMock()
                                    mock_display.show_updater = AsyncMock(return_value=True)
                                    mock_display.show_printer = AsyncMock(return_value=True)
                                    MockDisplay.return_value = mock_display

                                    await _update_workflow("1.0.0")

        mock_display.show_updater.assert_awaited_once()
        mock_deploy.deploy_package.assert_awaited_once()
        mock_display.show_printer.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_update_workflow_continues_when_show_updater_fails(self):
        from updater.api.routes import _update_workflow

        with patch("updater.api.routes.StateManager") as MockSM:
            with patch("updater.api.routes.ReportService"):
                with patch("updater.api.routes.DeployService") as MockDS:
                    with patch("updater.api.routes.DisplaySwitchService") as MockDisplay:
                        with patch("updater.api.routes.Path") as MockPath:
                            with patch("updater.api.routes.asyncio.sleep", new_callable=AsyncMock):
                                with patch("updater.api.routes.verify_md5_or_raise"):
                                    mock_sm = MagicMock()
                                    persistent = MagicMock()
                                    persistent.package_name = "pkg.zip"
                                    persistent.package_md5 = "d41d8cd98f00b204e9800998ecf8427e"
                                    mock_sm.get_persistent_state.return_value = persistent
                                    MockSM.return_value = mock_sm

                                    package_path = MagicMock()
                                    package_path.exists.return_value = True
                                    MockPath.return_value.__truediv__ = MagicMock(return_value=package_path)

                                    mock_deploy = MagicMock()
                                    mock_deploy.deploy_package = AsyncMock(return_value=None)
                                    MockDS.return_value = mock_deploy

                                    mock_display = MagicMock()
                                    mock_display.show_updater = AsyncMock(return_value=False)
                                    mock_display.show_printer = AsyncMock(return_value=True)
                                    MockDisplay.return_value = mock_display

                                    await _update_workflow("1.0.0")

        mock_deploy.deploy_package.assert_awaited_once()
        mock_display.show_printer.assert_awaited_once()
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
uv run pytest tests/unit/test_routes.py -q
```

Expected: failures because `_update_workflow()` still takes `gui_launcher` and uses `GUILauncher`.

- [ ] **Step 3: Update route implementation**

Modify `src/updater/api/routes.py`:

```python
from updater.services.display import DisplaySwitchService
```

Remove:

```python
from updater.gui.launcher import GUILauncher
```

In `post_update()`, remove `GUILauncher()` creation and call:

```python
    background_tasks.add_task(_update_workflow, request.version)
```

Change workflow signature and final handling:

```python
async def _update_workflow(version: str) -> None:
    """Background task for update workflow."""
    state_manager = StateManager()
    reporter = ReportService()
    deploy_service = DeployService(reporter=reporter)
    display_service = DisplaySwitchService()

    try:
        persistent_state = state_manager.get_persistent_state()
        if not persistent_state:
            raise ValueError("No persistent state found")

        package_path = Path("./tmp") / persistent_state.package_name
        if not package_path.exists():
            raise FileNotFoundError(f"Package not found: {package_path}")

        verify_md5_or_raise(package_path, persistent_state.package_md5)

        if not await display_service.show_updater():
            logger.warning("Failed to switch display to updater GUI, continuing OTA")

        await deploy_service.deploy_package(package_path, version)

        state_manager.delete_state()
        await asyncio.sleep(65)
        state_manager.reset()

    except Exception as e:
        state_manager.update_status(
            stage=StageEnum.FAILED,
            progress=0,
            message="Update failed",
            error=f"UPDATE_FAILED: {str(e)}",
        )

    finally:
        if not await display_service.show_printer():
            logger.error("Failed to switch display back to printer GUI")
```

- [ ] **Step 4: Run route tests**

Run:

```bash
uv run pytest tests/unit/test_routes.py -q
```

Expected: route tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/updater/api/routes.py tests/unit/test_routes.py
git commit --author="cuihuir <cuihuir@163.com>" -m "feat: switch display during update workflow"
```

---

### Task 5: Qt Progress Client

**Files:**
- Create: `src/updater/qt_gui/__init__.py`
- Create: `src/updater/qt_gui/progress_client.py`
- Create: `tests/unit/test_qt_progress_client.py`

- [ ] **Step 1: Write progress client tests**

Create `tests/unit/test_qt_progress_client.py`:

```python
from updater.qt_gui.progress_client import normalize_progress


def test_normalize_success_response():
    result = normalize_progress(
        {
            "code": 200,
            "msg": "success",
            "data": {
                "stage": "installing",
                "progress": 42,
                "message": "Installing module printer-gui...",
                "error": None,
            },
        }
    )

    assert result == {
        "stage": "installing",
        "progress": 42,
        "message": "Installing module printer-gui...",
        "error": "",
        "terminal": False,
    }


def test_normalize_failed_response_is_terminal():
    result = normalize_progress(
        {
            "code": 500,
            "msg": "Update failed",
            "data": {
                "stage": "failed",
                "progress": 0,
                "message": "Update failed",
                "error": "DEPLOYMENT_FAILED",
            },
        }
    )

    assert result["stage"] == "failed"
    assert result["terminal"] is True
    assert result["error"] == "DEPLOYMENT_FAILED"


def test_normalize_invalid_response_returns_waiting_state():
    result = normalize_progress({"bad": "shape"})

    assert result["stage"] == "waiting"
    assert result["progress"] == 0
    assert result["terminal"] is False
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
uv run pytest tests/unit/test_qt_progress_client.py -q
```

Expected: import fails because `updater.qt_gui` does not exist.

- [ ] **Step 3: Implement progress client**

Create `src/updater/qt_gui/__init__.py` as an empty package marker.

Create `src/updater/qt_gui/progress_client.py`:

```python
"""Helpers for the Qt updater GUI progress model."""

import urllib.request
import json


def normalize_progress(payload: dict) -> dict:
    """Normalize updater /progress JSON for QML consumption."""
    try:
        data = payload["data"]
        stage = str(data["stage"])
        progress = int(data["progress"])
        message = str(data["message"])
        error = data.get("error") or ""
    except Exception:
        return {
            "stage": "waiting",
            "progress": 0,
            "message": "Waiting for updater...",
            "error": "",
            "terminal": False,
        }

    return {
        "stage": stage,
        "progress": max(0, min(100, progress)),
        "message": message,
        "error": str(error),
        "terminal": stage in {"success", "failed"},
    }


def fetch_progress(url: str, timeout: float = 1.0) -> dict:
    """Fetch and normalize updater progress using stdlib HTTP."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception:
        return normalize_progress({})
    return normalize_progress(payload)
```

- [ ] **Step 4: Run tests**

Run:

```bash
uv run pytest tests/unit/test_qt_progress_client.py -q
```

Expected: progress client tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/updater/qt_gui tests/unit/test_qt_progress_client.py
git commit --author="cuihuir <cuihuir@163.com>" -m "feat: add updater GUI progress client"
```

---

### Task 6: Minimal Qt EGLFS Updater GUI

**Files:**
- Create: `src/updater/qt_gui/main.py`
- Create: `src/updater/qt_gui/qml/UpdaterWindow.qml`

- [ ] **Step 1: Implement Qt entrypoint**

Create `src/updater/qt_gui/main.py`:

```python
"""Qt/QML updater progress GUI entrypoint."""

import os
import sys

from PySide6.QtCore import QObject, Property, QTimer, Signal, Slot
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

from updater.qt_gui.progress_client import fetch_progress


class ProgressModel(QObject):
    changed = Signal()

    def __init__(self, url: str):
        super().__init__()
        self.url = url
        self._stage = "waiting"
        self._progress = 0
        self._message = "Waiting for updater..."
        self._error = ""

    @Property(str, notify=changed)
    def stage(self):
        return self._stage

    @Property(int, notify=changed)
    def progress(self):
        return self._progress

    @Property(str, notify=changed)
    def message(self):
        return self._message

    @Property(str, notify=changed)
    def error(self):
        return self._error

    @Slot()
    def refresh(self):
        data = fetch_progress(self.url)
        self._stage = data["stage"]
        self._progress = data["progress"]
        self._message = data["message"]
        self._error = data["error"]
        self.changed.emit()


def main() -> int:
    app = QGuiApplication(sys.argv)
    url = os.environ.get(
        "TOPE_UPDATER_PROGRESS_URL",
        "http://127.0.0.1:12315/api/v1.0/progress",
    )
    model = ProgressModel(url)

    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("progressModel", model)
    qml_path = os.path.join(os.path.dirname(__file__), "qml", "UpdaterWindow.qml")
    engine.load(qml_path)

    if not engine.rootObjects():
        return 1

    timer = QTimer()
    timer.setInterval(500)
    timer.timeout.connect(model.refresh)
    timer.start()
    model.refresh()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Implement QML window**

Create `src/updater/qt_gui/qml/UpdaterWindow.qml`:

```qml
import QtQuick
import QtQuick.Controls

Window {
    id: root
    visible: true
    visibility: Window.FullScreen
    color: "#101418"

    Rectangle {
        anchors.fill: parent
        color: "#101418"

        Column {
            anchors.centerIn: parent
            width: Math.min(parent.width * 0.72, 720)
            spacing: 28

            Text {
                width: parent.width
                text: progressModel.stage === "failed" ? "Update Failed"
                    : progressModel.stage === "success" ? "Update Complete"
                    : "System Update"
                color: "#F4F7FA"
                font.pixelSize: 34
                horizontalAlignment: Text.AlignHCenter
                wrapMode: Text.WordWrap
            }

            Text {
                width: parent.width
                text: progressModel.error.length > 0 ? progressModel.error : progressModel.message
                color: progressModel.stage === "failed" ? "#FF6B6B" : "#B8C2CC"
                font.pixelSize: 22
                horizontalAlignment: Text.AlignHCenter
                wrapMode: Text.WordWrap
            }

            Rectangle {
                width: parent.width
                height: 18
                radius: 6
                color: "#2A3138"

                Rectangle {
                    width: parent.width * progressModel.progress / 100
                    height: parent.height
                    radius: 6
                    color: progressModel.stage === "failed" ? "#FF6B6B" : "#47D18C"
                }
            }

            Text {
                width: parent.width
                text: progressModel.progress + "%"
                color: "#F4F7FA"
                font.pixelSize: 28
                horizontalAlignment: Text.AlignHCenter
            }
        }
    }
}
```

- [ ] **Step 3: Smoke check import without PySide dependency in updater venv**

Run:

```bash
uv run python -c "from updater.qt_gui.progress_client import normalize_progress; print(normalize_progress({})['stage'])"
```

Expected: prints `waiting`.

Do not run `python -m updater.qt_gui.main` on a dev machine unless PySide6 is installed. The service runs it with the `printer-gui` Python runtime on device.

- [ ] **Step 4: Commit**

```bash
git add src/updater/qt_gui/main.py src/updater/qt_gui/qml/UpdaterWindow.qml
git commit --author="cuihuir <cuihuir@163.com>" -m "feat: add Qt updater progress GUI"
```

---

### Task 7: Deployment Units and Install Script

**Files:**
- Create: `deploy/tope-updater-gui.service`
- Create: `deploy/updater-gui-eglfs-kms.json`
- Modify: `deploy/tope-updater.service`
- Modify: `deploy/install.sh`

- [ ] **Step 1: Add updater GUI service**

Create `deploy/tope-updater-gui.service`:

```ini
[Unit]
Description=TOPE OTA Updater GUI (EGLFS)
After=tope-updater.service dbus.socket
Requires=tope-updater.service
Conflicts=printer-gui-eglfs.service
ConditionPathExists=/dev/dri/card0
ConditionPathExists=/opt/tope/services/printer-gui-qml/.venv/bin/python

[Service]
Type=simple
User=tope
Group=tope
WorkingDirectory=/opt/tope/updater
Environment=HOME=/home/tope
Environment=PYTHONPATH=/opt/tope/updater/src
Environment=QT_QPA_PLATFORM=eglfs
Environment=QT_QPA_EGLFS_INTEGRATION=eglfs_kms
Environment=QT_QPA_EGLFS_KMS_CONFIG=/opt/tope/updater/deploy/updater-gui-eglfs-kms.json
Environment=QSG_RHI_BACKEND=opengl
Environment=QT_QPA_EGLFS_HIDECURSOR=1
Environment=TOPE_UPDATER_PROGRESS_URL=http://127.0.0.1:12315/api/v1.0/progress
ExecStart=/opt/tope/services/printer-gui-qml/.venv/bin/python -m updater.qt_gui.main
Restart=no
TimeoutStopSec=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=tope-updater-gui
SupplementaryGroups=video render

[Install]
WantedBy=multi-user.target
```

- [ ] **Step 2: Add KMS config**

Create `deploy/updater-gui-eglfs-kms.json`:

```json
{
  "device": "/dev/dri/card0",
  "hwcursor": false,
  "pbuffers": true
}
```

- [ ] **Step 3: Add PYTHONPATH to updater service**

In `deploy/tope-updater.service`, add under `WorkingDirectory=/opt/tope/updater`:

```ini
Environment=PYTHONPATH=/opt/tope/updater/src
```

- [ ] **Step 4: Install files in deploy/install.sh**

Add install commands to `deploy/install.sh` near service installation:

```bash
install -m 0755 deploy/tope-display-switcher /usr/local/bin/tope-display-switcher
install -m 0644 deploy/tope-updater-gui.service /etc/systemd/system/tope-updater-gui.service
install -m 0644 deploy/updater-gui-eglfs-kms.json /opt/tope/updater/deploy/updater-gui-eglfs-kms.json
```

Ensure `systemctl daemon-reload` runs after these files are installed. Do not enable `tope-updater-gui.service`.

- [ ] **Step 5: Run static checks**

Run:

```bash
bash -n deploy/tope-display-switcher
bash -n deploy/install.sh
uv run ruff check src/ tests/
```

Expected: all checks pass.

- [ ] **Step 6: Commit**

```bash
git add deploy/tope-updater-gui.service deploy/updater-gui-eglfs-kms.json deploy/tope-updater.service deploy/install.sh
git commit --author="cuihuir <cuihuir@163.com>" -m "deploy: add updater GUI systemd units"
```

---

### Task 8: Documentation and Full Verification

**Files:**
- Modify: `docs/SHIPMENT_OTA_NOTES.md`
- Modify: `README.md` if needed

- [ ] **Step 1: Document the new runtime commands**

Add this section to `docs/SHIPMENT_OTA_NOTES.md`:

    ## Display switcher commands

    ```bash
    sudo tope-display-switcher status
    sudo tope-display-switcher show updater
    sudo tope-display-switcher show printer
    sudo tope-display-switcher blank
    ```

    On beta devices, `tope-updater-gui.service` uses the existing `printer-gui` PySide6 runtime and imports updater GUI code through `PYTHONPATH=/opt/tope/updater/src`.

- [ ] **Step 2: Run focused tests**

Run:

```bash
uv run pytest tests/unit/test_process.py tests/unit/test_display.py tests/unit/test_display_switcher_script.py tests/unit/test_routes.py tests/unit/test_qt_progress_client.py -q
```

Expected: focused tests pass.

- [ ] **Step 3: Run full unit suite**

Run:

```bash
uv run pytest tests/unit/ -q
```

Expected: all unit tests pass.

- [ ] **Step 4: Run lint and shell syntax checks**

Run:

```bash
uv run ruff check src/ tests/
bash -n deploy/tope-display-switcher
bash -n deploy/install.sh
```

Expected: all checks pass.

- [ ] **Step 5: Commit**

```bash
git add docs/SHIPMENT_OTA_NOTES.md README.md
git commit --author="cuihuir <cuihuir@163.com>" -m "docs: document display switcher workflow"
```

---

## Device Validation Checklist

Run on target device after deploying the new files:

```bash
sudo systemctl daemon-reload
sudo systemctl restart tope-updater.service
sudo tope-display-switcher status
sudo tope-display-switcher show updater
sudo systemctl status tope-updater-gui.service --no-pager
sudo tope-display-switcher show printer
sudo systemctl status printer-gui-eglfs.service --no-pager
```

Then run OTA:

```bash
curl -X POST http://127.0.0.1:12315/api/v1.0/download \
  -H "Content-Type: application/json" \
  -d @download-payload.json

curl -X POST http://127.0.0.1:12315/api/v1.0/update \
  -H "Content-Type: application/json" \
  -d '{"version":"0.1.1"}'
```

Expected device result:

- updater GUI appears during install;
- printer GUI stops before updater GUI starts;
- printer GUI returns after success or failure;
- `journalctl -u tope-updater -u tope-updater-gui -u printer-gui-eglfs` contains clear transition logs;
- no OTA rollback is triggered solely because updater GUI failed to start.

## Plan Self-Review

- Spec coverage: covers process stop semantics, switcher, updater integration, Qt GUI, deployment files, and device validation.
- Incomplete-marker scan: runtime paths and service names are explicit.
- Type consistency: `DisplaySwitchService.show_updater()` and `show_printer()` are async bool-returning methods used consistently in route workflow tests and implementation.
- Scope check: does not include system package OTA or modifications to `ota-service`.
