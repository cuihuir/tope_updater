# TOP.E OTA Updater - GUI Feature Tasks

**Feature**: 002-gui
**Status**: Planning
**Created**: 2026-01-29
**Last Updated**: 2026-01-29

---

## Task Overview

| Phase | Tasks | Status | Priority |
|-------|-------|--------|----------|
| Phase 0: Setup | 3 tasks | ⏳ Pending | P0 |
| Phase 1: GUI Foundation | 4 tasks | ⏳ Pending | P0 |
| Phase 2: Process Management | 3 tasks | ⏳ Pending | P0 |
| Phase 3: Integration | 3 tasks | ⏳ Pending | P0 |
| Phase 4: Testing | 6 tasks | ⏳ Pending | P1 |
| Phase 5: Documentation | 3 tasks | ⏳ Pending | P2 |

**Total**: 22 tasks

---

## Phase 0: Setup and Prerequisites

### T001: Install PySDL2 Dependencies
- **Status**: ⏳ Pending
- **Priority**: P0 (Critical)
- **Estimated Time**: 0.5 hours
- **Assignee**: TBD

**Description**:
Add PySDL2 dependencies to `pyproject.toml` and install them.

**Acceptance Criteria**:
- [ ] `PySDL2>=0.9.16` added to dependencies
- [ ] `PySDL2-dll>=2.28.0` added to dependencies
- [ ] `uv sync` completes successfully
- [ ] `python -c "import sdl2; print('OK')"` works

**Commands**:
```bash
# Edit pyproject.toml
# Add PySDL2 dependencies

# Install
uv sync

# Verify
python -c "import sdl2; print('SDL2 OK')"
```

---

### T002: Download and Bundle Font
- **Status**: ⏳ Pending
- **Priority**: P0 (Critical)
- **Estimated Time**: 0.5 hours
- **Assignee**: TBD

**Description**:
Download Noto Sans CJK SC font and place it in the GUI fonts directory.

**Acceptance Criteria**:
- [ ] Font directory created: `src/updater/gui/fonts/`
- [ ] Font downloaded: `NotoSansCJKsc-Regular.otf`
- [ ] Font file size ~5MB
- [ ] Font file readable

**Commands**:
```bash
mkdir -p src/updater/gui/fonts

wget -O src/updater/gui/fonts/NotoSansCJKsc-Regular.otf \
  https://github.com/googlefonts/noto-cjk/raw/main/Sans/OTF/SimplifiedChinese/NotoSansCJKsc-Regular.otf

# Verify
ls -lh src/updater/gui/fonts/NotoSansCJKsc-Regular.otf
```

---

### T003: Create GUI Directory Structure
- **Status**: ⏳ Pending
- **Priority**: P0 (Critical)
- **Estimated Time**: 0.25 hours
- **Assignee**: TBD

**Description**:
Create the GUI module directory structure.

**Acceptance Criteria**:
- [ ] Directory created: `src/updater/gui/`
- [ ] File created: `src/updater/gui/__init__.py`
- [ ] File created: `src/updater/gui/progress_window.py`
- [ ] File created: `src/updater/gui/renderer.py`
- [ ] File created: `src/updater/gui/launcher.py`

**Commands**:
```bash
mkdir -p src/updater/gui/fonts
touch src/updater/gui/__init__.py
touch src/updater/gui/progress_window.py
touch src/updater/gui/renderer.py
touch src/updater/gui/launcher.py
```

---

## Phase 1: GUI Foundation

### T004: Implement Renderer Class
- **Status**: ⏳ Pending
- **Priority**: P0 (Critical)
- **Estimated Time**: 4 hours
- **Assignee**: TBD
- **Dependencies**: T001, T002, T003

**Description**:
Implement the `Renderer` class in `renderer.py` for rendering text and progress bars.

**Acceptance Criteria**:
- [ ] `Renderer` class implemented (~100 lines)
- [ ] `__init__()` initializes SDL_ttf and loads fonts
- [ ] `render_progress()` renders message, progress bar, and percentage
- [ ] `_render_text()` renders centered UTF-8 text
- [ ] `_render_progress_bar()` renders filled/unfilled progress bar
- [ ] `cleanup()` properly releases resources
- [ ] Chinese text renders correctly
- [ ] Code follows project style guidelines

**Files**:
- `src/updater/gui/renderer.py` (new, ~100 lines)

**Testing**:
```bash
# Manual test (requires mock)
python -c "from updater.gui.renderer import Renderer; print('OK')"
```

---

### T005: Implement ProgressWindow Class
- **Status**: ⏳ Pending
- **Priority**: P0 (Critical)
- **Estimated Time**: 6 hours
- **Assignee**: TBD
- **Dependencies**: T004

**Description**:
Implement the `ProgressWindow` class in `progress_window.py` for the main GUI window.

**Acceptance Criteria**:
- [ ] `ProgressWindow` class implemented (~150 lines)
- [ ] `__init__()` initializes SDL
- [ ] `create_window()` creates full-screen window with ALWAYS_ON_TOP flag
- [ ] `fetch_progress()` polls `/api/v1.0/progress` endpoint
- [ ] `run()` implements main event loop with 500ms polling
- [ ] Auto-closes after 3 seconds when stage is "success" or "failed"
- [ ] `cleanup()` properly releases resources
- [ ] `main()` entry point for subprocess
- [ ] Error handling for network failures
- [ ] Code follows project style guidelines

**Files**:
- `src/updater/gui/progress_window.py` (new, ~150 lines)

**Testing**:
```bash
# Manual test (requires updater API running)
python -m updater.gui.progress_window
```

---

### T006: Test Renderer on Development Machine
- **Status**: ⏳ Pending
- **Priority**: P1 (High)
- **Estimated Time**: 2 hours
- **Assignee**: TBD
- **Dependencies**: T004

**Description**:
Create unit tests for the Renderer class (with mocked SDL2).

**Acceptance Criteria**:
- [ ] Test file created: `tests/unit/test_renderer.py`
- [ ] Test: Renderer initialization
- [ ] Test: Text rendering (mocked)
- [ ] Test: Progress bar rendering (mocked)
- [ ] Test: Cleanup
- [ ] All tests pass
- [ ] Code coverage > 80%

**Files**:
- `tests/unit/test_renderer.py` (new, ~80 lines)

**Testing**:
```bash
pytest tests/unit/test_renderer.py -v
```

---

### T007: Test ProgressWindow on Development Machine
- **Status**: ⏳ Pending
- **Priority**: P1 (High)
- **Estimated Time**: 2 hours
- **Assignee**: TBD
- **Dependencies**: T005

**Description**:
Create manual test script for ProgressWindow visual verification.

**Acceptance Criteria**:
- [ ] Test file created: `tests/manual/test_gui_display.py`
- [ ] Script simulates progress from 0% to 100%
- [ ] Chinese text displays correctly
- [ ] Progress bar animates smoothly
- [ ] Window is full-screen
- [ ] Window is on top

**Files**:
- `tests/manual/test_gui_display.py` (new, ~80 lines)

**Testing**:
```bash
python tests/manual/test_gui_display.py
```

---

## Phase 2: Process Management

### T008: Implement GUILauncher Class
- **Status**: ⏳ Pending
- **Priority**: P0 (Critical)
- **Estimated Time**: 3 hours
- **Assignee**: TBD
- **Dependencies**: T005

**Description**:
Implement the `GUILauncher` class in `launcher.py` for managing GUI subprocess.

**Acceptance Criteria**:
- [ ] `GUILauncher` class implemented (~80 lines)
- [ ] `start()` spawns GUI subprocess
- [ ] `stop()` terminates subprocess gracefully (with timeout)
- [ ] `is_running()` checks subprocess status
- [ ] `__del__()` ensures cleanup
- [ ] Proper logging for all operations
- [ ] Error handling for subprocess failures
- [ ] Code follows project style guidelines

**Files**:
- `src/updater/gui/launcher.py` (new, ~80 lines)

**Testing**:
```bash
python -c "from updater.gui.launcher import GUILauncher; print('OK')"
```

---

### T009: Test GUILauncher Unit Tests
- **Status**: ⏳ Pending
- **Priority**: P0 (Critical)
- **Estimated Time**: 2 hours
- **Assignee**: TBD
- **Dependencies**: T008

**Description**:
Create unit tests for the GUILauncher class.

**Acceptance Criteria**:
- [ ] Test file created: `tests/unit/test_gui_launcher.py`
- [ ] Test: Start subprocess
- [ ] Test: Stop subprocess
- [ ] Test: Double start (should fail)
- [ ] Test: Stop non-existent process
- [ ] Test: Timeout and force kill
- [ ] All tests pass
- [ ] Code coverage > 80%

**Files**:
- `tests/unit/test_gui_launcher.py` (new, ~100 lines)

**Testing**:
```bash
pytest tests/unit/test_gui_launcher.py -v
```

---

### T010: Test Process Lifecycle
- **Status**: ⏳ Pending
- **Priority**: P1 (High)
- **Estimated Time**: 1 hour
- **Assignee**: TBD
- **Dependencies**: T009

**Description**:
Manually test the full GUI process lifecycle.

**Acceptance Criteria**:
- [ ] GUI starts successfully
- [ ] GUI process appears in process list
- [ ] GUI stops gracefully
- [ ] No zombie processes left
- [ ] Logs show correct PID and status

**Testing**:
```bash
# Manual test
python -c "
from updater.gui.launcher import GUILauncher
import time

launcher = GUILauncher()
launcher.start()
time.sleep(5)
launcher.stop()
"
```

---

## Phase 3: Integration

### T011: Integrate GUI into Update API
- **Status**: ⏳ Pending
- **Priority**: P0 (Critical)
- **Estimated Time**: 2 hours
- **Assignee**: TBD
- **Dependencies**: T008

**Description**:
Modify `routes.py` to launch GUI when update is triggered.

**Acceptance Criteria**:
- [ ] Import `GUILauncher` in `routes.py`
- [ ] `post_update()` creates and starts GUILauncher
- [ ] GUILauncher passed to `_update_workflow()`
- [ ] `_update_workflow()` stops GUI in finally block
- [ ] Error handling if GUI fails to start
- [ ] Logging for GUI lifecycle events
- [ ] Code follows project style guidelines

**Files**:
- `src/updater/api/routes.py` (modified, +30 lines)

**Testing**:
```bash
# Start updater
uv run src/updater/main.py

# Trigger update
curl -X POST http://localhost:12315/api/v1.0/update \
  -H "Content-Type: application/json" \
  -d '{"version": "1.0.0"}'
```

---

### T012: Test GUI Integration
- **Status**: ⏳ Pending
- **Priority**: P0 (Critical)
- **Estimated Time**: 3 hours
- **Assignee**: TBD
- **Dependencies**: T011

**Description**:
Create integration tests for GUI lifecycle with update API.

**Acceptance Criteria**:
- [ ] Test file created: `tests/integration/test_gui_integration.py`
- [ ] Test: GUI starts when update triggered
- [ ] Test: GUI polls progress endpoint
- [ ] Test: GUI stops when update completes
- [ ] Test: GUI stops when update fails
- [ ] Test: Update continues if GUI fails to start
- [ ] All tests pass

**Files**:
- `tests/integration/test_gui_integration.py` (new, ~150 lines)

**Testing**:
```bash
pytest tests/integration/test_gui_integration.py -v
```

---

### T013: Update pyproject.toml Dependencies
- **Status**: ⏳ Pending
- **Priority**: P0 (Critical)
- **Estimated Time**: 0.25 hours
- **Assignee**: TBD
- **Dependencies**: T001

**Description**:
Ensure PySDL2 dependencies are properly documented in pyproject.toml.

**Acceptance Criteria**:
- [ ] `PySDL2>=0.9.16` in dependencies
- [ ] `PySDL2-dll>=2.28.0` in dependencies
- [ ] `uv sync` works
- [ ] Dependencies locked in `uv.lock`

**Files**:
- `pyproject.toml` (modified, +2 lines)

**Testing**:
```bash
uv sync
uv pip list | grep PySDL2
```

---

## Phase 4: Testing

### T014: Create Manual Test Suite
- **Status**: ⏳ Pending
- **Priority**: P1 (High)
- **Estimated Time**: 2 hours
- **Assignee**: TBD
- **Dependencies**: T011

**Description**:
Create comprehensive manual test scripts for GUI functionality.

**Acceptance Criteria**:
- [ ] Test: Full-screen display
- [ ] Test: Chinese text rendering
- [ ] Test: Progress bar animation
- [ ] Test: Auto-close behavior
- [ ] Test: Overlay on QT GUI (if available)
- [ ] Test: Different screen sizes

**Files**:
- `tests/manual/test_gui_fullscreen.py` (new)
- `tests/manual/test_gui_chinese.py` (new)
- `tests/manual/test_gui_overlay.py` (new)

---

### T015: Performance Testing
- **Status**: ⏳ Pending
- **Priority**: P1 (High)
- **Estimated Time**: 2 hours
- **Assignee**: TBD
- **Dependencies**: T011

**Description**:
Measure and verify GUI performance metrics.

**Acceptance Criteria**:
- [ ] Memory usage < 50MB
- [ ] CPU usage < 15% during rendering
- [ ] GUI launch time < 2 seconds
- [ ] No memory leaks over 10 minutes
- [ ] Performance report documented

**Testing**:
```bash
# Monitor memory
ps aux | grep progress_window

# Monitor CPU
top -p $(pgrep -f progress_window)
```

---

### T016: Test on Target Device
- **Status**: ⏳ Pending
- **Priority**: P0 (Critical)
- **Estimated Time**: 4 hours
- **Assignee**: TBD
- **Dependencies**: T011, T012

**Description**:
Deploy and test GUI on actual target device.

**Acceptance Criteria**:
- [ ] SDL2 libraries installed on device
- [ ] Updater deployed with GUI code
- [ ] Font file present on device
- [ ] GUI displays correctly
- [ ] GUI overlays QT interface
- [ ] Full update workflow works
- [ ] Performance metrics met

**Commands**:
```bash
# On target device
apt-get install libsdl2-2.0-0 libsdl2-ttf-2.0-0

# Deploy updater
# ... deployment steps ...

# Test
curl -X POST http://localhost:12315/api/v1.0/update \
  -H "Content-Type: application/json" \
  -d '{"version": "1.0.0"}'
```

---

### T017: Test Error Scenarios
- **Status**: ⏳ Pending
- **Priority**: P1 (High)
- **Estimated Time**: 2 hours
- **Assignee**: TBD
- **Dependencies**: T011

**Description**:
Test GUI behavior in error scenarios.

**Acceptance Criteria**:
- [ ] Test: SDL2 not installed
- [ ] Test: Font file missing
- [ ] Test: Progress API unreachable
- [ ] Test: GUI process killed externally
- [ ] Test: Update fails during deployment
- [ ] All errors handled gracefully
- [ ] Update continues despite GUI failures

---

### T018: Code Review and Cleanup
- **Status**: ⏳ Pending
- **Priority**: P1 (High)
- **Estimated Time**: 2 hours
- **Assignee**: TBD
- **Dependencies**: T004-T013

**Description**:
Review all GUI code for quality, style, and best practices.

**Acceptance Criteria**:
- [ ] Code follows project style guidelines
- [ ] All functions have docstrings
- [ ] Type hints added where appropriate
- [ ] No hardcoded values
- [ ] Proper error handling
- [ ] Logging at appropriate levels
- [ ] No console.log statements
- [ ] ruff check passes

**Commands**:
```bash
ruff check src/updater/gui/ --fix
ruff format src/updater/gui/
```

---

### T019: Test Coverage Report
- **Status**: ⏳ Pending
- **Priority**: P2 (Medium)
- **Estimated Time**: 1 hour
- **Assignee**: TBD
- **Dependencies**: T006, T009, T012

**Description**:
Generate and review test coverage report for GUI code.

**Acceptance Criteria**:
- [ ] Coverage report generated
- [ ] GUI code coverage > 80%
- [ ] Critical paths covered
- [ ] Coverage report documented

**Commands**:
```bash
pytest --cov=src/updater/gui --cov-report=html
open htmlcov/index.html
```

---

## Phase 5: Documentation

### T020: Update README
- **Status**: ⏳ Pending
- **Priority**: P2 (Medium)
- **Estimated Time**: 1 hour
- **Assignee**: TBD
- **Dependencies**: T016

**Description**:
Add GUI section to README.md.

**Acceptance Criteria**:
- [ ] GUI feature described
- [ ] Requirements listed
- [ ] Usage instructions provided
- [ ] Troubleshooting section added
- [ ] Screenshots/examples included (optional)

**Files**:
- `README.md` (modified, +30 lines)

---

### T021: Create GUI Documentation
- **Status**: ⏳ Pending
- **Priority**: P2 (Medium)
- **Estimated Time**: 2 hours
- **Assignee**: TBD
- **Dependencies**: T016

**Description**:
Create comprehensive GUI documentation.

**Acceptance Criteria**:
- [ ] Architecture overview
- [ ] Configuration options
- [ ] Troubleshooting guide
- [ ] Development guide
- [ ] API reference

**Files**:
- `docs/GUI.md` (new, ~300 lines)

---

### T022: Update CLAUDE.md
- **Status**: ⏳ Pending
- **Priority**: P2 (Medium)
- **Estimated Time**: 0.5 hours
- **Assignee**: TBD
- **Dependencies**: T020, T021

**Description**:
Update CLAUDE.md to reflect GUI feature completion.

**Acceptance Criteria**:
- [ ] GUI feature added to "Completed" section
- [ ] Project structure updated
- [ ] Recent changes documented
- [ ] Known limitations updated (if any)

**Files**:
- `CLAUDE.md` (modified, +20 lines)

---

## Progress Tracking

### Summary
- **Total Tasks**: 22
- **Completed**: 0
- **In Progress**: 0
- **Pending**: 22
- **Blocked**: 0

### By Phase
- **Phase 0 (Setup)**: 0/3 completed
- **Phase 1 (Foundation)**: 0/4 completed
- **Phase 2 (Process Mgmt)**: 0/3 completed
- **Phase 3 (Integration)**: 0/3 completed
- **Phase 4 (Testing)**: 0/6 completed
- **Phase 5 (Documentation)**: 0/3 completed

### By Priority
- **P0 (Critical)**: 0/11 completed
- **P1 (High)**: 0/8 completed
- **P2 (Medium)**: 0/3 completed

---

## Risk Register

### Risk 1: SDL2 Compatibility Issues
- **Likelihood**: Medium
- **Impact**: High
- **Mitigation**: Test on target device early (T016)
- **Contingency**: Prepare Tkinter fallback

### Risk 2: Font Rendering Problems
- **Likelihood**: Low
- **Impact**: Medium
- **Mitigation**: Test Chinese rendering early (T007)
- **Contingency**: Use alternative font or ASCII-only

### Risk 3: GUI Cannot Overlay QT
- **Likelihood**: Low
- **Impact**: High
- **Mitigation**: Test window layering (T016)
- **Contingency**: Stop QT before showing GUI

### Risk 4: Performance Issues
- **Likelihood**: Low
- **Impact**: Medium
- **Mitigation**: Performance testing (T015)
- **Contingency**: Optimize rendering or reduce update frequency

---

## Notes

### Design Decisions
- **PySDL2 over Tkinter**: Better control, no X11 dependency
- **Subprocess model**: Isolates GUI failures from updater
- **500ms polling**: Balance between responsiveness and overhead
- **3-second final display**: Gives user time to see result

### Future Enhancements
- Animated progress bar
- Custom branding/logo
- Multi-language support
- Touch input support
- Cancel button

---

**Document Status**: ✅ Ready for Implementation
**Next Action**: Start with Phase 0 tasks (T001-T003)
