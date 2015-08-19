#!/usr/bin/python
# -*- coding: utf-8 -*-
# utf-8 中文编码

from gevent import socket as _socket
import re
import gevent
from httptool import HttpPool
from gevent.lock import BoundedSemaphore


class UpstreamBase(object):
    u""" 特定线路 socket 模块

    使用方式为创建本类实例，然后把实例当作 socket 模块即可。所有的操作都会经过 config 配置的线路。"""

    # 封装好的 socket 类
    socket = None

    def __init__(self, config):
        self.type = config.get('type', None)
        self.config = config

        import upstream as upstream_mod

        upconfig = config.get('upstream', None)

        if upconfig:
            uptype = upconfig.get("type", None)
            if uptype is None:
                raise ConfigError(u'[配置错误] upstream 未配置 type ！')

            Upstream = upstream_mod.get_upstream(uptype)
            if Upstream is None:
                raise ConfigError(u'[配置错误] upstream type %s 不被支持！' % uptype)

            self.upstream = Upstream(upconfig)
            pass
        else:
            if self.type != 'direct':
                self.upstream = upstream_mod.get_upstream('direct')({'type':'direct'})
            else:
                self.upstream = _socket

        self.http_pool = HttpPool(self,lock=BoundedSemaphore)

    def create_connection(self,address, timeout=5):
        if timeout == _socket._GLOBAL_DEFAULT_TIMEOUT:
            timeout = 10
        raise NotImplementedError()

    def get_display_name(self):
        return self.get_name()

    def get_name(self):
        return '%s-host:port' % (self.type)

    # http 请求处理
    # http 代理可以重写本方法
    # socks 类代理不需要处理。
    def get_http_conn(self,host,port):
        u"""  获得http with 连接 """
        return self.http_pool.get_conn(host,port)




class ConfigError(ValueError):
    def __init__(self, *args, **kwargs):
        ValueError.__init__(self, *args, **kwargs)

class UpstreamError(_socket.error):
    def __init__(self, *args, **kwargs):
        _socket.error.__init__(self, *args, **kwargs)

class UpstreamLoginError(UpstreamError):
    def __init__(self, *args, **kwargs):
        _socket.error.__init__(self, *args, **kwargs)

class UpstreamProtocolError(UpstreamError):
    def __init__(self, *args, **kwargs):
        _socket.error.__init__(self, *args, **kwargs)

class UpstreamConnectError(UpstreamError):
    def __init__(self, *args, **kwargs):
        _socket.error.__init__(self, *args, **kwargs)



