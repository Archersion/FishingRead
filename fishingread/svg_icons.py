"""
SVG 图标渲染与统一图标管理。
"""

from PyQt5.QtGui import QPainter, QPixmap, QIcon
from PyQt5.QtCore import Qt

from fishingread.constants import get_svg_icon_bytes


def _render_svg_icon(svg_bytes, size=20):
    """将 SVG 字节数据渲染为 QPixmap，失败返回 None。"""
    try:
        from PyQt5.QtSvg import QSvgRenderer
        from PyQt5.QtCore import QByteArray

        renderer = QSvgRenderer(QByteArray(svg_bytes))
        if not renderer.isValid():
            return None
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.transparent)
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        return pixmap
    except Exception:
        return None


def make_icon(svg_name, size=20):
    """通过 SVG 名称创建 QIcon，失败返回空 QIcon。"""
    svg_data = get_svg_icon_bytes(svg_name)
    if not svg_data:
        return QIcon()
    pixmap = _render_svg_icon(svg_data, size)
    if pixmap and not pixmap.isNull():
        return QIcon(pixmap)
    return QIcon()


def get_app_icon():
    """搜索应用图标，优先 SVG logo，然后 .ico/.png，最后兜底。"""
    import sys
    import os

    exe_dir = None
    if getattr(sys, "frozen", False):
        if hasattr(sys, "_MEIPASS"):
            exe_dir = sys._MEIPASS
        else:
            exe_dir = os.path.dirname(sys.executable)
    else:
        exe_dir = os.path.dirname(os.path.abspath(__file__))
        # 如果从包内运行，回退到运行目录
        parent = os.path.dirname(exe_dir)
        if os.path.exists(os.path.join(parent, "main.py")):
            exe_dir = parent

    # 1. 优先渲染 SVG logo
    if exe_dir:
        for svg_name in ("logo.svg", "read.svg"):
            svg_path = os.path.join(exe_dir, svg_name)
            if os.path.exists(svg_path):
                with open(svg_path, "rb") as f:
                    svg_data = f.read()
                pixmap = _render_svg_icon(svg_data, size=256)
                if pixmap and not pixmap.isNull():
                    return QIcon(pixmap)

    # 2. 尝试 .ico / .png
    if exe_dir:
        for fname in ("read.ico", "read.png", "icon.ico", "icon.png", "app.ico", "app.png"):
            path = os.path.join(exe_dir, fname)
            if os.path.exists(path):
                icon = QIcon(path)
                if not icon.isNull():
                    return icon

    # 3. PyInstaller 打包时从 exe 文件提取
    if getattr(sys, "frozen", False) and hasattr(sys, "executable"):
        exe_path = sys.executable
        if os.path.exists(exe_path):
            icon = QIcon(exe_path)
            if not icon.isNull():
                return icon

    return QIcon()


def add_menu_action(menu, text, callback, icon_name=None):
    """创建带图标的 QAction 并添加到菜单。"""
    from PyQt5.QtWidgets import QAction

    action = QAction(text, menu)
    if icon_name:
        icon = make_icon(icon_name)
        if icon and not icon.isNull():
            action.setIcon(icon)
    action.triggered.connect(callback)
    menu.addAction(action)
    return action
