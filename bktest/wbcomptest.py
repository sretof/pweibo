#!/usr/bin/env python3
# -*- coding: utf-8 -*-
__author__ = 'Erik YU'
import logging
import threading
import time
import uuid

import urllib3

import util.tulog as logger

urllib3.disable_warnings()  # 取消警告


class WbCompTest:
    def __init__(self, username, password, proxies=None, picdir='F:\OneDrive\weibopic', mlogger=None):
        if proxies is None:
            proxies = {}
        if mlogger is None:
            mlogger = logger.TuLog('WbCompTest', '/log', True, logging.INFO).getlog()
        self.username = username
        self.password = password
        self.proxies = proxies
        self.picdir = picdir

        self.wbuid = ''
        self.mlogger = mlogger

        self.wblock = threading.Lock()
        self.wbuuid = ''

    def login(self, ouuid='', dmid='', slogger=None, refresh=False):
        if slogger is None:
            slogger = self.mlogger
        tmpoid = self.wbuuid
        self.wblock.acquire()
        if ouuid and ouuid != self.wbuuid:
            self.wblock.release()
            return
        self.wbuuid = str(uuid.uuid1()).replace('-', '')
        self.wblock.release()
        if refresh:
            slogger.debug('refresh:dmid:{},param-ouuid:{},ouuid:{},newouuid:{}'.format(dmid, ouuid, tmpoid, self.wbuuid))
        else:
            slogger.debug('login:param-ouuid:{},ouuid:{},newouuid:{}'.format(ouuid, tmpoid, self.wbuuid))

    def refresh(self, ouuid, dmid='', slogger=None):
        if slogger is None:
            slogger = self.mlogger
        self.login(ouuid, dmid, slogger, True)

    def downmediat(self, mid, ex=False):
        self.wblock.acquire()
        self.wblock.release()
        tmpouuid = self.wbuuid
        dmid = 'mid:' + str(mid)
        dstrs = 'downmedia-SSSS mid:{},wbuuid:{},ex:{}'.format(dmid, self.wbuuid, ex)
        self.mlogger.debug(dstrs)
        time.sleep(2)
        dstre = 'downmedia-EEEE mid:{},wbuuid:{},ex:{}'.format(dmid, self.wbuuid, ex)
        dstrex = 'downmedia-EXEX mid:{},wbuuid:{},ex:{}'.format(dmid, self.wbuuid, ex)
        if ex:
            self.mlogger.error(dstrex)
            self.refresh(tmpouuid, dmid)
            raise Exception('EXXX' + dstre)
        else:
            self.mlogger.debug(dstre)


if __name__ == '__main__':
    glogger = logger.TuLog('wbcomptest', '/../log', True, logging.DEBUG).getlog()
    wbun = 'sretof@live.cn'
    wbpw = '1122aaa'
    wbcomp = WbCompTest(wbun, wbpw)
    wbcomp.login()
    wbcomp.refresh(wbcomp.wbuuid)
    wbcomp.refresh('ooo')
    wbcomp.downmediat(1)
    wbcomp.downmediat(2, True)
