"""
本地文件阅读器：支持 TXT 文件智能分页、编码自动检测、进度锚点恢复。
"""

import os
import traceback

from PyQt5.QtCore import QPoint

from fishingread.constants import LOCAL_PAGE_BUFFER_SIZE


class LocalReader:
    """本地 TXT 阅读引擎，负责文件加载、分页渲染和翻页。"""

    def __init__(self, on_update_text=None, on_save_progress=None):
        self.full_text = ""
        self.start_index = 0
        self.page_history = []
        self.file_path = ""
        self._on_update_text = on_update_text
        self._on_save_progress = on_save_progress

    def load_file(self, file_path, target_pos=0):
        """加载本地文件，支持 UTF-8/GB18030。"""
        try:
            content = ""
            try:
                with open(file_path, "r", encoding="utf-8-sig") as f:
                    content = f.read()
            except UnicodeDecodeError:
                try:
                    with open(file_path, "r", encoding="gb18030") as f:
                        content = f.read()
                except Exception:
                    if self._on_update_text:
                        self._on_update_text("编码无法识别，请转为 UTF-8 或 GBK", False)
                    return False

            if not content:
                if self._on_update_text:
                    self._on_update_text("文件为空", False)
                return False

            self.full_text = content
            self.file_path = file_path
            safe_pos = min(max(0, target_pos), len(content) - 1) if content else 0
            self.start_index = safe_pos
            self.page_history = []
            return True

        except Exception as e:
            traceback.print_exc()
            if self._on_update_text:
                self._on_update_text(f"打开文件失败: {str(e)}", False)
            return False

    def render_page(self, text_edit):
        """渲染当前页到 QTextEdit。"""
        if not self.full_text:
            return None

        end_buffer = min(self.start_index + LOCAL_PAGE_BUFFER_SIZE, len(self.full_text))
        display_text = self.full_text[self.start_index:end_buffer]

        text_edit.setPlainText(display_text)
        text_edit.verticalScrollBar().setValue(0)
        return display_text

    def calc_next_page_start(self, text_edit):
        """利用视图几何坐标，探测屏幕底部边缘的字符位置。"""
        if not text_edit.toPlainText():
            return 0

        viewport_h = text_edit.viewport().height()
        target_y = viewport_h + 2
        cursor = text_edit.cursorForPosition(QPoint(0, target_y))

        next_pos = cursor.position()
        if next_pos >= len(text_edit.toPlainText()):
            return len(text_edit.toPlainText())
        return next_pos

    def calc_prev_page_start(self, text_edit):
        """通过加载前文并滚到底部，探测上一页的起始位置。"""
        if self.start_index == 0:
            return 0

        text_edit.setUpdatesEnabled(False)
        try:
            temp_start = max(0, self.start_index - LOCAL_PAGE_BUFFER_SIZE)
            prev_content = self.full_text[temp_start:self.start_index]

            text_edit.setPlainText(prev_content)

            scrollbar = text_edit.verticalScrollBar()
            scrollbar.setValue(scrollbar.maximum())

            cursor = text_edit.cursorForPosition(QPoint(0, 0))
            chars_in_prev_page = len(prev_content) - cursor.position()
            return max(0, self.start_index - chars_in_prev_page)
        finally:
            text_edit.setUpdatesEnabled(True)

    def scroll_page(self, direction, text_edit):
        """翻页：direction > 0 为下一页，< 0 为上一页。"""
        if not self.full_text:
            return False

        if direction > 0:  # 下一页
            if self.start_index >= len(self.full_text):
                return False

            step = self.calc_next_page_start(text_edit)
            if step == 0 and self.start_index < len(self.full_text):
                step = 1

            self.page_history.append(self.start_index)
            self.start_index += step

            if self.start_index > len(self.full_text):
                self.start_index = len(self.full_text)

            self.render_page(text_edit)

        else:  # 上一页
            if self.page_history:
                self.start_index = self.page_history.pop()
            else:
                self.start_index = self.calc_prev_page_start(text_edit)

            self.render_page(text_edit)

        if self._on_save_progress:
            self._on_save_progress(self.start_index)

        return True

    def get_progress(self):
        """获取当前进度信息。"""
        return {
            "file_path": self.file_path,
            "position": self.start_index,
        }
