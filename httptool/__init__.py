#!/usr/bin/python
# -*- coding: utf-8 -*-
# utf-8 中文编码


u"""HTTP 工具

接受 socket

"""

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

# 请求中消息主体（message-body）的存在是被请求中消息头域中是否存在内容长度
# （Content-Length）或传输译码（Transfer-Encoding）头域来通知的。一个消息主体
# （message-body）不能被包含在请求里如果某种请求方法（见5.1.1节）不支持请求里包含实
# 体主体（entity-body）。一个服务器应该能阅读或再次转发请求里的消息主体；如果请求方法
# 不允许包含一个实体主体（entity-body），那么当服务器处理这个请求时消息主体应该被忽略。
# 对于响应消息，消息里是否包含消息主体依赖相应的请求方法和响应状态码。所有 HEAD请求
# 方法的请求的响应消息不能包含消息主体，即使实体头域出现在请求里。所有 1XX（信息的），
# 204（无内容的）和304（没有修改的）的响应都不能包括一个消息主体（message-body）。
# 所有其他的响应必须包括消息主体，即使它长度可能为零。


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

u"""
Expect

Expect请求头域用于指明客户端需要的特定服务器行为。

Expect = "Expect" ":" 1#expectation
expectation = "100-continue" | expectation-extension
expectation-extension = token [ "=" ( token | quoted-string )
*expect-params ]
expect-params = ";" token [ "=" ( token | quoted-string ) ]

一个服务器如果不能理解或遵循一个请求里 Expect头域的任何expectation值，那么它必须以
合适的错误状态码响应。如果服务器不能满足任何expectation值，服务器必须以417（期望失
败）状态码响应，或者如果服务器满足请求时遇到其它问题，服务器必须发送4xx状态码。
本头域为将来的扩展被定义成一个扩展的语法。若服务器接收到的请求含有它不支持的
expectation-extension，那么它必须以417（期望失败）状态响应。

expectation值的比较对于未引用标记（unquoted token）（包括“100-contine”标记）是而言
是不区分大小写的，对引用字符串（quoted-string）的expectation-extension而言是区分大小
写的。

Expect机制是hop-by-hop的：即HTTP/1.1代理（proxy）必须返回417（期望失败）响应如
果它接收了一个它不能满足的expectation。 然而，Expect请求头域本身是end-to-end头域；
它必须要随请求一起转发。

许多旧版的HTTP/1.0和HTTP/1.1应用程序并不理解Expect头域。
"""

u"""
Transfer-Encoding
传输译码（Transfer-Encoding）常用头域指示了消息主体（message body）的编码转换，这
是为了实现在接收端和发送端之间的安全数据传输。它不同于内容编码（content-coding），传
输代码是消息的属性，而不是实体（entity）的属性。

       Transfer-Encoding       = "Transfer-Encoding" ":" 1#transfer-coding

  传输编码（transfer-coding）在3.6节中被定义了。一个例子是：

         Transfer-Encoding: chunked

如果一个实体应用了多种传输编码，传输编码（transfer-coding）必须以应用的顺序列出。传输
编码（transfer-coding）可能会提供编码参数（译注：看传输编码的定义,3.6节），这些编码
参数额外的信息可能会被其它实体头域（entity-header）提供，但这并没有在规范里定义。

许多老的HTTP/1.1应用程序不能理解传输译码（Transfer-Encoding）头域。
"""

u"""
转发请求时需要删除 Upgrade 头，防止协议被切换到 http2 。

Upgrade常用头域允许客户端指定它所支持的附加通信协议，并且可能会使用如果服务器觉得
可以进行协议切换。服务器必须利用 Upgrade头域于一个101（切换协议）响应里，用来指明
哪个协议被切换了。
Upgrade = “Upgrade” “:” 1#product
例如，
Upgrade: HTTP/2.0，SHTTP/1.3, IRC/6.9, RTA/x11
Upgrade头域的目的是为了提供一个从HTTP/1.1到其它不兼容协议的简单迁移机制。这通过允
许客户端告诉服务器客户端期望利用另一种协议，例如主版本号更高的最新HTTP协议，即使
当前请求仍然使用HTTP/1.1。这能降低不兼容协议之间迁移的难度，只需要客户端以一个更普
遍被支持协议发起一个请求，同时告诉服务器客户端想利用“更好的”协议如果可以的话
（“更好的”由服务器决定，可能根据方法和/或请求资源的性质决定）。
Upgrade头域只能应用于应用程序层（application –layer）协议之间的切换，应用程序层协议
在传输层（transport-layer）连接之上。Upgrade头域并不意味着协议一定要改变；并且服务器
接受和使用是可选的。在协议改变后应用程序层（apllication-layer）的通信能力和性质，完全
依赖于新协议的选择，尽管在改变协议后的第一个动作必须是对初始 HTTP 请求（包含
Upgrade头域）的响应。
Upgrade头域只能应用于立即连接（immediate connection）。 因此，upgrade关键字必须被提
供在Connection头域里（见14.10节），只要Upgrade头域呈现在HTTP/1.1消息里。
"""
u"""
websocket 协议
GET /socket.io/?EIO=3&transport=websocket&sid=cpfS_eqI0SAR9R1CKAyO HTTP/1.1
Host: slack-io.socket.io
Connection: Upgrade
Pragma: no-cache
Cache-Control: no-cache
Upgrade: websocket
Origin: http://socket.io
Sec-WebSocket-Version: 13
DNT: 1
User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/44.0.2403.155 Safari/537.36
Accept-Encoding: gzip, deflate, sdch
Accept-Language: zh-CN,zh;q=0.8
Cookie: io=cpfS_eqI0SAR9R1CKAyO; __utmt=1; __utma=196034734.2078174180.1439598898.1439598898.1439598898.1; __utmb=196034734.1.10.1439598898; __utmc=196034734; __utmz=196034734.1439598898.1.1.utmcsr=(direct)|utmccn=(direct)|utmcmd=(none)
Sec-WebSocket-Key: dTf+3WZUeKBE2iRBqbqTJQ==
Sec-WebSocket-Extensions: permessage-deflate; client_max_window_bits

HTTP/1.1 101 Switching Protocols
Server: nginx/1.5.11
Date: Sat, 15 Aug 2015 00:35:33 GMT
Connection: upgrade
Upgrade: websocket
Sec-WebSocket-Accept: BGP2BW8CHCnvZFxexjtJa8IyQzw=

..............3probe....R....p...sG....

"""

u"""
Via常用头域必须被网关（gateways）和代理（proxies）使用，用来指明在用户代理和服务器
之间关于请求的中间协议和接收者，和在源服务器和客户端之间关于响应的中间协议和接收者。
它和RFC822[9]里的“Received”头域相似，并且它用于跟踪消息的转发，避免请求循环，和
指定沿着请求/响应链的所有发送者的协议能力。
"""
u"""

3.6.1 块传输编码（Chunked Transfer Coding）
块编码（chunked encoding）改变消息主体使消息主体（message body）成块发送。 每一个块
有它自己的大小（size）指示器，在所有的块之后会紧接着一个可选的包含实体头域的尾部
（trailer）。这种编码允许发送端能动态生成内容，并能携带能让接收端判断消息是否接收完整
的有用信息。
       Chunked-Body（块正文）   = *chunk（块）
                                 last-chunk（最后块）
                              trailer（尾部）
                             CRLF
       chunk（块）          = chunk-size [ chunk-extension ] CRLF
                         chunk-data CRLF
       chunk-size     = 1*HEX
       last-chunk     = 1*（"0"） [ chunk-extension ] CRLF
       chunk-extension= *（ ";" chunk-ext-name [ "=" chunk-ext-val ] ）
       chunk-ext-name = token
       chunk-ext-val  = token | quoted-string
       chunk-data     = chunk-size（OCTET）
       trailer        = *（entity-header CRLF）
chunk-size是用16 进制数字字符串。 块编码（chunked encoding）以大小为0的块结束，紧接
着是尾部（trailer），尾部以一个空行终止。

尾部（trailer）允许发送端在消息的末尾包含额外的HTTP头域（header field）。Trailer头域
（Trailer header field，在 14.40 节阐述）来指明哪些头域被包含在块传输编码的尾部
（trailer） （见14.40节）

如果服务器要使用块传输编码进行响应，除非以下至少一条为真时它才能包含尾部
（trailer）：
a）如果此响应的对应请求包括一个 TE头域，并且利用 “trailers”指明了块传输编码响应的尾
部是可以接受的（TE头域在14.39节中描述；或者
 b）如果是源服务器进行响应，响应里trailer字段里全部包含的是可选的元信息，并且接收端
接收此块传输编码响应时可能不会理会响应的尾部（以一种源服务器是可以接受的方式）。换
句话说，源服务器原意接受尾部（trailer）可能会在到达客户端时被丢弃的可能性。

当消息被一个HTTP/1.1（或更高版本）的代理（proxy）接收并转发到一个HTTP/1.0接收端
的时候，此要求防止了一种互操作性的失败。

在附录19.4.6节介绍了一个例子，这个例子介绍怎样对一个块主体（chunked-body）进行解
码。
所有HTTP/1.1应用程序必须能接收和解码以块（chunked）传输编码进行编码的消息主体，
并且必须能忽略它们不能理解的块扩展（chunk-extentsion）。"""
# HTTP 权威指南 400 / 722 分块编码规则。

import urlparse

try:
    from io import BytesIO
except ImportError:
    try:
        from cStringIO import StringIO as BytesIO
    except ImportError:
        from StringIO import StringIO as BytesIO


class HttpLengthBody():
    u""" http 实体类(Length 类型、同时支持关闭连接类型)

头部空行结束后就是实体，实体直接按长度结束，结束时并没有多余的换行。
    """

    def __init__(self, sock=None, length=None):
        u"""初始化"""
        if sock:
            self.sock = sock
        else:
            self.sock = BytesIO()
        self.length = length
        self.readed_length = 0

    def _recv(self, size):
        if hasattr(self.sock, "recv"):
            return self.sock.recv(size)
        else:
            return self.sock.read(size)

    def recv(self, size):
        u"""读取

正常结束时返回空，非正常结束(连接断开)时引发异常。
        """
        if self.length is None:
            return self._recv(size)
        else:
            assert self.readed_length <= self.length

            if self.readed_length == self.length:
                return b""
            else:
                remain_length = self.length - self.readed_length

                if size > remain_length:
                    size = remain_length

                data = self.recv(size)
                self.readed_length += len(data)

                if not data and size != 0:
                    raise Exception(u'连接异常关闭，数据未全部传输完成！')
                
                return data

class HttpChunkedOriginalBody():
    u"""chunked 格式原始 body

包含块的头部及内容。"""

    def __init__(self, sock=None):
        u"""初始化"""
        if sock:
            self.sock = sock
        else:
            self.sock = BytesIO()
        self.chunked_length = None
        self.readed_length = 0

    def _recv(self, size):
        if hasattr(self.sock, "recv"):
            return self.sock.recv(size)
        else:
            return self.sock.read(size)

    def recv(self, size):
        u"""读取

正常结束时返回空，非正常结束(连接断开)时引发异常。
        """
        if self.length is None:
            return self._recv(size)
        else:
            assert self.readed_length <= self.length

            if self.readed_length == self.length:
                return b""
            else:
                remain_length = self.length - self.readed_length

                if size > remain_length:
                    size = remain_length

                data = self.recv(size)
                self.readed_length += len(data)

                if not data and size != 0:
                    raise Exception(u'连接异常关闭，数据未全部传输完成！')

                return data



class HttpBase():
    u""""""

    def __init__(self, sock):
        self.sock = sock


class HttpRequest(HttpBase):
    u""" HTTP 请求类 """

    def __init__(self, sock=None):
        u"""如果存在 sock ，那么自动根据sock内容生成请求

注意，通过sock生成时只处理一个请求，调用方可以在本请求结束时再次创建新的 HttpRequest 处理下一个请求。
        """
        HttpBase.__init__(self, sock)
        self.command = ''
        self.request_version = "HTTP/1.1"
        self.path = ''
        self.host = ''  # 包含主机名及端口号
        self.close_connection = True
        self.scheme = 'http'
        # 实体长度判断规则将开头文档
        self.content_length = None  # 存在 content-length 头则为int类型的实体长度，否则为None
        self.body_chunked = False

    def _parse_request_head(self):
        raw_requestline = self.sock.readline(65537)
        if len(raw_requestline) > 65536:
            # TODO: 过长
            raise Exception()
        raw_requestline = raw_requestline.rstrip('\r\n')
        words = raw_requestline.split()
        if len(words) == 2:
            # http 0.9
            self.request_version = "HTTP/0.9"
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

        conntype = self.headers.get('Connection', '')
        conntype = self.headers.get('Proxy-Connection', conntype).lower()
        conntypes = (t.strip() for t in conntype.split(","))

        # 作为代理时需要删除 Connection 指定的头
        # 详见 HTTP协议RFC2616 14.10
        for t in conntypes:
            if self.headers.has_key(t):
                del self.headers[t]

        if 'close' in conntypes:
            self.close_connection = True
        elif 'keep-alive' in conntypes:
            self.close_connection = False

        # 防止协议被升级为 http2
        if self.headers.has_key('upgrade'):
            del self.headers['upgrade']

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

        if self.headers.has_key('Content-Length'):
            self.content_length = int(self.headers.get('Content-Length'))

        tr_enc = self.headers.get('transfer-encoding', '').lower()
        # Don't incur the penalty of creating a list and then discarding it
        encodings = (enc.strip() for enc in tr_enc.split(","))
        if "chunked" in encodings:
            self.body_chunked = True

        # TODO 未处理 post 存在请求实体的情况。

        return True

    pass


class HttpResponse(HttpBase):
    pass
