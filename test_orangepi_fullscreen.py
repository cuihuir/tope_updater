#!/usr/bin/env python3
"""
Orange Pi 3B 全屏测试
测试全屏模式下的显示效果
"""
import sys
sys.path.insert(0, 'src')

from updater.gui.progress_window import ProgressWindow
import sdl2
import time

print("=" * 60)
print("Orange Pi 3B 全屏模式测试")
print("=" * 60)
print("\n⚠️  警告: 将进入全屏模式")
print("   按 Ctrl+C 可以中断测试\n")

time.sleep(2)

# 创建全屏窗口
print("创建全屏窗口...")
window = ProgressWindow(fullscreen=True)
window.create_window()

print(f"✓ 全屏窗口创建成功")
print(f"  分辨率: {window.renderer.screen_width}x{window.renderer.screen_height}")

# 模拟进度
for i in range(0, 101, 5):
    surface = sdl2.SDL_GetWindowSurface(window.window)
    window.renderer.render_progress(
        surface,
        f"正在升级系统... ({i}%)",
        i
    )
    sdl2.SDL_UpdateWindowSurface(window.window)
    time.sleep(0.5)

window.cleanup()
print("\n✓ 全屏测试完成")
