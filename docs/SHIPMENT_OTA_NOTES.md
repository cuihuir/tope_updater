# 发货前 OTA 结论记录

**日期**: 2026-05-28
**范围**: beta 发货版本的普通应用/配置 OTA
**当前策略**: 本版本不做 apt/deb/系统包升级能力

本文记录本轮对 `tope_updater` 的能力审视、可靠性优化、真实包测试结果，以及后续 GUI 和系统包升级策略。

## 结论

当前 `tope_updater` 适合承担 beta 设备上的普通 OTA 服务，覆盖以下升级类型：

| 类型 | 当前支持情况 | 说明 |
|------|--------------|------|
| 完整应用升级 | 支持 | 通过版本目录 `/opt/tope/versions/vX.Y.Z` 和 `current/previous/factory` 链接完成原子切换与回滚。 |
| 部分组件升级 | 支持 | OTA 包 `manifest.json` 可只包含需要更新的模块。 |
| 配置文件升级 | 支持 | 例如只升级 `printer.cfg`，建议目标文件通过 `/opt/tope/versions/current` 或符号链接纳入版本体系。 |
| `klipper-5axis` | 支持普通文件/服务升级 | 需要服务 unit 从 `/opt/tope/versions/current` 或稳定符号链接加载。 |
| `device-api` | 支持二进制和配置升级 | 本轮范围为 OTA 二进制和配置，不改 `ota-service`。 |
| `printer-gui` | 支持包部署 | 已用真实 `printer-gui` 包完成下载和部署测试；服务路径还需切到 `/opt/tope/versions/current` 才能真正运行新版本。 |
| `udev_deploy` | 支持文件部署 | 若修改 udev 规则，需要 `post_cmds` 执行 `udevadm control --reload-rules` 等命令。 |
| `moonraker` | 支持普通文件/服务升级 | 同样要求 systemd unit 使用版本化路径。 |
| apt/deb/系统组件 | 本版本不支持 | 不应直接混入普通 OTA 包执行。后续如需要，单独增加系统包安装能力。 |

关键限制：

- `/opt/tope/...` 下的目标路径会进入版本快照，失败后可回滚到 `previous` 或 `factory`。
- 非 `/opt/tope/...` 的目标路径会在部署时做临时备份和原子替换，部署失败会恢复；但成功后的后续版本回滚不天然恢复这些外部路径。因此配置文件最好通过符号链接接入 `/opt/tope/versions/current`。
- systemd 服务必须从稳定入口启动，例如 `/opt/tope/versions/current/services/printer-gui-qml/main.py` 或 `/opt/tope/services/printer-gui-qml/...`，否则 OTA 只会更新文件，不会影响实际运行服务。

## 本轮已完成优化

提交：

```text
d923358 Improve OTA update reliability
```

主要变化：

- 下载包通过 MD5 后，持久化 `toInstall` 状态，设备重启后仍可继续安装。
- `/update` 前重新校验 MD5，避免本地包被破坏后仍部署。
- 部署顺序调整为 `stop -> deploy -> verify -> promote -> start`。
- 服务启动失败会触发回滚。
- 服务重启顺序按 `restart_order` 排序，并对重复服务去重。
- 非 `/opt/tope` 目标文件使用临时文件和原子替换。
- 非版本化外部文件在失败部署时备份并恢复。
- `delete_state()` 即使 state 文件不存在，也会清理内存状态。
- `package_name` 限制为普通 `.zip` 文件名，不能包含路径。
- 下载和上报使用 `trust_env=False`，避免设备环境代理影响 OTA。

验证：

```bash
uv run pytest tests/unit/ -q
uv run ruff check src/ tests/
```

结果：

- 单元测试：224 passed
- 覆盖率：91.38%
- ruff：通过

## OTA 包格式

OTA 包是 zip 文件，根目录必须包含 `manifest.json`。

当前 `modules` 是单文件映射，不是目录递归映射。一个要部署的文件对应一个 module。真实 `printer-gui` 包包含 427 个部署文件，因此 manifest 中也生成了 427 个 module 条目。

最小示例：

```json
{
  "version": "1.2.3",
  "modules": [
    {
      "name": "printer-cfg",
      "src": "configs/printer.cfg",
      "dst": "/opt/tope/services/klipper/config/printer.cfg",
      "process_name": "klipper.service",
      "restart_order": 10
    }
  ]
}
```

字段说明：

| 字段 | 必填 | 说明 |
|------|------|------|
| `version` | 是 | 必须是 `X.Y.Z`，并且与 `/download` 和 `/update` 请求版本一致。 |
| `modules[].name` | 是 | 模块名，包内唯一。 |
| `modules[].src` | 是 | zip 内相对路径，不能以 `/` 开头，不能包含 `..`。 |
| `modules[].dst` | 是 | 设备上的绝对目标路径，不能包含 `..`。 |
| `modules[].process_name` | 否 | 需要停止/启动的 systemd 服务名。 |
| `modules[].restart_order` | 否 | 服务启动顺序，数字越小越先启动。 |
| `modules[].post_cmds` | 否 | 文件部署后的命令列表；任一命令失败会导致部署失败并回滚。 |

`/download` 请求示例：

```json
{
  "version": "1.2.3",
  "package_url": "http://ota.example.com/packages/update-1.2.3.zip",
  "package_name": "update-1.2.3.zip",
  "package_size": 1048576,
  "package_md5": "0123456789abcdef0123456789abcdef"
}
```

`package_name` 必须是普通 zip 文件名，例如 `printer-gui-0.1.1.zip`，不能是路径。

## 制作测试包

通用步骤：

1. 准备一个临时目录。
2. 把要升级的文件放入该目录，例如 `services/printer-gui-qml/...` 或 `configs/printer.cfg`。
3. 在临时目录根部写入 `manifest.json`，每个要部署的文件生成一个 module。
4. 将目录打成 zip。
5. 计算 zip 的 size 和 MD5。
6. 用这些值构造 `/download` 请求。

示例命令：

```bash
cd /tmp/tope_ota_pkg
zip -r /tmp/tope_ota/update-1.2.3.zip manifest.json services configs
stat -c %s /tmp/tope_ota/update-1.2.3.zip
md5sum /tmp/tope_ota/update-1.2.3.zip
```

只升级 `printer.cfg` 的推荐包结构：

```text
printer-cfg-1.2.3.zip
├── manifest.json
└── configs/
    └── printer.cfg
```

对应 manifest：

```json
{
  "version": "1.2.3",
  "modules": [
    {
      "name": "printer-cfg",
      "src": "configs/printer.cfg",
      "dst": "/opt/tope/services/klipper/config/printer.cfg",
      "process_name": "klipper.service",
      "restart_order": 10
    }
  ]
}
```

如果实际 `printer.cfg` 必须位于其它路径，建议让那个路径成为指向 `/opt/tope/versions/current/...` 的符号链接，而不是直接把外部路径作为 `dst`。

## 真实 printer-gui 包测试记录

测试包来自 `/home/tope/project/printer-gui`：

```text
包路径: /tmp/tope_ota/printer-gui-0.1.1-test-20260528.zip
版本: 0.1.1
大小: 30715472
MD5: 760042bed75eb318f0a159e3d557f7ef
模块/文件数: 427
目标路径: /opt/tope/services/printer-gui-qml/...
服务: printer-gui-eglfs.service
```

测试请求：

```json
{
  "version": "0.1.1",
  "package_url": "http://127.0.0.1:18888/printer-gui-0.1.1-test-20260528.zip",
  "package_name": "printer-gui-0.1.1-test-20260528.zip",
  "package_size": 30715472,
  "package_md5": "760042bed75eb318f0a159e3d557f7ef"
}
```

设备测试结果：

- `/download` 成功。
- MD5 校验成功。
- 状态进入 `toInstall`。
- 第一次 `/update` 因 `printer-gui-eglfs.service` stop 后进入 `failed` 状态被 updater 判定为未停止，安装超时失败。
- 手动执行 `systemctl reset-failed printer-gui-eglfs.service` 后再次 `/update` 成功。
- 最终 `current -> /opt/tope/versions/v0.1.1`。
- 部署文件数 427。
- `printer-gui-eglfs.service` 最终为 `active`。
- updater progress 回到 `idle`。

需要特别记录：

- 这次包部署本身是成功的。
- 当前设备上的 `printer-gui-eglfs.service` 仍从旧路径 `/home/tope/printer-gui-qml/...` 启动，因此服务 active 不代表它已经运行 OTA 部署的新目录。
- 发货镜像中必须把 `printer-gui-eglfs.service` 的启动路径改为 `/opt/tope/versions/current` 或 `/opt/tope/services` 下的稳定入口。

## 发现的问题和发货前处理项

### 必须处理

1. `tope-updater.service` 需要保证能找到 Python 包。

   设备测试时服务缺少 `PYTHONPATH=/opt/tope/updater/src`，出现：

   ```text
   ModuleNotFoundError: No module named 'updater'
   ```

   临时修复方式是 systemd drop-in：

   ```ini
   [Service]
   Environment=PYTHONPATH=/opt/tope/updater/src
   ```

   发货镜像应在 service 文件或安装流程中固化该能力，或者把 updater 正确安装进 venv。

2. 服务 stop 逻辑应接受 `failed` 作为“已停止，可部署”状态。

   `systemctl stop printer-gui-eglfs.service` 后服务可能进入 `failed`，但此时进程已退出，屏幕资源也已释放。updater 当前只等待 `inactive`，导致误判超时。建议：

   - `stop` 后接受 `inactive` 和 `failed`。
   - 对 `failed` 状态执行 `systemctl reset-failed <service>`。
   - 增加单元测试覆盖。

3. 业务服务 systemd unit 必须使用版本化入口。

   OTA 是否真正生效，取决于服务是否从 `current` 或稳定符号链接启动。

### 可接受但需跟踪

1. `device-api` OTA report 返回 HTTP 500。

   测试中看到：

   ```text
   http://localhost:9080/api/v1.0/ota/report -> 500
   ```

   updater 目前会继续流程，不会因为上报失败中断升级。需要和 `device-api` 团队对齐接口实现。

2. updater API 监听地址。

   当前发货策略是用户侧改成 `127.0.0.1`。本轮不作为代码阻塞项。

## GUI 方案结论

当前 updater GUI 是 SDL 子进程。它能被 `/update` 触发，测试日志中可见：

```text
GUI process started
```

但在 Qt EGLFS 环境中没有窗口管理器，“置顶窗口”不是可靠概念。`printer-gui-eglfs` 和 updater GUI 不能同时稳定占用显示设备。

推荐方案已经确定为：

```text
systemd display switcher + 独立 Qt EGLFS updater-gui
```

推荐流程：

1. 下载阶段：保持 `printer-gui` 运行，由主 GUI 或云端状态展示下载进度。
2. 安装阶段：updater 调用 `tope-display-switcher show updater`。
3. switcher 停止 `printer-gui-eglfs.service`，执行 `reset-failed`，启动 `tope-updater-gui.service`。
4. `tope-updater-gui.service` 是最小 Qt/QML EGLFS 全屏界面，轮询 `/progress`。
5. 安装完成或失败后，updater 调用 `tope-display-switcher show printer`。
6. 系统配置隐藏 tty/getty/cursor/kernel log，避免切换过程中露出 console。

最小命令接口：

```bash
tope-display-switcher show updater
tope-display-switcher show printer
tope-display-switcher blank
```

关键要求：

- `tope-updater-gui.service` 启动失败时必须回退到 `printer-gui`。
- `printer-gui-eglfs.service` 停止后的 `failed` 状态不能阻塞 OTA。
- 禁用或隐藏 `getty@tty1.service`、console 光标和内核日志输出，降低中间黑屏/console 暴露概率。

## 系统包升级策略

本版本不做系统包升级，不把 apt/deb 混入普通 OTA。

原因：

- apt 在线更新受源、网络、锁、依赖版本影响，不适合发货前临时塞进普通 OTA 流程。
- deb 离线安装在目标系统完全一致时可以测试通过，但仍需要事务边界、失败回滚、服务重启、依赖校验和日志归档，直接用普通 `post_cmds` 执行不可控。
- 当前目标是 beta 可靠升级，普通应用和配置 OTA 的稳定性优先。

后续如果确实需要系统包升级，建议新增专门能力，而不是复用普通 manifest：

- 新增独立包类型，例如 `package_type: system-deb`。
- OTA 包内声明 deb 清单、sha256、安装顺序、允许安装的包名和版本。
- 安装前检查设备型号、OS 版本、磁盘空间、dpkg/apt 锁、依赖可满足性。
- 使用本地离线仓库或受控 deb 集合安装。
- 记录安装日志和 dpkg 状态快照。
- 明确哪些失败可自动恢复，哪些失败必须停机人工介入。

在目标系统只有一种且实验室镜像完全一致的前提下，这条路线是可行的，但应该作为后续专项实现和测试。

## 发货前检查清单

- [ ] `tope-updater.service` 能在冷启动后正常 import `updater`。
- [ ] updater API 监听改为 `127.0.0.1`。
- [ ] 所有被 OTA 管理的业务服务都从 `/opt/tope/versions/current` 或 `/opt/tope/services` 启动。
- [ ] `printer-gui-eglfs.service` 停止后进入 `failed` 时，OTA 不误判失败。
- [ ] `factory` 版本已创建且只读保护。
- [ ] `/opt/tope/versions/current`、`previous`、`factory` 符号链接正确。
- [ ] 至少使用一次真实 `printer-gui` 包在发货镜像上完成 `/download -> /update -> 服务启动`。
- [ ] 至少测试一次配置-only 包，例如只升级 `printer.cfg`。
- [ ] `device-api` 的 `/api/v1.0/ota/report` 不再返回 500，或明确发货阶段允许忽略上报失败。
- [ ] GUI 切换方案落地前，安装阶段的可视化体验和 console 暴露风险已被产品接受。
