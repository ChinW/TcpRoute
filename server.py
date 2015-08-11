#!/usr/bin/python
# -*- coding: utf-8 -*-
# utf-8 中文编码
import json
import logging
import os
import sys
import signal

try:
    import gevent
    from gevent import socket as _socket
    from gevent.server import StreamServer
    from gevent.pool import Group
    from gevent.threadpool import ThreadPool
except:
    print >>sys.stderr, "please install gevent first!"
    sys.exit(1)

import dnslib
import handler
from mysocket import MySocket
import upstream
from LRUCacheDict import LRUCacheDict

# 悲剧，windows python 3.4 才支持 ipv6 的 inet_ntop
# https://bugs.python.org/issue7171
from upstream.base import ConfigError

if not hasattr(_socket, 'inet_ntop'):
    import win_inet_pton

    _socket.inet_ntop = win_inet_pton.inet_ntop
if not hasattr(_socket, 'inet_pton'):
    import win_inet_pton

    _socket.inet_pton = win_inet_pton.inet_pton

logging.basicConfig(level=logging.INFO)
basedir = os.path.dirname(os.path.abspath(__file__))


class Server(StreamServer):
    def __init__(self, config):
        self.config = config
        self.upstream = None

        listener = ("0.0.0.0", config.get("port", 7070))
        StreamServer.__init__(self, listener, backlog=1024, )

        config_upstream = config.get("upstream", {'type': 'direct'})
        type = config_upstream.get('type', None)
        if type is None:
            raise ConfigError(u'[upstream]未配置代理类型！详细信息:%s' % config_upstream)
        Upstream = upstream.get_upstream(type)
        if Upstream is None:
            raise ConfigError(u'[upstream]不支持 %s 类型代理！' % type)

        self.upstream = Upstream(config_upstream)

    def addUpstream(self, upstream):
        logging.info('addUpstream %s' % upstream.get_display_name())
        self.upstreuamDict[upstream.get_name()] = upstream

    def getUpstream(self, name=None, default=None):
        if name:
            return self.upstreuamDict.get(name, default)
        else:
            return self.upstreuamDict.values()

    def handle(self, sock, addr):
        logging.debug(u'connection from %s:%s' % addr)

        # 调用各个 handler 尝试生成 client
        #  检查结果，如果生成了就表示本次客户端请求的是这个协议。
        #      剩下的就交由这个协议处理。

        _handler = None
        _reset_peek_offset = False
        mysocket = MySocket(sock)

        for Handler in handler.get_handler():
            mysocket.reset_peek_offset()
            (_handler, _reset_peek_offset) = Handler.create(mysocket, self)
            if _handler is not None:
                break

        if _handler is None:
            mysocket.close(safe=False)
            logging.warn(u'[Handler]收到未识别的协议，关闭连接。')
            return

        try:
            if _reset_peek_offset:
                mysocket.reset_peek_offset()

            mysocket.set_peek(False)

            # handler 有可能是异步调用
            _handler.handler()
        except:
            logging.exception(u'client.handle()')
            mysocket.close(safe=False)

    def close(self):
        logging.info('exit')
        sys.exit(0)

    @staticmethod
    def start_server():

        try:
            with open(os.path.join(basedir, "config.json"), 'rb') as f:
                config = json.load(f, encoding="utf-8")
        except:
            logging.exception(u'[config]配置错误！。')
            return

        logLevel = config.get('logLevel', "INFO")
        logLevel = logging.getLevelName(logLevel.strip().upper())

        if isinstance(logLevel, (str, unicode)):
            logLevel = logging.INFO
            logging.warn(u'错误的日志级别 %s ，重置为 INFO。' % config.get('logLevel', ''))

        logging.getLogger().setLevel(logLevel)

        try:
            dnslib.nameservers = config['nameservers']
            dnslib.nameservers_backup = config['nameservers_backup']

            if dnslib.nameservers != 'system' and isinstance(dnslib.nameservers, (str, unicode)):
                dnslib.nameservers = [dnslib.nameservers, ]

            if dnslib.nameservers_backup != 'system' and isinstance(dnslib.nameservers_backup, (str, unicode)):
                dnslib.nameservers_backup = [dnslib.nameservers_backup, ]

        except:
            logging.exception(u'[DNS]DNS服务器配置错误！')

        server = Server(config)

        gevent.signal(signal.SIGTERM, server.close)
        gevent.signal(signal.SIGINT, server.close)

        gevent.spawn(dnslib.dnsQueryLoop)

        logging.info("Server is listening on 0.0.0.0:%d" % config.get('port', 7070))

        try:
            server.serve_forever()
        except _socket.error as e:
            if e.errno == 10048:
                logging.error(u'%s 端口已被使用，程序退出。' % config.get('port', 7070))
                server.close()


if __name__ == '__main__':
    Server.start_server()
