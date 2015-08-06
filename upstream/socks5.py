#!/usr/bin/python
# -*- coding: utf-8 -*-
# utf-8 中文编码
import logging
import traceback
import gevent
from gevent.pool import Group
import time
from gevent.socket import socket
import struct

from base import UpstreamBase

class Socks5Upstream(UpstreamBase):
    u'''socks5'''
    def __init__(self,config):
        super(Socks5Upstream,self).__init__(config)

        self.host = config.get('host',None)
        if self.host is None:
            logging.warn(u'[Handler][socks5] 未指定 host ，使用默认值 127.0.0.1 。详细信息:%s'%(config))
            self.host = '127.0.0.1'

        self.port = config.get('port',None)
        if self.port is None:
            logging.warn(u'[Handler][socks5] 未指定 port ，使用默认值 5000.')
            self.port = 5000

    def get_name(self):
        return '%s-%s:%s'%(self.type,self.host,self.port)

    @staticmethod
    def unpack(s, fmt):
        length = struct.calcsize(fmt)
        data = s.recv(length)
        if len(data) < length:
            raise Exception("SClient.unpack: bad formatted stream")
        return struct.unpack(fmt, data)

    @staticmethod
    def pack(s, fmt, *args):
        data = struct.pack(fmt, *args)
        return s.sendall(data)

    def forward(self,sClient,atyp,hostname,port,timeout=socket._GLOBAL_DEFAULT_TIMEOUT,ip=None):
        u'''阻塞调用，'''
        logging.debug(u'socks5Proxy.forward(atyp=%s,hostname=%s,port=%s,timeout=%s,ip=%s)'%(atyp,hostname,port,timeout,ip))

        self.__forward(sClient,atyp,hostname,port,timeout)

    def __forward(self,sClient,atyp,hostname,port,timeout=socket._GLOBAL_DEFAULT_TIMEOUT):
        startTime = int(time.time()*1000)
        try:
            s = socket.create_connection((self.host,self.port),timeout)
        except:
            #TODO: 处理下连接失败
            info = traceback.format_exc()
            tcpping = int(time.time()*1000)-startTime
            logging.warn(u'[socks5] 远程代理服务器连接失败！ host:%s ,port:%s ,timeout:%s,time:%s'%(self.host,self.port,timeout,tcpping))
            logging.warn('%s\r\n\r\n'%info)

            return

        s.setsockopt(socket.IPPROTO_TCP,socket.TCP_NODELAY, 1)
        s.settimeout(timeout)
        sClient.conn.settimeout(timeout)

        tcpping = int(time.time()*1000)-startTime
        logging.debug(u'[socks5] 远程代理服务器已连接  host:%s ,port:%s ,timeout:%s,time:%s'%(self.host,self.port,timeout,tcpping))

        # 登录
        Socks5Proxy.pack(s,'BBB',0x05,0x01,0x00)

        # 登录回应
        ver,method = Socks5Proxy.unpack(s,'BB')
        tcpping = int(time.time()*1000)-startTime
        if ver != 0x05 or method != 0x00:
            logging.error(u'[socks5] 远程代理服务器登录失败！ host:%s ,port:%s, time:%s'%(self.host,self.port,tcpping))
            s.close()
            return
        logging.debug(u'[socks5] 远程代理服务器登陆成功。 host:%s ,port:%s ,time:%s'%(self.host,self.port,tcpping))

        # 请求连接
        Socks5Proxy.pack(s,'!BBBB',0x05,0x01,0x00,atyp)
        if atyp == 0x01:
            #ipv4
            Socks5Proxy.pack(s,'!IH',struct.unpack('!I',socket.inet_aton(hostname))[0],port)
        elif atyp == 0x03:
            # 域名
            Socks5Proxy.pack(s,'!B%ssH'%len(hostname),len(hostname),hostname,port)
        elif atyp == 0x04:
            # ipv6
            _str = socket.inet_pton(socket.AF_INET6, hostname)
            a, b = struct.unpack('!2Q', _str)
            Socks5Proxy.pack(s,'!2QH',a,b,port)
        else:
            tcpping = int(time.time()*1000)-startTime
            logging.warn(u'[socks5] 远程代理服务器绑定地址类型未知！ atyp:%s ,time:%s'%(atyp,tcpping))
            s.close()
            return

        # 请求回应
        ver,rep,rsv,atyp = Socks5Proxy.unpack(s,'BBBB')
        if ver != 0x05 or rep != 0x00:
            tcpping = int(time.time()*1000)-startTime
            logging.warn(u'[socks5] 远程代理服务器无法连接目标网站！ ver:%s ,rep:%s， time=%s'%(ver,rep,tcpping))
            s.close()
            return

        if atyp == 0x01:
            Socks5Proxy.unpack(s,'!IH')
        elif atyp == 0x03:
            length = Socks5Proxy.unpack(s,'B')
            Socks5Proxy.unpack(s,'%ssH'%length)
        elif atyp == 0x04:
            Socks5Proxy.unpack(s,'!2QH')

        gevent.sleep(0)
        # 直连的话连接建立就可以了
        # 如果是 socks5 代理，时间统计需要包含远端代理服务器连接到远端服务器的时间。
        tcpping = int(time.time()*1000)-startTime
        sClient.server.upProxyPing(self.getName(),hostname,port,tcpping,None)
        if not sClient.connected:
            # 第一个连接上的
            logging.debug(u'[Socks5Proxy] 连接命中 (hostname=%s,atyp=%s,port=%s,timeout=%s,tcpping=%s)'%(hostname,atyp,port,timeout,tcpping))

            sClient.connected=True

            # 为了应付长连接，超时设置的长点。
            s.settimeout(3*60)
            sClient.conn.settimeout(3*60)

            #TODO: 按照socks5协议，这里应该返回服务器绑定的地址及端口
            # http://blog.csdn.net/testcs_dn/article/details/7915505
            sClient.pack('!BBBBIH', 0x05, 0x00, 0x00, 0x01, 0, 0)
            # 第一个连接上的，执行转发
            group = Group()
            group.add(gevent.spawn(self.__forwardData,sClient.conn,s))
            group.add(gevent.spawn(self.__forwardData,s,sClient.conn))
            group.join()
        else:
            # 不是第一个连接上的
            s.close()
            logging.debug(u'[Socks5Proxy] 连接未命中 (hostname=%s,atyp=%s,port=%s,timeout=%s,tcpping=%s)'%(hostname,atyp,port,timeout,tcpping))

    def __forwardData(self,s,d):
        try:
            while True:
                data=s.recv(1024)
                if not data:
                    break
                d.sendall(data)
        except Exception as e :
            if e.errno ==9:
                # 另一个协程关闭了链接。
                pass
            elif e.errno == 10053:
                # 远端关闭了连接
                logging.debug(u'远端关闭了连接。')
                pass
            elif e.errno == 10054:
                # 远端重置了连接
                logging.debug(u'远端重置了连接。')
                pass
            else:
                logging.exception(u'socks5Proxy.__forwardData')
        finally:
            # 这里 和 socks5Handle 会重复关闭
            logging.debug(u'socks5Proxy.__forwardData close()')
            gevent.sleep(5)
            s.close()
            d.close()


    def getName(self):
        u'''代理唯一名称
需要保证唯一性，建议使用 socks5-proxyhost:port 为代理名称。
'''
        return 'socks5-%s:%s'%(self.host,self.port)