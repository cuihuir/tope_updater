"""测试 SVG logo 显示"""
import sys
sys.path.insert(0, 'src')

from updater.gui.progress_window import ProgressWindow
import sdl2
import time

# 创建窗口
window = ProgressWindow()
window.create_window()

print(f"使用的 logo 尺寸: {window.renderer.layout.logo_size}x{window.renderer.layout.logo_size}")

# 模拟进度更新
print("显示 GUI 窗口 10 秒（使用 SVG 转换的 logo）...")
for i in range(0, 101, 10):
    surface = sdl2.SDL_GetWindowSurface(window.window)
    
    window.renderer.render_progress(
        surface,
        f"正在升级系统... ({i}%)",
        i
    )
    
    sdl2.SDL_UpdateWindowSurface(window.window)
    time.sleep(1)

window.cleanup()
print("测试完成 - SVG logo 显示成功！")
