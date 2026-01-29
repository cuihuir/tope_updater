# GUI UI 设计方案 - 多分辨率适配

**更新日期**: 2026-01-29
**Logo 文件**: `specs/002-gui/logo.png` (1114x830 PNG)

---

## 🖥️ 目标屏幕分辨率

| 优先级 | 分辨率 | 宽高比 | 典型设备 | Logo 尺寸 | 字体大小 |
|--------|--------|--------|----------|-----------|----------|
| **P0** | **1920x440** | 4.36:1 | 超宽屏 | 100x100 | 36/28 |
| P1 | 1024x600 | 1.71:1 | 7寸平板 | 80x80 | 28/20 |
| P1 | 1280x800 | 1.6:1 | 10寸平板 | 100x100 | 32/24 |
| P1 | 1920x1080 | 1.78:1 | 标准显示器 | 120x120 | 42/32 |

---

## 🎨 UI 布局设计

### 主要分辨率：1920x440（超宽屏）

```
┌──────────────────────────────────────────────────────────────────────────┐
│                                                                          │
│  [LOGO]              正在升级系统...  (36px)                             │
│  100x100                                                                 │
│                 ████████████████████████░░░░░░░░░░                       │
│                           45%  (28px)                                    │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘

尺寸规范（1920x440）:
- Logo: (40, 170) - 左侧，垂直居中，100x100px（正方形）
- 内容区起始X: 180
- 内容区宽度: 1700
- 文字Y: 120, 字体: 36px
- 进度条Y: 220
- 进度条宽度: 1000px (约60%内容区)
- 百分比Y: 270, 字体: 28px
```

### 其他分辨率布局

#### 1024x600
```
Logo: 80x80（正方形）, 位置(30, 260)
内容区: X=150, 宽度=840
进度条: 宽度=500px
字体: 28px/20px
```

#### 1280x800
```
Logo: 100x100（正方形）, 位置(40, 350)
内容区: X=180, 宽度=1060
进度条: 宽度=600px
字体: 32px/24px
```

#### 1920x1080
```
Logo: 120x120（正方形）, 位置(50, 480)
内容区: X=210, 宽度=1660
进度条: 宽度=1000px
字体: 42px/32px
```

---

## 📐 自适应布局算法

### Logo 尺寸计算（正方形）

```python
def calculate_logo_size(screen_width: int, screen_height: int) -> int:
    """
    根据屏幕尺寸计算 logo 大小（正方形）
    返回边长
    """
    # 根据屏幕宽度和高度确定 logo 尺寸
    if screen_width >= 1920:
        if screen_height <= 600:  # 超宽屏 (1920x440)
            return 100
        else:  # 标准屏 (1920x1080)
            return 120
    elif screen_width >= 1280:
        return 100
    elif screen_width >= 1024:
        return 80
    else:
        return 60
```

### 布局参数计算

```python
class LayoutConfig:
    """布局配置"""

    def __init__(self, screen_width: int, screen_height: int):
        self.screen_width = screen_width
        self.screen_height = screen_height

        # Logo 尺寸和位置（正方形）
        self.logo_size = self.calculate_logo_size()
        self.logo_x = 40 if screen_width >= 1280 else 30
        self.logo_y = (screen_height - self.logo_size) // 2

        # 内容区域
        self.content_x = self.logo_x + self.logo_size + 40
        self.content_width = screen_width - self.content_x - 50

        # 字体大小（根据分辨率调整）
        self.font_size_large = self.calculate_font_size_large()
        self.font_size_small = self.calculate_font_size_small()

        # 文字位置（内容区上方 1/3）
        self.text_y = screen_height // 3

        # 进度条
        self.progress_y = screen_height // 2
        self.progress_width = min(1000, int(self.content_width * 0.6))
        self.progress_height = 30

        # 百分比
        self.percent_y = self.progress_y + 50

    def calculate_logo_size(self) -> int:
        """计算 logo 尺寸（正方形边长）"""
        if self.screen_width >= 1920:
            return 100 if self.screen_height <= 600 else 120
        elif self.screen_width >= 1280:
            return 100
        elif self.screen_width >= 1024:
            return 80
        else:
            return 60

    def calculate_font_size_large(self) -> int:
        """计算大字体尺寸"""
        if self.screen_width >= 1920:
            return 36 if self.screen_height <= 600 else 42
        elif self.screen_width >= 1280:
            return 32
        elif self.screen_width >= 1024:
            return 28
        else:
            return 24

    def calculate_font_size_small(self) -> int:
        """计算小字体尺寸"""
        if self.screen_width >= 1920:
            return 28 if self.screen_height <= 600 else 32
        elif self.screen_width >= 1280:
            return 24
        elif self.screen_width >= 1024:
            return 20
        else:
            return 18
```

---

## 🖼️ Logo 处理方案

### 方案：强制缩放/裁切为正方形

**原理**:
- 使用 `specs/002-gui/logo.png` (1114x830) 作为临时 logo
- 运行时强制缩放或裁切为正方形
- **后期替换为 SVG 格式**，可任意缩放

**处理方式**:
1. **居中裁切**：从原图中心裁切出正方形区域（830x830）
2. **缩放**：将裁切后的正方形缩放到目标尺寸

**优点**:
- ✅ 统一为正方形，布局简洁
- ✅ 后期可无缝替换为 SVG
- ✅ 实施简单

**实施代码**:

```python
import sdl2
import sdl2.sdlimage as sdlimage
from pathlib import Path

class Renderer:
    def __init__(self, screen_width: int, screen_height: int):
        self.screen_width = screen_width
        self.screen_height = screen_height

        # 初始化布局配置
        self.layout = LayoutConfig(screen_width, screen_height)

        # 初始化 SDL_image
        sdlimage.IMG_Init(sdlimage.IMG_INIT_PNG)

        # 加载并处理 logo
        logo_path = Path(__file__).parent.parent.parent / "specs" / "002-gui" / "logo.png"
        self.logo = self._load_and_crop_logo(logo_path, self.layout.logo_size)

        # 初始化字体（根据分辨率调整大小）
        font_path = Path(__file__).parent / "fonts" / "NotoSansCJKsc-Regular.otf"
        self.font_large = sdlttf.TTF_OpenFont(
            str(font_path).encode(),
            self.layout.font_size_large
        )
        self.font_small = sdlttf.TTF_OpenFont(
            str(font_path).encode(),
            self.layout.font_size_small
        )
        # ...

    def _load_and_crop_logo(self, logo_path: Path, target_size: int):
        """
        加载 logo 并裁切/缩放为正方形

        Args:
            logo_path: logo 文件路径
            target_size: 目标正方形边长

        Returns:
            处理后的 SDL surface（正方形）
        """
        # 加载原始 logo
        original = sdlimage.IMG_Load(str(logo_path).encode())
        if not original:
            raise RuntimeError(f"Failed to load logo from {logo_path}")

        orig_rect = original.contents.clip_rect
        orig_width = orig_rect.w
        orig_height = orig_rect.h

        # 步骤 1: 居中裁切为正方形
        crop_size = min(orig_width, orig_height)
        crop_x = (orig_width - crop_size) // 2
        crop_y = (orig_height - crop_size) // 2

        # 创建裁切后的 surface
        cropped = sdl2.SDL_CreateRGBSurface(
            0, crop_size, crop_size, 32,
            0xFF000000, 0x00FF0000, 0x0000FF00, 0x000000FF
        )

        src_rect = sdl2.SDL_Rect(crop_x, crop_y, crop_size, crop_size)
        dst_rect = sdl2.SDL_Rect(0, 0, crop_size, crop_size)
        sdl2.SDL_BlitSurface(original, src_rect, cropped, dst_rect)

        # 步骤 2: 缩放到目标尺寸
        scaled = sdl2.SDL_CreateRGBSurface(
            0, target_size, target_size, 32,
            0xFF000000, 0x00FF0000, 0x0000FF00, 0x000000FF
        )

        src_rect = sdl2.SDL_Rect(0, 0, crop_size, crop_size)
        dst_rect = sdl2.SDL_Rect(0, 0, target_size, target_size)
        sdl2.SDL_BlitScaled(cropped, src_rect, scaled, dst_rect)

        # 清理临时 surface
        sdl2.SDL_FreeSurface(original)
        sdl2.SDL_FreeSurface(cropped)

        return scaled

    def render_progress(self, surface, message: str, progress: int):
        """渲染进度 UI"""
        # 清屏（黑色背景）
        sdl2.ext.fill(surface, sdl2.ext.Color(0, 0, 0))

        # 渲染 Logo（左侧）
        if self.logo:
            logo_rect = sdl2.SDL_Rect(
                self.layout.logo_x,
                self.layout.logo_y,
                self.layout.logo_width,
                self.layout.logo_height
            )
            sdl2.SDL_BlitSurface(self.logo, None, surface, logo_rect)

        # 渲染文字（右侧内容区，居中）
        self._render_text_centered(
            surface,
            message,
            self.font_large,
            self.layout.content_x,
            self.layout.text_y,
            self.layout.content_width
        )

        # 渲染进度条（右侧内容区，居中）
        self._render_progress_bar_centered(
            surface,
            progress,
            self.layout.content_x,
            self.layout.progress_y,
            self.layout.content_width
        )

        # 渲染百分比
        percent_text = f"{progress}%"
        self._render_text_centered(
            surface,
            percent_text,
            self.font_small,
            self.layout.content_x,
            self.layout.percent_y,
            self.layout.content_width
        )

    def _render_text_centered(self, surface, text: str, font,
                              area_x: int, y: int, area_width: int):
        """在指定区域内渲染居中文字"""
        color = sdl2.SDL_Color(255, 255, 255)
        text_surface = sdlttf.TTF_RenderUTF8_Blended(
            font, text.encode('utf-8'), color
        )

        if not text_surface:
            return

        text_rect = text_surface.contents.clip_rect
        x = area_x + (area_width - text_rect.w) // 2

        dest_rect = sdl2.SDL_Rect(x, y, text_rect.w, text_rect.h)
        sdl2.SDL_BlitSurface(text_surface, None, surface, dest_rect)
        sdl2.SDL_FreeSurface(text_surface)

    def _render_progress_bar_centered(self, surface, progress: int,
                                      area_x: int, y: int, area_width: int):
        """在指定区域内渲染居中进度条"""
        bar_width = self.layout.progress_width
        bar_height = self.layout.progress_height
        x = area_x + (area_width - bar_width) // 2

        # 背景（深灰色）
        bg_rect = sdl2.SDL_Rect(x, y, bar_width, bar_height)
        sdl2.ext.fill(surface, sdl2.ext.Color(51, 51, 51), bg_rect)

        # 已填充部分（绿色）
        filled_width = int(bar_width * progress / 100)
        if filled_width > 0:
            fill_rect = sdl2.SDL_Rect(x, y, filled_width, bar_height)
            sdl2.ext.fill(surface, sdl2.ext.Color(0, 255, 0), fill_rect)
```

---

## 📊 各分辨率效果预览

### 1920x440（超宽屏）- 优先适配 ⭐
```
┌──────────────────────────────────────────────────────────────────────────┐
│                                                                          │
│  [100x100]          正在升级系统... (36px)                               │
│                                                                          │
│              ████████████████████████░░░░░░░░░░ (1000px)                │
│                        45% (28px)                                        │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

### 1024x600（小屏）
```
┌────────────────────────────────────────────────┐
│                                                │
│  [80x80]      正在升级系统... (28px)           │
│                                                │
│          ████████████░░░░░░ (500px)           │
│                45% (20px)                      │
│                                                │
└────────────────────────────────────────────────┘
```

### 1280x800（中屏）
```
┌──────────────────────────────────────────────────────────┐
│                                                          │
│                                                          │
│  [100x100]        正在升级系统... (32px)                 │
│                                                          │
│            ████████████████░░░░░░ (600px)               │
│                    45% (24px)                            │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

### 1920x1080（标准屏）
```
┌──────────────────────────────────────────────────────────────────────────┐
│                                                                          │
│                                                                          │
│                                                                          │
│  [120x120]          正在升级系统... (42px)                               │
│                                                                          │
│              ████████████████████████░░░░░░░░░░ (1000px)                │
│                        45% (32px)                                        │
│                                                                          │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

---

## 🎨 颜色方案

```python
# 颜色定义
COLORS = {
    "background": (0, 0, 0),        # 黑色
    "text": (255, 255, 255),        # 白色
    "progress_bg": (51, 51, 51),    # 深灰色
    "progress_fill": (0, 255, 0),   # 绿色
}
```

---

## 📦 依赖

**无额外依赖**，使用现有的：
```toml
[project]
dependencies = [
    "PySDL2>=0.9.16",
    "PySDL2-dll>=2.28.0",
]
```

**系统库**:
```bash
apt-get install libsdl2-2.0-0 libsdl2-image-2.0-0
```

---

## ✅ 实施步骤

1. **复制 logo 到正确位置**
   ```bash
   cp specs/002-gui/logo.png src/updater/gui/assets/logo.png
   ```

2. **实现 LayoutConfig 类**
   - 文件: `src/updater/gui/layout.py`
   - 自适应计算布局参数

3. **更新 Renderer 类**
   - 加载和缩放 logo
   - 实现横向布局渲染

4. **测试各分辨率**
   - 优先测试 1920x440
   - 验证其他分辨率

---

## 🧪 测试计划

### 手动测试脚本

```python
# tests/manual/test_ui_resolutions.py

from updater.gui.progress_window import ProgressWindow
import sdl2

def test_resolution(width: int, height: int):
    """测试指定分辨率"""
    print(f"\n测试分辨率: {width}x{height}")

    # 创建指定尺寸的窗口
    window = ProgressWindow()
    window.create_window_with_size(width, height)

    # 模拟进度
    for progress in range(0, 101, 10):
        window.renderer.render_progress(
            window.window.get_surface(),
            f"正在升级系统... ({progress}%)",
            progress
        )
        window.window.refresh()
        sdl2.SDL_Delay(500)

    window.cleanup()

if __name__ == "__main__":
    # 测试所有目标分辨率
    resolutions = [
        (1920, 440),   # P0
        (1024, 600),   # P1
        (1280, 800),   # P1
        (1920, 1080),  # P1
    ]

    for width, height in resolutions:
        test_resolution(width, height)
```

---

## ✅ 已确认设计要点

- ✅ **Logo 格式**: 正方形，强制裁切/缩放
- ✅ **Logo 尺寸**:
  - 1920x440: 100x100px
  - 1024x600: 80x80px
  - 1280x800: 100x100px
  - 1920x1080: 120x120px
- ✅ **进度条宽度**: 1000px（合适）
- ✅ **字体大小**: 根据分辨率自适应
  - 1920x440: 36px/28px
  - 1024x600: 28px/20px
  - 1280x800: 32px/24px
  - 1920x1080: 42px/32px
- ✅ **品牌名称**: 不需要
- ✅ **颜色方案**: 黑色背景 + 白色文字 + 绿色进度条
- ✅ **后期计划**: 替换为 SVG 格式 logo

---

## 🎯 实施优先级

### Phase 1: 基础实现（使用现有 PNG）
1. 实现 `LayoutConfig` 类（自适应布局）
2. 实现 logo 裁切和缩放逻辑
3. 实现根据分辨率调整字体大小
4. 优先适配 1920x440 分辨率

### Phase 2: 多分辨率测试
1. 测试 1920x440（P0）
2. 测试 1024x600, 1280x800, 1920x1080（P1）
3. 验证布局和字体大小

### Phase 3: SVG 支持（后期）
1. 接收 SVG 格式 logo
2. 实现 SVG 渲染或预转换
3. 替换现有 PNG

---

**状态**: ✅ 设计已确认
**下一步**: 开始实施 Phase 1
