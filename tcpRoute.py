#!/usr/bin/python
# -*- coding: utf-8 -*-
# utf-8 中文编码

u''' TCP 路由器

TCP 路由器会自动选择最快的线路转发TCP连接。
通过 socks5 代理服务器提供服务。目前支持直连及 socks5 代理线路。

具体细节：
    1.对 DNS 解析获得的多个IP同时尝试连接，最终使用最快建立的连接。
    2.同时使用直连及代理建立连接，最终使用最快建立的连接。
    3.缓存10分钟上次检测到的最快线路方便以后使用。
    4.不使用异常的dns解析结果。

'''

# 参考了 https://github.com/felix021/ssocks5/blob/master/msocks5.py

import sys
stdout = sys.stdout
reload(sys)
sys.stdout = stdout


import json
import os
import sys
import struct
import signal
import threading
import time
import logging
import traceback
from LRUCacheDict import LRUCacheDict

try:
    import gevent
    from gevent import socket
    from gevent.server import StreamServer
    from gevent.pool import Group
except:
    print >>sys.stderr, "please install gevent first!"
    sys.exit(1)

try:
    import dns.resolver
except:
    print >>sys.stderr, 'please install dnspython !'

# 悲剧，windows python 3.4 才支持 ipv6 的 inet_ntop
# https://bugs.python.org/issue7171
if not socket.__dict__.has_key('inet_ntop'):
    from win_inet_pton import inet_ntop
    socket.inet_ntop = inet_ntop
if not socket.__dict__.has_key("inet_pton"):
    from win_inet_pton import inet_pton
    socket.inet_pton = inet_pton

logging.basicConfig(level=logging.INFO)

basedir = os.path.dirname(os.path.abspath(__file__))


getaddrinfoLock = threading.Lock()
def getaddrinfo(hostname,port):
    global errIP
    try:
        for i in range(5):
            res = socket.getaddrinfo(hostname, port,0,socket.SOCK_STREAM,socket.IPPROTO_TCP)
            with getaddrinfoLock:
                for r in res:
                    if not errIP.has_key(r[4][0]):
                        return res
                    else:
                        logging.info('[DNS]%s(%s) ip is errIP !'%(hostname,r[4][0]))
                        break
    except socket.gaierror as e:
        pass
    return []

def getAddrinfoLoop():
    try:
        import dns.resolver
    except:
        return
    while True:
        logging.info('errIP loop start')
        global errIP
        _errIP = {}

        for i in range(5):
            res=[]
            try:
                res = socket.getaddrinfo('asgdgksjiyrsdfgvsydsaunsbfyiobsnalnalnv%s.com'%i, port,0,socket.SOCK_STREAM,socket.IPPROTO_TCP)
            except:
                pass
            for r in res:
                 _errIP[r[4][0]] = int(time.time()*1000)
            time.sleep(0.3)
        with getaddrinfoLock:
             errIP=_errIP.copy()
        logging.info('errIP-1:\r\n' + '\r\n'.join(errIP))

        m = dns.resolver.Resolver()
        m.nameservers=['8.8.8.123',]
        for i in range(100):
            for a in m.query('twitter.com').response.answer:
                for r in a:
                    _errIP[r.address]=int(time.time()*1000)
            time.sleep(0.1)
        with getaddrinfoLock:
             errIP=_errIP.copy()
        logging.info('errIP-all:\r\n' + '\r\n'.join(errIP))

        time.sleep(1*60*60)


# 源客户端
class SClient:
    u'''每个代理请求会生成一个源客户端。'''
    def __init__(self,server,conn, address):
        self.server =server
        self.conn =conn
        self.sAddress = address
        self.connected = False

    def unpack(self, fmt):
        length = struct.calcsize(fmt)
        data = self.conn.recv(length)
        if len(data) < length:
            raise Exception("SClient.unpack: bad formatted stream")
        return struct.unpack(fmt, data)

    def pack(self, fmt, *args):
        data = struct.pack(fmt, *args)
        return self.conn.sendall(data)

    def handle(self):

        # 获得请求并发出新的请求。
        (ver,) = self.unpack('B')
        if ver ==0x05:
            # socks5 协议
            logging.debug('Receive socks5 protocol header')
            self.socks5Handle(ver)
        elif chr(ver) in 'GgPpHhDdTtCcOo':
            # 误被当作 http 代理
            logging.error('Receive http header')
            self.httpHandle(ver)
        else:
            # 未知的类型，以 socks5 协议拒绝
            logging.error('Receive an unknown protocol header')
            self.pack('BB',0x05,0xff)

    def isConnected(self):
        u''' 是否已连接到远程
如果已连接就不会再次通过新的代理服务器尝试建立连接。 '''
        return self.connected
    def setConnected(self,value):
        self.connected = value


    def socks5Handle(self,head):
        # 鉴定
        (nmethods,) = self.unpack('B')
        if nmethods>0:
            (methods,) = self.unpack('B'*nmethods)
            #TODO: 未检查客户端支持的鉴定方式
        self.pack('BB',0x05,0x00)
        logging.debug('client login')

        # 接收代理请求
        ver,cmd,rsv,atyp = self.unpack('BBBB')

        if ver != 0x05 or cmd != 0x01:
            logging.error(u'[SClient]收到未知类型的请求，关闭连接。 ver=%s ,cmd=%s'%(ver,cmd))
            self.pack('BBBBIH',0x05, 0x07, 0x00, 0x01, 0, 0)
            gevent.sleep(3)
            self.conn.close()
            return

        if atyp == 0x01:
            # ipv4
            host,port = self.unpack('!IH')
            hostname = socket.inet_ntoa(struct.pack('!I', host))
        elif atyp == 0x03:
            # 域名
            length = self.unpack('B')[0]
            hostname, port = self.unpack("!%dsH" % length)
        elif atyp == 0x04:
            # ipv6
            ipv61 ,ipv62,port = self.unpack('!2QH')
            hostname = socket.inet_ntop(socket.AF_INET6, struct.pack('!2Q', ipv61, ipv62))
        else:
            logging.error(u'[SClient]收到未知的目的地址类型，关闭连接。 atyp=%s '%(atyp))
            self.pack('!BBBBIH', 0x05, 0x07, 0x00, 0x01, 0, 0)
            gevent.sleep(3)
            self.conn.close()
            return
        logging.debug('[SClient] host:%s   prot:%s'%(hostname,port))

        # 对外发起请求

        proxyDict = self.server.getProxyCache(hostname,port,None)
        if proxyDict:
            proxyList = sorted(proxyDict.values(),key=lambda x:x['tcpping'])
            proxyName = proxyList[0]['proxyName']
            hitIp = proxyList[0]['hitIp']
            proxy = self.server.getProxy(proxyName)
            if proxy:
                logging.debug('[Cache] hit host:%s ,prot:%s ,proxy:%s ,ip:%s'%(hostname,port,proxy.getName(),hitIp))
                proxy.forward(self,atyp,hostname,port,3,hitIp)
        if not self.connected:
            # 不管是没有缓存记录还是没连接上，都使用全部链接做一次测试。
            logging.debug('[all proxt]  host:%s ,prot:%s '%(hostname,port))
            group = Group()
            for proxy in self.server.getProxy():
                # 启动多个代理进行转发尝试
                # 最先成功的会执行转发，之后成功的会自动退出。
                group.add(gevent.spawn(proxy.forward,self,atyp,hostname,port,30))
            group.join()
        if not self.connected:
            logging.info(u'[SClient]无法连接到目的主机，关闭连接。 hostname=%s ，port=%s '%(hostname,port))
            self.pack('!BBBBIH', 0x05, 0x03, 0x00, 0x01, 0, port)
        gevent.sleep(5)
        self.conn.close()




    def httpHandle(self,head):
        self.conn.sendall('''HTTP/1.1 200 OK
Content-Type:text/html; charset=utf-8

<h1>http proxy is not supported</h1>
http proxy is not supported, Only support socks5.''')
        gevent.sleep(5)
        self.conn.close()






class DirectProxy():
    u'''直接连接'''
    def forward(self,sClient,atyp,hostname,port,timeout=socket._GLOBAL_DEFAULT_TIMEOUT,ip=None):
        u'''阻塞调用，'''
        logging.debug('DirectProxy.forward(atyp=%s,hostname=%s,port=%s,timeout=%s,ip=%s)'%(atyp,hostname,port,timeout,ip))
        addrinfoList = getaddrinfo(hostname,port)
        logging.debug('[DNS]resolution name:%s\r\n'%hostname+'\r\n'.join([('IP:%s'%addrin[4][0]) for addrin in addrinfoList]))
        group = Group()
        if ip in [addrin[4][0] for addrin in addrinfoList]:
            group.add(gevent.spawn(self.__forward,sClient,(ip,port),hostname,timeout))
            logging.debug('cache ip hit Domain=%s ip=%s '%(hostname,ip))
        else:
            for addrinfo in addrinfoList:
                # 启动多个代理进行转发尝试
                # 最先成功的会执行转发，之后成功的会自动退出。
                group.add(gevent.spawn(self.__forward,sClient,addrinfo[4],hostname,timeout))
        group.join()

    def __forward(self,sClient,addr,hostname,timeout=socket._GLOBAL_DEFAULT_TIMEOUT):
        ip = addr[0]
        port = addr[1]
        logging.debug('DirectProxy.__forward(hostname=%s,ip=%s,port=%s,timeout=%s)'%(hostname,ip,port,timeout))
        startTime = int(time.time()*1000)
        try:
            s = socket.create_connection(addr,timeout)
        except:
            #TODO: 处理下连接失败
            info = traceback.format_exc()
            logging.debug(u'[DirectProxy]直连失败。 hostname:%s ,ip:%s ,port:%s ,timeout:%s'%(hostname,addr[0],addr[1],timeout))
            logging.debug('%s\r\n\r\n'%info)
            return
        # 直连的话直接链接到服务器就可以，
        # 如果是 socks5 代理，时间统计需要包含远端代理服务器连接到远端服务器的时间。
        sClient.server.upProxyPing(self.getName(),hostname,addr[1],int(time.time()*1000)-startTime,addr[0])
        if not sClient.connected:
            # 第一个连接上的
            logging.debug('[DirectProxy] Connection hit (hostname=%s,ip=%s,port=%s,timeout=%s)'%(hostname,addr[0],addr[1],timeout))
            sClient.connected=True

            # 为了应付长连接推送，超时设置的长点。
            s.settimeout(10*60)
            sClient.conn.settimeout(10*60)

            #TODO: 按照socks5协议，这里应该返回服务器绑定的地址及端口
            # http://blog.csdn.net/testcs_dn/article/details/7915505
            sClient.pack('!BBBBIH', 0x05, 0x00, 0x00, 0x01, 0, 0)


            # 第一个连接上的，执行转发
            group = Group()
            group.add(gevent.spawn(self.__forwardData,sClient.conn,s))
            group.add(gevent.spawn(self.__forwardData,s,sClient.conn))
            group.join()
        else:
            # 不是第一个连接上的
            s.close()
            logging.debug('[DirectProxy] Connection miss (hostname=%s,ip=%s,port=%s,timeout=%s)'%(hostname,addr[0],addr[1],timeout))


    def __forwardData(self,s,d):
        try:
            while True:
                data=s.recv(1024)
                if not data:
                    break
                d.sendall(data)
        except Exception as e :
            if e.errno == 9:
                # 另一个协程关闭了链接。
                pass
            else:
                logging.exception('DirectProxy.__forwardData')
        finally:
            # 这里 和 socks5 Handle 会重复关闭
            logging.debug('DirectProxy.__forwardData  finally')
            gevent.sleep(5)
            s.close()
            d.close()


    def getName(self):
        u'''代理唯一名称
需要保证唯一性，建议使用 socks5-proxyhost:port 为代理名称。
'''
        return 'direct'



class Socks5Proxy():
    u'''socks5'''
    def __init__(self,host,port):
        self.host = host
        self.port =port

    @staticmethod
    def unpack(s, fmt):
        length = struct.calcsize(fmt)
        data = s.recv(length)
        if len(data) < length:
            raise Exception("SClient.unpack: bad formatted stream")
        return struct.unpack(fmt, data)

    @staticmethod
    def pack(s, fmt, *args):
        data = struct.pack(fmt, *args)
        return s.sendall(data)

    def forward(self,sClient,atyp,hostname,port,timeout=socket._GLOBAL_DEFAULT_TIMEOUT,ip=None):
        u'''阻塞调用，'''
        logging.debug('socks5Proxy.forward(atyp=%s,hostname=%s,port=%s,timeout=%s,ip=%s)'%(atyp,hostname,port,timeout,ip))

        self.__forward(sClient,atyp,hostname,port,timeout)

    def __forward(self,sClient,atyp,hostname,port,timeout=socket._GLOBAL_DEFAULT_TIMEOUT):
        startTime = int(time.time()*1000)
        try:
            s = socket.create_connection((self.host,self.port),timeout)
        except:
            #TODO: 处理下连接失败
            info = traceback.format_exc()
            logging.error(u'[socks5] 连接代理服务器失败！ host:%s ,port:%s ,timeout:%s'%(self.host,self.port,timeout,))
            logging.error('%s\r\n\r\n'%info)

            return

        logging.debug(u'[socks5]代理服务器已连接  host:%s ,port:%s ,timeout:%s'%(self.host,self.port,timeout))

        # 登录
        Socks5Proxy.pack(s,'BBB',0x05,0x01,0x00)

        # 登录回应
        ver,method = Socks5Proxy.unpack(s,'BB')
        if ver != 0x05 or method != 0x00:
            logging.error(u'[socks5]代理服务器登录失败！ host:%s ,port:%s'%(self.host,self.port))
            s.close()
            return
        logging.debug(u'[socks5]代理服务器登陆成功。 host:%s ,port:%s'%(self.host,self.port))

        # 请求连接
        Socks5Proxy.pack(s,'!BBBB',0x05,0x01,0x00,atyp)
        if atyp == 0x01:
            #ipv4
            Socks5Proxy.pack(s,'!IH',socket.inet_aton(hostname),port)
        elif atyp == 0x03:
            # 域名
            Socks5Proxy.pack(s,'!B%ssH'%len(hostname),len(hostname),hostname,port)
        elif atyp == 0x04:
            # ipv6
            _str = socket.inet_pton(socket.AF_INET6, hostname)
            a, b = struct.unpack('!2Q', _str)
            Socks5Proxy.pack(s,'!2QH',a,b,port)
        else:
            logging.error(u'[socks5]代理服务器绑定地址类型未知！ atyp:%s'%atyp)
            s.close()
            return

        # 请求回应
        ver,rep,rsv,atyp = Socks5Proxy.unpack(s,'BBBB')
        if ver != 0x05 or rep != 0x00:
            logging.error(u'[socks5]代理服务器无法连接目标网站！ ver:%s ,rep:%s'%(ver,rep))
            s.close()
            return

        if atyp == 0x01:
            Socks5Proxy.unpack(s,'!IH')
        elif atyp == 0x03:
            length = Socks5Proxy.unpack(s,'B')
            Socks5Proxy.unpack(s,'%ssH'%length)
        elif atyp == 0x04:
            Socks5Proxy.unpack(s,'!2QH')

        # 直连的话连接建立就可以了
        # 如果是 socks5 代理，时间统计需要包含远端代理服务器连接到远端服务器的时间。
        sClient.server.upProxyPing(self.getName(),hostname,port,int(time.time()*1000)-startTime,None)
        if not sClient.connected:
            # 第一个连接上的
            logging.debug('[socks5Proxy] Connection hit (%s,%s,%s,%s)'%(hostname,atyp,port,timeout))

            sClient.connected=True

            # 为了应付长连接推送，超时设置的长点。
            s.settimeout(10*60)
            sClient.conn.settimeout(10*60)

            #TODO: 按照socks5协议，这里应该返回服务器绑定的地址及端口
            # http://blog.csdn.net/testcs_dn/article/details/7915505
            sClient.pack('!BBBBIH', 0x05, 0x00, 0x00, 0x01, 0, 0)
            # 第一个连接上的，执行转发
            group = Group()
            group.add(gevent.spawn(self.__forwardData,sClient.conn,s))
            group.add(gevent.spawn(self.__forwardData,s,sClient.conn))
            group.join()
        else:
            # 不是第一个连接上的
            s.close()
            logging.debug('[socks5Proxy] Connection miss (%s,%s,%s,%s)'%(hostname,atyp,port,timeout))

    def __forwardData(self,s,d):
        try:
            while True:
                data=s.recv(1024)
                if not data:
                    break
                d.sendall(data)
        except Exception as e :
            if e.errno ==9:
                # 另一个协程关闭了链接。
                pass
            else:
                logging.exception('socks5Proxy.__forwardData')
        finally:
            # 这里 和 socks5Handle 会重复关闭
            logging.debug('socks5Proxy.__forwardData close()')
            gevent.sleep(5)
            s.close()
            d.close()


    def getName(self):
        u'''代理唯一名称
需要保证唯一性，建议使用 socks5-proxyhost:port 为代理名称。
'''
        return 'socks5-%s:%s'%(self.host,self.port)


class SocksServer(StreamServer):

    def __init__(self, listener):
        StreamServer.__init__(self, listener)
        self.proxyDict={}
        self.addProxy(DirectProxy())
        # 路由缓存格式
        # {
        #   %s-%s-%s'%(atyp,hostname,port) :
        #   {
        #       proxyName:
        #       {
        #           'tcpping':starTime - time()*1000,
        #           'proxyName': proxy.getName(),
        #           'hitIp' : '115.239.210.27'命中IP，在代理支持的情况下会使用。
        #       },
        #   }

        # }
        self.routeCache = LRUCacheDict(500,10*60*1000)

    def addProxy(self,proxy):
        logging.info('addProxy %s'%proxy.getName())
        self.proxyDict[proxy.getName()]=proxy

    def getProxy(self,name=None,default=None):
        if name:
            return self.proxyDict.get(name,default)
        else:
            return self.proxyDict.values()

    def getProxyCache(self,hostname,port,default=None):
        return self.routeCache.get('%s-%s'%(hostname,port),default)

    def __setProxyCache(self,hostname,port,value):
        self.routeCache['%s-%s'%(hostname,port)]=value

    def upProxyPing(self,proxyName,hostname,port,ping,ip):
        proxyDict = self.getProxyCache(hostname,port)
        if proxyDict==None:
            proxyDict = { }
            self.__setProxyCache(hostname,port,proxyDict)

        proxyDict[proxyName]={
                                'tcpping':ping,
                                'proxyName':proxyName,
                                'hitIp':ip
                            }

    def handle(self, sock, addr):
        logging.debug('connection from %s:%s' % addr)

        client = SClient(self,sock,addr)
        try:
            client.handle()
        except:
            logging.exception('client.handle()')
            client.conn.close()

    def close(self):
        logging.info('exit')
        sys.exit(0)

    @staticmethod
    def start_server(port):
        global errIP
        errIP = {}

        threading.Thread(target=getAddrinfoLoop).start()

        server = SocksServer(('0.0.0.0', port))
        try:
            with open(os.path.join(basedir,"config.json"),'rb') as f:
                config = json.load(f,encoding="utf-8")
            for proxy in config['proxyList']:
                if proxy['type'] == 'socks5':
                    server.addProxy(Socks5Proxy(proxy['host'],proxy['port']))
                else:
                    logging.error(u'[config] 未知的代理类型。type=%s'%proxy['type'])
        except:
            logging.exception('[config]配置错误！。')
            return

        gevent.signal(signal.SIGTERM, server.close)
        gevent.signal(signal.SIGINT, server.close)
        logging.info("Server is listening on 0.0.0.0:%d" % port)
        server.serve_forever()

if __name__ == '__main__':
    import sys
    port = 7070
    if len(sys.argv) > 1:
        port = int(sys.argv[1])
    SocksServer.start_server(port)
