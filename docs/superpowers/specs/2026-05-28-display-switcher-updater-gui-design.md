# Systemd Display Switcher + Qt EGLFS Updater GUI Design

**Date:** 2026-05-28
**Status:** Ready for review
**Scope:** beta shipment OTA install-stage display control

## Goal

Build a reliable install-stage visual path for OTA on the EGLFS device:

- only one EGLFS process owns DRM/KMS at a time;
- OTA install progress is visible while `printer-gui-eglfs.service` is stopped;
- display control is deterministic through systemd, not window stacking;
- GUI failure does not block OTA file deployment and rollback.

This design replaces the current SDL child-process overlay behavior for the production EGLFS path. The existing SDL GUI can remain as a development/manual fallback until removed.

## Current Context

Current updater behavior:

- `POST /api/v1.0/update` creates a `GUILauncher`.
- `GUILauncher` starts `python -m updater.gui.progress_window` as a child process.
- `_update_workflow()` stops that child process in `finally`.

This is acceptable on desktop-like environments, but it is not reliable on Qt EGLFS. There is no window manager, no topmost layer, and the main `printer-gui-eglfs.service` owns the display device. Running a second GUI process as an overlay is not a stable production mechanism.

Current printer GUI behavior:

- `printer-gui` uses PySide6 + QML.
- `printer-gui-eglfs.service` starts `/usr/local/bin/printer-gui-eglfs-start.sh`.
- The script exports:
  - `QT_QPA_PLATFORM=eglfs`
  - `QT_QPA_EGLFS_INTEGRATION=eglfs_kms`
  - `QT_QPA_EGLFS_KMS_CONFIG=...`
  - `QSG_RHI_BACKEND=opengl`
  - `QT_QPA_EGLFS_HIDECURSOR=1`
- The current deployed service path still points at `/home/tope/printer-gui-qml`; shipment must move it to `/opt/tope/versions/current` or `/opt/tope/services`.

## Approaches Considered

### Recommended: systemd switcher + independent Qt EGLFS updater GUI

Updater calls a small command-line switcher:

```bash
tope-display-switcher show updater
tope-display-switcher show printer
tope-display-switcher blank
```

The switcher uses systemd to stop/start display-owner services. The updater GUI is its own PySide6/QML EGLFS service and polls `http://127.0.0.1:12315/api/v1.0/progress`.

Pros:

- Matches EGLFS ownership model.
- Keeps display control outside FastAPI route code.
- Easy to test with mocked `systemctl`.
- Uses the same Qt/PySide6 stack as `printer-gui`.
- Service-level restart, logging, permissions, and failure behavior are explicit.

Cons:

- Adds one script, one service unit, and a small Qt app.
- Requires careful boot/TTY hiding configuration to avoid console flashes.

### Alternative: updater directly stops printer GUI and starts Qt GUI

Updater would call `systemctl stop printer-gui-eglfs.service` and `systemctl start tope-updater-gui.service` directly.

Pros:

- Fewer files.

Cons:

- Couples OTA deployment logic to display policy.
- Harder to reuse for boot recovery or future display modes.
- More brittle when service names or fallback rules change.

### Rejected: SDL overlay or always-on-top window

This is the current direction in code and previous specs.

Reason for rejection:

- Qt EGLFS has no window manager.
- The main GUI owns DRM/KMS.
- "Always on top" is not a meaningful guarantee.
- Two EGLFS GUI processes competing for the display will be device/driver dependent.

## Architecture

```text
Cloud/device-api
      |
      v
tope-updater FastAPI
      |
      | install stage starts
      v
DisplaySwitchService
      |
      v
/usr/local/bin/tope-display-switcher show updater
      |
      +-- systemctl stop printer-gui-eglfs.service
      +-- systemctl reset-failed printer-gui-eglfs.service
      +-- systemctl start tope-updater-gui.service
      +-- verify updater GUI active
      |
      v
DeployService deploys package
      |
      | install completes or fails
      v
/usr/local/bin/tope-display-switcher show printer
      |
      +-- systemctl stop tope-updater-gui.service
      +-- systemctl reset-failed tope-updater-gui.service
      +-- systemctl start printer-gui-eglfs.service
      +-- verify printer GUI active
```

## Components

### 1. `tope-display-switcher`

Path:

```text
/usr/local/bin/tope-display-switcher
```

Interface:

```bash
tope-display-switcher show updater
tope-display-switcher show printer
tope-display-switcher blank
tope-display-switcher status
```

Responsibilities:

- serialize display transitions with a lock file;
- stop services that may own EGLFS;
- accept both `inactive` and `failed` as "not running";
- call `systemctl reset-failed` after failed-but-stopped states;
- start the requested GUI service;
- verify the requested GUI service reaches `active`;
- return non-zero on transition failure;
- write clear logs to stdout/stderr for journald.

Recommended service names:

```text
PRINTER_GUI_SERVICE=printer-gui-eglfs.service
UPDATER_GUI_SERVICE=tope-updater-gui.service
```

`show updater` behavior:

1. Acquire lock.
2. Stop `printer-gui-eglfs.service`.
3. Wait until `printer-gui-eglfs.service` is `inactive` or `failed`.
4. Run `systemctl reset-failed printer-gui-eglfs.service`.
5. Start `tope-updater-gui.service`.
6. Wait until `tope-updater-gui.service` is `active`.
7. Release lock.

`show printer` behavior:

1. Acquire lock.
2. Stop `tope-updater-gui.service`.
3. Wait until `tope-updater-gui.service` is `inactive` or `failed`.
4. Run `systemctl reset-failed tope-updater-gui.service`.
5. Start `printer-gui-eglfs.service`.
6. Wait until `printer-gui-eglfs.service` is `active`.
7. Release lock.

`blank` behavior:

1. Acquire lock.
2. Stop both GUI services.
3. Reset failed states.
4. Keep display unowned.
5. Release lock.

`status` behavior:

- print active state for both GUI services;
- return success if exactly one display GUI is active or both are inactive;
- return failure if both are active.

### 2. `tope-updater-gui.service`

Path:

```text
/etc/systemd/system/tope-updater-gui.service
```

Draft unit:

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

Notes:

- The service should normally be started by the switcher, not enabled for boot.
- `Restart=no` avoids fighting the switcher after install completes.
- The unit uses the same EGLFS style as `printer-gui-eglfs.service`.
- The GUI source lives in `tope_updater`, but the process uses the existing `printer-gui` PySide6 runtime for beta to avoid adding a second large PySide6 dependency to the updater venv.
- If `/dev/dri/card0` is missing, service start fails quickly and updater continues without GUI.
- If the `printer-gui` Python runtime is missing, service start fails quickly and updater continues without GUI.

### 3. Qt updater GUI app

Recommended source layout:

```text
src/updater/qt_gui/
├── __init__.py
├── main.py
├── progress_client.py
└── qml/
    └── UpdaterWindow.qml
```

Responsibilities:

- create `QGuiApplication`;
- load one fullscreen QML window;
- poll `/api/v1.0/progress` every 500ms;
- display stage, message, progress bar, percent, and final success/failure state;
- after `success` or `failed`, keep final state visible for a short time;
- exit when switcher stops the service.

The GUI is display-only. It must not trigger install actions, mutate updater state, or stop/start services.

Recommended UI content:

- title: `System Update`;
- status line: updater `message`;
- progress bar and percent;
- final success/failure state;
- no interactive controls for beta.

Reason:

- During install, input may be unavailable after EGLFS handoff.
- A non-interactive screen is simpler and safer for OTA.

### 4. `DisplaySwitchService` inside updater

Recommended source file:

```text
src/updater/services/display.py
```

Responsibilities:

- wrap calls to `/usr/local/bin/tope-display-switcher`;
- expose:
  - `show_updater()`
  - `show_printer()`
  - `blank()`
- enforce command timeouts;
- log stdout/stderr;
- never make GUI launch failure fatal by default.

Default behavior:

- if `show updater` fails, log warning and continue OTA;
- if `show printer` fails after OTA, log error and leave updater state accurate;
- do not rollback the software package only because GUI display restoration failed.

This keeps the OTA correctness boundary separate from the display UX boundary.

## OTA Flow Integration

### Download stage

No display switch.

Rationale:

- Download can take time.
- Main printer GUI is still useful.
- `printer-gui` or cloud UI can show download progress by polling updater if needed.

### Install stage

`POST /api/v1.0/update` should keep request validation synchronous and start the background task quickly.

Recommended flow inside `_update_workflow()`:

```text
1. Validate persistent package and MD5.
2. Call DisplaySwitchService.show_updater().
3. Deploy package through DeployService.
4. Delete state and delay/reset as today.
5. In finally, call DisplaySwitchService.show_printer().
```

Important: display switching belongs in `_update_workflow()`, not before scheduling the background task in `post_update()`. This avoids delaying the HTTP response and keeps failure handling in one async flow.

### Service stop interaction

There are two separate stop paths:

1. display switcher stops `printer-gui-eglfs.service` before OTA visual display;
2. `DeployService` may also stop services declared in manifest.

If the package manifest includes `printer-gui-eglfs.service`, the second stop should be idempotent and treat `inactive` or `failed` as already stopped. This requires updating `ProcessManager.stop_service()`.

## Failure Handling

### `show updater` fails

Behavior:

- log warning;
- continue OTA without install GUI;
- progress remains available through `/progress` and reporter.

Reason:

- OTA file correctness is higher priority than visual feedback.

### updater GUI crashes during install

Behavior:

- systemd records failure;
- updater deployment continues;
- final `show printer` still runs.

Not in beta scope:

- updater could periodically check GUI service status, but this is not required for beta.

### deployment fails and rollback succeeds

Behavior:

- updater state becomes `failed`;
- rollback follows existing `DeployService` logic;
- final `show printer` runs in `finally`;
- printer GUI starts from the rolled-back `current` symlink.

### `show printer` fails

Behavior:

- log error;
- leave OTA state as success/failed according to deployment result;
- do not alter version symlinks only because display restoration failed;
- device may require service-level recovery or manual intervention.

Recommended recovery command:

```bash
sudo tope-display-switcher show printer
sudo journalctl -u printer-gui-eglfs.service -u tope-updater-gui.service -n 100 --no-pager
```

### both GUI services active

Switcher `status` should return failure. `show updater` and `show printer` should always stop the opposite service first, so this is mainly a diagnostic and boot-recovery condition.

## Console Flash Mitigation

Qt EGLFS handoff can briefly leave the display unowned. To reduce visible console exposure in the shipment image:

- disable or mask `getty@tty1.service` if no interactive console is needed;
- set kernel log level low enough to avoid messages on tty;
- hide cursor:

```bash
setterm -cursor off >/dev/tty1
```

- prefer quiet boot parameters in the image:

```text
quiet loglevel=3 vt.global_cursor_default=0
```

This does not guarantee zero black frames, but it avoids exposing a usable shell or noisy logs during GUI switching.

## Packaging and Deployment

Updater package should include:

```text
deploy/
├── tope-display-switcher
├── tope-updater-gui.service
└── updater-gui-eglfs-kms.json
```

Install flow should:

1. install `tope-display-switcher` to `/usr/local/bin/tope-display-switcher`;
2. install `tope-updater-gui.service` to `/etc/systemd/system/`;
3. install `updater-gui-eglfs-kms.json` to `/opt/tope/updater/deploy/`;
4. run `systemctl daemon-reload`;
5. not enable `tope-updater-gui.service` by default;
6. ensure `tope-updater.service` has `PYTHONPATH=/opt/tope/updater/src` or installs the package into venv.

`printer-gui-eglfs.service` shipment change:

- `WorkingDirectory` should be a versioned stable path;
- start script should resolve from `/opt/tope/versions/current` or `/opt/tope/services`;
- it must no longer run from `/home/tope/printer-gui-qml` if OTA is expected to update it.

## Testing Strategy

### Unit tests

Add tests for `DisplaySwitchService`:

- calls switcher with `show updater`;
- times out and returns failure;
- logs stderr on non-zero exit;
- does not raise by default when GUI switching fails.

Add tests for `ProcessManager.stop_service()`:

- `inactive` after stop passes;
- `failed` after stop passes and calls `reset-failed`;
- `active` until timeout still fails;
- `systemctl stop` non-zero still fails.

Add tests for update workflow:

- `show_updater()` called before deploy;
- `show_printer()` called in `finally` after success;
- `show_printer()` called in `finally` after deploy failure;
- failed `show_updater()` does not prevent `DeployService.deploy_package()`.

### Switcher script tests

Use shell tests or Python subprocess tests with a fake `systemctl` in `PATH`:

- `show updater` stops printer, resets failed, starts updater;
- `show printer` stops updater, resets failed, starts printer;
- lock prevents concurrent transitions;
- timeout returns non-zero.

### Qt GUI tests

Run with offscreen Qt:

```bash
QT_QPA_PLATFORM=offscreen uv run pytest tests/unit/test_qt_updater_gui.py -q
```

Test:

- progress client parses updater API response;
- connection errors produce a visible "waiting for updater" state;
- `success` and `failed` states are rendered in model state.

### Device tests

On real device:

1. `tope-display-switcher show updater` while printer GUI is running.
2. Confirm updater GUI appears full screen.
3. `tope-display-switcher show printer`.
4. Confirm printer GUI returns.
5. Trigger real OTA install package.
6. Confirm updater GUI appears during install.
7. Confirm printer GUI returns after success.
8. Repeat with a package that fails deploy and rolls back.
9. Check no console text appears during normal transition.

Useful commands:

```bash
systemctl status printer-gui-eglfs.service tope-updater-gui.service --no-pager
journalctl -u tope-updater -u tope-updater-gui -u printer-gui-eglfs -n 200 --no-pager
tope-display-switcher status
```

## Implementation Order

Recommended order:

1. Fix service stop semantics in `ProcessManager`: accept `inactive` and `failed`, reset failed state.
2. Add `tope-display-switcher` with fake-systemctl tests.
3. Add `DisplaySwitchService` wrapper in updater.
4. Integrate display switch calls into `_update_workflow()`.
5. Add minimal Qt/PySide6 updater GUI.
6. Add systemd unit and install/deploy documentation.
7. Test on device with manual switcher commands.
8. Test full OTA install path with real `printer-gui` package.

This order keeps OTA service-control reliability first, then adds display UX.

## Explicit Non-Goals

- No apt/deb/system package update support in this work.
- No always-on-top overlay.
- No window manager.
- No user interaction required on updater GUI.
- No rollback only because GUI switching failed.
- No modification to `ota-service`.

## Decisions For Beta Implementation

1. The Qt updater GUI source lives inside `tope_updater`.

   Reason: API model, packaging, service files, and install-stage behavior ship together.

2. The GUI process reuses the existing `printer-gui` PySide6 runtime for beta.

   Reason: PySide6 is already required by the product GUI and is large; reusing that runtime avoids growing the updater package. `PYTHONPATH=/opt/tope/updater/src` lets that interpreter import the updater GUI module.

3. `tope-updater-gui.service` has `Conflicts=printer-gui-eglfs.service`.

   Reason: systemd gets a formal conflict declaration, while the switcher still stops the opposite service explicitly for clearer logs and status handling.
