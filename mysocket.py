#!/usr/bin/python
# -*- coding: utf-8 -*-
# utf-8 中文编码
import logging
from socket import _fileobject, EINTR, error
import traceback
from gevent import socket
import struct
import gevent
import time
import math

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

    def recv(self, size):
        return self.read(size)

    def sendall(self, data):
        return self.write(data)


class SocketBase:
    u"""基本 socket

注意：readline 有可能将一部分数据保存到类的缓冲区内，
      所以一旦使用了readline 函数就不能在直接使用原始套接字的 recv 等函数了。
"""

    def __init__(self, sock):
        self.sock = sock
        self.peek_data = BytesIO()

    def recv(self, size):
        u'''读数据，在读不够指定 size 数据时也会返回。
完全无数据时会阻塞(缓冲区数据量不够，并且源无数据时也会阻塞)。
超时会引发超时异常。
如果有缓存的数据，就会忽略所有的异常。
虽然正常操作系统在连接异常时会直接抛弃缓冲区的内容，不过这里还是先处理完缓冲区的内容再引发异常。
'''
        # 先读缓冲区
        offset = self.peek_data.tell()
        res = self.peek_data.read(size)

        assert len(res) <= size, u'read 错误，读了比预期多的数据。'

        if len(res) < size:
            # 数据不够时从 sock 读取
            data = b''
            try:
                data = self.sock.recv(size - len(res))
            except error, e:
                if (not res) and e.errno != EINTR:
                    # 没有预读数据并且不是 EINTR 异常
                    raise e
                else:
                    # 如果存在缓存数据，忽略异常，直接返回缓存的部分数据
                    info = traceback.format_exc()
                    logging.debug(u'[MySocket]recv 读取异常，存在缓冲区数据，忽略异常。')
                    logging.debug('%s\r\n\r\n' % info)
            finally:
                self.peek_data.write(data)
                self.peek_data.seek(offset)
                res = self.peek_data.read(size)

        self._clear_peek_data()
        return res

    def _clear_peek_data(self):
        u'''清理不需要的缓冲区数据'''
        old_peek_data = self.peek_data
        self.peek_data = BytesIO()
        self.peek_data.write(old_peek_data.read())
        self.peek_data.seek(0)

    def read(self, size):
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

            assert len(res) <= size, u'read 错误，读了比预期多的数据。'

            if len(res) == size or is_end:
                # 读够 size 或 读不到数据(连接关闭)
                self._clear_peek_data()
                return res
            elif len(res) < size:
                data = b''
                try:
                    data = self.sock.recv(size - len(res))
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

    def readline(self, size):
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

            assert len(res) <= size, u'readline 错误，读了比预期多的数据。'

            if res[-1] == '\n' or len(res) == size or is_end:
                self._clear_peek_data()
                return res
            elif len(res) < size:
                data = b''
                try:
                    data = self.sock.recv(size - len(res))
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

    def sendall(self, data):
        return self.sock.sendall(data)

    def unpack(self, fmt, block=True):
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

    def setblocking(self, flag):
        return self.sock.setblocking(flag)

    def settimeout(self, howlong):
        return self.sock.settimeout(howlong)

    def setsockopt(self,level, option, value):
        return self.sock.setsockopt(level,option,value)

    def close(self, safe=True, timeout=5, sleep='read'):
        u''' 关闭

if sleep == 'read':
    shutdown
    设置读超时为 timeout
    循环读
    读到结尾在关闭连接
sleep = gevent.sleep
    shutdown
    sleep(timeout)
    close()
        '''
        self.peek_data = BytesIO()

        if safe:
            try:
                self.shutdown(socket.SHUT_WR)

                if sleep == 'read':
                    end = time.time() + timeout
                    self.setblocking(1)
                    while True:
                        timeout = math.ceil(end - time.time())
                        if timeout <= 0:
                            break
                        self.sock.settimeout(timeout)
                        data = self.recv(2048)
                        if not data:
                            break

                elif callable(self):
                    sleep(timeout)

                else:
                    raise ValueError()
                    # 正常操作是先关闭写通道
                    # 等待对方关闭对方的写通道(既本机的读通道)(会读到空表示关闭了)
                    # 双向流都关闭了后在 close 连接。
            except:
                pass
            finally:
                try:
                    return self.close()
                except:
                    pass
        return self.sock.close()

    def fileno(self):
        return self.sock.fileno()

    def shutdown(self, how):
        self.sock.shutdown(how)


    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        u'''退出与该对象相关的运行时刻上下文。参数描述导致该上下文即将退出的异常。如果该上下文退出时没有异常，三个参数都将为None。

如果提供了一个异常，但该方法期望压制该异常（例如，防止它扩散），它应该返回一个真值。否则，该异常将在从该函数退出时被正常处理。

注意__exit__()方法不应该重新抛出传递进去的异常；这是调用者的责任。 '''
        try:
            self.close()
        except:
            pass
        return False


# 为了防止upstream处不被支持的方法被使用，暂时只支持以上方法。
#    def __getattr__(self, name):
#        return getattr(self.sock,name)

class MySocket(SocketBase):
    u"""预读缓冲区

注意：所有的读写操作都需要仔细检查。
      基类的每个读写操作都需要小心，可能基类会使用自己的缓冲区！
"""
    def __init__(self, sock, peek=True):
        SocketBase.__init__(self,sock)

        self.peek = peek
        # 缓冲区开头为启用 peek 的位置
        # 当前位置为当前读取到的位置
        #       缓冲区中间表示之前已经预读的数据当前还未发完
        #       缓冲区结尾表示读取的已经超过预读缓冲区尺寸了
        #
        self.peek_data = BytesIO()

    def recv(self, size):
        u'''读数据，在读不够指定 size 数据时也会返回。
完全无数据时会阻塞(缓冲区数据量不够，并且源无数据时也会阻塞)。
超时会引发超时异常。
如果有缓存的数据，就会忽略所有的异常。
虽然正常操作系统在连接异常时会直接抛弃缓冲区的内容，不过这里还是先处理完缓冲区的内容再引发异常。

'''
        # 先读缓冲区
        offset = self.peek_data.tell()
        res = self.peek_data.read(size)

        assert len(res) <= size, u'read 错误，读了比预期多的数据。'

        if len(res) < size:
            # 数据不够时从 sock 读取
            data = b''
            try:
                data = self.sock.recv(size - len(res))
            except error, e:
                if (not res) and e.errno != EINTR:
                    # 没有预读数据并且不是 EINTR 异常
                    raise e
                else:
                    # 如果存在缓存数据，忽略异常，直接返回缓存的部分数据
                    info = traceback.format_exc()
                    logging.debug(u'[MySocket]recv 读取异常，存在缓冲区数据，忽略异常。')
                    logging.debug('%s\r\n\r\n' % info)
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

    def read(self, size):
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

            assert len(res) <= size, u'read 错误，读了比预期多的数据。'

            if len(res) == size or is_end:
                # 读够 size 或 读不到数据(连接关闭)
                self._clear_peek_data()
                return res
            elif len(res) < size:
                data = b''
                try:
                    data = self.sock.recv(size - len(res))
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

    def readline(self, size):
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

            assert len(res) <= size, u'readline 错误，读了比预期多的数据。'

            if res[-1] == '\n' or len(res) == size or is_end:
                self._clear_peek_data()
                return res
            elif len(res) < size:
                data = b''
                try:
                    data = self.sock.recv(size - len(res))
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

    def sendall(self, data):
        return self.sock.sendall(data)

    def set_peek(self, value):
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

    def unpack(self, fmt, block=True):
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

    def setblocking(self, flag):
        return self.sock.setblocking(flag)

    def settimeout(self, howlong):
        return self.sock.settimeout(howlong)

    def close(self, safe=True, timeout=5, sleep='read'):
        u''' 关闭

if sleep == 'read':
    shutdown
    设置读超时为 timeout
    循环读
    读到结尾在关闭连接
sleep = gevent.sleep
    shutdown
    sleep(timeout)
    close()
        '''
        self.peek_data = BytesIO()

        if safe:
            try:
                self.shutdown(socket.SHUT_WR)

                if sleep == 'read':
                    end = time.time() + timeout
                    self.setblocking(1)
                    while True:
                        timeout = math.ceil(end - time.time())
                        if timeout <= 0:
                            break
                        self.sock.settimeout(timeout)
                        data = self.recv(2048)
                        if not data:
                            break

                elif callable(self):
                    sleep(timeout)

                else:
                    raise ValueError()
                    # 正常操作是先关闭写通道
                    # 等待对方关闭对方的写通道(既本机的读通道)(会读到空表示关闭了)
                    # 双向流都关闭了后在 close 连接。
            except:
                pass
            finally:
                try:
                    return self.close()
                except:
                    pass
        return self.sock.close()

    def fileno(self):
        return self.sock.fileno()

    def makefile(self, mode='rb', bufsize=-1, close=False):
        u'''不建议使用了，自身已经实现了 makefile 的大部分功能。'''
        return FileObject(self, mode, bufsize, close)

    def shutdown(self, how):
        self.sock.shutdown(how)

    def flush(self):
        pass
