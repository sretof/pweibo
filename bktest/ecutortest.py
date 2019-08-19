#!/usr/bin/env python3
# -*- coding: utf-8 -*-
__author__ = 'Erik YU'
import logging
import random
import time
from concurrent.futures import ThreadPoolExecutor

import bktest.wbcomptest as wbcmptest
import util.tulog as logger


class WbGTlCmpTest:
    def __init__(self, wbcomp, mlogger=None):
        if mlogger is None:
            mlogger = logger.TuLog('WbGTlCmpTest', '/log', True, logging.DEBUG).getlog()
        self.wbcomp = wbcomp
        self.mlogger = mlogger
        self.downfexecutor = ThreadPoolExecutor(max_workers=1)
        self.vdownfexecutor = ThreadPoolExecutor(max_workers=2)

    def fgrouptl(self, mid, ex, exo):
        if mid.startswith('p'):
            self.downfexecutor.submit(self.wbcomp.downmediat, mid, ex)
        else:
            self.vdownfexecutor.submit(self.wbcomp.downmediat, mid, ex)
        if exo:
            raise Exception('EXXX-fgrouptl')

    def fgroupstl(self):
        midp = ['p1', 'p2', 'p3', 'p4', 'p5', 'p6', 'p7', 'p8', 'p9', 'v1', 'v2', 'v3', 'v4', 'v5', 'v6', 'v7']
        mlen = len(midp) - 1
        for i in range(10):
            self.mlogger.debug('fgroupstl SSSS t:{}'.format(i))
            for j in range(10):
                ridx = random.randint(0, mlen)
                exo = random.randint(0, 1)
                exi = random.randint(0, 1)
                mid = midp[ridx]
                if exi:
                    exi = True
                else:
                    exi = False
                if exo:
                    exo = True
                else:
                    exo = False
                # tmpouuid = self.wbcomp.wbuuid
                try:
                    tmid = str(i) + mid
                    self.mlogger.debug('fgrouptl SSSS t:{},mid:{}'.format(i, mid))
                    self.fgrouptl(tmid, exi, exo)
                    self.mlogger.debug('fgrouptl EEEE t:{},mid:{}'.format(i, mid))
                except Exception as ex:
                    self.mlogger.error('fgrouptl EXEX t:{},mid:{},ex:{}'.format(i, mid, str(ex)))
                    # self.wbcomp.refresh(tmpouuid)
            self.mlogger.debug('fgroupstl EEEE t:{}'.format(i))
            time.sleep(4)


if __name__ == '__main__':
    wbun = 'sretof@live.cn'
    wbpw = '1122aaa'
    mlogger = logger.TuLog('WbGTlCmpTest', '/log', True, logging.DEBUG).getlog()
    owbcomp = wbcmptest.WbCompTest(wbun, wbpw, mlogger=mlogger)
    gtlcmp = WbGTlCmpTest(owbcomp, mlogger=mlogger)
    owbcomp.login()
    gtlcmp.fgroupstl()
