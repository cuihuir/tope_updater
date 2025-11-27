# Quickstart Guide: Updater Core Development

**Branch**: `001-updater-core` | **Date**: 2025-11-26

This guide provides step-by-step instructions to set up the development environment, run the updater locally, test endpoints, and deploy as a systemd service.

---

## Prerequisites

### System Requirements

- **OS**: Linux (Ubuntu 20.04+, Debian 11+, or compatible)
- **Python**: 3.11 or higher
- **systemd**: Required for service deployment
- **Network**: Internet access for downloading packages

### Check Python Version

```bash
python3 --version
# Expected: Python 3.11.0 or higher
```

If Python 3.11+ is not installed:

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install python3.11 python3.11-venv python3.11-dev

# Or use pyenv for version management
curl https://pyenv.run | bash
pyenv install 3.11.7
pyenv global 3.11.7
```

---

## Project Setup

### 1. Clone Repository

```bash
git clone <repository-url>
cd tope_updater
git checkout 001-updater-core
```

### 2. Create Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies

```bash
# Install production dependencies
pip install --upgrade pip
pip install fastapi==0.115.0 uvicorn==0.32.0 httpx==0.27.0 aiofiles==24.1.0

# Install development/testing dependencies
pip install pytest==8.3.0 pytest-asyncio==0.24.0 pytest-cov==5.0.0 black==24.8.0 mypy==1.11.0
```

### 4. Create Required Directories

```bash
mkdir -p tmp logs backups
chmod 0755 tmp logs backups
```

### 5. Verify Directory Structure

```bash
tree -L 2 -d
# Expected output:
# .
# ├── src/updater/       # Source code (to be created)
# ├── tests/             # Test files (to be created)
# ├── deploy/            # Deployment files (to be created)
# ├── tmp/               # Temporary downloads and state
# ├── logs/              # Log files
# ├── backups/           # Backup files for rollback
# └── venv/              # Virtual environment
```

---

## Development Workflow

### Running Locally (Development Mode)

Once implementation is complete, run the updater in development mode:

```bash
# From project root with venv activated
cd src
python -m updater.main

# Expected output:
# INFO:     Started server process [12345]
# INFO:     Waiting for application startup.
# INFO:     Application startup complete.
# INFO:     Uvicorn running on http://0.0.0.0:12315 (Press CTRL+C to quit)
```

**Development Features**:
- Auto-reload on code changes: `uvicorn updater.main:app --reload --port 12315`
- Debug logging: Set environment variable `LOG_LEVEL=DEBUG`
- Local testing: Use `http://localhost:12315` for API calls

### Testing API Endpoints

#### 1. Check Health (GET /progress - idle state)

```bash
curl -X GET http://localhost:12315/api/v1.0/progress | jq
```

**Expected Response**:
```json
{
  "stage": "idle",
  "progress": 0,
  "message": "Updater ready",
  "error": null
}
```

#### 2. Trigger Download (POST /download)

```bash
curl -X POST http://localhost:12315/api/v1.0/download \
  -H "Content-Type: application/json" \
  -d '{
    "version": "1.2.3",
    "package_url": "https://example.com/test-package.zip",
    "package_name": "test-package.zip",
    "package_size": 1048576,
    "package_md5": "a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4"
  }' | jq
```

**Expected Response**:
```json
{
  "status": "success",
  "message": "Download started"
}
```

#### 3. Poll Progress (GET /progress - downloading)

```bash
watch -n 1 'curl -s http://localhost:12315/api/v1.0/progress | jq'
```

**Expected Response** (during download):
```json
{
  "stage": "downloading",
  "progress": 45,
  "message": "Downloading package... 472 KB / 1024 KB",
  "error": null
}
```

#### 4. Trigger Installation (POST /update)

```bash
# Wait until download completes (stage: "idle", progress: 100)
curl -X POST http://localhost:12315/api/v1.0/update \
  -H "Content-Type: application/json" \
  -d '{"version": "1.2.3"}' | jq
```

**Expected Response**:
```json
{
  "status": "success",
  "message": "Installation started"
}
```

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src/updater --cov-report=html

# Run specific test file
pytest tests/unit/test_download.py

# Run integration tests (may require root for process control)
sudo pytest tests/integration/

# Run with verbose output
pytest -v -s
```

**Test Categories**:
- `tests/unit/`: Unit tests for individual services (download, verification, deployment, process_control, state_manager)
- `tests/integration/`: Full OTA flow tests (download → verify → install)
- `tests/contract/`: API endpoint contract validation against OpenAPI specs

---

## Mock Services for Local Testing

### Mock device-api Callback Receiver

Create a simple Flask server to receive updater callbacks:

```python
# mock_device_api.py
from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/api/v1.0/ota/report', methods=['POST'])
def ota_report():
    payload = request.json
    print(f"[device-api] Received OTA status: {payload}")
    return jsonify({"status": "received", "message": "OTA status acknowledged"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=9080)
```

Run mock device-api:

```bash
pip install flask
python mock_device_api.py
```

### Mock OTA Package Server

Create a simple HTTP server to serve test packages:

```bash
# Create test package
mkdir -p test-package/modules/test-module
echo "test binary content" > test-package/modules/test-module/test-binary
cat > test-package/manifest.json <<EOF
{
  "version": "1.2.3",
  "modules": [
    {
      "name": "test-module",
      "src": "modules/test-module/test-binary",
      "dst": "/tmp/test-install/test-binary",
      "process_name": null,
      "restart_order": 1
    }
  ]
}
EOF

# Create ZIP package
cd test-package
zip -r ../test-package.zip .
cd ..

# Compute MD5
md5sum test-package.zip
# Output: a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4  test-package.zip

# Serve package via HTTP
python3 -m http.server 8000
# Package URL: http://localhost:8000/test-package.zip
```

---

## Systemd Service Deployment

### 1. Install Updater to System

```bash
# Create installation directory
sudo mkdir -p /opt/tope/updater
sudo chown $USER:$USER /opt/tope/updater

# Copy source code
cp -r src/updater /opt/tope/updater/
cp -r venv /opt/tope/updater/

# Create runtime directories
sudo mkdir -p /opt/tope/updater/{tmp,logs,backups}
sudo chmod 0755 /opt/tope/updater/{tmp,logs,backups}
```

### 2. Create systemd Service Unit

```bash
sudo tee /etc/systemd/system/tope-updater.service > /dev/null <<EOF
[Unit]
Description=TOPE OTA Updater Service
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/tope/updater
ExecStart=/opt/tope/updater/venv/bin/python3 -m updater.main
Restart=always
RestartSec=10
StartLimitInterval=300
StartLimitBurst=5

# Resource limits (Constitution Principle IX)
MemoryMax=100M
CPUQuota=50%

# Security hardening
PrivateTmp=yes
ProtectSystem=strict
ReadWritePaths=/opt/tope/updater/tmp /opt/tope/updater/logs /opt/tope/updater/backups /opt/tope
NoNewPrivileges=false
CapabilityBoundingSet=CAP_KILL CAP_FOWNER CAP_CHOWN CAP_DAC_OVERRIDE

# Timeout settings (graceful shutdown)
TimeoutStopSec=30
KillSignal=SIGTERM
KillMode=mixed

[Install]
WantedBy=multi-user.target
EOF
```

### 3. Enable and Start Service

```bash
# Reload systemd daemon
sudo systemctl daemon-reload

# Enable auto-start on boot
sudo systemctl enable tope-updater.service

# Start service
sudo systemctl start tope-updater.service

# Check status
sudo systemctl status tope-updater.service
```

### 4. Monitor Logs

```bash
# View real-time logs
sudo journalctl -u tope-updater.service -f

# View recent logs
sudo journalctl -u tope-updater.service -n 100

# View updater log file
tail -f /opt/tope/updater/logs/updater.log
```

### 5. Service Management

```bash
# Stop service
sudo systemctl stop tope-updater.service

# Restart service
sudo systemctl restart tope-updater.service

# Disable auto-start
sudo systemctl disable tope-updater.service

# Check service health
curl http://localhost:12315/api/v1.0/progress
```

---

## Troubleshooting

### Port 12315 Already in Use

**Symptom**: Updater fails to start with error `Address already in use`

**Solution**:
```bash
# Find process using port 12315
sudo lsof -i :12315

# Kill the process
sudo kill -9 <PID>

# Or change port temporarily (development only)
# Edit src/updater/main.py: uvicorn.run(app, host="0.0.0.0", port=12316)
```

### Import Errors (Module Not Found)

**Symptom**: `ModuleNotFoundError: No module named 'fastapi'`

**Solution**:
```bash
# Ensure virtual environment is activated
source venv/bin/activate

# Reinstall dependencies
pip install -r requirements.txt  # (create requirements.txt first)
```

### Permission Denied During Installation

**Symptom**: `PermissionError: [Errno 13] Permission denied: '/opt/tope/device-api/device-api'`

**Solution**:
```bash
# Updater MUST run as root for process control and system file deployment
sudo systemctl restart tope-updater.service

# Check service user
systemctl show tope-updater.service -p User
# Expected: User=root
```

### Download Fails with SSL Error

**Symptom**: `SSLError: [SSL: CERTIFICATE_VERIFY_FAILED]`

**Solution**:
```bash
# Install CA certificates
sudo apt update
sudo apt install ca-certificates

# Update Python certifi package
pip install --upgrade certifi
```

### State File Corruption

**Symptom**: Updater keeps re-downloading after restart

**Solution**:
```bash
# Remove corrupted state file
sudo rm /opt/tope/updater/tmp/state.json

# Restart updater
sudo systemctl restart tope-updater.service
```

---

## Development Tools

### Code Formatting

```bash
# Format all Python files with black
black src/ tests/

# Check formatting without modifying
black --check src/ tests/
```

### Type Checking

```bash
# Run mypy type checker
mypy src/updater/

# Strict mode
mypy --strict src/updater/
```

### Linting

```bash
# Install linters
pip install ruff pylint

# Run ruff (fast)
ruff check src/ tests/

# Run pylint (detailed)
pylint src/updater/
```

### API Documentation (Auto-Generated)

FastAPI automatically generates interactive API documentation:

- **Swagger UI**: http://localhost:12315/docs
- **ReDoc**: http://localhost:12315/redoc
- **OpenAPI JSON**: http://localhost:12315/openapi.json

---

## Next Steps

1. **Implement Source Code**: Follow [plan.md](./plan.md) and [data-model.md](./data-model.md) to implement services
2. **Write Tests**: Create unit tests as you implement each service
3. **Integration Testing**: Use mock services to test full OTA flow
4. **Contract Testing**: Validate API against [contracts/updater-api.yaml](./contracts/updater-api.yaml)
5. **Field Testing**: Deploy to test device and run update scenarios

---

## References

- [Feature Specification](./spec.md) - Complete functional requirements
- [Implementation Plan](./plan.md) - Phased implementation strategy
- [Data Model](./data-model.md) - Entities, state machines, validation rules
- [Updater API Contract](./contracts/updater-api.yaml) - OpenAPI specification
- [device-api Callbacks](./contracts/device-api-callbacks.yaml) - Callback endpoint contract
- [Constitution](../../.specify/memory/constitution.md) - Core principles and governance
