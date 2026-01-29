"""
GUI Layout Configuration

自适应布局配置，根据屏幕尺寸计算布局参数
"""


class LayoutConfig:
    """
    GUI 布局配置类

    根据屏幕尺寸自动计算：
    - Logo 尺寸（正方形）
    - 字体大小
    - 内容区域位置和尺寸
    - 进度条参数
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

        # Logo 尺寸和位置（正方形）
        self.logo_size = self._calculate_logo_size()
        self.logo_x = 40 if screen_width >= 1280 else 30
        self.logo_y = (screen_height - self.logo_size) // 2

        # 内容区域
        self.content_x = self.logo_x + self.logo_size + 40
        self.content_width = screen_width - self.content_x - 50

        # 字体大小（根据分辨率调整）
        self.font_size_large = self._calculate_font_size_large()
        self.font_size_small = self._calculate_font_size_small()

        # 文字位置（内容区上方 1/3）
        self.text_y = screen_height // 3

        # 进度条
        self.progress_y = screen_height // 2
        self.progress_width = min(1000, int(self.content_width * 0.6))
        self.progress_height = 30

        # 百分比
        self.percent_y = self.progress_y + 50

    def _calculate_logo_size(self) -> int:
        """
        计算 logo 尺寸（正方形边长）

        Returns:
            Logo 边长（像素）
        """
        if self.screen_width >= 1920:
            # 超宽屏 (1920x440) 或标准屏 (1920x1080)
            return 100 if self.screen_height <= 600 else 120
        elif self.screen_width >= 1280:
            return 100
        elif self.screen_width >= 1024:
            return 80
        else:
            return 60

    def _calculate_font_size_large(self) -> int:
        """
        计算大字体尺寸

        Returns:
            字体大小（像素）
        """
        if self.screen_width >= 1920:
            return 36 if self.screen_height <= 600 else 42
        elif self.screen_width >= 1280:
            return 32
        elif self.screen_width >= 1024:
            return 28
        else:
            return 24

    def _calculate_font_size_small(self) -> int:
        """
        计算小字体尺寸

        Returns:
            字体大小（像素）
        """
        if self.screen_width >= 1920:
            return 28 if self.screen_height <= 600 else 32
        elif self.screen_width >= 1280:
            return 24
        elif self.screen_width >= 1024:
            return 20
        else:
            return 18

    def __repr__(self) -> str:
        """字符串表示"""
        return (
            f"LayoutConfig(screen={self.screen_width}x{self.screen_height}, "
            f"logo={self.logo_size}x{self.logo_size}, "
            f"fonts={self.font_size_large}/{self.font_size_small}, "
            f"progress={self.progress_width}x{self.progress_height})"
        )
