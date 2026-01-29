# TOP.E OTA Updater - GUI Feature Specification

**Feature ID**: 002-gui
**Status**: Draft
**Created**: 2026-01-29
**Last Updated**: 2026-01-29

---

## 1. Overview

### 1.1 Purpose
Add a lightweight GUI to display OTA update progress during system upgrades. The GUI must overlay the existing QT-based device interface and provide real-time visual feedback to users.

### 1.2 Background
- Phase 1-2 completed: Reporter integration + Version snapshot architecture
- Device uses full-screen QT GUI as primary interface
- OTA updater needs to display progress during upgrades
- Embedded Linux environment with minimal dependencies

### 1.3 Goals
- ✅ Minimal dependencies (< 10MB total)
- ✅ Full-screen overlay on existing QT GUI
- ✅ Real-time progress display (text + percentage)
- ✅ Auto-adaptive to screen sizes
- ✅ Top-level window (always visible)
- ✅ Automatic lifecycle management

---

## 2. Requirements

### 2.1 Functional Requirements

#### FR-001: GUI Activation
- **Trigger**: POST `/api/v1.0/update` endpoint called
- **Behavior**: GUI launches immediately, overlays existing interface
- **Priority**: P0 (Critical)

#### FR-002: Progress Display
- **Content**:
  - Text message (e.g., "正在升级系统...")
  - Progress bar (visual indicator)
  - Percentage (e.g., "45%")
- **Update Frequency**: Every 500ms
- **Priority**: P0 (Critical)

#### FR-003: Progress Polling
- **Source**: GET `/api/v1.0/progress` endpoint
- **Frequency**: 500ms intervals
- **Data**: Stage, progress percentage, message
- **Priority**: P0 (Critical)

#### FR-004: Auto-Close
- **Trigger**: Update completes (success/failed)
- **Behavior**: Display final status for 3 seconds, then close
- **Priority**: P0 (Critical)

#### FR-005: Chinese Language Support
- **Requirement**: Display Chinese text correctly
- **Solution**: Bundle Noto Sans CJK SC font
- **Priority**: P0 (Critical)

### 2.2 Non-Functional Requirements

#### NFR-001: Performance
- **GUI Launch Time**: < 2 seconds
- **Memory Usage**: < 50MB
- **CPU Usage**: < 5% (idle), < 15% (rendering)
- **Priority**: P0 (Critical)

#### NFR-002: Reliability
- **GUI Crash**: Must not affect updater process
- **Process Isolation**: GUI runs as separate subprocess
- **Error Handling**: All exceptions logged, graceful degradation
- **Priority**: P0 (Critical)

#### NFR-003: Compatibility
- **Platform**: Embedded Linux (ARM/x86)
- **Display**: Framebuffer or X11
- **Screen Sizes**: 800x480 to 1920x1080
- **Priority**: P1 (High)

#### NFR-004: Dependencies
- **Total Size**: < 10MB (SDL2 + font)
- **External Dependencies**: SDL2, SDL2_ttf
- **Python Dependencies**: PySDL2, PySDL2-dll
- **Priority**: P1 (High)

---

## 3. Technical Design

### 3.1 Technology Stack

#### Selected: PySDL2
- **Library**: SDL2 (Simple DirectMedia Layer)
- **Python Binding**: PySDL2
- **Size**: ~5MB (SDL2) + ~5MB (font) = ~10MB total
- **Advantages**:
  - ✅ Lightweight and fast
  - ✅ No X11 dependency (framebuffer support)
  - ✅ Native full-screen and window management
  - ✅ Cross-platform (Linux/Windows/macOS)
  - ✅ Mature and stable

#### Alternative Considered: Tkinter
- **Pros**: Built into Python, no extra dependencies
- **Cons**: Requires X11, less control over window layering
- **Decision**: Rejected due to X11 requirement

### 3.2 Architecture

```
┌─────────────────────────────────────────────────┐
│  Updater Main Process (FastAPI)                 │
│  ├─ POST /api/v1.0/update (trigger)             │
│  ├─ GET /api/v1.0/progress (data source)        │
│  └─ Background Task (deployment)                │
└─────────────────────────────────────────────────┘
                    │
                    ├─ spawn ──────────┐
                    │                   ↓
                    │    ┌──────────────────────────┐
                    │    │  GUI Subprocess (PySDL2)  │
                    │    │  ├─ Full-screen window    │
                    │    │  ├─ Poll progress (500ms) │
                    │    │  └─ Render UI             │
                    │    └──────────────────────────┘
                    │                   │
                    └─ poll ────────────┘
                         HTTP GET /api/v1.0/progress
```

### 3.3 Component Structure

```
src/updater/
├── gui/
│   ├── __init__.py
│   ├── fonts/
│   │   └── NotoSansCJKsc-Regular.otf    # ~5MB
│   ├── progress_window.py               # Main window (~150 lines)
│   ├── renderer.py                      # Rendering engine (~100 lines)
│   └── launcher.py                      # Process manager (~80 lines)
├── api/
│   └── routes.py                        # Modified: +30 lines
└── services/
    └── deploy.py                        # Modified: +10 lines
```

### 3.4 UI Design

```
┌─────────────────────────────────────────────────┐
│                                                 │
│                                                 │
│                                                 │
│              正在升级系统...                     │
│                                                 │
│         ████████████████░░░░░░░░░░              │
│                   45%                           │
│                                                 │
│                                                 │
│                                                 │
└─────────────────────────────────────────────────┘

Colors:
- Background: Black (#000000)
- Text: White (#FFFFFF)
- Progress Bar (filled): Green (#00FF00)
- Progress Bar (empty): Dark Gray (#333333)

Layout:
- Text: Centered, 32px font
- Progress Bar: 60% screen width, centered
- Percentage: Below progress bar, 24px font
```

---

## 4. Implementation Plan

### Phase 1: GUI Foundation (1-2 days)
- **Files**: `progress_window.py`, `renderer.py`
- **Tasks**:
  - Create full-screen window with SDL2
  - Implement text rendering (Chinese support)
  - Implement progress bar rendering
  - Test on development machine

### Phase 2: Process Management (1 day)
- **Files**: `launcher.py`
- **Tasks**:
  - Implement subprocess spawning
  - Implement process termination
  - Add error handling and logging

### Phase 3: Integration (1 day)
- **Files**: `routes.py`, `deploy.py`
- **Tasks**:
  - Modify `/api/v1.0/update` to launch GUI
  - Modify deployment workflow to stop GUI
  - Add GUI lifecycle management

### Phase 4: Progress Polling (1 day)
- **Files**: `progress_window.py`
- **Tasks**:
  - Implement HTTP polling (500ms interval)
  - Parse progress data
  - Update UI in real-time
  - Handle completion/failure states

### Phase 5: Testing & Debugging (1-2 days)
- **Tasks**:
  - Unit tests for launcher
  - Integration tests for GUI lifecycle
  - Manual testing on target device
  - Performance profiling

**Total Estimate**: 5-7 days

---

## 5. Data Flow

### 5.1 GUI Lifecycle

```
1. User triggers update
   POST /api/v1.0/update
   ↓
2. Updater validates request
   ↓
3. Updater spawns GUI subprocess
   GUILauncher.start()
   ↓
4. GUI creates full-screen window
   SDL_CreateWindow(FULLSCREEN | ALWAYS_ON_TOP)
   ↓
5. GUI enters polling loop
   Every 500ms: GET /api/v1.0/progress
   ↓
6. GUI renders progress
   Renderer.render_progress(message, percentage)
   ↓
7. Update completes
   Stage = "success" or "failed"
   ↓
8. GUI displays final status (3 seconds)
   ↓
9. GUI closes
   SDL_DestroyWindow()
   ↓
10. Updater terminates GUI subprocess
    GUILauncher.stop()
```

### 5.2 Progress Data Format

```json
{
  "stage": "downloading",
  "progress": 45,
  "message": "正在下载更新包...",
  "error": null
}
```

**Stages**:
- `idle`: No update in progress
- `downloading`: Downloading package
- `verifying`: Verifying package integrity
- `deploying`: Deploying update
- `success`: Update completed successfully
- `failed`: Update failed

---

## 6. Error Handling

### 6.1 GUI Crash
- **Detection**: Process exit code != 0
- **Action**: Log error, continue update process
- **Impact**: User loses visual feedback, but update continues

### 6.2 Progress Polling Failure
- **Detection**: HTTP request timeout or error
- **Action**: Retry 3 times, then display "连接失败"
- **Impact**: GUI shows stale data

### 6.3 SDL2 Initialization Failure
- **Detection**: SDL_Init() returns error
- **Action**: Log error, exit GUI process gracefully
- **Impact**: No GUI displayed, update continues

### 6.4 Font Loading Failure
- **Detection**: TTF_OpenFont() returns NULL
- **Action**: Fall back to built-in font or exit
- **Impact**: No text displayed or no GUI

---

## 7. Testing Strategy

### 7.1 Unit Tests
- `test_gui_launcher.py`: Process management
- `test_renderer.py`: Rendering logic (mocked SDL2)

### 7.2 Integration Tests
- `test_gui_integration.py`: Full lifecycle test
- `test_progress_polling.py`: HTTP polling test

### 7.3 Manual Tests
- `test_gui_display.py`: Visual verification on device
- `test_screen_sizes.py`: Test on different resolutions
- `test_overlay.py`: Verify overlay on QT GUI

### 7.4 Performance Tests
- Memory usage profiling
- CPU usage monitoring
- Launch time measurement

---

## 8. Deployment

### 8.1 Dependencies Installation

```bash
# On target device
apt-get install libsdl2-2.0-0 libsdl2-ttf-2.0-0

# Python dependencies (via uv)
uv sync
```

### 8.2 Font Bundling

```bash
# Download Noto Sans CJK SC
wget https://github.com/googlefonts/noto-cjk/raw/main/Sans/OTF/SimplifiedChinese/NotoSansCJKsc-Regular.otf

# Place in src/updater/gui/fonts/
cp NotoSansCJKsc-Regular.otf src/updater/gui/fonts/
```

### 8.3 Verification

```bash
# Test SDL2
python -c "import sdl2; print('SDL2 OK')"

# Test GUI launch
python -m updater.gui.progress_window
```

---

## 9. Risks & Mitigations

### Risk 1: SDL2 Compatibility on Embedded Linux
- **Likelihood**: Medium
- **Impact**: High (no GUI)
- **Mitigation**: Test on target device early, prepare Tkinter fallback

### Risk 2: GUI Cannot Overlay QT GUI
- **Likelihood**: Low
- **Impact**: High (GUI not visible)
- **Mitigation**: Use `SDL_WINDOW_ALWAYS_ON_TOP`, test window layering

### Risk 3: Font Rendering Issues
- **Likelihood**: Low
- **Impact**: Medium (text not readable)
- **Mitigation**: Bundle font, test Chinese rendering early

### Risk 4: Process Management Complexity
- **Likelihood**: Medium
- **Impact**: Medium (zombie processes)
- **Mitigation**: Proper subprocess cleanup, timeout mechanisms

---

## 10. Success Criteria

### Must Have (P0)
- ✅ GUI displays during update
- ✅ Progress updates in real-time
- ✅ Chinese text renders correctly
- ✅ GUI closes automatically after update
- ✅ Memory usage < 50MB

### Should Have (P1)
- ✅ GUI overlays QT interface
- ✅ Adaptive to screen sizes
- ✅ Graceful error handling

### Nice to Have (P2)
- ⏸️ Animated progress bar
- ⏸️ Custom branding/logo
- ⏸️ Sound effects

---

## 11. Future Enhancements

### Phase 2 (Optional)
- Add logo/branding
- Animated transitions
- Multi-language support (English, etc.)
- Customizable themes

### Phase 3 (Optional)
- Touch input support
- Cancel button (with confirmation)
- Detailed error messages

---

## 12. References

- [SDL2 Documentation](https://wiki.libsdl.org/)
- [PySDL2 Documentation](https://pysdl2.readthedocs.io/)
- [Noto CJK Fonts](https://github.com/googlefonts/noto-cjk)
- [TOP.E Updater Core Spec](../001-updater-core/spec.md)

---

**Document Status**: ✅ Ready for Review
**Next Steps**: Create implementation plan (plan.md)
