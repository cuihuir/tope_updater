# TOP.E OTA Updater - GUI 功能规范

**功能 ID**: 002-gui
**状态**: 草稿
**创建日期**: 2026-01-29
**最后更新**: 2026-01-29

---

## 1. 概述

### 1.1 目的
为 OTA 更新添加轻量级 GUI，在系统升级期间显示更新进度。GUI 必须覆盖现有的基于 QT 的设备界面，并为用户提供实时视觉反馈。

### 1.2 背景
- Phase 1-2 已完成：Reporter 集成 + 版本快照架构
- 设备使用全屏 QT GUI 作为主界面
- OTA updater 需要在升级期间显示进度
- 嵌入式 Linux 环境，依赖最小化

### 1.3 目标
- ✅ 最小依赖（总计 < 10MB）
- ✅ 全屏覆盖现有 QT GUI
- ✅ 实时进度显示（文字 + 百分比）
- ✅ 自适应屏幕尺寸
- ✅ 最顶层窗口（始终可见）
- ✅ 自动生命周期管理

---

## 2. 需求

### 2.1 功能需求

#### FR-001: GUI 激活
- **触发条件**: 调用 POST `/api/v1.0/update` 端点
- **行为**: GUI 立即启动，覆盖现有界面
- **优先级**: P0（关键）

#### FR-002: 进度显示
- **内容**:
  - 文字消息（例如："正在升级系统..."）
  - 进度条（视觉指示器）
  - 百分比（例如："45%"）
- **更新频率**: 每 500ms
- **优先级**: P0（关键）

#### FR-003: 进度轮询
- **数据源**: GET `/api/v1.0/progress` 端点
- **频率**: 500ms 间隔
- **数据**: 阶段、进度百分比、消息
- **优先级**: P0（关键）

#### FR-004: 自动关闭
- **触发条件**: 更新完成（成功/失败）
- **行为**: 显示最终状态 3 秒后关闭
- **优先级**: P0（关键）

#### FR-005: 中文语言支持
- **需求**: 正确显示中文文本
- **解决方案**: 打包 Noto Sans CJK SC 字体
- **优先级**: P0（关键）

### 2.2 非功能需求

#### NFR-001: 性能
- **GUI 启动时间**: < 2 秒
- **内存使用**: < 50MB
- **CPU 使用**: < 5%（空闲），< 15%（渲染）
- **优先级**: P0（关键）

#### NFR-002: 可靠性
- **GUI 崩溃**: 不得影响 updater 进程
- **进程隔离**: GUI 作为独立子进程运行
- **错误处理**: 所有异常记录日志，优雅降级
- **优先级**: P0（关键）

#### NFR-003: 兼容性
- **平台**: 嵌入式 Linux（ARM/x86）
- **显示**: Framebuffer 或 X11
- **屏幕尺寸**: 800x480 到 1920x1080
- **优先级**: P1（高）

#### NFR-004: 依赖
- **总大小**: < 10MB（SDL2 + 字体）
- **外部依赖**: SDL2, SDL2_ttf
- **Python 依赖**: PySDL2, PySDL2-dll
- **优先级**: P1（高）

---

## 3. 技术设计

### 3.1 技术栈

#### 选择方案：PySDL2
- **库**: SDL2（Simple DirectMedia Layer）
- **Python 绑定**: PySDL2
- **大小**: ~5MB（SDL2）+ ~5MB（字体）= ~10MB 总计
- **优势**:
  - ✅ 轻量快速
  - ✅ 无 X11 依赖（支持 framebuffer）
  - ✅ 原生全屏和窗口管理
  - ✅ 跨平台（Linux/Windows/macOS）
  - ✅ 成熟稳定

#### 备选方案：Tkinter
- **优点**: Python 内置，无额外依赖
- **缺点**: 需要 X11，窗口层级控制较弱
- **决策**: 因 X11 依赖而拒绝

### 3.2 架构

```
┌─────────────────────────────────────────────────┐
│  Updater 主进程 (FastAPI)                        │
│  ├─ POST /api/v1.0/update (触发)                │
│  ├─ GET /api/v1.0/progress (数据源)             │
│  └─ 后台任务 (部署)                             │
└─────────────────────────────────────────────────┘
                    │
                    ├─ 启动 ────────────┐
                    │                   ↓
                    │    ┌──────────────────────────┐
                    │    │  GUI 子进程 (PySDL2)      │
                    │    │  ├─ 全屏窗口              │
                    │    │  ├─ 轮询进度 (500ms)      │
                    │    │  └─ 渲染 UI               │
                    │    └──────────────────────────┘
                    │                   │
                    └─ 轮询 ────────────┘
                         HTTP GET /api/v1.0/progress
```

### 3.3 组件结构

```
src/updater/
├── gui/
│   ├── __init__.py
│   ├── fonts/
│   │   └── NotoSansCJKsc-Regular.otf    # ~5MB
│   ├── progress_window.py               # 主窗口 (~150 行)
│   ├── renderer.py                      # 渲染引擎 (~100 行)
│   └── launcher.py                      # 进程管理器 (~80 行)
├── api/
│   └── routes.py                        # 修改: +30 行
└── services/
    └── deploy.py                        # 修改: +10 行
```

### 3.4 UI 设计

```
┌─────────────────────────────────────────────────┐
│                                                 │
│                                                 │
│                                                 │
│              正在升级系统...                     │
│                                                 │
│         ████████████████░░░░░░░░░░              │
│                   45%                           │
│                                                 │
│                                                 │
│                                                 │
└─────────────────────────────────────────────────┘

颜色:
- 背景: 黑色 (#000000)
- 文字: 白色 (#FFFFFF)
- 进度条（已填充）: 绿色 (#00FF00)
- 进度条（未填充）: 深灰色 (#333333)

布局:
- 文字: 居中，32px 字体
- 进度条: 屏幕宽度的 60%，居中
- 百分比: 进度条下方，24px 字体
```

---

## 4. 实施计划

### Phase 1: GUI 基础框架（1-2 天）
- **文件**: `progress_window.py`, `renderer.py`
- **任务**:
  - 使用 SDL2 创建全屏窗口
  - 实现文字渲染（中文支持）
  - 实现进度条渲染
  - 在开发机上测试

### Phase 2: 进程管理（1 天）
- **文件**: `launcher.py`
- **任务**:
  - 实现子进程启动
  - 实现进程终止
  - 添加错误处理和日志

### Phase 3: 集成（1 天）
- **文件**: `routes.py`, `deploy.py`
- **任务**:
  - 修改 `/api/v1.0/update` 启动 GUI
  - 修改部署工作流停止 GUI
  - 添加 GUI 生命周期管理

### Phase 4: 进度轮询（1 天）
- **文件**: `progress_window.py`
- **任务**:
  - 实现 HTTP 轮询（500ms 间隔）
  - 解析进度数据
  - 实时更新 UI
  - 处理完成/失败状态

### Phase 5: 测试与调试（1-2 天）
- **任务**:
  - launcher 单元测试
  - GUI 生命周期集成测试
  - 目标设备手动测试
  - 性能分析

**总计估算**: 5-7 天

---

## 5. 数据流

### 5.1 GUI 生命周期

```
1. 用户触发更新
   POST /api/v1.0/update
   ↓
2. Updater 验证请求
   ↓
3. Updater 启动 GUI 子进程
   GUILauncher.start()
   ↓
4. GUI 创建全屏窗口
   SDL_CreateWindow(FULLSCREEN | ALWAYS_ON_TOP)
   ↓
5. GUI 进入轮询循环
   每 500ms: GET /api/v1.0/progress
   ↓
6. GUI 渲染进度
   Renderer.render_progress(message, percentage)
   ↓
7. 更新完成
   Stage = "success" 或 "failed"
   ↓
8. GUI 显示最终状态（3 秒）
   ↓
9. GUI 关闭
   SDL_DestroyWindow()
   ↓
10. Updater 终止 GUI 子进程
    GUILauncher.stop()
```

### 5.2 进度数据格式

```json
{
  "stage": "downloading",
  "progress": 45,
  "message": "正在下载更新包...",
  "error": null
}
```

**阶段**:
- `idle`: 无更新进行中
- `downloading`: 下载更新包
- `verifying`: 验证包完整性
- `deploying`: 部署更新
- `success`: 更新成功完成
- `failed`: 更新失败

---

## 6. 错误处理

### 6.1 GUI 崩溃
- **检测**: 进程退出码 != 0
- **操作**: 记录错误，继续更新进程
- **影响**: 用户失去视觉反馈，但更新继续

### 6.2 进度轮询失败
- **检测**: HTTP 请求超时或错误
- **操作**: 重试 3 次，然后显示"连接失败"
- **影响**: GUI 显示过时数据

### 6.3 SDL2 初始化失败
- **检测**: SDL_Init() 返回错误
- **操作**: 记录错误，优雅退出 GUI 进程
- **影响**: 无 GUI 显示，更新继续

### 6.4 字体加载失败
- **检测**: TTF_OpenFont() 返回 NULL
- **操作**: 回退到内置字体或退出
- **影响**: 无文字显示或无 GUI

---

## 7. 测试策略

### 7.1 单元测试
- `test_gui_launcher.py`: 进程管理
- `test_renderer.py`: 渲染逻辑（模拟 SDL2）

### 7.2 集成测试
- `test_gui_integration.py`: 完整生命周期测试
- `test_progress_polling.py`: HTTP 轮询测试

### 7.3 手动测试
- `test_gui_display.py`: 设备上视觉验证
- `test_screen_sizes.py`: 不同分辨率测试
- `test_overlay.py`: 验证覆盖 QT GUI

### 7.4 性能测试
- 内存使用分析
- CPU 使用监控
- 启动时间测量

---

## 8. 部署

### 8.1 依赖安装

```bash
# 在目标设备上
apt-get install libsdl2-2.0-0 libsdl2-ttf-2.0-0

# Python 依赖（通过 uv）
uv sync
```

### 8.2 字体打包

```bash
# 下载 Noto Sans CJK SC
wget https://github.com/googlefonts/noto-cjk/raw/main/Sans/OTF/SimplifiedChinese/NotoSansCJKsc-Regular.otf

# 放置到 src/updater/gui/fonts/
cp NotoSansCJKsc-Regular.otf src/updater/gui/fonts/
```

### 8.3 验证

```bash
# 测试 SDL2
python -c "import sdl2; print('SDL2 OK')"

# 测试 GUI 启动
python -m updater.gui.progress_window
```

---

## 9. 风险与缓解

### 风险 1: SDL2 在嵌入式 Linux 上的兼容性
- **可能性**: 中
- **影响**: 高（无 GUI）
- **缓解**: 提前在目标设备上测试，准备 Tkinter 备选方案

### 风险 2: GUI 无法覆盖 QT GUI
- **可能性**: 低
- **影响**: 高（GUI 不可见）
- **缓解**: 使用 `SDL_WINDOW_ALWAYS_ON_TOP`，测试窗口层级

### 风险 3: 字体渲染问题
- **可能性**: 低
- **影响**: 中（文字不可读）
- **缓解**: 打包字体，提前测试中文渲染

### 风险 4: 进程管理复杂性
- **可能性**: 中
- **影响**: 中（僵尸进程）
- **缓解**: 正确的子进程清理，超时机制

---

## 10. 成功标准

### 必须有（P0）
- ✅ GUI 在更新期间显示
- ✅ 进度实时更新
- ✅ 中文文字正确渲染
- ✅ 更新后 GUI 自动关闭
- ✅ 内存使用 < 50MB

### 应该有（P1）
- ✅ GUI 覆盖 QT 界面
- ✅ 自适应屏幕尺寸
- ✅ 优雅的错误处理

### 可以有（P2）
- ⏸️ 动画进度条
- ⏸️ 自定义品牌/logo
- ⏸️ 声音效果

---

## 11. 未来增强

### Phase 2（可选）
- 添加 logo/品牌
- 动画过渡
- 多语言支持（英语等）
- 可自定义主题

### Phase 3（可选）
- 触摸输入支持
- 取消按钮（带确认）
- 详细错误消息

---

## 12. 参考资料

- [SDL2 文档](https://wiki.libsdl.org/)
- [PySDL2 文档](https://pysdl2.readthedocs.io/)
- [Noto CJK 字体](https://github.com/googlefonts/noto-cjk)
- [TOP.E Updater 核心规范](../001-updater-core/spec.md)

---

**文档状态**: ✅ 准备审查
**下一步**: 创建实施计划（plan.md）
