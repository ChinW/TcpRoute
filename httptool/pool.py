#!/usr/bin/python
# -*- coding: utf-8 -*-
# utf-8 中文编码
#
from Queue import Empty, LifoQueue, Full
import logging
import socket as _socket
from LRUCacheDict import LRUCacheDict, _lock

try:
    from select import poll, POLLIN
except ImportError:  # `poll` doesn't exist on OSX and other platforms
    poll = False
    try:
        from select import select
    except ImportError:  # `select` doesn't exist on AppEngine.
        select = False


# urllib3 https://github.com/shazow/urllib3/blob/master/urllib3/util/connection.py
def is_connection_dropped(sock):  # Platform-specific
    """
    Returns True if the connection is dropped and should be closed.

    Note: For platforms like AppEngine, this will always return ``False`` to
    let the platform handle connection recycling transparently for us.
    """

    if not poll:
        if not select:  # Platform-specific: AppEngine
            return False

        try:
            return select([sock], [], [], 0.0)[0]
        except _socket.error:
            return True

    # This version is better on platforms that support it.
    p = poll()
    p.register(sock, POLLIN)
    for (fno, ev) in p.poll(0.0):
        if fno == sock.fileno():
            # Either data is buffered (bad), or the connection is dropped.
            return True
    return False


class HttpConn:
    def __init__(self, sock, pool=None, host=None, port=None):
        self.sock = sock
        self.pool = pool
        self.host = host
        self.port = port

    def __enter__(self):
        # TODO: 是否替换掉 sock.close 函数，方便判断是否已关闭连接？
        return self.sock

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.pool is None or exc_type:
            try:
                self.sock.close()
            except:
                pass
        else:
            poll._put_conn(self.host, self.port, self.sock)

        # 继续传播异常
        return False


def _safe_del_connes(d, k, v):
    while True:
        try:
            conn = v.get(False)
        except Empty:
            break
        try:
            conn.close()
        except:
            pass


class HttpPool():
    u"""http 池"""

    def __init__(self, sock_mod=None, max_site=20, max_size_conn=10, expire=60, lock=None):
        if sock_mod is None:
            sock_mod = __import__("socket")
        self.sock_mod = sock_mod

        self.site_dict = LRUCacheDict(max_site, expire, _safe_del_connes)

        self.max_site_conn = max_size_conn

        if lock is None:
            self.lock = _lock()
        elif callable(lock):
            self.lock = lock()
        else:
            raise ValueError('callable(lock)==False')

    def get_conn(self, host, port):
        u"""获得连接

没有连接时自动创建链接。
        """
        with self.lock:
            site_connes = self.site_dict.get(u'%s:%s' % (host, poll), None)
            if site_connes:
                while True:
                    try:
                        conn = site_connes.get(False)
                        if is_connection_dropped(conn):
                            try:
                                conn.close()
                            except:
                                pass
                        else:
                            return conn
                    except Empty:
                        break
        return HttpConn(self.sock_mod.create_connection((host, port)), self, host, port)

    def _put_conn(self, host, port, sock):
        u""" 将连接添加回连接池

会检查连接状态，不正常的连接会被抛弃。

        """
        if hasattr(self.sock_mod, "get_display_name"):
            sock_name = self.sock_mod.get_display_name()
        else:
            sock_name = None
        sock_info = 'sock_mod:%s host:%s port:%s' % (sock_name, host, port)

        if sock:
            if is_connection_dropped(sock):
                logging.debug(u'已关闭连接无法添加回连接池。%s' % sock_info)
                try:
                    sock.close()
                except:
                    pass
            else:
                with self.lock:
                    site_connes = self.site_dict.get(u'%s:%s' % (host, port), None)
                    if site_connes is None:
                        site_connes = LifoQueue(self.max_site_conn)
                    try:
                        site_connes.put(sock)
                        logging.debug(u'添加连接回连接池。 %s' % sock_info)
                    except Full:
                        logging.debug(u'连接池满. %s' % sock_info)
                        try:
                            sock.close()
                        except:
                            pass
                        return
                    self.site_dict[u'%s:%s' % (host, port)] = site_connes

    def __del__(self):
        with self.lock:
            del self.site_dict
