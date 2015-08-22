#!/usr/bin/python
# -*- coding: utf-8 -*-
# utf-8 中文编码
from BaseHTTPServer import _quote_html
import logging
import mimetools
import urlparse
from gevent import socket
from handler.base import HandlerBase
import httptool
from mysocket import MySocket

HTTP_METHOD = ('GET', 'HEAD', 'PUT', 'POST', 'TRACE', 'OPTIONS', 'DELETE', 'CONNECT')

u"""
预期http处理

收到 http 请求后解析头，然后获得host、port。
获得到 host、port的http连接。
转发 发出http头。


"""

class HttpHandler(HandlerBase):
    u'''http 代理协议'''

    def __init__(self, sock, server,porxy = True,remote_host=None,remote_port=None):
        u"""

porxy               是否是代理服务器模式，代理服务器模式会强制关闭不支持的协议。
                        删除未知的 Connection 指定的 http 头，删除未知的 upgrade 头。
                    非代理服务器模式（socks5拦截模式）碰到未知的 upgrade 头会回退到socks5代理模式。

remote_host        目标主机
remote_port        目标端口
        """
        HandlerBase.__init__(self,sock,server)
        self.porxy = porxy
        self.remote_host = remote_host
        self.remote_port = remote_port

    def handler(self):
        # 开启 socket peek 功能。
        msock = MySocket(self.sock,True)

        # 解析 http 协议头
        request = httptool.HttpRequest(self.msock)
        request.parse_head()

        upgrade = request.headers.get('Upgrade').lower()
        if upgrade == "websocket":
            # websocket 协议
            # TODO: 这里不处理，收到服务器升级成功的回复后在处理
            request.del_conntype(retain=['Upgrade'])
        elif upgrade is not None:
            # 存在未知的升级协议
            if self.porxy is False and self.remote_host and self.remote_port:
                # 非代理模式，对未知的协议直接转发。
                msock.reset_peek_offset()
                msock.set_peek(False)
                # 对外发起请求
                try:
                    remote_sock = self.server.upstream.create_connection((self.remote_host,self.remote_port),)
                except:
                    logging.exception(u'所有线路连接 tcp host:%s port:%s 失败。'%(self.remote_host,self.remote_port))
                    self.msock.close()
                    return
                self.forward(self.sock,remote_sock,5*60)
                return
            else:
                # 代理模式，删除各种未知的协议
                request.del_conntype(retain=[])
                del request.headers['Upgrade']

        try:
            remote_sock = self.server.upstream.create_connection(request.get_http_host_address(),)
        except:
            logging.exception(u'所有线路连接 tcp host:%s port:%s 失败。'%(self.remote_host,self.remote_port))
            self.msock.close()
            return
        #TODO: 转发 http请求。
        raise  NotImplementedError(u'未完成')
        remote_sock






        for retry in range(1):
            try:
                with self.server.upstream.get_http_conn() as http_conn:

                    pass
            except:
                pass

        self.handle_one_request()

    def handle_one_request(self):
        if not self.parse_request():
            self.sock.shutdown(socket.SHUT_WR)
            self.sock.close()
            return
        self.send_error(500, '%s %s %s %s' % (self.command, self.path, self.request_version, self.remote_host))
        self.sock.shutdown(socket.SHUT_WR)
        self.sock.close()


    def send_error(self, code, message=None):
        self.close_connection = True

        short, long = HttpHandler.responses.get(code, ('???', message))
        if message is None:
            message = long

        content = (HttpHandler.MESSAGE %
                   {'code': code, 'message': _quote_html(message), 'short': short})

        if self.request_version != "HTTP/0.9":
            self.sock.sendall('%s %s %s\r\n' % (self.request_version, code, short))
            self.sock.sendall('Content-Type:text/html; charset=UTF-8\r\n')
            self.sock.sendall('Connection: close\r\n\r\n')
        self.sock.sendall(content.encode('utf-8'))

    @staticmethod
    def create(sock,server):
        u'''创建handler
如果是本类可处理的协议返回本类实例，否则返回None
'''
        # 预先检测 1 字节
        exit = True
        data = sock.recv(1)
        data = data.upper()
        for m in HTTP_METHOD:
            if m[0] == data:
                exit = False

        if not exit:
            data += sock.recv(6)
            data = data.upper()

            for m in HTTP_METHOD:
                if data.startswith('%s ' % m):
                    # 是 http 请求
                    return (HttpHandler(sock,server), True)
        return (None, True)

    responses = {
        100: ('Continue', 'Request received, please continue'),
        101: ('Switching Protocols',
              'Switching to new protocol; obey Upgrade header'),

        200: ('OK', 'Request fulfilled, document follows'),
        201: ('Created', 'Document created, URL follows'),
        202: ('Accepted',
              'Request accepted, processing continues off-line'),
        203: ('Non-Authoritative Information', 'Request fulfilled from cache'),
        204: ('No Content', 'Request fulfilled, nothing follows'),
        205: ('Reset Content', 'Clear input form for further input.'),
        206: ('Partial Content', 'Partial content follows.'),

        300: ('Multiple Choices',
              'Object has several resources -- see URI list'),
        301: ('Moved Permanently', 'Object moved permanently -- see URI list'),
        302: ('Found', 'Object moved temporarily -- see URI list'),
        303: ('See Other', 'Object moved -- see Method and URL list'),
        304: ('Not Modified',
              'Document has not changed since given time'),
        305: ('Use Proxy',
              'You must use proxy specified in Location to access this '
              'resource.'),
        307: ('Temporary Redirect',
              'Object moved temporarily -- see URI list'),

        400: ('Bad Request',
              'Bad request syntax or unsupported method'),
        401: ('Unauthorized',
              'No permission -- see authorization schemes'),
        402: ('Payment Required',
              'No payment -- see charging schemes'),
        403: ('Forbidden',
              'Request forbidden -- authorization will not help'),
        404: ('Not Found', 'Nothing matches the given URI'),
        405: ('Method Not Allowed',
              'Specified method is invalid for this resource.'),
        406: ('Not Acceptable', 'URI not available in preferred format.'),
        407: ('Proxy Authentication Required', 'You must authenticate with '
                                               'this proxy before proceeding.'),
        408: ('Request Timeout', 'Request timed out; try again later.'),
        409: ('Conflict', 'Request conflict.'),
        410: ('Gone',
              'URI no longer exists and has been permanently removed.'),
        411: ('Length Required', 'Client must specify Content-Length.'),
        412: ('Precondition Failed', 'Precondition in headers is false.'),
        413: ('Request Entity Too Large', 'Entity is too large.'),
        414: ('Request-URI Too Long', 'URI is too long.'),
        415: ('Unsupported Media Type', 'Entity body in unsupported format.'),
        416: ('Requested Range Not Satisfiable',
              'Cannot satisfy request range.'),
        417: ('Expectation Failed',
              'Expect condition could not be satisfied.'),

        500: ('Internal Server Error', 'Server got itself in trouble'),
        501: ('Not Implemented',
              'Server does not support this operation'),
        502: ('Bad Gateway', 'Invalid responses from another server/proxy.'),
        503: ('Service Unavailable',
              'The server cannot process the request due to a high load'),
        504: ('Gateway Timeout',
              'The gateway server did not receive a timely response'),
        505: ('HTTP Version Not Supported', 'Cannot fulfill request.'),
    }

    MESSAGE = u"""\
<head>
<title>%(short)s</title>
</head>
<body>
<h1>%(short)s</h1>
<p>code %(code)d.
<p>Message: %(message)s.
</body>
"""
    MessageClass = mimetools.Message
