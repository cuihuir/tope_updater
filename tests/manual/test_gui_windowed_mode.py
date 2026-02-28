"""测试窗口模式（开发环境）"""
import sys
sys.path.insert(0, 'src')

from updater.gui.progress_window import ProgressWindow
import sdl2
import time

# 创建窗口（非全屏模式）
window = ProgressWindow(fullscreen=False)
window.create_window()

print("窗口已创建（窗口模式）")
print("显示进度 10 秒...")

# 模拟进度更新
for i in range(0, 101, 10):
    sdl2.SDL_RaiseWindow(window.window)
    
    surface = sdl2.SDL_GetWindowSurface(window.window)
    window.renderer.render_progress(
        surface,
        f"正在升级系统... ({i}%)",
        i,
        ["下载完成 (564B)", "MD5 验证通过"] if i > 30 else [],
        "installing",
    )
    
    sdl2.SDL_UpdateWindowSurface(window.window)
    time.sleep(1)

window.cleanup()
print("测试完成")
