"""
鱼阅 (FishingRead) 主窗口。
模块级导入，仅在 run_app() 中首次 import 时触发一次，不影响启动速度。
"""
import sys
import os
import time
import ctypes
import traceback
import logging
from ctypes import wintypes

from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QTextEdit, QShortcut,
    QSystemTrayIcon, QDialog,
)
from PyQt5.QtCore import Qt, QPoint, QRect, QTimer, QEvent
from PyQt5.QtGui import (
    QFont, QColor, QCursor, QKeySequence,
    QFontMetrics, QTextCursor, QTextBlockFormat,
)

from fishingread.constants import (
    DEFAULT_CONFIG, DARK_STYLESHEET, MENU_STYLESHEET,
    WM_HOTKEY, PROGRESS_AUTO_SAVE_CHECK_INTERVAL, PROGRESS_AUTO_SAVE_INTERVAL,
)
from fishingread.config import load_config, save_config
from fishingread.core.local_reader import LocalReader
from fishingread.core.network_reader import NetworkReader
from fishingread.ui.widgets import CornerFrame
from fishingread.ui.dialogs import BookSelector, TocSelector, SettingsDialog
from fishingread.ui.menu import create_context_menu, create_tray
from fishingread.svg_icons import make_icon, get_app_icon
from fishingread.platform.windows import set_window_protection, NativeHotkeyManager
from fishingread.single_instance import SingleInstanceServer


class FishingRead(QWidget):
    """鱼阅主窗口。"""

    HOTKEY_ID_BOSS = 1
    HOTKEY_ID_FOCUS = 2

    def __init__(self):
        super().__init__()
        self.config = load_config()
        self.is_settings_open = False

        # 阅读引擎
        self.local_reader = LocalReader(
            on_update_text=self._on_local_update_text,
            on_save_progress=self._on_local_save_progress,
        )
        self.network = NetworkReader(self)
        self.network.set_ip(self.config.get("ip", ""))
        self.is_local_mode = False

        # UI 状态
        self.single_line_height = 20
        self.ghost_text_visible = True
        self.current_display_text = ""
        self.current_scroll_value = 0
        self.pending_content_scroll_anchor = None
        self.content_scroll_token = 0
        self.is_resizing = False
        self.is_moving = False
        self.resize_margin = 15
        self.last_toggle_time = 0
        self.oldPos = QPoint(0, 0)
        self._startup_guard = True
        self._first_show = True
        self._last_hide_time = 0.0
        self.book_selector_dialog = None

        # 热键
        self.local_shortcut = None
        self.focus_shortcut = None
        self.hotkey_manager = NativeHotkeyManager()

        # 网络阅读状态
        self._current_content_raw_length = 0
        self._current_title_prefix_len = 0
        self.current_chapter_progress = 0
        self.network.bookshelf_updated.connect(self._on_bookshelf_updated)
        self.network.chapter_loaded.connect(self._on_chapter_loaded)
        self.network.chapter_load_failed.connect(self._on_chapter_load_failed)

        # 定时器
        self.chameleon_timer = QTimer(self)
        self.chameleon_timer.setInterval(500)
        self.chameleon_timer.timeout.connect(self.adjust_color_to_background)

        self.progress_auto_save_timer = QTimer(self)
        self.progress_auto_save_timer.setInterval(PROGRESS_AUTO_SAVE_CHECK_INTERVAL * 1000)
        self.progress_auto_save_timer.timeout.connect(self._auto_save_progress)
        self.progress_auto_save_timer.start()

        # 初始化 UI
        self._init_ui()
        self._show_default_network_prompt()
        self.tray_icon = create_tray(self)
        self.tray_icon.show()

        # 单实例 IPC
        self.ipc_server = SingleInstanceServer(activate_callback=self._on_ipc_activate)

        # QShortcut（窗口可见时生效）
        self._create_qshortcuts()

        # 启动延迟
        QTimer.singleShot(1500, lambda: self._release_startup_guard())

        # 恢复上次阅读
        last_file = self.config.get("last_local_file", "")
        if last_file and os.path.exists(last_file):
            QTimer.singleShot(500, lambda: self._restore_last_local_file(last_file))
        elif self.config["ip"].startswith("http"):
            self.network.fetch_bookshelf_silent()

        # 防截屏
        if self.config.get("antishot_mode", False):
            QTimer.singleShot(100, lambda: set_window_protection(int(self.winId()), True))

        QTimer.singleShot(50, self._startup_activate)

    # ── 启动与激活 ────────────────────────────────────────

    def _startup_activate(self):
        """启动后轻量激活：显示窗口 + 注册热键。"""
        if not self.isVisible():
            self.showNormal()
        self.raise_()
        self.activateWindow()
        self._refresh_hotkeys()
        if self.config.get("auto_mode", False):
            self.chameleon_timer.start()
            self.adjust_color_to_background()
        if self.config.get("antishot_mode", False):
            set_window_protection(int(self.winId()), True)

    def _reload_progress_on_reveal(self):
        """如果隐藏超过自动保存间隔，重新读取阅读进度。"""
        if self._last_hide_time <= 0:
            return
        if time.time() - self._last_hide_time < PROGRESS_AUTO_SAVE_CHECK_INTERVAL:
            return

        if self.is_local_mode:
            last_file = self.config.get("last_local_file", "")
            if last_file and os.path.exists(last_file):
                pos = self.config.get("last_local_pos", 0)
                self.load_local_file(last_file, pos)
        elif self.network.current_book:
            self.network.fetch_chapter_content(
                self.network.current_book.get("bookUrl"),
                self.network.current_chapter_index,
                False,
                self.network.current_chapter_progress,
            )

    def _release_startup_guard(self):
        self._startup_guard = False

    def _on_ipc_activate(self):
        """单实例 IPC 收到激活请求时唤起窗口。"""
        self.reveal_window()
        self._refresh_hotkeys()

    def _show_default_network_prompt(self):
        """网络模式未选书时显示默认提示。"""
        if not self.is_local_mode and not self.network.current_book:
            self._on_local_update_text("请先选择一本书！", False)

    def hideEvent(self, event):
        """窗口隐藏时记录时间，覆盖所有隐藏路径（Esc、托盘菜单等）。"""
        self._last_hide_time = time.time()
        super().hideEvent(event)

    def showEvent(self, event):
        """窗口显示时检查是否需要刷新进度。"""
        super().showEvent(event)
        if self._first_show:
            self._first_show = False
        if self.isVisible() and event.spontaneous():
            self._reload_progress_on_reveal()
            self.raise_()
            self.activateWindow()
            try:
                ctypes.windll.user32.SetForegroundWindow(int(self.winId()))
            except Exception:
                pass

    def save_config_to_disk(self):
        """保存配置到磁盘。"""
        save_config(
            self.config,
            window_x=self.x(), window_y=self.y(),
            window_width=self.width(), window_height=self.height(),
        )

    # ── UI 初始化 ──

    def _build_window_flags(self):
        flags = Qt.FramelessWindowHint
        if self.config.get("always_on_top", True):
            flags |= Qt.WindowStaysOnTopHint
        if self.config.get("show_in_switcher", False):
            flags |= Qt.Window
        else:
            flags |= Qt.Tool
        return flags

    def _apply_window_flags(self):
        was_visible = self.isVisible()
        geometry = self.geometry()
        self.setWindowFlags(self._build_window_flags())
        self.setGeometry(geometry)
        if was_visible:
            self.show()
            self.apply_style()
            self._refresh_hotkeys()
            if self.config.get("antishot_mode", False):
                set_window_protection(int(self.winId()), True)

    def _init_ui(self):
        self._apply_window_flags()
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setMouseTracking(True)

        self.main_layout = QVBoxLayout()
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)

        self.content_frame = CornerFrame()
        self.content_layout = QVBoxLayout(self.content_frame)
        self.content_layout.setContentsMargins(5, 0, 5, 0)
        self.content_layout.setSpacing(0)

        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setFrameStyle(QTextEdit.NoFrame)
        self.text_edit.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.text_edit.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.text_edit.setTextInteractionFlags(Qt.NoTextInteraction)
        self.text_edit.setFocusPolicy(Qt.NoFocus)
        self.text_edit.document().setDocumentMargin(0)
        self.text_edit.verticalScrollBar().rangeChanged.connect(self._on_scroll_range_changed)

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

    # ── 文本排版 ──────────────────────────────────────────

    def _apply_text_layout(self):
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

    def _set_text_edit_content(self, text):
        self.text_edit.setPlainText(text)
        self._apply_text_layout()

    # ── 滚动位置控制 ──────────────────────────────────────

    def _apply_scroll_position(self, is_bottom, token):
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

    def _schedule_scroll_position(self, is_bottom):
        self.content_scroll_token += 1
        token = self.content_scroll_token
        self.pending_content_scroll_anchor = (is_bottom, token)
        self._apply_scroll_position(is_bottom, token)
        for delay in (0, 50, 150, 300):
            QTimer.singleShot(delay, lambda b=is_bottom, t=token: self._apply_scroll_position(b, t))
        QTimer.singleShot(350, lambda t=token: self._clear_scroll_anchor(t))

    def _clear_scroll_anchor(self, token):
        if self.pending_content_scroll_anchor and self.pending_content_scroll_anchor[1] == token:
            self.pending_content_scroll_anchor = None

    def _on_scroll_range_changed(self, minimum, maximum):
        if not self.pending_content_scroll_anchor:
            return
        is_bottom, token = self.pending_content_scroll_anchor
        self._apply_scroll_position(is_bottom, token)
        if token == self.content_scroll_token and maximum > minimum:
            self.pending_content_scroll_anchor = None

    def _schedule_progress_restore_scroll(self, display_char_pos):
        """按字符位置恢复滚动。"""
        token = self.network.chapter_request_token
        for delay in (0, 100, 300):
            QTimer.singleShot(delay, lambda p=display_char_pos, t=token: self._apply_char_pos_scroll(p, t))

    def _apply_char_pos_scroll(self, display_char_pos, token):
        """将 QTextEdit 滚动到指定字符位置。"""
        if token != self.network.chapter_request_token:
            return
        doc = self.text_edit.document()
        max_pos = doc.characterCount() - 1
        target = min(display_char_pos, max_pos)
        if target <= 0:
            return
        cursor = QTextCursor(doc)
        cursor.setPosition(target)
        self.text_edit.setTextCursor(cursor)
        cursor_rect = self.text_edit.cursorRect(cursor)
        scrollbar = self.text_edit.verticalScrollBar()
        scrollbar.setValue(scrollbar.value() + cursor_rect.top())

    # ── 样式 ──────────────────────────────────────────────

    def _apply_alpha_to_rgba(self, rgba_text, opacity):
        try:
            value = rgba_text.strip()
            if not value.startswith("rgba(") or not value.endswith(")"):
                return rgba_text
            parts = [p.strip() for p in value[5:-1].split(",")]
            if len(parts) != 4:
                return rgba_text
            alpha = max(0, min(255, int(opacity * 255)))
            return f"rgba({parts[0]}, {parts[1]}, {parts[2]}, {alpha})"
        except Exception:
            return rgba_text

    def _get_effective_bg_color(self):
        return self._apply_alpha_to_rgba(
            self.config["bg_color"],
            self.config.get("background_opacity", 0.78),
        )

    def _get_effective_text_color(self):
        return self._apply_alpha_to_rgba(
            self.config["text_color"],
            self.config.get("text_opacity", 0.9),
        )

    def _build_frame_style(self, bg_color):
        return f"""
            CornerFrame {{
                background-color: {bg_color};
                border: none;
                border-radius: 5px;
            }}
        """

    def apply_style(self):
        """应用当前配置的样式。"""
        font_family = self.config.get("font_family", "Microsoft YaHei")
        font_size = self.config["font_size"]
        line_spacing = max(0, self.config.get("line_spacing", 0))
        font = QFont(font_family, font_size)
        self.text_edit.setFont(font)

        fm = QFontMetrics(font)
        self.single_line_height = fm.lineSpacing() + line_spacing
        base_css = "padding: 0px; margin: 0px; border: none;"

        if self.config.get("ghost_mode", False) and not self.ghost_text_visible:
            self._apply_ghost_hidden_style()
            return

        if self.config.get("auto_mode", False):
            self.setWindowOpacity(1.0)
            self.content_frame.set_mode(True)
            self.content_frame.setStyleSheet("background: transparent; border: none;")
            self.content_frame.set_draw_corners(True)
            self.chameleon_timer.start()
            self.adjust_color_to_background()
            self._apply_text_layout()
        else:
            self.chameleon_timer.stop()
            self.content_frame.set_draw_corners(False)
            self.setWindowOpacity(1.0)
            self.setStyleSheet("")
            self.content_frame.set_mode(False)
            bg_color = self._get_effective_bg_color()
            text_color = self._get_effective_text_color()
            self.content_frame.setStyleSheet(self._build_frame_style(bg_color))
            self.text_edit.setStyleSheet(f"""
                QTextEdit {{
                    color: {text_color};
                    background-color: transparent;
                    {base_css}
                }}
            """)
            self._apply_text_layout()
            if self.is_local_mode:
                self._render_local_page()

    def _apply_ghost_hidden_style(self):
        """幽灵模式下隐藏文字的样式。"""
        if self.config.get("auto_mode", False):
            self.chameleon_timer.stop()
            self.content_frame.set_draw_corners(False)
            current_bg = self.content_frame.auto_bg_fill
            ghost_bg = f"rgba({current_bg.red()}, {current_bg.green()}, {current_bg.blue()}, 2)"
            self.text_edit.setStyleSheet(f"""
                QTextEdit {{
                    color: {self.config['text_color']};
                    background-color: {ghost_bg};
                    padding: 0px; margin: 0px; border: none;
                }}
            """)
            self._apply_text_layout()
            self.setWindowOpacity(1.0)
        else:
            self.chameleon_timer.stop()
            self.content_frame.set_draw_corners(False)
            self.setWindowOpacity(1.0)
            self.setStyleSheet("")
            self.content_frame.set_mode(False)
            bg_color = self._get_effective_bg_color()
            text_color = self._get_effective_text_color()
            self.content_frame.setStyleSheet(self._build_frame_style(bg_color))
            self.text_edit.setStyleSheet(f"""
                QTextEdit {{
                    color: {text_color};
                    background-color: transparent;
                    padding: 0px; margin: 0px; border: none;
                }}
            """)
            self._apply_text_layout()

    def _apply_dialog_readable_style(self):
        """打开对话框前的样式保存。"""
        if self.config.get("auto_mode"):
            self.setWindowOpacity(0.95)
            self.content_frame.setStyleSheet(self._build_frame_style(self._get_effective_bg_color()))
            self.content_frame.set_mode(False)

    # ── 变色龙模式 ──────────────────────────────────────

    def adjust_color_to_background(self):
        """自动拾取窗口背后颜色并调整文字/背景。"""
        if not self.isVisible() or not self.config.get("auto_mode"):
            self.chameleon_timer.stop()
            return

        screen = QApplication.primaryScreen()
        if not screen:
            return

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
            base_text = (0, 0, 0) if brightness > 128 else (255, 255, 255)
            user_alpha = int(self.config.get("text_opacity", 0.9) * 255)
            rgba_color = f"rgba({base_text[0]}, {base_text[1]}, {base_text[2]}, {user_alpha})"
            self.text_edit.setStyleSheet(f"""
                QTextEdit {{
                    color: {rgba_color};
                    background-color: transparent;
                    padding: 0px; margin: 0px; border: none;
                }}
            """)
            self._apply_text_layout()

    # ── 本地阅读 ──────────────────────────────────────────

    def _on_local_update_text(self, text, is_bottom):
        """本地阅读器的文本更新回调。"""
        self.current_display_text = text
        if self.config.get("ghost_mode", False) and not self.ghost_text_visible:
            self._set_text_edit_content("")
            self.text_edit.verticalScrollBar().setValue(0)
            return
        self._set_text_edit_content(text)

    def _on_local_save_progress(self, position):
        """本地阅读器的进度保存回调。"""
        self.config["last_local_pos"] = position
        self.save_config_to_disk()

    def _render_local_page(self):
        """渲染本地阅读当前页。"""
        display_text = self.local_reader.render_page(self.text_edit)
        if display_text:
            self.current_display_text = display_text

    def open_local_file_dialog(self):
        """打开本地 TXT 文件。"""
        from PyQt5.QtWidgets import QFileDialog

        options = QFileDialog.DontUseNativeDialog
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择文本文件", "",
            "Text Files (*.txt);;All Files (*)",
            options=options,
        )
        if not file_path:
            return

        last_file = self.config.get("last_local_file", "")
        same_file = False
        if last_file:
            try:
                same_file = os.path.normpath(file_path) == os.path.normpath(last_file)
            except OSError:
                same_file = file_path == last_file

        target_pos = self.config.get("last_local_pos", 0) if same_file else 0
        self.load_local_file(file_path, target_pos)

    def load_local_file(self, file_path, target_pos=0):
        """加载本地文件。"""
        self.is_local_mode = True
        if not self.local_reader.load_file(file_path, target_pos):
            return

        self.config["last_local_file"] = file_path
        self.config["last_local_pos"] = target_pos
        self.save_config_to_disk()
        self._render_local_page()

    def _restore_last_local_file(self, file_path):
        """启动时恢复上次阅读文件。"""
        pos = self.config.get("last_local_pos", 0)
        self.load_local_file(file_path, pos)

    # ── 网络阅读 ──────────────────────────────────────────

    def _on_bookshelf_updated(self, books):
        self.network.books = books
        if self.book_selector_dialog and self.book_selector_dialog.isVisible():
            self.book_selector_dialog.update_data(books)

    def _on_chapter_loaded(
        self, chapter_index, full_text, scroll_to_bottom,
        request_token, display_char_pos, raw_length, title_prefix_len,
    ):
        if request_token != self.network.chapter_request_token:
            return
        self.network.is_chapter_loading = False
        self.network.current_chapter_index = chapter_index
        self._current_content_raw_length = raw_length
        self._current_title_prefix_len = title_prefix_len
        self.network._current_content_raw_length = raw_length
        self.network._current_title_prefix_len = title_prefix_len
        raw_char_pos = max(0, display_char_pos - title_prefix_len) if not scroll_to_bottom else raw_length
        self.network.current_chapter_progress = raw_char_pos
        if self.network.current_book:
            self.network.current_book["durChapterIndex"] = chapter_index
            self.network.current_book["durChapterPos"] = raw_char_pos

        self.current_chapter_progress = display_char_pos
        self.current_display_text = full_text

        if self.config.get("ghost_mode", False) and not self.ghost_text_visible:
            self._set_text_edit_content("")
            self.text_edit.verticalScrollBar().setValue(0)
        else:
            self._set_text_edit_content(full_text)
            if scroll_to_bottom:
                self._schedule_scroll_position(True)
            elif display_char_pos > 0:
                self._schedule_progress_restore_scroll(display_char_pos)

        self.network.sync_progress_async()
        self._trim_and_prefetch()

    def _on_chapter_load_failed(self, error_text, request_token):
        if request_token != self.network.chapter_request_token:
            return
        self.network.is_chapter_loading = False
        self.current_display_text = error_text
        self._on_local_update_text(error_text, False)

    def _trim_and_prefetch(self):
        """清理旧缓存并预拉取后续章节。"""
        if self.network.current_book and not self.is_local_mode:
            book_url = self.network.current_book.get("bookUrl")
            self.network.trim_cache(book_url, self.network.current_chapter_index)
            self.network.prefetch_future_chapters(book_url, self.network.current_chapter_index)

    def fetch_bookshelf_silent(self):
        self.network.fetch_bookshelf_silent()

    # ── 翻页 ──────────────────────────────────────────────

    def scroll_page(self, direction):
        """翻页：direction > 0 下一页，< 0 上一页。"""
        if self.is_local_mode:
            self.local_reader.scroll_page(direction, self.text_edit)
            self.config["last_local_pos"] = self.local_reader.start_index
            self.save_config_to_disk()
        else:
            if not self.network.current_book or self.network.is_chapter_loading:
                return
            scrollbar = self.text_edit.verticalScrollBar()
            current_val = scrollbar.value()
            max_val = scrollbar.maximum()
            min_val = scrollbar.minimum()
            page_step = self.text_edit.viewport().height() - 30

            target_val = current_val + (direction * page_step)
            if direction > 0:
                if current_val >= max_val - 5:
                    self._next_chapter()
                else:
                    scrollbar.setValue(min(target_val, max_val))
            else:
                if current_val <= min_val + 5:
                    self._prev_chapter()
                else:
                    scrollbar.setValue(max(target_val, min_val))

    def _next_chapter(self):
        """网络模式下加载下一章。"""
        if not self.network.current_book or self.network.is_chapter_loading:
            return
        next_index = self.network.current_chapter_index + 1
        self.network.current_chapter_index = next_index
        self._on_local_update_text("加载下一章...", False)
        self.network.fetch_chapter_content(
            self.network.current_book["bookUrl"], next_index, False, 0,
        )

    def _prev_chapter(self):
        """网络模式下加载上一章。"""
        if not self.network.current_book or self.network.is_chapter_loading:
            return
        if self.network.current_chapter_index > 0:
            prev_index = self.network.current_chapter_index - 1
            self.network.current_chapter_index = prev_index
            self._on_local_update_text("加载上一章...", False)
            self.network.fetch_chapter_content(
                self.network.current_book["bookUrl"], prev_index, True, 0,
            )

    # ── 进度自动保存 ──────────────────────────────────────

    def _auto_save_progress(self):
        """定时自动保存阅读进度。"""
        from time import monotonic

        # 窗口隐藏时不保存
        if not self.isVisible():
            return

        if self.is_local_mode:
            self.config["last_local_pos"] = self.local_reader.start_index
            self.save_config_to_disk()
            return
        if not self.network.current_book or self.network.is_chapter_loading:
            return
        if monotonic() - self.network.last_progress_sync_time < PROGRESS_AUTO_SAVE_INTERVAL:
            return
        self.network.sync_progress_async(self.text_edit)

    # ── 热键 ──────────────────────────────────────────────

    def _create_qshortcuts(self):
        """创建 QShortcut 实例（窗口聚焦时生效）。"""
        hotkey_str = self.config.get("boss_key", "Esc")
        focus_hotkey_str = self.config.get("focus_hotkey", "Ctrl+Shift+R")
        try:
            if self.local_shortcut:
                self.local_shortcut.setKey(QKeySequence())
            self.local_shortcut = QShortcut(QKeySequence(hotkey_str), self)
            self.local_shortcut.activated.connect(self.toggle_window)

            if self.focus_shortcut:
                self.focus_shortcut.setKey(QKeySequence())
            self.focus_shortcut = QShortcut(QKeySequence(focus_hotkey_str), self)
            self.focus_shortcut.activated.connect(self.reveal_window)
        except Exception:
            pass

    def _refresh_hotkeys(self):
        """重新注册全局热键。"""
        hotkey_str = self.config.get("boss_key", "Esc")
        focus_hotkey_str = self.config.get("focus_hotkey", "Ctrl+Shift+R")
        hwnd = int(self.winId())
        self.hotkey_manager.unregister_all(hwnd)
        self.hotkey_manager.register(hwnd, self.HOTKEY_ID_BOSS, hotkey_str)
        self.hotkey_manager.register(hwnd, self.HOTKEY_ID_FOCUS, focus_hotkey_str)
        self._create_qshortcuts()

    def nativeEvent(self, event_type, message):
        """处理 Windows 原生消息（全局热键）。"""
        try:
            event_name = event_type.decode() if isinstance(event_type, bytes) else event_type
            if sys.platform == "win32" and event_name in ("windows_generic_MSG", "windows_dispatcher_MSG"):
                msg = wintypes.MSG.from_address(int(message))
                if msg.message == WM_HOTKEY:
                    if msg.wParam == self.HOTKEY_ID_BOSS:
                        self.toggle_window()
                        return True, 0
                    if msg.wParam == self.HOTKEY_ID_FOCUS:
                        self.reveal_window()
                        return True, 0
        except Exception:
            logging.exception("处理原生热键消息失败")
        return super().nativeEvent(event_type, message)

    # ── 窗口操作 ──────────────────────────────────────────

    def toggle_window(self):
        """老板键：隐藏/显示窗口。"""
        current_time = time.time()
        if current_time - self.last_toggle_time < 0.3:
            return
        self.last_toggle_time = current_time
        if self.isVisible():
            self.sync_progress_async()
            self.hide()
        else:
            self.showNormal()
            self.raise_()
            self.activateWindow()
            self._reload_progress_on_reveal()
            self.apply_style()
            try:
                ctypes.windll.user32.SetForegroundWindow(int(self.winId()))
            except Exception:
                pass
            if self.config.get("auto_mode", False):
                self.chameleon_timer.start()
                self.adjust_color_to_background()
            if self.config.get("antishot_mode", False):
                set_window_protection(int(self.winId()), True)

    def reveal_window(self):
        """显示并激活窗口（唤醒快捷键）。"""
        if not self.isVisible():
            self.showNormal()
        self._reload_progress_on_reveal()
        if self.config.get("ghost_mode", False) and not self.ghost_text_visible:
            self._set_ghost_text_visible(True)
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

    def sync_progress_async(self):
        """同步阅读进度。"""
        if self.is_local_mode:
            self.config["last_local_pos"] = self.local_reader.start_index
            self.save_config_to_disk()
        else:
            self.network.sync_progress_async(self.text_edit)

    # ── 书架、目录、设置对话框 ────────────────────────────

    def open_book_selector(self):
        """打开网络书架选择器。"""
        self.network.fetch_bookshelf_silent()
        self.book_selector_dialog = BookSelector(self.network, self)
        self._apply_dialog_readable_style()
        if self.book_selector_dialog.exec_() == QDialog.Accepted:
            if self.book_selector_dialog.selected_book:
                self._load_book(self.book_selector_dialog.selected_book)
        self.apply_style()
        self.book_selector_dialog = None

    def open_toc_selector(self):
        """打开章节目录选择器。"""
        if not self.network.current_book:
            self._on_local_update_text("请先选择一本书！", False)
            return
        self._apply_dialog_readable_style()
        toc = TocSelector(
            self.config["ip"], self.network.current_book["bookUrl"],
            self.network.current_chapter_index, self.network.current_toc, self,
        )
        if toc.exec_() == QDialog.Accepted and toc.selected_index is not None:
            self.network.current_chapter_index = toc.selected_index
            self._on_local_update_text(f"跳转到章节: {toc.selected_index}", False)
            self.network.fetch_chapter_content(
                self.network.current_book["bookUrl"], toc.selected_index, False, 0,
            )
        self.apply_style()

    def open_settings(self):
        """打开设置对话框。"""
        self.is_settings_open = True
        self._apply_dialog_readable_style()
        dialog = SettingsDialog(self.config, self)
        if dialog.exec_() == QDialog.Accepted:
            self.config = dialog.config
            self.save_config_to_disk()
            self._apply_window_flags()
            self.apply_style()
            self._refresh_hotkeys()
            self.network.set_ip(self.config["ip"])
            if self.config["ip"].startswith("http"):
                self.network.fetch_bookshelf_silent()
        else:
            self.apply_style()
        self.is_settings_open = False
        self.showNormal()
        self.activateWindow()

    def _load_book(self, book):
        """加载网络书籍。"""
        self.is_local_mode = False
        self._on_local_update_text(f"打开: {book.get('name', '未知书籍')}", False)
        self.network.load_book(book)

    def on_toc_loaded(self, chapters):
        """目录加载完成回调（由 TocSelector 调用）。"""
        self.network.current_toc = chapters

    # ── 幽灵模式 ──────────────────────────────────────────

    def get_ghost_mode_display_mode(self):
        return self.config.get("ghost_mode_display_mode", "hover")

    def should_show_text_on_enter(self):
        return self.get_ghost_mode_display_mode() != "double_click"

    def _cache_current_view_state(self):
        if self.ghost_text_visible:
            self.current_display_text = self.text_edit.toPlainText()
            self.current_scroll_value = self.text_edit.verticalScrollBar().value()

    def _restore_current_view_state(self):
        if self.is_local_mode:
            self._render_local_page()
            return
        self._set_text_edit_content(self.current_display_text)
        scrollbar = self.text_edit.verticalScrollBar()
        if self.current_scroll_value < 0:
            self._schedule_scroll_position(True)
        else:
            scrollbar.setValue(min(self.current_scroll_value, scrollbar.maximum()))

    def _set_ghost_text_visible(self, visible):
        if self.ghost_text_visible == visible:
            return
        if visible:
            self.ghost_text_visible = True
            self.apply_style()
            self._restore_current_view_state()
        else:
            self._cache_current_view_state()
            self.ghost_text_visible = False
            self._set_text_edit_content("")
            self.text_edit.verticalScrollBar().setValue(0)
            self.apply_style()

    # ── 菜单 ──────────────────────────────────────────────

    def show_context_menu(self, global_pos):
        """显示右键上下文菜单。"""
        cmenu = create_context_menu(self)
        cmenu.exec_(global_pos)

    def should_open_context_menu(self, modifiers):
        if not self.config.get("context_menu_requires_ctrl", True):
            return True
        return bool(modifiers & Qt.ControlModifier)

    def on_tray_activated(self, reason):
        if reason == QSystemTrayIcon.DoubleClick:
            self.toggle_window()

    # ── 事件过滤 ──────────────────────────────────────────

    def eventFilter(self, source, event):
        if source in (self.text_edit, self.text_edit.viewport()):
            if event.type() == QEvent.Wheel:
                if self.config.get("ghost_mode", False) and not self.ghost_text_visible:
                    return True
                if not self.is_local_mode and not self.network.current_book:
                    return True
                delta = event.angleDelta().y()
                if self.is_local_mode:
                    self.scroll_page(-1 if delta > 0 else 1)
                    return True
                else:
                    scrollbar = self.text_edit.verticalScrollBar()
                    if delta < 0 and scrollbar.value() >= scrollbar.maximum() - 2:
                        self._next_chapter()
                        return True
                    elif delta > 0 and scrollbar.value() <= scrollbar.minimum() + 2:
                        self._prev_chapter()
                        return True

        if source == self.text_edit.viewport():
            local_pos = None
            if hasattr(event, "globalPos") and hasattr(event, "pos"):
                local_pos = event.pos()

            if event.type() == QEvent.MouseMove and local_pos is not None:
                if not (event.buttons() & Qt.LeftButton):
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
                    self._set_ghost_text_visible(True)
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

    # ── 鼠标事件 ──────────────────────────────────────────

    def is_in_resize_area(self, pos):
        rect = self.rect()
        resize_rect = QRect(
            rect.width() - self.resize_margin,
            rect.height() - self.resize_margin,
            self.resize_margin, self.resize_margin,
        )
        return resize_rect.contains(pos)

    def begin_pointer_action(self, local_pos, global_pos):
        if self.is_in_resize_area(local_pos):
            self.is_resizing = True
            self.is_moving = False
            return
        self.is_moving = True
        self.is_resizing = False
        self.oldPos = global_pos

    def handle_pointer_drag(self, local_pos, global_pos):
        if self.is_resizing:
            new_w = max(local_pos.x(), 100)
            min_h = getattr(self, "single_line_height", 20)
            new_h = max(local_pos.y(), min_h)
            self.resize(new_w, new_h)
            if self.is_local_mode:
                self._render_local_page()
        elif self.is_moving:
            delta = QPoint(global_pos - self.oldPos)
            self.move(self.x() + delta.x(), self.y() + delta.y())
            self.oldPos = global_pos
        if self.config.get("auto_mode"):
            self.adjust_color_to_background()

    def finish_pointer_action(self):
        self.is_resizing = False
        self.is_moving = False
        self.setCursor(Qt.ArrowCursor)
        self.save_config_to_disk()

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
        if event.button() == Qt.LeftButton:
            if self.config.get("ghost_mode", False) and self.get_ghost_mode_display_mode() == "double_click":
                self._set_ghost_text_visible(True)
        super().mouseDoubleClickEvent(event)

    def contextMenuEvent(self, event):
        if self.should_open_context_menu(event.modifiers()):
            self.show_context_menu(self.mapToGlobal(event.pos()))

    # ── 键盘事件 ──────────────────────────────────────────

    def keyPressEvent(self, event):
        key = event.key()
        if key in (Qt.Key_Right, Qt.Key_Down, Qt.Key_Space, Qt.Key_PageDown):
            self.scroll_page(1)
        elif key in (Qt.Key_Left, Qt.Key_Up, Qt.Key_PageUp):
            self.scroll_page(-1)

    # ── 鼠标进入/离开 ──────────────────────────────────────

    def enterEvent(self, event):
        if self.config.get("ghost_mode", False) and self.should_show_text_on_enter():
            self._set_ghost_text_visible(True)
        super().enterEvent(event)

    def leaveEvent(self, event):
        if self.is_settings_open or self.is_resizing or self.is_moving:
            return
        if self._startup_guard:
            return
        global_pos = QCursor.pos()
        local_pos = self.mapFromGlobal(global_pos)
        if self.rect().contains(local_pos):
            return
        if self.config.get("ghost_mode", False):
            self._set_ghost_text_visible(False)
        super().leaveEvent(event)

    # ── 退出 ──────────────────────────────────────────────

    def closeEvent(self, event):
        self.sync_progress_async()
        if self.is_local_mode:
            self.config["last_local_pos"] = self.local_reader.start_index
        self.save_config_to_disk()
        super().closeEvent(event)

    def quit_app(self):
        """退出应用。"""
        self.sync_progress_async()
        if self.is_local_mode:
            self.config["last_local_pos"] = self.local_reader.start_index
        self.save_config_to_disk()
        hwnd = int(self.winId())
        self.hotkey_manager.unregister_all(hwnd)
        QApplication.instance().quit()


def run_app():
    """启动鱼阅应用。"""
    from PyQt5.QtWidgets import QApplication
    from fishingread.single_instance import try_activate_existing_instance
    from fishingread.early_logging import setup_file_logging

    setup_file_logging()
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)

    # 单实例检查
    activated, shared_mem = try_activate_existing_instance()
    if activated:
        sys.exit(0)
    shared_mem.create(1)

    # 启动主窗口
    ex = FishingRead()
    sys.exit(app.exec_())
