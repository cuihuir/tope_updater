# Feature Specification: Updater Core OTA Program

**Feature Branch**: `001-updater-core`
**Created**: 2025-11-25
**Status**: Draft
**Input**: User description: "实现 updater 核心 OTA 更新程序"

## Clarifications

### Session 2025-11-26

- Q: How should updater report real-time progress to device-api and ota-gui? → A: Hybrid - updater POSTs progress callbacks to device-api every 5%, ota-gui polls updater's GET /progress endpoint every 500ms
- Q: Which Python HTTP server framework should updater use? → A: FastAPI + uvicorn (modern async framework with ~15-20 packages)
- Q: Should the HTTP port configuration be hardcoded or configurable? → A: Hardcoded - device-api:9080, updater:12315 (fail on conflict)
- Q: How should updater be deployed and managed as a service? → A: systemd service (auto-start on boot, restart on failure)
- Q: What HTTP endpoints should updater expose? → A: Separate endpoints - POST /api/v1.0/download, POST /api/v1.0/update, GET /api/v1.0/progress

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Basic Update Flow (Priority: P1)

When device-api triggers an OTA update, the updater program must download the update package from cloud storage, verify its integrity, deploy files according to the manifest, and safely restart affected services to complete the update.

**Why this priority**: This is the minimum viable OTA capability. Without this, no updates can be delivered to devices in the field.

**Independent Test**: Can be fully tested by providing a valid update package URL and manifest, verifying the updater downloads the file, checks MD5, deploys files to target locations, and restarts services successfully.

**Acceptance Scenarios**:

1. **Given** device-api POSTs to `/api/v1.0/download` with package URL and MD5, **When** updater downloads the full package, **Then** updater verifies MD5 matches and sets stage to "success" in progress endpoint
2. **Given** a valid update package is downloaded and verified, **When** device-api POSTs to `/api/v1.0/update`, **Then** updater extracts manifest, deploys all files to target paths, and restarts specified services
3. **Given** all files are deployed successfully, **When** updater completes the update, **Then** updater POSTs final success status to device-api and cleans up temporary files

---

### User Story 2 - Resumable Downloads (Priority: P2)

When network connectivity is unreliable or interrupted during download, the updater must support resuming downloads from the last successful position rather than restarting from scratch.

**Why this priority**: Devices operate on WiFi/cellular networks with frequent interruptions. Resumable downloads reduce bandwidth waste and update time in poor network conditions.

**Independent Test**: Can be tested by simulating network interruption mid-download, verifying updater saves progress, and resumes from the same byte position when reconnected.

**Acceptance Scenarios**:

1. **Given** download in progress at 50%, **When** network disconnects, **Then** updater saves current byte position to state file
2. **Given** partial download exists with valid state file, **When** updater restarts download, **Then** updater sends HTTP Range header and resumes from saved position
3. **Given** resumed download completes, **When** updater verifies MD5, **Then** MD5 matches expected value confirming successful resume

---

### User Story 3 - Atomic File Deployment (Priority: P2)

When deploying updated files, the updater must ensure atomic file replacement to prevent corrupted state if power fails during deployment.

**Why this priority**: Power failures during OTA could brick devices if files are partially written. Atomic operations ensure system is always in a consistent state.

**Independent Test**: Can be tested by simulating power failure during file deployment, verifying target files remain unchanged (old version) or fully updated (new version), never partially written.

**Acceptance Scenarios**:

1. **Given** updated file ready to deploy, **When** updater writes to temporary file first, **Then** updater verifies MD5 of temp file before committing
2. **Given** temp file verified, **When** updater uses atomic rename operation, **Then** target file is replaced in single filesystem operation
3. **Given** deployment interrupted before rename, **When** system restarts, **Then** target file contains original version (no corruption)

---

### User Story 4 - Safe Process Control (Priority: P2)

When updating services like device-api or voice-app, the updater must gracefully terminate processes before file replacement and restart them in correct dependency order afterward.

**Why this priority**: Forcefully killing processes can corrupt application state or leave resources locked. Graceful shutdown ensures clean state transitions.

**Independent Test**: Can be tested by monitoring process termination signals and timing, verifying SIGTERM is sent first with timeout before SIGKILL, and services restart in dependency order.

**Acceptance Scenarios**:

1. **Given** service needs updating, **When** updater terminates process, **Then** updater sends SIGTERM and waits 10 seconds for graceful shutdown
2. **Given** process doesn't respond to SIGTERM within timeout, **When** timeout expires, **Then** updater sends SIGKILL to force termination
3. **Given** all services terminated and files deployed, **When** updater restarts services, **Then** updater starts device-api first, then other services in dependency order

---

### User Story 5 - Startup Self-Healing (Priority: P3)

When updater starts and finds incomplete operations from previous execution (due to crash or power loss), it must validate state and resume or retry as appropriate.

**Why this priority**: Field devices experience power failures and crashes. Self-healing reduces manual intervention and support burden.

**Independent Test**: Can be tested by stopping updater mid-operation, verifying state file exists, restarting updater, and confirming it detects incomplete state and resumes correctly.

**Acceptance Scenarios**:

1. **Given** updater starts with partial download state file, **When** updater checks state file integrity, **Then** updater resumes download from saved position
2. **Given** state file indicates MD5 verification failed previously, **When** updater restarts, **Then** updater deletes corrupted file and re-downloads from scratch
3. **Given** state file indicates deployment failed, **When** updater restarts, **Then** updater attempts rollback to previous version if backup exists

---

### User Story 6 - Status Reporting (Priority: P3)

Throughout the update process, the updater must report current status (stage, progress, errors) to device-api via HTTP callbacks and provide a progress endpoint for ota-gui to poll.

**Why this priority**: Users and cloud need visibility into update progress. HTTP-based status reporting enables real-time monitoring with clear service boundaries.

**Independent Test**: Can be tested by monitoring HTTP callbacks to device-api and polling updater's progress endpoint, verifying JSON format, stage names, progress percentages, and error messages match updater's actual state.

**Acceptance Scenarios**:

1. **Given** updater starts download, **When** progress reaches 25%, **Then** updater POSTs to device-api `/api/v1.0/ota/report` with `{"stage":"downloading","progress":25,"message":"Downloading...","error":null}`
2. **Given** ota-gui polls updater's `/api/v1.0/progress` endpoint, **When** download is at 45%, **Then** updater returns `{"stage":"downloading","progress":45,"message":"Downloading...","error":null}`
3. **Given** updater encounters MD5 mismatch, **When** verification fails, **Then** updater POSTs to device-api with `{"stage":"failed","progress":100,"message":"","error":"MD5_MISMATCH: expected abc123, got def456"}`

---

### User Story 7 - Optional GUI Launch (Priority: P4)

When updater begins OTA process, it may optionally launch ota-gui program to display full-screen progress interface, but GUI failure must not prevent updater from completing the update.

**Why this priority**: GUI improves user experience by showing progress and preventing confusion, but updater must work reliably even on headless devices or when GUI fails.

**Independent Test**: Can be tested by running updater with and without ota-gui present, verifying update succeeds in both cases, and GUI displays status when available.

**Acceptance Scenarios**:

1. **Given** ota-gui binary exists at `/opt/tope/ota-gui`, **When** updater starts, **Then** updater launches ota-gui process and continues regardless of launch success
2. **Given** ota-gui binary does not exist, **When** updater starts, **Then** updater logs warning and continues update without GUI
3. **Given** ota-gui crashes during update, **When** updater detects crash, **Then** updater continues update and completes successfully

---

### Edge Cases

- **What happens when disk space is insufficient during download?** Updater detects disk full error, reports `DISK_FULL` error to device-api, aborts update without retry, and cleans up partial download.

- **What happens when manifest.json is malformed or missing?** Updater validates manifest structure after extraction, reports `INVALID_MANIFEST` error if parsing fails, and aborts update.

- **What happens when target directory for deployment does not exist?** Updater creates missing directories with appropriate permissions (0755) before deployment.

- **What happens when a service process cannot be killed even with SIGKILL?** Updater reports `PROCESS_KILL_FAILED` error, logs process ID and name, but continues with other modules (partial update).

- **What happens when device loses power during atomic rename operation?** Filesystem guarantees atomicity of rename() - target file will contain either old version (rename didn't complete) or new version (rename completed). Updater validates on next startup.

- **What happens when HTTP download returns 404 or 5xx error?** Updater retries download with exponential backoff (1s, 2s, 4s) up to 3 attempts, then reports `DOWNLOAD_FAILED` error.

- **What happens when state file becomes corrupted?** Updater validates state file JSON on load, discards corrupted state, and treats as fresh start (re-download from beginning).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Updater MUST run HTTP server on port 12315 and expose three endpoints: POST `/api/v1.0/download` (trigger package download), POST `/api/v1.0/update` (trigger installation), GET `/api/v1.0/progress` (query current status). Server MUST fail to start if port 12315 is already bound.
- **FR-001a**: POST `/api/v1.0/download` endpoint MUST accept JSON payload with fields: `version` (string), `package_url` (string), `package_name` (string), `package_size` (integer bytes), `package_md5` (string). Endpoint MUST return 200 OK immediately and start download in background. Endpoint MUST be idempotent - if state.json exists for same package_url, resume existing download.
- **FR-001b**: POST `/api/v1.0/update` endpoint MUST accept JSON payload with field: `version` (string). Endpoint MUST verify downloaded package exists and MD5 matches before starting installation. Endpoint MUST return 200 OK immediately and start installation in background. Endpoint MUST return 409 Conflict if download not completed or if another operation is in progress.
- **FR-001c**: GET `/api/v1.0/progress` endpoint MUST return JSON with fields: `stage` (string enum: idle/downloading/verifying/toInstall/installing/rebooting/success/failed), `progress` (integer 0-100), `message` (string), `error` (string or null). Endpoint MUST respond within 100ms.
- **FR-002**: Updater MUST download packages from S3-compatible storage via HTTP/HTTPS URLs using standard library HTTP client
- **FR-003**: Updater MUST implement HTTP Range-based resumable downloads by sending Range header and tracking byte position in persistent state file at `./tmp/state.json`
- **FR-004**: Updater MUST compute MD5 hash of downloaded package and compare byte-for-byte with provided MD5 value
- **FR-005**: Updater MUST abort update and report `MD5_MISMATCH` error if verification fails, then delete corrupted file
- **FR-006**: Updater MUST extract downloaded ZIP package using standard library archive functions
- **FR-007**: Updater MUST parse manifest.json from package root to extract version, module list, source paths, and destination paths
- **FR-008**: Updater MUST validate all destination paths to prevent directory traversal attacks (reject paths containing `..` or absolute paths outside allowed directories)
- **FR-009**: Updater MUST create missing target directories with permissions 0755 before deploying files
- **FR-010**: Updater MUST deploy files atomically by writing to temporary files (e.g., `target.tmp`), verifying MD5, then using `rename()` syscall
- **FR-011**: Updater MUST maintain backup of critical files before replacement to enable rollback
- **FR-012**: Updater MUST terminate processes by sending SIGTERM, waiting 10 seconds, then sending SIGKILL if still running
- **FR-013**: Updater MUST verify process termination before deploying files by checking `/proc/<pid>` disappears
- **FR-014**: Updater MUST restart services in dependency order specified by manifest (device-api before other services)
- **FR-015**: Updater MUST expose HTTP GET endpoint at `http://localhost:12315/api/v1.0/progress` returning JSON: `{"stage":"<stage>","progress":<0-100>,"message":"<msg>","error":"<err>"}` for ota-gui polling
- **FR-016**: Updater MUST POST status updates to device-api at `http://localhost:9080/api/v1.0/ota/report` every 5% progress during download and at every major stage transition with JSON payload: `{"stage":"<stage>","progress":<0-100>,"message":"<msg>","error":"<err>"}`
- **FR-017**: Updater MUST log all critical operations (download start/complete, MD5 result, deployment actions, process control, errors) to `./logs/updater.log` (relative to updater working directory)
- **FR-018**: Updater MUST rotate log file when size exceeds 10MB, keeping last 3 rotations
- **FR-019**: Updater MUST include ISO 8601 timestamps and log levels (DEBUG/INFO/WARN/ERROR) in all log entries
- **FR-020**: Updater MUST report errors to device-api via HTTP POST to `http://localhost:9080/api/v1.0/ota/report` with error code and descriptive message in error field
- **FR-021**: Updater MUST limit memory usage by streaming downloads to disk (not buffering entire file in RAM)
- **FR-022**: Updater MUST optionally launch ota-gui by executing `/opt/tope/ota-gui` if binary exists
- **FR-023**: Updater MUST continue OTA process if ota-gui is missing, fails to start, or crashes (non-blocking)
- **FR-024**: Updater MUST check for incomplete operations on startup by validating state file existence and contents
- **FR-025**: Updater MUST resume incomplete downloads if state file indicates partial download with valid byte position
- **FR-026**: Updater MUST re-download from scratch if state file indicates MD5 failure or corrupted partial download
- **FR-027**: Updater MUST attempt rollback if deployment fails, restoring backup files and reporting `DEPLOYMENT_FAILED` error
- **FR-028**: Updater MUST clean up temporary files (ZIP package, extracted files, state file) after successful update completion
- **FR-029**: Updater MUST minimize third-party dependencies, using only: FastAPI (async HTTP server), uvicorn (ASGI server), httpx (async HTTP client), and Python standard library. Rationale: FastAPI's async model prevents blocking during concurrent operations (download + progress polling), satisfying Constitution Principle II's performance/compatibility exception clause.
- **FR-030**: Updater MUST handle SIGTERM gracefully by completing current atomic operation before shutdown
- **FR-031**: Updater MUST create `./tmp/` and `./logs/` directories with permissions 0755 on startup if they do not exist
- **FR-032**: Updater MUST create `./backups/` directory with permissions 0755 before backup operations if it does not exist
- **FR-033**: Updater MUST be deployed as a systemd service unit with Type=simple, auto-restart on failure (Restart=always), and dependency on network.target (After=network.target)
- **FR-034**: Updater systemd service MUST run as root user to enable process control (SIGTERM/SIGKILL) and file deployment to system directories
- **FR-035**: After MD5 verification succeeds, updater MUST transition to `toInstall` stage and record verification timestamp (`verified_at`) in state.json. Updater MUST remain in `toInstall` stage until POST `/api/v1.0/update` is received.
- **FR-036**: Before starting installation (POST `/api/v1.0/update`), updater MUST validate package trust window by checking `(current_time - verified_at) < 24 hours`. If expired, updater MUST return application-level status code 410 with error `PACKAGE_EXPIRED`, delete package files and state.json, and require re-download.

### Key Entities

- **Update Package**: ZIP archive containing manifest.json, module directories, and binary files to be deployed. Stored on S3 with pre-signed URL for download.

- **Manifest**: JSON file (`manifest.json`) embedded in package root, defining version string and array of modules with name, source path (relative in ZIP), and destination path (absolute on device).

- **Status State**: In-memory JSON structure containing current stage (idle/downloading/verifying/installing/rebooting/success/failed), progress percentage (0-100), human-readable message, and error object (code + message) if failed. Exposed via HTTP GET `/api/v1.0/progress` endpoint for ota-gui polling and pushed to device-api via HTTP POST `/api/v1.0/ota/report` callbacks.

- **State File**: JSON file at `./tmp/state.json` (relative to updater working directory) containing persistent state across restarts: download URL, byte position, total size, MD5 hash, last update timestamp. This file survives reboots for resumable downloads.

- **Module**: Individual software component to be updated (e.g., device-api, voice-app, klippy), defined in manifest with source and destination paths.

- **Updater HTTP API**: REST API exposed on port 12315 with three endpoints: (1) POST `/api/v1.0/download` - trigger async download with payload `{version, package_url, package_name, package_size, package_md5}`, returns 200 OK immediately; (2) POST `/api/v1.0/update` - trigger async installation with payload `{version}`, returns 200 OK or 409 Conflict; (3) GET `/api/v1.0/progress` - query current status, returns `{stage, progress, message, error}` within 100ms.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Updater successfully downloads, verifies, and deploys update packages in 100% of cases with valid packages and working network
- **SC-002**: Updater resumes interrupted downloads from exact byte position in 100% of network interruption cases
- **SC-003**: Updater completes atomic file deployment with zero file corruption cases, verified by testing with simulated power failures during 1000 deployment cycles
- **SC-004**: Updater gracefully terminates 95% of processes with SIGTERM within 10 seconds, requiring SIGKILL for remaining 5%
- **SC-005**: Updater detects and reports all failure scenarios (MD5 mismatch, disk full, invalid manifest, download failure) with appropriate error codes within 5 seconds of detection
- **SC-006**: Updater sends HTTP callback to device-api within 500ms of progress changes and responds to ota-gui progress endpoint queries within 100ms, enabling real-time monitoring
- **SC-007**: Updater self-heals from incomplete operations in 100% of startup cases where state file is valid
- **SC-008**: Updater continues and completes updates successfully in 100% of cases where ota-gui is missing or crashes
- **SC-009**: Updater consumes less than 50MB RAM during peak operation (downloading + extracting simultaneously)
- **SC-010**: Updater completes full update cycle (download + verify + deploy + restart) in under 5 minutes for 100MB package on 10Mbps network
