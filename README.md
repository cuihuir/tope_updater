# TOPE Updater - OTA Update Service

OTA (Over-The-Air) update service for embedded 3D printer devices. Provides HTTP API for triggering downloads, verifying packages, and deploying updates with atomic file operations and safe process control.

## Features

- **HTTP API**: FastAPI-based async server on port 12315
- **Resumable Downloads**: HTTP Range-based断点续传 for unreliable networks
- **MD5 Verification**: Mandatory integrity checking with no skip mechanism
- **Atomic Deployment**: Crash-safe file replacement using temp → verify → rename pattern
- **Safe Process Control**: Graceful SIGTERM → SIGKILL with 10s timeout
- **Status Reporting**: Real-time callbacks to device-api + polling endpoint for ota-gui
- **Self-Healing**: Automatic recovery from incomplete operations on startup

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
# Activate venv
source .venv/bin/activate

# Run from project root (absolute imports work anywhere)
python -m updater.main
```

The service will start on `http://localhost:12315`.

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

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src/updater --cov-report=html

# Run specific test suite
pytest tests/unit/
pytest tests/integration/
```

## Deployment

### systemd Service

```bash
# Install service
sudo deploy/install.sh

# Start service
sudo systemctl start tope-updater

# Enable auto-start on boot
sudo systemctl enable tope-updater

# Check status
sudo systemctl status tope-updater

# View logs
sudo journalctl -u tope-updater -f
```

## Project Structure

```
src/updater/
├── main.py              # FastAPI app + uvicorn startup
├── api/
│   ├── endpoints.py     # HTTP endpoints
│   └── models.py        # Pydantic request/response models
├── services/
│   ├── download.py      # Async download with httpx
│   ├── verification.py  # MD5 computation
│   ├── deployment.py    # Atomic file operations
│   ├── process_control.py # SIGTERM/SIGKILL logic
│   └── state_manager.py # State persistence
├── models/
│   ├── manifest.py      # Manifest data structure
│   ├── state.py         # State file structure
│   └── status.py        # Status enum
└── utils/
    ├── logging.py       # Rotating logger
    └── callbacks.py     # HTTP callbacks to device-api
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
- [API Contracts](specs/001-updater-core/contracts/)
- [Quick Start Guide](specs/001-updater-core/quickstart.md)
- [Task List](specs/001-updater-core/tasks.md)

## License

Proprietary
