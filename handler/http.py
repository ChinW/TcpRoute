#!/usr/bin/python
# -*- coding: utf-8 -*-
# utf-8 中文编码
from BaseHTTPServer import _quote_html
import logging
import mimetools
import urlparse
from gevent import socket
from handler.base import HandlerBase

HTTP_METHOD = ('GET', 'HEAD', 'PUT', 'POST', 'TRACE', 'OPTIONS', 'DELETE', 'CONNECT')


class HttpHandler(HandlerBase):
    u'''http 代理协议'''

    def __init__(self, sock, server):
        HandlerBase.__init__(self,sock,server)

    def handler(self):
        self.handle_one_request()

    def handle_one_request(self):
        if not self.parse_request():
            self.sock.shutdown(socket.SHUT_WR)
            self.sock.close()
            return
        self.send_error(200, '%s %s %s %s' % (self.command, self.path, self.request_version, self.host))
        self.sock.shutdown(socket.SHUT_WR)
        self.sock.close()

    def parse_request(self):
        self.command = ''
        self.request_version = "HTTP/0.9"
        self.path = ''
        self.host = ''  # 包含主机名及端口号
        self.close_connection = True
        self.scheme = 'http'

        raw_requestline = self.sock.readline(65537)
        if len(raw_requestline) > 65536:
            # TODO: 过长
            raise Exception()
        raw_requestline = raw_requestline.rstrip('\r\n')
        words = raw_requestline.split()
        if len(words) == 2:
            # http 0.9
            self.command, self.path = words
            if self.command != 'GET':
                self.send_error(400, "Bad HTTP/0.9 request type (%r)" % self.command)
                return False
        elif len(words) == 3:
            self.command, self.path, self.request_version = words

            if not self.request_version.startswith('HTTP/'):
                self.send_error(400, "Bad request version (%r)" % self.request_version)
                return False

            base_version_number = self.request_version.split('/', 1)[1]
            self.version_number = base_version_number.split(".")

            if len(self.version_number) != 2:
                self.send_error(400, "Bad request version (%r)" % self.request_version)
                return False

            self.version_number = [int(i) for i in self.version_number]

            if self.version_number >= (1, 1):
                # http 1.1 默认打开 持久连接
                self.close_connection = False

            if self.version_number >= (2, 0):
                self.send_error(505, "Bad request version (%r)" % self.request_version)
                return False
        else:
            self.send_error(400, "Bad request syntax (%r)" % raw_requestline)
            return False

        self.headers = self.MessageClass(self.sock, 0)

        # TODO: 作为代理时需要删除 Connection 指定的头
        conntype = self.headers.get('Connection', '')
        conntype = self.headers.get('Proxy-Connection', conntype)

        if self.headers.has_key('Connection'):
            del self.headers['Connection']
        if self.headers.has_key('Proxy-Connection'):
            del self.headers['Proxy-Connection']

        if conntype.lower() == 'close':
            self.close_connection = True
        elif conntype.lower() == 'keep-alive':
            self.close_connection = False

        self.host = self.headers.get('Host', None)

        # 处理 path 携带 host 的情况，例如 GET http://www.163.com/ HTTP/1.1
        self.urlparse = urlparse.urlparse(self.path)
        if self.urlparse.hostname:
            self.host = self.urlparse.hostname
            self.path = '%s?%s' % (self.urlparse.path, self.urlparse.query)
        if self.urlparse.scheme:
            self.scheme = self.urlparse.scheme


        # TODO 未处理 post 存在请求实体的情况。

        return True

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
