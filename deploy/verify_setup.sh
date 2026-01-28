#!/bin/bash
# verify_setup.sh - 验证符号链接配置
#
# 此脚本检查所有符号链接和版本配置是否正确。
#
# 使用方法:
#   sudo ./verify_setup.sh

set -e

VERSIONS_BASE="/opt/tope/versions"
CURRENT_LINK="$VERSIONS_BASE/current"
PREVIOUS_LINK="$VERSIONS_BASE/previous"
FACTORY_LINK="$VERSIONS_BASE/factory"
BIN_DIR="/usr/local/bin"
SERVICES_DIR="/opt/tope/services"

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 计数器
total_checks=0
passed_checks=0
failed_checks=0

# 检查函数
check() {
    local description=$1
    local command=$2

    total_checks=$((total_checks + 1))

    echo -n "[$total_checks] $description ... "

    if eval "$command" > /dev/null 2>&1; then
        echo -e "${GREEN}✓ PASS${NC}"
        passed_checks=$((passed_checks + 1))
        return 0
    else
        echo -e "${RED}✗ FAIL${NC}"
        failed_checks=$((failed_checks + 1))
        return 1
    fi
}

echo "=========================================="
echo "TOP.E OTA Updater - 配置验证"
echo "=========================================="
echo ""

# 检查版本目录结构
echo "检查版本目录结构..."
check "版本基础目录存在" "[ -d '$VERSIONS_BASE' ]"
check "current 符号链接存在" "[ -L '$CURRENT_LINK' ]"
check "previous 符号链接存在" "[ -L '$PREVIOUS_LINK' ]"
check "factory 符号链接存在" "[ -L '$FACTORY_LINK' ]"

echo ""
echo "检查版本目录内容..."

if [ -L "$CURRENT_LINK" ]; then
    CURRENT_VERSION=$(readlink -f "$CURRENT_LINK")
    check "current 指向的目录存在" "[ -d '$CURRENT_VERSION' ]"

    if [ -d "$CURRENT_VERSION" ]; then
        FILE_COUNT=$(find "$CURRENT_VERSION" -type f | wc -l)
        DIR_COUNT=$(find "$CURRENT_VERSION" -type d | wc -l)

        echo "      当前版本: $CURRENT_VERSION"
        echo "      文件数量: $FILE_COUNT"
        echo "      目录数量: $DIR_COUNT"

        check "当前版本非空" "[ $FILE_COUNT -gt 0 ]"
    fi
fi

echo ""
echo "检查符号链接..."

# 检查二进制文件符号链接
if [ -d "$BIN_DIR" ]; then
    BINARY_LINK_COUNT=0

    for symlink in "$BIN_DIR"/*; do
        if [ -L "$symlink" ]; then
            BINARY_LINK_COUNT=$((BINARY_LINK_COUNT + 1))
        fi
    done

    echo "  二进制文件符号链接: $BINARY_LINK_COUNT"

    if [ $BINARY_LINK_COUNT -gt 0 ]; then
        for symlink in "$BIN_DIR"/*; do
            if [ -L "$symlink" ]; then
                name=$(basename "$symlink")
                target=$(readlink -f "$symlink")

                if [ -e "$target" ]; then
                    echo -e "    ${GREEN}✓${NC} $name -> $target"
                else
                    echo -e "    ${RED}✗${NC} $name -> $target (目标不存在)"
                fi
            fi
        done
    fi
fi

# 检查服务目录符号链接
if [ -d "$SERVICES_DIR" ]; then
    SERVICE_LINK_COUNT=0

    for symlink in "$SERVICES_DIR"/*; do
        if [ -L "$symlink" ]; then
            SERVICE_LINK_COUNT=$((SERVICE_LINK_COUNT + 1))
        fi
    done

    echo "  服务目录符号链接: $SERVICE_LINK_COUNT"

    if [ $SERVICE_LINK_COUNT -gt 0 ]; then
        for symlink in "$SERVICES_DIR"/*; do
            if [ -L "$symlink" ]; then
                name=$(basename "$symlink")
                target=$(readlink -f "$symlink")

                if [ -e "$target" ]; then
                    echo -e "    ${GREEN}✓${NC} $name -> $target"
                else
                    echo -e "    ${RED}✗${NC} $name -> $target (目标不存在)"
                fi
            fi
        done
    fi
fi

echo ""
echo "检查版本切换能力..."

# 检查可以切换到的版本
AVAILABLE_VERSIONS=$(ls -1 "$VERSIONS_BASE" 2>/dev/null | grep "^v" || true)

if [ -z "$AVAILABLE_VERSIONS" ]; then
    echo -e "  ${YELLOW}!${NC} 没有可用的版本目录"
else
    VERSION_COUNT=$(echo "$AVAILABLE_VERSIONS" | wc -l)
    echo "  可用版本数量: $VERSION_COUNT"

    for version in $AVAILABLE_VERSIONS; do
        version_path="$VERSIONS_BASE/$version"
        if [ -d "$version_path" ]; then
            if [ "$version_path" = "$(readlink -f "$CURRENT_LINK" 2>/dev/null)" ]; then
                echo -e "    ${GREEN}→${NC} $version (current)"
            elif [ "$version_path" = "$(readlink -f "$PREVIOUS_LINK" 2>/dev/null)" ]; then
                echo -e "    ${YELLOW}→${NC} $version (previous)"
            elif [ "$version_path" = "$(readlink -f "$FACTORY_LINK" 2>/dev/null)" ]; then
                echo -e "    ${BLUE}→${NC} $version (factory)"
            else
                echo -e "    ${GRAY}→${NC} $version (available)"
            fi
        fi
    done
fi

echo ""
echo "检查出厂版本保护..."

if [ -L "$FACTORY_LINK" ]; then
    FACTORY_DIR=$(readlink -f "$FACTORY_LINK")
    check "factory 版本存在" "[ -d '$FACTORY_DIR' ]"

    if [ -d "$FACTORY_DIR" ]; then
        # 检查是否为只读
        MODE=$(stat -c "%a" "$FACTORY_DIR" | head -c 1)

        if [ "$MODE" = "5" ]; then
            echo -e "  factory 版本: ${GREEN}只读${NC} ($FACTORY_DIR)"
        else
            echo -e "  factory 版本: ${YELLOW}可写${NC} ($FACTORY_DIR)"
        fi
    fi
fi

echo ""
echo "=========================================="
echo "验证总结"
echo "=========================================="
echo "总检查项: $total_checks"
echo -e "通过: ${GREEN}$passed_checks${NC}"
echo -e "失败: ${RED}$failed_checks${NC}"
echo ""

if [ $failed_checks -eq 0 ]; then
    echo -e "${GREEN}✓ 所有检查通过！配置正确。${NC}"
    exit 0
else
    echo -e "${RED}✗ 有 $failed_checks 个检查失败。${NC}"
    echo "请查看上面的详细信息并进行修复。"
    exit 1
fi
