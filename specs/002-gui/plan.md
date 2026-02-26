# TOP.E OTA Updater - GUI Implementation Plan

**Feature**: 002-gui
**Status**: Planning
**Created**: 2026-01-29
**Estimated Duration**: 5-7 days

---

## Overview

This plan outlines the implementation of a lightweight GUI for displaying OTA update progress. The GUI will use PySDL2 to create a full-screen overlay that displays real-time progress information.

---

## Prerequisites

### Dependencies
```toml
# Add to pyproject.toml
[project]
dependencies = [
    # ... existing dependencies ...
    "PySDL2>=0.9.16",
    "PySDL2-dll>=2.28.0",  # Includes SDL2 binaries
]
```

### Font Asset
- Download Noto Sans CJK SC font (~5MB)
- Place in `src/updater/gui/fonts/`

### System Libraries (Target Device)
```bash
apt-get install libsdl2-2.0-0 libsdl2-ttf-2.0-0
```

---

## Phase 1: GUI Foundation (1-2 days)

### 1.1 Create Directory Structure

```bash
mkdir -p src/updater/gui/fonts
touch src/updater/gui/__init__.py
touch src/updater/gui/progress_window.py
touch src/updater/gui/renderer.py
touch src/updater/gui/launcher.py
```

### 1.2 Download and Bundle Font

```bash
# Download Noto Sans CJK SC
wget -O src/updater/gui/fonts/NotoSansCJKsc-Regular.otf \
  https://github.com/googlefonts/noto-cjk/raw/main/Sans/OTF/SimplifiedChinese/NotoSansCJKsc-Regular.otf
```

### 1.3 Implement Renderer (`renderer.py`)

**File**: `src/updater/gui/renderer.py` (~100 lines)

**Key Components**:
- `Renderer` class
- `render_progress(surface, message, progress)` method
- Text rendering with Chinese support
- Progress bar rendering

**Code Structure**:
```python
import sdl2
import sdl2.ext
import sdl2.sdlttf as sdlttf
from pathlib import Path

class Renderer:
    def __init__(self, screen_width: int, screen_height: int):
        """Initialize renderer with screen dimensions"""
        self.screen_width = screen_width
        self.screen_height = screen_height

        # Initialize SDL_ttf
        if sdlttf.TTF_Init() == -1:
            raise RuntimeError("Failed to initialize SDL_ttf")

        # Load font
        font_path = Path(__file__).parent / "fonts" / "NotoSansCJKsc-Regular.otf"
        self.font_large = sdlttf.TTF_OpenFont(str(font_path).encode(), 32)
        self.font_small = sdlttf.TTF_OpenFont(str(font_path).encode(), 24)

        if not self.font_large or not self.font_small:
            raise RuntimeError("Failed to load font")

    def render_progress(self, surface, message: str, progress: int):
        """Render progress UI"""
        # Clear screen (black background)
        sdl2.ext.fill(surface, sdl2.ext.Color(0, 0, 0))

        # Render message text (centered, top third)
        self._render_text(surface, message, self.font_large,
                         self.screen_height // 3)

        # Render progress bar (centered, middle)
        self._render_progress_bar(surface, progress,
                                  self.screen_height // 2)

        # Render percentage (centered, below bar)
        percent_text = f"{progress}%"
        self._render_text(surface, percent_text, self.font_small,
                         self.screen_height // 2 + 60)

    def _render_text(self, surface, text: str, font, y_pos: int):
        """Render centered text"""
        # Create text surface
        color = sdl2.SDL_Color(255, 255, 255)  # White
        text_surface = sdlttf.TTF_RenderUTF8_Blended(
            font, text.encode('utf-8'), color
        )

        if not text_surface:
            return

        # Calculate centered position
        text_rect = text_surface.contents.clip_rect
        x_pos = (self.screen_width - text_rect.w) // 2

        # Blit to screen
        dest_rect = sdl2.SDL_Rect(x_pos, y_pos, text_rect.w, text_rect.h)
        sdl2.SDL_BlitSurface(text_surface, None, surface, dest_rect)
        sdl2.SDL_FreeSurface(text_surface)

    def _render_progress_bar(self, surface, progress: int, y_pos: int):
        """Render progress bar"""
        bar_width = int(self.screen_width * 0.6)
        bar_height = 30
        x_pos = (self.screen_width - bar_width) // 2

        # Background (dark gray)
        bg_rect = sdl2.SDL_Rect(x_pos, y_pos, bar_width, bar_height)
        sdl2.ext.fill(surface, sdl2.ext.Color(51, 51, 51), bg_rect)

        # Filled portion (green)
        filled_width = int(bar_width * progress / 100)
        if filled_width > 0:
            fill_rect = sdl2.SDL_Rect(x_pos, y_pos, filled_width, bar_height)
            sdl2.ext.fill(surface, sdl2.ext.Color(0, 255, 0), fill_rect)

    def cleanup(self):
        """Clean up resources"""
        if self.font_large:
            sdlttf.TTF_CloseFont(self.font_large)
        if self.font_small:
            sdlttf.TTF_CloseFont(self.font_small)
        sdlttf.TTF_Quit()
```

**Testing**:
```bash
# Unit test (mocked SDL2)
pytest tests/unit/test_renderer.py -v
```

### 1.4 Implement Progress Window (`progress_window.py`)

**File**: `src/updater/gui/progress_window.py` (~150 lines)

**Key Components**:
- `ProgressWindow` class
- Full-screen window creation
- Event loop
- Progress polling from `/api/v1.0/progress`

**Code Structure**:
```python
import sdl2
import sdl2.ext
import time
import httpx
from typing import Dict, Any
from .renderer import Renderer

class ProgressWindow:
    def __init__(self, updater_url: str = "http://localhost:12315"):
        """Initialize progress window"""
        self.updater_url = updater_url
        self.running = False
        self.window = None
        self.renderer = None

        # Initialize SDL
        if sdl2.SDL_Init(sdl2.SDL_INIT_VIDEO) != 0:
            raise RuntimeError(f"SDL_Init failed: {sdl2.SDL_GetError()}")

    def create_window(self):
        """Create full-screen window"""
        # Get display mode
        display_mode = sdl2.SDL_DisplayMode()
        if sdl2.SDL_GetCurrentDisplayMode(0, display_mode) != 0:
            raise RuntimeError("Failed to get display mode")

        # Create window
        self.window = sdl2.SDL_CreateWindow(
            b"OTA Update",
            sdl2.SDL_WINDOWPOS_CENTERED,
            sdl2.SDL_WINDOWPOS_CENTERED,
            display_mode.w,
            display_mode.h,
            sdl2.SDL_WINDOW_FULLSCREEN_DESKTOP | sdl2.SDL_WINDOW_ALWAYS_ON_TOP
        )

        if not self.window:
            raise RuntimeError("Failed to create window")

        # Create renderer
        screen_surface = sdl2.SDL_GetWindowSurface(self.window)
        self.renderer = Renderer(display_mode.w, display_mode.h)

    def fetch_progress(self) -> Dict[str, Any]:
        """Fetch progress from updater API"""
        try:
            response = httpx.get(
                f"{self.updater_url}/api/v1.0/progress",
                timeout=2.0
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            # Return error state
            return {
                "stage": "failed",
                "progress": 0,
                "message": "连接失败",
                "error": str(e)
            }

    def run(self):
        """Main event loop"""
        self.running = True
        last_poll = time.time()
        current_data = {
            "stage": "idle",
            "progress": 0,
            "message": "正在初始化..."
        }

        while self.running:
            # Process events
            event = sdl2.SDL_Event()
            while sdl2.SDL_PollEvent(event) != 0:
                if event.type == sdl2.SDL_QUIT:
                    self.running = False

            # Poll progress every 500ms
            now = time.time()
            if now - last_poll >= 0.5:
                current_data = self.fetch_progress()
                last_poll = now

            # Render
            surface = sdl2.SDL_GetWindowSurface(self.window)
            self.renderer.render_progress(
                surface,
                current_data.get("message", ""),
                current_data.get("progress", 0)
            )
            sdl2.SDL_UpdateWindowSurface(self.window)

            # Check if update completed
            stage = current_data.get("stage")
            if stage in ["success", "failed"]:
                # Display final status for 3 seconds
                time.sleep(3)
                self.running = False

            # Small delay to reduce CPU usage
            sdl2.SDL_Delay(50)

    def cleanup(self):
        """Clean up resources"""
        if self.renderer:
            self.renderer.cleanup()
        if self.window:
            sdl2.SDL_DestroyWindow(self.window)
        sdl2.SDL_Quit()

def main():
    """Entry point for GUI subprocess"""
    window = None
    try:
        window = ProgressWindow()
        window.create_window()
        window.run()
    except Exception as e:
        print(f"GUI Error: {e}")
    finally:
        if window:
            window.cleanup()

if __name__ == "__main__":
    main()
```

**Testing**:
```bash
# Manual test (requires SDL2)
python -m updater.gui.progress_window
```

---

## Phase 2: Process Management (1 day)

### 2.1 Implement GUI Launcher (`launcher.py`)

**File**: `src/updater/gui/launcher.py` (~80 lines)

**Key Components**:
- `GUILauncher` class
- Subprocess spawning
- Process termination
- Error handling

**Code Structure**:
```python
import subprocess
import sys
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

class GUILauncher:
    """Manages GUI subprocess lifecycle"""

    def __init__(self):
        self.process: Optional[subprocess.Popen] = None

    def start(self) -> bool:
        """
        Start GUI subprocess

        Returns:
            True if started successfully, False otherwise
        """
        if self.process is not None:
            logger.warning("GUI process already running")
            return False

        try:
            # Launch GUI as subprocess
            self.process = subprocess.Popen(
                [sys.executable, "-m", "updater.gui.progress_window"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=Path(__file__).parent.parent.parent
            )

            logger.info(f"GUI process started (PID: {self.process.pid})")
            return True

        except Exception as e:
            logger.error(f"Failed to start GUI: {e}")
            self.process = None
            return False

    def stop(self, timeout: int = 5) -> bool:
        """
        Stop GUI subprocess

        Args:
            timeout: Seconds to wait for graceful termination

        Returns:
            True if stopped successfully, False otherwise
        """
        if self.process is None:
            logger.warning("No GUI process to stop")
            return False

        try:
            # Try graceful termination
            self.process.terminate()

            try:
                self.process.wait(timeout=timeout)
                logger.info("GUI process terminated gracefully")
            except subprocess.TimeoutExpired:
                # Force kill if timeout
                logger.warning("GUI process did not terminate, forcing kill")
                self.process.kill()
                self.process.wait()

            # Log output
            stdout, stderr = self.process.communicate(timeout=1)
            if stdout:
                logger.debug(f"GUI stdout: {stdout.decode()}")
            if stderr:
                logger.warning(f"GUI stderr: {stderr.decode()}")

            self.process = None
            return True

        except Exception as e:
            logger.error(f"Failed to stop GUI: {e}")
            return False

    def is_running(self) -> bool:
        """Check if GUI process is running"""
        if self.process is None:
            return False
        return self.process.poll() is None

    def __del__(self):
        """Ensure process is cleaned up"""
        if self.process and self.is_running():
            self.stop()
```

**Testing**:
```bash
# Unit test
pytest tests/unit/test_gui_launcher.py -v
```

---

## Phase 3: Integration (1 day)

### 3.1 Modify Update API (`routes.py`)

**File**: `src/updater/api/routes.py`

**Changes** (+30 lines):

```python
# Add import at top
from updater.gui.launcher import GUILauncher

# Modify post_update endpoint
@router.post("/update")
async def post_update(request: UpdateRequest, background_tasks: BackgroundTasks):
    """Trigger OTA update"""

    # ... existing validation logic ...

    # Start GUI (NEW)
    gui_launcher = GUILauncher()
    gui_started = gui_launcher.start()

    if not gui_started:
        logger.warning("Failed to start GUI, continuing without visual feedback")

    # Start update workflow
    background_tasks.add_task(
        _update_workflow,
        request.version,
        gui_launcher  # Pass launcher to workflow
    )

    return SuccessResponse(message="Update started")

# Modify _update_workflow
async def _update_workflow(version: str, gui_launcher: GUILauncher):
    """Background update workflow"""
    try:
        # ... existing download and deploy logic ...

        await deploy_service.deploy_package(package_path, version)

    except Exception as e:
        logger.error(f"Update failed: {e}")
        # ... existing error handling ...

    finally:
        # Stop GUI (NEW)
        if gui_launcher.is_running():
            gui_launcher.stop()
            logger.info("GUI stopped")
```

**Testing**:
```bash
# Integration test
pytest tests/integration/test_gui_integration.py -v
```

### 3.2 Update Dependencies (`pyproject.toml`)

**File**: `pyproject.toml`

**Changes** (+2 lines):

```toml
[project]
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn>=0.32.0",
    "httpx>=0.27.0",
    "aiofiles>=24.1.0",
    "PySDL2>=0.9.16",        # NEW
    "PySDL2-dll>=2.28.0",    # NEW
]
```

**Install**:
```bash
uv sync
```

---

## Phase 4: Testing (1-2 days)

### 4.1 Unit Tests

**File**: `tests/unit/test_gui_launcher.py`

```python
import pytest
from updater.gui.launcher import GUILauncher

def test_launcher_start():
    """Test GUI launcher starts process"""
    launcher = GUILauncher()
    assert launcher.start()
    assert launcher.is_running()
    launcher.stop()

def test_launcher_stop():
    """Test GUI launcher stops process"""
    launcher = GUILauncher()
    launcher.start()
    assert launcher.stop()
    assert not launcher.is_running()

def test_launcher_double_start():
    """Test starting already running process"""
    launcher = GUILauncher()
    launcher.start()
    assert not launcher.start()  # Should return False
    launcher.stop()
```

### 4.2 Integration Tests

**File**: `tests/integration/test_gui_integration.py`

```python
import pytest
import httpx
from updater.gui.launcher import GUILauncher

@pytest.mark.asyncio
async def test_gui_lifecycle():
    """Test full GUI lifecycle"""
    launcher = GUILauncher()

    # Start GUI
    assert launcher.start()

    # Wait for GUI to initialize
    await asyncio.sleep(2)

    # Verify GUI is polling progress
    # (This requires updater API to be running)

    # Stop GUI
    assert launcher.stop()

@pytest.mark.asyncio
async def test_update_with_gui(test_client):
    """Test update endpoint starts GUI"""
    response = await test_client.post(
        "/api/v1.0/update",
        json={"version": "1.0.0"}
    )

    assert response.status_code == 200

    # Verify GUI process started
    # (Check process list or logs)
```

### 4.3 Manual Tests

**File**: `tests/manual/test_gui_display.py`

```python
"""
Manual test script for GUI display

Run on target device to verify:
- Full-screen display
- Chinese text rendering
- Progress bar animation
- Auto-close behavior
"""

import time
from updater.gui.progress_window import ProgressWindow

def test_gui_display():
    """Test GUI display manually"""
    window = ProgressWindow()

    try:
        window.create_window()

        # Simulate progress updates
        for i in range(0, 101, 5):
            window.renderer.render_progress(
                window.window.get_surface(),
                f"正在升级系统... ({i}%)",
                i
            )
            window.window.refresh()
            time.sleep(0.5)

        print("Test completed successfully")

    finally:
        window.cleanup()

if __name__ == "__main__":
    test_gui_display()
```

---

## Phase 5: Documentation (0.5 day)

### 5.1 Update README

Add GUI section to `README.md`:

```markdown
## GUI Feature

The updater includes a lightweight GUI for displaying update progress.

### Requirements
- SDL2 libraries: `libsdl2-2.0-0`, `libsdl2-ttf-2.0-0`
- Python packages: `PySDL2`, `PySDL2-dll`

### Usage
GUI automatically launches when update is triggered via `/api/v1.0/update`.

### Troubleshooting
- If GUI doesn't appear, check SDL2 installation
- Check logs at `logs/updater.log` for errors
- GUI failure does not affect update process
```

### 5.2 Create GUI Documentation

**File**: `docs/GUI.md`

Document:
- Architecture overview
- Configuration options
- Troubleshooting guide
- Development guide

---

## Deployment Checklist

### Development Environment
- [ ] Install PySDL2: `uv sync`
- [ ] Download font to `src/updater/gui/fonts/`
- [ ] Test GUI launch: `python -m updater.gui.progress_window`
- [ ] Run unit tests: `pytest tests/unit/test_gui_launcher.py -v`
- [ ] Run integration tests: `pytest tests/integration/test_gui_integration.py -v`

### Target Device
- [ ] Install SDL2: `apt-get install libsdl2-2.0-0 libsdl2-ttf-2.0-0`
- [ ] Deploy updater with GUI code
- [ ] Verify font file exists
- [ ] Test GUI display manually
- [ ] Test full update workflow with GUI
- [ ] Verify memory usage < 50MB
- [ ] Verify GUI overlays QT interface

---

## Success Criteria

### Functional
- ✅ GUI launches when update triggered
- ✅ Progress updates in real-time (500ms)
- ✅ Chinese text displays correctly
- ✅ Progress bar animates smoothly
- ✅ GUI closes automatically after update
- ✅ GUI overlays existing QT interface

### Non-Functional
- ✅ Memory usage < 50MB
- ✅ CPU usage < 15% during rendering
- ✅ GUI launch time < 2 seconds
- ✅ No impact on update process if GUI fails

### Testing
- ✅ All unit tests pass
- ✅ All integration tests pass
- ✅ Manual tests pass on target device
- ✅ Performance benchmarks met

---

## Rollback Plan

If GUI implementation causes issues:

1. **Disable GUI**: Comment out GUI launcher code in `routes.py`
2. **Remove dependencies**: Remove PySDL2 from `pyproject.toml`
3. **Revert commits**: `git revert <commit-hash>`
4. **Redeploy**: Deploy without GUI feature

GUI is designed to be non-critical - updater continues to function even if GUI fails.

---

## Timeline

| Phase | Duration | Dependencies |
|-------|----------|--------------|
| Phase 1: GUI Foundation | 1-2 days | Font download |
| Phase 2: Process Management | 1 day | Phase 1 |
| Phase 3: Integration | 1 day | Phase 1, 2 |
| Phase 4: Testing | 1-2 days | Phase 1, 2, 3 |
| Phase 5: Documentation | 0.5 day | Phase 4 |

**Total**: 5-7 days

---

## Next Steps

1. ✅ Review and approve this plan
2. ⏳ Install dependencies and download font
3. ⏳ Implement Phase 1 (GUI Foundation)
4. ⏳ Implement Phase 2 (Process Management)
5. ⏳ Implement Phase 3 (Integration)
6. ⏳ Execute Phase 4 (Testing)
7. ⏳ Complete Phase 5 (Documentation)
8. ⏳ Deploy to target device

---

**Plan Status**: ✅ Ready for Implementation
**Approval Required**: Yes
**Risk Level**: Low (GUI is non-critical feature)
