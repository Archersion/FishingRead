"""
Legado 网络阅读器：书架同步、章节加载、进度同步、章节缓存。
"""

import threading
import time
import logging
from PyQt5.QtCore import QObject, pyqtSignal

from fishingread.constants import (
    BOOKSHELF_TIMEOUT, CHAPTER_LIST_TIMEOUT, CHAPTER_CONTENT_TIMEOUT,
    PROGRESS_SYNC_TIMEOUT, PROGRESS_AUTO_SAVE_INTERVAL,
    FUTURE_CHAPTER_CACHE_SIZE,
)


class NetworkReader(QObject):
    """Legado 网络阅读引擎，负责书架、章节、进度同步。"""

    # 信号
    bookshelf_updated = pyqtSignal(list)
    chapter_loaded = pyqtSignal(int, str, bool, int, int, int, int)
    chapter_load_failed = pyqtSignal(str, int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.ip = ""

        # 书架/书籍状态
        self.books = []
        self.current_book = None
        self.current_chapter_index = 0
        self.current_toc = []
        self.is_chapter_loading = False
        self.chapter_request_token = 0
        self.current_chapter_progress = 0
        self.last_progress_sync_time = time.monotonic()
        self._progress_restore = None
        self._current_content_raw_length = 0
        self._current_title_prefix_len = 0

        # 章节缓存
        self.chapter_cache = {}
        self.chapter_cache_lock = threading.Lock()
        self.prefetching_chapters = set()

    def set_ip(self, ip):
        self.ip = ip

    # ── 书架 ──────────────────────────────────────────────

    def fetch_bookshelf_silent(self):
        """后台线程拉取书架数据。"""
        threading.Thread(target=self._fetch_bookshelf_thread, daemon=True).start()

    def _fetch_bookshelf_thread(self):
        import requests
        url = f"{self.ip}/getBookshelf"
        try:
            res = requests.get(url, timeout=BOOKSHELF_TIMEOUT)
            if res.status_code == 200:
                data = res.json()
                self.bookshelf_updated.emit(data.get("data", []))
            else:
                logging.error("获取书架失败: url=%s status=%s", url, res.status_code)
        except requests.RequestException:
            logging.exception("获取书架网络异常: url=%s", url)
        except ValueError:
            logging.exception("获取书架 JSON 解析失败: url=%s", url)

    # ── 目录 ──────────────────────────────────────────────

    def fetch_toc_silent(self, book_url):
        """后台线程拉取章节目录。"""
        threading.Thread(target=self._fetch_toc_thread, args=(book_url,), daemon=True).start()

    def _fetch_toc_thread(self, book_url):
        import requests
        try:
            url = f"{self.ip}/getChapterList"
            res = requests.get(url, params={"url": book_url}, timeout=CHAPTER_LIST_TIMEOUT)
            if res.status_code == 200:
                data = res.json()
                if data["isSuccess"]:
                    self.current_toc = data["data"]
        except requests.RequestException:
            pass

    # ── 章节内容 ──────────────────────────────────────────

    def load_book(self, book):
        """加载一本书。"""
        self.current_book = book
        try:
            self.current_chapter_index = int(book.get("durChapterIndex") or 0)
        except (TypeError, ValueError):
            self.current_chapter_index = 0
        self.clear_cache()
        try:
            raw_progress_pos = int(book.get("durChapterPos") or 0)
        except (TypeError, ValueError):
            raw_progress_pos = 0
        self.current_chapter_progress = 0
        self.current_toc = []
        book_url = book.get("bookUrl")
        if not book_url:
            self.chapter_request_token += 1
            self.is_chapter_loading = False
            logging.error("书籍数据缺少 bookUrl: %s", book)
            self.chapter_load_failed.emit("书籍数据缺少 bookUrl，无法打开。", self.chapter_request_token)
            return
        logging.info(
            "开始加载网络书籍: name=%s author=%s index=%s url=%s",
            book.get("name"), book.get("author"), self.current_chapter_index, book_url,
        )
        self.fetch_chapter_content(book_url, self.current_chapter_index, False, raw_progress_pos)
        self.fetch_toc_silent(book_url)

    def fetch_chapter_content(self, book_url, chapter_index, scroll_to_bottom=False, progress_pos=0):
        """获取章节内容（优先缓存）。"""
        self.chapter_request_token += 1
        request_token = self.chapter_request_token
        self.is_chapter_loading = True

        cached_entry = self._get_cached(book_url, chapter_index)
        if cached_entry:
            display_char_pos = self._calc_display_char_pos(cached_entry, progress_pos)
            self.chapter_loaded.emit(
                chapter_index, cached_entry["full_text"], scroll_to_bottom,
                request_token, display_char_pos,
                cached_entry["raw_length"], cached_entry["title_prefix_len"],
            )
            return

        t = threading.Thread(
            target=self._fetch_chapter_thread,
            args=(book_url, chapter_index, scroll_to_bottom, request_token, progress_pos),
            daemon=True,
        )
        t.start()

    def _fetch_chapter_thread(self, book_url, chapter_index, scroll_to_bottom, request_token, progress_pos):
        import requests
        url = f"{self.ip}/getBookContent"
        params = {"url": book_url, "index": chapter_index}
        try:
            res = requests.get(url, params=params, timeout=CHAPTER_CONTENT_TIMEOUT)

            if res.status_code == 200:
                data = res.json()
                if not data.get("isSuccess"):
                    logging.error(
                        "章节读取失败: url=%s params=%s error=%s",
                        url, params, data.get("errorMsg"),
                    )
                    self.chapter_load_failed.emit(
                        f"读取失败: {data.get('errorMsg')}", request_token
                    )
                    return

                raw_content = data.get("data", "")
                entry = self._build_cache_entry(chapter_index, raw_content)
                self._set_cached(book_url, chapter_index, entry)

                display_char_pos = self._calc_display_char_pos(entry, progress_pos)
                self.chapter_loaded.emit(
                    chapter_index, entry["full_text"], scroll_to_bottom,
                    request_token, display_char_pos,
                    entry["raw_length"], entry["title_prefix_len"],
                )
            else:
                logging.error("章节 HTTP 错误: url=%s params=%s status=%s", url, params, res.status_code)
                self.chapter_load_failed.emit(f"HTTP错误: {res.status_code}", request_token)
        except Exception as e:
            logging.exception("章节网络异常: url=%s params=%s", url, params)
            self.chapter_load_failed.emit(f"网络错误: {str(e)}", request_token)

    def get_chapter_title(self, chapter_index):
        """获取章节标题。"""
        if self.current_toc and 0 <= chapter_index < len(self.current_toc):
            return self.current_toc[chapter_index].get("title", "")
        return f"第 {chapter_index + 1} 章"

    def _build_cache_entry(self, chapter_index, raw_content):
        """构建缓存条目。"""
        chapter_title = self.get_chapter_title(chapter_index)
        content = raw_content.replace("<br>", "\n").replace("&nbsp;", " ")
        title_prefix = f"【 {chapter_title} 】\n\n"
        return {
            "full_text": f"{title_prefix}{content}",
            "raw_length": len(content),
            "title_prefix_len": len(title_prefix),
        }

    def _calc_display_char_pos(self, entry, progress_pos):
        """计算显示字符位置。"""
        if entry["raw_length"] > 0 and progress_pos > 0:
            return entry["title_prefix_len"] + min(progress_pos, entry["raw_length"])
        return 0

    # ── 缓存管理 ──────────────────────────────────────────

    def _get_cached(self, book_url, chapter_index):
        with self.chapter_cache_lock:
            return self.chapter_cache.get((book_url, chapter_index))

    def _set_cached(self, book_url, chapter_index, entry):
        with self.chapter_cache_lock:
            self.chapter_cache[(book_url, chapter_index)] = entry

    def clear_cache(self):
        with self.chapter_cache_lock:
            self.chapter_cache.clear()
            self.prefetching_chapters.clear()

    def trim_cache(self, book_url, chapter_index):
        """清理远离当前章节的缓存。"""
        min_index = max(0, chapter_index - 1)
        max_index = chapter_index + FUTURE_CHAPTER_CACHE_SIZE
        with self.chapter_cache_lock:
            stale_keys = [
                key for key in self.chapter_cache
                if key[0] != book_url or key[1] < min_index or key[1] > max_index
            ]
            for key in stale_keys:
                self.chapter_cache.pop(key, None)

    # ── 预拉取 ────────────────────────────────────────────

    def prefetch_future_chapters(self, book_url, chapter_index):
        """提前缓存后续章节。"""
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
                target=self._prefetch_thread,
                args=(book_url, next_index, cache_key),
                daemon=True,
            ).start()

    def _prefetch_thread(self, book_url, chapter_index, cache_key):
        import requests
        try:
            url = f"{self.ip}/getBookContent"
            params = {"url": book_url, "index": chapter_index}
            res = requests.get(url, params=params, timeout=CHAPTER_CONTENT_TIMEOUT)
            if res.status_code != 200:
                return
            data = res.json()
            if not data.get("isSuccess"):
                return
            entry = self._build_cache_entry(chapter_index, data.get("data", ""))
            self._set_cached(book_url, chapter_index, entry)
        except Exception:
            pass
        finally:
            with self.chapter_cache_lock:
                self.prefetching_chapters.discard(cache_key)

    # ── 进度同步 ──────────────────────────────────────────

    def sync_progress_async(self, text_edit=None):
        """后台同步阅读进度到 Legado。"""
        if not self.current_book:
            return

        self.last_progress_sync_time = time.monotonic()

        # 获取章节内字符位置
        if text_edit is not None:
            from PyQt5.QtCore import QPoint
            cursor = text_edit.cursorForPosition(QPoint(0, 0))
            char_pos = max(0, cursor.position() - self._current_title_prefix_len)
            if self._current_content_raw_length > 0:
                char_pos = min(char_pos, self._current_content_raw_length)
            else:
                char_pos = max(0, char_pos)
        else:
            char_pos = self.current_chapter_progress

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
        ip = self.ip

        threading.Thread(
            target=self._sync_task,
            args=(book, chapter_index, title, char_pos, ip),
            daemon=True,
        ).start()

    def _sync_task(self, book, chapter_index, title, progress, ip):
        import requests
        try:
            data = {
                "name": book["name"],
                "author": book["author"],
                "durChapterIndex": chapter_index,
                "durChapterPos": progress,
                "durChapterTime": book.get("durChapterTime", int(time.time() * 1000)),
                "durChapterTitle": title,
            }
            url = f"{ip}/saveBookProgress"
            requests.post(url, json=data, timeout=PROGRESS_SYNC_TIMEOUT)
        except requests.RequestException:
            pass
