#!/usr/bin/python
# -*- coding: utf-8 -*-
# utf-8 中文编码

u''' 转发的协议支持

目前已知的转发协议分为：
http 类 、tcp 、udp类型。






 '''

# 显式 import ，防止打包出错。
#from base import UpstreamBase
import sys
#from socks5 import Socks5Upstream
#from direct import DirectUpstream

UPSTREAM_NAME_SUFFIX = 'Upstream'


def get_upstream(name):
    u'''
>>> get_upstream("socks5") == Socks5Upstream
True
>>> get_upstream("socks5") == DirectUpstream
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
