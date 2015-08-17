#!/usr/bin/python
# -*- coding: utf-8 -*-
# utf-8 中文编码
import logging
import threading

from time import time
from functools import wraps
from contextlib import contextmanager


class __None():
    pass

class __lock:
    def __enter__(self):
        return None

    def __exit__(self, exc_type, exc_val, exc_tb):
        return True

def lru_cache(maxSize=128, expire=10*60*1000, typed = False,lock = threading.Lock):
    u'''
lock == None 时表示不使用锁
    '''
    if callable(maxSize):
        # 目的是当用户 @lru_cache 时也有效。
        return lru_cache()(maxSize)

    if lock == None:
        lock = __lock

    def _lru_cache(func):
        cache = LRUCacheDict(maxSize,expire)
        l = lock()

        @wraps(func)
        def nfunc( *args, **kwargs):
            key = _make_key(args,kwargs,typed)
            with l:
                res = cache.get(key ,__None)
            if res == __None:
                res = func(*args, **kwargs)
                cache[key] = res
            return res
        return nfunc
    return _lru_cache



class LRUCacheDict():
    u''' LRU 字典

只在必要的时候删除内容，例如：
    读取过期内容时会删除将要读取的内容
    大小超出maxSize时，会遍历删除所有过期内容
    调用 clean 时强制删除所有过期内容

>>> import time
>>> d= LRUCacheDict(5,3*1000)
>>> d[1]='111'
>>> d[2]='22'
>>> d.has_key(3)
False
>>> d.has_key(2)
True
>>> d.get(2,'999')
'22'
>>> d.get(3,'123')
'123'
>>> d[3]='333'
>>> d[4]='1234'
>>> d[5]='5'
>>> d[1]
'111'
>>> d[6]='5'
>>> d[1]
'111'
>>> len(d)
5
>>> d[2]
Traceback (most recent call last):
...
KeyError: 2
>>> d[4]
'1234'
>>> del d[4]
>>> d[4]
Traceback (most recent call last):
...
KeyError: 4
>>> import time
>>> d[1]
'111'
>>> time.sleep(2)
>>> d[1]
'111'
>>> d[2]='202'
>>> time.sleep(2)
>>> d[2]
'202'
>>> d[1]
Traceback (most recent call last):
...
KeyError: 1
>>> d[3]
Traceback (most recent call last):
...
KeyError: 3
>>> d[5]
Traceback (most recent call last):
...
KeyError: 5
>>> time.sleep(2)
>>> d[2]
Traceback (most recent call last):
...
KeyError: 2

    '''
    def __init__(self,maxSize=100,expire=10*60*1000,safe_del = None):
        self.maxSize=maxSize
        self.expire=expire
        self.__value = {}
        self.__expireDict = {}
        self.__accessDict = {}
        self.safe_del = safe_del

    def __len__(self):
        return self.__value.__len__()

    def __checkKey(self,key):
        if self.__value.has_key(key) and (self.__expireDict[key] < int(time()*1000)):
            del self[key]

    def __updateTime(self,key):
        if self.__value.has_key(key):
            del self.__accessDict[key]
            self.__accessDict[key]=int(time()*1000)

    def has_key(self,key):
        self.__checkKey(key)
        self.__updateTime(key)
        return self.__value.has_key(key)

    def __getitem__(self, key):
        self.__checkKey(key)
        self.__updateTime(key)
        return self.__value[key]

    def __setitem__(self, key, value):
        if self.has_key(key):
            del self[key]

        now = int(time()*1000)
        self.__value[key] = value
        self.__accessDict[key] = now
        self.__expireDict[key] = now + self.expire

        if len(self)>self.maxSize:
            self.clean()

    def get(self,key,default=None):
        if self.has_key(key):
            return self.__value[key]
        return default

    def __delitem__(self, key):
        u"""
>>> import sys
>>> safe_del=lambda d,k,v:sys.stdout.write('%s,%s,%s'%(type(d),k,v))
>>> dd = LRUCacheDict(5,3*1000,safe_del=safe_del)
>>> dd['a'] = 'aaa'
>>> del dd['a']
<type 'instance'>,a,aaa
"""
        if self.safe_del:
            try:
                self.safe_del(self,key,self.__value[key])
            except:
                logging.exception(u'safe_del err')
        del self.__value[key]
        del self.__accessDict[key]
        del self.__expireDict[key]

    def clean(self):
        now = int(time()*1000)
        for k in self.__expireDict.keys():
            if self.__expireDict[k] < now:
                del self[k]

        if len(self)>self.maxSize:
            accessList = sorted(self.__accessDict.iteritems(),key=lambda x:x[1])
            for i in range(len(self)-self.maxSize):
                del self[accessList[i][0]]

    def __del__(self):
        if self.safe_del:
            for k in self.__value.keys():
                del self.__value[k]


class _HashedSeq(list):
    """ This class guarantees that hash() will be called no more than once
        per element.  This is important because the lru_cache() will hash
        the key multiple times on a cache miss.

    """

    __slots__ = 'hashvalue'

    def __init__(self, tup, hash=hash):
        self[:] = tup
        self.hashvalue = hash(tup)

    def __hash__(self):
        return self.hashvalue


def _make_key(args, kwds, typed,
             kwd_mark = (object(),),
             fasttypes = {int, str, frozenset, type(None)},
             sorted=sorted, tuple=tuple, type=type, len=len):
    """Make a cache key from optionally typed positional and keyword arguments

    The key is constructed in a way that is flat as possible rather than
    as a nested structure that would take more memory.

    If there is only a single argument and its data type is known to cache
    its hash value, then that argument is returned without a wrapper.  This
    saves space and improves lookup speed.

    """
    key = args
    if kwds:
        sorted_items = sorted(kwds.items())
        key += kwd_mark
        for item in sorted_items:
            key += item
    if typed:
        key += tuple(type(v) for v in args)
        if kwds:
            key += tuple(type(v) for k, v in sorted_items)
    elif len(key) == 1 and type(key[0]) in fasttypes:
        return key[0]
    return _HashedSeq(key)












if __name__ == "__main__":
    import doctest
    doctest.testmod()
