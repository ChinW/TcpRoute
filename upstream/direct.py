#!/usr/bin/python
# -*- coding: utf-8 -*-
# utf-8 中文编码
import logging
import traceback
from gevent import socket as _socket
import gevent
import time
from gevent.pool import Group

from base import UpstreamBase
from mysocket import SocketBase


class DirectUpstream(UpstreamBase):
    u""" 直接连接 socket 模块

    使用方式为创建本类实例，然后把实例当作 socket 模块即可。所有的操作都会经过 config 配置的线路。
    """

    def __init__(self,config):
        u""" 初始化直连 socket 环境 """
        UpstreamBase.__init__(self,config=config)

        self.source_ip = config.get('source_ip','0.0.0.0')
        self.source_port = config.get('source_port',0)

        class socket(SocketBase):
            def __init__(self, family=_socket.AF_INET, type=_socket.SOCK_STREAM, proto=0,_sock=None):
                if _sock is None:
                    _sock = socket.upsocket.socket(family=family,type=type,proto=proto)
                    _sock.bind((socket.source_ip,socket.source_port))
                SocketBase.__init__(self,_sock)

        socket.source_ip = self.source_ip
        socket.source_port = self.source_port
        socket.upstream = self.upstream

        self.socket = socket

    def get_display_name(self):
        return '[%s]source_ip=%s,source_port=%s' % (self.type,self.source_ip,self.source_port)

    def get_name(self):
        return '%s?source_ip=%s&source_port=%s' % (self.type,self.source_ip,self.source_port)

    def create_connection(self,address, timeout=10, data_timeout = 5*60):
        # TODO: 这里需要记录下本sock连接远程的耗时。
        # TODO: 需要实现多ip同时连接的功能。
        _sock = self.upstream.create_connection(address,timeout,source_address=(self.source_ip,self.source_port))
        sock = self.socket(_sock=_sock)
        _sock.setsockopt(_socket.IPPROTO_TCP,_socket.TCP_NODELAY, 1)
        _sock.settimeout(data_timeout)
        return sock
