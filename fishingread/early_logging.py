"""
早期异常钩子：在 QApplication 创建前捕获崩溃，写入日志文件。
"""

import sys
import os
import time
import traceback
import faulthandler
import threading

_FAULT_LOG_FILE = None
_FAULT_LOG_PATH = None


def get_runtime_dir():
    """获取运行目录（兼容打包模式）。"""
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def write_crash_log(title, exc_type, exc_value, exc_traceback):
    """写入早期崩溃日志，覆盖 PyQt 导入失败等 QApplication 创建前异常。"""
    try:
        log_path = os.path.join(get_runtime_dir(), "鱼阅.log")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"\n{time.strftime('%Y-%m-%d %H:%M:%S')} [ERROR] {title}\n")
            traceback.print_exception(exc_type, exc_value, exc_traceback, file=f)
    except Exception:
        pass


def install_early_exception_hook():
    """安装全局异常钩子，避免 windowed 打包后无日志闪退。"""
    global _FAULT_LOG_FILE, _FAULT_LOG_PATH
    default_hook = sys.excepthook
    try:
        log_path = os.path.join(get_runtime_dir(), "鱼阅.log")
        _FAULT_LOG_PATH = log_path
        _FAULT_LOG_FILE = open(log_path, "a", encoding="utf-8")
        faulthandler.enable(file=_FAULT_LOG_FILE, all_threads=True)
    except Exception:
        _FAULT_LOG_FILE = None

    def handle_exception(exc_type, exc_value, exc_traceback):
        write_crash_log("未捕获异常", exc_type, exc_value, exc_traceback)
        default_hook(exc_type, exc_value, exc_traceback)

    sys.excepthook = handle_exception


def setup_file_logging():
    """将错误日志写入文件（打包后无控制台时同样可查）。"""
    try:
        log_dir = get_runtime_dir()
        log_path = os.path.join(log_dir, "鱼阅.log")
        import logging
        logging.basicConfig(
            filename=log_path,
            level=logging.ERROR,
            format="%(asctime)s [%(levelname)s] %(message)s",
            encoding="utf-8",
        )
    except Exception:
        pass
