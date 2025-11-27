# Data Model: Updater Core OTA Program

**Branch**: `001-updater-core` | **Date**: 2025-11-26 | **Spec**: [spec.md](./spec.md)

This document defines the core entities, state machines, and data structures for the OTA updater system.

## Core Entities

### 1. Update Package

**Description**: ZIP archive containing manifest.json, module directories, and binary files to be deployed. Stored on S3 with pre-signed URL for download.

**Fields**:
- `version` (string): Semantic version identifier (e.g., "1.2.3")
- `package_url` (string): HTTPS URL to download package from S3-compatible storage
- `package_name` (string): Filename of package (e.g., "tope-update-1.2.3.zip")
- `package_size` (integer): Total size in bytes
- `package_md5` (string): Expected MD5 hash for integrity verification (32-character hex string)

**Validation Rules** (from FR-001a):
- `version` MUST match semantic versioning pattern `\d+\.\d+\.\d+`
- `package_url` MUST use HTTPS protocol
- `package_size` MUST be positive integer
- `package_md5` MUST be 32-character hexadecimal string

**Storage**: Downloaded to `./tmp/<package_name>`, extracted to `./tmp/extracted/`

---

### 2. Manifest

**Description**: JSON file (`manifest.json`) embedded in package root, defining version string and array of modules with source and destination paths.

**Schema**:
```json
{
  "version": "1.2.3",
  "modules": [
    {
      "name": "device-api",
      "src": "modules/device-api/device-api",
      "dst": "/opt/tope/device-api/device-api",
      "process_name": "device-api",
      "restart_order": 1
    },
    {
      "name": "voice-app",
      "src": "modules/voice-app/voice-app",
      "dst": "/opt/tope/voice-app/voice-app",
      "process_name": "voice-app",
      "restart_order": 2
    }
  ]
}
```

**Fields**:
- `version` (string): Must match Update Package version
- `modules` (array): List of Module objects

**Validation Rules** (from FR-007, FR-008):
- MUST exist at package root: `manifest.json`
- `version` field MUST be present and non-empty
- `modules` array MUST contain at least 1 module
- Each module MUST have `name`, `src`, `dst` fields
- `src` paths MUST be relative (no leading `/`, no `..`)
- `dst` paths MUST be absolute (start with `/`)
- `dst` paths MUST NOT contain `..` (directory traversal prevention)

---

### 3. Module

**Description**: Individual software component to be updated (e.g., device-api, voice-app, klippy).

**Fields**:
- `name` (string): Human-readable module identifier
- `src` (string): Relative path within ZIP package to source file
- `dst` (string): Absolute target path on device filesystem
- `process_name` (string, optional): Name of running process to terminate before deployment
- `restart_order` (integer, optional): Sequence for restarting services (lower = earlier)

**Validation Rules** (from FR-008, FR-014):
- `name` MUST be unique within manifest
- `src` MUST exist within extracted package directory
- `dst` parent directory MUST be created if missing (FR-009)
- If `process_name` provided, process control applies (FR-012, FR-013)
- If `restart_order` provided, services restart in ascending order (FR-014)

---

### 4. Status State

**Description**: In-memory JSON structure containing current OTA operation state. Exposed via HTTP GET `/api/v1.0/progress` endpoint for ota-gui polling and pushed to device-api via HTTP POST `/api/v1.0/ota/report` callbacks.

**Schema**:
```json
{
  "stage": "downloading",
  "progress": 45,
  "message": "Downloading package...",
  "error": null
}
```

**Fields**:
- `stage` (string enum): Current lifecycle stage
  - `idle`: No operation in progress
  - `downloading`: Package download in progress
  - `verifying`: MD5 verification in progress
  - `toInstall`: Package verified and ready for installation, waiting for POST /update command
  - `installing`: File deployment and process restart in progress
  - `rebooting`: System reboot triggered (optional)
  - `success`: Update completed successfully
  - `failed`: Update failed (see `error` field)
- `progress` (integer): Percentage completion (0-100)
- `message` (string): Human-readable status description
- `error` (string or null): Error code and message if `stage == "failed"`

**Error Codes** (from FR-005, FR-020, Edge Cases):
- `MD5_MISMATCH`: MD5 hash verification failed
- `DISK_FULL`: Insufficient disk space during download
- `INVALID_MANIFEST`: Malformed or missing manifest.json
- `DOWNLOAD_FAILED`: HTTP download failed after retries
- `PROCESS_KILL_FAILED`: Unable to terminate process even with SIGKILL
- `DEPLOYMENT_FAILED`: File deployment or atomic rename failed
- `PACKAGE_EXPIRED`: Verified package exceeded 24-hour trust window, re-download required

**Update Triggers** (from FR-016):
- Progress changes by 5% during download stage
- Stage transitions (downloading → verifying → installing → success/failed)
- Error detected

---

### 5. State File

**Description**: JSON file at `./tmp/state.json` containing persistent state across restarts for resumable downloads. This file survives reboots.

**Schema**:
```json
{
  "version": "1.2.3",
  "package_url": "https://s3.example.com/updates/tope-1.2.3.zip",
  "package_name": "tope-update-1.2.3.zip",
  "package_size": 104857600,
  "package_md5": "abc123def456...",
  "bytes_downloaded": 52428800,
  "last_update": "2025-11-26T10:30:45Z",
  "stage": "downloading"
}
```

**Fields**:
- `version` (string): Version being downloaded/installed
- `package_url` (string): Original download URL
- `package_name` (string): Target filename
- `package_size` (integer): Total expected bytes
- `package_md5` (string): Expected MD5 hash
- `bytes_downloaded` (integer): Current byte position for resumable download
- `last_update` (string): ISO 8601 timestamp of last state update
- `stage` (string): Last known stage (for recovery on startup)
- `verified_at` (string): ISO 8601 timestamp when MD5 verification completed (null if not yet verified)

**Validation Rules** (from FR-003, FR-024, FR-025, FR-026):
- File MUST be valid JSON
- If `bytes_downloaded > 0`, partial file MUST exist at `./tmp/<package_name>`
- If `bytes_downloaded == package_size`, MD5 verification MUST be performed before installation
- If file corrupted or `stage == "failed"`, discard and re-download from scratch
- **Package Timeout**: If `verified_at` exists and `(current_time - verified_at) > 24 hours`, package is considered expired. POST /update MUST return error `PACKAGE_EXPIRED` and require re-download

**Lifecycle**:
- Created when POST `/api/v1.0/download` starts download
- Updated every 5% progress during download
- Deleted after successful update completion (FR-028)
- Validated on startup for self-healing (FR-024)

---

## State Machine

### OTA Lifecycle State Machine

```
┌──────┐
│ idle │ ◄────────────────────────────────────────┐
└───┬──┘                                           │
    │ POST /api/v1.0/download                      │
    ▼                                              │
┌─────────────┐                                    │
│ downloading │ ─── network failure ───┐           │
└──────┬──────┘                        │           │
       │ download complete             │           │
       ▼                               │           │
┌───────────┐                          │           │
│ verifying │ ─── MD5 mismatch ────────┼────┐      │
└─────┬─────┘                          │    │      │
      │ MD5 valid                      │    │      │
      ▼                                │    │      │
┌───────────┐                          │    │      │
│ toInstall │ ─── package expired ─────┼────┼──┐   │
└─────┬─────┘     (>24h)               │    │  │   │
      │ POST /api/v1.0/update          │    │  │   │
      ▼                                │    │  │   │
┌────────────┐                         │    │  │   │
│ installing │ ─── deployment fail ────┼────┼──┼───┤
└──────┬─────┘                         │    │  │   │
       │ deployment success            │    │  │   │
       ▼                               │    │  │   │
┌───────────┐                          │    │  │   │
│ rebooting │ (optional)               │    │  │   │
└─────┬─────┘                          │    │  │   │
      │                                │    │  │   │
      ▼                                │    │  │   │
┌─────────┐                            │    │  │   │
│ success │ ────────────────────────────────────────┘
└─────────┘                            │    │  │
                                       │    │  │
                ┌──────┐               │    │  │
                │failed│ ◄─────────────┴────┴──┘
                └───┬──┘
                    │ cleanup + retry/abort
                    └──────────────────────►
```

**State Transitions**:

| From State    | Event                     | To State      | Actions                                      |
|---------------|---------------------------|---------------|----------------------------------------------|
| idle          | POST /download            | downloading   | Create state.json, start httpx download      |
| downloading   | Download complete         | verifying     | Compute MD5 hash                             |
| downloading   | Network failure           | failed        | Save state.json, report `DOWNLOAD_FAILED`    |
| downloading   | Disk full                 | failed        | Abort, report `DISK_FULL`                    |
| verifying     | MD5 matches               | toInstall     | Set verified_at timestamp, report to device-api, wait for POST /update |
| verifying     | MD5 mismatch              | failed        | Delete file, report `MD5_MISMATCH`           |
| toInstall     | POST /update              | installing    | Check timeout (current_time - verified_at < 24h), launch OTA-GUI, stop processes, deploy files, restart |
| toInstall     | Package expired (>24h)    | failed        | Delete package, report `PACKAGE_EXPIRED`, require re-download |
| installing    | Deployment success        | success       | Cleanup temp files, delete state.json        |
| installing    | Deployment failure        | failed        | Rollback, report `DEPLOYMENT_FAILED`         |
| success       | Cleanup complete          | idle          | Reset status state                           |
| failed        | Cleanup complete          | idle          | Reset status state (requires new /download)  |

**OTA-GUI Integration** (from FR-022, FR-023):
- **When**: Launched at transition to `installing` stage (triggered by POST /update)
- **Purpose**: Displays full-screen progress interface, masking original GUI
- **Implementation**: Updater executes `/opt/tope/ota-gui` if binary exists
- **Failure Handling**: OTA-GUI missing/crash MUST NOT prevent update completion (non-blocking)
- **Status Source**: OTA-GUI polls GET `/api/v1.0/progress` endpoint every 500ms
- **Scope**: OTA-GUI implementation is NOT part of current spec (001-updater-core), documented here for reference

**Idempotency Rules** (from FR-001a):
- POST /download with same `package_url` → resume existing download (check state.json)
- POST /update when stage != toInstall → return 409 Conflict with appropriate error message
- POST /update during active installation → return 409 Conflict
- POST /update when package expired (verified_at + 24h < current_time) → return 409 Conflict with `PACKAGE_EXPIRED` error

**Package Timeout Rules**:
- **Trust Window**: 24 hours from `verified_at` timestamp
- **Validation**: Checked at POST /update request before installation begins
- **Action on Expiry**: Delete package files, delete state.json, return 409 error `PACKAGE_EXPIRED: Package verified at {timestamp} has exceeded 24-hour trust window, please re-download`
- **Rationale**: Prevents installation of potentially compromised packages that were verified long ago

---

## Relationships

```
┌──────────────────┐
│ Update Package   │
│ (downloaded ZIP) │
└────────┬─────────┘
         │ contains
         ▼
    ┌─────────┐
    │Manifest │
    └────┬────┘
         │ defines
         ▼
    ┌────────┐
    │ Module │ (1..N)
    └────┬───┘
         │ deployed as
         ▼
    ┌──────────────┐
    │ Target Files │
    │ on Filesystem│
    └──────────────┘

┌─────────────┐         ┌──────────────┐
│ Status State│ ◄───────┤ State File   │
│ (in-memory) │  loads  │ (persistent) │
└──────┬──────┘         └──────────────┘
       │
       │ exposes via HTTP
       ▼
┌─────────────────────┐      ┌──────────────┐      ┌──────────┐
│ GET /progress       │      │device-api    │      │ OTA-GUI  │
│ (for ota-gui poll)  │◄─────┤callbacks     │      │(optional)│
└─────────────────────┘      └──────▲───────┘      └────┬─────┘
                                    │                     │
                            POST /ota/report              │
                            (from updater)                │
                                                          │
                                             launched by POST /update
                                             (installing stage)
```

---

## Pydantic Models (Implementation Reference)

### API Request/Response Models

```python
from pydantic import BaseModel, Field, validator
from typing import Optional, Literal
from enum import Enum

class DownloadRequest(BaseModel):
    """POST /api/v1.0/download payload (FR-001a)"""
    version: str = Field(..., pattern=r'^\d+\.\d+\.\d+$')
    package_url: str = Field(..., regex=r'^https://.+')
    package_name: str
    package_size: int = Field(..., gt=0)
    package_md5: str = Field(..., regex=r'^[a-f0-9]{32}$')

class UpdateRequest(BaseModel):
    """POST /api/v1.0/update payload (FR-001b)"""
    version: str = Field(..., pattern=r'^\d+\.\d+\.\d+$')

class StageEnum(str, Enum):
    IDLE = "idle"
    DOWNLOADING = "downloading"
    VERIFYING = "verifying"
    TO_INSTALL = "toInstall"
    INSTALLING = "installing"
    REBOOTING = "rebooting"
    SUCCESS = "success"
    FAILED = "failed"

class ProgressResponse(BaseModel):
    """GET /api/v1.0/progress response (FR-001c)"""
    stage: StageEnum
    progress: int = Field(..., ge=0, le=100)
    message: str
    error: Optional[str] = None

class ReportPayload(BaseModel):
    """POST to device-api /api/v1.0/ota/report (FR-016)"""
    stage: StageEnum
    progress: int = Field(..., ge=0, le=100)
    message: str
    error: Optional[str] = None
```

### Persistent State Models

```python
from datetime import datetime

class StateFile(BaseModel):
    """Persistent state at ./tmp/state.json (FR-003, FR-025)"""
    version: str
    package_url: str
    package_name: str
    package_size: int
    package_md5: str
    bytes_downloaded: int = 0
    last_update: datetime
    stage: StageEnum
    verified_at: Optional[datetime] = None  # Timestamp when MD5 verification completed

    @validator('last_update', 'verified_at', pre=True)
    def parse_iso8601(cls, v):
        if isinstance(v, str):
            return datetime.fromisoformat(v.replace('Z', '+00:00'))
        return v

    def is_package_expired(self) -> bool:
        """Check if package has exceeded 24-hour trust window"""
        if self.verified_at is None:
            return False
        from datetime import timedelta
        return (datetime.now() - self.verified_at) > timedelta(hours=24)
```

### Manifest Models

```python
class ManifestModule(BaseModel):
    """Module entry in manifest.json (FR-007)"""
    name: str
    src: str = Field(..., regex=r'^[^/].*$')  # No leading /
    dst: str = Field(..., regex=r'^/.*$')     # Must be absolute
    process_name: Optional[str] = None
    restart_order: Optional[int] = None

    @validator('src')
    def no_directory_traversal_src(cls, v):
        if '..' in v:
            raise ValueError('Source path must not contain ..')
        return v

    @validator('dst')
    def no_directory_traversal_dst(cls, v):
        if '..' in v:
            raise ValueError('Destination path must not contain ..')
        return v

class Manifest(BaseModel):
    """Root manifest.json schema (FR-007)"""
    version: str = Field(..., pattern=r'^\d+\.\d+\.\d+$')
    modules: list[ManifestModule] = Field(..., min_items=1)

    @validator('modules')
    def unique_module_names(cls, v):
        names = [m.name for m in v]
        if len(names) != len(set(names)):
            raise ValueError('Module names must be unique')
        return v
```

---

## Validation Summary

**Constitution Principle Alignment**:

- **Principle III (Idempotent Operations)**: Status State tracks stage, State File enables resumption
- **Principle IV (Atomic File Operations)**: Module deployment uses temp files + rename() pattern
- **Principle V (Mandatory MD5 Verification)**: Update Package includes `package_md5`, State Machine includes explicit `verifying` stage
- **Principle VI (Manifest-Driven Deployment)**: Manifest entity is single source of truth for module deployment
- **Principle VIII (Resumable Operations)**: State File tracks `bytes_downloaded` for HTTP Range requests
- **Principle X (Comprehensive Error Reporting)**: Status State includes structured `error` field with error codes

**Functional Requirements Coverage**:
- FR-001a/b/c: Covered by DownloadRequest, UpdateRequest, ProgressResponse models
- FR-003: Covered by State File `bytes_downloaded` field
- FR-004, FR-005: Covered by Update Package `package_md5` and State Machine `verifying` stage
- FR-007, FR-008: Covered by Manifest validation rules (path traversal prevention)
- FR-016: Covered by ReportPayload model for device-api callbacks
- FR-022, FR-023: Covered by OTA-GUI Integration notes in State Machine
- FR-024, FR-025, FR-026: Covered by State File persistence and startup validation logic
