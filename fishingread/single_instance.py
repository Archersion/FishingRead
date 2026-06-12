"""
单实例 IPC：通过 QLocalServer/QLocalSocket 防止多个实例同时运行。
"""

from PyQt5.QtNetwork import QLocalServer, QLocalSocket
from PyQt5.QtCore import QSharedMemory

from fishingread.constants import SINGLE_INSTANCE_SERVER


def try_activate_existing_instance():
    """检查是否已有实例在运行，有则激活其窗口并返回 (True, shared_memory)。"""
    shared_mem = QSharedMemory(SINGLE_INSTANCE_SERVER)
    if not shared_mem.attach():
        return False, shared_mem  # 没有其他实例在运行

    # 尝试连接 IPC 服务器，发送显示信号
    socket = QLocalSocket()
    socket.connectToServer(SINGLE_INSTANCE_SERVER)
    if socket.waitForConnected(1000):
        socket.write(b"show")
        socket.waitForBytesWritten(500)
        socket.disconnectFromServer()
        return True, shared_mem  # 已激活旧实例

    # 服务器未响应，旧实例可能已崩溃，清理并继续
    shared_mem.detach()
    QLocalServer.removeServer(SINGLE_INSTANCE_SERVER)
    return False, shared_mem


class SingleInstanceServer:
    """IPC 服务器，监听重复运行的激活请求。"""

    def __init__(self, activate_callback=None):
        self.server = QLocalServer()
        self.activate_callback = activate_callback
        QLocalServer.removeServer(SINGLE_INSTANCE_SERVER)
        self.server.listen(SINGLE_INSTANCE_SERVER)
        self.server.newConnection.connect(self._on_new_connection)

    def _on_new_connection(self):
        conn = self.server.nextPendingConnection()
        if conn:
            conn.readyRead.connect(lambda: self._handle_message(conn))

    def _handle_message(self, conn):
        data = conn.readAll().data()
        if data == b"show" and self.activate_callback:
            self.activate_callback()
        conn.disconnectFromServer()
