#!/usr/bin/python
# -*- coding: utf-8 -*-
# utf-8 中文编码

u''' 转发的协议支持

目前已知的转发协议分为：
http 类 、tcp 、udp类型。


每个新代理注册后应该尝试自动识别代理的特征，例如：
是否支持 udp
是否支持 tcp(socks5、http CONNECT)
是否支持 http
支持的目的端口
是否支持 ipv6
代理所在地
对于特定类型网站的可访问性
    twitter.com
    google.com ip 机器人验证
    维基封锁ip
    国内的版权视频
    日本的游戏服务

还可以测试线路中间是否有透明代理
    通过向不存在的http服务器发出http请求，但是host主机存在来探测部分透明代理
    通过发出异常的http头(部分头重复，特定顺序)，并查询远端服务器返回收到的

测试代理是否存在异常缓存，例如：
    超期缓存
    跨会话缓存
    404缓存



 '''

# 显式 import ，防止打包出错。
#from base import UpstreamBase
import sys
from socks5 import Socks5Upstream
from direct import DirectUpstream
from multipath import MultipathUpstream

UPSTREAM_NAME_SUFFIX = 'Upstream'


def get_upstream(name):
    u'''
>>> get_upstream("socks5") == Socks5Upstream
True
>>> get_upstream("direct") == DirectUpstream
True
>>> get_upstream('xxx') == None
True
    '''
    module_name = ("%s%s"%(name,UPSTREAM_NAME_SUFFIX))
    module = sys.modules[__name__]
    for k in dir(module):
        if module_name.lower() == k.lower():
            return getattr(module,k)
    return  None


if __name__ == "__main__":
    import doctest
    doctest.testmod()
