# GUI 倒计时自动退出 + 完成按钮 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** 安装完成（success/failed）后显示 60s 倒计时，同时显示"完成安装"按钮，点击立即退出，倒计时结束自动退出。

**Architecture:** 在 `progress_window.py` 的主循环中增加倒计时状态和鼠标点击检测；在 `renderer.py` 中增加倒计时文字和按钮渲染；`layout.py` 增加按钮区域布局参数。

**Tech Stack:** Python 3.11+, SDL2 (pysdl2), sdl2.sdlttf

---

### Task 1: layout.py 增加按钮布局参数

**Files:**
- Modify: `src/updater/gui/layout.py`

**Step 1: 在 `__init__` 末尾添加按钮布局参数**

```python
# 完成按钮（进度条下方居中）
self.button_width = min(300, int(self.content_width * 0.3))
self.button_height = max(50, self.font_size_large + 20)
self.button_x = self.content_x + (self.content_width - self.button_width) // 2
self.button_y = self.percent_y + self.font_size_small + 30

# 倒计时文字（按钮下方）
self.countdown_y = self.button_y + self.button_height + 20
```

**Step 2: 验证布局参数合理**

```bash
uv run python -c "
from updater.gui.layout import LayoutConfig
l = LayoutConfig(1920, 1080)
print(f'button: {l.button_x},{l.button_y} {l.button_width}x{l.button_height}')
print(f'countdown_y: {l.countdown_y}')
assert l.button_width > 0
assert l.button_height > 0
print('OK')
"
```
Expected: 打印合理数值，无 AssertionError

**Step 3: Commit**

```bash
git add src/updater/gui/layout.py
git commit -m "feat: add button and countdown layout params"
```

---

### Task 2: renderer.py 增加按钮和倒计时渲染

**Files:**
- Modify: `src/updater/gui/renderer.py`

**Step 1: 在 `render_progress` 签名后增加可选参数，添加 `render_completion` 方法**

在 `render_progress` 方法末尾（`percent_y` 渲染后）不做改动。新增独立方法：

```python
def render_completion(
    self,
    surface: sdl2.SDL_Surface,
    message: str,
    countdown: int,
    button_hovered: bool = False
):
    """
    渲染完成状态 UI（success/failed）

    Args:
        surface: 目标 surface
        message: 状态消息
        countdown: 剩余秒数 (0-60)
        button_hovered: 按钮是否悬停（触摸屏不需要，保留扩展性）
    """
    # 清屏
    sdl2.ext.fill(surface, sdl2.ext.Color(0, 0, 0))

    # Logo
    if self.logo:
        self._render_logo(surface)

    # 状态消息
    self._render_text_centered(
        surface, message, self.font_large,
        self.layout.content_x, self.layout.text_y, self.layout.content_width
    )

    # 完成按钮
    btn_color = sdl2.ext.Color(0, 180, 0) if not button_hovered else sdl2.ext.Color(0, 220, 0)
    btn_rect = sdl2.SDL_Rect(
        self.layout.button_x, self.layout.button_y,
        self.layout.button_width, self.layout.button_height
    )
    sdl2.ext.fill(surface, btn_color, btn_rect)
    self._render_text_centered(
        surface, "完成安装", self.font_small,
        self.layout.button_x, self.layout.button_y + (self.layout.button_height - self.layout.font_size_small) // 2,
        self.layout.button_width
    )

    # 倒计时文字
    countdown_text = f"{countdown} 秒后自动关闭"
    self._render_text_centered(
        surface, countdown_text, self.font_small,
        self.layout.content_x, self.layout.countdown_y, self.layout.content_width
    )
```

**Step 2: 验证渲染器可以导入**

```bash
uv run python -c "from updater.gui.renderer import Renderer; print('OK')"
```
Expected: `OK`

**Step 3: Commit**

```bash
git add src/updater/gui/renderer.py
git commit -m "feat: add render_completion with button and countdown"
```

---

### Task 3: progress_window.py 实现倒计时和按钮点击逻辑

**Files:**
- Modify: `src/updater/gui/progress_window.py`

**Step 1: 在 `run()` 方法中替换原有的 success/failed 处理逻辑**

原来的代码：
```python
# 检查更新是否完成
stage = current_data.get("stage")
if stage in ["success", "failed"]:
    # 显示最终状态 5 秒
    time.sleep(5)
    self.running = False
```

替换为：
```python
# 检查更新是否完成
stage = current_data.get("stage")
if stage in ["success", "failed"]:
    # 进入倒计时模式
    countdown_total = 60
    countdown_start = time.time()
    final_message = current_data.get("message", "")

    while self.running:
        # 处理事件
        event = sdl2.SDL_Event()
        while sdl2.SDL_PollEvent(event) != 0:
            if event.type == sdl2.SDL_QUIT:
                self.running = False
            elif event.type == sdl2.SDL_MOUSEBUTTONDOWN:
                mx, my = event.button.x, event.button.y
                bx = self.renderer.layout.button_x
                by = self.renderer.layout.button_y
                bw = self.renderer.layout.button_width
                bh = self.renderer.layout.button_height
                if bx <= mx <= bx + bw and by <= my <= by + bh:
                    self.running = False

        elapsed = time.time() - countdown_start
        remaining = max(0, countdown_total - int(elapsed))

        if remaining == 0:
            self.running = False
            break

        # 渲染完成状态
        surface = sdl2.SDL_GetWindowSurface(self.window)
        if surface:
            self.renderer.render_completion(surface, final_message, remaining)
            sdl2.SDL_UpdateWindowSurface(self.window)

        sdl2.SDL_Delay(50)
    break
```

**Step 2: 验证 GUI 可以启动并正常运行**

```bash
uv run python -m updater.gui.progress_window 2>&1 &
sleep 5
kill %1 2>/dev/null
echo "exit OK"
```
Expected: 启动无报错，5 秒后被 kill 正常退出

**Step 3: Commit**

```bash
git add src/updater/gui/progress_window.py
git commit -m "feat: countdown 60s + button to close GUI on success/failed"
```

---

### Task 4: routes.py 同步调整 reset 延迟

**Files:**
- Modify: `src/updater/api/routes.py`

**Step 1: 将 reset 延迟从 6s 改为 65s，确保 GUI 倒计时结束前状态不归 idle**

```python
# Reset to idle after success so next upgrade can proceed
await asyncio.sleep(65)
state_manager.reset()
```

**Step 2: 验证**

```bash
uv run python -c "import ast, sys; ast.parse(open('src/updater/api/routes.py').read()); print('syntax OK')"
```
Expected: `syntax OK`

**Step 3: Commit**

```bash
git add src/updater/api/routes.py
git commit -m "feat: extend reset delay to 65s to match GUI countdown"
```

---

### Task 5: 端到端验证

**Step 1: 启动环境**

```bash
# 文件服务器（如未运行）
cd tests/e2e/test_data/packages && python3 -m http.server 8888 &
cd -

# 清理上次测试残留
sudo rm -rf /opt/tope/versions/v0.0.2
rm -f tmp/state.json

# 启动 updater
uv run src/updater/main.py > /tmp/updater_e2e.log 2>&1 &
sleep 4
```

**Step 2: 触发完整升级流程**

```bash
curl -s -X POST http://localhost:12315/api/v1.0/download \
  -H "Content-Type: application/json" \
  -d '{"version":"0.0.2","package_url":"http://localhost:8888/device-api-0.0.2.zip","package_name":"device-api-0.0.2.zip","package_size":25410974,"package_md5":"52d95e55cf3627e8b4f0b81d26463a4c"}'

# 等 toInstall
for i in $(seq 1 20); do
  stage=$(curl -s http://localhost:12315/api/v1.0/progress | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['stage'])")
  [ "$stage" = "toInstall" ] && break; sleep 2
done

curl -s -X POST http://localhost:12315/api/v1.0/update \
  -H "Content-Type: application/json" \
  -d '{"version":"0.0.2"}'
```

**Step 3: 监控 GUI 存活时间**

```bash
for i in $(seq 1 75); do
  stage=$(curl -s http://localhost:12315/api/v1.0/progress | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['stage'])")
  gui=$(ps aux | grep progress_window | grep -v grep | awk '{print $2}')
  echo "[$(date +%H:%M:%S)] stage=$stage GUI=${gui:-已退出}"
  sleep 1
done
```

Expected:
- success 后 GUI 持续存活约 60s
- 60s 后 GUI 自动退出
- 约 65s 后 stage 变为 idle
