#!/usr/bin/python
# -*- coding: utf-8 -*-
# utf-8 中文编码

class HandlerBase(object):
    def __init__(self,sock):
        self.sock = sock

    def handler(self):
        pass

    @staticmethod
    def create(sock):
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

