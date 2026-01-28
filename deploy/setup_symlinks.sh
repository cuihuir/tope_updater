#!/bin/bash
# setup_symlinks.sh - 设置服务符号链接
#
# 此脚本创建符号链接，将服务二进制文件指向版本快照目录。
# 这样可以快速切换版本而无需修改服务配置。
#
# 使用方法:
#   sudo ./setup_symlinks.sh
#
# 目录结构:
#   /opt/tope/versions/
#   ├── current -> v1.0.0/          (当前版本)
#   ├── previous -> v0.9.0/         (上一版本)
#   └── factory -> v1.0.0/          (出厂版本)
#
# 符号链接:
#   /usr/local/bin/device-api -> /opt/tope/versions/current/bin/device-api
#   /usr/local/bin/web-server -> /opt/tope/versions/current/bin/web-server
#   /opt/tope/services/device-api -> /opt/tope/versions/current/device-api

set -e

VERSIONS_BASE="/opt/tope/versions"
CURRENT_LINK="$VERSIONS_BASE/current"
BIN_DIR="/usr/local/bin"
SERVICES_DIR="/opt/tope/services"

echo "=========================================="
echo "设置服务符号链接"
echo "=========================================="
echo "版本基础目录: $VERSIONS_BASE"
echo "当前版本链接: $CURRENT_LINK"
echo ""

# 检查是否以 root 权限运行
if [ "$EUID" -ne 0 ]; then
    echo "错误: 此脚本需要 root 权限运行"
    echo "请使用: sudo $0"
    exit 1
fi

# 检查 current 符号链接是否存在
if [ ! -L "$CURRENT_LINK" ]; then
    echo "错误: current 符号链接不存在"
    echo "请确保已创建版本快照并设置 current 链接"
    exit 1
fi

# 解析 current 指向的实际版本
CURRENT_VERSION=$(readlink -f "$CURRENT_LINK")
echo "当前版本: $CURRENT_VERSION"

# 检查当前版本目录是否存在
if [ ! -d "$CURRENT_VERSION" ]; then
    echo "错误: 当前版本目录不存在: $CURRENT_VERSION"
    exit 1
fi

# 创建 /usr/local/bin 下的符号链接
echo "创建 /usr/local/bin 下的符号链接..."

mkdir -p "$BIN_DIR"

# 遍历当前版本的 bin 目录
if [ -d "$CURRENT_VERSION/bin" ]; then
    for binary in "$CURRENT_VERSION/bin"/*; do
        if [ -f "$binary" ]; then
            binary_name=$(basename "$binary")
            symlink_path="$BIN_DIR/$binary_name"

            # 删除旧链接（如果存在）
            if [ -L "$symlink_path" ]; then
                rm -f "$symlink_path"
            fi

            # 创建新链接
            ln -s "$binary" "$symlink_path"
            echo "  ✓ $binary_name -> $binary"
        fi
    done
else
    echo "  警告: 当前版本没有 bin 目录"
fi

# 创建 /opt/tope/services 下的符号链接
echo ""
echo "创建 /opt/tope/services 下的符号链接..."

mkdir -p "$SERVICES_DIR"

# 遍历当前版本的服务目录
for service_dir in "$CURRENT_VERSION"/*; do
    if [ -d "$service_dir" ]; then
        service_name=$(basename "$service_dir")
        symlink_path="$SERVICES_DIR/$service_name"

        # 删除旧链接（如果存在）
        if [ -L "$symlink_path" ]; then
            rm -f "$symlink_path"
        fi

        # 创建新链接
        ln -s "$service_dir" "$symlink_path"
        echo "  ✓ $service_name -> $service_dir"
    fi
done

echo ""
echo "=========================================="
echo "验证符号链接"
echo "=========================================="

# 验证符号链接
verify_symlink() {
    local symlink=$1
    local description=$2

    if [ -L "$symlink" ]; then
        target=$(readlink -f "$symlink")
        echo "✓ $description: $symlink -> $target"
        return 0
    else
        echo "✗ $description: $symlink (不存在)"
        return 1
    fi
}

# 验证关键符号链接
verify_count=0

# 验证 bin 目录链接
for symlink in "$BIN_DIR"/*; do
    if [ -L "$symlink" ]; then
        verify_symlink "$symlink" "二进制文件"
        verify_count=$((verify_count + 1))
    fi
done

# 验证 services 目录链接
for symlink in "$SERVICES_DIR"/*; do
    if [ -L "$symlink" ]; then
        verify_symlink "$symlink" "服务目录"
        verify_count=$((verify_count + 1))
    fi
done

echo ""
echo "=========================================="
echo "✓ 符号链接设置完成！"
echo "=========================================="
echo "创建的符号链接数量: $verify_count"
echo ""
echo "符号链接已指向当前版本: $CURRENT_VERSION"
echo ""
echo "切换版本时，只需更新 current 符号链接："
echo "  ln -sfn /opt/tope/versions/v1.1.0 /opt/tope/versions/current"
echo ""
echo "然后重启服务即可："
echo "  systemctl restart device-api"
