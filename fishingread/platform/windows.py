"""
Windows 平台特定功能封装：
- 防截屏（SetWindowDisplayAffinity）
- 原生全局热键注册
"""

import sys
import ctypes
from ctypes import wintypes

from fishingread.constants import (
    WM_HOTKEY, MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_WIN, MOD_NOREPEAT,
)


def set_window_protection(hwnd, enable=True):
    """设置或取消窗口防截屏保护（Win10 2004+ WDA_EXCLUDEFROMCAPTURE）。"""
    try:
        user32 = ctypes.windll.user32
        WDA_NONE = 0x00000000
        WDA_EXCLUDEFROMCAPTURE = 0x00000011
        mode = WDA_EXCLUDEFROMCAPTURE if enable else WDA_NONE
        user32.SetWindowDisplayAffinity(hwnd, mode)
    except Exception as e:
        print(f"防截屏设置失败: {e}")


def parse_native_hotkey(hotkey_str):
    """将热键字符串解析为 (modifiers, vk_code) 元组。"""
    if not hotkey_str:
        return None

    vk_map = {
        "esc": 0x1B, "escape": 0x1B, "tab": 0x09,
        "space": 0x20, "enter": 0x0D, "return": 0x0D,
        "left": 0x25, "up": 0x26, "right": 0x27, "down": 0x28,
        "pageup": 0x21, "pgup": 0x21,
        "pagedown": 0x22, "pgdn": 0x22,
        "home": 0x24, "end": 0x23,
        "insert": 0x2D, "delete": 0x2E, "del": 0x2E,
    }

    modifiers = 0
    key_code = None
    parts = [p.strip().lower() for p in hotkey_str.replace("-", "+").split("+") if p.strip()]
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


class NativeHotkeyManager:
    """管理 Windows 全局热键的注册与注销。"""

    def __init__(self):
        self.registered_ids = set()

    def register(self, hwnd, hotkey_id, hotkey_str):
        """注册一个全局热键。成功返回 True。"""
        if sys.platform != "win32":
            return False
        parsed = parse_native_hotkey(hotkey_str)
        if not parsed:
            return False
        modifiers, key_code = parsed
        user32 = ctypes.windll.user32
        user32.UnregisterHotKey(hwnd, hotkey_id)
        if user32.RegisterHotKey(hwnd, hotkey_id, modifiers, key_code):
            self.registered_ids.add(hotkey_id)
            return True
        return False

    def unregister_all(self, hwnd):
        """注销所有已注册的热键。"""
        if sys.platform != "win32":
            self.registered_ids.clear()
            return
        user32 = ctypes.windll.user32
        for hotkey_id in list(self.registered_ids):
            try:
                user32.UnregisterHotKey(hwnd, hotkey_id)
            except Exception:
                pass
        self.registered_ids.clear()
