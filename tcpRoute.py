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

感谢 https://github.com/felix021/ssocks5/blob/master/msocks5.py
'''

import os
import sys
import struct
import signal
import time
import logging
import json
import traceback
import math
from LRUCacheDict import LRUCacheDict,lru_cache

try:
    import gevent
    from gevent import socket
    from gevent.server import StreamServer
    from gevent.pool import Group
    from gevent.threadpool import ThreadPool
except:
    print >>sys.stderr, "please install gevent first!"
    sys.exit(1)

try:
    import dns.resolver
    import dns.rdtypes.IN.A
    import dns.rdtypes.IN.AAAA
    import dns.rdtypes.ANY.CNAME
except:
    print >>sys.stderr, 'please install dnspython !'
    sys.exit(1)

# 悲剧，windows python 3.4 才支持 ipv6 的 inet_ntop
# https://bugs.python.org/issue7171
if not hasattr(socket, 'inet_ntop'):
    import win_inet_pton
    socket.inet_ntop = win_inet_pton.inet_ntop
if not hasattr(socket, 'inet_pton'):
    import win_inet_pton
    socket.inet_pton = win_inet_pton.inet_pton

logging.basicConfig(level=logging.INFO)
basedir = os.path.dirname(os.path.abspath(__file__))

dnsPool = ThreadPool(20)
configIpBlacklist = []
errIP={}
nameservers = 'system'
nameserversBackup = ['8.8.8.8','208.67.222.222']

@lru_cache(500,10*60*1000,lock=None)
def dnsQuery(hostname):
    global errIP

    ipList = _dnsQuery(hostname,nameservers)

    for ip in ipList:
        if ip in errIP:
            # 解析异常，清空解析结果
            logging.info(u'[DNS]默认解析服务器解析到异常IP，hostname=%s ，ip=%s ,nameserver=%s'%(hostname,ip,nameservers))
            ipList=[]
            break

    if not ipList:
        # 无解析结果时使用备用服务器重新解析
        for i in range(4):
            tcp = bool((i+1)%2) # 间隔使用 TCP 协议查询
            ipList = _dnsQuery(hostname,nameserversBackup,tcp)
            for ip in ipList:
                if ip in errIP:
                    ipList=[]
                    logging.info(u'[DNS]备用解析服务器解析得到异常IP(%s)，hostname=%s ，ip=%s ,nameserver=%s,TCP=%s'%(i,hostname,ip,nameserversBackup,tcp))
                    break
            if ipList:
                logging.debug(u'[DNS]备用解析服务器解析成功(%s)，hostname=%s ，ip=%s ,nameserver=%s,TCP=%s'%(i,hostname,ipList,nameserversBackup,tcp))
                return ipList
            else:
                logging.info(u'[DNS]备用解析服务器解析失败(%s)，hostname=%s ，nameserver=%s,TCP=%s'%(i,hostname,nameserversBackup,tcp))

    else:
        logging.debug(u'[DNS]默认解析服务器解析成功，hostname=%s ，ip=%s ,nameserver=%s'%(hostname,ipList,nameservers))

    if not ipList:
        logging.warn(u'[DNS]默认及备用解析服务器解析失败，hostname=%s ，ip=%s ,nameserver=%s ,nameserversBackup=%s'%(hostname,ipList,nameservers,nameserversBackup))

    return ipList

def _dnsQuery(hostname,serveListr='system',tcp=False):
    u'''纯粹的查询，并没有过滤之类的功能

server:
    'system'
    '8.8.8.8'
    ['8.8.8.8','8.8.4.4']
返回值
    ['1.1.1.1','2.2.2.2']
    '''
    if serveListr == 'system':
        try:
            res = socket.getaddrinfo(hostname, 80,0,socket.SOCK_STREAM,socket.IPPROTO_TCP)
            return [r[4][0] for r in res]
        except Exception:
            info = traceback.format_exc()
            logging.debug(u'[DNS][_dnsQuery][socket.getaddrinfo] 解析失败，host=%s 详细信息：'%hostname)
            logging.debug('%s\r\n\r\n'%info)
            return []
    else:
        t = dnsPool.spawn(_dnspythonQuery,hostname,serveListr,tcp)
        return t.get(True)

def _dnspythonQuery(hostname,serveListr,tcp=False):
    try:
        res = []
        m = dns.resolver.Resolver()

        if isinstance(serveListr,(str,unicode)):
            serveListr = [serveListr,]

        m.nameservers=serveListr

        answerList = m.query(hostname,tcp=tcp).response.answer
        for a in answerList:
            for r in a:
                res.append(r.address)
        return res
    except :
        info = traceback.format_exc()
        logging.debug(u'[DNS][_dnspythonQuery][dns.resolver.query] 解析失败，host=%s ,nameserver=%s详细信息：'%(hostname,serveListr))
        logging.debug('%s\r\n\r\n'%info)
        return []

def dnsQueryLoop():
    while True:
        global  errIP
        global  configIpBlacklist
        _errIP ={}

        for ip in configIpBlacklist:
            _errIP[ip]=-1


        if not errIP:
            errIP.update(_errIP)

        logging.info(u'[DNS]开始采集异常解析IP...')

        # 统计所有的 DNS 服务器
        allDnsServer = set()

        if isinstance(nameservers,(str,unicode)):
            allDnsServer.add(nameservers)
        else:
            allDnsServer.update(nameservers)

        if isinstance(nameserversBackup,(str,unicode)):
            allDnsServer.add(nameserversBackup)
        else:
            allDnsServer.update(nameserversBackup)

        for i in range(3):
            for dnsServer in allDnsServer:
                ipList = _dnsQuery("sdfagdfkjvgsbyeastkisbtgvbgkjscabgfaklrv%s.com"%i,dnsServer)
                for ip in ipList:
                    logging.info(u'[DNS]采集到域名服务器(%s)域名纠错IP(%s)。' % (dnsServer,ip))
                    _errIP[ip] = int(time.time()*1000)


        if len(errIP) == len(configIpBlacklist):
            errIP.update(_errIP)

        for i in range(100):
            ipList = _dnsQuery('twitter.com',['8.8.8.234','8.8.8.123',])
            for ip in ipList:
                logging.info(u'[DNS]采集到远程异常IP(%s)。'%ip)
                _errIP[ip] = int(time.time()*1000)
            if i%10 == 0:
                errIP.clear()
                errIP.update(_errIP)
            gevent.sleep(1)

        errIP.clear()
        errIP.update(_errIP)

        logging.info(u'[DNS]采集到的所有异常IP为：\r\n' + '\r\n'.join(errIP))

        gevent.sleep(1*60*60)




# 源客户端
class SClient:
    u'''每个代理请求会生成一个源客户端。'''
    def __init__(self,server,conn, address):
        self.server =server
        self.conn =conn
        self.sAddress = address
        self.connected = False

        self.conn.setsockopt(socket.IPPROTO_TCP,socket.TCP_NODELAY, 1)

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
        if ver == 0x04:
            # socks4 协议
            logging.debug(u'[客户端] 协议错误，TcpRoute 不支持 socks4 协议。')
            # socks4 拒绝转发回应。
            self.pack('BBIH',0,0x5b,0,0)
        elif ver == 0x05:
            # socks5 协议
            logging.debug(u'Receive socks5 protocol header')
            self.socks5Handle(ver)
        elif chr(ver) in 'GgPpHhDdTtCcOo':
            # 误被当作 http 代理
            logging.error(u'[客户端] 协议错误，TcpRoute 不支持 http 代理协议。请修改浏览器配置，将代理服务器类型改为 socks5 。')
            self.httpHandle(ver)
        else:
            # 未知的类型，以 socks5 协议拒绝
            logging.error(u'[客户端] 未知的协议，连接关闭。')
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
            logging.warn(u'[SClient]收到未知类型的请求，关闭连接。 ver=%s ,cmd=%s'%(ver,cmd))
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
            logging.warn(u'[SClient]收到未知的目的地址类型，关闭连接。 atyp=%s '%(atyp))
            self.pack('!BBBBIH', 0x05, 0x07, 0x00, 0x01, 0, 0)
            gevent.sleep(3)
            self.conn.close()
            return
        logging.debug(u'[SClient] host:%s   prot:%s'%(hostname,port))

        # 对外发起请求

        proxyDict = self.server.getProxyCache(hostname,port,None)
        if proxyDict:
            proxyList = sorted(proxyDict.values(),key=lambda x:x['tcpping'])
            proxyName = proxyList[0]['proxyName']
            hitIp = proxyList[0]['hitIp']
            tcpping = proxyList[0]['tcpping']
            _tcpping =tcpping
            if _tcpping<=500:
                _tcpping=1000
            elif _tcpping<=3000:
                _tcpping+=1000
            else:
                _tcpping += _tcpping/2.0
            timeout = int(math.ceil(_tcpping/1000.0))

            proxy = self.server.getProxy(proxyName)
            if proxy:
                logging.debug(u'[ProxyCache] hit host:%s ,prot:%s ,proxy:%s ,ip:%s,tcpping:%s,timeout:%s'%(hostname,port,proxy.getName(),hitIp,tcpping,timeout))
                proxy.forward(self,atyp,hostname,port,timeout,hitIp)
        if not self.connected:
            # 不管是没有缓存记录还是没连接上，都使用全部链接做一次测试。
            logging.debug(u'[All Proxy]  host:%s ,prot:%s '%(hostname,port))
            group = Group()
            for proxy in self.server.getProxy():
                # 启动多个代理进行转发尝试
                # 最先成功的会执行转发，之后成功的会自动退出。
                group.add(gevent.spawn(proxy.forward,self,atyp,hostname,port,10))
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
http proxy is not supported, only support socks5.''')
        # 必须等待
        # 立刻关闭浏览器显示 ERR_CONNECTION_RESET 错误(chrome 测试)
        gevent.sleep(5)
        self.conn.close()






class DirectProxy():
    u'''直接连接'''
    def forward(self,sClient,atyp,hostname,port,timeout=socket._GLOBAL_DEFAULT_TIMEOUT,ip=None):
        u'''阻塞调用，'''
        logging.debug(u'DirectProxy.forward(atyp=%s,hostname=%s,port=%s,timeout=%s,ip=%s)'%(atyp,hostname,port,timeout,ip))
        ipList = dnsQuery(hostname)
        logging.debug(u'[DNS]resolution name:%s\r\n'%hostname+'\r\n'.join([('IP:%s'%ip) for ip in ipList]))
        group = Group()
        if ip in ipList:
            group.add(gevent.spawn(self.__forward,sClient,(ip,port),hostname,timeout))
            logging.debug(u'cache ip hit Domain=%s ip=%s '%(hostname,ip))
        else:
            for ip in ipList:
                # 启动多个代理进行转发尝试
                # 最先成功的会执行转发，之后成功的会自动退出。
                group.add(gevent.spawn(self.__forward,sClient,(ip,port),hostname,timeout))
        group.join()

    def __forward(self,sClient,addr,hostname,timeout=socket._GLOBAL_DEFAULT_TIMEOUT):
        ip = addr[0]
        port = addr[1]
        logging.debug(u'DirectProxy.__forward(hostname=%s,ip=%s,port=%s,timeout=%s)'%(hostname,ip,port,timeout))
        startTime = int(time.time()*1000)
        try:
            s = socket.create_connection(addr,timeout)
            s.setsockopt(socket.IPPROTO_TCP,socket.TCP_NODELAY, 1)
        except:
            #TODO: 处理下连接失败
            info = traceback.format_exc()
            logging.debug(u'[DirectProxy]直连失败。 hostname:%s ,ip:%s ,port:%s ,timeout:%s'%(hostname,ip,port,timeout))
            logging.debug('%s\r\n\r\n'%info)
            return
        # 直连的话直接链接到服务器就可以，
        # 如果是 socks5 代理，时间统计需要包含远端代理服务器连接到远端服务器的时间。
        tcpping = int(time.time()*1000)-startTime
        sClient.server.upProxyPing(self.getName(),hostname,addr[1],tcpping,ip)
        if not sClient.connected:
            # 第一个连接上的
            logging.debug(u'[DirectProxy] Connection hit (hostname=%s,ip=%s,port=%s,timeout=%s, tcpping=%s)'%(hostname,ip,port,timeout,tcpping))
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
            logging.debug(u'[DirectProxy] Connection miss (hostname=%s,ip=%s,port=%s,timeout=%s, tcpping=%s)'%(hostname,ip,port,timeout,tcpping))


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
            elif e.errno == 10053:
                # 远端关闭了连接
                logging.debug(u'远端关闭了连接。')
                pass
            elif e.errno == 10054:
                # 远端重置了连接
                logging.debug(u'远端重置了连接。')
                pass
            else:
                logging.exception(u'DirectProxy.__forwardData')
        finally:
            # 这里 和 socks5 Handle 会重复关闭
            logging.debug(u'DirectProxy.__forwardData  finally')
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
        logging.debug(u'socks5Proxy.forward(atyp=%s,hostname=%s,port=%s,timeout=%s,ip=%s)'%(atyp,hostname,port,timeout,ip))

        self.__forward(sClient,atyp,hostname,port,timeout)

    def __forward(self,sClient,atyp,hostname,port,timeout=socket._GLOBAL_DEFAULT_TIMEOUT):
        startTime = int(time.time()*1000)
        try:
            s = socket.create_connection((self.host,self.port),timeout)
        except:
            #TODO: 处理下连接失败
            info = traceback.format_exc()
            tcpping = int(time.time()*1000)-startTime
            logging.warn(u'[socks5] 远程代理服务器连接失败！ host:%s ,port:%s ,timeout:%s,time:%s'%(self.host,self.port,timeout,tcpping))
            logging.warn('%s\r\n\r\n'%info)

            return

        s.setsockopt(socket.IPPROTO_TCP,socket.TCP_NODELAY, 1)
        s.settimeout(timeout)
        sClient.conn.settimeout(timeout)

        tcpping = int(time.time()*1000)-startTime
        logging.debug(u'[socks5] 远程代理服务器已连接  host:%s ,port:%s ,timeout:%s,time:%s'%(self.host,self.port,timeout,tcpping))

        # 登录
        Socks5Proxy.pack(s,'BBB',0x05,0x01,0x00)

        # 登录回应
        ver,method = Socks5Proxy.unpack(s,'BB')
        tcpping = int(time.time()*1000)-startTime
        if ver != 0x05 or method != 0x00:
            logging.error(u'[socks5] 远程代理服务器登录失败！ host:%s ,port:%s, time:%s'%(self.host,self.port,tcpping))
            s.close()
            return
        logging.debug(u'[socks5] 远程代理服务器登陆成功。 host:%s ,port:%s ,time:%s'%(self.host,self.port,tcpping))

        # 请求连接
        Socks5Proxy.pack(s,'!BBBB',0x05,0x01,0x00,atyp)
        if atyp == 0x01:
            #ipv4
            Socks5Proxy.pack(s,'!IH',struct.unpack('!I',socket.inet_aton(hostname))[0],port)
        elif atyp == 0x03:
            # 域名
            Socks5Proxy.pack(s,'!B%ssH'%len(hostname),len(hostname),hostname,port)
        elif atyp == 0x04:
            # ipv6
            _str = socket.inet_pton(socket.AF_INET6, hostname)
            a, b = struct.unpack('!2Q', _str)
            Socks5Proxy.pack(s,'!2QH',a,b,port)
        else:
            tcpping = int(time.time()*1000)-startTime
            logging.warn(u'[socks5] 远程代理服务器绑定地址类型未知！ atyp:%s ,time:%s'%(atyp,tcpping))
            s.close()
            return

        # 请求回应
        ver,rep,rsv,atyp = Socks5Proxy.unpack(s,'BBBB')
        if ver != 0x05 or rep != 0x00:
            tcpping = int(time.time()*1000)-startTime
            logging.warn(u'[socks5] 远程代理服务器无法连接目标网站！ ver:%s ,rep:%s， time=%s'%(ver,rep,tcpping))
            s.close()
            return

        if atyp == 0x01:
            Socks5Proxy.unpack(s,'!IH')
        elif atyp == 0x03:
            length = Socks5Proxy.unpack(s,'B')
            Socks5Proxy.unpack(s,'%ssH'%length)
        elif atyp == 0x04:
            Socks5Proxy.unpack(s,'!2QH')

        gevent.sleep(0)
        # 直连的话连接建立就可以了
        # 如果是 socks5 代理，时间统计需要包含远端代理服务器连接到远端服务器的时间。
        tcpping = int(time.time()*1000)-startTime
        sClient.server.upProxyPing(self.getName(),hostname,port,tcpping,None)
        if not sClient.connected:
            # 第一个连接上的
            logging.debug(u'[Socks5Proxy] 连接命中 (hostname=%s,atyp=%s,port=%s,timeout=%s,tcpping=%s)'%(hostname,atyp,port,timeout,tcpping))

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
            logging.debug(u'[Socks5Proxy] 连接未命中 (hostname=%s,atyp=%s,port=%s,timeout=%s,tcpping=%s)'%(hostname,atyp,port,timeout,tcpping))

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
            elif e.errno == 10053:
                # 远端关闭了连接
                logging.debug(u'远端关闭了连接。')
                pass
            elif e.errno == 10054:
                # 远端重置了连接
                logging.debug(u'远端重置了连接。')
                pass
            else:
                logging.exception(u'socks5Proxy.__forwardData')
        finally:
            # 这里 和 socks5Handle 会重复关闭
            logging.debug(u'socks5Proxy.__forwardData close()')
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
        StreamServer.__init__(self, listener,backlog=2048,)
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

        proxyDict['%s-%s'%(proxyName,ip)]={
                                'tcpping':ping,
                                'proxyName':proxyName,
                                'hitIp':ip
                            }

    def handle(self, sock, addr):
        logging.debug(u'connection from %s:%s' % addr)

        client = SClient(self,sock,addr)
        try:
            client.handle()
        except:
            logging.exception(u'client.handle()')
            client.conn.close()

    def close(self):
        logging.info('exit')
        sys.exit(0)

    @staticmethod
    def start_server():
        global nameservers
        global nameserversBackup
        global configIpBlacklist

        try:
            with open(os.path.join(basedir,"config.json"),'rb') as f:
                config = json.load(f,encoding="utf-8")
            port = config['port']
            server = SocksServer(('0.0.0.0', port))

            configIpBlacklist = config.get('IpBlacklist',[])
            if not configIpBlacklist:
                logging.info(u'[config]不存在静态配置ip黑名单。')


            try:
                nameservers = config['nameservers']
                nameserversBackup = config['nameserversBackup']

                if  nameservers != 'system'and isinstance(nameservers,(str,unicode)):
                    nameservers = [nameservers,]

                if  nameserversBackup != 'system'and isinstance(nameserversBackup,(str,unicode)):
                    nameserversBackup = [nameserversBackup,]

            except:
                logging.exception(u'[DNS]DNS服务器配置错误！')

            for proxy in config['proxyList']:
                if proxy['type'] == 'socks5':
                    server.addProxy(Socks5Proxy(proxy['host'],proxy['port']))
                else:
                    logging.error(u'[config] 未知的代理类型。type=%s'%proxy['type'])
        except:
            logging.exception(u'[config]配置错误！。')
            return

        t = gevent.spawn(dnsQueryLoop)

        gevent.signal(signal.SIGTERM, server.close)
        gevent.signal(signal.SIGINT, server.close)
        logging.info("Server is listening on 0.0.0.0:%d" % port)
        try:
            server.serve_forever()
        except Exception as e:
            if e.errno == 10048:
                logging.error(u'%s 端口已被使用，程序退出。'%port)
                server.close()


if __name__ == '__main__':
    SocksServer.start_server()
