"""
菜单创建工具：上下文菜单、托盘菜单。
"""

from PyQt5.QtWidgets import QMenu, QSystemTrayIcon

from fishingread.constants import MENU_STYLESHEET
from fishingread.svg_icons import add_menu_action, get_app_icon


def create_context_menu(parent):
    """创建主窗口右键上下文菜单。"""
    cmenu = QMenu(parent)
    cmenu.setStyleSheet(MENU_STYLESHEET)

    add_menu_action(cmenu, "打开本地 TXT", parent.open_local_file_dialog, "folder-open")
    cmenu.addSeparator()
    add_menu_action(cmenu, "网络书架 (搜索)", parent.open_book_selector, "bookshelf")
    add_menu_action(cmenu, "章节目录 (网络)", parent.open_toc_selector, "book-open")
    cmenu.addSeparator()
    add_menu_action(cmenu, "设置", parent.open_settings, "settings")
    cmenu.addSeparator()
    add_menu_action(cmenu, "退出", parent.quit_app, "x")

    return cmenu


def create_tray(parent):
    """创建系统托盘图标和菜单。"""
    tray_icon = QSystemTrayIcon(parent)
    icon = get_app_icon()
    parent.setWindowIcon(icon)
    tray_icon.setIcon(icon)

    tray_menu = QMenu()
    tray_menu.setStyleSheet(MENU_STYLESHEET)

    add_menu_action(tray_menu, "显示", parent.reveal_window, "eye")
    add_menu_action(tray_menu, "隐藏", lambda: (
        parent.sync_progress_async(),
        parent.hide(),
    ) or None, "x")
    tray_menu.addSeparator()
    add_menu_action(tray_menu, "退出", parent.quit_app, "x")

    tray_icon.setContextMenu(tray_menu)
    tray_icon.activated.connect(parent.on_tray_activated)

    return tray_icon
