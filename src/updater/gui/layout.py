"""
GUI Layout Configuration

三列布局：Logo（左） / 信息+进度（中） / 操作（右）
根据屏幕尺寸自动计算各列宽度和控件位置。
"""

_OUTER_PADDING = 20
_COL_GAP = 30
_LOGO_COL_RATIO = 0.22
_ACTION_COL_RATIO = 0.25


class LayoutConfig:
    """
    GUI 三列布局配置

    根据屏幕尺寸自动计算：
    - Logo 列（左）：接近屏幕高度的正方形 logo
    - 内容列（中）：标题、进度条、日志条目
    - 操作列（右）：按钮、倒计时、阶段名称
    """

    def __init__(self, screen_width: int, screen_height: int):
        """
        初始化布局配置

        Args:
            screen_width: 屏幕宽度
            screen_height: 屏幕高度
        """
        self.screen_width = screen_width
        self.screen_height = screen_height

        # 字体大小
        self.font_size_large = self._calc_font_large()
        self.font_size_small = self._calc_font_small()

        # --- Logo 列（左） ---
        logo_col_width = int(screen_width * _LOGO_COL_RATIO)
        logo_max_height = screen_height - 2 * _OUTER_PADDING
        logo_max_width = logo_col_width - 2 * _OUTER_PADDING
        self.logo_size = min(logo_max_height, logo_max_width)
        self.logo_x = _OUTER_PADDING
        self.logo_y = (screen_height - self.logo_size) // 2
        self.logo_render_w = self.logo_size
        self.logo_render_h = self.logo_size

        # --- 操作列（右） ---
        action_col_width = int(screen_width * _ACTION_COL_RATIO)
        self.action_x = screen_width - action_col_width - _OUTER_PADDING
        self.action_width = action_col_width

        # 按钮（操作列水平居中，垂直居中偏上）
        self.button_width = int(action_col_width * 0.80)
        self.button_height = max(50, self.font_size_large + 20)
        self.button_x = self.action_x + (action_col_width - self.button_width) // 2
        self.button_y = screen_height // 2 - self.button_height // 2

        # 倒计时（按钮下方）
        self.countdown_y = self.button_y + self.button_height + 16

        # 阶段标签（进度状态时，操作列垂直居中）
        self.stage_label_y = screen_height // 2 - self.font_size_small // 2

        # --- 内容列（中） ---
        self.content_x = _OUTER_PADDING + logo_col_width + _COL_GAP
        self.content_width = self.action_x - _COL_GAP - self.content_x

        # 标题文字（内容列顶部）
        self.title_y = _OUTER_PADDING + self.font_size_large

        # 进度条（内容列垂直中心偏上）
        self.progress_height = max(20, int(screen_height * 0.05))
        self.progress_width = self.content_width
        self.progress_y = screen_height // 2 - self.progress_height // 2 - 10

        # 百分比文字（进度条下方）
        self.percent_y = self.progress_y + self.progress_height + 8

        # 日志条目（百分比下方，逐行显示）
        self.log_start_y = self.percent_y + self.font_size_small + 16
        self.log_line_height = self.font_size_small + 8

    def _calc_font_large(self) -> int:
        """计算大字体尺寸"""
        if self.screen_width >= 1920:
            return 36 if self.screen_height <= 600 else 42
        elif self.screen_width >= 1280:
            return 32
        elif self.screen_width >= 1024:
            return 28
        return 24

    def _calc_font_small(self) -> int:
        """计算小字体尺寸"""
        if self.screen_width >= 1920:
            return 28 if self.screen_height <= 600 else 32
        elif self.screen_width >= 1280:
            return 24
        elif self.screen_width >= 1024:
            return 20
        return 18

    def __repr__(self) -> str:
        """字符串表示"""
        return (
            f"LayoutConfig(screen={self.screen_width}x{self.screen_height}, "
            f"logo={self.logo_size}px, "
            f"content_x={self.content_x}, content_w={self.content_width}, "
            f"action_x={self.action_x}, action_w={self.action_width})"
        )
