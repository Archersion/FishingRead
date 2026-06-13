"""
对话框：书架选择器、目录选择器、设置对话框。
"""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
    QLineEdit, QSlider, QSpinBox, QPushButton, QListWidget,
    QListWidgetItem, QLabel, QFontComboBox, QCheckBox, QComboBox,
    QColorDialog, QFileDialog,
)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QColor

from fishingread.constants import DARK_STYLESHEET, CHAPTER_LIST_TIMEOUT
from fishingread.svg_icons import make_icon, add_menu_action
from fishingread.core.network_reader import NetworkReader


# ================== 书架选择器 ==================

class BookSelector(QDialog):
    """通过网络书架选择书籍的对话框。"""

    def __init__(self, network_reader, parent=None):
        super().__init__(parent)
        self.main_window = parent
        self.network = network_reader
        self.selected_book = None
        self.setWindowTitle("书架")
        self.resize(400, 500)
        self.setStyleSheet(DARK_STYLESHEET)
        self._init_ui()
        self.populate_list(self.network.books)

    def _init_ui(self):
        layout = QVBoxLayout()
        top = QHBoxLayout()

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("搜索书名或作者...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self.filter_books)
        top.addWidget(self.search_input)

        btn_refresh = QPushButton("刷新")
        btn_refresh.setIcon(make_icon("refresh-cw", 16))
        btn_refresh.setFixedWidth(80)
        btn_refresh.clicked.connect(self.manual_refresh)
        top.addWidget(btn_refresh)
        layout.addLayout(top)

        self.list_widget = QListWidget()
        self.list_widget.itemActivated.connect(self.on_item_activated)
        self.list_widget.itemDoubleClicked.connect(self.on_item_double_clicked)
        layout.addWidget(self.list_widget)

        bottom = QHBoxLayout()
        btn_open = QPushButton("打开选中书籍")
        btn_open.setIcon(make_icon("book-open", 16))
        btn_open.clicked.connect(self.accept_current_book)
        bottom.addStretch(1)
        bottom.addWidget(btn_open)
        layout.addLayout(bottom)
        self.setLayout(layout)

    def manual_refresh(self):
        self.setWindowTitle("书架 (加载中...)")
        self.network.fetch_bookshelf_silent()

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
            b for b in self.network.books
            if text in b["name"].lower() or text in b["author"].lower()
        ]
        self.populate_list(filtered)

    def select_book_item(self, item):
        if not item:
            return False
        self.selected_book = item.data(Qt.UserRole)
        return bool(self.selected_book)

    def accept_current_book(self):
        if self.select_book_item(self.list_widget.currentItem()):
            self.accept()

    def on_item_activated(self, item):
        if self.select_book_item(item):
            self.accept()

    def on_item_double_clicked(self, item):
        if not self.select_book_item(item):
            return
        self.accept()


# ================== 目录加载线程 ==================

from PyQt5.QtCore import QThread, pyqtSignal
import requests


class ChapterLoaderThread(QThread):
    """后台加载章节目录的线程。"""
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
                if data["isSuccess"]:
                    self.loaded.emit(data["data"])
                else:
                    self.failed.emit(data.get("errorMsg", "未知错误"))
            else:
                self.failed.emit(f"HTTP {res.status_code}")
        except Exception as e:
            self.failed.emit(str(e))


# ================== 目录选择器 ==================

class TocSelector(QDialog):
    """章节目录选择对话框。"""

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
        self._init_ui()

        if cached_toc and len(cached_toc) > 0:
            self.on_loaded(cached_toc)
        else:
            self.loader = ChapterLoaderThread(ip, book_url)
            self.loader.loaded.connect(self.on_loaded)
            self.loader.failed.connect(self.on_failed)
            self.loader.start()

    def _init_ui(self):
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

            if self.main_window and hasattr(self.main_window, "on_toc_loaded"):
                self.main_window.on_toc_loaded(chapters)

            for i, chapter in enumerate(chapters):
                title = str(chapter.get("title", f"第 {i + 1} 章"))
                item = QListWidgetItem(title)
                idx = chapter.get("index", i)
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


# ================== 设置对话框 ==================

class SettingsDialog(QDialog):
    """应用设置对话框。"""

    def __init__(self, config, parent=None):
        super().__init__(parent)
        self.config = config
        self.main_window = parent
        self.original_text_opacity = config.get("text_opacity", config.get("opacity", 0.9))
        self.original_background_opacity = config.get("background_opacity", config.get("opacity", 0.9))
        self.original_line_spacing = config.get("line_spacing", 0)
        self.temp_text_color = config.get("text_color")
        self.temp_bg_color = config.get("bg_color")
        self.original_focus_hotkey = config.get("focus_hotkey", "Ctrl+Shift+R")

        self.setWindowTitle("设置")
        self.resize(350, 590)
        self.setStyleSheet(DARK_STYLESHEET)
        self._init_ui()

    def _init_ui(self):
        layout = QFormLayout()

        # Legado 地址
        self.ip_input = QLineEdit(self.config.get("ip"))
        layout.addRow("Legado地址:", self.ip_input)

        # 变色龙模式
        self.check_auto_mode = QCheckBox("自动挡 (变色龙)")
        self.check_auto_mode.setToolTip("开启后，背景变为背景色+极低透明度。字体颜色自动反转。")
        self.check_auto_mode.setIcon(make_icon("chameleon", 18))
        self.check_auto_mode.setChecked(self.config.get("auto_mode", False))
        self.check_auto_mode.toggled.connect(self.on_auto_mode_toggled)
        layout.addRow(self.check_auto_mode)

        # 防截屏
        self.check_antishot = QCheckBox("系统级防截屏")
        self.check_antishot.setToolTip("开启后，肉眼可见，但截图/录屏时窗口会完全消失（透明）。")
        self.check_antishot.setIcon(make_icon("shield", 18))
        self.check_antishot.setChecked(self.config.get("antishot_mode", False))
        self.check_antishot.toggled.connect(self.on_antishot_toggled)
        layout.addRow(self.check_antishot)

        # 透明度滑杆
        self.text_opacity_slider = QSlider(Qt.Horizontal)
        self.text_opacity_slider.setRange(0, 100)
        self.text_opacity_slider.setValue(int(self.config.get("text_opacity", 0.9) * 100))
        self.text_opacity_slider.valueChanged.connect(self.on_text_opacity_change)
        layout.addRow("字体透明度:", self.text_opacity_slider)

        self.background_opacity_slider = QSlider(Qt.Horizontal)
        self.background_opacity_slider.setRange(1, 100)
        self.background_opacity_slider.setValue(max(1, int(self.config.get("background_opacity", 0.78) * 100)))
        self.background_opacity_slider.valueChanged.connect(self.on_background_opacity_change)
        layout.addRow("背景透明度:", self.background_opacity_slider)

        # 字体
        self.font_spin = QSpinBox()
        self.font_spin.setRange(8, 60)
        self.font_spin.setValue(self.config.get("font_size"))
        layout.addRow("字体大小:", self.font_spin)

        self.line_spacing_spin = QSpinBox()
        self.line_spacing_spin.setRange(0, 30)
        self.line_spacing_spin.setValue(self.config.get("line_spacing", 0))
        layout.addRow("行间距:", self.line_spacing_spin)

        self.font_combo = QFontComboBox()
        current_font = self.config.get("font_family", "Microsoft YaHei")
        self.font_combo.setCurrentFont(QFont(current_font))
        layout.addRow("字体样式:", self.font_combo)

        # 颜色按钮
        self.btn_text_color = QPushButton("文字颜色 (手动)")
        self._apply_color_button_style(self.btn_text_color, self.temp_text_color)
        self.btn_text_color.clicked.connect(self.pick_text_color)
        self.btn_bg_color = QPushButton("背景颜色 (手动)")
        self._apply_color_button_style(self.btn_bg_color, self.temp_bg_color)
        self.btn_bg_color.clicked.connect(self.pick_bg_color)
        layout.addRow(self.btn_text_color, self.btn_bg_color)

        # 幽灵模式
        self.check_ghost_mode = QCheckBox("幽灵模式 (移开变透明)")
        self.check_ghost_mode.setIcon(make_icon("ghost", 18))
        self.check_ghost_mode.setChecked(self.config.get("ghost_mode", False))
        self.check_ghost_mode.toggled.connect(self.on_ghost_mode_toggled)
        layout.addRow(self.check_ghost_mode)

        self.combo_ghost_mode_display = QComboBox()
        self.combo_ghost_mode_display.addItem("鼠标进入自动显示", "hover")
        self.combo_ghost_mode_display.addItem("双击后显示", "double_click")
        display_mode = self.config.get("ghost_mode_display_mode", "hover")
        idx = self.combo_ghost_mode_display.findData(display_mode)
        if idx < 0:
            idx = 0
        self.combo_ghost_mode_display.setCurrentIndex(idx)
        layout.addRow("幽灵显示方式:", self.combo_ghost_mode_display)

        # 窗口行为
        self.check_show_in_switcher = QCheckBox("在 Alt+Tab 和任务栏中显示窗口")
        self.check_show_in_switcher.setChecked(self.config.get("show_in_switcher", False))
        layout.addRow(self.check_show_in_switcher)

        self.check_always_on_top = QCheckBox("窗口保持置顶")
        self.check_always_on_top.setChecked(self.config.get("always_on_top", True))
        layout.addRow(self.check_always_on_top)

        self.check_context_menu_requires_ctrl = QCheckBox("右键菜单需要按住 Ctrl")
        self.check_context_menu_requires_ctrl.setChecked(self.config.get("context_menu_requires_ctrl", True))
        layout.addRow(self.check_context_menu_requires_ctrl)

        # 热键
        self.boss_key_input = QLineEdit(self.config.get("boss_key", "Esc"))
        layout.addRow("全局老板键:", self.boss_key_input)

        self.focus_hotkey_input = QLineEdit(self.config.get("focus_hotkey", "Ctrl+Shift+R"))
        layout.addRow("唤醒快捷键:", self.focus_hotkey_input)

        # 保存按钮
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
            from fishingread.platform.windows import set_window_protection
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

    def _parse_qcolor(self, rgba_text, fallback):
        color = QColor(rgba_text)
        return color if color.isValid() else QColor(fallback)

    def _apply_color_button_style(self, button, rgba_text):
        color = self._parse_qcolor(rgba_text, "#444444")
        brightness = 0.299 * color.red() + 0.587 * color.green() + 0.114 * color.blue()
        foreground = "#111111" if brightness > 150 else "#ffffff"
        button.setStyleSheet(
            f"background-color: {rgba_text}; color: {foreground}; "
            "border: 1px solid #666; padding: 5px; border-radius: 4px;"
        )

    def pick_text_color(self):
        initial = self._parse_qcolor(self.temp_text_color, "#ffffff")
        color = QColorDialog.getColor(initial, self, "选择文字颜色", QColorDialog.ShowAlphaChannel)
        if color.isValid():
            self.temp_text_color = f"rgba({color.red()}, {color.green()}, {color.blue()}, {color.alpha()})"
            self._apply_color_button_style(self.btn_text_color, self.temp_text_color)

    def pick_bg_color(self):
        initial = self._parse_qcolor(self.temp_bg_color, "#1e1e1e")
        color = QColorDialog.getColor(initial, self, "选择背景颜色", QColorDialog.ShowAlphaChannel)
        if color.isValid():
            self.temp_bg_color = f"rgba({color.red()}, {color.green()}, {color.blue()}, {color.alpha()})"
            self._apply_color_button_style(self.btn_bg_color, self.temp_bg_color)

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
            from fishingread.platform.windows import set_window_protection
            set_window_protection(int(self.main_window.winId()), self.config.get("antishot_mode", False))
        super().reject()
