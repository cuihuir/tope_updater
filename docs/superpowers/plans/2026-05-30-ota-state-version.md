# OTA State And Version Handling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Normalize OTA versions and make pending-package replacement/recovery reliable.

**Architecture:** Add a focused version utility and keep all external `vX.Y.Z` handling at API/manifest/report boundaries. Preserve existing services while tightening state transitions and cleanup paths.

**Tech Stack:** Python 3.11, FastAPI, Pydantic v2, pytest, ruff.

---

### Task 1: Version Boundary

**Files:**
- Create: `src/updater/utils/version.py`
- Modify: `src/updater/api/models.py`
- Modify: `src/updater/models/manifest.py`
- Modify: `src/updater/api/routes.py`
- Test: `tests/unit/test_version_utils.py`
- Test: `tests/unit/test_routes.py`
- Test: `tests/unit/test_deploy.py`

- [ ] Write failing tests for accepting `v0.1.1` and normalizing to `0.1.1`.
- [ ] Implement `normalize_version()` and `format_report_version()`.
- [ ] Use normalized versions before download/update workflows and manifest comparison.
- [ ] Verify version directories remain `v0.1.1`, not `vv0.1.1`.

### Task 2: Pending Package Replacement

**Files:**
- Modify: `src/updater/api/routes.py`
- Modify: `src/updater/services/download.py`
- Test: `tests/unit/test_routes.py`
- Test: `tests/unit/test_download.py`

- [ ] Write failing tests showing `toInstall` allows new download.
- [ ] Write failing tests showing expired pending packages are cleared and replaced.
- [ ] Write failing tests showing a superseding package removes the old pending ZIP.
- [ ] Implement cleanup before starting a new download while preserving active-operation rejection.

### Task 3: Install Persistence And Recovery

**Files:**
- Modify: `src/updater/api/routes.py`
- Modify: `src/updater/main.py`
- Test: `tests/unit/test_routes.py`
- Test: `tests/unit/test_main_lifespan.py`

- [ ] Write failing tests proving `_update_workflow` saves `installing` state before deployment.
- [ ] Write failing tests proving startup recovers interrupted `installing` to `failed`.
- [ ] Implement minimal persistence and startup recovery.

### Task 4: Progress Clamping And Verification

**Files:**
- Modify: `src/updater/services/download.py`
- Test: `tests/unit/test_download.py`

- [ ] Write failing test for over-100 download progress when bytes exceed declared size.
- [ ] Clamp progress to `0..100`.
- [ ] Run focused tests, full unit tests, and ruff.

### Task 5: Final Review

**Files:**
- All touched files.

- [ ] Run `uv run pytest tests/unit/ -q`.
- [ ] Run `uv run ruff check` on touched files.
- [ ] Review diffs for scope, no unrelated edits, and no `vv` version paths.
