#!/usr/bin/python
# -*- coding: utf-8 -*-
# utf-8 中文编码


class UpstreamBase(object):

    def __init__(self,config):
        self.type = config.get('type',None)
        pass

    def get_display_name(self):
        return self.get_name()

    def get_name(self):
        return '%s-host:port'%(self.type)