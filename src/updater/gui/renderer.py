"""
GUI Renderer

三列布局渲染：Logo（左） / 信息+进度（中） / 操作（右）

颜色规范：
- 背景: #1E1E1E (30, 30, 30)
- 按钮: #28A745 (40, 167, 69)
- 进度条填充: #28A745
"""

import sdl2
import sdl2.ext
import sdl2.sdlimage as sdlimage
import sdl2.sdlttf as sdlttf
from pathlib import Path
from typing import List, Optional

from .layout import LayoutConfig

_BG_COLOR = sdl2.ext.Color(30, 30, 30)
_BTN_COLOR = sdl2.ext.Color(40, 167, 69)
_BTN_HOVER_COLOR = sdl2.ext.Color(60, 200, 90)
_PROGRESS_BG_COLOR = sdl2.ext.Color(51, 51, 51)
_PROGRESS_FILL_COLOR = sdl2.ext.Color(40, 167, 69)
_TEXT_WHITE = sdl2.SDL_Color(255, 255, 255)
_TEXT_GRAY = sdl2.SDL_Color(180, 180, 180)

_LOGO_CANDIDATES = ["logo.png", "logo_120.png", "logo_100.png", "logo_80.png"]


class Renderer:
    """
    GUI 渲染器（三列布局）

    负责渲染：
    - Logo（左列，缩放至接近屏幕高度）
    - 信息+进度条+日志条目（中列）
    - 按钮/阶段名称+倒计时（右列）
    """

    def __init__(self, screen_width: int, screen_height: int):
        """
        初始化渲染器

        Args:
            screen_width: 屏幕宽度
            screen_height: 屏幕高度
        """
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.layout = LayoutConfig(screen_width, screen_height)

        sdlimage.IMG_Init(sdlimage.IMG_INIT_PNG)

        if sdlttf.TTF_Init() == -1:
            raise RuntimeError("Failed to initialize SDL_ttf")

        # 加载最高质量 logo（用于缩放）
        self.logo: Optional[sdl2.SDL_Surface] = None
        assets_dir = Path(__file__).parent / "assets"
        for filename in _LOGO_CANDIDATES:
            logo_path = assets_dir / filename
            if logo_path.exists():
                self.logo = sdlimage.IMG_Load(str(logo_path).encode("utf-8"))
                if self.logo:
                    # 开启 alpha blend，使透明背景与 GUI 底色融合
                    sdl2.SDL_SetSurfaceBlendMode(
                        self.logo, sdl2.SDL_BLENDMODE_BLEND
                    )
                    break

        if not self.logo:
            print("Warning: No logo found in assets/")

        # 加载字体
        font_path = Path(__file__).parent / "fonts" / "NotoSansCJKsc-Regular.otf"
        if not font_path.exists():
            raise RuntimeError(f"Font not found at {font_path}")

        font_path_b = str(font_path).encode("utf-8")
        self.font_large = sdlttf.TTF_OpenFont(font_path_b, self.layout.font_size_large)
        self.font_small = sdlttf.TTF_OpenFont(font_path_b, self.layout.font_size_small)

        if not self.font_large or not self.font_small:
            raise RuntimeError("Failed to load fonts")

    def render_progress(
        self,
        surface: sdl2.SDL_Surface,
        message: str,
        progress: int,
        log_entries: List[str],
        stage: str = "",
    ):
        """
        渲染安装进行中 UI（三列布局）

        Args:
            surface: 目标 surface
            message: 当前阶段消息（显示为标题）
            progress: 进度百分比 (0-100)
            log_entries: 已完成阶段的日志消息列表（最多显示 4 条）
            stage: 当前阶段名称（显示在右列）
        """
        sdl2.ext.fill(surface, _BG_COLOR)

        # 左列：Logo
        if self.logo:
            self._render_logo_scaled(surface)

        # 中列：标题 + 进度条 + 百分比 + 日志条目
        self._render_text_centered(
            surface,
            message,
            self.font_large,
            self.layout.content_x,
            self.layout.title_y,
            self.layout.content_width,
        )
        self._render_progress_bar(surface, progress)
        self._render_text_centered(
            surface,
            f"{progress}%",
            self.font_small,
            self.layout.content_x,
            self.layout.percent_y,
            self.layout.content_width,
        )
        self._render_log_entries(surface, log_entries, bullet="·")

        # 右列：阶段名称
        if stage:
            self._render_text_centered(
                surface,
                stage,
                self.font_small,
                self.layout.action_x,
                self.layout.stage_label_y,
                self.layout.action_width,
            )

    def render_completion(
        self,
        surface: sdl2.SDL_Surface,
        message: str,
        log_entries: List[str],
        countdown: int,
        button_hovered: bool = False,
    ):
        """
        渲染安装完成 UI（success/failed，三列布局）

        Args:
            surface: 目标 surface
            message: 完成状态消息
            log_entries: 已完成阶段的日志消息列表
            countdown: 剩余秒数 (0-60)
            button_hovered: 按钮是否处于悬停状态
        """
        sdl2.ext.fill(surface, _BG_COLOR)

        # 左列：Logo
        if self.logo:
            self._render_logo_scaled(surface)

        # 中列：标题 + 日志条目（带 ✓ 前缀）
        self._render_text_centered(
            surface,
            message,
            self.font_large,
            self.layout.content_x,
            self.layout.title_y,
            self.layout.content_width,
        )
        self._render_log_entries(surface, log_entries, bullet="✓")

        # 右列：完成按钮 + 倒计时
        btn_color = _BTN_HOVER_COLOR if button_hovered else _BTN_COLOR
        btn_rect = sdl2.SDL_Rect(
            self.layout.button_x,
            self.layout.button_y,
            self.layout.button_width,
            self.layout.button_height,
        )
        sdl2.ext.fill(surface, btn_color, btn_rect)
        self._render_text_centered(
            surface,
            "完成安装",
            self.font_small,
            self.layout.button_x,
            self.layout.button_y
            + (self.layout.button_height - self.layout.font_size_small) // 2,
            self.layout.button_width,
        )

        self._render_text_centered(
            surface,
            f"{countdown} 秒后自动关闭",
            self.font_small,
            self.layout.action_x,
            self.layout.countdown_y,
            self.layout.action_width,
        )

    def _render_logo_scaled(self, surface: sdl2.SDL_Surface):
        """将 logo 缩放渲染到布局指定尺寸"""
        dst_rect = sdl2.SDL_Rect(
            self.layout.logo_x,
            self.layout.logo_y,
            self.layout.logo_render_w,
            self.layout.logo_render_h,
        )
        sdl2.SDL_BlitScaled(self.logo, None, surface, dst_rect)

    def _render_progress_bar(self, surface: sdl2.SDL_Surface, progress: int):
        """渲染进度条（左对齐到内容列左边缘）"""
        x = self.layout.content_x
        y = self.layout.progress_y
        w = self.layout.progress_width
        h = self.layout.progress_height

        bg_rect = sdl2.SDL_Rect(x, y, w, h)
        sdl2.ext.fill(surface, _PROGRESS_BG_COLOR, bg_rect)

        filled_width = int(w * progress / 100)
        if filled_width > 0:
            fill_rect = sdl2.SDL_Rect(x, y, filled_width, h)
            sdl2.ext.fill(surface, _PROGRESS_FILL_COLOR, fill_rect)

    def _render_log_entries(
        self,
        surface: sdl2.SDL_Surface,
        entries: List[str],
        bullet: str = "·",
    ):
        """
        渲染日志条目列表（左对齐，灰色文字，最多显示 4 条）

        Args:
            surface: 目标 surface
            entries: 日志消息列表
            bullet: 前缀符号（进度状态用 "·"，完成状态用 "✓"）
        """
        x = self.layout.content_x + 10
        y = self.layout.log_start_y
        for entry in entries[-4:]:
            self._render_text_left(
                surface, f"{bullet} {entry}", self.font_small, x, y, _TEXT_GRAY
            )
            y += self.layout.log_line_height

    def _render_text_centered(
        self,
        surface: sdl2.SDL_Surface,
        text: str,
        font,
        area_x: int,
        y: int,
        area_width: int,
        color: sdl2.SDL_Color = None,
    ):
        """在指定区域内渲染水平居中文字"""
        if color is None:
            color = _TEXT_WHITE
        text_surface = sdlttf.TTF_RenderUTF8_Blended(
            font, text.encode("utf-8"), color
        )
        if not text_surface:
            return

        text_rect = text_surface.contents.clip_rect
        x = area_x + (area_width - text_rect.w) // 2
        dest_rect = sdl2.SDL_Rect(x, y, text_rect.w, text_rect.h)
        sdl2.SDL_BlitSurface(text_surface, None, surface, dest_rect)
        sdl2.SDL_FreeSurface(text_surface)

    def _render_text_left(
        self,
        surface: sdl2.SDL_Surface,
        text: str,
        font,
        x: int,
        y: int,
        color: sdl2.SDL_Color = None,
    ):
        """渲染左对齐文字"""
        if color is None:
            color = _TEXT_WHITE
        text_surface = sdlttf.TTF_RenderUTF8_Blended(
            font, text.encode("utf-8"), color
        )
        if not text_surface:
            return

        text_rect = text_surface.contents.clip_rect
        dest_rect = sdl2.SDL_Rect(x, y, text_rect.w, text_rect.h)
        sdl2.SDL_BlitSurface(text_surface, None, surface, dest_rect)
        sdl2.SDL_FreeSurface(text_surface)

    def cleanup(self):
        """清理资源"""
        if self.logo:
            sdl2.SDL_FreeSurface(self.logo)
        if self.font_large:
            sdlttf.TTF_CloseFont(self.font_large)
        if self.font_small:
            sdlttf.TTF_CloseFont(self.font_small)
        sdlttf.TTF_Quit()
        sdlimage.IMG_Quit()
