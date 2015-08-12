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
        self.send_error(500, '%s %s %s %s' % (self.command, self.path, self.request_version, self.host))
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

            self.version_number = tuple([int(i) for i in self.version_number])

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
        # 详见 HTTP协议RFC2616 14.10
        conntype = self.headers.get('Connection', '')
        conntype = self.headers.get('Proxy-Connection', conntype).lower()
        conntypes = [t.strip() for t in conntype.split(",")]

        if self.headers.has_key('Connection'):
            del self.headers['Connection']
        if self.headers.has_key('Proxy-Connection'):
            del self.headers['Proxy-Connection']

        if 'close' in conntypes:
            self.close_connection = True
        elif 'keep-alive' in conntypes:
            self.close_connection = False

        self.host = self.headers.get('Host', None)

        # 处理 path 携带 host 的情况，例如 GET http://www.163.com/ HTTP/1.1
        self.urlparse = urlparse.urlparse(self.path)
        if self.urlparse.hostname:
            self.host = self.urlparse.hostname
            if self.urlparse.query:
                self.path = '%s?%s' % (self.urlparse.path, self.urlparse.query)
            else:
                self.path = self.urlparse.path
        if self.urlparse.scheme:
            self.scheme = self.urlparse.scheme


        # TODO 未处理 post 存在请求实体的情况。
        # GET 无请求实体
        # PUT 方法，写入新文档，有请求实体
        # POST 提交表单，有请求实体
        # TRACE 测试方法，请求无实体，响应有实体，内容时web服务器收到的请求头
        # OPTIONS 请求应该无实体，响应可能有实体(0长度)。
        # DELETE 请求无实体，响应有实体

        # Expect: 100-continue
        # http://www.cnblogs.com/cxd4321/archive/2012/01/30/2331621.html
        # http://www.cnblogs.com/zhengyun_ustc/p/100continue.html
        # 代理收到源服务器的 100 响应需要检查客户是否是 http 1.0 或之前的版本，
        # 1.0 或更早的版本不支持 100 请求，所以不应该转发 100 响应。

        # 204 响应没有响应实体
        #

        # 等幂 方法
        # GET，HEAD，PUT，DELETE
        # OPTIONS和TRACE

        # 代理需要维护同名首部字段的相对顺序。 http 权威指南 116页。

        # 目前这个类不需要对内容进行理解，只要能确保能识别到每个请求结尾即可。
        # 具体对内容进行理解不需要在当前阶段实现，可以另外使用

        #请求中消息主体（message-body）的存在是被请求中消息头域中是否存在内容长度
        #（Content-Length）或传输译码（Transfer-Encoding）头域来通知的。一个消息主体
        #（message-body）不能被包含在请求里如果某种请求方法（见5.1.1节）不支持请求里包含实
        #体主体（entity-body）。一个服务器应该能阅读或再次转发请求里的消息主体；如果请求方法
        #不允许包含一个实体主体（entity-body），那么当服务器处理这个请求时消息主体应该被忽略。
        #对于响应消息，消息里是否包含消息主体依赖相应的请求方法和响应状态码。所有 HEAD请求
        #方法的请求的响应消息不能包含消息主体，即使实体头域出现在请求里。所有 1XX（信息的），
        #204（无内容的）和304（没有修改的）的响应都不能包括一个消息主体（message-body）。
        #所有其他的响应必须包括消息主体，即使它长度可能为零。


        u'''

当消息主体出现在消息中时，一条消息的传输长度（transfer-length）是消息主体（message-
body）的长度；也就是说在实体主体被应用了传输编码（transfer-coding）后。当消息中出现消息主体时，消息主体的传输长度（transfer-length）由下面（以优先权的顺序）决定：:

1。任何不能包含消息主体（message-body）的消息（这种消息如1xx，204和304响应和任
何HEAD方法请求的响应）总是被头域后的第一个空行（CRLF）终止，不管消息里是否存在
实体头域（entity-header fields）。

2。如果Transfer-Encoding头域（见14.41节）出现，并且它的域值是非”“dentity”传输编码
值，那么传输长度（transfer-length）被“块”（chunked）传输编码定义，除非消息因为通过
关闭连接而结束。
3。如果出现Content-Length头域（属于实体头域）（见14.13节），那么它的十进制值（以
字节表示）即代表实体主体长度（entity-length，译注：实体长度其实就是实体主体的长度，
以后把entity-length翻译成实体主体的长度）又代表传输长度（transfer-length）。Content-
Length 头域不能包含在消息中，如果实体主体长度（entity-length）和传输长度（transfer-
length）两者不相等（也就是说，出现Transfer-Encodind头域）。如果一个消息即存在传输译
码（Transfer-Encoding）头域并且也Content-Length头域，后者会被忽略。

4。如果消息用到媒体类型“multipart/byteranges”，并且传输长度（transfer-length）另外也没
有指定，那么这种自我定界的媒体类型定义了传输长度（transfer-length）。这种媒体类型不能
被利用除非发送者知道接收者能怎样去解析它； HTTP1.1客户端请求里如果出现Range头域
并且带有多个字节范围（byte-range）指示符，这就意味着客户端能解析multipart/byteranges
响应。
一个Range请求头域可能会被一个不能理解multipart/byteranges的HTTP1.0代理（proxy）
再次转发；在这种情况下，服务器必须能利用这节的1，3或5项里定义的方法去定界此消息。

5。通过服务器关闭连接能确定消息的传输长度。（请求端不能通过关闭连接来指明请求消息体
的结束，因为这样可以让服务器没有机会继续给予响应）。

为了与HTTP/1.0应用程序兼容，包含 HTTP/1.1消息主体的请求必须包括一个有效的内容长
度（Content-Length）头域，除非服务器是HTTP/1.1遵循的。如果一个请求包含一个消息主体
并且没有给出内容长度（Content-Length），那么服务器如果不能判断消息长度的话应该以
400响应（错误的请求），或者以411响应（要求长度）如果它坚持想要收到一个有效内容长
度（Content-length）。

所有的能接收实体的HTTP/1.1应用程序必须能接受"chunked"的传输编码（3.6节），因此当
消息的长度不能被提前确定时，可以利用这种机制来处理消息。

消息不能同时都包括内容长度（Content-Length）头域和非identity传输编码。如果消息包括了
一个非identity的传输编码，内容长度（Content-Length）头域必须被忽略.

当内容长度（Content-Length）头域出现在一个具有消息主体（message-body）的消息里，
它的域值必须精确匹配消息主体里字节数量。 HTTP/1.1用户代理（user agents）当接收了一个
无效的长度时必须能通知用户。
'''

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
