"""
鱼阅 (FishingRead) 主窗口应用 — 延迟加载入口。
所有重量级导入推迟到 run_app() 被调用时。
"""

import sys
import os


def run_app():
    """启动鱼阅应用（延迟导入，加速启动）。"""
    from fishingread.main_window import run_app as _run

    _run()
