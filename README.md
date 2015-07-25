# TcpRoute

TCP 路由器会自动选择最快的线路转发TCP连接。

通过 socks5 代理服务器提供服务。目前支持直连及 socks5 代理线路。

## windows 安装

有二进制文件发布，直接下载 dist/tcpRoute.exe 、dist/config 修改配置并执行即可。

## linux 安装

$ sudo pip install greenlet gevent dnspython
$ vi config.json  # 修改配置
# python tcpRoute.py

## 配置

config.json 为配置文件，json格式。

port 为监听端口。目前只提供 socks5 代理服务。

nameservers 、nameserversBackup 为DNS解析服务器地址，在 nameservers 解析出错时会启用 nameserversBackup 解析。
支持过滤域名纠错，支持过滤部分DNS欺骗，在 nameservers 解析错误后会尝试 TCP DNS协议。

可选的格式：
* "system"   使用系统DNS解析
* "8.8.8.8"  使用 "8.8.8.8" 解析
* ["8.8.8.8","208.67.222.222"]   使用两个服务器进行解析

proxyList 为使用代理服务器列表，目前只支持 socks5 格式。

TcpRoute 会同时尝试使用直连及所有的代理服务器建立连接，最终使用最快建立连接的线路。

TcpRoute 会缓存检测结果方便下次使用。

IpBlacklist 为静态 ip 黑名单，黑名单上的ip不会用来建立连接(目前直连线路有效)。一般不需要配置，系统会自动检测异常ip并屏蔽。
格式为["123.123.123.123","456.456.456.456"]



## 具体细节
* 对 DNS 解析获得的多个IP同时尝试连接，最终使用最快建立的连接。
* 同时使用直连及代理建立连接，最终使用最快建立的连接。
* 缓存10分钟上次检测到的最快线路方便以后使用。
* 不使用异常的dns解析结果。

