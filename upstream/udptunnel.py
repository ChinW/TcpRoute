#!/usr/bin/python
# -*- coding: utf-8 -*-
# utf-8 中文编码
import logging
import traceback
import gevent
from gevent.pool import Group
import time
from gevent import socket as _socket
import struct

from base import UpstreamBase, ConfigError, UpstreamLoginError, UpstreamProtocolError
import dnslib
from mysocket import SocketBase


class UdpTunnelUpstream(UpstreamBase):
    u"""Udp 隧道

通过配置生成实例，实例内含 socket 类


预期 udp 承载 tcp、udp。

udp部分没什么大的问题，直接转发即可(可选加密)。

tcp部分需要考虑下了。

目前意图通过超大缓冲区来尝试解决丢包造成低速的问题。

通过 udp ping 测试显示丢包并不严重，但是延时不稳定。

单线程 tcp 下载从一开始的 10k 慢慢的升到了900k，然后又跌倒了200k左右。之后又开始上升到600k。

看情况可能是偶尔的丢包造成了 tcp 拥塞策略降速造成的问题。

如果自己通过 udp 承载 tcp ，那么拥塞控制就是自己实现了。打算通过激进的拥塞策略实现高速网络。策略是：

默认使用超大发送缓冲区，来降低偶发丢包对速度的影响。
默认直接把缓冲区的内容发送完，而不进行慢启动。
    tcp 通过控制未确认的包数量来控制速度。默认只允许1个，然后慢慢的上升。

对于大尺寸的包，既认为是流量型连接，策略是：
    定时发送确认包，间隔需要保证单次重发也不能影响整体速度，不会影响滑动窗口。

对于小尺寸的包，认为是需要低延迟的性能，策略是：
    接收方收到包后立刻回应
    发送方在 RTT*1.5 后还未收到确认既立刻重发，

现在还需要一个策略做拥赛控制，在拥塞时控制未确认的包的数量。在下列情况下认为拥塞了：
    丢包率超过一定程度
    线路测试也丢包严重(另开一个ping，ping 一个可靠的线路来确认。)

对了，还需要处理应用程序阻塞数据的情况，应用程序阻塞需要单独标记，不能和线路阻塞弄混。



理论上讲，延迟并不会影响速度。
只要在缓冲区满之前发送方能收到确认即可清理缓冲区，就不会影响影响发送的速度。

正常情况下拥塞策略是，协商确定滑动窗口大小
然后发送方将滑动窗口内的内容发送出去，如果哪部分数据长时间未收到确认就重发。
在收到确认是会动态的调整滑动窗口位置。
但当丢包时会使用拥塞窗口来代替滑动窗口。默认用赛窗口时滑动窗口的一般。。。

正常情况下造成阻塞的原因是发送出去的包或确认包丢失，使得滑动窗口无法继续向前移动，超时重发的速度就慢了。
同时拥塞控制策略还会降低滑动窗口的大小，使得发送再次暂停。

好吧，实际测试显示udp很少丢包。晚上再测试一次，确认夜间丢包现象。
暴力udpping测试显示速度能达到40M。已经很好了。

如果应付丢包的策略是重发，甚至发生严重丢包时双倍重发。
现在需要一个策略来发现是跨洋线路阻塞引起的丢包还是本地出口已满造成的。
可选的识别方案是
* 超过一定比例的丢包被认为是线路已满，需要降速。
* 另开一个测试通道，用来测试本地出口是否还有余量。








2015-08-10 13-20 udping测试
Connected to pydev debugger (build 141.1245)
ping 0 size:1400 time:330ms
ping 1 size:1400 time:313ms
ping 2 size:1400 time:314ms
ping 3 size:1400 time:314ms
ping 4 size:1400 time:312ms
5 超时
ping 6 size:1400 time:311ms
ping 7 size:1400 time:313ms
ping 8 size:1400 time:316ms
ping 9 size:1400 time:315ms
ping 10 size:1400 time:333ms
ping 11 size:1400 time:326ms
ping 12 size:1400 time:315ms
ping 13 size:1400 time:314ms
14 超时
15 超时
ping 16 size:1400 time:320ms
17 超时
ping 18 size:1400 time:310ms
ping 19 size:1400 time:314ms
ping 20 size:1400 time:305ms
ping 21 size:1400 time:305ms
ping 22 size:1400 time:338ms
ping 23 size:1400 time:322ms
ping 24 size:1400 time:311ms
ping 25 size:1400 time:312ms
ping 26 size:1400 time:322ms
ping 27 size:1400 time:338ms
ping 28 size:1400 time:334ms
ping 29 size:1400 time:313ms
ping 30 size:1400 time:311ms
ping 31 size:1400 time:305ms
ping 32 size:1400 time:303ms
ping 33 size:1400 time:306ms
ping 34 size:1400 time:336ms
ping 35 size:1400 time:311ms
ping 36 size:1400 time:311ms
ping 37 size:1400 time:312ms
ping 38 size:1400 time:298ms
ping 39 size:1400 time:266ms
ping 40 size:1400 time:247ms
ping 41 size:1400 time:231ms
ping 42 size:1400 time:254ms
ping 43 size:1400 time:223ms
ping 44 size:1400 time:215ms
ping 45 size:1400 time:225ms
ping 46 size:1400 time:211ms
ping 47 size:1400 time:265ms
ping 48 size:1400 time:234ms
ping 49 size:1400 time:208ms
ping 50 size:1400 time:209ms
ping 51 size:1400 time:218ms
ping 52 size:1400 time:201ms
ping 53 size:1400 time:196ms
ping 54 size:1400 time:198ms
ping 55 size:1400 time:202ms
ping 56 size:1400 time:198ms
ping 57 size:1400 time:181ms
ping 58 size:1400 time:180ms
ping 59 size:1400 time:181ms
ping 60 size:1400 time:184ms
ping 61 size:1400 time:194ms
ping 62 size:1400 time:180ms
ping 63 size:1400 time:181ms
ping 64 size:1400 time:228ms
ping 65 size:1400 time:179ms
ping 66 size:1400 time:180ms
ping 67 size:1400 time:180ms
ping 68 size:1400 time:200ms
ping 69 size:1400 time:188ms
ping 70 size:1400 time:179ms
ping 71 size:1400 time:180ms
ping 72 size:1400 time:189ms
ping 73 size:1400 time:181ms
ping 74 size:1400 time:180ms
ping 75 size:1400 time:181ms
ping 76 size:1400 time:181ms
ping 77 size:1400 time:239ms
ping 78 size:1400 time:189ms
79 超时
ping 80 size:1400 time:225ms
ping 81 size:1400 time:179ms
ping 82 size:1400 time:192ms
ping 83 size:1400 time:308ms
ping 84 size:1400 time:190ms
ping 85 size:1400 time:185ms
ping 86 size:1400 time:186ms
ping 87 size:1400 time:190ms
ping 88 size:1400 time:183ms
ping 89 size:1400 time:179ms
ping 90 size:1400 time:182ms
ping 91 size:1400 time:181ms
ping 92 size:1400 time:180ms
ping 93 size:1400 time:183ms
ping 94 size:1400 time:182ms
ping 95 size:1400 time:182ms
ping 96 size:1400 time:179ms
ping 97 size:1400 time:184ms
ping 98 size:1400 time:180ms
ping 99 size:1400 time:179ms
ping 100 size:1400 time:181ms
ping 101 size:1400 time:181ms
ping 102 size:1400 time:181ms
ping 103 size:1400 time:180ms
ping 104 size:1400 time:184ms
ping 105 size:1400 time:180ms
ping 106 size:1400 time:182ms
ping 107 size:1400 time:180ms
ping 108 size:1400 time:180ms
ping 109 size:1400 time:182ms
ping 110 size:1400 time:179ms
ping 111 size:1400 time:180ms
ping 112 size:1400 time:180ms
ping 113 size:1400 time:180ms
ping 114 size:1400 time:180ms
ping 115 size:1400 time:179ms
ping 116 size:1400 time:181ms
ping 117 size:1400 time:184ms
ping 118 size:1400 time:180ms
ping 119 size:1400 time:180ms
ping 120 size:1400 time:180ms
ping 121 size:1400 time:183ms
ping 122 size:1400 time:180ms
ping 123 size:1400 time:181ms
ping 124 size:1400 time:180ms
ping 125 size:1400 time:181ms
ping 126 size:1400 time:179ms
ping 127 size:1400 time:181ms
ping 128 size:1400 time:180ms
ping 129 size:1400 time:180ms
ping 130 size:1400 time:181ms
ping 131 size:1400 time:181ms
ping 132 size:1400 time:180ms
ping 133 size:1400 time:182ms
ping 134 size:1400 time:182ms
ping 135 size:1400 time:180ms
ping 136 size:1400 time:182ms
ping 137 size:1400 time:191ms
ping 138 size:1400 time:187ms
ping 139 size:1400 time:181ms
ping 140 size:1400 time:179ms
ping 141 size:1400 time:183ms
ping 142 size:1400 time:220ms
ping 143 size:1400 time:191ms
ping 144 size:1400 time:184ms
ping 145 size:1400 time:185ms
ping 146 size:1400 time:192ms
ping 147 size:1400 time:182ms
ping 148 size:1400 time:180ms
ping 149 size:1400 time:180ms
ping 150 size:1400 time:180ms
ping 151 size:1400 time:181ms
ping 152 size:1400 time:181ms
ping 153 size:1400 time:180ms
ping 154 size:1400 time:182ms
ping 155 size:1400 time:183ms
ping 156 size:1400 time:179ms
ping 157 size:1400 time:182ms
ping 158 size:1400 time:216ms
ping 159 size:1400 time:181ms
ping 160 size:1400 time:180ms
ping 161 size:1400 time:180ms
ping 162 size:1400 time:227ms
ping 163 size:1400 time:218ms
ping 164 size:1400 time:244ms
ping 165 size:1400 time:315ms
ping 166 size:1400 time:310ms
ping 167 size:1400 time:314ms
ping 168 size:1400 time:312ms
ping 169 size:1400 time:312ms
ping 170 size:1400 time:313ms
ping 171 size:1400 time:311ms
ping 172 size:1400 time:313ms
ping 173 size:1400 time:312ms
ping 174 size:1400 time:311ms
ping 175 size:1400 time:313ms
ping 176 size:1400 time:313ms
ping 177 size:1400 time:309ms
ping 178 size:1400 time:300ms
ping 179 size:1400 time:286ms
ping 180 size:1400 time:272ms
ping 181 size:1400 time:261ms
ping 182 size:1400 time:254ms
ping 183 size:1400 time:242ms
ping 184 size:1400 time:229ms
ping 185 size:1400 time:203ms
ping 186 size:1400 time:186ms
ping 187 size:1400 time:179ms
ping 188 size:1400 time:180ms
ping 189 size:1400 time:180ms
ping 190 size:1400 time:181ms
ping 191 size:1400 time:179ms
ping 192 size:1400 time:181ms
ping 193 size:1400 time:180ms
ping 194 size:1400 time:181ms
ping 195 size:1400 time:180ms
ping 196 size:1400 time:180ms
ping 197 size:1400 time:180ms
ping 198 size:1400 time:180ms
ping 199 size:1400 time:181ms
ping 200 size:1400 time:182ms
ping 201 size:1400 time:181ms
ping 202 size:1400 time:185ms
ping 203 size:1400 time:180ms
ping 204 size:1400 time:180ms
ping 205 size:1400 time:183ms
ping 206 size:1400 time:182ms
ping 207 size:1400 time:183ms
ping 208 size:1400 time:182ms
ping 209 size:1400 time:181ms
ping 210 size:1400 time:181ms
ping 211 size:1400 time:182ms
ping 212 size:1400 time:183ms
ping 213 size:1400 time:181ms
ping 214 size:1400 time:181ms
ping 215 size:1400 time:182ms
ping 216 size:1400 time:183ms
ping 217 size:1400 time:181ms
ping 218 size:1400 time:180ms
ping 219 size:1400 time:183ms
ping 220 size:1400 time:194ms
ping 221 size:1400 time:197ms
ping 222 size:1400 time:202ms
ping 223 size:1400 time:222ms
ping 224 size:1400 time:221ms
ping 225 size:1400 time:181ms
ping 226 size:1400 time:181ms
ping 227 size:1400 time:181ms
ping 228 size:1400 time:186ms
ping 229 size:1400 time:182ms
ping 230 size:1400 time:180ms
ping 231 size:1400 time:180ms
ping 232 size:1400 time:195ms
ping 233 size:1400 time:188ms
ping 234 size:1400 time:193ms
ping 235 size:1400 time:197ms
ping 236 size:1400 time:198ms
ping 237 size:1400 time:213ms
ping 238 size:1400 time:198ms
ping 239 size:1400 time:196ms
ping 240 size:1400 time:193ms
ping 241 size:1400 time:189ms
ping 242 size:1400 time:199ms
ping 243 size:1400 time:209ms
ping 244 size:1400 time:211ms
ping 245 size:1400 time:222ms
ping 246 size:1400 time:224ms
ping 247 size:1400 time:246ms
ping 248 size:1400 time:279ms
249 超时
250 超时
ping 251 size:1400 time:281ms
ping 252 size:1400 time:281ms
ping 253 size:1400 time:283ms
ping 254 size:1400 time:283ms
ping 255 size:1400 time:280ms
ping 256 size:1400 time:284ms
ping 257 size:1400 time:287ms
ping 258 size:1400 time:285ms
259 超时
ping 260 size:1400 time:336ms
ping 261 size:1400 time:294ms
262 超时
ping 263 size:1400 time:315ms
ping 264 size:1400 time:312ms
ping 265 size:1400 time:276ms
ping 266 size:1400 time:266ms
ping 267 size:1400 time:256ms
ping 268 size:1400 time:256ms
ping 269 size:1400 time:268ms
ping 270 size:1400 time:281ms
ping 271 size:1400 time:282ms
ping 272 size:1400 time:280ms
ping 273 size:1400 time:281ms
ping 274 size:1400 time:282ms
ping 275 size:1400 time:282ms
ping 276 size:1400 time:281ms
ping 277 size:1400 time:281ms
ping 278 size:1400 time:281ms
ping 279 size:1400 time:282ms
ping 280 size:1400 time:282ms
ping 281 size:1400 time:280ms
ping 282 size:1400 time:282ms
ping 283 size:1400 time:281ms
ping 284 size:1400 time:280ms
ping 285 size:1400 time:284ms
ping 286 size:1400 time:283ms
ping 287 size:1400 time:281ms
ping 288 size:1400 time:282ms
ping 289 size:1400 time:275ms
ping 290 size:1400 time:266ms
ping 291 size:1400 time:262ms
ping 292 size:1400 time:262ms
ping 293 size:1400 time:262ms
ping 294 size:1400 time:266ms
ping 295 size:1400 time:264ms
ping 296 size:1400 time:267ms
ping 297 size:1400 time:272ms
ping 298 size:1400 time:279ms
ping 299 size:1400 time:283ms
ping 300 size:1400 time:282ms
ping 301 size:1400 time:282ms
ping 302 size:1400 time:280ms
ping 303 size:1400 time:281ms
ping 304 size:1400 time:279ms
ping 305 size:1400 time:286ms
ping 306 size:1400 time:280ms
ping 307 size:1400 time:280ms
ping 308 size:1400 time:276ms
ping 309 size:1400 time:270ms
ping 310 size:1400 time:264ms
ping 311 size:1400 time:272ms
ping 312 size:1400 time:278ms
ping 313 size:1400 time:280ms
ping 314 size:1400 time:281ms
ping 315 size:1400 time:280ms
ping 316 size:1400 time:276ms
ping 317 size:1400 time:257ms
ping 318 size:1400 time:236ms
ping 319 size:1400 time:228ms
ping 320 size:1400 time:210ms
ping 321 size:1400 time:209ms
ping 322 size:1400 time:201ms
ping 323 size:1400 time:182ms
ping 324 size:1400 time:183ms
ping 325 size:1400 time:179ms
ping 326 size:1400 time:181ms
ping 327 size:1400 time:180ms
ping 328 size:1400 time:182ms
ping 329 size:1400 time:182ms
ping 330 size:1400 time:180ms
ping 331 size:1400 time:180ms
ping 332 size:1400 time:180ms
ping 333 size:1400 time:181ms
ping 334 size:1400 time:180ms
ping 335 size:1400 time:181ms
ping 336 size:1400 time:180ms
ping 337 size:1400 time:179ms
ping 338 size:1400 time:180ms
ping 339 size:1400 time:179ms
ping 340 size:1400 time:181ms
ping 341 size:1400 time:178ms
ping 342 size:1400 time:181ms
ping 343 size:1400 time:180ms
ping 344 size:1400 time:179ms
ping 345 size:1400 time:180ms
ping 346 size:1400 time:181ms
ping 347 size:1400 time:184ms
ping 348 size:1400 time:180ms
ping 349 size:1400 time:180ms
ping 350 size:1400 time:180ms
ping 351 size:1400 time:180ms
ping 352 size:1400 time:181ms
ping 353 size:1400 time:179ms
ping 354 size:1400 time:180ms
ping 355 size:1400 time:181ms
ping 356 size:1400 time:180ms
ping 357 size:1400 time:180ms
ping 358 size:1400 time:181ms
ping 359 size:1400 time:180ms
ping 360 size:1400 time:179ms
ping 361 size:1400 time:180ms
ping 362 size:1400 time:180ms
ping 363 size:1400 time:180ms
ping 364 size:1400 time:180ms
ping 365 size:1400 time:180ms
ping 366 size:1400 time:180ms
ping 367 size:1400 time:181ms
ping 368 size:1400 time:181ms
ping 369 size:1400 time:183ms
ping 370 size:1400 time:182ms
ping 371 size:1400 time:181ms
ping 372 size:1400 time:183ms
ping 373 size:1400 time:182ms
ping 374 size:1400 time:180ms
ping 375 size:1400 time:184ms
ping 376 size:1400 time:182ms
ping 377 size:1400 time:181ms
ping 378 size:1400 time:180ms
ping 379 size:1400 time:182ms
ping 380 size:1400 time:182ms
ping 381 size:1400 time:182ms
ping 382 size:1400 time:180ms
ping 383 size:1400 time:180ms
ping 384 size:1400 time:180ms
ping 385 size:1400 time:183ms
ping 386 size:1400 time:179ms
ping 387 size:1400 time:180ms
ping 388 size:1400 time:179ms
ping 389 size:1400 time:183ms
ping 390 size:1400 time:180ms
ping 391 size:1400 time:180ms
ping 392 size:1400 time:182ms
ping 393 size:1400 time:180ms
ping 394 size:1400 time:184ms
ping 395 size:1400 time:181ms
ping 396 size:1400 time:181ms
ping 397 size:1400 time:179ms
ping 398 size:1400 time:184ms
ping 399 size:1400 time:180ms
ping 400 size:1400 time:180ms
ping 401 size:1400 time:180ms
ping 402 size:1400 time:180ms
ping 403 size:1400 time:185ms
ping 404 size:1400 time:180ms
ping 405 size:1400 time:180ms
ping 406 size:1400 time:179ms
ping 407 size:1400 time:180ms
ping 408 size:1400 time:180ms
ping 409 size:1400 time:181ms
ping 410 size:1400 time:181ms
ping 411 size:1400 time:179ms
ping 412 size:1400 time:180ms
ping 413 size:1400 time:183ms
ping 414 size:1400 time:180ms
ping 415 size:1400 time:180ms
ping 416 size:1400 time:180ms
ping 417 size:1400 time:180ms
ping 418 size:1400 time:181ms
ping 419 size:1400 time:179ms
ping 420 size:1400 time:180ms
ping 421 size:1400 time:180ms
ping 422 size:1400 time:180ms
ping 423 size:1400 time:180ms
ping 424 size:1400 time:179ms
ping 425 size:1400 time:181ms
ping 426 size:1400 time:180ms
ping 427 size:1400 time:179ms
ping 428 size:1400 time:181ms
ping 429 size:1400 time:179ms
ping 430 size:1400 time:180ms
ping 431 size:1400 time:180ms
ping 432 size:1400 time:179ms
ping 433 size:1400 time:181ms
ping 434 size:1400 time:180ms
ping 435 size:1400 time:180ms
ping 436 size:1400 time:179ms
ping 437 size:1400 time:181ms
ping 438 size:1400 time:181ms
ping 439 size:1400 time:181ms
ping 440 size:1400 time:180ms
ping 441 size:1400 time:182ms
ping 442 size:1400 time:180ms
ping 443 size:1400 time:180ms
ping 444 size:1400 time:180ms
ping 445 size:1400 time:179ms
ping 446 size:1400 time:181ms
ping 447 size:1400 time:180ms
ping 448 size:1400 time:180ms
ping 449 size:1400 time:180ms
ping 450 size:1400 time:179ms
ping 451 size:1400 time:180ms
ping 452 size:1400 time:181ms
ping 453 size:1400 time:186ms
ping 454 size:1400 time:202ms
ping 455 size:1400 time:209ms
ping 456 size:1400 time:208ms
ping 457 size:1400 time:209ms
ping 458 size:1400 time:203ms
ping 459 size:1400 time:205ms
ping 460 size:1400 time:207ms
ping 461 size:1400 time:202ms
ping 462 size:1400 time:199ms
ping 463 size:1400 time:198ms
ping 464 size:1400 time:202ms
ping 465 size:1400 time:205ms
ping 466 size:1400 time:209ms
ping 467 size:1400 time:207ms
ping 468 size:1400 time:210ms
ping 469 size:1400 time:202ms
ping 470 size:1400 time:203ms
ping 471 size:1400 time:206ms
ping 472 size:1400 time:207ms
ping 473 size:1400 time:209ms
ping 474 size:1400 time:209ms
ping 475 size:1400 time:197ms
ping 476 size:1400 time:191ms
ping 477 size:1400 time:189ms
ping 478 size:1400 time:190ms
ping 479 size:1400 time:184ms
ping 480 size:1400 time:184ms
ping 481 size:1400 time:192ms
ping 482 size:1400 time:181ms
ping 483 size:1400 time:183ms
ping 484 size:1400 time:184ms
ping 485 size:1400 time:180ms
ping 486 size:1400 time:182ms
ping 487 size:1400 time:180ms
ping 488 size:1400 time:181ms
ping 489 size:1400 time:180ms
ping 490 size:1400 time:181ms
ping 491 size:1400 time:183ms
ping 492 size:1400 time:182ms
ping 493 size:1400 time:182ms
ping 494 size:1400 time:187ms
ping 495 size:1400 time:187ms
ping 496 size:1400 time:187ms
ping 497 size:1400 time:187ms
ping 498 size:1400 time:190ms
ping 499 size:1400 time:192ms

Process finished with exit code 0
"""
    def __init__(self, config):
        UpstreamBase.__init__(self, config)

        self.udp_tunnel_hostname = config.get('host')
        self.udp_tunnel = config.get('port')

        if self.udp_tunnel is None or self.udp_tunnel is None:
            ms = u'[配置错误] host、port 不能为空！ upstream-type:%s' % self.type
            raise ConfigError(ms)

        class socket(SocketBase):
            # TODO: 停掉一些不支持方法。
            def __init__(self, family=_socket.AF_INET, type=_socket.SOCK_STREAM, proto=0, _sock=None):
                if _sock is None:
                    _sock = socket.upstream.socket(family=family, type=type, proto=proto)
                SocketBase.__init__(self, _sock)

        socket.udp_tunnel = self.udp_tunnel
        socket.udp_tunnel = self.udp_tunnel
        socket.upstream = self.upstream

        self.socket = socket

    def create_connection(self, address, timeout=5):
        startTime = int(time.time() * 1000)
        hostname = address[0]
        port = address[1]

        try:
            _sock = self.upstream.create_connection((self.socks5_hostname, self.socks5_port), timeout,)
        except:
            info = traceback.format_exc()
            tcpping = int(time.time() * 1000) - startTime
            logging.warn(u'[socks5] 远程代理服务器连接失败！ socks5_hostname:%s ,socks5_port:%s ,timeout:%s,time:%s' % (
                self.socks5_hostname, self.socks5_port, timeout, tcpping))
            logging.warn('%s\r\n\r\n' % info)
            raise
            raise

        _sock.setsockopt(_socket.IPPROTO_TCP, _socket.TCP_NODELAY, 1)
        _sock.settimeout(timeout * 2)

        tcpping = int(time.time() * 1000) - startTime
        logging.debug(u'[socks5] 远程代理服务器已连接  socks5_hostname:%s ,socks5_port:%s ,timeout:%s,time:%s' % (
            self.socks5_hostname, self.socks5_port, timeout, tcpping))

        # 登录
        _sock.pack('BBB', 0x05, 0x01, 0x00)

        # 登录回应
        ver, method = _sock.unpack( 'BB')
        tcpping = int(time.time() * 1000) - startTime
        if ver != 0x05 or method != 0x00:
            _sock.close(safe=False)
            ms = u'[socks5] 远程代理服务器登录失败！ host:%s ,port:%s, time:%s' % (self.socks5_hostname, self.socks5_port, tcpping)
            raise UpstreamLoginError(ms)
        logging.debug(
            u'[socks5] 远程代理服务器登陆成功。 host:%s ,port:%s ,time:%s' % (self.socks5_hostname, self.socks5_port, tcpping))

        # 请求连接
        atyp = dnslib.get_addr_type(hostname)
        if atyp == 0x01:
            # ipv4
            _sock.pack('!BBBBIH', 0x05, 0x01, 0x00, atyp, struct.unpack('!I', _socket.inet_aton(hostname))[0], port)
        elif atyp == 0x03:
            # 域名
            _sock.pack('!BBBBB%ssH' % len(hostname), 0x05, 0x01, 0x00, atyp, len(hostname), hostname, port)
        elif atyp == 0x04:
            # ipv6
            _str = _socket.inet_pton(_socket.AF_INET6, hostname)
            a, b = struct.unpack('!2Q', _str)
            _sock.pack('!BBBB2QH', 0x05, 0x01, 0x00, atyp, a, b, port)
        else:
            tcpping = int(time.time() * 1000) - startTime
            ms = u'[socks5] 地址类型未知！ atyp:%s ,time:%s' % (atyp, tcpping)
            _sock.close(safe=False)
            assert False, ms

        # 请求回应
        ver, rep, rsv, atyp = _sock.unpack('BBBB')
        if ver != 0x05:
            _sock.close(safe=False)
            raise UpstreamProtocolError(u'未知的服务器协议版本！')
        if rep != 0x00:
            tcpping = int(time.time() * 1000) - startTime
            ms = u'[socks5] 远程代理服务器无法连接目标网站！ ver:%s ,rep:%s， time=%s' % (ver, rep, tcpping)
            _sock.close(safe=False)
            raise _socket.error(10060,
                                (u'[Socks5] 代理服务器无法连接到目的主机。socks5_host = %s, '
                                 u'socks5_port = %s ,host = %s ,port = %s ,rep = %s') %
                                (self.socks5_hostname, self.socks5_port, hostname, port, rep))

        if atyp == 0x01:
            _sock.unpack('!IH')
        elif atyp == 0x03:
            length = _sock.unpack('B')
            _sock.unpack('%ssH' % length)
        elif atyp == 0x04:
            _sock.unpack('!2QH')

        tcpping = int(time.time() * 1000) - startTime
        # TODO: 这里需要记录下本sock连接远程的耗时。

        return self.socket(_sock=_sock)


    def get_display_name(self):
        return '[%s]socks5_hostname=%s,socks5_port=%s' % (self.type,self.socks5_hostname, self.socks5_port)

    def get_name(self):
        return '%s?socks5_hostname=%s&socks5_port=%s' % (self.type,self.socks5_hostname, self.socks5_port)