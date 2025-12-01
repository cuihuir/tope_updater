# TOPE Updater - OTA Update Service

OTA (Over-The-Air) update service for embedded 3D printer devices. Provides HTTP API for triggering downloads, verifying packages, and deploying updates with atomic file operations and safe process control.

## Project Status (2025-11-28)

**Current Phase**: MVP Implementation Complete, Testing & Deployment Prep

- ✅ **Core OTA Workflow**: Download → Verify → Deploy (implemented & tested)
- ✅ **Download Validation**: 3-layer validation (HTTP/size/MD5)
- ✅ **Error Handling**: Comprehensive error detection and recovery
- ✅ **State Management**: Persistent state with restart recovery
- ⚠️ **断点续传**: Deferred - currently restarts download after interruption
- ⚠️ **Deployment**: Code complete, needs integration testing
- ❌ **Automated Tests**: Not yet implemented
- ❌ **Systemd Deployment**: Service unit file pending

See [tasks.md](specs/001-updater-core/tasks.md) for detailed progress.

## Features

- **HTTP API**: FastAPI-based async server on port 12315
- **Download with Validation**: HTTP streaming with 3-layer validation (Content-Length, package_size, MD5)
- **MD5 Verification**: Mandatory integrity checking with automatic file cleanup on mismatch
- **Atomic Deployment**: Crash-safe file replacement using temp → verify → rename pattern
- **Safe Process Control**: Graceful SIGTERM → SIGKILL with timeout (simplified implementation)
- **Status Reporting**: Real-time progress tracking via HTTP API + device-api callbacks (implemented)
- **Self-Healing**: Automatic cleanup of interrupted operations on startup

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

### Manual Testing (Current)

The download workflow has been manually tested with real files:

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

**Test Results**:
- ✅ 270MB download in 2min 7sec
- ✅ PACKAGE_SIZE_MISMATCH detection
- ✅ MD5_MISMATCH detection and cleanup
- ✅ Service restart recovery (FAILED state preserved)
- ✅ Interrupted download cleanup (downloading → idle on restart)

### Automated Testing (TODO)

```bash
# Unit tests (not yet implemented)
pytest tests/unit/

# Integration tests (not yet implemented)
pytest tests/integration/

# Run with coverage
pytest --cov=src/updater --cov-report=html
```

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
│   ├── deploy.py            # ZIP extraction, manifest parsing, atomic file ops
│   ├── process.py           # SIGTERM/SIGKILL process control (simplified)
│   ├── reporter.py          # HTTP callbacks to device-api
│   └── state_manager.py     # State persistence (state.json) + singleton
├── models/
│   ├── manifest.py          # Manifest data structure (ManifestModule)
│   ├── state.py             # State file structure (StateFile with expiry)
│   └── status.py            # Status enum (StageEnum)
└── utils/
    ├── logging.py           # Rotating logger (10MB, 3 files)
    └── verification.py      # MD5 computation utilities

tests/                       # TODO: Not yet implemented
deploy/                      # TODO: systemd service files pending
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

See [tasks.md](specs/001-updater-core/tasks.md#-current-project-status-2025-11-28) for detailed roadmap. Recommended priorities:

**Immediate (Production Ready)**:
1. Create systemd service unit file and install script
2. End-to-end integration test with real update package
3. Performance validation (<100ms /progress, <50MB RAM)

**Short-term (Quality Assurance)**:
1. Setup pytest and write unit tests for core services
2. Create integration test suite for full OTA flow
3. Add contract tests for API endpoints

**Medium-term (Enhancements)**:
1. Implement true resumable downloads (auto-resume on restart)
2. Add atomic deployment rollback capability
3. Enhance process control with systemd integration

## Known Limitations

- **断点续传**: Currently restarts download after service interruption (no auto-resume)
- **Deployment Testing**: Code complete but not integration tested with real ZIP packages
- **Automated Tests**: No pytest tests yet, manual testing only
- **Systemd**: No service unit file or installation script

## Contributing

Follow existing code patterns:
- Use `from updater.services import X` (absolute imports)
- All services should be async where possible
- Update state via StateManager singleton
- Follow Pydantic models for validation
- Add docstrings to all public methods

## License

Proprietary
