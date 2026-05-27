import sys
import requests
import json
import os
import logging
import threading
import time
import ctypes
import traceback
from ctypes import wintypes
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QMenu,
                             QAction, QDialog, QFormLayout, QLineEdit, QSlider,
                             QSpinBox, QPushButton, QSystemTrayIcon,
                             QColorDialog, QCheckBox, QHBoxLayout,
                             QFrame, QTextEdit, QShortcut, QListWidget,
                             QComboBox,
                             QListWidgetItem, QLabel, QFontComboBox, QSizePolicy, QFileDialog)
from PyQt5.QtCore import Qt, QPoint, QRect, pyqtSignal, QThread, QTimer, QEvent, QSharedMemory
from PyQt5.QtNetwork import QLocalServer, QLocalSocket
from PyQt5.QtGui import QFont, QColor, QCursor, QKeySequence, QPainter, QPen, QFontMetrics, QTextCursor, QTextBlockFormat, QIcon, QPixmap

# 启用高分屏支持
QApplication.setAttribute(Qt.AA_EnableHighDpiScaling)
QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps)

CONFIG_FILE = "config.json"
LOCAL_PAGE_BUFFER_SIZE = 5000
BOOKSHELF_TIMEOUT = 3
CHAPTER_LIST_TIMEOUT = 10
CHAPTER_CONTENT_TIMEOUT = 5
PROGRESS_SYNC_TIMEOUT = 3
PROGRESS_AUTO_SAVE_INTERVAL = 30
PROGRESS_AUTO_SAVE_CHECK_INTERVAL = 5
FUTURE_CHAPTER_CACHE_SIZE = 5
LEGACY_CONFIG_KEYS = (
    "opacity",
    "show_in_alt_tab",
    "show_in_taskbar",
    "hide_from_alt_tab",
)

WM_HOTKEY = 0x0312
MOD_ALT = 0x0001
MOD_CONTROL = 0x0002
MOD_SHIFT = 0x0004
MOD_WIN = 0x0008
MOD_NOREPEAT = 0x4000

DEFAULT_CONFIG = {
    "ip": "http://192.168.6.94:1122",
    "text_opacity": 0.9,
    "background_opacity": 0.78,
    "font_size": 14,
    "line_spacing": 0,
    "font_family": "Microsoft YaHei",
    "text_color": "rgba(200, 200, 200, 255)",
    "bg_color": "rgba(30, 30, 30, 200)",
    "boss_key": "Esc",
    "focus_hotkey": "Ctrl+Shift+R",
    "ghost_mode": False,
    "ghost_mode_display_mode": "hover",
    "show_in_switcher": False,
    "always_on_top": True,
    "context_menu_requires_ctrl": False,
    "auto_mode": False,
    "antishot_mode": False,
    "window_x": 100,
    "window_y": 100,
    "window_width": 400,
    "window_height": 300,
    "last_local_file": "",
    "last_local_pos": 0
}

DARK_STYLESHEET = """
    QDialog, QWidget { background-color: #2b2b2b; color: #cccccc; }
    QLineEdit { background-color: #3c3c3c; color: white; border: 1px solid #555; padding: 5px; border-radius: 4px; }
    QListWidget { background-color: #333; color: #ddd; border: 1px solid #444; }
    QListWidget::item:selected { background-color: #505050; color: white; }
    QListWidget::item:hover { background-color: #3e3e3e; }
    QPushButton { background-color: #444; color: white; border: 1px solid #555; padding: 5px; border-radius: 4px; }
    QPushButton:hover { background-color: #555; }
    QComboBox { background-color: #3c3c3c; color: white; border: 1px solid #555; padding: 5px; }
    QComboBox QAbstractItemView { background-color: #3c3c3c; color: white; selection-background-color: #505050; }
    QLabel { color: #aaa; }
"""

# ================= SVG 图标系统 + 统一图标管理 =================
MENU_STYLESHEET = """
    QMenu {
        background-color: #2b2b2b;
        color: #f0f0f0;
        border: 1px solid #555555;
        border-radius: 8px;
        padding: 6px 4px;
        font-size: 13px;
    }
    QMenu::item {
        padding: 8px 32px 8px 12px;
        border-radius: 4px;
        color: #f0f0f0;
    }
    QMenu::item:selected {
        background-color: #4a8ec7;
        color: #ffffff;
    }
    QMenu::item:disabled {
        color: #666666;
    }
    QMenu::separator {
        height: 1px;
        background: #3a3a3a;
        margin: 5px 8px;
    }
"""

_SVG_COLOR = "#cccccc"

_SVG_ICONS = {
    "folder-open": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        f'stroke="{_SVG_COLOR}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M2 6a2 2 0 0 1 2-2h5l2 2h9a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V6z"/>'
        '</svg>'
    ),
    "bookshelf": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        f'stroke="{_SVG_COLOR}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<rect x="3" y="4" width="4" height="16" rx="1"/>'
        '<rect x="8" y="6" width="4" height="14" rx="1"/>'
        '<rect x="13" y="3" width="4" height="18" rx="1"/>'
        '<rect x="18" y="7" width="4" height="12" rx="1"/>'
        '</svg>'
    ),
    "book-open": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        f'stroke="{_SVG_COLOR}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/>'
        '<path d="M4 4.5A2.5 2.5 0 0 1 6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15z"/>'
        '<line x1="8" y1="7" x2="16" y2="7"/>'
        '<line x1="8" y1="10" x2="14" y2="10"/>'
        '<line x1="8" y1="13" x2="15" y2="13"/>'
        '</svg>'
    ),
    "settings": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        f'stroke="{_SVG_COLOR}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<circle cx="12" cy="12" r="3"/>'
        '<path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06'
        'a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09'
        'A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06'
        'A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09'
        'A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06'
        'A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09'
        'a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06'
        'A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09'
        'a1.65 1.65 0 0 0-1.51 1z"/>'
        '</svg>'
    ),
    "x": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        f'stroke="{_SVG_COLOR}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<line x1="18" y1="6" x2="6" y2="18"/>'
        '<line x1="6" y1="6" x2="18" y2="18"/>'
        '</svg>'
    ),
    "refresh-cw": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        f'stroke="{_SVG_COLOR}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<polyline points="23 4 23 10 17 10"/>'
        '<path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>'
        '</svg>'
    ),
    "save": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        f'stroke="{_SVG_COLOR}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/>'
        '<polyline points="17 21 17 13 7 13 7 21"/>'
        '<polyline points="7 11 7 3 15 3"/>'
        '</svg>'
    ),
    "eye": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        f'stroke="{_SVG_COLOR}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>'
        '<circle cx="12" cy="12" r="3"/>'
        '</svg>'
    ),
    "shield": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        f'stroke="{_SVG_COLOR}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>'
        '<polyline points="9 12 11 14 15 10"/>'
        '</svg>'
    ),
    "ghost": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        f'stroke="{_SVG_COLOR}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M12 2a8 8 0 0 0-8 8v10l3-2 2 2 2-2 2 2 2-2 2 2 3-2V10a8 8 0 0 0-8-8z"/>'
        f'<circle cx="9" cy="10" r="1.5" fill="{_SVG_COLOR}"/>'
        f'<circle cx="15" cy="10" r="1.5" fill="{_SVG_COLOR}"/>'
        '</svg>'
    ),
    "chameleon": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        f'stroke="{_SVG_COLOR}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<ellipse cx="12" cy="12" rx="9" ry="6"/>'
        f'<circle cx="12" cy="9" r="2" fill="{_SVG_COLOR}"/>'
        '<path d="M12 15c-3 0-5-1-5-1s2 3 5 3 5-3 5-3-2 1-5 1z"/>'
        '</svg>'
    ),
}


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
    svg_data = _SVG_ICONS.get(svg_name)
    if not svg_data:
        return QIcon()
    pixmap = _render_svg_icon(svg_data.encode("utf-8"), size)
    if pixmap and not pixmap.isNull():
        return QIcon(pixmap)
    return QIcon()


def add_menu_action(menu, text, callback, icon_name=None):
    """创建带图标的 QAction 并添加到菜单。"""
    action = QAction(text, menu)
    if icon_name:
        icon = make_icon(icon_name)
        if icon and not icon.isNull():
            action.setIcon(icon)
    action.triggered.connect(callback)
    menu.addAction(action)
    return action


def get_app_icon():
    """搜索应用图标，优先尝试 SVG logo，然后 .ico/.png，最后兜底。"""
    exe_dir = None
    if getattr(sys, "frozen", False):
        if hasattr(sys, "_MEIPASS"):
            exe_dir = sys._MEIPASS
        else:
            exe_dir = os.path.dirname(sys.executable)
    else:
        exe_dir = os.path.dirname(os.path.abspath(__file__))

    # 1. 优先尝试渲染 SVG logo（logo.svg 或 read.svg）
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

    # 3. PyInstaller 打包时从可执行文件提取
    if getattr(sys, "frozen", False) and hasattr(sys, "executable"):
        exe_path = sys.executable
        if os.path.exists(exe_path):
            icon = QIcon(exe_path)
            if not icon.isNull():
                return icon

    return QIcon()


def setup_file_logging():
    """将错误日志写入文件（打包后无控制台时同样可查）。"""
    try:
        if getattr(sys, "frozen", False):
            log_dir = os.path.dirname(sys.executable)
        else:
            log_dir = os.path.dirname(os.path.abspath(__file__))
        log_path = os.path.join(log_dir, "鱼阅.log")
        logging.basicConfig(
            filename=log_path,
            level=logging.ERROR,
            format="%(asctime)s [%(levelname)s] %(message)s",
            encoding="utf-8",
        )
    except Exception:
        pass


# ================= Windows 防截屏 API 封装 =================
def set_window_protection(hwnd, enable=True):
    try:
        user32 = ctypes.windll.user32
        WDA_NONE = 0x00000000
        WDA_EXCLUDEFROMCAPTURE = 0x00000011  # Win10 2004+

        mode = WDA_EXCLUDEFROMCAPTURE if enable else WDA_NONE
        user32.SetWindowDisplayAffinity(hwnd, mode)
    except Exception as e:
        print(f"防截屏设置失败: {e}")


# ================= 辅助类：绘制背景和角标 =================
class CornerFrame(QFrame):
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


# ================= 独立窗口：书籍选择器 =================
class BookSelector(QDialog):
    def __init__(self, main_window, parent=None):
        super().__init__(parent)
        self.main_window = main_window
        self.selected_book = None
        self.setWindowTitle("​书架")
        self.resize(400, 500)
        self.setStyleSheet(DARK_STYLESHEET)
        self.initUI()
        self.populate_list(self.main_window.books)

    def initUI(self):
        layout = QVBoxLayout()
        top_layout = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("搜索书名或作者...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self.filter_books)
        top_layout.addWidget(self.search_input)

        btn_refresh = QPushButton("刷新")
        btn_refresh.setIcon(make_icon("refresh-cw", 16))
        btn_refresh.setFixedWidth(80)
        btn_refresh.clicked.connect(self.manual_refresh)
        top_layout.addWidget(btn_refresh)

        layout.addLayout(top_layout)
        self.list_widget = QListWidget()
        self.list_widget.itemDoubleClicked.connect(self.on_item_double_clicked)
        layout.addWidget(self.list_widget)
        self.setLayout(layout)

    def manual_refresh(self):
        self.setWindowTitle("书架 (加载中...)")
        self.main_window.fetch_bookshelf_silent()

    def update_data(self, books):
        self.setWindowTitle(f"书架 (共 {len(books)} 本)")
        current_search = self.search_input.text()
        if current_search:
            self.filter_books(current_search)
        else:
            self.populate_list(books)

    def populate_list(self, books_to_show):
        self.list_widget.clear()
        if not books_to_show:
            return
        for book in books_to_show:
            display_text = f"{book['name']} - {book['author']}"
            item = QListWidgetItem(display_text)
            item.setData(Qt.UserRole, book)
            self.list_widget.addItem(item)

    def filter_books(self, text):
        text = text.lower()
        filtered = [
            book for book in self.main_window.books
            if text in book['name'].lower() or text in book['author'].lower()
        ]
        self.populate_list(filtered)

    def on_item_double_clicked(self, item):
        self.selected_book = item.data(Qt.UserRole)
        self.accept()


# ================= 独立窗口：目录选择器 =================
class ChapterLoader(QThread):
    loaded = pyqtSignal(list)
    failed = pyqtSignal(str)

    def __init__(self, ip, book_url):
        super().__init__()
        self.ip = ip
        self.book_url = book_url

    def run(self):
        try:
            url = f"{self.ip}/getChapterList"
            res = requests.get(url, params={"url": self.book_url}, timeout=CHAPTER_LIST_TIMEOUT)
            if self.isInterruptionRequested():
                return
            if res.status_code == 200:
                data = res.json()
                if data['isSuccess']:
                    self.loaded.emit(data['data'])
                else:
                    self.failed.emit(data.get('errorMsg', '未知错误'))
            else:
                self.failed.emit(f"HTTP {res.status_code}")
        except Exception as e:
            self.failed.emit(str(e))


class TocSelector(QDialog):
    def __init__(self, ip, book_url, current_index, cached_toc=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("目录加载中...")
        self.resize(400, 600)
        self.ip = ip
        self.book_url = book_url
        self.selected_index = None
        self.main_window = parent
        self.target_index = current_index
        self.loader = None
        self.setStyleSheet(DARK_STYLESHEET)

        self.initUI()

        if cached_toc and len(cached_toc) > 0:
            self.on_loaded(cached_toc)
        else:
            self.loader = ChapterLoader(ip, book_url)
            self.loader.loaded.connect(self.on_loaded)
            self.loader.failed.connect(self.on_failed)
            self.loader.start()

    def initUI(self):
        layout = QVBoxLayout()
        self.status_label = QLabel("正在从手机获取目录...")
        self.status_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.status_label)

        self.list_widget = QListWidget()
        self.list_widget.itemDoubleClicked.connect(self.on_item_double_clicked)
        self.list_widget.hide()
        layout.addWidget(self.list_widget)
        self.setLayout(layout)

    def on_loaded(self, chapters):
        try:
            self.setWindowTitle(f"目录 (共 {len(chapters)} 章)")
            self.status_label.hide()
            self.list_widget.show()

            if self.main_window:
                self.main_window.current_toc = chapters

            for i, chapter in enumerate(chapters):
                title = str(chapter.get('title', f'第 {i + 1} 章'))
                item = QListWidgetItem(title)
                idx = chapter.get('index', i)
                item.setData(Qt.UserRole, idx)
                self.list_widget.addItem(item)
                if i == self.target_index:
                    item.setSelected(True)
                    self.list_widget.scrollToItem(item, QListWidget.PositionAtCenter)
        except Exception as e:
            self.status_label.setText(f"数据解析错误: {str(e)}")
            self.status_label.show()

    def on_failed(self, msg):
        self.status_label.setText(f"目录加载失败: {msg}")

    def on_item_double_clicked(self, item):
        self.selected_index = item.data(Qt.UserRole)
        self.accept()

    def closeEvent(self, event):
        if self.loader and self.loader.isRunning():
            self.loader.requestInterruption()
            self.loader.wait(1000)
        super().closeEvent(event)


# ================= 设置窗口 =================
class SettingsDialog(QDialog):
    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self.main_window = parent
        self.original_text_opacity = self.config.get("text_opacity", self.config.get("opacity", 0.9))
        self.original_background_opacity = self.config.get("background_opacity", self.config.get("opacity", 0.9))
        self.original_line_spacing = self.config.get("line_spacing", 0)
        self.temp_text_color = self.config.get("text_color")
        self.temp_bg_color = self.config.get("bg_color")
        self.original_focus_hotkey = self.config.get("focus_hotkey", "Ctrl+Shift+R")

        self.setWindowTitle("设置")
        self.resize(350, 590)
        self.setStyleSheet(DARK_STYLESHEET)
        self.initUI()

    def initUI(self):
        layout = QFormLayout()
        self.ip_input = QLineEdit(self.config.get("ip"))
        layout.addRow("Legado地址:", self.ip_input)

        self.check_auto_mode = QCheckBox("自动挡 (变色龙)")
        self.check_auto_mode.setToolTip("开启后，背景变为背景色+极低透明度。\n字体颜色自动反转。")
        self.check_auto_mode.setIcon(make_icon("chameleon", 18))
        self.check_auto_mode.setChecked(self.config.get("auto_mode", False))
        self.check_auto_mode.toggled.connect(self.on_auto_mode_toggled)
        layout.addRow(self.check_auto_mode)

        self.check_antishot = QCheckBox("系统级防截屏")
        self.check_antishot.setToolTip("开启后，肉眼可见，但截图/录屏时窗口会完全消失（透明）。\n使用 Windows 系统底层保护。")
        self.check_antishot.setIcon(make_icon("shield", 18))
        self.check_antishot.setChecked(self.config.get("antishot_mode", False))
        self.check_antishot.toggled.connect(self.on_antishot_toggled)
        layout.addRow(self.check_antishot)

        self.text_opacity_slider = QSlider(Qt.Horizontal)
        self.text_opacity_slider.setRange(0, 100)
        self.text_opacity_slider.setValue(int(self.config.get("text_opacity", self.config.get("opacity", 0.9)) * 100))
        self.text_opacity_slider.valueChanged.connect(self.on_text_opacity_change)
        layout.addRow("字体透明度:", self.text_opacity_slider)

        self.background_opacity_slider = QSlider(Qt.Horizontal)
        self.background_opacity_slider.setRange(1, 100)
        self.background_opacity_slider.setValue(max(1, int(self.config.get("background_opacity", self.config.get("opacity", 0.9)) * 100)))
        self.background_opacity_slider.valueChanged.connect(self.on_background_opacity_change)
        layout.addRow("背景透明度:", self.background_opacity_slider)

        self.font_spin = QSpinBox()
        self.font_spin.setRange(8, 60)
        self.font_spin.setValue(self.config.get("font_size"))
        layout.addRow("字体大小:", self.font_spin)

        self.line_spacing_spin = QSpinBox()
        self.line_spacing_spin.setRange(0, 30)
        self.line_spacing_spin.setValue(self.config.get("line_spacing", 0))
        layout.addRow("行间距:", self.line_spacing_spin)

        self.font_combo = QFontComboBox()
        current_font_family = self.config.get("font_family", "Microsoft YaHei")
        self.font_combo.setCurrentFont(QFont(current_font_family))
        layout.addRow("字体样式:", self.font_combo)

        self.btn_text_color = QPushButton("文字颜色 (手动)")
        self.btn_text_color.setStyleSheet(f"background-color: {self.temp_text_color};")
        self.btn_text_color.clicked.connect(self.pick_text_color)
        self.btn_bg_color = QPushButton("背景颜色 (手动)")
        self.btn_bg_color.setStyleSheet(f"background-color: {self.temp_bg_color};")
        self.btn_bg_color.clicked.connect(self.pick_bg_color)
        layout.addRow(self.btn_text_color, self.btn_bg_color)

        self.check_ghost_mode = QCheckBox("幽灵模式 (移开变透明)")
        self.check_ghost_mode.setIcon(make_icon("ghost", 18))
        self.check_ghost_mode.setChecked(self.config.get("ghost_mode", False))
        layout.addRow(self.check_ghost_mode)

        self.check_ghost_mode.toggled.connect(self.on_ghost_mode_toggled)

        self.combo_ghost_mode_display = QComboBox()
        self.combo_ghost_mode_display.addItem("鼠标进入自动显示", "hover")
        self.combo_ghost_mode_display.addItem("双击后显示", "double_click")
        ghost_mode_display_mode = self.config.get("ghost_mode_display_mode", "hover")
        ghost_mode_display_index = self.combo_ghost_mode_display.findData(ghost_mode_display_mode)
        if ghost_mode_display_index < 0:
            ghost_mode_display_index = 0
        self.combo_ghost_mode_display.setCurrentIndex(ghost_mode_display_index)
        layout.addRow("幽灵显示方式:", self.combo_ghost_mode_display)

        self.check_show_in_switcher = QCheckBox("在 Alt+Tab 和任务栏中显示窗口")
        self.check_show_in_switcher.setChecked(self.config.get("show_in_switcher", False))
        layout.addRow(self.check_show_in_switcher)

        self.check_always_on_top = QCheckBox("窗口保持置顶")
        self.check_always_on_top.setChecked(self.config.get("always_on_top", True))
        layout.addRow(self.check_always_on_top)

        self.check_context_menu_requires_ctrl = QCheckBox("右键菜单需要按住 Ctrl")
        self.check_context_menu_requires_ctrl.setChecked(self.config.get("context_menu_requires_ctrl", True))
        layout.addRow(self.check_context_menu_requires_ctrl)

        self.boss_key_input = QLineEdit(self.config.get("boss_key", "Esc"))
        layout.addRow("全局老板键:", self.boss_key_input)

        self.focus_hotkey_input = QLineEdit(self.config.get("focus_hotkey", "Ctrl+Shift+R"))
        layout.addRow("唤醒快捷键:", self.focus_hotkey_input)

        btn_save = QPushButton("保存并应用")
        btn_save.setIcon(make_icon("save", 18))
        btn_save.setFixedHeight(36)
        btn_save.clicked.connect(self.accept)
        layout.addRow(btn_save)

        self.on_auto_mode_toggled(self.check_auto_mode.isChecked())
        self.on_ghost_mode_toggled(self.check_ghost_mode.isChecked())
        self.on_antishot_toggled(self.check_antishot.isChecked())
        self.setLayout(layout)

    def on_auto_mode_toggled(self, checked):
        self.btn_bg_color.setEnabled(not checked)
        self.btn_text_color.setEnabled(not checked)
        self.text_opacity_slider.setEnabled(True)
        self.background_opacity_slider.setEnabled(True)

    def on_antishot_toggled(self, checked):
        if self.main_window:
            hwnd = int(self.main_window.winId())
            set_window_protection(hwnd, checked)

    def on_ghost_mode_toggled(self, checked):
        self.combo_ghost_mode_display.setEnabled(checked)

    def on_text_opacity_change(self, value):
        self.config["text_opacity"] = value / 100.0
        if self.main_window:
            self.main_window.apply_style()

    def on_background_opacity_change(self, value):
        self.config["background_opacity"] = max(0.01, value / 100.0)
        if self.main_window:
            self.main_window.apply_style()

    def pick_text_color(self):
        color = QColorDialog.getColor()
        if color.isValid():
            self.temp_text_color = f"rgba({color.red()}, {color.green()}, {color.blue()}, {color.alpha()})"
            self.btn_text_color.setStyleSheet(f"background-color: {self.temp_text_color};")

    def pick_bg_color(self):
        color = QColorDialog.getColor(options=QColorDialog.ShowAlphaChannel)
        if color.isValid():
            self.temp_bg_color = f"rgba({color.red()}, {color.green()}, {color.blue()}, {color.alpha()})"
            self.btn_bg_color.setStyleSheet(f"background-color: {self.temp_bg_color};")

    def accept(self):
        self.config.update({
            "ip": self.ip_input.text().strip(),
            "font_size": self.font_spin.value(),
            "line_spacing": self.line_spacing_spin.value(),
            "font_family": self.font_combo.currentFont().family(),
            "boss_key": self.boss_key_input.text().strip(),
            "focus_hotkey": self.focus_hotkey_input.text().strip() or "Ctrl+Shift+R",
            "text_color": self.temp_text_color,
            "bg_color": self.temp_bg_color,
            "text_opacity": self.text_opacity_slider.value() / 100.0,
            "background_opacity": max(0.01, self.background_opacity_slider.value() / 100.0),
            "ghost_mode": self.check_ghost_mode.isChecked(),
            "ghost_mode_display_mode": self.combo_ghost_mode_display.currentData(),
            "show_in_switcher": self.check_show_in_switcher.isChecked(),
            "always_on_top": self.check_always_on_top.isChecked(),
            "context_menu_requires_ctrl": self.check_context_menu_requires_ctrl.isChecked(),
            "auto_mode": self.check_auto_mode.isChecked(),
            "antishot_mode": self.check_antishot.isChecked(),
        })
        super().accept()

    def reject(self):
        self.config["text_opacity"] = self.original_text_opacity
        self.config["background_opacity"] = self.original_background_opacity
        self.config["line_spacing"] = self.original_line_spacing
        self.config["focus_hotkey"] = self.original_focus_hotkey
        if self.main_window:
            self.main_window.apply_style()
            set_window_protection(int(self.main_window.winId()), self.config.get("antishot_mode", False))
        super().reject()


# ================= 单实例 IPC 常量 =================
SINGLE_INSTANCE_SERVER = "FishingRead_IPC"


def try_activate_existing_instance():
    """检查是否已有实例在运行，有则激活其窗口并返回 True。"""
    shared_mem = QSharedMemory(SINGLE_INSTANCE_SERVER)
    if not shared_mem.attach():
        return False, shared_mem  # 没有其他实例在运行

    # 尝试连接 IPC 服务器，发送显示信号
    socket = QLocalSocket()
    socket.connectToServer(SINGLE_INSTANCE_SERVER)
    if socket.waitForConnected(1000):
        socket.write(b"show")
        socket.waitForBytesWritten(500)
        socket.disconnectFromServer()
        return True, shared_mem  # 已激活旧实例

    # 服务器未响应，旧实例可能已崩溃，清理并继续
    shared_mem.detach()
    QLocalServer.removeServer(SINGLE_INSTANCE_SERVER)
    return False, shared_mem


# ================= 主程序 =================
class FishingRead(QWidget):
    update_text_signal = pyqtSignal(str, bool)
    hotkey_signal = pyqtSignal()
    focus_hotkey_signal = pyqtSignal()
    bookshelf_updated_signal = pyqtSignal(list)
    chapter_loaded_signal = pyqtSignal(int, str, bool, int, int, int, int)
    chapter_load_failed_signal = pyqtSignal(str, int)
    HOTKEY_ID_BOSS = 1
    HOTKEY_ID_FOCUS = 2

    def __init__(self):
        super().__init__()
        self.load_config()
        self.is_settings_open = False

        # --- 网络书架数据 ---
        self.books = []
        self.current_book = None
        self.current_chapter_index = 0
        self.current_toc = []
        self.is_chapter_loading = False
        self.chapter_request_token = 0
        self.current_chapter_progress = 0
        self.last_progress_sync_time = time.monotonic()
        self._progress_restore = None  # 章节加载后要恢复的字符位置（不含标题前缀）
        self._current_content_raw_length = 0   # 当前章节原始内容长度（不含标题前缀）
        self._current_title_prefix_len = 0     # 当前章节标题前缀长度
        self.chapter_cache = {}
        self.chapter_cache_lock = threading.Lock()
        self.prefetching_chapters = set()

        # --- 本地书籍数据 ---
        self.is_local_mode = False  # 模式标记
        self.local_full_text = ""  # 本地文件全文内容
        self.local_start_index = 0  # 当前页起始字符在全文中的索引 (锚点)
        self.local_page_history = []  # 记录翻页历史，用于"上一页"
        self.local_file_path = ""  # 当前文件路径

        # --- 界面控制 ---
        self.single_line_height = 20
        self.ghost_text_visible = True
        self.current_display_text = ""
        self.current_scroll_value = 0
        self.content_scroll_token = 0
        self.pending_content_scroll_anchor = None
        self.is_resizing = False
        self.is_moving = False
        self.resize_margin = 15
        self.last_toggle_time = 0
        self.local_shortcut = None
        self.focus_shortcut = None
        self.registered_hotkey_ids = set()
        self.book_selector_dialog = None
        self.oldPos = QPoint(0, 0)
        self._startup_guard = True  # 阻止 ghost 模式在首次显示时立即隐藏窗口
        self._first_show = True     # 标记是否首次显示

        self.chameleon_timer = QTimer(self)
        self.chameleon_timer.setInterval(500)
        self.chameleon_timer.timeout.connect(self.adjust_color_to_background)

        self.progress_auto_save_timer = QTimer(self)
        self.progress_auto_save_timer.setInterval(PROGRESS_AUTO_SAVE_CHECK_INTERVAL * 1000)
        self.progress_auto_save_timer.timeout.connect(self.auto_save_progress_if_needed)
        self.progress_auto_save_timer.start()

        self.initUI()
        self.initTray()

        self.update_text_signal.connect(self.on_update_text_safe)
        self.hotkey_signal.connect(self.toggle_window)
        self.focus_hotkey_signal.connect(self.reveal_window)
        self.bookshelf_updated_signal.connect(self.on_bookshelf_updated)
        self.chapter_loaded_signal.connect(self.on_chapter_loaded)
        self.chapter_load_failed_signal.connect(self.on_chapter_load_failed)

        # 设置单实例 IPC 服务器（接收重复启动时的激活信号）
        self.setup_ipc_server()

        # __init__ 中不注册原生热键（HWND 尚未稳定），在 showEvent 中延迟注册
        # 但创建 QShortcut 实例（仅当窗口可见且聚焦时生效，early binding 无副作用）
        self._create_qshortcuts()

        # 释放启动守卫：延迟 1.5 秒后允许 ghost 模式隐藏窗口
        QTimer.singleShot(1500, lambda: self._release_startup_guard())

        # 尝试恢复上次打开的本地文件
        if self.config.get("last_local_file") and os.path.exists(self.config["last_local_file"]):
            self.update_text_signal.emit("正在恢复上次阅读...", False)
            QTimer.singleShot(500, self.restore_last_local_file)
        elif self.config["ip"] and self.config["ip"].startswith("http"):
            self.fetch_bookshelf_silent()
            self.update_text_signal.emit("初始化完成。\n右键菜单可打开本地TXT文件。", False)
        else:
            self.update_text_signal.emit("欢迎使用。\n右键打开本地书籍或设置Legado。", False)

        if self.config.get("antishot_mode", False):
            QTimer.singleShot(100, lambda: set_window_protection(int(self.winId()), True))

        # 启动后尽快完成激活（极短延迟，确保窗口已显示、不干扰用户操作）
        QTimer.singleShot(50, self.startup_activate)

    def startup_activate(self):
        """启动后轻量激活：注册热键 + 窗口激活（不强制抢焦点避免干扰）。"""
        # 注册全局热键
        self.refresh_hotkeys()
        # 确保窗口已显示
        if not self.isVisible():
            self.showNormal()
        # 轻量激活：将窗口提到前台但不强制置顶（ex.show() 已完成首次显示）
        self.raise_()
        self.activateWindow()
        if self.config.get("auto_mode", False):
            self.chameleon_timer.start()
            self.adjust_color_to_background()
        if self.config.get("antishot_mode", False):
            set_window_protection(int(self.winId()), True)

    # --- 单实例 IPC 服务器（接收重复启动时的激活信号） ---
    def setup_ipc_server(self):
        """启动 IPC 本地服务器，监听重复运行的激活请求。"""
        QLocalServer.removeServer(SINGLE_INSTANCE_SERVER)
        self.ipc_server = QLocalServer()
        self.ipc_server.listen(SINGLE_INSTANCE_SERVER)
        self.ipc_server.newConnection.connect(self._on_ipc_new_connection)

    def _on_ipc_new_connection(self):
        conn = self.ipc_server.nextPendingConnection()
        if conn:
            conn.readyRead.connect(lambda: self._handle_ipc_message(conn))

    def _handle_ipc_message(self, conn):
        data = conn.readAll().data()
        if data == b"show":
            # 重复启动时，激活已有窗口
            self.reveal_window()
            self.refresh_hotkeys()
        conn.disconnectFromServer()

    def showEvent(self, event):
        super().showEvent(event)
        # 窗口首次显示标记已消费（热键注册统一在 startup_activate 中处理）
        if self._first_show:
            self._first_show = False

    def _release_startup_guard(self):
        self._startup_guard = False

    def restore_last_local_file(self):
        path = self.config["last_local_file"]
        pos = self.config.get("last_local_pos", 0)
        self.load_local_file(path, target_pos=pos)

    # --- 打开本地文件 (防止 0xC0000409 崩溃) ---
    def open_local_file_dialog(self):
        options = QFileDialog.Options()
        # 【关键】禁用 Windows 原生对话框，改用 Qt 内置对话框
        options |= QFileDialog.DontUseNativeDialog

        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择文本文件",
            "",
            "Text Files (*.txt);;All Files (*)",
            options=options
        )

        if file_path:
            # 检查是否是同一本书
            last_file = self.config.get("last_local_file", "")

            is_same_file = False
            if last_file:
                try:
                    is_same_file = os.path.normpath(file_path) == os.path.normpath(last_file)
                except OSError:
                    is_same_file = (file_path == last_file)

            if is_same_file:
                # 是同一本书：恢复上次进度
                saved_pos = self.config.get("last_local_pos", 0)
                self.load_local_file(file_path, target_pos=saved_pos)
            else:
                # 是新书：从头开始
                self.load_local_file(file_path, target_pos=0)

    def load_local_file(self, file_path, target_pos=0):
        try:
            content = ""
            # 尝试多种编码读取
            try:
                with open(file_path, 'r', encoding='utf-8-sig') as f:
                    content = f.read()
            except UnicodeDecodeError:
                try:
                    with open(file_path, 'r', encoding='gb18030') as f:
                        content = f.read()
                except Exception as e:
                    self.update_text_signal.emit(f"编码无法识别，请转为UTF-8或GBK", False)
                    return

            if not content:
                self.update_text_signal.emit("文件为空", False)
                return

            self.is_local_mode = True
            self.local_file_path = file_path
            self.local_full_text = content

            # 安全校验索引
            safe_pos = min(max(0, target_pos), len(content) - 1)
            self.local_start_index = safe_pos
            self.local_page_history = []

            # 【关键】加载时立即保存配置
            self.config["last_local_file"] = file_path
            self.config["last_local_pos"] = safe_pos
            self.save_config()

            self.render_local_page()

            if safe_pos > 0:
                self.update_text_signal.emit(f"已恢复进度: {os.path.basename(file_path)}", False)

        except Exception as e:
            traceback.print_exc()
            self.update_text_signal.emit(f"打开文件失败: {str(e)}", False)

    # --- 本地分页渲染算法 (锚点核心) ---
    def render_local_page(self):
        if not self.is_local_mode or not self.local_full_text:
            return

        # 截取缓冲区（保证填满屏幕，取5000字足以覆盖各种屏幕）
        end_buffer = min(self.local_start_index + LOCAL_PAGE_BUFFER_SIZE, len(self.local_full_text))

        display_text = self.local_full_text[self.local_start_index: end_buffer]

        self.current_display_text = display_text
        self.set_text_edit_content(display_text)

        # 【关键】强制滚动条回顶，确保 local_start_index 对应的字符永远在第一行
        self.text_edit.verticalScrollBar().setValue(0)
        self.current_scroll_value = 0

    # --- 核心：基于几何坐标探测下一页起始位置 ---
    def calc_next_page_start(self):
        """利用视图几何坐标，探测屏幕底部边缘的字符位置"""
        # 【新增保护】防止空内容计算
        if not self.text_edit.toPlainText():
            return 0

        viewport_h = self.text_edit.viewport().height()
        # 探测点：视图左下角再往下一点点 (取下一行的开头)
        target_y = viewport_h + 2

        cursor = self.text_edit.cursorForPosition(QPoint(0, target_y))
        next_pos_in_buffer = cursor.position()

        # 异常处理：如果一页装不满，cursor会指向文档末尾
        if next_pos_in_buffer >= len(self.text_edit.toPlainText()):
            return len(self.text_edit.toPlainText())

        return next_pos_in_buffer

    # --- 核心：基于反向排版探测上一页起始位置 ---
    def calc_prev_page_start(self):
        """通过加载前文并滚到底部，探测上一页的起始位置"""
        if self.local_start_index == 0:
            return 0

        self.text_edit.setUpdatesEnabled(False)
        try:
            temp_start = max(0, self.local_start_index - LOCAL_PAGE_BUFFER_SIZE)
            prev_content = self.local_full_text[temp_start: self.local_start_index]

            self.set_text_edit_content(prev_content)

            scrollbar = self.text_edit.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())

            cursor = self.text_edit.cursorForPosition(QPoint(0, 0))
            chars_in_prev_page = len(prev_content) - cursor.position()

            real_prev_start = self.local_start_index - chars_in_prev_page

            return max(0, real_prev_start)
        finally:
            self.text_edit.setUpdatesEnabled(True)

    # --- 翻页逻辑 (即时存档 + 几何分页) ---
    def scroll_page(self, direction):
        if self.is_local_mode:
            # --- 本地模式 ---
            # 【新增保护】
            if not self.local_full_text:
                return

            if direction > 0:  # 下一页
                if self.local_start_index >= len(self.local_full_text):
                    return

                # 几何计算本页内容量
                step = self.calc_next_page_start()
                if step == 0 and self.local_start_index < len(self.local_full_text):
                    step = 1

                self.local_page_history.append(self.local_start_index)
                self.local_start_index += step

                if self.local_start_index > len(self.local_full_text):
                    self.local_start_index = len(self.local_full_text)

                self.render_local_page()

            else:  # 上一页
                if self.local_page_history:
                    # 优先使用历史
                    self.local_start_index = self.local_page_history.pop()
                else:
                    # 无历史时，反向排版计算
                    self.local_start_index = self.calc_prev_page_start()

                self.render_local_page()

            # 【关键】即时存档
            self.config["last_local_pos"] = self.local_start_index
            self.save_config()

        else:
            # --- 网络模式 ---
            # 【关键保护】如果还没选书，直接拦截滚动，防止崩溃
            if not self.current_book or self.is_chapter_loading:
                return

            scrollbar = self.text_edit.verticalScrollBar()
            current_val = scrollbar.value()
            max_val = scrollbar.maximum()
            min_val = scrollbar.minimum()

            target_val = current_val + (direction * (self.text_edit.viewport().height() - 30))

            if direction > 0:
                if current_val >= max_val - 5:
                    self.next_chapter()
                else:
                    scrollbar.setValue(min(target_val, max_val))
            else:
                if current_val <= min_val + 5:
                    self.prev_chapter()
                else:
                    scrollbar.setValue(max(target_val, min_val))

    def load_config(self):
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
                    file_config = json.load(f)
                self.config = self.normalize_config(file_config)
            except (OSError, json.JSONDecodeError):
                self.config = DEFAULT_CONFIG.copy()
        else:
            self.config = DEFAULT_CONFIG.copy()

    def normalize_config(self, file_config):
        config = {**DEFAULT_CONFIG, **file_config}
        if "show_in_switcher" not in file_config:
            if "show_in_alt_tab" in file_config or "show_in_taskbar" in file_config:
                config["show_in_switcher"] = bool(
                    file_config.get("show_in_alt_tab", False) or file_config.get("show_in_taskbar", False)
                )
            else:
                config["show_in_switcher"] = not file_config.get("hide_from_alt_tab", True)

        if "text_opacity" not in file_config:
            config["text_opacity"] = file_config.get("opacity", DEFAULT_CONFIG["text_opacity"])
        if "background_opacity" not in file_config:
            config["background_opacity"] = file_config.get("opacity", DEFAULT_CONFIG["background_opacity"])

        config["background_opacity"] = max(
            0.01,
            config.get("background_opacity", DEFAULT_CONFIG["background_opacity"])
        )
        for key in LEGACY_CONFIG_KEYS:
            config.pop(key, None)
        return config

    def save_config(self):
        try:
            for key in LEGACY_CONFIG_KEYS:
                self.config.pop(key, None)
            self.config["background_opacity"] = max(0.01, self.config.get("background_opacity", DEFAULT_CONFIG["background_opacity"]))
            self.config["window_x"] = self.x()
            self.config["window_y"] = self.y()
            self.config["window_width"] = self.width()
            self.config["window_height"] = self.height()
            with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            print(f"Failed to save config: {e}")

    def apply_text_layout(self):
        line_spacing = max(0, self.config.get("line_spacing", 0))
        cursor = QTextCursor(self.text_edit.document())
        cursor.select(QTextCursor.Document)
        block_format = QTextBlockFormat()
        block_format.setLineHeight(max(1, self.single_line_height), QTextBlockFormat.FixedHeight)
        if line_spacing == 0:
            block_format.setTopMargin(0)
            block_format.setBottomMargin(0)
        else:
            block_format.setTopMargin(0)
            block_format.setBottomMargin(line_spacing)
        cursor.mergeBlockFormat(block_format)
        cursor.clearSelection()

    def set_text_edit_content(self, text):
        self.text_edit.setPlainText(text)
        self.apply_text_layout()

    def apply_content_scroll_position(self, is_bottom, token):
        if token != self.content_scroll_token:
            return

        scrollbar = self.text_edit.verticalScrollBar()
        if is_bottom:
            self.text_edit.moveCursor(QTextCursor.End)
            self.text_edit.ensureCursorVisible()
            scrollbar.setValue(scrollbar.maximum())
        else:
            self.text_edit.moveCursor(QTextCursor.Start)
            scrollbar.setValue(0)
        self.current_scroll_value = scrollbar.value()

    def schedule_content_scroll_position(self, is_bottom):
        self.content_scroll_token += 1
        token = self.content_scroll_token
        self.pending_content_scroll_anchor = (is_bottom, token)
        self.apply_content_scroll_position(is_bottom, token)
        for delay in (0, 50, 150, 300):
            QTimer.singleShot(delay, lambda is_bottom=is_bottom, token=token: self.apply_content_scroll_position(is_bottom, token))
        QTimer.singleShot(350, lambda token=token: self.clear_pending_content_scroll_anchor(token))

    def _schedule_progress_restore_scroll(self, display_char_pos):
        """按字符位置恢复滚动，延迟等待文本布局稳定。"""
        token = self.chapter_request_token
        for delay in (0, 100, 300):
            QTimer.singleShot(delay, lambda p=display_char_pos, t=token: self._apply_char_pos_scroll(p, t))

    def _apply_char_pos_scroll(self, display_char_pos, token):
        """将 QTextEdit 滚动到指定字符位置在视口顶部。"""
        if token != self.chapter_request_token:
            return
        doc = self.text_edit.document()
        max_pos = doc.characterCount() - 1
        target = min(display_char_pos, max_pos)
        if target <= 0:
            return

        cursor = QTextCursor(doc)
        cursor.setPosition(target)
        self.text_edit.setTextCursor(cursor)

        # 计算光标矩形并调整滚动，使光标位于视口顶部
        cursor_rect = self.text_edit.cursorRect(cursor)
        scrollbar = self.text_edit.verticalScrollBar()
        scrollbar.setValue(scrollbar.value() + cursor_rect.top())

    def clear_pending_content_scroll_anchor(self, token):
        if self.pending_content_scroll_anchor and self.pending_content_scroll_anchor[1] == token:
            self.pending_content_scroll_anchor = None

    def on_content_scroll_range_changed(self, minimum, maximum):
        if not self.pending_content_scroll_anchor:
            return

        is_bottom, token = self.pending_content_scroll_anchor
        self.apply_content_scroll_position(is_bottom, token)
        if token == self.content_scroll_token and maximum > minimum:
            self.pending_content_scroll_anchor = None

    def on_update_text_safe(self, text, is_bottom):
        self.current_display_text = text
        if self.config.get("ghost_mode", False) and not self.ghost_text_visible:
            self.current_scroll_value = -1 if is_bottom else 0
            self.set_text_edit_content("")
            self.text_edit.verticalScrollBar().setValue(0)
            return

        self.set_text_edit_content(text)

        # 如果设置了进度恢复，按百分比滚动而非默认的顶部/底部
        if self._progress_restore is not None:
            progress = self._progress_restore
            self._progress_restore = None  # 消费掉，避免重复触发
            self._schedule_progress_restore_scroll(progress)
        else:
            self.schedule_content_scroll_position(is_bottom)

    def on_bookshelf_updated(self, books):
        self.books = books
        if self.book_selector_dialog and self.book_selector_dialog.isVisible():
            self.book_selector_dialog.update_data(books)

    def on_chapter_loaded(
        self,
        chapter_index,
        full_text,
        scroll_to_bottom,
        request_token,
        display_char_pos,
        raw_length,
        title_prefix_len
    ):
        if request_token != self.chapter_request_token:
            return

        self.is_chapter_loading = False
        self.current_chapter_index = chapter_index
        self._current_content_raw_length = raw_length
        self._current_title_prefix_len = title_prefix_len

        # 存储显示字符位置（含标题前缀），用于文本渲染后恢复滚动
        self._progress_restore = None
        if not scroll_to_bottom and display_char_pos > 0:
            self._progress_restore = display_char_pos

        # 同步到 Legado：存入当前视口位置的原始字符数（不含标题前缀）
        raw_char_pos = max(0, display_char_pos - title_prefix_len) if not scroll_to_bottom else raw_length
        self.current_chapter_progress = display_char_pos
        if self.current_book:
            self.current_book["durChapterIndex"] = chapter_index
            self.current_book["durChapterPos"] = raw_char_pos

        self.update_text_signal.emit(full_text, scroll_to_bottom)
        self.sync_progress_async(raw_char_pos)
        if self.current_book and not self.is_local_mode:
            book_url = self.current_book.get('bookUrl')
            self.trim_chapter_cache(book_url, chapter_index)
            self.prefetch_future_chapters(book_url, chapter_index)

    def on_chapter_load_failed(self, error_text, request_token):
        if request_token != self.chapter_request_token:
            return

        self.is_chapter_loading = False
        self.update_text_signal.emit(error_text, False)

    def parse_native_hotkey(self, hotkey_str):
        if not hotkey_str:
            return None

        vk_map = {
            "esc": 0x1B,
            "escape": 0x1B,
            "tab": 0x09,
            "space": 0x20,
            "enter": 0x0D,
            "return": 0x0D,
            "left": 0x25,
            "up": 0x26,
            "right": 0x27,
            "down": 0x28,
            "pageup": 0x21,
            "pgup": 0x21,
            "pagedown": 0x22,
            "pgdn": 0x22,
            "home": 0x24,
            "end": 0x23,
            "insert": 0x2D,
            "delete": 0x2E,
            "del": 0x2E,
        }

        modifiers = 0
        key_code = None
        parts = [part.strip().lower() for part in hotkey_str.replace("-", "+").split("+") if part.strip()]
        for part in parts:
            if part in ("ctrl", "control"):
                modifiers |= MOD_CONTROL
            elif part == "shift":
                modifiers |= MOD_SHIFT
            elif part == "alt":
                modifiers |= MOD_ALT
            elif part in ("win", "windows", "meta"):
                modifiers |= MOD_WIN
            elif len(part) == 1 and part.isalpha():
                key_code = ord(part.upper())
            elif len(part) == 1 and part.isdigit():
                key_code = ord(part)
            elif part.startswith("f") and part[1:].isdigit():
                fn_num = int(part[1:])
                if 1 <= fn_num <= 24:
                    key_code = 0x6F + fn_num
            elif part in vk_map:
                key_code = vk_map[part]

        if key_code is None:
            return None

        return modifiers | MOD_NOREPEAT, key_code

    def unregister_native_hotkeys(self):
        if sys.platform != "win32":
            self.registered_hotkey_ids.clear()
            return

        hwnd = int(self.winId())
        user32 = ctypes.windll.user32
        for hotkey_id in list(self.registered_hotkey_ids):
            try:
                user32.UnregisterHotKey(hwnd, hotkey_id)
            except Exception:
                pass
        self.registered_hotkey_ids.clear()

    def register_native_hotkey(self, hotkey_id, hotkey_str):
        if sys.platform != "win32":
            return False

        parsed_hotkey = self.parse_native_hotkey(hotkey_str)
        if not parsed_hotkey:
            return False

        modifiers, key_code = parsed_hotkey
        hwnd = int(self.winId())
        user32 = ctypes.windll.user32
        user32.UnregisterHotKey(hwnd, hotkey_id)
        if user32.RegisterHotKey(hwnd, hotkey_id, modifiers, key_code):
            self.registered_hotkey_ids.add(hotkey_id)
            return True
        return False

    def _create_qshortcuts(self):
        """仅创建 QShortcut 实例（不注册原生热键），可在窗口显示前安全调用。"""
        hotkey_str = self.config.get("boss_key", "Esc")
        focus_hotkey_str = self.config.get("focus_hotkey", "Ctrl+Shift+R")
        try:
            if self.local_shortcut:
                self.local_shortcut.setKey(QKeySequence())
                self.local_shortcut = None
            self.local_shortcut = QShortcut(QKeySequence(hotkey_str), self)
            self.local_shortcut.activated.connect(self.toggle_window)

            if self.focus_shortcut:
                self.focus_shortcut.setKey(QKeySequence())
                self.focus_shortcut = None
            self.focus_shortcut = QShortcut(QKeySequence(focus_hotkey_str), self)
            self.focus_shortcut.activated.connect(self.reveal_window)
        except Exception:
            pass

    def refresh_hotkeys(self):
        hotkey_str = self.config.get("boss_key", "Esc")
        focus_hotkey_str = self.config.get("focus_hotkey", "Ctrl+Shift+R")
        self.unregister_native_hotkeys()
        self.register_native_hotkey(self.HOTKEY_ID_BOSS, hotkey_str)
        self.register_native_hotkey(self.HOTKEY_ID_FOCUS, focus_hotkey_str)
        self._create_qshortcuts()

    def on_global_hotkey_triggered(self):
        self.hotkey_signal.emit()

    def on_focus_hotkey_triggered(self):
        self.focus_hotkey_signal.emit()

    def nativeEvent(self, event_type, message):
        event_name = event_type.decode() if isinstance(event_type, bytes) else event_type
        if sys.platform == "win32" and event_name in ("windows_generic_MSG", "windows_dispatcher_MSG"):
            msg = wintypes.MSG.from_address(int(message))
            if msg.message == WM_HOTKEY:
                if msg.wParam == self.HOTKEY_ID_BOSS:
                    self.on_global_hotkey_triggered()
                    return True, 0
                if msg.wParam == self.HOTKEY_ID_FOCUS:
                    self.on_focus_hotkey_triggered()
                    return True, 0
        return super().nativeEvent(event_type, message)

    def build_window_flags(self):
        flags = Qt.FramelessWindowHint
        if self.config.get("always_on_top", True):
            flags |= Qt.WindowStaysOnTopHint
        if self.config.get("show_in_switcher", False):
            flags |= Qt.Window
        else:
            flags |= Qt.Tool
        return flags

    def apply_window_flags(self):
        was_visible = self.isVisible()
        geometry = self.geometry()
        self.setWindowFlags(self.build_window_flags())
        self.setGeometry(geometry)

        if was_visible:
            self.show()
            self.apply_style()
            self.refresh_hotkeys()  # setWindowFlags 可能重建原生窗口，需重新注册热键
            if self.config.get("antishot_mode", False):
                set_window_protection(int(self.winId()), True)

    def initUI(self):
        self.apply_window_flags()
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMouseTracking(True)

        self.main_layout = QVBoxLayout()
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        self.content_frame = CornerFrame()
        self.content_layout = QVBoxLayout(self.content_frame)

        self.update_content_margins()
        self.content_layout.setSpacing(0)

        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setFrameStyle(QFrame.NoFrame)
        self.text_edit.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.text_edit.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.text_edit.setTextInteractionFlags(Qt.NoTextInteraction)
        self.text_edit.setFocusPolicy(Qt.NoFocus)

        self.text_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Ignored)
        self.text_edit.setMinimumHeight(0)
        self.text_edit.document().setDocumentMargin(0)
        self.text_edit.verticalScrollBar().rangeChanged.connect(self.on_content_scroll_range_changed)

        self.text_edit.installEventFilter(self)
        self.text_edit.viewport().installEventFilter(self)

        self.content_layout.addWidget(self.text_edit)
        self.main_layout.addWidget(self.content_frame)
        self.setLayout(self.main_layout)

        w = self.config.get("window_width", 400)
        h = self.config.get("window_height", 300)
        x = self.config.get("window_x", 100)
        y = self.config.get("window_y", 100)
        self.resize(w, h)
        self.move(x, y)
        self.oldPos = self.pos()

        self.apply_style()

    def show_context_menu(self, global_pos):
        cmenu = QMenu(self)
        cmenu.setStyleSheet(MENU_STYLESHEET)

        add_menu_action(cmenu, "打开本地 TXT", self.open_local_file_dialog, "folder-open")
        cmenu.addSeparator()
        add_menu_action(cmenu, "网络书架 (搜索)", self.open_book_selector, "bookshelf")
        add_menu_action(cmenu, "章节目录 (网络)", self.open_toc_selector, "book-open")
        cmenu.addSeparator()
        add_menu_action(cmenu, "设置", self.open_settings, "settings")
        cmenu.addSeparator()
        add_menu_action(cmenu, "退出", self.quit_app, "x")

        cmenu.exec_(global_pos)

    def should_open_context_menu(self, modifiers):
        if not self.config.get("context_menu_requires_ctrl", True):
            return True
        return bool(modifiers & Qt.ControlModifier)

    def eventFilter(self, source, event):
        if source in (self.text_edit, self.text_edit.viewport()) and event.type() == QEvent.Wheel:
            # 幽灵模式隐藏内容时，窗口仍可能接收滚轮，必须阻止误翻页。
            if self.config.get("ghost_mode", False) and not self.ghost_text_visible:
                return True

            # 【关键保护】如果既没选书，也不是本地模式，直接拦截滚轮不处理
            if not self.is_local_mode and not self.current_book:
                return True

            delta = event.angleDelta().y()
            if self.is_local_mode:
                if delta < 0:
                    self.scroll_page(1)
                elif delta > 0:
                    self.scroll_page(-1)
                return True
            else:
                scrollbar = self.text_edit.verticalScrollBar()
                if delta < 0:
                    if scrollbar.value() >= scrollbar.maximum() - 2:
                        self.next_chapter()
                        return True
                elif delta > 0:
                    if scrollbar.value() <= scrollbar.minimum() + 2:
                        self.prev_chapter()
                        return True
        if source == self.text_edit.viewport():
            local_pos = self.mapFromGlobal(event.globalPos()) if hasattr(event, "globalPos") else None

            if event.type() == QEvent.MouseMove and local_pos is not None and not (event.buttons() & Qt.LeftButton):
                if self.is_in_resize_area(local_pos):
                    self.setCursor(Qt.SizeFDiagCursor)
                elif not self.is_resizing:
                    self.setCursor(Qt.ArrowCursor)

            if event.type() == QEvent.MouseButtonPress and event.button() == Qt.LeftButton:
                if local_pos is not None:
                    self.begin_pointer_action(local_pos, event.globalPos())
                return True

            if event.type() == QEvent.MouseMove and event.buttons() & Qt.LeftButton:
                if local_pos is not None:
                    self.handle_pointer_drag(local_pos, event.globalPos())
                return True

            if event.type() == QEvent.MouseButtonRelease:
                self.finish_pointer_action()
                return True

            if event.type() == QEvent.MouseButtonDblClick and event.button() == Qt.LeftButton:
                if self.config.get("ghost_mode", False) and self.get_ghost_mode_display_mode() == "double_click":
                    self.set_ghost_text_visible(True)
                return True

            if event.type() == QEvent.MouseButtonPress and event.button() == Qt.RightButton:
                if self.should_open_context_menu(event.modifiers()):
                    self.show_context_menu(event.globalPos())
                return True

            if event.type() == QEvent.ContextMenu:
                if self.should_open_context_menu(event.modifiers()):
                    self.show_context_menu(event.globalPos())
                return True

        return super().eventFilter(source, event)

    def initTray(self):
        self.tray_icon = QSystemTrayIcon(self)
        icon = get_app_icon()
        self.setWindowIcon(icon)
        self.tray_icon.setIcon(icon)

        tray_menu = QMenu()
        tray_menu.setStyleSheet(MENU_STYLESHEET)
        add_menu_action(tray_menu, "显示 / 隐藏", self.toggle_window, "eye")
        tray_menu.addSeparator()
        add_menu_action(tray_menu, "退出", self.quit_app, "x")

        self.tray_icon.setContextMenu(tray_menu)
        self.tray_icon.activated.connect(self.on_tray_activated)
        self.tray_icon.show()

    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self.toggle_window()

    def toggle_window(self):
        current_time = time.time()
        if current_time - self.last_toggle_time < 0.3:
            return
        self.last_toggle_time = current_time

        if self.isVisible():
            self.sync_progress_async()
            self.hide()
        else:
            self.showNormal()
            self.apply_style()
            self.activateWindow()
            if self.config.get("auto_mode", False):
                self.chameleon_timer.start()
                self.adjust_color_to_background()

            if self.config.get("antishot_mode", False):
                set_window_protection(int(self.winId()), True)

    def reveal_window(self):
        if not self.isVisible():
            self.showNormal()

        if self.config.get("ghost_mode", False) and not self.ghost_text_visible:
            self.set_ghost_text_visible(True)
        else:
            self.apply_style()

        self.raise_()
        self.activateWindow()

        try:
            ctypes.windll.user32.SetForegroundWindow(int(self.winId()))
        except Exception:
            pass

        if self.config.get("auto_mode", False):
            self.chameleon_timer.start()
            self.adjust_color_to_background()

        if self.config.get("antishot_mode", False):
            set_window_protection(int(self.winId()), True)

    def adjust_color_to_background(self):
        if not self.isVisible() or not self.config.get("auto_mode"):
            self.chameleon_timer.stop()
            return

        screen = QApplication.primaryScreen()
        if not screen: return

        pick_x = self.x() - 5
        pick_y = self.y() + 10

        if pick_x < 0:
            pick_x = self.x() + self.width() + 5

        pixmap = screen.grabWindow(0, pick_x, pick_y, 1, 1)
        img = pixmap.toImage()

        if img.width() > 0:
            color = img.pixelColor(0, 0)
            brightness = 0.299 * color.red() + 0.587 * color.green() + 0.114 * color.blue()

            self.content_frame.set_auto_bg_color(color)
            base_text_color = (0, 0, 0) if brightness > 128 else (255, 255, 255)
            user_alpha = int(self.config.get("text_opacity", 0.9) * 255)
            rgba_color = f"rgba({base_text_color[0]}, {base_text_color[1]}, {base_text_color[2]}, {user_alpha})"

            self.text_edit.setStyleSheet(f"""
                QTextEdit {{
                    color: {rgba_color};
                    background-color: transparent;
                    padding: 0px; margin: 0px; border: none;
                }}
            """)
            self.apply_text_layout()

    def get_ghost_mode_display_mode(self):
        return self.config.get("ghost_mode_display_mode", "hover")

    def should_show_text_on_enter(self):
        return self.get_ghost_mode_display_mode() != "double_click"

    def apply_alpha_to_rgba(self, rgba_text, opacity):
        try:
            value = rgba_text.strip()
            if not value.startswith("rgba(") or not value.endswith(")"):
                return rgba_text
            parts = [part.strip() for part in value[5:-1].split(",")]
            if len(parts) != 4:
                return rgba_text
            alpha = max(0, min(255, int(opacity * 255)))
            return f"rgba({parts[0]}, {parts[1]}, {parts[2]}, {alpha})"
        except Exception:
            return rgba_text

    def get_effective_bg_color(self):
        return self.apply_alpha_to_rgba(
            self.config['bg_color'],
            self.config.get("background_opacity", 0.78)
        )

    def get_effective_text_color(self):
        return self.apply_alpha_to_rgba(
            self.config['text_color'],
            self.config.get("text_opacity", 0.9)
        )

    def update_content_margins(self):
        if not hasattr(self, "content_layout"):
            return
        self.content_layout.setContentsMargins(5, 0, 5, 0)

    def build_frame_style(self, bg_color):
        return f"""
            CornerFrame {{
                background-color: {bg_color};
                border: none;
                border-radius: 5px;
            }}
        """

    def apply_dialog_readable_style(self):
        if not self.config.get("auto_mode"):
            return

        self.setWindowOpacity(0.95)
        self.content_frame.setStyleSheet(self.build_frame_style(self.get_effective_bg_color()))
        self.content_frame.set_mode(False)

    def cache_current_view_state(self):
        if self.ghost_text_visible:
            self.current_display_text = self.text_edit.toPlainText()
            self.current_scroll_value = self.text_edit.verticalScrollBar().value()

    def restore_current_view_state(self):
        if self.is_local_mode:
            self.render_local_page()
            return

        self.set_text_edit_content(self.current_display_text)
        scrollbar = self.text_edit.verticalScrollBar()
        if self.current_scroll_value < 0:
            self.schedule_content_scroll_position(True)
        else:
            scrollbar.setValue(min(self.current_scroll_value, scrollbar.maximum()))

    def set_ghost_text_visible(self, visible):
        if self.ghost_text_visible == visible:
            return

        if visible:
            self.ghost_text_visible = True
            self.apply_style()
            self.restore_current_view_state()
            return

        self.cache_current_view_state()
        self.ghost_text_visible = visible
        self.set_text_edit_content("")
        self.text_edit.verticalScrollBar().setValue(0)
        self.apply_style()

    def apply_ghost_hidden_style(self):
        self.update_content_margins()
        if self.config.get("auto_mode", False):
            self.chameleon_timer.stop()
            self.content_frame.set_draw_corners(False)
            current_bg = self.content_frame.auto_bg_fill
            r, g, b = current_bg.red(), current_bg.green(), current_bg.blue()
            ghost_bg_style = f"rgba({r}, {g}, {b}, 2)"
            self.text_edit.setStyleSheet(f"""
                QTextEdit {{
                    color: {self.config['text_color']};
                    background-color: {ghost_bg_style};
                    padding: 0px; margin: 0px; border: none;
                }}
            """)
            self.apply_text_layout()
            self.setWindowOpacity(1.0)
        else:
            self.chameleon_timer.stop()
            self.content_frame.set_draw_corners(False)
            self.setWindowOpacity(1.0)
            self.setStyleSheet("")
            self.content_frame.set_mode(False)
            bg_color = self.get_effective_bg_color()
            text_color = self.get_effective_text_color()
            frame_style = self.build_frame_style(bg_color)
            self.content_frame.setStyleSheet(frame_style)
            self.text_edit.setStyleSheet(f"""
                QTextEdit {{
                    color: {text_color};
                    background-color: transparent;
                    padding: 0px; margin: 0px; border: none;
                }}
            """)
            self.apply_text_layout()

    def apply_style(self):
        font_family = self.config.get('font_family', 'Microsoft YaHei')
        font_size = self.config['font_size']
        line_spacing = max(0, self.config.get("line_spacing", 0))
        font = QFont(font_family, font_size)
        self.update_content_margins()

        self.text_edit.setFont(font)

        fm = QFontMetrics(font)
        self.single_line_height = fm.lineSpacing() + line_spacing
        base_css = "padding: 0px; margin: 0px; border: none;"

        if self.config.get("ghost_mode", False) and not self.ghost_text_visible:
            if self.config.get("auto_mode", False):
                self.setWindowOpacity(1.0)
                self.content_frame.set_mode(True)
                self.content_frame.setStyleSheet("background: transparent; border: none;")
            else:
                self.content_frame.set_mode(False)
            self.apply_ghost_hidden_style()
            return

        if self.config.get("auto_mode", False):
            self.setWindowOpacity(1.0)
            self.content_frame.set_mode(True)
            self.content_frame.setStyleSheet("background: transparent; border: none;")
            self.content_frame.set_draw_corners(True)
            self.chameleon_timer.start()
            self.adjust_color_to_background()
            self.apply_text_layout()
        else:
            self.chameleon_timer.stop()
            self.content_frame.set_draw_corners(False)
            self.setWindowOpacity(1.0)
            self.setStyleSheet("")
            self.content_frame.set_mode(False)
            bg_color = self.get_effective_bg_color()
            text_color = self.get_effective_text_color()
            frame_style = self.build_frame_style(bg_color)
            self.content_frame.setStyleSheet(frame_style)
            text_style = f"""
                QTextEdit {{
                    color: {text_color};
                    background-color: transparent;
                    {base_css}
                }}
            """
            self.text_edit.setStyleSheet(text_style)
            self.apply_text_layout()

            # 本地模式下修改样式需要重绘页面
            if self.is_local_mode:
                self.render_local_page()

    def enterEvent(self, event):
        if self.config.get("ghost_mode", False):
            if self.should_show_text_on_enter():
                self.set_ghost_text_visible(True)
        super().enterEvent(event)

    def leaveEvent(self, event):
        if self.is_settings_open or self.is_resizing or self.is_moving: return
        if self._startup_guard: return  # 启动期间不触发 ghost 隐藏，避免窗口消失

        global_pos = QCursor.pos()
        local_pos = self.mapFromGlobal(global_pos)
        if self.rect().contains(local_pos): return

        if self.config.get("ghost_mode", False):
            self.set_ghost_text_visible(False)
        super().leaveEvent(event)

    def fetch_bookshelf_silent(self):
        threading.Thread(target=self._fetch_bookshelf_thread, daemon=True).start()

    def _fetch_bookshelf_thread(self):
        try:
            url = f"{self.config['ip']}/getBookshelf"
            res = requests.get(url, timeout=BOOKSHELF_TIMEOUT)
            if res.status_code == 200:
                data = res.json()
                self.bookshelf_updated_signal.emit(data.get("data", []))
        except requests.RequestException:
            pass

    def fetch_toc_silent(self, book_url):
        threading.Thread(target=self._fetch_toc_thread, args=(book_url,), daemon=True).start()

    def _fetch_toc_thread(self, book_url):
        try:
            url = f"{self.config['ip']}/getChapterList"
            res = requests.get(url, params={"url": book_url}, timeout=CHAPTER_LIST_TIMEOUT)
            if res.status_code == 200:
                data = res.json()
                if data['isSuccess']:
                    self.current_toc = data['data']
        except requests.RequestException:
            pass

    def open_book_selector(self):
        self.fetch_bookshelf_silent()
        self.book_selector_dialog = BookSelector(self, self)

        self.apply_dialog_readable_style()

        if self.book_selector_dialog.exec_() == QDialog.Accepted:
            if self.book_selector_dialog.selected_book:
                self.load_book(self.book_selector_dialog.selected_book)

        self.apply_style()
        self.book_selector_dialog = None

    def open_toc_selector(self):
        if not self.current_book:
            self.update_text_signal.emit("请先选择一本书！", False)
            return

        if not hasattr(self, 'current_toc') or self.current_toc is None:
            self.current_toc = []

        self.apply_dialog_readable_style()

        toc = TocSelector(self.config['ip'], self.current_book['bookUrl'],
                          self.current_chapter_index, self.current_toc, self)

        if toc.exec_() == QDialog.Accepted:
            if toc.selected_index is not None:
                self.current_chapter_index = toc.selected_index
                self.update_text_signal.emit(f"跳转到章节: {self.current_chapter_index}", False)
                self.fetch_chapter_content(self.current_book['bookUrl'], self.current_chapter_index, False, 0)

        self.apply_style()

    def get_chapter_title(self, chapter_index):
        if hasattr(self, 'current_toc') and self.current_toc:
            if 0 <= chapter_index < len(self.current_toc):
                return self.current_toc[chapter_index].get('title', '')
        return f"第 {chapter_index + 1} 章"

    def build_chapter_cache_entry(self, chapter_index, raw_content):
        chapter_title = self.get_chapter_title(chapter_index)
        content = raw_content.replace("<br>", "\n").replace("&nbsp;", " ")
        title_prefix = f"【 {chapter_title} 】\n\n"
        return {
            "full_text": f"{title_prefix}{content}",
            "raw_length": len(content),
            "title_prefix_len": len(title_prefix),
        }

    def get_cached_chapter(self, book_url, chapter_index):
        with self.chapter_cache_lock:
            return self.chapter_cache.get((book_url, chapter_index))

    def set_cached_chapter(self, book_url, chapter_index, entry):
        with self.chapter_cache_lock:
            self.chapter_cache[(book_url, chapter_index)] = entry

    def clear_chapter_cache(self):
        with self.chapter_cache_lock:
            self.chapter_cache.clear()
            self.prefetching_chapters.clear()

    def trim_chapter_cache(self, book_url, chapter_index):
        min_index = max(0, chapter_index - 1)
        max_index = chapter_index + FUTURE_CHAPTER_CACHE_SIZE
        with self.chapter_cache_lock:
            stale_keys = [
                key for key in self.chapter_cache
                if key[0] != book_url or key[1] < min_index or key[1] > max_index
            ]
            for key in stale_keys:
                self.chapter_cache.pop(key, None)

    def calc_display_char_pos(self, entry, progress_pos):
        if entry["raw_length"] > 0 and progress_pos > 0:
            return entry["title_prefix_len"] + min(progress_pos, entry["raw_length"])
        return 0

    def prefetch_future_chapters(self, book_url, chapter_index):
        if not book_url:
            return

        max_toc_index = len(self.current_toc) - 1 if self.current_toc else None
        for offset in range(1, FUTURE_CHAPTER_CACHE_SIZE + 1):
            next_index = chapter_index + offset
            if max_toc_index is not None and next_index > max_toc_index:
                break

            cache_key = (book_url, next_index)
            with self.chapter_cache_lock:
                if cache_key in self.chapter_cache or cache_key in self.prefetching_chapters:
                    continue
                self.prefetching_chapters.add(cache_key)

            threading.Thread(
                target=self._prefetch_chapter_thread,
                args=(book_url, next_index, cache_key),
                daemon=True
            ).start()

    def _prefetch_chapter_thread(self, book_url, chapter_index, cache_key):
        try:
            url = f"{self.config['ip']}/getBookContent"
            params = {'url': book_url, 'index': chapter_index}
            res = requests.get(url, params=params, timeout=CHAPTER_CONTENT_TIMEOUT)
            if res.status_code != 200:
                return

            data = res.json()
            if not data.get("isSuccess"):
                return

            entry = self.build_chapter_cache_entry(chapter_index, data.get("data", ""))
            self.set_cached_chapter(book_url, chapter_index, entry)
        except Exception:
            pass
        finally:
            with self.chapter_cache_lock:
                self.prefetching_chapters.discard(cache_key)

    def load_book(self, book):
        self.is_local_mode = False  # 切换回网络模式
        self.current_book = book
        self.current_chapter_index = book.get('durChapterIndex', 0)
        self.clear_chapter_cache()
        # 原始字符位移量，在线程中按内容转换为渲染文本中的显示位置
        raw_progress_pos = book.get('durChapterPos', 0)
        self.current_chapter_progress = 0
        self.current_toc = []
        self.update_text_signal.emit(f"打开: {book['name']}", False)
        self.fetch_chapter_content(
            book['bookUrl'],
            self.current_chapter_index,
            False,
            raw_progress_pos
        )
        self.fetch_toc_silent(book['bookUrl'])

    def fetch_chapter_content(self, book_url, chapter_index, scroll_to_bottom=False, progress_pos=0):
        self.chapter_request_token += 1
        request_token = self.chapter_request_token
        self.is_chapter_loading = True

        cached_entry = self.get_cached_chapter(book_url, chapter_index)
        if cached_entry:
            display_char_pos = self.calc_display_char_pos(cached_entry, progress_pos)
            self.chapter_loaded_signal.emit(
                chapter_index,
                cached_entry["full_text"],
                scroll_to_bottom,
                request_token,
                display_char_pos,
                cached_entry["raw_length"],
                cached_entry["title_prefix_len"],
            )
            return

        t = threading.Thread(target=self._fetch_chapter_thread,
                             args=(book_url, chapter_index, scroll_to_bottom, request_token, progress_pos), daemon=True)
        t.start()

    def _fetch_chapter_thread(self, book_url, chapter_index, scroll_to_bottom, request_token, progress_pos):
        try:
            url = f"{self.config['ip']}/getBookContent"
            params = {'url': book_url, 'index': chapter_index}
            res = requests.get(url, params=params, timeout=CHAPTER_CONTENT_TIMEOUT)

            if res.status_code == 200:
                data = res.json()
                if not data.get("isSuccess"):
                    self.chapter_load_failed_signal.emit(f"读取失败: {data.get('errorMsg')}", request_token)
                    return

                raw_content = data.get("data", "")
                entry = self.build_chapter_cache_entry(chapter_index, raw_content)
                self.set_cached_chapter(book_url, chapter_index, entry)

                # 计算在渲染文本中的显示字符位置（标题偏移 + 章节内字符偏移）
                display_char_pos = self.calc_display_char_pos(entry, progress_pos)

                self.chapter_loaded_signal.emit(
                    chapter_index, entry["full_text"], scroll_to_bottom,
                    request_token, display_char_pos, entry["raw_length"],
                    entry["title_prefix_len"]
                )
            else:
                self.chapter_load_failed_signal.emit(f"HTTP错误: {res.status_code}", request_token)
        except Exception as e:
            self.chapter_load_failed_signal.emit(f"网络错误: {str(e)}", request_token)

    def sync_progress_async(self, char_pos=None):
        if not self.current_book or self.is_local_mode:
            return

        self.last_progress_sync_time = time.monotonic()

        if char_pos is None:
            # 从视口顶部的光标位置计算原始章节内字符数
            cursor = self.text_edit.cursorForPosition(QPoint(0, 0))
            char_pos = max(0, cursor.position() - self._current_title_prefix_len)

        # 限制在有效范围内
        if self._current_content_raw_length > 0:
            char_pos = min(char_pos, self._current_content_raw_length)
        else:
            char_pos = max(0, char_pos)

        self.current_book["durChapterIndex"] = self.current_chapter_index
        self.current_book["durChapterPos"] = char_pos
        self.current_chapter_progress = char_pos

        title = ""
        if self.current_toc and 0 <= self.current_chapter_index < len(self.current_toc):
            title = self.current_toc[self.current_chapter_index].get("title", "")

        self.current_book["durChapterTime"] = int(time.time() * 1000)
        self.current_book["durChapterTitle"] = title
        book = self.current_book.copy()
        chapter_index = self.current_chapter_index
        ip = self.config['ip']
        threading.Thread(
            target=self._sync_task,
            args=(book, chapter_index, title, char_pos, ip),
            daemon=True
        ).start()

    def _sync_task(self, book, chapter_index, title, progress, ip):
        try:
            data = {
                "name": book['name'],
                "author": book['author'],
                "durChapterIndex": chapter_index,
                "durChapterPos": progress,
                "durChapterTime": book.get("durChapterTime", int(time.time() * 1000)),
                "durChapterTitle": title,
            }
            url = f"{ip}/saveBookProgress"
            requests.post(url, json=data, timeout=PROGRESS_SYNC_TIMEOUT)
        except requests.RequestException:
            pass

    def auto_save_progress_if_needed(self):
        if self.is_local_mode or not self.current_book or self.is_chapter_loading:
            return

        if time.monotonic() - self.last_progress_sync_time < PROGRESS_AUTO_SAVE_INTERVAL:
            return

        self.sync_progress_async()

    def next_chapter(self):
        # 【新增保护】防止 current_book 为 None
        if not self.current_book or self.is_chapter_loading:
            return
        self.sync_progress_async(self._current_content_raw_length)
        next_index = self.current_chapter_index + 1
        self.current_chapter_index = next_index
        self.update_text_signal.emit("加载下一章...", False)
        self.fetch_chapter_content(self.current_book['bookUrl'], next_index, False, 0)

    def prev_chapter(self):
        # 【新增保护】防止 current_book 为 None
        if not self.current_book or self.is_chapter_loading:
            return
        if self.current_chapter_index > 0:
            self.sync_progress_async(0)
            prev_index = self.current_chapter_index - 1
            self.current_chapter_index = prev_index
            self.update_text_signal.emit("加载上一章...", False)
            self.fetch_chapter_content(
                self.current_book['bookUrl'],
                prev_index,
                True,
                0
            )

    def is_in_resize_area(self, pos):
        rect = self.rect()
        resize_rect = QRect(rect.width() - self.resize_margin,
                            rect.height() - self.resize_margin,
                            self.resize_margin, self.resize_margin)
        return resize_rect.contains(pos)

    def begin_pointer_action(self, local_pos, global_pos):
        if self.is_in_resize_area(local_pos):
            self.is_resizing = True
            self.is_moving = False
            return

        self.is_moving = True
        self.is_resizing = False
        self.oldPos = global_pos

    def resize_window_to_pos(self, local_pos):
        new_w = max(local_pos.x(), 100)
        min_h = getattr(self, 'single_line_height', 20)
        new_h = max(local_pos.y(), min_h)
        self.resize(new_w, new_h)
        if self.is_local_mode:
            self.render_local_page()

    def move_window_by_pos(self, global_pos):
        delta = QPoint(global_pos - self.oldPos)
        self.move(self.x() + delta.x(), self.y() + delta.y())
        self.oldPos = global_pos

    def handle_pointer_drag(self, local_pos, global_pos):
        if self.is_resizing:
            self.resize_window_to_pos(local_pos)
        elif self.is_moving:
            self.move_window_by_pos(global_pos)

        if self.config.get("auto_mode"):
            self.adjust_color_to_background()

    def finish_pointer_action(self):
        self.is_resizing = False
        self.is_moving = False
        self.setCursor(Qt.ArrowCursor)
        self.save_config()

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.begin_pointer_action(event.pos(), event.globalPos())

    def mouseMoveEvent(self, event):
        if self.is_in_resize_area(event.pos()):
            self.setCursor(Qt.SizeFDiagCursor)
        elif not self.is_resizing:
            self.setCursor(Qt.ArrowCursor)

        if event.buttons() == Qt.LeftButton:
            self.handle_pointer_drag(event.pos(), event.globalPos())

    def mouseReleaseEvent(self, event):
        self.finish_pointer_action()

    def mouseDoubleClickEvent(self, event):
        if event.button() == Qt.LeftButton and self.config.get("ghost_mode", False):
            if self.get_ghost_mode_display_mode() == "double_click":
                self.set_ghost_text_visible(True)
        super().mouseDoubleClickEvent(event)

    def contextMenuEvent(self, event):
        if self.should_open_context_menu(event.modifiers()):
            self.show_context_menu(self.mapToGlobal(event.pos()))

    def open_settings(self):
        self.is_settings_open = True
        self.apply_dialog_readable_style()

        dialog = SettingsDialog(self.config, self)

        if dialog.exec_() == QDialog.Accepted:
            self.config = dialog.config
            self.save_config()
            self.apply_window_flags()
            self.apply_style()
            self.refresh_hotkeys()
            if self.config["ip"].startswith("http"):
                self.fetch_bookshelf_silent()
        else:
            self.apply_style()

        self.is_settings_open = False
        self.showNormal()
        self.activateWindow()

    def keyPressEvent(self, event):
        key = event.key()
        if key in [Qt.Key_Right, Qt.Key_Down, Qt.Key_Space, Qt.Key_PageDown]:
            self.scroll_page(1)
        elif key in [Qt.Key_Left, Qt.Key_Up, Qt.Key_PageUp]:
            self.scroll_page(-1)

    def closeEvent(self, event):
        self.sync_progress_async()
        if self.is_local_mode:
            self.config["last_local_pos"] = self.local_start_index
        self.save_config()
        super().closeEvent(event)

    def quit_app(self):
        # 退出前强制保存阅读进度和窗口位置
        self.sync_progress_async()
        if self.is_local_mode:
            self.config["last_local_pos"] = self.local_start_index
        self.save_config()

        self.unregister_native_hotkeys()
        QApplication.instance().quit()


if __name__ == '__main__':
    setup_file_logging()
    try:
        app = QApplication(sys.argv)
        app.setQuitOnLastWindowClosed(False)

        # 单实例检查：如果已有实例，激活其窗口后立即退出
        activated, shared_mem = try_activate_existing_instance()
        if activated:
            sys.exit(0)

        # 标记当前实例为唯一实例
        shared_mem.create(1)

        ex = FishingRead()
        ex.show()
        sys.exit(app.exec_())
    except Exception as e:
        logging.exception("程序启动失败: %s", e)
        # 弹窗显示错误信息（方便用户截图汇报）
        try:
            from PyQt5.QtWidgets import QMessageBox
            app = QApplication(sys.argv) if 'app' not in dir() else app
            QMessageBox.critical(None, "启动失败", f"鱼阅启动时发生错误：\n{e}\n\n详情请查看同目录下的「鱼阅.log」文件。")
        except Exception:
            pass
