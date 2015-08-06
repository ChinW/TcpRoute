#!/usr/bin/python
# -*- coding: utf-8 -*-
# utf-8 中文编码
import logging
import traceback
from gevent import socket
import gevent
import time
from gevent.pool import Group

from base import UpstreamBase


class DirectUpstream(UpstreamBase):

    u'''直接连接'''
    def forward(self,sClient,atyp,hostname,port,timeout=socket._GLOBAL_DEFAULT_TIMEOUT,ip=None):
        u'''阻塞调用，'''
        logging.debug(u'DirectProxy.forward(atyp=%s,hostname=%s,port=%s,timeout=%s,ip=%s)'%(atyp,hostname,port,timeout,ip))
        ipList = dnsQuery(hostname)
        logging.debug(u'[DNS]resolution name:%s\r\n'%hostname+'\r\n'.join([('IP:%s'%ip) for ip in ipList]))
        group = Group()
        if ip in ipList:
            group.add(gevent.spawn(self.__forward,sClient,(ip,port),hostname,timeout))
            logging.debug(u'cache ip hit Domain=%s ip=%s '%(hostname,ip))
        else:
            for ip in ipList:
                # 启动多个代理进行转发尝试
                # 最先成功的会执行转发，之后成功的会自动退出。
                group.add(gevent.spawn(self.__forward,sClient,(ip,port),hostname,timeout))
        group.join()

    def __forward(self,sClient,addr,hostname,timeout=socket._GLOBAL_DEFAULT_TIMEOUT):
        ip = addr[0]
        port = addr[1]
        logging.debug(u'DirectProxy.__forward(hostname=%s,ip=%s,port=%s,timeout=%s)'%(hostname,ip,port,timeout))
        startTime = int(time.time()*1000)
        try:
            s = socket.create_connection(addr,timeout)
            s.setsockopt(socket.IPPROTO_TCP,socket.TCP_NODELAY, 1)
        except:
            #TODO: 处理下连接失败
            info = traceback.format_exc()
            logging.debug(u'[DirectProxy]直连失败。 hostname:%s ,ip:%s ,port:%s ,timeout:%s'%(hostname,ip,port,timeout))
            logging.debug('%s\r\n\r\n'%info)
            return
        # 直连的话直接链接到服务器就可以，
        # 如果是 socks5 代理，时间统计需要包含远端代理服务器连接到远端服务器的时间。
        tcpping = int(time.time()*1000)-startTime
        sClient.server.upProxyPing(self.getName(),hostname,addr[1],tcpping,ip)
        if not sClient.connected:
            # 第一个连接上的
            logging.debug(u'[DirectProxy] Connection hit (hostname=%s,ip=%s,port=%s,timeout=%s, tcpping=%s)'%(hostname,ip,port,timeout,tcpping))
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
            logging.debug(u'[DirectProxy] Connection miss (hostname=%s,ip=%s,port=%s,timeout=%s, tcpping=%s)'%(hostname,ip,port,timeout,tcpping))


    def __forwardData(self,s,d):
        try:
            while True:
                data=s.recv(1024)
                if not data:
                    break
                d.sendall(data)
        except Exception as e :
            if e.errno == 9:
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
                logging.exception(u'DirectProxy.__forwardData')
        finally:
            # 这里 和 socks5 Handle 会重复关闭
            logging.debug(u'DirectProxy.__forwardData  finally')
            gevent.sleep(5)
            s.close()
            d.close()


    def getName(self):
        u'''代理唯一名称
需要保证唯一性，建议使用 socks5-proxyhost:port 为代理名称。
'''
        return 'direct'

