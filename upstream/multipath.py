#!/usr/bin/python
# -*- coding: utf-8 -*-
# utf-8 中文编码
from gevent import socket as _socket
import gevent
from gevent.pool import Group
from mysocket import SocketBase
from gevent.event import AsyncResult
import upstream
from upstream.base import UpstreamBase, ConfigError, UpstreamConnectError

__author__ = 'GameXG'


class MultipathUpstream(UpstreamBase):
    u""" 多路径 socket 模块

对于 tcp 连接，同时使用多个线路尝试连接，最终使用最快建立连接的线路。

使用方式为创建本类实例，然后把实例当作 socket 模块即可。所有的操作都会经过 config 配置的线路。
"""

    def __init__(self, config):
        u""" 初始化直连 socket 环境 """
        UpstreamBase.__init__(self, config)

        self._list = config.get('list', [{'type': 'direct'}])
        self.upstream_dict = {}
        for i in self._list:
            type = i.get('type')
            if not type:
                return ConfigError(u'[upstream]代理类型不能为空！ ')
            Upstream = upstream.get_upstream(type)
            u = Upstream(i)
            self.upstream_dict[u.get_name()] = u
    u'''
        class socket(SocketBase):
            def __init__(self, family=_socket.AF_INET, type=_socket.SOCK_STREAM, proto=0, _sock=None):
                if _sock is None:
                    _sock = socket.upsocket.socket(family=family, type=type, proto=proto)
                    _sock.bind((socket.source_ip, socket.source_port))
                SocketBase.__init__(self, _sock)

        socket.upstream = self.upstream

        self.socket = socket'''

    def _create_connection(self,ares,upstream, address, timeout=10, data_timeout=5 * 60):
        # 实际连接部分
        sock = upstream.create_connection(address,timeout,data_timeout)
        # TODO: 更新 tcpping 。
        ares.set(sock)

    def create_connection(self, address, timeout=10, data_timeout=5 * 60):
        ares = AsyncResult()
        group = Group()
        for i in self.upstream_dict.values():
            group.add(gevent.spawn(self._create_connection,ares,i,address,timeout,data_timeout))
        # TODO 多线路失败没有处理啊...
        sock = ares.get(timeout=timeout*2)
        if sock:
            return sock
        else:
            raise UpstreamConnectError()


