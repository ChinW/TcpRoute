#!/usr/bin/python
# -*- coding: utf-8 -*-
# utf-8 中文编码

u''' DNS 部分，主要的方案有：

通过系统解析
通过指定dns解析(udp、tcp)
通过 upstream 转发解析。
 '''
import logging
import traceback
from gevent import socket
import gevent
import time
import re
from gevent.threadpool import ThreadPool
import sys
from LRUCacheDict import lru_cache

try:
    import dns.resolver
    import dns.rdtypes.IN.A
    import dns.rdtypes.IN.AAAA
    import dns.rdtypes.ANY.CNAME
except:
    print >>sys.stderr, 'please install dnspython !'
    sys.exit(1)

ATYP_IPV4 = 0x01
ATYP_DOMAINNAME = 0x03
ATYP_IPV6 = 0x04

RE_IPV4_ADDR = re.compile(r'^((25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(25[0-5]|2[0-4]\d|[01]?\d\d?)$')
RE_IPV6_ADDR = re.compile(
    r'^\s*((([0-9A-Fa-f]{1,4}:){7}([0-9A-Fa-f]{1,4}|:))|(([0-9A-Fa-f]{1,4}:){6}(:[0-9A-Fa-f]{1,4}|((25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3})|:))|(([0-9A-Fa-f]{1,4}:){5}(((:[0-9A-Fa-f]{1,4}){1,2})|:((25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3})|:))|(([0-9A-Fa-f]{1,4}:){4}(((:[0-9A-Fa-f]{1,4}){1,3})|((:[0-9A-Fa-f]{1,4})?:((25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}))|:))|(([0-9A-Fa-f]{1,4}:){3}(((:[0-9A-Fa-f]{1,4}){1,4})|((:[0-9A-Fa-f]{1,4}){0,2}:((25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}))|:))|(([0-9A-Fa-f]{1,4}:){2}(((:[0-9A-Fa-f]{1,4}){1,5})|((:[0-9A-Fa-f]{1,4}){0,3}:((25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}))|:))|(([0-9A-Fa-f]{1,4}:){1}(((:[0-9A-Fa-f]{1,4}){1,6})|((:[0-9A-Fa-f]{1,4}){0,4}:((25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}))|:))|(:(((:[0-9A-Fa-f]{1,4}){1,7})|((:[0-9A-Fa-f]{1,4}){0,5}:((25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)(\.(25[0-5]|2[0-4]\d|1\d\d|[1-9]?\d)){3}))|:)))(%.+)?\s*$')

dnsPool = ThreadPool(20)
configIpBlacklist = []
errIP = {}
nameservers = 'system'
nameservers_backup = ['8.8.8.8', '208.67.222.222']


def get_addr_type(addr):
    u""" 分析地址类型(IPv4、IPv6、域名)
>>> get_addr_type('0.0.0.0') == ATYP_IPV4
True
>>> get_addr_type('255.255.255.255') == ATYP_IPV4
True
>>> get_addr_type('1.1.1.256') == ATYP_IPV4
False
>>> get_addr_type('1.1.0') == ATYP_IPV4
False
>>> get_addr_type('192.168.1.1') == ATYP_IPV4
True
>>> get_addr_type('fe80:0000:0000:0000:0204:61ff:fe9d:f156') == ATYP_IPV6
True
>>> get_addr_type('fe80:0:0:0:204:61ff:fe9d:f156') == ATYP_IPV6
True
>>> get_addr_type('fe80::204:61ff:fe9d:f156') == ATYP_IPV6
True
>>> get_addr_type('fe80:0000:0000:0000:0204:61ff:254.157.241.86') == ATYP_IPV6
True
>>> get_addr_type('fe80:0:0:0:0204:61ff:254.157.241.86') == ATYP_IPV6
True
>>> get_addr_type('fe80::204:61ff:254.157.241.86') == ATYP_IPV6
True
>>> get_addr_type('::1') == ATYP_IPV6
True
>>> get_addr_type('fe80::') == ATYP_IPV6
True
>>> get_addr_type('2001::') == ATYP_IPV6
True
>>> get_addr_type('2001::99999') == ATYP_DOMAINNAME
True
>>> get_addr_type('2001:101@192.168.1.1') == ATYP_DOMAINNAME
True
>>> get_addr_type('www.google.com') == ATYP_DOMAINNAME
True
>>> get_addr_type('abc') == ATYP_DOMAINNAME
True
    """
    if RE_IPV4_ADDR.match(addr):
        return ATYP_IPV4
    elif RE_IPV6_ADDR.match(addr):
        return ATYP_IPV6
    else:
        return ATYP_DOMAINNAME


if __name__ == "__main__":
    import doctest

    doctest.testmod()


@lru_cache(500, 10 * 60 * 1000, lock=None)
def dnsQuery(hostname):
    global errIP

    ipList = _dnsQuery(hostname, nameservers)

    for ip in ipList:
        if ip in errIP:
            # 解析异常，清空解析结果
            logging.info(u'[DNS]默认解析服务器解析到异常IP，hostname=%s ，ip=%s ,nameserver=%s' % (hostname, ip, nameservers))
            ipList = []
            break

    if not ipList:
        # 无解析结果时使用备用服务器重新解析
        for i in range(4):
            tcp = bool((i + 1) % 2)  # 间隔使用 TCP 协议查询
            ipList = _dnsQuery(hostname, nameservers_backup, tcp)
            for ip in ipList:
                if ip in errIP:
                    ipList = []
                    logging.info(u'[DNS]备用解析服务器解析得到异常IP(%s)，hostname=%s ，ip=%s ,nameserver=%s,TCP=%s' % (
                        i, hostname, ip, nameservers_backup, tcp))
                    break
            if ipList:
                logging.debug(u'[DNS]备用解析服务器解析成功(%s)，hostname=%s ，ip=%s ,nameserver=%s,TCP=%s' % (
                    i, hostname, ipList, nameservers_backup, tcp))
                return ipList
            else:
                logging.info(
                    u'[DNS]备用解析服务器解析失败(%s)，hostname=%s ，nameserver=%s,TCP=%s' % (i, hostname, nameservers_backup, tcp))

    else:
        logging.debug(u'[DNS]默认解析服务器解析成功，hostname=%s ，ip=%s ,nameserver=%s' % (hostname, ipList, nameservers))

    if not ipList:
        logging.warn(u'[DNS]默认及备用解析服务器解析失败，hostname=%s ，ip=%s ,nameserver=%s ,nameserversBackup=%s' % (
            hostname, ipList, nameservers, nameservers_backup))

    return ipList


def _dnsQuery(hostname, serveListr='system', tcp=False):
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
            res = socket.getaddrinfo(hostname, 80, 0, socket.SOCK_STREAM, socket.IPPROTO_TCP)
            return [r[4][0] for r in res]
        except Exception:
            info = traceback.format_exc()
            logging.debug(u'[DNS][_dnsQuery][socket.getaddrinfo] 解析失败，host=%s 详细信息：' % hostname)
            logging.debug('%s\r\n\r\n' % info)
            return []
    else:
        t = dnsPool.spawn(_dnspythonQuery, hostname, serveListr, tcp)
        return t.get(True)


def _dnspythonQuery(hostname, serveListr, tcp=False):
    try:
        res = []
        m = dns.resolver.Resolver()

        if isinstance(serveListr, (str, unicode)):
            serveListr = [serveListr, ]

        m.nameservers = serveListr

        answerList = m.query(hostname, tcp=tcp).response.answer
        for a in answerList:
            for r in a:
                res.append(r.address)
        return res
    except:
        info = traceback.format_exc()
        logging.debug(
            u'[DNS][_dnspythonQuery][dns.resolver.query] 解析失败，host=%s ,nameserver=%s详细信息：' % (hostname, serveListr))
        logging.debug('%s\r\n\r\n' % info)
        return []


def dnsQueryLoop():
    while True:
        global errIP
        global configIpBlacklist
        _errIP = {}

        for ip in configIpBlacklist:
            _errIP[ip] = -1

        if not errIP:
            errIP.update(_errIP)

        logging.info(u'[DNS]开始采集异常解析IP...')

        # 统计所有的 DNS 服务器
        allDnsServer = set()

        if isinstance(nameservers, (str, unicode)):
            allDnsServer.add(nameservers)
        else:
            allDnsServer.update(nameservers)

        if isinstance(nameservers_backup, (str, unicode)):
            allDnsServer.add(nameservers_backup)
        else:
            allDnsServer.update(nameservers_backup)

        for i in range(3):
            for dnsServer in allDnsServer:
                ipList = _dnsQuery("sdfagdfkjvgsbyeastkisbtgvbgkjscabgfaklrv%s.com" % i, dnsServer)
                for ip in ipList:
                    logging.info(u'[DNS]采集到域名服务器(%s)域名纠错IP(%s)。' % (dnsServer, ip))
                    _errIP[ip] = int(time.time() * 1000)

        if len(errIP) == len(configIpBlacklist):
            errIP.update(_errIP)

        for i in range(100):
            ipList = _dnsQuery('twitter.com', ['8.8.8.234', '8.8.8.123', ])
            for ip in ipList:
                logging.info(u'[DNS]采集到远程异常IP(%s)。' % ip)
                _errIP[ip] = int(time.time() * 1000)
            if i % 10 == 0:
                errIP.clear()
                errIP.update(_errIP)
            gevent.sleep(1)

        errIP.clear()
        errIP.update(_errIP)

        logging.info(u'[DNS]采集到的所有异常IP为：\r\n' + '\r\n'.join(errIP))

        gevent.sleep(
* 60 * 60)

