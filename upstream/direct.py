#!/usr/bin/python
# -*- coding: utf-8 -*-
# utf-8 中文编码
import logging
import traceback
from gevent import socket as _socket
import gevent
import time
from gevent.event import Event
from gevent.pool import Group
import math
from LRUCacheDict import LRUCacheDict

from base import UpstreamBase, UpstreamConnectError
import dnslib
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

        self.route_cache = LRUCacheDict(500, 10 * 60 * 1000)

        if self.source_ip == '0.0.0.0' and self.source_port==0:
            self.source_address = None
        else:
            self.source_address=(self.source_ip,self.source_port)

        class socket(SocketBase):
            def __init__(self, family=_socket.AF_INET, type=_socket.SOCK_STREAM, proto=0,_sock=None):
                if _sock is None:
                    _sock = socket.upsocket.socket(family=family,type=type,proto=proto)
                    _sock.bind(self.source_address)
                SocketBase.__init__(self,_sock)

        socket.source_address = self.source_address
        socket.upstream = self.upstream
        socket.display_name = self.get_display_name()
        socket.name = self.get_name()

        self.socket = socket

    def get_display_name(self):
        return '[%s]source_ip=%s,source_port=%s' % (self.type,self.source_ip,self.source_port)

    def get_name(self):
        return '%s?source=%s&source_port=%s' % (self.type,self.source_ip,self.source_port)

    def get_route_order_ping(self, hostname, port, default=None):
        route = self.get_route_cache(hostname, port, None)
        if route:
            return sorted(route.values(), key=lambda x: x['tcp_ping'])
        return None

    def get_route_cache(self, hostname, port, default=None):
        return self.route_cache.get('%s-%s' % (hostname, port), default)

    def __set_route_cache(self, hostname, port, value):
        self.route_cache['%s-%s' % (hostname, port)] = value

    def update_route_ping(self,  hostname, port, ping, ip):
        proxyDict = self.get_route_cache(hostname, port)
        if proxyDict == None:
            proxyDict = {}
            self.__set_route_cache(hostname, port, proxyDict)

        proxyDict['%s' % ( ip)] = {
            'tcp_ping': ping,
            'hit_ip': ip
        }

    def _direct_create_connection(self,address,ip, timeout=10):
        # 实际连接
        _sock = self.upstream.create_connection((ip,address[1]),timeout,source_address=self.source_address)
        _sock.setsockopt(_socket.IPPROTO_TCP,_socket.TCP_NODELAY, 1)
        sock = self.socket(_sock=_sock)
        return sock

    def _create_connection(self, aync_task, address,ip, timeout=10):
        # 多线程连接执行部分
        start_time = int(time.time() * 1000)
        try:
            sock = self._direct_create_connection(address,ip, timeout)
        except:
            t = int(time.time() * 1000) - start_time
            info = traceback.format_exc()
            logging.debug(
                u'[upstream]%s 连接 %s(%s):%s 失败。time:%s' % (self.get_display_name(), address[0],ip, address[1], t))
            logging.debug('%s\r\n\r\n' % info)
            return
        t = int(time.time() * 1000) - start_time
        self.update_route_ping(address[0],address[1],t,ip)
        if aync_task.sock:
            sock.close(safe=False)
            logging.debug(
                u'[upstream]%s 连接 %s(%s):%s 未命中。time:%s' % (self.get_display_name(), address[0],ip, address[1], t))
        else:
            aync_task.sock = sock
            aync_task.evt.set()
            logging.debug(
                u'[upstream]%s 连接 %s(%s):%s 命中。time:%s' % (self.get_display_name(), address[0],ip, address[1], t))

    def _create_connection_all_end(self, aync_task):
        u"""在所有链接全部出错时发出事件通知主协程。"""
        aync_task.group.join()
        if aync_task.sock is None:
            aync_task.evt.set()

    def create_connection(self, address, timeout=10):

        ip_list = dnslib.dnsQuery(address[0])

        # 尝试连接缓存
        route_list = self.get_route_order_ping(address[0],address[1],None)
        if route_list:
            try:
                route = route_list[0]
                hit_ip = route['hit_ip']

                if hit_ip in ip_list:
                    cache_timeout = route['tcp_ping']

                    if cache_timeout<1000:
                        cache_timeout = cache_timeout * 2
                    else:
                        cache_timeout = cache_timeout+1000
                    cache_timeout = int(math.ceil(cache_timeout/1000.0))

                    start_time = int(time.time() * 1000)
                    sock = self._direct_create_connection(address,hit_ip, cache_timeout)
                    t = int(time.time() * 1000) - start_time
                    logging.debug(u'[upstream][RouteCache]%s 缓存记录 连接 %s(%s):%s 命中。time:%s'%(self.get_display_name(),address[0],hit_ip,address[1],t))
                    self.update_route_ping(address[0],address[1],t,hit_ip)
                    return sock
                else:
                    logging.debug(u'[upstream][RouteCache]%s 缓存记录 连接 %s(%s):%s IP 不匹配，放弃缓存。'%(self.get_display_name(),address[0],hit_ip,address[1]))
            except:
                t = int(time.time() * 1000) - start_time
                info = traceback.format_exc()
                logging.debug(
                    u'[upstream][RouteCache]%s 缓存记录 连接 %s(%s):%s 失败。time:%s' % (self.get_display_name(), address[0],hit_ip, address[1],t))
                logging.debug('%s\r\n\r\n' % info)

        # 缓存失败，连接全部
        evt = Event()
        group = Group()
        aync_task = DirectAsyncTask(evt, None, group)

        for ip in ip_list:
            group.add(gevent.spawn(self._create_connection,  aync_task, address,ip, timeout))

        # 所有连接失败时发出通知
        gevent.spawn(self._create_connection_all_end, aync_task)

        evt.wait()
        if aync_task.sock:
            return aync_task.sock
        else:
            raise UpstreamConnectError()

class DirectAsyncTask():
    def __init__(self, evt, sock, group):
        self.evt = evt
        self.sock = sock
        self.group = group