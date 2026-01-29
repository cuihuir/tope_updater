"""
GUI Renderer

渲染 logo、文字和进度条
"""

import sdl2
import sdl2.ext
import sdl2.sdlimage as sdlimage
import sdl2.sdlttf as sdlttf
from pathlib import Path
from typing import Optional

from .layout import LayoutConfig


class Renderer:
    """
    GUI 渲染器

    负责渲染：
    - Logo（正方形，裁切和缩放）
    - 文字（支持中文）
    - 进度条
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

        # 初始化布局配置
        self.layout = LayoutConfig(screen_width, screen_height)

        # 初始化 SDL_image
        sdlimage.IMG_Init(sdlimage.IMG_INIT_PNG)

        # 初始化 SDL_ttf
        if sdlttf.TTF_Init() == -1:
            raise RuntimeError("Failed to initialize SDL_ttf")

        # 加载并处理 logo
        logo_filename = f"logo_{self.layout.logo_size}.png"
        logo_path = Path(__file__).parent / "assets" / logo_filename
        self.logo: Optional[sdl2.SDL_Surface] = None
        if logo_path.exists():
            self.logo = self._load_logo(logo_path)
        else:
            print(f"Warning: Logo not found at {logo_path}")

        # 加载字体
        font_path = Path(__file__).parent / "fonts" / "NotoSansCJKsc-Regular.otf"
        if not font_path.exists():
            raise RuntimeError(f"Font not found at {font_path}")

        self.font_large = sdlttf.TTF_OpenFont(
            str(font_path).encode('utf-8'),
            self.layout.font_size_large
        )
        self.font_small = sdlttf.TTF_OpenFont(
            str(font_path).encode('utf-8'),
            self.layout.font_size_small
        )

        if not self.font_large or not self.font_small:
            raise RuntimeError("Failed to load fonts")

    def _load_logo(self, logo_path: Path) -> sdl2.SDL_Surface:
        """
        加载 logo PNG 文件

        Args:
            logo_path: logo 文件路径

        Returns:
            SDL surface
        """
        logo = sdlimage.IMG_Load(str(logo_path).encode('utf-8'))
        if not logo:
            raise RuntimeError(f"Failed to load logo from {logo_path}")
        return logo

    def render_progress(self, surface: sdl2.SDL_Surface, message: str, progress: int):
        """
        渲染进度 UI

        Args:
            surface: 目标 surface
            message: 显示的消息
            progress: 进度百分比 (0-100)
        """
        # 清屏（黑色背景）
        sdl2.ext.fill(surface, sdl2.ext.Color(0, 0, 0))

        # 渲染 Logo（左侧，垂直居中）
        if self.logo:
            self._render_logo(surface)

        # 渲染消息文字（右侧内容区，居中）
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

    def _render_logo(self, surface: sdl2.SDL_Surface):
        """渲染 logo（左侧居中）"""
        logo_rect = sdl2.SDL_Rect(
            self.layout.logo_x,
            self.layout.logo_y,
            self.layout.logo_size,
            self.layout.logo_size
        )
        sdl2.SDL_BlitSurface(self.logo, None, surface, logo_rect)

    def _render_text_centered(
        self,
        surface: sdl2.SDL_Surface,
        text: str,
        font,
        area_x: int,
        y: int,
        area_width: int
    ):
        """在指定区域内渲染居中文字"""
        color = sdl2.SDL_Color(255, 255, 255)  # 白色
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

    def _render_progress_bar_centered(
        self,
        surface: sdl2.SDL_Surface,
        progress: int,
        area_x: int,
        y: int,
        area_width: int
    ):
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
