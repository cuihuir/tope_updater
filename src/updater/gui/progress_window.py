"""
GUI Progress Window

全屏进度显示窗口
"""

import sdl2
import sdl2.ext
import time
import httpx
from typing import Dict, Any, Optional

from .renderer import Renderer


class ProgressWindow:
    """
    进度显示窗口

    功能：
    - 创建全屏窗口（置顶）
    - 轮询 /api/v1.0/progress 获取进度
    - 渲染进度 UI
    - 自动关闭
    """

    def __init__(self, updater_url: str = "http://localhost:12315", fullscreen: bool = True):
        """
        初始化进度窗口

        Args:
            updater_url: Updater API 地址
            fullscreen: 是否全屏模式（默认 True）
        """
        self.updater_url = updater_url
        self.fullscreen = fullscreen
        self.running = False
        self.window: Optional[sdl2.SDL_Window] = None
        self.renderer: Optional[Renderer] = None

        # 初始化 SDL
        if sdl2.SDL_Init(sdl2.SDL_INIT_VIDEO) != 0:
            error = sdl2.SDL_GetError()
            raise RuntimeError(f"SDL_Init failed: {error.decode('utf-8')}")

    def create_window(self):
        """创建全屏窗口"""
        # 获取显示模式
        display_mode = sdl2.SDL_DisplayMode()
        if sdl2.SDL_GetCurrentDisplayMode(0, display_mode) != 0:
            raise RuntimeError("Failed to get display mode")

        screen_width = display_mode.w
        screen_height = display_mode.h

        print(f"Creating window: {screen_width}x{screen_height} (fullscreen={self.fullscreen})")

        # 创建窗口
        window_flags = sdl2.SDL_WINDOW_SHOWN
        if self.fullscreen:
            window_flags |= sdl2.SDL_WINDOW_FULLSCREEN_DESKTOP

        self.window = sdl2.SDL_CreateWindow(
            b"OTA Update",
            sdl2.SDL_WINDOWPOS_CENTERED,
            sdl2.SDL_WINDOWPOS_CENTERED,
            screen_width if not self.fullscreen else screen_width,
            screen_height if not self.fullscreen else screen_height,
            window_flags
        )

        if not self.window:
            error = sdl2.SDL_GetError()
            raise RuntimeError(f"Failed to create window: {error.decode('utf-8')}")

        # 设置窗口置顶（在创建后设置）
        sdl2.SDL_RaiseWindow(self.window)

        # 尝试设置窗口为始终置顶（X11）
        try:
            import ctypes

            # 获取 SDL 窗口信息
            wm_info = sdl2.SDL_SysWMinfo()
            sdl2.SDL_VERSION(wm_info.version)

            if sdl2.SDL_GetWindowWMInfo(self.window, ctypes.byref(wm_info)):
                # 如果是 X11，设置窗口属性
                if wm_info.subsystem == sdl2.SDL_SYSWM_X11:
                    print("Setting X11 window to always on top")
                    # 这里可以添加 X11 特定的置顶代码
        except Exception as e:
            print(f"Warning: Could not set always on top: {e}")

        # 创建渲染器
        self.renderer = Renderer(screen_width, screen_height)

    def fetch_progress(self) -> Dict[str, Any]:
        """
        从 updater API 获取进度

        Returns:
            进度数据字典
        """
        try:
            response = httpx.get(
                f"{self.updater_url}/api/v1.0/progress",
                timeout=2.0
            )
            response.raise_for_status()
            return response.json().get("data", {})
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
        last_raise = time.time()
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

            # 每 2 秒提升窗口一次（保持在最前面）
            now = time.time()
            if now - last_raise >= 2.0:
                sdl2.SDL_RaiseWindow(self.window)
                last_raise = now

            # 每 500ms 轮询一次进度
            if now - last_poll >= 0.5:
                current_data = self.fetch_progress()
                last_poll = now

            # 渲染
            surface = sdl2.SDL_GetWindowSurface(self.window)
            if surface:
                self.renderer.render_progress(
                    surface,
                    current_data.get("message", ""),
                    current_data.get("progress", 0)
                )
                sdl2.SDL_UpdateWindowSurface(self.window)

            # 检查更新是否完成
            stage = current_data.get("stage")
            if stage in ["success", "failed"]:
                # 进入倒计时模式
                countdown_total = 60
                countdown_start = time.time()
                final_message = current_data.get("message", "")

                while self.running:
                    # 处理事件
                    event = sdl2.SDL_Event()
                    while sdl2.SDL_PollEvent(event) != 0:
                        if event.type == sdl2.SDL_QUIT:
                            self.running = False
                        elif event.type == sdl2.SDL_MOUSEBUTTONDOWN:
                            mx, my = event.button.x, event.button.y
                            bx = self.renderer.layout.button_x
                            by = self.renderer.layout.button_y
                            bw = self.renderer.layout.button_width
                            bh = self.renderer.layout.button_height
                            if bx <= mx <= bx + bw and by <= my <= by + bh:
                                self.running = False

                    elapsed = time.time() - countdown_start
                    remaining = max(0, countdown_total - int(elapsed))

                    if remaining == 0:
                        self.running = False
                        break

                    # 渲染完成状态
                    surface = sdl2.SDL_GetWindowSurface(self.window)
                    if surface:
                        self.renderer.render_completion(surface, final_message, remaining)
                        sdl2.SDL_UpdateWindowSurface(self.window)

                    sdl2.SDL_Delay(50)
                break

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
        import traceback
        traceback.print_exc()
    finally:
        if window:
            window.cleanup()


if __name__ == "__main__":
    main()
