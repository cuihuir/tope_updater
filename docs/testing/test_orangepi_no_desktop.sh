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

# 查找 uv 命令
UV_CMD=""
if command -v uv &> /dev/null; then
    UV_CMD="uv"
elif [ -f "/home/tope/.local/bin/uv" ]; then
    UV_CMD="/home/tope/.local/bin/uv"
elif [ -f "/home/tope/.cargo/bin/uv" ]; then
    UV_CMD="/home/tope/.cargo/bin/uv"
else
    echo "错误: 找不到 uv 命令"
    echo "请确保 uv 已安装: curl -LsSf https://astral.sh/uv/install.sh | sh"
    exit 1
fi

echo "使用 uv: $UV_CMD"
echo ""

# 尝试 KMS/DRM
if [ "$SDL_VIDEODRIVER" = "kmsdrm" ]; then
    echo "尝试 kmsdrm..."
    if ! $UV_CMD run python test_orangepi_fullscreen.py 2>&1 | tee /tmp/gui_test.log; then
        echo ""
        echo "kmsdrm 失败，尝试 kmsdrm_legacy..."
        export SDL_VIDEODRIVER=kmsdrm_legacy
        $UV_CMD run python test_orangepi_fullscreen.py 2>&1 | tee /tmp/gui_test.log
    fi
else
    # Framebuffer
    $UV_CMD run python test_orangepi_fullscreen.py 2>&1 | tee /tmp/gui_test.log
fi

echo ""
echo "=========================================="
echo "测试完成"
echo "=========================================="
echo "日志保存在: /tmp/gui_test.log"
