"""
自定义 UI 组件。
"""

from PyQt5.QtWidgets import QFrame
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QPainter, QPen, QColor


class CornerFrame(QFrame):
    """带角标绘制的容器框，用于变色龙模式下的背景填充。"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.is_auto_mode = False
        self.draw_corners = True
        self.corner_color = QColor(128, 128, 128, 200)
        self.auto_bg_fill = QColor(0, 0, 0, 2)

    def set_mode(self, auto_mode):
        self.is_auto_mode = auto_mode
        self.update()

    def set_auto_bg_color(self, color):
        self.auto_bg_fill = QColor(color)
        self.auto_bg_fill.setAlpha(2)
        if self.is_auto_mode:
            self.update()

    def set_draw_corners(self, enable):
        self.draw_corners = enable
        self.update()

    def paintEvent(self, event):
        if not self.is_auto_mode:
            super().paintEvent(event)
            return

        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        painter.fillRect(self.rect(), self.auto_bg_fill)

        if self.draw_corners and self.height() > 20:
            painter.setPen(QPen(self.corner_color, 3))
            w, h = self.width(), self.height()
            length = 15
            painter.drawLine(0, 0, length, 0)
            painter.drawLine(0, 0, 0, length)
            painter.drawLine(w, h, w - length, h)
            painter.drawLine(w, h, w, h - length)
