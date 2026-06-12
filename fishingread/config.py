"""
配置加载/保存/规范化。
"""

import os
import json

from fishingread.constants import DEFAULT_CONFIG, LEGACY_CONFIG_KEYS

CONFIG_FILE = "config.json"


def load_config():
    """从磁盘加载配置，合并默认值。"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                file_config = json.load(f)
            return normalize_config(file_config)
        except (OSError, json.JSONDecodeError):
            return DEFAULT_CONFIG.copy()
    return DEFAULT_CONFIG.copy()


def normalize_config(file_config):
    """合并用户配置与默认值，兼容旧版键名。"""
    config = {**DEFAULT_CONFIG, **file_config}

    # 兼容旧版 show_in_alt_tab / show_in_taskbar / hide_from_alt_tab
    if "show_in_switcher" not in file_config:
        if "show_in_alt_tab" in file_config or "show_in_taskbar" in file_config:
            config["show_in_switcher"] = bool(
                file_config.get("show_in_alt_tab", False)
                or file_config.get("show_in_taskbar", False)
            )
        else:
            config["show_in_switcher"] = not file_config.get("hide_from_alt_tab", True)

    # 兼容旧版单 opacity 键
    if "text_opacity" not in file_config:
        config["text_opacity"] = file_config.get("opacity", DEFAULT_CONFIG["text_opacity"])
    if "background_opacity" not in file_config:
        config["background_opacity"] = file_config.get("opacity", DEFAULT_CONFIG["background_opacity"])

    # 背景透明度下限
    config["background_opacity"] = max(0.01, config.get("background_opacity", DEFAULT_CONFIG["background_opacity"]))

    # 清理旧键
    for key in LEGACY_CONFIG_KEYS:
        config.pop(key, None)

    return config


def save_config(config, window_x=None, window_y=None, window_width=None, window_height=None):
    """保存配置到磁盘。"""
    try:
        for key in LEGACY_CONFIG_KEYS:
            config.pop(key, None)
        config["background_opacity"] = max(0.01, config.get("background_opacity", DEFAULT_CONFIG["background_opacity"]))

        if window_x is not None:
            config["window_x"] = window_x
            config["window_y"] = window_y
            config["window_width"] = window_width
            config["window_height"] = window_height

        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=4, ensure_ascii=False)
    except Exception as e:
        print(f"保存配置失败: {e}")
