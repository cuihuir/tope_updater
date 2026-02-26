#!/usr/bin/env python3
"""
Orange Pi 3B 测试脚本 - 1920x440 分辨率
优先测试目标分辨率
"""
import sys
sys.path.insert(0, 'src')

from updater.gui.progress_window import ProgressWindow
import sdl2
import time

print("=" * 60)
print("Orange Pi 3B GUI 测试")
print("目标分辨率: 1920x440")
print("=" * 60)

# 创建窗口（窗口模式，方便调试）
print("\n创建窗口...")
window = ProgressWindow(fullscreen=False)
window.create_window()

print(f"✓ 窗口创建成功")
print(f"  - 屏幕尺寸: {window.renderer.screen_width}x{window.renderer.screen_height}")
print(f"  - Logo 尺寸: {window.renderer.layout.logo_size}x{window.renderer.layout.logo_size}")
print(f"  - 字体大小: {window.renderer.layout.font_size_large}px / {window.renderer.layout.font_size_small}px")
print(f"  - 进度条宽度: {window.renderer.layout.progress_width}px")

print("\n开始模拟升级进度（10秒）...")
print("请观察窗口显示效果\n")

# 模拟进度更新
stages = [
    (0, "正在初始化..."),
    (10, "正在下载更新包..."),
    (30, "正在验证更新包..."),
    (50, "正在部署更新..."),
    (70, "正在重启服务..."),
    (90, "正在验证服务..."),
    (100, "升级完成！"),
]

for progress, message in stages:
    surface = sdl2.SDL_GetWindowSurface(window.window)
    window.renderer.render_progress(surface, message, progress)
    sdl2.SDL_UpdateWindowSurface(window.window)
    sdl2.SDL_RaiseWindow(window.window)
    
    print(f"  [{progress:3d}%] {message}")
    time.sleep(1.5)

print("\n✓ 测试完成")
print("\n检查项:")
print("  □ Logo 是否显示清晰？")
print("  □ 中文文字是否正常显示？")
print("  □ 进度条是否平滑更新？")
print("  □ 布局是否合理（Logo 左侧，内容右侧）？")

window.cleanup()
