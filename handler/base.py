#!/usr/bin/python
# -*- coding: utf-8 -*-
# utf-8 中文编码

import logging
import gevent
from gevent import socket as _socket
from gevent.pool import Group
import time


class HandlerBase(object):
    def __init__(self,sock,server):
        self.sock = sock
        self.server = server

    def handler(self):
        pass

    @staticmethod
    def create(sock,server):
        u'''创建handler

返回值
    (None,True)
    None:
        如果是本类可处理的协议返回本类实例，否则返回None。
    True:
        是否需要复位流 seek
        当前一个变量返回 None 时不考虑本变量的值，会直接会退。
注意：
    小心读不到足够的数据可能引发阻塞！！！
    可以随意读取 sock 的内容，返回 None 时已读取的内容会被透明的会退，不影响下一个 Handler 。
    返回实例时会根据第二个变量的值决定是否进行回退，True进行回退。
    但是在未确定是支持的协议前不能写数据，否则会影响其他的 Handler 探测协议！！！
'''
        return (None,True)

    def close(self):
        self.sock.close()

    def forward(self,sock,remote_sock,data_timeout=5*60):
        u"""在两个套接字之间转发数据(阻塞调用)

在转发失败时自动关闭连接。在双向都出现超时的情况下会关闭连接。

未专门处理 shutdown ，单方向 shutdown 时会关闭双向链接。

"""
        try:
            o = {
                # 最后一次转发数据的时间 = int(time()*1000)
                'forward_data_time':int(time.time()*1000),
            }
            sock.settimeout(data_timeout)
            remote_sock.settimeout(data_timeout)

            group = Group()
            group.add(gevent.spawn(self.__forwardData,sock,remote_sock,o,data_timeout))
            group.add(gevent.spawn(self.__forwardData,remote_sock,sock,o,data_timeout))
            group.join()
        finally:
            sock.close()
            remote_sock.close()

    def __forwardData(self,s,d,o,data_timeout=5*60):
        # TODO: 这里没有处理单方向关闭连接的情况。
        try:
            while True:
                try:
                    data=s.recv(1024)
                    if not data:
                        break
                    o['forward_data_time'] = int(time.time()*1000)
                except _socket.timeout as e:
                    if o['forward_data_time'] + data_timeout > int(time.time()*1000):
                        # 解决下慢速下载长时间无上传造成读超时断开连接的问题
                        continue
                    raise
                d.sendall(data)
        except _socket.error as e :
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

u'''
class HandlerPipeBase():
    u"""管道类


为了应付连接复用及UDP承载TCP等情况，必须存在本虚拟管道。
    """

    TYPE_TCP = 0x1
    TYPE_BIND = 0x2
    TYPE_UDP = 0x3
    TYPE_HTTP = 0x60


    def get_type(self):
        pass

    # 连接已建立
    # 读
    # 写
    # 结束(安全/不安全)
    #   tcp 级别的都是直接关闭连接，没什么需要特殊处理的
    #   http 有可能有长链接的问题，所以对于不确定的请求结尾需要标记为不安全，要求源放弃长连接复用，直接关闭连接。
    # 错误


#    def on_upstream_connected(self):
#        u""" 已连接到要代理 """

#    def on_remote_connected(self):
#        u""" 已连接到要远端
#socks5 代理回应客户连接已建立。 """

    # 连接无法建立

    #

    # 需要写(就是读源)

    # 需要读

    # 关闭


        # 调用 调度 建立一个到远端的连接
        # 回复客户端连接已建立
        # 写数据、读数据
        # 关闭连接

        # 上面有个问题，无法处理 http 透明代理并有缓存的情况
        # 如果提前回复已建立连接，无法建立到目标的连接时会影响 post 请求
        # 不过如果自己内部多次尝试可答题解决这个问题。

        # 另一个做法
        # 提供一个回调对象，提交给调度器
        # 调度器回调来工作
        #     获得接口类型 tcp、http、udp
        #     获得远端地址
        #     已连接到远端回调
        #     获得需要发出的数据
        #     收到需要发出的数据
        #     已结束(http 代理时可用？)
        #     关闭连接(socks5 、http代理可用)

        # 好处是灵活性更高，可以单独的线程测速，可以启用http透明代理、http协议分析、https协议分析、dns协议分析等功能。
        # 坏处是更改了原始逻辑，handler 返回时链接可能还在使用，不能在连接创建处管理链接。

        # 对于 http 代理需要考虑什么接口

        # http 代理接口
        #     是否可重试_无法建立连接时(tcp 等需提供)
        #     是否可重试_未发送数据时
        #     是否可重试_已发送数据时(tcp 指的是已发送数据并出错时是否可重新建立新连接并重新发送数据)
        #                            (UDP 指的是重新发包)
        #      但是感觉除了TCP连接建立失败，其他的都不能确定是不是协议本身就是这样的，所以无法使用。。。
        #      调度部分可能会根据 协议类型、目标端口等信息将连接转发到特定的协议处理器处进行处理。例如
        #          http 透明代理，尝试解析http协议，使得可以使用不支持 CONNECT 的 http 代理转发请求。
        #               可以做广告过滤，可以识别http服务器对特定ip的拒绝请求，自动更换后端
        #          https 旁路，尝试识别 https 证书错误，自动更换 后端
        #          dns 旁路，

    pass

class HandlerPipeHttpBase(HandlerPipeBase):
    u""" http 管道类

预期分为：命令行、头、实体 三部分。

在当前请求都到结尾的时候会后台启动一个新的

    """

class HandlerPipeTcpBase(HandlerPipeBase):
    u"""TCP 管道类"""

    def get_type(self):
        return HandlerPipeTcpBase.TYPE_TCP

    def get_remote_addr(self):
        u""" 获得远端地址

即预期的本 pipe 连接的另一侧的地址，调度会根据这个地址确定需要连接的目的地。

格式为 ('host',80,'atyp')
    host        目的主机，可能是域名、IPv4、IPv6 等格式
    80          目的端口
    atyp        目的主机格式的类型，和 socks5 的 atyp 一致。
                IPv4 = 0x01
                域名 = 0x03
                IPv6 = 0x04
"""
        return ('host',80,'atyp')

    def on_remote_connect_ok(self):
        pass
    def on_remote_connect_err(self):
        pass

    def read(self,size):
        pass
    def write(self,size):
        pass
    def close(self):
        pass
'''