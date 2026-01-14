# TOPE Updater - OTA Update Service

OTA (Over-The-Air) update service for embedded 3D printer devices. Provides HTTP API for triggering downloads, verifying packages, and deploying updates with atomic file operations and safe process control.

## Project Status (2026-01-14)

**Current Phase**: Phase 5-6 + Testing Infrastructure Complete, Production Readiness: ~85%

- ✅ **Core OTA Workflow**: Download → Verify → Deploy (implemented & tested)
- ✅ **Download Validation**: 3-layer validation (HTTP/size/MD5)
- ✅ **Atomic Deployment**: Temp → verify → rename with auto-rollback
- ✅ **Service Management**: Full systemd integration (stop/start/status)
- ✅ **Error Handling**: Comprehensive error detection and recovery
- ✅ **State Management**: Persistent state with restart recovery
- ✅ **Rollback Mechanism**: Auto-restore backups on deployment failure
- ✅ **Testing Infrastructure**: Complete pytest setup with unit tests ⭐ NEW
  - pytest configuration (pytest.ini, pyproject.toml)
  - Global fixtures (conftest.py)
  - Unit tests for download and state_manager services
  - Mock servers (device-api, package server)
  - Test fixtures and test data
  - Manual test scripts (tests/manual/)
  - Test reports (tests/reports/)
- ⚠️ **断点续传**: Optional - currently restarts download after interruption
- ⚠️ **Integration Tests**: Unit tests complete, integration tests pending
- ⚠️ **Deployment Testing**: Manual tests complete, E2E tests pending

See [tasks.md](specs/001-updater-core/tasks.md) for detailed progress.

## Features

### Core Functionality
- **HTTP API**: FastAPI-based async server on port 12315
- **Download with Validation**: HTTP streaming with 3-layer validation (Content-Length, package_size, MD5)
- **MD5 Verification**: Mandatory integrity checking with automatic file cleanup on mismatch
- **Atomic Deployment**: Crash-safe file replacement using temp → verify → rename pattern
- **Auto-Rollback**: Automatic backup creation and restoration on deployment failure

### Service Management (New ✨)
- **Full systemd Integration**: systemctl stop/start with status verification
- **Service Status Monitoring**: Real-time service state checking (active/inactive/failed)
- **Graceful Shutdown**: 10s timeout for service stop, automatic SIGKILL by systemd
- **Dependency Ordering**: Uses systemd service dependencies for proper startup sequence

### Reliability Features
- **Self-Healing**: Automatic cleanup of interrupted operations on startup
- **Error Reporting**: Structured error codes (DEPLOYMENT_FAILED, ROLLBACK_FAILED, etc.)
- **State Persistence**: JSON-based state file with restart recovery
- **Comprehensive Logging**: Rotating logs (10MB, 3 files) with ISO 8601 timestamps

## Quick Start

### Prerequisites

- Python 3.11+
- Linux with systemd
- Root privileges (for process control and system file deployment)

### Installation

```bash
# Clone repository
git checkout 001-updater-core

# Install package with all dependencies (creates venv automatically)
uv sync

# For development with additional tools
uv sync --extra dev

# Activate virtual environment
source .venv/bin/activate
```

**Note**: Using `uv sync` installs the package in editable mode, enabling stable absolute imports like `from updater.services import download` throughout the codebase.

### Running Locally

```bash
# Method 1: Using uv (recommended)
uv run src/updater/main.py

# Method 2: Using activated venv
source .venv/bin/activate
python -m updater.main

# Method 3: Direct python module
python src/updater/main.py
```

The service will start on `http://localhost:12315`.

**Stop service**:
```bash
# Find and kill process
pkill -f 'updater/main.py'

# Or with signal 9 (force kill)
pkill -f -9 'updater/main.py'
```

### API Endpoints

**POST /api/v1.0/download** - Trigger async package download
```bash
curl -X POST http://localhost:12315/api/v1.0/download \
  -H "Content-Type: application/json" \
  -d '{
    "version": "1.2.3",
    "package_url": "https://s3.example.com/update.zip",
    "package_name": "update.zip",
    "package_size": 104857600,
    "package_md5": "abc123def456..."
  }'
```

**POST /api/v1.0/update** - Trigger async installation
```bash
curl -X POST http://localhost:12315/api/v1.0/update \
  -H "Content-Type: application/json" \
  -d '{"version": "1.2.3"}'
```

**GET /api/v1.0/progress** - Query current status
```bash
curl http://localhost:12315/api/v1.0/progress
```

Response example:
```json
{
  "code": 200,
  "msg": "success",
  "data": {
    "stage": "downloading",
    "progress": 45,
    "message": "Downloading package... 47.2 MB / 104.9 MB",
    "error": null
  }
}
```

## Testing

### Manual Testing Scripts

Several test scripts are available for manual testing:

```bash
# Test download with validation
curl -X POST http://localhost:12315/api/v1.0/download \
  -H "Content-Type: application/json" \
  -d '{
    "version": "1.0.68",
    "package_url": "https://example.com/package.apk",
    "package_name": "test.apk",
    "package_size": 270186022,
    "package_md5": "c2a4a1fbfd904d9b2c73f84a1876b26e"
  }'

# Monitor progress
curl http://localhost:12315/api/v1.0/progress

# Check logs
tail -f ./logs/updater.log
```

### Test Scripts (New ✨)

```bash
# Test systemd integration (requires sudo)
sudo python test_systemd_refactor.py

# Test rollback mechanism
python test_rollback.py

# Test deployment flow
python test_deploy_flow.py

# Test full deployment with services
python test_full_deploy_flow.py
```

**Test Results**:
- ✅ 270MB download in 2min 7sec
- ✅ PACKAGE_SIZE_MISMATCH detection
- ✅ MD5_MISMATCH detection and cleanup
- ✅ Service restart recovery (FAILED state preserved)
- ✅ Interrupted download cleanup (downloading → idle on restart)
- ✅ Rollback on deployment failure (Phase 5)
- ✅ systemd stop/start/status verification (Phase 6)

### Automated Testing

**Test Infrastructure**: Complete ✨

```bash
# Run all tests
pytest

# Run unit tests
pytest tests/unit/ -v

# Run integration tests (when ready)
pytest tests/integration/ -v -m integration

# Run with coverage report
pytest --cov=src/updater --cov-report=html
pytest --cov=src/updater --cov-report=term-missing

# View coverage report
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
```

**Test Structure**:
```
tests/
├── conftest.py                  # Global pytest fixtures
├── unit/                        # Unit tests
│   ├── test_download.py         # ✅ Complete (461 lines)
│   └── test_state_manager.py    # ✅ Complete (160 lines)
├── integration/                 # Integration tests (TODO)
├── contract/                    # Contract tests (TODO)
├── e2e/                        # End-to-end tests (TODO)
├── fixtures/                    # Test data and generation
│   ├── generate_test_packages.py
│   ├── packages/               # Test ZIP files
│   └── tests/mocks/            # Mock servers
│       ├── device_api_server.py
│       └── package_server.py
├── manual/                     # Manual test scripts
│   ├── test_deploy_flow.py
│   ├── test_full_deploy_flow.py
│   ├── test_rollback.py
│   └── test_systemd_refactor.py
└── reports/                    # Test documentation
    ├── DEPLOYMENT_TEST_REPORT.md
    ├── DOWNLOAD_TEST_SUMMARY.md
    └── TESTING_SETUP_SUMMARY.md
```

**Test Results**:
- ✅ Unit tests written for download and state_manager
- ✅ pytest configuration complete
- ✅ Mock servers implemented (device-api, package)
- ✅ Test fixtures and data generation
- ✅ Manual test scripts (all passing)

**Note**: See [testing-guide.md](specs/001-updater-core/testing-guide.md) for complete testing documentation.

## Deployment

### systemd Service (TODO)

Systemd service unit file and installation script are not yet created. For production deployment:

```bash
# TODO: Install service
sudo deploy/install.sh

# TODO: Start service
sudo systemctl start tope-updater

# TODO: Enable auto-start on boot
sudo systemctl enable tope-updater

# Check status
sudo systemctl status tope-updater

# View logs
sudo journalctl -u tope-updater -f
```

**Current workaround**: Run manually with `nohup` for background execution:

```bash
nohup uv run src/updater/main.py > /tmp/updater.log 2>&1 &

# Check process
ps aux | grep 'updater/main.py'

# View logs
tail -f /tmp/updater.log
```

## Project Structure

```
src/updater/
├── main.py                  # FastAPI app + uvicorn startup + lifespan manager
├── api/
│   ├── routes.py            # HTTP endpoints (download, update, progress)
│   └── models.py            # Pydantic request/response models
├── services/
│   ├── download.py          # Async download with httpx + 3-layer validation
│   ├── deploy.py            # ZIP extraction, manifest parsing, atomic file ops + rollback ✨
│   ├── process.py           # systemd service management (stop/start/status) ✨
│   ├── reporter.py          # HTTP callbacks to device-api
│   └── state_manager.py     # State persistence (state.json) + singleton
├── models/
│   ├── manifest.py          # Manifest data structure (ManifestModule)
│   ├── state.py             # State file structure (StateFile with expiry)
│   └── status.py            # Status enum (StageEnum)
└── utils/
    ├── logging.py           # Rotating logger (10MB, 3 files)
    └── verification.py      # MD5 computation utilities

specs/001-updater-core/
├── spec.md / spec_cn.md     # Feature specification (EN/CN)
├── plan.md / plan_cn.md     # Implementation plan (EN/CN)
├── tasks.md                 # Task list & progress tracking ⭐
├── testing-guide.md         # Testing infrastructure guide ✨ NEW
├── data-model.md            # Data model documentation
├── quickstart.md            # Quick start guide
└── research.md              # Technical research

tests/                       # ✅ Infrastructure Complete
├── conftest.py              # Global pytest fixtures ✅
├── unit/                    # Unit tests
│   ├── test_download.py     # ✅ Complete (461 lines)
│   └── test_state_manager.py # ✅ Complete (160 lines)
├── integration/             # Integration tests (TODO)
├── contract/                # Contract tests (TODO)
├── e2e/                    # End-to-end tests (TODO)
├── fixtures/                # Test data and generation
│   ├── generate_test_packages.py ✅
│   ├── packages/           # Test ZIP files ✅
│   └── tests/mocks/        # Mock servers ✅
│       ├── device_api_server.py ✅
│       └── package_server.py ✅
├── manual/                 # Manual test scripts
│   ├── test_deploy_flow.py ✅
│   ├── test_full_deploy_flow.py ✅
│   ├── test_rollback.py ✅
│   └── test_systemd_refactor.py ✅
└── reports/                # Test documentation ✅
    ├── DEPLOYMENT_TEST_REPORT.md ✅
    ├── DOWNLOAD_TEST_SUMMARY.md ✅
    └── TESTING_SETUP_SUMMARY.md ✅

Test Scripts (Root)
├── test_systemd_refactor.py # systemd integration tests ✨ NEW
├── test_rollback.py         # Rollback mechanism tests ✨ NEW
├── test_deploy_flow.py      # Deployment flow tests
└── test_full_deploy_flow.py # Full deployment tests
```

## Configuration

All configuration is hardcoded per design:
- **Updater Port**: 12315
- **device-api Port**: 9080
- **Working Directory**: Current directory
- **Temp Directory**: `./tmp/`
- **Logs Directory**: `./logs/`
- **Backups Directory**: `./backups/`

## Architecture

- **Language**: Python 3.11+
- **Framework**: FastAPI 0.115.0 + uvicorn 0.32.0
- **HTTP Client**: httpx 0.27.0 (async with Range support)
- **File I/O**: aiofiles 24.1.0 (non-blocking)
- **Target Platform**: Linux embedded device (ARM/x86)

## Development

### Code Quality

```bash
# Format code
ruff format src/ tests/

# Lint code
ruff check src/ tests/

# Type checking
mypy src/updater/
```

### Adding Dependencies

```bash
# Edit pyproject.toml to add dependency
# Then regenerate requirements files:
uv pip compile pyproject.toml -o requirements.txt
uv pip compile pyproject.toml --extra dev -o dev-requirements.txt
```

## Documentation

- [Feature Specification](specs/001-updater-core/spec.md)
- [Implementation Plan](specs/001-updater-core/plan.md)
- [Data Model](specs/001-updater-core/data-model.md)
- [Task List & Progress](specs/001-updater-core/tasks.md) ⭐
- [Quick Start Guide](specs/001-updater-core/quickstart.md)

## Next Steps

See [tasks.md](specs/001-updater-core/tasks.md) for detailed roadmap.

**Immediate (Production Ready) - P0**:
1. ✅ Phase 6: systemd service management (COMPLETED)
2. ✅ Phase 5: Atomic deployment + rollback (COMPLETED)
3. ⏳ End-to-end integration test with real update package
4. ⏳ Performance validation (<100ms /progress, <50MB RAM)

**Short-term (Quality Assurance) - P1**:
1. ⏳ Phase 7: Startup self-healing enhancements
2. ✅ Setup pytest and write unit tests for core services - **COMPLETE** ⭐
3. ⏳ Create integration test suite for full OTA flow
4. ⏳ Add contract tests for API endpoints

**Medium-term (Enhancements) - P2**:
1. ⏳ Phase 8: Complete status reporting and callbacks
2. ⏳ Phase 10: Code polish (error handling, SIGTERM, path validation)
3. ⏸️ Phase 4: Resumable downloads (OPTIONAL - low priority)

## Known Limitations

1. **断点续传 (Resumable Downloads)** - ✅ Acceptable per Constitution:
   - HTTP Range header code exists but not active
   - Service restart → cleans up and restarts from scratch
   - Status: Optional enhancement (Constitution Principle VIII: SHOULD)

2. **Automated Tests** - ✅ Infrastructure Complete:
   - ✅ pytest configuration (pytest.ini, pyproject.toml)
   - ✅ Global fixtures and test utilities
   - ✅ Unit tests for download and state_manager services
   - ✅ Mock servers (device-api, package)
   - ✅ Test fixtures and data generation
   - ⏳ Integration tests (pending)
   - ⏳ Contract tests (pending)
   - ⏳ E2E tests (pending)

3. **Deployment Testing** - ⚠️ Partial:
   - Manual tests complete (download, deploy, rollback)
   - Need real device integration test
   - Need E2E test with production-like environment

4. **systemd Service File** - ⚠️ Deferred:
   - Unit file exists but not tested in production
   - Install script exists but not validated
   - TODO: Deploy to target device for production testing

## Contributing

Follow existing code patterns:
- Use `from updater.services import X` (absolute imports)
- All services should be async where possible
- Update state via StateManager singleton
- Follow Pydantic models for validation
- Add docstrings to all public methods

## License

Proprietary
