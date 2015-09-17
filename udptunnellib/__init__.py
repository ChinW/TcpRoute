#!/usr/bin/python
# -*- coding: utf-8 -*-
# utf-8 中文编码

u"""
UDP 隧道

"""
import ctypes

import random
import math

import time
import struct

try:
    from io import BytesIO
except ImportError:
    try:
        from cStringIO import StringIO as BytesIO
    except ImportError:
        from StringIO import StringIO as BytesIO



# 单个包数据部分大小
PACKET_DATA_SIZE = 1400


# 包格式

# L 32位发送序列号(和tcp有个区别，这里序号每次不是按数据长度增加，而是每个流包+1)
# L 32位确认接受序列号
# H 16位接收窗口大小
# L 32选项
#    1bit 1:非流式包（不怕丢失，不会重发，不增加序列号的包。）
#         一般收到相同序列的包只处理第一个，存在这个标志的话不管是否已经收到了相同序列号的包都会处理。
#         置1 时不会处理数据部分。
#    1bit 1: SYN 建立连接位
# B 8位可选头长度0-255
# H 16位 数据长度
# 可选字段
# 数据
PACKET_FORMAT = u'LLHLBH'


class ReliableStrram():
    u"""可靠流

在底层不可靠的情况下提供可靠的流传输。

每个实例为单个隧道。
    """

    def __init__(self):
        # 下一个包的数据序列号
        self.send_offset = random.randint(0, 0x1000000)
        self.send_buff = []

        # 缓冲区保存的第一个包的序列号
        self.recv_start_offset = None
        # 预期收到的下一个报的序列号(非连续序列号的包不被计算。) = recv_start_offset + self
        # 使用时需要注意溢出的问题！！
        self.recv_safe_offset = None
        # 收到的最大的包序列号 = recv_start_offset + self
        self.recv_max_offset = None
        self.recv_buff = {}
        # 接收窗口大小
        self.recv_buff_available_size = 2 ** 16

        #  包重发时间
        self.packet_retry_time = 50
        pass

    def _fact_recv_data(self, data):
        u""" 外部真实包输入时调用 """
        send_offset, recv_offset, recv_buff_available_size, option, head_size, data_size \
            = struct.unpack_from(PACKET_FORMAT, data)
        struct_size = struct.calcsize(PACKET_FORMAT)

        # 可选头
        packet_head = data[struct_size:struct_size + head_size]
        packet_data = data[struct_size + head_size:struct_size + head_size + data_size]
        # 新的安全接收偏移相对于老的safe偏移移动了多少(safe 是预期的下一个包的序列号)
        new_safe_offset = ctypes.c_uint32(recv_offset - (self.recv_start_offset + self.recv_safe_offset))
        # 删除本地缓冲区内远端已确认收到的包
        self.send_buff = [p for p in self.send_buff if \
                          # 由于序列号有溢出的问题，所以只能使用相对与老safe偏移的位置前移多少位来进行比较
                          # 当前处理的包相对于上次 safe 偏移的位置
                          ctypes.c_uint32(p['offset'] - (self.recv_start_offset + self.recv_safe_offset)) >= new_safe_offset
                          ]
        self.recv_buff[send_offset] = {'data':packet_data}



    def _fact_sendall(self, data):
        u""" 真实的发送数据接口 """

    def _send_packet(self, p):
        u""" 实际发出单个包idea函数

注意：目前未处理包选项部分，例如 非流式包
         """
        packet_byte = BytesIO()
        packet_data = p['data']
        packet_data_size = len(packet_data)
        packet_byte.write(struct.pack(PACKET_FORMAT, p['offset'],
                                      ctypes.c_uint32(self.recv_start_offset + self.recv_safe_offset).value,
                                      self.recv_buff_available_size,
                                      0,  # TODO: 包选项,非流式包
                                      0,  # TODO: 可选字段长度
                                      packet_data_size
                                      ))
        packet_byte.write(packet_data)
        self._fact_sendall(packet_byte.getvalue())

    def _send_buff(self):
        u"""发送缓冲区内的内容

会将超时未收到ACK的包重新发送一遍。
        """
        t = int(time.time() * 1000)
        retry_time = t - self.packet_retry_time
        for p in self.send_buff:
            if p['send_time'] < retry_time:
                self._send_packet(p)
                p['send_time'] = t

    def sendall(self, data):
        u""" 安全 stream 发送 """
        packet_count = math.ceil(len(data) / float(PACKET_DATA_SIZE))

        for i in range(packet_count):
            packet_data = data[i * PACKET_DATA_SIZE:(i + 1) * PACKET_DATA_SIZE]
            packet_data_size = len(packet_data)

            packet_offset = self.send_offset
            self.send_offset = ctypes.c_uint32(self.send_offset + 1).value

            packet = {
                'data': packet_data,
                'offset': packet_offset,
                'send_time': 0,
            }
            self.send_buff.append(packet)

        self._send_buff()
