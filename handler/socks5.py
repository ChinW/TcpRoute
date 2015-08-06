#!/usr/bin/python
# -*- coding: utf-8 -*-
# utf-8 中文编码
import logging
from gevent import socket
import struct
import gevent
import math
from handler.base import HandlerBase

# 悲剧，windows python 3.4 才支持 ipv6 的 inet_ntop
# https://bugs.python.org/issue7171
if not hasattr(socket, 'inet_ntop'):
    import win_inet_pton
    socket.inet_ntop = win_inet_pton.inet_ntop
if not hasattr(socket, 'inet_pton'):
    import win_inet_pton
    socket.inet_pton = win_inet_pton.inet_pton


class Socks5Handler(HandlerBase):
    u'''socks5 、socks4 双协议支持'''
    rbufsize = -1
    wbufsize = 0

    def __init__(self,sock):
        super(Socks5Handler,self).__init__(sock)

    def handler(self):
        (ver,) =self.sock.unpack('B')
        self.ver = ver
        if ver == 0x04:
            self.socks4Handle()
        elif ver == 0x05:
            self.socks5Handle()
        else:
            logging.error(u'[Socks5Handler]异常的协议类型， ver = %s'%(ver))
            self.sock.close()
            return

    def socks4Handle(self):
        pass

    def socks5Handle(self):
        # 鉴定
        (nmethods,) = self.sock.unpack('B')
        if nmethods>0:
            (methods,) = self.sock.unpack('B'*nmethods)
            #TODO: 未检查客户端支持的鉴定方式
        self.sock.pack('BB',0x05,0x00)
        logging.debug(u'[Socks5Handler]client login')

        # 接收代理请求
        ver,cmd,rsv,atyp = self.sock.unpack('BBBB')

        if ver != 0x05 or cmd != 0x01:
            logging.warn(u'[Socks5Handler]收到未知类型的请求，关闭连接。 ver=%s ,cmd=%s'%(ver,cmd))
            self.sock.pack('BBBBIH',0x05, 0x07, 0x00, 0x01, 0, 0)
            self.sock.shutdown(socket.SHUT_WR)
            self.sock.close()
            return

        if atyp == 0x01:
            # ipv4
            host,port = self.sock.unpack('!IH')
            hostname = socket.inet_ntoa(struct.pack('!I', host))
        elif atyp == 0x03:
            # 域名
            length = self.sock.unpack('B')[0]
            hostname, port = self.sock.unpack("!%dsH" % length)
        elif atyp == 0x04:
            # ipv6
            ipv61 ,ipv62,port = self.sock.unpack('!2QH')
            hostname = socket.inet_ntop(socket.AF_INET6, struct.pack('!2Q', ipv61, ipv62))
        else:
            logging.warn(u'[SClient]收到未知的目的地址类型，关闭连接。 atyp=%s '%(atyp))
            self.sock.pack('!BBBBIH', 0x05, 0x07, 0x00, 0x01, 0, 0)
            self.sock.shutdown(socket.SHUT_WR)
            self.sock.close()
            return
        logging.debug(u'[SClient] host:%s   prot:%s'%(hostname,port))

        # 对外发起请求

        proxyDict = self.server.getProxyCache(hostname,port,None)
        if proxyDict:
            proxyList = sorted(proxyDict.values(),key=lambda x:x['tcpping'])
            proxyName = proxyList[0]['proxyName']
            hitIp = proxyList[0]['hitIp']
            tcpping = proxyList[0]['tcpping']
            _tcpping =tcpping
            if _tcpping<=500:
                _tcpping=1000
            elif _tcpping<=3000:
                _tcpping+=1000
            else:
                _tcpping += _tcpping/2.0
            timeout = int(math.ceil(_tcpping/1000.0))

            proxy = self.server.getProxy(proxyName)
            if proxy:
                logging.debug(u'[ProxyCache] hit host:%s ,prot:%s ,proxy:%s ,ip:%s,tcpping:%s,timeout:%s'%(hostname,port,proxy.getName(),hitIp,tcpping,timeout))
                proxy.forward(self,atyp,hostname,port,timeout,hitIp)
        if not self.connected:
            # 不管是没有缓存记录还是没连接上，都使用全部链接做一次测试。
            logging.debug(u'[All Proxy]  host:%s ,prot:%s '%(hostname,port))
            group = Group()
            for proxy in self.server.getProxy():
                # 启动多个代理进行转发尝试
                # 最先成功的会执行转发，之后成功的会自动退出。
                group.add(gevent.spawn(proxy.forward,self,atyp,hostname,port,10))
            group.join()
        if not self.connected:
            logging.info(u'[SClient]无法连接到目的主机，关闭连接。 hostname=%s ，port=%s '%(hostname,port))
            self.sock.pack('!BBBBIH', 0x05, 0x03, 0x00, 0x01, 0, port)
        self.sock.shutdown(socket.SHUT_WR)
        self.sock.close()


    @staticmethod
    def create(sock):
        u'''创建handler
如果是本类可处理的协议返回本类实例，否则返回None
'''
        (ver,) = sock.unpack('B')
        if ver in (0x04,0x04):
            logging.debug(u'[Socks5Handler]收到 socks%s 协议头。' % ver)
            return (Socks5Handler(sock),True)
        return (None,True)







