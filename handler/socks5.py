#!/usr/bin/python
# -*- coding: utf-8 -*-
# utf-8 中文编码
import logging
from gevent import socket as _socket
import struct
import gevent
import math
from gevent.pool import Group
from handler.base import HandlerBase

# 悲剧，windows python 3.4 才支持 ipv6 的 inet_ntop
# https://bugs.python.org/issue7171
if not hasattr(_socket, 'inet_ntop'):
    import win_inet_pton

    _socket.inet_ntop = win_inet_pton.inet_ntop
if not hasattr(_socket, 'inet_pton'):
    import win_inet_pton

    _socket.inet_pton = win_inet_pton.inet_pton




class Socks5Handler(HandlerBase):
    u'''socks5 、socks4 双协议支持'''

    def __init__(self, sock,server):
        HandlerBase.__init__(self,sock,server)

    def handler(self):
        (ver,) = self.sock.unpack('B')
        self.ver = ver
        if ver == 0x04:
            self.socks4Handle()
        elif ver == 0x05:
            self.socks5Handle()
        else:
            logging.error(u'[Socks5Handler]异常的协议类型， ver = %s' % (ver))
            self.sock.close()
            return

    def socks4Handle(self):
        cd,port,dstip = self.sock.unpack('!BHI')

        if cd != 1:
            # 1 == 连接， 2 == 绑定
            self.sock.pack('!BBHI',0,91,port,dstip)
            self.sock.close()

        userid = self.sock.readline(end='\0')[:-1]

        hostname = _socket.inet_ntoa(struct.pack('!I', dstip))

        if hostname.startswith('0.0.0.'):
            # SOCKS4a 支持 ，chrome 不支持 socks4a 扩展。
            hostname = self.sock.readline(end='\0')[:-1]

        # 对外发起请求
        try:
            remote_sock = self.server.upstream.create_connection((hostname,port),)
        except:
            logging.exception(u'所有线路连接 tcp host:%s port:%s 失败。'%(hostname,port))
            # 按照socks4协议，这里返回和请求相同的ip和端口
            # https://zh.wikipedia.org/wiki/SOCKS
            self.sock.pack('!BBHI',0,91,port,dstip)
            self.sock.close()
            return

        # 按照socks4协议，这里返回和请求相同的ip和端口
        # https://zh.wikipedia.org/wiki/SOCKS
        self.sock.pack('!BBHI',0,90,port,dstip)

        self.forward(self.sock,remote_sock,5*60)



    def socks5Handle(self):
        # 鉴定
        (nmethods,) = self.sock.unpack('B')
        if nmethods > 0:
            (methods,) = self.sock.unpack('B' * nmethods)
            # TODO: 未检查客户端支持的鉴定方式
        self.sock.pack('BB', 0x05, 0x00)
        logging.debug(u'[Socks5Handler]client login')

        # 接收代理请求
        ver, cmd, rsv, atyp = self.sock.unpack('BBBB')

        if ver != 0x05 or cmd != 0x01:
            logging.warn(u'[Socks5Handler]收到未知类型的请求，关闭连接。 ver=%s ,cmd=%s' % (ver, cmd))
            self.sock.pack('BBBBIH', 0x05, 0x07, 0x00, 0x01, 0, 0)
            self.sock.close()
            return

        if atyp == 0x01:
            # ipv4
            host, port = self.sock.unpack('!IH')
            hostname = _socket.inet_ntoa(struct.pack('!I', host))
        elif atyp == 0x03:
            # 域名
            length = self.sock.unpack('B')[0]
            hostname, port = self.sock.unpack("!%dsH" % length)
        elif atyp == 0x04:
            # ipv6
            ipv61, ipv62, port = self.sock.unpack('!2QH')
            hostname = _socket.inet_ntop(_socket.AF_INET6, struct.pack('!2Q', ipv61, ipv62))
        else:
            logging.warn(u'[SClient]收到未知的目的地址类型，关闭连接。 atyp=%s ' % (atyp))
            self.sock.pack('!BBBBIH', 0x05, 0x07, 0x00, 0x01, 0, 0)
            self.sock.close()
            return
        logging.debug(u'[SClient] host:%s   prot:%s' % (hostname, port))

        # 对外发起请求
        try:
            remote_sock = self.server.upstream.create_connection((hostname,port),)
        except:
            logging.exception(u'所有线路连接 tcp host:%s port:%s 失败。'%(hostname,port))
            # TODO: 按照socks5协议，这里应该返回服务器绑定的地址及端口
            # http://blog.csdn.net/testcs_dn/article/details/7915505
            self.sock.pack('!BBBBIH', 0x05, 0x03, 0x00, 0x01, 0, 0)
            self.sock.close()
            return

        # TODO: 按照socks5协议，这里应该返回服务器绑定的地址及端口
        # http://blog.csdn.net/testcs_dn/article/details/7915505
        self.sock.pack('!BBBBIH', 0x05, 0x00, 0x00, 0x01, 0, 0)

        self.forward(self.sock,remote_sock,5*60)


    @staticmethod
    def create(sock,server):
        u'''创建handler
如果是本类可处理的协议返回本类实例，否则返回None
'''
        (ver,) = sock.unpack('B')
        if ver in (0x04, 0x05):
            logging.debug(u'[Socks5Handler]收到 socks%s 协议头。' % ver)
            return (Socks5Handler(sock,server), True)
        return (None, True)
