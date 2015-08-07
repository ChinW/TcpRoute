#!/usr/bin/python
# -*- coding: utf-8 -*-
# utf-8 中文编码
import json
import logging
import os
import gevent
from gevent import socket
from gevent.server import StreamServer
import sys
import signal
from LRUCacheDict import LRUCacheDict
import handler
from mysocket import MySocket
import upstream

logging.basicConfig(level=logging.INFO)
basedir = os.path.dirname(os.path.abspath(__file__))


class Server(StreamServer):
    def __init__(self, config):
        listener = ("0.0.0.0", config.get("port", 7070))
        StreamServer.__init__(self, listener, backlog=1024, )

        self.routeCache = LRUCacheDict(500, 10 * 60 * 1000)
        self.upstreuamDict = {}

        for p in config.get("upstream_list", []):
            type = p.get('type', None)
            if type is None:
                logging.error(u'[upstream]未配置代理类型！详细信息:%s' % p)
                continue
            Upstream = upstream.get_upstream(type)
            if Upstream is None:
                logging.error(u'[upstream]不支持 %s 类型代理！' % type)
                continue
            _upstream = Upstream(p)
            self.addUpstream(_upstream)
            logging.info(u'[upstream]已添加 %s 代理。' % _upstream.get_display_name())

    def addUpstream(self, upstream):
        logging.info('addUpstream %s' % upstream.get_display_name())
        self.upstreuamDict[upstream.get_name()] = upstream

    def getUpstream(self, name=None, default=None):
        if name:
            return self.upstreuamDict.get(name, default)
        else:
            return self.upstreuamDict.values()

    def getProxyCache(self, hostname, port, default=None):
        return self.routeCache.get('%s-%s' % (hostname, port), default)

    def __setProxyCache(self, hostname, port, value):
        self.routeCache['%s-%s' % (hostname, port)] = value

    def upProxyPing(self, proxyName, hostname, port, ping, ip):
        proxyDict = self.getProxyCache(hostname, port)
        if proxyDict == None:
            proxyDict = {}
            self.__setProxyCache(hostname, port, proxyDict)

        proxyDict['%s-%s' % (proxyName, ip)] = {
            'tcpping': ping,
            'proxyName': proxyName,
            'hitIp': ip
        }

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
            (_handler, _reset_peek_offset) = Handler.create(mysocket)
            if _handler is not None:
                break

        if _handler is None:
            sock.close(safe=False)
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
            sock.close(safe=False)

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

        server = Server(config)

        gevent.signal(signal.SIGTERM, server.close)
        gevent.signal(signal.SIGINT, server.close)

        logging.info("Server is listening on 0.0.0.0:%d" % config.get('port', 7070))

        try:
            server.serve_forever()
        except socket.error as e:
            if e.errno == 10048:
                logging.error(u'%s 端口已被使用，程序退出。' % config.get('port', 7070))
                server.close()


if __name__ == '__main__':
    Server.start_server()
