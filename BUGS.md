# Bug 跟踪清单

**项目**: tope_updater (TOP.E OTA Updater)
**创建日期**: 2026-01-14
**维护团队**: 测试团队
**说明**: 本文档记录测试过程中发现的所有bug，由开发团队负责修复

---

## 📋 Bug 统计

| 状态 | 数量 |
|------|------|
| 🔴 待修复 (Open) | 0 |
| 🟡 进行中 (In Progress) | 0 |
| 🟢 已修复 (Fixed) | 0 |
| ⚫ 已关闭 (Closed) | 1 |
| **总计** | **1** |

---

## 🔴 待修复 Bug (Open)

_暂无_

---

## 🟡 进行中 Bug (In Progress)

_暂无_

---

## 🟢 已修复 Bug (Fixed)

_暂无_

---

## ⚫ 已关闭 Bug (Closed)

### BUG-001: download.py 中 expected_from_server 变量未初始化

**严重程度**: 🔴 High (高) → ⚫ Closed
**发现日期**: 2026-01-14
**修复日期**: 2026-01-14
**验证日期**: 2026-01-14
**发现者**: 测试团队 (单元测试)
**修复者**: Claude Code
**发现位置**: `tests/unit/test_download.py::test_download_network_error`
**状态**: ⚫ Closed (已修复并验证)

#### 问题描述
当网络请求失败且服务器未返回 `Content-Length` 头时，`expected_from_server` 变量未被初始化，导致抛出 `UnboundLocalError` 而不是预期的异常。

#### 代码位置
- **文件**: `src/updater/services/download.py`
- **函数**: `_download_with_resume()`
- **原问题行号**: 207, 254

#### 根本原因
变量 `expected_from_server` 在 `async with client.stream(...)` 块内部声明（原 line 207），但在该块外部使用（原 line 254）。当网络错误发生在进入 stream 块之前，该变量未被声明就被使用。

#### 修复方案
在函数开始处（在 headers 之前）初始化变量：

**修复前** (line 206-207):
```python
async with httpx.AsyncClient(timeout=30.0) as client:
    async with client.stream("GET", url, headers=headers) as response:
        response.raise_for_status()

        # Get Content-Length from server (if available)
        content_length_header = response.headers.get("Content-Length")
        expected_from_server = None  # ❌ 在 stream 块内部
```

**修复后** (line 197-199):
```python
# Initialize variables before try/catch to avoid UnboundLocalError
# FIX for BUG-001: Initialize before async with block
expected_from_server = None  # ✅ 在函数开始处

headers = {}
if bytes_downloaded > 0:
    headers["Range"] = f"bytes={bytes_downloaded}-"

async with httpx.AsyncClient(timeout=30.0) as client:
    async with client.stream("GET", url, headers=headers) as response:
        response.raise_for_status()

        # Get Content-Length from server (if available)
        content_length_header = response.headers.get("Content-Length")
        if content_length_header:
            expected_from_server = int(content_length_header)
            # ...
```

#### 修复验证
- ✅ 代码编译通过，无语法错误
- ✅ 单元测试 `test_download_network_error` 通过
- ✅ 网络错误场景正确抛出 httpx.RequestError，UnboundLocalError 已修复

#### 影响范围
- 修复前：网络错误导致 `UnboundLocalError`，掩盖真实错误
- 修复后：网络错误正确抛出 `httpx.RequestError`，便于调试
- 不影响正常下载流程（只影响错误场景）

#### 相关测试
- **测试文件**: `tests/unit/test_download.py`
- **测试用例**: `test_download_network_error`
- **操作**: 测试通过，验证完成

#### 提交记录
- Commit hash: 1c2ecbf
- Commit message: "fix: 修复 download.py 中 expected_from_server 未初始化的 bug (BUG-001)"

---

## 📝 Bug 报告模板

当发现新 bug 时，请按以下格式添加：

```markdown
### BUG-XXX: [简短描述]

**严重程度**: 🔴 High / 🟡 Medium / 🟢 Low  
**发现日期**: YYYY-MM-DD  
**发现者**: [发现者/团队]  
**发现位置**: [测试文件::测试方法]  
**状态**: 🔴 Open / 🟡 In Progress / 🟢 Fixed / ⚫ Closed

#### 问题描述
[详细描述问题]

#### 代码位置
- **文件**: path/to/file.py
- **函数**: function_name()
- **行号**: XX

#### 重现步骤
1. 步骤1
2. 步骤2
3. ...

#### 当前代码
\`\`\`python
# 有问题的代码
\`\`\`

#### 根本原因
[分析根本原因]

#### 预期行为
[描述期望的正确行为]

#### 建议修复方案
\`\`\`python
# 建议的修复代码
\`\`\`

#### 影响范围
[描述影响范围和严重性]

#### 相关测试
- **测试文件**: path/to/test.py
- **测试用例**: test_name
- **当前状态**: Pass / Fail / Skip

#### 备注
[其他补充信息]
```

---

## 🎯 严重程度定义

| 级别 | 图标 | 定义 | 示例 |
|------|------|------|------|
| **Critical** | 💀 | 导致系统崩溃或数据丢失 | 核心功能完全失效 |
| **High** | 🔴 | 严重影响功能，无替代方案 | 主要功能失效 |
| **Medium** | 🟡 | 影响功能但有变通方案 | 边界情况失效 |
| **Low** | 🟢 | 小问题，不影响主要功能 | UI问题、日志错误 |

---

## 📊 Bug 生命周期

```
🔴 Open (待修复)
    ↓
🟡 In Progress (进行中) ← 开发团队认领
    ↓
🟢 Fixed (已修复) ← 开发团队完成修复
    ↓
✅ Verified (已验证) ← 测试团队验证
    ↓
⚫ Closed (已关闭)
```

---

## 📌 工作流程

### 测试团队职责
1. ✅ 发现并记录 bug（添加到本文档）
2. ✅ 提供详细的重现步骤和代码位置
3. ✅ 编写失败或跳过的测试用例
4. ✅ 更新 bug 统计

### 开发团队职责
1. 🔧 认领 bug（状态改为 In Progress）
2. 🔧 修复代码
3. 🔧 更新状态为 Fixed
4. 🔧 通知测试团队验证

### 协作流程
```
测试发现 → 记录BUGS.md → 开发认领 → 修复代码 → 测试验证 → 关闭Bug
```

---

## 📅 更新记录

| 日期 | 操作 | 说明 |
|------|------|------|
| 2026-01-14 | 创建文档 | 初始化 bug 跟踪系统 |
| 2026-01-14 | 添加 BUG-001 | download.py expected_from_server 未初始化 |
| 2026-01-14 | 修复 BUG-001 | 在函数开始处初始化 expected_from_server 变量 |

---

## 🔗 相关文档

- [测试指南](specs/001-updater-core/testing-guide.md)
- [测试基础设施总结](TESTING_SETUP_SUMMARY.md)
- [下载测试总结](DOWNLOAD_TEST_SUMMARY.md)
- [任务清单](specs/001-updater-core/tasks.md)

---

**维护说明**: 
- 测试团队发现 bug 时，立即添加到本文档
- 每个 bug 必须有唯一编号 (BUG-XXX)
- 定期更新 bug 统计和状态
- 已关闭的 bug 保留记录，便于追溯

**最后更新**: 2026-01-14
