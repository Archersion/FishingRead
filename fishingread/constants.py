"""
常量、默认配置、样式表和 SVG 图标定义。
"""

import sys
import os

# ── 运行目录 ──────────────────────────────────────────────

def get_runtime_dir():
    """获取运行目录，保证源码运行和打包运行结果一致。"""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


# ── 常量 ──────────────────────────────────────────────────

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

SINGLE_INSTANCE_SERVER = "FishingRead_IPC"


# ── 默认配置 ──────────────────────────────────────────────

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
    "last_local_pos": 0,
}


# ── 样式表 ────────────────────────────────────────────────

DARK_STYLESHEET = """\
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

MENU_STYLESHEET = """\
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


# ── SVG 图标定义 ──────────────────────────────────────────

_SVG_COLOR = "#cccccc"

_SVG_ICONS = {
    "folder-open": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        'stroke="#cccccc" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M2 6a2 2 0 0 1 2-2h5l2 2h9a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V6z"/>'
        '</svg>'
    ),
    "bookshelf": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        'stroke="#cccccc" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<rect x="3" y="4" width="4" height="16" rx="1"/>'
        '<rect x="8" y="6" width="4" height="14" rx="1"/>'
        '<rect x="13" y="3" width="4" height="18" rx="1"/>'
        '<rect x="18" y="7" width="4" height="12" rx="1"/>'
        '</svg>'
    ),
    "book-open": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        'stroke="#cccccc" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/>'
        '<path d="M4 4.5A2.5 2.5 0 0 1 6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15z"/>'
        '<line x1="8" y1="7" x2="16" y2="7"/>'
        '<line x1="8" y1="10" x2="14" y2="10"/>'
        '<line x1="8" y1="13" x2="15" y2="13"/>'
        '</svg>'
    ),
    "settings": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        'stroke="#cccccc" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
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
        'stroke="#cccccc" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<line x1="18" y1="6" x2="6" y2="18"/>'
        '<line x1="6" y1="6" x2="18" y2="18"/>'
        '</svg>'
    ),
    "refresh-cw": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        'stroke="#cccccc" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<polyline points="23 4 23 10 17 10"/>'
        '<path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"/>'
        '</svg>'
    ),
    "save": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        'stroke="#cccccc" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/>'
        '<polyline points="17 21 17 13 7 13 7 21"/>'
        '<polyline points="7 11 7 3 15 3"/>'
        '</svg>'
    ),
    "eye": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        'stroke="#cccccc" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/>'
        '<circle cx="12" cy="12" r="3"/>'
        '</svg>'
    ),
    "shield": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        'stroke="#cccccc" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>'
        '<polyline points="9 12 11 14 15 10"/>'
        '</svg>'
    ),
    "ghost": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        'stroke="#cccccc" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M12 2a8 8 0 0 0-8 8v10l3-2 2 2 2-2 2 2 2-2 2 2 3-2V10a8 8 0 0 0-8-8z"/>'
        '<circle cx="9" cy="10" r="1.5" fill="#cccccc"/>'
        '<circle cx="15" cy="10" r="1.5" fill="#cccccc"/>'
        '</svg>'
    ),
    "chameleon": (
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" '
        'stroke="#cccccc" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<ellipse cx="12" cy="12" rx="9" ry="6"/>'
        '<circle cx="12" cy="9" r="2" fill="#cccccc"/>'
        '<path d="M12 15c-3 0-5-1-5-1s2 3 5 3 5-3 5-3-2 1-5 1z"/>'
        '</svg>'
    ),
}


def get_svg_icon_bytes(name):
    """根据名称获取 SVG 字节数据。"""
    svg = _SVG_ICONS.get(name)
    return svg.encode("utf-8") if svg else None
