#!/usr/bin/python
# -*- coding: utf-8 -*-
# utf-8 中文编码
import logging
import traceback
from gevent import socket as _socket
import gevent
from gevent.pool import Group
import time
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

    def _create_connection(self,_upstream,aync_task, address, timeout=10, data_timeout=5 * 60):
        # 实际连接部分
        start_time = int(time.time()*1000)
        try:
            sock = _upstream.create_connection(address,timeout,data_timeout)
        except:
            t = int(time.time()*1000) - start_time
            info = traceback.format_exc()
            logging.debug(u'[upstream]%s 连接 %s:%s 失败。time:%s'%(_upstream.get_display_name(),address[0],address[1],t))
            logging.debug('%s\r\n\r\n'%info)
            return
        # TODO: 更新 tcpping 。
        t = int(time.time()*1000) - start_time
        if aync_task.sock:
            sock.close(safe=False)
            logging.debug(u'[upstream]%s 连接 %s:%s 未命中。time:%s'%(_upstream.get_display_name(),address[0],address[1],t))
        else:
            aync_task.sock = sock
            aync_task.evt.set()
            logging.debug(u'[upstream]%s 连接 %s:%s 命中。time:%s'%(_upstream.get_display_name(),address[0],address[1],t))

    def _create_connection_all_end(self,aync_task):
        u"""在所有链接全部出错时发出事件通知主协程。"""
        aync_task.group.join()
        if aync_task.sock is None:
            aync_task.evt.set()

    def create_connection(self, address, timeout=10, data_timeout=5 * 60):
        evt = Event()
        group = Group()
        aync_task = MultipathAsyncTask(evt,None,group)

        for _upstream in self.upstream_dict.values():
            group.add(gevent.spawn(self._create_connection,_upstream,aync_task,address,timeout,data_timeout))

        # 所有连接失败时发出通知
        gevent.spawn(self._create_connection_all_end,aync_task)

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
    def __init__(self,evt,sock,group):
        self.evt =evt
        self.sock = sock
        self.group = group