<!--
SYNC IMPACT REPORT
==================
Version: 1.1.0 → 1.2.0
Date: 2025-11-28

Changes Summary:
- Modified Principle VIII: Resumable Operations (断点续传)
  - Changed from MUST to SHOULD (relaxed requirement)
  - Added MAY clause for restart-from-scratch approach
  - Updated rationale to reflect reliability over bandwidth optimization

Previous Changes (v1.1.0):
- Added Principle XII: Bilingual Documentation (Chinese + English)
- Created companion Chinese version at constitution_cn.md

Previous Changes (v1.0.0):
- Initial constitution creation from template
- Established 11 core principles for OTA updater device program
- Added Security & Reliability Standards section
- Added Exception Handling & Recovery section
- Defined Governance rules for locked codebase

Current Principles (v1.2.0):
- PRINCIPLE_1: Core Mission (Prime Directive)
- PRINCIPLE_2: Minimal Dependencies
- PRINCIPLE_3: Idempotent Operations
- PRINCIPLE_4: Atomic File Operations
- PRINCIPLE_5: Mandatory MD5 Verification
- PRINCIPLE_6: Manifest-Driven Deployment
- PRINCIPLE_7: Safe Process Control (systemd service management)
- PRINCIPLE_8: Resumable Operations (断点续传) - MODIFIED: MUST → SHOULD
- PRINCIPLE_9: Resource Protection
- PRINCIPLE_10: Comprehensive Error Reporting
- PRINCIPLE_11: Structured Logging
- PRINCIPLE_12: Bilingual Documentation

Modified Sections (v1.2.0):
- Principle VIII: Relaxed from mandatory to recommended
- Principle VII note: Clarified systemd service management (not process management)

Templates Requiring Updates:
⚠️ spec.md - Need to update FR-003, US2 to reflect optional resumption
⚠️ plan.md - Need to update constitution check for Principle VIII
⚠️ tasks.md - Need to update Phase 4 status (deferred → optional)

Follow-up TODOs:
- Update spec.md FR-003 to change MUST to SHOULD
- Update plan.md Principle VIII check to PASS (SHOULD compliance)
- Update tasks.md Phase 4 to mark as "Optional Enhancement"
- Update constitution_cn.md (Chinese version)

Rationale for MINOR version (1.2.0):
- Relaxed requirement (MUST → SHOULD) for Principle VIII
- No breaking changes to existing implementations
- Allows simpler restart-from-scratch approach for MVP
- Maintains option for future resumption enhancement
-->

# TOP.E OTA Updater Device Program Constitution

## Core Principles

### I. Core Mission (Prime Directive)

The `updater` program has ONE mission: **安全可靠地完成固件/软件更新** (safely and reliably complete firmware/software updates).

**Rules**:
- MUST NOT include any business logic unrelated to OTA update operations
- MUST NOT add features beyond: download, verify, deploy, process control
- MUST prioritize reliability and simplicity over feature richness

**Rationale**: As the seed OTA updater for the device's entire lifecycle, this program must be bulletproof. Complexity is the enemy of reliability. Every line of code is a potential failure point.

---

### II. Minimal Dependencies

The `updater` program MUST minimize external dependencies to ensure long-term stability.

**Rules**:
- MUST NOT depend on third-party libraries except:
  - System-level libraries (libc, POSIX APIs)
  - Standard language runtime libraries (Go stdlib, Rust std, C++ STL)
- MUST implement core functionality using system calls and standard libraries
- MUST justify ANY exception with security/performance/compatibility rationale

**Rationale**: Third-party dependencies introduce:
- Version compatibility risks across device lifecycle
- Security vulnerabilities requiring updates (violates zero-maintenance principle)
- Potential supply chain attacks
- Increased binary size and complexity

---

### III. Idempotent Operations

All critical operations MUST be idempotent—repeatable without adverse side effects.

**Rules**:
- Download operations MUST safely resume or restart
- File deployment MUST handle partial completion gracefully
- Process restart MUST tolerate multiple execution attempts
- Update state MUST be recoverable from any interruption point

**Rationale**: Network failures, power loss, and system crashes are inevitable in field deployment. Idempotency ensures the updater can always recover safely without manual intervention.

---

### IV. Atomic File Operations

File system modifications MUST be atomic to prevent corrupted state.

**Rules**:
- MUST write to temporary files first (e.g., `target.tmp`)
- MUST verify integrity before committing (MD5 check on temp file)
- MUST use atomic operations (e.g., `rename()`) to replace target files
- MUST maintain backup of critical files before replacement

**Rationale**: A power failure during file write could corrupt the target program. Atomic operations ensure the system is always in a consistent state—either the old version or the new version, never a broken hybrid.

---

### V. Mandatory MD5 Verification

ALL downloaded update packages MUST pass MD5 integrity verification.

**Rules**:
- MUST obtain `package_md5` from cloud version management API
- MUST compute MD5 hash of downloaded package locally
- MUST compare cloud MD5 with local MD5 byte-for-byte
- MUST abort update and report `MD5_MISMATCH` error if verification fails
- MUST NOT skip verification under any circumstance

**Rationale**: Network corruption, man-in-the-middle attacks, and storage errors can corrupt update packages. MD5 verification (while not cryptographically secure) provides basic corruption detection. For security-critical deployments, consider upgrading to SHA-256 in future hardening (requires constitution amendment).

---

### VI. Manifest-Driven Deployment

Package deployment MUST strictly follow the embedded Manifest file.

**Rules**:
- MUST parse Manifest to extract module list, source paths (`src`), target paths (`dst`)
- MUST validate all paths before deployment (no directory traversal attacks)
- MUST verify target directory existence and permissions
- MUST create missing directories with appropriate permissions
- MUST deploy files in Manifest order (if dependencies exist)

**Rationale**: The Manifest is the single source of truth for deployment. Hard-coding paths or making assumptions violates maintainability and creates version-specific bugs.

---

### VII. Safe Service Management

Service termination and restart MUST be safe and orderly using systemd service management.

**Rules**:
- MUST use `systemctl stop <service>` for graceful shutdown (systemd sends SIGTERM, waits for timeout, then SIGKILL)
- MUST verify service termination before file replacement (check systemd service status)
- MUST restart services in dependency order using systemd service dependencies (e.g., `device-api.service` before dependent services)
- MUST report service control failures to cloud
- MAY use direct SIGTERM/SIGKILL for services not managed by systemd (fallback only)

**Rationale**: systemd provides robust service lifecycle management with built-in timeout handling, dependency ordering, and health monitoring. Using systemd ensures consistent service control across all device components. Direct process management (SIGTERM/SIGKILL) is fragile and error-prone compared to systemd's declarative approach.

---

### VIII. Resumable Operations (断点续传)

Downloads SHOULD support HTTP Range-based resumption for improved user experience, but restart-from-scratch is acceptable for reliable delivery.

**Rules**:
- SHOULD use HTTP `Range` header to request partial content
- SHOULD track download progress persistently (e.g., state file)
- SHOULD validate partial downloads before resuming
- MUST fall back to full download if partial state is corrupted or on service restart/timeout
- MAY restart download from beginning on service interruption (acceptable tradeoff for simpler implementation)

**Rationale**: While resumable downloads minimize data transfer on unreliable networks (WiFi dropouts, cellular handoffs), restart-from-scratch also guarantees reliable version delivery. The primary goal is successful update completion, not bandwidth optimization. Service restart/timeout scenarios can safely restart downloads as network stability is typically restored before retry.

---

### IX. Resource Protection

The `updater` MUST limit its resource consumption.

**Rules**:
- MUST limit memory usage (e.g., streaming downloads, not buffering entire file)
- MUST limit CPU usage (avoid tight loops, use blocking I/O where appropriate)
- MUST limit disk I/O rate if device has active workloads (e.g., printing)
- MUST release resources promptly (close file handles, free memory)

**Rationale**: The updater runs on resource-constrained embedded devices. Excessive resource usage could interfere with primary device functions (e.g., printing), leading to user-visible failures and support burden.

---

### X. Comprehensive Error Reporting

ALL errors MUST be reported to the cloud via `device-api`.

**Rules**:
- MUST define error codes for all failure scenarios (e.g., `DOWNLOAD_FAILED`, `MD5_MISMATCH`, `DEPLOY_FAILED`, `PROCESS_RESTART_FAILED`)
- MUST include descriptive error messages (e.g., "Failed to verify MD5: expected abc123, got def456")
- MUST report error context (e.g., retry count, network state, disk space)
- MUST send error reports before aborting update

**Rationale**: Silent failures are impossible to debug in field deployments. Comprehensive error reporting enables remote diagnostics, proactive alerting, and data-driven reliability improvements.

---

### XI. Structured Logging

The `updater` MUST log all critical operations to a local log file.

**Rules**:
- MUST log to size-limited file (e.g., 10MB max, rotating)
- MUST include timestamps (ISO 8601 format)
- MUST log at appropriate levels (DEBUG/INFO/WARN/ERROR)
- MUST log: download start/complete, MD5 verification, file deployment, process control, errors

**Rationale**: Local logs are the last line of defense when cloud connectivity fails. Size limits prevent disk exhaustion. Structured logging enables automated parsing for remote diagnostics.

---

### XII. Bilingual Documentation

ALL design documents MUST be provided in both Chinese and English versions.

**Rules**:
- MUST create both `[document].md` (English) and `[document]_cn.md` (Chinese) for all specifications
- MUST keep both versions synchronized when updates occur
- MUST maintain equivalent technical precision in both languages
- Applies to: constitution, specifications, plans, API contracts, user guides

**Rationale**: Bilingual documentation ensures:
- Accessibility for both Chinese and international engineering teams
- Knowledge transfer across language boundaries
- Reduced miscommunication in critical safety requirements
- Long-term maintainability by diverse contributors

---

## Security & Reliability Standards

### Code Language & Compilation

- **Approved Languages**: Go (preferred), Rust, or C/C++
- **Rationale**: Small binary size, high performance, no runtime dependencies, memory safety (Go/Rust)
- **Build Requirements**: Static linking preferred to minimize runtime dependencies

### Rollback & Recovery

- MUST implement basic rollback mechanism for critical system components
- On deployment failure, MUST attempt to restore previous version
- If rollback fails, MUST enter safe/recovery mode (e.g., boot into minimal shell)

### Progress Reporting

- MUST report download progress (0-100%) to `device-api` at regular intervals (e.g., every 5%)
- MUST report deployment progress (e.g., "deploying module X of Y")
- Progress reporting enables user-visible status and timeout detection

---

## Exception Handling & Recovery

### Startup Self-Healing

On startup, the `updater` MUST:
1. Check for incomplete update operations
2. Validate integrity of previously deployed files
3. Attempt to resume or retry failed operations
4. Report recovery actions to cloud

### Failure Recovery Strategy

| Failure Scenario | Recovery Action |
|-----------------|-----------------|
| Download failure (network) | Retry with exponential backoff (max 3 attempts), then report failure |
| MD5 mismatch | Delete corrupted file, re-download from scratch, report corruption |
| Disk full | Report error immediately, do not retry |
| Process kill failure | Report error, continue with other modules (partial update) |
| Deployment failure | Rollback deployed files, restore previous version, report failure |

---

## Governance

### Amendment Procedure

This constitution governs all development of the `updater` program. Amendments require:

1. **Documentation**: Proposal with rationale, impact analysis, migration plan
2. **Approval**: Technical lead review and explicit approval
3. **Version Bump**:
   - MAJOR: Breaking changes to principles, removal of guarantees
   - MINOR: New principles, expanded requirements
   - PATCH: Clarifications, typo fixes, non-semantic changes

### Code Lock Policy (NON-NEGOTIABLE)

Once `updater v1.0.0` is released and field-tested:

- Core logic code MUST be locked
- Only high-severity security vulnerability fixes allowed
- NO new features permitted (create new update mechanism if needed)
- Any modification requires constitution amendment justification

**Rationale**: The `updater` is the bedrock of device OTA. Feature creep and "improvements" introduce instability. Stability through immutability.

### Compliance Review

- All code changes MUST be reviewed against this constitution
- Reviewers MUST explicitly confirm compliance before approval
- Violations MUST be justified in writing or rejected

### Documentation Requirements

- All functions MUST have comments explaining "why" (not just "what")
- Platform-specific code MUST document OS/architecture assumptions
- Error handling MUST document failure modes and recovery strategies

---

**Version**: 1.2.0 | **Ratified**: 2025-11-25 | **Last Amended**: 2025-11-28
