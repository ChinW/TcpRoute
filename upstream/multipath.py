#!/usr/bin/python
# -*- coding: utf-8 -*-
# utf-8 中文编码
import logging
import traceback
from gevent import socket as _socket
import gevent
from gevent.pool import Group
import time
import math
from LRUCacheDict import LRUCacheDict
from mysocket import SocketBase
from gevent.event import Event
import upstream
from upstream.base import UpstreamBase, ConfigError, UpstreamConnectError

__author__ = 'GameXG'


class MultipathUpstream(UpstreamBase):
    u""" 多路径 socket 模块

对于 tcp 连接，同时使用多个线路尝试连接，最终使用最快建立连接的线路。

使用方式为创建本类实例，然后把实例当作 socket 模块即可。所有的操作都会经过 config 配置的线路。

以后也许会弄个当连接多路复用。
"""

    def __init__(self, config):
        u""" 初始化直连 socket 环境 """
        UpstreamBase.__init__(self, config)

        self.route_cache = LRUCacheDict(500, 10 * 60 * 1000)

        self._list = config.get('list', [{'type': 'direct'}])
        self.upstream_dict = {}
        for i in self._list:
            type = i.get('type')
            if not type:
                raise ConfigError(u'[upstream]代理类型不能为空！ ')
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

    def get_route_order_ping(self, hostname, port, default=None):
        route = self.get_route_cache(hostname, port, None)
        if route:
            return sorted(route.values(), key=lambda x: x['tcp_ping'])
        return None

    def get_route_cache(self, hostname, port, default=None):
        return self.route_cache.get('%s-%s' % (hostname, port), default)

    def __set_route_cache(self, hostname, port, value):
        self.route_cache['%s-%s' % (hostname, port)] = value

    def update_route_ping(self, proxyName, hostname, port, ping, ip=None):
        proxyDict = self.get_route_cache(hostname, port)
        if proxyDict == None:
            proxyDict = {}
            self.__set_route_cache(hostname, port, proxyDict)

        proxyDict['%s-%s' % (proxyName, ip)] = {
            'tcp_ping': ping,
            'proxy_name': proxyName,
            'hit_ip': ip
        }

    def _create_connection(self, _upstream, aync_task, address, timeout=10):
        # 实际连接部分
        start_time = int(time.time() * 1000)
        try:
            sock = _upstream.create_connection(address, timeout)
        except:
            t = int(time.time() * 1000) - start_time
            info = traceback.format_exc()
            logging.debug(
                u'[upstream]%s 连接 %s:%s 失败。time:%s' % (_upstream.get_display_name(), address[0], address[1], t))
            logging.debug('%s\r\n\r\n' % info)
            return
        t = int(time.time() * 1000) - start_time
        self.update_route_ping(_upstream.get_name(),address[0],address[1],t)
        if aync_task.sock:
            sock.close(safe=False)
            logging.debug(
                u'[upstream]%s 连接 %s:%s 未命中。time:%s' % (_upstream.get_display_name(), address[0], address[1], t))
        else:
            aync_task.sock = sock
            aync_task.evt.set()
            logging.debug(
                u'[upstream]%s 连接 %s:%s 命中。time:%s' % (_upstream.get_display_name(), address[0], address[1], t))

    def _create_connection_all_end(self, aync_task):
        u"""在所有链接全部出错时发出事件通知主协程。"""
        aync_task.group.join()
        if aync_task.sock is None:
            aync_task.evt.set()

    def create_connection(self, address, timeout=10):

        # 尝试连接缓存
        route_list = self.get_route_order_ping(address[0],address[1],None)
        if route_list:
            try:
                route = route_list[0]

                cache_timeout = route['tcp_ping']

                if cache_timeout<1000:
                    cache_timeout = cache_timeout * 2
                else:
                    cache_timeout = cache_timeout+1000
                cache_timeout = int(math.ceil(cache_timeout/1000.0))

                _upstream = self.upstream_dict.get(route['proxy_name'])
                start_time = int(time.time() * 1000)
                sock = _upstream.create_connection(address, cache_timeout)
                t = int(time.time() * 1000) - start_time
                logging.debug(u'[upstream][RouteCache]%s 缓存记录 连接 %s:%s 命中。time:%s'%(_upstream.get_display_name(),address[0],address[1],t))
                self.update_route_ping(_upstream.get_name(),address[0],address[1],t)
                return sock
            except:
                t = int(time.time() * 1000) - start_time
                info = traceback.format_exc()
                logging.debug(
                    u'[upstream][RouteCache]%s 缓存记录 连接 %s:%s 失败。time:%s' % (_upstream.get_display_name(), address[0], address[1],t))
                logging.debug('%s\r\n\r\n' % info)

        # 缓存失败，连接全部
        evt = Event()
        group = Group()
        aync_task = MultipathAsyncTask(evt, None, group)

        for _upstream in self.upstream_dict.values():
            group.add(gevent.spawn(self._create_connection, _upstream, aync_task, address, timeout))

        # 所有连接失败时发出通知
        gevent.spawn(self._create_connection_all_end, aync_task)

        evt.wait()
        if aync_task.sock:
            return aync_task.sock
        else:
            raise UpstreamConnectError()

    def get_display_name(self):
        return '[%s]' % (self.type)

    def get_name(self):
        return '%s' % (self.type)


class MultipathAsyncTask():
    def __init__(self, evt, sock, group):
        self.evt = evt
        self.sock = sock
        self.group = group
