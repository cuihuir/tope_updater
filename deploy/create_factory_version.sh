#!/bin/bash
# create_factory_version.sh - 创建出厂版本的安装脚本
#
# 此脚本用于在首次部署时创建出厂版本（factory version）。
# 应该在系统首次安装后运行一次。
#
# 使用方法:
#   sudo ./create_factory_version.sh <version>
#
# 示例:
#   sudo ./create_factory_version.sh 1.0.0

set -e

VERSION=${1:-"1.0.0"}
BASE_DIR="/opt/tope/versions"
FACTORY_LINK="$BASE_DIR/factory"
CURRENT_LINK="$BASE_DIR/current"

echo "=========================================="
echo "创建出厂版本 (Factory Version)"
echo "=========================================="
echo "版本: $VERSION"
echo "基础目录: $BASE_DIR"
echo ""

# 检查是否以 root 权限运行
if [ "$EUID" -ne 0 ]; then
    echo "错误: 此脚本需要 root 权限运行"
    echo "请使用: sudo $0 $VERSION"
    exit 1
fi

# 检查当前版本是否存在
if [ ! -L "$CURRENT_LINK" ]; then
    echo "错误: current 符号链接不存在"
    echo "请确保系统已正确安装"
    exit 1
fi

CURRENT_VERSION=$(readlink -f "$CURRENT_LINK")
echo "当前版本: $CURRENT_VERSION"

# 检查出厂版本是否已存在
if [ -L "$FACTORY_LINK" ]; then
    EXISTING_FACTORY=$(readlink -f "$FACTORY_LINK")
    echo "警告: 出厂版本已存在"
    echo "现有版本: $EXISTING_FACTORY"
    echo ""
    read -p "是否要替换现有出厂版本? (yes/no): " confirm

    if [ "$confirm" != "yes" ]; then
        echo "操作已取消"
        exit 0
    fi

    echo "删除现有出厂版本..."
    rm -f "$FACTORY_LINK"
fi

# 复制当前版本到出厂版本目录
FACTORY_DIR="$BASE_DIR/v$VERSION"
echo "复制当前版本到: $FACTORY_DIR"

if [ -d "$FACTORY_DIR" ]; then
    echo "警告: 目标目录已存在，正在删除..."
    rm -rf "$FACTORY_DIR"
fi

cp -r "$CURRENT_VERSION" "$FACTORY_DIR"
echo "✓ 复制完成"

# 创建 factory 符号链接
echo "创建 factory 符号链接..."
ln -s "v$VERSION" "$FACTORY_LINK"
echo "✓ factory -> v$VERSION"

# 设置出厂版本为只读
echo "设置出厂版本为只读..."
find "$FACTORY_DIR" -type f -exec chmod 444 {} \;
find "$FACTORY_DIR" -type d -exec chmod 555 {} \;
echo "✓ 只读权限设置完成"

# 验证
echo ""
echo "=========================================="
echo "验证出厂版本"
echo "=========================================="

if [ ! -L "$FACTORY_LINK" ]; then
    echo "❌ factory 符号链接创建失败"
    exit 1
fi

FACTORY_TARGET=$(readlink -f "$FACTORY_LINK")
echo "出厂版本路径: $FACTORY_TARGET"

if [ ! -d "$FACTORY_TARGET" ]; then
    echo "❌ 出厂版本目录不存在"
    exit 1
fi

FILE_COUNT=$(find "$FACTORY_TARGET" -type f | wc -l)
DIR_COUNT=$(find "$FACTORY_TARGET" -type d | wc -l)

echo "文件数量: $FILE_COUNT"
echo "目录数量: $DIR_COUNT"

if [ "$FILE_COUNT" -eq 0 ]; then
    echo "❌ 出厂版本目录为空"
    exit 1
fi

echo ""
echo "=========================================="
echo "✓ 出厂版本创建成功！"
echo "=========================================="
echo "版本: $VERSION"
echo "路径: $FACTORY_TARGET"
echo "状态: 只读"
echo ""
echo "现在可以使用以下命令回滚到出厂版本:"
echo "  python -c 'from updater.services.version_manager import VersionManager; vm = VersionManager(); vm.rollback_to_factory()'"
