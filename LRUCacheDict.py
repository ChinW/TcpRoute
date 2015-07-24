#!/usr/bin/python
# -*- coding: utf-8 -*-
# utf-8 中文编码

from time import time

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
    def __init__(self,maxSize=100,expire=10*60*1000):
        self.maxSize=maxSize
        self.expire=expire
        self.__value = {}
        self.__expireDict = {}
        self.__accessDict = {}

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

if __name__ == "__main__":
    import doctest
    doctest.testmod()
