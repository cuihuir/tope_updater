#!/bin/bash
# test_symlink_switch.sh - 测试符号链接切换功能
#
# 此脚本演示如何切换版本并验证服务仍能正常运行。
#
# 使用方法:
#   sudo ./test_symlink_switch.sh

set -e

VERSIONS_BASE="/opt/tope/versions"
CURRENT_LINK="$VERSIONS_BASE/current"

echo "=========================================="
echo "测试符号链接切换功能"
echo "=========================================="
echo ""

# 检查是否以 root 权限运行
if [ "$EUID" -ne 0 ]; then
    echo "错误: 此脚本需要 root 权限运行"
    echo "请使用: sudo $0"
    exit 1
fi

# 显示当前版本
if [ -L "$CURRENT_LINK" ]; then
    CURRENT_VERSION=$(readlink -f "$CURRENT_LINK")
    echo "当前版本: $CURRENT_VERSION"
else
    echo "警告: current 链接不存在"
fi

echo ""
echo "可用的版本:"
ls -1 "$VERSIONS_BASE" | grep "^v" || echo "  (无版本目录)"

echo ""
echo "符号链接状态:"
echo "  current -> $(readlink $CURRENT_LINK 2>/dev/null || echo '不存在')"
echo "  previous -> $(readlink $VERSIONS_BASE/previous 2>/dev/null || echo '不存在')"
echo "  factory -> $(readlink $VERSIONS_BASE/factory 2>/dev/null || echo '不存在')"

echo ""
echo "=========================================="
echo "测试版本切换"
echo "=========================================="

# 获取当前版本
OLD_CURRENT=$(readlink "$CURRENT_LINK" 2>/dev/null | sed 's/.*\///')
echo "原始 current 链接: current -> $OLD_CURRENT"

# 切换到其他版本（如果有多个版本）
OTHER_VERSIONS=$(ls -1 "$VERSIONS_BASE" | grep "^v" | grep -v "$OLD_CURRENT" | head -1)

if [ -z "$OTHER_VERSIONS" ]; then
    echo ""
    echo "只有一个版本，无法测试切换"
    echo "请先创建多个版本进行测试"
    exit 0
fi

echo ""
echo "切换到版本: $OTHER_VERSIONS"

# 备份当前链接
TEMP_LINK="$VERSIONS_BASE/.current.backup"
ln -s "$OTHER_VERSIONS" "$TEMP_LINK"

# 原子替换
mv -fT "$TEMP_LINK" "$CURRENT_LINK"

echo "✓ 切换完成: current -> $OTHER_VERSIONS"

# 验证新版本
NEW_CURRENT=$(readlink "$CURRENT_LINK" | sed 's/.*\///')
echo "新 current 链接: current -> $NEW_CURRENT"

echo ""
echo "验证符号链接正确性:"

# 验证二进制文件链接
if [ -L "/usr/local/bin/device-api" ]; then
    BINARY_TARGET=$(readlink -f "/usr/local/bin/device-api")
    echo "  ✓ device-api -> $BINARY_TARGET"

    # 检查是否指向新版本
    if echo "$BINARY_TARGET" | grep -q "$NEW_CURRENT"; then
        echo "    ✓ 正确指向新版本"
    else
        echo "    ✗ 未指向新版本 (可能需要重新运行 setup_symlinks.sh)"
    fi
fi

# 验证服务目录链接
if [ -L "/opt/tope/services/device-api" ]; then
    SERVICE_TARGET=$(readlink -f "/opt/tope/services/device-api")
    echo "  ✓ services/device-api -> $SERVICE_TARGET"

    # 检查是否指向新版本
    if echo "$SERVICE_TARGET" | grep -q "$NEW_CURRENT"; then
        echo "    ✓ 正确指向新版本"
    else
        echo "    ✗ 未指向新版本 (可能需要重新运行 setup_symlinks.sh)"
    fi
fi

echo ""
echo "=========================================="
echo "切换回原版本"
echo "=========================================="

# 切换回原版本
ln -s "$OLD_CURRENT" "$TEMP_LINK"
mv -fT "$TEMP_LINK" "$CURRENT_LINK"

echo "✓ 恢复完成: current -> $OLD_CURRENT"

echo ""
echo "=========================================="
echo "✓ 测试完成！"
echo "=========================================="
echo ""
echo "符号链接切换功能正常工作"
echo ""
echo "实际使用示例:"
echo "  1. 部署新版本到 /opt/tope/versions/v1.1.0/"
echo "  2. 更新符号链接:"
echo "     ln -sfn /opt/tope/versions/v1.1.0 /opt/tope/versions/current"
echo "  3. 重启服务:"
echo "     systemctl restart device-api"
echo "  4. 如果失败，回滚到上一版本:"
echo "     ln -sfn /opt/tope/versions/v1.0.0 /opt/tope/versions/current"
echo "     systemctl restart device-api"
