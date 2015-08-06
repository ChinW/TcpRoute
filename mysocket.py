#!/usr/bin/python
# -*- coding: utf-8 -*-
# utf-8 中文编码
import logging
from socket import _fileobject, EINTR, error
import traceback
from gevent import socket
import struct

try:
    from io import BytesIO
except ImportError:
    try:
        from cStringIO import StringIO as BytesIO
    except ImportError:
        from StringIO import StringIO as BytesIO



class FileObject(_fileobject):
    u'''
不建议使用了，MySocket 已经实现了 FileObject 的大部分功能。

注意：在使用 readline 并且 bufsize > 1 时，会使用缓冲区，并且会多读数据存放到缓冲区。
C:/Python27/Lib/socket.py:447
意味着如果使用了 readline ，并且 bufsize >1 ，之后的读操作必须继续使用本类的read、readline 等函数，否则有可能丢失数据！！
'''
    def unpack(self, fmt):
        length = struct.calcsize(fmt)
        data = self.recv(length)
        if len(data) < length:
            raise Exception("[FileObject].unpack: bad formatted stream")
        return struct.unpack(fmt, data)

    def pack(self, fmt, *args):
        data = struct.pack(fmt, *args)
        return self.sendall(data)

    def recv(self,size):
        return self.read(size)

    def sendall(self,data):
        return self.write(data)


class MySocket:
    u'''预读缓冲区
'''
    def __init__(self,sock,peek=True):
        self.sock = sock
        self.peek = peek
        # 缓冲区开头为启用 peek 的位置
        # 当前位置为当前读取到的位置
        #       缓冲区中间表示之前已经预读的数据当前还未发完
        #       缓冲区结尾表示读取的已经超过预读缓冲区尺寸了
        #
        self.peek_data = BytesIO()

    def recv(self,size):
        u'''读数据，在读不够指定 size 数据时也会返回。
完全无数据时会阻塞(缓冲区数据量不够，并且源无数据时也会阻塞)。
超时会引发超时异常。
如果有缓存的数据，就会忽略所有的异常。
'''
        # 先读缓冲区
        offset = self.peek_data.tell()
        res = self.peek_data.read(size)

        assert len(res) <= size ,u'read 错误，读了比预期多的数据。'

        if len(res)<size:
            # 数据不够时从 sock 读取
            data = b''
            try:
                data = self.sock.recv(size-len(res))
            except error, e:
                if (not res) and e.errno != EINTR:
                    # 没有预读数据并且不是 EINTR 异常
                    raise e
                else:
                    # 如果存在缓存数据，忽略异常，直接返回缓存的部分数据
                    info = traceback.format_exc()
                    logging.debug(u'[MySocket]recv 读取异常，存在缓冲区数据，忽略异常。')
                    logging.debug('%s\r\n\r\n'%info)
            finally:
                self.peek_data.write(data)
                self.peek_data.seek(offset)
                res = self.peek_data.read(size)

        self._clear_peek_data()
        return res

    def _clear_peek_data(self):
        u'''清理不需要的 peek 缓冲区数据'''
        if self.peek is False:
            # 无 peek 时需要删除已读缓冲区
            old_peek_data = self.peek_data
            self.peek_data = BytesIO()
            self.peek_data.write(old_peek_data.read())
            self.peek_data.seek(0)

    def read(self,size):
        u'''读数据（完全阻塞）

在不够 size 时会不断尝试读取，直到数据足够或超时。
当出现超时错误时可能已经读到了一部分数据，但是并未达到要求的数据量。
重新读时不会丢失缓冲区的内容。
超时计算是按照完全收不到数据时开始计算，也就是慢速连接并不会触发超时机制。
'''
        is_end = False

        while True:
            offset = self.peek_data.tell()
            res = self.peek_data.read(size)

            assert len(res) <= size ,u'read 错误，读了比预期多的数据。'

            if len(res) == size or is_end:
                # 读够 size 或 读不到数据(连接关闭)
                self._clear_peek_data()
                return res
            elif len(res) < size:
                data = b''
                try:
                    data = self.sock.recv(size-len(res))
                except error as e:
                    if e.errno == EINTR:
                        continue
                    raise e
                finally:
                    self.peek_data.write(data)
                    self.peek_data.seek(offset)
                if not data:
                    # 如果读到结尾(data == b'')
                    is_end = True


    def readline(self,size):
        u'''读一行数据(完全阻塞)

size 尝试读取的最大长度。

直到读到 \n 或达到 size 长度时返回。
否则会不断尝试读取，直到超时引发异常。
超时异常不会丢失缓冲区的数据。
'''
        is_end = False

        while True:
            offset = self.peek_data.tell()
            res = self.peek_data.readline(size)

            assert len(res)<=size, u'readline 错误，读了比预期多的数据。'

            if res[-1] == '\n' or len(res) == size or is_end:
                self._clear_peek_data()
                return res
            elif len(res)<size:
                data = b''
                try:
                    data = self.sock.recv(size-len(res))
                except error as e:
                    if e.errno == EINTR:
                        continue
                    raise e
                finally:
                    self.peek_data.write(data)
                    self.peek_data.seek(offset)

                if not data:
                    # 如果读到结尾(data == b'')
                    is_end = True


    def sendall(self,data):
        return self.sock.sendall(data)

    def set_peek(self,value):
        u'''开关预读'''
        if self.peek == False and value == True:
            new = BytesIO()
            new.write(self.peek_data.read())
            new.seek(0)
            self.peek_data = new
        self.peek = value

    def reset_peek_offset(self):
        u'''复位预读指针'''
        self.peek_data.seek(0)

    def unpack(self, fmt,block = True):
        u'''解包

block 是否阻塞
    即使非阻塞模式是标准的 recv ，也会阻塞。
    阻塞模式会完全阻塞，直到连接关闭或连接超时。
'''
        length = struct.calcsize(fmt)
        if block:
            data = self.read(length)
        else:
            data = self.recv(length)
        if len(data) < length:
            raise Exception("SClient.unpack: bad formatted stream")
        return struct.unpack(fmt, data)

    def pack(self, fmt, *args):
        data = struct.pack(fmt, *args)
        return self.sendall(data)

    def close(self):
        self.peek_data = BytesIO()
        return self.sock.close()

    def fileno(self):
        return self.sock.fileno()

    def makefile(self,mode='rb', bufsize=-1, close=False):
        u'''不建议使用了，自身已经实现了 makefile 的大部分功能。'''
        return FileObject(self,mode,bufsize,close)

    def shutdown(self,how):
        self.sock.shutdown(how)

    def flush(self):
        pass