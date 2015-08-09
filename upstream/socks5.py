#!/usr/bin/python
# -*- coding: utf-8 -*-
# utf-8 中文编码
import logging
import traceback
import gevent
from gevent.pool import Group
import time
from gevent import socket as _socket
import struct

from base import UpstreamBase, ConfigError, UpstreamLoginError, UpstreamProtocolError
import dnslib
from mysocket import SocketBase


class Socks5Upstream(UpstreamBase):
    u"""socks5

通过配置生成实例，实例内含 socket 类
"""
    def __init__(self, config):
        UpstreamBase.__init__(self, config)

        self.socks5_hostname = config.get('host')
        self.socks5_port = config.get('port')

        if self.socks5_hostname is None or self.socks5_port is None:
            ms = u'[配置错误] host、port 不能为空！ upstream-type:%s' % self.type
            raise ConfigError(ms)

        class socket(SocketBase):
            # TODO: 停掉一些不支持方法。
            def __init__(self, family=_socket.AF_INET, type=_socket.SOCK_STREAM, proto=0, _sock=None):
                if _sock is None:
                    _sock = socket.upstream.socket(family=family, type=type, proto=proto)
                SocketBase.__init__(self, _sock)

        socket.socks5_hostname = self.socks5_hostname
        socket.socks5_port = self.socks5_port
        socket.upstream = self.upstream

        self.socket = socket

    def create_connection(self, address, timeout=5, data_timeout=5 * 60):
        startTime = int(time.time() * 1000)
        hostname = address[0]
        port = address[1]

        try:
            _sock = self.upstream.create_connection((self.socks5_hostname, self.socks5_port), timeout,
                                                    )
        except:
            info = traceback.format_exc()
            tcpping = int(time.time() * 1000) - startTime
            logging.warn(u'[socks5] 远程代理服务器连接失败！ socks5_hostname:%s ,socks5_port:%s ,timeout:%s,time:%s' % (
                self.socks5_hostname, self.socks5_port, timeout, tcpping))
            logging.warn('%s\r\n\r\n' % info)
            raise

        _sock.setsockopt(_socket.IPPROTO_TCP, _socket.TCP_NODELAY, 1)
        _sock.settimeout(timeout * 2)

        tcpping = int(time.time() * 1000) - startTime
        logging.debug(u'[socks5] 远程代理服务器已连接  socks5_hostname:%s ,socks5_port:%s ,timeout:%s,time:%s' % (
            self.socks5_hostname, self.socks5_port, timeout, tcpping))

        # 登录
        _sock.pack('BBB', 0x05, 0x01, 0x00)

        # 登录回应
        ver, method = _sock.unpack( 'BB')
        tcpping = int(time.time() * 1000) - startTime
        if ver != 0x05 or method != 0x00:
            _sock.close(safe=False)
            ms = u'[socks5] 远程代理服务器登录失败！ host:%s ,port:%s, time:%s' % (self.socks5_hostname, self.socks5_port, tcpping)
            raise UpstreamLoginError(ms)
        logging.debug(
            u'[socks5] 远程代理服务器登陆成功。 host:%s ,port:%s ,time:%s' % (self.socks5_hostname, self.socks5_port, tcpping))

        # 请求连接
        atyp = dnslib.get_addr_type(hostname)
        if atyp == 0x01:
            # ipv4
            _sock.pack('!BBBBIH', 0x05, 0x01, 0x00, atyp, struct.unpack('!I', _socket.inet_aton(hostname))[0], port)
        elif atyp == 0x03:
            # 域名
            _sock.pack('!BBBBB%ssH' % len(hostname), 0x05, 0x01, 0x00, atyp, len(hostname), hostname, port)
        elif atyp == 0x04:
            # ipv6
            _str = _socket.inet_pton(_socket.AF_INET6, hostname)
            a, b = struct.unpack('!2Q', _str)
            _sock.pack('!BBBB2QH', 0x05, 0x01, 0x00, atyp, a, b, port)
        else:
            tcpping = int(time.time() * 1000) - startTime
            ms = u'[socks5] 地址类型未知！ atyp:%s ,time:%s' % (atyp, tcpping)
            _sock.close(safe=False)
            assert False, ms

        # 请求回应
        ver, rep, rsv, atyp = _sock.unpack('BBBB')
        if ver != 0x05:
            _sock.close(safe=False)
            raise UpstreamProtocolError(u'未知的服务器协议版本！')
        if rep != 0x00:
            tcpping = int(time.time() * 1000) - startTime
            ms = u'[socks5] 远程代理服务器无法连接目标网站！ ver:%s ,rep:%s， time=%s' % (ver, rep, tcpping)
            _sock.close(safe=False)
            raise _socket.error(10060,
                                (u'[Socks5] 代理服务器无法连接到目的主机。socks5_host = %s, '
                                 u'socks5_port = %s ,host = %s ,port = %s ,rep = %s') %
                                (self.socks5_hostname, self.socks5_port, hostname, port, rep))

        if atyp == 0x01:
            _sock.unpack('!IH')
        elif atyp == 0x03:
            length = _sock.unpack('B')
            _sock.unpack('%ssH' % length)
        elif atyp == 0x04:
            _sock.unpack('!2QH')

        tcpping = int(time.time() * 1000) - startTime
        # TODO: 这里需要记录下本sock连接远程的耗时。
        _sock.settimeout(data_timeout)
        return self.socket(_sock=_sock)

    def get_name(self):
        return '%s-%s:%s' % (self.type, self.socks5_hostname, self.socks5_port)
