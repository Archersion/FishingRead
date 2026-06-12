"""
鱼阅 (FishingRead) - 隐蔽式桌面阅读工具
入口文件：python main.py
"""

from fishingread.early_logging import install_early_exception_hook

install_early_exception_hook()

from fishingread.app import run_app

if __name__ == "__main__":
    run_app()
