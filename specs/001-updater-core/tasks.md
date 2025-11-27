# Implementation Tasks: Updater Core OTA Program

**Feature Branch**: `001-updater-core`
**Generated**: 2025-11-27
**Based on**: [plan.md](./plan.md), [spec.md](./spec.md), [data-model.md](./data-model.md)

## Task Summary

- **Total Tasks**: 58
- **User Stories**: 7 (P1: 1, P2: 3, P3: 2, P4: 1)
- **Parallel Opportunities**: 35 parallelizable tasks marked with [P]
- **MVP Scope**: User Story 1 (Basic Update Flow) - 12 tasks

## Implementation Strategy

**Incremental Delivery Approach**:
1. **MVP (US1)**: Complete User Story 1 for basic end-to-end OTA capability
2. **Iteration 2 (US2-US4)**: Add resilience features (resumable downloads, atomic deployment, safe process control)
3. **Iteration 3 (US5-US6)**: Add operational features (self-healing, status reporting)
4. **Polish (US7)**: Optional GUI integration

Each user story is independently testable and delivers incremental value.

---

## Phase 1: Setup & Project Initialization

**Goal**: Establish project structure, dependencies, and development environment.

### Tasks

- [ ] T001 Create project directory structure per plan.md (src/updater/, tests/, deploy/)
- [ ] T002 Create Python package structure with __init__.py files in src/updater/, src/updater/api/, src/updater/services/, src/updater/models/, src/updater/utils/
- [ ] T003 Create requirements.txt with FastAPI==0.115.0, uvicorn==0.32.0, httpx==0.27.0, aiofiles==24.1.0
- [ ] T004 Create dev-requirements.txt with pytest==8.3.0, pytest-asyncio==0.24.0, pytest-cov==5.0.0, ruff==0.6.0
- [ ] T005 Create .gitignore for Python (__pycache__/, *.pyc, venv/, tmp/, logs/, backups/)
- [ ] T006 Create README.md with project description, setup instructions, and basic usage
- [ ] T007 Create deploy/tope-updater.service systemd unit file per research.md specifications
- [ ] T008 Create deploy/install.sh script to install service and create runtime directories
- [ ] T009 Initialize pytest.ini with asyncio_mode=auto and test paths configuration

**Verification**: Run `tree src/` to confirm structure, `pip install -r requirements.txt` succeeds, systemd unit file validates with `systemd-analyze verify`

---

## Phase 2: Foundational Components

**Goal**: Implement blocking prerequisites shared across all user stories.

### Tasks

- [ ] T010 [P] Implement StageEnum in src/updater/models/status.py with values (idle, downloading, verifying, toInstall, installing, rebooting, success, failed)
- [ ] T011 [P] Implement Manifest and ManifestModule Pydantic models in src/updater/models/manifest.py with path validation (FR-007, FR-008)
- [ ] T012 [P] Implement StateFile Pydantic model in src/updater/models/state.py with verified_at field and is_package_expired() method (FR-036)
- [ ] T013 [P] Implement DownloadRequest, UpdateRequest, ProgressResponse Pydantic models in src/updater/api/models.py with application-level status codes
- [ ] T014 Implement rotating logger setup in src/updater/utils/logging.py (10MB rotation, 3 files, ISO 8601 timestamps - FR-017, FR-018, FR-019)
- [ ] T015 Implement StateManager class in src/updater/services/state_manager.py with singleton pattern for shared status state and state.json persistence
- [ ] T016 Create FastAPI app instance in src/updater/main.py with lifespan context manager for startup/shutdown hooks
- [ ] T017 Implement directory creation logic in src/updater/main.py startup (./tmp/, ./logs/, ./backups/ with 0755 permissions - FR-031, FR-032)

**Verification**: Run `pytest tests/unit/test_models.py` for Pydantic validation, verify StateManager loads/saves state.json, FastAPI app starts on port 12315

---

## Phase 3: User Story 1 - Basic Update Flow (P1)

**Goal**: Enable complete OTA update flow: download → verify → deploy → restart services.

**Independent Test**: Provide valid update package URL and manifest, verify updater downloads file, checks MD5, deploys files to target locations, restarts services successfully.

### Tasks

- [ ] T018 [P] [US1] Implement DownloadService class in src/updater/services/download.py with async httpx streaming download to ./tmp/<package_name> (FR-002, FR-021)
- [ ] T019 [P] [US1] Implement VerificationService class in src/updater/services/verification.py with incremental MD5 computation during download (FR-004)
- [ ] T020 [P] [US1] Implement DeploymentService class in src/updater/services/deployment.py with manifest parsing, ZIP extraction, and atomic file operations (temp → verify → rename - FR-010, FR-011)
- [ ] T021 [P] [US1] Implement ProcessControlService class in src/updater/services/process_control.py with SIGTERM/SIGKILL logic and /proc validation (FR-012, FR-013, FR-014)
- [ ] T022 [P] [US1] Implement device-api callback utility in src/updater/utils/callbacks.py for HTTP POST to http://localhost:9080/api/v1.0/ota/report (FR-016)
- [ ] T023 [US1] Implement POST /api/v1.0/download endpoint in src/updater/api/endpoints.py to trigger async download with DownloadRequest payload (FR-001a)
- [ ] T024 [US1] Implement POST /api/v1.0/update endpoint in src/updater/api/endpoints.py to trigger async installation with UpdateRequest payload and 24h timeout check (FR-001b, FR-036)
- [ ] T025 [US1] Implement GET /api/v1.0/progress endpoint in src/updater/api/endpoints.py to return current status state within 100ms (FR-001c)
- [ ] T026 [US1] Integrate download workflow in DownloadService: start download → compute MD5 → transition to toInstall on success → callback device-api (FR-035)
- [ ] T027 [US1] Integrate deployment workflow in DeploymentService: extract ZIP → parse manifest → deploy modules → restart services → cleanup (FR-006, FR-007, FR-009, FR-014)
- [ ] T028 [US1] Add error handling to DownloadService for DISK_FULL, DOWNLOAD_FAILED errors and report to device-api (FR-005, FR-020)
- [ ] T029 [US1] Add error handling to VerificationService for MD5_MISMATCH and delete corrupted files (FR-005)

**Acceptance Tests**:
1. POST /download with valid package → downloads file, MD5 verifies, stage transitions to toInstall
2. POST /update with verified package → extracts manifest, deploys files, restarts services, stage = success
3. POST callback to device-api with final success status

**Verification**: Run integration test simulating full OTA flow from download to successful deployment

---

## Phase 4: User Story 2 - Resumable Downloads (P2)

**Goal**: Support HTTP Range-based resumable downloads to handle network interruptions.

**Independent Test**: Simulate network interruption mid-download, verify updater saves progress, resumes from same byte position when reconnected.

### Tasks

- [ ] T030 [P] [US2] Add HTTP Range header support to DownloadService.download_package() method (Range: bytes=<resume_pos>-)
- [ ] T031 [P] [US2] Implement resume logic in DownloadService: check state.json for bytes_downloaded, send Range header if >0 (FR-003, FR-025)
- [ ] T032 [P] [US2] Handle HTTP 206 Partial Content vs 200 OK responses in DownloadService streaming loop
- [ ] T033 [P] [US2] Handle HTTP 416 Range Not Satisfiable by deleting partial file and restarting from scratch (FR-026)
- [ ] T034 [US2] Update StateManager to persist bytes_downloaded and last_update timestamp every 5% progress
- [ ] T035 [US2] Add idempotency check in POST /download endpoint: if state.json exists for same package_url, resume download (FR-001a)
- [ ] T036 [US2] Verify incremental MD5 computation continues from partial file when resuming (read existing bytes, update hash, continue streaming)

**Acceptance Tests**:
1. Download interrupted at 50% → state.json saved with bytes_downloaded
2. Resume download → sends Range header, downloads remaining bytes, MD5 matches
3. Corrupted state file → fallback to full download from scratch

**Verification**: Run test_resume_download.py simulating network disconnection at various progress points

---

## Phase 5: User Story 3 - Atomic File Deployment (P2)

**Goal**: Ensure atomic file replacement to prevent corrupted state during power failures.

**Independent Test**: Simulate power failure during file deployment, verify target files remain unchanged or fully updated, never partially written.

### Tasks

- [ ] T037 [P] [US3] Implement atomic file deployment in DeploymentService: write to temp file in ./tmp/, verify MD5, atomic os.rename() to target (FR-010)
- [ ] T038 [P] [US3] Implement backup creation in DeploymentService: copy existing target file to ./backups/<module>.<timestamp>.bak before replacement (FR-011)
- [ ] T039 [P] [US3] Add parent directory creation logic in DeploymentService for target paths that don't exist (os.makedirs with exist_ok=True - FR-009)
- [ ] T040 [US3] Add rollback logic in DeploymentService: if deployment fails, restore from backup in ./backups/ directory
- [ ] T041 [US3] Add DEPLOYMENT_FAILED error reporting when atomic operations fail (e.g., permission denied, disk full during rename)

**Acceptance Tests**:
1. Deploy file → temp file written, MD5 verified, atomic rename succeeds
2. Target doesn't exist → parent directory created automatically
3. Deployment interrupted before rename → target file unchanged (old version intact)

**Verification**: Run power failure simulation test checking filesystem state after interruption

---

## Phase 6: User Story 4 - Safe Process Control (P2)

**Goal**: Gracefully terminate processes with SIGTERM timeout before SIGKILL, restart in dependency order.

**Independent Test**: Monitor process termination signals and timing, verify SIGTERM sent first with 10s timeout, SIGKILL if needed, services restart in dependency order.

### Tasks

- [ ] T042 [P] [US4] Implement terminate_process() in ProcessControlService: send SIGTERM, wait 10 seconds, check /proc/<pid>, send SIGKILL if still running (FR-012, FR-013)
- [ ] T043 [P] [US4] Implement verify_termination() in ProcessControlService by checking /proc/<pid>/status file existence
- [ ] T044 [P] [US4] Implement restart_services() in ProcessControlService to start services in restart_order from manifest (device-api first - FR-014)
- [ ] T045 [US4] Integrate process control into deployment workflow: terminate all module processes → deploy files → restart in order
- [ ] T046 [US4] Add PROCESS_KILL_FAILED error reporting when process doesn't terminate even after SIGKILL (FR-020)

**Acceptance Tests**:
1. Terminate process → SIGTERM sent, waits 10s, process exits gracefully
2. Process hangs → SIGTERM timeout expires, SIGKILL sent, process forcefully killed
3. Multiple services → terminated, files deployed, restarted in dependency order (device-api=1, voice-app=2)

**Verification**: Run test monitoring process lifecycle during update with mock processes

---

## Phase 7: User Story 5 - Startup Self-Healing (P3)

**Goal**: Detect incomplete operations on startup, validate state, resume or retry appropriately.

**Independent Test**: Stop updater mid-operation, verify state file exists, restart updater, confirm it detects incomplete state and resumes correctly.

### Tasks

- [ ] T047 [P] [US5] Implement startup self-healing logic in main.py lifespan: load state.json, validate stage field (FR-024)
- [ ] T048 [P] [US5] Add recovery logic for stage=downloading: validate partial file exists, resume download from bytes_downloaded (FR-025)
- [ ] T049 [P] [US5] Add recovery logic for stage=failed: delete corrupted files, reset to idle (FR-026)
- [ ] T050 [US5] Add recovery logic for stage=toInstall: check package expiry (verified_at + 24h), proceed or reset (FR-036)
- [ ] T051 [US5] Add state file corruption handling: if JSON parsing fails, delete state.json and start fresh

**Acceptance Tests**:
1. Startup with partial download state → resumes from bytes_downloaded
2. Startup with failed verification state → deletes corrupted file, resets to idle
3. Startup with expired toInstall package → deletes package, reports PACKAGE_EXPIRED

**Verification**: Run test_power_failure_simulation.py stopping/restarting updater at various stages

---

## Phase 8: User Story 6 - Status Reporting (P3)

**Goal**: Report status to device-api via HTTP callbacks and provide progress endpoint for ota-gui polling.

**Independent Test**: Monitor HTTP callbacks and progress endpoint, verify JSON format, stage names, progress percentages, error messages match updater state.

### Tasks

- [ ] T052 [P] [US6] Implement progress callback logic in StateManager: POST to device-api every 5% progress change (FR-016)
- [ ] T053 [P] [US6] Implement stage transition callback logic in StateManager: POST to device-api on every stage change
- [ ] T054 [P] [US6] Add callback timeout and retry logic in callbacks.py: 500ms timeout, log but don't abort on failure
- [ ] T055 [US6] Optimize GET /progress endpoint for <100ms response time: return cached status from StateManager without blocking operations (FR-001c)

**Acceptance Tests**:
1. Download reaches 25% → POST to device-api with {"code":200,"msg":"success","data":{"stage":"downloading","progress":25,...}}
2. ota-gui polls /progress at 45% → returns {"code":200,"msg":"success","data":{"stage":"downloading","progress":45,...}}
3. MD5 mismatch → POST to device-api with {"code":500,"msg":"MD5_MISMATCH:...","stage":"failed",...}

**Verification**: Run test with mock device-api server logging all received callbacks

---

## Phase 9: User Story 7 - Optional GUI Launch (P4)

**Goal**: Launch ota-gui program during installation if available, continue regardless of GUI success/failure.

**Independent Test**: Run updater with and without ota-gui present, verify update succeeds in both cases, GUI displays status when available.

### Tasks

- [ ] T056 [P] [US7] Implement launch_ota_gui() in utils/ module: check /opt/tope/ota-gui exists, execute with subprocess.Popen() non-blocking (FR-022)
- [ ] T057 [US7] Integrate GUI launch into POST /update workflow: launch before deployment starts, log warning if binary missing or launch fails, continue update (FR-023)

**Acceptance Tests**:
1. ota-gui binary exists → launched successfully, update continues
2. ota-gui binary missing → warning logged, update completes without GUI
3. ota-gui crashes → updater detects crash, logs error, completes update

**Verification**: Test with and without ota-gui binary, simulate GUI crash mid-update

---

## Phase 10: Polish & Cross-Cutting Concerns

**Goal**: Complete non-functional requirements, testing, and deployment preparation.

### Tasks

- [ ] T058 [P] Add comprehensive error handling to all service methods with try/except blocks and structured error codes (FR-020)
- [ ] T059 [P] Add SIGTERM handler in main.py for graceful shutdown: complete current atomic operation before exit (FR-030)
- [ ] T060 [P] Implement manifest path traversal validation: reject paths with ".." or leading "/" in src field (FR-008)
- [ ] T061 [P] Add resource monitoring to prevent >50MB RAM usage: use streaming for large files, avoid loading full package in memory (SC-009)
- [ ] T062 [P] Create unit tests for DownloadService in tests/unit/test_download.py with mocked httpx responses
- [ ] T063 [P] Create unit tests for VerificationService in tests/unit/test_verification.py with sample files and MD5 hashes
- [ ] T064 [P] Create unit tests for DeploymentService in tests/unit/test_deployment.py with mock filesystem operations
- [ ] T065 [P] Create unit tests for ProcessControlService in tests/unit/test_process_control.py with mock process signals
- [ ] T066 [P] Create unit tests for StateManager in tests/unit/test_state_manager.py with temporary state files
- [ ] T067 [P] Create integration test in tests/integration/test_full_ota_flow.py simulating complete update with real files
- [ ] T068 [P] Create contract test in tests/contract/test_api_endpoints.py validating against contracts/updater-api.yaml
- [ ] T069 [P] Create contract test in tests/contract/test_device_api_callbacks.py validating callback payload format
- [ ] T070 Validate deploy/install.sh script creates directories and installs service correctly
- [ ] T071 Test systemd service deployment: install service, verify auto-start on boot, test restart on failure
- [ ] T072 Run full end-to-end test on target embedded device (ARM/x86) with real network conditions
- [ ] T073 Performance validation: verify <100ms /progress response, <500ms callback latency, <50MB RAM usage
- [ ] T074 Create CHANGELOG.md documenting feature completion and version 1.0.0 release

**Verification**: All tests pass (`pytest`), service deploys successfully, performance benchmarks met

---

## Dependencies & Execution Order

### User Story Dependencies

```
Phase 1 (Setup) → Phase 2 (Foundational)
                       ↓
                  Phase 3 (US1 - P1) ← MVP Milestone
                       ↓
         ┌─────────────┼─────────────┐
         ▼             ▼             ▼
    Phase 4 (US2)  Phase 5 (US3)  Phase 6 (US4)  ← All P2, can run in parallel
         │             │             │
         └─────────────┼─────────────┘
                       ↓
         ┌─────────────┴─────────────┐
         ▼                           ▼
    Phase 7 (US5)               Phase 8 (US6)  ← Both P3, can run in parallel
         │                           │
         └─────────────┬─────────────┘
                       ▼
                  Phase 9 (US7)  ← P4, optional
                       ↓
                  Phase 10 (Polish)
```

**Key Dependencies**:
- **US1** (P1) is BLOCKING for all other stories - must complete first for MVP
- **US2-US4** (P2) are INDEPENDENT of each other - can be implemented in parallel after US1
- **US5-US6** (P3) are INDEPENDENT of each other - can be implemented in parallel after US1
- **US7** (P4) depends on US1 but is optional/low priority

### Parallel Execution Examples

**Phase 2 (Foundational) - 8 parallel tasks**:
```bash
# Run in parallel (different files, no dependencies):
T010 (status.py) || T011 (manifest.py) || T012 (state.py) || T013 (models.py)
```

**Phase 3 (US1) - Services can be built in parallel**:
```bash
# Run in parallel (independent service implementations):
T018 (download.py) || T019 (verification.py) || T020 (deployment.py) || T021 (process_control.py) || T022 (callbacks.py)

# Then sequentially integrate endpoints:
T023 → T024 → T025 → T026 → T027 → T028 → T029
```

**Phase 4-6 (US2-US4) - Fully parallel phases**:
```bash
# Entire phases can run in parallel:
Phase 4 (US2 tasks) || Phase 5 (US3 tasks) || Phase 6 (US4 tasks)
```

---

## Testing Strategy

**Test Execution Order**:
1. **Unit Tests**: Run after each service implementation (T062-T066)
2. **Integration Tests**: Run after US1 complete (T067)
3. **Contract Tests**: Run after all endpoints implemented (T068-T069)
4. **End-to-End Tests**: Run on target device after deployment (T072)
5. **Performance Tests**: Run after full implementation (T073)

**Coverage Goals**:
- Unit tests: >80% code coverage
- Integration tests: All user story acceptance scenarios
- Contract tests: 100% OpenAPI spec compliance
- End-to-end tests: Real device with network interruptions, power failures

---

## Task Checklist Format Reference

✅ **CORRECT Examples**:
- `- [ ] T001 Create project structure per plan.md`
- `- [ ] T010 [P] Implement StageEnum in src/updater/models/status.py`
- `- [ ] T018 [P] [US1] Implement DownloadService in src/updater/services/download.py`

❌ **WRONG Examples**:
- `- [ ] Create models` (missing Task ID, file path)
- `T020 Implement service` (missing checkbox)
- `- [ ] [US1] Add endpoint` (missing Task ID)
