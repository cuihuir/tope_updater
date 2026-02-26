# Bug 跟踪清单

**项目**: tope_updater (TOP.E OTA Updater)
**创建日期**: 2026-01-14
**维护团队**: 测试团队
**说明**: 本文档记录测试过程中发现的所有bug，由开发团队负责修复

---

## 📋 Bug 统计

| 状态 | 数量 |
|------|------|
| 🔴 待修复 (Open) | 1 |
| 🟡 进行中 (In Progress) | 0 |
| 🟢 已修复 (Fixed) | 5 |
| ⚫ 已关闭 (Closed) | 1 |
| **总计** | **7** |

---

## 🔴 待修复 Bug (Open)

### BUG-005: 更新 device-api 自身时 Reporter 无法回调

**严重程度**: 🟢 Low
**发现日期**: 2026-02-26
**发现者**: 真实升级测试
**发现位置**: 升级 device-api 0.0.2 全流程测试
**状态**: 🔴 Open

#### 问题描述
当升级包含 device-api 本身时，updater 的 reporter 在部署阶段无法连接 device-api（All connection attempts failed），导致进度无法实时上报。

#### 根本原因
升级 device-api 时，deploy 流程会先 `systemctl stop device-api`，此后 device-api 进程不再运行，reporter 自然无法连接。这是升级自身服务的固有问题，不是代码 bug。

#### 影响范围
仅影响升级 device-api 本身的场景。升级其他服务时 reporter 应正常工作。

#### 待验证
- ⏳ 升级非 device-api 服务时，reporter 是否能正常上报进度

#### 备注
reporter 失败不阻塞主流程（防御性处理），升级仍然成功完成。

---

## 🟡 进行中 Bug (In Progress)

_暂无_

---

### BUG-006: manifest 未赋值时 perform_two_level_rollback 抛出 UnboundLocalError

**严重程度**: 🔴 High
**发现日期**: 2026-02-26
**修复日期**: 2026-02-26
**发现者**: 真实升级测试（版本目录已存在场景）
**修复者**: Claude Code
**发现位置**: `src/updater/services/deploy.py::deploy_package`
**状态**: 🟢 Fixed

#### 问题描述
当 Step 1（创建版本目录）失败时，`manifest` 变量尚未赋值，但 `except` 块中直接调用 `perform_two_level_rollback(manifest, e)`，导致 `UnboundLocalError: cannot access local variable 'manifest'`。

#### 根本原因
`manifest` 变量在 try 块内部赋值（Step 2），但 except 块无条件使用它。当异常发生在 Step 2 之前时变量未初始化。

#### 修复方案
在 try 块前初始化 `manifest = None`，except 块中判断 `if manifest is not None` 再执行回滚。

---

### BUG-007: GUI fetch_progress 未取 data 层导致 progress 为 None 崩溃

**严重程度**: 🔴 High
**发现日期**: 2026-02-26
**修复日期**: 2026-02-26
**发现者**: GUI 延迟测试
**修复者**: Claude Code
**发现位置**: `src/updater/gui/progress_window.py::fetch_progress`
**状态**: 🟢 Fixed

#### 问题描述
GUI 在安装过程中崩溃退出，`renderer.py` 抛出 `TypeError: unsupported operand type(s) for *: 'int' and 'NoneType'`，导致进度条无法渲染。

#### 根本原因
`/api/v1.0/progress` 返回结构为 `{"code":200, "data": {"stage":..., "progress":...}}`，但 `fetch_progress` 直接返回整个 JSON，`run()` 用 `current_data.get("progress", 0)` 取到的是顶层的 `null` 而非 `data.progress`。

#### 修复方案
```python
# 修复前
return response.json()
# 修复后
return response.json().get("data", {})
```

---

### BUG-002: _start_services 中 'str' object has no attribute 'value' 错误

**严重程度**: 🟡 Medium
**发现日期**: 2026-02-26
**修复日期**: 2026-02-26
**发现者**: 真实升级测试日志
**修复者**: Claude Code
**发现位置**: `src/updater/services/deploy.py::_start_services`
**状态**: 🟢 Fixed

#### 问题描述
`_start_services` 调用 `wait_for_service_status` 时传入字符串 `"active"` 而非 `ServiceStatus.ACTIVE` 枚举，导致比较失败并抛出 `AttributeError: 'str' object has no attribute 'value'`。服务实际已启动成功，但错误被静默吞掉。

#### 代码位置
- **文件**: `src/updater/services/deploy.py`
- **函数**: `_start_services()`
- **行号**: 464

#### 根本原因
`wait_for_service_status` 的 `target_status` 参数类型为 `ServiceStatus` 枚举，但调用时传入了字符串 `"active"`，导致内部 `current_status == target_status` 比较时访问 `.value` 失败。

#### 修复方案
```python
# 修复前
await self.process_manager.wait_for_service_status(
    service_name, target_status="active", timeout=30
)
# 修复后
await self.process_manager.wait_for_service_status(
    service_name, target_status=ServiceStatus.ACTIVE, timeout=30
)
```
同时在 deploy.py 顶部补充导入 `ServiceStatus`。

---

### BUG-003: 安装成功后状态永久停留在 success，不自动重置为 idle

**严重程度**: 🟡 Medium
**发现日期**: 2026-02-26
**修复日期**: 2026-02-26
**发现者**: 真实升级测试
**修复者**: Claude Code
**发现位置**: `src/updater/api/routes.py::_update_workflow`
**状态**: 🟢 Fixed

#### 问题描述
安装完成后状态永久停留在 `success 100%`，不会自动归位到 `idle`，导致下次升级前必须手动重置 state.json。

#### 根本原因
`_update_workflow` 成功后只调用了 `state_manager.delete_state()`（删除持久化文件），未调用 `state_manager.reset()`（重置内存状态）。

#### 修复方案
在 `delete_state()` 后延迟 5 秒再调用 `reset()`，让调用方有足够时间读取到 success 状态。

---

### BUG-004: dst 路径不在 /opt/tope/ 下时文件未实际覆盖目标

**严重程度**: 🔴 High
**发现日期**: 2026-02-26
**修复日期**: 2026-02-26
**发现者**: 真实升级测试
**修复者**: Claude Code
**发现位置**: `src/updater/services/deploy.py::_deploy_module_to_version`
**状态**: 🟢 Fixed

#### 问题描述
manifest 中 `dst` 路径不以 `/opt/tope/` 开头时，文件只被写入版本快照目录（`/opt/tope/versions/vX.Y.Z/...`），未同步到实际目标路径，导致升级后目标文件未更新。

#### 根本原因
`_deploy_module_to_version` 设计上只写版本目录，依赖符号链接指向。但当 `dst` 不在 `/opt/tope/` 下时，没有符号链接机制将文件映射到实际路径。

#### 修复方案
当 `dst` 不以 `/opt/tope/` 开头时，在写入版本目录后额外用 `shutil.copy2` 同步到实际绝对路径。

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
| 2026-02-26 | 添加 BUG-002~005 | 真实升级测试发现 4 个问题 |
| 2026-02-26 | 修复 BUG-002 | deploy.py _start_services 传入 ServiceStatus 枚举 |
| 2026-02-26 | 修复 BUG-003 | 安装成功后 5s 自动 reset 到 idle |
| 2026-02-26 | 修复 BUG-004 | 非 /opt/tope/ 路径同步到实际 dst |

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
