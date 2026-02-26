#!/bin/bash
# Orange Pi 3B 无桌面环境测试脚本

set -e

echo "=========================================="
echo "Orange Pi 3B 无桌面环境 GUI 测试"
echo "=========================================="
echo ""

# 检查是否为 root
if [ "$EUID" -ne 0 ]; then 
    echo "错误: 需要 root 权限"
    echo "请使用: sudo bash test_orangepi_no_desktop.sh"
    exit 1
fi

# 检查 DRM 设备
echo "1. 检查 DRM 设备..."
if [ -e /dev/dri/card0 ]; then
    echo "   ✓ 找到 DRM 设备: /dev/dri/card0"
    USE_KMSDRM=1
else
    echo "   ✗ 未找到 DRM 设备"
    USE_KMSDRM=0
fi

# 检查 Framebuffer 设备
echo "2. 检查 Framebuffer 设备..."
if [ -e /dev/fb0 ]; then
    echo "   ✓ 找到 Framebuffer: /dev/fb0"
    USE_FBCON=1
else
    echo "   ✗ 未找到 Framebuffer"
    USE_FBCON=0
fi

echo ""

# 选择后端
if [ $USE_KMSDRM -eq 1 ]; then
    echo "使用 KMS/DRM 后端（推荐）"
    export SDL_VIDEODRIVER=kmsdrm
    BACKEND="KMS/DRM"
elif [ $USE_FBCON -eq 1 ]; then
    echo "使用 Framebuffer 后端"
    export SDL_VIDEODRIVER=fbcon
    export SDL_FBDEV=/dev/fb0
    BACKEND="Framebuffer"
else
    echo "错误: 没有可用的显示后端"
    exit 1
fi

echo ""
echo "=========================================="
echo "开始测试 ($BACKEND)"
echo "=========================================="
echo ""

# 运行测试
cd /home/tope/tope_updater

# 尝试 KMS/DRM
if [ "$SDL_VIDEODRIVER" = "kmsdrm" ]; then
    echo "尝试 kmsdrm..."
    if ! uv run python test_orangepi_fullscreen.py 2>&1 | tee /tmp/gui_test.log; then
        echo ""
        echo "kmsdrm 失败，尝试 kmsdrm_legacy..."
        export SDL_VIDEODRIVER=kmsdrm_legacy
        uv run python test_orangepi_fullscreen.py 2>&1 | tee /tmp/gui_test.log
    fi
else
    # Framebuffer
    uv run python test_orangepi_fullscreen.py 2>&1 | tee /tmp/gui_test.log
fi

echo ""
echo "=========================================="
echo "测试完成"
echo "=========================================="
echo "日志保存在: /tmp/gui_test.log"
