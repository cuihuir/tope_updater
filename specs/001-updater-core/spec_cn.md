# 功能规格说明：Updater 核心 OTA 程序

**功能分支**: `001-updater-core`
**创建时间**: 2025-11-25
**状态**: 草稿
**输入**: 用户描述："实现 updater 核心 OTA 更新程序"

## 澄清事项

### 2025-11-26 会议

- Q: updater 如何向 device-api 和 ota-gui 报告实时进度？ → A: 混合模式 - updater 每 5% 向 device-api POST 进度回调，ota-gui 每 500ms 轮询 updater 的 GET /progress 端点
- Q: updater 应使用哪个 Python HTTP 服务器框架？ → A: FastAPI + uvicorn（现代异步框架，约 15-20 个包）
- Q: HTTP 端口配置应该硬编码还是可配置？ → A: 硬编码 - device-api:9080, updater:12315（冲突时启动失败）
- Q: updater 应如何作为服务部署和管理？ → A: systemd 服务（开机自启动，失败时自动重启）
- Q: updater 应该暴露哪些 HTTP 端点？ → A: 独立端点 - POST /api/v1.0/download, POST /api/v1.0/update, GET /api/v1.0/progress

## 用户场景与测试 *(必填)*

### 用户故事 1 - 基础更新流程 (优先级: P1)

当 device-api 触发 OTA 更新时，updater 程序必须从云存储下载更新包，验证其完整性，根据 manifest 部署文件，并安全地重启受影响的服务以完成更新。

**优先级原因**: 这是最小可行的 OTA 能力。没有它，就无法向现场设备交付任何更新。

**独立测试**: 可以通过提供有效的更新包 URL 和 manifest 进行完整测试，验证 updater 下载文件、检查 MD5、将文件部署到目标位置，并成功重启服务。

**验收场景**:

1. **假设** device-api POST 到 `/api/v1.0/download` 包含包 URL 和 MD5，**当** updater 下载完整包时，**则** updater 验证 MD5 匹配并在进度端点设置 stage 为 "success"
2. **假设** 有效的更新包已下载并验证，**当** device-api POST 到 `/api/v1.0/update` 时，**则** updater 提取 manifest，将所有文件部署到目标路径，并重启指定的服务
3. **假设** 所有文件部署成功，**当** updater 完成更新时，**则** updater POST 最终成功状态到 device-api 并清理临时文件

---

### 用户故事 2 - 可恢复下载（断点续传） (优先级: P2)

当网络连接不可靠或在下载过程中中断时，updater 必须支持从上次成功位置恢复下载，而不是从头开始。

**优先级原因**: 设备在 WiFi/蜂窝网络上运行，经常中断。可恢复下载减少带宽浪费并缩短网络条件差时的更新时间。

**独立测试**: 可以通过模拟下载中途网络中断进行测试，验证 updater 保存进度，并在重新连接时从相同字节位置恢复。

**验收场景**:

1. **假设** 下载进度在 50%，**当** 网络断开时，**则** updater 将当前字节位置保存到状态文件
2. **假设** 存在具有有效状态文件的部分下载，**当** updater 重新开始下载时，**则** updater 发送 HTTP Range 头并从保存的位置恢复
3. **假设** 恢复的下载完成，**当** updater 验证 MD5 时，**则** MD5 匹配预期值，确认成功恢复

---

### 用户故事 3 - 原子文件部署 (优先级: P2)

在部署更新的文件时，updater 必须确保原子文件替换，以防止在部署期间断电导致状态损坏。

**优先级原因**: OTA 期间断电可能会导致设备变砖，如果文件部分写入。原子操作确保系统始终处于一致状态。

**独立测试**: 可以通过模拟文件部署期间断电进行测试，验证目标文件保持不变（旧版本）或完全更新（新版本），绝不会部分写入。

**验收场景**:

1. **假设** 更新的文件准备部署，**当** updater 首先写入临时文件时，**则** updater 在提交前验证临时文件的 MD5
2. **假设** 临时文件已验证，**当** updater 使用原子重命名操作时，**则** 目标文件在单个文件系统操作中被替换
3. **假设** 部署在重命名前中断，**当** 系统重启时，**则** 目标文件包含原始版本（无损坏）

---

### 用户故事 4 - 安全的进程控制 (优先级: P2)

在更新 device-api 或 voice-app 等服务时，updater 必须在文件替换前优雅地终止进程，并在之后以正确的依赖顺序重启它们。

**优先级原因**: 强制杀死进程可能会损坏应用程序状态或导致资源锁定。优雅关闭确保干净的状态转换。

**独立测试**: 可以通过监控进程终止信号和时序进行测试，验证首先发送 SIGTERM，超时后再发送 SIGKILL，并且服务按依赖顺序重启。

**验收场景**:

1. **假设** 服务需要更新，**当** updater 终止进程时，**则** updater 发送 SIGTERM 并等待 10 秒优雅关闭
2. **假设** 进程在超时内未响应 SIGTERM，**当** 超时到期时，**则** updater 发送 SIGKILL 强制终止
3. **假设** 所有服务已终止并部署文件，**当** updater 重启服务时，**则** updater 首先启动 device-api，然后按依赖顺序启动其他服务

---

### 用户故事 5 - 启动自愈 (优先级: P3)

当 updater 启动并发现上次执行的未完成操作（由于崩溃或断电）时，它必须验证状态并适当地恢复或重试。

**优先级原因**: 现场设备会经历断电和崩溃。自愈减少了人工干预和支持负担。

**独立测试**: 可以通过在操作中途停止 updater 进行测试，验证状态文件存在，重启 updater，并确认它检测到不完整状态并正确恢复。

**验收场景**:

1. **假设** updater 启动时有部分下载状态文件，**当** updater 检查状态文件完整性时，**则** updater 从保存的位置恢复下载
2. **假设** 状态文件指示 MD5 验证之前失败，**当** updater 重启时，**则** updater 删除损坏的文件并从头重新下载
3. **假设** 状态文件指示部署失败，**当** updater 重启时，**则** updater 尝试回滚到以前的版本（如果存在备份）

---

### 用户故事 6 - 状态上报 (优先级: P3)

在整个更新过程中，updater 必须通过 HTTP 回调向 device-api 报告当前状态（阶段、进度、错误），并提供进度端点供 ota-gui 轮询。

**优先级原因**: 用户和云端需要了解更新进度。基于 HTTP 的状态上报实现清晰的服务边界下的实时监控。

**独立测试**: 可以通过监控到 device-api 的 HTTP 回调和轮询 updater 的进度端点进行测试，验证 JSON 格式、阶段名称、进度百分比和错误消息与 updater 的实际状态匹配。

**验收场景**:

1. **假设** updater 开始下载，**当** 进度达到 25% 时，**则** updater POST 到 device-api `/api/v1.0/ota/report` 包含 `{"stage":"downloading","progress":25,"message":"正在下载...","error":null}`
2. **假设** ota-gui 轮询 updater 的 `/api/v1.0/progress` 端点，**当** 下载在 45% 时，**则** updater 返回 `{"stage":"downloading","progress":45,"message":"正在下载...","error":null}`
3. **假设** updater 遇到 MD5 不匹配，**当** 验证失败时，**则** updater POST 到 device-api 包含 `{"stage":"failed","progress":100,"message":"","error":"MD5_MISMATCH: expected abc123, got def456"}`

---

### 用户故事 7 - 可选的 GUI 启动 (优先级: P4)

当 updater 开始 OTA 过程时，它可以选择性地启动 ota-gui 程序以显示全屏进度界面，但 GUI 失败不能阻止 updater 完成更新。

**优先级原因**: GUI 通过显示进度和防止混淆改善用户体验，但 updater 必须在无头设备或 GUI 失败时可靠地工作。

**独立测试**: 可以通过在有和没有 ota-gui 的情况下运行 updater 进行测试，验证两种情况下更新都成功，并且在可用时 GUI 显示状态。

**验收场景**:

1. **假设** ota-gui 二进制文件存在于 `/opt/tope/ota-gui`，**当** updater 启动时，**则** updater 启动 ota-gui 进程并继续，无论启动是否成功
2. **假设** ota-gui 二进制文件不存在，**当** updater 启动时，**则** updater 记录警告并继续无 GUI 更新
3. **假设** ota-gui 在更新期间崩溃，**当** updater 检测到崩溃时，**则** updater 继续更新并成功完成

---

### 边界情况

- **下载期间磁盘空间不足时会发生什么？** Updater 检测到磁盘已满错误，向 device-api 报告 `DISK_FULL` 错误，中止更新而不重试，并清理部分下载。

- **manifest.json 格式错误或缺失时会发生什么？** Updater 在提取后验证 manifest 结构，如果解析失败则报告 `INVALID_MANIFEST` 错误，并中止更新。

- **部署的目标目录不存在时会发生什么？** Updater 在部署前以适当的权限（0755）创建缺失的目录。

- **即使使用 SIGKILL 也无法杀死服务进程时会发生什么？** Updater 报告 `PROCESS_KILL_FAILED` 错误，记录进程 ID 和名称，但继续处理其他模块（部分更新）。

- **设备在原子重命名操作期间断电时会发生什么？** 文件系统保证 rename() 的原子性 - 目标文件将包含旧版本（重命名未完成）或新版本（重命名已完成）。Updater 在下次启动时进行验证。

- **HTTP 下载返回 404 或 5xx 错误时会发生什么？** Updater 使用指数退避（1s、2s、4s）重试下载，最多 3 次尝试，然后报告 `DOWNLOAD_FAILED` 错误。

- **状态文件损坏时会发生什么？** Updater 在加载时验证状态文件 JSON，丢弃损坏的状态，并视为全新开始（从头重新下载）。

## 需求 *(必填)*

### 功能需求

- **FR-001**: Updater 必须在端口 12315 运行 HTTP 服务器，并暴露三个端点：POST `/api/v1.0/download`（触发包下载）、POST `/api/v1.0/update`（触发安装）、GET `/api/v1.0/progress`（查询当前状态）。如果端口 12315 已被占用，服务器必须启动失败。
- **FR-001a**: POST `/api/v1.0/download` 端点必须接受 JSON 负载，包含字段：`version`（字符串）、`package_url`（字符串）、`package_name`（字符串）、`package_size`（整数字节）、`package_md5`（字符串）。端点必须立即返回 200 OK 并在后台启动下载。端点必须是幂等的 - 如果相同 package_url 的 state.json 存在，则恢复现有下载。
- **FR-001b**: POST `/api/v1.0/update` 端点必须接受 JSON 负载，包含字段：`version`（字符串）。端点必须在开始安装前验证已下载的包存在且 MD5 匹配。端点必须立即返回 200 OK 并在后台启动安装。如果下载未完成或另一个操作正在进行，端点必须返回 409 Conflict。
- **FR-001c**: GET `/api/v1.0/progress` 端点必须返回 JSON，包含字段：`stage`（字符串枚举：idle/downloading/verifying/toInstall/installing/rebooting/success/failed）、`progress`（整数 0-100）、`message`（字符串）、`error`（字符串或 null）。端点必须在 100ms 内响应。
- **FR-002**: Updater 必须使用标准库 HTTP 客户端通过 HTTP/HTTPS URL 从 S3 兼容存储下载包
- **FR-003**: Updater 必须通过发送 Range 头并在持久状态文件 `./tmp/state.json` 中跟踪字节位置来实现基于 HTTP Range 的可恢复下载
- **FR-004**: Updater 必须计算下载包的 MD5 哈希并与提供的 MD5 值逐字节比较
- **FR-005**: Updater 必须在验证失败时中止更新并报告 `MD5_MISMATCH` 错误，然后删除损坏的文件
- **FR-006**: Updater 必须使用标准库归档函数提取下载的 ZIP 包
- **FR-007**: Updater 必须从包根目录解析 manifest.json 以提取版本、模块列表、源路径和目标路径
- **FR-008**: Updater 必须验证所有目标路径以防止目录遍历攻击（拒绝包含 `..` 或允许目录之外的绝对路径的路径）
- **FR-009**: Updater 必须在部署文件前以权限 0755 创建缺失的目标目录
- **FR-010**: Updater 必须通过写入临时文件（例如 `target.tmp`）、验证 MD5，然后使用 `rename()` 系统调用来原子地部署文件
- **FR-011**: Updater 必须在替换前维护关键文件的备份以启用回滚
- **FR-012**: Updater 必须通过发送 SIGTERM、等待 10 秒，然后如果仍在运行则发送 SIGKILL 来终止进程
- **FR-013**: Updater 必须在部署文件前通过检查 `/proc/<pid>` 消失来验证进程终止
- **FR-014**: Updater 必须按 manifest 指定的依赖顺序重启服务（device-api 在其他服务之前）
- **FR-015**: Updater 必须在 `http://localhost:12315/api/v1.0/progress` 暴露 HTTP GET 端点，返回 JSON：`{"stage":"<stage>","progress":<0-100>,"message":"<msg>","error":"<err>"}` 供 ota-gui 轮询
- **FR-016**: Updater 必须在下载期间每 5% 进度和每个主要阶段转换时 POST 状态更新到 device-api 端点 `http://localhost:9080/api/v1.0/ota/report`，JSON 负载：`{"stage":"<stage>","progress":<0-100>,"message":"<msg>","error":"<err>"}`
- **FR-017**: Updater 必须将所有关键操作（下载开始/完成、MD5 结果、部署操作、进程控制、错误）记录到 `./logs/updater.log`（相对于 updater 工作目录）
- **FR-018**: Updater 必须在日志文件大小超过 10MB 时轮转日志文件，保留最后 3 次轮转
- **FR-019**: Updater 必须在所有日志条目中包含 ISO 8601 时间戳和日志级别（DEBUG/INFO/WARN/ERROR）
- **FR-020**: Updater 必须通过 HTTP POST 到 `http://localhost:9080/api/v1.0/ota/report` 向 device-api 报告错误，在 error 字段包含错误代码和描述性消息
- **FR-021**: Updater 必须通过将下载流式传输到磁盘（不在 RAM 中缓冲整个文件）来限制内存使用
- **FR-022**: Updater 必须在二进制文件存在时通过执行 `/opt/tope/ota-gui` 来可选地启动 ota-gui
- **FR-023**: Updater 必须在 ota-gui 缺失、启动失败或崩溃时继续 OTA 过程（非阻塞）
- **FR-024**: Updater 必须在启动时通过验证状态文件的存在性和内容来检查未完成的操作
- **FR-025**: Updater 必须在状态文件指示具有有效字节位置的部分下载时恢复未完成的下载
- **FR-026**: Updater 必须在状态文件指示 MD5 失败或损坏的部分下载时从头重新下载
- **FR-027**: Updater 必须在部署失败时尝试回滚，恢复备份文件并报告 `DEPLOYMENT_FAILED` 错误
- **FR-028**: Updater 必须在成功完成更新后清理临时文件（ZIP 包、提取的文件、状态文件）
- **FR-029**: Updater 必须最小化第三方依赖，仅使用：FastAPI（异步 HTTP 服务器）、uvicorn（ASGI 服务器）、httpx（异步 HTTP 客户端）和 Python 标准库。理由：FastAPI 的异步模型防止并发操作（下载 + 进度轮询）期间的阻塞，满足 Constitution 原则 II 的性能/兼容性例外条款。
- **FR-030**: Updater 必须通过在关闭前完成当前原子操作来优雅地处理 SIGTERM
- **FR-031**: Updater 必须在启动时创建 `./tmp/` 和 `./logs/` 目录（权限 0755），如果它们不存在
- **FR-032**: Updater 必须在备份操作前创建 `./backups/` 目录（权限 0755），如果它不存在
- **FR-033**: Updater 必须作为 systemd 服务单元部署，类型为 Type=simple，失败时自动重启（Restart=always），依赖于 network.target（After=network.target）
- **FR-034**: Updater systemd 服务必须以 root 用户运行，以启用进程控制（SIGTERM/SIGKILL）和文件部署到系统目录
- **FR-035**: MD5 校验成功后，updater 必须转换到 `toInstall` 阶段，并在 state.json 中记录校验时间戳（`verified_at`）。Updater 必须保持在 `toInstall` 阶段直到收到 POST `/api/v1.0/update` 请求。
- **FR-036**: 开始安装前（POST `/api/v1.0/update`），updater 必须通过检查 `(当前时间 - verified_at) < 24小时` 来验证包的信任窗口。如果过期，updater 必须返回应用层状态码 410 并附带错误 `PACKAGE_EXPIRED`，删除包文件和 state.json，并要求重新下载。

### 关键实体

- **更新包**: 包含 manifest.json、模块目录和要部署的二进制文件的 ZIP 归档。存储在 S3 上，带有预签名 URL 用于下载。

- **Manifest**: 嵌入在包根目录中的 JSON 文件（`manifest.json`），定义版本字符串和模块数组，包含名称、源路径（ZIP 中相对路径）和目标路径（设备上绝对路径）。

- **状态状态**: 内存中的 JSON 结构，包含当前阶段（idle/downloading/verifying/installing/rebooting/success/failed）、进度百分比（0-100）、人类可读消息和错误对象（代码 + 消息，如果失败）。通过 HTTP GET `/api/v1.0/progress` 端点暴露供 ota-gui 轮询，并通过 HTTP POST `/api/v1.0/ota/report` 回调推送到 device-api。

- **状态持久化文件**: `./tmp/state.json`（相对于 updater 工作目录）的 JSON 文件，包含跨重启的持久状态：下载 URL、字节位置、总大小、MD5 哈希、上次更新时间戳。此文件在重启后保留，用于可恢复下载。

- **模块**: 要更新的单个软件组件（例如，device-api、voice-app、klippy），在 manifest 中定义，包含源路径和目标路径。

- **Updater HTTP API**: 在端口 12315 暴露的 REST API，有三个端点：(1) POST `/api/v1.0/download` - 触发异步下载，负载 `{version, package_url, package_name, package_size, package_md5}`，立即返回 200 OK；(2) POST `/api/v1.0/update` - 触发异步安装，负载 `{version}`，返回 200 OK 或 409 Conflict；(3) GET `/api/v1.0/progress` - 查询当前状态，在 100ms 内返回 `{stage, progress, message, error}`。

## 成功标准 *(必填)*

### 可衡量的结果

- **SC-001**: Updater 在具有有效包和工作网络的情况下，以 100% 的成功率下载、验证和部署更新包
- **SC-002**: Updater 在 100% 的网络中断情况下从精确字节位置恢复中断的下载
- **SC-003**: Updater 完成原子文件部署，在 1000 次部署周期中模拟断电测试时零文件损坏案例
- **SC-004**: Updater 在 10 秒内优雅地终止 95% 的进程（使用 SIGTERM），其余 5% 需要 SIGKILL
- **SC-005**: Updater 在检测后 5 秒内检测并报告所有故障场景（MD5 不匹配、磁盘已满、无效 manifest、下载失败），并提供适当的错误代码
- **SC-006**: Updater 在进度变化后 500ms 内发送 HTTP 回调到 device-api，并在 100ms 内响应 ota-gui 进度端点查询，实现实时监控
- **SC-007**: Updater 在 100% 的启动情况下自愈未完成的操作（当状态文件有效时）
- **SC-008**: Updater 在 100% 的 ota-gui 缺失或崩溃情况下继续并成功完成更新
- **SC-009**: Updater 在峰值操作期间（同时下载 + 提取）消耗少于 50MB RAM
- **SC-010**: Updater 在 10Mbps 网络上为 100MB 包完成完整更新周期（下载 + 验证 + 部署 + 重启）在 5 分钟内
