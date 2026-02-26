#!/bin/bash
# 手工测试脚本：版本快照和回滚机制

# 不使用 set -e，手动处理错误

echo "=========================================="
echo "TOP.E OTA Updater 手工测试"
echo "=========================================="
echo ""

# 颜色定义
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 测试结果
TESTS_PASSED=0
TESTS_FAILED=0

# 辅助函数
check_status() {
    local expected=$1
    local actual=$(curl -s http://localhost:12315/api/v1.0/progress | python3 -m json.tool | grep '"stage"' | cut -d'"' -f4)
    if [ "$actual" == "$expected" ]; then
        echo -e "${GREEN}✓${NC} 状态正确: $actual"
        ((TESTS_PASSED++))
        return 0
    else
        echo -e "${RED}✗${NC} 状态错误: 期望 $expected, 实际 $actual"
        ((TESTS_FAILED++))
        return 1
    fi
}

print_progress() {
    echo ""
    echo -e "${YELLOW}>>> $1${NC}"
    curl -s http://localhost:12315/api/v1.0/progress | python3 -m json.tool | grep -E '"stage"|"progress"|"message"'
    echo ""
}

# 测试 1: 检查服务状态
echo "测试 1: 检查服务状态"
echo "----------------------------"
check_status "idle"
echo ""

# 测试 2: 下载小文件
echo "测试 2: 下载小文件 (468 bytes)"
echo "----------------------------"
curl -s -X POST http://localhost:12315/api/v1.0/download \
  -H "Content-Type: application/json" \
  -d '{
    "version": "1.0.0",
    "package_url": "http://localhost:8888/test-update-1.0.0.zip",
    "package_name": "test-update-1.0.0.zip",
    "package_size": 468,
    "package_md5": "600aff0f78265dd25bb6907828f916dd"
  }' | python3 -m json.tool

sleep 2
print_progress "下载完成后状态"
check_status "toInstall"
echo ""

# 测试 3: 查看下载的文件
echo "测试 3: 验证下载的文件"
echo "----------------------------"
if [ -f "tmp/test-update-1.0.0.zip" ]; then
    echo -e "${GREEN}✓${NC} 文件存在"
    ls -lh tmp/test-update-1.0.0.zip
    echo "MD5:"
    md5sum tmp/test-update-1.0.0.zip
    ((TESTS_PASSED++))
else
    echo -e "${RED}✗${NC} 文件不存在"
    ((TESTS_FAILED++))
fi
echo ""

# 测试 4: 查看版本快照目录
echo "测试 4: 检查版本快照目录"
echo "----------------------------"
echo "当前版本目录结构:"
ls -la /opt/tope/versions/ 2>/dev/null || echo "目录不存在或为空"
echo ""

# 总结
echo "=========================================="
echo "测试总结"
echo "=========================================="
echo -e "通过: ${GREEN}$TESTS_PASSED${NC}"
echo -e "失败: ${RED}$TESTS_FAILED${NC}"
echo ""

if [ $TESTS_FAILED -eq 0 ]; then
    echo -e "${GREEN}✓ 所有测试通过！${NC}"
    exit 0
else
    echo -e "${RED}✗ 有测试失败${NC}"
    exit 1
fi
