#!/usr/bin/python
# -*- coding: utf-8 -*-
# utf-8 中文编码

u''' 对外提供的协议支持

http 代理及 socks5 代理显示的地方都在于初始化玩协议头后都是转发内容。
也就是可以尝试合并两者实现，



 '''
from pprint import pprint

import sys

# 为了防止打包出错，显式导入。
from socks5 import Socks5Handler
from http import HttpHandler

HANDLER_NAME_SUFFIX = 'Handler'


def get_handler(name=None):
    u'''
>>> get_handler("socks5") == Socks5Handler
True
>>> get_handler('xxx') == None
True
>>> Socks5Handler in get_handler(None)
True
    '''
    module_name = ("%s%s" % (name, HANDLER_NAME_SUFFIX))
    module = sys.modules[__name__]

    if name is None:
        #        res =[]
        #        for k in dir(module):
        #            if k.endswith(HANDLER_NAME_SUFFIX):
        #                res.append(getattr(module,k))
        #        return res
        # 手工输出，指定顺序，防止 http 阻塞 socks5
        return (Socks5Handler, HttpHandler)

    for k in dir(module):
        if module_name.lower() == k.lower():
            return getattr(module, k)
    return None


if __name__ == "__main__":
    import doctest

    doctest.testmod()
