# TOP.E OTA Updater - GUI 实施计划

**功能**: 002-gui
**状态**: 规划中
**创建日期**: 2026-01-29
**预计工期**: 5-7 天

---

## 概述

本计划概述了用于显示 OTA 更新进度的轻量级 GUI 的实施。GUI 将使用 PySDL2 创建全屏覆盖层，显示实时进度信息。

---

## 前置条件

### 依赖
```toml
# 添加到 pyproject.toml
[project]
dependencies = [
    # ... 现有依赖 ...
    "PySDL2>=0.9.16",
    "PySDL2-dll>=2.28.0",  # 包含 SDL2 二进制文件
]
```

### 字体资源
- 下载 Noto Sans CJK SC 字体（~5MB）
- 放置到 `src/updater/gui/fonts/`

### 系统库（目标设备）
```bash
apt-get install libsdl2-2.0-0 libsdl2-ttf-2.0-0
```

---

## Phase 1: GUI 基础框架（1-2 天）

### 1.1 创建目录结构

```bash
mkdir -p src/updater/gui/fonts
touch src/updater/gui/__init__.py
touch src/updater/gui/progress_window.py
touch src/updater/gui/renderer.py
touch src/updater/gui/launcher.py
```

### 1.2 下载并打包字体

```bash
# 下载 Noto Sans CJK SC
wget -O src/updater/gui/fonts/NotoSansCJKsc-Regular.otf \
  https://github.com/googlefonts/noto-cjk/raw/main/Sans/OTF/SimplifiedChinese/NotoSansCJKsc-Regular.otf
```

### 1.3 实现渲染器（`renderer.py`）

**文件**: `src/updater/gui/renderer.py`（~100 行）

**关键组件**:
- `Renderer` 类
- `render_progress(surface, message, progress)` 方法
- 支持中文的文字渲染
- 进度条渲染

**代码结构**:
```python
import sdl2
import sdl2.ext
import sdl2.sdlttf as sdlttf
from pathlib import Path

class Renderer:
    def __init__(self, screen_width: int, screen_height: int):
        """使用屏幕尺寸初始化渲染器"""
        self.screen_width = screen_width
        self.screen_height = screen_height

        # 初始化 SDL_ttf
        if sdlttf.TTF_Init() == -1:
            raise RuntimeError("Failed to initialize SDL_ttf")

        # 加载字体
        font_path = Path(__file__).parent / "fonts" / "NotoSansCJKsc-Regular.otf"
        self.font_large = sdlttf.TTF_OpenFont(str(font_path).encode(), 32)
        self.font_small = sdlttf.TTF_OpenFont(str(font_path).encode(), 24)

        if not self.font_large or not self.font_small:
            raise RuntimeError("Failed to load font")

    def render_progress(self, surface, message: str, progress: int):
        """渲染进度 UI"""
        # 清屏（黑色背景）
        sdl2.ext.fill(surface, sdl2.ext.Color(0, 0, 0))

        # 渲染消息文字（居中，上三分之一）
        self._render_text(surface, message, self.font_large,
                         self.screen_height // 3)

        # 渲染进度条（居中，中间）
        self._render_progress_bar(surface, progress,
                                  self.screen_height // 2)

        # 渲染百分比（居中，进度条下方）
        percent_text = f"{progress}%"
        self._render_text(surface, percent_text, self.font_small,
                         self.screen_height // 2 + 60)

    def _render_text(self, surface, text: str, font, y_pos: int):
        """渲染居中文字"""
        # 创建文字表面
        color = sdl2.SDL_Color(255, 255, 255)  # 白色
        text_surface = sdlttf.TTF_RenderUTF8_Blended(
            font, text.encode('utf-8'), color
        )

        if not text_surface:
            return

        # 计算居中位置
        text_rect = text_surface.contents.clip_rect
        x_pos = (self.screen_width - text_rect.w) // 2

        # 绘制到屏幕
        dest_rect = sdl2.SDL_Rect(x_pos, y_pos, text_rect.w, text_rect.h)
        sdl2.SDL_BlitSurface(text_surface, None, surface, dest_rect)
        sdl2.SDL_FreeSurface(text_surface)

    def _render_progress_bar(self, surface, progress: int, y_pos: int):
        """渲染进度条"""
        bar_width = int(self.screen_width * 0.6)
        bar_height = 30
        x_pos = (self.screen_width - bar_width) // 2

        # 背景（深灰色）
        bg_rect = sdl2.SDL_Rect(x_pos, y_pos, bar_width, bar_height)
        sdl2.ext.fill(surface, sdl2.ext.Color(51, 51, 51), bg_rect)

        # 已填充部分（绿色）
        filled_width = int(bar_width * progress / 100)
        if filled_width > 0:
            fill_rect = sdl2.SDL_Rect(x_pos, y_pos, filled_width, bar_height)
            sdl2.ext.fill(surface, sdl2.ext.Color(0, 255, 0), fill_rect)

    def cleanup(self):
        """清理资源"""
        if self.font_large:
            sdlttf.TTF_CloseFont(self.font_large)
        if self.font_small:
            sdlttf.TTF_CloseFont(self.font_small)
        sdlttf.TTF_Quit()
```

**测试**:
```bash
# 单元测试（模拟 SDL2）
pytest tests/unit/test_renderer.py -v
```

### 1.4 实现进度窗口（`progress_window.py`）

**文件**: `src/updater/gui/progress_window.py`（~150 行）

**关键组件**:
- `ProgressWindow` 类
- 全屏窗口创建
- 事件循环
- 从 `/api/v1.0/progress` 轮询进度

**代码结构**:
```python
import sdl2
import sdl2.ext
import time
import httpx
from typing import Dict, Any
from .renderer import Renderer

class ProgressWindow:
    def __init__(self, updater_url: str = "http://localhost:12315"):
        """初始化进度窗口"""
        self.updater_url = updater_url
        self.running = False
        self.window = None
        self.renderer = None

        # 初始化 SDL
        if sdl2.SDL_Init(sdl2.SDL_INIT_VIDEO) != 0:
            raise RuntimeError(f"SDL_Init failed: {sdl2.SDL_GetError()}")

    def create_window(self):
        """创建全屏窗口"""
        # 获取显示模式
        display_mode = sdl2.SDL_DisplayMode()
        if sdl2.SDL_GetCurrentDisplayMode(0, display_mode) != 0:
            raise RuntimeError("Failed to get display mode")

        # 创建窗口
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

        # 创建渲染器
        screen_surface = sdl2.SDL_GetWindowSurface(self.window)
        self.renderer = Renderer(display_mode.w, display_mode.h)

    def fetch_progress(self) -> Dict[str, Any]:
        """从 updater API 获取进度"""
        try:
            response = httpx.get(
                f"{self.updater_url}/api/v1.0/progress",
                timeout=2.0
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            # 返回错误状态
            return {
                "stage": "failed",
                "progress": 0,
                "message": "连接失败",
                "error": str(e)
            }

    def run(self):
        """主事件循环"""
        self.running = True
        last_poll = time.time()
        current_data = {
            "stage": "idle",
            "progress": 0,
            "message": "正在初始化..."
        }

        while self.running:
            # 处理事件
            event = sdl2.SDL_Event()
            while sdl2.SDL_PollEvent(event) != 0:
                if event.type == sdl2.SDL_QUIT:
                    self.running = False

            # 每 500ms 轮询一次进度
            now = time.time()
            if now - last_poll >= 0.5:
                current_data = self.fetch_progress()
                last_poll = now

            # 渲染
            surface = sdl2.SDL_GetWindowSurface(self.window)
            self.renderer.render_progress(
                surface,
                current_data.get("message", ""),
                current_data.get("progress", 0)
            )
            sdl2.SDL_UpdateWindowSurface(self.window)

            # 检查更新是否完成
            stage = current_data.get("stage")
            if stage in ["success", "failed"]:
                # 显示最终状态 3 秒
                time.sleep(3)
                self.running = False

            # 小延迟以减少 CPU 使用
            sdl2.SDL_Delay(50)

    def cleanup(self):
        """清理资源"""
        if self.renderer:
            self.renderer.cleanup()
        if self.window:
            sdl2.SDL_DestroyWindow(self.window)
        sdl2.SDL_Quit()

def main():
    """GUI 子进程入口点"""
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

**测试**:
```bash
# 手动测试（需要 SDL2）
python -m updater.gui.progress_window
```

---

## Phase 2: 进程管理（1 天）

### 2.1 实现 GUI 启动器（`launcher.py`）

**文件**: `src/updater/gui/launcher.py`（~80 行）

**关键组件**:
- `GUILauncher` 类
- 子进程启动
- 进程终止
- 错误处理

**代码结构**:
```python
import subprocess
import sys
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

class GUILauncher:
    """管理 GUI 子进程生命周期"""

    def __init__(self):
        self.process: Optional[subprocess.Popen] = None

    def start(self) -> bool:
        """
        启动 GUI 子进程

        Returns:
            成功返回 True，否则返回 False
        """
        if self.process is not None:
            logger.warning("GUI process already running")
            return False

        try:
            # 启动 GUI 作为子进程
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
        停止 GUI 子进程

        Args:
            timeout: 等待优雅终止的秒数

        Returns:
            成功返回 True，否则返回 False
        """
        if self.process is None:
            logger.warning("No GUI process to stop")
            return False

        try:
            # 尝试优雅终止
            self.process.terminate()

            try:
                self.process.wait(timeout=timeout)
                logger.info("GUI process terminated gracefully")
            except subprocess.TimeoutExpired:
                # 超时则强制杀死
                logger.warning("GUI process did not terminate, forcing kill")
                self.process.kill()
                self.process.wait()

            # 记录输出
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
        """检查 GUI 进程是否运行"""
        if self.process is None:
            return False
        return self.process.poll() is None

    def __del__(self):
        """确保进程被清理"""
        if self.process and self.is_running():
            self.stop()
```

**测试**:
```bash
# 单元测试
pytest tests/unit/test_gui_launcher.py -v
```

---

## Phase 3: 集成（1 天）

### 3.1 修改更新 API（`routes.py`）

**文件**: `src/updater/api/routes.py`

**修改**（+30 行）:

```python
# 在顶部添加导入
from updater.gui.launcher import GUILauncher

# 修改 post_update 端点
@router.post("/update")
async def post_update(request: UpdateRequest, background_tasks: BackgroundTasks):
    """触发 OTA 更新"""

    # ... 现有验证逻辑 ...

    # 启动 GUI（新增）
    gui_launcher = GUILauncher()
    gui_started = gui_launcher.start()

    if not gui_started:
        logger.warning("Failed to start GUI, continuing without visual feedback")

    # 启动更新工作流
    background_tasks.add_task(
        _update_workflow,
        request.version,
        gui_launcher  # 将 launcher 传递给工作流
    )

    return SuccessResponse(message="Update started")

# 修改 _update_workflow
async def _update_workflow(version: str, gui_launcher: GUILauncher):
    """后台更新工作流"""
    try:
        # ... 现有下载和部署逻辑 ...

        await deploy_service.deploy_package(package_path, version)

    except Exception as e:
        logger.error(f"Update failed: {e}")
        # ... 现有错误处理 ...

    finally:
        # 停止 GUI（新增）
        if gui_launcher.is_running():
            gui_launcher.stop()
            logger.info("GUI stopped")
```

**测试**:
```bash
# 集成测试
pytest tests/integration/test_gui_integration.py -v
```

### 3.2 更新依赖（`pyproject.toml`）

**文件**: `pyproject.toml`

**修改**（+2 行）:

```toml
[project]
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn>=0.32.0",
    "httpx>=0.27.0",
    "aiofiles>=24.1.0",
    "PySDL2>=0.9.16",        # 新增
    "PySDL2-dll>=2.28.0",    # 新增
]
```

**安装**:
```bash
uv sync
```

---

## Phase 4: 测试（1-2 天）

### 4.1 单元测试

**文件**: `tests/unit/test_gui_launcher.py`

```python
import pytest
from updater.gui.launcher import GUILauncher

def test_launcher_start():
    """测试 GUI launcher 启动进程"""
    launcher = GUILauncher()
    assert launcher.start()
    assert launcher.is_running()
    launcher.stop()

def test_launcher_stop():
    """测试 GUI launcher 停止进程"""
    launcher = GUILauncher()
    launcher.start()
    assert launcher.stop()
    assert not launcher.is_running()

def test_launcher_double_start():
    """测试启动已运行的进程"""
    launcher = GUILauncher()
    launcher.start()
    assert not launcher.start()  # 应该返回 False
    launcher.stop()
```

### 4.2 集成测试

**文件**: `tests/integration/test_gui_integration.py`

```python
import pytest
import httpx
from updater.gui.launcher import GUILauncher

@pytest.mark.asyncio
async def test_gui_lifecycle():
    """测试完整 GUI 生命周期"""
    launcher = GUILauncher()

    # 启动 GUI
    assert launcher.start()

    # 等待 GUI 初始化
    await asyncio.sleep(2)

    # 验证 GUI 正在轮询进度
    # （这需要 updater API 正在运行）

    # 停止 GUI
    assert launcher.stop()

@pytest.mark.asyncio
async def test_update_with_gui(test_client):
    """测试更新端点启动 GUI"""
    response = await test_client.post(
        "/api/v1.0/update",
        json={"version": "1.0.0"}
    )

    assert response.status_code == 200

    # 验证 GUI 进程已启动
    # （检查进程列表或日志）
```

### 4.3 手动测试

**文件**: `tests/manual/test_gui_display.py`

```python
"""
GUI 显示手动测试脚本

在目标设备上运行以验证：
- 全屏显示
- 中文文字渲染
- 进度条动画
- 自动关闭行为
"""

import time
from updater.gui.progress_window import ProgressWindow

def test_gui_display():
    """手动测试 GUI 显示"""
    window = ProgressWindow()

    try:
        window.create_window()

        # 模拟进度更新
        for i in range(0, 101, 5):
            window.renderer.render_progress(
                window.window.get_surface(),
                f"正在升级系统... ({i}%)",
                i
            )
            window.window.refresh()
            time.sleep(0.5)

        print("测试成功完成")

    finally:
        window.cleanup()

if __name__ == "__main__":
    test_gui_display()
```

---

## Phase 5: 文档（0.5 天）

### 5.1 更新 README

在 `README.md` 中添加 GUI 章节：

```markdown
## GUI 功能

updater 包含用于显示更新进度的轻量级 GUI。

### 要求
- SDL2 库：`libsdl2-2.0-0`、`libsdl2-ttf-2.0-0`
- Python 包：`PySDL2`、`PySDL2-dll`

### 使用
通过 `/api/v1.0/update` 触发更新时，GUI 会自动启动。

### 故障排除
- 如果 GUI 未出现，检查 SDL2 安装
- 检查 `logs/updater.log` 中的错误日志
- GUI 失败不会影响更新进程
```

### 5.2 创建 GUI 文档

**文件**: `docs/GUI.md`

文档内容：
- 架构概述
- 配置选项
- 故障排除指南
- 开发指南

---

## 部署检查清单

### 开发环境
- [ ] 安装 PySDL2：`uv sync`
- [ ] 下载字体到 `src/updater/gui/fonts/`
- [ ] 测试 GUI 启动：`python -m updater.gui.progress_window`
- [ ] 运行单元测试：`pytest tests/unit/test_gui_launcher.py -v`
- [ ] 运行集成测试：`pytest tests/integration/test_gui_integration.py -v`

### 目标设备
- [ ] 安装 SDL2：`apt-get install libsdl2-2.0-0 libsdl2-ttf-2.0-0`
- [ ] 部署带 GUI 代码的 updater
- [ ] 验证字体文件存在
- [ ] 手动测试 GUI 显示
- [ ] 测试带 GUI 的完整更新工作流
- [ ] 验证内存使用 < 50MB
- [ ] 验证 GUI 覆盖 QT 界面

---

## 成功标准

### 功能性
- ✅ 触发更新时 GUI 启动
- ✅ 进度实时更新（500ms）
- ✅ 中文文字正确显示
- ✅ 进度条平滑动画
- ✅ 更新后 GUI 自动关闭
- ✅ GUI 覆盖现有 QT 界面

### 非功能性
- ✅ 内存使用 < 50MB
- ✅ 渲染期间 CPU 使用 < 15%
- ✅ GUI 启动时间 < 2 秒
- ✅ GUI 失败不影响更新进程

### 测试
- ✅ 所有单元测试通过
- ✅ 所有集成测试通过
- ✅ 目标设备上手动测试通过
- ✅ 性能基准达标

---

## 回滚计划

如果 GUI 实施导致问题：

1. **禁用 GUI**：注释掉 `routes.py` 中的 GUI launcher 代码
2. **移除依赖**：从 `pyproject.toml` 移除 PySDL2
3. **回退提交**：`git revert <commit-hash>`
4. **重新部署**：部署不带 GUI 功能的版本

GUI 设计为非关键功能 - 即使 GUI 失败，updater 也能继续运行。

---

## 时间线

| 阶段 | 工期 | 依赖 |
|------|------|------|
| Phase 1: GUI 基础框架 | 1-2 天 | 字体下载 |
| Phase 2: 进程管理 | 1 天 | Phase 1 |
| Phase 3: 集成 | 1 天 | Phase 1, 2 |
| Phase 4: 测试 | 1-2 天 | Phase 1, 2, 3 |
| Phase 5: 文档 | 0.5 天 | Phase 4 |

**总计**: 5-7 天

---

## 下一步

1. ✅ 审查并批准本计划
2. ⏳ 安装依赖并下载字体
3. ⏳ 实施 Phase 1（GUI 基础框架）
4. ⏳ 实施 Phase 2（进程管理）
5. ⏳ 实施 Phase 3（集成）
6. ⏳ 执行 Phase 4（测试）
7. ⏳ 完成 Phase 5（文档）
8. ⏳ 部署到目标设备

---

**计划状态**: ✅ 准备实施
**需要批准**: 是
**风险等级**: 低（GUI 是非关键功能）
